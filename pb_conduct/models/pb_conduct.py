# -*- coding: utf-8 -*-
"""`pb.conduct` — the Conduct board's only server surface.

THE GATE IS THIS MODULE'S OWN TWO GROUPS (owner ruling P3). A general HR
user, a lifecycle user, a payroll officer, a line manager and a system
administrator who has not been named all get the same explained refusal and
no data. Every method re-checks; and every case read below is done AS THE
USER (no sudo), so the record rules are a second, independent wall. Only the
employee's NAME and job are read under sudo (the employee record prefetches
some forty payroll-only fields — the pb_pip `_emp` lesson).
"""

import base64
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
from odoo.tools.misc import format_date, format_datetime

from .conduct_common import (
    DEFAULT_VALID_MONTHS, NOTE_KINDS, OPEN_STATES, WARNING_OUTCOMES,
    initials, is_head, is_reader,
)

_logger = logging.getLogger(__name__)

PAGE_SIZE = 60
FILE_MAX_BYTES = 10 * 1024 * 1024

WHERE_DOMAINS = {
    'concern': [('state', '=', 'concern')],
    'hearing': [('state', '=', 'hearing')],
    'decision': [('state', '=', 'decision')],
    'letter': [('state', '=', 'letter')],
    'closed': [('state', '=', 'closed')],
}


