# -*- coding: utf-8 -*-
"""RECRUIT phase 1 — the role board, Rize's stages, the non-blocking rule.

WHAT THIS FILE ADDS, in the order a recruiter meets it:

  * **Presets** (`pb.hiring.stage.preset`): which columns a NEW role shows,
    by department and country. Matching: department + country, then
    department, then country, then the company's Standard preset.
  * **A role's own columns** (`pb_visible_stage_ids` on the hiring request —
    RC-D6: the request record IS the role). Filled from the preset on
    create, never stored empty, and never touched again by a preset change.
  * **The board payload**: `get_requisition` gains the role's stages with
    counts and typical days, the closed rail's counts, the per-role quiet
    numbers and a richer card per candidate.
  * **Moving** (`journey_stage`): bulk, in any direction, no reason demanded,
    Undo by calling it back with the `from_key`s it returned. Joined is the
    only column a card cannot be dropped on — it is set from the offer.
  * **Who moves** (RC-D1): recruiters (and anyone covering one of the
    role's recruiter) and the talent lead. A line manager reads the board and
    leaves notes; the set-up switch that widens this ships OFF.
  * **The candidate drawer** (`get_candidate`, `get_timeline`): the Next box
    computed from the record, the story of the person newest first.
  * **Hiring set-up** (`get_setup` and its verbs) for the talent lead.

Every read that crosses a boundary a plain user cannot cross (a line manager
has no read on candidates) checks the ROLE first, as the user, and then reads
the candidates as the system with the role written into the domain — the
doctrine this module already uses for covers (R89, R157).
"""

import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext

from .hiring_common import (
    GROUP_ADMIN, GROUP_MANAGER, GROUP_USER, P_CANDIDATE_MAIL,
    P_LINE_MANAGERS_MOVE, SCREEN_TAGS, as_id, flag, leg,
)
from .journey import ALWAYS_ON, FAMILY, HIDDEN_BY_DEFAULT, OUTCOMES

_logger = logging.getLogger(__name__)

#: How many candidates one role's board reads. A column shows 30 and offers
#: "Show 40 more"; the cap is what keeps a 2,000-applicant role a slow screen
#: rather than a broken one.
BOARD_CANDIDATES = 600

#: The switches the set-up page may flip. A whitelist: the page is not a
#: general editor of system parameters.
SWITCHES = {
    'candidate_mail': P_CANDIDATE_MAIL,
    'line_managers_move': P_LINE_MANAGERS_MOVE,
}


