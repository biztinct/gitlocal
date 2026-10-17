# -*- coding: utf-8 -*-
"""RECRUIT P8 — the one-line hooks that feed the automations, and the four
leftovers this phase closes.

EVERY HOOK IS A `leg` AFTER `super()`: the thing that happened has happened
before any rule looks at it, and a rule that fails is a line in the run log,
never a move, an offer or a signature undone (handover §4).

Leftovers:
  * G-44 — an offer is signed and the role has nobody else to find: the other
    finalists are closed at Interview reject ("Not selected"), with a note on
    their timeline and the "Not this time" email in their language. A
    built-in the talent lead can switch off (`pb_hiring.auto_close_finalists`).
  * RC80 — the "papers are in" to-do now reaches the recruiter (on the offer,
    `comms_p8.HiringDocreqComms.activity_schedule`).
  * P4 owner item — the person a candidate is shared with gets an email.
  * Background check started → a to-do for the recruiter.
"""

import logging

from markupsafe import Markup

from odoo import _, api, fields, models

from .hiring_common import P_CANDIDATE_MAIL, flag, leg

_logger = logging.getLogger(__name__)

_TODO = 'mail.mail_activity_data_todo'
#: Who counts as a finalist (P5 `FINALIST_KEYS`).
FINALIST_KEYS = ('discussion_1', 'discussion_2', 'discussion_3', 'reference', 'offer')


def _fire(env, event, app=None, record=None, stage=None, req=None):
    return leg(env, 'the %s automations' % event,
               lambda: env['pb.hiring.automation.rule'].sudo()._fire(
                   event, app=app, record=record, stage=stage, req=req))


# =========================================================================
#  Candidates: applied, entered a stage
# =========================================================================
class HiringApplicantHooks(models.Model):
    _inherit = 'hr.applicant'

    @api.model_create_multi
    def create(self, vals_list):
        apps = super().create(vals_list)
        ctx = self.env.context
        if not (ctx.get('pb_no_stage_log') or ctx.get('pb_no_automation')
                or ctx.get('install_mode')):
            for app in apps:
                if app.pb_requisition_id or app.job_id:
                    _fire(self.env, 'applied', app)
        return apps

    def write(self, vals):
        before = {}
        ctx = self.env.context
        if 'stage_id' in vals and not (ctx.get('pb_board_move') or ctx.get('pb_no_stage_log')
                                       or ctx.get('pb_no_automation')):
            before = {rec.id: rec.stage_id.id for rec in self}
        res = super().write(vals)
        for rec in self:
            if rec.id in before and before[rec.id] != rec.stage_id.id and rec.stage_id.pb_key:
                _fire(self.env, 'stage_entered', rec, stage=rec.stage_id)
        return res


# =========================================================================
#  Interviews and opinions
# =========================================================================
class HiringInterviewHooks(models.Model):
    _inherit = 'pb.hiring.interview'

    def _after_scheduled(self, move_stage=True):
        res = super()._after_scheduled(move_stage=move_stage)
        _fire(self.env, 'interview_scheduled', self.applicant_id, record=self)
        return res

    def action_mark_done(self, force=False):
        was = {r.id: r.state for r in self}
        res = super().action_mark_done(force=force)
        for rec in self:
            if was.get(rec.id) != 'done' and rec.state == 'done':
                _fire(self.env, 'interview_done', rec.applicant_id, record=rec)
        return res

    def action_no_show(self, by=None, note=None):
        res = super().action_no_show(by=by, note=note)
        for rec in self:
            _fire(self.env, 'interview_no_show', rec.applicant_id, record=rec)
        return res


class HiringFeedbackHooks(models.Model):
    _inherit = 'pb.hiring.feedback'

    def _summarise_if_complete(self):
        res = super()._summarise_if_complete()
        if res:
            iv = self.interview_id.sudo()
            _fire(self.env, 'opinions_all_in', iv.applicant_id, record=iv)
        return res


# =========================================================================
#  Papers, the background check
# =========================================================================
class HiringDocreqHooks(models.Model):
    _inherit = 'pb.hiring.docreq'

    def _all_in(self):
        res = super()._all_in()
        _fire(self.env, 'documents_complete', self.sudo().offer_id.applicant_id, record=self)
        return res


