# -*- coding: utf-8 -*-
"""RECRUIT P5 — the screens' payloads and verbs for interviews.

  * **Calendly on the move** (G-37): `_act_journey_stage` → after the move,
    `_pb_on_stage_entered(apps, key)` — THE HOOK P8 turns into the first row of
    the automations list. Today it knows one rule: entering `phone`
    (Recruiter review) sends the "Let's chat" email with the recruiter's own
    scheduling link, in the candidate's language. The toast names it; a
    missing link says where to add it. Undo never unsends.
  * **Scorecards in Hiring set-up** (G-32): list, questions editor with drag
    reorder, preview; the role's rounds pick theirs (G-18).
  * **Enter it for them**: `_act_feedback_proxy` (recruiters), stamped with
    who typed it and where it came from.
  * **Google**: connection state per recruiter, the connect link.
  * **Transcript slot**: hiring team only.
  * **Finalists side by side** (G-38): `get_finalists`, `_act_finalist_decide`.
"""

import base64
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .hiring_common import (
    DECISIONS, GROUP_USER, P_CANDIDATE_MAIL, P_PHONE_AUTO_MAIL,
    P_PHONE_MINUTES, ROLE_FAMILIES, SCORECARD_FAMILIES, SCORECARD_PART_KINDS,
    SCORECARD_ROUNDS, STEP_KINDS, as_id, flag, number,
)
from .journey import text_html

_logger = logging.getLogger(__name__)

#: Who is a finalist: anybody in a discussion round, a reference check or the
#: offer column (not yet closed).
FINALIST_KEYS = ('discussion_1', 'discussion_2', 'discussion_3', 'reference', 'offer')
#: The finalist decisions and the column each one lands on.
FINALIST_MOVES = {'choose': 'offer', 'warm': 'on_hold', 'no': 'interview_reject'}
#: A transcript file is a recording's notes, not the recording.
TRANSCRIPT_MAX_BYTES = 15 * 1024 * 1024


