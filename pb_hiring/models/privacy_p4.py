# -*- coding: utf-8 -*-
"""RECRUIT phase 4 — private until shared.

WHAT THIS FILE ADDS (register lines G-08, G-26, G-36, G-41 masking, G-45
retention), in the order a recruiter meets it:

  * **Sharing** (`pb.hiring.share`): a candidate belongs to the hiring team
    until a recruiter shares PARTS of the record with a named person — the
    hiring manager, the reporting manager, a panel member. One row per person
    per candidate; `parts` says what. The role carries a default ("What the
    hiring manager sees by default") applied when a candidate arrives.
  * **Every payload masks** (`_parts`): board cards, the candidate drawer, the
    timeline, the role page. Sudo reads bypass field `groups`, so nothing here
    trusts the ORM to hide a field: what leaves the server is built from the
    reader's parts. A reader with no share sees name, stage and interview
    dates only, and a sentence saying so.
  * **Money locks**: expected pay is its own part, off by default. Offer and
    budget figures are blanked for anybody who is not on the hiring team
    (field `groups` on the offer money fields as well; the approval inbox
    reads the record as the system and keeps showing amounts to a seat).
  * **Private recruiter notes** (`pb.hiring.note`): never `mail.message`.
    The author and the talent lead read them; one note at a time can be
    shared with named people.
  * **The Resume bank** (`search_bank`): Future-fit people, pool members and,
    on a switch, everyone who ever applied — hiring team only.
  * **Retention** (`pb.hiring.retention.rule`, `pb_retention_until`): the
    consent a candidate gave starts a clock per market; the anonymise leg
    runs nightly only when `pb_hiring.retention_enabled` is on (it ships
    OFF), and "Run now" does exactly what the night would.

API left for P5–P8 (see the phase report): `pb.hiring.share.parts_for(app,
user)`, `pb.hiring._parts(app)`, `pb.hiring._doc_rows(app, parts,
tokenised)`, `pb.hiring.note`, `search_bank`, `get_retention_preview`,
`hr.applicant._pb_retention_protected()` / `_pb_anonymise()`.
"""

import logging
import re

from dateutil.relativedelta import relativedelta
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext

from .hiring_common import (
    GROUP_ADMIN, GROUP_MANAGER, GROUP_USER, OFFER_LIVE, SCREEN_TAGS, as_id,
    flag, fold, leg,
)

_logger = logging.getLogger(__name__)

#: What a recruiter can share, in the order the Share sheet lists it.
PART_KEYS = ('profile', 'cv', 'portfolio', 'assignment', 'attachments',
             'answers', 'scorecards', 'expected_pay')
#: The parts that are FILES: taking one away regenerates the file links.
FILE_PARTS = ('cv', 'portfolio', 'assignment', 'attachments')
#: The role's default when nobody has set one (G-08: profile and CV).
DEFAULT_PARTS = 'profile,cv'
SHARE_WITH = [
    ('nobody', 'Nobody until a recruiter shares'),
    ('hiring_manager', 'The hiring manager'),
    ('hiring_manager_and_panel', 'The hiring manager and the panel'),
]
PURGE_MODES = [
    ('anonymise', 'Anonymise'),
    ('delete', 'Delete'),
]
#: What an anonymised candidate is called everywhere afterwards.
REMOVED = 'Candidate (removed)'
P_RETENTION_ENABLED = 'pb_hiring.retention_enabled'
#: How far ahead the preview looks for "expiring soon".
SOON_DAYS = 30
BANK_PAGE = 40
BANK_READ_CAP = 5000

_CV_NAME = re.compile(r'(\bcv\b|resume|résumé|curriculum|lý lịch|ly lich)', re.I)
_ASSIGN_NAME = re.compile(r'(assignment|take[- ]?home|task|bài tập|bai tap|tugas)', re.I)
_PORTFOLIO_NAME = re.compile(r'portfolio', re.I)


def _csv(parts):
    """A clean, ordered CSV of known part keys."""
    if isinstance(parts, str):
        parts = parts.split(',')
    wanted = {str(p).strip() for p in (parts or []) if p}
    return ','.join(k for k in PART_KEYS if k in wanted)


def _split(csv):
    return {p for p in (csv or '').split(',') if p in PART_KEYS}