class HiringBgvHooks(models.Model):
    _inherit = 'pb.hiring.bgv'

    @api.model
    def open_for(self, requisition_id, applicant_id=None):
        from .hiring_common import as_id
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id)).exists()
        app_id = as_id(applicant_id) or (req.selected_applicant_id.id if req else 0)
        existed = bool(req and app_id and self.sudo().search_count(
            [('requisition_id', '=', req.id), ('applicant_id', '=', app_id)]))
        bgv = super().open_for(requisition_id, applicant_id=applicant_id)
        if bgv and not existed:
            leg(self.env, 'the check-started to-do on %s' % bgv.id, bgv._pb_started_todo)
            _fire(self.env, 'check_started', bgv.applicant_id, record=bgv)
        return bgv

    def _pb_started_todo(self):
        """Background check started → the recruiter's to-do (on the candidate:
        the check itself has no to-do list, RC46)."""
        self.ensure_one()
        if not flag(self.env, 'pb_hiring.auto_check_todo', '1'):
            return False
        rec = self.sudo()
        user = rec.requisition_id.recruiter_id or rec.applicant_id.user_id
        app = rec.applicant_id
        if not user or not app or user.share:
            return False
        summary = _('Background check started: %s', app.partner_name or '')
        if self.env['mail.activity'].sudo().search_count([
                ('res_model', '=', 'hr.applicant'), ('res_id', '=', app.id),
                ('summary', '=', summary)]):
            return False
        app.activity_schedule(_TODO, summary=summary, user_id=user.id,
                              note=_("The checklist is open on the candidate's offer tab. "
                                     "The offer does not wait for it."),
                              date_deadline=fields.Date.context_today(self))
        return True


# =========================================================================
#  The offer: sent, answered, signed (G-44), joined, did not join
# =========================================================================
class HiringOfferHooks(models.Model):
    _inherit = 'pb.hiring.offer'

    def action_send_to_candidate(self, force=False):
        res = super().action_send_to_candidate(force=force)
        _fire(self.env, 'offer_sent', self.applicant_id, record=self)
        return res

    def record_decision(self, decision, comment=None):
        res = super().record_decision(decision, comment=comment)
        event = {'accepted': 'offer_accepted', 'declined': 'offer_declined'}.get(decision)
        if event:
            for rec in self:
                _fire(self.env, event, rec.applicant_id, record=rec)
        return res

    def _on_signed(self, kind=None, label=None, quiet=False):
        res = super()._on_signed(kind=kind, label=label, quiet=quiet)
        if not quiet:
            leg(self.env, 'closing the other finalists on %s' % self.name,
                self._pb_close_other_finalists)
            _fire(self.env, 'offer_signed', self.applicant_id, record=self)
        return res

    def action_confirm_joined(self, joined_on=None):
        res = super().action_confirm_joined(joined_on=joined_on)
        for rec in self:
            _fire(self.env, 'joined', rec.applicant_id, record=rec)
        return res

    def action_did_not_join(self, reason=None, note=None, source='drawer', by_name=None):
        res = super().action_did_not_join(reason=reason, note=note, source=source,
                                          by_name=by_name)
        for rec in self:
            _fire(self.env, 'did_not_join', rec.applicant_id, record=rec)
        return res

    def _pb_close_other_finalists(self):
        """G-44. The role is full once as many people have signed as it
        needs; then every other finalist still in play is told "not this
        time" — never somebody with an offer of their own on the way."""
        self.ensure_one()
        if not flag(self.env, 'pb_hiring.auto_close_finalists', '1'):
            return 0
        offer = self.sudo()
        req = offer.requisition_id
        if not req:
            return 0
        signed = self.search_count([('requisition_id', '=', req.id),
                                    ('state', 'in', ('signed', 'joined'))])
        if signed < max(1, req.headcount or 1):
            return 0
        Stage = self.env['hr.recruitment.stage']
        reject = Stage._pb_stage('interview_reject')
        if not reject:
            return 0
        others = self.env['hr.applicant'].sudo().search([
            ('pb_requisition_id', '=', req.id), ('id', '!=', offer.applicant_id.id),
            ('active', '=', True), ('stage_id.pb_key', 'in', FINALIST_KEYS)])
        live = set(self.search([('requisition_id', '=', req.id),
                                ('state', 'in', ('draft', 'submitted', 'manager_ok', 'hr_ok',
                                                 'sent', 'accepted'))]).mapped('applicant_id').ids)
        reason = _("Not selected: %s signed for this role.", offer.candidate_name or '')
        closed = 0
        Hiring = self.env['pb.hiring']
        for app in others:
            if app.id in live:
                continue
            app.with_context(just_moved=True, pb_no_automation=True).write(
                {'stage_id': reject.id, 'pb_stage_reason': reason})
            app.message_post(body=Markup('<p>%s</p>') % _(
                "Closed as %(stage)s: another finalist signed for this role.",
                stage=reject.name or ''), message_type='comment',
                subtype_xmlid='mail.mt_note')
            if flag(self.env, P_CANDIDATE_MAIL):
                leg(self.env, 'the not-selected email to %s' % app.id,
                    lambda a=app: Hiring._mail_candidate('interview_reject', a))
            closed += 1
        if closed:
            req.message_post(body=_(
                "%(n)s other finalists closed as %(stage)s after %(who)s signed.",
                n=closed, stage=reject.name or '', who=offer.candidate_name or ''))
        return closed


# =========================================================================
#  The request, referrals, agencies
# =========================================================================
class HiringRequisitionHooks(models.Model):
    _inherit = 'pb.hiring.requisition'

    def _request_write(self, state):
        was = {r.id: r.request_state for r in self}
        res = super()._request_write(state)
        event = {'sent_in': 'request_sent_in', 'agreed': 'request_agreed'}.get(state)
        if event:
            for rec in self:
                if was.get(rec.id) != state:
                    _fire(self.env, event, req=rec.sudo())
        return res


