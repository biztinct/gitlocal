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

from odoo import _, http
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
        return values

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
