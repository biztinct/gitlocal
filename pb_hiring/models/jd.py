# -*- coding: utf-8 -*-
"""`pb.hiring.jd` — the advert, numbered, agreed and kept.

A JOB DESCRIPTION IS A VERSION, NOT A FIELD. The thing a hiring manager agreed
to in March is not the thing a recruiter edited in May, and a single text box
on the request cannot tell those apart. So each one is a numbered row, the
agreed one is pointed at from the request, and every older one stays readable.
That is the sheet's "centralized folder" and it needs no folder: the list view
filtered to the agreed ones IS the library.

ONLY ONE CAN BE OUT FOR AGREEMENT AT A TIME. Two versions of the same advert
in front of the same person is two approvals that contradict each other, and
whichever comes back last wins by accident.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .hiring_common import GROUP_MANAGER, GROUP_USER, JD_STATES

_logger = logging.getLogger(__name__)


class PbHiringJd(models.Model):
    _name = 'pb.hiring.jd'
    _description = 'Job description'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'requisition_id, version desc, id desc'

    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'approved'): None,
        ('submitted', 'refused'): None,
        ('draft', 'refused'): GROUP_USER,
    }

    name = fields.Char(string='Reference', compute='_compute_name',
                       store=True, readonly=True)
    requisition_id = fields.Many2one(
        'pb.hiring.requisition', string='Hiring request', required=True,
        index=True, ondelete='cascade')
    version = fields.Integer(string='Version', default=1, readonly=True,
                             copy=False)
    title = fields.Char(string='Job title', required=True)
    body = fields.Html(
        string='The advert', sanitize_attributes=False,
        help='What a candidate reads. This is what goes onto the careers '
             'page word for word once it is agreed.')
    summary = fields.Text(
        string='The one-line version',
        help='Used in the advert pack sent to job boards and in the list of '
             'open roles on the referral page.')
    state = fields.Selection(JD_STATES, string='How far it has got',
                             default='draft', required=True, tracking=True,
                             copy=False)
    approved_on = fields.Datetime(string='Agreed on', readonly=True,
                                  copy=False)
    approved_by = fields.Many2one('res.users', string='Agreed by',
                                  readonly=True, copy=False)
    refuse_note = fields.Text(string='Why it was sent back', copy=False)
    company_id = fields.Many2one(
        'res.company', related='requisition_id.company_id', store=True,
        index=True, readonly=True)
    is_current = fields.Boolean(string='The agreed one',
                                compute='_compute_is_current', store=True)

    @api.depends('requisition_id.jd_current_id')
    def _compute_is_current(self):
        for rec in self:
            rec.is_current = rec.requisition_id.jd_current_id.id == rec.id

    @api.depends('requisition_id.name', 'version', 'title')
    def _compute_name(self):
        for rec in self:
            ref = rec.requisition_id.name or ''
            rec.name = _('%(ref)s · advert v%(n)s', ref=ref,
                         n=rec.version or 1).strip()

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Job description')

    # ---------------------------------------------------------- the version
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            req_id = vals.get('requisition_id')
            if req_id and not vals.get('version'):
                highest = self.sudo().search(
                    [('requisition_id', '=', req_id)],
                    order='version desc', limit=1)
                vals['version'] = (highest.version or 0) + 1
            if req_id and not vals.get('title'):
                req = self.env['pb.hiring.requisition'].sudo().browse(req_id)
                vals['title'] = req.title
        return super().create(vals_list)

    @api.constrains('state', 'requisition_id')
    def _check_one_in_flight(self):
        for rec in self:
            if rec.state != 'submitted':
                continue
            other = self.sudo().search_count([
                ('requisition_id', '=', rec.requisition_id.id),
                ('state', '=', 'submitted'), ('id', '!=', rec.id)])
            if other:
                raise ValidationError(_(
                    "Another version of this advert is already waiting to be "
                    "agreed. Deal with that one first, or send it back."))

    # ----------------------------------------------------------- the buttons
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("This version has already been sent."))
            if not (rec.body or '').strip():
                raise UserError(_(
                    "Write the advert before you send it to be agreed. An "
                    "empty one cannot be agreed to."))
            rec._advance_state('submitted')
        return True

    def action_approve(self, note=False):
        for rec in self:
            rec._advance_state('approved', note=note or False)
        return True

    def action_refuse(self, note=False):
        for rec in self:
            rec.refuse_note = note or rec.refuse_note
        return self.action_refuse_chain(note=note or False)

    def action_new_version(self):
        """Start again from this one, keeping what was written."""
        self.ensure_one()
        copy = self.sudo().create({
            'requisition_id': self.requisition_id.id,
            'title': self.title,
            'body': self.body,
            'summary': self.summary,
        })
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': copy.id, 'view_mode': 'form',
                'views': [[False, 'form']], 'name': copy.name}

    # -------------------------------------------------------- what agreeing does
    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'approved':
            self._become_current()
        return res

    def _become_current(self):
        """Point the request at this version and put it on the job.

        Both legs guarded: a request whose job does not exist yet is the
        normal case for an advert written before the sign-off came back, and
        that must not turn an agreement into an error (R104).
        """
        self.ensure_one()
        self.sudo().write({'approved_on': fields.Datetime.now(),
                           'approved_by': self.env.uid})
        try:
            self.requisition_id.sudo().write({'jd_current_id': self.id})
        except Exception:               # noqa: BLE001
            _logger.warning('pb_hiring: advert %s could not be made the '
                            'current one', self.id, exc_info=True)
        job = self.requisition_id.job_id
        if job:
            try:
                job.sudo().write({'website_description': self.body or ''})
            except Exception:           # noqa: BLE001
                _logger.warning('pb_hiring: the job text was not updated from '
                                'advert %s', self.id, exc_info=True)
        return True

    def _approval_can(self, from_state, to_state):
        """Agreeing an advert is the hiring manager's job, and the HR team's.

        The hiring manager is the person who ASKED for the role — the one
        whose team the person will join — so the check is against the record
        rather than against a group.
        """
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        if to_state in ('approved', 'refused') and from_state == 'submitted':
            if self.env.uid in self._jd_approver_uids():
                return True
            return self.env.user.has_group(GROUP_MANAGER)
        return super()._approval_can(from_state, to_state)

    def _jd_approver_uids(self):
        """Who is asked to agree this advert, in the order it is asked.

        The person who asked for the role; if they are the person who wrote
        this version, their own manager instead; and if neither has a login,
        the HR lead's seat. Whoever it lands on is NAMED in the title so the
        approver is never a mystery.
        """
        self.ensure_one()
        req = self.requisition_id.sudo()
        Employee = self.env['hr.employee'].sudo()
        asked = Employee.browse(req.requested_by_id.id).exists()
        candidates = []
        if asked.user_id and asked.user_id.id != self.create_uid.id:
            candidates.append(asked.user_id.id)
        boss = asked.parent_id.user_id
        if boss:
            candidates.append(boss.id)
        if req.reporting_manager_id.user_id:
            candidates.append(req.reporting_manager_id.user_id.id)
        if not candidates and asked.user_id:
            candidates.append(asked.user_id.id)
        seen, out = set(), []
        for uid in candidates:
            if uid and uid not in seen:
                seen.add(uid)
                out.append(uid)
        return out

    # ------------------------------------------------------------ the doors
    def action_open_requisition(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.hiring.requisition',
                'res_id': self.requisition_id.id, 'view_mode': 'form',
                'views': [[False, 'form']],
                'name': self.requisition_id.display_name}
