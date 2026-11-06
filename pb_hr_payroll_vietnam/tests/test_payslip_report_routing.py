# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Which payslip document does "Print Payslip" actually print?

Found live on the reference tenant 2026-09-04. A customer imported their own
payslip workbook into their formula config, mapped 15 components into it, and
pressed Print Payslip — and got the LEGACY report instead. That template looks
up every amount by a hard-coded rule code (ATI, OTTAX, ACTTAXI, MONPIT…); their
payroll's 76 components use entirely different codes, so the overlap was ZERO
and the PDF printed 0 on every line it could not resolve. The one real number
on the page was the contract wage, which that template reads directly rather
than by code.

The rule these tests pin: an imported document, when one exists, is the thing
that prints. When there is none, the legacy routing is untouched.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged

THEMED = 'pb_hr_payroll_formula.payslip_themed'
THEMED_ACTION = 'pb_hr_payroll_formula.action_report_payslip_themed'
LEGACY = 'om_hr_payroll.report_payslip'
LEGACY_VN = 'pb_hr_payroll_vietnam.report_payslip_vietnam'


@tagged('post_install', '-at_install')
class TestPayslipReportRouting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'PS Routing Emp'})
        cls.d_from = date(2030, 3, 1)
        cls.d_to = date(2030, 3, 31)
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'PS routing config', 'code': 'PS_ROUTING',
            'country_code': 'VN', 'state': 'draft',
        })

    def _slip(self, **vals):
        base = {
            'name': 'PS routing slip', 'employee_id': self.employee.id,
            'date_from': self.d_from, 'date_to': self.d_to,
        }
        base.update(vals)
        return self.env['hr.payslip'].create(base)

    # ------------------------------------------------- the imported document
    def test_01_an_imported_document_is_what_prints(self):
        self.config.payslip_layout_html = (
            '<table><tr><td>Taxi allowance</td>'
            '<td>{{pb_component:1:value}}</td></tr></table>')
        slip = self._slip(formula_config_id=self.config.id)
        self.assertEqual(slip._get_report_name(), THEMED,
                         "a customer who built a payslip document must get "
                         "that document, not a template keyed on codes their "
                         "payroll does not use")

    def test_02_no_imported_document_keeps_the_legacy_routing(self):
        """Deliberately narrow: this must not change what anybody else prints."""
        self.config.payslip_layout_html = False
        slip = self._slip(formula_config_id=self.config.id)
        self.assertEqual(slip._get_report_name(), LEGACY)

    def test_03_an_empty_editor_is_not_a_document(self):
        """A rich-text field merely opened and closed holds ``<p><br></p>``.
        Routing that at the themed report would print a BLANK page — strictly
        worse than the wrong-but-populated template it replaces."""
        slip = self._slip(formula_config_id=self.config.id)
        for empty in ('<p><br></p>', '<p> </p>', '<p>&nbsp;</p>', '   ',
                      '<div><p><br></p></div>'):
            self.config.payslip_layout_html = empty
            slip.invalidate_recordset()
            self.assertEqual(slip._get_report_name(), LEGACY,
                             "%r is an empty editor, not a document" % empty)

    def test_03b_a_document_with_only_a_token_or_a_table_counts(self):
        slip = self._slip(formula_config_id=self.config.id)
        for real in ('<p>{{pb_meta:employee_name}}</p>',
                     '<table><tr><td></td></tr></table>',
                     '<p><img src="data:image/png;base64,AAA"/></p>',
                     '<p>Payslip</p>'):
            self.config.payslip_layout_html = real
            slip.invalidate_recordset()
            self.assertEqual(slip._get_report_name(), THEMED,
                             "%r is a real document" % real)

    def test_04_a_slip_with_no_config_at_all(self):
        slip = self._slip()
        self.assertEqual(slip._get_report_name(), LEGACY)

    def test_05_the_imported_document_beats_the_vietnam_template_too(self):
        """The VN branch is chosen on the structure name; an imported document
        outranks it, because its owner built it to be printed."""
        struct = self.env['hr.payroll.structure'].search(
            [('name', 'ilike', 'vietnam')], limit=1)
        if not struct:
            self.skipTest('no Vietnam salary structure on this database')
        self.config.payslip_layout_html = '<p>{{pb_meta:employee_name}}</p>'
        slip = self._slip(formula_config_id=self.config.id, struct_id=struct.id)
        self.assertEqual(slip._get_report_name(), THEMED)
        # …and without the document, that same slip still takes the VN branch
        self.config.payslip_layout_html = False
        slip.invalidate_recordset()
        self.assertEqual(slip._get_report_name(), LEGACY_VN)

    # ------------------------------------------------------ multi-selection
    def test_06_printing_several_slips_follows_the_same_rule(self):
        self.config.payslip_layout_html = '<p>{{pb_meta:employee_name}}</p>'
        slips = self._slip(formula_config_id=self.config.id) \
            + self._slip(formula_config_id=self.config.id)
        self.assertEqual(slips._pb_batch_report_ref(), THEMED_ACTION)

    def test_07_a_mixed_selection_never_prints_half_on_the_wrong_template(self):
        """One slip with a document and one without must not silently print the
        second on a template it has nothing to do with."""
        self.config.payslip_layout_html = '<p>{{pb_meta:employee_name}}</p>'
        bare = self.env['hr.formula.config'].create({
            'name': 'PS routing bare', 'code': 'PS_ROUTING_BARE',
            'country_code': 'VN', 'state': 'draft',
        })
        slips = self._slip(formula_config_id=self.config.id) \
            + self._slip(formula_config_id=bare.id)
        self.assertEqual(slips._pb_batch_report_ref(),
                         'om_hr_payroll.action_report_payslip',
                         "a mixed selection falls back to the shared template")

    def test_08_the_batch_action_resolves_to_a_real_report(self):
        """The ref the decision returns must exist — a typo here would only
        surface as a crash on somebody's print button."""
        self.config.payslip_layout_html = '<p>{{pb_meta:employee_name}}</p>'
        slips = self._slip(formula_config_id=self.config.id)
        report = self.env.ref(slips._pb_batch_report_ref())
        self.assertEqual(report.report_name, THEMED)
        self.assertEqual(report.model, 'hr.payslip')