def _user_of(employee):
    """An employee's login: the internal one first, else the portal one
    (`pb_zoho_bridge`). Both are checked when a share is matched."""
    if not employee:
        return employee.env['res.users']
    emp = employee.sudo()
    user = emp.user_id
    if not user and 'pb_portal_user_id' in emp._fields:
        user = emp.pb_portal_user_id
    return user


def _is_hiring_user(user):
    return bool(user) and (user.has_group(GROUP_USER) or user.has_group(GROUP_MANAGER)
                           or user.has_group(GROUP_ADMIN))


# =========================================================================
#  The share
# =========================================================================
class PbHiringShare(models.Model):
    _name = 'pb.hiring.share'
    _description = 'What the hiring team shared about a candidate, and with whom'
    _order = 'granted_on desc, id desc'

    applicant_id = fields.Many2one('hr.applicant', string='Candidate', required=True,
                                   index=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Shared with', required=True,
                              index=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', ondelete='set null')
    parts = fields.Char(string='What they see', required=True, default=DEFAULT_PARTS,
                        help='Comma list of: ' + ', '.join(PART_KEYS))
    granted_by_id = fields.Many2one('res.users', string='Shared by', ondelete='set null')
    granted_on = fields.Datetime(string='Shared on', default=fields.Datetime.now)
    note = fields.Char(string='Note')
    company_id = fields.Many2one('res.company', related='applicant_id.company_id',
                                 store=True, index=True, readonly=True)
    active = fields.Boolean(default=True)

    _applicant_user_uniq = models.Constraint(
        'unique(applicant_id, user_id)',
        'A candidate is shared with a person once; change what they see instead.')

    def _part_set(self):
        self.ensure_one()
        return _split(self.parts)

    @api.model
    def parts_for(self, applicant, user=None):
        """The parts of one candidate this user may see.

        The hiring team sees everything (every part, plus `card`). Anybody
        who may read the candidate's ROLE (the person who asked for it, who
        they would report to, the department head on an ordinary role) gets
        `card` — name, stage, interview dates — and nothing more without a
        share. A share adds its parts (and `card`)."""
        user = user or self.env.user
        app = self.env['hr.applicant'].sudo().with_context(active_test=False).browse(
            as_id(applicant)).exists()
        if not app or not user:
            return set()
        if _is_hiring_user(user):
            return set(PART_KEYS) | {'card'}
        out = set()
        req = app.pb_requisition_id
        if req:
            try:
                self.env['pb.hiring.requisition'].with_user(user).browse(req.id) \
                    .check_access('read')
                out.add('card')
            except AccessError:
                pass
        for share in self.sudo().search([('applicant_id', '=', app.id),
                                         ('user_id', '=', user.id)]):
            out |= share._part_set() | {'card'}
        return out

    @api.model
    def _grant(self, app, user, parts, employee=None, by=None, note='', keep=False):
        """Create or update ONE share. `keep`: an existing share wins (a role
        default never overrides what a recruiter chose). Returns the share
        and what it was before ({'parts': csv or None})."""
        Share = self.sudo().with_context(active_test=False)
        share = Share.search([('applicant_id', '=', app.id), ('user_id', '=', user.id)], limit=1)
        before = {'applicant_id': app.id, 'user_id': user.id,
                  'parts': share.parts if share and share.active else None}
        csv = _csv(parts)
        if share and keep and share.active:
            return share, before
        if not csv:
            if share and share.active:
                share.write({'active': False})
            return share, before
        vals = {'parts': csv, 'active': True, 'granted_on': fields.Datetime.now(),
                'granted_by_id': by.id if by else False, 'note': (note or '')[:200]}
        if employee:
            vals['employee_id'] = employee.id
        if share:
            share.write(vals)
        else:
            vals.update({'applicant_id': app.id, 'user_id': user.id})
            share = Share.create(vals)
        return share, before


# =========================================================================
#  The private recruiter note
# =========================================================================
class PbHiringNote(models.Model):
    _name = 'pb.hiring.note'
    _description = 'A private recruiter note on a candidate'
    _order = 'create_date desc, id desc'

    applicant_id = fields.Many2one('hr.applicant', string='Candidate', required=True,
                                   index=True, ondelete='cascade')
    author_id = fields.Many2one('res.users', string='Written by', required=True,
                                default=lambda self: self.env.user, index=True,
                                ondelete='restrict')
    body = fields.Html(string='Note', sanitize=True)
    shared_user_ids = fields.Many2many('res.users', 'pb_hiring_note_user_rel', 'note_id',
                                       'user_id', string='Shared with')
    company_id = fields.Many2one('res.company', related='applicant_id.company_id',
                                 store=True, index=True, readonly=True)

    @api.depends('create_date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Note by %s', rec.author_id.name or '')


# =========================================================================
#  Retention per market
# =========================================================================
class PbHiringRetentionRule(models.Model):
    """How long one market keeps an application.

    ITS OWN TABLE, not columns on `pb.hiring.country.rule` as the handover
    planned: that table's `recruiter_id` is REQUIRED (it routes an agreed role
    to a real desk), so a market could not have a retention period without
    naming a recruiter first. The company's own number
    (`res.company.pb_retention_months`, P2) stays the fallback."""
    _name = 'pb.hiring.retention.rule'
    _description = 'How long a market keeps applications'
    _order = 'company_id, country_id'

    company_id = fields.Many2one('res.company', string='Company', required=True, index=True,
                                 default=lambda self: self.env.company)
    country_id = fields.Many2one('res.country', string='Market', required=True, index=True)
    months = fields.Integer(string='Months we keep an application', default=12, required=True)
    purge_mode = fields.Selection(PURGE_MODES, string='Afterwards', default='anonymise',
                                  required=True)
    note = fields.Char(string='Why (law or policy)')

    _company_country_uniq = models.Constraint(
        'unique(company_id, country_id)', 'That market already has a retention rule.')

    @api.constrains('months')
    def _check_months(self):
        for rec in self:
            if not 1 <= (rec.months or 0) <= 120:
                raise UserError(_("Keep an application for between 1 and 120 months."))

    @api.model
    def _for(self, company, country=None):
        company_id = as_id(company)
        country_id = as_id(country)
        if not company_id or not country_id:
            return self.browse()
        return self.sudo().search([('company_id', '=', company_id),
                                   ('country_id', '=', country_id)], limit=1)

    @api.model
    def _months_for(self, company, country=None):
        rule = self._for(company, country)
        if rule:
            return rule.months
        company = self.env['res.company'].sudo().browse(as_id(company))
        return (company.pb_retention_months if company else 0) or 12

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._touch_applicants()
        return recs

    def write(self, vals):
        before = [(r.company_id.id, r.country_id.id) for r in self]
        res = super().write(vals)
        self._touch_applicants(extra=before)
        return res

    def unlink(self):
        keys = [(r.company_id.id, r.country_id.id) for r in self]
        res = super().unlink()
        self.env['hr.applicant']._pb_recompute_retention(keys)
        return res

    def _touch_applicants(self, extra=None):
        keys = [(r.company_id.id, r.country_id.id) for r in self] + list(extra or [])
        self.env['hr.applicant']._pb_recompute_retention(keys)


# =========================================================================
#  The role: who sees what by default
# =========================================================================
class HiringRequestPrivacy(models.Model):
    _inherit = 'pb.hiring.requisition'

    default_share_parts = fields.Char(
        string='What the hiring manager sees by default', default=DEFAULT_PARTS,
        help='Applied to each new candidate on this role. Changing it never '
             'changes what was already shared.')
    default_share_with = fields.Selection(
        SHARE_WITH, string='Shared by default with', default='hiring_manager')

    def _pb_manager_targets(self):
        """[(user, employee, label)] — the hiring manager (who asked / was
        asked for the request) and the reporting manager. Internal logins
        first; a portal-only manager is returned with their portal login."""
        self.ensure_one()
        rec = self.sudo()
        out, seen = [], set()

        def add(emp, user, label):
            user = user or _user_of(emp)
            if user and user.id not in seen:
                seen.add(user.id)
                out.append((user, emp or self.env['hr.employee'], label))

        add(rec.requested_by_id, rec.requested_by_user_id, _('Hiring manager'))
        if 'asked_employee_id' in rec._fields:
            add(rec.asked_employee_id, rec.asked_user_id, _('Hiring manager'))
        add(rec.reporting_manager_id, None, _('Reporting manager'))
        return out

    def _pb_panel_targets(self):
        """[(user, employee, label)] for everybody on this role's panels and
        every interview step owner."""
        self.ensure_one()
        out, seen = [], set()
        ivs = self.env['pb.hiring.interview'].sudo().search(
            [('requisition_id', '=', self.id), ('state', 'not in', ('cancelled', 'rescheduled'))],
            order='round_no, start')
        for iv in ivs:
            for emp in iv.panel_employee_ids:
                user = _user_of(emp)
                if user and user.id not in seen:
                    seen.add(user.id)
                    out.append((user, emp, _('Panel · Round %s', iv.round_no or 1)))
        for step in self.sudo().step_ids:
            user = step.owner_id
            if user and user.id not in seen:
                seen.add(user.id)
                emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
                out.append((user, emp, _('Panel · %s', step.name or _('interview'))))
        return out


# =========================================================================
#  The candidate
# =========================================================================
class HiringApplicantPrivacy(models.Model):
    _inherit = 'hr.applicant'

    pb_origin_applicant_id = fields.Many2one(
        'hr.applicant', string='Added from the Resume bank', copy=False,
        ondelete='set null', index='btree_not_null')
    pb_share_ids = fields.One2many('pb.hiring.share', 'applicant_id', string='Shared with')
    pb_note_ids = fields.One2many('pb.hiring.note', 'applicant_id', string='Recruiter notes')
    pb_retention_until = fields.Date(
        string='Kept until', compute='_compute_pb_retention_until', store=True,
        index=True, copy=False,
        help='The consent they gave (or the day they applied) plus the months '
             'their market keeps an application.')
    pb_retention_extended_by_id = fields.Many2one('res.users', string='Kept longer by',
                                                  copy=False, ondelete='set null')
    pb_retention_extended_on = fields.Datetime(string='Kept longer on', copy=False)
    pb_anonymised_on = fields.Datetime(string='Anonymised on', copy=False, readonly=True)

    # ------------------------------------------------------------ retention
    def _pb_country(self):
        self.ensure_one()
        app = self.sudo()
        return (app.pb_country_id or app.pb_requisition_id.country_id
                or app.company_id.country_id)

    @api.depends('pb_consent_on', 'create_date', 'pb_country_id', 'company_id',
                 'pb_requisition_id.country_id', 'pb_retention_extended_on',
                 'company_id.pb_retention_months')
    def _compute_pb_retention_until(self):
        Rule = self.env['pb.hiring.retention.rule'].sudo()
        cache = {}
        for app in self:
            start = app.pb_consent_on or app.create_date
            if not start:
                app.pb_retention_until = False
                continue
            country = app._pb_country()
            key = (app.company_id.id, country.id)
            if key not in cache:
                cache[key] = Rule._months_for(app.company_id, country)
            months = cache[key]
            until = fields.Datetime.to_datetime(start).date() + relativedelta(months=months)
            if app.pb_retention_extended_on:
                until += relativedelta(months=months)
            app.pb_retention_until = until

    @api.model
    def _pb_recompute_retention(self, keys):
        """A market's rule changed: every candidate it covers gets a new date."""
        companies = {k[0] for k in keys if k and k[0]}
        if not companies:
            return 0
        apps = self.sudo().with_context(active_test=False).search(
            [('company_id', 'in', list(companies)), ('pb_anonymised_on', '=', False)])
        if not apps:
            return 0
        self.env.add_to_compute(self._fields['pb_retention_until'], apps)
        apps._recompute_recordset(['pb_retention_until'])
        return len(apps)

    def _pb_retention_protected(self):
        """'' when the clean-up may take this person, else why not.

        Hired people, anyone still in a working column, anyone with a live
        offer or an employee record are never anonymised by this job."""
        self.ensure_one()
        app = self.sudo()
        stage = app.stage_id
        family = stage.pb_family or ('closed' if not app.active else 'open')
        if not app.active and family == 'open':
            family = 'closed'
        if app.employee_id or app.application_status == 'hired' \
                or stage.pb_key in ('joined', 'post_offer') or family == 'done':
            return 'hired'
        if family != 'closed':
            return 'open'
        offers = self.env['pb.hiring.offer'].sudo().search_count(
            [('applicant_id', '=', app.id), ('state', 'in', list(OFFER_LIVE))])
        if offers:
            return 'offer'
        return ''

    def _pb_anonymise(self):
        """Take a person out, keep the numbers.

        Name becomes "Candidate (removed)"; email, phone, LinkedIn, portfolio,
        location, answers, notes and expected pay are blanked; files, private
        notes, shares, the chatter and the opinions' words go. The stage
        history and the counts stay, so Hiring numbers still add up."""
        self.ensure_one()
        app = self.sudo().with_context(active_test=False, tracking_disable=True,
                                       mail_notrack=True, mail_create_nolog=True)
        partner = app.partner_id
        self.env['ir.attachment'].sudo().search(
            [('res_model', '=', 'hr.applicant'), ('res_id', '=', app.id)]).unlink()
        app.pb_note_ids.sudo().unlink()
        app.with_context(active_test=False).pb_share_ids.sudo().unlink()
        self.env['mail.message'].sudo().search(
            [('model', '=', 'hr.applicant'), ('res_id', '=', app.id)]).unlink()
        self.env['pb.hiring.referral'].sudo().search([('applicant_id', '=', app.id)]).write({
            'candidate_name': REMOVED, 'candidate_email': False,
            'candidate_phone': False, 'note': False})
        self.env['pb.hiring.feedback'].sudo().search([('applicant_id', '=', app.id)]).write(
            {'notes': False})
        self.env['pb.hiring.interview'].sudo().search([('applicant_id', '=', app.id)]).write(
            {'debrief_notes': False, 'no_show_note': False, 'cancel_note': False})
        vals = {
            'partner_id': False, 'partner_name': REMOVED, 'email_from': False,
            'partner_phone': False, 'linkedin_profile': False, 'pb_linkedin': False,
            'pb_portfolio': False, 'pb_location': False, 'pb_nationality': False,
            'pb_motivation': False, 'pb_form_answers': {}, 'pb_stage_reason': False,
            'applicant_notes': False, 'categ_ids': [(5, 0, 0)],
            'talent_pool_ids': [(5, 0, 0)], 'pb_possible_duplicate_id': False,
            'pb_same_person_id': False, 'pb_anonymised_on': fields.Datetime.now(),
        }
        for fname in ('salary_expected', 'salary_proposed', 'salary_expected_extra',
                      'salary_proposed_extra'):
            if fname in app._fields:
                vals[fname] = 0.0 if app._fields[fname].type in ('float', 'monetary') else False
        if 'applicant_skill_ids' in app._fields:
            app.applicant_skill_ids.sudo().unlink()
        app.write(vals)
        self.sudo().with_context(active_test=False).search(
            [('pb_possible_duplicate_id', '=', app.id)]).write({'pb_possible_duplicate_id': False})
        self.sudo().with_context(active_test=False).search(
            [('pb_same_person_id', '=', app.id)]).write({'pb_same_person_id': False})
        if partner:
            leg(self.env, 'the contact behind candidate %s' % app.id,
                lambda: self._pb_forget_partner(partner))
        return True

    @api.model
    def _pb_forget_partner(self, partner):
        """The candidate's contact goes too — unless somebody else uses it (a
        login, an employee, another application)."""
        partner = partner.sudo().with_context(active_test=False)
        if partner.user_ids:
            return False
        if self.env['hr.employee'].sudo().with_context(active_test=False).search_count(
                [('work_contact_id', '=', partner.id)]):
            return False
        if self.sudo().with_context(active_test=False).search_count([('partner_id', '=', partner.id)]):
            return False
        partner.write({'name': REMOVED, 'email': False, 'phone': False, 'active': False})
        return True

    @api.model
    def _pb_retention_leg(self, companies=None, limit=2000):
        """The clean-up itself: every candidate past their date that it may
        take, one savepoint each. Returns honest counts."""
        today = fields.Date.context_today(self)
        dom = [('pb_retention_until', '<', today), ('pb_anonymised_on', '=', False)]
        if companies:
            dom.append(('company_id', 'in', companies.ids))
        apps = self.sudo().with_context(active_test=False).search(dom, order='pb_retention_until, id',
                                                                    limit=limit)
        counts = {'anonymised': 0, 'kept': 0, 'failed': 0}
        for app in apps:
            if app._pb_retention_protected():
                counts['kept'] += 1
                continue
            if leg(self.env, 'anonymising candidate %s' % app.id, app._pb_anonymise):
                counts['anonymised'] += 1
            else:
                counts['failed'] += 1
        return counts

    # ------------------------------------------------- the role's defaults
    @api.model_create_multi
    def create(self, vals_list):
        apps = super().create(vals_list)
        if not self.env.context.get('pb_no_default_share'):
            for app in apps:
                if app.sudo().pb_requisition_id:
                    leg(self.env, 'the default shares on candidate %s' % app.id,
                        app._pb_apply_default_shares)
        return apps

    def _pb_apply_default_shares(self, panel_only=False, interview=None):
        """The role's "What the hiring manager sees by default", applied once
        to a new candidate. Never overrides a share somebody already made."""
        self.ensure_one()
        app = self.sudo()
        req = app.pb_requisition_id
        mode = req.default_share_with or 'hiring_manager'
        parts = _csv(req.default_share_parts if req.default_share_parts is not False
                     else DEFAULT_PARTS)
        if not req or mode == 'nobody' or not parts:
            return 0
        targets = []
        if not panel_only:
            targets += req._pb_manager_targets()
        if mode == 'hiring_manager_and_panel':
            if interview is not None:
                for emp in interview.sudo().panel_employee_ids:
                    user = _user_of(emp)
                    if user:
                        targets.append((user, emp, ''))
            elif not panel_only:
                targets += req._pb_panel_targets()
        Share = self.env['pb.hiring.share']
        made = 0
        for user, emp, _label in targets:
            if _is_hiring_user(user):
                continue
            share, before = Share._grant(app, user, parts, employee=emp or None,
                                         note=_("the role's default"), keep=True)
            if before['parts'] is None and share and share.active:
                made += 1
        return made


class HiringInterviewPrivacy(models.Model):
    _inherit = 'pb.hiring.interview'

    @api.model_create_multi
    def create(self, vals_list):
        ivs = super().create(vals_list)
        for iv in ivs:
            app = iv.sudo().applicant_id
            req = iv.sudo().requisition_id
            if app and req and req.default_share_with == 'hiring_manager_and_panel':
                leg(self.env, 'the panel default shares on interview %s' % iv.id,
                    lambda app=app, iv=iv: app._pb_apply_default_shares(panel_only=True,
                                                                          interview=iv))
        return ivs


class HiringOfferPrivacy(models.Model):
    """G-41: the offer's money carries field `groups`, so the native screens
    drop it for anybody outside the hiring team. The payloads mask it as
    well (sudo reads bypass `groups`)."""
    _inherit = 'pb.hiring.offer'

    monthly_total = fields.Monetary(groups='pb_hiring.group_hiring_user')
    annual_total = fields.Monetary(groups='pb_hiring.group_hiring_user')

    def _chain_revision_values(self):
        # The route re-reads the numbers when the LAST rung is given, as the
        # person giving it — a Head of HR or a Finance seat without the hiring
        # group. The stamp is the system's business, so it reads as the system.
        return super(HiringOfferPrivacy, self.sudo())._chain_revision_values()


class HiringOfferLinePrivacy(models.Model):
    _inherit = 'pb.hiring.offer.line'

    amount = fields.Monetary(groups='pb_hiring.group_hiring_user')
    annual_amount = fields.Monetary(groups='pb_hiring.group_hiring_user')


class HiringAutomationRetention(models.AbstractModel):
    _inherit = 'pb.hiring.automation'

    @api.model
    def run_now(self):
        counts = super().run_now()
        counts['retention'] = 0
        if flag(self.env, P_RETENTION_ENABLED):
            try:
                res = self.env['hr.applicant']._pb_retention_leg()
                counts['retention'] = res.get('anonymised', 0)
            except Exception:           # noqa: BLE001 — a job never raises
                _logger.warning('pb_hiring: the retention clean-up failed', exc_info=True)
        return counts

    @api.model
    def describe(self, counts):
        text = super().describe(counts)
        n = (counts or {}).get('retention') or 0
        if n:
            text = '%s %s' % (text, _("%s old applications were anonymised.", n)
                              if n != 1 else _("1 old application was anonymised."))
        return text
