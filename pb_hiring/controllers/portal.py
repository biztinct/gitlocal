# -*- coding: utf-8 -*-
"""`/my/refer` — the one hiring page everybody in the company can use.

THE ROUTE IS THE GATE, exactly as P2, P3 and P4 established. The employee is
re-resolved from the SESSION user on every request and no route accepts an
employee id, so a crafted URL can never put a referral in somebody else's
name. Everything past that point is read and written under `sudo()` — the
doctrine `pb_me_portal` set — because the employee has already been proved to
be the caller's own.

THE ROLE ID IS THE ONE THING THE FORM DOES SEND, so it is checked twice: the
request must be OPEN, must have referrals switched on, and must belong to the
employee's own company. A forged id for another company's role is refused with
a sentence rather than a traceback — a portal page never shows a traceback.
"""

import base64
import logging
from datetime import timedelta

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

_UPLOAD_MAX_BYTES = 5 * 1024 * 1024
_UPLOAD_MIME_OK = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}
_MAX_NOTE = 2000

_PROBLEMS = {
    'role': _("That role is not open to referrals any more."),
    'name': _("Give the person's name — a referral with no name cannot be "
              "followed up."),
    'contact': _("Give an email address or a phone number so somebody can "
                 "reach them."),
    'size': _("That file is bigger than 5 MB. Send a smaller one, or leave "
              "it out and email it to the recruiter."),
    'type': _("Attach a PDF or a Word document."),
    'denied': _("That could not be saved. Try again, and tell the HR team if "
                "it keeps happening."),
}


