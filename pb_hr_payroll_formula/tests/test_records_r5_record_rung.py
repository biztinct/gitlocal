# -*- coding: utf-8 -*-
"""RECORDS RD45 — the rung the file-less resolver never had.

A pay run computed WITHOUT a pay-data file goes through
`hr.payslip._get_formula_input_values`, and that function knew only two of the
ladder's rungs: the connected system, then the tail (a contract-wage special
case, worked-days lines, the component's default). Rank 4 — the mapped
employee/contract field — and rank 5 — the contract component — were simply
absent, so a component pointed at a record fell to its default however plainly
the record answered, and the SAME month produced a different gross depending
only on whether a pay-data file had been uploaded. The Source Atlas reported it honestly and nobody could act
on it: *"Payobook records — nothing in this run came this way"*, on a tenant
with twenty-one such mappings.

The bill on the reference tenant was the entire deduction side. `SHUIPARTICIP`
is mapped to `hr.contract.shuipart`, which read YES on every contract, and each
insurance line is `IF(SHUIPARTICIP="YES", …, 0)`. The component resolved to 0,
every gate took the zero leg, and thirty-six payslips reported ₫0.00 deducted.

What is asserted here, in order:

  * the record rung delivers, and says so in the product's own vocabulary;
  * it does NOT outrank the feed, and is not even READ when the feed answered —
    the walk's laziness contract, asserted as "the read did not happen" rather
    than "the value differs" (J10's case 6);
  * `0` and `False` are values and a NULL column is not (MJ15);
  * rank 5 (the contract component) joined it on the owner's ruling — a
    contract line that says zero HAS answered, and a component the contract
    does not mention at all falls to zero, exactly as a file-fed run resolves
    it (`test_06*`);
  * a component with no mapping resolves exactly as it did before, which is the
    neutrality rail: nothing that works today may move.
"""
import json

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRecordsRecordRung(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Mapping = cls.env['hr.payslip.import.mapping']
        cls.Connector = cls.env['hr.integration.connector']
        cls.FieldMapping = cls.env['hr.integration.field.mapping']
        cls.Store = cls.env['hr.api.data.store']
        cls.Fields = cls.env['ir.model.fields']

    # ------------------------------------------------------------- fixtures
    def _fixture(self, code='SHUIPART', field='shuipart',
                 model='hr.contract', **rule_vals):
        cfg = self.Config.create({
            'name': 'RD45 %s' % code, 'code': 'RD45%s' % code,
            'country_code': 'VN', 'state': 'active',
        })
        vals = {'config_id': cfg.id, 'name': code, 'code': code,
                'column_type': 'input', 'sequence': 1, 'default_value': 0.0}
        vals.update(rule_vals)
        rule = self.Rule.create(vals)
        company = self.env.company
        emp = self.env['hr.employee'].create({
            'name': 'RD45 Subject', 'company_id': company.id})
        # Created explicitly, never searched for: a bare employee has no
        # contract in this build, and a fixture that skipped itself when it
        # found none would silently retire every assertion that matters here.
        contract = self.env['hr.contract'].create({
            'name': 'RD45 contract', 'employee_id': emp.id, 'wage': 1000.0,
            'state': 'open', 'date_start': '2020-01-01',
            'company_id': company.id,
        })
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'name': 'RD45 Slip',
            'formula_config_id': cfg.id, 'contract_id': contract.id,
        })
        return cfg, rule, emp, contract, slip

    def _map(self, cfg, rule, model, field):
        return self.Mapping.create({
            'salary_structure_id': cfg.id,
            'component_id': rule.id,
            'destination_type': 'field',
            'target_model_id': self.env['ir.model']._get_id(model),
            'target_field_id': self.Fields._get(model, field).id,
        })

    def _advantage(self, contract, code, amount):
        """A contract component line, the way a contract really carries one."""
        Tmpl = self.env['hr.contract.advantage.template']
        tmpl = Tmpl.search([('code', '=', code)], limit=1) or Tmpl.create({
            'name': code.title(), 'code': code})
        return self.env['hr.contract.advantage'].create({
            'contract_id': contract.id,
            'advantage_template_id': tmpl.id,
            'amount': amount,
        })

    def _resolve(self, slip, cfg):
        prov = {}
        return slip._get_formula_input_values(cfg, provenance=prov), prov

    # =====================================================================
    # 1 — the rung delivers (the ABM failure, reproduced and closed)
    # =====================================================================
    def test_01a_a_mapped_contract_field_reaches_the_payslip(self):
        cfg, rule, _e, contract, slip = self._fixture()
        contract.shuipart = 'YES'
        self._map(cfg, rule, 'hr.contract', 'shuipart')

        values, prov = self._resolve(slip, cfg)

        self.assertEqual(
            values['SHUIPART'], 'YES',
            "before RD45 this was the component's default of 0.0, and every "
            "IF(...=\"YES\") gate above it took the zero leg")
        self.assertEqual(prov['SHUIPART']['src'], 'employee_field',
                         "the Source Atlas lane the owner was told was empty")
        self.assertEqual(prov['SHUIPART']['via'], 'employee_mapping')
        self.assertEqual(prov['SHUIPART']['key'], 'shuipart')

    def test_01b_the_selection_arrives_as_a_word_a_formula_can_compare(self):
        """`_streq(raw_values.get('SHUIPART'), 'YES')` has to be able to match."""
        cfg, rule, _e, contract, slip = self._fixture()
        contract.shuipart = 'YES'
        self._map(cfg, rule, 'hr.contract', 'shuipart')
        values, _prov = self._resolve(slip, cfg)
        self.assertTrue(rule._streq(values['SHUIPART'], 'YES'))

    def test_01c_a_mapped_employee_field_is_the_same_rung(self):
        cfg, rule, emp, _c, slip = self._fixture(code='WORKEMAIL')
        emp.work_email = 'rd45@example.com'
        self._map(cfg, rule, 'hr.employee', 'work_email')
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(values['WORKEMAIL'], 'rd45@example.com')
        self.assertEqual(prov['WORKEMAIL']['src'], 'employee_field',
                         "employee and contract are ONE lane — 'Payobook "
                         "records' — and `via` is what says which record")

    # =====================================================================
    # 2 — rank, and the laziness contract that goes with it
    # =====================================================================
    def test_02a_the_feed_still_outranks_the_record(self):
        cfg, rule, emp, contract, slip = self._fixture(code='OTHOURS')
        connector = self.Connector.create({'name': 'RD45', 'connector_type': 'demo'})
        cfg.connector_id = connector.id
        self.FieldMapping.create({
            'connector_id': connector.id, 'target_rule_id': rule.id,
            'source_field': 'OT', 'active_state': 'active',
        })
        self.Store.create({
            'connector_id': connector.id, 'data_type': 'salary',
            'employee_id': emp.id, 'employee_external_id': 'R1',
            'raw_payload': {'OT': 12}, 'extracted_data': {'OT': 12},
            'state': 'extracted',
        })
        if contract:
            contract.wage = 999.0
            self._map(cfg, rule, 'hr.contract', 'wage')

        values, prov = self._resolve(slip, cfg)

        self.assertEqual(values['OTHOURS'], 12,
                         "J-D5: no rung moves. The feed is rank 1 and stays it")
        self.assertEqual(prov['OTHOURS']['src'], 'feed')

    def test_02b_a_record_that_is_outranked_is_never_even_read(self):
        """Case 6's shape: assert the READ did not happen, not that it lost.

        A tier that is merely outranked is still a query per component on every
        payslip of every run, and still a claim the card would make without
        evidence.
        """
        cfg, rule, emp, contract, slip = self._fixture(code='OTHOURS')
        connector = self.Connector.create({'name': 'RD45b', 'connector_type': 'demo'})
        cfg.connector_id = connector.id
        self.FieldMapping.create({
            'connector_id': connector.id, 'target_rule_id': rule.id,
            'source_field': 'OT', 'active_state': 'active',
        })
        self.Store.create({
            'connector_id': connector.id, 'data_type': 'salary',
            'employee_id': emp.id, 'employee_external_id': 'R2',
            'raw_payload': {'OT': 7}, 'extracted_data': {'OT': 7},
            'state': 'extracted',
        })
        self._map(cfg, rule, 'hr.contract', 'wage')

        Batch = type(self.env['hr.payroll.import.batch'])
        with patch.object(Batch, '_mapped_record_value',
                          autospec=True) as read:
            values, _prov = self._resolve(slip, cfg)
        self.assertEqual(values['OTHOURS'], 7)
        read.assert_not_called()

    # =====================================================================
    # 3 — emptiness, exactly as the batch resolver spells it
    # =====================================================================
    def test_03a_a_null_column_is_not_an_answer(self):
        cfg, rule, emp, _c, slip = self._fixture(code='WORKEMAIL')
        emp.work_email = False
        self._map(cfg, rule, 'hr.employee', 'work_email')
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(values['WORKEMAIL'], rule.default_value,
                         "`False` is how Odoo spells NULL on a Char — a column "
                         "holding nothing chose nothing (MJ15)")
        self.assertEqual(prov['WORKEMAIL']['via'], 'default')

    def test_03b_zero_is_a_value(self):
        cfg, rule, _e, contract, slip = self._fixture(code='BASESAL')
        rule.default_value = 500.0
        contract.wage = 0.0
        self._map(cfg, rule, 'hr.contract', 'wage')
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(values['BASESAL'], 0.0,
                         "a record saying zero has answered the question")
        self.assertEqual(prov['BASESAL']['src'], 'employee_field')

    # =====================================================================
    # 4 — the neutrality rail
    # =====================================================================
    def test_04a_a_component_with_no_mapping_resolves_as_before(self):
        cfg, rule, _e, _c, slip = self._fixture(code='NOTHING')
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(values['NOTHING'], rule.default_value)
        self.assertEqual(prov['NOTHING']['src'], 'none')
        self.assertEqual(prov['NOTHING']['via'], 'default')

    def test_04b_a_mapping_on_another_scheme_is_not_this_scheme_s(self):
        cfg, rule, _e, contract, slip = self._fixture()
        contract.shuipart = 'YES'
        other = self.Config.create({
            'name': 'RD45 Other', 'code': 'RD45OTHER',
            'country_code': 'VN', 'state': 'active',
        })
        self.Mapping.create({
            'salary_structure_id': other.id,
            'component_id': rule.id,
            'destination_type': 'field',
            'target_model_id': self.env['ir.model']._get_id('hr.contract'),
            'target_field_id': self.Fields._get('hr.contract', 'shuipart').id,
        })
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(values['SHUIPART'], rule.default_value)
        self.assertEqual(prov['SHUIPART']['via'], 'default')

    # =====================================================================
    # 5 — "Recompute" has to be able to SEE a change
    # =====================================================================
    def _recompute_fixture(self):
        """A payslip that already carries a resolved input blob.

        `appears_on_payslip=False` because these cases are about the INPUT
        blob, and a component that renders needs a salary-rule category
        (`hr_payslip_line.category_id` is NOT NULL) that has nothing to do
        with what is being asserted.
        """
        cfg, rule, emp, contract, slip = self._fixture(appears_on_payslip=False)
        self._map(cfg, rule, 'hr.contract', 'shuipart')
        slip.calculation_method = 'formula'
        slip.formula_input_values = json.dumps({'SHUIPART': 0.0})
        slip.formula_input_sources = json.dumps(
            {'SHUIPART': {'src': 'none', 'key': None, 'via': 'default'}})
        return cfg, rule, emp, contract, slip

    def test_05a_recompute_picks_up_a_changed_record(self):
        """The owner's actual sequence: change the field, press the button."""
        _cfg, _r, _e, contract, slip = self._recompute_fixture()
        contract.shuipart = 'YES'

        slip.action_recompute_formula_lines()

        self.assertEqual(
            json.loads(slip.formula_input_values)['SHUIPART'], 'YES',
            "the button says 'recalculated with current settings' — before "
            "RD45 it reused the stale blob and could not see any setting")
        self.assertEqual(
            json.loads(slip.formula_input_sources)['SHUIPART']['src'],
            'employee_field')

    def test_05b_a_value_no_live_source_can_supply_is_not_erased(self):
        """What the old reuse was protecting, kept.

        A spreadsheet's numbers survive only in this blob once the import line
        is gone, and `pb_demo` stages values onto a payslip the same way. A
        code nothing can source today keeps what it had.
        """
        _cfg, _r, _e, contract, slip = self._recompute_fixture()
        contract.shuipart = False
        slip.formula_input_values = json.dumps(
            {'SHUIPART': 0.0, 'FROMAFILE': 12345.0})
        slip.formula_input_sources = json.dumps(
            {'FROMAFILE': {'src': 'excel', 'key': 'Some column',
                           'via': 'header'}})

        slip.action_recompute_formula_lines()

        values = json.loads(slip.formula_input_values)
        self.assertEqual(values['FROMAFILE'], 12345.0,
                         "nothing answers for this code today, so the payslip's "
                         "own record of it is the better one")
        self.assertEqual(
            json.loads(slip.formula_input_sources)['FROMAFILE']['src'], 'excel')

    # =====================================================================
    # 6 — rank 5, the contract component (RD46, on the owner's ruling)
    # =====================================================================
    def test_06a_a_contract_line_that_says_zero_has_answered(self):
        """The ₫243,000,000 case, as a rule rather than as an anecdote."""
        cfg, rule, _e, contract, slip = self._fixture(code='PAIDLEAVE')
        rule.default_value = 6750000.0
        rule.is_contract_component = True
        self._advantage(contract, 'PAIDLEAVE', 0.0)

        values, prov = self._resolve(slip, cfg)

        self.assertEqual(values['PAIDLEAVE'], 0.0,
                         "a contract line saying zero is an answer (MJ15) and "
                         "outranks the component's default")
        self.assertEqual(prov['PAIDLEAVE']['src'], 'contract_component')
        self.assertEqual(prov['PAIDLEAVE']['via'], 'contract')

    def test_06b_a_real_contract_amount_reaches_the_payslip(self):
        cfg, rule, _e, contract, slip = self._fixture(code='PAIDLEAVE')
        rule.is_contract_component = True
        self._advantage(contract, 'PAIDLEAVE', 4200.0)
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(values['PAIDLEAVE'], 4200.0)
        self.assertEqual(prov['PAIDLEAVE']['via'], 'contract')

    def test_06c_a_contract_component_the_contract_never_mentions_is_zero(self):
        """The batch resolver's `contract_component_default` branch, matched."""
        cfg, rule, _e, _c, slip = self._fixture(code='PAIDLEAVE')
        rule.default_value = 6750000.0
        rule.is_contract_component = True
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(values['PAIDLEAVE'], 0.0)
        self.assertEqual(prov['PAIDLEAVE']['via'], 'contract_default')

    def test_06d_an_ordinary_component_still_keeps_its_default(self):
        """The rung is for contract components. Nothing else may lose a default."""
        cfg, rule, _e, _c, slip = self._fixture(code='ALLOWANCE')
        rule.default_value = 999.0
        rule.is_contract_component = False
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(values['ALLOWANCE'], 999.0)
        self.assertEqual(prov['ALLOWANCE']['via'], 'default')

    def test_06e_the_record_field_still_outranks_the_contract_component(self):
        cfg, rule, _e, contract, slip = self._fixture()
        rule.is_contract_component = True
        contract.shuipart = 'YES'
        self._map(cfg, rule, 'hr.contract', 'shuipart')
        self._advantage(contract, 'SHUIPART', 0.0)
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(values['SHUIPART'], 'YES',
                         "J-D5: rank 4 is above rank 5 and stays there")
        self.assertEqual(prov['SHUIPART']['src'], 'employee_field')

    def test_04c_the_record_is_read_through_the_batch_resolver_s_function(self):
        """One reading of a record, not two.

        The rung calls `_mapped_record_value` and `_contract_component_amounts`
        — the same functions the import-batch tail calls — so the file-less run
        and the file-fed run cannot come to different conclusions about what a
        field holds.
        """
        # NOT `inspect.getsource(type(env['hr.payslip'])…)`: two bridge modules
        # (`pb_trip_payroll_bridge`, `pb_workforce_payroll_bridge`) override
        # this method and call super, so the registry class resolves to
        # WHICHEVER loaded last and the assertion would be about their file.
        # The claim is about THIS module's implementation, so read it.
        import os
        import re

        from odoo.modules.module import get_module_path
        path = os.path.join(get_module_path('pb_hr_payroll_formula'),
                            'models', 'hr_payslip_formula.py')
        with open(path, encoding='utf-8') as fh:
            body = fh.read().split('def _get_formula_input_values', 1)[1]
        body = re.split(r'\n    def ', body, maxsplit=1)[0]

        self.assertIn('_mapped_record_value', body)
        # RD46 — rank 5 joined it once the owner ruled on it, and it must read
        # the contract through the batch resolver's function for the same
        # reason rank 4 does.
        self.assertIn('_contract_component_amounts', body)
        self.assertNotIn('getattr(record,', body,
                         "a second implementation of 'read the record' is the "
                         "failure this rung exists inside of")