class PbConduct(models.AbstractModel):
    _name = 'pb.conduct'
    _inherit = ['pb.filter.mixin']
    _description = 'Conduct cases board data'

    # ============================================================ gates
    @api.model
    def _can_read(self):
        return is_reader(self.env)

    @api.model
    def can_open(self):
        """The Talent rail's probe: is this person named for conduct cases?"""
        return self._can_read()

    @api.model
    def _refusal(self):
        return _("Conduct cases are seen only by the people HR names for them on "
                 "the Access screen. Being in HR, running payroll or managing a "
                 "team does not include it. Ask your head of HR if you believe "
                 "you should have it.")

    @api.model
    def _require(self):
        if not self._can_read():
            raise AccessError(self._refusal())

    @api.model
    def _require_head(self):
        if not is_head(self.env):
            raise AccessError(_("Only the head of HR for conduct cases can change this."))

    @api.model
    def _scope(self):
        return [('company_id', 'in', self.env.companies.ids)]

    @api.model
    def _safe(self, fn, default=0):
        try:
            with self.env.cr.savepoint(flush=False):
                return fn()
        except Exception as e:      # noqa: BLE001
            _logger.debug('conduct board metric failed: %s', e)
            return default

    @api.model
    def _case(self, case_id):
        self._require()
        case = self.env['pb.conduct.case'].browse(int(case_id or 0)).exists()
        if not case:
            raise UserError(_("This case no longer exists, or it is not one you can see."))
        case.check_access('read')
        return case

    @api.model
    def _letter(self, letter_id):
        self._require()
        letter = self.env['pb.conduct.letter'].browse(int(letter_id or 0)).exists()
        if not letter:
            raise UserError(_("This letter no longer exists."))
        letter.check_access('read')
        return letter

    # ============================================================ head
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'why': self._refusal()}
        Case = self.env['pb.conduct.case']
        Letter = self.env['pb.conduct.letter']
        scope = self._scope()
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()

        def count(dom, model=Case):
            return self._safe(lambda: model.search_count(dom))

        kpis = {
            'open': count(scope + [('state', 'in', OPEN_STATES)]),
            'hearings_soon': count(scope + [('state', '=', 'hearing'),
                                            ('hearing_date', '>=', now),
                                            ('hearing_date', '<=', now + timedelta(days=7))]),
            'to_decide': count(scope + [('state', '=', 'decision')]),
            'letters': count(scope + [('state', '=', 'letter')]),
            'replies': count([('company_id', 'in', self.env.companies.ids),
                              ('reply', '!=', False), ('reply_seen', '=', False)],
                             model=Letter),
            'live': count(scope + [('state', '=', 'closed'),
                                   ('outcome', 'in', list(WARNING_OUTCOMES)),
                                   ('valid_until', '>=', today)]),
        }
        Reason = self.env['pb.conduct.reason']
        reasons = self._safe(lambda: Reason.search(
            ['|', ('company_id', '=', False), ('company_id', 'in', self.env.companies.ids)]),
            default=Reason)
        return {
            'allowed': True, 'why': '',
            'is_head': is_head(self.env),
            'total': count(scope),
            'kpis': kpis,
            'reasons': [{'id': r.id, 'name': r.name or ''} for r in reasons],
            'outcomes': [{'key': k, 'label': v} for k, v in
                         Case._fields['outcome']._description_selection(self.env)],
            'note_kinds': [{'key': k, 'label': v} for k, v in
                           self.env['pb.conduct.note']._fields['kind']._description_selection(self.env)],
            'valid_months': DEFAULT_VALID_MONTHS,
            'today': fields.Date.to_string(today),
        }

    # ============================================================ filter panel
    def _pbf_model(self):
        return 'pb.conduct.case'

    def _pbf_screen(self):
        return 'conduct'

    def _pbf_base_domain(self):
        return self._scope()

    def _pbf_search_domain(self, search):
        q = (search or '').strip()
        if not q:
            return None
        parts = [Domain('name', 'ilike', q), Domain('summary', 'ilike', q)]
        try:
            emp_ids = self.env['hr.employee'].sudo().with_context(active_test=False).search(
                [('company_id', 'in', self.env.companies.ids),
                 '|', ('name', 'ilike', q), ('barcode', 'ilike', q)]).ids
        except Exception:   # noqa: BLE001
            emp_ids = []
        if emp_ids:
            parts.append(Domain('employee_id', 'in', emp_ids))
        return Domain.OR(parts)

    def _pbf_sorts(self):
        return [
            {'key': 'recent', 'label': _('Opened most recently'), 'order': 'id desc'},
            {'key': 'hearing', 'label': _('Hearing date, soonest first'),
             'order': 'hearing_date asc, id desc'},
            {'key': 'oldest', 'label': _('Opened longest ago'), 'order': 'id asc'},
        ]

    def _pbf_spec(self):
        return [
            {'key': 'where', 'label': _('Step'), 'icon': 'route', 'group': 'other',
             'type': 'choice', 'pinned': True, 'requires': ['state'],
             'help': _('The steps above the table.'),
             'options': [
                 {'value': 'concern', 'label': _('Concern'), 'tone': 'slate',
                  'domain': WHERE_DOMAINS['concern']},
                 {'value': 'hearing', 'label': _('Hearing'), 'tone': 'blue',
                  'domain': WHERE_DOMAINS['hearing']},
                 {'value': 'decision', 'label': _('Decision'), 'tone': 'amber',
                  'domain': WHERE_DOMAINS['decision']},
                 {'value': 'letter', 'label': _('Letter'), 'tone': 'amber',
                  'domain': WHERE_DOMAINS['letter']},
                 {'value': 'closed', 'label': _('Closed'), 'tone': 'green',
                  'domain': WHERE_DOMAINS['closed']},
             ]},
            {'key': 'reason', 'label': _('Reason'), 'icon': 'tag', 'group': 'other',
             'type': 'many2one', 'path': 'reason_id', 'pinned': True},
            {'key': 'outcome', 'label': _('Decision'), 'icon': 'scale', 'group': 'other',
             'type': 'selection', 'path': 'outcome', 'pinned': True},
            {'key': 'opened', 'label': _('Opened'), 'icon': 'calendar', 'group': 'dates',
             'type': 'date', 'path': 'opened_on', 'presets': 'past'},
            {'key': 'person', 'label': _('Who it is about'), 'icon': 'user',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id',
             'label_sudo': True},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'department_id',
             'none_label': _('No department'), 'label_sudo': True},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All cases'), 'icon': 'scale', 'filters': {}},
            {'key': 'open', 'label': _('Open cases'),
             'filters': {'where': ['concern', 'hearing', 'decision', 'letter']}},
            {'key': 'closed', 'label': _('Closed cases'), 'filters': {'where': ['closed']}},
        ]

    @api.model
    def pbf_layout(self):
        if not self._can_read():
            return {'refused': self._refusal()}
        return super().pbf_layout()

    @api.model
    def _pbf_step_counts(self, filters, search):
        spec = self._pbf_clean_spec()
        s = next((x for x in spec if x['key'] == 'where'), None)
        if not s:
            return {}
        res = self._pbf_count_section(s, filters or {}, search, spec)
        return {r['v']: r['n'] for r in res.get('values') or []}

    @api.model
    def get_cases_page(self, filters=None, search=None, sort=None, offset=0,
                       limit=PAGE_SIZE):
        if not self._can_read():
            return {'rows': [], 'total': 0, 'offset': 0, 'steps': {}}
        Case = self.env['pb.conduct.case']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'id desc'
        rows = []
        for case in Case.search(domain, order=order, offset=offset, limit=limit):
            try:
                rows.append(self._row(case))
            except Exception as e:      # noqa: BLE001 — one bad row never blanks it
                _logger.debug('conduct row %s failed: %s', case.id, e)
        out = {'rows': rows, 'total': Case.search_count(domain), 'offset': offset}
        if not offset:
            out['steps'] = self._safe(lambda: self._pbf_step_counts(filters, search),
                                      default={})
        return out

    @api.model
    def _when(self, value):
        if not value:
            return ''
        return format_datetime(self.env, value, dt_format='d MMM y, HH:mm')

    @api.model
    def _day(self, value):
        return format_date(self.env, value) if value else ''

    @api.model
    def _row(self, case):
        emp = case.employee_id.sudo()
        nxt = ''
        if case.state == 'hearing' and case.hearing_date:
            nxt = _('Hearing %s', self._when(case.hearing_date))
        elif case.state == 'decision':
            nxt = _('Decide the outcome')
        elif case.state == 'letter':
            nxt = _('Issue the letter')
        elif case.state == 'concern':
            nxt = _('Look into it, then plan a hearing')
        today = fields.Date.context_today(self)
        return {
            'id': case.id, 'name': case.name or '',
            'employee': emp.name or '', 'employee_id': emp.id,
            'initials': initials(emp.name or ''),
            'department': case.department_id.sudo().name or '',
            'company': case.company_id.name or '',
            'reason': case.reason_id.name or '',
            'opened_on': self._day(case.opened_on),
            'state': case.state, 'state_label': case._state_label(),
            'outcome': case.outcome or '', 'outcome_label': case._outcome_label(),
            'valid_until': self._day(case.valid_until),
            'live': bool(case.state == 'closed' and case.valid_until
                         and case.valid_until >= today),
            'next': nxt,
            'replies': len(case.letter_ids.filtered(lambda l: l.reply and not l.reply_seen)),
        }

    # ============================================================ drawer
    @api.model
    def _country_notes(self, case):
        country = case.company_id.country_id
        if not country:
            return []
        Note = self.env['pb.conduct.country.note']
        rows = Note.search([('country_id', '=', country.id)])
        labels = dict(Note._fields['step']._description_selection(self.env))
        return [{'step': n.step, 'step_label': labels.get(n.step, ''),
                 'note': n.note or '', 'current': n.step == case.state}
                for n in rows]

    @api.model
    def get_case(self, case_id):
        case = self._case(case_id)
        row = self._row(case)
        emp = case.employee_id.sudo()
        kinds = dict(self.env['pb.conduct.note']._fields['kind']._description_selection(self.env))
        notes = [{'id': n.id, 'kind': n.kind, 'kind_label': kinds.get(n.kind, ''),
                  'date': self._day(n.date), 'body': n.body or '',
                  'author': n.author_id.name or ''} for n in case.note_ids]
        Att = self.env['ir.attachment']
        files = [{'id': a.id, 'name': a.name or '',
                  'url': '/web/content/%s?download=true' % a.id,
                  'when': self._day(a.create_date.date()) if a.create_date else ''}
                 for a in Att.search([('res_model', '=', 'pb.conduct.case'),
                                      ('res_id', '=', case.id)], order='id desc')]
        letters = []
        for l in case.letter_ids.sorted('id'):
            letters.append({
                'id': l.id, 'kind': l.kind,
                'kind_label': dict(l._fields['kind']._description_selection(self.env)).get(l.kind, ''),
                'title': l.title or '', 'body': l.body or '',
                'state': l.state, 'issued_on': self._day(l.issued_on),
                'pdf_url': ('/web/content/%s?download=true' % l.attachment_id.id)
                if l.attachment_id else '',
                'read_on': self._when(l.read_on), 'reply': l.reply or '',
                'reply_on': self._when(l.reply_on), 'reply_seen': l.reply_seen,
            })
        events = [{'when': self._when(e.create_date), 'who': e.user_id.sudo().name or '',
                   'text': e.text or ''} for e in case.event_ids[:40]]
        has_exit = 'pb.journey.case' in self.env and 'pb.journey.template' in self.env
        row.update({
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '') or '',
            'summary': case.summary or '', 'raised_by': case.raised_by or '',
            'incident_date': self._day(case.incident_date),
            'hearing_date': self._when(case.hearing_date),
            'hearing_date_raw': fields.Datetime.to_string(case.hearing_date)
            if case.hearing_date else '',
            'hearing_place': case.hearing_place or '',
            'hearing_attendees': case.hearing_attendees or '',
            'hearing_held_on': self._day(case.hearing_held_on),
            'decision_summary': case.decision_summary or '',
            'decided_on': self._day(case.decided_on),
            'decided_by': case.decided_by.sudo().name or '',
            'closed_on': self._day(case.closed_on),
            'close_reason': case.close_reason or '',
            'notes': notes, 'files': files, 'letters': letters, 'events': events,
            'history': case._history_rows(),
            'country': case.company_id.country_id.name or '',
            'country_notes': self._country_notes(case),
            'can': {
                'plan_hearing': case.state in ('concern', 'hearing'),
                'skip_hearing': case.state == 'concern',
                'hearing_held': case.state == 'hearing',
                'decide': case.state == 'decision',
                'invite': case.state in ('concern', 'hearing'),
                'close': case.state in OPEN_STATES,
                'reopen': case.state == 'closed',
                'exit': case.outcome == 'dismissal' and has_exit and not case.exit_case_id,
            },
        })
        return row

    # ============================================================ new case
    @api.model
    def employee_options(self, term=''):
        self._require()
        term = (term or '').strip()
        if len(term) < 2:
            return []
        people = self.env['hr.employee'].sudo().search([
            ('company_id', 'in', self.env.companies.ids),
            ('user_id', '!=', self.env.uid),
            '|', ('name', 'ilike', term), ('barcode', 'ilike', term)], limit=8)
        return [{'id': e.id, 'name': e.name or '', 'code': e.barcode or '',
                 'department': e.department_id.name or '',
                 'company': e.company_id.name or ''} for e in people]

    @api.model
    def create_case(self, vals):
        self._require()
        vals = vals or {}
        emp = self.env['hr.employee'].sudo().browse(int(vals.get('employee_id') or 0)).exists()
        if not emp or emp.company_id.id not in self.env.companies.ids:
            raise UserError(_("Pick who the case is about."))
        if emp.user_id and emp.user_id.id == self.env.uid:
            raise UserError(_("You cannot open a case about yourself."))
        reason = self.env['pb.conduct.reason'].browse(int(vals.get('reason_id') or 0)).exists()
        if not reason:
            raise UserError(_("Choose the reason."))
        summary = (vals.get('summary') or '').strip()
        if not summary:
            raise UserError(_("Write what happened, in a few sentences."))
        case = self.env['pb.conduct.case'].create({
            'employee_id': emp.id,
            'reason_id': reason.id,
            'summary': summary,
            'incident_date': vals.get('incident_date') or False,
            'raised_by': (vals.get('raised_by') or '').strip() or False,
        })
        return {'id': case.id}

    # ============================================================ moves
    @api.model
    def move(self, case_id, verb, args=None):
        case = self._case(case_id)
        args = args or {}
        if verb == 'plan_hearing':
            case.action_plan_hearing(args.get('hearing_date'), args.get('place'),
                                     args.get('attendees'))
            msg = _("Hearing saved.")
        elif verb == 'hearing_held':
            case.action_hearing_held(args.get('held_on') or None, args.get('minutes'))
            msg = _("Hearing recorded. Next: the decision.")
        elif verb == 'skip_hearing':
            case.action_skip_hearing(args.get('why'))
            msg = _("Moved to the decision.")
        elif verb == 'decide':
            case.action_decide(args.get('outcome'), args.get('summary'),
                               args.get('valid_until') or None, args.get('decided_on') or None)
            msg = _("Decision saved. The letter is ready to check and issue.")
        elif verb == 'invite':
            self.env['pb.conduct.letter'].prepare(case, 'invite')
            msg = _("Invitation prepared. Check it, then issue it.")
        elif verb == 'close':
            case.action_close(args.get('why'))
            msg = _("Case closed.")
        elif verb == 'reopen':
            case.action_reopen()
            msg = _("Case opened again.")
        elif verb == 'exit':
            case.action_start_exit()
            msg = _("The leaving checklist is open on the employee's record.")
        else:
            raise UserError(_("That cannot be done here."))
        return {'ok': True, 'msg': msg}

    @api.model
    def add_note(self, case_id, kind, body, date=None):
        case = self._case(case_id)
        if kind not in dict(NOTE_KINDS):
            kind = 'other'
        if not (body or '').strip():
            raise UserError(_("Write the note first."))
        self.env['pb.conduct.note'].create({
            'case_id': case.id, 'kind': kind, 'body': body.strip(),
            'date': date or fields.Date.context_today(self)})
        return {'ok': True, 'msg': _("Note added.")}

    @api.model
    def add_file(self, case_id, name, data):
        """A file kept WITH THE CASE (never in the documents vault)."""
        case = self._case(case_id)
        case.check_access('write')
        try:
            raw = base64.b64decode(data or b'', validate=False)
        except Exception:       # noqa: BLE001
            raw = b''
        if not raw:
            raise UserError(_("The file is empty."))
        if len(raw) > FILE_MAX_BYTES:
            raise UserError(_("The file is larger than 10 MB."))
        self.env['ir.attachment'].create({
            'name': (name or 'file').strip()[:200], 'type': 'binary',
            'datas': base64.b64encode(raw), 'res_model': 'pb.conduct.case',
            'res_id': case.id,
        })
        case._log(_('File added: %s.', (name or 'file').strip()[:200]))
        return {'ok': True, 'msg': _("File added to the case.")}

    @api.model
    def save_letter(self, letter_id, title, body):
        letter = self._letter(letter_id)
        if letter.state != 'draft':
            raise UserError(_("An issued letter cannot be changed."))
        if not (title or '').strip() or not (body or '').strip():
            raise UserError(_("A letter needs a title and some text."))
        letter.write({'title': title.strip(), 'body': body.strip()})
        return {'ok': True, 'msg': _("Letter saved.")}

    @api.model
    def issue_letter(self, letter_id):
        letter = self._letter(letter_id)
        letter.action_issue()
        return {'ok': True, 'msg': _("Letter issued. The employee can read it on their own page now.")}

    @api.model
    def delete_letter(self, letter_id):
        letter = self._letter(letter_id)
        case = letter.case_id
        title = letter.title
        letter.unlink()
        case._log(_('Draft letter deleted: %s.', title))
        return {'ok': True, 'msg': _("Draft letter deleted.")}

    @api.model
    def reply_seen(self, letter_id):
        letter = self._letter(letter_id)
        letter.sudo().write({'reply_seen': True})
        return {'ok': True}

    # ============================================================ set up
    @api.model
    def setup_action(self, which):
        """The set-up lists (head of HR for conduct cases only)."""
        self._require_head()
        xmlids = {
            'reasons': 'pb_conduct.action_pb_conduct_reason',
            'letters': 'pb_conduct.action_pb_conduct_letter_template',
            'countries': 'pb_conduct.action_pb_conduct_country_note',
        }
        if which not in xmlids:
            raise UserError(_("That cannot be done here."))
        return self.env['ir.actions.act_window']._for_xml_id(xmlids[which])
