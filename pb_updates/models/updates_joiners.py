# -*- coding: utf-8 -*-
"""UPDATES P3b — new employees from a sheet.

A row of a "Lasting changes" file that matches nobody can be added as a NEW
employee with a first contract — only when the person switches that on for
this file (default off, every file), and only through the EXISTING new-hire
path: `pb.people.onboard.wizard.create_employee`, the very call "Add employee"
makes, and therefore the company's new-hire approval (`pb.newhire.proposal`,
process `newhire`). Nothing here creates an employee or a contract row, and
nothing here sets the "this is the approved write" context key.

Rails (handover §2):
  * opt-in per file, never automatic; at most 200 new people per file;
  * never a duplicate: same code, work email, or name + team as anybody
    already here (archived people too), as another row of the file, or as a
    new-hire request still waiting — refused in a sentence, never merged;
  * teams, jobs, managers, countries and working hours are FOUND, never made;
  * a "Pay scheme" column is a CHECK against the team: the scheme map is read
    (`_department_schemes`, the pay run's own ladder for a department) and
    never written;
  * undo never deletes or archives a person.

What the rest of a row carries (pay items, bank details, other fields) is
kept on a `pb.updates.joiner` row until the person exists, then sent through
the normal lanes of the same named update as the person who sent the file:
at once under "No approval needed", or from the moment the hire is approved
(`PbNewHireProposalUpdates._approval_apply`). If that follow-up cannot be
made, the row says "Hired. N values from the sheet are still to apply" and
offers Apply now, which reads the kept values again against today's record.

Loaded after `updates_desk` (models/__init__.py); constants come FROM that
file, never the other way round (ledger G21).
"""
import io
import base64
import json
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

from odoo.addons.pb_records.models.pb_records_io import (
    _norm, XLSX_MIME, ID_COMMENT, META_SHEET, IDENTITY_COLS, SHEET)
from odoo.addons.pb_hr_payroll_formula.models.payroll_import_batch import (
    m2o_resolution_key)
from odoo.addons.pb_people_advanced.models.newhire_approval import NEWHIRE_WRITE
from odoo.addons.pb_updates.models.updates_desk import SCHEME_TARGET

try:  # WHITELABEL — the tenant's own name for the product
    from odoo.addons.biz_debrand.models.brand import product_label
except Exception:  # pragma: no cover — biz_debrand absent on this build
    def product_label(env, default='Payobook'):
        return default

_logger = logging.getLogger(__name__)

EMP = 'hr.employee'
CON = 'hr.contract'
#: Headings read as that check column.
SCHEME_HEADINGS = ('pay scheme', 'payroll scheme', 'pay scheme name',
                   'chế độ lương', 'skema gaji')
#: At most this many new employees from one file.
MAX_NEW = 200
#: A contract start date may be this many days back or ahead.
START_REACH = 366
#: The fields the new-hire call itself takes, by card id → its own key.
CONSUMED = {
    'f:hr.employee:name': 'name',
    'f:hr.employee:department_id': 'department_id',
    'f:hr.employee:job_id': 'job_id',
    'f:hr.employee:job_title': 'job_title',
    'f:hr.employee:parent_id': 'parent_id',
    'f:hr.employee:work_email': 'work_email',
    'f:hr.employee:work_phone': 'work_phone',
    'f:hr.employee:country_id': 'country_id',
    'f:hr.contract:date_start': 'date_start',
    'f:hr.contract:date_end': 'date_end',
    'f:hr.contract:wage': 'wage',
    'f:hr.contract:resource_calendar_id': 'resource_calendar_id',
    'f:hr.employee:resource_calendar_id': 'resource_calendar_id',
}
TEAM = 'f:hr.employee:department_id'
START = 'f:hr.contract:date_start'
WAGE = 'f:hr.contract:wage'
NEWHIRE_GROUPS = ('hr.group_hr_user', 'hr.group_hr_manager')
#: The columns of the blank sheet for new employees, after the identity three.
BLANK_COLUMNS = (TEAM, 'f:hr.employee:job_id', 'f:hr.employee:job_title',
                 'f:hr.employee:parent_id', 'f:hr.employee:work_phone',
                 'f:hr.employee:country_id', START, 'f:hr.contract:date_end',
                 WAGE, 'f:hr.contract:resource_calendar_id')

JOINER_STATES = [
    ('waiting', 'Waiting for approval'),
    ('created', 'Added'),
    ('turned_down', 'Turned down'),
    ('needs_attention', 'Hired, values still to apply'),
]


class PbUpdatesJoiner(models.Model):
    """One row of a file added as a new employee (UPDATES P3b).

    Written only by Updates itself (under sudo, after its own gates): people
    can read their companies' rows, nobody edits them by hand."""
    _name = 'pb.updates.joiner'
    _description = 'New employee from an update'
    _order = 'id'

    batch_id = fields.Many2one('pb.updates.batch', string='Named update',
                               required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True, index=True)
    user_id = fields.Many2one('res.users', string='Sent by', required=True)
    row = fields.Integer(string='Row in the file')
    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Employee code')
    department_id = fields.Many2one('hr.department', string='Team',
                                    ondelete='set null')
    start_date = fields.Date(string='Contract starts')
    wage = fields.Float(string='Monthly pay')
    proposal_id = fields.Many2one('pb.newhire.proposal', string='New-hire request',
                                  ondelete='set null', index=True)
    reference = fields.Char(string='Reference')
    state = fields.Selection(JOINER_STATES, string='State', default='waiting',
                             required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  ondelete='set null')
    contract_id = fields.Many2one('hr.contract', string='Contract',
                                  ondelete='set null')
    #: The row's other values `[{field_id, value, start}]`, sent once the
    #: person exists. Kept as typed; judged again when sent.
    cells_json = fields.Text(string='Values still to send')
    values_count = fields.Integer(string='Values in the row')
    cells_done = fields.Boolean(string='Values sent')
    note = fields.Text(string='Note')

    def cells(self):
        self.ensure_one()
        try:
            data = json.loads(self.cells_json or '[]')
        except (TypeError, ValueError):
            return []
        return [c for c in data if isinstance(c, dict)] if isinstance(data, list) else []


class PbNewHireProposalUpdates(models.Model):
    """The hook: a new-hire request that came from an Updates file finishes
    the row once the person exists. The onboarding module is not changed; this
    only continues after its own apply has returned."""
    _inherit = 'pb.newhire.proposal'

    def _approval_apply(self, request):
        done = super()._approval_apply(request)
        if self.applied and self.kind == 'employee':
            Joiner = self.env['pb.updates.joiner'].sudo()
            for joiner in Joiner.search([('proposal_id', '=', self.id),
                                         ('state', '=', 'waiting')]):
                self.env['pb.updates.desk'].sudo()._joiner_hired(joiner, self)
        return done

    def _approval_reject(self, request, reason):
        done = super()._approval_reject(request, reason)
        self._joiner_closed(_("Turned down"), reason)
        return done

    def _approval_return(self, request, reason):
        done = super()._approval_return(request, reason)
        self._joiner_closed(_("Sent back"), reason)
        return done

    def _joiner_closed(self, word, reason):
        Joiner = self.env['pb.updates.joiner'].sudo()
        rows = Joiner.search([('proposal_id', 'in', self.ids),
                              ('state', '=', 'waiting')])
        if rows:
            note = word if not (reason or '').strip() else '%s: %s' % (word, reason.strip())
            rows.write({'state': 'turned_down', 'note': note})


