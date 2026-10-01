# -*- coding: utf-8 -*-
"""RECRUIT P7 (G-21) — the agency side: submissions, the 6-month rule, the
agency's own emails.

AN AGENCY SEES TWO THINGS AND NOTHING ELSE: the roles it was put on, and the
people it put forward, each with a coarse stage (In review / Interviewing /
Offer / Joined / Not selected). Every read on the portal is made here or in
`controllers/agency_portal.py` as the system, after the route has proved the
sign-in belongs to the agency — and only those fields leave.

THE 6-MONTH RULE. A submission is refused when the same person (email or
phone) is an active candidate anywhere in the company, or applied — or was
put forward — in the last six months (`pb_hiring.agency_cooling_months`).
The agency is told the date and nothing else. Every attempt is written down,
refused ones included, because "the agency says they sent us Lan in March" is
a conversation somebody will have.

A REFUSED ATTEMPT DOES NOT START A NEW WINDOW. The window counts applications
and ACCEPTED submissions; counting refused attempts too would let one refusal
extend itself for ever.
"""

import base64
import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import email_normalize

from .channels_p7 import utm_record
from .hiring_common import P_NOTIFY_MAIL, flag, number

_logger = logging.getLogger(__name__)

P_COOLING_MONTHS = 'pb_hiring.agency_cooling_months'
COOLING_DEFAULT = 6

SUBMISSION_STATES = [
    ('accepted', 'Accepted'),
    ('refused_rule', 'Not accepted (6-month rule)'),
    ('withdrawn', 'Withdrawn'),
]
COARSE_STAGES = [
    ('in_review', 'In review'),
    ('interviewing', 'Interviewing'),
    ('offer', 'Offer'),
    ('joined', 'Joined'),
    ('not_selected', 'Not selected'),
]
INTERVIEW_KEYS = ('phone', 'assignment', 'discussion_1', 'discussion_2',
                  'discussion_3', 'reference')
OFFER_KEYS = ('offer', 'post_offer')


def coarse_of(app):
    """The one word an agency is given about where its person is."""
    app = app.sudo().with_context(active_test=False)
    if not app:
        return ''
    key = app.stage_id.pb_key or ''
    family = app.stage_id.pb_family or 'open'
    if key == 'joined' or app.application_status == 'hired':
        return 'joined'
    if family == 'closed' or not app.active:
        return 'not_selected'
    if key in OFFER_KEYS:
        return 'offer'
    if key in INTERVIEW_KEYS:
        return 'interviewing'
    return 'in_review'


def _phone_key(env, phone, company):
    """The phone as the applicant model stores it for matching (E.164 against
    the company's country), plus the bare digits as a second key."""
    raw = (phone or '').strip()
    if not raw:
        return '', ''
    digits = ''.join(ch for ch in raw if ch.isdigit())
    sanitized = ''
    try:
        probe = env['hr.applicant'].sudo().new({'partner_phone': raw,
                                                 'company_id': company.id})
        sanitized = probe.partner_phone_sanitized or ''
    except Exception:                   # noqa: BLE001 — a key, never a crash
        sanitized = ''
    return sanitized, digits


