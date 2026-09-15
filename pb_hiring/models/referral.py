# -*- coding: utf-8 -*-
"""`pb.hiring.referral` — somebody in the company put a name forward.

A REFERRAL IS NOT A COPY OF A CANDIDATE. The candidate is an `hr.applicant`
like any other, on the real job, in the real pipeline, tagged with the real
Referral source — because a referral that lives in a side table is a referral
the recruiter never sees. This row is the OTHER half: who put the name
forward, so the person who did it can be told how it went and so the company
can see which roles referrals actually fill.

THE STATE IS READ, NEVER TYPED. It follows the candidate: received while
nobody has looked, being looked at once they are past the first stage, joined
us when the hired stage is reached, not this time when the application is
refused or archived. A referral whose state is a stored word is a referral
that is wrong within a week (R50, from the other side — never let a status be
maintained by hand when the truth lives somewhere else).
"""

import logging

from odoo import _, api, fields, models

from .hiring_common import REFERRAL_STATES, as_id, flag, P_REFERRAL_MAIL

_logger = logging.getLogger(__name__)


class PbHiringReferral(models.Model):
    _name = 'pb.hiring.referral'
    _description = 'Referral'
    _inherit = ['mail.thread']
    _order = 'id desc'

    requisition_id = fields.Many2one(
        'pb.hiring.requisition', string='Hiring request', required=True,
        index=True, ondelete='cascade')
    job_id = fields.Many2one('hr.job', related='requisition_id.job_id',
                             store=True, readonly=True, string='The job')
    employee_id = fields.Many2one(
        'hr.employee', string='Who put them forward', required=True,
        index=True, ondelete='cascade')
    referrer_user_id = fields.Many2one(
        'res.users', string='Who put them forward (login)', index=True,
        compute='_compute_referrer_user', store=True, readonly=True)
    applicant_id = fields.Many2one('hr.applicant', string='The candidate',
                                   index=True, ondelete='set null')
    candidate_name = fields.Char(string='Their name', required=True)
    candidate_email = fields.Char(string='Their email')
    candidate_phone = fields.Char(string='Their phone')
    note = fields.Text(string='Why they would be good')
    state = fields.Selection(REFERRAL_STATES, string='How it is going',
                             compute='_compute_state', store=False)
    state_label = fields.Char(compute='_compute_state', store=False,
                              string='How it is going, in words')
    submitted_on = fields.Datetime(string='Sent in on', readonly=True,
                                   default=fields.Datetime.now, copy=False)
    company_id = fields.Many2one(
        'res.company', related='requisition_id.company_id', store=True,
        index=True, readonly=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.candidate_name or _('Referral')

    @api.depends('employee_id')
    def _compute_referrer_user(self):
        for rec in self:
            rec.referrer_user_id = rec.employee_id.sudo().user_id

    # THE DEPENDENCY LIST IS WHAT MAKES A NON-STORED COMPUTE HONEST. Odoo
    # uses it to invalidate the cache as well as to recompute, so depending
    # on `applicant_id` alone means the state is right the first time it is
    # read and then frozen for the life of the environment — a referral that
    # says "received" over a candidate who was turned down half an hour ago.
    # Named through `application_status` (itself computed) plus the stage,
    # because those are the two things this answer is actually made of.
    @api.depends('applicant_id', 'applicant_id.active',
                 'applicant_id.application_status', 'applicant_id.stage_id')
    def _compute_state(self):
        """Read as the system: the person who made the referral holds no
        recruitment permission and must still be able to see how it went."""
        labels = dict(REFERRAL_STATES)
        for rec in self:
            key = rec._state_of(rec.applicant_id)
            rec.state = key
            rec.state_label = labels.get(key, '')

    @api.model
    def _state_of(self, applicant):
        """The mapping, in one place, so the board and the page agree."""
        applicant = applicant.sudo() if applicant else applicant
        if not applicant or not applicant.exists():
            return 'received'
        status = applicant.application_status
        if status == 'hired':
            return 'hired'
        if status in ('refused', 'archived'):
            return 'not_this_time'
        stage = applicant.stage_id
        if stage and stage.sequence and stage.sequence > 0:
            return 'in_progress'
        return 'received'

    # =====================================================================
    #  Making one
    # =====================================================================
    @api.model
    def refer(self, requisition_id, employee_id, values):
        """Create the candidate and the referral, in that order.

        PUBLIC AND THEREFORE COERCED AT THE DOOR (R43). Called by the portal
        controller, which has already proved the employee is the session's
        own — this method never trusts an employee id on its own and is not
        reachable from a browser without one of the two groups.
        """
        requisition_id = as_id(requisition_id)
        employee_id = as_id(employee_id)
        Requisition = self.env['pb.hiring.requisition'].sudo()
        req = Requisition.browse(requisition_id).exists()
        employee = self.env['hr.employee'].sudo().browse(employee_id).exists()
        if not req or not employee:
            raise ValueError('unknown request or employee')
        if not req.referral_open or req.state != 'open':
            raise ValueError('this role is not open to referrals')
        if employee.company_id and req.company_id \
                and employee.company_id != req.company_id:
            raise ValueError('that role belongs to another company')

        applicant = self._make_applicant(req, employee, values)
        referral = self.sudo().create({
            'requisition_id': req.id,
            'employee_id': employee.id,
            'applicant_id': applicant.id if applicant else False,
            'candidate_name': values.get('name') or '',
            'candidate_email': values.get('email') or '',
            'candidate_phone': values.get('phone') or '',
            'note': values.get('note') or '',
        })
        try:
            referral._tell_the_recruiter()
        except Exception:               # noqa: BLE001 — never fail a referral
            _logger.warning('pb_hiring: the recruiter was not told about '
                            'referral %s', referral.id, exc_info=True)
        return referral

    @api.model
    def _make_applicant(self, req, employee, values):
        job = req.job_id
        if not job:
            job = req._ensure_job()
        source = self._referral_source()
        vals = {
            'partner_name': values.get('name') or '',
            'email_from': values.get('email') or False,
            'partner_phone': values.get('phone') or False,
            'job_id': job.id,
            'company_id': req.company_id.id,
            'department_id': req.department_id.id,
            'user_id': req.recruiter_id.id or job.user_id.id or False,
            'applicant_notes': _(
                "Put forward by %(who)s.\n\n%(note)s",
                who=employee.name or '', note=values.get('note') or ''),
            'pb_requisition_id': req.id,
        }
        if source:
            vals['source_id'] = source.id
        applicant = self.env['hr.applicant'].sudo().create(vals)
        attachment = values.get('attachment')
        if attachment:
            try:
                self.env['ir.attachment'].sudo().create({
                    'name': attachment.get('name') or 'CV',
                    'datas': attachment.get('datas'),
                    'mimetype': attachment.get('mimetype') or False,
                    'res_model': 'hr.applicant',
                    'res_id': applicant.id,
                })
            except Exception:           # noqa: BLE001
                _logger.warning('pb_hiring: the CV on a referral for %s was '
                                'not stored', job.name, exc_info=True)
        return applicant

    @api.model
    def _referral_source(self):
        """BY NAME, never by id. Ids differ between databases and a hard-coded
        one silently tags a referral as something else entirely."""
        Source = self.env['utm.source'].sudo()
        source = Source.search([('name', '=ilike', 'Referral')], limit=1)
        if not source:
            source = Source.create({'name': 'Referral'})
        return source

    def _tell_the_recruiter(self):
        self.ensure_one()
        if not flag(self.env, P_REFERRAL_MAIL):
            _logger.info('pb_hiring: referral mail is switched off; %s would '
                         'have told %s', self.candidate_name,
                         self.requisition_id.recruiter_id.name or 'nobody')
            return False
        recruiter = self.requisition_id.sudo().recruiter_id
        if not recruiter or not recruiter.email:
            _logger.info('pb_hiring: referral %s has no recruiter to tell',
                         self.id)
            return False
        template = self.env.ref('pb_hiring.mail_template_referral_recruiter',
                                raise_if_not_found=False)
        if not template:
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': recruiter.email})
        return True

    # ------------------------------------------------------------ the doors
    def action_open_applicant(self):
        self.ensure_one()
        if not self.applicant_id:
            return False
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.applicant',
                'res_id': self.applicant_id.id, 'view_mode': 'form',
                'views': [[False, 'form']], 'name': self.candidate_name or '',
                'context': {'active_test': False}}
