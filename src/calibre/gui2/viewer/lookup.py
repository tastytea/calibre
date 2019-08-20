#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys

from PyQt5.Qt import (
    QApplication, QComboBox, QHBoxLayout, QLabel, Qt, QTimer, QUrl, QVBoxLayout,
    QWidget
)
from PyQt5.QtWebEngineWidgets import (
    QWebEnginePage, QWebEngineProfile, QWebEngineView
)

from calibre import prints, random_user_agent
from calibre.constants import cache_dir
from calibre.gui2.viewer.web_view import vprefs
from calibre.gui2.webengine import create_script, insert_scripts, secure_webengine

vprefs.defaults['lookup_locations'] = [
    {
        'name': 'Google dictionary',
        'url': 'https://google.com/search?q=define:{word}',
        'langs': [],
    },

    {
        'name': 'Google search',
        'url':  'https://google.com/search?q={word}',
        'langs': [],
    },

    {
        'name': 'Wordnik',
        'url':  'https://www.wordnik.com/words/{word}',
        'langs': ['eng'],
    },
]
vprefs.defaults['lookup_location'] = 'Google dictionary'


def create_profile():
    ans = getattr(create_profile, 'ans', None)
    if ans is None:
        ans = QWebEngineProfile('viewer-lookup', QApplication.instance())
        ans.setHttpUserAgent(random_user_agent(allow_ie=False))
        ans.setCachePath(os.path.join(cache_dir(), 'ev2vl'))
        js = P('lookup.js', data=True, allow_user_override=False)
        insert_scripts(ans, create_script('lookup.js', js))
        s = ans.settings()
        s.setDefaultTextEncoding('utf-8')
        create_profile.ans = ans
    return ans


class Page(QWebEnginePage):

    def javaScriptConsoleMessage(self, level, msg, linenumber, source_id):
        prefix = {QWebEnginePage.InfoMessageLevel: 'INFO', QWebEnginePage.WarningMessageLevel: 'WARNING'}.get(
                level, 'ERROR')
        if source_id == 'userscript:lookup.js':
            prints('%s: %s:%s: %s' % (prefix, source_id, linenumber, msg), file=sys.stderr)
            sys.stderr.flush()


class Lookup(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.is_visible = False
        self.selected_text = ''
        self.current_query = ''
        self.current_source = ''
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        self.debounce_timer = t = QTimer(self)
        t.setInterval(150), t.timeout.connect(self.update_query)
        self.source_box = sb = QComboBox(self)
        self.label = la = QLabel(_('Lookup &in:'))
        h.addWidget(la), h.addWidget(sb), la.setBuddy(sb)
        self.view = QWebEngineView(self)
        self._page = Page(create_profile(), self.view)
        secure_webengine(self._page, for_viewer=True)
        self.view.setPage(self._page)
        l.addWidget(self.view)
        self.populate_sources()
        self.source_box.currentIndexChanged.connect(self.source_changed)
        self.view.setHtml('<p>' + _('Double click on a word in the viewer window'
            ' to look it up.'))

    def source_changed(self):
        vprefs['lookup_location'] = self.source['name']
        self.update_query()

    def populate_sources(self):
        sb = self.source_box
        sb.clear()
        for item in vprefs['lookup_locations']:
            sb.addItem(item['name'], item)
        idx = sb.findText(vprefs['lookup_location'], Qt.MatchExactly)
        if idx > -1:
            sb.setCurrentIndex(idx)

    def visibility_changed(self, is_visible):
        self.is_visible = is_visible
        self.update_query()

    @property
    def source(self):
        idx = self.source_box.currentIndex()
        if idx > -1:
            return self.source_box.itemData(idx)

    @property
    def url_template(self):
        idx = self.source_box.currentIndex()
        if idx > -1:
            return self.source_box.itemData(idx)['url']

    def update_query(self):
        self.debounce_timer.stop()
        query = self.selected_text or self.current_query
        if self.current_query == query and self.current_source == self.url_template:
            return
        if not self.is_visible or not query:
            return
        self.current_source = self.url_template
        url = self.current_source.format(word=query)
        self.view.load(QUrl(url))
        self.current_query = query

    def selected_text_changed(self, text):
        self.selected_text = text or ''
        self.debounce_timer.start()