class HiringReferralHooks(models.Model):
    _inherit = 'pb.hiring.referral'

    @api.model
    def refer(self, requisition_id, employee_id, values):
        referral = super().refer(requisition_id, employee_id, values)
        if referral and referral.sudo().applicant_id:
            _fire(self.env, 'referral_received', referral.sudo().applicant_id, record=referral)
        return referral


class HiringAgencyHooks(models.Model):
    _inherit = 'pb.hiring.agency.submission'

    @api.model
    def _submit(self, vendor, req, user, values, attachment=None):
        row = super()._submit(vendor, req, user, values, attachment=attachment)
        if row and row.state == 'accepted' and row.applicant_id:
            _fire(self.env, 'agency_submitted', row.applicant_id, record=row)
        return row


# =========================================================================
#  Board moves carry their own flag; shares tell the person
# =========================================================================
class PbHiringHooks(models.AbstractModel):
    _inherit = 'pb.hiring'

    def _act_journey_stage(self, payload):
        """The board fires "enters a stage" itself (P5's hook, with the toast),
        so its own write carries `pb_board_move` and the write-level hook
        stays quiet. On hold with "send the email" sends the on-hold email."""
        res = super(PbHiringHooks, self.with_context(pb_board_move=True))._act_journey_stage(payload)
        if payload.get('send_email') and payload.get('key') == 'on_hold' and not payload.get('undo'):
            sent, why = 0, ''
            Hiring = self.env['pb.hiring']
            for m in res.get('moved') or []:
                app = self.env['hr.applicant'].sudo().browse(m['id'])
                values = {'reason': (payload.get('reason') or '').strip()}
                hold = payload.get('hold_until') or payload.get('update_date')
                if hold:
                    values['update_date'] = lambda lang, h=hold: Hiring._pb_day(
                        fields.Date.to_date(h), lang)
                out = Hiring._mail_candidate('on_hold', app, values=values,
                                             reply_to=self.env.user.email_formatted or None)
                if out['status'] == 'sent':
                    sent += 1
                elif out['status'] == 'missing':
                    why = _("add a reason and a date to look again, then the on-hold "
                            "email can go")
                elif out['status'] == 'no_email':
                    why = _("there is no email address for them")
            if sent:
                res['note'] += ' · ' + (_("the on-hold email went out") if sent == 1 else
                                        _("%s on-hold emails went out", sent))
            elif why:
                res['note'] += ' · ' + why
        return res

    def _act_share(self, payload):
        Share = self.env['pb.hiring.share'].sudo().with_context(active_test=False)
        res = super()._act_share(payload)
        if not flag(self.env, 'pb_hiring.auto_share_mail', '1'):
            return res
        told = 0
        for was in res.get('before') or []:
            if was.get('parts'):
                continue        # they could already see something: no new email
            share = Share.search([('applicant_id', '=', was['applicant_id']),
                                  ('user_id', '=', was['user_id']), ('active', '=', True)],
                                 limit=1)
            if share and leg(self.env, 'the share email for %s' % share.id, share._pb_tell):
                told += 1
        if told:
            res['note'] += ' ' + (_("They got an email with the link.") if told == 1 else
                                  _("%s people got an email with the link.", told))
        return res


class HiringShareMail(models.Model):
    _inherit = 'pb.hiring.share'

    pb_board_url = fields.Char(compute='_compute_pb_share_words')
    pb_parts_words = fields.Char(compute='_compute_pb_share_words')
    pb_role_title = fields.Char(compute='_compute_pb_share_words')

    def _compute_pb_share_words(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        Hiring = self.env['pb.hiring']
        for rec in self:
            rec.pb_board_url = '%s/bizapp/action-pb_hiring.action_pb_hiring_board' % base
            try:
                rec.pb_parts_words = Hiring._parts_label(rec._part_set()) if rec.parts else ''
            except Exception:           # noqa: BLE001 — words, never a crash
                rec.pb_parts_words = rec.parts or ''
            app = rec.applicant_id.sudo()
            rec.pb_role_title = (app.pb_requisition_id.title or app.job_id.name or '') if app else ''

    def _pb_tell(self):
        """"You were given access to <candidate> on <role>" — English, to a
        colleague with a full login (shares are never made with a portal
        login, P4), with the door to the hiring board."""
        self.ensure_one()
        user = self.sudo().user_id
        email = (user.email or (self.employee_id.work_email if self.employee_id else '') or '').strip()
        if not email or user.share:
            return False
        template = self.env.ref('pb_hiring.mail_template_share_granted', raise_if_not_found=False)
        if not template:
            return False
        template.sudo().send_mail(self.id, force_send=False, email_values={
            'email_to': email, 'auto_delete': False})
        return True
