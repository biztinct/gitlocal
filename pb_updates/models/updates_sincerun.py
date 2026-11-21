# -*- coding: utf-8 -*-
"""UPDATES P3b — "Since the last pay run: N people have changes".

The pay-run preparation workspace (`hr.payroll.preparation._workspace`, the
"Review pay data" worksheet) gains ONE informational key, `since_last_run`,
the way `pb_records/models/records_payrun.py` adds `scheduled_changes` — and
only when there is something to show, so a preparation with nothing to show
answers byte for byte what it answered before (test H14).

For the people in the run, since each person's last FINISHED payslip
(`state='done'`, latest end date; a person never paid → since their first
contract start):

  * written changes — `pb.records.change` of applies that were carried out
    and not undone (an undo is not a change to show), grouped pay / contract
    / bank / personal details, bank values masked to their last 4
    characters;
  * one-off pay items for this run's month, waiting for approval, approved
    or in a pay run;
  * scheduled changes starting on or before the period's last day;
  * pay-item history written by anything else (de-duplicated against the
    first source by person, pay item and date);
  * new employees since the last finished run of this pay scheme.

INFORMATION ONLY: never a blocker, never a figure. Grouped queries only.
"""
import logging
import re
from datetime import timedelta

from odoo import _, fields, models
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

KINDS = ('pay', 'contract', 'bank', 'details', 'oneoff', 'scheduled', 'new')


def _kind_of(field_key):
    key = field_key or ''
    if key.startswith('b:'):
        return 'bank'
    if key.startswith('c:'):
        return 'pay'
    if key.startswith('f:hr.contract:'):
        return 'contract'
    return 'details'


def _mask(text):
    """Bank values to their last 4 characters: "•••• 6655"."""
    raw = re.sub(r'\s+', '', str(text or ''))
    if not raw:
        return ''
    return '•••• %s' % raw[-4:] if len(raw) > 4 else '••••'


