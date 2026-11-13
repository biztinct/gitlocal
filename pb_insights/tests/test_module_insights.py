"""Reporting contracts shared by the seven module Insights entries."""

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestModuleInsights(TransactionCase):

    def setUp(self):
        super().setUp()
        self.service = self.env['pb.module.insights']

    def test_catalogue_routes_are_original_actions(self):
        reports = self.service.catalogue('all')
        self.assertTrue(reports)
        self.assertEqual(len(reports), len({(r['area'], r['xmlid'], r['lens']) for r in reports}))
        for report in reports:
            self.assertTrue(self.env.ref(report['xmlid'], raise_if_not_found=False), report)
        self.assertIn('pb_hr_flow.action_hr_payslip_line_analytics',
                      {r['xmlid'] for r in reports})

    def test_people_counts_current_employees_instead_of_people_paid(self):
        company_ids = self.env.companies.ids
        active = self.env['hr.employee'].search_count([
            ('company_id', 'in', company_ids), ('active', '=', True)])
        working = self.env['hr.employee'].search_count([
            ('company_id', 'in', company_ids), ('active', '=', True),
            ('contract_id.state', '=', 'open')])
        employee = self.service.explore('people', 'employees', 'department', 'total', 6)
        contract = self.service.explore('people', 'working', 'department', 'total', 6)
        self.assertEqual(employee['total'], active)
        self.assertEqual(contract['total'], working)
        self.assertIn('not payroll people paid', contract['note'].lower())
        self.assertEqual(sum(row['records'] for row in employee['rows']), active)

    def test_learning_completion_uses_assignment_cohort(self):
        model = self.env['pb.training.assignment'].sudo()
        # The service uses calendar months; use its actual domain for a
        # comparison with the source records, never a hard-coded demo total.
        spec = self.service.measures('learning')['measures']
        self.assertIn('completion', {m['key'] for m in spec})
        result = self.service.explore('learning', 'completion', 'course', 'total', 6)
        from odoo.addons.pb_insights.models.module_insights import MEASURES
        domain = self.service._domain(MEASURES['learning']['completion'], 6)
        denominator = model.search_count(domain + [('state', '!=', 'excused')])
        numerator = model.search_count(domain + [('state', '=', 'done')])
        self.assertAlmostEqual(result['total'], round(100 * numerator / denominator, 2)
                               if denominator else 0)
        self.assertEqual(result['record_count'], denominator)

    def test_hiring_and_talent_are_scoped_to_selected_companies(self):
        for area, measure, source, field in (
                ('hiring', 'agreed', 'pb.hiring.requisition', 'department'),
                ('talent', 'sheets', 'pb.goal.set', 'department')):
            result = self.service.explore(area, measure, field, 'total', 6)
            from odoo.addons.pb_insights.models.module_insights import MEASURES
            domain = self.service._domain(MEASURES[area][measure], 6)
            self.assertEqual(result['total'], self.env[source].sudo().search_count(domain))

    def test_hiring_keeps_requisition_record_rules(self):
        user = self.env['res.users'].create({
            'name': 'Hiring scope reader',
            'login': 'module.insights.hiring.scope@example.invalid',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        from odoo.addons.pb_insights.models.module_insights import MEASURES
        source = self.service.with_user(user)._source('hiring', MEASURES['hiring']['agreed'])
        self.assertFalse(source.env.su)

    def test_unknown_measure_and_bad_range_are_refused(self):
        with self.assertRaises(UserError):
            self.service.explore('people', 'payroll_people_paid', 'department', 'total', 6)
        with self.assertRaises(UserError):
            self.service.explore('people', 'employees', 'department', 'total', 100)

    def test_person_without_reporting_role_cannot_read_people_insights(self):
        user = self.env['res.users'].create({
            'name': 'Module Insights outsider',
            'login': 'module.insights.outsider@example.invalid',
        })
        self.assertFalse(self.service.with_user(user)._allowed('people'))
        with self.assertRaises(AccessError):
            self.service.with_user(user).explore('people', 'employees', 'company', 'total', 6)
