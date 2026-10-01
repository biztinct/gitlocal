# -*- coding: utf-8 -*-
"""RECRUIT phase 4 — what the screens read and press about privacy.

THE LAST LAYER OF EVERY PAYLOAD. This file is imported after every other
phase, so its `get_candidate`, `_candidates`, `get_timeline`, `_row`,
`get_requisition`, `_offer_row` and `get_board` see the finished payload and
take out what the reader may not see. The rule is one function, `_parts(app)`:
the hiring team (and a recruiter's cover, on that recruiter's roles) gets
everything; anybody else gets `card` (name, stage, interview dates) plus what
a recruiter shared with them, and nothing else, ever — because sudo reads
bypass field `groups`, nothing here leans on the ORM to hide a field.
"""

import logging
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext

from .hiring_common import (
    GROUP_ADMIN, GROUP_MANAGER, GROUP_USER, SCREEN_TAGS, as_id, flag, fold, leg,
)
from .privacy_p4 import (
    _ASSIGN_NAME, _CV_NAME, _PORTFOLIO_NAME, BANK_PAGE, BANK_READ_CAP, DEFAULT_PARTS,
    FILE_PARTS, P_RETENTION_ENABLED, PART_KEYS, PURGE_MODES, SHARE_WITH, SOON_DAYS,
    _csv, _is_hiring_user, _split, _user_of,
)

_logger = logging.getLogger(__name__)

#: Interview fields a reader outside the hiring team may see: when, which
#: round, how — never the opinions, the verdict or the decision.
IV_PUBLIC = ('id', 'requisition_id', 'role', 'applicant_id', 'candidate', 'round_no',
             'kind', 'kind_label', 'start', 'stop', 'mode', 'mode_label', 'location',
             'state', 'state_label', 'bucket')


