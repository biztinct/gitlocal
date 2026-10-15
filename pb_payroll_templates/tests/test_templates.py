import base64
import io
from unittest.mock import patch

import openpyxl
from odoo.exceptions import UserError, AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPayrollTemplates(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = cls.env['pb.payroll.templates']
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.env.company, 'records')
        cls.cfg = cls.env['hr.formula.config'].create({'name': 'Workbook tests', 'code': 'WORKBOOKTEST', 'country_code': 'SG', 'state': 'active', 'company_id': cls.env.company.id})
        cls.salary = cls.rule('Salary', 'WBBASE', 'money')
        cls.paid = cls.rule('Paid days', 'WBDAYS', 'quantity')
        cls.bonus = cls.rule('Monthly bonus', 'WBBONUS', 'money')
        cls.email = cls.rule('Employee email', 'WBEMAIL', 'text')
        cls.map_field(cls.salary, 'hr.contract', 'wage')
        cls.map_field(cls.email, 'hr.employee', 'work_email')
        cls.emp = cls.env['hr.employee'].create({'name':'Workbook One', 'barcode':'000001', 'work_email':'workbook1@example.test', 'company_id':cls.env.company.id})
        cls.contract = cls.env['hr.contract'].create({'name':'Workbook contract', 'employee_id':cls.emp.id, 'wage':1000, 'state':'open', 'date_start':'2026-01-01'})

    @classmethod
    def rule(cls, name, code, kind):
        r=cls.env['hr.formula.rule'].create({'config_id':cls.cfg.id,'name':name,'code':code,'column_type':'input','value_kind':kind})
        r.set_source_binding('excel','Payroll|'+name)
        return r

    @classmethod
    def map_field(cls, rule, model, field):
        cls.env['hr.payslip.import.mapping'].create({'salary_structure_id':cls.cfg.id,'component_id':rule.id,'destination_type':'field','target_model_id':cls.env['ir.model']._get(model).id,'target_field_id':cls.env['ir.model.fields'].search([('model','=',model),('name','=',field)],limit=1).id})

    def setUp(self):
        super().setUp()
        self.roster_patch=patch.object(type(self.api),'_roster',return_value=self.emp)
        self.roster_patch.start()
        self.addCleanup(self.roster_patch.stop)

    def export(self, mode='monthly', period='2026-10'):
        d=self.api.download(self.cfg.id,period,mode)
        return openpyxl.load_workbook(io.BytesIO(base64.b64decode(d['file_b64'])))

    def review(self, wb, mode='monthly', period='2026-10'):
        b=io.BytesIO();wb.save(b)
        return self.api.review(self.cfg.id,period,mode,base64.b64encode(b.getvalue()).decode(),'workbook.xlsx')

    def set_value(self, wb, sheet, label, value):
        ws=wb[sheet];headers=[c.value for c in ws[1]];ws.cell(2,headers.index(label)+1,value)
        if value is None: ws.cell(2,headers.index(label)+1).value=None

    def apply(self, review):
        return self.api.confirm(self.cfg.id,review['token'],[c['key'] for c in review['changes']])

    def test_monthly_two_tabs_and_identity(self):
        wb=self.export()
        self.assertEqual([s.title for s in wb if s.sheet_state=='visible'],['Time','Monthly adjustments'])
        for s in ('Time','Monthly adjustments'):
            self.assertEqual(wb[s]['A2'].value,'000001')
            self.assertTrue(wb[s]['A2'].protection.locked)
            self.assertEqual(wb[s].freeze_panes,'C2')
        self.assertEqual(self.review(wb)['changes'],[])

    def test_zero_blank_and_selected_period(self):
        wb=self.export();self.set_value(wb,'Monthly adjustments','Monthly bonus',70)
        self.apply(self.review(wb))
        wb=self.export();self.set_value(wb,'Monthly adjustments','Monthly bonus',None)
        self.assertEqual(self.review(wb)['changes'],[])
        self.assertEqual(self.api._current(self.cfg,'2026-10',self.emp)[self.emp.id]['rule:%s'%self.bonus.id],70)
        self.set_value(wb,'Monthly adjustments','Monthly bonus',0)
        self.apply(self.review(wb))
        self.assertEqual(self.api._current(self.cfg,'2026-10',self.emp)[self.emp.id]['rule:%s'%self.bonus.id],0)
        next_month=self.export(period='2026-11')
        col=[c.value for c in next_month['Monthly adjustments'][1]].index('Monthly bonus')+1
        self.assertIsNone(next_month['Monthly adjustments'].cell(2,col).value)

    def test_records_diff_apply_and_blank_ignore(self):
        wb=self.export('records');self.set_value(wb,'Employee records','Wage',1200)
        review=self.review(wb,'records')
        self.assertFalse(review['issues']);self.assertEqual(len(review['changes']),1)
        self.assertEqual(self.contract.wage,1000)
        res=self.apply(review);self.assertFalse(res['pending']);self.assertEqual(self.contract.wage,1200)

    def test_id_and_email_cannot_change(self):
        for label,value in [('Employee ID','000002'),('Email','other@example.test')]:
            wb=self.export('records');self.set_value(wb,'Employee records',label,value)
            self.set_value(wb,'Employee records','Wage',1200)
            review=self.review(wb,'records');self.assertTrue(review['issues'])
            with self.assertRaises(UserError):self.apply(review)
        self.assertEqual(self.contract.wage,1000)

    def test_stale_review_is_atomic_and_cannot_replay(self):
        wb=self.export();self.set_value(wb,'Monthly adjustments','Monthly bonus',15)
        review=self.review(wb);self.apply(review)
        with self.assertRaises(UserError):self.apply(review)
        self.set_value(wb,'Monthly adjustments','Monthly bonus',20)
        stale=self.review(wb);self.assertTrue(stale['issues'])

    def test_concurrent_change_after_review(self):
        wb=self.export('records');self.set_value(wb,'Employee records','Wage',1200)
        review=self.review(wb,'records');self.contract.wage=1100
        with self.assertRaises(UserError):self.apply(review)
        self.assertEqual(self.contract.wage,1100)

    def test_duplicate_and_cross_tab_missing_id(self):
        wb=self.export();ws=wb['Time'];ws.append([c.value for c in ws[2]])
        self.assertTrue(self.review(wb)['issues'])
        wb=self.export();wb['Time'].delete_rows(2)
        self.assertTrue(self.review(wb)['issues'])

    def test_wrong_month_and_stale_layout(self):
        wb=self.export()
        with self.assertRaises(UserError):self.review(wb,period='2026-11')
        d=self.api.workspace(self.cfg.id,'2026-10');layout=d['layout'];fid='rule:%s'%self.bonus.id
        layout['adjustments'].remove(fid);layout['time'].append(fid)
        self.api.save_layout(self.cfg.id,layout)
        with self.assertRaises(UserError):self.review(wb)
        fresh=self.export();self.assertIn('Monthly bonus',[c.value for c in fresh['Time'][1]])

    def test_readonly_salary_context(self):
        d=self.api.workspace(self.cfg.id,'2026-10');layout=d['layout'];fid='rule:%s'%self.salary.id
        layout['available'].remove(fid);layout['time'].append(fid);self.api.save_layout(self.cfg.id,layout)
        wb=self.export();self.assertEqual(wb['Time'].cell(2,[c.value for c in wb['Time'][1]].index('Salary')+1).value,1000)
        self.set_value(wb,'Time','Salary',1500)
        self.assertTrue(self.review(wb)['issues'])

    def test_engine_aliases_and_recurring_records(self):
        wb=self.export();self.set_value(wb,'Time','Paid days',20);self.set_value(wb,'Monthly adjustments','Monthly bonus',0)
        self.apply(self.review(wb));raw,ids=self.api._engine_file(self.cfg,'2026-10')
        probe=self.env['hr.payroll.import.batch'].with_context(pb_template_engine=True).new({'formula_config_id':self.cfg.id})
        parsed=probe._parse_source_file(raw,'file.xlsx');blob=probe._raw_data_from_row(parsed['headers'],parsed['rows'][0])
        self.assertEqual(blob['Payroll|Paid days'],20)
        self.assertEqual(blob['Payroll|Monthly bonus'],0)
        self.assertEqual(blob['Payroll|Salary'],1000)
        self.assertEqual(self.contract.wage,1000)

    def test_missing_time_blocks_computation(self):
        with self.assertRaises(UserError):self.api._engine_file(self.cfg,'2026-10')

    def test_manual_time_inputs_are_available(self):
        self.paid.clear_source_binding('excel');self.paid.data_source='manual'
        d=self.api.workspace(self.cfg.id,'2026-10')
        self.assertIn('rule:%s'%self.paid.id,d['layout']['time'])

    def test_formula_and_invalid_number_are_refused(self):
        for value in ('=1+1','abc'):
            wb=self.export();self.set_value(wb,'Monthly adjustments','Monthly bonus',value)
            self.assertTrue(self.review(wb)['issues'])

    def test_company_scope_and_token_owner(self):
        wb=self.export();token=wb['_Payobook']['B1'].value
        other=self.env['res.users'].create({'name':'Workbook reader','login':'workbook.reader','group_ids':[(6,0,[self.env.ref('pb_records.group_records_viewer').id])]})
        with self.assertRaises(UserError):self.api.with_user(other)._get_exchange(self.cfg,token,'export')
        company=self.env['res.company'].create({'name':'Other workbook company'})
        with self.assertRaises(AccessError):self.api.with_company(company)._config(self.cfg.id)
