# -*- coding: utf-8 -*-
"""RECRUIT P8 — the automations the talent lead owns (G-48, G-50).

  * `pb.hiring.automation.rule` — "When <something happens> (for these
    departments / countries), <do this> <right away / after N hours>". Rows
    per company, edited in Hiring set-up → Automations as sentences.
  * `pb.hiring.automation.run` — every time a rule ran, was queued, was
    skipped and why, or failed. The run log is this table.
  * THE BUILT-INS are not rows: they are the emails and to-dos the code has
    always sent (application received, invitations, reminders, the opinion
    chase, the papers, the offer, the week-before, joining…). They are listed
    beside the rules as sentences (`BUILTINS`), each with the switch it maps
    to (`pb_hiring.*`, global like every hiring switch) or "always on" with
    the reason. A switch here is the SAME parameter the code reads — the
    list never pretends.

THE DISPATCHER `_fire(event, applicant, record, stage)` is called at every
state change the phases left (one-line hooks below, each inside `leg`):
an automation can NEVER stop or undo the move that triggered it (RC-D1 and
§4 of the handover). A delayed action is queued (`due_at`) and run by the
ten-minute job; "has waited N days" is checked by the night job. Depth is
capped: a rule that moves a candidate can trigger at most one more rule.

The P5 Calendly rule IS the first seeded row ("When a candidate enters
Recruiter review, send Let's chat to the candidate, right away"): its email
goes through P5's own sender (`_pb_send_scheduling_link`, the scheduling
link and its warnings) and its toast words are P5's, word for word. The old
parameter `pb_hiring.phone_auto_mail` stays a master switch over that row.
"""

import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .comms_i18n_p8 import TOKEN_WORDS

from .hiring_common import (
    P_CLOSURE_MAIL, P_LEAD_LATE_DAYS, P_NOTIFY_MAIL, P_OFFER_MAIL,
    P_PHONE_AUTO_MAIL, P_REFERRAL_ANNOUNCE, P_REFERRAL_MAIL, P_REMINDER_CAP,
    P_REMINDERS, P_WEEK_BEFORE_DAYS, as_id, counted, flag, leg, number,
)

_logger = logging.getLogger(__name__)
#: Language names on the hiring team's (English) screens.
LANG_EN = {'en_US': 'English', 'vi_VN': 'Vietnamese', 'id_ID': 'Bahasa Indonesia'}

_TODO = 'mail.mail_activity_data_todo'

EVENTS = [
    ('applied', 'Somebody applies'),
    ('stage_entered', 'A candidate enters a stage'),
    ('stage_waiting', 'A candidate has waited in a stage'),
    ('interview_scheduled', 'An interview is arranged'),
    ('interview_done', 'An interview is marked done'),
    ('interview_no_show', 'Nobody came to an interview'),
    ('opinions_all_in', 'Every opinion on an interview is in'),
    ('documents_complete', 'All the papers are in'),
    ('check_started', 'A background check starts'),
    ('offer_sent', 'An offer is sent'),
    ('offer_accepted', 'An offer is accepted'),
    ('offer_declined', 'An offer is turned down'),
    ('offer_signed', 'An offer is signed'),
    ('joined', 'Somebody joins'),
    ('did_not_join', 'Somebody who signed will not join'),
    ('request_sent_in', 'A hiring request is sent in'),
    ('request_agreed', 'A hiring request is agreed'),
    ('referral_received', 'A colleague refers somebody'),
    ('agency_submitted', 'An agency puts somebody forward'),
]
#: The lower-case clause after "When" in a sentence.
EVENT_CLAUSE = {
    'applied': 'somebody applies', 'stage_entered': 'a candidate enters %(stage)s',
    'stage_waiting': 'a candidate has waited %(days)s in %(stage)s',
    'interview_scheduled': 'an interview is arranged',
    'interview_done': 'an interview is marked done',
    'interview_no_show': 'nobody came to an interview',
    'opinions_all_in': 'every opinion on an interview is in',
    'documents_complete': 'all the papers are in',
    'check_started': 'a background check starts', 'offer_sent': 'an offer is sent',
    'offer_accepted': 'an offer is accepted', 'offer_declined': 'an offer is turned down',
    'offer_signed': 'an offer is signed', 'joined': 'somebody joins',
    'did_not_join': 'somebody who signed will not join',
    'request_sent_in': 'a hiring request is sent in',
    'request_agreed': 'a hiring request is agreed',
    'referral_received': 'a colleague refers somebody',
    'agency_submitted': 'an agency puts somebody forward',
}
STAGE_EVENTS = ('stage_entered', 'stage_waiting')
#: Events about a ROLE, with no candidate: nothing can go to "the candidate".
ROLE_EVENTS = ('request_sent_in', 'request_agreed')

ACTIONS = [
    ('send_email', 'Send an email'),
    ('todo', 'Give somebody a to-do'),
    ('move_stage', 'Move the candidate'),
    ('tag', 'Tag the candidate'),
]
RECIPIENTS = [
    ('candidate', 'The candidate'),
    ('recruiter', 'The recruiter'),
    ('hiring_manager', 'The hiring manager'),
    ('talent_lead', 'The talent lead'),
    ('custom', 'These email addresses'),
]
RUN_STATES = [
    ('queued', 'Waiting'),
    ('done', 'Done'),
    ('skipped', 'Skipped'),
    ('failed', 'Did not work'),
]
#: How deep one rule may set off another (a rule that moves a candidate
#: fires "enters a stage" once more, and no further).
MAX_DEPTH = 2