class PbHiringAgencySubmission(models.Model):
    _name = 'pb.hiring.agency.submission'
    _description = 'Somebody an agency put forward'
    _order = 'submitted_on desc, id desc'

    vendor_id = fields.Many2one('pb.vendor', string='Agency', required=True,
                                index=True, ondelete='cascade')
    requisition_id = fields.Many2one('pb.hiring.requisition', string='Role',
                                     required=True, index=True, ondelete='cascade')
    applicant_id = fields.Many2one('hr.applicant', string='Candidate',
                                   ondelete='set null', index='btree_not_null')
    submitted_by_user_id = fields.Many2one('res.users', string='Put forward by',
                                           ondelete='set null')
    submitted_on = fields.Datetime(string='Put forward on', required=True,
                                   default=fields.Datetime.now, index=True)
    candidate_name = fields.Char(string='Name', required=True)
    candidate_email = fields.Char(string='Email')
    candidate_phone = fields.Char(string='Phone')
    candidate_location = fields.Char(string='Where they are')
    note = fields.Text(string='The agency\'s note')
    state = fields.Selection(SUBMISSION_STATES, string='Outcome', required=True,
                             default='accepted', index=True)
    refusal_reason = fields.Char(string='Why it was not accepted')
    coarse_stage = fields.Selection(COARSE_STAGES, string='Where they are now',
                                    compute='_compute_coarse')
    coarse_label = fields.Char(compute='_compute_coarse')
    company_id = fields.Many2one('res.company', related='requisition_id.company_id',
                                 store=True, index=True)

    def _compute_coarse(self):
        labels = dict(COARSE_STAGES)
        for rec in self:
            if rec.state == 'refused_rule':
                rec.coarse_stage = False
                rec.coarse_label = dict(SUBMISSION_STATES)['refused_rule']
                continue
            if rec.state == 'withdrawn':
                rec.coarse_stage = False
                rec.coarse_label = dict(SUBMISSION_STATES)['withdrawn']
                continue
            key = coarse_of(rec.applicant_id) if rec.applicant_id else 'not_selected'
            rec.coarse_stage = key or False
            rec.coarse_label = labels.get(key, '')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s · %s' % (rec.candidate_name or '',
                                            rec.vendor_id.name or '')

    # =====================================================================
    #  The 6-month rule
    # =====================================================================
    @api.model
    def _months(self):
        return max(1, number(self.env, P_COOLING_MONTHS, COOLING_DEFAULT) or COOLING_DEFAULT)

    @api.model
    def _cooling_block(self, company, email, phone):
        """None, or the one sentence the agency is told (with only a date).

        Same person = same normalised email, or same phone (as the applicant
        model sanitises it, or the same digits). Any of the company's
        pipelines counts.
        """
        Applicant = self.env['hr.applicant'].sudo().with_context(active_test=False)
        address = email_normalize(email or '') or ''
        sanitized, digits = _phone_key(self.env, phone, company)
        ors = []
        if address:
            ors.append([('email_normalized', '=', address)])
        if sanitized:
            ors.append([('partner_phone_sanitized', '=', sanitized)])
        if digits and len(digits) >= 7:
            ors.append([('partner_phone', '=', (phone or '').strip())])
        if not ors:
            return None
        dom = ors[0]
        for extra in ors[1:]:
            dom = ['|'] + dom + extra
        dom = [('company_id', '=', company.id)] + dom
        months = self._months()
        rule = _("Under the %s-month rule this submission is not accepted.", months) \
            if months != 6 else _("Under the 6-month rule this submission is not accepted.")
        # 1. an active candidate anywhere in the company's pipelines
        active = Applicant.search(dom + [('active', '=', True)], order='create_date desc')
        live = active.filtered(lambda a: (a.stage_id.pb_family or 'open') == 'open')
        if live:
            when = min(live.mapped('create_date'))
            return _("This person is already a candidate with us (since %(date)s). %(rule)s",
                     date=self._words(when), rule=rule)
        # 2. applied, or was put forward, inside the window (any state)
        since = fields.Datetime.now() - relativedelta(months=months)
        recent = Applicant.search(dom + [('create_date', '>=', since)],
                                  order='create_date desc', limit=1)
        sub_dom = [('company_id', '=', company.id), ('state', '=', 'accepted'),
                   ('submitted_on', '>=', since)]
        s_ors = []
        if address:
            s_ors.append([('candidate_email', '=ilike', address)])
        if (phone or '').strip():
            s_ors.append([('candidate_phone', '=', (phone or '').strip())])
        sub = self.browse()
        if s_ors:
            sdom = s_ors[0] if len(s_ors) == 1 else ['|'] + s_ors[0] + s_ors[1]
            sub = self.sudo().search(sub_dom + sdom, order='submitted_on desc', limit=1)
        dates = [d for d in (recent.create_date if recent else None,
                             sub.submitted_on if sub else None) if d]
        if dates:
            return _("This person applied to us on %(date)s. %(rule)s",
                     date=self._words(max(dates)), rule=rule)
        return None

    @api.model
    def _words(self, when):
        day = fields.Date.to_date(when) if when else None
        return day.strftime('%d %b %Y').lstrip('0') if day else ''

    # =====================================================================
    #  Putting somebody forward
    # =====================================================================
    @api.model
    def _submit(self, vendor, req, user, values, attachment=None):
        """Log the attempt, apply the rule, make the candidate.

        values: name, email, phone, location, note (already checked by the
        route: required fields, the tick, the file). Returns the submission.
        """
        vendor = vendor.sudo()
        req = req.sudo()
        if req.state != 'open' or vendor not in req.agency_vendor_ids:
            raise UserError(_("This role is not open to your agency any more."))
        name = (values.get('name') or '').strip()[:200]
        email = email_normalize(values.get('email') or '') or (values.get('email') or '').strip()
        phone = (values.get('phone') or '').strip()[:60]
        base = {
            'vendor_id': vendor.id, 'requisition_id': req.id,
            'submitted_by_user_id': user.id if user else False,
            'candidate_name': name, 'candidate_email': email,
            'candidate_phone': phone,
            'candidate_location': (values.get('location') or '').strip()[:200],
            'note': (values.get('note') or '').strip()[:2000],
        }
        block = self._cooling_block(req.company_id, email, phone)
        if block:
            row = self.sudo().create(dict(base, state='refused_rule', refusal_reason=block))
            req._leg('the refused-submission note on %s' % req.name,
                     lambda: req.message_post(body=_(
                         "%(agency)s tried to put forward %(who)s; not accepted under "
                         "the 6-month rule.", agency=vendor.name or '', who=name)))
            return row
        app = self._make_applicant(vendor, req, base, attachment)
        row = self.sudo().create(dict(base, state='accepted', applicant_id=app.id))
        req._leg('the to-do for the recruiter on %s' % req.name,
                 lambda: self._todo(req, app, vendor))
        req._leg('the submission note on %s' % req.name,
                 lambda: req.message_post(body=_(
                     "%(agency)s put forward %(who)s.", agency=vendor.name or '', who=name)))
        return row

    @api.model
    def _make_applicant(self, vendor, req, base, attachment):
        job = req.job_id or req._ensure_job()
        Stage = self.env['hr.recruitment.stage']
        screening = Stage._pb_stage('screening') if hasattr(Stage, '_pb_stage') else Stage.browse()
        source = utm_record(self.env, 'utm.source', 'Agency')
        channel = self.env['pb.hiring.channel'].sudo().search(
            [('company_id', '=', req.company_id.id), ('key', '=', 'agency')], limit=1)
        vals = {
            'partner_name': base['candidate_name'],
            'email_from': base['candidate_email'] or False,
            'partner_phone': base['candidate_phone'] or False,
            'job_id': job.id,
            'company_id': req.company_id.id,
            'department_id': req.department_id.id or False,
            'user_id': req.recruiter_id.id or job.user_id.id or False,
            'pb_requisition_id': req.id,
            'source_id': source.id,
            'pb_channel_id': channel.id or False,
            'pb_agency_vendor_id': vendor.id,
            'pb_location': base['candidate_location'] or False,
            'pb_application_touch': {'source': 'Agency', 'vendor_id': vendor.id},
            'pb_consent_on': fields.Datetime.now(),
            'pb_consent_text': _("Put forward by %s, who confirmed the candidate "
                                 "agreed to be put forward for this role.",
                                 vendor.name or ''),
            'applicant_notes': _("Put forward by %(agency)s.\n\n%(note)s",
                                 agency=vendor.name or '', note=base.get('note') or ''),
        }
        if screening:
            vals['stage_id'] = screening.id
        app = self.env['hr.applicant'].sudo().create(vals)
        if attachment:
            self.env['ir.attachment'].sudo().create({
                'name': attachment.get('name') or 'CV',
                'datas': attachment.get('datas'),
                'mimetype': attachment.get('mimetype') or False,
                'res_model': 'hr.applicant', 'res_id': app.id, 'public': False,
                'pb_form_key': 'cv',
            })
        return app

    @api.model
    def _todo(self, req, app, vendor):
        user = req.recruiter_id or req.job_id.user_id
        if not user:
            return False
        app.sudo().activity_schedule(
            'mail.mail_activity_data_todo', user_id=user.id,
            summary=_("First look: put forward by %s", vendor.name or ''),
            note=_("%(agency)s put %(who)s forward for %(role)s through the agency "
                   "portal.", agency=vendor.name or '', who=app.partner_name or '',
                   role=req.title or ''))
        return True

    # =====================================================================
    #  Figures (the vendor card, Hiring numbers)
    # =====================================================================
    @api.model
    def _figures(self, subs):
        subs = subs.sudo()
        accepted = subs.filtered(lambda s: s.state == 'accepted' and s.applicant_id)
        apps = accepted.mapped('applicant_id').with_context(active_test=False)
        reached = set()
        if apps:
            logs = self.env['pb.hiring.stage.log'].sudo().search_read(
                [('applicant_id', 'in', apps.ids),
                 ('to_stage_id.pb_key', 'in', list(INTERVIEW_KEYS + OFFER_KEYS + ('joined',)))],
                ['applicant_id'])
            reached = {r['applicant_id'][0] for r in logs if r['applicant_id']}
            ivs = self.env['pb.hiring.interview'].sudo().search_read(
                [('applicant_id', 'in', apps.ids)], ['applicant_id'])
            reached |= {r['applicant_id'][0] for r in ivs if r['applicant_id']}
        offered = set()
        if apps:
            offers = self.env['pb.hiring.offer'].sudo().search_read(
                [('applicant_id', 'in', apps.ids),
                 ('state', 'in', ('sent', 'accepted', 'declined', 'signed', 'joined', 'dropped'))],
                ['applicant_id'])
            offered = {r['applicant_id'][0] for r in offers if r['applicant_id']}
        out = {'submitted': len(subs.filtered(lambda s: s.state != 'withdrawn')),
               'accepted': len(accepted), 'refused': len(subs.filtered(
                   lambda s: s.state == 'refused_rule')),
               'interviewed': 0, 'offers': 0, 'joined': 0}
        for s in accepted:
            coarse = coarse_of(s.applicant_id)
            aid = s.applicant_id.id
            if aid in reached or coarse in ('interviewing', 'offer', 'joined'):
                out['interviewed'] += 1
            if aid in offered or coarse in ('offer', 'joined'):
                out['offers'] += 1
            if coarse == 'joined':
                out['joined'] += 1
        return out


