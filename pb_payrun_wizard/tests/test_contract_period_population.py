"""A month's template and payroll preview use the contract's actual dates."""
from unittest.mock import patch
from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestContractPeriodPopulation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.wizard = self.env['pb.payrun.wizard']
        self.people = self.env['hr.employee'].browse()
        self.leaver = self.person('Period leaver', '2026-01-01', '2026-08-14')
        self.retained = self.person('Period continuing', '2026-01-01')
        self.new_hire = self.person('Period future hire', '2026-10-01')
        self.first_day = self.person('Period first-day end', '2026-01-01', '2026-08-01')
        self.last_day = self.person('Period last-day hire', '2026-08-31')
        self.draft = self.person('Period draft contract', '2026-01-01', state='draft')

    def person(self, name, start, end=False, state='open'):
        person = self.env['hr.employee'].create({'name':name,'company_id':self.env.company.id})
        self.env['hr.contract'].create({'name':name,'employee_id':person.id,
            'company_id':self.env.company.id,'date_start':start,'date_end':end,
            'wage':1000,'state':state})
        self.people += person
        return person

    def eligible(self, start, end):
        with patch.object(type(self.wizard), '_segment_hosts', return_value=[]):
            return set(self.wizard._eligible_employees(employee_ids=self.people.ids,
                date_start=start,date_end=end))

    def test_leaver_is_in_august_and_out_of_the_next_month(self):
        august = self.eligible('2026-08-01','2026-08-31')
        september = self.eligible('2026-09-01','2026-09-30')
        self.assertIn(self.leaver.id, august)
        self.assertNotIn(self.leaver.id, september)
        self.assertIn(self.retained.id, september)

    def test_future_hire_and_inclusive_boundaries(self):
        august = self.eligible('2026-08-01','2026-08-31')
        self.assertIn(self.first_day.id, august)
        self.assertIn(self.last_day.id, august)
        self.assertNotIn(self.new_hire.id, august)
        self.assertNotIn(self.draft.id, august)
        self.assertIn(self.new_hire.id, self.eligible('2026-10-01','2026-10-31'))

    def test_no_period_overlap_does_not_fall_back_to_all_people(self):
        self.assertFalse(self.eligible('2025-08-01','2025-08-31'))

    def test_employee_and_scheme_previews_use_the_selected_period(self):
        values={'employee_ids':self.people.ids,'date_start':'2026-09-01','date_end':'2026-09-30'}
        expected={self.retained.id,self.last_day.id}
        with patch.object(type(self.wizard),'_segment_hosts',return_value=[]), \
                patch.object(type(self.wizard),'_scheme_population',side_effect=lambda cfg,ids:(list(ids),[])):
            preview=self.wizard.eligible_preview(values)
            scheme=self.wizard.scheme_preview(values)
        self.assertEqual({p['id'] for p in preview['employees']},expected)
        self.assertEqual(preview['total'],len(expected))
        self.assertEqual(scheme['covered'],len(expected))

    def test_undated_callers_keep_the_existing_population(self):
        actual=set(self.wizard._eligible_employees(employee_ids=self.people.ids))
        self.assertIn(self.leaver.id,actual)
        self.assertIn(self.new_hire.id,actual)
        self.assertNotIn(self.draft.id,actual)

    def test_workbook_date_objects_use_the_same_period(self):
        self.assertEqual(self.eligible(date(2026,8,1),date(2026,8,31)),
                         self.eligible('2026-08-01','2026-08-31'))

    def test_automatically_closed_leaver_keeps_the_historical_contract(self):
        contract=self.env['hr.contract'].search([('employee_id','=',self.leaver.id)])
        contract.write({'date_end':'2026-08-14'})
        self.assertEqual(contract.state,'close')
        self.assertIn(self.leaver.id,self.eligible('2026-08-01','2026-08-31'))
        self.assertNotIn(self.leaver.id,self.eligible('2026-09-01','2026-09-30'))
        slip=self.env['hr.payslip']
        self.assertEqual(slip.get_contract(self.leaver,'2026-08-01','2026-08-31'),contract.ids)
        self.assertFalse(slip.get_contract(self.leaver,'2026-09-01','2026-09-30'))
        self.assertFalse(slip.get_contract(self.draft,'2026-08-01','2026-08-31'))
