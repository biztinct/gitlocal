# -*- coding: utf-8 -*-
"""PSCHEME P2b B — the pay scheme belongs to the person, in the Updates sheets.

Owner ruling R1: a person's pay scheme is stored on the PERSON, from a date,
pre-filled from their Country of work. Two sheets carry it:

* the new-employee rows (`updates_joiners.py`): "Pay scheme" is a VALUE.
  Empty, the usual scheme of the row's Country of work (`pb.scheme.map.
  usual_scheme`, the answer Add employee gives); several and no usual one,
  the row asks, with the country's schemes in its dropdown. Filled, it must be
  an active scheme of that country, else the row says why and names the
  allowed ones. When the person is added it becomes their own pay scheme from
  their first day (`source='import'`), with the mid-month advance the
  "Mid-month advance" column gives, else the scheme's one paired advance
  (ledger A13: only a real mid-month scheme; R7: never the team's).
* the rows of people already here (lasting changes): a "Pay scheme" cell that
  differs from their pay scheme today asks for the change from the row's start
  date, through the same door every pay scheme change uses
  (`pb.scheme.board.person_set`, ledger R9: a payroll manager approves, or it
  is saved at once where nobody else is set up). An unchanged cell changes
  nothing. A Country of work changed in the same row SUGGESTS the new
  country's usual scheme in the review — never applied by itself (A7).

Nothing here writes a team line, and every person row goes through phase 1's
one writer (`_person_set_write`) or its door (`person_set`).
"""
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.pb_hr_payroll_formula.models.schememap_approval import SCHEMEMAP_WRITE
from odoo.addons.pb_records.models.pb_records_io import _norm

_logger = logging.getLogger(__name__)

COUNTRY = 'f:hr.employee:payroll_country'
MAIN_KINDS = ('regular', 'end_cycle')
#: A "Mid-month advance" cell that means "none".
NO_WORDS = ('no', 'none', 'n', '0', 'không', 'khong', 'tidak', 'tidak ada', '-')
#: At most this many pay scheme changes in one sheet.
MAX_SCHEME_CHANGES = 2000


class PbUpdatesJoinerScheme(models.Model):
    _inherit = 'pb.updates.joiner'

    scheme_id = fields.Many2one('hr.formula.config', string='Their pay scheme',
                                ondelete='set null')
    advance_scheme_id = fields.Many2one('hr.formula.config',
                                        string='Their mid-month advance',
                                        ondelete='set null')