class PbHiringP4(models.AbstractModel):
    _inherit = 'pb.hiring'

    # =====================================================================
    #  Who sees what
    # =====================================================================
    @api.model
    def _hiring_group(self):
        return _is_hiring_user(self.env.user)

    @api.model
    def _is_hiring_reader(self, req=None):
        """The hiring team, or somebody covering THIS role's recruiter."""
        if self._hiring_group():
            return True
        if req:
            return bool(self._can_recruit(req.sudo()))
        return False

    @api.model
    def _parts(self, app):
        req = app.sudo().pb_requisition_id
        if self._is_hiring_reader(req):
            return set(PART_KEYS) | {'card'}
        return self.env['pb.hiring.share'].parts_for(app, self.env.user) | {'card'}

    @api.model
    def _part_rows(self):
        """The Share sheet's list: key, the word, one line of meaning."""
        return [
            {'key': 'profile', 'label': _('Profile'),
             'help': _('Where they are based, where they applied from, LinkedIn and the first look.')},
            {'key': 'cv', 'label': _('CV'),
             'help': _('The CV they sent, opened from a private link.')},
            {'key': 'portfolio', 'label': _('Portfolio'),
             'help': _('Their portfolio link and files.')},
            {'key': 'assignment', 'label': _('Assignment'),
             'help': _('The take-home task they sent back, when there is one.')},
            {'key': 'attachments', 'label': _('Other files'),
             'help': _('Any other file on their record.')},
            {'key': 'answers', 'label': _('Answers'),
             'help': _('What they answered on the application form. Expected pay stays separate.')},
            {'key': 'scorecards', 'label': _('Scorecards'),
             'help': _('What each interviewer scored and said.')},
            {'key': 'expected_pay', 'label': _('Expected pay'),
             'help': _('The pay they asked for. Never shared unless you tick it.'),
             'money': True},
        ]

    @api.model
    def _parts_label(self, parts):
        words = {r['key']: r['label'] for r in self._part_rows()}
        return ', '.join(words[k] for k in PART_KEYS if k in parts)

    @api.model
    def _short_name(self, name):
        return (name or '').strip()

    # =====================================================================
    #  Files: which part a file is, and the link a reader gets
    # =====================================================================
    @api.model
    def _doc_rows(self, app, parts=None, tokenised=False):
        """Every file on the candidate, each with its part. With `parts`,
        only the files of those parts; with `tokenised`, each URL carries the
        file's own access token (a reader outside the hiring team cannot open
        `/web/content/<id>` on their own: they have no read on the candidate).
        """
        app = app.sudo()
        atts = self.env['ir.attachment'].sudo().search(
            [('res_model', '=', 'hr.applicant'), ('res_id', '=', app.id)],
            order='id desc', limit=60)
        kinds = {}
        form = app.pb_form_id.sudo().with_context(active_test=False)
        for fld in form.field_ids:
            label = '%s %s' % (fld.key or '', fld.with_context(lang='en_US').label or '')
            if fld.kind == 'cv':
                kinds[fld.key] = 'cv'
            elif fld.kind == 'portfolio':
                kinds[fld.key] = 'portfolio'
            elif _ASSIGN_NAME.search(label):
                kinds[fld.key] = 'assignment'
        rows = []
        for att in atts:
            key = att.pb_form_key or ''
            if key and key in kinds:
                kind = kinds[key]
            elif key:
                kind = 'assignment' if _ASSIGN_NAME.search(key) else 'attachments'
            elif _CV_NAME.search(att.name or ''):
                kind = 'cv'
            elif _ASSIGN_NAME.search(att.name or ''):
                kind = 'assignment'
            elif _PORTFOLIO_NAME.search(att.name or ''):
                kind = 'portfolio'
            else:
                kind = 'attachments'
            rows.append([att, kind])
        # A CV with no tell-tale name: the first PDF / Word file, when nothing
        # else on the record is the CV.
        if not any(k == 'cv' for _a, k in rows):
            for row in reversed(rows):
                if row[1] == 'attachments' and (row[0].mimetype or '') in (
                        'application/pdf', 'application/msword',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'):
                    row[1] = 'cv'
                    break
        out = []
        for att, kind in rows:
            if parts is not None and kind not in parts:
                continue
            url = '/web/content/%s' % att.id
            if tokenised:
                token = att.sudo().generate_access_token()[0]
                url = '/web/content/%s?access_token=%s' % (att.id, token)
            out.append({'id': att.id, 'name': att.name or '', 'mimetype': att.mimetype or '',
                        'kind': kind, 'url': url, 'form_key': att.pb_form_key or ''})
        return out

    @api.model
    def _regenerate_tokens(self, app):
        """Every shared file link of this candidate stops working: a fresh
        token on each file that had one. The hiring team's own links do not
        use tokens and are untouched."""
        atts = self.env['ir.attachment'].sudo().search(
            [('res_model', '=', 'hr.applicant'), ('res_id', '=', app.id),
             ('access_token', '!=', False)])
        for att in atts:
            att.write({'access_token': False})
            att.generate_access_token()
        return len(atts)

    # =====================================================================
    #  The gate: a share opens the candidate even off the role
    # =====================================================================
    @api.model
    def _applicant(self, applicant_id, for_move=False):
        try:
            return super()._applicant(applicant_id, for_move=for_move)
        except AccessError:
            if for_move:
                raise
            app = self.env['hr.applicant'].sudo().with_context(active_test=False).browse(
                as_id(applicant_id)).exists()
            if app and self.env['pb.hiring.share'].sudo().search_count(
                    [('applicant_id', '=', app.id), ('user_id', '=', self.env.uid)]):
                return app
            raise

    @api.model
    def can_open(self):
        return bool(super().can_open() or self._safe(
            lambda: self.env['pb.hiring.share'].sudo().search_count(
                [('user_id', '=', self.env.uid)]), default=0))

    # =====================================================================
    #  The board: budget, offers, "Shared with you"
    # =====================================================================
    @api.model
    def _mask_money_row(self, row):
        row.update({
            'budget_cost': 0.0, 'budget_over_by': 0.0, 'budget_note': '',
            'budget_flag': '', 'budget_status': 'hidden',
            'budget_label': _('Budget: hiring team only'), 'money_locked': True,
        })
        return row

    @api.model
    def _row(self, req):
        row = super()._row(req)
        if not self._is_hiring_reader(req):
            self._mask_money_row(row)
        return row

    @api.model
    def _offer_row(self, offer, full=False):
        """Read as the system (the money fields carry `groups` now), then
        blanked for anybody outside the hiring team."""
        hiring = self._is_hiring_reader(offer.sudo().requisition_id)
        row = super()._offer_row(offer.sudo(), full=full)
        if not hiring:
            row.update({'monthly_total': None, 'annual_total': None, 'money_locked': True})
            for line in row.get('lines') or []:
                line['amount'] = None
        return row

    @api.model
    def _shared_with_me(self):
        """The candidates shared with this reader, newest first."""
        rows = self.env['pb.hiring.share'].sudo().search(
            [('user_id', '=', self.env.uid), ('applicant_id.pb_anonymised_on', '=', False)],
            limit=50)
        out = []
        for share in rows:
            app = share.applicant_id.with_context(active_test=False)
            out.append({
                'share_id': share.id, 'applicant_id': app.id,
                'name': app.partner_name or _('Candidate'),
                'role': app.pb_requisition_id.title or app.job_id.name or '',
                'requisition_id': app.pb_requisition_id.id or False,
                'stage': app.stage_id.name or '',
                'parts': sorted(share._part_set(), key=PART_KEYS.index),
                'parts_label': self._parts_label(share._part_set()),
                'by': share.granted_by_id.name or _("the role's default"),
                'on': str(share.granted_on or ''),
            })
        return out

    @api.model
    def get_board(self, limit=None):
        board = super().get_board(limit=limit)
        hiring = self._hiring_group()
        shared = [] if hiring else self._safe(self._shared_with_me, default=[])
        if not board.get('allowed') and shared:
            board = self._empty_board()
            board.update({'allowed': True, 'share_only': True, 'offer_rows': [],
                          'agencies': [], 'covering': []})
        board['shared_with_me'] = shared
        board['can_bank'] = bool(hiring)
        return board

    # =====================================================================
    #  One role: candidates, offers, request figures, defaults
    # =====================================================================
    @api.model
    def _iv_public(self, row):
        return {k: row.get(k) for k in IV_PUBLIC if k in row}

    @api.model
    def _candidates(self, req):
        cards = super()._candidates(req)
        if not cards:
            return cards
        Share = self.env['pb.hiring.share'].sudo()
        ids = [c['id'] for c in cards]
        if self._is_hiring_reader(req):
            names = {}
            for share in Share.search([('applicant_id', 'in', ids)]):
                names.setdefault(share.applicant_id.id, []).append(
                    self._short_name(share.user_id.name))
            for c in cards:
                who = names.get(c['id']) or []
                if who:
                    c['shared'] = _('Shared with %s', who[0]) if len(who) == 1 \
                        else _('Shared with %(who)s +%(n)s', who=who[0], n=len(who) - 1)
                    c['shared_tone'] = 'info'
                else:
                    c['shared'] = _('Private')
                    c['shared_tone'] = 'quiet'
                c['shared_names'] = who
            return cards
        mine = {}
        for share in Share.search([('applicant_id', 'in', ids), ('user_id', '=', self.env.uid)]):
            mine[share.applicant_id.id] = share._part_set()
        return [self._mask_card(c, mine.get(c['id'], set())) for c in cards]

    @api.model
    def _mask_card(self, card, parts):
        """Name, stage, interview dates — plus what was shared, said in words."""
        keep = {k: card.get(k) for k in (
            'id', 'name', 'stage', 'stage_id', 'stage_key', 'stage_seq', 'family', 'active',
            'next_interview_at', 'rounds', 'selected')}
        days = card.get('days_in_stage') or 0
        keep.update({
            'email': '', 'applied_on': '', 'applied_days': 0, 'days_in_stage': days,
            'source': '', 'source_label': '', 'screen': '', 'screen_label': '', 'status': '',
            'waiting': '', 'lang': '', 'edge': '',
            'next_interview': self._iv_public(card['next_interview']) if card.get('next_interview') else None,
            'interviews': [self._iv_public(i) for i in card.get('interviews') or []],
            'opinions': {'in': 0, 'total': 0, 'late': 0},
            'has_cv': False, 'chips': [],
            'flags': [f for f in card.get('flags') or [] if f == 'iv'],
            'parts': sorted(parts, key=PART_KEYS.index),
            'locked': not parts,
            'sub': (_('Shared with you: %s', self._parts_label(parts)) if parts
                    else _('Not shared with you yet')),
            'shared': _('Shared with you') if parts else '',
            'shared_tone': 'info' if parts else '',
        })
        if parts & {'profile'}:
            keep['source'] = card.get('source') or ''
            keep['applied_on'] = card.get('applied_on') or ''
        keep['has_cv'] = bool(card.get('has_cv')) and 'cv' in parts
        return keep

    @api.model
    def get_requisition(self, requisition_id):
        row = super().get_requisition(requisition_id)
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id))
        hiring = self._is_hiring_reader(req)
        if not hiring:
            self._mask_money_row(row)
            board = row.get('board') or {}
            board['show_money'] = False
            board['interviews'] = [self._iv_public(i) for i in board.get('interviews') or []]
            request = row.get('request') or {}
            if request.get('figures'):
                uid = self.env.uid
                writer = uid in (req.requested_by_user_id.id,
                                 req.asked_user_id.id if 'asked_user_id' in req._fields else 0)
                if not writer:
                    request['figures'] = None
                    request['figures_locked'] = True
            journey = row.get('journey') or {}
            if journey.get('bgv'):
                journey['bgv'] = {}
        row['share_defaults'] = self._safe(lambda: self._share_defaults(req), default={})
        row['can_bank'] = bool(self._hiring_group())
        return row

    @api.model
    def _share_defaults(self, req):
        parts = _split(req.default_share_parts if req.default_share_parts is not False
                       else DEFAULT_PARTS)
        return {
            'parts': sorted(parts, key=PART_KEYS.index),
            'parts_label': self._parts_label(parts) or _('nothing'),
            'with': req.default_share_with or 'hiring_manager',
            'withs': [{'key': k, 'label': v} for k, v in SHARE_WITH],
            'catalogue': self._part_rows(),
            'people': [{'name': u.name or '', 'role': label}
                       for u, _e, label in req._pb_manager_targets()],
            'can_edit': bool(self._can_write()),
        }

    # =====================================================================
    #  The drawer
    # =====================================================================
    @api.model
    def get_candidate(self, applicant_id):
        res = super().get_candidate(applicant_id)
        app = self.env['hr.applicant'].sudo().with_context(active_test=False).browse(res['id'])
        req = app.pb_requisition_id
        if self._is_hiring_reader(req):
            res.update(self._privacy_block(app))
            return res
        parts = self.env['pb.hiring.share'].parts_for(app, self.env.user)
        return self._mask_candidate(res, app, parts - {'card'})

    @api.model
    def _privacy_block(self, app):
        """What the hiring team reads about who sees this person."""
        Share = self.env['pb.hiring.share'].sudo()
        rows = []
        pay_with = []
        for share in Share.search([('applicant_id', '=', app.id)]):
            parts = share._part_set()
            if 'expected_pay' in parts:
                pay_with.append(self._short_name(share.user_id.name))
            rows.append({
                'id': share.id, 'user_id': share.user_id.id,
                'name': share.user_id.name or '',
                'employee_id': share.employee_id.id or False,
                'parts': sorted(parts, key=PART_KEYS.index),
                'parts_label': self._parts_label(parts),
                'on': str(share.granted_on or ''),
                'by': share.granted_by_id.name or _("the role's default"),
            })
        summary = ' · '.join('%s (%s)' % (r['name'], r['parts_label']) for r in rows)
        until = app.pb_retention_until
        months = self.env['pb.hiring.retention.rule']._months_for(app.company_id, app._pb_country())
        return {
            'share': {'rows': rows, 'summary': summary, 'private': not rows},
            'money_who': (_('Recruiters and %s', ', '.join(pay_with)) if pay_with
                          else _('Recruiters only')),
            'notes': self._notes_payload(app),
            'retention': {
                'until': str(until or ''), 'months': months,
                'extended': bool(app.pb_retention_extended_on),
                'extended_by': app.pb_retention_extended_by_id.name or '',
                'extended_on': str(app.pb_retention_extended_on or ''),
                'can_extend': bool(until and not app.pb_retention_extended_on
                                   and not app.pb_anonymised_on),
                'country': app._pb_country().name or '',
                'anonymised_on': str(app.pb_anonymised_on or ''),
            },
            'anonymised': bool(app.pb_anonymised_on),
            'locks': [],
            'parts': list(PART_KEYS),
            'locked': False,
        }

    @api.model
    def _mask_candidate(self, res, app, parts):
        """The drawer for somebody outside the hiring team: exactly the
        shared parts, every other thing a labelled lock."""
        out = {k: res.get(k) for k in ('id', 'name', 'role', 'requisition_id', 'stage',
                                       'stage_key', 'family', 'active', 'can_move')}
        out.update({
            'can_recruit': False, 'parts': sorted(parts, key=PART_KEYS.index),
            'locked': not parts,
            'locked_text': _("The recruiter has not shared this person's details with you yet.")
            if not parts else '',
            'applied_on': '', 'source': '', 'location': '', 'country': '', 'email': '',
            'phone': '', 'linkedin': '', 'portfolio': '', 'screen': '', 'screen_label': '',
            'reason': '', 'hold_until': '', 'lang': '', 'consent': None, 'duplicate': None,
            'money': None, 'scorecards': [], 'answers': [], 'documents': [], 'doc_count': 0,
            'interviews': [self._iv_public(i) for i in res.get('interviews') or []],
            'timeline': res.get('timeline') or [],
            'notes': self._notes_payload(app),
            'share': None, 'retention': None, 'anonymised': bool(app.pb_anonymised_on),
        })
        mine = self.env['pb.hiring.share'].sudo().search(
            [('applicant_id', '=', app.id), ('user_id', '=', self.env.uid)], limit=1)
        out['shared_by'] = (_('Shared with you by %(who)s on %(when)s',
                              who=mine.granted_by_id.name or _("the role's default"),
                              when=(mine.granted_on or fields.Datetime.now()).strftime('%d %b'))
                            if mine and parts else '')
        if 'profile' in parts:
            out.update({k: res.get(k) or '' for k in (
                'applied_on', 'source', 'location', 'country', 'linkedin', 'screen',
                'screen_label', 'lang')})
        if 'portfolio' in parts:
            out['portfolio'] = res.get('portfolio') or ''
        if 'scorecards' in parts:
            out['scorecards'] = res.get('scorecards') or []
        if 'expected_pay' in parts and 'salary_expected' in app._fields and app.salary_expected:
            out['money'] = {'expected': app.salary_expected or 0.0,
                            'currency': app.company_id.currency_id.name or ''}
        files = parts & set(FILE_PARTS)
        docs = self._doc_rows(app, parts=files, tokenised=True) if files else []
        out['documents'] = docs
        out['doc_count'] = len(docs)
        if 'answers' in parts or files:
            out['answers'] = self._shared_answers(app, parts, docs)
        locks = []
        for row in self._part_rows():
            if row['key'] not in parts:
                locks.append({'key': row['key'], 'label': row['label'],
                              'text': _('Not shared with you')})
        locks.append({'key': 'contact', 'label': _('Email and phone'),
                      'text': _('The recruiter keeps in touch with them')})
        out['locks'] = locks if parts else []
        # The Next box speaks about the reader's own part only.
        now = fields.Datetime.now()
        live = [i for i in out['interviews'] if i.get('state') == 'scheduled'
                and i.get('start') and fields.Datetime.to_datetime(i['start']) > now]
        if live:
            first = sorted(live, key=lambda i: i['start'])[0]
            text = _('Round %(n)s is on %(when)s.', n=first.get('round_no') or 1,
                     when=fields.Datetime.to_datetime(first['start']).strftime('%a %d %b, %H:%M'))
        else:
            text = _('%(name)s is at %(stage)s. The recruiter moves them on.',
                     name=out['name'] or '', stage=out['stage'] or '')
        out['next'] = {'text': text}
        return out

    @api.model
    def _shared_answers(self, app, parts, docs):
        """The form's answers for a reader outside the team: answers only with
        `answers`, expected pay only with `expected_pay`, a file only when its
        part is shared (and then through its token link)."""
        rows = self._safe(lambda: self._answers(app, True), default=[])
        form = app.pb_form_id.sudo().with_context(active_test=False)
        kinds = {f.key: f.kind for f in form.field_ids}
        by_id = {d['id']: d for d in docs}
        out = []
        for row in rows:
            kind = kinds.get(row['key'], '')
            if kind == 'expected_pay':
                if 'expected_pay' not in parts:
                    continue
            elif 'answers' not in parts and not row.get('files'):
                continue
            files = []
            for f in row.get('files') or []:
                if f['id'] in by_id:
                    files.append({'id': f['id'], 'name': f['name'], 'url': by_id[f['id']]['url']})
            if row.get('files') and not files:
                if 'answers' not in parts:
                    continue
                row = dict(row, value=_('A file — not shared with you'))
            out.append(dict(row, files=files))
        return out

    # =====================================================================
    #  The timeline
    # =====================================================================
    @api.model
    def get_timeline(self, applicant_id):
        items = super().get_timeline(applicant_id)
        app = self.env['hr.applicant'].sudo().with_context(active_test=False).browse(
            as_id(applicant_id))
        req = app.pb_requisition_id
        Share = self.env['pb.hiring.share'].sudo()
        if self._is_hiring_reader(req):
            for share in Share.search([('applicant_id', '=', app.id)]):
                items.append({'at': str(share.granted_on or share.create_date or ''),
                              'kind': 'share',
                              'text': _('Shared with %(who)s: %(what)s',
                                        who=share.user_id.name or '',
                                        what=self._parts_label(share._part_set())),
                              'by': share.granted_by_id.name or ''})
            items.sort(key=lambda r: r['at'], reverse=True)
            return items
        parts = Share.parts_for(app, self.env.user)
        keep = []
        for it in items:
            if it['kind'] in ('move', 'interview'):
                keep.append(it)
            elif it['kind'] == 'applied':
                keep.append(dict(it, text=it['text'] if 'profile' in parts else _('Applied')))
            elif it['kind'] == 'first_look' and 'profile' in parts:
                keep.append(it)
        # The reader's OWN notes from the board (the line manager's one write)
        me = self.env.user.partner_id
        for msg in self.env['mail.message'].sudo().search(
                [('model', '=', 'hr.applicant'), ('res_id', '=', app.id),
                 ('message_type', '=', 'comment'), ('author_id', '=', me.id)],
                order='date desc', limit=30):
            plain = html2plaintext(msg.body or '').strip()
            if plain:
                keep.append({'at': str(msg.date), 'kind': 'note',
                             'text': plain.split('\n')[0][:140], 'by': me.name or ''})
        for share in Share.search([('applicant_id', '=', app.id), ('user_id', '=', self.env.uid)]):
            keep.append({'at': str(share.granted_on or ''), 'kind': 'share',
                         'text': _('Shared with you: %s', self._parts_label(share._part_set())),
                         'by': share.granted_by_id.name or ''})
        keep.sort(key=lambda r: r['at'], reverse=True)
        return keep

    # =====================================================================
    #  Sharing — the verbs
    # =====================================================================
    @api.model
    def _require_share(self, app):
        req = app.sudo().pb_requisition_id
        if not self._is_hiring_reader(req):
            raise AccessError(_("Sharing a candidate is for the hiring team."))
        return True

    @api.model
    def _target_users(self, targets):
        """[{user_id} | {employee_id}] → [(user, employee)]; a target with no
        login is refused in a sentence."""
        out = []
        for t in targets or []:
            emp = self.env['hr.employee'].sudo().browse(as_id(t.get('employee_id'))).exists() \
                if t.get('employee_id') else self.env['hr.employee']
            user = self.env['res.users'].sudo().browse(as_id(t.get('user_id'))).exists() \
                if t.get('user_id') else _user_of(emp)
            if not user:
                raise UserError(_("%s has no login, so there is nowhere to show it to them.",
                                  emp.name or _('That person')))
            if user.share:
                raise UserError(_("%s has a portal login only and cannot open the hiring "
                                  "board. Share with somebody who has a full login.", user.name))
            if not emp:
                emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            out.append((user, emp))
        return out

    def _act_share(self, payload):
        """Share parts of one or many candidates with one or many people.

        Idempotent: one share per person per candidate, set to exactly the
        parts given (an empty list stops sharing). Returns `before` so the
        toast can undo it."""
        ids = [as_id(i) for i in (payload.get('applicant_ids')
                                  or [payload.get('applicant_id')]) if as_id(i)]
        if not ids:
            raise UserError(_("Choose at least one candidate to share."))
        people = self._target_users(payload.get('targets') or [])
        if not people:
            raise UserError(_("Choose who to share with."))
        parts = _csv(payload.get('parts') or [])
        Share = self.env['pb.hiring.share']
        before, done = [], 0
        for app_id in ids:
            app = self._applicant(app_id)
            self._require_share(app)
            dropped_files = False
            for user, emp in people:
                share, was = Share._grant(app, user, parts, employee=emp or None,
                                          by=self.env.user, note=payload.get('note') or '')
                before.append(was)
                if was['parts'] and (set(_split(was['parts'])) - _split(parts)) & set(FILE_PARTS):
                    dropped_files = True
                done += 1
            if dropped_files:
                self._regenerate_tokens(app)
        names = ', '.join(u.name for u, _e in people)
        if not parts:
            note = _("Stopped sharing with %s.", names)
        elif len(ids) == 1:
            note = _("Shared with %(who)s: %(what)s.", who=names, what=self._parts_label(_split(parts)))
        else:
            note = _("%(n)s people shared with %(who)s: %(what)s.", n=len(ids), who=names,
                     what=self._parts_label(_split(parts)))
        return {'note': note, 'before': before, 'shares': done}

    def _act_share_restore(self, payload):
        """Undo: put each (candidate, person) back as it was."""
        Share = self.env['pb.hiring.share']
        for was in payload.get('before') or []:
            app = self._applicant(was.get('applicant_id'))
            self._require_share(app)
            user = self.env['res.users'].sudo().browse(as_id(was.get('user_id'))).exists()
            if not user:
                continue
            Share._grant(app, user, was.get('parts') or '', by=self.env.user)
            self._regenerate_tokens(app)
        return {'note': _("Put back as it was.")}

    def _act_unshare(self, payload):
        Share = self.env['pb.hiring.share'].sudo()
        before = []
        for share in Share.browse([as_id(i) for i in payload.get('share_ids') or []]).exists():
            app = share.applicant_id
            self._require_share(app)
            before.append({'applicant_id': app.id, 'user_id': share.user_id.id,
                           'parts': share.parts})
            name = share.user_id.name
            share.write({'active': False})
            self._regenerate_tokens(app)
        if not before:
            raise UserError(_("That share is no longer there."))
        return {'note': _("Stopped sharing with %s. Their file links no longer open.", name)
                if len(before) == 1 else _("Stopped sharing with %s people.", len(before)),
                'before': before}

    @api.model
    def get_share_options(self, requisition_id=None, applicant_ids=None):
        """Who the Share sheet offers, and what each already sees."""
        ids = [as_id(i) for i in applicant_ids or [] if as_id(i)]
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id)).exists()
        if not req and ids:
            req = self.env['hr.applicant'].sudo().browse(ids[0]).pb_requisition_id
        if not self._is_hiring_reader(req):
            raise AccessError(_("Sharing a candidate is for the hiring team."))
        people, seen = [], set()
        targets = (req._pb_manager_targets() + req._pb_panel_targets()) if req else []
        for user, emp, label in targets:
            if user.id in seen or _is_hiring_user(user):
                continue
            seen.add(user.id)
            people.append({'user_id': user.id, 'employee_id': emp.id or False,
                           'name': user.name or emp.name or '', 'role': label,
                           'portal': bool(user.share)})
        current = {}
        if ids:
            for share in self.env['pb.hiring.share'].sudo().search([('applicant_id', 'in', ids)]):
                row = current.setdefault(share.user_id.id, {'parts': set(), 'n': 0})
                row['parts'] |= share._part_set()
                row['n'] += 1
                if share.user_id.id not in seen and not _is_hiring_user(share.user_id):
                    seen.add(share.user_id.id)
                    people.append({'user_id': share.user_id.id,
                                   'employee_id': share.employee_id.id or False,
                                   'name': share.user_id.name or '', 'role': _('Shared before'),
                                   'portal': bool(share.user_id.share)})
        defaults = _split(req.default_share_parts if req and req.default_share_parts is not False
                          else DEFAULT_PARTS)
        return {
            'people': people,
            'current': {str(k): {'parts': sorted(v['parts'], key=PART_KEYS.index),
                                 'all': v['n'] >= len(ids)} for k, v in current.items()},
            'parts': self._part_rows(),
            'defaults': sorted(defaults, key=PART_KEYS.index),
            'role': req.title or '' if req else '',
        }

    @api.model
    def share_people(self, query='', requisition_id=None, limit=20):
        """Anybody in the company with a full login, for the sheet's search."""
        if not self._hiring_group() and not self._cover_scope():
            return []
        co = self.env.companies.ids or [self.env.company.id]
        q = fold(query or '')
        if len(q) < 2:
            return []
        rows = self.env['hr.employee'].sudo().search_read(
            [('company_id', 'in', co), ('user_id', '!=', False), ('user_id.share', '=', False)],
            ['id', 'name', 'job_title', 'user_id'], limit=5000)
        out = []
        for r in rows:
            if q in fold(r['name'] or ''):
                out.append({'user_id': r['user_id'][0], 'employee_id': r['id'],
                            'name': r['name'] or '', 'role': r.get('job_title') or '',
                            'portal': False})
        out.sort(key=lambda r: fold(r['name']))
        return out[:max(1, min(int(limit or 20), 60))]

    def _act_role_share_defaults(self, payload):
        """"What the hiring manager sees by default" — the talent lead's call.
        Only new candidates pick it up."""
        req = self._get(payload)
        self._require_write()
        rec = req.sudo()
        before = {'parts': rec.default_share_parts or '', 'with': rec.default_share_with}
        vals = {}
        if 'parts' in payload:
            vals['default_share_parts'] = _csv(payload.get('parts') or []) or ''
        if payload.get('with') in dict(SHARE_WITH):
            vals['default_share_with'] = payload['with']
        if vals:
            rec.write(vals)
        return {'id': req.id, 'before': before,
                'note': _("Saved. New candidates on this role pick it up; what was already "
                          "shared does not change.")}

    # =====================================================================
    #  Recruiter notes
    # =====================================================================
    @api.model
    def _note_rows(self, app):
        """The private notes this reader may see on one candidate."""
        Note = self.env['pb.hiring.note'].sudo()
        me = self.env.user
        lead = me.has_group(GROUP_MANAGER)
        notes = Note.search([('applicant_id', '=', app.id)])
        return notes.filtered(lambda n: n.author_id == me or lead or me in n.shared_user_ids)

    @api.model
    def _notes_payload(self, app):
        app = app.sudo()
        me = self.env.user
        lead = me.has_group(GROUP_MANAGER)
        hiring = self._is_hiring_reader(app.pb_requisition_id)
        req = app.pb_requisition_id
        targets = []
        if hiring and req:
            seen = set()
            for user, _e, label in req._pb_manager_targets() + req._pb_panel_targets():
                if user.id in seen or user.share or _is_hiring_user(user):
                    continue
                seen.add(user.id)
                targets.append({'id': user.id, 'name': user.name or '', 'role': label})
        rows = []
        for note in self._note_rows(app):
            mine = note.author_id == me
            rows.append({
                'id': note.id, 'author': note.author_id.name or '',
                'body': html2plaintext(note.body or '').strip(),
                'on': str(note.create_date or ''),
                'shared': [{'id': u.id, 'name': u.name or ''} for u in note.shared_user_ids],
                'mine': mine,
                'can_edit': mine and hiring,
                'can_delete': hiring and (mine or lead),
                'can_share': hiring and (mine or lead),
            })
        return {'rows': rows, 'can_add': bool(hiring), 'targets': targets,
                'who': _('Only you and the talent lead') if hiring else _('Shared with you')}

    @api.model
    def get_notes(self, applicant_id):
        app = self._applicant(applicant_id)
        return self._notes_payload(app)

    @api.model
    def _note(self, payload):
        note = self.env['pb.hiring.note'].sudo().browse(as_id(payload.get('note_id'))).exists()
        if not note:
            raise UserError(_("That note is no longer there."))
        app = note.applicant_id
        if not self._is_hiring_reader(app.pb_requisition_id):
            raise AccessError(_("Recruiter notes are for the hiring team."))
        return note

    @api.model
    def _note_html(self, body):
        body = (body or '').strip()
        if not body:
            raise UserError(_("Write the note first."))
        return Markup('').join(Markup('<p>%s</p>') % line for line in body[:4000].split('\n')
                               if line.strip()) or Markup('<p>%s</p>') % body

    def _act_note_add(self, payload):
        app = self._applicant(payload.get('applicant_id'))
        if not self._is_hiring_reader(app.pb_requisition_id):
            raise AccessError(_("Recruiter notes are for the hiring team. Leave an ordinary "
                                "note instead."))
        users = self.env['res.users'].sudo().browse(
            [as_id(i) for i in payload.get('share_user_ids') or []]).exists()
        note = self.env['pb.hiring.note'].sudo().create({
            'applicant_id': app.id, 'author_id': self.env.uid,
            'body': self._note_html(payload.get('body')),
            'shared_user_ids': [(6, 0, users.filtered(lambda u: not u.share).ids)]})
        return {'id': note.id, 'note': _("Note saved. Only you and the talent lead can read it.")
                if not note.shared_user_ids else _("Note saved and shared with %s.",
                                                   ', '.join(note.shared_user_ids.mapped('name')))}

    def _act_note_edit(self, payload):
        note = self._note(payload)
        if note.author_id != self.env.user:
            raise AccessError(_("Only the person who wrote a note changes it."))
        old = html2plaintext(note.body or '').strip()
        note.write({'body': self._note_html(payload.get('body'))})
        return {'id': note.id, 'old': old, 'note': _("Note changed.")}

    def _act_note_share(self, payload):
        note = self._note(payload)
        me = self.env.user
        if note.author_id != me and not me.has_group(GROUP_MANAGER):
            raise AccessError(_("Only the person who wrote a note, or the talent lead, shares it."))
        before = note.shared_user_ids.ids
        users = self.env['res.users'].sudo().browse(
            [as_id(i) for i in payload.get('user_ids') or []]).exists().filtered(
                lambda u: not u.share)
        note.write({'shared_user_ids': [(6, 0, users.ids)]})
        return {'id': note.id, 'before': before,
                'note': _("This note is shared with %s now.", ', '.join(users.mapped('name')))
                if users else _("This note is private again: only you and the talent lead.")}

    def _act_note_delete(self, payload):
        note = self._note(payload)
        me = self.env.user
        if note.author_id != me and not me.has_group(GROUP_MANAGER):
            raise AccessError(_("Only the person who wrote a note, or the talent lead, removes it."))
        saved = {'applicant_id': note.applicant_id.id, 'author_id': note.author_id.id,
                 'body': note.body or '', 'shared_user_ids': note.shared_user_ids.ids}
        note.unlink()
        return {'saved': saved, 'note': _("Note removed.")}

    def _act_note_restore(self, payload):
        saved = payload.get('saved') or {}
        app = self._applicant(saved.get('applicant_id'))
        if not self._is_hiring_reader(app.pb_requisition_id):
            raise AccessError(_("Recruiter notes are for the hiring team."))
        author = self.env['res.users'].sudo().browse(as_id(saved.get('author_id'))).exists()
        if author != self.env.user and not self.env.user.has_group(GROUP_MANAGER):
            raise AccessError(_("Only the person who wrote a note puts it back."))
        note = self.env['pb.hiring.note'].sudo().create({
            'applicant_id': app.id, 'author_id': author.id or self.env.uid,
            'body': saved.get('body') or '',
            'shared_user_ids': [(6, 0, [as_id(i) for i in saved.get('shared_user_ids') or []])]})
        return {'id': note.id, 'note': _("Note put back.")}

    # =====================================================================
    #  The Resume bank
    # =====================================================================
    @api.model
    def _require_bank(self):
        if not self._hiring_group():
            raise AccessError(_("The Resume bank is for the hiring team."))
        return True

    @api.model
    def _skills_on(self):
        return 'skill_ids' in self.env['hr.applicant']._fields

    @api.model
    def search_bank(self, params=None):
        """Future-fit people, pool members and — with `include_all` —
        everybody who ever applied; one row per person (the newest
        application), searched accent-blind on name, email, skills, role and
        tags. Facet counts are over the people the search text and the
        switch give, before any facet is picked."""
        self._require_bank()
        p = params or {}
        co = self.env.companies.ids or [self.env.company.id]
        dom = [('company_id', 'in', co), ('pb_anonymised_on', '=', False)]
        if not p.get('include_all'):
            dom += ['|', ('pb_screen', '=', 'future_fit'), ('talent_pool_ids', '!=', False)]
        Applicant = self.env['hr.applicant'].sudo().with_context(active_test=False)
        fnames = ['partner_name', 'email_from', 'email_normalized', 'job_id', 'pb_country_id',
                  'pb_requisition_id', 'categ_ids', 'source_id', 'pb_screen', 'create_date',
                  'pb_retention_until', 'talent_pool_ids', 'department_id', 'stage_id', 'active']
        skills_on = self._skills_on()
        if skills_on:
            fnames.append('skill_ids')
        raw = Applicant.search_read(dom, fnames, order='create_date desc, id desc',
                                    limit=BANK_READ_CAP)
        # one row per person: the newest application wins
        people, order = {}, []
        for r in raw:
            key = r['email_normalized'] or ('id:%s' % r['id'])
            if key in people:
                people[key]['applications'] += 1
                continue
            r['applications'] = 1
            people[key] = r
            order.append(key)
        rows = [people[k] for k in order]
        req_ids = {r['pb_requisition_id'][0] for r in rows if r['pb_requisition_id']}
        req_country = {r['id']: r['country_id'] for r in self.env['pb.hiring.requisition'].sudo()
                       .search_read([('id', 'in', list(req_ids))], ['country_id'])}
        tag_ids = {t for r in rows for t in r['categ_ids']}
        tags = {t['id']: t['name'] for t in self.env['hr.applicant.category'].sudo()
                .search_read([('id', 'in', list(tag_ids))], ['name'])}
        pool_ids = {t for r in rows for t in r['talent_pool_ids']}
        pools = {t['id']: t['name'] for t in self.env['hr.talent.pool'].sudo()
                 .search_read([('id', 'in', list(pool_ids))], ['name'])}
        skills = {}
        if skills_on:
            sk_ids = {s for r in rows for s in r.get('skill_ids') or []}
            skills = {s['id']: s['name'] for s in self.env['hr.skill'].sudo()
                      .search_read([('id', 'in', list(sk_ids))], ['name'])}
        screen = dict(SCREEN_TAGS)
        q = fold(p.get('q') or '')
        built = []
        for r in rows:
            country = r['pb_country_id'] or (req_country.get(r['pb_requisition_id'][0])
                                            if r['pb_requisition_id'] else False)
            row = {
                'id': r['id'], 'name': r['partner_name'] or r['email_from'] or _('Candidate'),
                'email': r['email_from'] or '',
                'last_role': r['job_id'][1] if r['job_id'] else '',
                'requisition_id': r['pb_requisition_id'][0] if r['pb_requisition_id'] else False,
                'country_id': country[0] if country else False,
                'country': country[1] if country else '',
                'team_id': r['department_id'][0] if r['department_id'] else False,
                'team': r['department_id'][1] if r['department_id'] else '',
                'skills': [{'id': s, 'name': skills.get(s, '')} for s in r.get('skill_ids') or []],
                'tags': [{'id': t, 'name': tags.get(t, '')} for t in r['categ_ids']],
                'screen': r['pb_screen'] or '',
                'screen_label': screen.get(r['pb_screen'], ''),
                'source_id': r['source_id'][0] if r['source_id'] else False,
                'source': r['source_id'][1] if r['source_id'] else '',
                'applied_on': str(r['create_date'].date()) if r['create_date'] else '',
                'expires_on': str(r['pb_retention_until'] or ''),
                'in_pools': [pools.get(t, '') for t in r['talent_pool_ids']],
                'stage': r['stage_id'][1] if r['stage_id'] else '',
                'applications': r['applications'],
            }
            if q:
                hay = fold(' '.join([row['name'], row['email'], row['last_role'], row['team'],
                                     ' '.join(s['name'] for s in row['skills']),
                                     ' '.join(t['name'] for t in row['tags'])]))
                if q not in hay:
                    continue
            built.append(row)

        def ids(key):
            return {as_id(i) for i in p.get(key) or [] if as_id(i)}
        picks = {'skill_ids': ids('skill_ids'), 'country_ids': ids('country_ids'),
                 'team_ids': ids('team_ids'), 'tag_ids': ids('tag_ids'),
                 'source_ids': ids('source_ids')}
        facets = {'skills': {}, 'countries': {}, 'teams': {}, 'tags': {}, 'sources': {}}

        def bump(name, key, label):
            if key:
                f = facets[name].setdefault(key, {'id': key, 'name': label, 'count': 0})
                f['count'] += 1
        for row in built:
            for s in row['skills']:
                bump('skills', s['id'], s['name'])
            bump('countries', row['country_id'], row['country'])
            bump('teams', row['team_id'], row['team'])
            for t in row['tags']:
                bump('tags', t['id'], t['name'])
            bump('sources', row['source_id'], row['source'])

        def keep(row):
            if picks['skill_ids'] and not picks['skill_ids'] & {s['id'] for s in row['skills']}:
                return False
            if picks['country_ids'] and row['country_id'] not in picks['country_ids']:
                return False
            if picks['team_ids'] and row['team_id'] not in picks['team_ids']:
                return False
            if picks['tag_ids'] and not picks['tag_ids'] & {t['id'] for t in row['tags']}:
                return False
            if picks['source_ids'] and row['source_id'] not in picks['source_ids']:
                return False
            return True
        hits = [r for r in built if keep(r)]
        page = max(0, int(p.get('page') or 0))
        return {
            'rows': hits[page * BANK_PAGE:(page + 1) * BANK_PAGE],
            'total': len(hits),
            'page': page, 'page_size': BANK_PAGE,
            'facets': {k: sorted(v.values(), key=lambda f: (-f['count'], fold(f['name'])))[:30]
                       for k, v in facets.items()},
            'skills_on': skills_on,
            'include_all': bool(p.get('include_all')),
            'capped': len(raw) >= BANK_READ_CAP,
        }

    @api.model
    def bank_options(self):
        """The lists the bank's pickers need: open roles, every tag, skills."""
        self._require_bank()
        co = self.env.companies.ids or [self.env.company.id]
        roles = self.env['pb.hiring.requisition'].sudo().search(
            [('company_id', 'in', co), ('state', 'in', ('setup', 'open'))], order='title')
        out = {
            'roles': [{'id': r.id, 'title': r.title or '', 'country': r.country_id.name or '',
                       'department': r.department_id.name or ''} for r in roles],
            'tags': self.env['hr.applicant.category'].sudo().search_read([], ['name'], limit=300),
            'skills': [],
            'skills_on': self._skills_on(),
        }
        if out['skills_on']:
            out['skills'] = [{'id': s.id, 'name': s.name or '', 'type': s.skill_type_id.name or ''}
                             for s in self.env['hr.skill'].sudo().search([], order='name', limit=400)]
        return out

    def _act_bank_add_to_role(self, payload):
        """Copy people from the bank into a role's Applications received,
        files and all; the copy remembers where it came from. Somebody already
        on that role is skipped, never duplicated."""
        self._require_bank()
        req = self._get(payload)
        self._require_recruit(req)
        if not req.job_id:
            if req.state == 'setup':
                req._open_for_candidates()
            else:
                req._leg('the job for %s' % req.name, req._ensure_job)
        if not req.job_id:
            raise UserError(_("This role has no job yet, so there is nowhere to add a "
                              "candidate. Open it for candidates first."))
        Stage = self.env['hr.recruitment.stage']
        Applicant = self.env['hr.applicant'].sudo().with_context(active_test=False)
        added, skipped = [], []
        for src in Applicant.browse([as_id(i) for i in payload.get('applicant_ids') or []]).exists():
            if src.pb_anonymised_on:
                continue
            if src.email_normalized and Applicant.search_count(
                    [('job_id', '=', req.job_id.id), ('email_normalized', '=', src.email_normalized)]):
                skipped.append(src.partner_name or '')
                continue
            if src.job_id == req.job_id:
                skipped.append(src.partner_name or '')
                continue
            vals = {
                'job_id': req.job_id.id, 'department_id': req.job_id.department_id.id or False,
                'stage_id': Stage._pb_stage('screening').id or False,
                'pb_requisition_id': req.id, 'pb_screen': False, 'pb_other_job_id': False,
                'pb_origin_applicant_id': src.id, 'active': True, 'talent_pool_ids': [(5, 0, 0)],
                'company_id': req.company_id.id,
            }
            if src.pb_consent_on:
                vals.update({'pb_consent_on': src.pb_consent_on,
                             'pb_consent_text': src.pb_consent_text})
            copy = src.with_context(no_copy_in_partner_name=True, pb_no_stage_log=True).copy(vals)
            for att in self.env['ir.attachment'].sudo().search(
                    [('res_model', '=', 'hr.applicant'), ('res_id', '=', src.id)]):
                att.copy({'res_id': copy.id, 'access_token': False})
            copy.message_post(body=_("Added from the Resume bank (applied for %(job)s on %(when)s).",
                                     job=src.job_id.name or _('another role'),
                                     when=str((src.create_date or fields.Datetime.now()).date())),
                              message_type='comment', subtype_xmlid='mail.mt_note')
            added.append(copy.id)
        if not added and skipped:
            note = _("Already on %(role)s: %(who)s.", role=req.title, who=', '.join(skipped))
        elif len(added) == 1:
            note = _("Added to %s, in Applications received.", req.title)
        else:
            note = _("%(n)s people added to %(role)s, in Applications received.",
                     n=len(added), role=req.title)
        if added and skipped:
            note += ' ' + _("Already there: %s.", ', '.join(skipped))
        return {'added': added, 'skipped': skipped, 'requisition_id': req.id, 'note': note}

    def _act_bank_tag(self, payload):
        """Add or remove a tag ("Keep in touch", a skill word, anything)."""
        self._require_bank()
        Tag = self.env['hr.applicant.category'].sudo()
        tags = Tag.browse([as_id(i) for i in payload.get('tag_ids') or []]).exists()
        name = (payload.get('new_tag') or '').strip()
        if name:
            tag = Tag.search([('name', '=ilike', name)], limit=1) or Tag.create({'name': name[:60]})
            tags |= tag
        if not tags:
            raise UserError(_("Pick a tag, or type a new one."))
        apps = self.env['hr.applicant'].sudo().with_context(active_test=False).browse(
            [as_id(i) for i in payload.get('applicant_ids') or []]).exists()
        remove = payload.get('op') == 'remove'
        apps.write({'categ_ids': [(3 if remove else 4, t.id) for t in tags]})
        return {'tag_ids': tags.ids,
                'note': (_("Tag %(tag)s taken off %(n)s.", tag=', '.join(tags.mapped('name')), n=len(apps))
                         if remove else _("Tagged %(n)s: %(tag)s.", n=len(apps),
                                          tag=', '.join(tags.mapped('name'))))}

    def _act_bank_skills(self, payload):
        """Add or remove a skill on people in the bank (the standard skills
        list; each added at its type's default level)."""
        self._require_bank()
        if not self._skills_on():
            raise UserError(_("Skills are not switched on in this build. Tags work instead."))
        skills = self.env['hr.skill'].sudo().browse(
            [as_id(i) for i in payload.get('skill_ids') or []]).exists()
        apps = self.env['hr.applicant'].sudo().with_context(active_test=False).browse(
            [as_id(i) for i in payload.get('applicant_ids') or []]).exists()
        if not skills or not apps:
            raise UserError(_("Pick a skill and at least one person."))
        AppSkill = self.env['hr.applicant.skill'].sudo()
        remove = payload.get('op') == 'remove'
        n = 0
        for app in apps:
            for skill in skills:
                have = app.applicant_skill_ids.filtered(lambda s, sk=skill: s.skill_id == sk)
                if remove and have:
                    have.unlink()
                    n += 1
                elif not remove and not have:
                    levels = skill.skill_type_id.skill_level_ids
                    level = levels.filtered('default_level')[:1] if 'default_level' in levels._fields \
                        else levels[:1]
                    AppSkill.create({'applicant_id': app.id, 'skill_id': skill.id,
                                     'skill_type_id': skill.skill_type_id.id,
                                     'skill_level_id': (level or levels[:1]).id})
                    n += 1
        return {'note': _("Skills updated on %s.", len(apps)), 'changed': n}

    # =====================================================================
    #  Retention
    # =====================================================================
    @api.model
    def get_retention_preview(self):
        """Per market: its rule, who is due now, who expires within 30 days,
        who is past their date but kept (hired, still in play, an offer), a
        few names; the switch and the next run."""
        if not self._hiring_group():
            raise AccessError(_("The retention preview is for the hiring team."))
        co = self.env.companies
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=SOON_DAYS)
        Rule = self.env['pb.hiring.retention.rule'].sudo()
        rules = Rule.search([('company_id', 'in', co.ids)])
        apps = self.env['hr.applicant'].sudo().with_context(active_test=False).search(
            [('company_id', 'in', co.ids), ('pb_anonymised_on', '=', False),
             ('pb_retention_until', '!=', False), ('pb_retention_until', '<=', soon)],
            order='pb_retention_until, id', limit=5000)
        markets = {}
        modes = dict(PURGE_MODES)

        def market(country):
            key = country.id or 0
            if key not in markets:
                rule = rules.filtered(lambda r: r.country_id == country)[:1]
                months = rule.months if rule else (self.env.company.pb_retention_months or 12)
                markets[key] = {
                    'country_id': country.id or False,
                    'country': country.name or _('Everywhere else'),
                    'rule_id': rule.id or False, 'months': months,
                    'mode': rule.purge_mode if rule else 'anonymise',
                    'mode_label': modes.get(rule.purge_mode if rule else 'anonymise'),
                    'note': rule.note or '' if rule else '',
                    'due': 0, 'soon': 0, 'kept': 0, 'sample': [],
                }
            return markets[key]
        for rule in rules:
            market(rule.country_id)
        for app in apps:
            m = market(app._pb_country())
            why = app._pb_retention_protected()
            if app.pb_retention_until < today:
                if why:
                    m['kept'] += 1
                else:
                    m['due'] += 1
                    if len(m['sample']) < 5:
                        m['sample'].append({'id': app.id, 'name': app.partner_name or _('Candidate'),
                                            'until': str(app.pb_retention_until)})
            elif not why:
                m['soon'] += 1
        cron = self.env.ref('pb_hiring.cron_hiring_daily', raise_if_not_found=False)
        rows = sorted(markets.values(), key=lambda m: (not m['rule_id'], fold(m['country'])))
        return {
            'markets': rows,
            'due': sum(m['due'] for m in rows), 'soon': sum(m['soon'] for m in rows),
            'kept': sum(m['kept'] for m in rows),
            'enabled': flag(self.env, P_RETENTION_ENABLED),
            'next_run': str(cron.sudo().nextcall or '') if cron else '',
            'fallback_months': self.env.company.pb_retention_months or 12,
            'can_edit': bool(self._can_write()), 'can_run': bool(self._can_admin()),
            'modes': [{'key': k, 'label': v} for k, v in PURGE_MODES],
            'countries': self.env['res.country'].sudo().search_read([], ['name']),
        }

    def _act_retention_rule_save(self, payload):
        self._require_write()
        Rule = self.env['pb.hiring.retention.rule'].sudo()
        try:
            months = int(payload.get('months') or 0)
        except (TypeError, ValueError):
            raise UserError(_("Type the months as a number."))
        mode = payload.get('mode') if payload.get('mode') in dict(PURGE_MODES) else 'anonymise'
        vals = {'months': months, 'purge_mode': mode, 'note': (payload.get('note') or '')[:200]}
        if payload.get('id'):
            rule = Rule.browse(as_id(payload['id'])).exists()
            if not rule:
                raise UserError(_("That rule is no longer there."))
            before = {'id': rule.id, 'months': rule.months, 'mode': rule.purge_mode, 'note': rule.note}
            rule.write(vals)
            return {'id': rule.id, 'before': before,
                    'note': _("%(c)s keeps applications for %(m)s months now.",
                              c=rule.country_id.name, m=rule.months)}
        country = self.env['res.country'].sudo().browse(as_id(payload.get('country_id'))).exists()
        if not country:
            raise UserError(_("Pick the market."))
        if Rule.search_count([('company_id', '=', self.env.company.id), ('country_id', '=', country.id)]):
            raise UserError(_("%s already has a rule. Change that one.", country.name))
        vals.update({'company_id': self.env.company.id, 'country_id': country.id})
        rule = Rule.create(vals)
        return {'id': rule.id, 'note': _("%(c)s keeps applications for %(m)s months.",
                                         c=country.name, m=rule.months)}

    def _act_retention_rule_delete(self, payload):
        self._require_write()
        rule = self.env['pb.hiring.retention.rule'].sudo().browse(as_id(payload.get('id'))).exists()
        if not rule:
            raise UserError(_("That rule is no longer there."))
        saved = {'country_id': rule.country_id.id, 'months': rule.months,
                 'mode': rule.purge_mode, 'note': rule.note or ''}
        name = rule.country_id.name
        rule.unlink()
        return {'saved': saved, 'note': _("%s follows the company's own number again.", name)}

    def _act_retention_fallback(self, payload):
        self._require_write()
        try:
            months = int(payload.get('months') or 0)
        except (TypeError, ValueError):
            raise UserError(_("Type the months as a number."))
        if not 1 <= months <= 120:
            raise UserError(_("Keep an application for between 1 and 120 months."))
        company = self.env.company.sudo()
        before = company.pb_retention_months or 12
        company.write({'pb_retention_months': months})
        return {'before': before, 'note': _("Every other market keeps applications for %s months.", months)}

    def _act_retention_switch(self, payload):
        """The nightly clean-up, on or off — the head of hiring's call."""
        if not self._can_admin():
            raise AccessError(_("Switching the clean-up on or off is for the head of hiring."))
        on = bool(payload.get('on'))
        self.env['ir.config_parameter'].sudo().set_param(P_RETENTION_ENABLED, '1' if on else '0')
        return {'on': on, 'note': _("The clean-up runs every night now.") if on
                else _("The clean-up is switched off. Nothing is removed until it is on, or "
                       "somebody presses Run now.")}

    def _act_retention_run(self, payload):
        """"Run now": exactly what the night does, for this company."""
        if not self._can_admin():
            raise AccessError(_("Running the clean-up is for the head of hiring."))
        counts = self.env['hr.applicant']._pb_retention_leg(companies=self.env.company)
        n = counts['anonymised']
        note = _("Nobody was due.") if not n else (
            _("1 person was anonymised.") if n == 1 else _("%s people were anonymised.", n))
        if counts['failed']:
            note += ' ' + _("%s could not be done and are listed in the server log.", counts['failed'])
        return {'counts': counts, 'note': note}

    def _act_retention_extend(self, payload):
        """Keep one person longer — once, by the same months, written down."""
        app = self._applicant(payload.get('applicant_id'))
        self._require_recruit(app.pb_requisition_id)
        if app.pb_anonymised_on:
            raise UserError(_("This person has already been removed."))
        if app.pb_retention_extended_on:
            raise UserError(_("%(who)s already kept them longer on %(when)s. It can be done once.",
                              who=app.pb_retention_extended_by_id.name or _('Somebody'),
                              when=app.pb_retention_extended_on.strftime('%d %b %Y')))
        app.sudo().write({'pb_retention_extended_by_id': self.env.uid,
                          'pb_retention_extended_on': fields.Datetime.now()})
        app.sudo().message_post(body=_("Kept longer, until %s.", app.pb_retention_until),
                                message_type='comment', subtype_xmlid='mail.mt_note')
        return {'until': str(app.pb_retention_until or ''),
                'note': _("Kept until %s.", app.pb_retention_until.strftime('%d %b %Y')
                          if app.pb_retention_until else '')}

    @api.model
    def get_setup(self):
        res = super().get_setup()
        preview = self._safe(self.get_retention_preview, default=None) if self._hiring_group() else None
        res['retention'] = preview
        if preview is not None:
            n = len([m for m in preview['markets'] if m['rule_id']])
            status = _("%(m)s months unless a market says otherwise · %(n)s markets with their own rule",
                       m=preview['fallback_months'], n=n)
            status += ' · ' + (_("clean-up on") if preview['enabled'] else _("clean-up off"))
            res.setdefault('cards', []).append({
                'key': 'retention', 'title': _('Consent & retention'), 'icon': 'hourglass',
                'status': status, 'action': False, 'inline': True})
        return res