class HiringApplicantAgency(models.Model):
    _inherit = 'hr.applicant'

    pb_agency_vendor_id = fields.Many2one('pb.vendor', string='Put forward by agency',
                                          ondelete='set null', index='btree_not_null',
                                          copy=False)
    pb_agency_submission_ids = fields.One2many('pb.hiring.agency.submission',
                                               'applicant_id', string='Agency submissions')


class HiringRequisitionAgency(models.Model):
    _inherit = 'pb.hiring.requisition'

    pb_agency_portal_url = fields.Char(compute='_compute_pb_agency_portal_url')
    pb_agency_name = fields.Char(compute='_compute_pb_agency_portal_url')
    pb_agency_submission_ids = fields.One2many('pb.hiring.agency.submission',
                                               'requisition_id', string='Agency submissions')

    @api.depends_context('pb_agency_name')
    def _compute_pb_agency_portal_url(self):
        for rec in self:
            base = rec.get_base_url().rstrip('/') if rec.id else ''
            rec.pb_agency_portal_url = '%s/my/agency/role/%s' % (base, rec.id) if rec.id else ''
            rec.pb_agency_name = self.env.context.get('pb_agency_name') or \
                (rec.agency_vendor_ids[:1].name or '')

    def _tell_the_agency(self, vendor):
        """The agency's own email: the role is on its portal (with the advert).
        To each person who signs in for the agency, else its contact."""
        self.ensure_one()
        vendor = vendor.sudo()
        if not flag(self.env, P_NOTIFY_MAIL):
            return 0
        template = self.env.ref('pb_hiring.mail_template_agency_assigned',
                                raise_if_not_found=False)
        if not template:
            return 0
        addresses = [u.email for u in vendor.portal_user_ids if u.active and u.email]
        if not addresses and vendor.contact_email:
            addresses = [vendor.contact_email]
        sender = self.env['pb.hiring']._sender(self.company_id)
        sent = 0
        for address in dict.fromkeys(a.strip() for a in addresses if a and a.strip()):
            values = {'email_to': address, 'auto_delete': False}
            if sender:
                values['email_from'] = sender
            template.sudo().with_context(pb_agency_name=vendor.name or '').send_mail(
                self.id, force_send=False, email_values=values)
            sent += 1
        return sent


