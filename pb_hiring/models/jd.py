# -*- coding: utf-8 -*-
"""`pb.hiring.jd` — the advert, numbered, shared and kept.

A JOB DESCRIPTION IS A VERSION, NOT A FIELD. The thing a hiring manager read
in March is not the thing a recruiter edited in May, and a single text box on
the request cannot tell those apart. So each one is a numbered row, the one
in use is pointed at from the role, and every older one stays readable.

RECRUIT P3 (G-17): NO SIGN-OFF. A draft is shared with the manager for input
(an email and a link to read it and leave a comment); the recruiter makes it
final when it is right. Making a version final puts it on the job straight
away, and the role's Details tab then offers "Republish" for the job-board
packs. The `hiring_jd` route is retired.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hiring_common import JD_STATES

_logger = logging.getLogger(__name__)


class PbHiringJd(models.Model):
    _name = 'pb.hiring.jd'
    _description = 'Job description'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'requisition_id, version desc, id desc'

    # The chain mixin stays (its fields carry the old trail and the seat
    # rule reads `seat_user_ids`), but no route is registered for this model
    # any more; `state` is written by `action_make_final` alone.
    _approval_transitions = {}

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
    approved_on = fields.Datetime(string='Made final on', readonly=True,
                                  copy=False)
    approved_by = fields.Many2one('res.users', string='Made final by',
                                  readonly=True, copy=False)
    refuse_note = fields.Text(string='Why it was sent back', copy=False)
    # RECRUIT P3 — shared for input
    share_token = fields.Char(copy=False, readonly=True, index=True,
                              groups='base.group_system')
    shared_with_id = fields.Many2one('hr.employee', string='Shared with',
                                     readonly=True, copy=False)
    shared_on = fields.Datetime(string='Shared on', readonly=True, copy=False)
    template_id = fields.Many2one('pb.hiring.jd.template',
                                  string='Started from', copy=False,
                                  ondelete='set null')
    comment_ids = fields.One2many('pb.hiring.jd.comment', 'jd_id',
                                  string='Comments')
    company_id = fields.Many2one(
        'res.company', related='requisition_id.company_id', store=True,
        index=True, readonly=True)
    is_current = fields.Boolean(string='The one in use',
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

    # ----------------------------------------------------------- the buttons
    def action_make_final(self):
        """This version is the advert. It goes onto the job at once."""
        for rec in self:
            if not (rec.body or '').strip():
                raise UserError(_(
                    "Write the advert before you make it final. An empty one "
                    "cannot go on the careers page."))
            if rec.state != 'final':
                rec._chain_state_write('final')
            rec._become_current()
        return True

    # Old names, kept so a stored button or a script still does the right
    # thing: there is nothing to send and nothing to agree any more.
    def action_submit(self):
        return self.action_make_final()

    def action_approve(self, note=False):
        return self.action_make_final()

    def action_new_version(self):
        """Start again from this one, keeping what was written."""
        self.ensure_one()
        copy = self.sudo().create({
            'template_id': self.template_id.id or False,
            'requisition_id': self.requisition_id.id,
            'title': self.title,
            'body': self.body,
            'summary': self.summary,
        })
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': copy.id, 'view_mode': 'form',
                'views': [[False, 'form']], 'name': copy.name}

    # ---------------------------------------------------- what final does
    def _become_current(self):
        """Point the request at this version and put it on the job.

        Both legs guarded: a request whose job does not exist yet is the
        normal case for an advert written before the sign-off came back, and
        that must not turn an agreement into an error (R104).
        """
        self.ensure_one()
        self.sudo().write({'approved_on': fields.Datetime.now(),
                           'approved_by': self.env.uid})
        req = self.requisition_id.sudo()
        was = req.jd_current_id
        # SAVEPOINTS, not bare try/excepts: a failure that reached the
        # database aborts the WHOLE transaction, and catching the exception
        # in Python does not revive it — every statement after it fails too,
        # including the ones that record the agreement itself.
        self.requisition_id._leg(
            'pointing the request at advert %s' % self.id,
            lambda: self.requisition_id.sudo().write(
                {'jd_current_id': self.id}))
        job = self.requisition_id.job_id
        if job:
            self.requisition_id._leg(
                'putting advert %s on the job' % self.id,
                lambda: job.sudo().write(
                    {'website_description': self.body or ''}))
        # A role already advertised has job-board packs built from the old
        # words: the Details tab offers "Republish" until somebody does.
        if req.published and was != self:
            req.write({'advert_stale': True})
        req._log_role(_("Version %s of the advert is final and in use.",
                        self.version or 1))
        return True

    def _jd_manager(self):
        """Who a draft is shared with: the manager the request was asked of,
        else the person it is for, else who they would report to."""
        self.ensure_one()
        req = self.requisition_id.sudo()
        return (req.asked_employee_id or req.requested_by_id
                or req.reporting_manager_id)

    # ------------------------------------------------------------ the doors
    def action_open_requisition(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.hiring.requisition',
                'res_id': self.requisition_id.id, 'view_mode': 'form',
                'views': [[False, 'form']],
                'name': self.requisition_id.display_name}
