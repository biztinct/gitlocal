# -*- coding: utf-8 -*-
"""`pb.updates.desk` — the Updates screen's whole server side.

An AbstractModel and a FACADE. Every value is read, judged, written, audited,
routed for approval and undone by `pb.records.desk` (`pb_records`), in Master
records mode (`config_id = 0`: the scheme-free catalogue of employee, contract,
bank and contract-component fields). What this file adds is only what a guided
front door needs and the desk does not have:

  * column matching for a file the desk did not export — the company's
    remembered layouts first, then a careful guess, and always the person's
    own choice last (`read_columns`);
  * the peek reshaped into a person × column grid in the file's own row order
    (`review`);
  * a NAMED update that keeps the original file and points at the desk apply
    it produced (`apply`, `get_history`, `undo`).

Rails, all inherited rather than re-implemented:

  * nothing is written before `apply`, and `apply` writes only through
    `Desk.apply_changes`, which re-evaluates every change server-side (so the
    browser's list is trusted no more than the desk trusts it);
  * this file never calls `sudo()` on an employee or a contract — people are
    read through the desk's own scoped helpers;
  * every public method starts with the desk's own read gate.
"""
import difflib
import logging
import re

from odoo import _, api, fields, models
from odoo.tools.misc import format_date

from odoo.addons.pb_records.models.pb_records_io import _norm, XLSX_MIME
from odoo.addons.pb_records.models.records_approval import lane_of
from odoo.addons.pb_updates.models.updates_batch import heading_fingerprint

try:  # WHITELABEL — the tenant's own name for the product
    from odoo.addons.biz_debrand.models.brand import product_label
except Exception:  # pragma: no cover — biz_debrand absent on this build
    def product_label(env, default='Payobook'):
        return default

_logger = logging.getLogger(__name__)

EMP = 'hr.employee'
CON = 'hr.contract'

#: UPDATES P2b — the two context keys that switch the Records Desk's
#: Updates-only seams on (`pb_records`): every pay item of every pay scheme in
#: the catalogue (`records_scheme_items`), and the explicit-CLEAR rules
#: (`records_strict_clear`). The Records screen sets neither.
DOOR_CONTEXT = {'records_scheme_items': True, 'records_strict_clear': True,
                # UPDATES P2c: values come from a file, so a sentence about a
                # manager named twice says what to type, not where to click.
                'records_from_file': True,
                # UPDATES P3a (D3): a file is split into three lanes —
                # personal details, pay and contract, bank details — and its
                # personal details apply at once where the company allows it.
                'records_lanes': True,
                'records_details_at_once': True}

#: UPDATES P2c — the "Goes to" target of the column that says when a row's
#: changes start. It is never a value to write: Updates reads it itself.
WHEN_TARGET = 'when:start'
#: UPDATES P3b — the "Goes to" target of a "Pay scheme" column: a CHECK of a
#: new employee's team, never a value to write (`updates_joiners.py`).
SCHEME_TARGET = 'check:scheme'
#: At most this many different start dates in one file (keeps approvals
#: readable): more is refused before the review.
MAX_START_DATES = 6
#: The catalogue groups a future date holds back by default ("Pay and
#: contract changes wait; personal details change today").
DATED_GROUPS = ('contract', 'component')
#: Headings that most likely mean "the start date of this row". A guess only
#: — "Start date" on its own is the CONTRACT's start date and stays that.
START_HEADINGS = ('start date for this row', 'effective date', 'effective from',
                  'starts on', 'start from', 'change starts', 'ngày hiệu lực',
                  'ngày áp dụng', 'tanggal efektif', 'berlaku mulai')
MANAGER_FIELDS = ('f:hr.employee:parent_id', 'f:hr.employee:coach_id')

#: The desk's four catalogue groups, in order, with their icons. Their words
#: are `PbUpdatesDesk._topic_label` (literal `_()` calls, so they translate).
TOPICS = (
    ('employee', 'user'),
    ('contract', 'fileText'),
    ('bank', 'creditCard'),
    ('component', 'banknote'),
)
#: The fields a topic is best described by, when the catalogue has them.
TOPIC_EXAMPLES = {
    'employee': ('job_title', 'department_id', 'parent_id', 'work_email',
                 'mobile_phone', 'work_phone'),
    'contract': ('wage', 'date_start', 'date_end', 'resource_calendar_id'),
}
#: How close a heading must read to a field's name before it is offered as a
#: guess. High on purpose: a wrong guess is worse than no guess, because a
#: person may not look twice at a column that already says where it goes.
GUESS_RATIO = 0.86
IDENTITY_KEYS = ('code', 'name', 'email')
#: The fields whose value IS how a row finds its person (the desk's matching
#: ladder, `pb_records_io.CODE_FIELDS`, plus the name and the work email).
IDENTITY_FIELDS = {
    'f:hr.employee:barcode': 'code',
    'f:hr.employee:employee_id': 'code',
    'f:hr.employee:identification_id': 'code',
    'f:hr.employee:pb_source_ref': 'code',
    'f:hr.employee:name': 'name',
    'f:hr.employee:work_email': 'email',
}


def _same_text(file_text, shown):
    """True when a file cell says exactly what the screen shows today.

    Whitespace-insensitive but CASE-SENSITIVE, so "operator" → "Operator" is
    still a change somebody asked for."""
    left = re.sub(r'\s+', ' ', str(file_text if file_text is not None else '')).strip()
    right = re.sub(r'\s+', ' ', str(shown if shown is not None else '')).strip()
    return bool(left) and left == right


