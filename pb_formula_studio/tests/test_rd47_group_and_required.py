# -*- coding: utf-8 -*-
"""RD47 — two display faults that made correct payroll look wrong.

1. A REAL EARNING DRAWN AS A DEDUCTION. The studio decided which side of the
   Live Preview a component belongs to by looking for letters INSIDE its code.
   `ACTUBASISALA` ("Actual Basic salary") contains S-I — "ba**si**sala" — so it
   was filed as Social Insurance and rendered with a minus in front of it: a
   ₫30,443,548 earning shown as a negative. `TAXABLEINCOM` (TAX) and the
   SI-HI-UI constants went the same way.

   This codebase has already paid for substring matching once: NETROLE replaced
   `_get_default_category`'s 'SI'/'TAX'-in-code test after it invented ₫5.06bn
   of phantom deductions. The same test survived in the studio's `_group_for`.
   `net_role` — the sign-propagation classifier's own verdict — had
   `ACTUBASISALA` right as `earning` the whole time, and is now asked first.

   The lexicon was wrong in BOTH directions, which only came out while writing
   `test_01f`: `SOCIALINS8` does not contain "SI" either, so Social Insurance
   8% was filed as an EARNING. A real earning drawn with a minus and a real
   deduction drawn without one, from the same rule.

2. NO FORMULA PAYSLIP COULD BE SAVED. The payslip form carries TWO `struct_id`
   fields, and the xpath that relaxes "a structure is required" matches the
   FIRST in document order — which was a duplicate the same view had just added
   to the header. The real field in the sheet kept `required="contract_id"`, so
   every formula payslip (which by design has no structure) refused to save with
   "Missing required fields": from Confirm, from Cancel Payslip, and from any
   button that saves first. It went unnoticed because the buttons people use
   live on the pay run, not inside the payslip.

   The test reads the SERVED ARCH rather than the source file, because "one
   field in the file, two in the browser" is precisely what reading the source
   hides.
"""
import re

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_formula_studio.models.pb_formula_studio import _group_for


