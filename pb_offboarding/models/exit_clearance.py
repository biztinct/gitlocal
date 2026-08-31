# -*- coding: utf-8 -*-
"""The four desks that have to sign a leaver off.

A clearance is a ROW, not a step on a checklist, and the difference matters.
A step is done by whoever the checklist gave it to; a clearance is owed by a
DESK — IT, HR, Finance, Admin — and the person sitting at that desk changes
without the leaver's checklist knowing. So the four rows are created once when
the leaving checklist opens, they carry their own owner, and the final
settlement reads them directly rather than inferring them from a step somebody
might have ticked for another reason.

IDEMPOTENT BY (case, desk). The same case reaches `ensure_for_case` up to three
times — `action_open()`, the connected system's `_after_offboard`, and again
when a resignation is approved onto a checklist that was already running — and
every one of those has to leave exactly four rows behind (R30).
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .offboarding_common import (
    CLEARANCE_DEPTS, CLEARANCE_DEPT_LABEL, CLEARANCE_ORDER, CLEARANCE_STATES,
    GROUP_MANAGER, P_DEPT_USER, counted,
)

_logger = logging.getLogger(__name__)


class PbExitClearance(models.Model):
    _name = 'pb.exit.clearance'
    _description = 'Exit Clearance'
    _order = 'case_id, sequence, id'

    name = fields.Char(compute='_compute_name', store=True, string='Clearance')
    case_id = fields.Many2one(
        'pb.journey.case', string='Leaving checklist', required=True,
        index=True, ondelete='cascade')
    employee_id = fields.Many2one(
        related='case_id.employee_id', store=True, index=True,
        string='Employee')
    dept = fields.Selection(
        CLEARANCE_DEPTS, string='Desk', required=True, index=True)
    sequence = fields.Integer(default=10)
    owner_user_id = fields.Many2one('res.users', string='Owner', index=True)
    state = fields.Selection(
        CLEARANCE_STATES, string='Status', default='pending', required=True,
        index=True)
    note = fields.Text(string='Note')
    cleared_at = fields.Datetime(string='Cleared on', readonly=True)
    cleared_by = fields.Many2one('res.users', string='Cleared by',
                                 readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    # A row per desk per checklist, and only one. The partial-index trap R22
    # describes does not apply — a clearance is never re-opened as a second row,
    # it is written back to `pending` on the row that exists.
    _case_dept_uniq = models.Constraint(
        'unique(case_id, dept)',
        'This desk already has a clearance row on that leaving checklist.')

    @api.depends('case_id.employee_id', 'dept')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s — %s' % (
                rec.case_id.employee_id.name or _('Employee'),
                CLEARANCE_DEPT_LABEL.get(rec.dept, rec.dept or ''))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Clearance')

    # ------------------------------------------------------------- the rows
    @api.model
    def ensure_for_case(self, case):
        """The four rows for one leaving checklist. Safe to call three times.

        Returns the full set for the case, not just what it created, so the
        caller can count what a leaver actually has rather than what this run
        happened to add.
        """
        if not case or case.case_type != 'offboarding':
            return self.browse()
        existing = self.sudo().search([('case_id', '=', case.id)])
        have = set(existing.mapped('dept'))
        vals_list = []
        for index, dept in enumerate(CLEARANCE_ORDER):
            if dept in have:
                continue
            owner = case._pb_clearance_owner(dept)
            vals_list.append({
                'case_id': case.id,
                'dept': dept,
                'sequence': (index + 1) * 10,
                'owner_user_id': owner.id if owner else False,
                'company_id': (case.company_id or case.employee_id.company_id
                               or self.env.company).id,
            })
        if vals_list:
            made = self.sudo().create(vals_list)
            case.message_post(body=_(
                "%(count)s added for this exit: %(who)s.",
                count=counted(len(made), _('clearance'), _('clearances')),
                who=', '.join(CLEARANCE_DEPT_LABEL.get(v['dept'], v['dept'])
                              for v in vals_list)))
            existing |= made
        return existing

    # --------------------------------------------------------------- actions
    def _can_clear(self):
        """The person who owns the desk, or the HR team. Nobody else.

        Deliberately NOT "anybody who can write to the model": a clearance is a
        statement that one desk is satisfied, and a statement made by the wrong
        desk is worse than no statement — it is a gate that reports itself as
        open.
        """
        self.ensure_one()
        user = self.env.user
        if self.env.su or user._is_admin() or user.has_group(GROUP_MANAGER):
            return True
        return bool(self.owner_user_id and self.owner_user_id.id == user.id)

    def action_clear(self, note=None):
        for rec in self:
            if not rec._can_clear():
                raise AccessError(_(
                    "Only %(who)s or the HR team can sign off the %(desk)s "
                    "clearance.",
                    who=rec.owner_user_id.name or _('the owner of this desk'),
                    desk=CLEARANCE_DEPT_LABEL.get(rec.dept, rec.dept or '')))
            if rec.state == 'cleared':
                continue                       # said once is said
            rec.write({
                'state': 'cleared',
                'note': (note or rec.note or '') or False,
                'cleared_at': fields.Datetime.now(),
                'cleared_by': self.env.uid,
            })
            rec.case_id.message_post(body=_(
                "%(desk)s clearance signed off by %(who)s%(note)s.",
                desk=CLEARANCE_DEPT_LABEL.get(rec.dept, rec.dept or ''),
                who=self.env.user.name,
                note=(': %s' % note) if note else ''))
        return True

    def action_not_needed(self, note=None):
        """"This desk has nothing to sign off" — which is a real answer.

        A contractor with no company laptop should not leave an IT clearance
        pending forever, and marking it cleared would claim a check that never
        happened.
        """
        for rec in self:
            if not rec._can_clear():
                raise AccessError(_(
                    "Only %(who)s or the HR team can settle the %(desk)s "
                    "clearance.",
                    who=rec.owner_user_id.name or _('the owner of this desk'),
                    desk=CLEARANCE_DEPT_LABEL.get(rec.dept, rec.dept or '')))
            rec.write({
                'state': 'na',
                'note': (note or rec.note or '') or False,
                'cleared_at': fields.Datetime.now(),
                'cleared_by': self.env.uid,
            })
            rec.case_id.message_post(body=_(
                "%(desk)s has nothing to sign off for this exit%(note)s.",
                desk=CLEARANCE_DEPT_LABEL.get(rec.dept, rec.dept or ''),
                note=(': %s' % note) if note else ''))
        return True

    def action_reopen(self):
        """Undo a sign-off. HR only, and it says so in the log."""
        for rec in self:
            if not (self.env.su or self.env.user._is_admin()
                    or self.env.user.has_group(GROUP_MANAGER)):
                raise AccessError(_(
                    "Only the HR team can re-open a clearance that has been "
                    "signed off."))
            rec.write({'state': 'pending', 'cleared_at': False,
                       'cleared_by': False})
            rec.case_id.message_post(body=_(
                "%(desk)s clearance re-opened by %(who)s.",
                desk=CLEARANCE_DEPT_LABEL.get(rec.dept, rec.dept or ''),
                who=self.env.user.name))
        return True

    # ------------------------------------------------------------- the gate
    @api.model
    def pending_for(self, employee_id):
        """The clearances still owed for a person who is leaving.

        Read under sudo ON PURPOSE, the same reason P2's `open_items_for` is:
        the answer is a gate, and a gate a reader's own access can soften is
        not a gate.
        """
        return self.sudo().search([
            ('employee_id', '=', int(employee_id or 0)),
            ('case_id.state', 'in', ('draft', 'active', 'on_hold')),
            ('state', '=', 'pending'),
        ])


class PbJourneyCaseClearance(models.Model):
    _inherit = 'pb.journey.case'

    clearance_ids = fields.One2many(
        'pb.exit.clearance', 'case_id', string='Clearances')

    def _pb_clearance_owner(self, dept):
        """Who signs this desk off.

        This module's own setting first, because a tenant that has named a
        person for "Finance clearance" means that person and not whoever the
        lifecycle role happens to resolve to. Then P0's role resolution, which
        already reads `pb_lifecycle.<role>_user_id` and falls back to the
        lifecycle managers — so a database where nobody has configured anything
        still puts a name on every row.
        """
        self.ensure_one()
        Users = self.env['res.users']
        raw = self.env['ir.config_parameter'].sudo().get_param(
            P_DEPT_USER.get(dept, ''), '')
        if raw:
            try:
                user = Users.sudo().browse(int(raw)).exists()
                if user and user.active:
                    return user
            except (TypeError, ValueError):
                _logger.warning('pb_offboarding: %s is not a user id',
                                P_DEPT_USER.get(dept))
        try:
            found = self._resolve_assignee(dept, self.employee_id)
            if found:
                return found[:1]
        except Exception:               # noqa: BLE001 — a name, not a crash
            _logger.debug('pb_offboarding: no %s owner for journey %s', dept,
                          self.id)
        return self.create_uid or self.env.user

    def ensure_exit_clearances(self):
        """The four rows. Idempotent — see the module docstring."""
        self.ensure_one()
        return self.env['pb.exit.clearance'].ensure_for_case(self)
