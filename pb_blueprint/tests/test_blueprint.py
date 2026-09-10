# -*- coding: utf-8 -*-
"""What the guided setup promises, asserted.

The promises worth a test are the ones whose failure is invisible on screen:
that pressing Continue twice makes ONE configuration, that a failed seed leaves
NOTHING behind, that another company's draft cannot be opened, and that
finishing refuses a configuration whose formulas do not compute.
"""
import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBlueprint(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.blueprint.studio']
        cls.Blueprint = cls.env['pb.formula.blueprint']
        cls.Config = cls.env['hr.formula.config']
        cls.company = cls.env.company
        cls.vn_tpl = cls.env['hr.formula.config.template'].sudo().search(
            [('code', '=', 'vn_standard_2026'), ('state', '!=', 'superseded')], limit=1)

    # ------------------------------------------------------------------
    def _start(self, token, **over):
        vals = {
            'name': over.pop('name', 'Test configuration'),
            'country_code': 'VN',
            'cycle_type': 'regular',
            'effective_from': '2026-10-01',
            'template_key': over.pop('template_key', 'blank'),
            'situations': {'audiences': ['local'], 'reallife': ['joiners']},
        }
        vals.update(over)
        return self.Studio.bp_start(vals, token)

    # ---- 1 ----------------------------------------------------------
    def test_bp_start_idempotent(self):
        """The same setup key never makes a second configuration."""
        before = self.Config.search_count([])
        first = self._start('tok-idem')
        self.assertTrue(first['ok'], first.get('reason'))
        second = self._start('tok-idem', name='A different name')
        self.assertTrue(second['ok'])
        self.assertEqual(first['config_id'], second['config_id'],
                         "a repeated press must resolve to the same draft")
        self.assertEqual(self.Config.search_count([]), before + 1)
        self.assertEqual(self.Blueprint.search_count([('token', '=', 'tok-idem')]), 1)

    # ---- 2 ----------------------------------------------------------
    def test_bp_start_seeds_starter(self):
        if not self.vn_tpl:
            self.skipTest("the Vietnam rule pack is not installed on this database")
        res = self._start('tok-seed', template_key='vn_standard_2026')
        self.assertTrue(res['ok'], res.get('reason'))
        config = self.Config.browse(res['config_id'])
        expected = len(self.vn_tpl._components())
        self.assertEqual(res['rule_count'], expected)
        self.assertEqual(len(config.rule_ids), expected)
        self.assertTrue(config.rate_table_ids, "the rule pack brings its rate table")
        self.assertTrue(config.sample_data_ids, "a sample employee must exist")
        self.assertEqual(config.state, 'draft')
        self.assertEqual(config.company_id, self.company,
                         "the draft is filed under the company on screen")

    # ---- 3 ----------------------------------------------------------
    def test_bp_start_blank(self):
        res = self._start('tok-blank', template_key='blank')
        self.assertTrue(res['ok'], res.get('reason'))
        config = self.Config.browse(res['config_id'])
        self.assertEqual(len(config.rule_ids), 0)
        self.assertEqual(len(config.sample_data_ids), 1,
                         "even an empty canvas gets somebody for the pay panel")
        blueprint = self.Blueprint.search([('config_id', '=', config.id)])
        self.assertEqual(blueprint.step, 'rules',
                         "creation lands you on the step after Start")
        self.assertEqual(blueprint.state, 'draft')

    # ---- 4 ----------------------------------------------------------
    def test_bp_start_failure_rolls_back(self):
        """A starter that cannot be found leaves NOTHING behind."""
        before = self.Config.search_count([])
        res = self._start('tok-bad', template_key='no_such_starter_2026')
        self.assertFalse(res['ok'])
        self.assertIn('starting point', res['reason'].lower())
        self.assertEqual(self.Config.search_count([]), before,
                         "a refused start must not half-create a configuration")
        self.assertFalse(self.Blueprint.search([('token', '=', 'tok-bad')]))

    # ---- 5 ----------------------------------------------------------
    def test_bp_load_refuses_other_company(self):
        other = self.env['res.company'].create({'name': 'BP Other Co'})
        res = self._start('tok-comp')
        self.assertTrue(res['ok'], res.get('reason'))
        config = self.Config.browse(res['config_id'])
        config.company_id = other

        # Reading it while standing in another company is a normal, explainable
        # situation: a sentence and a next step, not a traceback.
        as_both = self.Studio.with_company(self.company).with_context(
            allowed_company_ids=[self.company.id, other.id])
        refusal = as_both.bp_load(config.id)
        self.assertFalse(refusal['ok'])
        self.assertIn(other.name, refusal['reason'])

        # A company the user cannot reach at all is refused the SAME way. The
        # record rule is still the security boundary — no data crosses — but
        # the framework's own AccessError text must never reach a person: it
        # names the technical model, is not white-labelled, and jokes about
        # cookies. The only fact worth passing on is which company to switch to.
        as_one = self.Studio.with_context(allowed_company_ids=[self.company.id])
        blocked = as_one.bp_load(config.id)
        self.assertFalse(blocked['ok'])
        self.assertIn(other.name, blocked['reason'])
        for banned in ('hr.formula.config', 'cookies', 'Odoo', 'access to:'):
            self.assertNotIn(banned, blocked['reason'])
        self.assertNotIn('config', blocked)
        self.assertNotIn('blueprint', blocked)

    # ---- 6 ----------------------------------------------------------
    def test_bp_save_revision_conflict(self):
        res = self._start('tok-rev')
        cid = res['config_id']
        blueprint = self.Blueprint.search([('config_id', '=', cid)])
        stale = blueprint.revision

        ok = self.Studio.bp_save(cid, {'name': 'Renamed once'}, stale)
        self.assertTrue(ok['ok'])
        self.assertEqual(ok['revision'], stale + 1)
        self.assertEqual(self.Config.browse(cid).name, 'Renamed once')

        clash = self.Studio.bp_save(cid, {'name': 'Renamed twice'}, stale)
        self.assertFalse(clash['ok'])
        self.assertTrue(clash.get('conflict'))
        self.assertEqual(self.Config.browse(cid).name, 'Renamed once',
                         "a stale write must change nothing")

    # ---- 7 ----------------------------------------------------------
    def test_bp_preview_lines(self):
        if not self.vn_tpl:
            self.skipTest("the Vietnam rule pack is not installed on this database")
        res = self._start('tok-prev', template_key='vn_standard_2026')
        cid = res['config_id']
        preview = self.Studio.bp_preview(cid, res['sample_id'])
        self.assertTrue(preview['ok'], preview.get('reason'))
        self.assertEqual(preview['take_home']['code'], 'NET')
        self.assertIsNotNone(preview['take_home']['value'])
        keys = [line['key'] for line in preview['lines']]
        self.assertEqual(keys, ['cash', 'deductions', 'tax', 'employer'])
        by_key = {line['key']: line for line in preview['lines']}
        self.assertEqual(by_key['cash']['code'], 'GROSS')
        self.assertEqual(by_key['tax']['code'], 'PIT')
        self.assertTrue(preview['currency']['code'])

    # ---- 8 ----------------------------------------------------------
    def test_bp_restart_guard(self):
        if not self.vn_tpl:
            self.skipTest("the Vietnam rule pack is not installed on this database")
        res = self._start('tok-restart', template_key='blank')
        cid = res['config_id']
        config = self.Config.browse(cid)

        config.state = 'active'
        refused = self.Studio.bp_restart(cid, 'vn_standard_2026')
        self.assertFalse(refused['ok'])
        self.assertIn('draft', refused['reason'].lower())

        config.state = 'draft'
        done = self.Studio.bp_restart(cid, 'vn_standard_2026')
        self.assertTrue(done['ok'], done.get('reason'))
        self.assertEqual(done['rule_count'], len(self.vn_tpl._components()))
        self.assertTrue(config.sample_data_ids)

    # ---- 9a ---------------------------------------------------------
    def test_bp_finish_accepts_the_rule_pack(self):
        """The journey's own default starter must be finishable.

        `has_errors` is `any(not rule.is_valid)`, and `is_valid` is a static
        lint that does not know the engine's own `BRACKET(...)` — so every
        configuration seeded from the Vietnam pack reports an error for a PIT
        formula that computes correctly. Finish asks the question the engine
        actually answers instead: did the formula convert?
        """
        if not self.vn_tpl:
            self.skipTest("the Vietnam rule pack is not installed on this database")
        res = self._start('tok-finish-pack', template_key='vn_standard_2026')
        cfg = self.Config.browse(res['config_id'])
        cfg.invalidate_recordset()
        done = self.Studio.bp_finish(cfg.id)
        self.assertTrue(done['ok'], done.get('reason'))
        self.assertFalse(cfg.rule_ids.filtered(
            lambda r: r.column_type == 'formula' and r.excel_formula
            and not r.python_formula),
            "every seeded formula converted, which is what Finish checks")

    # ---- 9 ----------------------------------------------------------
    def test_bp_finish_requires_valid_formulas(self):
        res = self._start('tok-finish', template_key='blank')
        cid = res['config_id']
        config = self.Config.browse(cid)
        # A component that refers to itself: no number can ever come out.
        self.env['hr.formula.rule'].create({
            'config_id': cid, 'code': 'LOOPA', 'name': 'Loop A',
            'column_type': 'formula', 'excel_formula': '=B1', 'column_letter': 'A',
        })
        self.env['hr.formula.rule'].create({
            'config_id': cid, 'code': 'LOOPB', 'name': 'Loop B',
            'column_type': 'formula', 'excel_formula': '=A1', 'column_letter': 'B',
        })
        config.invalidate_recordset()
        refused = self.Studio.bp_finish(cid)
        self.assertFalse(refused['ok'])
        self.assertTrue(refused['reason'])

        config.rule_ids.unlink()
        config.invalidate_recordset()
        done = self.Studio.bp_finish(cid)
        self.assertTrue(done['ok'], done.get('reason'))
        blueprint = self.Blueprint.search([('config_id', '=', cid)])
        self.assertEqual(blueprint.state, 'finished')
        self.assertEqual(blueprint.step, 'finish')

        again = self.Studio.bp_finish(cid)
        self.assertTrue(again['ok'])
        self.assertTrue(again['already'], "finishing twice is not an error")

    # ---- 10 ---------------------------------------------------------
    def test_bureau_board_carries_blueprint(self):
        res = self._start('tok-board')
        cid = res['config_id']
        board = self.env['pb.formula.studio'].bureau_board()
        cards = {c['id']: c for c in board['cards']}
        self.assertIn(cid, cards, "the draft appears on the configurations board")
        setup = cards[cid]['blueprint']
        self.assertTrue(setup)
        self.assertEqual(setup['step'], 'rules')
        self.assertEqual(setup['step_no'], 2)
        self.assertEqual(setup['total'], 6)

        # A configuration built any other way carries no setup at all — the
        # card must show its health ring, not a progress ring stuck at 1/6.
        plain = self.Config.create({
            'name': 'Built by hand', 'country_code': 'VN',
            'company_id': self.company.id, 'state': 'draft'})
        board = self.env['pb.formula.studio'].bureau_board()
        cards = {c['id']: c for c in board['cards']}
        self.assertFalse(cards[plain.id]['blueprint'])

    # ---- 11 ---------------------------------------------------------
    def test_import_return_door(self):
        res = self._start('tok-import', template_key='excel')
        config = self.Config.browse(res['config_id'])
        rules = self.env['hr.formula.rule']

        back = config.with_context(pb_blueprint_return=True).\
            studio_people_mapping_action(rules)
        self.assertEqual(back['tag'], 'pb_blueprint')
        self.assertEqual(back['params']['config_id'], config.id)
        self.assertEqual(back['context']['config_id'], config.id)
        blueprint = self.Blueprint.search([('config_id', '=', config.id)])
        self.assertEqual(blueprint.step, 'rules')

        # Without the flag the original behaviour is untouched: the parent only
        # bounces to the people board for a workbook that produced people
        # columns, and this one produced none.
        plain = config.with_context(pbfs_studio_import=True).\
            studio_people_mapping_action(rules)
        self.assertIsNone(plain)

    # ---- 12 ---------------------------------------------------------
    def test_bp_add_sample_and_inputs(self):
        res = self._start('tok-sample', template_key='blank')
        cid = res['config_id']
        config = self.Config.browse(cid)
        self.env['hr.formula.rule'].create({
            'config_id': cid, 'code': 'BASIC', 'name': 'Basic salary',
            'column_type': 'input', 'default_value': 12000000.0, 'column_letter': 'A',
        })

        # A configuration whose samples were all deleted is not a dead end.
        config.sample_data_ids.unlink()
        empty = self.Studio.bp_preview(cid)
        self.assertFalse(empty['ok'])
        self.assertTrue(empty.get('empty'))

        added = self.Studio.bp_add_sample(cid)
        self.assertTrue(added['ok'])
        sid = added['sample_id']

        rows = self.Studio.bp_sample_inputs(cid, sid)
        self.assertTrue(rows['ok'])
        self.assertEqual([r['code'] for r in rows['rows']], ['BASIC'])

        saved = self.Studio.bp_save_sample_inputs(cid, sid, {'BASIC': 25000000})
        self.assertTrue(saved['ok'])
        stored = json.loads(
            self.env['hr.formula.sample.data'].browse(sid).input_values_json)
        self.assertEqual(stored['BASIC'], 25000000)

    # ---- 13 ---------------------------------------------------------
    def test_bp_templates_shape(self):
        """The starter list always offers a way forward, on any country."""
        vn = self.Studio.bp_templates('VN')
        self.assertTrue(vn['ok'])
        self.assertTrue(vn['company'])
        kinds = [s['kind'] for s in vn['starters']]
        self.assertIn('excel', kinds)
        self.assertIn('blank', kinds)
        self.assertEqual(sum(1 for s in vn['starters'] if s['default']), 1,
                         "exactly one starter is pre-selected")
        self.assertFalse(any(s['key'] == 'vn_standard' for s in vn['starters']),
                         "the superseded built-in Vietnam set is never offered")

        # A country with no rule pack still gets Excel and a blank canvas, and
        # the blank canvas becomes the default rather than nothing at all.
        kh = self.Studio.bp_templates('KH')
        self.assertTrue(kh['ok'])
        self.assertTrue(any(s['kind'] == 'blank' and s['default'] for s in kh['starters'])
                        or kh['has_template'])

    # ---- 14 ---------------------------------------------------------
    def test_bp_close_and_discard(self):
        res = self._start('tok-close')
        cid = res['config_id']
        self.Studio.bp_close(cid, 'outputs')
        blueprint = self.Blueprint.search([('config_id', '=', cid)])
        self.assertEqual(blueprint.step, 'outputs')

        # A step key nobody recognises falls back to the start rather than
        # storing a value the rail cannot render.
        self.Studio.bp_close(cid, 'nonsense')
        self.assertEqual(blueprint.step, 'start')

        self.assertTrue(self.Studio.bp_discard(cid)['ok'])
        self.assertFalse(self.Config.browse(cid).exists())
        self.assertFalse(blueprint.exists(), "the setup row goes with it")
