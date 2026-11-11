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

from odoo.addons.pb_records.models.pb_records_io import _norm, XLSX_MIME
from odoo.addons.pb_updates.models.updates_batch import heading_fingerprint

try:  # WHITELABEL — the tenant's own name for the product
    from odoo.addons.biz_debrand.models.brand import product_label
except Exception:  # pragma: no cover — biz_debrand absent on this build
    def product_label(env, default='Payobook'):
        return default

_logger = logging.getLogger(__name__)

EMP = 'hr.employee'
CON = 'hr.contract'

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
        return self.env['pb.records.desk']

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

        used = {}
        for key, value in (columns.get('used') or {}).items():
            idx = as_int(key)
            if idx > 0 and value:
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
        return {'used': used, 'identity': identity, 'heads': heads}

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
        }

    @api.model
    def download_sheet(self, topic_keys=None, filters=None):
        """The desk's own export, for the fields of the picked topics."""
        desk = self._gate()
        if not desk._may_export():
            return {'ok': False, 'msg': _(
                "Downloading a sheet needs permission to export employee "
                "records. Ask an administrator, or upload a file of your own.")}
        topics, _by_id, _data = self._catalogue(desk)
        keys = set(topic_keys or [])
        field_ids = [fid for t in topics if t['key'] in keys
                     for fid in t['field_ids']]
        if not field_ids:
            return {'ok': False, 'msg': _(
                "Pick at least one topic first, so the sheet has columns to "
                "fill in.")}
        answer = desk.export_records(0, filters or {}, field_ids, 'data')
        if answer.get('ok'):
            # The desk names its files after a pay scheme; this one is not
            # tied to any, so it gets a name a person recognises in Downloads.
            answer['filename'] = _("%(product)s update sheet %(date)s.xlsx") % {
                'product': product_label(self.env),
                'date': fields.Date.context_today(self).isoformat()}
        return answer

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
    def read_columns(self, file_b64='', filename=''):
        """What each column of the file is, and where it most likely goes.

        Placement, best first: the desk's own (a Payobook sheet's hidden ids,
        its identity headings, a heading equal to a field's name); then this
        company's remembered matchings (the exact set of headings first, then
        any matching that knows the heading); then a careful guess. A card a
        memory or a guess points at that is no longer in the catalogue is
        dropped. The same field is never offered to two columns."""
        desk = self._gate()
        res = desk.import_columns(0, file_b64, filename)
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
        layouts = Layout.search([('company_id', '=', self.env.company.id)],
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
            guess = self._guess(head, by_id, taken)
            if guess:
                taken.add(guess)
                col.update(how='guess', field_id=guess, target=guess)

        placed_by_id = [c for c in columns if c['how'] == 'id']
        from_sheet = bool(placed_by_id) and all(
            c['how'] in ('id', 'identity') for c in columns)
        return {
            'ok': True, 'filename': res.get('filename'), 'rows': res['rows'],
            'truncated': bool(res.get('truncated')), 'columns': columns,
            'fields': topics, 'layout_known': bool(exact),
            'from_sheet': from_sheet,
        }

    # =================================================================
    # Review
    # =================================================================
    @api.model
    def review(self, file_b64='', filename='', columns=None):
        """The peek, as a person × column grid in the file's own row order.

        Writes nothing. A matched row's cell that has no value in the file is
        simply absent. When the same person is in the file twice the desk
        would write both values in file order, so the LOWER row's value is the
        one that stays; the earlier cell is shown as overridden and is not sent
        back, which leaves the result exactly what the desk would have made."""
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
        peek = desk.import_peek(
            0, file_b64, filename,
            columns={'used': {str(k): v for k, v in cols['used'].items()},
                     'identity': cols['identity']})
        if not peek.get('ok'):
            return peek
        _topics, by_id, _data = self._catalogue(desk)
        seen, out_columns = set(), []
        for idx in sorted(cols['used']):
            fid = cols['used'][idx]
            if fid in seen or fid not in by_id or idx in cols['identity'].values():
                continue
            seen.add(fid)
            out_columns.append({'field_id': fid, 'label': by_id[fid]['label'],
                                'group': by_id[fid]['group'], 'idx': idx,
                                'head': cols['heads'].get(idx, '')})
        base = {
            'ok': True, 'filename': peek.get('filename') or filename,
            'summary': peek.get('summary') or {},
            'identity': peek.get('identity') or '',
            'truncated': bool(peek.get('truncated')),
            'columns': out_columns,
        }
        if peek.get('empty'):
            base.update(empty=True, msg=peek.get('msg'), rows=[], unmatched=[],
                        changes=[])
            return base

        matched = peek.get('matched') or []
        changes = peek.get('changes') or []
        info = self._people_info(desk, {m['emp_id'] for m in matched})

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
            cells = {}
            for change in sliced[pos]:
                key = (change['emp_id'], change['field_id'])
                queue = queues.get(key) or []
                is_last = last_row.get(key) == pos
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
                if status == 'ok':
                    ok_changes.append({'emp_id': m['emp_id'],
                                       'field_id': change['field_id'],
                                       'value': value})
            rows.append({
                'row': m['row'], 'emp_id': m['emp_id'], 'method': m.get('method'),
                'name': person.get('name') or '', 'code': person.get('code') or '',
                'department': person.get('department') or '',
                'twice': emp_rows.get(m['emp_id'], 0) > 1,
                'cells': cells,
            })
        base.update(rows=rows, unmatched=peek.get('unmatched') or [],
                    changes=ok_changes)
        return base

    @api.model
    def recheck(self, changes=None):
        """After an on-screen fix or a row bound by hand: the desk's verdict."""
        desk = self._gate()
        return desk.preview_changes(0, changes or [])

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
            elif idx in cols['used']:
                target = cols['used'][idx]
            else:
                target = 'ignore'
            pairs.append((heads[idx], target))
        return self.env['pb.updates.layout'].remember(pairs)

    @api.model
    def apply(self, name='', file_b64='', filename='', columns=None,
              changes=None, stats=None):
        """Name the update, keep the file, and hand the changes to the desk.

        One transaction. The desk re-evaluates every change (whitelist, company
        scope, permissions, audit, approval route) — nothing here decides what
        is written. When the desk finds nothing to change, no batch is left
        behind and the answer says so."""
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
        changes = [c for c in (changes or []) if isinstance(c, dict)]
        if not changes:
            return {'ok': False, 'msg': _(
                "There is nothing to apply: no value in this file would change "
                "anything.")}
        cols = self._clean_columns(columns)
        answer = desk.apply_changes(0, changes, note=name, source='import')
        self._remember_layout(desk, file_b64, filename, cols)
        if not answer.get('apply_id'):
            answer.update(batch_id=0, nothing=True, msg=_(
                "Nothing was changed: every value in this file is already on "
                "record, or could not be used."))
            return answer

        stats = stats if isinstance(stats, dict) else {}

        def count(key):
            try:
                return max(0, int(stats.get(key) or 0))
            except (TypeError, ValueError):
                return 0

        batch = self.env['pb.updates.batch'].create({
            'name': name[:200],
            'filename': (filename or '').strip() or False,
            'rows_total': count('rows'),
            'rows_unmatched': count('unmatched'),
            'values_refused': count('left_out') + len(answer.get('refused') or []),
        })
        if file_b64:
            attachment = self.env['ir.attachment'].create({
                'name': (filename or '').strip() or _("Update file"),
                'datas': file_b64,
                'res_model': 'pb.updates.batch',
                'res_id': batch.id,
                'mimetype': 'text/csv' if (filename or '').lower().endswith('.csv')
                else XLSX_MIME,
            })
            batch.attachment_id = attachment
        # The desk files its applies under sudo; the back-link follows it.
        self.env['pb.records.apply'].sudo().browse(answer['apply_id']).write(
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
        if any(a.state == 'pending' for a in applies):
            return 'pending', labels.get('pending') or _("Waiting for approval")
        if all(a.undone for a in applies):
            return 'undone', _("Undone")
        if all(a.applied for a in applies):
            return 'applied', _("Applied")
        other = applies.filtered(lambda a: not a.applied)[:1]
        return other.state, labels.get(other.state) or other.state

    @api.model
    def _batch_row(self, batch, may_write):
        applies = batch.apply_ids.sudo()
        state, label = self._batch_state(applies)
        undone = applies.filtered('undone')[:1]
        pending = applies.filtered(lambda a: a.state == 'pending')[:1]
        return {
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
            'state': state,
            'state_label': label,
            'with_whom': pending._waiting_for() if pending else '',
            'undone_date': undone.undone_date and undone.undone_date.strftime(
                '%Y-%m-%d %H:%M:%S') or '',
            'undone_by': undone.undone_by_id.display_name or '',
            'can_undo': bool(may_write and applies.filtered(
                lambda a: a.applied and not a.undone)),
        }

    @api.model
    def get_history(self, limit=20):
        desk = self._gate()
        may_write = self._can_write(desk)
        batches = self.env['pb.updates.batch'].search(
            [('company_id', 'in', self.env.companies.ids)],
            order='id desc', limit=int(limit or 20))
        total = self.env['pb.updates.batch'].search_count(
            [('company_id', 'in', self.env.companies.ids)])
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
            [('id', '=', batch_id), ('company_id', 'in', self.env.companies.ids)],
            limit=1)
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
