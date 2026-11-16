# -*- coding: utf-8 -*-
"""Hiring › Staff moves — the hiring team's view of staff applications.

ONE READ, ONE WRITE PER PRESS, gated on the hiring team's own group
(`pb_hiring.group_hiring_user`): a line manager who raises requests and holds
no hiring group never reaches it, so an employee's application to another
team is never shown to their current manager here (E4). Everything is read
under sudo AFTER that gate, and only for the companies the reader has open.
"""
from odoo import _, api, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from odoo.addons.pb_hiring.models.hiring_common import as_id

from .requisition import STAFF_POSTING, role_paused

#: How many staff applications the board lists.
BOARD_LIMIT = 200


class PbHiringInternal(models.AbstractModel):
    _name = 'pb.hiring.internal'
    _description = 'Staff applications for open roles'

    # ------------------------------------------------------------ the gate
    @api.model
    def can_open(self):
        return bool(self.env.su or self.env.user.has_group(
            'pb_hiring.group_hiring_user'))

    @api.model
    def _gate(self):
        if not self.can_open():
            raise AccessError(_("Only the hiring team sees staff moves."))

    # ------------------------------------------------------------- reading
    @api.model
    def get_board(self):
        self._gate()
        companies = self.env.companies
        Req = self.env['pb.hiring.requisition'].sudo()
        roles = Req.search([('state', '=', 'open'),
                            ('company_id', 'in', companies.ids)],
                           order='opened_on desc, id desc', limit=BOARD_LIMIT)
        App = self.env['hr.applicant'].sudo().with_context(active_test=False)
        apps = App.search([('pb_internal', '=', True),
                           ('company_id', 'in', companies.ids)],
                          order='create_date desc, id desc', limit=BOARD_LIMIT)
        staff_apps = {}
        for app in apps:
            if app.pb_requisition_id:
                staff_apps.setdefault(app.pb_requisition_id.id, 0)
                if app._pbhi_state() not in ('closed', 'withdrawn'):
                    staff_apps[app.pb_requisition_id.id] += 1
        # Selection labels in the reader's language (the field's own terms).
        labels = dict(Req._fields['pb_staff_posting']._description_selection(
            self.env))
        role_rows = [{
            'id': r.id,
            'title': r._pbhi_title(),
            'department': r.department_id.name or '',
            'company': r.company_id.name or '',
            'posting': r.pb_staff_posting,
            'posting_label': labels.get(r.pb_staff_posting, ''),
            'published': bool(r.published),
            'paused': role_paused(r),
            'confidential': bool(r.is_confidential),
            'quiet_replacement': r.role_type == 'sensitive_replacement',
            'staff_applications': staff_apps.get(r.id, 0),
        } for r in roles]
        app_rows = [self._app_row(a) for a in apps]
        open_to_staff = [r for r in role_rows if r['posting'] != 'outside']
        return {
            'roles': role_rows,
            'applications': app_rows,
            'counts': {
                'open_to_staff': len(open_to_staff),
                'applications': len([a for a in app_rows if a['live']]),
                'job_change_to_do': len([a for a in app_rows
                                         if a['job_change'] == 'to_do']),
            },
            'job_change_available': self.env['pb.hiring.offer']
            ._pbhi_job_change_target() is not None,
            'postings': [{'key': k, 'label': labels.get(k, k)}
                         for k, _v in STAFF_POSTING],
        }

    @api.model
    def _app_row(self, app):
        emp = app.employee_id
        state = app._pbhi_state()
        return {
            'id': app.id,
            'name': emp.name or app.partner_name or '',
            'employee_id': emp.id or False,
            'now': emp.job_id.name or emp.job_title or '',
            'now_department': emp.department_id.name or '',
            'role': app.pb_requisition_id._pbhi_title() if app.pb_requisition_id
            else (app.job_id.name or ''),
            'requisition_id': app.pb_requisition_id.id or False,
            'stage': app.stage_id.name or '',
            'state': state,
            'live': state not in ('closed', 'withdrawn', 'moved'),
            'applied_on': app.create_date and format_date(
                self.env, app.create_date.date(), date_format='d MMM y') or '',
            'manager': emp.parent_id.name or '',
            'manager_told_on': app.pb_manager_told_on and format_date(
                self.env, app.pb_manager_told_on.date(),
                date_format='d MMM') or False,
            'job_change': app.pb_job_change_state or False,
        }

    # ------------------------------------------------------------- writing
    @api.model
    def set_posting(self, requisition_id, value):
        """Who can apply for one role. The hiring team's own right to change
        the role is checked AS THEM before anything is written."""
        self._gate()
        if value not in dict(STAFF_POSTING):
            raise UserError(_("Choose who can apply for this role."))
        req = self.env['pb.hiring.requisition'].browse(as_id(requisition_id)).exists()
        if not req or req.company_id not in self.env.companies:
            raise UserError(_("That role is not there any more."))
        req.check_access('write')
        req.sudo().write({'pb_staff_posting': value})
        return self.get_board()

    @api.model
    def start_job_change(self, applicant_id):
        """C-1 from the board: the Change job action for a confirmed move, or
        a plain note when the system has no Change job flow."""
        self._gate()
        app = self.env['hr.applicant'].sudo().with_context(
            active_test=False).browse(as_id(applicant_id)).exists()
        if not app or not app.pb_internal or app.company_id not in self.env.companies:
            raise UserError(_("That application is not there any more."))
        offer = self.env['pb.hiring.offer'].sudo().search(
            [('applicant_id', '=', app.id), ('state', '=', 'joined')],
            order='id desc', limit=1)
        if not offer:
            raise UserError(_(
                "Confirm the move on their offer first. The job change starts "
                "from there."))
        action = offer._pbhi_job_change_action()
        if action:
            return {'action': action}
        return {'note': _(
            "Change %(who)s's job on their employee record: new job, manager, "
            "pay and start date. This system has no guided job change yet.",
            who=app.employee_id.name or '')}


class PbHiringFacadeInternal(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def get_candidate(self, applicant_id):
        """The drawer says when a candidate already works here, and whether
        their current manager has been told (E4) — for whoever the board
        already lets open the candidate (pb_hiring's own check runs first)."""
        res = super().get_candidate(applicant_id)
        app = self.env['hr.applicant'].sudo().with_context(
            active_test=False).browse(as_id(applicant_id)).exists()
        if isinstance(res, dict) and app and app.pb_internal and app.employee_id:
            emp = app.employee_id
            res['pbhi'] = {
                'now': emp.job_id.name or emp.job_title or '',
                'department': emp.department_id.name or '',
                'told_on': app.pb_manager_told_on and format_date(
                    self.env, app.pb_manager_told_on.date(),
                    date_format='d MMM') or False,
                'has_manager': bool(emp.parent_id),
            }
        return res

    def _act_confirm_joined(self, payload):
        offer = self._signed_offer(payload)
        if not offer._pbhi_internal():
            return super()._act_confirm_joined(payload)
        result = offer.action_confirm_joined(
            joined_on=payload.get('joined_on') or None)
        who = offer.candidate_name or ''
        if isinstance(result, dict):
            note = _("%(who)s moves to this role. No new employee record was "
                     "made. The job change is open for you to check and send.",
                     who=who)
            return self._joining_reply(offer, note, pb_open_action=result,
                                       employee_id=offer.employee_id.id or False)
        note = _("%(who)s moves to this role. No new employee record was "
                 "made. Job change to do: change their job on their employee "
                 "record.", who=who)
        return self._joining_reply(offer, note,
                                   employee_id=offer.employee_id.id or False)