class PbUpdatesDesk(models.AbstractModel):
    _name = 'pb.updates.desk'
    _description = 'Updates'

    # =================================================================
    # Helpers
    # =================================================================
    @api.model
    def _desk(self):
        """The Records Desk, with Updates' two opt-in seams switched on
        (UPDATES P2b): every pay item of every pay scheme in the catalogue,
        and CLEAR's rules. Every desk call Updates makes goes through here, so
        the catalogue a column was matched against is the one its values are
        judged and written against."""
        return self.env['pb.records.desk'].with_context(**DOOR_CONTEXT)

    @api.model
    def _gate(self):
        desk = self._desk()
        desk._check_read()
        return desk

    @api.model
    def _can_write(self, desk=None):
        desk = desk or self._desk()
        return bool(desk._may_write(EMP) or desk._may_write(CON))

    @api.model
    def _topic_label(self, key):
        """The desk's four groups, in the words a payroll officer uses."""
        return {
            'employee': _("Personal and job details"),
            'contract': _("Contract"),
            'bank': _("Bank details"),
            'component': _("Ongoing pay items"),
        }.get(key, key)

    @api.model
    def _catalogue(self, desk=None):
        """The desk's Master-records catalogue, relabelled into topics.

        `(topics, by_id, data)` — `topics` for the screen, `by_id` a flat
        `{card id: {label, group}}` for reshaping, `data` the desk's answer."""
        desk = desk or self._desk()
        data = desk.get_fields(0)
        groups = {g['key']: g for g in data.get('groups') or []}
        # UPDATES P2b: which pay schemes have each pay item, for the "Goes
        # to" list's groups and the sheet's columns.
        by_code = {}
        if groups.get('component'):
            for cid, scheme in sorted(self._scheme_items(desk).items(),
                                      key=lambda kv: (kv[1]['name'].lower(), kv[0])):
                for code in scheme['codes']:
                    by_code.setdefault(code, []).append(
                        {'id': cid, 'name': scheme['name']})
        topics, by_id = [], {}
        for key, icon in TOPICS:
            group = groups.get(key)
            if not group:
                continue
            rows = []
            for card in group['fields']:
                row = {'id': card['id'], 'label': card.get('label') or '',
                       'group': key, 'ttype': card.get('ttype') or '',
                       'editable': bool(card.get('editable')),
                       'locked': bool(card.get('locked'))}
                if key == 'component':
                    row['code'] = card.get('code') or card['id'][2:]
                    row['schemes'] = by_code.get(row['code'], [])
                by_id[card['id']] = row
                # A field that is read-only ON THE RECORD (not merely locked
                # for this person) can never be changed from a file, so it is
                # neither put in the sheet nor offered as a destination: every
                # cell of it would come back refused.
                if not row['editable'] and not row['locked']:
                    continue
                rows.append(row)
            wanted = TOPIC_EXAMPLES.get(key) or ()
            preferred = [r['label'] for name in wanted for r in rows
                         if r['id'].endswith(':%s' % name)]
            examples = (preferred + [r['label'] for r in rows
                                     if r['label'] not in preferred])[:3]
            topics.append({
                'key': key, 'label': self._topic_label(key), 'icon': icon,
                'count': len(rows), 'field_ids': [r['id'] for r in rows],
                'fields': rows, 'examples': examples,
                'locked': bool(rows) and all(r['locked'] for r in rows),
            })
        return topics, by_id, data

    @api.model
    def _clean_columns(self, columns):
        """The browser's column choice, read defensively.

        `{'used': {idx: card id}, 'identity': {key: idx}, 'heads': {idx: text}}`
        with integer keys. Keys arrive as strings over JSON-RPC."""
        columns = columns if isinstance(columns, dict) else {}

        def as_int(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0

        used, start = {}, 0
        for key, value in sorted((columns.get('used') or {}).items(),
                                 key=lambda kv: as_int(kv[0])):
            idx = as_int(key)
            if idx <= 0 or not value:
                continue
            if str(value) == WHEN_TARGET:
                # UPDATES P2c: at most one start-date column — the first.
                start = start or idx
                continue
            used[idx] = str(value)
        identity = {}
        for key in IDENTITY_KEYS:
            idx = as_int((columns.get('identity') or {}).get(key))
            if idx > 0:
                identity[key] = idx
        heads = {}
        for key, value in (columns.get('heads') or {}).items():
            idx = as_int(key)
            if idx > 0:
                heads[idx] = str(value if value is not None else '')
        if start in identity.values():
            start = 0
        return {'used': used, 'identity': identity, 'heads': heads,
                'start': start}

    @api.model
    def _people_info(self, desk, emp_ids):
        """`{emp_id: {name, code, department}}` through the desk's own scoped
        search — never a `sudo()` of our own on the employee model."""
        if not emp_ids:
            return {}
        people = desk._matching({'employee_ids': list(emp_ids)}, ctx={})
        return {e.id: {'name': e.display_name or e.name or '',
                       'code': e.barcode or e.employee_id or '',
                       'department': e.department_id.display_name or ''}
                for e in people}

    # =================================================================
    # Home
    # =================================================================
    @api.model
    def get_home(self):
        desk = self._gate()
        topics, _by_id, data = self._catalogue(desk)
        can_write = data.get('can_write') or {}
        return {
            'can_write': bool(can_write.get('employee') or can_write.get('contract')),
            'can_export': bool(data.get('can_export')),
            'people_count': len(desk._matching({}, ctx={})),
            'topics': topics,
            'history': self.get_history(8)['batches'],
            'coming_up': self.get_coming_up()['items'],
            'today': fields.Date.to_string(
                self.env['pb.records.apply']._today_for()),
        }

    @api.model
    def download_sheet(self, topic_keys=None, filters=None):
        """The desk's own export, for the fields of the picked topics."""
        desk = self._gate()
        if not desk._may_export():
            return {'ok': False, 'msg': _(
                "Downloading a sheet needs permission to export employee "
                "records. Ask an administrator, or upload a file of your own.")}
        topics, by_id, _data = self._catalogue(desk)
        keys = set(topic_keys or [])
        field_ids = [fid for t in topics if t['key'] in keys
                     for fid in t['field_ids']]
        if not field_ids:
            return {'ok': False, 'msg': _(
                "Pick at least one topic first, so the sheet has columns to "
                "fill in.")}
        blank_cells, notes = {}, []
        if 'component' in keys:
            field_ids, blank_cells = self._sheet_pay_items(
                desk, filters or {}, field_ids, by_id)
            notes = [
                _("How to fill in this sheet"),
                _("Change a value to update it. Leave a cell as it is, or "
                  "blank, and nothing changes for it."),
                _("Grey cells are pay items that are not in that person's pay "
                  "scheme. They stay blank and anything typed there is left "
                  "out."),
                _("To empty a value, type CLEAR in its cell."),
            ]
        if any(fid in field_ids for fid in MANAGER_FIELDS):
            # UPDATES P2c (decision D9): how a manager may be named.
            if not notes:
                notes = [_("How to fill in this sheet"),
                         _("Change a value to update it. Leave a cell as it "
                           "is, or blank, and nothing changes for it.")]
            notes.append(_("A manager or coach can be given by name, employee "
                           "code or work email. A name nobody has is not "
                           "used, and nobody is ever created from this sheet."))
        answer = desk.export_records(0, filters or {}, field_ids, 'data',
                                     blank_cells=blank_cells, notes=notes)
        if answer.get('ok'):
            # The desk names its files after a pay scheme; this one is not
            # tied to any, so it gets a name a person recognises in Downloads.
            answer['filename'] = _("%(product)s update sheet %(date)s.xlsx") % {
                'product': product_label(self.env),
                'date': fields.Date.context_today(self).isoformat()}
        return answer

    @api.model
    def _sheet_pay_items(self, desk, filters, field_ids, by_id):
        """`(field_ids, blank_cells)` for a sheet that carries pay items.

        The columns: every pay item of the pay schemes the people in the
        sheet are paid under, plus every pay item that already has a line on
        some contract (the sheet always carried those). A cell for a person
        whose schemes do not have that pay item, and whose contract has no
        line for it, is left blank and greyed."""
        pay = [fid for fid in field_ids if by_id.get(fid, {}).get('group') == 'component']
        if not pay:
            return field_ids, {}
        people = desk._matching(filters, ctx={})
        codes = {by_id[fid]['code']: fid for fid in pay}
        ctx = self._scheme_context(desk, people.ids, set(codes))
        in_file = {cid for p in ctx['people'].values() for cid in p['ids']}
        wanted = set()
        for cid in in_file:
            wanted |= (ctx['items'].get(cid) or {}).get('codes', set())
        saved = {by_id[fid]['code'] for fid in pay if not by_id[fid].get('schemes')}
        # A pay item of a scheme nobody in the sheet is paid under is left
        # out; one kept on contracts (no scheme has it) stays, as before.
        held = {code for (_emp, code) in ctx['held']}
        keep = {fid for code, fid in codes.items()
                if code in wanted or code in saved or code in held}
        if not in_file:
            keep = set(pay)
        field_ids = [fid for fid in field_ids if fid not in pay or fid in keep]
        blank = {}
        for emp_id in people.ids:
            for fid in keep:
                if self._is_off_scheme(ctx, emp_id, fid):
                    blank.setdefault(emp_id, set()).add(fid)
        return field_ids, blank

    # =================================================================
    # Match columns
    # =================================================================
    @api.model
    def _guess(self, head, by_id, taken):
        best, best_ratio = '', 0.0
        for fid, row in by_id.items():
            if fid in taken or not row['editable']:
                continue
            ratio = difflib.SequenceMatcher(None, head, _norm(row['label'])).ratio()
            if ratio > best_ratio:
                best, best_ratio = fid, ratio
        return best if best_ratio >= GUESS_RATIO else ''

    @api.model
    def read_columns(self, file_b64='', filename='', kind='lasting', month=None):
        """What each column of the file is, and where it most likely goes.

        UPDATES P2d: `kind='oneoff'` reads a sheet of one-off pay items for a
        pay month (`updates_oneoff_desk.py`); the lasting-change reading below
        is untouched.

        Placement, best first: the desk's own (a Payobook sheet's hidden ids,
        its identity headings, a heading equal to a field's name); then this
        company's remembered matchings (the exact set of headings first, then
        any matching that knows the heading); then a careful guess. A card a
        memory or a guess points at that is no longer in the catalogue is
        dropped. The same field is never offered to two columns."""
        if kind == 'oneoff':
            return self._oneoff_read_columns(file_b64, filename, month)
        desk = self._gate()
        res, body = desk._import_columns(0, file_b64, filename)
        if not res.get('ok'):
            return res
        if not res.get('rows'):
            return {'ok': False, 'empty': True, 'filename': res.get('filename'),
                    'msg': _("This file has headings only — fill it in and "
                             "drop it again.")}
        topics, by_id, _data = self._catalogue(desk)
        offered = {f['id'] for t in topics for f in t['fields']}
        columns = res['columns']
        fingerprint = heading_fingerprint([c['head'] for c in columns])
        Layout = self.env['pb.updates.layout']
        layouts = Layout.search([('company_id', '=', self.env.company.id),
                                 ('kind', 'not in', ('oneoff', 'leave'))],
                                order='last_used desc, id desc', limit=50)
        exact = layouts.filtered(lambda l: l.fingerprint == fingerprint)[:1]
        maps = ([exact.get_map()] if exact else []) + \
            [l.get_map() for l in layouts if l != exact]

        # A heading such as "Employee Name" or "Employee ID" reads exactly
        # like the field that HOLDS the name or the code, so the desk's label
        # step places it as a value to write. On a file the desk did not export
        # that is almost never what the person meant, and finding the person is
        # the safe reading: it can only match a row, never change a record.
        taken_identity = {c['identity'] for c in columns if c['identity']}
        for col in columns:
            key = IDENTITY_FIELDS.get(col['field_id']) if col['how'] == 'label' else ''
            if key and key not in taken_identity:
                taken_identity.add(key)
                col.update(how='identity', identity=key, field_id='')

        taken = {c['field_id'] for c in columns if c['field_id']}
        when_taken = scheme_taken = False
        for col in columns:
            col['target'] = col['field_id'] or (
                'identity:%s' % col['identity'] if col['identity'] else '')
            if col['how']:
                continue
            head = _norm(col['head'])
            remembered = next((m[head] for m in maps if head in m), '')
            if remembered:
                if remembered == 'ignore':
                    col.update(how='memory', target='ignore')
                    continue
                if remembered == WHEN_TARGET:
                    # UPDATES P2c — the start-date column, remembered.
                    if not when_taken:
                        when_taken = True
                        col.update(how='memory', target=WHEN_TARGET)
                    continue
                if remembered == SCHEME_TARGET:
                    # UPDATES P3b — the new employees' pay scheme check.
                    if not scheme_taken:
                        scheme_taken = True
                        col.update(how='memory', target=SCHEME_TARGET)
                    continue
                if remembered.startswith('identity:'):
                    key = remembered.split(':', 1)[1]
                    if key in IDENTITY_KEYS and key not in taken_identity:
                        taken_identity.add(key)
                        col.update(how='memory', identity=key, target=remembered)
                        continue
                elif remembered in offered and remembered not in taken:
                    taken.add(remembered)
                    col.update(how='memory', field_id=remembered, target=remembered)
                    continue
            if head in START_HEADINGS and not when_taken:
                when_taken = True
                col.update(how='guess', target=WHEN_TARGET)
                continue
            guess = self._guess(head, by_id, taken)
            if guess:
                taken.add(guess)
                col.update(how='guess', field_id=guess, target=guess)

        placed_by_id = [c for c in columns if c['how'] == 'id']
        from_sheet = bool(placed_by_id) and all(
            c['how'] in ('id', 'identity') for c in columns)
        answer = {
            'ok': True, 'filename': res.get('filename'), 'rows': res['rows'],
            'truncated': bool(res.get('truncated')), 'columns': columns,
            'fields': topics, 'layout_known': bool(exact),
            'from_sheet': from_sheet, 'schemes': [], 'no_scheme': 0,
        }
        if any(t['key'] == 'component' and t['fields'] for t in topics):
            # UPDATES P2b: the pay schemes of the people in this file, with
            # head-counts, so the "Goes to" list can put their pay items first.
            ids = self._file_people(desk, columns, body)
            if ids:
                ctx = {'people': self._people_schemes(ids), 'held': set()}
                ctx['items'] = self._scheme_items(
                    desk, {c for p in ctx['people'].values() for c in p['ids']})
                answer.update(self._strip(ctx, ids))
        return answer

    @api.model
    def file_schemes(self, file_b64='', filename='', identity=None):
        """The "Goes to" list's head-counts again, after the person chose by
        hand which column finds the person (UPDATES P2b). Reads only.
        `identity` is `{'code'|'name'|'email': column number}`."""
        desk = self._gate()
        res, body = desk._import_columns(0, file_b64, filename)
        out = {'ok': bool(res.get('ok')), 'schemes': [], 'no_scheme': 0}
        if not res.get('ok'):
            return out
        columns = []
        for key, idx in (identity or {}).items():
            try:
                idx = int(idx or 0)
            except (TypeError, ValueError):
                idx = 0
            if key in IDENTITY_KEYS and idx > 0:
                columns.append({'idx': idx, 'target': 'identity:%s' % key})
        ids = self._file_people(desk, columns, body)
        if ids:
            ctx = {'people': self._people_schemes(ids), 'held': set()}
            ctx['items'] = self._scheme_items(
                desk, {c for p in ctx['people'].values() for c in p['ids']})
            out.update(self._strip(ctx, ids))
        return out

    @api.model
    def _file_people(self, desk, columns, body):
        """The people a file's rows find, by the columns placed as "finds the
        person" so far — the desk's own matching ladder (code, email, name).
        Only for head-counts: the review matches again with what was chosen."""
        identity = {}
        for col in columns:
            target = col.get('target') or ''
            if target.startswith('identity:'):
                identity.setdefault(target.split(':', 1)[1], col['idx'])
        if not identity or not body:
            return []
        index = desk._io_index(desk._matching({}, ctx={}))
        found = set()
        for _offset, row in body[:10000]:
            values = {key: desk._io_text(desk._io_cell(row, idx))
                      for key, idx in identity.items()}
            emp_id, _method, _why = desk._io_match(
                index, values.get('code'), values.get('name'), values.get('email'))
            if emp_id:
                found.add(emp_id)
        return sorted(found)

    # =================================================================
    # Review
    # =================================================================
    @api.model
    def review(self, file_b64='', filename='', columns=None, kind='lasting',
               month=None):
        """The peek, as a person × column grid in the file's own row order.

        Writes nothing. A matched row's cell that has no value in the file is
        simply absent. When the same person is in the file twice the desk
        would write both values in file order, so the LOWER row's value is the
        one that stays; the earlier cell is shown as overridden and is not sent
        back, which leaves the result exactly what the desk would have made.

        UPDATES P2d: `kind='oneoff'` reviews one-off pay items for `month`."""
        if kind == 'oneoff':
            return self._oneoff_review(file_b64, filename, columns, month)
        desk = self._gate()
        cols = self._clean_columns(columns)
        if not cols['identity']:
            return {'ok': False, 'msg': _(
                "Pick the column that finds the person: an employee code, a "
                "name or a work email.")}
        if not cols['used']:
            return {'ok': False, 'msg': _(
                "Pick at least one column to bring in. Only the columns that "
                "find the person are matched so far.")}
        # `clear_word`: a cell saying CLEAR empties that value (decision D6).
        start_col = cols.get('start') or 0
        # UPDATES P3b — a "Pay scheme" column is read by Updates itself, for
        # rows that may be added as new employees; never a value to write.
        scheme_col = cols.get('scheme') or 0
        extras = [c for c in (start_col, scheme_col) if c]
        peek = desk.import_peek(
            0, file_b64, filename,
            columns={'used': {str(k): v for k, v in cols['used'].items()},
                     'identity': cols['identity']},
            clear_word=True,
            extra_columns=extras or None)
        if not peek.get('ok'):
            return peek
        # UPDATES P2c — each row's own start date, read and judged once.
        starts = {}
        if start_col:
            starts, refusal = self._row_starts(desk, peek, start_col)
            if refusal:
                return {'ok': False, 'msg': refusal}
        _topics, by_id, _data = self._catalogue(desk)
        seen, out_columns = set(), []
        for idx in sorted(cols['used']):
            fid = cols['used'][idx]
            if fid in seen or fid not in by_id or idx in cols['identity'].values():
                continue
            seen.add(fid)
            out_columns.append({'field_id': fid, 'label': by_id[fid]['label'],
                                'group': by_id[fid]['group'], 'idx': idx,
                                'head': cols['heads'].get(idx, ''),
                                # UPDATES P3a — the lane this column goes in.
                                'lane': lane_of(fid)})
        pay_codes = {c['field_id'][2:] for c in out_columns
                     if c['group'] == 'component'}
        base = {
            'ok': True, 'filename': peek.get('filename') or filename,
            'summary': peek.get('summary') or {},
            'identity': peek.get('identity') or '',
            'truncated': bool(peek.get('truncated')),
            'columns': out_columns,
            'pay_items': bool(pay_codes), 'schemes': [], 'no_scheme': 0,
            'dated': bool(start_col),
            'today': fields.Date.to_string(
                self.env['pb.records.apply']._today_for()),
        }
        if peek.get('empty'):
            base.update(empty=True, msg=peek.get('msg'), rows=[], unmatched=[],
                        changes=[])
            return base

        matched = peek.get('matched') or []
        changes = peek.get('changes') or []
        info = self._people_info(desk, {m['emp_id'] for m in matched})
        # UPDATES P2b: each person's pay scheme, asked once for the whole file
        # and only when the file brings pay items in.
        scheme_ctx = self._scheme_context(
            desk, {m['emp_id'] for m in matched}, pay_codes) if pay_codes else None

        # One queue of the desk's verdicts per (person, field).
        queues = {}
        for item in peek.get('items') or []:
            queues.setdefault((item['emp_id'], item['field_id']), []).append(item)

        # Slice the changes back into their file rows (`cells` per row), and
        # find, per (person, field), the LAST row that sets it.
        sliced, pointer, last_row = [], 0, {}
        for pos, m in enumerate(matched):
            count = int(m.get('cells') or 0)
            row_changes = changes[pointer:pointer + count]
            pointer += count
            sliced.append(row_changes)
            for change in row_changes:
                last_row[(change['emp_id'], change['field_id'])] = pos

        rows, ok_changes = [], []
        emp_rows = {}
        for m in matched:
            emp_rows[m['emp_id']] = emp_rows.get(m['emp_id'], 0) + 1
        for pos, m in enumerate(matched):
            person = info.get(m['emp_id']) or {}
            start = starts.get(m['row']) or {}
            cells = {}
            for change in sliced[pos]:
                key = (change['emp_id'], change['field_id'])
                queue = queues.get(key) or []
                is_last = last_row.get(key) == pos
                if start.get('error') and \
                        by_id.get(change['field_id'], {}).get('group') in DATED_GROUPS:
                    # UPDATES P2c: this row's start date cannot be read, so
                    # the values that would wait for it are refused. The
                    # verdict is still taken off the queue so the rows below
                    # read theirs.
                    if change['field_id'][:1] != 'b':
                        queue.pop(0) if queue else None
                    value = change.get('value')
                    cells[change['field_id']] = {
                        'status': 'refused', 'date_refused': True,
                        'old': '', 'new': '' if value is None else str(value),
                        'value': value, 'why': start['error']}
                    continue
                if change['field_id'][:1] == 'b':
                    # Four bank roles are judged as ONE account per person, so
                    # the desk answers once per role — for the last value.
                    item = queue[0] if (queue and is_last) else None
                else:
                    item = queue.pop(0) if queue else None
                value = change.get('value')
                text = '' if value is None else str(value)
                if not is_last:
                    cells[change['field_id']] = {
                        'status': 'dup', 'old': (item or {}).get('old_label', ''),
                        'new': (item or {}).get('new_label') or text,
                        'why': _("This person is in the file again further "
                                 "down, and that row's value is the one used."),
                        'value': value}
                    continue
                if scheme_ctx and self._is_off_scheme(
                        scheme_ctx, m['emp_id'], change['field_id']):
                    # Not in this person's pay scheme: greyed, never sent,
                    # never a problem to fix (decision D5).
                    cells[change['field_id']] = {
                        'status': 'off_scheme',
                        'old': (item or {}).get('old_label') or '',
                        'new': text, 'value': value, 'cleared': value == '',
                        'why': self._off_scheme_why(
                            scheme_ctx, m['emp_id'], person.get('name'),
                            by_id.get(change['field_id'], {}).get('label') or '')}
                    continue
                if item is None:
                    cells[change['field_id']] = {
                        'status': 'refused', 'old': '', 'new': text, 'value': value,
                        'why': _("This value could not be checked. Try it again.")}
                    continue
                status = item['status']
                if status in ('ok', 'refused') and _same_text(text, item.get('old_label')):
                    # The file says, word for word, what the screen shows on
                    # record today: the person meant "no change". Two live
                    # cases make this load-bearing (ledger G4, G11): a field
                    # read-only on the record is refused even when unchanged,
                    # and a named reference (working hours, department,
                    # manager) is looked up by NAME, so a namesake record or a
                    # department's full path reads as a change — applying an
                    # untouched sheet would re-point people or create
                    # departments. Shown as staying the same, never sent.
                    status = 'same'
                cells[change['field_id']] = {
                    'status': status, 'old': item.get('old_label') or '',
                    'new': item.get('new_label') or text,
                    'why': (item.get('why') or '') if status != 'same' else '',
                    'value': value}
                if value == '':
                    # A CLEAR from the file: shown as "Cleared", the old value
                    # struck through. Clearing what is already empty is "same".
                    cells[change['field_id']]['cleared'] = True
                if status == 'ok':
                    sent = {'emp_id': m['emp_id'],
                            'field_id': change['field_id'], 'value': value}
                    if start.get('date'):
                        sent['start'] = start['date']
                    ok_changes.append(sent)
            row = {
                'row': m['row'], 'emp_id': m['emp_id'], 'method': m.get('method'),
                'name': person.get('name') or '', 'code': person.get('code') or '',
                'department': person.get('department') or '',
                'twice': emp_rows.get(m['emp_id'], 0) > 1,
                'cells': cells,
            }
            if start_col:
                row['start'] = start
            if scheme_ctx:
                row.update(self._person_scheme(scheme_ctx, m['emp_id']))
            rows.append(row)
        if scheme_ctx:
            base.update(self._strip(scheme_ctx, [m['emp_id'] for m in matched]))
        unmatched = peek.get('unmatched') or []
        for entry in unmatched:
            extra = entry.pop('extra', None) or {}
            if start_col:
                entry['start'] = starts.get(entry['row']) or {}
            if scheme_col:
                value = extra.get(scheme_col)
                entry['scheme'] = '' if value in (None, False) else str(value).strip()
        base.update(rows=rows, unmatched=unmatched, changes=ok_changes)
        return base

    @api.model
    def _clear_words(self, desk, changes):
        """A value typed as CLEAR (any case, or the word in the reader's
        language) means "empty this value" — the same reading the file gets."""
        words = desk._io_clear_words()
        out = []
        for change in changes or []:
            if not isinstance(change, dict):
                continue
            value = change.get('value')
            if isinstance(value, str) and value.strip().lower() in words:
                change = dict(change, value='')
            out.append(change)
        return out

    @api.model
    def recheck(self, changes=None, kind='lasting', month=None):
        """After an on-screen fix or a row bound by hand: the desk's verdict,
        and — for a pay item — whether it is in the person's pay scheme at all
        (the same verdict `review` gives, UPDATES P2b)."""
        if kind == 'oneoff':
            return self._oneoff_recheck(changes, month)
        desk = self._gate()
        changes = self._clear_words(desk, changes)
        answer = desk.preview_changes(0, changes)
        pay = {str(c.get('field_id'))[2:] for c in changes
               if str(c.get('field_id') or '')[:2] == 'c:'}
        emp_ids = {int(c.get('emp_id') or 0) for c in changes} - {0}
        cleared = {(int(c.get('emp_id') or 0), c.get('field_id'))
                   for c in changes if c.get('value') == ''}
        ctx = self._scheme_context(desk, emp_ids, pay) if pay else None
        names = {i: p['name'] for i, p in self._people_info(desk, emp_ids).items()} \
            if ctx else {}
        for item in answer.get('items') or []:
            if (item['emp_id'], item['field_id']) in cleared:
                item['cleared'] = True
            if ctx and self._is_off_scheme(ctx, item['emp_id'], item['field_id']):
                item.update(status='off_scheme', why=self._off_scheme_why(
                    ctx, item['emp_id'], names.get(item['emp_id']),
                    item.get('field_label') or ''))
        if ctx:
            answer['people'] = {str(i): self._person_scheme(ctx, i) for i in emp_ids}
        return answer

    @api.model
    def lookup_people(self, term='', limit=10):
        desk = self._gate()
        return desk.lookup_people(term or '', limit=limit)

    # =================================================================
    # Apply
    # =================================================================
    @api.model
    def _remember_layout(self, desk, file_b64, filename, cols):
        heads = dict(cols['heads'])
        if not heads:
            res = desk.import_columns(0, file_b64, filename)
            heads = {c['idx']: c['head'] for c in res.get('columns') or []}
        identity_at = {idx: key for key, idx in cols['identity'].items()}
        pairs = []
        for idx in sorted(heads):
            if not _norm(heads[idx]):
                continue
            if idx in identity_at:
                target = 'identity:%s' % identity_at[idx]
            elif idx == cols.get('start'):
                target = WHEN_TARGET
            elif idx in cols['used']:
                target = cols['used'][idx]
            else:
                target = 'ignore'
            pairs.append((heads[idx], target))
        return self.env['pb.updates.layout'].remember(pairs)

    @api.model
    def _own_draft(self, draft_id):
        """The caller's own draft with this id, or an empty recordset. A
        search, so another person's draft is simply not found (record rule)
        and an id that is not a draft never is."""
        try:
            draft_id = int(draft_id or 0)
        except (TypeError, ValueError):
            draft_id = 0
        if not draft_id:
            return self.env['pb.updates.batch']
        return self.env['pb.updates.batch'].search(
            [('id', '=', draft_id), ('state', '=', 'draft'),
             ('user_id', '=', self.env.uid),
             ('company_id', 'in', self.env.companies.ids)], limit=1)

    @api.model
    def _new_batch(self, vals, file_b64='', filename='', draft_id=0):
        """The named update an apply files its parts under (UPDATES P3b).

        With the caller's own draft, the SAME record becomes the real update
        — no second batch, and the file it already keeps is kept once.
        Otherwise a new one, with the file, exactly as before."""
        draft = self._own_draft(draft_id)
        if draft:
            vals = dict(vals, state='sent', date=fields.Datetime.now(),
                        draft_columns=False, draft_choices=False,
                        draft_saved_at=False, draft_step=False)
            draft.write(vals)
            batch = draft
        else:
            batch = self.env['pb.updates.batch'].create(vals)
        if file_b64 and not batch.attachment_id:
            batch.attachment_id = self.env['ir.attachment'].create({
                'name': (filename or '').strip() or _("Update file"),
                'datas': file_b64,
                'res_model': 'pb.updates.batch',
                'res_id': batch.id,
                'mimetype': 'text/csv' if (filename or '').lower().endswith('.csv')
                else XLSX_MIME,
            })
        return batch

    @api.model
    def apply(self, name='', file_b64='', filename='', columns=None,
              changes=None, stats=None, start_date=None, hold_scope='pay',
              kind='lasting', month=None, draft_id=0, joiners=None):
        """Name the update, keep the file, and hand the changes to the desk.

        One transaction. The desk re-evaluates every change (whitelist, company
        scope, permissions, audit, approval route) — nothing here decides what
        is written. When the desk finds nothing to change, no batch is left
        behind and the answer says so.

        UPDATES P2c: `start_date` is the default start for every change that
        does not carry its own (`change['start']`, from the file's start-date
        column). Changes are grouped by start date — one desk apply per date,
        plus one with no date for today's values; with `hold_scope='pay'` a
        future date holds back only contract and pay-item values, and the
        personal and bank values of those rows go in today's apply. With no
        date anywhere this is exactly the call it always was.

        UPDATES P2d: `kind='oneoff'` sends one-off pay items for `month`
        (`updates_oneoff_desk.py`): one named update, one approval.

        UPDATES P3b: `draft_id` — the caller's own draft becomes this update
        (same record, file kept once). `joiners` — rows that match nobody,
        which the person chose to add as new employees for THIS file
        (`updates_joiners.py`): each is judged again here and goes through
        the new-hire path and its approval. Left out (the default), this is
        exactly the call it always was."""
        if kind == 'oneoff':
            return self._oneoff_apply(name, file_b64, filename, columns,
                                      changes, stats, month, draft_id=draft_id)
        joiners = [j for j in (joiners or []) if isinstance(j, dict)]
        if joiners:
            return self._apply_with_joiners(
                name, file_b64, filename, columns, changes, stats,
                start_date, hold_scope, draft_id, joiners)
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
        changes = self._clear_words(desk, changes)
        if not changes:
            return {'ok': False, 'msg': _(
                "There is nothing to apply: no value in this file would change "
                "anything.")}
        cols = self._clean_columns(columns)
        stats = stats if isinstance(stats, dict) else {}

        def count(key):
            try:
                return max(0, int(stats.get(key) or 0))
            except (TypeError, ValueError):
                return 0

        # UPDATES P2b — the server's own rail: a pay item that is not in the
        # person's pay scheme is dropped here too, whatever the browser sent,
        # and the answer says how many.
        changes, skipped = self._drop_off_scheme(desk, changes)
        off_scheme = count('off_scheme') + len(skipped)
        if not changes:
            self._remember_layout(desk, file_b64, filename, cols)
            return {'ok': True, 'apply_id': 0, 'batch_id': 0, 'nothing': True,
                    'written': 0, 'people': 0, 'refused': [], 'pending': False,
                    'skipped_off_scheme': len(skipped), 'off_scheme': off_scheme,
                    'msg': _("Nothing was changed: every value left is for a "
                             "pay item that is not in that person's pay "
                             "scheme.")}
        buckets, refusal = self._split_by_start(desk, changes, start_date,
                                                hold_scope)
        if refusal:
            return {'ok': False, 'msg': refusal}
        if list(buckets) == [None]:
            # No date anywhere: exactly the call Updates has always made.
            answer = desk.apply_changes(0, buckets[None], note=name,
                                        source='import')
            answers = [(None, answer)]
        else:
            answer, answers = self._apply_by_start(desk, buckets, name,
                                                   hold_scope)
            if not answer.get('ok', True):
                return answer
        answer.update(skipped_off_scheme=len(skipped), off_scheme=off_scheme)
        self._remember_layout(desk, file_b64, filename, cols)
        if not answer.get('apply_id'):
            answer.update(batch_id=0, nothing=True, msg=_(
                "Nothing was changed: every value in this file is already on "
                "record, or could not be used."))
            return answer

        batch = self._new_batch({
            'name': name[:200],
            'filename': (filename or '').strip() or False,
            'rows_total': count('rows'),
            'rows_unmatched': count('unmatched'),
            'values_refused': count('left_out') + len(answer.get('refused') or []),
            'values_off_scheme': off_scheme,
        }, file_b64, filename, draft_id)
        # The desk files its applies under sudo; the back-link follows it.
        # UPDATES P3a: one desk answer can carry several parts (lanes).
        apply_ids = []
        for _day, a in answers:
            apply_ids += a.get('apply_ids') or ([a['apply_id']] if a.get('apply_id') else [])
        self.env['pb.records.apply'].sudo().browse(apply_ids).write(
            {'updates_batch_id': batch.id})
        answer['batch_id'] = batch.id
        answer['batch_name'] = batch.name
        return answer

    # =================================================================
    # History and undo
    # =================================================================
    @api.model
    def _batch_state(self, applies):
        """`(state, label)` read off the desk applies, never stored."""
        if not applies:
            return 'applied', _("Applied")
        # The desk's own words for its states, in the reader's language.
        labels = dict(applies._fields['state']._description_selection(self.env))
        # UPDATES P2c — a cancelled part is out of the picture: it changed
        # nothing and never will.
        live = applies.filtered(lambda a: a.state != 'cancelled')
        if not live:
            return 'cancelled', _("Cancelled")
        # UPDATES P2d (P2c report, item 3) — approved, but the change could not
        # be written: say so, with the reason, instead of "Waiting for
        # approval". Display only: the approval engine is unchanged.
        if live.filtered(lambda a: a._blocked_reason()):
            return 'blocked', _("Could not be made")
        if any(a.state == 'pending' for a in live):
            return 'pending', labels.get('pending') or _("Waiting for approval")
        scheduled = live.filtered(lambda a: a.state == 'scheduled')
        done = live.filtered('applied')
        if scheduled:
            when = format_date(self.env, min(scheduled.mapped('start_date')))
            if done.filtered(lambda a: not a.undone):
                return 'mixed', _("Part applied, part scheduled for %s") % when
            return 'scheduled', _("Scheduled for %s") % when
        returned = live.filtered(lambda a: a.state == 'returned')
        if returned and not done:
            reason = (returned[:1].block_note or '').strip()
            return 'returned', (_("Sent back: %s") % reason) if reason \
                else (labels.get('returned') or _("Sent back"))
        if done and all(a.undone for a in done):
            return 'undone', _("Undone")
        if all(a.applied for a in live):
            return 'applied', _("Applied")
        other = live.filtered(lambda a: not a.applied)[:1]
        return other.state, labels.get(other.state) or other.state

    @api.model
    def _batch_row(self, batch, may_write):
        if batch.kind == 'oneoff':
            # UPDATES P2d — a sheet of one-off pay items reads its own rows.
            return self._oneoff_batch_row(batch, may_write)
        applies = batch.apply_ids.sudo()
        state, label = self._batch_state(applies)
        undone = applies.filtered('undone')[:1]
        pending = applies.filtered(lambda a: a.state == 'pending')[:1]
        scheduled = applies.filtered(
            lambda a: a.state == 'scheduled' and not a.applied).sorted(
                lambda a: (a.start_date, a.id))
        cancelled = applies.filtered(lambda a: a.state == 'cancelled')
        returned = applies.filtered(lambda a: a.state == 'returned')
        open_parts = applies.filtered(
            lambda a: not a.applied and a.state in ('pending', 'scheduled'))
        applied = applies.filtered(lambda a: a.applied)
        row = {
            'id': batch.id,
            'name': batch.name or '',
            'user': batch.user_id.display_name or '',
            'date': batch.date and batch.date.strftime('%Y-%m-%d %H:%M:%S') or '',
            'filename': batch.filename or '',
            'file_id': batch.attachment_id.id or 0,
            'people': sum(a.count_people or a.people_count for a in applies),
            'values': sum(a.count_values or a.values_count for a in applies),
            'rows_unmatched': batch.rows_unmatched,
            'values_refused': batch.values_refused,
            'values_off_scheme': batch.values_off_scheme,
            'state': state,
            'state_label': label,
            'with_whom': pending._waiting_for() if pending else '',
            'undone_date': undone.undone_date and undone.undone_date.strftime(
                '%Y-%m-%d %H:%M:%S') or '',
            'undone_by': undone.undone_by_id.display_name or '',
            'can_undo': bool(may_write and applies.filtered(
                lambda a: a.applied and not a.undone)),
        }
        # UPDATES P2c — the parts waiting for their day, the parts stopped,
        # and what a person can still do about them.
        row.update({
            'state_date': fields.Date.to_string(scheduled[:1].start_date)
            if scheduled else '',
            'state_reason': (returned[:1].block_note or '') if state == 'returned'
            else (next((a._blocked_reason() for a in applies if a._blocked_reason()), '')
                  if state == 'blocked' else ''),
            'scheduled': [{
                'apply_id': a.id, 'date': fields.Date.to_string(a.start_date),
                'values': a.values_count, 'people': a.people_count,
            } for a in scheduled],
            # Recorded with their own date: the past ones and the ones the job
            # wrote on the day. One started early is recorded as of that day.
            'recorded': [{
                'date': fields.Date.to_string(a.start_date),
                'values': a.count_values or a.values_count,
            } for a in applied if a.start_date and not a.undone
                and not (a.started_by_id and not a.started_by_job)],
            'started_early': sum(a.count_values or a.values_count for a in applied
                                 if a.started_by_id and not a.started_by_job
                                 and not a.undone),
            'applied_values': sum(a.count_values or a.values_count
                                  for a in applied if not a.undone),
            'cancelled_values': sum(a.values_count for a in cancelled),
            'cancelled_date': cancelled[:1].cancelled_at and cancelled[:1].cancelled_at.strftime(
                '%Y-%m-%d %H:%M:%S') or '',
            'cancelled_by': cancelled[:1].cancelled_by_id.display_name or '',
            'can_cancel': bool(may_write and open_parts.filtered(
                lambda a: a.with_env(self.env)._may_cancel())),
            'can_start': bool(may_write and scheduled),
            # Part of it still waiting (approval or its day): Undo only puts
            # back what was applied, and says so.
            'has_open': bool(open_parts),
            'open_values': sum(a.values_count for a in open_parts),
        })
        if len(applies) > 1:
            # A dated update is several desk applies: count each person once.
            row['people'] = len({int(r.get('emp_id') or 0)
                                 for a in applies for r in a.plan()} - {0})
        if state in ('scheduled', 'mixed', 'cancelled', 'returned'):
            # The scheduled part's people and values, not the whole batch's.
            if state == 'scheduled':
                row['people'] = sum(a.people_count for a in scheduled)
                row['values'] = sum(a.values_count for a in scheduled)
            elif state == 'cancelled':
                row['people'] = sum(a.people_count for a in cancelled)
                row['values'] = sum(a.values_count for a in cancelled)
        return row

    @api.model
    def get_history(self, limit=20):
        desk = self._gate()
        may_write = self._can_write(desk)
        # UPDATES P3b — a draft is never a past update, nor counted as one.
        domain = [('company_id', 'in', self.env.companies.ids),
                  ('state', '!=', 'draft')]
        batches = self.env['pb.updates.batch'].search(
            domain, order='id desc', limit=int(limit or 20))
        total = self.env['pb.updates.batch'].search_count(domain)
        return {'batches': [self._batch_row(b, may_write) for b in batches],
                'total': total}

    @api.model
    def undo(self, batch_id=0):
        """Put a named update back, through the desk's own Undo.

        A value somebody has changed since is kept and counted, never
        overwritten — that is `undo_apply`'s rule and it is not bent here."""
        desk = self._gate()
        try:
            batch_id = int(batch_id or 0)
        except (TypeError, ValueError):
            batch_id = 0
        # A search, not a browse: the record rules answer "not yours" with an
        # empty result instead of an access error.
        batch = self.env['pb.updates.batch'].search(
            [('id', '=', batch_id), ('company_id', 'in', self.env.companies.ids),
             ('state', '!=', 'draft')], limit=1)
        if not batch:
            return {'ok': False, 'msg': _(
                "That update is not on record in the companies you are "
                "working in.")}
        if not self._can_write(desk):
            return {'ok': False, 'msg': _(
                "Undoing an update needs permission to change employee "
                "records. Ask an administrator for the HR or Payroll Officer "
                "role.")}
        applies = batch.apply_ids.sudo()
        todo = applies.filtered(lambda a: a.applied and not a.undone)
        if not todo:
            if applies and all(a.undone for a in applies):
                msg = _("This update has already been undone.")
            elif any(a.state == 'scheduled' for a in applies):
                msg = _("Nothing in this update has been changed yet. Cancel "
                        "the scheduled part instead.")
            elif any(a.state == 'pending' for a in applies):
                msg = _("This update is still waiting for approval, so there "
                        "is nothing to undo yet.")
            else:
                msg = _("Nothing in this update can be undone.")
            return {'ok': False, 'msg': msg}
        restored = changed_since = missing = 0
        for apply_rec in todo:
            res = desk.undo_apply(apply_rec.id)
            if not res.get('ok'):
                continue
            restored += res.get('restored') or 0
            changed_since += res.get('skipped_changed_since') or 0
            missing += res.get('skipped_missing') or 0
        return {'ok': True, 'restored': restored,
                'skipped_changed_since': changed_since,
                'skipped_missing': missing, 'batch_id': batch.id,
                'name': batch.name}