class HiringVendorInvite(models.Model):
    _inherit = 'pb.vendor'

    def _pb_invite_agency(self, email, name=None):
        """Give somebody at this agency a portal sign-in and email them the
        set-password link (to `/my/agency`). Returns `(user, made, mailed)`."""
        self.ensure_one()
        if self.vendor_type != 'recruitment':
            raise UserError(_("Only a recruitment agency has a portal."))
        user, made = self._pb_portal_login(email, name=name)
        mailed = self._pb_send_invite(user)
        return user, made, mailed

    def _pb_signup_url(self, user):
        """The standard portal invitation link (signup type, valid six days by
        default), landing on the agency portal once the password is set."""
        partner = user.sudo().partner_id
        partner.signup_prepare()
        url = partner._get_signup_url_for_action(url='/my/agency').get(partner.id)
        return url or ''

    def _pb_send_invite(self, user):
        template = self.env.ref('pb_hiring.mail_template_agency_invite',
                                raise_if_not_found=False)
        if not template or not user.email:
            return False
        url = self._pb_signup_url(user)
        sender = self.env['pb.hiring']._sender(self.company_id or self.env.company)
        values = {'email_to': user.email, 'auto_delete': False}
        if sender:
            values['email_from'] = sender
        template.sudo().with_context(
            pb_signup_url=url, pb_person=user.name or '',
            pb_portal_url='%s/my/agency' % self.sudo().get_base_url().rstrip('/'),
        ).send_mail(self.id, force_send=False, email_values=values)
        self.sudo().message_post(body=_("Invited %s to the agency portal.", user.email))
        return True
