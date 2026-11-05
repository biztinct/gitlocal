# -*- coding: utf-8 -*-
"""MANAGERCOL — the pay data file keeps managers up to date.

Owner ruling 2026-11-05: Rize's pay data file carries a "Reporting Manager"
column ("Master Reporting Manager" in the Indonesia and Singapore files) and
THE FILE WINS each import: every import sets the manager (`parent_id`) where
the name resolves cleanly and lists the rows it could not match
(docs/handovers/orgchart/MANAGERCOL_HANDOVER.md).

How it works
------------
* **The mapping is the contract.** The column is read only when the batch's
  scheme maps it to `hr.employee.parent_id` (`hr.payslip.import.mapping`,
  destination "field"). No mapping → this step does nothing at all; no
  heading is guessed at write time.
* **A dedicated step, not the generic one.** The generic writeback resolves a
  many2one with `=ilike … limit=1` (the FIRST of two "Nithya"s), is not
  accent-insensitive ("Ho Huu Du" ≠ "Hồ Hữu Dư"), CREATES a record it cannot
  find (`m2o_creates_missing` is true for hr.employee — an employee called
  "Board" would be born), and writes through `employee.write`, which drags the
  coach and both approvers with the manager (ORGCHART_LEDGER G16). So the
  generic path is told to skip the manager mapping (`_get_mapping_updates`)
  and this module does it instead, through `pb.orgchart._set_managers`.
* **Matching = the seed's matching** (`tools/seed_rize_managers_from_payfile.py`,
  RIZE_MANAGERS_SEED_REPORT.md), so the one-off seed and every later import
  agree: accent-insensitive, in three tiers — full name, the same words in
  another order, a short name whose every word is inside the person's name —
  the first tier that finds anyone (active or not) decides. Written only when
  that tier holds exactly ONE current employee and nobody who has left
  ("Shreya": one current, one left → not written). Two or more current people
  → the file's own manager-email column settles it, if the file's emails can
  be trusted (below). A short or reordered name must not contradict that email
  either. Nothing by name → an employee code, if the cell is one.
* **When the email column is trusted.** The seed never trusted Vietnam's
  (one address beside five different names). The ongoing path asks the FILE
  instead of the country: the emails are trusted unless one address sits
  beside two names that cannot be the same person (no word in common:
  du.ho@ beside "Ho Huu Du" and "Le Hong Phong"; a typo such as "Dhruv
  Swhney" / "Dhruv Sawhney" does not count). Same answers as the seed on all four rize files
  (MANAGERCOL_REPORT.md §3), and a cleaner Vietnam file would earn trust.
* **Never**: clear a manager from a blank cell, set a loop (`_loop_in`), pick
  someone who has left or works for a company outside the batch's, make a
  person their own manager, or fail the row — the step has its own savepoint
  and try/except, and a failure is a note on the row.
* **Unchanged → no write**, so a re-import writes no history at all.

What the importer sees: every row the step looked at carries
`pb_manager_state` and, when it was not set, a one-sentence
`pb_manager_note`; `_pb_manager_summary()` turns them into the line
"Managers from the file: 3 updated · 115 already up to date · 4 not matched"
with the rows behind a fold-out, on the import's last step and on the batch
page (pb_import_wizard / pb_import_batch payloads, extended below).
"""
import json
import logging
import re
import unicodedata

from odoo import api, fields, models

from odoo.addons.pb_hr_payroll_formula.models.column_role_classifier import (
    is_manager_email_header, is_manager_header)

_logger = logging.getLogger(__name__)

MANAGER_FIELD = 'parent_id'
_NON_WORD = re.compile(r'[^a-z0-9]+')


def norm_name(text):
    """The seed's `norm`: đ→d, accents off, lower case, punctuation → space,
    whitespace collapsed. "Hồ Hữu Dư" → "ho huu du"."""
    s = (str(text or '')).replace('đ', 'd').replace('Đ', 'D')
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return ' '.join(_NON_WORD.sub(' ', s).split())