class PbHiringP5(models.AbstractModel):
    _inherit = 'pb.hiring'

    # =====================================================================
    #  Calendly: the rule on entering Recruiter review (G-37)
    # =====================================================================
    def _act_journey_stage(self, payload):
        res = super()._act_journey_stage(payload)
        moved = res.get('moved') or []
        if not moved:
            return res
        if payload.get('undo'):
            back = [m for m in moved if m.get('from_key') == 'phone']
            sent = self.env['hr.applicant'].sudo().browse([m['id'] for m in back]).filtered(
                'pb_scheduling_sent_at')
            if sent:
                res['note'] += ' · ' + _("the Calendly email already went and stays sent")
            return res
        by_key = {}
        for m in moved:
            by_key.setdefault(m['to_key'], []).append(m['id'])
        for key, ids in by_key.items():
            out = self._pb_on_stage_entered(
                self.env['hr.applicant'].sudo().browse(ids), key)
            if out.get('note'):
                res['note'] += ' · ' + out['note']
            if out.get('warning'):
                res['warning'] = out['warning']
            if out.get('mail_sent'):
                res['mail_sent'] = out['mail_sent']
        return res

    @api.model
    def _pb_on_stage_entered(self, apps, key):
        """THE HOOK for "when a candidate reaches a stage, do X" (P8 turns
        this into rows of the automations list). P5 ships one rule:
        Recruiter review sends the recruiter's scheduling link."""
        if key == 'phone':
            return self._pb_phone_rule(apps)
        return {}

    @api.model
    def _pb_phone_rule(self, apps):
        if not flag(self.env, P_PHONE_AUTO_MAIL):
            return {}
        results = [self._pb_send_scheduling_link(app) for app in apps]
        sent = [r for r in results if r['status'] == 'sent']
        out = {}
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

    @api.model
    def _pb_send_scheduling_link(self, app):
        """The "Let's chat" email, with the recruiter's own link, in the
        language they applied in. Returns {status, who, user_id}."""
        app = app.sudo()
        req = app.pb_requisition_id
        recruiter = req.recruiter_id if req and req.recruiter_id else self.env.user
        answer = {'who': recruiter.name or '', 'user_id': recruiter.id}
        if not app.email_from:
            return dict(answer, status='no_email')
        if not flag(self.env, P_CANDIDATE_MAIL):
            return dict(answer, status='mail_off')
        link = (recruiter.sudo().pb_scheduling_link or '').strip()
        if not link:
            return dict(answer, status='no_link')
        template = self.env['pb.hiring.message.template'].sudo().search([
            ('company_id', '=', app.company_id.id), ('key', '=', 'phone')], limit=1)
        if not template:
            return dict(answer, status='no_template')
        from .forms_p2 import _raw
        lang = app.pb_lang or 'en_US'
        if lang != 'en_US':
            raw = _raw(template, 'body').get(template.id) or {}
            if not (raw.get(lang) or '').strip():
                lang = 'en_US'
        values = {'scheduling_link': link, 'hr_name': recruiter.name or '',
                  'sender_name': recruiter.name or '',
                  'duration': str(number(self.env, P_PHONE_MINUTES, 30))}
        try:
            rendered = template.with_context(lang=lang)._render(app, values)
        except UserError:
            _logger.info('pb_hiring: the Let\'s chat email for applicant %s is missing '
                         'a detail', app.id, exc_info=True)
            return dict(answer, status='no_template')
        company = app.company_id
        mail = self.env['mail.mail'].sudo().create({
            'subject': rendered['subject'], 'body_html': text_html(rendered['body']),
            'email_to': app.email_from, 'email_from': self._sender(company),
            'reply_to': recruiter.email_formatted or False,
            'model': 'hr.applicant', 'res_id': app.id, 'auto_delete': False})
        app.message_post(subject=rendered['subject'], body=text_html(rendered['body']),
                         message_type='comment', subtype_xmlid='mail.mt_note')
        app.write({'pb_scheduling_sent_at': fields.Datetime.now()})
        return dict(answer, status='sent', mail_id=mail.id)

    # =====================================================================
    #  The card and the interview rows
    # =====================================================================
    @api.model
    def _card(self, app, ivs, doc_count, req, now, today, can_recruit):
        card = super()._card(app, ivs, doc_count, req, now, today, can_recruit)
        late = None
        for iv in ivs:
            if iv.state not in ('scheduled', 'done'):
                continue
            for f in iv.feedback_ids:
                if f.state == 'pending' and f.due_at and f.due_at < now:
                    late = f
                    break
            if late:
                break
        card['remind'] = {'feedback_id': late.id,
                          'who': late.panel_employee_id.sudo().name or ''} \
            if (late and can_recruit) else None
        if app.pb_scheduling_sent_at and (app.stage_id.pb_key or '') == 'phone':
            chips = card.get('chips') or []
            if len(chips) < 2:
                chips.append({'label': _('Calendly sent'), 'tone': 'info'})
            card['chips'] = chips
        return card

    @api.model
    def _interview_row(self, rec):
        row = super()._interview_row(rec)
        counts = {k: 0 for k, _l in DECISIONS}
        for f in rec.feedback_ids:
            if f.state == 'submitted' and f.decision in counts:
                counts[f.decision] += 1
        att = rec.transcript_attachment_id
        row.update({
            'scorecard_id': rec.scorecard_id.id or False,
            'scorecard': rec.scorecard_id.name or '',
            'videocall_url': rec.videocall_url or '',
            'decision_counts': counts,
            'invites_pending': bool(rec.invites_pending),
            # Hiring team only: IV_PUBLIC (P4) leaves these out of every
            # payload for anybody else.
            'transcript_url': rec.transcript_url or '',
            'transcript_file': {'id': att.id, 'name': att.name or '',
                                'url': '/web/content/%s?download=true' % att.id} if att else None,
            'feedback_rows': [{
                'id': f.id, 'who': f.panel_employee_id.sudo().name or '',
                'state': f.state, 'decision': f.decision or '',
                'late': bool(f.state == 'pending' and f.due_at
                             and f.due_at < fields.Datetime.now()),
                'entered': f._entered_words(),
            } for f in rec.feedback_ids.sorted('id') if f.state != 'expired'],
        })
        return row

    @api.model
    def get_board(self, limit=None):
        board = super().get_board(limit=limit)
        if not self._hiring_group():
            # The transcript slot is the hiring team's (G-30): a panellist's
            # own Interviews list never carries it.
            for row in board.get('interviews') or []:
                row.pop('transcript_url', None)
                row.pop('transcript_file', None)
        return board

    # =====================================================================
    #  The drawer: opinions hidden between panellists until all are in
    # =====================================================================
    @api.model
    def get_candidate(self, applicant_id):
        res = super().get_candidate(applicant_id)
        if res.get('can_recruit'):
            res['google'] = self._google_state()
            return res
        # Somebody outside the hiring team who sat on a panel sees the
        # others' answers only once everybody is in (G-32).
        me = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)])
        for block in res.get('scorecards') or []:
            block.pop('transcript', None)
            iv = self.env['pb.hiring.interview'].sudo().browse(block['interview_id'])
            mine = iv.feedback_ids.filtered(lambda f: f.panel_employee_id in me)
            if not mine or block.get('in', 0) >= block.get('total', 0):
                continue
            for row in block['rows']:
                if row['id'] in mine.ids:
                    continue
                row.update({'hidden': True, 'answers': {}, 'legacy': [], 'notes': '',
                            'decision': '', 'decision_label': '', 'verdict': '',
                            'score': 0})
            block['hidden_note'] = _("The other answers stay hidden until everyone is in.")
        return res

    # =====================================================================
    #  Enter it for them
    # =====================================================================
    @api.model
    def get_feedback_form(self, feedback_id):
        row = self.env['pb.hiring.feedback'].sudo().browse(as_id(feedback_id)).exists()
        if not row:
            raise UserError(_("That opinion is no longer being asked for."))
        self._require_recruit(row.requisition_id)
        iv = row.interview_id
        card = row._ensure_scorecard()
        return {
            'id': row.id, 'who': row.panel_employee_id.name or '',
            'candidate': iv.candidate_name or '', 'round_no': iv.round_no or 1,
            'scorecard': card.name if card else '', 'intro': card.intro or '' if card else '',
            'parts': row.parts_for_page(), 'state': row.state,
            'decision': row.decision or '', 'notes': row.notes or '',
            'decisions': [{'key': k, 'label': v} for k, v in DECISIONS],
            'link': row._token_url(),
        }

    def _act_feedback_proxy(self, payload):
        row = self.env['pb.hiring.feedback'].sudo().browse(
            as_id(payload.get('feedback_id'))).exists()
        if not row:
            raise UserError(_("That opinion is no longer being asked for."))
        self._require_recruit(row.requisition_id)
        if row.state != 'pending':
            raise UserError(_("%s has already answered. Their own answer stays.",
                              row.panel_employee_id.name or _('They')))
        source = (payload.get('source') or '').strip()
        if not source:
            raise UserError(_("Say where it came from — a Slack message, a call, an email."))
        row.submit_answers(payload.get('answers') or {}, payload.get('decision'),
                           notes=payload.get('notes'), by_user=self.env.user, via=source)
        return {'id': row.id,
                'note': _("Saved for %(who)s — %(how)s.",
                          who=row.panel_employee_id.name or '',
                          how=row._entered_words())}

    # =====================================================================
    #  The transcript slot (hiring team only)
    # =====================================================================
    def _transcript_interview(self, payload):
        iv = self.env['pb.hiring.interview'].sudo().browse(
            as_id(payload.get('interview_id'))).exists()
        if not iv:
            raise UserError(_("That interview is no longer there."))
        if not self._is_hiring_reader(iv.requisition_id):
            raise AccessError(_("The recording and transcript are for the hiring team."))
        return iv

    def _act_transcript_set(self, payload):
        iv = self._transcript_interview(payload)
        url = (payload.get('url') or '').strip()
        if url and not url.lower().startswith(('https://', 'http://')):
            raise UserError(_("Paste the full link, starting with https://"))
        before = iv.transcript_url or ''
        iv.write({'transcript_url': url or False})
        return {'id': iv.id, 'before': before,
                'note': _("Transcript link saved. Only the hiring team sees it.") if url
                else _("Transcript link removed.")}

    def _act_transcript_file(self, payload):
        iv = self._transcript_interview(payload)
        data = payload.get('data') or ''
        name = (payload.get('name') or 'transcript').strip()[:120]
        if not data:
            raise UserError(_("The file did not arrive. Try it again."))
        raw = base64.b64decode(data)
        if len(raw) > TRANSCRIPT_MAX_BYTES:
            raise UserError(_("That file is bigger than 15 MB. Paste the link to it instead."))
        att = self.env['ir.attachment'].sudo().create({
            'name': name, 'raw': raw, 'res_model': 'pb.hiring.interview', 'res_id': iv.id})
        iv.write({'transcript_attachment_id': att.id})
        return {'id': iv.id, 'note': _("Transcript file saved. Only the hiring team sees it.")}

    def _act_transcript_clear_file(self, payload):
        iv = self._transcript_interview(payload)
        iv.write({'transcript_attachment_id': False})
        return {'id': iv.id, 'note': _("Transcript file removed from the interview.")}

    # =====================================================================
    #  Scheduling: the scorecard and the video line in the dialog
    # =====================================================================
    @api.model
    def get_schedule_defaults(self, applicant_id, step_id=None, mode=None):
        app = self._applicant(applicant_id)
        req = app.pb_requisition_id.sudo()
        self._require_recruit(req)
        step = self.env['pb.hiring.step'].sudo().browse(as_id(step_id)).exists()
        card = req._pb_scorecard_for(step=step or None,
                                     stage_key=app.stage_id.pb_key or '') if req else False
        Card = self.env['pb.hiring.scorecard'].sudo()
        cards = Card.search([('company_id', '=', (req.company_id or self.env.company).id)])
        organiser = req.recruiter_id or self.env.user
        connected = self.env['pb.hiring.interview']._pb_google_connected(organiser) \
            if hasattr(self.env['pb.hiring.interview'], '_pb_google_connected') else False
        return {
            'scorecard_id': card.id if card else False,
            'scorecards': [{'id': c.id, 'name': c.name or '',
                            'family': dict(SCORECARD_FAMILIES).get(c.family, '')} for c in cards],
            'google': {'connected': bool(connected), 'organiser': organiser.name or '',
                       'mine': organiser.id == self.env.uid},
        }

    def _act_interview_scorecard(self, payload):
        iv = self._interview(payload)
        self._require_recruit(iv.requisition_id)
        card = iv.sudo()._pb_set_scorecard(payload.get('scorecard_id'))
        return {'id': iv.id, 'note': _("This interview uses %s now.", card.name)}

    # =====================================================================
    #  The role's rounds and their scorecards (G-18)
    # =====================================================================
    @api.model
    def get_requisition(self, requisition_id):
        row = super().get_requisition(requisition_id)
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id))
        if self._is_hiring_reader(req):
            row['rounds'] = self._safe(lambda: req._pb_rounds(), default=[])
            row['scorecard_family'] = req.scorecard_family or ''
            row['role_families'] = [{'key': k, 'label': v} for k, v in ROLE_FAMILIES]
            row['scorecard_choices'] = self._safe(lambda: [
                {'id': c.id, 'name': c.name or '',
                 'family': dict(SCORECARD_FAMILIES).get(c.family, ''),
                 'applies': dict(SCORECARD_ROUNDS).get(c.applies_to, '')}
                for c in self.env['pb.hiring.scorecard'].sudo().search(
                    [('company_id', '=', req.company_id.id)])], default=[])
            row['finalists_count'] = self._safe(lambda: len(self._finalist_apps(req)), default=0)
            row['google'] = self._safe(lambda: self._google_state(req.recruiter_id), default={})
        return row

    def _act_role_family(self, payload):
        req = self._get(payload)
        self._require_write()
        key = payload.get('family') or False
        if key and key not in dict(ROLE_FAMILIES):
            raise UserError(_("That is not one of the kinds of role."))
        before = req.scorecard_family or ''
        req.sudo().write({'scorecard_family': key})
        return {'id': req.id, 'before': before,
                'note': _("Rounds without their own pick now use the %s scorecards.",
                          dict(ROLE_FAMILIES).get(key, '')) if key
                else _("Rounds without their own pick use the company default.")}

    def _act_round_scorecard(self, payload):
        req = self._get(payload)
        self._require_write()
        step = self.env['pb.hiring.step'].sudo().browse(as_id(payload.get('step_id'))).exists()
        if step and step.requisition_id != req.sudo():
            raise UserError(_("That round belongs to another role."))
        if not step:
            step = req.sudo()._pb_round_step(payload.get('stage_key'))
        before = step.scorecard_id.id or False
        card = self.env['pb.hiring.scorecard'].sudo().browse(as_id(payload.get('scorecard_id'))).exists()
        step.write({'scorecard_id': card.id or False})
        return {'id': req.id, 'step_id': step.id, 'before': before,
                'note': _("%(round)s uses %(card)s.", round=step.name or '', card=card.name)
                if card else _("%s goes back to the role's own rule.", step.name or '')}

    # =====================================================================
    #  Hiring set-up: Scorecards, scheduling links, Google
    # =====================================================================
    @api.model
    def get_setup(self):
        res = super().get_setup()
        co_ids = self.env.companies.ids or [self.env.company.id]
        Card = self.env['pb.hiring.scorecard'].sudo()
        cards = Card.search([('company_id', 'in', co_ids)])
        steps = self.env['pb.hiring.step'].sudo().search(
            [('scorecard_id', 'in', cards.ids), ('requisition_id.state', '!=', 'closed')])
        used = {}
        for st in steps:
            used[st.scorecard_id.id] = used.get(st.scorecard_id.id, 0) + 1
        ivs = self.env['pb.hiring.interview'].sudo()._read_group(
            [('scorecard_id', 'in', cards.ids)], ['scorecard_id'], ['__count'])
        iv_used = {g[0].id: g[1] for g in ivs}
        res['scorecards'] = {
            'cards': [dict(c._payload(), rounds_using=used.get(c.id, 0),
                           interviews=iv_used.get(c.id, 0)) for c in cards],
            'families': [{'key': k, 'label': v} for k, v in SCORECARD_FAMILIES],
            'rounds': [{'key': k, 'label': v} for k, v in SCORECARD_ROUNDS],
            'kinds': [{'key': k, 'label': v} for k, v in SCORECARD_PART_KINDS],
            'decisions': [{'key': k, 'label': v} for k, v in DECISIONS],
        }
        status = _("%(n)s scorecards · %(names)s", n=len(cards),
                   names=', '.join(cards[:5].mapped('name')))
        for card in res.get('cards', []):
            if card['key'] == 'scorecards':
                card.update({'status': status if cards else
                             _("No scorecards yet. Add the first one below."),
                             'action': False, 'live': True})
        res['links'] = self._safe(self._links_payload, default=[])
        res['google'] = self._google_state()
        return res

    @api.model
    def _links_payload(self):
        """The recruiters (and the reader), each with their scheduling link
        and whether their Google Calendar is connected."""
        group = self.env.ref(GROUP_USER, raise_if_not_found=False)
        users = group.sudo().all_user_ids.filtered(
            lambda u: u.active and not u.share and self.env.company in u.company_ids) \
            if group else self.env['res.users']
        users |= self.env.user
        Iv = self.env['pb.hiring.interview']
        return sorted([{
            'id': u.id, 'name': u.name or '', 'link': u.sudo().pb_scheduling_link or '',
            'me': u.id == self.env.uid, 'google': bool(Iv._pb_google_connected(u)),
        } for u in users[:80]], key=lambda r: (not r['me'], r['name'].lower()))

    @api.model
    def _google_state(self, user=None):
        """Is Google set up for the company, and is this person connected?"""
        user = user or self.env.user
        ICP = self.env['ir.config_parameter'].sudo()
        ready = bool(ICP.get_param('google_calendar_client_id')) and \
            bool(ICP.get_param('google_calendar_client_secret'))
        return {
            'ready': ready,
            'connected': bool(self.env['pb.hiring.interview']._pb_google_connected(user)),
            'who': user.name or '',
            'mine': user.id == self.env.uid,
            'can_set_up': self.env.user.has_group('base.group_system'),
            'sentence': '' if ready else _(
                "Google Calendar is not set up for this company yet. An administrator "
                "pastes the Google client id and secret in General settings."),
        }

    def _act_google_connect(self, payload):
        """The standard Google consent page for the PERSON PRESSING (a
        connection is always somebody's own Google account)."""
        state = self._google_state()
        if not state['ready']:
            raise UserError(state['sentence'])
        from odoo.addons.google_calendar.utils.google_calendar import GoogleCalendarService
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        back = payload.get('from_url') or (base + '/bizapp/action-pb_hiring.action_pb_hiring_setup')
        service = GoogleCalendarService(self.env['google.service'].with_context(base_url=base))
        return {'url': service._google_authentication_url(from_url=back)}

    def _act_google_settings(self, payload):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("General settings are for an administrator."))
        action = self.env['ir.actions.actions']._for_xml_id('base_setup.action_general_configuration')
        return action

    def _act_scheduling_link_set(self, payload):
        user = self.env['res.users'].sudo().browse(as_id(payload.get('user_id')) or self.env.uid).exists()
        if not user:
            raise UserError(_("That person is no longer here."))
        if user.id != self.env.uid:
            self._require_write()
        link = (payload.get('link') or '').strip()
        before = user.pb_scheduling_link or ''
        user.write({'pb_scheduling_link': link or False})
        mine = user.id == self.env.uid
        return {'user_id': user.id, 'before': before,
                'note': (_("Your scheduling link is saved. Recruiter review sends it from now on.")
                         if mine else _("%s's scheduling link is saved.", user.name)) if link
                else _("Scheduling link removed.")}

    def _act_open_my_link(self, payload):
        view = self.env.ref('pb_hiring.view_users_scheduling_link', raise_if_not_found=False)
        return {'type': 'ir.actions.act_window', 'res_model': 'res.users',
                'res_id': self.env.uid, 'target': 'new', 'name': _('Your scheduling link'),
                'views': [[view.id if view else False, 'form']]}

    # ----------------------------------------------- the scorecard editor
    def _card_of(self, payload, key='scorecard_id'):
        self._require_write()
        card = self.env['pb.hiring.scorecard'].sudo().with_context(active_test=False).browse(
            as_id(payload.get(key) or payload.get('id'))).exists()
        if not card:
            raise UserError(_("That scorecard is no longer there."))
        return card

    def _act_scorecard_save(self, payload):
        card = self._card_of(payload)
        vals, before = {}, {}
        for fname in ('name', 'intro', 'family', 'applies_to'):
            if fname in payload:
                before[fname] = card[fname] or ''
                vals[fname] = (payload[fname] or '').strip() if fname in ('name', 'intro') \
                    else payload[fname]
        if 'name' in vals and not vals['name']:
            raise UserError(_("A scorecard needs a name."))
        if vals.get('family') and vals['family'] not in dict(SCORECARD_FAMILIES):
            raise UserError(_("That is not one of the kinds of role."))
        if vals.get('applies_to') and vals['applies_to'] not in dict(SCORECARD_ROUNDS):
            raise UserError(_("That is not one of the rounds."))
        if payload.get('is_default'):
            card.search([('company_id', '=', card.company_id.id), ('id', '!=', card.id)]).write(
                {'is_default': False})
            vals['is_default'] = True
        card.write(vals)
        return {'id': card.id, 'before': before,
                'note': _("%s is the company default now.", card.name) if payload.get('is_default')
                else _("Saved.")}

    def _act_scorecard_new(self, payload):
        self._require_write()
        Card = self.env['pb.hiring.scorecard'].sudo()
        src = Card.browse(as_id(payload.get('copy_of'))).exists()
        if src:
            card = src.copy({'name': _('%s (copy)', src.name), 'seed_key': False,
                             'is_default': False})
        else:
            card = Card.create({
                'name': (payload.get('name') or '').strip() or _('New scorecard'),
                'company_id': self.env.company.id, 'family': payload.get('family') or 'other',
                'applies_to': 'any_round',
                'part_ids': [(0, 0, {'sequence': 10, 'kind': 'rating', 'prompt': _('Overall'),
                                     'required': True}),
                             (0, 0, {'sequence': 20, 'kind': 'text', 'prompt': _('What stood out')})]})
        return {'id': card.id, 'note': _("%s is ready to edit.", card.name)}

    def _act_scorecard_archive(self, payload):
        card = self._card_of(payload)
        on = bool(payload.get('restore'))
        if not on and card.is_default:
            raise UserError(_("This is the company default. Make another one the default first."))
        card.write({'active': on})
        return {'id': card.id, 'note': _("%s is back.", card.name) if on
                else _("%s is put away. Rounds that used it fall back to the role's rule.", card.name)}

    def _act_scorecard_part_save(self, payload):
        part = self.env['pb.hiring.scorecard.part'].sudo().browse(as_id(payload.get('part_id'))).exists()
        if not part:
            raise UserError(_("That question is no longer there."))
        self._card_of({'id': part.scorecard_id.id})
        vals, before = {}, {}
        for fname in ('prompt', 'help', 'kind', 'required'):
            if fname in payload:
                before[fname] = part[fname]
                vals[fname] = payload[fname]
        if 'prompt' in vals:
            vals['prompt'] = (vals['prompt'] or '').strip()
            if not vals['prompt']:
                raise UserError(_("A question needs words."))
            if len(vals['prompt']) > 160:
                raise UserError(_("Keep a question under 160 characters."))
        if 'help' in vals:
            vals['help'] = (vals['help'] or '').strip()[:200] or False
        if vals.get('kind') and vals['kind'] not in dict(SCORECARD_PART_KINDS):
            raise UserError(_("That is not one of the kinds of question."))
        if 'required' in vals:
            vals['required'] = bool(vals['required'])
        part.write(vals)
        return {'id': part.id, 'before': before, 'note': _("Saved.")}

    def _act_scorecard_part_add(self, payload):
        card = self._card_of(payload)
        kind = payload.get('kind') or 'rating'
        if kind not in dict(SCORECARD_PART_KINDS):
            raise UserError(_("That is not one of the kinds of question."))
        last = max(card.part_ids.mapped('sequence') or [0])
        default = {'text': _('What stood out'), 'rating': _('A new rating'),
                   'line': _('A new scored line'), 'yes_no': _('A yes or no question')}[kind]
        part = self.env['pb.hiring.scorecard.part'].sudo().create({
            'scorecard_id': card.id, 'kind': kind, 'sequence': last + 10,
            'prompt': (payload.get('prompt') or '').strip() or default})
        return {'id': part.id, 'note': _("Question added. Click it to change the words.")}

    def _act_scorecard_part_remove(self, payload):
        part = self.env['pb.hiring.scorecard.part'].sudo().browse(as_id(payload.get('part_id'))).exists()
        if not part:
            raise UserError(_("That question is no longer there."))
        card = self._card_of({'id': part.scorecard_id.id})
        if len(card.part_ids) <= 1:
            raise UserError(_("A scorecard needs at least one question besides the decision."))
        saved = {'scorecard_id': card.id, 'kind': part.kind, 'prompt': part.prompt,
                 'help': part.help or '', 'required': part.required, 'sequence': part.sequence}
        part.unlink()
        return {'saved': saved, 'note': _("Question removed. Answers already given keep it.")}

    def _act_scorecard_part_restore(self, payload):
        saved = payload.get('saved') or {}
        card = self._card_of({'id': saved.get('scorecard_id')})
        part = self.env['pb.hiring.scorecard.part'].sudo().create({
            'scorecard_id': card.id, 'kind': saved.get('kind') or 'text',
            'prompt': saved.get('prompt') or _('Question'), 'help': saved.get('help') or False,
            'required': bool(saved.get('required')), 'sequence': saved.get('sequence') or 10})
        return {'id': part.id, 'note': _("Question is back.")}

    def _act_scorecard_reorder(self, payload):
        card = self._card_of(payload)
        ids = [as_id(i) for i in payload.get('ids') or []]
        parts = card.part_ids
        before = parts.sorted(lambda p: (p.sequence, p.id)).ids
        order = {pid: n for n, pid in enumerate(ids)}
        for p in parts:
            if p.id in order:
                p.write({'sequence': (order[p.id] + 1) * 10})
        return {'id': card.id, 'before': before, 'note': _("New order saved.")}

    # =====================================================================
    #  Finalists side by side (G-38)
    # =====================================================================
    @api.model
    def _finalist_apps(self, req):
        if not req.job_id:
            return self.env['hr.applicant']
        return self.env['hr.applicant'].sudo().search([
            ('job_id', '=', req.job_id.id), ('active', '=', True),
            ('stage_id.pb_key', 'in', FINALIST_KEYS)], limit=40)

    @api.model
    def get_finalists(self, requisition_id):
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id)).exists()
        if not req:
            raise UserError(_("That role is no longer there."))
        if not self._is_hiring_reader(req):
            raise AccessError(_("Comparing finalists is for the hiring team."))
        labels = dict(DECISIONS)
        apps = self._finalist_apps(req)
        ivs = self.env['pb.hiring.interview'].sudo().search([
            ('applicant_id', 'in', apps.ids),
            ('state', 'not in', ('cancelled', 'rescheduled'))], order='round_no, start')
        by_app = {}
        for iv in ivs:
            by_app.setdefault(iv.applicant_id.id, []).append(iv)
        rounds = {}
        cands = []
        for app in apps:
            out_rounds = []
            scores, counts, inn, total = [], {k: 0 for k in labels}, 0, 0
            for iv in by_app.get(app.id, []):
                n = iv.round_no or 1
                label = iv.scorecard_id.name or dict(STEP_KINDS).get(iv.kind, '') or _('Round %s', n)
                rounds.setdefault(n, label)
                ops = []
                for f in iv.feedback_ids.sorted('id'):
                    if f.state == 'expired':
                        continue
                    total += 1
                    if f.state == 'submitted':
                        inn += 1
                        if f.score_avg:
                            scores.append(f.score_avg)
                        if f.decision in counts:
                            counts[f.decision] += 1
                    ops.append({'id': f.id, 'who': f.panel_employee_id.name or '',
                                'state': f.state, 'decision': f.decision or '',
                                'decision_label': labels.get(f.decision, ''),
                                'score': round(f.score_avg or 0.0, 1),
                                'notes': (f.notes or '')[:600],
                                'entered': f._entered_words(),
                                'late': bool(f.state == 'pending' and f.due_at
                                             and f.due_at < fields.Datetime.now())})
                out_rounds.append({'round_no': n, 'interview_id': iv.id, 'label': label,
                                   'when': str(iv.start or ''), 'state': iv.state,
                                   'opinions': ops})
            cands.append({
                'id': app.id, 'name': app.partner_name or app.email_from or _('Candidate'),
                'stage': app.stage_id.name or '', 'stage_key': app.stage_id.pb_key or '',
                'selected': app.id == req.selected_applicant_id.id,
                'avg': round(sum(scores) / len(scores), 1) if scores else 0.0,
                'decision_counts': counts, 'in': inn, 'total': total,
                'rounds': out_rounds,
                'source': app.source_id.name or '',
            })
        cands.sort(key=lambda c: (not c['selected'], -c['avg'], c['name'].lower()))
        return {
            'requisition_id': req.id, 'role': req.title or '',
            'candidates': cands,
            'rounds': [{'round_no': n, 'label': rounds[n]} for n in sorted(rounds)],
            'can_decide': bool(self._can_move(req)),
            'selected_id': req.selected_applicant_id.id or False,
            'decisions': [{'key': k, 'label': v} for k, v in DECISIONS],
        }

    def _act_finalist_decide(self, payload):
        """Choose / Keep warm / Not this time, one click per column. No gate
        on missing opinions (RC-D5): the grid shows "2 of 3 in" and the
        decision is the recruiter's."""
        app = self._applicant(payload.get('applicant_id'), for_move=True)
        req = app.pb_requisition_id.sudo()
        decision = payload.get('decision')
        if decision not in FINALIST_MOVES:
            raise UserError(_("Choose, keep warm or not this time."))
        note = (payload.get('note') or '').strip()
        prev = req.selected_applicant_id.id or False
        move = {'applicant_ids': [app.id], 'key': FINALIST_MOVES[decision]}
        if decision == 'warm':
            move['reason'] = note or _("Kept warm from the finalists.")
            move['hold_until'] = payload.get('hold_until') or False
        if decision == 'no':
            move['reason'] = note or False
            move['send_email'] = bool(payload.get('send_email'))
        res = self._act_journey_stage(move)
        name = app.partner_name or ''
        if decision == 'choose':
            req.write({'selected_applicant_id': app.id})
            final = self.env['pb.hiring.interview'].sudo().search([
                ('applicant_id', '=', app.id), ('state', 'in', ('scheduled', 'done')),
                ('decision', '=', False)], order='round_no desc, start desc', limit=1)
            if final and final.kind in ('final', 'panel'):
                final.write({'decision': 'select', 'decided_on': fields.Datetime.now(),
                             'debrief_notes': note or False})
            req.message_post(body=_("%(who)s is the one, chosen from the finalists side by side.",
                                    who=name))
            app.message_post(body=Markup('<p>%s</p>') % _("Chosen from the finalists side by side."),
                             message_type='comment', subtype_xmlid='mail.mt_note')
            res['note'] = _("%s is the one · moved to Offer", name)
        elif decision == 'warm':
            res['note'] = _("%s is kept warm (On hold)", name)
        res.update({'prev_selected_id': prev, 'decision': decision, 'applicant_id': app.id})
        return res

    def _act_finalist_undo(self, payload):
        app = self._applicant(payload.get('applicant_id'), for_move=True)
        req = app.pb_requisition_id.sudo()
        res = {'moved': [], 'note': _("Undone.")}
        if payload.get('from_key'):
            res = self._act_journey_stage({'applicant_ids': [app.id], 'key': payload['from_key'],
                                           'undo': True})
        if payload.get('decision') == 'choose' and req.selected_applicant_id.id == app.id:
            req.write({'selected_applicant_id': as_id(payload.get('prev_selected_id')) or False})
            final = self.env['pb.hiring.interview'].sudo().search([
                ('applicant_id', '=', app.id), ('decision', '=', 'select')],
                order='decided_on desc', limit=1)
            if final:
                final.write({'decision': False, 'decided_on': False})
        return res


class HiringApplicantScheduling(models.Model):
    _inherit = 'hr.applicant'

    pb_scheduling_sent_at = fields.Datetime(
        string='Scheduling link sent', readonly=True, copy=False,
        help='When the "Let\'s chat" email with the recruiter\'s scheduling link went.')