class PayrollPreparationSince(models.Model):
    _inherit = 'hr.payroll.preparation'

    def _workspace(self):
        answer = super()._workspace()
        try:
            since = self._updates_since_last_run()
        except Exception:  # noqa: BLE001 — a notice must never break the worksheet
            _logger.exception('pb_updates: since-last-run failed on preparation %s', self.id)
            since = None
        if since:
            answer['since_last_run'] = since
        return answer

    # ------------------------------------------------------------------
    def _since_cutoffs(self, people):
        """`{employee_id: date or None}` — the day after which a change is
        "since the last pay run". None = never paid and no contract: all."""
        Payslip = self.env['hr.payslip'].sudo()
        groups = Payslip._read_group(
            [('employee_id', 'in', people), ('state', '=', 'done')],
            ['employee_id'], ['date_to:max'])
        cut = {emp.id: last for emp, last in groups if last}
        never = [p for p in people if p not in cut]
        first_start = {}
        if never and 'hr.contract' in self.env:
            rows = self.env['hr.contract'].sudo().with_context(active_test=False)._read_group(
                [('employee_id', 'in', never)], ['employee_id'], ['date_start:min'])
            first_start = {emp.id: start for emp, start in rows if start}
        for p in never:
            start = first_start.get(p)
            cut[p] = (start - timedelta(days=1)) if start else None
        return cut, set(never), first_start

    def _updates_since_last_run(self):
        self.ensure_one()
        people = sorted(set(self.employee_ids.ids))
        if not people or not self.date_to:
            return None
        companies = [c for c in {self.company_id.id, self.config_id.company_id.id} if c] \
            or self.env.companies.ids
        cut, never, first_start = self._since_cutoffs(people)
        known = [c for c in cut.values() if c]
        floor = min(known) if known and all(cut.values()) else None
        staff = self.env['hr.employee'].sudo().with_context(active_test=False).browse(people)
        names = {e.id: e.name or '' for e in staff}
        items = {}      # emp_id -> [item]

        def add(emp_id, kind, text, day=None, key=None):
            items.setdefault(emp_id, []).append({
                'kind': kind, 'text': text,
                'date': fields.Date.to_string(day) if day else '', 'key': key})

        def after(emp_id, *days):
            limit = cut.get(emp_id)
            if limit is None:
                return True
            return any(d and d > limit for d in days)

        # 1 — values written by Records and Updates.
        seen_pay = set()
        if 'pb.records.change' in self.env:
            domain = [('employee_id', 'in', people), ('apply_id.applied', '=', True),
                      ('apply_id.undone', '=', False), ('apply_id.source', '!=', 'undo'),
                      ('apply_id.company_id', 'in', companies)]
            if floor:
                domain += ['|', ('effective_date', '>', floor),
                           ('create_date', '>', fields.Datetime.to_string(floor))]
            Change = self.env['pb.records.change'].sudo()
            rows = Change.search_read(domain, [
                'employee_id', 'field_key', 'field_label', 'old_label', 'new_label',
                'effective_date', 'create_date', 'apply_id'], load=False)
            applies = {a['id']: a for a in self.env['pb.records.apply'].sudo().browse(
                {r['apply_id'] for r in rows}).read(['user_id'])} if rows else {}
            users = {}
            for a in applies.values():
                if a.get('user_id'):
                    users[a['id']] = a['user_id'][1]
            for r in rows:
                emp_id = r['employee_id']
                made = r['create_date'].date() if r.get('create_date') else None
                if not after(emp_id, r.get('effective_date'), made):
                    continue
                kind = _kind_of(r['field_key'])
                old, new = r.get('old_label') or '', r.get('new_label') or ''
                if r['field_key'] == 'b:acc_number':
                    old, new = _mask(old), _mask(new)
                day = r.get('effective_date') or made
                who = users.get(r['apply_id']) or ''
                text = _("%(label)s: %(old)s → %(new)s, %(date)s") % {
                    'label': r.get('field_label') or '', 'old': old or _("empty"),
                    'new': new or _("empty"), 'date': format_date(self.env, day)}
                if who:
                    text = _("%(text)s, by %(who)s") % {'text': text, 'who': who}
                add(emp_id, kind, text, day)
                if kind == 'pay':
                    seen_pay.add((emp_id, r['field_key'][2:], day))
                    seen_pay.add((emp_id, r['field_key'][2:], made))

        # 2 — one-off pay items for this run's month.
        if 'pb.updates.oneoff' in self.env:
            Oneoff = self.env['pb.updates.oneoff'].sudo()
            month = Oneoff._month_of(self.date_to)
            labels = dict(Oneoff._fields['state']._description_selection(self.env))
            for row in Oneoff.search([
                    ('employee_id', 'in', people), ('period_month', '=', month),
                    ('action', '=', 'set'), ('company_id', 'in', companies),
                    ('state', 'in', ('pending', 'approved', 'reserved'))]):
                add(row.employee_id.id, 'oneoff', _("%(item)s %(amount)s for %(month)s · %(state)s") % {
                    'item': row.label or row.code, 'amount': row._amount_label(),
                    'month': Oneoff._month_label(month),
                    'state': labels.get(row.state, row.state)})

        # 3 — scheduled changes starting inside (or before the end of) the period.
        if 'pb.records.apply' in self.env:
            wanted = set(people)
            for rec in self.env['pb.records.apply'].sudo().search([
                    ('state', '=', 'scheduled'), ('applied', '=', False),
                    ('start_date', '!=', False), ('start_date', '<=', self.date_to),
                    ('company_id', 'in', companies)], order='start_date, id'):
                for row in rec.plan():
                    try:
                        emp_id = int(row.get('emp_id') or 0)
                    except (TypeError, ValueError):
                        continue
                    if emp_id not in wanted:
                        continue
                    new = row.get('new_label') or ''
                    if row.get('field_id') == 'b:acc_number':
                        new = _mask(new)
                    add(emp_id, 'scheduled', _(
                        "%(label)s becomes %(new)s on %(date)s. Scheduled: not in "
                        "this pay run unless it is started now.") % {
                            'label': row.get('field_label') or '', 'new': new or _("empty"),
                            'date': format_date(self.env, rec.start_date)}, rec.start_date)

        # 4 — pay items changed on the contract by anything else. A Records
        # or Updates write logs a line here too (and so does its undo), so
        # every pay item those wrote — undone or not — is left out by person,
        # code and date: an undone change never comes back through here.
        if 'pb.records.change' in self.env:
            domain = [('employee_id', 'in', people), ('field_key', '=like', 'c:%')]
            if floor:
                domain += ['|', ('effective_date', '>', floor),
                           ('create_date', '>', fields.Datetime.to_string(floor))]
            for r in self.env['pb.records.change'].sudo().search_read(
                    domain, ['employee_id', 'field_key', 'effective_date', 'create_date'],
                    load=False):
                code = r['field_key'][2:]
                seen_pay.add((r['employee_id'], code, r.get('effective_date')))
                if r.get('create_date'):
                    seen_pay.add((r['employee_id'], code, r['create_date'].date()))
        if 'hr.contract.advantage.change' in self.env:
            domain = [('employee_id', 'in', people),
                      ('change_source', '!=', 'checked')]
            if floor:
                domain += ['|', ('effective_date', '>', floor),
                           ('changed_at', '>', fields.Datetime.to_string(floor))]
            for row in self.env['hr.contract.advantage.change'].sudo().search(domain):
                emp_id = row.employee_id.id
                made = row.changed_at.date() if row.changed_at else None
                if not after(emp_id, row.effective_date, made):
                    continue
                code = row.advantage_template_code or ''
                if (emp_id, code, row.effective_date) in seen_pay or \
                        (emp_id, code, made) in seen_pay:
                    continue
                text_kind = bool(row.old_text_value or row.new_text_value)
                old = row.old_text_value if text_kind else row.old_amount
                new = row.new_text_value if text_kind else row.new_amount
                if old == new:
                    continue
                fmt = (lambda v: '{:,.2f}'.format(v).rstrip('0').rstrip('.')) \
                    if not text_kind else (lambda v: v or '')
                add(emp_id, 'pay', _("%(item)s: %(old)s → %(new)s, %(date)s (changed on "
                                     "the contract)") % {
                    'item': row.advantage_template_id.name or code,
                    'old': fmt(old) or _("empty"), 'new': fmt(new) or _("empty"),
                    'date': format_date(self.env, row.effective_date)}, row.effective_date)

        # 5 — new employees since this scheme's last finished run.
        Payslip = self.env['hr.payslip'].sudo()
        if 'formula_config_id' in Payslip._fields and never:
            last = Payslip._read_group(
                [('formula_config_id', '=', self.config_id.id), ('state', '=', 'done')],
                [], ['date_to:max'])
            last_run = last[0][0] if last and last[0] else None
            if last_run:
                created = {e.id: e.create_date.date() for e in staff
                           if e.id in never and e.create_date}
                for emp_id in never:
                    start = first_start.get(emp_id)
                    if (start and start > last_run) or (created.get(emp_id) and created[emp_id] > last_run):
                        add(emp_id, 'new', _("New: %(name)s, starts %(date)s") % {
                            'name': names.get(emp_id, ''),
                            'date': format_date(self.env, start) if start else _("date not set")},
                            start)
        if not items:
            return None
        counts = {k: 0 for k in KINDS}
        out = []
        for emp_id in sorted(items, key=lambda e: (names.get(e, '').lower(), e)):
            rows = sorted(items[emp_id], key=lambda i: (KINDS.index(i['kind']), i['date']))
            kinds = []
            for i in rows:
                i.pop('key', None)
                if i['kind'] not in kinds:
                    kinds.append(i['kind'])
            for k in kinds:
                counts[k] += 1
            out.append({'employee_id': emp_id, 'name': names.get(emp_id, ''),
                        'kinds': kinds, 'items': rows})
        words = {'pay': _("pay"), 'contract': _("contract"), 'bank': _("bank"),
                 'details': _("personal details"), 'oneoff': _("one-off"),
                 'scheduled': _("scheduled"), 'new': _("new")}
        parts = ', '.join(_("%(n)s %(what)s") % {'n': counts[k], 'what': words[k]}
                          for k in KINDS if counts[k])
        n = len(out)
        line = _("Since the last pay run: 1 person has changes (%s)") % parts if n == 1 else \
            _("Since the last pay run: %(n)s people have changes (%(parts)s)") % {
                'n': n, 'parts': parts}
        return {'line': line, 'people_count': n, 'counts': counts, 'people': out,
                'kinds': [{'key': k, 'label': words[k], 'count': counts[k]}
                          for k in KINDS if counts[k]]}