def _could_be_one_person(a, b):
    """Two normalised names that could be one person share at least one word:
    "monica" / "monica bhojwani", and a typo — "dhruv swhney" / "dhruv sawhney"
    (rize India). "ho huu du" / "le hong phong" share none (rize Vietnam)."""
    return bool(set(a.split()) & set(b.split()))


class HrPayrollImportLine(models.Model):
    _inherit = 'hr.payroll.import.line'

    pb_manager_state = fields.Selection([
        ('set', 'Updated'),
        ('same', 'Already up to date'),
        ('unmatched', 'Not matched'),
        ('blank', 'Left blank'),
    ], string='Manager from the file', readonly=True, copy=False,
        help="What the import did with this row's manager column.")
    pb_manager_note = fields.Char(
        string='Manager note', readonly=True, copy=False,
        help="Why the manager in this row was not set, in plain words.")


class HrPayrollImportBatch(models.Model):
    _inherit = 'hr.payroll.import.batch'

    pb_manager_set_count = fields.Integer(
        string='Managers updated', compute='_compute_pb_manager_counts')
    pb_manager_same_count = fields.Integer(
        string='Managers already up to date', compute='_compute_pb_manager_counts')
    pb_manager_unmatched_count = fields.Integer(
        string='Managers not matched', compute='_compute_pb_manager_counts')
    pb_manager_blank_count = fields.Integer(
        string='Manager cells left blank', compute='_compute_pb_manager_counts')

    @api.depends('import_line_ids.pb_manager_state')
    def _compute_pb_manager_counts(self):
        for batch in self:
            counts = {'set': 0, 'same': 0, 'unmatched': 0, 'blank': 0}
            for st in batch.import_line_ids.mapped('pb_manager_state'):
                if st in counts:
                    counts[st] += 1
            batch.pb_manager_set_count = counts['set']
            batch.pb_manager_same_count = counts['same']
            batch.pb_manager_unmatched_count = counts['unmatched']
            batch.pb_manager_blank_count = counts['blank']

    # ================================================================ seam
    def _pb_manager_mapping(self):
        """The scheme's mapping onto the manager field, or an empty recordset.
        Lowest id wins, the tie-break `_get_component_mapping_index` uses."""
        self.ensure_one()
        if not self.formula_config_id:
            return self.env['hr.payslip.import.mapping']
        return self.env['hr.payslip.import.mapping'].sudo().search([
            ('salary_structure_id', '=', self.formula_config_id.id),
            ('destination_type', '=', 'field'),
            ('target_model_id.model', '=', 'hr.employee'),
            ('target_field_id.name', '=', MANAGER_FIELD),
            ('component_id', '!=', False),
        ], order='id asc', limit=1)

    def _get_mapping_updates(self, record, raw_data, mappings=None, line=None,
                             contract=None, employee=None):
        """The generic writeback skips the manager mapping; `_sync_employee_manager`
        owns it. Filtered BEFORE the generic resolver runs, not after: that
        resolver would search `=ilike … limit=1` and CREATE an employee it
        cannot find. An empty remainder must not reach `super()`, whose
        `mappings or …` would fetch them all again."""
        if record._name == 'hr.employee':
            mappings = mappings or self._get_model_mappings(record._name)
            kept = mappings.filtered(
                lambda m: m.target_field_id.name != MANAGER_FIELD)
            if not kept:
                return {}
            mappings = kept
        return super()._get_mapping_updates(
            record, raw_data, mappings=mappings, line=line, contract=contract,
            employee=employee)

    def _update_employee_from_raw_data(self, employee, raw_data, line=None):
        """Right after the employee's own columns, the manager — on every path
        that updates the employee (a matched person, and a new starter, whose
        `_create_employee` calls this too). A one-time file never reaches
        here, so it changes no manager either (RECORDS R1)."""
        res = super()._update_employee_from_raw_data(employee, raw_data, line=line)
        self._pb_manager_step(employee, raw_data, line)
        return res

    def _pb_manager_step(self, employee, raw_data, line):
        """Run `_sync_employee_manager` so that nothing it does can fail the row."""
        if not employee or len(self) != 1:
            return
        state, note = False, False
        try:
            with self.env.cr.savepoint():
                state, note = self._sync_employee_manager(employee, raw_data, line)
        except Exception:      # noqa: BLE001 — a manager never fails a pay row
            self.env.invalidate_all()
            _logger.exception(
                "Manager step failed for batch %s line %s (employee %s); the row "
                "carries on.", self.id, line.id if line else False, employee.id)
            state = 'unmatched'
            note = self.env._("Manager not set: the change could not be saved.")
        if line and state:
            vals = {'pb_manager_state': state, 'pb_manager_note': note or False}
            if line.pb_manager_state != vals['pb_manager_state'] \
                    or (line.pb_manager_note or False) != vals['pb_manager_note']:
                line.write(vals)

    # ================================================================ step
    def _sync_employee_manager(self, employee, raw_data, line=None):
        """Set `employee`'s manager from this row. Returns `(state, note)`:
        state False (no mapping — nothing to say), 'set', 'same', 'blank' or
        'unmatched' with a plain sentence."""
        self.ensure_one()
        _ = self.env._
        mapping = self._pb_manager_mapping()
        if not mapping:
            return False, False
        if not employee.active:
            # Someone who has left is off the chart; the seed skipped them too.
            return False, False
        value, has_value = self._writeback_raw_value(
            raw_data, mapping.component_id, mapping=mapping, line=line,
            employee=employee, allow_column_letter=False)
        text = ' '.join(str(value).split()) if has_value and value is not None else ''
        if not text or not norm_name(text):
            return 'blank', _("Manager cell is empty — the current manager is kept.")

        mgr, note = self._pb_manager_resolve(text, raw_data, employee, line=line)
        if not mgr:
            return 'unmatched', note
        if mgr.id == employee.id:
            return 'unmatched', _("Manager not set: “%(v)s” is this person.", v=text)
        if mgr.company_id and employee.company_id and mgr.company_id != employee.company_id:
            return 'unmatched', _(
                "Manager not set: %(m)s works for %(c)s — a manager must be in the same company.",
                m=mgr.name, c=mgr.company_id.name)
        if employee.parent_id.id == mgr.id:
            return 'same', False
        Org = self.env['pb.orgchart']
        if Org._loop_in({employee.id: mgr.id}):
            return 'unmatched', _(
                "Manager not set: %(m)s is inside %(p)s's own team.",
                m=mgr.name, p=employee.name)
        # `_set_managers` writes the manager and nothing else: coach and both
        # approvers are written back with their own value in the same write
        # (ledger rule 12 / G16). As the importing user, so the employee's
        # history names them.
        Org._set_managers({employee.id: mgr.id})
        return 'set', False

    # ============================================================ matching
    def _pb_manager_companies(self):
        """The companies a manager may be found in: the batch's and the ones
        the importing user has switched on."""
        ids = set(self.env.companies.ids) | set(self.company_id.ids)
        return sorted(ids)

    def _pb_manager_index(self):
        """Every employee of the allowed companies, active or not, with the
        normalised name, its word set, emails and code. Built once per batch
        per transaction (`cr.cache`) and rebuilt only when someone was added —
        a new starter created by an earlier row of the same file can be a
        later row's manager."""
        Emp = self.env['hr.employee']
        Emp.flush_model(['name', 'active', 'company_id'])
        self.env.cr.execute("SELECT max(id), count(*) FROM hr_employee")
        stamp = tuple(self.env.cr.fetchone())
        comps = tuple(self._pb_manager_companies())
        key = ('pb_orgchart.manager_index', self.id, comps, stamp)
        cache = self.env.cr.cache
        if key in cache:
            return cache[key]
        for old in [k for k in cache if isinstance(k, tuple) and k[:2] == key[:2]]:
            cache.pop(old, None)
        fnames = ['name', 'active', 'company_id', 'work_email']
        for f in ('private_email', 'employee_id'):
            if f in Emp._fields:
                fnames.append(f)
        rows = Emp.sudo().with_context(active_test=False).search_read(
            ['|', ('company_id', 'in', list(comps)), ('company_id', '=', False)], fnames)
        index = []
        for r in rows:
            n = norm_name(r['name'])
            if not n:
                continue
            index.append({
                'id': r['id'], 'name': r['name'], 'norm': n, 'words': frozenset(n.split()),
                'active': bool(r['active']),
                'mails': {m.strip().lower() for m in (r.get('work_email'), r.get('private_email'))
                          if m and isinstance(m, str)},
                'code': (str(r.get('employee_id') or '')).strip().lower(),
            })
        cache[key] = index
        return index

    def _pb_manager_mail_trusted(self, mapping):
        """Can this FILE's manager-email column settle a tie? Not when one
        address sits beside two names that cannot be one person (Rize
        Vietnam: du.ho@ beside five names). Judged once per batch."""
        key = ('pb_orgchart.manager_mail_trust', self.id, mapping.id)
        cache = self.env.cr.cache
        if key in cache:
            return cache[key]
        seen = {}
        trusted = True
        for ln in self.import_line_ids:
            raw = ln.get_raw_data()
            mail = self._pb_manager_mail(raw)
            if not mail:
                continue
            value, has = self._get_rule_raw_value(
                raw, mapping.component_id, allow_column_letter=False)
            n = norm_name(value) if has else ''
            if not n:
                continue
            names = seen.setdefault(mail, set())
            if any(not _could_be_one_person(n, other) for other in names):
                trusted = False
                break
            names.add(n)
        cache[key] = trusted
        return trusted

    @staticmethod
    def _pb_manager_mail(raw_data):
        """The row's manager email, from a column whose heading says so."""
        for k, v in (raw_data or {}).items():
            if v in (None, '') or not isinstance(k, str):
                continue
            if is_manager_email_header(k):
                m = str(v).strip().lower()
                if '@' in m:
                    return m
        return ''

    @staticmethod
    def _pb_manager_find(index, text):
        """(current people, people who have left, tier) at the first tier that
        finds anyone — the seed's `find`, unchanged."""
        n = norm_name(text)
        ws = set(n.split())
        tiers = [('full', lambda p: p['norm'] == n),
                 ('reordered', lambda p: p['words'] == ws)]
        if ws and max(len(x) for x in ws) >= 3:
            tiers.append(('short', lambda p: ws <= p['words']))
        for how, ok in tiers:
            hit = [p for p in index if ok(p)]
            if hit:
                return ([p for p in hit if p['active']],
                        [p for p in hit if not p['active']], how)
        return [], [], ''

    def _pb_manager_resolve(self, text, raw_data, employee, line=None):
        """(hr.employee or None, note) for one manager cell."""
        _ = self.env._
        Emp = self.env['hr.employee']
        mapping = self._pb_manager_mapping()
        index = self._pb_manager_index()
        mail = self._pb_manager_mail(raw_data)
        trusted = bool(mail) and self._pb_manager_mail_trusted(mapping)
        cands, gone, how = self._pb_manager_find(index, text)

        if len(cands) == 1 and not gone:
            pick = cands[0]
            # A short or reordered name must not contradict the file's own
            # manager email (when the file's emails can be trusted at all).
            if how != 'full' and trusted and pick['mails'] and mail not in pick['mails']:
                return None, _(
                    "Manager not set: “%(v)s” fits %(m)s, but the manager email in the file is %(e)s.",
                    v=text, m=pick['name'], e=mail)
            return Emp.browse(pick['id']), False
        if cands:
            if trusted and not gone:
                hit = [p for p in cands if mail in p['mails']]
                if len(hit) == 1:
                    return Emp.browse(hit[0]['id']), False
            total = len(cands) + len(gone)
            if gone:
                return None, _(
                    "Manager not set: “%(v)s” fits %(n)s people, and %(g)s of them has left.",
                    v=text, n=total, g=len(gone))
            return None, _("Manager not set: “%(v)s” fits %(n)s people.", v=text, n=total)
        if gone:
            return None, _("Manager not set: %(m)s has left.", m=gone[0]['name'])
        # Nothing by name: the cell may be an employee code.
        code = text.strip().lower()
        if code:
            hit = [p for p in index if p['active'] and p['code'] and p['code'] == code]
            if len(hit) == 1:
                return Emp.browse(hit[0]['id']), False
            if len(hit) > 1:
                return None, _("Manager not set: the code “%(v)s” fits %(n)s people.",
                               v=text, n=len(hit))
        return None, _("Manager not set: nobody is called “%(v)s”.", v=text)

    # ============================================================= screens
    def _pb_manager_summary(self):
        """The manager line for the import's last step and the batch page.
        Every word comes from here (translated once, server-side), so the two
        screens only lay it out. `{'show': False}` when there is nothing to say."""
        self.ensure_one()
        _ = self.env._
        out = {'show': False}
        mapping = self._pb_manager_mapping()
        if not mapping:
            header = self._pb_manager_unmapped_header()
            if header:
                out.update({
                    'show': True, 'title': _("Managers from the file"), 'chips': [],
                    'rows': [], 'tone': '',
                    'hint': _(
                        "This file has a “%(h)s” column, but this scheme does not read it, "
                        "so no manager was changed. Map the column to Manager to keep "
                        "managers up to date.", h=header),
                })
            return out
        lines = self.import_line_ids
        looked = lines.filtered('pb_manager_state')
        if not looked:
            return out
        n_set, n_same = self.pb_manager_set_count, self.pb_manager_same_count
        n_un, n_blank = self.pb_manager_unmatched_count, self.pb_manager_blank_count
        chips = [
            {'key': 'set', 'n': n_set, 'label': _("updated"), 'tone': 'green' if n_set else ''},
            {'key': 'same', 'n': n_same, 'label': _("already up to date"), 'tone': ''},
            {'key': 'unmatched', 'n': n_un, 'label': _("not matched"), 'tone': 'amber' if n_un else ''},
        ]
        if n_blank:
            chips.append({'key': 'blank', 'n': n_blank, 'label': _("left blank"), 'tone': ''})
        rows = []
        for ln in looked.filtered(lambda l: l.pb_manager_state in ('unmatched', 'blank')).sorted(
                lambda l: (l.pb_manager_state != 'unmatched', l.sequence, l.id)):
            rows.append({
                'id': ln.id,
                'name': ln.employee_id.name or ln.employee_name or '—',
                'code': ln.employee_code or '',
                'note': ln.pb_manager_note or '',
                'state': ln.pb_manager_state,
            })
        out.update({
            'show': True, 'title': _("Managers from the file"), 'chips': chips,
            'tone': 'amber' if n_un else '', 'hint': '',
            'rows': rows,
            'toggle': (_("See the row") if len(rows) == 1
                       else _("See the %(n)s rows", n=len(rows))) if rows else '',
        })
        return out

    def _pb_manager_unmapped_header(self):
        """A manager heading this file carries while the scheme reads none —
        so the importer is told rather than left to wonder. First row only."""
        line = self.import_line_ids[:1]
        if not line:
            return ''
        for k in line.get_raw_data():
            if isinstance(k, str) and is_manager_header(k):
                return k.rsplit('|', 1)[-1].strip()
        return ''


class PbImportWizard(models.AbstractModel):
    _inherit = 'pb.import.wizard'

    @api.model
    def get_summary(self, batch_id):
        res = super().get_summary(batch_id)
        if isinstance(res, dict) and res.get('batch_id'):
            res['managers'] = _manager_payload(self.env, res['batch_id'])
        return res


class PbImportBatchCockpit(models.AbstractModel):
    _inherit = 'pb.import.batch.cockpit'

    @api.model
    def get_batch_detail(self, batch_id):
        res = super().get_batch_detail(batch_id)
        if isinstance(res, dict) and res.get('batch_id'):
            res['managers'] = _manager_payload(self.env, res['batch_id'])
        return res


def _manager_payload(env, batch_id):
    """A read never fails the screen it rides on."""
    try:
        batch = env['hr.payroll.import.batch'].browse(int(batch_id)).exists()
        return batch._pb_manager_summary() if batch else {'show': False}
    except Exception:      # noqa: BLE001
        _logger.debug("Manager summary failed for batch %s", batch_id, exc_info=True)
        return {'show': False}
