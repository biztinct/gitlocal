# -*- coding: utf-8 -*-
"""Who can apply for a role: outside candidates, staff, or both.

THE DEFAULT IS TODAY'S BEHAVIOUR. Every existing role and every new one is
"Outside candidates only" until somebody in the hiring team says otherwise,
so installing this module changes nothing on any screen (silent install).

A STAFF-ONLY ROLE NEVER REACHES THE CAREERS PAGE. Three doors are shut, all
by inheritance so no `pb_hiring` file is edited:
  * `hr.job.pb_hiring_accepts_applications` — the careers page's own "may
    somebody apply here?" answers no;
  * `pb.hiring.posting.publish_for` — Publish refuses with a sentence;
  * choosing "Staff only" on a role already on the careers page takes it off.

PAUSED ROLES (contract C-2). Step 8 adds a boolean `pb_hiring_paused` on
`hr.job`. It may not exist in this database, so it is PROBED, never imported:
a role whose job is paused is not shown to staff and cannot be applied for.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

STAFF_POSTING = [
    ('outside', 'Outside candidates only'),
    ('both', 'Staff and outside candidates'),
    ('staff', 'Staff only'),
]
#: The values that put a role on the staff's own page.
OPEN_TO_STAFF = ('both', 'staff')
#: Role kinds that are never shown to staff, whatever the setting says: a
#: quiet replacement is kept off the referral page for the same reason.
NEVER_TO_STAFF = ('sensitive_replacement',)
#: At most this many roles on the staff page.
MAX_ROLES = 60
#: The field Step 8 adds (C-2).
PAUSED_FIELD = 'pb_hiring_paused'


def job_paused(job):
    """True when Step 8's pause switch is on for this job (C-2, probed)."""
    if not job or PAUSED_FIELD not in job._fields:
        return False
    try:
        return bool(job.sudo()[PAUSED_FIELD])
    except Exception:                   # noqa: BLE001 — a probe never fails a page
        _logger.warning('pb_hiring_internal: could not read the pause switch '
                        'on job %s', job.id, exc_info=True)
        return False


def role_paused(req):
    """C-2 for one role: its job's answer, or — for a role with no job record
    yet — its team's answer (`hr.department.pb_hiring_paused`, S8-C), both
    probed."""
    req = req.sudo()
    if req.job_id:
        return job_paused(req.job_id)
    dept = req.department_id
    if not dept or PAUSED_FIELD not in dept._fields:
        return False
    try:
        return bool(dept[PAUSED_FIELD])
    except Exception:                   # noqa: BLE001 — a probe never fails a page
        return False


class HiringRequisitionStaff(models.Model):
    _inherit = 'pb.hiring.requisition'

    pb_staff_posting = fields.Selection(
        STAFF_POSTING, string='Who can apply', default='outside',
        required=True, copy=False,
        help='Staff see a role on their own pages only when it is open to '
             'staff. A staff-only role is never put on the careers page.')

    # ------------------------------------------------------------ staff view
    @api.model
    def _pbhi_staff_domain(self, company_ids):
        return [
            ('state', '=', 'open'),
            ('pb_staff_posting', 'in', OPEN_TO_STAFF),
            ('role_type', 'not in', NEVER_TO_STAFF),
            ('is_confidential', '=', False),
            ('company_id', 'in', list(company_ids)),
        ]

    @api.model
    def _pbhi_roles_for(self, employee):
        """The roles THIS employee may see and apply for, newest first.

        `employee` is the session's own (the controller proved it). Read
        under sudo; never another company's role; never a paused one."""
        if not employee:
            return self.sudo().browse()
        company_ids = employee.company_id.ids
        roles = self.sudo().search(self._pbhi_staff_domain(company_ids),
                                   order='opened_on desc, id desc',
                                   limit=MAX_ROLES)
        return roles.filtered(lambda r: r._pbhi_open_for_staff())

    def _pbhi_open_for_staff(self):
        """Every condition, on one role, read again at the moment of applying
        (the list may be minutes old)."""
        self.ensure_one()
        req = self.sudo()
        return bool(
            req.state == 'open'
            and req.pb_staff_posting in OPEN_TO_STAFF
            and req.role_type not in NEVER_TO_STAFF
            and not req.is_confidential
            and not role_paused(req))

    def _pbhi_title(self):
        self.ensure_one()
        req = self.sudo()
        return req.title or req.job_id.name or req.name or ''

    def _pbhi_hiring_team_users(self):
        """The logins on this role's hiring team: recruiter, their manager,
        who asked for it, the interview owners. (The reporting manager is an
        employee and is checked by the caller.)"""
        self.ensure_one()
        req = self.sudo()
        return (req.recruiter_id | req.recruiter_manager_id
                | req.requested_by_user_id | req.step_ids.owner_id)

    def _pbhi_manager_on_team(self, employee):
        """True when the employee's CURRENT manager would see an application
        to this role anyway — they are on its hiring team, or they are in the
        hiring team's group, which sees every candidate in the company. The
        employee is told before they apply (E4: the manager is otherwise told
        only when an offer is near)."""
        self.ensure_one()
        manager = employee.sudo().parent_id
        if not manager:
            return False
        req = self.sudo()
        if manager in (req.reporting_manager_id | req.requested_by_id):
            return True
        user = manager.user_id
        if not user:
            return False
        if user in self._pbhi_hiring_team_users():
            return True
        return bool(not user.share
                    and user.has_group('pb_hiring.group_hiring_user'))

    # ------------------------------------------------------ the careers page
    def write(self, vals):
        res = super().write(vals)
        if vals.get('pb_staff_posting') == 'staff':
            for req in self.sudo():
                req._pbhi_take_off_careers_page()
        return res

    def _pbhi_take_off_careers_page(self):
        """A role turned staff-only comes off the careers page at once."""
        self.ensure_one()
        job = self.job_id
        if not job or not job.website_published:
            if self.published:
                self.sudo().write({'published': False})
            return False
        try:
            with self.env.cr.savepoint():
                job.sudo().write({'website_published': False})
                self.sudo().write({'published': False})
                self.sudo().message_post(body=_(
                    "Now open to staff only, so it came off the careers page."))
        except Exception:               # noqa: BLE001 — never fail the setting
            _logger.warning('pb_hiring_internal: could not take %s off the '
                            'careers page', self.name, exc_info=True)
            return False
        return True


class HiringPostingStaff(models.Model):
    _inherit = 'pb.hiring.posting'

    @api.model
    def publish_for(self, requisition_id):
        req = self.env['pb.hiring.requisition'].sudo().browse(
            int(requisition_id or 0)).exists()
        if req and req.pb_staff_posting == 'staff':
            raise UserError(_(
                "This role is open to staff only, so it is not put on the "
                "careers page. Change who can apply first."))
        return super().publish_for(requisition_id)


class HrJobStaff(models.Model):
    _inherit = 'hr.job'

    def pb_hiring_accepts_applications(self, website):
        ok = super().pb_hiring_accepts_applications(website)
        if not ok:
            return ok
        req = self.env['pb.hiring.requisition'].sudo().search(
            [('job_id', '=', self.sudo().id)], order='id desc', limit=1)
        return not (req and req.pb_staff_posting == 'staff')