class PbHiringPortal(CustomerPortal):

    # --------------------------------------------------------------- helpers
    def _hiring_employee(self):
        """The OWN employee, from the session user. Never a parameter."""
        Emp = request.env['hr.employee'].sudo()
        emp = Emp.search([('user_id', '=', request.env.user.id),
                          ('company_id', '=', request.env.company.id)],
                         limit=1)
        return emp or Emp.search(
            [('user_id', '=', request.env.user.id)], limit=1)

    def _open_roles(self, employee):
        if not employee:
            return request.env['pb.hiring.requisition'].sudo().browse()
        co_ids = employee.company_id.ids or request.env.companies.ids
        return request.env['pb.hiring.requisition'].sudo().search([
            ('state', '=', 'open'),
            ('referral_open', '=', True),
            ('company_id', 'in', co_ids),
        ], order='opened_on desc, id desc', limit=60)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'refer_count' in counters:
            emp = self._hiring_employee()
            values['refer_count'] = len(self._open_roles(emp)) if emp else 0
        if 'hiring_count' in counters:
            emp = self._hiring_employee()
            values['hiring_count'] = self._hiring_waiting(emp) if emp else 0
        return values

    # =================================================================
    #  A2 — what hiring is waiting on this person for
    # =================================================================
    def _hiring_waiting(self, employee):
        """The number on the home card: things that need THEM, not things
        that merely mention them.

        An opinion they owe and an interview they are sitting in this
        fortnight are both work. A hiring request they raised that is sailing
        through a sign-off is not, and putting it in the number would make
        the card cry wolf every week.
        """
        if not employee:
            return 0
        return len(self._feedback_owed(employee)) \
            + len(self._my_interviews(employee))

    def _feedback_owed(self, employee):
        if not employee:
            return request.env['pb.hiring.feedback'].sudo().browse()
        return request.env['pb.hiring.feedback'].sudo().search(
            [('panel_employee_id', '=', employee.id),
             ('state', '=', 'pending')], order='due_at', limit=40)

    def _my_interviews(self, employee, days=14):
        """The hours this person is sitting in, over the next fortnight.

        A fortnight rather than everything: a page that lists an interview
        six months out is a page somebody scrolls past, and the hour that
        matters is always near the top of it.
        """
        if not employee:
            return request.env['pb.hiring.interview'].sudo().browse()
        now = fields.Datetime.now()
        return request.env['pb.hiring.interview'].sudo().search([
            ('panel_employee_ids', 'in', employee.ids),
            ('state', '=', 'scheduled'),
            ('start', '>=', now),
            ('start', '<=', now + timedelta(days=days)),
        ], order='start', limit=40)

    def _my_requests(self, employee):
        if not employee:
            return request.env['pb.hiring.requisition'].sudo().browse()
        return request.env['pb.hiring.requisition'].sudo().search(
            ['|', ('requested_by_id', '=', employee.id),
             ('reporting_manager_id', '=', employee.id)],
            order='id desc', limit=30)

    @http.route(['/my/hiring'], type='http', auth='user', website=True)
    def portal_my_hiring(self, **kw):
        """Everything hiring wants from ONE person, on one page.

        Three lists and no navigation: what I asked for, what I am sitting
        in, and what I owe somebody. A hiring manager and a panel member are
        different people with different work, and neither of them should have
        to learn a system to find their own two things.
        """
        emp = self._hiring_employee()
        if not emp:
            return request.redirect('/my')
        interviews = self._my_interviews(emp)
        requests = self._my_requests(emp)
        values = {
            'page_name': 'hiring',
            'employee': emp,
            'requests': requests,
            'interviews': interviews,
            'owed': self._feedback_owed(emp),
            'now': fields.Datetime.now(),
            # A3. WHICH OFFERS ARE SITTING ON THIS PERSON, worked out on the
            # server and handed over as a plain map. The template must not
            # ask the engine anything itself: a QWeb expression that calls a
            # method per row is a query per row on a public page, and the
            # answer here is one read for the lot.
            'user_waiting': self._offers_waiting_on(requests),
        }
        return request.render('pb_hiring.portal_my_hiring', values)

    def _offers_waiting_on(self, requests):
        """`{offer_id: True}` for the offers whose route is on this user.

        Read from the ENGINE and never guessed from the status: a route with
        a conditional rung legitimately skips one, and a second opinion
        written here would only ever disagree with the one that counts.
        """
        out = {}
        for req in requests:
            for offer in req.offer_ids:
                try:
                    if offer.sudo().with_user(
                            request.env.user)._chain_my_seat():
                        out[offer.id] = True
                except Exception:       # noqa: BLE001 — never a 500 on /my
                    _logger.warning('pb_hiring: could not read the sign-off '
                                    'state of offer %s', offer.id,
                                    exc_info=True)
        return out

    @http.route(['/my/hiring/ics/<int:interview_id>'], type='http',
                auth='user', website=False, sitemap=False)
    def portal_hiring_ics(self, interview_id, **kw):
        """The hour, as a file their own diary understands.

        THE ROUTE IS THE GATE and the employee is re-resolved from the
        session, so the id in the URL buys nothing: it is checked against the
        panel, the recruiter and the person who asked for the role, and
        anything else is a redirect with a sentence rather than a file.
        """
        emp = self._hiring_employee()
        interview = request.env['pb.hiring.interview'].sudo().browse(
            interview_id).exists()
        if not emp or not interview:
            return request.redirect('/my/hiring')
        allowed = (emp.id in interview.panel_employee_ids.ids
                   or interview.recruiter_id.id == request.env.user.id
                   or interview.requisition_id.requested_by_id.id == emp.id)
        if not allowed:
            return request.redirect('/my/hiring')
        return request.make_response(
            interview._ics(),
            headers=[('Content-Type', 'text/calendar; charset=utf-8'),
                     ('Content-Disposition',
                      'attachment; filename="interview-%s.ics"'
                      % interview.id)])

    # =================================================================
    #  /my/refer
    # =================================================================
    @http.route(['/my/refer'], type='http', auth='user', website=True)
    def portal_my_refer(self, **kw):
        emp = self._hiring_employee()
        if not emp:
            return request.redirect('/my')
        roles = self._open_roles(emp)
        mine = request.env['pb.hiring.referral'].sudo().search(
            [('employee_id', '=', emp.id)], order='id desc', limit=40)
        problem = _PROBLEMS.get(kw.get('problem') or '', '')
        values = {
            'page_name': 'refer',
            'employee': emp,
            'roles': roles,
            'mine': mine,
            'picked': int(kw.get('role') or 0),
            'notice': _("Thank you — the recruiter has it.")
            if kw.get('ok') else '',
            'problem': problem,
        }
        return request.render('pb_hiring.portal_my_refer', values)

    @http.route(['/my/refer/submit'], type='http', auth='user', website=True,
                methods=['POST'])
    def portal_refer_submit(self, **post):
        emp = self._hiring_employee()
        if not emp:
            return request.redirect('/my')

        try:
            role_id = int(post.get('requisition_id') or 0)
        except (TypeError, ValueError):
            role_id = 0
        name = (post.get('name') or '').strip()
        email = (post.get('email') or '').strip()
        phone = (post.get('phone') or '').strip()
        note = (post.get('note') or '').strip()[:_MAX_NOTE]

        if not role_id:
            return request.redirect('/my/refer?problem=role')
        if not name:
            return request.redirect('/my/refer?problem=name&role=%s' % role_id)
        if not email and not phone:
            return request.redirect(
                '/my/refer?problem=contact&role=%s' % role_id)

        attachment = None
        upload = post.get('cv')
        if upload and getattr(upload, 'filename', ''):
            # Bounded read — never buffer more than the limit (+1 to notice
            # the excess) so a large upload cannot be used to exhaust memory.
            data = upload.read(_UPLOAD_MAX_BYTES + 1)
            if len(data) > _UPLOAD_MAX_BYTES:
                return request.redirect(
                    '/my/refer?problem=size&role=%s' % role_id)
            mimetype = upload.mimetype or ''
            if mimetype not in _UPLOAD_MIME_OK:
                return request.redirect(
                    '/my/refer?problem=type&role=%s' % role_id)
            attachment = {'name': upload.filename or 'CV',
                          'datas': base64.b64encode(data),
                          'mimetype': mimetype}

        try:
            request.env['pb.hiring.referral'].refer(
                role_id, emp.id,
                {'name': name, 'email': email, 'phone': phone, 'note': note,
                 'attachment': attachment})
        except ValueError:
            # The role is not open, or is another company's. Said plainly,
            # never as a traceback.
            return request.redirect('/my/refer?problem=role')
        except (AccessError, UserError, ValidationError):
            _logger.warning('pb_hiring: a referral from employee %s was '
                            'refused', emp.id, exc_info=True)
            return request.redirect('/my/refer?problem=denied')
        return request.redirect('/my/refer?ok=1')
