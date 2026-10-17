# -*- coding: utf-8 -*-
"""JOURNEY J9 — a component may declare several sources, and the order is stated.

The owner withdrew the either/or restriction: API and spreadsheet may both map to
a Payroll Schema component, the contract component may sit beside them, and the
card has to show all of them with the precedence visible. **What was missing was
never the order — it was the arity** (J-D5 still binds; no rung of the resolver
ladder moved in this phase).

The two claims these tests exist to defend, in order of how much they matter:

  * **NEUTRALITY.** A component declaring exactly ONE source resolves
    byte-identically to the way it did before this phase — same value, same
    provenance blob, key for key — and `_multi_source_walk_entered` proves the new
    code path was never entered at all. Everything on all four live databases is
    single-source, so this is the whole of the risk.
  * **PRECEDENCE.** With two or more declared, the walk takes the first that
    actually delivered a value by the resolver's own emptiness test — in which
    `0` and `False` ARE values (MJ15) and only `None` or whitespace is silence —
    and the unused side is REPORTED rather than dropped.

The resolver is exercised through `_transform_data_to_formula_inputs` directly
rather than through a batch run, deliberately and for the same reason J3 gave:
`action_process` WRITES BACK onto employee and contract records, and a resolver
assertion has no business creating that risk. Nothing here calls it.
"""
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestJourneyJ9Sources(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Source = cls.env['hr.formula.rule.source']
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Connector = cls.env['hr.integration.connector']
        cls.FieldMapping = cls.env['hr.integration.field.mapping']

    # ------------------------------------------------------------- fixtures
    def _config(self, name, connector=None):
        cfg = self.Config.create({
            'name': name, 'code': name.upper().replace(' ', '')[:32],
            'country_code': 'VN', 'state': 'active',
        })
        if connector:
            cfg.connector_id = connector.id
        self.bonus = self.Rule.create({
            'config_id': cfg.id, 'name': 'Site Bonus', 'code': 'SITEBONUS',
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
        })
        return cfg

    def _connector(self, name='J9 Demo'):
        return self.Connector.create({'name': name, 'connector_type': 'demo'})

    def _batch(self, cfg, source_type='api_data_store', connector=None):
        vals = {'name': 'J9 %s' % source_type, 'source_type': source_type,
                'formula_config_id': cfg.id}
        if connector:
            vals['connector_id'] = connector.id
        return self.Batch.create(vals)

    def _resolve(self, batch, raw, topup=None, contract=None):
        """One resolve, with the counters reset so each test measures its own."""
        self.Batch._sourcing_reset_branch_counter()
        prov = {}
        vals = batch._transform_data_to_formula_inputs(
            raw, contract=contract, provenance=prov, topup_data=topup or {})
        return vals, prov

    @property
    def _multi(self):
        return self.Batch._sourcing_multi_walk_counter()

    # =====================================================================
    # 1 — THE NEUTRALITY RAIL. One source behaves exactly as one source did.
    # =====================================================================
    def test_01a_one_excel_source_is_the_legacy_binding_exactly(self):
        cfg = self._config('J9 One')
        self.bonus.set_source_binding('excel', 'Bonus Col', origin='user')
        # The legacy Chars are the plural form's head, so "the equivalent legacy
        # binding" and "one source row" are now the SAME record — which is the
        # compatibility claim, stated as an assertion rather than assumed.
        self.assertEqual(self.bonus.source_binding, 'excel')
        self.assertEqual(self.bonus.source_binding_key, 'Bonus Col')
        self.assertEqual(self.bonus.source_binding_origin, 'user')

        batch = self._batch(cfg, 'excel')
        vals, prov = self._resolve(batch, {'Bonus Col': 1250})
        self.assertEqual(vals['SITEBONUS'], 1250.0)
        self.assertEqual(prov['SITEBONUS'],
                         {'src': 'excel', 'key': 'Bonus Col', 'via': 'binding'})
        self.assertEqual(
            self._multi, 0,
            "the multi-source walk must not have run for a single-source "
            "component — the numbers agreeing is a weaker claim than the new "
            "path never having executed")

    def test_01b_one_source_keeps_the_heuristic_other_side_and_its_provenance(self):
        """The single-source path is S3's, verbatim, including `side_o`."""
        cfg = self._config('J9 One Fallback')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        batch = self._batch(cfg, 'excel')
        # nothing under the bound key; the FEED side is searched by the bound key
        # and then by the component's natural candidates — today's heuristic.
        vals, prov = self._resolve(batch, {}, topup={'Site Bonus': 400})
        self.assertEqual(vals['SITEBONUS'], 400.0)
        self.assertEqual(prov['SITEBONUS'], {
            'src': 'feed', 'key': 'Site Bonus', 'via': 'fallback',
            'fell_back': True})
        self.assertEqual(self._multi, 0)

    def test_01c_one_source_that_delivered_nothing_still_says_binding_empty(self):
        cfg = self._config('J9 One Empty')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        batch = self._batch(cfg, 'excel')
        vals, prov = self._resolve(batch, {'Something Else': 9})
        self.assertEqual(vals['SITEBONUS'], 0.0)
        self.assertEqual(prov['SITEBONUS']['via'], 'binding_empty')
        self.assertEqual(self._multi, 0)

    def test_01d_an_unbound_component_never_enters_either_branch(self):
        cfg = self._config('J9 Unbound')
        batch = self._batch(cfg, 'excel')
        vals, prov = self._resolve(batch, {'Site Bonus': 77})
        self.assertEqual(vals['SITEBONUS'], 77.0)
        self.assertEqual(prov['SITEBONUS']['via'], 'header')
        self.assertEqual(self.Batch._sourcing_branch_counter(), 0)
        self.assertEqual(self._multi, 0)

    # =====================================================================
    # 2 — the binding is plural, and clearing still clears everything
    # =====================================================================
    def test_02a_two_kinds_coexist_and_the_head_is_the_highest_ranked(self):
        self._config('J9 Two')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        self.bonus.set_source_binding('feed', 'SiteBonus')
        self.assertEqual(len(self.bonus.source_ids), 2)
        self.assertEqual({s.kind for s in self.bonus.source_ids},
                         {'excel', 'feed'})
        # rank 1 is `feed`: both arrive in the feed payload and a connector's own
        # statement is the more specific one. The order was already in the file.
        self.assertEqual(self.bonus.source_binding, 'feed')
        self.assertEqual(self.bonus.source_binding_key, 'SiteBonus')
        self.assertEqual(
            [d['kind'] for d in self.bonus.declared_sources()],
            ['feed', 'excel'])

    def test_02b_setting_the_same_kind_twice_upserts_rather_than_adds(self):
        self._config('J9 Upsert')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        self.bonus.set_source_binding('excel', 'Other Col')
        self.assertEqual(len(self.bonus.source_ids), 1)
        self.assertEqual(self.bonus.source_binding_key, 'Other Col')

    def test_02c_a_falsy_kind_still_means_clear_everything(self):
        self._config('J9 Clear')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        self.bonus.set_source_binding('feed', 'SiteBonus')
        self.bonus.set_source_binding(False, '')
        self.assertEqual(len(self.bonus.source_ids), 0)
        self.assertFalse(self.bonus.source_binding)
        self.assertFalse(self.bonus.source_binding_key)
        self.assertEqual(self.bonus.declared_sources(), [])

    def test_02d_clear_one_kind_leaves_the_others(self):
        self._config('J9 Clear One')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        self.bonus.set_source_binding('feed', 'SiteBonus')
        self.bonus.clear_source_binding('feed')
        self.assertEqual([s.kind for s in self.bonus.source_ids], ['excel'])
        self.assertEqual(self.bonus.source_binding, 'excel')

    def test_02e_the_contract_component_is_rank_four_and_is_not_a_row(self):
        self._config('J9 Rank Four')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        self.bonus.is_contract_component = True
        self.assertEqual(len(self.bonus.source_ids), 1,
                         "the contract component is a boolean, not a binding — "
                         "a second representation is a second thing to keep in "
                         "step")
        self.assertEqual([d['kind'] for d in self.bonus.declared_sources()],
                         ['excel', 'contract_component'])

    # =====================================================================
    # 4-7 — the ranked walk, with a feed and a spreadsheet both declared
    # =====================================================================
    def _two_source_fixture(self, name, primary='api_data_store'):
        conn = self._connector()
        cfg = self._config(name, connector=conn)
        self.bonus.set_source_binding('feed', 'SiteBonus')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        return cfg, self._batch(cfg, primary, connector=conn)

    def _two_source_blobs(self, batch, feed_value, excel_value):
        """The same two payloads, whichever side of the run is primary."""
        feed = {'SiteBonus': feed_value}
        excel = {'Bonus Col': excel_value}
        if batch.source_type == 'api_data_store':
            return feed, excel
        return excel, feed

    def test_04_feed_delivers_so_feed_wins_and_excel_is_reported(self):
        _cfg, batch = self._two_source_fixture('J9 Both')
        raw, topup = self._two_source_blobs(batch, 900, 100)
        vals, prov = self._resolve(batch, raw, topup=topup)
        self.assertEqual(vals['SITEBONUS'], 900.0)
        self.assertEqual(prov['SITEBONUS']['src'], 'feed')
        self.assertEqual(prov['SITEBONUS']['via'], 'binding')
        self.assertNotIn('fell_back', prov['SITEBONUS'])
        # the unused side is REPORTED, never silently discarded
        self.assertEqual(prov['SITEBONUS']['ignored'],
                         {'src': 'excel', 'key': 'Bonus Col', 'value': 100})
        self.assertEqual(self._multi, 1)

    def test_05_an_empty_feed_lets_the_spreadsheet_speak(self):
        _cfg, batch = self._two_source_fixture('J9 Empty Feed')
        raw, topup = self._two_source_blobs(batch, '   ', 100)
        vals, prov = self._resolve(batch, raw, topup=topup)
        self.assertEqual(vals['SITEBONUS'], 100.0)
        self.assertEqual(prov['SITEBONUS']['src'], 'excel')
        self.assertEqual(prov['SITEBONUS']['via'], 'fallback')
        self.assertTrue(prov['SITEBONUS']['fell_back'])
        self.assertNotIn('ignored', prov['SITEBONUS'])

    def test_06_zero_is_an_answer_so_the_feed_still_wins(self):
        """MJ15, restated where it is most likely to be reintroduced.

        A connector reporting zero overtime has answered the question. `0` is a
        value; only `None` and whitespace are silence.
        """
        _cfg, batch = self._two_source_fixture('J9 Zero Feed')
        raw, topup = self._two_source_blobs(batch, 0, 100)
        vals, prov = self._resolve(batch, raw, topup=topup)
        self.assertEqual(vals['SITEBONUS'], 0.0)
        self.assertEqual(prov['SITEBONUS']['src'], 'feed')
        self.assertEqual(prov['SITEBONUS']['via'], 'binding')
        self.assertEqual(prov['SITEBONUS']['ignored']['value'], 100)

    def test_07_false_is_an_answer_too(self):
        _cfg, batch = self._two_source_fixture('J9 False Feed')
        raw, topup = self._two_source_blobs(batch, False, 100)
        vals, prov = self._resolve(batch, raw, topup=topup)
        self.assertEqual(vals['SITEBONUS'], 0.0)
        self.assertEqual(prov['SITEBONUS']['src'], 'feed')
        self.assertEqual(prov['SITEBONUS']['via'], 'binding')

    # =====================================================================
    # 8-9 — the tail below the declared sources is untouched
    # =====================================================================
    def _contract_with_component(self, code, amount):
        Template = self.env['hr.contract.advantage.template']
        employee = self.env['hr.employee'].create({'name': 'J9 Tester'})
        contract = self.env['hr.contract'].create({
            'name': 'J9 Contract', 'employee_id': employee.id,
            'wage': 1000.0, 'state': 'open',
            'date_start': '2026-01-01',
        })
        template = Template.create({
            'name': code, 'code': code, 'lower_bound': 0, 'upper_bound': 0,
            'default_value': 0,
        })
        # CR18 — `hr.contract.create` seeds one EMPTY advantage line per
        # template, so line EXISTENCE proves nothing. Reuse the seeded line if
        # there is one and give it a value; count only lines with a value.
        line = contract.advantages_ids.filtered(
            lambda a: a.advantage_template_id.id == template.id)
        if line:
            line[0].amount = amount
        else:
            self.env['hr.contract.advantage'].create({
                'contract_id': contract.id,
                'advantage_template_id': template.id, 'amount': amount})
        return contract

    def test_08_both_blank_so_the_contract_component_wins(self):
        _cfg, batch = self._two_source_fixture('J9 Contract Wins')
        self.bonus.is_contract_component = True
        contract = self._contract_with_component('SITEBONUS', 555.0)
        raw, topup = self._two_source_blobs(batch, '', '  ')
        vals, prov = self._resolve(batch, raw, topup=topup, contract=contract)
        self.assertEqual(vals['SITEBONUS'], 555.0)
        self.assertEqual(prov['SITEBONUS']['via'], 'contract')
        self.assertEqual(self._multi, 1,
                         "the walk ran and found nothing; the untouched tail "
                         "then produced the answer, exactly as it does for a "
                         "single empty binding")

    def test_09_all_blank_and_no_contract_line_lands_on_the_default(self):
        _cfg, batch = self._two_source_fixture('J9 All Blank')
        self.bonus.default_value = 42.0
        raw, topup = self._two_source_blobs(batch, None, None)
        raw, topup = {}, {}
        vals, prov = self._resolve(batch, raw, topup=topup)
        self.assertEqual(vals['SITEBONUS'], 42.0)
        self.assertEqual(prov['SITEBONUS']['via'], 'binding_empty')

    def test_09b_the_name_ladder_below_is_byte_identical_when_nothing_is_declared(self):
        """The tail is the tail. A declared source suppresses the name ladder on
        the blob it names — that is S3's behaviour and J9 did not change it — so
        the comparison that matters is against an UNBOUND component."""
        cfg = self._config('J9 Tail')
        other = self.Rule.create({
            'config_id': cfg.id, 'name': 'Site Bonus B', 'code': 'SITEBONUSB',
            'column_type': 'input', 'sequence': 2, 'default_value': 7.0,
        })
        batch = self._batch(cfg, 'excel')
        vals, prov = self._resolve(batch, {'Site Bonus B': 31})
        self.assertEqual(vals[other.code], 31.0)
        self.assertEqual(prov[other.code],
                         {'src': 'excel', 'key': 'Site Bonus B', 'via': 'header'})

    # =====================================================================
    # 10 — T5. The pre-pass never fires on any live database.
    # =====================================================================
    def test_10_the_same_outcomes_with_no_pre_pass_and_an_excel_primary_run(self):
        """`config.connector_id` is unset on every scheme on all four databases
        (S20), and the pre-pass is gated on exactly that field — so a `feed`
        source is served by the bound branch reading the TOP-UP blob. Cases 4-8
        again, on that path."""
        conn = self._connector()
        cfg = self._config('J9 No Prepass')      # deliberately NO connector_id
        self.assertFalse(cfg.connector_id)
        self.bonus.set_source_binding('feed', 'SiteBonus')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        batch = self._batch(cfg, 'excel', connector=conn)

        # 4 — feed delivers, feed wins, excel reported
        vals, prov = self._resolve(batch, {'Bonus Col': 100},
                                   topup={'SiteBonus': 900})
        self.assertEqual(vals['SITEBONUS'], 900.0)
        self.assertEqual(prov['SITEBONUS']['via'], 'binding')
        self.assertEqual(prov['SITEBONUS']['ignored']['value'], 100)
        # 5 — empty feed, excel wins
        vals, prov = self._resolve(batch, {'Bonus Col': 100},
                                   topup={'SiteBonus': ''})
        self.assertEqual(vals['SITEBONUS'], 100.0)
        self.assertTrue(prov['SITEBONUS']['fell_back'])
        # 6 — zero feed, feed wins
        vals, _p = self._resolve(batch, {'Bonus Col': 100},
                                 topup={'SiteBonus': 0})
        self.assertEqual(vals['SITEBONUS'], 0.0)
        # 7 — False feed, feed wins
        vals, _p = self._resolve(batch, {'Bonus Col': 100},
                                 topup={'SiteBonus': False})
        self.assertEqual(vals['SITEBONUS'], 0.0)
        # 8 — both blank, the contract component wins
        self.bonus.is_contract_component = True
        contract = self._contract_with_component('SITEBONUS', 555.0)
        vals, prov = self._resolve(batch, {'Bonus Col': ' '},
                                   topup={'SiteBonus': ''}, contract=contract)
        self.assertEqual(vals['SITEBONUS'], 555.0)
        self.assertEqual(prov['SITEBONUS']['via'], 'contract')

    def test_10b_a_live_pre_pass_still_outranks_everything_j_d5(self):
        """The rung did not move. A wire that DELIVERED still wins over a
        declared source, exactly as it did before this phase."""
        conn = self._connector()
        cfg = self._config('J9 Prepass', connector=conn)
        self.bonus.set_source_binding('feed', 'SiteBonus')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        self.FieldMapping.create({
            'connector_id': conn.id, 'target_rule_id': self.bonus.id,
            'source_field': 'Wired', 'active_state': 'active'})
        batch = self._batch(cfg, 'api_data_store', connector=conn)
        vals, prov = self._resolve(batch, {'Wired': 12, 'SiteBonus': 900},
                                   topup={'Bonus Col': 100})
        self.assertEqual(vals['SITEBONUS'], 12.0)
        self.assertEqual(prov['SITEBONUS']['via'], 'connector_mapping')
        self.assertEqual(self._multi, 0,
                         "the pre-pass filled the slot, so the loop skipped the "
                         "code and the walk never ran")

    # =====================================================================
    # 11 — T8. The writeback fires once, with the winner.
    # =====================================================================
    def test_11_the_contract_component_is_written_once_with_the_winner(self):
        conn = self._connector()
        cfg = self._config('J9 Writeback', connector=conn)
        self.bonus.write({'is_contract_component': True})
        self.bonus.set_source_binding('feed', 'Site Bonus')
        self.bonus.set_source_binding('excel', 'Site Bonus')
        batch = self._batch(cfg, 'api_data_store', connector=conn)
        contract = self._contract_with_component('SITEBONUS', 0.0)
        line = self.Batch.env['hr.payroll.import.line'].create({
            'batch_id': batch.id,
            'raw_data_json': '{"Site Bonus": 900}',
        })
        batch._sync_contract_components(line, contract)
        lines = contract.advantages_ids.filtered(
            lambda a: (a.advantage_template_code or
                       (a.advantage_template_id.code or '')) == 'SITEBONUS')
        # CR18 — count LINES WITH A VALUE, never lines: `hr.contract.create`
        # seeds an empty one per template and its existence proves nothing.
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].amount, 900.0)

    # =====================================================================
    # 12 — one row per kind, refused in Python (Odoo 19 ignores _sql_constraints)
    # =====================================================================
    def test_12_two_rows_of_one_kind_are_refused(self):
        self._config('J9 Constraint')
        self.bonus.set_source_binding('excel', 'Bonus Col')
        with self.assertRaises(ValidationError):
            self.Source.create({'rule_id': self.bonus.id, 'kind': 'excel',
                                'key': 'Another Col'})

    def test_12b_a_sealed_column_refuses_a_source_at_the_row(self):
        cfg = self._config('J9 Sealed')
        sealed = self.Rule.create({
            'config_id': cfg.id, 'name': 'Net Pay', 'code': 'NETPAY',
            'column_type': 'formula', 'excel_formula': '=SITEBONUS',
            'sequence': 9,
        })
        with self.assertRaises(ValidationError):
            self.Source.create({'rule_id': sealed.id, 'kind': 'excel',
                                'key': 'Anything'})

    def test_12c_a_source_with_no_key_is_refused(self):
        self._config('J9 No Key')
        with self.assertRaises(ValidationError):
            self.Source.create({'rule_id': self.bonus.id, 'kind': 'excel',
                                'key': '   '})

    # =====================================================================
    # 13 — T4. The migration, on abm's shape.
    # =====================================================================
    def _run_j9_migration(self):
        from odoo.addons.pb_hr_payroll_formula.migrations import (  # noqa: F401
            __name__ as _pkg)
        import importlib.util
        import os
        base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'migrations', '19.0.1.82.0')
        out = []
        for fname in ('pre-keep_the_bindings_we_have.py',
                      'post-one_row_per_declared_source.py'):
            spec = importlib.util.spec_from_file_location(
                'j9mig_%s' % fname.split('-')[0], os.path.join(base, fname))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.migrate(self.env.cr, '19.0.1.81.0')
            out.append(mod)
        self.env.invalidate_all()
        return out

    def _become_pre_j9(self, rules):
        """Put the world back the way it was before this phase: the legacy
        columns set, and not a single child row."""
        self.env.flush_all()
        self.env.cr.execute(
            "DELETE FROM hr_formula_rule_source WHERE rule_id IN %s",
            (tuple(rules.ids),))
        self.env.invalidate_all()

    @mute_logger('odoo.addons.pb_hr_payroll_formula.models.formula_rule')
    def test_13_the_migration_converts_inputs_skips_sealed_and_is_idempotent(self):
        cfg = self._config('J9 Migration')
        made = self.bonus
        self.bonus.set_source_binding('excel', 'Bonus Col', origin='board')
        for i in range(12):
            r = self.Rule.create({
                'config_id': cfg.id, 'name': 'Col %s' % i,
                'code': 'J9MIGCOL%s' % i, 'column_type': 'input',
                'sequence': 10 + i,
            })
            r.set_source_binding('feed' if i % 2 else 'excel', 'Key %s' % i,
                                 origin='migration')
            made |= r
        sealed = self.Rule.create({
            'config_id': cfg.id, 'name': 'Sealed', 'code': 'J9MIGSEALED',
            'column_type': 'formula', 'excel_formula': '=SITEBONUS',
            'sequence': 90,
        })
        self.env.flush_all()
        # a sealed column carrying a stale binding, written past the constraint
        # exactly as a legacy database could have carried one
        self.env.cr.execute(
            "UPDATE hr_formula_rule SET source_binding='excel', "
            "source_binding_key='Stale' WHERE id = %s", (sealed.id,))
        self._become_pre_j9(made | sealed)
        self.assertEqual(self.Source.search_count(
            [('rule_id', 'in', (made | sealed).ids)]), 0)

        self._run_j9_migration()
        self.assertEqual(
            self.Source.search_count([('rule_id', 'in', made.ids)]), 13,
            "thirteen bindings, thirteen rows — abm's shape exactly")
        self.assertEqual(
            self.Source.search_count([('rule_id', '=', sealed.id)]), 0,
            "a sealed column must not be converted: `_check_source_binding` "
            "raises on one, and an upgrade that aborts half-way through a "
            "ninety-nine-column scheme is the failure this guard exists for")
        first = self.Source.search([('rule_id', '=', self.bonus.id)])
        self.assertEqual(first.kind, 'excel')
        self.assertEqual(first.key, 'Bonus Col')
        self.assertEqual(first.origin, 'board',
                         "origin/date/uid travel across; a migration that "
                         "forgets them turns a person's decision into the "
                         "system's guess")
        self.assertEqual(self.bonus.source_binding, 'excel')
        self.assertEqual(self.bonus.source_binding_key, 'Bonus Col')

        # idempotent: a second run changes nothing
        before = sorted(self.Source.search(
            [('rule_id', 'in', made.ids)]).mapped(
                lambda s: (s.rule_id.id, s.kind, s.key)))
        self._run_j9_migration()
        after = sorted(self.Source.search(
            [('rule_id', 'in', made.ids)]).mapped(
                lambda s: (s.rule_id.id, s.kind, s.key)))
        self.assertEqual(before, after)
        self.assertEqual(
            self.Source.search_count([('rule_id', 'in', made.ids)]), 13)

    # =====================================================================
    # 14 — T6. `binding_dangling`, per source.
    # =====================================================================
    def test_14_dangling_is_per_source_and_excel_is_never_one(self):
        conn = self._connector('J9 Catalogue')
        self._config('J9 Dangling', connector=conn)
        self.bonus.set_source_binding('excel', 'Nothing Answers To This')
        self.assertFalse(self.bonus.binding_dangling,
                         "a spreadsheet column exists when a spreadsheet is "
                         "uploaded; calling it dangling because no file happens "
                         "to be loaded is a false alarm on every fresh scheme")

        FM = self.env['hr.integration.field.mapping']
        catalogue = [{'path': 'Employee_Id'}, {'path': 'Bank_Name'}]
        with patch.object(type(FM), 'get_available_source_fields',
                          lambda self, *a, **k: catalogue):
            self.env.invalidate_all()
            self.bonus.set_source_binding('feed', 'Bank_Name')
            self.env.invalidate_all()
            self.assertFalse(self.bonus.binding_dangling)
            self.bonus.set_source_binding('feed', 'Gone_Away')
            self.env.invalidate_all()
            self.assertTrue(self.bonus.binding_dangling)

        # An EMPTY catalogue means the connector has never synced. That is
        # UNKNOWN, not gone, and it must not raise a false alarm.
        with patch.object(type(FM), 'get_available_source_fields',
                          lambda self, *a, **k: []):
            self.env.invalidate_all()
            self.assertFalse(self.bonus.binding_dangling)

    def test_14b_one_dangling_source_among_several_raises_the_flag(self):
        conn = self._connector('J9 Catalogue B')
        self._config('J9 Dangling B', connector=conn)
        FM = self.env['hr.integration.field.mapping']
        with patch.object(type(FM), 'get_available_source_fields',
                          lambda self, *a, **k: [{'path': 'Known'}]):
            self.bonus.set_source_binding('excel', 'A Column')
            self.bonus.set_source_binding('feed', 'Known')
            self.env.invalidate_all()
            self.assertFalse(self.bonus.binding_dangling)
            self.bonus.set_source_binding('feed', 'Vanished')
            self.env.invalidate_all()
            self.assertTrue(self.bonus.binding_dangling)
            self.assertEqual(
                sorted(s.kind for s in self.bonus.source_ids
                       if s.dangling), ['feed'])