class PbUpdatesJoiners(models.AbstractModel):
    _inherit = 'pb.updates.desk'

    # =================================================================
    # Gates
    # =================================================================
    @api.model
    def _may_hire(self):
        user = self.env.user
        return user._is_superuser() or any(user.has_group(g) for g in NEWHIRE_GROUPS)

    @api.model
    def _hire_route(self):
        """`'none'`, `'fast'` or `'route'` — the company's new-hire route."""
        return self.env['pb.newhire.proposal'].route_mode(self.env.company)

    @api.model
    def _joiner_refusal(self, count):
        """A sentence when new employees cannot be added from this file at
        all, else ''."""
        if count > MAX_NEW:
            return _("This file has %(n)s rows to add as new employees. At most "
                     "%(max)s can be added from one file: split it into smaller "
                     "files.") % {'n': count, 'max': MAX_NEW}
        if not self._may_hire():
            return _("Adding new employees is for HR. Ask somebody in HR to "
                     "send this file, or to give you the HR permission.")
        if self._hire_route() == 'none':
            return _("New employees cannot be added yet: nobody has set up who "
                     "approves new people in %s. Ask whoever looks after "
                     "approvals.") % self.env.company.name
        return ''

    # =================================================================
    # Pay schemes of a team — read only
    # =================================================================
    @api.model
    def _department_schemes(self, dept_ids):
        """`{department_id: {'ids': {config_id}, 'names': {config_id: name}}}`.

        The pay run's own ladder (`pb.scheme.map.resolve_many`) asked about a
        TEAM instead of a person: the team map, deepest team first, then the
        team's division, then the company's only scheme — for "any kind of
        run" and every kind of run the map has lines for. A work segment
        names a person and a rule reads a person's record, so neither can be
        asked before the person exists (UPDATES_P3B_REPORT, deviation). Reads
        only; the map is never written."""
        ids = sorted({int(d) for d in dept_ids or [] if d})
        out = {d: {'ids': set(), 'names': {}} for d in ids}
        if not ids:
            return out
        Map = self.env['pb.scheme.map']
        depts = self.env['hr.department'].sudo().browse(ids).exists()
        company_ids = sorted({d.company_id.id for d in depts if d.company_id}
                             | set(self.env.companies.ids))
        chains, _meta = Map._chains(company_ids)
        rows = Map._map_rows(company_ids)
        by_department = Map._by_department(rows)
        by_division = Map._by_division(rows)
        division_of = Map._division_of_department()
        kinds = self.env['hr.formula.scheme.assignment'].sudo()._read_group(
            [('active', '=', True)], ['cycle_type'])
        cycles = ['any'] + sorted({k for (k,) in kinds if k and k != 'any'})
        only_cache = {}
        for dept in depts:
            chain = chains.get(dept.id) or [dept.id]
            for cycle in cycles:
                found = None
                for candidate in reversed(chain):
                    found = Map._pick(by_department.get(candidate), cycle)
                    if found:
                        break
                if not found:
                    division_id = next((division_of[c] for c in reversed(chain)
                                        if c in division_of), 0)
                    if division_id:
                        found = Map._pick(by_division.get(division_id), cycle)
                config = found.config_id if found else None
                if not config:
                    key = (dept.company_id.id, cycle)
                    if key not in only_cache:
                        only_cache[key] = Map._only_scheme(dept.company_id.id, cycle)
                    config = only_cache[key]
                if config:
                    out[dept.id]['ids'].add(config.id)
                    out[dept.id]['names'][config.id] = config.name or ''
        return out

    @api.model
    def _named_scheme(self, text):
        """The active pay scheme called `text` in the companies in use:
        `(config or None, why)`."""
        Config = self.env['hr.formula.config'].sudo()
        domain = [('state', '=', 'active'), '|', ('company_id', '=', False),
                  ('company_id', 'in', self.env.companies.ids)]
        hits = Config.search(domain + [('name', '=ilike', text)], limit=3) \
            if not ('%' in text or '_' in text) else \
            Config.search(domain).filtered(lambda c: (c.name or '').lower() == text.lower())
        if len(hits) == 1:
            return hits, ''
        if len(hits) > 1:
            return None, _("%(n)s pay schemes are called '%(name)s'. Leave the "
                           "pay scheme column empty, or use a name that is "
                           "unique.") % {'n': len(hits), 'name': text}
        return None, _("No pay scheme is called '%s'. Check the spelling, or "
                       "leave the pay scheme column empty.") % text

    # =================================================================
    # Judging rows
    # =================================================================
    @api.model
    def _find_linked(self, desk, fid, text):
        """`(id, label, why)` for a team, job, manager, country or working
        hours typed in a new employee's row. Found the P2a way (company
        scope, full path, namesakes refused) — and NEVER created."""
        model, fname = fid[2:].split(':', 1)
        field = self.env[model]._fields[fname]
        comodel = self.env[field.comodel_name]
        key = m2o_resolution_key(comodel)
        if not key:
            return None, '', _("%s cannot be typed in here.") % field.string
        rec_id, label, why = desk._m2o_ladder(field, comodel, key, text)
        if why:
            return None, '', why
        if isinstance(rec_id, dict) or not rec_id:
            what = {
                'hr.department': _("team"), 'hr.job': _("job"),
                'res.country': _("country"),
                'resource.calendar': _("working hours"),
            }.get(comodel._name) or (field.string or '').lower()
            return None, '', _("No %(what)s called '%(value)s' exists. New "
                               "employees are only added to what is already "
                               "set up, never created from a file.") % {
                                   'what': what, 'value': text}
        return rec_id, label, ''

    @api.model
    def _new_amount(self, value):
        try:
            amount = float(str(value).replace(',', '').strip())
        except (TypeError, ValueError):
            return None
        return amount

    @api.model
    def _joiner_index(self, rows):
        """Everybody a new row could be a copy of, archived people included:
        `{'code': {code: name}, 'email': {..}, 'name_team': {(name, team):
        name}, 'waiting': {(name, team): reference}}`, in the companies in
        use. Only the codes, emails and names the rows carry are looked up
        (one search, not the whole roster); every hit is compared exactly
        again here, so a wildcard character in a cell can only over-match,
        never miss."""
        Desk = self.env['pb.records.desk']
        Emp = self.env[EMP].sudo().with_context(active_test=False)
        code_fields = [f for f in ('barcode', 'employee_id', 'pb_source_ref',
                                   'identification_id') if f in Emp._fields]
        codes, emails, names = set(), set(), set()
        for r in rows:
            values = r.get('values') if isinstance(r.get('values'), dict) else {}
            code = str(r.get('code') or '').strip()
            if code:
                codes.add(code)
            email = str(values.get('f:hr.employee:work_email') or r.get('email') or '').strip()
            if email:
                emails.add(email)
            name = str(values.get('f:hr.employee:name') or r.get('name') or '').strip()
            if name:
                names.add(name)
        terms = [Domain(f, '=ilike', c) for c in sorted(codes) for f in code_fields]
        terms += [Domain('work_email', '=ilike', e) for e in sorted(emails)]
        terms += [Domain('name', '=ilike', n) for n in sorted(names)]
        index = {'code': {}, 'email': {}, 'name_team': {}, 'name': {}}
        people = Emp.search_read(
            Domain.AND([Domain('company_id', 'in', self.env.companies.ids),
                        Domain.OR(terms)]),
            ['name', 'work_email', 'department_id', 'active'] + code_fields,
            load=False) if terms else []
        for p in people:
            label = p['name'] or ''
            if not p.get('active'):
                label = _("%s (archived)") % label
            for f in code_fields:
                code = Desk._normalise_code(p.get(f))
                if code:
                    index['code'].setdefault(code, label)
            email = (p.get('work_email') or '').strip().lower()
            if email:
                index['email'].setdefault(email, label)
            if p.get('department_id'):
                index['name_team'].setdefault((_norm(p['name']), p['department_id']), label)
            index['name'].setdefault(_norm(p['name']), label)
        # A badge code is unique across the whole database, not one company.
        if codes and 'barcode' in Emp._fields:
            for p in Emp.search_read(Domain.OR([Domain('barcode', '=ilike', c)
                                                for c in sorted(codes)]),
                                     ['name', 'barcode', 'active'], load=False):
                code = Desk._normalise_code(p.get('barcode'))
                if code:
                    index['code'].setdefault(code, p['name'] or '')
        waiting = {}
        if 'pb.newhire.proposal' in self.env:
            for prop in self.env['pb.newhire.proposal'].sudo().search([
                    ('kind', '=', 'employee'), ('state', '=', 'pending'),
                    ('company_id', 'in', self.env.companies.ids)]):
                values = (prop.payload() or {}).get('values') or {}
                try:
                    team = int(values.get('department_id') or 0)
                except (TypeError, ValueError):
                    team = 0
                key = (_norm(values.get('name')), team)
                if key[0]:
                    waiting.setdefault(key, prop.name or '')
        index['waiting'] = waiting
        return index

    @api.model
    def _quick_block(self, row, index, desk=None, memo=None):
        """The sentence that refuses a row before any of its cells is judged,
        else ''. Two cases only: the row's code or work email is somebody
        already here (archived people too), or the row does not have the
        minimum a new employee needs. On a full sheet these are the namesake
        rows by the thousand; judging their cells would only cost time, and
        they never count towards the 200. A shared NAME alone is not a copy
        (namesakes are common): name + team is judged with the rest."""
        values = row.get('values') if isinstance(row.get('values'), dict) else {}
        code = self.env['pb.records.desk']._normalise_code(row.get('code'))
        email = str(values.get('f:hr.employee:work_email') or row.get('email') or '').strip().lower()
        hit = (code and index['code'].get(code)) or (email and index['email'].get(email))
        if hit:
            return _("This looks like %s, who is already here. Nobody is added "
                     "twice: find the person instead, or skip the row.") % hit
        name = str(values.get('f:hr.employee:name') or row.get('name') or '').strip()
        if not name:
            return _("A new employee needs a name.")
        filled = lambda fid: str(values.get(fid) if values.get(fid) is not None else '').strip()
        if not filled(TEAM) or not filled(START):
            return _("To add %s as a new employee, the row needs a team and a "
                     "contract start date.") % name
        if desk is not None:
            # Name + team: the team found the P2a way, once per team name.
            memo = memo if memo is not None else {}
            key = (TEAM, filled(TEAM).lower())
            if key not in memo:
                memo[key] = self._find_linked(desk, TEAM, filled(TEAM))
            team_id = memo[key][0]
            hit = team_id and index['name_team'].get((_norm(name), team_id))
            if hit:
                return _("This looks like %s, who is already here. Nobody is "
                         "added twice: find the person instead, or skip the "
                         "row.") % hit
        return ''

    @api.model
    def _judge_joiners(self, desk, rows, default_start=None, index=None):
        """Judge every row the person wants to add. Writes nothing.

        Each row is `{row, code, name, email, values: {card id: value},
        scheme, start}` (what the review handed the screen, with on-screen
        fixes). The answer, per row: `cells` in the review grid's shape,
        `block` (a row-level sentence: the row cannot be added and stays
        under "matches nobody"), `addable`, and — server side only — `vals`
        (the new-hire call) and `rest` (the row's other values)."""
        cards = desk._cards(0)
        probe = desk._probe(0)
        today = self.env['pb.records.apply']._today_for()
        index = index if index is not None else self._joiner_index(rows)
        memo = {}
        clear_words = desk._io_clear_words()
        out = []
        new_emp = self.env[EMP].new({'company_id': self.env.company.id})
        new_con = self.env[CON].new({}) if CON in self.env else None
        teams = {}
        # First pass: each cell on its own.
        for raw in rows:
            values = raw.get('values') if isinstance(raw.get('values'), dict) else {}
            try:
                rowno = int(raw.get('row') or 0)
            except (TypeError, ValueError):
                rowno = 0
            name = str(values.get('f:hr.employee:name') or raw.get('name') or '').strip()
            email = str(values.get('f:hr.employee:work_email') or raw.get('email') or '').strip()
            code = str(raw.get('code') or '').strip()
            j = {'row': rowno, 'key': 'n%s' % rowno, 'name': name, 'code': code,
                 'email': email, 'cells': {}, 'block': '', 'addable': False,
                 'vals': {'name': name}, 'rest': [], 'team': '', 'team_id': 0,
                 'scheme': '', 'scheme_text': str(raw.get('scheme') or '').strip(),
                 'scheme_note': '', 'no_contract': False, 'start': raw.get('start') or {}}
            if email:
                j['vals']['work_email'] = email
            quick = self._quick_block(raw, index, desk, memo)
            if quick:
                j.update(block=quick, quick=True)
                out.append(j)
                continue
            for fid, value in values.items():
                fid = str(fid)
                text = '' if value is None else (value if isinstance(value, (int, float))
                                                  and not isinstance(value, bool)
                                                  else str(value).strip())
                if text == '' or (isinstance(text, str) and text.lower() in clear_words):
                    # Nothing to empty on somebody who does not exist yet.
                    continue
                card = cards.get(fid)
                cell = {'status': 'ok', 'old': '', 'new': str(text), 'why': '',
                        'value': value, 'consumed': fid in CONSUMED,
                        'label': (card or {}).get('label') or ''}
                j['cells'][fid] = cell
                if card is None or (not card.get('editable') and not card.get('locked')):
                    cell.update(status='refused', why=_("This column cannot be "
                                                        "filled in for a new employee."))
                    continue
                if fid in CONSUMED:
                    self._judge_consumed(desk, j, fid, text, cell, today, memo)
                else:
                    self._judge_rest(desk, probe, card, j, fid, value, cell, new_emp, new_con)
            if j['team_id']:
                teams[j['team_id']] = True
            out.append(j)
        schemes = self._department_schemes(list(teams))
        items = self._scheme_items(desk, {c for s in schemes.values() for c in s['ids']}) \
            if teams else {}
        # Second pass: what needs the whole file — schemes, copies, twins.
        seen = {}
        for j in out:
            for key in self._joiner_keys(j):
                seen.setdefault(key, []).append(j['row'])
        for j in out:
            self._judge_row(j, schemes, items, index, seen, today, default_start)
        return out

    @api.model
    def _joiner_keys(self, j):
        keys = []
        code = self.env['pb.records.desk']._normalise_code(j['code'])
        if code:
            keys.append(('code', code))
        if j['email']:
            keys.append(('email', j['email'].lower()))
        if j['name'] and j['team_id']:
            keys.append(('name_team', (_norm(j['name']), j['team_id'])))
        return keys

    @api.model
    def _judge_consumed(self, desk, j, fid, text, cell, today, memo):
        key = CONSUMED[fid]
        if key in ('department_id', 'job_id', 'parent_id', 'country_id',
                   'resource_calendar_id'):
            memo_key = (fid, str(text).strip().lower())
            if memo_key not in memo:
                memo[memo_key] = self._find_linked(desk, fid, str(text))
            rec_id, label, why = memo[memo_key]
            if why:
                cell.update(status='refused', why=why)
                return
            cell['new'] = label or str(text)
            j['vals'][key] = rec_id
            if key == 'department_id':
                j['team_id'], j['team'] = rec_id, label or str(text)
            return
        if key in ('date_start', 'date_end'):
            day, why = self._parse_start(text)
            if why or not day:
                cell.update(status='refused', why=why or _("This is not a date."))
                return
            if key == 'date_start' and abs((day - today).days) > START_REACH:
                cell.update(status='refused', why=_(
                    "A contract start date can be up to a year back or a year "
                    "ahead. %s is further away than that.") % self.start_label(
                        fields.Date.to_string(day)))
                return
            cell['new'] = self.start_label(fields.Date.to_string(day))
            j['vals'][key] = fields.Date.to_string(day)
            return
        if key == 'wage':
            amount = self._new_amount(text)
            if amount is None or amount <= 0:
                cell.update(status='refused', why=_(
                    "'%s' is not a positive amount. Type the monthly pay as a "
                    "number, like 15000000.") % text)
                return
            cell['new'] = desk._num(amount) if hasattr(desk, '_num') else str(amount)
            j['vals']['wage'] = amount
            return
        if key == 'work_email':
            if '@' not in str(text):
                cell.update(status='refused', why=_("'%s' is not an email address.") % text)
                return
            j['email'] = str(text).strip()
        if key == 'name':
            j['name'] = str(text).strip()
        j['vals'][key] = str(text).strip()

    @api.model
    def _judge_rest(self, desk, probe, card, j, fid, value, cell, new_emp, new_con):
        """A value for after the person exists: judged now as far as it can
        be without a record (numbers, choices, dates, bank details); judged
        again by the Records Desk when it is sent."""
        try:
            coerced, label, why = desk._coerce(probe, card, value, new_emp,
                                               new_con if fid.startswith('f:hr.contract:') else None)
        except Exception:   # noqa: BLE001 — judged again when it is sent
            _logger.debug('pb_updates: new-employee value %s not pre-checked', fid,
                          exc_info=True)
            coerced, label, why = value, str(value), ''
        if why and fid.startswith('f:hr.contract:'):
            why = _("%s is set on the contract once it exists.") % (card.get('label') or '') \
                if 'no contract' in why.lower() or 'has no contract' in why.lower() else why
        if why:
            cell.update(status='refused', why=why)
            return
        cell['new'] = label or str(value)
        j['rest'].append({'field_id': fid, 'value': value})

    @api.model
    def _judge_row(self, j, schemes, items, index, seen, today, default_start):
        if j.get('quick'):
            # Refused before its cells were judged: nothing to add to that.
            return
        cells = j['cells']
        team_cell = cells.get(TEAM)
        start_cell = cells.get(START)
        # — the pay scheme check and its greying of pay items
        info = schemes.get(j['team_id']) or {'ids': set(), 'names': {}}
        if j['team_id']:
            names = sorted(set(info['names'].values()))
            j['scheme'] = ', '.join(names)
            if not info['ids']:
                j['scheme_note'] = _("No pay scheme covers %s yet. Pay items are "
                                     "still saved on the contract.") % j['team']
            if j['scheme_text']:
                config, why = self._named_scheme(j['scheme_text'])
                if why:
                    team_cell.update(status='refused', why=why)
                elif info['ids'] and config.id not in info['ids']:
                    team_cell.update(status='refused', why=_(
                        "%(team)s is paid under %(scheme)s, not %(named)s. Change "
                        "the team or the pay scheme column.") % {
                            'team': j['team'], 'scheme': j['scheme'],
                            'named': config.name})
            codes = set()
            for cid in info['ids']:
                codes |= (items.get(cid) or {}).get('codes', set())
            if info['ids']:
                keep = []
                for change in j['rest']:
                    fid = change['field_id']
                    if fid.startswith('c:') and fid[2:] not in codes:
                        cells[fid].update(status='off_scheme', why=_(
                            "%(item)s is not in %(scheme)s, so it is left out "
                            "for %(name)s.") % {'item': cells[fid].get('label') or fid[2:],
                                                 'scheme': j['scheme'],
                                                 'name': j['name'] or _("this person")})
                        continue
                    keep.append(change)
                j['rest'] = keep
        # — the minimum
        if not j['name']:
            j['block'] = _("A new employee needs a name.")
        elif not team_cell or not start_cell:
            j['block'] = _("To add %s as a new employee, the row needs a team and "
                           "a contract start date.") % j['name']
        # — copies of somebody already here
        if not j['block']:
            code = self.env['pb.records.desk']._normalise_code(j['code'])
            hit = (code and index['code'].get(code)) or \
                (j['email'] and index['email'].get(j['email'].lower())) or \
                (j['team_id'] and index['name_team'].get((_norm(j['name']), j['team_id'])))
            if hit:
                j['block'] = _("This looks like %s, who is already here. Nobody "
                               "is added twice: find the person instead, or skip "
                               "the row.") % hit
        if not j['block']:
            for key in self._joiner_keys(j):
                rows = seen.get(key) or []
                if len(rows) > 1:
                    others = ', '.join(str(r) for r in rows if r != j['row'])
                    j['block'] = _("%(name)s is in this file twice (also row "
                                   "%(rows)s). Keep one row and drop it again.") % {
                                       'name': j['name'], 'rows': others}
                    break
        if not j['block'] and j['team_id']:
            ref = index['waiting'].get((_norm(j['name']), j['team_id']))
            if ref:
                j['block'] = _("%(name)s is already waiting for approval "
                               "(%(ref)s).") % {'name': j['name'], 'ref': ref}
        # — the contract
        if 'wage' not in j['vals']:
            j['no_contract'] = WAGE not in cells
        else:
            j['vals']['with_contract'] = True
            # As "Add employee" does by default: the contract is in force.
            j['vals']['activate'] = True
            if j['vals'].get('date_end') and j['vals'].get('date_start') \
                    and j['vals']['date_end'] <= j['vals']['date_start']:
                cells['f:hr.contract:date_end'].update(status='refused', why=_(
                    "The contract end date must be after its start date."))
        if j['no_contract']:
            for fid, cell in cells.items():
                if fid.startswith('f:hr.contract:') and fid not in CONSUMED \
                        and cell['status'] == 'ok':
                    cell.update(status='refused', why=_(
                        "No contract yet: there is no wage in the file, so this "
                        "cannot be set."))
            j['rest'] = [c for c in j['rest'] if not c['field_id'].startswith('f:hr.contract:')]
        consumed_bad = any(c['status'] == 'refused' for f, c in cells.items()
                           if f in CONSUMED)
        j['addable'] = not j['block'] and not consumed_bad
        start = j.get('start') or {}
        own = start.get('date') if isinstance(start, dict) and not start.get('error') else ''
        for change in j['rest']:
            if own:
                change['start'] = own
            elif default_start:
                change['start'] = default_start

    @api.model
    def _public_joiner(self, j):
        """A judged row for the screen: no server-only keys."""
        return {k: v for k, v in j.items() if k not in ('vals', 'rest', 'team_id', 'quick')}

    @api.model
    def judge_joiners(self, rows=None):
        """The add-as-new choice, switched on: every row that matches nobody,
        judged as a new employee. Writes nothing. Refused before anything is
        judged when there are more than 200 (or the person cannot add
        people at all)."""
        desk = self._gate()
        rows = [r for r in (rows or []) if isinstance(r, dict)]
        index = self._joiner_index(rows)
        memo = {}
        fresh = sum(1 for r in rows if not self._quick_block(r, index, desk, memo))
        refusal = self._joiner_refusal(fresh)
        if refusal:
            return {'ok': False, 'msg': refusal}
        judged = self._judge_joiners(desk, rows, index=index)
        return {'ok': True, 'rows': [self._public_joiner(j) for j in judged],
                'outlook': self.joiner_outlook(sum(1 for j in judged if j['addable']))}

    # =================================================================
    # The Apply step's fourth card
    # =================================================================
    @api.model
    def joiner_outlook(self, count=0):
        """`{count, outcome, line, names}` — what adding `count` new people
        does: `now` (added at once), `approval` (one new-hire request each,
        to <who>) or `none` (cannot be added)."""
        self._gate()
        try:
            count = max(0, int(count or 0))
        except (TypeError, ValueError):
            count = 0
        out = {'count': count, 'outcome': 'none', 'names': [], 'line': ''}
        refusal = self._joiner_refusal(count)
        if refusal:
            out['line'] = refusal
            return out
        mode = self._hire_route()
        if mode == 'fast':
            out.update(outcome='now', line=_("Added now, each with a first "
                                             "contract. No approval needed."))
            return out
        probe = self.env['pb.newhire.proposal'].sudo().new({
            'kind': 'employee', 'title_text': '/', 'payload_json': '{}',
            'snapshot_json': '{}', 'facts_json': '{}', 'scope_json': '[""]',
            'subject_json': '[]', 'company_id': self.env.company.id,
            'user_id': self.env.uid})
        kind, names, sentence = self._first_step_people(probe, 'newhire')
        if kind == 'fast':
            out.update(outcome='now', line=_("Added now, each with a first "
                                             "contract. No approval needed."))
        elif names:
            out.update(outcome='approval', names=names, line=_(
                "One new-hire request each, to %s") % self._names_line(names))
        else:
            out.update(outcome='approval', line=sentence or _(
                "One new-hire request each, for approval"))
        return out

    # =================================================================
    # Applying
    # =================================================================
    @api.model
    def _apply_with_joiners(self, name, file_b64, filename, columns, changes,
                            stats, start_date, hold_scope, draft_id, joiners):
        """`apply` when the person chose to add rows as new employees.

        One transaction. Every row is judged again here, whatever the screen
        said; only rows that pass are sent to the new-hire path, one request
        per person. A person created at once (no approval needed) gets the
        rest of their row through the normal lanes of this same update; a
        person waiting for approval keeps it on their row until approved.
        Anything refused after somebody was created raises, so nothing of
        this update is kept — all or none."""
        desk = self._gate()
        name = (name or '').strip()
        if not name:
            return {'ok': False, 'msg': _(
                "Give this update a name first, so you can find it later in "
                "Past updates.")}
        if not self._can_write(desk):
            return {'ok': False, 'msg': _(
                "You can look through these changes, but you do not have "
                "permission to change employee records. Ask an administrator "
                "for the HR or Payroll Officer role.")}
        refusal = self._joiner_refusal(len(joiners))
        if refusal:
            return {'ok': False, 'msg': refusal}
        default_day, why = desk._start_date_of(start_date)
        if why:
            return {'ok': False, 'msg': why}
        cols = self._clean_columns(columns)
        stats = stats if isinstance(stats, dict) else {}

        def count(key):
            try:
                return max(0, int(stats.get(key) or 0))
            except (TypeError, ValueError):
                return 0

        changes = self._clear_words(desk, changes)
        judged = self._judge_joiners(
            desk, joiners, fields.Date.to_string(default_day) if default_day else None)
        addable = [j for j in judged if j['addable']]
        if not addable and not changes:
            first = next((j['block'] or next((c['why'] for c in j['cells'].values()
                                               if c['status'] == 'refused'), '')
                          for j in judged), '')
            return {'ok': False, 'msg': _("Nobody can be added from this file "
                                          "yet: %s") % first if first else _(
                "There is nothing to apply: no value in this file would change "
                "anything.")}
        # The existing people's values are checked BEFORE anybody is added.
        changes, skipped = self._drop_off_scheme(desk, changes)
        if changes:
            _buckets, refusal = self._split_by_start(desk, changes, start_date, hold_scope)
            if refusal:
                return {'ok': False, 'msg': refusal}
        # The new-hire call, exactly as "Add employee" makes it. The
        # "approved write" switch is never ours to set: whatever the caller's
        # context says, it is off here (the web door drops it too, ledger
        # biz_approval_workflow `scrub_params`), so each person is a request.
        Onboard = self.env['pb.people.onboard.wizard'].with_context(
            **{NEWHIRE_WRITE: False})
        results, extra = [], []
        for j in addable:
            answer = Onboard.create_employee(dict(j['vals']))
            emp_id = int(answer.get('employee_id') or 0)
            res = {'j': j, 'answer': answer, 'emp_id': emp_id,
                   'note': answer.get('error') or ''}
            if emp_id:
                res['state'] = 'created'
                if not answer.get('proposal_id') and answer.get('reference'):
                    # Under "No approval needed" the request was carried out
                    # inside the call: find it by the reference it answered.
                    prop = self.env['pb.newhire.proposal'].sudo().search(
                        [('name', '=', answer['reference'])], limit=1)
                    answer = dict(answer, proposal_id=prop.id)
                    res['answer'] = answer
                res['note'] = self._joiner_code(emp_id, j['code'], res['note'])
                extra += [dict(c, emp_id=emp_id) for c in j['rest']]
            elif answer.get('proposal_id') and not answer.get('error'):
                res['state'] = 'waiting'
            else:
                raise UserError(_("Nothing was changed: %(name)s could not be "
                                  "added. %(why)s") % {
                                      'name': j['name'],
                                      'why': answer.get('error') or answer.get(
                                          'block_note') or answer.get('message') or ''})
            results.append(res)
        extra, skipped_new = self._drop_off_scheme(desk, extra)
        skipped += skipped_new
        all_changes = changes + extra
        answer, answers = {}, []
        if all_changes:
            buckets, refusal = self._split_by_start(desk, all_changes, start_date,
                                                    hold_scope)
            if refusal:
                raise UserError(refusal)
            if list(buckets) == [None]:
                answer = desk.apply_changes(0, buckets[None], note=name, source='import')
                answers = [(None, answer)]
            else:
                answer, answers = self._apply_by_start(desk, buckets, name, hold_scope)
            if answer.get('ok') is False:
                raise UserError(answer.get('msg') or _(
                    "Nothing was changed: the update could not be sent."))
        else:
            answer = {'ok': True, 'apply_id': 0, 'apply_ids': [], 'written': 0,
                      'people': 0, 'refused': [], 'pending': False, 'items': []}
        self._remember_layout(desk, file_b64, filename, cols)
        off_scheme = count('off_scheme') + len(skipped)
        not_added = len(judged) - len(addable)
        batch = self._new_batch({
            'name': name[:200],
            'filename': (filename or '').strip() or False,
            'rows_total': count('rows'),
            'rows_unmatched': count('unmatched') + not_added,
            'values_refused': count('left_out') + len(answer.get('refused') or []),
            'values_off_scheme': off_scheme,
        }, file_b64, filename, draft_id)
        apply_ids = []
        for _day, a in answers:
            apply_ids += a.get('apply_ids') or ([a['apply_id']] if a.get('apply_id') else [])
        self.env['pb.records.apply'].sudo().browse(apply_ids).write(
            {'updates_batch_id': batch.id})
        Joiner = self.env['pb.updates.joiner'].sudo()
        rows_out = []
        for res in results:
            j, a = res['j'], res['answer']
            created = res['state'] == 'created'
            rec = Joiner.create({
                'batch_id': batch.id, 'company_id': self.env.company.id,
                'user_id': self.env.uid, 'row': j['row'], 'name': j['name'],
                'code': j['code'] or False,
                'department_id': j['team_id'] or False,
                'start_date': j['vals'].get('date_start') or False,
                'wage': j['vals'].get('wage') or 0.0,
                'proposal_id': a.get('proposal_id') or False,
                'reference': a.get('reference') or False,
                'state': res['state'],
                'employee_id': res['emp_id'] or False,
                'contract_id': a.get('contract_id') or False,
                'cells_json': json.dumps(j['rest'], default=str),
                'values_count': len(j['rest']),
                'cells_done': created,
                'note': res['note'] or False,
            })
            rows_out.append(self._joiner_payload(rec, a.get('with_whom') or ''))
        answer = dict(answer)
        answer.update(
            ok=True, batch_id=batch.id, batch_name=batch.name,
            apply_id=answer.get('apply_id') or 0,
            skipped_off_scheme=len(skipped), off_scheme=off_scheme,
            joiners=rows_out,
            joiners_added=sum(1 for r in rows_out if r['state'] == 'created'),
            joiners_waiting=sum(1 for r in rows_out if r['state'] == 'waiting'),
            joiners_not_added=not_added)
        return answer

    @api.model
    def _joiner_code(self, emp_id, code, note=''):
        """The employee code, written after the person exists (the new-hire
        call does not take one). A code somebody already has is refused by
        the record itself: the person stays, the row says so."""
        code = (code or '').strip()
        if not code:
            return note
        emp = self.env[EMP].browse(emp_id)
        try:
            with self.env.cr.savepoint():
                emp.write({'barcode': code})
        except Exception as error:   # noqa: BLE001 — the person stays
            why = str(getattr(error, 'name', None) or getattr(error, 'args', [''])[0] or '')
            bit = _("The employee code %(code)s could not be saved (%(why)s). Add "
                    "it on the employee record.") % {'code': code, 'why': why[:160]}
            return ('%s %s' % (note, bit)).strip()
        return note

    # =================================================================
    # After the hire is approved
    # =================================================================
    @api.model
    def _joiner_hired(self, joiner, proposal):
        """The new-hire request was approved and the person exists: record
        them, write their code, and send the rest of their row through the
        lanes of the same named update AS THE PERSON WHO SENT THE FILE. Never
        raises — the approval itself must stand whatever happens here."""
        result = proposal.result() or {}
        try:
            emp_id = int(result.get('employee_id') or 0)
        except (TypeError, ValueError):
            emp_id = 0
        if not emp_id:
            joiner.write({'state': 'needs_attention', 'note': _(
                "Approved, but the new employee could not be found.")})
            return False
        vals = {'employee_id': emp_id, 'state': 'created',
                'contract_id': int(result.get('contract_id') or 0) or False}
        if result.get('error'):
            vals['note'] = _("The contract could not be made: %s") % result['error']
        joiner.write(vals)
        sender = self._as_sender(joiner)
        note = sender._joiner_code(emp_id, joiner.code, joiner.note or '')
        if note != (joiner.note or ''):
            joiner.write({'note': note})
        return self._joiner_send(joiner, sender)

    @api.model
    def _as_sender(self, joiner):
        return self.env['pb.updates.desk'].with_user(joiner.user_id).with_context(
            allowed_company_ids=[joiner.company_id.id])

    @api.model
    def _joiner_send(self, joiner, upd):
        """Send a hired person's kept values through the lanes, in a savepoint.
        `upd` is `pb.updates.desk` as the person acting. True when done."""
        cells = joiner.cells()
        if not cells:
            joiner.write({'cells_done': True})
            return True
        changes = [dict(c, emp_id=joiner.employee_id.id) for c in cells]
        try:
            with self.env.cr.savepoint():
                answer = upd._joiner_apply_cells(changes, joiner.batch_id)
        except Exception as error:   # noqa: BLE001 — the hire stands
            _logger.info('pb_updates: values for new employee %s not sent: %s',
                         joiner.id, error)
            why = str(getattr(error, 'name', None) or getattr(error, 'args', [''])[0] or '')
            joiner.write({'state': 'needs_attention', 'cells_done': False,
                          'note': _("Hired. %(n)s values from the sheet are still "
                                    "to apply: %(why)s") % {'n': len(cells),
                                                            'why': why[:300]}})
            return False
        refused = answer.get('refused') or []
        bits = []
        if refused:
            bits.append(_("%s values could not be used.") % len(refused))
        joiner.write({'state': 'created', 'cells_done': True,
                      'note': ' '.join([b for b in [joiner.note or ''] + bits if b]) or False})
        return True

    @api.model
    def _joiner_apply_cells(self, changes, batch):
        """The kept values of one new employee, through the desk, as `self`'s
        user, filed under `batch`. Raises on anything refused as a whole."""
        desk = self._gate()
        changes, _skipped = self._drop_off_scheme(desk, changes)
        if not changes:
            return {'refused': []}
        buckets, refusal = self._split_by_start(desk, changes, None, 'pay')
        if refusal:
            raise UserError(refusal)
        if list(buckets) == [None]:
            answer = desk.apply_changes(0, buckets[None], note=batch.name or '',
                                        source='import')
            answers = [(None, answer)]
        else:
            answer, answers = self._apply_by_start(desk, buckets, batch.name or '', 'pay')
        if answer.get('ok') is False:
            raise UserError(answer.get('msg') or _("The values could not be sent."))
        ids = []
        for _day, a in answers:
            ids += a.get('apply_ids') or ([a['apply_id']] if a.get('apply_id') else [])
        self.env['pb.records.apply'].sudo().browse(ids).write({'updates_batch_id': batch.id})
        return answer

    @api.model
    def apply_now(self, joiner_id=0):
        """"Apply now": a hired person's kept values, read again against
        today's record and sent through the lanes as the person pressing."""
        desk = self._gate()
        if not self._can_write(desk):
            return {'ok': False, 'msg': _(
                "Sending these values needs permission to change employee "
                "records. Ask an administrator for the HR or Payroll Officer "
                "role.")}
        try:
            joiner_id = int(joiner_id or 0)
        except (TypeError, ValueError):
            joiner_id = 0
        joiner = self.env['pb.updates.joiner'].search(
            [('id', '=', joiner_id), ('company_id', 'in', self.env.companies.ids)],
            limit=1).sudo()
        if not joiner:
            return {'ok': False, 'msg': _(
                "That new employee is not on record in the companies you are "
                "working in.")}
        self._joiner_sync(joiner)
        if joiner.state != 'needs_attention' or not joiner.employee_id:
            return {'ok': False, 'msg': _("There is nothing left to apply for %s.")
                    % joiner.name}
        upd = self.with_context(allowed_company_ids=[joiner.company_id.id])
        if not joiner.cells_done:
            if not upd._joiner_send(joiner, upd):
                return {'ok': False, 'msg': joiner.note or _("The values could not be sent.")}
        joiner.write({'state': 'created'})
        return {'ok': True, 'msg': _("%s: the values from the sheet are sent.") % joiner.name}

    @api.model
    def _joiner_sync(self, joiners):
        """A waiting row whose request was decided without the hook having
        run (a request approved before this module was upgraded, say): read
        the request's own state."""
        for joiner in joiners.filtered(lambda r: r.state == 'waiting' and r.proposal_id):
            prop = joiner.proposal_id
            if prop.state == 'applied' and prop.applied:
                result = prop.result() or {}
                emp_id = int(result.get('employee_id') or 0)
                joiner.write({'state': 'needs_attention', 'cells_done': not joiner.cells(),
                              'employee_id': emp_id or False,
                              'note': _("Hired. %s values from the sheet are still "
                                        "to apply.") % len(joiner.cells())})
            elif prop.state in ('rejected', 'returned'):
                joiner.write({'state': 'turned_down', 'note': _("Turned down")
                              if prop.state == 'rejected' else _("Sent back")})

    # =================================================================
    # What the screens say
    # =================================================================
    @api.model
    def _joiner_payload(self, rec, with_whom=''):
        labels = dict(JOINER_STATES)
        state = rec.state
        label = _(labels.get(state, state))
        if state == 'waiting':
            if not with_whom and rec.proposal_id:
                try:
                    with_whom = rec.proposal_id.waiting_for()
                except Exception:   # noqa: BLE001
                    with_whom = ''
            line = _("Waiting for approval (%(ref)s) with %(who)s") % {
                'ref': rec.reference or '', 'who': with_whom} if with_whom else \
                _("Waiting for approval (%s)") % (rec.reference or '')
        elif state == 'created':
            line = _("Added, starts %s") % self.start_label(
                fields.Date.to_string(rec.start_date)) if rec.start_date else _("Added")
        elif state == 'needs_attention':
            line = rec.note or _("Hired. %s values from the sheet are still to "
                                 "apply.") % rec.values_count
        else:
            line = rec.note or _("Turned down")
        return {
            'id': rec.id, 'row': rec.row, 'name': rec.name, 'state': state,
            'state_label': label, 'line': line, 'reference': rec.reference or '',
            'team': rec.department_id.display_name or '',
            'employee_id': rec.employee_id.id or 0,
            'values': rec.values_count, 'note': rec.note or '',
            'with_whom': with_whom,
            'can_apply_now': state == 'needs_attention' and bool(rec.employee_id),
        }

    @api.model
    def _batch_row(self, batch, may_write):
        row = super()._batch_row(batch, may_write)
        joiners = self.env['pb.updates.joiner'].sudo().search([('batch_id', '=', batch.id)])
        if joiners:
            self._joiner_sync(joiners)
            row['joiners'] = [dict(self._joiner_payload(j),
                                   can_apply_now=bool(may_write and j.state == 'needs_attention'
                                                      and j.employee_id))
                              for j in joiners]
            if not batch.apply_ids:
                waiting = joiners.filtered(lambda j: j.state == 'waiting')
                row['state'] = 'pending' if waiting else 'applied'
                row['state_label'] = _("Waiting for approval") if waiting else _("Applied")
                row['people'] = len(joiners)
        return row

    @api.model
    def get_joiners_waiting(self):
        """The home's "New employees waiting": requests still with somebody
        and hired people whose values are still to apply."""
        desk = self._gate()
        may_write = self._can_write(desk)
        rows = self.env['pb.updates.joiner'].search([
            ('company_id', 'in', self.env.companies.ids),
            ('state', 'in', ('waiting', 'needs_attention'))], order='id desc', limit=200).sudo()
        self._joiner_sync(rows)
        rows = rows.filtered(lambda r: r.state in ('waiting', 'needs_attention'))
        return {'items': [dict(self._joiner_payload(r), batch=r.batch_id.name or '',
                               can_apply_now=bool(may_write and r.state == 'needs_attention'
                                                  and r.employee_id))
                          for r in rows]}

    @api.model
    def get_home(self):
        answer = super().get_home()
        try:
            answer['joiners_waiting'] = self.get_joiners_waiting()['items']
            answer['can_hire'] = self._may_hire()
        except Exception:   # noqa: BLE001 — a list never blocks the home
            _logger.exception('pb_updates: new employees waiting failed')
            answer['joiners_waiting'] = []
            answer['can_hire'] = False
        return answer

    # =================================================================
    # Reading a file: the "Pay scheme" check column
    # =================================================================
    @api.model
    def read_columns(self, file_b64='', filename='', kind='lasting', month=None):
        answer = super().read_columns(file_b64, filename, kind, month)
        if kind == 'oneoff' or not answer.get('ok'):
            return answer
        taken = any(c.get('target') == SCHEME_TARGET for c in answer['columns'])
        for col in answer['columns']:
            if taken:
                break
            if col.get('target') and col['target'] != 'ignore':
                continue
            head = _norm(col.get('head'))
            remembered = col.get('how') == 'memory'
            if head in SCHEME_HEADINGS and not remembered:
                col.update(how='label', target=SCHEME_TARGET, field_id='')
                taken = True
        if answer.get('columns'):
            answer['from_sheet'] = any(c['how'] == 'id' for c in answer['columns']) and all(
                c['how'] in ('id', 'identity') or c.get('target') == SCHEME_TARGET
                for c in answer['columns'])
        return answer

    @api.model
    def _clean_columns(self, columns):
        cols = super()._clean_columns(columns)
        scheme = 0
        for idx, target in list(cols['used'].items()):
            if target == SCHEME_TARGET:
                scheme = scheme or idx
                cols['used'].pop(idx)
        cols['scheme'] = scheme if scheme not in cols['identity'].values() else 0
        return cols

    @api.model
    def _remember_layout(self, desk, file_b64, filename, cols):
        if cols.get('scheme'):
            used = dict(cols['used'])
            used[cols['scheme']] = SCHEME_TARGET
            cols = dict(cols, used=used)
        return super()._remember_layout(desk, file_b64, filename, cols)

    # =================================================================
    # The blank sheet for new employees
    # =================================================================
    @api.model
    def joiner_sheet_schemes(self):
        """The pay schemes the blank new-employee sheet can carry pay items
        of: `[{id, name, items}]`."""
        desk = self._gate()
        out = []
        for cid, scheme in sorted(self._scheme_items(desk).items(),
                                  key=lambda kv: (kv[1]['name'].lower(), kv[0])):
            out.append({'id': cid, 'name': scheme['name'], 'items': len(scheme['codes'])})
        return {'schemes': out}

    @api.model
    def download_joiner_sheet(self, config_id=0):
        """Headings only: the identity three, the columns a new employee
        needs, "Pay scheme", and the pay items of the chosen scheme — with a
        "Read me" sheet. Every heading carries its card id, so the file reads
        back as a Payobook sheet."""
        desk = self._gate()
        try:
            import openpyxl
            from openpyxl.comments import Comment
            from openpyxl.styles import Alignment, Font, PatternFill
            from openpyxl.utils import get_column_letter
        except Exception:   # noqa: BLE001 — a missing library, not a bug
            return {'ok': False, 'msg': _(
                "Spreadsheets cannot be written on this server yet. Ask an "
                "administrator to install the spreadsheet library.")}
        cards = desk._cards(0)
        try:
            config_id = int(config_id or 0)
        except (TypeError, ValueError):
            config_id = 0
        schemes = self._scheme_items(desk)
        scheme = schemes.get(config_id) if config_id else None
        picked = [cards[f] for f in BLANK_COLUMNS if f in cards]
        if scheme:
            for code in sorted(scheme['codes']):
                card = cards.get('c:%s' % code)
                if card:
                    picked.append(card)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = SHEET
        bold = Font(bold=True, color='241F52')
        id_fill = PatternFill('solid', fgColor='EEF2F6')
        head_fill = PatternFill('solid', fgColor='EAF1FB')
        need_fill = PatternFill('solid', fgColor='E4DEF7')
        author = product_label(self.env)
        heads = [(_(label), None, id_fill) for _key, label in IDENTITY_COLS]
        need = {TEAM, START}
        for card in picked:
            heads.append((card['label'], card['id'],
                          need_fill if card['id'] in need else head_fill))
        heads.append((_("Pay scheme"), SCHEME_TARGET, head_fill))
        for idx, (label, cid, fill) in enumerate(heads, start=1):
            cell = ws.cell(row=1, column=idx, value=label)
            cell.font = bold
            cell.fill = fill
            cell.alignment = Alignment(vertical='center')
            if cid and cid != SCHEME_TARGET:
                cell.comment = Comment(text=ID_COMMENT % cid, author=author)
            ws.column_dimensions[get_column_letter(idx)].width = \
                max(16, min(36, len(label or '') + 6))
        ws.freeze_panes = 'D2'
        meta = wb.create_sheet(title=META_SHEET)
        meta['A1'] = 'config_id'
        meta['B1'] = 0
        meta['A2'] = 'column_index'
        meta['B2'] = 'field_id'
        meta['C2'] = 'label'
        for offset, card in enumerate(picked):
            meta.cell(row=3 + offset, column=1, value=len(IDENTITY_COLS) + 1 + offset)
            meta.cell(row=3 + offset, column=2, value=card['id'])
            meta.cell(row=3 + offset, column=3, value=card['label'])
        meta.sheet_state = 'hidden'
        guide = wb.create_sheet(title=_("Read me")[:31])
        guide.column_dimensions['A'].width = 110
        lines = [
            _("How to fill in this sheet for new employees"),
            _("One row per new person. Each row needs at least a Name, a Team "
              "that already exists, and a Contract start date (shaded columns)."),
            _("Type a Wage to give the person a first contract. Leave it blank "
              "and the person is added without a contract."),
            _("Team, Job, Manager, Country and Working hours must already exist: "
              "nothing is created from this sheet. A manager can be given by "
              "name, employee code or work email."),
            _("Pay scheme is a check only: it must be the scheme the team is "
              "paid under. It never changes who is paid by what."),
            _("When you upload it, choose \"Add these people as new employees\" "
              "on the review. Each person goes through your company's new-hire "
              "approval, exactly like Add employee."),
            _("Adding a person cannot be undone from Updates. Check the review "
              "before you apply."),
        ]
        if scheme:
            lines.insert(5, _("The pay items are those of %s. A pay item left "
                              "blank is not set.") % scheme['name'])
        for idx, line in enumerate(lines, start=1):
            cell = guide.cell(row=idx, column=1, value=line)
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            if idx == 1:
                cell.font = bold
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        stem = _("%(product)s new employees %(date)s") % {
            'product': product_label(self.env),
            'date': fields.Date.context_today(self).isoformat()}
        return {'ok': True, 'file_b64': base64.b64encode(out.read()).decode(),
                'filename': re.sub(r'[\\/:*?"<>|]+', '-', stem) + '.xlsx',
                'mimetype': XLSX_MIME, 'rows': 0, 'total': 0,
                'columns': len(heads)}
