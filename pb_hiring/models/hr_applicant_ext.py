# -*- coding: utf-8 -*-
"""Screening, on the candidate record the recruiter already uses.

FOUR ADDITIVE FIELDS AND ONE BUTTON. The standard applicant is left exactly as
it is — its stages, its refuse reasons, its talent pools, its kanban — because
that store works and rebuilding it would be a worse version of something that
already ships. What it does not have is the one-press answer a screener
actually gives: shortlisted, not this time, worth keeping in touch with, or
better suited to another role.

THE LAST ONE IS THE POINT. "Better suited to another role" is a screening
decision everywhere and a retyping exercise in most systems. Here it moves the
candidate to the other job, puts them at its first stage and writes a line on
both jobs so neither recruiter is surprised.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hiring_common import SCREEN_TAGS, as_id

_logger = logging.getLogger(__name__)


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    pb_requisition_id = fields.Many2one(
        'pb.hiring.requisition', string='Hiring request', index=True,
        ondelete='set null',
        help='The request this role was opened by, where there was one.')
    pb_screen = fields.Selection(
        SCREEN_TAGS, string='First look', copy=False, tracking=True,
        help='What the screener decided when they read the CV.')
    pb_screen_on = fields.Datetime(string='Screened on', readonly=True,
                                   copy=False)
    pb_screen_by = fields.Many2one('res.users', string='Screened by',
                                   readonly=True, copy=False)
    pb_other_job_id = fields.Many2one(
        'hr.job', string='Better suited to', copy=False,
        help='Where this candidate was moved to, or should be moved to.')
    pb_referral_ids = fields.One2many('pb.hiring.referral', 'applicant_id',
                                      string='Referral')

    # =====================================================================
    #  The four answers
    # =====================================================================
    def action_pb_screen(self, tag, job_id=None, reason_id=None):
        """One press, one outcome, and every outcome says what it did."""
        tag = (tag or '').strip()
        if tag not in dict(SCREEN_TAGS):
            raise UserError(_("That is not one of the screening answers."))
        done = []
        for rec in self:
            rec.sudo().write({'pb_screen': tag,
                              'pb_screen_on': fields.Datetime.now(),
                              'pb_screen_by': rec.env.uid})
            if tag == 'shortlisted':
                rec._pb_shortlist()
            elif tag == 'rejected':
                rec._pb_reject(reason_id)
            elif tag == 'future_fit':
                rec._pb_keep_in_touch()
            elif tag == 'other_role':
                rec._pb_move_role(job_id)
            done.append(rec.id)
        return done

    def _pb_shortlist(self):
        self.ensure_one()
        stage = self.env['hr.recruitment.stage'].sudo().search(
            [('sequence', '>', self.stage_id.sequence or 0),
             '|', ('job_ids', '=', False), ('job_ids', 'in', self.job_id.ids)],
            order='sequence, id', limit=1)
        if stage:
            self.sudo().write({'stage_id': stage.id,
                               'kanban_state': 'done'})
        else:
            self.sudo().write({'kanban_state': 'done'})
        self.sudo().message_post(body=_("Shortlisted."))
        return True

    def _pb_reject(self, reason_id=None):
        """The standard refuse, done exactly as the standard wizard does it —
        reason, archived, dated — so nothing downstream can tell the
        difference (`hr_recruitment/wizard/applicant_refuse_reason.py`)."""
        self.ensure_one()
        Reason = self.env['hr.applicant.refuse.reason'].sudo()
        reason = Reason.browse(as_id(reason_id)).exists() if reason_id \
            else Reason.browse()
        if not reason:
            reason = Reason.search([], order='id', limit=1)
        vals = {'active': False, 'refuse_date': fields.Datetime.now()}
        if reason:
            vals['refuse_reason_id'] = reason.id
        self.sudo().write(vals)
        self.sudo().message_post(body=_(
            "Not this time%s.", (' — %s' % reason.name) if reason else ''))
        return True

    def _pb_keep_in_touch(self):
        """Into the company's own talent pool, made once and named plainly."""
        self.ensure_one()
        Pool = self.env['hr.talent.pool'].sudo()
        company = self.company_id or self.env.company
        name = _('Worth keeping in touch with — %s', company.name or '')
        pool = Pool.search([('name', '=', name)], limit=1)
        if not pool:
            pool = Pool.create({'name': name, 'company_id': company.id})
        self.sudo().write({'talent_pool_ids': [(4, pool.id)]})
        self.sudo().message_post(body=_(
            "Added to “%s” so they are not lost.", pool.name))
        return True

    def _pb_move_role(self, job_id):
        self.ensure_one()
        job = self.env['hr.job'].sudo().browse(as_id(job_id)).exists()
        if not job:
            raise UserError(_(
                "Say which role they are better suited to before moving them."))
        if job.id == self.job_id.id:
            raise UserError(_("They are already on that role."))
        if job.company_id and self.company_id \
                and job.company_id != self.company_id:
            raise UserError(_(
                "That role belongs to another company, so a candidate cannot "
                "be moved onto it."))
        old = self.job_id
        first = self.env['hr.recruitment.stage'].sudo().search(
            ['|', ('job_ids', '=', False), ('job_ids', 'in', job.ids)],
            order='sequence, id', limit=1)
        vals = {'job_id': job.id, 'pb_other_job_id': job.id,
                'department_id': job.department_id.id or False}
        if first:
            vals['stage_id'] = first.id
        requisition = self.env['pb.hiring.requisition'].sudo().search(
            [('job_id', '=', job.id)], order='id desc', limit=1)
        vals['pb_requisition_id'] = requisition.id or False
        self.sudo().write(vals)
        self.sudo().message_post(body=_(
            "Moved from %(old)s to %(new)s, back to the first stage.",
            old=old.name or '', new=job.name or ''))
        # A line on BOTH jobs: the recruiter losing a candidate and the one
        # gaining one both want to know, and neither is watching the other.
        for target, text in ((old, _("%(who)s was moved to %(job)s.",
                                     who=self.partner_name or '',
                                     job=job.name or '')),
                             (job, _("%(who)s came across from %(job)s.",
                                     who=self.partner_name or '',
                                     job=old.name or ''))):
            if not target:
                continue
            try:
                target.sudo().message_post(body=text)
            except Exception:           # noqa: BLE001 — a note is a courtesy
                _logger.warning('pb_hiring: could not note the move on job %s',
                                target.id, exc_info=True)
        return True

    # ------------------------------------------------------------ the doors
    def action_pb_move_role(self):
        """The form button: move to the role already named on the record."""
        self.ensure_one()
        if not self.pb_other_job_id:
            raise UserError(_(
                "Pick the role they are better suited to first."))
        return self.action_pb_screen('other_role',
                                     job_id=self.pb_other_job_id.id)

    @api.model
    def pb_open_jobs(self, company_ids=None):
        """The roles a candidate could be moved onto, for the drawer's list."""
        co_ids = company_ids or self.env.companies.ids \
            or [self.env.company.id]
        jobs = self.env['hr.job'].sudo().search(
            [('company_id', 'in', co_ids), ('active', '=', True)],
            order='name', limit=200)
        return [{'id': job.id, 'name': job.name or '',
                 'department': job.department_id.name or ''} for job in jobs]