class PbUpdatesPersonScheme(models.AbstractModel):
    _inherit = 'pb.updates.desk'

    # =================================================================
    # Small readers
    # =================================================================
    @api.model
    def _country_labels(self):
        field = self.env['hr.employee']._fields.get('payroll_country')
        return dict(field._description_selection(self.env)) if field else {}

    @api.model
    def _country_code_of(self, text):
        """A Country of work typed in a cell — its code ('VN') or its name in
        English or the reader's language — as the code, else ''."""
        value = _norm(text)
        if not value:
            return ''
        labels = self._country_labels()
        english = self.with_context(lang='en_US')._country_labels()
        for code in labels:
            if value in (_norm(code), _norm(labels.get(code)), _norm(english.get(code))):
                return code
        return ''

    @api.model
    def _company_has_advances(self):
        """True when the company has an active mid-month advance scheme."""
        return bool(self.env['hr.formula.config'].sudo().search_count([
            ('state', '=', 'active'), ('cycle_type', '=', 'mid_cycle'),
            '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)]))

    @api.model
    def _board(self):
        return self.env['pb.scheme.board'].sudo()

    @api.model
    def _advance_from_text(self, config, text):
        """`(advance config, why)` for a "Mid-month advance" cell beside
        `config`: empty = the scheme's one paired advance (else none); a "no"
        word = none; a name = that advance, when it is paired with `config`."""
        Config = self.env['hr.formula.config']
        if not config:
            return Config, ''
        board = self._board()
        pairs = board._advance_pairs([config.id]).get(str(config.id)) or []
        value = _norm(text)
        if not value:
            return board.advance_default(config), ''
        if value in NO_WORDS:
            return Config, ''
        hit = [p for p in pairs if _norm(p['name']) == value]
        if hit:
            return Config.sudo().browse(hit[0]['id']), ''
        if pairs:
            return Config, _("%(text)s is not a mid-month advance of %(scheme)s. "
                             "Type one of: %(names)s, or No, or leave the cell "
                             "empty.") % {'text': text, 'scheme': config.name or '',
                                          'names': ', '.join(p['name'] for p in pairs)}
        return Config, _("%(scheme)s has no mid-month advance. Leave the cell "
                         "empty, or type No.") % {'scheme': config.name or ''}

    @api.model
    def _scheme_refusal(self, config, code, who):
        """Why `config` cannot be the own pay scheme of somebody working in
        `code` here, or ''."""
        countries = self._country_labels()
        if config.cycle_type not in MAIN_KINDS:
            return _("%(scheme)s cannot be somebody's own pay scheme: pick the pay "
                     "scheme that pays the month.") % {'scheme': config.name or ''}
        if config.company_id and config.company_id not in self.env.companies:
            return _("%(scheme)s belongs to %(company)s, so it cannot pay "
                     "%(person)s.") % {'scheme': config.name or '',
                                       'company': config.company_id.name or '',
                                       'person': who}
        if code and config.country_code and config.country_code != code:
            return _("%(scheme)s is a pay scheme for %(theirs)s, but %(person)s "
                     "works in %(mine)s.") % {
                         'scheme': config.name or '',
                         'theirs': countries.get(config.country_code) or config.country_code,
                         'person': who, 'mine': countries.get(code) or code}
        return ''

    @api.model
    def _scheme_choices(self, code):
        """`[{id, name}]` — the pay schemes a person of `code` can be given."""
        if not code:
            return []
        configs = self.env['pb.scheme.map'].sudo()._country_schemes(
            self.env.company.id, code).filtered(lambda c: c.cycle_type in MAIN_KINDS)
        return [{'id': c.id, 'name': c.name or ''} for c in configs]

    # =================================================================
    # B.1 — a new employee's own pay scheme
    # =================================================================
    @api.model
    def _judge_joiner_scheme(self, j):
        """Fill `j` with the row's own pay scheme. Writes nothing.

        `country` (code), `scheme_id`/`scheme`, `advance_id`/`advance`,
        `scheme_options` (the dropdown), `scheme_ask` (several, no usual
        one), `scheme_why` (the row cannot be added until it is fixed) and
        `scheme_from` (a calm line saying where it came from)."""
        cell = (j.get('cells') or {}).get(COUNTRY)
        code = ''
        if cell and cell.get('status') != 'refused':
            code = self._country_code_of(cell.get('value') if cell.get('value') not in
                                         (None, '') else cell.get('new'))
        countries = self._country_labels()
        j['country'] = code
        who = j.get('name') or _("this person")
        Config = self.env['hr.formula.config'].sudo()
        choices = self._scheme_choices(code)
        j['scheme_options'] = choices
        config = Config
        text = (j.get('scheme_text') or '').strip()
        if text:
            config, why = self._named_scheme(text)
            if why:
                j['scheme_why'] = why
                return j
            why = self._scheme_refusal(config, code, who)
            if why:
                names = ', '.join(c['name'] for c in choices)
                j['scheme_why'] = (why + ' ' + _("Pick one of: %s.") % names) if names else why
                return j
            j['scheme_from'] = _("Their own pay scheme, from the sheet.")
        elif code:
            found = self.env['pb.scheme.map'].sudo().usual_scheme(
                self.env.company.id, code, j.get('team_id') or 0)
            options = found['options'].filtered(lambda c: c.cycle_type in MAIN_KINDS)
            if not options:
                j['scheme_note'] = _("No pay scheme for %(country)s yet. They are added "
                                     "without one: give them a pay scheme from their "
                                     "record once %(country)s has one.") % {
                                         'country': countries.get(code) or code}
                return j
            if len(options) > 1 and found['ask']:
                j['scheme_ask'] = True
                j['scheme_why'] = _("%(country)s has %(n)s pay schemes. Pick the one "
                                    "that pays %(person)s.") % {
                                        'country': countries.get(code) or code,
                                        'n': len(options), 'person': who}
                return j
            config = found['config'] if found['config'] in options else options[:1]
            j['scheme_from'] = _("The only pay scheme for %s.") % (countries.get(code) or code) \
                if len(options) == 1 else \
                _("The usual pay scheme for %s.") % (countries.get(code) or code)
        else:
            # No Country of work in the row and no scheme named: the team's
            # usual scheme pays them (R2), nothing is written on the person.
            return j
        j['scheme_id'] = config.id
        j['scheme'] = config.name or ''
        advance, why = self._advance_from_text(config, j.get('advance_text'))
        if why:
            j['scheme_why'] = why
            return j
        j['advance_id'] = advance.id or 0
        j['advance'] = advance.name or ''
        return j

    @api.model
    def _joiner_scheme_write(self, emp_id, scheme_id, advance_id, day):
        """The new person's own pay scheme (and advance), from `day`, through
        the one writer. The new-hire route already approved the person."""
        if not scheme_id or 'pb.scheme.board' not in self.env:
            return 0
        Config = self.env['hr.formula.config'].sudo()
        config = Config.browse(int(scheme_id)).exists()
        if not config:
            return 0
        employee = self.env['hr.employee'].sudo().browse(int(emp_id)).exists()
        if not employee:
            return 0
        advance = Config.browse(int(advance_id or 0)).exists()
        board = self._board().with_context(**{SCHEMEMAP_WRITE: True})
        start = fields.Date.to_date(day) or self.env['pb.records.apply']._today_for()
        return board._person_set_write(employee, config, advance or False, start,
                                       source='import')

    # =================================================================
    # B.2 — people already here: a pay scheme cell is a change from a date
    # =================================================================
    @api.model
    def review(self, file_b64='', filename='', columns=None, kind='lasting', month=None,
               cutover=None):
        if kind == 'lasting':
            cols = self._clean_columns(columns)
            if cols['identity'] and not cols['used'] and cols.get('scheme'):
                # A sheet that only changes pay schemes: the desk's peek needs
                # a field to judge, so the rows are matched here, its way.
                return self._scheme_only_review(file_b64, filename, cols)
        answer = super().review(file_b64, filename, columns, kind, month, cutover)
        if kind != 'lasting' or not isinstance(answer, dict) or not answer.get('ok'):
            return answer
        rows = answer.get('rows') or []
        if any('scheme_text' in r for r in rows) or any(
                COUNTRY in (r.get('cells') or {}) for r in rows):
            self._judge_scheme_cells(rows)
            answer['scheme_changes'] = sum(1 for r in rows if (r.get('scheme_change') or {})
                                           .get('status') == 'ok')
        return answer

    @api.model
    def _scheme_only_review(self, file_b64, filename, cols):
        """`review` for a file whose only values are "Pay scheme" (and its
        "Mid-month advance" and start date): the rows found by the desk's own
        matching ladder, nothing judged by the desk (nothing for it to write)."""
        desk = self._gate()
        res, body = desk._import_columns(0, file_b64, filename)
        if not res.get('ok'):
            return res
        if not body:
            return {'ok': False, 'empty': True, 'filename': res.get('filename'),
                    'msg': _("This file has headings only — fill it in and drop it again.")}
        index = desk._io_index(desk._matching({}, ctx={}))
        start_col = cols.get('start') or 0
        extras = [c for c in (start_col, cols.get('scheme'), cols.get('advance')) if c]
        matched, unmatched = [], []
        for offset, row in body[:10000]:
            values = {key: desk._io_text(desk._io_cell(row, idx))
                      for key, idx in cols['identity'].items()}
            emp_id, method, why = desk._io_match(
                index, values.get('code'), values.get('name'), values.get('email'))
            extra = {idx: desk._io_extra(desk._io_cell(row, idx)) for idx in extras}
            if emp_id:
                matched.append({'row': offset, 'emp_id': emp_id, 'method': method,
                                'extra': extra})
            else:
                unmatched.append({'row': offset, 'code': values.get('code') or '',
                                  'name': values.get('name') or '',
                                  'email': values.get('email') or '', 'why': why,
                                  'values': {}, 'extra': extra})
        starts = {}
        if start_col:
            starts, refusal = self._row_starts(desk, {'matched': matched,
                                                      'unmatched': unmatched}, start_col)
            if refusal:
                return {'ok': False, 'msg': refusal}
        info = self._people_info(desk, {m['emp_id'] for m in matched})
        count = {}
        for m in matched:
            count[m['emp_id']] = count.get(m['emp_id'], 0) + 1

        def text(extra, idx):
            raw = extra.get(idx) if idx else None
            return '' if raw in (None, False) else str(raw).strip()
        rows = []
        for m in matched:
            person = info.get(m['emp_id']) or {}
            row = {'row': m['row'], 'emp_id': m['emp_id'], 'method': m.get('method'),
                   'name': person.get('name') or '', 'code': person.get('code') or '',
                   'department': person.get('department') or '',
                   'twice': count.get(m['emp_id'], 0) > 1, 'cells': {},
                   'scheme_text': text(m['extra'], cols.get('scheme')),
                   'advance_text': text(m['extra'], cols.get('advance'))}
            if start_col:
                row['start'] = starts.get(m['row']) or {}
            rows.append(row)
        for entry in unmatched:
            extra = entry.pop('extra', None) or {}
            entry['scheme'] = text(extra, cols.get('scheme'))
            entry['advance'] = text(extra, cols.get('advance'))
            if start_col:
                entry['start'] = starts.get(entry['row']) or {}
        self._judge_scheme_cells(rows)
        return {
            'ok': True, 'filename': res.get('filename') or filename,
            'summary': {'rows': len(body), 'people_matched': len(count),
                        'people_unmatched': len(unmatched), 'changes_ok': 0,
                        'changes_same': 0, 'changes_refused': 0, 'cells_blank': 0,
                        'columns_used': 0, 'columns_ignored': []},
            'identity': '', 'truncated': len(body) > 10000, 'columns': [],
            'pay_items': False, 'schemes': [], 'no_scheme': 0, 'dated': bool(start_col),
            'today': fields.Date.to_string(self.env['pb.records.apply']._today_for()),
            'rows': rows, 'unmatched': unmatched, 'changes': [],
            'scheme_changes': sum(1 for r in rows if (r.get('scheme_change') or {})
                                  .get('status') == 'ok'),
        }

    @api.model
    def _judge_scheme_cells(self, rows):
        """Each matched row's pay scheme cell, judged against the person's pay
        scheme today: `row['scheme_change']` = `{status: same|ok|refused, old,
        new, config_id, advance_id, advance, why}`; and, where the row moves
        their Country of work and says nothing about the pay scheme,
        `row['scheme_suggest']` with the new country's usual scheme."""
        emp_ids = [r['emp_id'] for r in rows if r.get('emp_id')]
        if not emp_ids:
            return rows
        Map = self.env['pb.scheme.map'].sudo()
        Employee = self.env['hr.employee'].sudo()
        main_cycle = {}
        countries = self._country_labels()
        people = {e.id: e for e in Employee.browse(emp_ids).exists()}
        for row in rows:
            emp = people.get(row.get('emp_id'))
            if not emp:
                continue
            key = emp.company_id.id
            if key not in main_cycle:
                main_cycle[key] = Employee._pb_main_cycle(key)
            now = Map.with_context(pb_scheme_main_question=True).resolve(
                emp.id, main_cycle[key])
            now_name = now.get('config_name') or ''
            row['scheme_now'] = now_name
            row['scheme_now_own'] = now.get('rung') == 'person'
            country_cell = (row.get('cells') or {}).get(COUNTRY) or {}
            moved_to = ''
            if country_cell.get('status') == 'ok':
                moved_to = self._country_code_of(country_cell.get('value'))
            code = moved_to or emp.payroll_country or ''
            text = (row.get('scheme_text') or '').strip()
            who = emp.name or ''
            if text:
                if _norm(text) == _norm(now_name):
                    row['scheme_change'] = {'status': 'same', 'old': now_name,
                                            'new': now_name}
                    continue
                config, why = self._named_scheme(text)
                if not why:
                    why = self._scheme_refusal(config, code, who)
                    if why:
                        names = ', '.join(c['name'] for c in self._scheme_choices(code))
                        why = (why + ' ' + (_("Change their Country of work in the same "
                                              "row, or pick one of: %s.") % names
                                            if names else _("Change their Country of "
                                                            "work in the same row.")))
                if why:
                    row['scheme_change'] = {'status': 'refused', 'old': now_name,
                                            'new': text, 'why': why}
                    continue
                advance, why = self._advance_from_text(config, row.get('advance_text'))
                if why:
                    row['scheme_change'] = {'status': 'refused', 'old': now_name,
                                            'new': config.name or '', 'why': why}
                    continue
                start = row.get('start') or {}
                row['scheme_change'] = {
                    'status': 'ok', 'old': now_name, 'new': config.name or '',
                    'config_id': config.id, 'advance_id': advance.id or 0,
                    'advance': advance.name or '',
                    'r6': self._board().r6_words(now_name, config.name, start.get('date'))
                    if start.get('date') else ''}
            elif moved_to:
                found = Map.usual_scheme(emp.company_id.id, moved_to,
                                         emp.department_id.id or 0)
                config = found['config']
                if config and config.cycle_type in MAIN_KINDS \
                        and config.id != now.get('config_id'):
                    advance = self._board().advance_default(config)
                    row['scheme_suggest'] = {
                        'config_id': config.id, 'new': config.name or '',
                        'old': now_name, 'advance_id': advance.id or 0,
                        'advance': advance.name or '',
                        'line': _("Their Country of work changes to %(country)s. "
                                  "Their pay scheme stays %(old)s unless you change "
                                  "it.") % {'country': countries.get(moved_to) or moved_to,
                                            'old': now_name or _("none")}}
        return rows

    @api.model
    def scheme_outlook(self):
        """What a pay scheme change from this sheet does: `{outcome: now |
        approval | none, line}` — the route every pay scheme change takes."""
        self._gate()
        board = self.env['pb.scheme.board']
        if not board._can_propose_person():
            return {'outcome': 'none', 'line': _(
                "Changing a person's pay scheme is for HR and payroll. Ask one "
                "of them to make the change.")}
        blocked = board._person_blocked(self.env.company)
        if blocked:
            return {'outcome': 'none', 'line': blocked}
        lane = board._person_lane(self.env.company)
        if lane in ('fast', 'none'):
            return {'outcome': 'now', 'line': _("Changed at once. No approval needed.")}
        return {'outcome': 'approval', 'line': _(
            "One request per pay scheme, for a payroll manager to approve")}

    @api.model
    def _scheme_plan(self, schemes):
        """The browser's pay scheme changes, read defensively and judged
        again: `[(employee, config, advance, day)]`. Raises UserError with the
        reason for the first one that cannot go."""
        Config = self.env['hr.formula.config'].sudo()
        Employee = self.env['hr.employee']
        today = self.env['pb.records.apply']._today_for()
        plan = []
        for item in (schemes or [])[:MAX_SCHEME_CHANGES]:
            if not isinstance(item, dict):
                continue
            try:
                emp_id = int(item.get('emp_id') or 0)
                config_id = int(item.get('config_id') or 0)
                advance_id = int(item.get('advance_id') or 0)
            except (TypeError, ValueError):
                continue
            if not emp_id or not config_id:
                continue
            employee = Employee.search([('id', '=', emp_id),
                                        ('company_id', 'in', self.env.companies.ids)],
                                       limit=1).sudo()
            config = Config.browse(config_id).exists()
            if not employee or not config:
                raise UserError(_("Nothing was changed: a person or a pay scheme in "
                                  "this sheet is not there any more. Review the sheet "
                                  "again."))
            why = self._scheme_refusal(config, '', employee.name or '')
            if why:
                raise UserError(_("Nothing was changed: %s") % why)
            advance = Config.browse(advance_id).exists() if advance_id else Config
            if advance and advance.cycle_type != 'mid_cycle':
                advance = Config
            day = fields.Date.to_date(item.get('date')) if item.get('date') else \
                today.replace(day=1) + relativedelta(months=1)
            if abs((day - today).days) > 366:
                raise UserError(_("Nothing was changed: a pay scheme change can start "
                                  "up to a year back or a year ahead."))
            plan.append((employee, config, advance, day))
        return plan

    @api.model
    def _apply_schemes(self, plan, name):
        """Send every pay scheme change of the sheet through the door, one
        request per (scheme, advance, date). `[{scheme, people, date, saved,
        pending, message}]`."""
        groups = {}
        for employee, config, advance, day in plan:
            key = (config.id, advance.id or 0, fields.Date.to_string(day))
            groups.setdefault(key, {'config': config, 'advance': advance, 'day': day,
                                    'people': self.env['hr.employee'].sudo()})
            groups[key]['people'] |= employee
        board = self.env['pb.scheme.board']
        out = []
        for key in sorted(groups):
            g = groups[key]
            answer = board.person_set(g['people'].ids, g['config'].id,
                                      g['advance'].id or False,
                                      fields.Date.to_string(g['day']),
                                      company_id=self.env.company.id, source='import',
                                      note=(name or '')[:200])
            if answer.get('ok') is False:
                raise UserError(_("Nothing was changed: %s") % (answer.get('message') or ''))
            out.append({
                'scheme': g['config'].name or '', 'people': len(g['people']),
                'names': ', '.join(g['people'][:6].mapped('name')),
                'advance': g['advance'].name or '',
                'date': fields.Date.to_string(g['day']),
                'saved': bool(answer.get('applied') or answer.get('saved')),
                'pending': bool(answer.get('pending')),
                'message': answer.get('message') or '',
            })
        return out

    @api.model
    def apply(self, name='', file_b64='', filename='', columns=None, changes=None, stats=None,
              start_date=None, hold_scope='pay', kind='lasting', month=None, draft_id=0,
              joiners=None, cutover=None, schemes=None):
        """`apply`, plus `schemes` (PSCHEME P2b B.2): the pay scheme changes of
        the people already here. One transaction: anything refused raises, so
        nothing of the update is kept."""
        args = dict(name=name, file_b64=file_b64, filename=filename, columns=columns,
                    changes=changes, stats=stats, start_date=start_date,
                    hold_scope=hold_scope, kind=kind, month=month, draft_id=draft_id,
                    joiners=joiners, cutover=cutover)
        if kind != 'lasting' or not schemes:
            return super().apply(**args)
        self._gate()
        if not (name or '').strip():
            return {'ok': False, 'msg': _(
                "Give this update a name first, so you can find it later in "
                "Past updates.")}
        outlook = self.scheme_outlook()
        if outlook['outcome'] == 'none':
            return {'ok': False, 'msg': outlook['line']}
        try:
            plan = self._scheme_plan(schemes)
        except UserError as error:
            return {'ok': False, 'msg': str(error.args[0] if error.args else error)}
        if not plan:
            return super().apply(**args)
        if not [c for c in (changes or []) if isinstance(c, dict)] and \
                not [j for j in (joiners or []) if isinstance(j, dict)]:
            answer = {'ok': True, 'apply_id': 0, 'batch_id': 0, 'written': 0,
                      'people': 0, 'refused': [], 'pending': False, 'only_schemes': True}
        else:
            answer = super().apply(**args)
            if not isinstance(answer, dict) or answer.get('ok') is False:
                return answer
        answer = dict(answer)
        answer['schemes'] = self._apply_schemes(plan, name)
        answer['nothing'] = False
        return answer