# -------------------------------------------------------------- built-ins
#: (key, sentence, switch parameter or None, default, email key, why locked)
BUILTINS = [
    ('received', 'When somebody applies on the careers page, send “Application received” '
                 'to the candidate, right away.', 'pb_hiring.auto_received', '1', 'received', ''),
    ('invite', 'When an interview is arranged, send the invitation with a calendar file to '
               'the candidate, the panel and the recruiter, right away.', None, '1',
     'interview_invite', 'An interview nobody is told about does not happen, so this one is '
                         'always on.'),
    ('reminders', 'The day before an interview and again half an hour before, remind the '
                  'candidate, the panel and the recruiter.', P_REMINDERS, '1',
     'interview_tomorrow', ''),
    ('opinions', 'When an interview ends, ask each panellist for their scorecard, remind them '
                 'every day while it is late, and tell the talent lead at %(lead)s.',
     'pb_hiring.auto_chase', '1', '', ''),
    ('papers_in', 'When all the papers are in, give the recruiter a to-do on the offer.', None,
     '1', '', 'It only puts the next step on the recruiter’s list; nothing goes to anybody '
              'outside.'),
    ('papers_remind', 'While papers are missing, remind the candidate once a day; when the '
                      'date passes, give the recruiter a to-do and tell the talent lead.',
     'pb_hiring.auto_doc_remind', '1', 'docreq_remind', ''),
    ('check', 'When a background check starts, give the recruiter a to-do.',
     'pb_hiring.auto_check_todo', '1', '', ''),
    ('offer', 'When an offer is sent, email it to the candidate with the letter attached.',
     P_OFFER_MAIL, '1', 'offer', ''),
    ('finalists', 'When an offer is signed and the role has nobody else to find, close the '
                  'other finalists as Interview reject and send them “Not this time”.',
     'pb_hiring.auto_close_finalists', '1', 'interview_reject', ''),
    ('week_before', '%(days)s before somebody joins, ask the recruiter, the hiring manager and '
                    'HR whether it is still on.', 'pb_hiring.auto_week_before', '1', '', ''),
    ('joined', 'When somebody joins, tell the hiring manager and the people who get the new '
               'joiner ready.', P_CLOSURE_MAIL, '1', '', ''),
    ('assigned', 'When a role gets its recruiter, tell the recruiter and their manager.',
     P_NOTIFY_MAIL, '1', '', ''),
    ('referral', 'When a colleague refers somebody, tell the recruiter.', P_REFERRAL_MAIL, '1',
     '', ''),
    ('announce', 'When a role opens to referrals, tell every colleague with a login by email.',
     P_REFERRAL_ANNOUNCE, '0', '', ''),
    ('shared', 'When a recruiter shares a candidate with somebody, email them that they were '
               'given access.', 'pb_hiring.auto_share_mail', '1', '', ''),
    ('agency', 'When an agency puts somebody forward, give the recruiter a to-do for a first '
               'look.', None, '1', '', 'It only puts the candidate on the recruiter’s list.'),
]
BUILTIN_SWITCHES = {k: (p, d) for k, _s, p, d, _e, _w in BUILTINS if p}

#: The editable rows every company starts with (handover §2.3).
SEEDS = [
    {'seed_key': 'calendly', 'event': 'stage_entered', 'stage': 'phone',
     'action': 'send_email', 'recipient': 'candidate', 'template_key': 'phone',
     'once_per_candidate': False, 'active': True, 'sequence': 10},
    {'seed_key': 'assignment', 'event': 'stage_entered', 'stage': 'assignment',
     'action': 'send_email', 'recipient': 'candidate', 'template_key': 'assignment',
     'active': False, 'sequence': 20},
    {'seed_key': 'first_look', 'event': 'stage_waiting', 'stage': 'screening', 'days': 7,
     'action': 'todo', 'recipient': 'recruiter', 'todo_text': 'Give them a first look',
     'active': False, 'sequence': 30},
    {'seed_key': 'buddy', 'event': 'offer_accepted', 'action': 'todo',
     'recipient': 'hiring_manager', 'todo_text': 'Name a buddy', 'active': False,
     'sequence': 40},
]
SEED_NOTES = {
    'calendly': 'Uses the recruiter’s own scheduling link (Who does what).',
    'assignment': 'Off to begin with: the assignment email needs the tasks and a date, which '
                  'only a person can fill. Switched on, it goes when those are written into '
                  'the email itself.',
    'first_look': '',
    'buddy': 'Off to begin with: the "Before they join" list already asks the hiring manager '
             'for a buddy when the offer is signed.',
}


def _days_words(days):
    return counted(days, _('1 day'), _('%s days') % days)


