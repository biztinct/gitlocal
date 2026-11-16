# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WDGAP S5-F (owner ruling TP3): employees see their own confirmed late and
early minutes on My Payobook.

L1 the facade answers the signed-in person's own decided rows only, grouped
   by month, newest first; only confirmed minutes count; an excused row says
   "Excused" and is never counted; another person's rows never appear.
L2 My Overtime's summary (for the door): count and this month's counted
   minutes; nobody else's; zero for a person with nothing decided.
L3 HTTP as REAL portal logins: /my/work/late shows the own rows and not
   another person's; My Overtime shows the door only to somebody with
   decided minutes; a login with no employee gets the plain page.
L4 read-only: reading the page writes nothing; the portal login still cannot
   read the decisions through the ORM.
L5 white-label: the new page has no vendor name.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged

from .common import TimePayCase


def _portal(env, login, pw):
    return env['res.users'].sudo().with_context(no_reset_password=True).create({
        'name': login, 'login': login, 'email': login, 'password': pw,
        'company_id': env.company.id, 'company_ids': [(6, 0, [env.company.id])],
        'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})


def _late(env, emp, day, kind, minutes, state):
    return env['pb.time.late'].sudo().create({
        'employee_id': emp.id, 'company_id': emp.company_id.id, 'date': day,
        'kind': kind, 'minutes': minutes, 'state': state})


@tagged('post_install', '-at_install', 'wdgap_s5f')
class TestLatePage(TimePayCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.me_user = _portal(cls.env, 's5f.late.me@example.invalid', 's5f-Late-Pass-1')
        Emp = cls.env['hr.employee'].sudo()
        cls.me = Emp.create({'name': 'S5F Late Me', 'company_id': cls.company.id,
                             'user_id': cls.me_user.id})
        cls.other = Emp.create({'name': 'S5F Late Other', 'company_id': cls.company.id})
        today = date.today()
        cls.this_month = today.replace(day=1)
        cls.last_month = cls.this_month - relativedelta(months=1)
        _late(cls.env, cls.me, cls.this_month, 'late', 20, 'confirmed')
        _late(cls.env, cls.me, cls.this_month, 'early', 10, 'excused')
        _late(cls.env, cls.me, cls.last_month, 'late', 35, 'confirmed')
        _late(cls.env, cls.other, cls.this_month, 'late', 77, 'confirmed')
        # older than a year: not on the page
        _late(cls.env, cls.me, cls.this_month - relativedelta(months=13), 'late', 99,
              'confirmed')

    def _ess(self, user):
        return self.env['pb.ess.workforce'].with_user(user)

    def test_l1_own_rows_by_month(self):
        data = self._ess(self.me_user).get_my_late_minutes()
        self.assertEqual([m['key'] for m in data['months']],
                         [self.this_month.strftime('%Y-%m'), self.last_month.strftime('%Y-%m')])
        now, before = data['months']
        self.assertEqual(now['counted'], 20, 'the excused 10 minutes never count')
        self.assertEqual(before['counted'], 35)
        self.assertEqual(data['total_counted'], 55)
        self.assertEqual(sorted((r['kind'], r['minutes'], r['state'], r['state_label'])
                                for r in now['rows']),
                         [('early', 10, 'excused', 'Excused'),
                          ('late', 20, 'confirmed', 'Counted')])
        minutes = [r['minutes'] for m in data['months'] for r in m['rows']]
        self.assertNotIn(77, minutes, "another person's minutes never appear")
        self.assertNotIn(99, minutes, 'older than a year is not listed')
        self.assertTrue(all(r['date'] and r['kind_label'] for m in data['months']
                            for r in m['rows']))

    def test_l2_overtime_summary(self):
        ot = self._ess(self.me_user).get_my_overtime()
        self.assertEqual(ot['late']['count'], 3, 'the three rows of the last 12 months')
        self.assertEqual(ot['late']['month_minutes'], 20)
        # every key the page always had is still there (contract C-4)
        for key in ('rows', 'total_approved', 'pending'):
            self.assertIn(key, ot)
        nobody_user = _portal(self.env, 's5f.late.none@example.invalid', 's5f-Late-Pass-2')
        self.env['hr.employee'].sudo().create({'name': 'S5F Nothing decided',
                                               'company_id': self.company.id,
                                               'user_id': nobody_user.id})
        self.assertEqual(self._ess(nobody_user).get_my_overtime()['late'],
                         {'count': 0, 'month_minutes': 0})

    def test_l4_read_only_and_no_orm_read(self):
        Late = self.env['pb.time.late'].sudo()
        self.env.flush_all()
        before = sorted(Late.search([('employee_id', '=', self.me.id)]).mapped(
            lambda r: (r.id, r.minutes, r.state, str(r.write_date))))
        self._ess(self.me_user).get_my_late_minutes()
        self._ess(self.me_user).get_my_overtime()
        self.env.flush_all()
        Late.invalidate_model()
        after = sorted(Late.search([('employee_id', '=', self.me.id)]).mapped(
            lambda r: (r.id, r.minutes, r.state, str(r.write_date))))
        self.assertEqual(before, after)
        row = Late.search([('employee_id', '=', self.me.id)], limit=1)
        with self.assertRaises(AccessError):
            row.with_user(self.me_user).read(['minutes'])

    def test_l5_no_vendor_name_on_the_page(self):
        word = 'Od' + 'oo'
        view = self.env.ref('pb_time_pay.portal_my_work_late')
        self.assertNotIn(word, view.arch_db)
        door = self.env.ref('pb_time_pay.portal_my_work_overtime_time_pay')
        self.assertNotIn(word, door.arch_db)


@tagged('post_install', '-at_install', 'wdgap_s5f')
class TestLatePageHttp(HttpCase):

    def test_l3_pages_as_real_portal_logins(self):
        env = self.env
        me_user = _portal(env, 's5f.http.me@example.invalid', 's5f-Http-Pass-1')
        other_user = _portal(env, 's5f.http.other@example.invalid', 's5f-Http-Pass-2')
        lost_user = _portal(env, 's5f.http.lost@example.invalid', 's5f-Http-Pass-3')
        Emp = env['hr.employee'].sudo()
        me = Emp.create({'name': 'S5F Http Me', 'company_id': env.company.id,
                         'user_id': me_user.id})
        other = Emp.create({'name': 'S5F Http Other', 'company_id': env.company.id,
                            'user_id': other_user.id})
        day = date.today().replace(day=1)
        _late(env, me, day, 'late', 23, 'confirmed')
        _late(env, me, day, 'early', 17, 'excused')
        _late(env, other, day, 'late', 88, 'confirmed')

        self.authenticate('s5f.http.me@example.invalid', 's5f-Http-Pass-1')
        res = self.url_open('/my/work/late')
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn('Late and early minutes', html)
        self.assertIn('23 min counted', html)
        self.assertIn('Excused', html)
        self.assertNotIn('>88<', html, "another person's minutes are never shown")
        self.assertNotIn('S5F Http Other', html)
        ot = self.url_open('/my/work/overtime')
        self.assertEqual(ot.status_code, 200)
        self.assertIn('href="/my/work/late"', ot.text)
        self.assertIn('23 minutes counted this month', ot.text)

        # the other person sees only their own 88 minutes
        self.authenticate('s5f.http.other@example.invalid', 's5f-Http-Pass-2')
        html = self.url_open('/my/work/late').text
        self.assertIn('88 min counted', html)
        self.assertNotIn('Excused', html)

        # a login with no employee: the plain page, no error; no door anywhere
        self.authenticate('s5f.http.lost@example.invalid', 's5f-Http-Pass-3')
        res = self.url_open('/my/work/late')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('min counted', res.text)
        del lost_user
