# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T3b — clock in / out from My Payobook (handover
docs/handovers/tiers/T3B_HANDOVER.md, tests T3b.1–T3b.5).

T3b.1 the facade's punch (state, debounce, tag, filer), T3b.2 the location,
T3b.3 the per-company switch, T3b.4 the pages over HTTP for an employee login
and a full account, T3b.5 the delete guard for a portal row.
"""
import logging
import re
from datetime import timedelta

from odoo import fields, http
from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pb_ess_workforce.models.ess_workforce import CLOCK_PARAM
from odoo.addons.pb_me_portal.tests.test_portal_accounts import (
    _make_share, _pin_dbfilter,
)
from odoo.addons.pb_me_portal.tests.test_portal_only import _make_people

_logger = logging.getLogger(__name__)

PASSWORD = 'tiers-t3b-clock-probe-2026'
TZ = 'Asia/Ho_Chi_Minh'


def _flexible(emp):
    """No working schedule = fully flexible (resource `_is_flexible`): stock's
    `worked_hours` then counts every minute, whatever the time of day the test
    runs (a fixed schedule leaves out its lunch hour)."""
    emp.sudo().write({'resource_calendar_id': False, 'tz': TZ})
    return emp


def _back(att, minutes):
    """Move a punch into the past (the debounce window is about real time)."""
    vals = {'check_in': att.check_in - timedelta(minutes=minutes)}
    if att.check_out:
        vals['check_out'] = att.check_out - timedelta(minutes=minutes)
    att.sudo().write(vals)


@tagged('post_install', '-at_install')
class TestT3bClockModel(TransactionCase):
    """T3b.1, T3b.2, T3b.3 (facade), T3b.5 — as an employee login."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t3b_clock_share', 'Quinn Clock Share')
        _flexible(cls.share_emp)
        cls.share2, cls.share2_emp = _make_share(
            cls.env, 'test_t3b_clock_share2', 'Rowan Clock Share')
        _flexible(cls.share2_emp)
        cls.Att = cls.env['hr.attendance'].sudo()
        cls.env['ir.config_parameter'].sudo().set_param(
            CLOCK_PARAM % cls.env.company.id, False)     # unset = on (D3)

    def _ess(self, user=None):
        return self.env['pb.ess.workforce'].with_user(user or self.share)

    def _rows(self, emp=None):
        return self.Att.search([('employee_id', '=', (emp or self.share_emp).id)])

    # T3b.1
    def test_t3b_1_punch_debounce_and_tag(self):
        Ess = self._ess()
        clock = Ess.get_my_clock()
        self.assertTrue(clock['enabled'], 'unset parameter = on (D3)')
        self.assertEqual(clock['state'], 'out')
        self.assertEqual(clock['today_minutes'], 0)
        self.assertEqual(len(clock['week']), 7)
        self.assertTrue(all(d['minutes'] == 0 for d in clock['week']))
        self.assertFalse(clock['open_attendance_id'])

        res = Ess.clock_toggle()
        self.assertEqual(res['punched'], 'in')
        self.assertFalse(res['already'])
        self.assertEqual(res['state'], 'in')
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows.check_in)
        self.assertFalse(rows.check_out)
        self.assertEqual(rows.pb_entry_source, 'portal')
        self.assertEqual(rows.create_uid, self.share,
                         'sudo keeps env.uid: the filer is the employee login')
        self.assertEqual(res['open_attendance_id'], rows.id)
        self.assertTrue(res['since_label'])

        again = Ess.clock_toggle()
        self.assertTrue(again['already'], 'a second press inside 60 s')
        self.assertEqual(again['state'], 'in')
        self.assertEqual(len(self._rows()), 1, 'still one row')

        _back(rows, 2)
        out = Ess.clock_toggle()
        self.assertEqual(out['punched'], 'out')
        rows.invalidate_recordset()
        self.assertTrue(rows.check_out)
        self.assertEqual(out['state'], 'out')
        self.assertGreater(out['today_minutes'], 0)
        self.assertEqual(out['last_punch']['kind'], 'out')
        self.assertEqual(rows.pb_entry_source, 'portal')
        _logger.info('T3b.1 | in → already → out; today %s min', out['today_minutes'])

    def test_t3b_1b_a_check_out_never_relabels_a_device_punch(self):
        """A device check-in (blank source) closed from the portal keeps its
        blank source — and with it the delete guard (`_is_device_row`)."""
        device = self.Att.create({
            'employee_id': self.share_emp.id,
            'check_in': fields.Datetime.now() - timedelta(hours=3)})
        res = self._ess().clock_toggle()
        self.assertEqual(res['punched'], 'out')
        device.invalidate_recordset()
        self.assertTrue(device.check_out)
        self.assertFalse(device.pb_entry_source)

    def test_t3b_1c_no_employee_is_a_plain_refusal(self):
        nobody, _none = _make_share(self.env, 'test_t3b_clock_nobody',
                                    'T3b Nobody', employee=False)
        with self.assertRaises(UserError):
            self._ess(nobody).clock_toggle()
        with self.assertRaises(UserError):
            self._ess(nobody).get_my_clock()

    # T3b.2
    def test_t3b_2_location_is_kept_only_when_it_parses(self):
        self.env.company.sudo().attendance_device_tracking = True
        self._ess().clock_toggle(lat='10.77', lng='106.70', accuracy='12')
        row = self._rows()
        self.assertAlmostEqual(row.in_latitude, 10.77, places=4)
        self.assertAlmostEqual(row.in_longitude, 106.70, places=4)
        self.assertEqual(row.in_mode, 'systray')

        res = self._ess(self.share2).clock_toggle(lat='x')
        self.assertEqual(res['punched'], 'in', 'a garbled location is not an error')
        row2 = self._rows(self.share2_emp)
        self.assertEqual(len(row2), 1)
        self.assertFalse(row2.in_latitude)
        self.assertFalse(row2.in_longitude)
        self.assertTrue(self._ess(self.share2).get_my_clock()['tracking'])

    def test_t3b_2b_no_tracking_no_location(self):
        """Stock's own switch: with "Device & Location Tracking" off, the
        place is not kept even when the browser sent one."""
        self.env.company.sudo().attendance_device_tracking = False
        self._ess().clock_toggle(lat='10.77', lng='106.70')
        row = self._rows()
        self.assertFalse(row.in_latitude)
        self.assertFalse(self._ess().get_my_clock()['tracking'])

    # T3b.3 (facade)
    def test_t3b_3_switch_off_refuses_in_plain_words(self):
        self.env['ir.config_parameter'].sudo().set_param(
            CLOCK_PARAM % self.env.company.id, '0')
        self.assertFalse(self._ess().get_my_clock()['enabled'])
        with self.assertRaises(UserError) as caught:
            self._ess().clock_toggle()
        self.assertIn('switched off for your company', str(caught.exception))
        self.assertIn('Use your usual device', str(caught.exception))
        self.assertFalse(self._rows())
        # the settings field reads and writes the same parameter
        settings = self.env['res.config.settings'].create({})
        self.assertFalse(settings.pb_ess_portal_clock)
        settings.pb_ess_portal_clock = True
        settings.set_values()
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param(
            CLOCK_PARAM % self.env.company.id), '1')
        self.assertTrue(self._ess().portal_clock_enabled())

    # T3b.5
    def test_t3b_5_hr_removes_a_portal_row_like_a_grid_row(self):
        """pb_attendance_flow's guard (`hr_attendance.py:42+`) protects only a
        blank-source (device) punch from a direct delete. A 'portal' row
        carries a source, so HR removes it like a grid row; a device punch
        still needs an approved correction."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        hr = Users.create({
            'name': 'T3b HR Attendance', 'login': 'test_t3b_clock_hr',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr.group_hr_user').id,
                                  self.env.ref('hr_attendance.group_hr_attendance_manager').id])]})
        self.assertFalse(hr._is_admin())
        self._ess().clock_toggle()
        portal_row = self._rows()
        self.assertEqual(portal_row.pb_entry_source, 'portal')
        self.assertFalse(portal_row._is_device_row())
        self.env['hr.attendance'].with_user(hr).browse(portal_row.id).unlink()
        self.assertFalse(portal_row.exists())

        device = self.Att.create({
            'employee_id': self.share2_emp.id,
            'check_in': fields.Datetime.now() - timedelta(hours=5),
            'check_out': fields.Datetime.now() - timedelta(hours=4)})
        with self.assertRaises(UserError):
            self.env['hr.attendance'].with_user(hr).browse(device.id).unlink()


@tagged('post_install', '-at_install')
class TestT3bClockPages(HttpCase):
    """T3b.3 (pages) and T3b.4 — over HTTP, as an employee login and as a full
    account (T-R6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t3b_clock_http_share', 'Quinn Clock Http', PASSWORD)
        _flexible(cls.share_emp)
        cls.plain, cls.plain_emp, _lead, _staff = _make_people(
            cls.env, 'test_t3b_clock_http', password=PASSWORD)
        _flexible(cls.plain_emp)
        cls.env['ir.config_parameter'].sudo().set_param(
            CLOCK_PARAM % cls.env.company.id, False)

    def _post(self, url, data=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, timeout=60)

    def _text(self, response):
        return (response.text or '').replace('&#39;', "'")

    def _flow(self, user, emp):
        self.authenticate(user.login, PASSWORD)
        page = self.url_open('/my/work/clock', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('pbew-clockbtn is-out', page.text)
        self.assertIn('Clock in', page.text)
        self.assertIn('Tap to start your day', page.text)
        self.assertIn('Last 7 days', page.text)
        self.assertEqual(len(re.findall(r'class="pbew-strip__d[ "]', page.text)), 7)

        done = self._post('/my/work/clock/toggle', {'lat': '', 'lng': '', 'nonce': 'a1'})
        self.assertEqual(done.status_code, 200)
        self.assertIn('done=in', done.url)
        self.assertIn('pbew-clockbtn is-in is-just-in', done.text)
        self.assertIn('You are clocked in. Have a good day.', done.text)
        self.assertIn('data-pbew-elapsed', done.text)
        self.assertIn('since', done.text)
        att = self.env['hr.attendance'].sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(len(att), 1)
        self.assertEqual(att.pb_entry_source, 'portal')
        self.assertEqual(att.create_uid, user)

        again = self._post('/my/work/clock/toggle', {'nonce': 'a2'})
        self.assertIn('done=already', again.url)
        self.assertIn('already done a moment ago', self._text(again))
        self.assertEqual(self.env['hr.attendance'].sudo().search_count(
            [('employee_id', '=', emp.id)]), 1)

        home = self.url_open('/my', timeout=60)
        self.assertEqual(home.status_code, 200)
        self.assertIn('Clocked in since', home.text)
        self.assertIn('pbme-clock is-in', home.text)
        self.assertIn('Clock out', home.text)
        self.assertIn('href="/my/work/clock"', home.text, 'the Clock tile')

        state = self.make_jsonrpc_request('/my/work/clock/state', {})
        self.assertEqual(state['state'], 'in')

        # 90 minutes later: clock out, and the timesheet has the day
        _back(att, 90)
        out = self._post('/my/work/clock/toggle', {'nonce': 'a3'})
        self.assertIn('done=out', out.url)
        self.assertIn('pbew-clockbtn is-out is-just-out', out.text)
        att.invalidate_recordset()
        self.assertTrue(att.check_out)
        sheet = self.url_open('/my/work/timesheet', timeout=60)
        self.assertEqual(sheet.status_code, 200)
        # the day of the punch (today, or yesterday when the run sits in the
        # first 90 minutes after midnight) reads 1.5 h worked
        self.assertRegex(sheet.text, r'<td class="pbme-num">1\.5</td>',
                         'the punch reached the timesheet')
        home = self.url_open('/my', timeout=60)
        self.assertIn('Not clocked in', home.text)
        _logger.info('T3b.4 | %s: in → already → home → out → timesheet', user.login)

    # T3b.4
    def test_t3b_4_clock_flow_for_an_employee_login(self):
        self._flow(self.share, self.share_emp)

    def test_t3b_4b_clock_flow_for_a_full_account(self):
        self._flow(self.plain, self.plain_emp)

    def test_t3b_4c_toggle_is_post_only(self):
        self.authenticate(self.share.login, PASSWORD)
        response = self.url_open('/my/work/clock/toggle', timeout=60)
        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(self.env['hr.attendance'].sudo().search(
            [('employee_id', '=', self.share_emp.id)]))

    # T3b.3 (pages)
    def test_t3b_3b_switch_off_page_and_home(self):
        self.env['ir.config_parameter'].sudo().set_param(
            CLOCK_PARAM % self.env.company.id, '0')
        self.authenticate(self.share.login, PASSWORD)
        page = self.url_open('/my/work/clock', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Clocking in here is off for your company', page.text)
        self.assertNotIn('pbew-clockbtn', page.text)
        self.assertNotIn('<span>Clock</span>', page.text, 'no Clock pill')
        posted = self._post('/my/work/clock/toggle')
        self.assertEqual(posted.status_code, 200)
        self.assertIn('That did not go through.', posted.text)
        self.assertIn('switched off for your company', posted.text)
        self.assertFalse(self.env['hr.attendance'].sudo().search(
            [('employee_id', '=', self.share_emp.id)]))
        home = self.url_open('/my', timeout=60)
        self.assertEqual(home.status_code, 200)
        self.assertNotIn('pbme-clock', home.text)
        self.assertNotIn('Clocked in since', home.text)
        self.assertNotIn('Not clocked in', home.text)