class PbHiringAutomationRule(models.Model):
    _name = 'pb.hiring.automation.rule'
    _description = 'Hiring automation'
    _order = 'sequence, id'

    company_id = fields.Many2one('res.company', string='Company', required=True, index=True,
                                 default=lambda self: self.env.company)
    sequence = fields.Integer(default=50)
    active = fields.Boolean(default=True)
    seed_key = fields.Char(string='Seeded as', readonly=True, copy=False,
                           help='The product row this one started from.')
    event = fields.Selection(EVENTS, string='When', required=True)
    stage_id = fields.Many2one('hr.recruitment.stage', string='Stage', ondelete='cascade',
                               domain=[('pb_key', '!=', False)])
    days = fields.Integer(string='Days waiting', default=3)
    department_ids = fields.Many2many('hr.department', 'pb_hiring_auto_dept_rel', 'rule_id',
                                      'department_id', string='Only for these departments')
    country_ids = fields.Many2many('res.country', 'pb_hiring_auto_country_rel', 'rule_id',
                                   'country_id', string='Only for these countries')
    action = fields.Selection(ACTIONS, string='Then', required=True, default='send_email')
    template_key = fields.Char(string='Candidate email',
                               help='The key of a candidate email (Emails and languages).')
    recipient = fields.Selection(RECIPIENTS, string='Who', default='candidate')
    custom_emails = fields.Char(string='Email addresses')
    message_subject = fields.Char(string='Email subject (to colleagues)')
    message_body = fields.Text(string='Email words (to colleagues)')
    todo_text = fields.Char(string='To-do')
    target_stage_id = fields.Many2one('hr.recruitment.stage', string='Move to',
                                      ondelete='cascade')
    tag_id = fields.Many2one('hr.applicant.category', string='Tag', ondelete='cascade')
    delay_hours = fields.Integer(string='After (hours)', default=0)
    once_per_candidate = fields.Boolean(string='Once per candidate', default=True)
    run_count = fields.Integer(string='Times it ran', readonly=True, copy=False)
    last_run_at = fields.Datetime(string='Last ran', readonly=True, copy=False)
    name = fields.Char(string='Rule', compute='_compute_name')

    @api.depends('event', 'stage_id', 'days', 'action', 'template_key', 'recipient',
                 'todo_text', 'target_stage_id', 'tag_id', 'delay_hours',
                 'department_ids', 'country_ids', 'custom_emails')
    def _compute_name(self):
        for rec in self:
            rec.name = rec._sentence()

    # ------------------------------------------------------------ words
    def _email_name(self):
        self.ensure_one()
        if not self.template_key:
            return ''
        tpl = self.env['pb.hiring']._pb_template(self.template_key, self.company_id or self.env.company)
        return (tpl.with_context(lang='en_US').name if tpl else '') or self.template_key

    def _who_words(self):
        return {'candidate': _('the candidate'), 'recruiter': _('the recruiter'),
                'hiring_manager': _('the hiring manager'), 'talent_lead': _('the talent lead'),
                'custom': self.custom_emails or _('these addresses')}.get(self.recipient or '', '')

    def _sentence(self):
        self.ensure_one()
        stage = self.stage_id.name or _('a stage')
        when = EVENT_CLAUSE.get(self.event or '', '') % {
            'stage': stage, 'days': _days_words(max(1, self.days or 1))}
        scope = []
        if self.department_ids:
            scope.append(', '.join(self.department_ids.mapped('name')))
        if self.country_ids:
            scope.append(', '.join(self.country_ids.mapped('name')))
        if scope:
            when += ' ' + _('(only %s)', ' · '.join(scope))
        who = self._who_words()
        if self.action == 'send_email' and self.recipient == 'candidate':
            then = _('send “%(e)s” to the candidate', e=self._email_name() or _('an email'))
        elif self.action == 'send_email':
            then = _('email %s', who)
        elif self.action == 'todo':
            then = _('give %(who)s a to-do: “%(t)s”', who=who, t=self.todo_text or '…')
        elif self.action == 'move_stage':
            then = _('move them to %s', self.target_stage_id.name or '…')
        elif self.action == 'tag':
            then = _('tag them “%s”', self.tag_id.name or '…')
        else:
            then = '…'
        hours = self.delay_hours or 0
        if not hours:
            after = _('right away')
        elif hours % 24 == 0:
            after = _('after %s', _days_words(hours // 24))
        else:
            after = counted(hours, _('after 1 hour'), _('after %s hours') % hours)
        return _('When %(when)s, %(then)s, %(after)s.', when=when, then=then, after=after)

    # ------------------------------------------------------- validation
    def _check_complete(self):
        """A rule that cannot work is never saved, and says why."""
        for rec in self:
            if rec.event in STAGE_EVENTS and not rec.stage_id:
                raise UserError(_("Pick the stage the rule is about."))
            if rec.event == 'stage_waiting' and (rec.days or 0) < 1:
                raise UserError(_("Say how many days they have waited — at least 1."))
            if rec.action in ('send_email', 'todo') and not rec.recipient:
                raise UserError(_("Say who it is for. A rule with nobody to tell does nothing."))
            if rec.event in ROLE_EVENTS and (rec.recipient == 'candidate'
                                             or rec.action in ('move_stage', 'tag')):
                raise UserError(_("A hiring request has no candidate yet: send an email or "
                                  "a to-do to somebody in the company instead."))
            if rec.action == 'send_email' and rec.recipient == 'candidate' and not rec.template_key:
                raise UserError(_("Pick which candidate email goes."))
            if rec.action == 'send_email' and rec.recipient == 'custom':
                emails = [e.strip() for e in (rec.custom_emails or '').split(',') if e.strip()]
                if not emails or any('@' not in e for e in emails):
                    raise UserError(_("Type the email addresses, separated by commas."))
            if rec.action == 'todo':
                if rec.recipient in ('candidate', 'custom'):
                    raise UserError(_("A to-do goes to somebody with a login: the recruiter, "
                                      "the hiring manager or the talent lead."))
                if not (rec.todo_text or '').strip():
                    raise UserError(_("Write the to-do, in a few words."))
            if rec.action == 'move_stage':
                if not rec.target_stage_id:
                    raise UserError(_("Pick the stage to move them to."))
                if rec.target_stage_id.pb_key == 'joined':
                    raise UserError(_("Joined is set when somebody confirms the person "
                                      "started, never by a rule."))
                if rec.event == 'stage_entered' and rec.target_stage_id == rec.stage_id:
                    raise UserError(_("That would move them to the stage they just entered."))
            if rec.action == 'tag' and not rec.tag_id:
                raise UserError(_("Pick or type the tag."))
            if (rec.delay_hours or 0) < 0 or (rec.delay_hours or 0) > 24 * 60:
                raise UserError(_("Wait between 0 hours and 60 days."))

    # ----------------------------------------------------- who and where
    def _matches(self, app, req):
        self.ensure_one()
        if self.department_ids:
            dept = (req.department_id if req else False) or (app.department_id if app else False)
            if not dept or dept not in self.department_ids:
                return False
        if self.country_ids:
            country = (req.country_id if req else False) or (
                (req.company_id if req else (app.company_id if app else False)).partner_id.country_id
                if (req or app) else False)
            if not country or country not in self.country_ids:
                return False
        return True

    def _people(self, app, req):
        """[(user or None, email, name)] for the recipient."""
        self.ensure_one()
        req = req.sudo() if req else req
        out = []
        if self.recipient == 'recruiter':
            user = (req.recruiter_id if req else False) or (app.user_id if app else False)
            if user:
                out.append((user, user.email or '', user.name or ''))
        elif self.recipient == 'hiring_manager' and req:
            for user, emp, _label in req._pb_manager_targets()[:1]:
                out.append((user if not user.share else None,
                            (user.email or (emp.work_email if emp else '') or ''),
                            user.name or (emp.name if emp else '')))
        elif self.recipient == 'talent_lead' and req:
            for user in req._talent_leads():
                out.append((user, user.email or '', user.name or ''))
        elif self.recipient == 'custom':
            for email in (self.custom_emails or '').split(','):
                if email.strip():
                    out.append((None, email.strip(), email.strip()))
        return out

    # ------------------------------------------------------------ doing
    def _do(self, app, req, record=None, dry=False):
        """Run the action once. Returns {status: done|skipped|failed, text,
        note?, mail_sent?}. `dry`: describe only, write nothing."""
        self.ensure_one()
        Hiring = self.env['pb.hiring']
        name = (app.partner_name or _('the candidate')) if app else (req.title if req else '')
        if self.action == 'send_email' and self.recipient == 'candidate':
            if self.template_key == 'phone':
                return self._do_phone(app, dry)
            res = Hiring._mail_candidate(self.template_key, app, values=self._auto_values(app),
                                         dry=dry)
            ename = self._email_name()
            if res['status'] in ('sent', 'dry'):
                lang = LANG_EN.get(res['lang'], res['lang'])
                if dry:
                    text = _('Would send “%(e)s” to %(who)s in %(l)s.', e=ename, who=name, l=lang)
                    if res.get('fell_back'):
                        text += ' ' + _('(No %s version yet, so English.)',
                                        LANG_EN.get(res.get('wanted'), res.get('wanted')))
                    if not app.email_from:
                        return {'status': 'skipped', 'text': _(
                            'Would not send “%(e)s”: %(who)s has no email address.',
                            e=ename, who=name)}
                    if not flag(self.env, 'pb_hiring.candidate_mail'):
                        return {'status': 'skipped', 'text': _(
                            'Would not send “%s”: candidate emails are switched off.', ename)}
                    return {'status': 'done', 'text': text}
                return {'status': 'done', 'text': _('Sent “%(e)s” to %(who)s in %(l)s.',
                                                    e=ename, who=name, l=lang),
                        'mail_sent': 1, 'email': ename}
            why = {
                'mail_off': _('candidate emails are switched off'),
                'no_email': _('there is no email address for them'),
                'no_template': _('the email is not set up for this company'),
                'missing': _('it needs details only a person can fill: %s',
                             ', '.join(TOKEN_WORDS.get(m, m) for m in res.get('missing') or [])),
            }.get(res['status'], res['status'])
            return {'status': 'skipped' if res['status'] in ('mail_off', 'no_email') else 'failed',
                    'text': _('“%(e)s” did not go to %(who)s: %(why)s.', e=ename, who=name, why=why),
                    'email': ename, 'why': why}
        if self.action == 'send_email':
            people = [p for p in self._people(app, req) if p[1]]
            if not people:
                return {'status': 'skipped', 'text': _('Nobody to email: %s has no email address.',
                                                      self._who_words())}
            if dry:
                return {'status': 'done', 'text': _('Would email %s.', ', '.join(p[2] for p in people))}
            for _user, email, _n in people:
                self._internal_mail(email, app, req)
            return {'status': 'done', 'text': _('Emailed %s.', ', '.join(p[2] for p in people)),
                    'mail_sent': len(people)}
        if self.action == 'todo':
            people = [p for p in self._people(app, req) if p[0]]
            if not people:
                return {'status': 'skipped', 'text': _('Nobody with a login to give the to-do: %s.',
                                                      self._who_words())}
            summary = '%s: %s' % (self.todo_text or '', name)
            if dry:
                return {'status': 'done', 'text': _('Would give %(who)s a to-do: “%(t)s”.',
                                                    who=', '.join(p[2] for p in people), t=summary)}
            target = app.sudo() if app else req.sudo()
            Activity = self.env['mail.activity'].sudo()
            for user, _e, _n in people:
                if Activity.search_count([('res_model', '=', target._name), ('res_id', '=', target.id),
                                          ('user_id', '=', user.id), ('summary', '=', summary)]):
                    continue
                target.activity_schedule(_TODO, summary=summary,
                                         note=_('From the automation: %s', self.name),
                                         user_id=user.id,
                                         date_deadline=fields.Date.context_today(self))
            return {'status': 'done', 'text': _('To-do for %(who)s: “%(t)s”.',
                                                who=', '.join(p[2] for p in people), t=summary),
                    'todo': 1}
        if self.action == 'move_stage':
            stage = self.target_stage_id
            if not app or not stage:
                return {'status': 'skipped', 'text': _('Nobody to move.')}
            if app.stage_id == stage:
                return {'status': 'skipped', 'text': _('%(who)s is already in %(s)s.',
                                                       who=name, s=stage.name)}
            if dry:
                return {'status': 'done', 'text': _('Would move %(who)s to %(s)s.', who=name,
                                                    s=stage.name)}
            depth = self.env.context.get('pb_automation_depth', 0) + 1
            app.sudo().with_context(pb_automation_depth=depth, just_moved=True).write(
                {'stage_id': stage.id})
            app.sudo().message_post(body=Markup('<p>%s</p>') % _(
                'Moved to %(s)s by the automation “%(r)s”.', s=stage.name, r=self.name),
                message_type='comment', subtype_xmlid='mail.mt_note')
            return {'status': 'done', 'text': _('Moved %(who)s to %(s)s.', who=name, s=stage.name)}
        if self.action == 'tag':
            if not app or not self.tag_id:
                return {'status': 'skipped', 'text': _('Nobody to tag.')}
            if self.tag_id in app.categ_ids:
                return {'status': 'skipped', 'text': _('%(who)s already has “%(t)s”.',
                                                       who=name, t=self.tag_id.name)}
            if dry:
                return {'status': 'done', 'text': _('Would tag %(who)s “%(t)s”.', who=name,
                                                    t=self.tag_id.name)}
            app.sudo().write({'categ_ids': [(4, self.tag_id.id)]})
            return {'status': 'done', 'text': _('Tagged %(who)s “%(t)s”.', who=name,
                                                t=self.tag_id.name)}
        return {'status': 'skipped', 'text': _('This rule has nothing to do.')}

    def _do_phone(self, app, dry):
        """The P5 rule: Let's chat with the recruiter's own scheduling link."""
        Hiring = self.env['pb.hiring']
        name = app.partner_name or _('the candidate')
        if dry:
            req = app.pb_requisition_id
            recruiter = req.recruiter_id if req and req.recruiter_id else self.env.user
            if not app.email_from:
                return {'status': 'skipped', 'text': _('Would not send “Let’s chat”: %s has no '
                                                       'email address.', name)}
            if not (recruiter.sudo().pb_scheduling_link or '').strip():
                return {'status': 'skipped', 'text': _(
                    'Would not send “Let’s chat”: no Calendly link on %s’s profile yet.',
                    recruiter.name or '')}
            res = Hiring._mail_candidate('phone', app, values={
                'scheduling_link': recruiter.pb_scheduling_link, 'duration': '30'}, dry=True)
            lang = LANG_EN.get(res['lang'], res['lang'])
            return {'status': 'done', 'text': _('Would send “Let’s chat” to %(who)s in %(l)s, '
                                                'with %(r)s’s Calendly link.', who=name, l=lang,
                                                r=recruiter.name or '')}
        res = Hiring._pb_send_scheduling_link(app)
        status = res['status']
        out = {'phone': res}
        if status == 'sent':
            out.update(status='done', text=_('Sent “Let’s chat” to %s.', name), mail_sent=1)
        elif status in ('mail_off', 'no_email'):
            out.update(status='skipped', text=_('“Let’s chat” did not go to %(who)s: %(why)s.',
                                                who=name, why=status))
        else:
            out.update(status='failed', text=_('“Let’s chat” did not go to %(who)s: %(why)s.',
                                               who=name, why={'no_link': _('no Calendly link on '
                                                                           'the recruiter’s profile'),
                                                              'no_template': _('the email is not '
                                                                               'set up')}.get(status, status)))
        return out

    def _auto_values(self, app):
        """The details an automation can fill for a candidate email."""
        if not app:
            return {}
        Hiring = self.env['pb.hiring']
        app = app.sudo()
        values = {}
        if app.pb_hold_until:
            values['update_date'] = lambda lang: Hiring._pb_day(app.pb_hold_until, lang)
        if app.pb_stage_reason:
            values['reason'] = app.pb_stage_reason
        return values

    def _internal_mail(self, email, app, req):
        """An email to a colleague, in English (R11), with a door to the board."""
        Hiring = self.env['pb.hiring']
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        name = (app.partner_name if app else '') or ''
        role = (req.title if req else '') or (app.job_id.name if app else '') or ''
        subject = (self.message_subject or '').strip() or (
            _('%(who)s · %(role)s', who=name, role=role) if name else role or _('Hiring'))
        body = (self.message_body or '').strip() or self.name
        body = body.replace('{{name}}', name).replace('{{role}}', role)
        body += '\n\n' + _('Sent by the automation: %s', self.name)
        html = Hiring._pb_email_html(body, _('Open the hiring board'),
                                     '%s/bizapp/action-pb_hiring.action_pb_hiring_board' % base)
        company = (req.company_id if req else False) or (app.company_id if app else False) \
            or self.company_id
        target = app or req
        return self.env['mail.mail'].sudo().create({
            'subject': subject, 'body_html': html, 'email_to': email,
            'email_from': Hiring._sender(company), 'auto_delete': False,
            'model': target._name if target else False, 'res_id': target.id if target else False})

    # ------------------------------------------------------------- dispatch
    @api.model
    def _fire(self, event, app=None, record=None, stage=None, req=None):
        """Run every active rule for this event. Returns the run results.
        Never raises (every rule in its own savepoint)."""
        if self.env.context.get('pb_no_automation') or self.env.context.get('install_mode'):
            return []
        if self.env.context.get('pb_automation_depth', 0) >= MAX_DEPTH:
            return []
        app = app.sudo() if app else self.env['hr.applicant']
        req = (req or (app.pb_requisition_id if app else False)
               or (record.requisition_id if record is not None and 'requisition_id' in record
                   else False))
        req = req.sudo() if req else self.env['pb.hiring.requisition']
        company = (app.company_id if app else False) or (req.company_id if req else False)
        if not company:
            return []
        self._ensure_seeds(company)
        dom = [('company_id', '=', company.id), ('event', '=', event), ('active', '=', True)]
        if event in STAGE_EVENTS:
            if not stage:
                return []
            dom.append(('stage_id', '=', stage.id))
        out = []
        for rule in self.sudo().search(dom):
            res = leg(self.env, 'the automation %s' % rule.id,
                      lambda r=rule: r._run_for(app, req, record, event))
            if res:
                out.append((rule, res))
        return out

    def _run_for(self, app, req, record, event):
        self.ensure_one()
        if not self._effective():
            return None
        if not self._matches(app, req):
            return None
        Run = self.env['pb.hiring.automation.run'].sudo()
        base = {'rule_id': self.id, 'applicant_id': app.id if app else False,
                'requisition_id': req.id if req else False, 'event': event,
                'res_model': record._name if record is not None else False,
                'res_id': record.id if record is not None else False}
        if app and self.once_per_candidate and Run.search_count(
                [('rule_id', '=', self.id), ('applicant_id', '=', app.id),
                 ('state', 'in', ('done', 'queued'))]):
            Run.create(dict(base, state='skipped', ran_at=fields.Datetime.now(),
                            result=_('Already ran for this candidate (once per candidate).')))
            return {'status': 'skipped', 'text': _('Already ran for this candidate.')}
        if self.delay_hours:
            due = fields.Datetime.now() + timedelta(hours=self.delay_hours)
            Run.create(dict(base, state='queued', due_at=due,
                            result=_('Waiting until %s.', fields.Datetime.to_string(due)[:16])))
            return {'status': 'queued', 'text': _('Queued for later.')}
        run = Run.create(dict(base, state='queued', due_at=fields.Datetime.now()))
        return run._execute()

    def _effective(self):
        """Switched on — and, for the Calendly row, the old P5 switch too."""
        self.ensure_one()
        if not self.active:
            return False
        if self.seed_key == 'calendly' and not flag(self.env, P_PHONE_AUTO_MAIL):
            return False
        return True

    # ---------------------------------------------------------- the seeds
    @api.model
    def _ensure_seeds(self, company):
        Rule = self.sudo().with_context(active_test=False)
        if Rule.search_count([('company_id', '=', company.id), ('seed_key', '!=', False)]):
            return 0
        Stage = self.env['hr.recruitment.stage']
        made = 0
        for seed in SEEDS:
            vals = {k: v for k, v in seed.items() if k not in ('stage',)}
            if seed.get('stage'):
                stage = Stage._pb_stage(seed['stage'])
                if not stage:
                    continue
                vals['stage_id'] = stage.id
            vals['company_id'] = company.id
            Rule.create(vals)
            made += 1
        return made

    @api.model
    def _seed_all(self):
        return sum(self._ensure_seeds(c) for c in self.env['res.company'].sudo().search([]))

    # --------------------------------------------------------- the clocks
    @api.model
    def _run_queue(self):
        """The ten-minute job: delayed actions whose time has come."""
        cap = max(1, number(self.env, P_REMINDER_CAP, 400))
        rows = self.env['pb.hiring.automation.run'].sudo().search(
            [('state', '=', 'queued'), ('due_at', '<=', fields.Datetime.now())],
            order='due_at', limit=cap)
        done = 0
        for run in rows:
            if leg(self.env, 'the queued automation run %s' % run.id, run._execute):
                done += 1
        return done

    @api.model
    def _run_waiting(self, company_ids=None):
        """The night job: "has waited N days in <stage>", once per stay."""
        dom = [('event', '=', 'stage_waiting'), ('active', '=', True)]
        if company_ids:
            dom.append(('company_id', 'in', list(company_ids)))
        cap = max(1, number(self.env, P_REMINDER_CAP, 400))
        Run = self.env['pb.hiring.automation.run'].sudo()
        made = 0
        for rule in self.sudo().search(dom):
            if not rule._effective() or not rule.stage_id:
                continue
            cutoff = fields.Datetime.now() - timedelta(days=max(1, rule.days or 1))
            apps = self.env['hr.applicant'].sudo().search([
                ('company_id', '=', rule.company_id.id), ('stage_id', '=', rule.stage_id.id),
                ('active', '=', True), ('date_last_stage_update', '<=', cutoff)],
                order='date_last_stage_update', limit=cap)
            for app in apps:
                stay = fields.Datetime.to_string(app.date_last_stage_update or app.create_date)
                if Run.search_count([('rule_id', '=', rule.id), ('applicant_id', '=', app.id),
                                     ('stay_key', '=', stay)]):
                    continue
                if not rule._matches(app, app.pb_requisition_id):
                    continue
                run = Run.create({'rule_id': rule.id, 'applicant_id': app.id,
                                  'requisition_id': app.pb_requisition_id.id or False,
                                  'event': 'stage_waiting', 'state': 'queued',
                                  'due_at': fields.Datetime.now(), 'stay_key': stay})
                if leg(self.env, 'the waiting rule %s on %s' % (rule.id, app.id), run._execute):
                    made += 1
        return made


class PbHiringAutomationRun(models.Model):
    _name = 'pb.hiring.automation.run'
    _description = 'Hiring automation: one run'
    _order = 'create_date desc, id desc'

    rule_id = fields.Many2one('pb.hiring.automation.rule', string='Rule', required=True,
                              index=True, ondelete='cascade')
    company_id = fields.Many2one(related='rule_id.company_id', store=True, index=True)
    applicant_id = fields.Many2one('hr.applicant', string='Candidate', index=True,
                                   ondelete='cascade')
    requisition_id = fields.Many2one('pb.hiring.requisition', string='Role', ondelete='set null')
    event = fields.Selection(EVENTS, string='What happened')
    res_model = fields.Char(string='Record type')
    res_id = fields.Integer(string='Record')
    stay_key = fields.Char(string='Stay', help='For "has waited": when they entered the stage.')
    due_at = fields.Datetime(string='Due', index=True)
    state = fields.Selection(RUN_STATES, string='Result', default='queued', required=True,
                             index=True)
    result = fields.Char(string='What it did')
    ran_at = fields.Datetime(string='Ran at')

    def _record(self):
        self.ensure_one()
        if self.res_model and self.res_id and self.res_model in self.env:
            return self.env[self.res_model].sudo().browse(self.res_id).exists()
        return None

    def _execute(self):
        """Run (or finish) one queued run. Returns the action's result."""
        self.ensure_one()
        rule = self.rule_id.sudo()
        app = self.applicant_id.sudo().with_context(active_test=False)
        req = self.requisition_id.sudo()
        if not rule._effective():
            self.write({'state': 'skipped', 'ran_at': fields.Datetime.now(),
                        'result': _('The rule was switched off before its time came.')})
            return {'status': 'skipped', 'text': self.result}
        if app and self.event in ('stage_entered',) and self.state == 'queued' and \
                self.due_at and self.create_date and self.due_at > self.create_date and \
                rule.stage_id and app.stage_id != rule.stage_id:
            self.write({'state': 'skipped', 'ran_at': fields.Datetime.now(),
                        'result': _('%s had moved on by then.', app.partner_name or '')})
            return {'status': 'skipped', 'text': self.result}
        try:
            with self.env.cr.savepoint():
                res = rule._do(app, req, record=self._record())
        except Exception as exc:        # noqa: BLE001 — logged, never raised
            _logger.warning('pb_hiring: automation %s failed', rule.id, exc_info=True)
            res = {'status': 'failed', 'text': _('Did not work: %s', str(exc)[:200])}
        self.write({'state': res.get('status') or 'done', 'ran_at': fields.Datetime.now(),
                    'result': (res.get('text') or '')[:250]})
        if res.get('status') == 'done':
            rule.write({'run_count': (rule.run_count or 0) + 1,
                        'last_run_at': fields.Datetime.now()})
        return res


# =========================================================================
#  The facade: the Automations card
# =========================================================================
class PbHiringAutomations(models.AbstractModel):
    _inherit = 'pb.hiring'

    # ------------------------------------------------- the board's moves
    @api.model
    def _pb_on_stage_entered(self, apps, key):
        """P5's hook, now the dispatcher's door for board moves: every
        "enters <stage>" rule runs for each candidate, and the toast names
        what happened (the Calendly words are P5's own)."""
        stage = self.env['hr.recruitment.stage']._pb_stage(key)
        if not stage:
            return {}
        Rule = self.env['pb.hiring.automation.rule']
        phone, other = [], []
        for app in apps:
            for rule, res in Rule._fire('stage_entered', app, stage=stage):
                if 'phone' in res:
                    phone.append(res['phone'])
                elif res.get('status') in ('done', 'failed') and rule.action == 'send_email':
                    other.append((rule, res))
        out = self._pb_phone_words(phone)
        notes = [out['note']] if out.get('note') else []
        sent = out.get('mail_sent', 0)
        by_rule = {}
        for rule, res in other:
            by_rule.setdefault(rule.id, [rule, 0, []])
            if res.get('status') == 'done':
                by_rule[rule.id][1] += 1
            else:
                by_rule[rule.id][2].append(res.get('why') or '')
        for rule, n, fails in by_rule.values():
            ename = rule._email_name()
            if n:
                notes.append(_('“%s” went out', ename) if n == 1 else
                             _('“%(e)s” went to %(n)s people', e=ename, n=n))
                sent += n
            elif fails:
                notes.append(_('“%(e)s” did not go: %(why)s', e=ename, why=fails[0]))
        res = {}
        if notes:
            res['note'] = ' · '.join(notes)
        if out.get('warning'):
            res['warning'] = out['warning']
        if sent:
            res['mail_sent'] = sent
        return res

    @api.model
    def _pb_phone_words(self, results):
        """P5's `_pb_phone_rule` sentences, from the per-candidate answers."""
        out = {}
        if not results:
            return out
        sent = [r for r in results if r['status'] == 'sent']
        if sent:
            out['note'] = _("the Calendly email went out") if len(sent) == 1 \
                else _("%s Calendly emails went out", len(sent))
            out['mail_sent'] = len(sent)
        missing = [r for r in results if r['status'] == 'no_link']
        if missing:
            who = missing[0]['who']
            mine = missing[0]['user_id'] == self.env.uid
            text = _("No Calendly link on your profile yet, so nothing was sent. Add it in Preferences.") \
                if mine else _("No Calendly link on %s's profile yet, so nothing was sent. "
                               "Add it in Hiring set-up → Who does what.", who)
            out['warning'] = {'text': text, 'mine': mine, 'user_id': missing[0]['user_id']}
            if not sent:
                out['note'] = _("no Calendly email went")
        if any(r['status'] == 'mail_off' for r in results) and not sent:
            out['note'] = _("candidate emails are switched off, so no Calendly email went")
        no_email = [r for r in results if r['status'] == 'no_email']
        if no_email and not sent and not missing:
            out['note'] = _("there is no email address for them, so no Calendly email went")
        return out

    # ------------------------------------------------------------ payload
    @api.model
    def get_automations(self):
        if not self._can_read():
            raise AccessError(_('Hiring access is required.'))
        company = self.env.company
        Rule = self.env['pb.hiring.automation.rule']
        Rule._ensure_seeds(company)
        rules = Rule.sudo().with_context(active_test=False).search(
            [('company_id', '=', company.id)])
        Stage = self.env['hr.recruitment.stage'].sudo()
        stages = Stage.search([('pb_key', '!=', False)], order='sequence,id')
        Tpl = self.env['pb.hiring.message.template'].sudo()
        emails = Tpl.search([('company_id', '=', company.id), ('active', '=', True)])
        from .comms_i18n_p8 import EMAIL_KEYS
        order = {k: i for i, k in enumerate(EMAIL_KEYS)}
        lead_days = number(self.env, P_LEAD_LATE_DAYS, 2)
        week = number(self.env, P_WEEK_BEFORE_DAYS, 7)
        builtins = []
        for key, sentence, param, default, email_key, why in BUILTINS:
            sentence = sentence % {'lead': _days_words(lead_days) + ' ' + _('late'),
                                   'days': _days_words(week).capitalize()} \
                if '%(' in sentence else sentence
            builtins.append({
                'key': key, 'sentence': sentence, 'locked': not param, 'why': why,
                'on': flag(self.env, param, default) if param else True,
                'email_key': email_key,
                'email_id': (emails.filtered(lambda t, k=email_key: t.key == k)[:1].id
                             if email_key else False),
            })
        runs = self.env['pb.hiring.automation.run'].sudo().search(
            [('company_id', '=', company.id)], limit=100)
        return {
            'can_edit': self._can_write(),
            'rules': [self._pb_rule_row(r) for r in rules],
            'builtins': builtins,
            'log': [{
                'id': r.id, 'when': fields.Datetime.to_string(r.ran_at or r.create_date),
                'state': r.state, 'rule': r.rule_id.name or '',
                'who': r.applicant_id.with_context(active_test=False).partner_name or
                (r.requisition_id.title or ''), 'result': r.result or '',
                'due': fields.Datetime.to_string(r.due_at) if r.state == 'queued' else '',
            } for r in runs],
            'events': [{'key': k, 'label': _(v), 'stage': k in STAGE_EVENTS,
                        'waiting': k == 'stage_waiting', 'role_only': k in ROLE_EVENTS}
                       for k, v in EVENTS],
            'actions': [{'key': k, 'label': _(v)} for k, v in ACTIONS],
            'recipients': [{'key': k, 'label': _(v)} for k, v in RECIPIENTS],
            'stages': [{'id': s.id, 'key': s.pb_key, 'name': s.name or '',
                        'family': s.pb_family or 'open'} for s in stages],
            'emails': [{'key': t.key, 'id': t.id, 'name': t.with_context(lang='en_US').name or ''}
                       for t in emails.sorted(lambda t: (order.get(t.key, 99), t.id))],
            'tags': [{'id': t.id, 'name': t.name or ''} for t in
                     self.env['hr.applicant.category'].sudo().search([], limit=200)],
            'departments': self._safe(lambda: self._departments(
                self.env.companies.ids or [company.id]), default=[]),
            'countries': self.env['res.country'].sudo().search_read([], ['name']),
            'queued': self.env['pb.hiring.automation.run'].sudo().search_count(
                [('company_id', '=', company.id), ('state', '=', 'queued')]),
        }

    @api.model
    def _pb_rule_row(self, r):
        return {
            'id': r.id, 'sentence': r.name, 'active': bool(r.active),
            'effective': bool(r._effective()), 'seed_key': r.seed_key or '',
            'note': SEED_NOTES.get(r.seed_key or '', ''),
            'event': r.event, 'stage_id': r.stage_id.id or False, 'days': r.days or 0,
            'action': r.action, 'template_key': r.template_key or '',
            'recipient': r.recipient or '', 'custom_emails': r.custom_emails or '',
            'message_subject': r.message_subject or '', 'message_body': r.message_body or '',
            'todo_text': r.todo_text or '', 'target_stage_id': r.target_stage_id.id or False,
            'tag_id': r.tag_id.id or False, 'tag': r.tag_id.name or '',
            'delay_hours': r.delay_hours or 0, 'once': bool(r.once_per_candidate),
            'department_ids': r.department_ids.ids, 'country_ids': r.country_ids.ids,
            'run_count': r.run_count or 0,
            'last_run': fields.Datetime.to_string(r.last_run_at) if r.last_run_at else '',
            'phone_off': r.seed_key == 'calendly' and r.active
            and not flag(self.env, P_PHONE_AUTO_MAIL),
        }

    @api.model
    def _pb_rule_vals(self, payload):
        def ids(key):
            return [as_id(i) for i in payload.get(key) or [] if as_id(i)]
        vals = {
            'event': payload.get('event') or False,
            'stage_id': as_id(payload.get('stage_id')) or False,
            'days': int(payload.get('days') or 0),
            'action': payload.get('action') or 'send_email',
            'template_key': payload.get('template_key') or False,
            'recipient': payload.get('recipient') or False,
            'custom_emails': (payload.get('custom_emails') or '').strip() or False,
            'message_subject': (payload.get('message_subject') or '').strip()[:200] or False,
            'message_body': (payload.get('message_body') or '').strip()[:4000] or False,
            'todo_text': (payload.get('todo_text') or '').strip()[:120] or False,
            'target_stage_id': as_id(payload.get('target_stage_id')) or False,
            'delay_hours': int(payload.get('delay_hours') or 0),
            'once_per_candidate': bool(payload.get('once', True)),
            'department_ids': [(6, 0, ids('department_ids'))],
            'country_ids': [(6, 0, ids('country_ids'))],
        }
        tag = payload.get('tag_id')
        if not tag and (payload.get('tag') or '').strip():
            Cat = self.env['hr.applicant.category'].sudo()
            name = payload['tag'].strip()[:60]
            tag = (Cat.search([('name', '=ilike', name)], limit=1) or Cat.create({'name': name})).id
        vals['tag_id'] = as_id(tag) or False
        if vals['action'] != 'send_email':
            vals['template_key'] = False
        return vals

    def _act_rule_save(self, payload):
        self._require_write()
        Rule = self.env['pb.hiring.automation.rule'].sudo().with_context(active_test=False)
        vals = self._pb_rule_vals(payload)
        if payload.get('id'):
            rule = Rule.browse(as_id(payload['id'])).exists()
            if not rule or rule.company_id not in self.env.companies:
                raise UserError(_("That rule is no longer there."))
            before = self._pb_rule_row(rule)
            with self.env.cr.savepoint():
                rule.write(vals)
                rule._check_complete()
            return {'id': rule.id, 'note': _("Saved: %s", rule.name), 'before': before}
        with self.env.cr.savepoint():
            rule = Rule.create(dict(vals, company_id=self.env.company.id, active=True))
            rule._check_complete()
        return {'id': rule.id, 'note': _("Added and switched on: %s", rule.name)}

    def _act_rule_toggle(self, payload):
        self._require_write()
        rule = self.env['pb.hiring.automation.rule'].sudo().with_context(
            active_test=False).browse(as_id(payload.get('id'))).exists()
        if not rule or rule.company_id not in self.env.companies:
            raise UserError(_("That rule is no longer there."))
        on = bool(payload.get('on'))
        if on:
            rule._check_complete()
        rule.write({'active': on})
        if on and rule.seed_key == 'calendly' and not flag(self.env, P_PHONE_AUTO_MAIL):
            self.env['ir.config_parameter'].sudo().set_param(P_PHONE_AUTO_MAIL, '1')
        return {'note': _("Switched on.") if on else _("Switched off. Nothing it would have "
                                                        "done will happen."), 'on': on}

    def _act_rule_delete(self, payload):
        self._require_write()
        rule = self.env['pb.hiring.automation.rule'].sudo().with_context(
            active_test=False).browse(as_id(payload.get('id'))).exists()
        if not rule or rule.company_id not in self.env.companies:
            raise UserError(_("That rule is no longer there."))
        if rule.seed_key:
            raise UserError(_("A starting rule is switched off rather than removed, so it can "
                              "be switched on again."))
        saved = self._pb_rule_row(rule)
        rule.unlink()
        return {'note': _("Rule removed."), 'saved': saved}

    def _act_builtin_switch(self, payload):
        self._require_write()
        key = payload.get('key')
        if key not in BUILTIN_SWITCHES:
            raise UserError(_("That one is always on."))
        param, _default = BUILTIN_SWITCHES[key]
        on = bool(payload.get('on'))
        self.env['ir.config_parameter'].sudo().set_param(param, '1' if on else '0')
        return {'on': on, 'note': _("Switched on.") if on else _("Switched off.")}

    def _act_rules_run_waiting(self, payload):
        """"Check the waiting candidates now" — exactly what the night does,
        for this company."""
        self._require_write()
        made = self.env['pb.hiring.automation.rule'].sudo()._run_waiting(
            company_ids=[self.env.company.id])
        return {'note': _("Checked. %s", counted(made, _('1 rule ran.'),
                                                  _('%s rules ran.') % made)
                                         if made else _('Nobody had waited long enough.'))}

    @api.model
    def get_rule_candidates(self, query=''):
        """The candidates "Try it on a candidate" offers (open ones first)."""
        if not self._can_read():
            raise AccessError(_('Hiring access is required.'))
        dom = [('company_id', 'in', self.env.companies.ids), ('pb_requisition_id', '!=', False)]
        if (query or '').strip():
            dom.append(('partner_name', 'ilike', query.strip()))
        apps = self.env['hr.applicant'].sudo().search(dom, order='write_date desc', limit=8)
        return [{'id': a.id, 'name': a.partner_name or a.email_from or '',
                 'role': a.pb_requisition_id.title or a.job_id.name or '',
                 'stage': a.stage_id.name or ''} for a in apps]

    def _act_rule_try(self, payload):
        """Dry run: what this rule (saved or still being written) would do for
        one candidate — nothing is sent or written."""
        if not self._can_read():
            raise AccessError(_('Hiring access is required.'))
        app = self.env['hr.applicant'].sudo().with_context(active_test=False).browse(
            as_id(payload.get('applicant_id'))).exists()
        if not app:
            raise UserError(_("Pick a candidate to try it on."))
        Rule = self.env['pb.hiring.automation.rule'].sudo()
        vals = self._pb_rule_vals(payload.get('rule') or {})
        draft = Rule.new(dict(vals, company_id=app.company_id.id, active=True))
        try:
            draft._check_complete()
        except UserError as exc:
            return {'lines': [{'ok': False, 'text': str(exc.args[0])}], 'sentence': draft.name}
        req = app.pb_requisition_id
        lines = []
        name = app.partner_name or ''
        if draft.event in STAGE_EVENTS and draft.stage_id:
            if app.stage_id == draft.stage_id:
                lines.append({'ok': True, 'text': _('%(who)s is in %(s)s now.', who=name,
                                                    s=draft.stage_id.name)})
            else:
                lines.append({'ok': None, 'text': _('%(who)s is in %(now)s, not %(s)s — '
                                                    'this shows what would happen when they '
                                                    'get there.', who=name,
                                                    now=app.stage_id.name or '',
                                                    s=draft.stage_id.name)})
        if not draft._matches(app, req):
            lines.append({'ok': False, 'text': _('Their role is outside the departments or '
                                                 'countries this rule is for, so nothing '
                                                 'would happen.')})
            return {'lines': lines, 'sentence': draft.name}
        if draft.once_per_candidate and payload.get('rule', {}).get('id'):
            if self.env['pb.hiring.automation.run'].sudo().search_count(
                    [('rule_id', '=', as_id(payload['rule']['id'])),
                     ('applicant_id', '=', app.id), ('state', '=', 'done')]):
                lines.append({'ok': False, 'text': _('It already ran for %s, and it runs once '
                                                     'per candidate.', name)})
                return {'lines': lines, 'sentence': draft.name}
        res = draft._do(app, req, dry=True)
        lines.append({'ok': res.get('status') == 'done', 'text': res.get('text') or ''})
        if draft.delay_hours:
            lines.append({'ok': None, 'text': _('It would wait %s first.',
                                                draft.name.rsplit(', ', 1)[-1].rstrip('.'))})
        return {'lines': lines, 'sentence': draft.name}

    # ------------------------------------------------------------- set-up
    @api.model
    def get_setup(self):
        res = super().get_setup()
        autos = self._safe(self.get_automations, default=None)
        res['automations'] = autos
        for card in res.get('cards', []):
            if card['key'] == 'automations' and autos:
                mine = [r for r in autos['rules'] if r['effective']]
                on = [b for b in autos['builtins'] if b['on']]
                card.update({'status': _("%(m)s of your rules on · %(b)s of %(t)s built-in "
                                         "on", m=len(mine), b=len(on), t=len(autos['builtins'])),
                             'inline': True, 'action': False})
        return res


# =========================================================================
#  The clocks
# =========================================================================
class HiringAutomationClocks(models.AbstractModel):
    _inherit = 'pb.hiring.automation'

    @api.model
    def run_reminders(self):
        counts = super().run_reminders()
        try:
            made = self.env['pb.hiring.automation.rule'].sudo()._run_queue()
            if made:
                counts['automations'] = made
        except Exception:               # noqa: BLE001 — a job never raises
            _logger.warning('pb_hiring: the automation queue failed', exc_info=True)
        return counts

    @api.model
    def run_now(self):
        counts = super().run_now()
        try:
            counts['waiting_rules'] = self.env['pb.hiring.automation.rule'].sudo()._run_waiting()
        except Exception:               # noqa: BLE001
            _logger.warning('pb_hiring: the waiting rules failed', exc_info=True)
        return counts

    # ------------------------------------------- the built-in switches
    @api.model
    def _ask_after_interview(self):
        if not flag(self.env, 'pb_hiring.auto_chase', '1'):
            return 0
        return super()._ask_after_interview()

    @api.model
    def _chase_late_feedback(self):
        if not flag(self.env, 'pb_hiring.auto_chase', '1'):
            return 0
        return super()._chase_late_feedback()

    @api.model
    def _tell_lead_late_feedback(self):
        if not flag(self.env, 'pb_hiring.auto_chase', '1'):
            return 0
        return super()._tell_lead_late_feedback()

    @api.model
    def _chase_documents(self):
        if not flag(self.env, 'pb_hiring.auto_doc_remind', '1'):
            return 0
        return super()._chase_documents()

    @api.model
    def _week_before_join(self):
        if not flag(self.env, 'pb_hiring.auto_week_before', '1'):
            return 0
        return super()._week_before_join()