@tagged('post_install', '-at_install')
class TestRd47GroupAndRequired(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'RD47', 'code': 'RD47', 'country_code': 'VN',
            'state': 'active',
        })

    def _rule(self, code, name, **vals):
        base = {'config_id': self.cfg.id, 'code': code, 'name': name,
                'column_type': 'formula', 'excel_formula': '=1'}
        base.update(vals)
        return self.env['hr.formula.rule'].create(base)

    # =====================================================================
    # 1 — the classifier decides, not the spelling
    # =====================================================================
    def test_01a_an_earning_whose_code_contains_SI_is_an_earning(self):
        """The reported case, exactly."""
        rule = self._rule('ACTUBASISALA', 'Actual Basic salary',
                          net_role='earning')
        self.assertEqual(
            _group_for(rule), 'Earnings',
            "'ba-SI-sala' contains SI, and the panel drew a ₫30,443,548 "
            "earning with a minus in front of it")

    def test_01b_a_code_containing_TAX_is_not_automatically_a_deduction(self):
        rule = self._rule('TAXABLEINCOM', 'Taxable Income', net_role='earning')
        self.assertEqual(_group_for(rule), 'Earnings')

    def test_01c_a_real_deduction_is_still_a_deduction(self):
        rule = self._rule('SOCIALINS8', 'Social Ins. - 8%', net_role='deduction')
        self.assertEqual(_group_for(rule), 'Deductions')

    def test_01d_net_pay_is_a_total(self):
        rule = self._rule('NETPAY', 'Net Pay', net_role='net')
        self.assertEqual(_group_for(rule), 'Totals')

    def test_01e_the_lexicon_still_covers_what_the_classifier_has_not_reached(self):
        """Neutrality: a component with no verdict resolves exactly as before."""
        rule = self._rule('PITWITHHELD', 'PIT withheld', net_role=False)
        self.assertEqual(_group_for(rule), 'Deductions')

    def test_01f_the_lexicon_missed_real_deductions_TOO(self):
        """Why the classifier had to win, not merely go first.

        `SOCIALINS8` does NOT contain "SI" — S-O-C-I-A-L-I-N-S — and none of
        the other keys match it either, so the name lexicon filed Social
        Insurance 8% as an EARNING. It was wrong in both directions at once:
        a real earning drawn with a minus (`ACTUBASISALA`, which does contain
        SI) and a real deduction drawn without one. That is what substring
        matching buys, and it is why `net_role` is asked first rather than
        consulted as a tie-breaker.
        """
        no_verdict = self._rule('SOCIALINS8', 'Social Ins. - 8%', net_role=False)
        self.assertEqual(_group_for(no_verdict), 'Earnings',
                         "the old behaviour, recorded so the improvement is "
                         "visible rather than assumed")
        with_verdict = self._rule('SOCIALINS9', 'Social Ins. - 8%',
                                  net_role='deduction')
        self.assertEqual(_group_for(with_verdict), 'Deductions')

    def test_01h_an_employer_cost_is_left_exactly_where_it_was(self):
        """Deliberately NOT remapped — see `_NET_ROLE_GROUP`.

        Four buckets, and an employer contribution is a fifth thing: money going
        out, but not off this person's net pay. Filing it under Deductions would
        draw a minus and say something false. Left on the lexicon and flagged,
        rather than quietly moved.
        """
        with_role = self._rule('CONSSOCIINS8', 'Constant Social Ins. - 17.5%',
                               net_role='employer_cost')
        without = self._rule('CONSSOCIINS9', 'Constant Social Ins. - 17.5%',
                             net_role=False)
        self.assertEqual(_group_for(with_role), _group_for(without))

    def test_01g_an_input_is_an_input_whatever_its_role(self):
        rule = self._rule('SHUIPARTICIP', 'SHUI Participation',
                          column_type='input', excel_formula='',
                          net_role='deduction')
        self.assertEqual(_group_for(rule), 'Inputs')

    # =====================================================================
    # 3 — the MINUS SIGN follows the arithmetic, not the column
    # =====================================================================
    def test_03a_the_panel_is_told_what_the_net_formula_does(self):
        """`net_role` has to REACH the client, or it cannot decide the sign."""
        rule = self._rule('TAXABLEINCOM', 'Taxable Income', net_role='info')
        payload = self.env['pb.formula.studio'].get_studio_data(self.cfg.id)
        sent = {c['code']: c for c in payload['components']}
        self.assertIn('net_role', sent[rule.code])
        self.assertEqual(sent[rule.code]['net_role'], 'info')

    def test_03b_only_a_deduction_is_drawn_with_a_minus(self):
        """Read off the template + getter, because that is where the sign lives.

        `TAXABLEINCOM` is a working figure the net formula neither adds nor
        subtracts, and it was rendered as −₫10,890,152 purely because the name
        lexicon had filed it in the Deductions column. Filing and arithmetic are
        two different questions; the minus answers the second one.
        """
        import os
        from odoo.modules.module import get_module_path
        base = get_module_path('pb_formula_studio')
        with open(os.path.join(base, 'static', 'src', 'xml', 'studio.xml'),
                  encoding='utf-8') as fh:
            xml = fh.read()
        self.assertIn('t-if="showsMinus(c)"', xml,
                      "the preview row must ask about net pay, not the column")
        self.assertNotIn('<t t-if="isDeduction(c)">−</t>', xml)

        with open(os.path.join(base, 'static', 'src', 'js', 'formula_studio.js'),
                  encoding='utf-8') as fh:
            js = fh.read()
        body = js.split('showsMinus(c) {', 1)[1].split('\n    }', 1)[0]
        self.assertIn('"deduction"', body)
        # and the column stays the fallback for a component with no verdict
        self.assertIn('isDeduction(c)', body)

    # =====================================================================
    # 2 — a formula payslip can be saved
    # =====================================================================
    def test_02a_every_struct_id_in_the_served_arch_relaxes_for_formulas(self):
        arch = self.env['hr.payslip'].get_views(
            [[False, 'form']])['views']['form']['arch']
        fields = re.findall(r'<field[^>]*name="struct_id"[^>]*/?>', arch)
        self.assertTrue(fields, "the payslip form must still carry struct_id")
        for field in fields:
            m = re.search(r'required="([^"]*)"', field)
            if not m:
                continue
            self.assertIn(
                "calculation_method != 'formula'", m.group(1),
                "a struct_id that is required whenever a contract is set makes "
                "EVERY formula payslip unsaveable — this is the copy the fix "
                "used to miss:\n%s" % field)

    def test_02b_a_formula_payslip_needs_no_structure(self):
        company = self.env.company
        emp = self.env['hr.employee'].create({
            'name': 'RD47 Person', 'company_id': company.id})
        contract = self.env['hr.contract'].create({
            'name': 'RD47 contract', 'employee_id': emp.id, 'wage': 1.0,
            'state': 'open', 'date_start': '2020-01-01',
            'company_id': company.id,
        })
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'contract_id': contract.id,
            'name': 'RD47 Slip', 'calculation_method': 'formula',
            'formula_config_id': self.cfg.id,
        })
        self.assertFalse(slip.struct_id)
        slip.write({'name': 'RD47 Slip (saved)'})   # must not raise
        self.assertEqual(slip.name, 'RD47 Slip (saved)')