# =========================================================================
#  Presets
# =========================================================================
class PbHiringStagePreset(models.Model):
    _name = 'pb.hiring.stage.preset'
    _description = 'Which columns a new role shows'
    _order = 'is_standard desc, sequence, id'

    name = fields.Char(string='Name', required=True, translate=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    department_id = fields.Many2one('hr.department', string='Department',
                                    index=True, ondelete='cascade')
    country_id = fields.Many2one('res.country', string='Country', index=True)
    stage_ids = fields.Many2many(
        'hr.recruitment.stage', 'pb_hiring_preset_stage_rel', 'preset_id',
        'stage_id', string='Columns it shows')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_standard = fields.Boolean(
        string='Standard', readonly=True,
        help='The company\'s fallback when no department or country matches.')

    @api.model
    def _standard_stages(self):
        Stage = self.env['hr.recruitment.stage'].sudo()
        return Stage.search([('pb_family', '=', 'open')], order='sequence,id') \
            .filtered(lambda s: s.pb_key not in HIDDEN_BY_DEFAULT)

    @api.model
    def _ensure_standard(self):
        """One Standard preset per company. Idempotent; never overwrites a
        Standard preset somebody has already edited."""
        Preset = self.sudo().with_context(active_test=False)
        made = 0
        stages = self._standard_stages()
        for company in self.env['res.company'].sudo().search([]):
            if Preset.search_count([('company_id', '=', company.id),
                                    ('is_standard', '=', True)]):
                continue
            Preset.create({'name': 'Standard', 'company_id': company.id,
                           'is_standard': True, 'sequence': 0,
                           'stage_ids': [(6, 0, stages.ids)]})
            made += 1
        return made

    @api.model
    def _match(self, company, department=None, country=None):
        """department + country, then department, then country, then the
        company's Standard preset — the order the owner's call agreed."""
        Preset = self.sudo()
        company = company or self.env.company
        base = [('company_id', '=', company.id), ('is_standard', '=', False)]
        dep = department.id if department else False
        ctry = country.id if country else False
        tries = []
        if dep and ctry:
            tries.append([('department_id', '=', dep), ('country_id', '=', ctry)])
        if dep:
            tries.append([('department_id', '=', dep), ('country_id', '=', False)])
        if ctry:
            tries.append([('department_id', '=', False), ('country_id', '=', ctry)])
        for extra in tries:
            hit = Preset.search(base + extra, order='sequence,id', limit=1)
            if hit:
                return hit
        return Preset.search([('company_id', '=', company.id),
                              ('is_standard', '=', True)], limit=1)


# =========================================================================
#  A role's own columns
# =========================================================================
class HiringRequestColumns(models.Model):
    _inherit = 'pb.hiring.requisition'

    pb_visible_stage_ids = fields.Many2many(
        'hr.recruitment.stage', 'pb_hiring_req_visible_stage_rel',
        'requisition_id', 'stage_id', string='Columns this role shows',
        help='Filled from the matching preset when the role is created. The '
             'first stages, Offer, Post-offer, Joined and every closed '
             'outcome are always shown whatever this says.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.pb_visible_stage_ids:
                rec.sudo().write({'pb_visible_stage_ids': [
                    (6, 0, rec._pb_default_stage_ids())]})
        return records

    def _pb_default_stage_ids(self):
        """Never empty: the matching preset, else Standard, else every open
        stage."""
        self.ensure_one()
        preset = self.env['pb.hiring.stage.preset']._match(
            self.company_id, self.department_id, self.country_id)
        ids = preset.stage_ids.ids if preset else []
        if not ids:
            ids = self.env['pb.hiring.stage.preset']._standard_stages().ids
        if not ids:
            ids = self.env['hr.recruitment.stage'].sudo().search(
                [('pb_family', '=', 'open')]).ids
        return ids

    @api.model
    def _pb_fill_visible_stages(self):
        """The upgrade half: every existing role with no columns gets them."""
        empty = self.sudo().with_context(active_test=False).search(
            [('pb_visible_stage_ids', '=', False)])
        for rec in empty:
            rec.write({'pb_visible_stage_ids': [
                (6, 0, rec._pb_default_stage_ids())]})
        return len(empty)

    def _pb_board_stages(self):
        """The stages this role's board shows, in order: its own set plus
        everything that is always on."""
        self.ensure_one()
        Stage = self.env['hr.recruitment.stage'].sudo()
        every = Stage.search([('pb_key', '!=', False)], order='sequence,id')
        mine = set(self.sudo().pb_visible_stage_ids.ids)
        return every.filtered(lambda s: s.id in mine or s.pb_always_on)


# =========================================================================
#  The facade
# =========================================================================
class PbHiringBoardP1(models.AbstractModel):
    _inherit = 'pb.hiring'

    # ------------------------------------------------------------ who moves
    @api.model
    def _line_managers_move(self):
        return flag(self.env, P_LINE_MANAGERS_MOVE)

    @api.model
    def _can_move(self, req):
        """RC-D1. A recruiter (or somebody covering this role's recruiter) or
        the talent lead; a line manager only when the switch is on, and only
        on a role the record rules already let them read."""
        if req and self._can_recruit(req):
            return True
        if not req and self._can_recruit():
            return True
        if req and self._line_managers_move() and self._role_readable(req):
            return True
        return False

    @api.model
    def _require_move(self, req):
        if not self._can_move(req):
            raise AccessError(_(
                "Only recruiters and the talent lead move candidates."))
        return True

    @api.model
    def _role_readable(self, req):
        """May THIS user read this role — asked as the user, never the
        system."""
        if not req:
            return False
        try:
            self.env['pb.hiring.requisition'].browse(req.id).check_access('read')
            return True
        except AccessError:
            return False

    @api.model
    def _applicant(self, applicant_id, for_move=False):
        """A candidate, read as the system once the reader has been checked
        against the ROLE: a line manager holds no read on candidates, and the
        board is theirs to read (RC-D1)."""
        app = self.env['hr.applicant'].sudo().with_context(
            active_test=False).browse(as_id(applicant_id)).exists()
        if not app:
            raise UserError(_("This candidate is no longer available."))
        req = app.pb_requisition_id
        if for_move:
            self._require_move(req)
            return app
        user = self.env.user
        if user.has_group(GROUP_USER) or user.has_group(GROUP_MANAGER) \
                or user.has_group(GROUP_ADMIN):
            return app
        if req and (self._can_recruit(req) or self._role_readable(req)):
            return app
        raise AccessError(_(
            "This candidate is on a role you are not part of."))

    # ---------------------------------------------------------------- moving
    def _act_journey_stage(self, payload):
        """Move one or many candidates. No gates but one: Joined is set from
        the offer, never by hand (RC-D5).

        payload: {applicant_ids: [..] | applicant_id, key | stage_id,
                  reason?, hold_until? (update_date accepted), send_email?,
                  undo?}
        returns: {moved: [{id, from_key, from_stage_id, to_key}], note,
                  interview_prompt?: {interview_id, applicant_id, name}}
        """
        Stage = self.env['hr.recruitment.stage']
        ids = payload.get('applicant_ids') or (
            [payload['applicant_id']] if payload.get('applicant_id') else [])
        ids = [as_id(i) for i in ids if as_id(i)]
        if not ids:
            raise UserError(_("Choose at least one candidate to move."))
        stage = Stage._pb_stage(payload.get('key')) if payload.get('key') \
            else Stage.sudo().browse(as_id(payload.get('stage_id'))).exists()
        if not stage or not stage.pb_key:
            raise UserError(_("Choose a hiring stage."))
        if stage.pb_key == 'joined':
            raise UserError(_(
                "Joined is set when you confirm the person started, from "
                "their offer."))
        reason = (payload.get('reason') or '').strip()
        hold = payload.get('hold_until') or payload.get('update_date') or False
        undo = bool(payload.get('undo'))
        now = fields.Datetime.now()
        moved, prompt, mailed = [], None, 0
        for app_id in ids:
            app = self._applicant(app_id, for_move=True)
            was = app.stage_id
            if was.id == stage.id:
                continue
            vals = {'stage_id': stage.id}
            if stage.pb_key in OUTCOMES:
                vals['pb_stage_reason'] = reason or False
            if stage.pb_key == 'on_hold':
                vals['pb_hold_until'] = hold or False
            elif app.pb_hold_until:
                vals['pb_hold_until'] = False
            if stage.pb_family != 'closed' and not app.active:
                # Coming back from a "not this time": they are a candidate
                # again, not an archived refusal in an open column.
                vals.update({'active': True, 'refuse_reason_id': False})
            app.with_context(just_moved=True).write(vals)
            if reason or undo:
                body = _("Moved back to %s (undone).", stage.name) if undo \
                    else _("Moved to %(stage)s. Reason: %(why)s",
                           stage=stage.name, why=reason)
                app.message_post(body=body, message_type='comment',
                                 subtype_xmlid='mail.mt_note')
            moved.append({'id': app.id, 'from_key': was.pb_key or '',
                          'from_stage_id': was.id, 'to_key': stage.pb_key})
            if payload.get('send_email') and stage.pb_key in (
                    'cv_reject', 'interview_reject'):
                if leg(self.env, 'the not-this-time email to %s' % app.id,
                       lambda app=app: app._pb_tell_candidate(
                           'pb_hiring.mail_template_candidate_rejected')):
                    mailed += 1
            if prompt is None and stage.pb_family != 'closed':
                open_iv = self.env['pb.hiring.interview'].sudo().search([
                    ('applicant_id', '=', app.id), ('state', '=', 'scheduled'),
                    ('stop', '<', now)], order='start desc', limit=1)
                if open_iv:
                    prompt = {'interview_id': open_iv.id, 'applicant_id': app.id,
                              'name': app.partner_name or ''}
        if not moved:
            return {'moved': [], 'note': _("Nothing to move — they are already there.")}
        if len(moved) == 1:
            who = self.env['hr.applicant'].sudo().browse(moved[0]['id']).partner_name or _('The candidate')
            note = _("%(who)s moved back to %(stage)s", who=who, stage=stage.name) if undo \
                else _("%(who)s moved to %(stage)s", who=who, stage=stage.name)
        else:
            note = _("%(n)s people moved back to %(stage)s", n=len(moved), stage=stage.name) if undo \
                else _("%(n)s people moved to %(stage)s", n=len(moved), stage=stage.name)
        if mailed:
            note += ' · ' + (_("the not-this-time email went out") if mailed == 1
                             else _("%s not-this-time emails went out", mailed))
        elif payload.get('send_email') and not flag(self.env, P_CANDIDATE_MAIL):
            note += ' · ' + _("candidate emails are switched off, so nothing was sent")
        res = {'moved': moved, 'note': note}
        if prompt:
            res['interview_prompt'] = prompt
        return res

    # --------------------------------------------------------------- a note
    def _act_candidate_note(self, payload):
        """Anybody who can read the role may leave a note — the line
        manager's one write on the board (RC-D1)."""
        app = self._applicant(payload.get('applicant_id'))
        body = (payload.get('body') or '').strip()
        if not body:
            raise UserError(_("Write the note first."))
        app.message_post(body=Markup('<p>%s</p>') % body[:4000],
                         message_type='comment', subtype_xmlid='mail.mt_note')
        return {'id': app.id, 'note': _("Note added.")}

    def _act_remind_opinion(self, payload):
        """"Remind Quang": the urgent chase if it has not gone, otherwise
        their own link on screen to send however the recruiter likes."""
        row = self.env['pb.hiring.feedback'].sudo().browse(
            as_id(payload.get('feedback_id'))).exists()
        if not row:
            raise UserError(_("That opinion is no longer being asked for."))
        self._require_recruit(row.requisition_id)
        who = row.panel_employee_id.name or _('them')
        if row.state != 'pending':
            return {'note': _("%s has already answered.", who)}
        if not row.urgent_sent_at:
            sent = leg(self.env, 'the reminder to %s' % row.id, row._chase)
            if sent is not False:
                return {'note': _("%s has been reminded.", who)}
        return {'link': row._token_url(),
                'note': _("%s was already reminded. Their own link is on screen — send it however you like.", who)}

    def _act_add_candidate(self, payload):
        """The empty board's second door: a new candidate on this role, in
        the full candidate form."""
        req = self._get(payload)
        self._require_recruit(req)
        if not req.job_id:
            raise UserError(_(
                "This role has no job yet, so there is nowhere to add a "
                "candidate. It gets one when the request is agreed."))
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.applicant',
                'view_mode': 'form', 'views': [[False, 'form']],
                'target': 'current', 'name': _('New candidate'),
                'context': {'default_job_id': req.job_id.id,
                            'default_pb_requisition_id': req.id,
                            'default_company_id': req.company_id.id}}

    # --------------------------------------------------------------- the row
    @api.model
    def _row(self, req):
        row = super()._row(req)
        row['funnel'] = self._safe(lambda: self._funnel(req), default=[])
        row['closed_total'] = sum(f['count'] for f in row['funnel']
                                  if f['family'] == 'closed')
        return row

    @api.model
    def _funnel(self, req):
        """The board in miniature, for the home card: one segment per shown
        stage in stage order, and the closed ones summed."""
        if not req.job_id:
            return []
        counts = {}
        rows = self.env['hr.applicant'].sudo().with_context(
            active_test=False).search_read(
                [('job_id', '=', req.job_id.id)], ['stage_id', 'active'],
                limit=2000)
        for r in rows:
            if r['stage_id']:
                counts[r['stage_id'][0]] = counts.get(r['stage_id'][0], 0) + 1
        shown = req._pb_board_stages()
        out = []
        for s in self.env['hr.recruitment.stage'].sudo().search(
                [('pb_key', '!=', False)], order='sequence,id'):
            n = counts.get(s.id, 0)
            if s in shown or n:
                out.append({'key': s.pb_key, 'name': s.name or '',
                            'family': s.pb_family or 'open', 'count': n})
        return out

    @api.model
    def get_board(self, limit=None):
        board = super().get_board(limit=limit)
        if board.get('allowed'):
            board['can_setup'] = self._can_write()
            board['line_managers_move'] = self._line_managers_move()
        return board

    # ------------------------------------------------------ one role, board
    @api.model
    def get_requisition(self, requisition_id):
        row = super().get_requisition(requisition_id)
        req = self.env['pb.hiring.requisition'].sudo().browse(
            as_id(requisition_id))
        row['board'] = self._safe(lambda: self._board(req, row), default={})
        return row

    @api.model
    def _candidates(self, req):
        """The card per candidate. Read as the system: the caller has already
        been let into this role (get_requisition's own gate)."""
        if not req.job_id:
            return []
        req = req.sudo()
        Applicant = self.env['hr.applicant'].sudo().with_context(active_test=False)
        apps = Applicant.search([('job_id', '=', req.job_id.id)],
                                order='date_last_stage_update desc, id desc',
                                limit=BOARD_CANDIDATES)
        ivs = {}
        for rec in self.env['pb.hiring.interview'].sudo().search(
                [('applicant_id', 'in', apps.ids)], order='start desc',
                limit=2000):
            ivs.setdefault(rec.applicant_id.id, []).append(rec)
        docs = {}
        for g in self.env['ir.attachment'].sudo()._read_group(
                [('res_model', '=', 'hr.applicant'), ('res_id', 'in', apps.ids)],
                ['res_id'], ['__count']):
            docs[g[0]] = g[1]
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        can_recruit = self._can_recruit(req)
        out = []
        for app in apps:
            out.append(self._card(app, ivs.get(app.id, []), docs.get(app.id, 0),
                                  req, now, today, can_recruit))
        return out

    @api.model
    def _card(self, app, ivs, doc_count, req, now, today, can_recruit):
        stage = app.stage_id
        key = stage.pb_key or ''
        family = stage.pb_family or 'open'
        if not app.active and family == 'open':
            family = 'closed'           # refused through the old path
        applied = app.create_date or now
        applied_days = max(0, (today - applied.date()).days)
        since = app.date_last_stage_update or applied
        days_here = max(0, (now - since).days)
        touch = app.pb_application_touch or {}
        source = app.source_id.name or (touch.get('source') if isinstance(
            touch, dict) else '') or ''
        referral = app.pb_referral_ids[:1]
        referred_by = referral.employee_id.name if referral else ''
        live = [i for i in ivs if i.state == 'scheduled' and i.start and i.start > now]
        live.sort(key=lambda i: i.start)
        past_open = [i for i in ivs if i.state == 'scheduled' and i.stop and i.stop <= now]
        asked = [i for i in ivs if i.state in ('scheduled', 'done') and i.feedback_total]
        latest = asked[0] if asked else None
        opinions = {'in': latest.feedback_in, 'total': latest.feedback_total,
                    'late': latest.feedback_late} if latest else \
            {'in': 0, 'total': 0, 'late': 0}
        chips, flags, edge, waiting = [], [], '', ''
        week_end = now + timedelta(days=7)
        if live and live[0].start <= week_end:
            flags.append('iv')
        if family == 'open':
            if key == 'screening' and not app.pb_screen:
                chips.append({'label': _('First look'), 'tone': 'amber'})
                flags.append('waiting')
            if past_open:
                chips.append({'label': _('Outcome to log'), 'tone': 'amber'})
                waiting = _("Log how round %s went", past_open[0].round_no or 1)
                edge = 'amber'
                flags.append('waiting')
            elif opinions['late']:
                chips.append({'label': _('%s late', opinions['late']) if opinions['late'] > 1
                              else _('1 opinion late'), 'tone': 'amber'})
                waiting = _("Opinions %(in)s of %(total)s", **{'in': opinions['in'], 'total': opinions['total']})
                edge = 'amber'
                flags.append('late')
            elif latest and opinions['total'] and opinions['in'] < opinions['total'] \
                    and latest.stop and latest.stop <= now:
                chips.append({'label': _('Opinions %(in)s of %(total)s', **{'in': opinions['in'], 'total': opinions['total']}), 'tone': 'info'})
            elif latest and opinions['total'] and opinions['in'] == opinions['total'] \
                    and not live:
                chips.append({'label': _('Ready to decide'), 'tone': 'green'})
            if live:
                chips.append({'label': _('Interview set'), 'tone': 'info'})
            if not edge and (key == 'shortlist' or app.pb_screen == 'shortlisted'):
                edge = 'green'
            if not edge and days_here > 14 and key not in ('offer', 'post_offer'):
                edge = 'rose'
                chips.insert(0, {'label': _('%s days here', days_here), 'tone': 'rose'})
            if key in ('offer', 'post_offer'):
                flags.append('offer')
        elif key == 'on_hold' and app.pb_hold_until:
            chips.append({'label': _('Look again %s', app.pb_hold_until.strftime('%d %b')), 'tone': 'amber'})
        if referred_by:
            chips.append({'label': _('Referred by %s', referred_by), 'tone': ''})
        if app.pb_portfolio:
            chips.append({'label': _('Portfolio'), 'tone': 'info'})
        if applied_days == 0:
            applied_words = _('Applied today')
        elif applied_days == 1:
            applied_words = _('Applied yesterday')
        else:
            applied_words = _('Applied %s days ago', applied_days)
        sub = applied_words + ((' · ' + source) if source else '')
        return {
            'id': app.id,
            'name': app.partner_name or app.email_from or _('Candidate'),
            'email': app.email_from or '',
            'stage': stage.name or '',
            'stage_id': stage.id,
            'stage_key': key,
            'stage_seq': stage.sequence or 0,
            'family': family,
            'active': bool(app.active),
            'applied_on': str(applied.date()),
            'applied_days': applied_days,
            'days_in_stage': days_here,
            'source': source,
            'source_label': source,
            'sub': sub,
            'screen': app.pb_screen or '',
            'screen_label': dict(SCREEN_TAGS).get(app.pb_screen, ''),
            'status': app.application_status or '',
            'waiting': waiting,
            'next_interview_at': str(live[0].start) if live else '',
            'next_interview': self._interview_row(live[0]) if live else None,
            'interviews': [self._interview_row(i) for i in ivs[:6]],
            'rounds': len([i for i in ivs if i.state not in ('cancelled', 'rescheduled')]),
            'opinions': opinions,
            'has_cv': bool(doc_count),
            'shared': '',
            'edge': edge,
            'chips': chips[:2],
            'flags': flags,
            'selected': app.id == req.selected_applicant_id.id,
        }

    @api.model
    def _board(self, req, row):
        """Everything the role page needs beyond the row itself."""
        cards = row.get('candidates_list') or []
        Stage = self.env['hr.recruitment.stage'].sudo()
        every = Stage.search([('pb_key', '!=', False)], order='sequence,id')
        shown = req._pb_board_stages()
        counts = {}
        for c in cards:
            counts[c['stage_id']] = counts.get(c['stage_id'], 0) + 1
        avg = self._safe(lambda: self._avg_days(req, cards), default={})
        stages = [{
            'id': s.id, 'key': s.pb_key, 'name': s.name or '',
            'family': s.pb_family or 'open', 'meaning': s.pb_meaning or '',
            'visible': s in shown, 'always_on': bool(s.pb_always_on),
            'count': counts.get(s.id, 0), 'avg_days': avg.get(s.id),
        } for s in every]
        closed = {s['key']: s['count'] for s in stages if s['family'] == 'closed'}
        can_move = self._can_move(req)
        interviews = self._safe(lambda: self.env['pb.hiring.interview'].sudo().search(
            [('requisition_id', '=', req.id)], order='start', limit=300), default=[])
        iv_rows = [self._interview_row(i) for i in interviews]
        offers_out = self._safe(lambda: len(req.sudo().offer_ids.filtered(
            lambda o: o.state in ('sent', 'accepted', 'signed'))), default=0)
        glance = [
            {'key': 'play', 'n': sum(1 for c in cards if c['family'] == 'open'),
             'label': _('people in play'), 'tone': ''},
            {'key': 'waiting', 'n': sum(1 for c in cards if 'waiting' in c['flags']),
             'label': _('waiting on you'), 'tone': 'amber'},
            {'key': 'iv', 'n': sum(1 for i in iv_rows if i['bucket'] in ('today', 'week')),
             'label': _('interviews this week'), 'tone': ''},
            {'key': 'late', 'n': sum(i['feedback_late'] for i in iv_rows),
             'label': _('opinions late'), 'tone': 'rose'},
            {'key': 'offers', 'n': offers_out, 'label': _('offers out'),
             'tone': 'green'},
        ]
        for g in glance:
            if not g['n']:
                g['tone'] = ''
        request_agreed = req.state in ('open', 'filled')
        return {
            'stages': stages,
            'closed_counts': closed,
            'role_glance': glance,
            'interviews': iv_rows,
            'can_move': can_move,
            'can_setup': self._can_write(),
            'can_note': True,
            'show_money': self._can_recruit(req),
            'request_agreed': request_agreed,
            'total': len(cards),
            'capped': len(cards) >= BOARD_CANDIDATES,
            'activity': self._safe(lambda: self._role_activity(req), default=[]),
        }

    @api.model
    def _avg_days(self, req, cards):
        """Typical days in each stage for THIS role, from the stage log:
        each finished stay, and today's stays where nobody has finished one."""
        if not req.job_id:
            return {}
        logs = self.env['pb.hiring.stage.log'].sudo().search_read(
            [('job_id', '=', req.job_id.id)],
            ['applicant_id', 'to_stage_id', 'at'], order='applicant_id, at',
            limit=5000)
        spans = {}
        prev = None
        for lg in logs:
            if prev and prev['applicant_id'] == lg['applicant_id'] and prev['to_stage_id']:
                days = (lg['at'] - prev['at']).total_seconds() / 86400.0
                spans.setdefault(prev['to_stage_id'][0], []).append(max(0.0, days))
            prev = lg
        current = {}
        for c in cards:
            current.setdefault(c['stage_id'], []).append(c['days_in_stage'])
        out = {}
        for sid in set(spans) | set(current):
            vals = spans.get(sid) or current.get(sid) or []
            if vals:
                out[sid] = round(sum(vals) / len(vals), 1)
        return out

    @api.model
    def _role_activity(self, req):
        """The Activity tab: the last fifty moves on this role, newest first."""
        if not req.job_id:
            return []
        logs = self.env['pb.hiring.stage.log'].sudo().search(
            [('job_id', '=', req.job_id.id)], order='at desc, id desc', limit=50)
        return [{
            'at': str(lg.at or ''),
            'who': lg.applicant_id.partner_name or '',
            'applicant_id': lg.applicant_id.id,
            'from': lg.from_stage_id.name or '',
            'to': lg.to_stage_id.name or '',
            'by': lg.by_user_id.name or '',
        } for lg in logs]

    # --------------------------------------------------------- the drawer
    @api.model
    def get_candidate(self, applicant_id):
        app = self._applicant(applicant_id)
        req = app.pb_requisition_id
        can_recruit = self._can_recruit(req) if req else self._can_recruit()
        can_move = self._can_move(req)
        now = fields.Datetime.now()
        ivs = self.env['pb.hiring.interview'].sudo().search(
            [('applicant_id', '=', app.id)], order='start desc', limit=40)
        docs = self.env['ir.attachment'].sudo().search_read(
            [('res_model', '=', 'hr.applicant'), ('res_id', '=', app.id)],
            ['id', 'name', 'mimetype', 'file_size'], order='id desc', limit=30)
        scorecards = []
        for iv in ivs:
            if not iv.feedback_ids or iv.state in ('cancelled', 'rescheduled'):
                continue
            scorecards.append({
                'interview_id': iv.id, 'round_no': iv.round_no or 1,
                'when': str(iv.start or ''), 'state': iv.state,
                'rows': [{
                    'id': f.id, 'who': f.panel_employee_id.name or '',
                    'state': f.state,
                    'late': bool(f.state == 'pending' and f.due_at and f.due_at < now),
                    'score': round(f.score_avg or 0.0, 1),
                    'verdict': dict(f._fields['recommendation'].selection).get(f.recommendation, ''),
                    'notes': (f.notes or '')[:280],
                } for f in iv.feedback_ids.sorted('id')],
            })
        money = None
        if can_recruit and 'salary_expected' in app._fields:
            proposed = app['salary_proposed'] if 'salary_proposed' in app._fields else 0.0
            money = {'expected': app.salary_expected or 0.0,
                     'proposed': proposed or 0.0,
                     'currency': (app.company_id.currency_id.name or '')}
        touch = app.pb_application_touch if isinstance(app.pb_application_touch, dict) else {}
        linkedin = app.pb_linkedin or (app['linkedin_profile'] if 'linkedin_profile' in app._fields else '') or ''
        return {
            'id': app.id,
            'name': app.partner_name or app.email_from or _('Candidate'),
            'role': (req.title if req else app.job_id.name) or '',
            'requisition_id': req.id or False,
            'stage': app.stage_id.name or '',
            'stage_key': app.stage_id.pb_key or '',
            'family': app.stage_id.pb_family or 'open',
            'active': bool(app.active),
            'applied_on': str((app.create_date or now).date()),
            'source': app.source_id.name or touch.get('source', '') or '',
            'location': app.pb_location or '',
            'email': app.email_from or '',
            'phone': app.partner_phone or '',
            'linkedin': linkedin,
            'portfolio': app.pb_portfolio or '',
            'screen': app.pb_screen or '',
            'screen_label': dict(SCREEN_TAGS).get(app.pb_screen, ''),
            'reason': app.pb_stage_reason or '',
            'hold_until': str(app.pb_hold_until or ''),
            'money': money,
            'can_recruit': bool(can_recruit),
            'can_move': bool(can_move),
            'next': self._next_box(app, ivs, can_recruit),
            'scorecards': scorecards,
            'documents': [{'id': d['id'], 'name': d['name'] or '',
                           'mimetype': d['mimetype'] or '',
                           'url': '/web/content/%s' % d['id']} for d in docs]
            if can_recruit else [],
            'doc_count': len(docs),
            'interviews': [self._interview_row(i) for i in ivs[:10]],
            'timeline': self.get_timeline(app.id),
        }

    @api.model
    def _next_box(self, app, ivs, can_recruit):
        """ONE sentence and, only when the move is the reader's, one button.

        {text, verb?, label?, payload?, secondary?: {verb,label,payload}}
        """
        now = fields.Datetime.now()
        key = app.stage_id.pb_key or ''
        family = app.stage_id.pb_family or 'open'
        name = (app.partner_name or '').split(' ')[-1] or _('them')
        if family == 'closed' or not app.active:
            when = (app.date_last_stage_update or now).strftime('%d %b')
            if key == 'on_hold' and app.pb_hold_until:
                return {'text': _("On hold until %s. Look again then, or move them back now.",
                                  app.pb_hold_until.strftime('%d %b'))}
            return {'text': _("Closed as %(stage)s on %(when)s. Drag them back if that was a mistake.",
                              stage=app.stage_id.name or '', when=when)}
        if family == 'done':
            return {'text': _("Joined. Their first days carry on under New joiners.")}
        past_open = ivs.filtered(lambda i: i.state == 'scheduled' and i.stop and i.stop <= now)
        if past_open:
            iv = past_open[0]
            box = {'text': _("Round %(n)s was on %(when)s. Log how it went.",
                             n=iv.round_no or 1, when=iv.start.strftime('%a %d %b'))}
            if can_recruit:
                box.update({'verb': 'mark_done', 'label': _('It happened'),
                            'payload': {'interview_id': iv.id},
                            'secondary': {'verb': 'no_show_open', 'label': _('Nobody came'),
                                          'payload': {'interview_id': iv.id}}})
            return box
        late = self.env['pb.hiring.feedback'].sudo().search([
            ('interview_id', 'in', ivs.ids), ('state', '=', 'pending'),
            ('due_at', '<', now)], order='due_at', limit=1)
        if late:
            iv = late.interview_id
            who = late.panel_employee_id.name or _('someone')
            box = {'text': _("Round %(n)s happened on %(when)s. %(in)s of %(total)s opinions are in; %(who)s's is late.",
                             n=iv.round_no or 1, when=iv.start.strftime('%a %d %b'),
                             who=who, **{'in': iv.feedback_in, 'total': iv.feedback_total})}
            if can_recruit:
                box.update({'verb': 'remind_opinion', 'label': _('Remind %s', who.split(' ')[-1]),
                            'payload': {'feedback_id': late.id}})
            return box
        live = ivs.filtered(lambda i: i.state == 'scheduled' and i.start and i.start > now)
        if live:
            iv = live.sorted('start')[0]
            panel = ', '.join(iv.panel_employee_ids.sudo().mapped('name')) or _('the panel')
            return {'text': _("Round %(n)s is on %(when)s with %(panel)s.",
                              n=iv.round_no or 1, when=iv.start.strftime('%a %d %b, %H:%M'),
                              panel=panel)}
        pending = ivs.filtered(lambda i: i.state == 'done' and i.feedback_in < i.feedback_total)
        if pending:
            iv = pending[0]
            return {'text': _("Round %(n)s is done; %(in)s of %(total)s opinions are in. The reminders keep going.",
                              n=iv.round_no or 1, **{'in': iv.feedback_in, 'total': iv.feedback_total})}
        if key == 'screening' and not app.pb_screen:
            box = {'text': _("Give %s a first look: shortlist them, or not this time.", name)}
            if can_recruit:
                box.update({'verb': 'screen', 'label': _('Shortlist'),
                            'payload': {'applicant_id': app.id, 'tag': 'shortlisted'},
                            'secondary': {'verb': 'screen', 'label': _('CV reject'),
                                          'payload': {'applicant_id': app.id, 'tag': 'rejected'}}})
            return box
        if key in ('offer', 'post_offer'):
            req = app.pb_requisition_id
            if key == 'offer':
                if req and req.state not in ('open', 'filled'):
                    return {'text': _("The request for this role is not agreed yet, so the offer cannot be sent until it is.")}
                return {'text': _("Make the offer from the role's Details tab — Offer & joining.")}
            return {'text': _("Offer accepted. Joined is set from the offer when they start.")}
        done = ivs.filtered(lambda i: i.state == 'done')
        if done and all(i.feedback_in >= i.feedback_total for i in done[:1]):
            box = {'text': _("Every opinion from round %s is in. Decide: the next round, or not this time.",
                             done[0].round_no or 1)}
            if can_recruit:
                box.update({'verb': 'advance', 'label': _('Advance'),
                            'payload': {'applicant_id': app.id}})
            return box
        box = {'text': _("Nothing is arranged yet. Arrange the next conversation, or advance them.")}
        if can_recruit:
            box.update({'verb': 'schedule_open', 'label': _('Arrange an interview'),
                        'payload': {'applicant_id': app.id},
                        'secondary': {'verb': 'advance', 'label': _('Advance'),
                                      'payload': {'applicant_id': app.id}}})
        return box

    @api.model
    def get_timeline(self, applicant_id):
        """One story, newest first: applied, first look, every move, emails,
        notes, interviews and the offer — from the places each already lives
        (G-25)."""
        app = self._applicant(applicant_id)
        items = []

        def add(at, kind, text, by=''):
            if at:
                items.append({'at': str(at), 'kind': kind, 'text': text, 'by': by or ''})

        source = app.source_id.name or ''
        add(app.create_date, 'applied', _('Applied via %s', source) if source else _('Applied'))
        if app.pb_screen_on and app.pb_screen:
            add(app.pb_screen_on, 'first_look',
                _('First look: %s', dict(SCREEN_TAGS).get(app.pb_screen, '')),
                app.pb_screen_by.name)
        for lg in self.env['pb.hiring.stage.log'].sudo().search(
                [('applicant_id', '=', app.id)], order='at desc', limit=200):
            add(lg.at, 'move', _('Moved to %s', lg.to_stage_id.name or ''),
                lg.by_user_id.name)
        for msg in self.env['mail.message'].sudo().search(
                [('model', '=', 'hr.applicant'), ('res_id', '=', app.id),
                 ('message_type', 'in', ('comment', 'email'))],
                order='date desc', limit=100):
            plain = html2plaintext(msg.body or '').strip()
            if not plain and not msg.subject:
                continue
            first = (msg.subject or plain.split('\n')[0])[:140]
            is_email = msg.message_type == 'email' or bool(msg.subject)
            add(msg.date, 'email' if is_email else 'note',
                (_('Email: %s', first) if is_email else first),
                msg.author_id.name)
        for iv in self.env['pb.hiring.interview'].sudo().search(
                [('applicant_id', '=', app.id)], limit=40):
            n = iv.round_no or 1
            add(iv.create_date, 'interview', _('Round %s arranged', n), iv.create_uid.name)
            if iv.state == 'done':
                add(iv.stop or iv.start, 'interview', _('Round %s happened', n))
            elif iv.state == 'no_show':
                add(iv.stop or iv.start, 'interview', _('Nobody came to round %s', n))
            elif iv.state == 'cancelled':
                add(iv.write_date, 'interview', _('Round %s called off', n))
        for offer in self.env['pb.hiring.offer'].sudo().search(
                [('applicant_id', '=', app.id)], limit=10):
            add(offer.create_date, 'offer', _('Offer drafted'), offer.create_uid.name)
            if 'sent_on' in offer._fields and offer.sent_on:
                add(offer.sent_on, 'offer', _('Offer sent'))
            if offer.signed_on:
                add(offer.signed_on, 'offer', _('Offer signed'))
        items.sort(key=lambda r: r['at'], reverse=True)
        return items[:200]

    # --------------------------------------------------- a role's columns
    def _act_role_stages(self, payload):
        """Show or hide a column on ONE role (the talent lead, RC-D1/G-04)."""
        req = self._get(payload)
        self._require_write()
        Stage = self.env['hr.recruitment.stage'].sudo()
        wanted = Stage.browse([as_id(i) for i in payload.get('stage_ids') or []]).exists()
        add = Stage.browse([as_id(i) for i in payload.get('add_ids') or []]).exists()
        remove = Stage.browse([as_id(i) for i in payload.get('remove_ids') or []]).exists()
        if payload.get('stage_ids') is not None:
            ids = wanted.filtered(lambda s: s.pb_family == 'open').ids
        else:
            ids = list((set(req.sudo().pb_visible_stage_ids.ids) | set(add.ids)) - set(remove.ids))
        if not ids:
            raise UserError(_("A role needs at least one working column."))
        req.sudo().write({'pb_visible_stage_ids': [(6, 0, ids)]})
        names = ', '.join(add.mapped('name')) if add else ''
        return {'id': req.id, 'note': _("%s is on this role's board now.", names)
                if names else _("This role's columns are saved.")}

    # ------------------------------------------------------------- set-up
    @api.model
    def get_setup(self):
        if not self._can_read():
            raise AccessError(_('Hiring access is required.'))
        Stage = self.env['hr.recruitment.stage'].sudo()
        stages = Stage.search([('pb_key', '!=', False)], order='sequence,id')
        Req = self.env['pb.hiring.requisition'].sudo()
        co_ids = self.env.companies.ids or [self.env.company.id]
        roles = Req.search([('company_id', 'in', co_ids),
                            ('state', 'not in', ('closed', 'refused'))])
        using = {}
        for r in roles:
            for s in r._pb_board_stages():
                using[s.id] = using.get(s.id, 0) + 1
        presets = self.env['pb.hiring.stage.preset'].sudo().search(
            [('company_id', 'in', co_ids)])
        last = stages.sorted(lambda s: s.write_date or fields.Datetime.now(), reverse=True)[:1]
        can_edit = self._can_write()
        mail_on = flag(self.env, P_CANDIDATE_MAIL)
        lm_on = self._line_managers_move()
        n_presets = len(presets.filtered(lambda p: not p.is_standard))
        stage_status = _("%(n)s stages, %(p)s presets, last changed by %(who)s on %(when)s",
                         n=len(stages), p=n_presets,
                         who=last.write_uid.name or _('the system'),
                         when=(last.write_date or fields.Datetime.now()).strftime('%d %b')) \
            if last else _("The standard stages")

        def act(xmlid):
            try:
                action = self.env['ir.actions.actions']._for_xml_id(xmlid)
            except Exception:           # noqa: BLE001 — a missing door says so
                return False
            if action.get('type') == 'ir.actions.act_window' and not action.get('views'):
                action['views'] = [[False, v] for v in (action.get('view_mode') or 'list,form').split(',')]
            return action
        brand = self._safe(lambda: self._act_open_brand({}), default=False) if can_edit else False
        templates = self._safe(lambda: self._act_open_templates({}), default=False)
        cards = [
            {'key': 'stages', 'title': _('Stages'), 'icon': 'layers',
             'status': stage_status, 'live': True, 'action': False},
            {'key': 'forms', 'title': _('Application forms'), 'icon': 'fileText',
             'status': _("The careers-page form and your company story. The form builder arrives in the next release."),
             'action': brand},
            {'key': 'scorecards', 'title': _('Scorecards'), 'icon': 'checkCheck',
             'status': _("The lines every interviewer scores, one to five."),
             'action': act('pb_hiring.action_pb_hiring_criterion')},
            {'key': 'emails', 'title': _('Emails and languages'), 'icon': 'mail',
             'status': _("Candidate emails are on.") if mail_on else _("Candidate emails are switched off."),
             'action': templates},
            {'key': 'automations', 'title': _('Automations'), 'icon': 'zap',
             'status': _("Line managers can move candidates.") if lm_on
             else _("Only recruiters and the talent lead move candidates."),
             'action': False, 'inline': True},
            {'key': 'people', 'title': _('Who does what'), 'icon': 'users',
             'status': _("Recruiter, Talent lead and Head of hiring, given on the Access screen."),
             'action': act('biz_access.action_pb_access_board')},
        ]
        return {
            'can_edit': can_edit,
            'stages': [{
                'id': s.id, 'key': s.pb_key, 'name': s.name or '',
                'meaning': s.pb_meaning or '', 'family': s.pb_family or 'open',
                'sequence': s.sequence, 'always_on': bool(s.pb_always_on),
                'roles_using': using.get(s.id, 0),
            } for s in stages],
            'presets': [{
                'id': p.id, 'name': p.name or '', 'is_standard': bool(p.is_standard),
                'department_id': p.department_id.id, 'department': p.department_id.name or '',
                'country_id': p.country_id.id, 'country': p.country_id.name or '',
                'stage_ids': p.stage_ids.ids,
            } for p in presets],
            'roles_count': len(roles),
            'departments': self._safe(lambda: self._departments(co_ids), default=[]),
            'countries': self.env['res.country'].sudo().search_read([], ['name']),
            'switches': {'candidate_mail': mail_on, 'line_managers_move': lm_on},
            'cards': cards,
        }

    def _stage_payload(self, payload):
        stage = self.env['hr.recruitment.stage'].sudo().browse(
            as_id(payload.get('stage_id'))).exists()
        if not stage or not stage.pb_key:
            raise UserError(_("That stage is no longer there."))
        return stage

    def _act_stage_rename(self, payload):
        self._require_write()
        stage = self._stage_payload(payload)
        name = (payload.get('name') or '').strip()
        if not name:
            raise UserError(_("A stage needs a name."))
        if len(name) > 60:
            raise UserError(_("Keep a stage name under 60 characters — it has to fit on a column."))
        old = stage.name
        stage.write({'name': name})
        return {'id': stage.id, 'old': old,
                'note': _("Renamed to %s everywhere.", name)}

    def _act_stage_meaning(self, payload):
        self._require_write()
        stage = self._stage_payload(payload)
        meaning = (payload.get('meaning') or '').strip()
        if len(meaning) > 160:
            raise UserError(_("Keep the meaning to one sentence, under 160 characters."))
        old = stage.pb_meaning or ''
        stage.write({'pb_meaning': meaning or False})
        return {'id': stage.id, 'old': old, 'note': _("Saved. It shows when somebody points at the column.")}

    def _act_stage_reorder(self, payload):
        self._require_write()
        Stage = self.env['hr.recruitment.stage'].sudo()
        ids = [as_id(i) for i in payload.get('ids') or []]
        stages = Stage.browse(ids).exists().filtered(lambda s: s.pb_key)
        if not stages:
            raise UserError(_("Nothing to reorder."))
        # Keep each family in its own band so a working column can never end
        # up after the closed outcomes.
        band = {'open': 0, 'done': 1000, 'closed': 2000}
        order = {sid: i for i, sid in enumerate(ids)}
        for s in stages:
            s.write({'sequence': band.get(s.pb_family, 0) + (order[s.id] + 1) * 10})
        return {'note': _("New order saved.")}

    def _act_preset_save(self, payload):
        self._require_write()
        Preset = self.env['pb.hiring.stage.preset'].sudo()
        Stage = self.env['hr.recruitment.stage'].sudo()
        stage_ids = Stage.browse([as_id(i) for i in payload.get('stage_ids') or []]).exists() \
            .filtered(lambda s: s.pb_family == 'open').ids
        vals = {'stage_ids': [(6, 0, stage_ids)]}
        if payload.get('id'):
            preset = Preset.browse(as_id(payload['id'])).exists()
            if not preset:
                raise UserError(_("That preset is no longer there."))
            if payload.get('name'):
                vals['name'] = payload['name'].strip()
            preset.write(vals)
            return {'id': preset.id, 'note': _("Preset saved. New roles pick it up; existing roles keep their own columns.")}
        dep = self.env['hr.department'].sudo().browse(as_id(payload.get('department_id'))).exists()
        ctry = self.env['res.country'].sudo().browse(as_id(payload.get('country_id'))).exists()
        if not dep and not ctry:
            raise UserError(_("Pick a department, a country, or both."))
        company = dep.company_id if dep and dep.company_id else self.env.company
        if Preset.search_count([('company_id', '=', company.id), ('is_standard', '=', False),
                                ('department_id', '=', dep.id or False),
                                ('country_id', '=', ctry.id or False)]):
            raise UserError(_("There is already a preset for that department and country."))
        name = (payload.get('name') or '').strip() or ' · '.join(
            [n for n in (dep.name if dep else _('Any department'),
                         ctry.name if ctry else _('any country')) if n])
        if not stage_ids:
            stage_ids = self.env['pb.hiring.stage.preset']._standard_stages().ids
        preset = Preset.create({'name': name, 'company_id': company.id,
                                'department_id': dep.id or False,
                                'country_id': ctry.id or False,
                                'stage_ids': [(6, 0, stage_ids)]})
        return {'id': preset.id, 'note': _("Preset added. New roles in %s pick it up.", name)}

    def _act_preset_delete(self, payload):
        self._require_write()
        preset = self.env['pb.hiring.stage.preset'].sudo().browse(
            as_id(payload.get('id'))).exists()
        if not preset:
            raise UserError(_("That preset is no longer there."))
        if preset.is_standard:
            raise UserError(_("The Standard preset is the fallback every role needs. Change its columns instead."))
        saved = {'name': preset.name, 'department_id': preset.department_id.id,
                 'country_id': preset.country_id.id, 'stage_ids': preset.stage_ids.ids}
        preset.unlink()
        return {'saved': saved, 'note': _("Preset removed. Roles made from it keep their columns.")}

    def _act_set_switch(self, payload):
        self._require_write()
        key = SWITCHES.get(payload.get('key'))
        if not key:
            raise UserError(_("That is not a switch this page can change."))
        on = bool(payload.get('on'))
        self.env['ir.config_parameter'].sudo().set_param(key, '1' if on else '0')
        return {'on': on, 'note': _("Switched on.") if on else _("Switched off.")}
