# -*- coding: utf-8 -*-
"""LEARNREV P0 T2 (G2, ledger LR-R2) — "Open the lesson" opens THIS screen's
lesson.

`coach.js openLesson()` used to open the lesson map at the top for every
screen. It now resolves a station: (1) the station whose key is the screen's
key, else the station a retired screen folded into (`station_aliases`), else
the station whose lesson walks the screen; (2) for a button under an answer,
the station its `show_me` anchors / walkthrough point at; (3) else the map,
with a note. This test mirrors rung (1) on the content plane and pins the
client code that implements it.

Source-only, like test_onechat_content: no database read.
"""
import os

from odoo.tests.common import TransactionCase, tagged

from .common import ADDON, load_content

#: Content screens with no station of the SAME key. Each one still opens a
#: lesson through rung (1)'s later steps — named here so a new screen without
#: a station is a decision, not an accident.
NO_OWN_STATION = {
    # retired stations, folded (`station_aliases`)
    'contracts': 'employees', 'proration': 'adjust', 'retro': 'adjust',
    # a step of another station's lesson is on this screen
    'importwizard': 'import', 'blueprint_rules': 'blueprint',
    'mapping_sheet': 'mapping', 'matrix_builder': 'matrix',
    'hiring_request': 'hiring', 'hiringnumbers': 'hiringsetup',
    'filing_flow': 'govreports',
    # no lesson yet: the drawer says so and opens the lesson map
    'wftimeoff': '', 'wfovertime': '',
}


def _station_for(tree, screen):
    """Rung (1) of coach.js `_lessonStationFor`, in Python."""
    keys = {s['key'] for s in tree['stations']}
    if screen.startswith('hub_'):
        return ''
    if screen in keys:
        return screen
    alias = (tree.get('station_aliases') or {}).get(screen)
    if alias in keys:
        return alias
    for st in tree['stations']:
        for lesson in st.get('lessons') or []:
            if any(step.get('screen') == screen for step in lesson.get('steps') or []):
                return st['key']
    return ''


@tagged('post_install', '-at_install')
class TestLearnrevLessonDoor(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tree = load_content()
        with open(os.path.join(ADDON, 'static', 'src', 'coach', 'coach.js'),
                  encoding='utf-8') as fh:
            cls.coach = fh.read()

    def test_01_every_content_screen_has_its_own_station_or_is_listed(self):
        stations = {s['key'] for s in self.tree['stations']}
        content = [s['key'] for s in self.tree['screens'] if not s['key'].startswith('hub_')]
        self.assertEqual(len(content), 54, 'the content screen count moved: review the list')
        missing = sorted(k for k in content if k not in stations)
        self.assertEqual(missing, sorted(NO_OWN_STATION))

    def test_02_the_client_rule_lands_where_the_list_says(self):
        for screen, expected in NO_OWN_STATION.items():
            self.assertEqual(_station_for(self.tree, screen), expected, screen)
        for s in self.tree['screens']:
            key = s['key']
            if key.startswith('hub_'):
                self.assertEqual(_station_for(self.tree, key), '', key)
            elif key not in NO_OWN_STATION:
                self.assertEqual(_station_for(self.tree, key), key, key)

    def test_03_the_drawer_opens_the_station_and_never_lands_silently(self):
        start = self.coach.index('    openLesson(answer) {')
        body = self.coach[start:self.coach.index('\n    }\n', start)]
        self.assertIn('openLearn(this.action, `station:${key}`)', body)
        # The map without a key only after the drawer said so.
        self.assertLess(body.index('NO_LESSON_NOTE'), body.index('openLearn(this.action, "")'))
        self.assertIn('station_aliases: content.station_aliases', self.coach)
        self.assertIn('this.openLesson(turn && turn.answer)', self.coach)
