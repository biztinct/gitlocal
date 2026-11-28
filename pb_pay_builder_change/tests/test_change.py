from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.addons.pb_pay_builder.tests.common import make_scheme


@tagged('post_install', '-at_install', 'paybuilder', 'paybuilder_change')
class TestChange(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'DEMO Pay changes', 'currency_id': cls.env.ref('base.VND').id})
        cls.env.user.company_ids = [Command.link(cls.company.id)]
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids, tracking_disable=True))
        cls.cfg = make_scheme(cls.env, cls.company, 'WAGE')
        cls.today = cls.env['pb.job.change']._today_for(cls.company)
        cls.person = cls.env['hr.employee'].create({'name': 'DEMO Contract person', 'company_id': cls.company.id})
        cls.contract = cls.env['hr.contract'].with_context(pb_skip_fill_in=True).create({
            'name': 'DEMO Pay contract', 'employee_id': cls.person.id, 'company_id': cls.company.id,
            'wage': 30000000, 'date_start': cls.today - timedelta(days=90), 'state': 'open'})
        cls.env['pb.person.scheme'].create({'employee_id': cls.person.id, 'config_id': cls.cfg.id, 'date_from': cls.contract.date_start})
        for code in ('PHONE', 'LUNCH'):
            tm = cls.env['hr.contract.advantage.template'].search([('code', '=', code)], limit=1)
            if not tm:
                tm = cls.env['hr.contract.advantage.template'].create({'name': 'DEMO ' + code.title(), 'code': code})
            if code == 'PHONE':
                cls.env['hr.contract.advantage'].create({'contract_id': cls.contract.id,
                    'advantage_template_id': tm.id, 'amount': 300000})
        cls.manager = cls._role('pay', ['hr.group_hr_user', 'hr_contract.group_hr_contract_manager', 'pb_pay.group_pay_manager'])
        cls.no_pay = cls._role('contracts', ['hr.group_hr_user', 'hr_contract.group_hr_contract_manager'])
        cls.reader = cls._role('reader', ['hr.group_hr_user'])
        cls.builder = cls.env['pb.pay.builder'].with_user(cls.manager)

    @classmethod
    def _role(cls, key, groups):
        return cls.env['res.users'].create({'name': 'DEMO ' + key, 'login': 'demo_pb_change_' + key,
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'group_ids': [Command.set([cls.env.ref(g).id for g in groups + ['base.group_user']])]})

    def _work(self, vals=None):
        return self.builder.work_out('change', {'contract_id': self.contract.id}, vals or {})

    def test_51_contract_gate(self):
        self.assertEqual(self._work()['state'], 'ok')
        self.assertTrue(self.env['pb.contracts'].with_user(self.manager).get_contract_360(self.contract.id).get('may_change_pay'))
        for user in (self.no_pay, self.reader):
            facade = self.builder.with_user(user)
            self.assertFalse(facade.work_out('change', {'contract_id': self.contract.id}, {})['ok'])
            self.assertFalse(self.env['pb.contracts'].with_user(user).get_contract_360(self.contract.id).get('may_change_pay'))
            with self.assertRaises(AccessError):
                facade.change_send(self.contract.id, str(self.today), 'review', {'wage': 42000000})

    def test_52_missing_contract_line_is_zero(self):
        result = self._work()
        rows = {r['code']: r for s in result['sections'] for r in s['lines']}
        self.assertEqual((rows['LUNCH']['usual'], rows['LUNCH']['amount']), (730000, 0))
        self.assertEqual(rows['PHONE']['amount'], 300000)
        self.assertEqual(result['totals']['gross'], 30300000)

    def test_53_before_values_and_deltas(self):
        before = self._work()
        after = self._work({'wage': 31000000, 'PHONE': 500000, 'DEP': 1})
        rows = {r['code']: r for s in after['sections'] for r in s['lines']}
        self.assertEqual(after['head']['was'], 30000000)
        self.assertEqual(rows['PHONE']['was'], 300000)
        self.assertIsNone(rows['LUNCH']['was'])
        self.assertEqual(next(r for r in after['asks'] if r['code'] == 'DEP')['was'], 0)
        for key in ('gross', 'net', 'deductions', 'cost', 'employer_cost'):
            old, new = before['totals'][key], after['totals'][key]
            if old == new:
                self.assertNotIn(key, after['totals']['was'])
            else:
                delta = new - old
                self.assertEqual(after['totals']['was'][key], old)
                self.assertEqual(after['deltas'][key], {'amount': delta,
                    'gain': delta < 0 if key in ('cost', 'deductions') else delta > 0})
        self.assertFalse(before['deltas'])

    def test_54_pending_does_not_write(self):
        day = self.today + timedelta(days=12)
        result = self.builder.change_send(self.contract.id, str(day), 'review', {'wage': 31000000, 'PHONE': 500000})
        rec = self.env['pb.job.change'].browse(result['id'])
        self.assertEqual(rec.state, 'pending', result)
        self.assertEqual((rec.effective_date, rec.new_wage, rec.reason_kind), (day, 31000000, 'pay'))
        self.assertEqual(rec.line_ids.filtered(lambda r: r.code == 'PHONE').new_amount, 500000)
        self.assertEqual(self.contract.wage, 30000000)
        self.assertEqual(self.contract.advantages_ids.filtered(lambda r: r.advantage_template_id.code == 'PHONE').amount, 300000)

    def test_55_scheduled_applies_on_date(self):
        self.env['biz.approval.seed'].set_no_approval_needed(self.company, 'jobchange')
        day = self.today + timedelta(days=12)
        result = self.builder.change_send(self.contract.id, str(day), 'promotion', {'wage': 31000000, 'PHONE': 500000})
        self.assertEqual(result['state'], 'scheduled', result)
        self.assertEqual(self.contract.wage, 30000000)
        jc = self.env['pb.job.change']
        with patch.object(type(jc), '_today_for', lambda model, company=None: day):
            self.assertEqual(jc._cron_start_due().get('started'), 1)
            self.assertFalse(jc._cron_start_due())
        self.assertEqual(self.contract.wage, 31000000)
        history = self.env['hr.contract.advantage.change'].search([('contract_id', '=', self.contract.id), ('advantage_template_code', '=', 'PHONE')])
        self.assertEqual((history.effective_date, history.old_amount, history.new_amount), (day, 300000, 500000))

    def test_56_fast_route_uses_save(self):
        self.env['biz.approval.seed'].set_no_approval_needed(self.company, 'jobchange')
        meta = self.builder.change_open(self.contract.id)
        self.assertTrue(meta['fast'])
        self.assertEqual(fields.Date.to_date(meta['date']), fields.Date.end_of(self.today, 'month') + timedelta(days=1))
        result = self.builder.change_send(self.contract.id, str(self.today), 'correction', {'wage': 31000000})
        self.assertEqual(result['state'], 'applied', result)
        self.assertEqual(self.contract.wage, 31000000)
