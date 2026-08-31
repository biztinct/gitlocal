# -*- coding: utf-8 -*-
"""SC-3 — a scheme chooses WHICH sources feed it, and WHO WINS.

The standing behaviour, now merely the DEFAULT: the connected system speaks
first, the spreadsheet answers when it is silent, Payobook's own records come
last — and the connected system writes back over whatever it maps. The
owner's requirement is that this become the scheme's choice: three lanes
(api / excel / records) that can be switched off and reordered, where the
order decides the pay run AND the writeback. A lane below the records lane
may only FILL an empty box; it may never overwrite a value Payobook already
holds (owner ruling, 2026-08-31).

The regression pin (case 1) is the most important test in this file: an
untouched scheme must produce today's rank tuple BIT FOR BIT.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSc3SourceLanes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Rule = cls.env['hr.formula.rule']

    def _scheme(self, code, **vals):
        return self.env['hr.formula.config'].create(dict({
            'name': 'SC3 %s' % code, 'code': code, 'country_code': 'VN',
            'state': 'active'}, **vals))

    def _component(self, cfg, code, name='Base pay', **vals):
        return self.Rule.create(dict({
            'config_id': cfg.id, 'name': name, 'code': code,
            'column_type': 'input'}, **vals))

    def _world(self, code, **cfg_vals):
        """A scheme + employee + contract + a component declaring a feed key
        + a record mapping onto the contract's wage."""
        cfg = self._scheme(code, **cfg_vals)
        rule = self._component(cfg, '%sPAY' % code)
        rule.set_source_binding('feed', 'Base_Salary', origin='board')
        employee = self.env['hr.employee'].create({'name': 'SC3 %s' % code})
        contract = self.env['hr.contract'].create({
            'name': 'SC3 c %s' % code, 'employee_id': employee.id,
            'wage': 10800000.0, 'date_start': '2026-01-01'})
        model = self.env['ir.model']._get('hr.contract')
        field = self.env['ir.model.fields']._get('hr.contract', 'wage')
        mapping = self.env['hr.payslip.import.mapping'].create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'field',
            'target_model_id': model.id, 'target_field_id': field.id,
        })
        batch = self.Batch.create({
            'name': 'SC3 batch %s' % code, 'source_type': 'excel',
            'formula_config_id': cfg.id})
        return cfg, rule, employee, contract, mapping, batch

    # =====================================================================
    # 1 — the regression pin
    # =====================================================================
    def test_01_the_default_reproduces_todays_order_bit_for_bit(self):
        cfg = self._scheme('SC3DEF')
        self.assertEqual(
            cfg._source_kind_rank(),
            self.Rule._SOURCE_RANK + ('contract_component',),
            "an untouched scheme must resolve exactly as every scheme has "
            "resolved until today — this is the whole neutrality argument")
        rule = self._component(cfg, 'SC3DEFPAY')
        self.assertEqual(rule._config_kind_rank(), cfg._source_kind_rank())

    # =====================================================================
    # 2/3 — records as the source of truth
    # =====================================================================
    def test_02_records_first_a_filled_box_wins_and_is_never_overwritten(self):
        cfg, rule, employee, contract, mapping, batch = self._world(
            'SC3RF', source_priority='records,api,excel')
        raw = {'Base_Salary': 18500000.0}
        # The pay run reads the record, not the payload.
        hits = batch._declared_source_walk(
            rule, {'excel': raw, 'feed': {}}, mapping=mapping,
            contract=contract, employee=employee)
        self.assertTrue(hits)
        self.assertEqual(hits[0]['tier'], 'record')
        self.assertEqual(hits[0]['value'], 10800000.0)
        # And the writeback refuses to touch the box.
        value, has_value = batch._writeback_raw_value(
            raw, rule, mapping=mapping, contract=contract, employee=employee)
        self.assertFalse(has_value,
                         "records are the source of truth here — a payload "
                         "may not overwrite a value Payobook already holds")

    def test_03_records_first_an_empty_box_is_still_filled(self):
        cfg, rule, employee, contract, mapping, batch = self._world(
            'SC3EF', source_priority='records,api,excel')
        contract.wage = 0.0
        # A wage of zero IS a value (MJS15) — so empty here means the record
        # mapping pointing at a field that answers nothing: point the mapping
        # at a genuinely empty text field instead.
        field = self.env['ir.model.fields']._get('hr.contract', 'notes')
        mapping.target_field_id = field.id
        raw = {'Base_Salary': 18500000.0}
        hits = batch._declared_source_walk(
            rule, {'excel': raw, 'feed': {}}, mapping=mapping,
            contract=contract, employee=employee)
        self.assertTrue(hits)
        self.assertEqual(hits[0]['tier'], 'blob',
                         "the record is silent, so the payload answers")
        value, has_value = batch._writeback_raw_value(
            raw, rule, mapping=mapping, contract=contract, employee=employee)
        self.assertTrue(has_value,
                        "filling an EMPTY box is allowed — only overwriting "
                        "is not (owner ruling)")
        self.assertEqual(value, 18500000.0)

    # =====================================================================
    # 4 — excel outranking the connected system
    # =====================================================================
    def test_04_excel_first_beats_the_feed_and_yields_when_silent(self):
        cfg, rule, employee, contract, mapping, batch = self._world(
            'SC3XF', source_priority='excel,api,records')
        rule.set_source_binding('excel', 'Base pay column', origin='board')
        both = {'excel': {'Base pay column': 19200000.0},
                'feed': {'Base_Salary': 18500000.0}}
        hits = batch._declared_source_walk(
            rule, both, mapping=mapping, contract=contract, employee=employee)
        self.assertEqual(hits[0]['kind'], 'excel')
        self.assertEqual(hits[0]['value'], 19200000.0)
        silent = {'excel': {}, 'feed': {'Base_Salary': 18500000.0}}
        hits = batch._declared_source_walk(
            rule, silent, mapping=mapping, contract=contract,
            employee=employee)
        self.assertEqual(hits[0]['value'], 18500000.0,
                         "a higher lane that is silent yields to the next")

    # =====================================================================
    # 5/6 — switching a lane off
    # =====================================================================
    def test_05_a_disabled_lane_is_not_read_at_all(self):
        cfg, rule, employee, contract, mapping, batch = self._world(
            'SC3OFF', source_api_enabled=False)
        self.assertNotIn('feed', cfg._source_kind_rank())
        self.assertNotIn(
            'feed', [d['kind'] for d in rule.declared_sources()],
            "a disabled lane's declared source drops out of the plan — that "
            "one filter is the gate every consumer inherits")
        hits = batch._declared_source_walk(
            rule, {'excel': {}, 'feed': {'Base_Salary': 18500000.0}},
            mapping=mapping, contract=contract, employee=employee)
        self.assertTrue(all(h['kind'] != 'feed' for h in hits))

    def test_06_records_lane_off_leaves_the_mapped_field_unread(self):
        cfg, rule, employee, contract, mapping, batch = self._world(
            'SC3NR', source_records_enabled=False)
        hits = batch._declared_source_walk(
            rule, {'excel': {}, 'feed': {}}, mapping=mapping,
            contract=contract, employee=employee)
        self.assertFalse(hits,
                         "nothing declared delivers and the record lane is "
                         "off — the walk must come back empty-handed")

    # =====================================================================
    # 7 — the file-less resolver agrees
    # =====================================================================
    def test_07_the_fileless_resolver_honours_the_same_order(self):
        cfg, rule, employee, contract, mapping, batch = self._world(
            'SC3FL', source_priority='records,api,excel')
        payslip = self.env['hr.payslip'].create({
            'name': 'SC3 slip', 'employee_id': employee.id,
            'contract_id': contract.id, 'formula_config_id': cfg.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
        })
        values = payslip._get_formula_input_values(cfg)
        self.assertEqual(
            values.get(rule.code), 10800000.0,
            "records-first must mean records-first on BOTH resolvers — the "
            "same month giving two answers depending on how it was run is "
            "the drift RD45 closed and this must not reopen")

    # =====================================================================
    # 8 — the stored badge follows the setting
    # =====================================================================
    def test_08_the_top_source_badge_reorders_with_the_priority(self):
        cfg, rule, employee, contract, mapping, batch = self._world('SC3BD')
        rule.set_source_binding('excel', 'Base pay column', origin='board')
        self.assertEqual(rule.source_binding, 'feed',
                         "default order: the connected system speaks first")
        cfg.source_priority = 'excel,api,records'
        self.assertEqual(rule.source_binding, 'excel',
                         "reordering the lanes must move the stored badge — "
                         "that is what the depends on the config fields buys")
        cfg.source_excel_enabled = False
        self.assertEqual(rule.source_binding, 'feed',
                         "a disabled lane's source may not be the badge")

    def test_09_a_bad_priority_string_is_refused(self):
        from odoo.exceptions import ValidationError
        cfg = self._scheme('SC3BAD')
        with self.assertRaises(ValidationError):
            cfg.source_priority = 'api,excel,records,api'
        with self.assertRaises(ValidationError):
            cfg.source_priority = 'api,excel,files'
