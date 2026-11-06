# -*- coding: utf-8 -*-
"""SCHEMECTX P3 — the journey opened on a configuration that already exists.

The promise being tested is narrow and it matters: **edit mode changes
settings and nothing else**. It may rename a configuration, point it at a
journal, turn part-month pay on and reorder the source lanes — all of which the
studio's Settings panel has always written straight to a live configuration —
and it may not touch a single rule, band, bracket, calendar preference or
sample on a configuration that is no longer a draft or that has paid somebody.

Every test here either proves a settings write lands, or proves a pay-logic
write is refused and left the rules byte-identical.

Numbering follows `SCHEMECTX_PHASE_3_HANDOVER.md` §6.
"""
import hashlib
import json
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

#: Words that may never reach a person on any of these refusals.
BANNED = ('odoo', 'schema', 'blueprint', 'rule set', 'traceback')


@tagged('post_install', '-at_install')
class TestSchemeCtxP3EditMode(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.blueprint.studio']
        cls.FStudio = cls.env['pb.formula.studio']
        cls.Blueprint = cls.env['pb.formula.blueprint']
        cls.Config = cls.env['hr.formula.config']
        cls.company = cls.env.company

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------
    def _bare(self, name, state='active'):
        """A configuration the journey has never seen — the whole point.

        Made the way the components grid makes one, with two rules and a rate
        table, so "nothing was touched" is a claim with something behind it.
        """
        config = self.Config.create({
            'name': 'P3 %s' % name,
            'country_code': 'VN',
            'cycle_type': 'regular',
            'company_id': self.company.id,
            'state': 'draft',
        })
        self.env['hr.formula.rule'].create([
            {'config_id': config.id, 'name': 'Basic pay', 'code': 'BASICPAY',
             'column_type': 'input', 'sequence': 10},
            {'config_id': config.id, 'name': 'Take home', 'code': 'NETPAY',
             'column_type': 'formula', 'excel_formula': '=A', 'sequence': 20},
        ])
        if state != 'draft':
            config.state = state
        return config

    def _draft(self, token):
        """A journey-made draft, exactly as create mode leaves it."""
        res = self.Studio.bp_start({
            'name': 'P3 %s' % token, 'country_code': 'VN',
            'cycle_type': 'regular', 'template_key': 'blank',
            'situations': {'audiences': ['local'], 'reallife': []},
        }, token)
        self.assertTrue(res.get('ok'), res.get('reason'))
        config = self.Config.browse(res['config_id'])
        return config, self.Blueprint.search([('config_id', '=', config.id)])

    def _pay_logic_fingerprint(self, config):
        """One key over everything edit mode must never move."""
        config.invalidate_recordset()
        rules = sorted(
            (r.code or '', r.column_type or '', r.excel_formula or '',
             str(r.constant_value or ''), r.column_letter or '')
            for r in config.rule_ids)
        tables = sorted(
            (t.code or '', str(sorted((b.lower, b.rate) for b in t.line_ids)))
            for t in config.rate_table_ids)
        samples = sorted(
            (s.name or '', s.input_values_json or '')
            for s in config.sample_data_ids)
        blob = json.dumps([rules, tables, samples], sort_keys=True,
                          default=str)
        return hashlib.sha256(blob.encode()).hexdigest()

    def _plain(self, text):
        self.assertTrue(text, "a refusal has to say something")
        for banned in BANNED:
            self.assertNotIn(banned, (text or '').lower(),
                             "%r reached a person in: %s" % (banned, text))

    # ==================================================================
    # 1 — entering edit mode creates the row and touches nothing else
    # ==================================================================
    def test_01_adopt_makes_an_editing_row_and_moves_no_pay_logic(self):
        config = self._bare('adopt')
        before = self._pay_logic_fingerprint(config)
        self.assertFalse(self.Blueprint.search([('config_id', '=', config.id)]))

        res = self.Studio.bp_adopt(config.id)
        self.assertTrue(res['ok'], res.get('reason'))
        self.assertEqual(res['mode'], 'edit')
        self.assertTrue(res['created'])

        row = self.Blueprint.search([('config_id', '=', config.id)])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.state, 'editing')
        self.assertEqual(row.step, 'start')
        self.assertFalse(row.template_key)
        self.assertTrue(row.effective_from, "edit mode fills in a sensible date")
        self.assertEqual(self._pay_logic_fingerprint(config), before,
                         "opening a configuration for editing changed its rules")

    # ==================================================================
    # 2 — idempotent, and a draft is left alone
    # ==================================================================
    def test_02_adopt_twice_is_one_row_and_a_draft_is_untouched(self):
        config = self._bare('twice')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])
        second = self.Studio.bp_adopt(config.id)
        self.assertTrue(second['ok'])
        self.assertFalse(second['created'])
        self.assertEqual(second['mode'], 'edit')
        self.assertEqual(
            len(self.Blueprint.search([('config_id', '=', config.id)])), 1)

    def test_02b_a_draft_opens_as_the_ordinary_journey(self):
        config, blueprint = self._draft('p3-adopt-draft')
        res = self.Studio.bp_adopt(config.id)
        self.assertTrue(res['ok'])
        self.assertEqual(res['mode'], 'create',
                         "a half-built draft is a build, not an edit")
        self.assertEqual(blueprint.state, 'draft')

    def test_02c_a_finished_setup_reopens_as_an_edit(self):
        config, blueprint = self._draft('p3-adopt-finished')
        blueprint.state = 'finished'
        res = self.Studio.bp_adopt(config.id)
        self.assertTrue(res['ok'])
        self.assertEqual(res['mode'], 'edit')
        self.assertEqual(blueprint.state, 'editing')

    # ==================================================================
    # 3 — the read stays a read (BP53)
    # ==================================================================
    def test_03_load_on_an_unadopted_configuration_writes_nothing(self):
        config = self._bare('needs-adopt')
        rows_before = self.Blueprint.search_count([])
        stamp = config.write_date

        res = self.Studio.bp_load(config.id)
        self.assertFalse(res['ok'])
        self.assertTrue(res.get('needs_adopt'))
        self._plain(res.get('reason'))

        self.assertEqual(self.Blueprint.search_count([]), rows_before)
        config.invalidate_recordset()
        self.assertEqual(config.write_date, stamp,
                         "a read RPC wrote to the configuration")

    def test_03b_load_in_edit_mode_answers_the_locks(self):
        config = self._bare('locks', state='active')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])
        res = self.Studio.bp_load(config.id)
        self.assertTrue(res['ok'], res.get('reason'))
        self.assertEqual(res['mode'], 'edit')
        self.assertTrue(res['locks']['pay_logic'],
                        "an Active configuration's rules are read only")
        self.assertFalse(res['locks']['country'],
                         "nothing has been paid, so the country is still open")
        self.assertEqual(res['scheme_state'], 'active')
        self.assertTrue(res['built_from'])
        self._plain(res['lock_reason'])

    # ==================================================================
    # 4 — settings land on a live configuration
    # ==================================================================
    def test_04_settings_write_to_an_active_configuration(self):
        config = self._bare('settings', state='active')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])
        before = self._pay_logic_fingerprint(config)

        values = {
            'use_proration': True,
            # The engine refuses part-month pay with nothing to prorate, and
            # says so in a sentence. The card has to send the pair together.
            'proration_component_ids': config.rule_ids.ids[:1],
            'proration_rounding': 2,
            'use_auto_retro': True,
            'retro_component_id': config.rule_ids.ids[0],
            'source_priority': 'records,excel,api',
            'source_excel_enabled': False,
            'export_identity_columns': True,
        }
        journals = self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', config.company_id.id)],
            limit=1)
        if journals:
            values['payroll_journal_id'] = journals.id

        res = self.Studio.bp_save_settings(config.id, values)
        self.assertTrue(res['ok'], res.get('reason'))
        self.assertIn('use_proration', res['saved'])

        back = self.Studio.bp_settings(config.id)
        self.assertTrue(back['ok'])
        self.assertTrue(back['values']['use_proration'])
        self.assertEqual(back['values']['proration_component_ids'],
                         config.rule_ids.ids[:1])
        self.assertEqual(back['values']['proration_rounding'], 2)
        self.assertTrue(back['values']['use_auto_retro'])
        self.assertEqual(back['values']['retro_component_id'],
                         config.rule_ids.ids[0])
        self.assertEqual(back['values']['source_priority'], 'records,excel,api')
        self.assertFalse(back['values']['source_excel_enabled'])
        self.assertTrue(back['values']['export_identity_columns'])
        if journals:
            self.assertEqual(back['values']['payroll_journal_id'], journals.id)

        self.assertEqual(config.state, 'active',
                         "saving settings must never change the lifecycle")
        self.assertEqual(self._pay_logic_fingerprint(config), before,
                         "saving settings moved pay logic")

    def test_04b_the_company_is_never_accepted(self):
        config = self._bare('company')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])
        other = self.env['res.company'].create({'name': 'P3 Other Co'})
        res = self.Studio.bp_save_settings(config.id, {'company_id': other.id})
        self.assertTrue(res['ok'])
        self.assertEqual(res['saved'], [],
                         "the company is read only everywhere in this journey")
        config.invalidate_recordset()
        self.assertEqual(config.company_id, self.company)
        self.assertNotIn('company_id', self.Studio.bp_settings(config.id)['values'])

    # ==================================================================
    # 5 — every settings field has a home
    # ==================================================================
    def test_05_every_settings_field_round_trips(self):
        """The whitelist is the contract: loop it rather than list it twice."""
        config = self._bare('roundtrip')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])
        payload = self.Studio.bp_settings(config.id)
        self.assertTrue(payload['ok'])

        expected = set(self.FStudio._CFG_FIELDS) - {'company_id'}
        self.assertEqual(set(payload['values']), expected,
                         "a settings field with no home in the journey")

        samples = {
            'name': 'P3 roundtrip renamed',
            'code': 'P3ROUNDTRIP',
            'country_code': 'VN',
            'cycle_type': 'end_cycle',
            'use_color_coded_excel_import': True,
            'export_identity_columns': True,
            'use_proration': True,
            'proration_basis': 'workdays',
            'proration_rounding': 1,
            'proration_component_ids': config.rule_ids.ids[:1],
            'use_auto_retro': True,
            'retro_component_id': config.rule_ids.ids[0],
            'source_api_enabled': False,
            'source_excel_enabled': False,
            'source_records_enabled': True,
            'source_priority': 'records,api,excel',
            'structure_id': False,
            'connector_id': False,
            'payroll_journal_id': False,
            'debit_account_id': False,
            'credit_account_id': False,
        }
        bases = dict(config._fields['proration_basis'].selection)
        if samples['proration_basis'] not in bases:
            samples['proration_basis'] = list(bases)[0]
        missing = expected - set(samples)
        self.assertFalse(missing, "no value written for %s" % sorted(missing))

        res = self.Studio.bp_save_settings(config.id, dict(samples))
        self.assertTrue(res['ok'], res.get('reason'))

        back = self.Studio.bp_settings(config.id)['values']
        for field, wanted in samples.items():
            if field == 'country_code':
                continue            # unchanged, so deliberately not resent
            self.assertEqual(back[field], wanted,
                             "%s did not come back as it was saved" % field)

    # ==================================================================
    # 6 — the country follows the money
    # ==================================================================
    def test_06_country_is_locked_once_somebody_has_been_paid(self):
        config = self._bare('country-paid')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])

        with patch.object(type(self.Studio), '_has_payslips', return_value=True):
            loaded = self.Studio.bp_load(config.id)
            self.assertTrue(loaded['locks']['country'])
            self._plain(loaded['country_lock_reason'])
            refused = self.Studio.bp_save_settings(config.id,
                                                   {'country_code': 'IN'})
        self.assertFalse(refused['ok'])
        self._plain(refused['reason'])
        config.invalidate_recordset()
        self.assertEqual(config.country_code, 'VN')

    def test_06b_country_changes_on_a_draft_that_has_paid_nobody(self):
        config = self._bare('country-open', state='draft')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])
        res = self.Studio.bp_save_settings(config.id, {'country_code': 'IN'})
        self.assertTrue(res['ok'], res.get('reason'))
        config.invalidate_recordset()
        self.assertEqual(config.country_code, 'IN')
        # SCHEMECTX P1: the country decides the money, and it still does.
        self.assertEqual(config.currency_id.name, 'INR')

    # ==================================================================
    # 7 — pay logic is refused, and the rules do not move
    # ==================================================================
    def _pay_logic_calls(self, config):
        rule = config.rule_ids[:1]
        table = config.rate_table_ids[:1]
        calls = [
            ('bp_component_save',
             lambda: self.Studio.bp_component_save(
                 config.id, rule.id, {'name': 'Renamed by a test'})),
            ('bp_component_exclude',
             lambda: self.Studio.bp_component_exclude(
                 config.id, rule.ids, True)),
            ('bp_component_include',
             lambda: self.Studio.bp_component_include(config.id, 'BASICPAY')),
            ('bp_regenerate',
             lambda: self.Studio.bp_regenerate(config.id)),
            ('bp_component_restore_guided',
             lambda: self.Studio.bp_component_restore_guided(rule.id)),
            ('bp_tax_save_values',
             lambda: self.Studio.bp_tax_save_values(config.id, {'X': 1.0})),
            ('bp_tax_sync_pack',
             lambda: self.Studio.bp_tax_sync_pack(config.id)),
            ('bp_calendar_save',
             lambda: self.Studio.bp_calendar_save(config.id, {'cutoff_day': 5})),
        ]
        if table:
            calls.append((
                'bp_tax_save_bands',
                lambda: self.Studio.bp_tax_save_bands(
                    config.id, table.id, [{'lower': 0, 'rate': 0.5}])))
        return calls

    def test_07_every_pay_logic_write_refuses_on_a_locked_configuration(self):
        config = self._bare('locked-writes', state='active')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])
        before = self._pay_logic_fingerprint(config)

        for name, call in self._pay_logic_calls(config):
            res = call()
            self.assertFalse(res.get('ok'), "%s wrote pay logic" % name)
            self._plain(res.get('reason'))
            self.assertIn('components grid', res.get('reason') or '',
                          "%s refused without saying where to go" % name)

        self.assertEqual(self._pay_logic_fingerprint(config), before,
                         "a refused pay-logic write still changed the rules")

    def test_07b_the_gate_holds_in_create_mode_too(self):
        """Owner ruling 2026-09-19 — the component writes had no gate at all.

        A journey draft that is later activated, or that has paid somebody,
        could be rewritten through these endpoints by anything that still held
        its id. They are now gated exactly as tax and calendar always were.
        """
        config, blueprint = self._draft('p3-create-gate')
        self.assertEqual(blueprint.state, 'draft')
        config.state = 'active'
        before = self._pay_logic_fingerprint(config)
        res = self.Studio.bp_regenerate(config.id, blueprint.revision)
        self.assertFalse(res.get('ok'))
        self._plain(res.get('reason'))
        self.assertEqual(self._pay_logic_fingerprint(config), before)

    def test_07c_a_draft_that_paid_nobody_still_works_exactly_as_before(self):
        config, blueprint = self._draft('p3-draft-open')
        res = self.Studio.bp_regenerate(config.id, blueprint.revision)
        self.assertTrue(res.get('ok'), res.get('reason'))

    # ==================================================================
    # 8 — edit mode never destroys anything
    # ==================================================================
    def test_08_restart_and_discard_refuse_in_edit_mode(self):
        config = self._bare('no-destroy', state='draft')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])
        before = self._pay_logic_fingerprint(config)

        restart = self.Studio.bp_restart(config.id, 'vn_standard_2026')
        self.assertFalse(restart['ok'])
        self._plain(restart['reason'])

        check = self.Studio.bp_discard_check(config.id)
        self.assertTrue(check['ok'])
        self.assertFalse(check['allowed'])
        self._plain(check['reason'])

        discard = self.Studio.bp_discard(config.id)
        self.assertFalse(discard['ok'])
        self._plain(discard['reason'])

        self.assertTrue(config.exists())
        self.assertEqual(self._pay_logic_fingerprint(config), before)

    # ==================================================================
    # 9 — "Save changes" closes the sitting and nothing else
    # ==================================================================
    def test_09_finish_in_edit_mode_changes_no_rule_and_no_state(self):
        config = self._bare('save-changes', state='active')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])
        before = self._pay_logic_fingerprint(config)

        res = self.Studio.bp_finish(config.id)
        self.assertTrue(res['ok'], res.get('reason'))
        self.assertEqual(res['mode'], 'edit')
        self.assertTrue(res.get('action'), "Save changes has to land somewhere")

        row = self.Blueprint.search([('config_id', '=', config.id)])
        self.assertEqual(row.state, 'finished')
        config.invalidate_recordset()
        self.assertEqual(config.state, 'active',
                         "an Active configuration is still Active afterwards")
        self.assertEqual(self._pay_logic_fingerprint(config), before)

    # ==================================================================
    # 10 — an edit is not a half-finished build
    # ==================================================================
    def test_10_an_editing_row_is_never_a_resume_setup_card(self):
        config = self._bare('board', state='active')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])
        board = self.FStudio.bureau_board()
        card = next((c for c in board.get('cards') or []
                     if c['id'] == config.id), None)
        self.assertTrue(card, "the configuration is missing from the board")
        self.assertFalse(card.get('blueprint'),
                         "a configuration being edited offered to be resumed")

    # ==================================================================
    # 11 — the company refusals are still sentences (BP-R11, BP13)
    # ==================================================================
    def test_11_company_refusals_are_sentences(self):
        other = self.env['res.company'].create({'name': 'P3 Elsewhere'})
        config = self._bare('elsewhere')
        config.company_id = other

        both = self.Studio.with_company(self.company).with_context(
            allowed_company_ids=[self.company.id, other.id])
        for res in (both.bp_adopt(config.id), both.bp_settings(config.id),
                    both.bp_save_settings(config.id, {'name': 'nope'})):
            self.assertFalse(res['ok'])
            self.assertIn(other.name, res['reason'])
            self._plain(res['reason'])

        one = self.Studio.with_context(allowed_company_ids=[self.company.id])
        blocked = one.bp_adopt(config.id)
        self.assertFalse(blocked['ok'])
        for banned in ('hr.formula.config', 'cookies', 'access to:'):
            self.assertNotIn(banned, blocked['reason'])

    # ==================================================================
    # 12 — two people, one configuration
    # ==================================================================
    def test_12_a_stale_revision_is_told_rather_than_overwritten(self):
        config = self._bare('revision')
        self.assertTrue(self.Studio.bp_adopt(config.id)['ok'])
        row = self.Blueprint.search([('config_id', '=', config.id)])
        stale = row.revision

        first = self.Studio.bp_save_settings(config.id, {'name': 'P3 first'},
                                             stale)
        self.assertTrue(first['ok'], first.get('reason'))

        second = self.Studio.bp_save_settings(config.id, {'name': 'P3 second'},
                                              stale)
        self.assertFalse(second['ok'])
        self.assertTrue(second.get('conflict'))
        self._plain(second['reason'])
        config.invalidate_recordset()
        self.assertEqual(config.name, 'P3 first',
                         "the stale save overwrote somebody else's change")
