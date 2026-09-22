from odoo import fields
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, AccessError


@tagged('post_install', '-at_install', 'pb_journey')
class TestHolidayJourney(TransactionCase):
    def setUp(self):
        super().setUp()
        self.facade = self.env['pb.holidays']
        self.company = self.env.company
        if not self.company.resource_calendar_id:
            self.company.resource_calendar_id = self.env['resource.calendar'].create({'name':'QA weekdays', 'company_id':self.company.id})

    def test_review_gate_publish_and_idempotency(self):
        draft = self.facade.prepare_import(self.company.id, 2090, 'QA reference',
            'QA collective | 2090-06-01 | | collective')
        with self.assertRaises(UserError):
            self.facade.publish_import(draft['id'])
        self.facade.resolve_import(draft['id'], {'0':'include'})
        self.assertEqual(self.facade.publish_import(draft['id'])['added'], 1)
        with self.assertRaises(UserError):
            self.facade.publish_import(draft['id'])
        batch = self.env['pb.holiday.batch'].browse(draft['id'])
        self.assertEqual(batch.state, 'published')
        leave = self.env['resource.calendar.leaves'].search([('pb_holiday_batch_id','=',batch.id)])
        self.assertEqual(leave.pb_holiday_kind, 'collective')

    def test_duplicates_and_invalid_year(self):
        draft = self.facade.prepare_import(self.company.id, 2090, 'QA duplicate',
            'QA one | 2090-07-01\nQA two | 2090-07-01')
        self.assertEqual(draft['rows'][1]['decision'], 'review')
        with self.assertRaises(UserError):
            self.facade.prepare_import(self.company.id, 2090, 'QA', 'QA wrong year | 2089-01-01')

    def test_other_company_denied(self):
        other = self.env['res.company'].create({'name':'QA other calendar'})
        with self.assertRaises(AccessError):
            self.facade.with_context(allowed_company_ids=[self.company.id]).prepare_import(other.id, 2090, 'QA', 'QA | 2090-01-01')
