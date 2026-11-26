# -*- coding: utf-8 -*-
"""PSCHEME P2b — the seams the job change, the Updates sheets, the hiring
offer and the pay data file share. ADDED file (ledger A15: P2b never edits a
line phase 1 wrote in this module).

* `pb.scheme.map.usual_scheme(...)` — THE answer to "which pay scheme would a
  person of this Country of work get when nobody picks one?". It is the
  "usual" half of Add employee's `_scheme_for` (P1 E.1), moved here so Add
  employee, the joiner sheet, the job change and the hiring offer give one and
  the same answer (handover C: share, do not copy). Writes nothing.
* `pb.scheme.board` helpers for writers that are not a person-by-person
  change: a company move ends the old company's rows first (ledger A9), and a
  taken-back job change puts the rows back exactly as they were. Every row is
  still CHANGED through phase 1's one writer (`_person_set_write`); these two
  only end, remove and restore — what the one writer cannot express.
* `pb.scheme.board.r6_words(...)` — owner ruling R6 in one sentence, so every
  screen says it the same way.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

from odoo.addons.pb_hr_payroll_formula.models.schememap_approval import (
    SCHEMEMAP_WRITE,
)

_logger = logging.getLogger(__name__)

MAIN_KINDS = ('regular', 'end_cycle')


class PbSchemeMapUsual(models.AbstractModel):
    _inherit = 'pb.scheme.map'

    @api.model
    def _payroll_country_codes(self):
        """The Country of work codes a person can have (the selection on
        `hr.employee.payroll_country`)."""
        field = self.env['hr.employee']._fields.get('payroll_country')
        if not field:
            return []
        return [code for code, _label in field._description_selection(self.env)]

    @api.model
    def _most_paid(self, company_id, config_ids, department_id=0, country_code=''):
        """`(config_id, where)` — of `config_ids`, the scheme that pays most of
        the team's people today ('team'), else most people working in
        `country_code` ('country'); `(0, '')` when nobody is paid by any of
        them (NEWHIRE P8, moved here unchanged)."""
        Employee = self.env['hr.employee'].sudo()
        if not config_ids or 'pb_paid_by_id' not in Employee._fields:
            return 0, ''
        base = [('company_id', '=', int(company_id or 0)), ('active', '=', True),
                ('pb_paid_by_id', 'in', list(config_ids))]
        for where, extra in (('team', [('department_id', '=', int(department_id))]
                              if department_id else None),
                             ('country', [('payroll_country', '=', country_code)])):
            if extra is None:
                continue
            groups = Employee._read_group(base + extra, ['pb_paid_by_id'], ['__count'])
            if groups:
                best = sorted(groups, key=lambda g: (-g[1], g[0].id))[0]
                return best[0].id, where
        return 0, ''

    @api.model
    def usual_scheme(self, company_id, country_code, department_id=0, values=None,
                     limit=None):
        """The pay scheme a person of `country_code` gets when nobody picks
        one, and why. Never raises; writes nothing.

        Order (owner ruling R1 — the country leads, the team only breaks a
        tie):

        1. the team ladder's answer (`resolve_for_draft`), when it is a scheme
           of that country (or when no country is given);
        2. else the country's only scheme;
        3. else, of several, the one that pays most of the team, then most
           people in the country, then the first by name;
        4. else (the country has none) the team ladder's answer, whatever its
           country.

        Returns `{'config', 'options', 'reason', 'rung', 'ask', 'ladder'}`:
        `reason` is 'ladder' | 'only' | 'team' | 'country' | 'one_of' |
        'ladder_other' | 'none'; `ask` is True when the country has several
        schemes and nothing but the order of names chose one."""
        Config = self.env['hr.formula.config'].sudo()
        company_id = self._as_company_id(company_id)
        code = country_code if country_code in self._payroll_country_codes() else ''
        options = self._country_schemes(company_id, code) if code else Config
        if limit:
            options = options[:int(limit)]
        ids = options.ids
        ladder = {}
        dept_id = int(department_id or 0)
        if dept_id:
            draft = dict(values or {})
            draft.pop('scheme_id', None)
            draft.pop('advance_scheme_id', None)
            draft['payroll_country'] = code or False
            ladder = self.resolve_for_draft(dept_id, draft, company_id)
        ladder_cfg = Config.browse(ladder.get('config_id') or 0).exists()
        rung = ladder.get('rung') or 'none'
        out = {'config': Config, 'options': options, 'reason': 'none',
               'rung': rung, 'ask': False, 'ladder': ladder}
        if ladder_cfg and (not code or ladder_cfg.country_code == code):
            out.update(config=ladder_cfg, reason='ladder')
        elif options:
            if len(options) == 1:
                out.update(config=options[:1], reason='only')
            else:
                best, where = self._most_paid(company_id, ids, dept_id, code)
                out.update(config=Config.browse(best or ids[0]),
                           reason=where if where else 'one_of', ask=not best)
        elif ladder_cfg:
            out.update(config=ladder_cfg, reason='ladder_other')
        return out


class PbSchemeBoardPersonTools(models.AbstractModel):
    _inherit = 'pb.scheme.board'

    # ============================================================ the words
    @api.model
    def r6_words(self, old_name, new_name, day):
        """Owner ruling R6 in one sentence, or '' when the change starts on a
        1st (nothing to explain) or there is no old scheme."""
        day = fields.Date.to_date(day) if day else None
        if not day or day.day == 1 or not old_name or old_name == new_name:
            return ''
        return _("%(old)s still pays %(month)s. %(new)s starts with the next "
                 "pay run.", old=old_name, new=new_name or '',
                 month=format_date(self.env, day, date_format='MMMM y'))

    @api.model
    def advance_default(self, config):
        """The mid-month advance a new main scheme comes with when nobody says
        otherwise: its ONE paired advance, else none (Add employee's default,
        P1 E.3; ledger A13 — only a real mid-month scheme)."""
        if not config:
            return self.env['hr.formula.config']
        pairs = self._advance_pairs([config.id]).get(str(config.id)) or []
        if len(pairs) != 1:
            return self.env['hr.formula.config']
        advance = self.env['hr.formula.config'].sudo().browse(pairs[0]['id']).exists()
        return advance if advance and advance.cycle_type == 'mid_cycle' else \
            self.env['hr.formula.config']

    # ===================================================== rows, as a state
    @api.model
    def _person_rows_state(self, employee_ids):
        """`{str(row id): [employee_id, config_id, date_from, date_to, source,
        note]}` of every active row of these people — what a writer keeps so a
        take-back can put exactly this back."""
        rows = self.env['pb.person.scheme'].sudo().search([
            ('employee_id', 'in', [int(e) for e in employee_ids or []]),
            ('active', '=', True)], order='id')
        return {str(r.id): [r.employee_id.id, r.config_id.id,
                            fields.Date.to_string(r.date_from),
                            fields.Date.to_string(r.date_to) if r.date_to else '',
                            r.source or 'hand', r.note or '']
                for r in rows}

    @api.model
    def _person_rows_restore(self, before, after, employee_ids):
        """Put the rows of `employee_ids` back from `after` to `before`.
        Refuses (UserError) when they are no longer exactly `after` — somebody
        changed the pay scheme since. Rows created since are removed, ended
        rows re-opened, removed rows written again. Returns how many rows
        moved."""
        if not self.env.su and not self.env.context.get(SCHEMEMAP_WRITE):
            raise UserError(_("A pay scheme change goes through approval."))
        before, after = dict(before or {}), dict(after or {})
        now = self._person_rows_state(employee_ids)
        if now != after:
            Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
            names = Employee.browse(sorted({int(v[0]) for v in
                                           list(now.values()) + list(after.values())}
                                          or [int(e) for e in employee_ids or []])).exists()
            raise UserError(_(
                "Somebody has changed %s's pay scheme since, so this cannot be "
                "taken back here.", ', '.join(n.name or '' for n in names)))
        Row = self.env['pb.person.scheme'].sudo()
        moved = 0
        self.env.flush_all()
        for key in sorted(set(after) - set(before), key=int):
            Row.browse(int(key)).unlink()
            moved += 1
        for key in sorted(set(after) & set(before), key=int):
            if after[key][3] != before[key][3]:
                Row.browse(int(key)).date_to = before[key][3] or False
                moved += 1
        for key in sorted(set(before) - set(after), key=int):
            employee_id, config_id, date_from, date_to, source, note = before[key]
            Row.create({'employee_id': employee_id, 'config_id': config_id,
                        'date_from': date_from, 'date_to': date_to or False,
                        'source': source or 'hand', 'note': note or False})
            moved += 1
        self.env.flush_all()
        return moved

    @api.model
    def _person_end_company(self, employee, new_company, day):
        """Ledger A9 — before a person moves to `new_company` from `day`, every
        row of a scheme that belongs to ANOTHER company ends the day before (a
        row that starts on or after `day` never took effect and is removed). A
        shared scheme (no company) is kept. Returns how many rows moved."""
        if not self.env.su and not self.env.context.get(SCHEMEMAP_WRITE):
            raise UserError(_("A pay scheme change goes through approval."))
        day = fields.Date.to_date(day) or fields.Date.context_today(self)
        Row = self.env['pb.person.scheme'].sudo()
        moved = 0
        self.env.flush_all()
        for row in Row.search([('employee_id', '=', employee.id), ('active', '=', True)],
                              order='date_from, id'):
            company = row.config_id.company_id
            if not company or company == new_company:
                continue
            if row.date_from >= day:
                row.unlink()
                moved += 1
            elif not row.date_to or row.date_to >= day:
                row.date_to = day - timedelta(days=1)
                moved += 1
        self.env.flush_all()
        return moved

    @api.model
    def _person_scheme_now(self, employee, day=None):
        """`(main config, advance config)` of the person's own rows counting on
        `day` (today), or empty recordsets."""
        Config = self.env['hr.formula.config']
        if not employee:
            return Config, Config
        day = fields.Date.to_date(day) or fields.Date.context_today(self)
        rows = self.env['pb.person.scheme'].sudo().search([
            ('employee_id', '=', employee.id), ('active', '=', True)],
            order='date_from, id')
        counting, _ended = self.env['pb.scheme.map'].sudo()._person_rows_for(list(rows), day)
        main = counting.get('end_cycle') or counting.get('regular')
        advance = counting.get('mid_cycle')
        return (main.config_id if main else Config), (advance.config_id if advance else Config)
