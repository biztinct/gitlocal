# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The "My Work" section of /my — four pages, one facade, no employee id.

Every route here is ``auth='user'`` and does exactly two things: ask
``pb.ess.workforce`` for the caller's own data, and render it. The controller
holds no access logic of its own, because a second place to answer "whose data
is this" is a second place to answer it differently — the facade is the only
one, and it resolves the employee from the session user every single time
(C18.26).

There is no employee_id parameter on any route in this file, and no form in
``views/portal_templates.xml`` posts one. That is not an omission to be filled
in later: a route that never reads an identity cannot be given a forged one.

A user with no linked employee gets a clean, styled empty page rather than a
redirect loop or a 500 (T1).
"""

from odoo import _, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_ERRORS = (AccessError, UserError, ValidationError, ValueError)


class PbEssWorkforcePortal(CustomerPortal):

    # ------------------------------------------------------------- helpers
    def _ess(self):
        return request.env['pb.ess.workforce']

    def _no_employee_page(self, page_name):
        return request.render('pb_ess_workforce.portal_work_no_employee',
                              {'page_name': page_name})

    def _flash(self, kw):
        """The one-word result of the previous POST, turned into a sentence
        HERE rather than passed as prose in the URL — a message assembled from
        a query string is a message a translator never sees (W80)."""
        key = (kw.get('done') or '').strip()
        return {
            'acked': _("Shift confirmed. Thanks — your manager can see it."),
            'week_acked': _("Week confirmed. Thanks — your manager can see it."),
            'nothing': _("Nothing left to confirm on that week."),
            'fix_sent': _("Your fix request was sent to your manager."),
            'fix_draft': _("Saved. Your manager will add the times and review it."),
            'leave_sent': _("Leave request sent for approval."),
            'pulse': _("Thanks — your rating was recorded anonymously."),
        }.get(key, '')

    # ------------------------------------------------- home portal counters
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        wanted = {'work_shift_count', 'work_leave_count', 'work_overtime_count'}
        if not wanted.intersection(counters):
            return values
        c = self._ess().get_my_counters()
        if 'work_shift_count' in counters:
            values['work_shift_count'] = c['shift_pending']
        if 'work_leave_count' in counters:
            values['work_leave_count'] = c['leave_pending']
        if 'work_overtime_count' in counters:
            values['work_overtime_count'] = c['overtime_pending']
        return values

    # ===================================================== My Schedule
    @http.route(['/my/work/schedule'], type='http', auth='user', website=True)
    def portal_my_work_schedule(self, week=None, **kw):
        try:
            data = self._ess().get_my_schedule(week or False)
        except UserError:
            return self._no_employee_page('work_schedule')
        return request.render('pb_ess_workforce.portal_my_work_schedule', {
            'page_name': 'work_schedule',
            'sched': data,
            'flash': self._flash(kw),
            'pulse': self._pulse_prompt(),
        })

    @http.route(['/my/work/schedule/ack'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_my_work_ack(self, **post):
        """Confirm one shift, or a whole week. The shift id is NOT trusted: the
        facade looks it up inside the caller's own shifts (see ``ack_shift``)."""
        try:
            if post.get('week_start'):
                res = self._ess().ack_week(post.get('week_start'))
                done = 'week_acked' if res.get('acked') else 'nothing'
            else:
                self._ess().ack_shift(post.get('shift_id'))
                done = 'acked'
        except _ERRORS as e:
            return self._error_page('work_schedule', e, '/my/work/schedule')
        return request.redirect('/my/work/schedule?done=%s' % done)

    # ===================================================== My Timesheet
    @http.route(['/my/work/timesheet'], type='http', auth='user', website=True)
    def portal_my_work_timesheet(self, week=None, **kw):
        try:
            data = self._ess().get_my_week(week or False)
        except UserError:
            return self._no_employee_page('work_timesheet')
        return request.render('pb_ess_workforce.portal_my_work_timesheet', {
            'page_name': 'work_timesheet',
            'wk': data,
            'flash': self._flash(kw),
        })

    @http.route(['/my/work/timesheet/fix'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_my_work_fix(self, **post):
        try:
            res = self._ess().request_fix(
                post.get('day'), post.get('reason'),
                post.get('check_in'), post.get('check_out'))
        except _ERRORS as e:
            return self._error_page('work_timesheet', e, '/my/work/timesheet')
        done = 'fix_sent' if res.get('state') == 'submitted' else 'fix_draft'
        week = (post.get('week') or '').strip()
        return request.redirect('/my/work/timesheet?done=%s%s' % (
            done, ('&week=%s' % week) if week else ''))

    # ===================================================== My Leave
    @http.route(['/my/work/leave'], type='http', auth='user', website=True)
    def portal_my_work_leave(self, **kw):
        try:
            data = self._ess().get_my_leave()
        except UserError:
            return self._no_employee_page('work_leave')
        return request.render('pb_ess_workforce.portal_my_work_leave', {
            'page_name': 'work_leave',
            'lv': data,
            'flash': self._flash(kw),
        })

    @http.route(['/my/work/leave/apply'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_my_work_leave_apply(self, **post):
        try:
            self._ess().apply_leave(
                post.get('type_id'), post.get('date_from'),
                post.get('date_to'), post.get('note'))
        except _ERRORS as e:
            return self._error_page('work_leave', e, '/my/work/leave')
        return request.redirect('/my/work/leave?done=leave_sent')

    # ===================================================== My Overtime
    @http.route(['/my/work/overtime'], type='http', auth='user', website=True)
    def portal_my_work_overtime(self, **kw):
        try:
            data = self._ess().get_my_overtime()
        except UserError:
            return self._no_employee_page('work_overtime')
        return request.render('pb_ess_workforce.portal_my_work_overtime', {
            'page_name': 'work_overtime',
            'ot': data,
            'flash': self._flash(kw),
        })

    # ===================================================== the shift pulse
    def _pulse_prompt(self):
        """Ask, unless the visitor has already said no TODAY.

        The dismissal lives in the HTTP SESSION, not in a table. Storing "this
        employee dismissed the pulse" would be a per-employee row about the
        pulse, in a feature whose entire premise is that no row is about an
        employee — and it would outlive the thing it refers to. A session flag
        costs nothing, forgets by itself, and cannot be joined to anything.
        """
        try:
            if request.session.get('pb_ess_pulse_off') == str(
                    request.env['pb.ess.workforce']._monday()):
                return {'show': False}
            return request.env['pb.shift.pulse'].get_my_prompt()
        except Exception:
            return {'show': False}

    @http.route(['/my/work/pulse'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_my_work_pulse(self, **post):
        """The portal half of the anonymous pulse.

        Note what is NOT forwarded: nothing identifying. The rating and the
        optional comment are the whole payload; the model resolves the company,
        the department and the day itself, from the session."""
        try:
            request.env['pb.shift.pulse'].submit_pulse(
                post.get('rating'), post.get('comment'))
        except _ERRORS:
            # Voluntary feedback. A double submission or a stale form must
            # never cost the employee their page.
            return request.redirect('/my/work/schedule')
        return request.redirect('/my/work/schedule?done=pulse')

    @http.route(['/my/work/pulse/dismiss'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_my_work_pulse_dismiss(self, **post):
        request.session['pb_ess_pulse_off'] = str(
            request.env['pb.ess.workforce']._monday())
        return request.redirect('/my/work/schedule')

    @http.route(['/work/pulse'], type='jsonrpc', auth='user')
    def work_pulse_rpc(self, rating=None, comment=None, **kw):
        """The SAME submission, for the driver PWA (plain fetch, no Odoo bundle).

        Two entry points, one write path. `**kw` swallows anything else a caller
        sends — including an employee_id — and `submit_pulse`'s signature has
        nowhere to put it even if this route tried to pass it on.
        """
        try:
            request.env['pb.shift.pulse'].submit_pulse(rating, comment)
        except _ERRORS as e:
            return {'ok': False, 'error': (e.args and e.args[0]) or str(e)}
        return {'ok': True}

    # ------------------------------------------------------------- errors
    def _error_page(self, page_name, exc, back_url):
        return request.render('pb_ess_workforce.portal_work_error', {
            'page_name': page_name,
            'error': (exc.args and exc.args[0]) or str(exc),
            'back_url': back_url,
        })
