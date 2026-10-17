# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Fixtures for ETP E1 (handover docs/handovers/etp/E1_HANDOVER.md).

`share_emp` — an employee LOGIN (portal/share user) with an employee; `plain`
— a full account with an employee; `hr` — an expense manager. Both employees
report to `manager` (an internal login), and the finance seat of the default
route is held by `finance`, so the route Their manager → Finance approver has
a real person on each step (pb_assets' test_asset_approval shape).
"""
import io
from datetime import timedelta

from odoo import fields

from odoo.addons.pb_me_portal.tests.test_portal_accounts import _PDF, _make_share
from odoo.addons.pb_me_portal.tests.test_portal_only import (
    PASSWORD as T1_PASSWORD, _make_people,
)

PASSWORD = 'etp-e1-expense-probe-2026'


def make_png(size=(24, 32), colour=(30, 120, 200)):
    """A small but real PNG (the image route resizes it)."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', size, colour).save(buf, format='PNG')
    return buf.getvalue()


PNG = make_png()
PDF = _PDF


class ExpenseFixtures:

    @classmethod
    def _expense_fixtures(cls, prefix, password=None):
        env = cls.env
        company = env.company
        cls.company = company
        Users = env['res.users'].with_context(no_reset_password=True)
        Emp = env['hr.employee']
        internal = env.ref('base.group_user')

        def login(suffix, name, groups):
            vals = {'name': name, 'login': '%s_%s' % (prefix, suffix),
                    'group_ids': [(6, 0, [g.id for g in groups])]}
            if password:
                vals['password'] = password
            return Users.create(vals)

        cls.manager = login('mgr', 'E1 Manager Minh', [internal])
        cls.manager_emp = Emp.create({'name': 'E1 Manager Minh',
                                      'user_id': cls.manager.id,
                                      'company_id': company.id})
        cls.finance = login('fin', 'E1 Finance Linh', [internal])
        Emp.create({'name': 'E1 Finance Linh', 'user_id': cls.finance.id,
                    'company_id': company.id})
        cls.hr = login('hr', 'E1 Expense Manager', [
            internal, env.ref('hr_expense.group_hr_expense_manager')])

        cls.share, cls.share_emp = _make_share(
            env, '%s_share' % prefix, 'Quinn Expense Share', password)
        cls.share_emp.parent_id = cls.manager_emp
        cls.plain, cls.plain_emp, _lead, _staff = _make_people(
            env, prefix, password=T1_PASSWORD if password else None)
        cls.plain_emp.parent_id = cls.manager_emp
        cls.plain_password = T1_PASSWORD

        # the default route, laid explicitly — a suite never depends on which
        # hook happened to run on its database (ledger AM70)
        env['pb.expense.claim']._approval_seed_default(company)
        role = env['biz.approval.role'].search([('key', '=', 'finance')], limit=1)
        Resp = env['biz.approval.responsibility']
        Resp.search([('company_id', '=', company.id),
                     ('role_id', '=', role.id)]).write({'active': False})
        Resp.create({'company_id': company.id, 'role_id': role.id,
                     'scope_key': '', 'scope_label': company.name,
                     'user_id': cls.finance.id})

        Product = env['product.product']
        cls.cat = Product.create({'name': 'E1 Meals', 'default_code': 'FOOD',
                                  'can_be_expensed': True, 'standard_price': 0.0})
        cls.cat2 = Product.create({'name': 'E1 Taxi', 'default_code': 'E1TAXI',
                                   'can_be_expensed': True, 'standard_price': 0.0})
        cls.priced = Product.create({'name': 'E1 Mileage', 'default_code': 'E1MIL',
                                     'can_be_expensed': True, 'standard_price': 3.5})
        cls.other_company = env['res.company'].create({'name': 'E1 Other Company'})
        cls.foreign = Product.create({'name': 'E1 Other Company Lunch',
                                      'can_be_expensed': True,
                                      'company_id': cls.other_company.id})
        cls.not_expensable = Product.create({'name': 'E1 Not an expense',
                                             'can_be_expensed': False})

        cls.Facade = env['pb.me.expense']
        cls.Claim = env['pb.expense.claim']
        cls.Engine = env['biz.approval.engine']
        cls.today = fields.Date.context_today(cls.share)

        cls.bridge = ('pb_trip_id' in env['hr.expense']._fields
                      and 'pb.business.trip' in env)
        cls.trip = None
        if cls.bridge:
            cls.trip = env['pb.business.trip'].sudo().create({
                'employee_id': cls.share_emp.id,
                'purpose': 'E1 client visit',
                'destination_city': 'Hanoi',
                'date_from': cls.today - timedelta(days=6),
                'date_to': cls.today - timedelta(days=4),
                'company_id': company.id,
            })
            # approved as the system: the trip's own route is not under test
            cls.trip.sudo().write({'state': 'approved'})

    # ------------------------------------------------------------ helpers
    def facade(self, user=None):
        return self.Facade.with_user(user or self.share)

    def new_claim(self, user=None, emp=None, amount=150000, product=None,
                  receipt=None, **kw):
        user = user or self.share
        emp = emp or self.share_emp
        return self.facade(user).new_claim(
            emp, receipt or ('lunch.png', PNG, 'image/png'), amount,
            (product or self.cat).id, kw.pop('date', self.today),
            kw.pop('note', 'E1 lunch with the client'),
            kw.pop('company_card', False), kw.pop('trip_id', None))

    def sent_claim(self, **kw):
        claim = self.new_claim(**kw)
        self.facade(kw.get('user')).send(claim)
        claim.invalidate_recordset()
        return claim

    def decide(self, claim, user, action='approve', reason=''):
        request = claim.sudo().approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.assertEqual(len(step), 1, 'one step waits for a decision')
        self.Engine.with_user(user).decide(request.id, step.key, action, reason)
        self.env.invalidate_all()
        return request
