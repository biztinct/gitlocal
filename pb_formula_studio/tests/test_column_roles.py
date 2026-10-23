# -*- coding: utf-8 -*-
"""COLROLES Phase 2 — the lens's server contract.

Phase 1 gave every column a role. This phase makes the role VISIBLE, and the
visible part is OWL: what a test can actually hold still is the four server
promises the cockpit is built on top of, each of which fails silently if it
breaks.

  * the serializer emits the role keys at all. The client guards with
    `c.column_role || 'payroll'`, which means a serializer that stopped sending
    them would look exactly like a structure in which everything is payroll —
    the decluttered sidebar would simply stop decluttering, with no error
    anywhere (test 1);
  * `_group_for` sends every non-payroll role to People & Data and leaves the
    payroll buckets byte-identical. Both halves matter: the second is the
    regression that would quietly re-file real pay components (test 2);
  * a role chosen in the editor is recorded as chosen BY A PERSON. If the
    source stayed 'auto', the next classifier run would overwrite the human's
    decision and nothing would report it (CR-A1, test 3);
  * the bulk whitelist accepts the role and still rejects everything else, so a
    stray key can never mass-mutate formulas (test 4);
  * the five role health checks fire on a structure that has those faults and
    stay silent on one that does not (test 5) — a lint that never fires and a
    lint that always fires are equally useless.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_formula_studio.models.pb_formula_studio import _group_for, PEOPLE_GROUP


@tagged('post_install', '-at_install')
class TestColumnRoles(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Mapping = cls.env['hr.payslip.import.mapping']

    # ------------------------------------------------------------- fixtures
    def _config(self, name):
        return self.Config.create({
            'name': name, 'code': name.replace(' ', '_').replace('—', '').upper()[:32],
            'country_code': 'VN', 'state': 'active',
        })

    def _rule(self, cfg, code, seq, **kw):
        vals = {
            'config_id': cfg.id, 'name': kw.pop('name', code.title()), 'code': code,
            'column_type': kw.pop('column_type', 'input'), 'sequence': seq,
        }
        vals.update(kw)
        return self.Rule.create(vals)

    def _map(self, cfg, rule, field_name='name'):
        """One import mapping row pointing at `rule` — enough to make the
        'goes nowhere' checks consider the column routed."""
        model = self.env['ir.model']._get('hr.employee')
        field = self.env['ir.model.fields']._get('hr.employee', field_name)
        return self.Mapping.create({
            'target_model_id': model.id, 'target_field_id': field.id,
            'salary_structure_id': cfg.id, 'component_id': rule.id,
        })

    def _kinds(self, cfg):
        res = self.Studio.get_problems(cfg.id)
        self.assertTrue(res.get('ok'))
        return [p['kind'] for p in res['problems']]

    # ------------------------------------------------------------- test 1
    def test_01_serializer_emits_role_keys(self):
        cfg = self._config('COLROLES probe serializer')
        self._rule(cfg, 'MSNV', 10, column_role='identity', column_role_source='auto')
        self._rule(cfg, 'BASIC', 20)

        data = self.Studio.get_studio_data(cfg.id)
        comps = {c['code']: c for c in data['components']}
        self.assertEqual(set(comps), {'MSNV', 'BASIC'})
        for c in comps.values():
            for key in ('column_role', 'column_role_source', 'is_contract_component',
                        'is_text_component', 'is_visible_in_grid'):
                self.assertIn(key, c, "serializer dropped %s" % key)
        self.assertEqual(comps['MSNV']['column_role'], 'identity')
        self.assertEqual(comps['MSNV']['column_role_source'], 'auto')
        # a column nobody re-filed still reads as payroll, never as empty
        self.assertEqual(comps['BASIC']['column_role'], 'payroll')

    # ------------------------------------------------------------- test 2
    def test_02_group_for_role_wins_and_payroll_is_unchanged(self):
        cfg = self._config('COLROLES probe grouping')
        # every non-payroll role leaves the payroll buckets…
        for i, role in enumerate(('identity', 'profile', 'contract', 'bank', 'reference')):
            r = self._rule(cfg, 'PPL%d' % i, 10 + i, column_role=role)
            self.assertEqual(_group_for(r), PEOPLE_GROUP, "role %s stayed in payroll" % role)
        # …even when the NAME screams Deductions (the role wins over the lexicon)
        taxref = self._rule(cfg, 'TAXCODE', 60, name='Tax code', column_role='reference')
        self.assertEqual(_group_for(taxref), PEOPLE_GROUP)

        # Regression: payroll rules bucket exactly as before. (The codes here are
        # chosen to avoid the grouping lexicon's substring hits — 'BASIC' has
        # always landed in Deductions because it contains 'SI'. That is
        # pre-existing behaviour and this phase deliberately does not touch it.)
        cases = [
            (self._rule(cfg, 'HOURS', 70, column_type='input'), 'Inputs'),
            (self._rule(cfg, 'ALLOW', 80, column_type='formula', name='Allowance'), 'Earnings'),
            (self._rule(cfg, 'PIT', 90, column_type='formula', name='Personal income tax'), 'Deductions'),
            (self._rule(cfg, 'NETPAY', 100, column_type='formula', name='Net pay'), 'Totals'),
        ]
        for rule, expected in cases:
            self.assertEqual(_group_for(rule), expected, "%s moved" % rule.code)

    # ------------------------------------------------------------- test 3
    def test_03_save_component_marks_the_role_as_chosen(self):
        cfg = self._config('COLROLES probe source')
        rule = self._rule(cfg, 'BANKNO', 10)
        self.assertEqual(rule.column_role_source, 'auto')

        res = self.Studio.save_component(rule.id, {'column_role': 'bank'})
        self.assertTrue(res.get('ok'), res)
        rule.invalidate_recordset()
        self.assertEqual(rule.column_role, 'bank')
        self.assertEqual(rule.column_role_source, 'user',
                         "a role chosen in the editor must not stay auto-classified")

        # the editor payload reports it back so the picker can say who decided
        payload = self.Studio.get_component_edit(rule.id)
        self.assertEqual(payload['column_role'], 'bank')
        self.assertEqual(payload['column_role_source'], 'user')
        self.assertIn('is_text_component', payload)

        # a save that does NOT touch the role leaves an auto row auto
        other = self._rule(cfg, 'BASIC', 20)
        self.Studio.save_component(other.id, {'name': 'Basic pay'})
        other.invalidate_recordset()
        self.assertEqual(other.column_role_source, 'auto')

    # ------------------------------------------------------------- test 4
    def test_04_bulk_accepts_role_and_rejects_the_rest(self):
        cfg = self._config('COLROLES probe bulk')
        rules = [self._rule(cfg, 'C%d' % i, 10 + i) for i in range(3)]
        ids = [r.id for r in rules]

        res = self.Studio.bulk_update_components(ids, {'column_role': 'profile'})
        self.assertTrue(res.get('ok'), res)
        for r in rules:
            r.invalidate_recordset()
            self.assertEqual(r.column_role, 'profile')
            self.assertEqual(r.column_role_source, 'user')

        with self.assertRaises(UserError):
            self.Studio.bulk_update_components(ids, {'excel_formula': '=1'})
        # the rejected call wrote nothing
        for r in rules:
            r.invalidate_recordset()
            self.assertEqual(r.column_role, 'profile')

    # ------------------------------------------------------------- test 5
    def test_05_the_five_role_checks_fire_and_stay_silent(self):
        # -- a structure with all five faults --------------------------------
        bad = self._config('COLROLES probe faults')
        base = self._rule(bad, 'BASIC', 10)                    # A, payroll input
        grade = self._rule(bad, 'GRADE', 20, column_role='contract',
                           is_text_component=True)             # B, read by a formula
        self._rule(bad, 'BANKACC', 30, column_role='bank')     # C, unmapped
        self._rule(bad, 'DOB', 40, column_role='profile')      # D, goes nowhere
        self._rule(bad, 'NOTE', 50, column_role='reference',
                   appears_on_payslip=True)                    # E, printed as pay
        self._rule(bad, 'GROSS', 60, column_type='formula',
                   excel_formula='=%s2*%s2' % (base.column_letter, grade.column_letter))
        kinds = self._kinds(bad)
        for kind in ('noident', 'refinformula', 'bankunmapped', 'idunmapped', 'nonpayslip'):
            self.assertIn(kind, kinds, "%s did not fire on a structure that has it" % kind)

        # -- and one with none of them ---------------------------------------
        # (appears_on_payslip defaults to True, so a correctly-configured people
        # column has to say it is not printed — which is exactly what the
        # 'nonpayslip' check exists to make someone do.)
        good = self._config('COLROLES probe clean')
        ident = self._rule(good, 'MSNV', 10, column_role='identity',
                           appears_on_payslip=False)
        self._map(good, ident, 'employee_id')
        b = self._rule(good, 'PAYBASE', 20)
        self._rule(good, 'ALLOW', 30, column_role='contract',
                   is_contract_component=True, appears_on_payslip=False)
        self._rule(good, 'GROSS', 40, column_type='formula',
                   excel_formula='=%s2*1' % b.column_letter, appears_on_payslip=True)
        kinds = self._kinds(good)
        for kind in ('noident', 'refinformula', 'bankunmapped', 'idunmapped', 'nonpayslip'):
            self.assertNotIn(kind, kinds, "%s fired on a clean structure" % kind)

    # ------------------------------------------------------------- test 5b
    def test_05b_mapped_people_columns_are_not_flagged(self):
        """The 'goes nowhere' checks must be silenced by a real mapping row —
        otherwise they would flag a correctly-configured structure forever."""
        cfg = self._config('COLROLES probe mapped')
        self._rule(cfg, 'MSNV', 10, column_role='identity', is_contract_component=True)
        bank = self._rule(cfg, 'BANKACC', 20, column_role='bank')
        self.assertIn('bankunmapped', self._kinds(cfg))
        self._map(cfg, bank, 'name')
        self.assertNotIn('bankunmapped', self._kinds(cfg))
