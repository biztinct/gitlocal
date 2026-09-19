# -*- coding: utf-8 -*-
"""SCHEMECTX P3 — Settings is a DOOR now, and nothing was lost behind it.

The studio's Settings tab used to open a panel of its own: five sub-tabs of
fields beside the components grid, plus an action bar that was the only place
in the product where five things could be pressed. Settings now opens the
guided journey in edit mode, and the panel is retired — so two claims have to
be true and neither has a runtime handle to grab.

**The door is wired the way the hand-off law says it is** (BP-R8, BP14): the
tab calls `bp_adopt` first, opens `pb_blueprint` BY TAG with `config_id` and
`mode`, carries a `pb_back`, and falls back rather than dead-ending when the
journey module is not installed.

**Nothing the old panel owned has been dropped.** The five actions that lived
only in its action bar — back to draft, retire, simulate, refresh the formulas,
import from Excel — each have a home somewhere a person can reach, and the
Intelligence sub-tab has a tab of its own. Owner ruling 2026-09-19.

Source assertions, in the shape `test_one_mapping_home.py` established: the
thing being protected is a wiring decision.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _read(*parts):
    path = os.path.join(get_module_path('pb_formula_studio'), *parts)
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestSchemeCtxP3SettingsDoor(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.js = _read('static', 'src', 'js', 'formula_studio.js')
        cls.xml = _read('static', 'src', 'xml', 'studio.xml')
        cls.door = cls.js[cls.js.index('async openSettings()'):
                          cls.js.index('async openSettingsPanel()')]

    # ==================================================================
    # 14 — the door itself
    # ==================================================================
    def test_14a_settings_adopts_then_opens_the_journey(self):
        self.assertIn("'pb.blueprint.studio', \"bp_adopt\"",
                      self.door.replace('"pb.blueprint.studio"',
                                        "'pb.blueprint.studio'"),
                      "Settings has to enter edit mode before it opens it")
        self.assertIn('tag: "pb_blueprint"', self.door)
        self.assertLess(self.door.index('bp_adopt'), self.door.index('doAction'),
                        "the journey is opened AFTER the configuration is adopted")

    def test_14b_it_opens_by_tag_and_carries_the_way_back(self):
        # BP14: opened by xmlid the URL becomes /odoo/action-<id> and every
        # extra parameter is dropped, so the refresh would lose the scheme.
        self.assertNotIn('xmlid', self.door)
        self.assertIn('type: "ir.actions.client"', self.door)
        for key in ('config_id: cid', 'mode: adopted.mode', 'pb_back'):
            self.assertIn(key, self.door, "the door lost %s" % key)

    def test_14c_a_journey_that_is_not_there_falls_back(self):
        self.assertIn('registry.category("actions").contains("pb_blueprint")',
                      self.door,
                      "the studio must probe: pb_blueprint depends on it, "
                      "not the other way round")
        self.assertIn('openSettingsPanel()', self.door,
                      "a door with nothing behind it is a dead end")
        # A refusal WITH a reason is an answer, not a reason to show a second
        # screen that would refuse the same thing in different words.
        self.assertIn('adopted.reason', self.door)

    def test_14d_every_other_way_in_goes_through_the_same_door(self):
        # The arrival parameter from a configuration row, and the command
        # palette row. Two more doors that must not reach the panel directly.
        self.assertIn('await this.openSettings();', self.js)
        palette = re.search(r'add\("view\.settings".*', self.js)
        self.assertTrue(palette, "the palette lost its Settings row")
        self.assertIn('this.openSettings()', palette.group(0),
                      "the palette row still opened the old panel")

    # ==================================================================
    # Nothing the panel owned was dropped (owner ruling 2026-09-19)
    # ==================================================================
    def test_15a_the_two_lifecycle_moves_live_beside_the_state(self):
        chip = self.xml[self.xml.index('pbfs-statewrap'):
                        self.xml.index('pbfs-branchchip')]
        self.assertIn("pickStateAction('draft')", chip)
        self.assertIn("pickStateAction('archive')", chip)
        # Both words are whole sentences in JS, never text split around a
        # `t-esc`: a label a QWeb expression builds is a label the extractor
        # never sees, and it stays English for ever (BP54's cousin).
        self.assertIn('t-esc="retireVerb"', chip)
        self.assertIn('t-esc="stageLine"', chip)
        # And the handlers are the SAME ones the panel called, so the
        # confirmation and the approval route are unchanged.
        action = self.js[self.js.index('async pickStateAction('):
                         self.js.index('    setView(v) {')]
        self.assertIn('this.setDraftCfg()', action)
        self.assertIn('this.archiveCfg()', action)

    def test_15b_the_three_tools_live_in_the_command_centre(self):
        lanes = self.js[self.js.index('get commandLanes()'):
                        self.js.index('get commandView()')]
        for key, handler in (('"simulate"', 'this.openSimulate()'),
                             ('"regenerate"', 'this.regenerateFormulas()'),
                             ('"importexcel"', 'this.importExcelCfg()')):
            self.assertIn(key, lanes, "%s has no lane" % key)
            self.assertIn(handler, lanes, "%s is not wired" % key)
        # Every lane card draws its glyph from one registry; a tool with no
        # glyph renders an empty box.
        for key in ('simulate', 'regenerate', 'importexcel'):
            self.assertIn("icon === '%s'" % key, self.xml,
                          "%s has no glyph in CmdIco" % key)

    def test_15c_the_intelligence_sub_tab_became_a_tab(self):
        self.assertIn("state.view === 'health'", self.xml)
        self.assertIn('t-on-click="openHealth"', self.xml)
        health = self.xml[self.xml.index("<t t-elif=\"state.view === 'health'\">"):
                          self.xml.index("<!-- ============ TEST &amp; VALIDATE")]
        for piece in ('Execution order', 'Unused components',
                      'Circular references'):
            self.assertIn(piece, health, "the Health tab lost %r" % piece)

    def test_15d_nothing_a_person_reads_on_the_new_surfaces_is_branded(self):
        health = self.xml[self.xml.index("<t t-elif=\"state.view === 'health'\">"):
                          self.xml.index("<!-- ============ TEST &amp; VALIDATE")]
        chip = self.xml[self.xml.index('pbfs-statewrap'):
                        self.xml.index('pbfs-branchchip')]
        for blob in (health, chip):
            self.assertNotIn('Odoo', blob)
            # The word on screen is "configuration" (BLUEPRINT vocabulary).
            self.assertNotIn('schema', blob.lower())
