# -*- coding: utf-8 -*-
""""Paid by" — the map's answer, written down on the person.

WHY IT IS STORED AND NOT COMPUTED ON READ
-----------------------------------------
Two reasons, and the second is the one that decided it.

  1. A list of 4,500 people showing "Paid by" cannot resolve the ladder per
     row. A non-stored compute would either be a per-record loop (minutes) or a
     batch compute the ORM calls in unpredictable slices.
  2. It has to be SEARCHABLE and GROUPABLE. "Show me everybody the Retail
     scheme pays", "how many people has nobody attached to anything" — those
     are the questions this whole phase exists to answer, and an unstored
     field can answer neither (WFPLAN WF7 is the same lesson from the other
     direction: `hr.employee.department_id` is unstored, so it is invisible to
     `read_group`, which is why the roster is read in SQL everywhere).

SO IT IS STORED, AND THE PRICE OF STORING IT IS KEEPING IT TRUE. That price is
paid three ways: anything that could change the answer marks the affected
company's people STALE in one SQL statement (never a per-record write); a
nightly job refreshes whatever is stale; and the map screen has a button that
does it now and says how many changed.

`pb_paid_by_stale` is therefore not a bug flag — it is the honest statement
"the map moved and these people have not been re-read yet", and every screen
that shows "Paid by" can say so.

NOTHING HERE IS PAY DATA. These three fields say which scheme WOULD pay this
person; they change no wage, no contract and no payslip.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

#: How many people one nightly pass refreshes. A group with 40,000 people
#: takes several nights to settle after a structural change, and that is the
#: right trade: a cron that runs for an hour is a cron somebody kills.
CRON_BATCH = 20000


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pb_paid_by_id = fields.Many2one(
        'hr.formula.config', string='Paid by', index=True, readonly=True,
        help="The payroll scheme that pays this person for the company's main "
             "monthly run, worked out from the scheme map.")
    pb_paid_by_advance_id = fields.Many2one(
        'hr.formula.config', string='Advance paid by', index=True,
        readonly=True,
        help="The payroll scheme that pays this person's mid-month advance, "
             "when the company runs one.")
    pb_paid_by_rung = fields.Char(
        string='How that was worked out', readonly=True)
    pb_paid_by_stale = fields.Boolean(
        string='Needs working out again', default=True, index=True,
        readonly=True)

    # ------------------------------------------------------- which kind of run
    @api.model
    def _pb_main_cycle(self, company_id):
        """The kind of run "Paid by" means for this company.

        End of month where the company runs one, otherwise its regular
        payroll, otherwise no opinion at all — which is the answer for a
        company whose single scheme has never been given a kind.
        """
        Config = self.env['hr.formula.config'].sudo()
        domain = ['|', ('company_id', '=', False),
                  ('company_id', '=', int(company_id or 0)),
                  ('state', '=', 'active')]
        for cycle in ('end_cycle', 'regular'):
            if Config.search_count(domain + [('cycle_type', '=', cycle)]):
                return cycle
        return 'any'

    # ------------------------------------------------------------- the refresh
    @api.model
    def _pb_mark_paid_by_stale(self, company_ids=None, employee_ids=None):
        """Say "these need working out again" in ONE statement.

        Never a recordset write: marking 4,500 people through the ORM fires
        4,500 `write`s, every tracked field's machinery and this method's own
        triggers. The flag is derived bookkeeping, so it is set in SQL and the
        cache is invalidated behind it.

        THE ORDER OF THE THREE LINES BELOW IS THE WHOLE OF GOTCHA GR13, and it
        is not obvious. `env.invalidate_all()` FLUSHES before it invalidates,
        so a raw statement followed by `invalidate_all()` has its work undone
        by whatever the ORM was still holding — here, the `pb_paid_by_stale =
        False` this very module wrote a moment earlier. Measured: the flag read
        back False every time. So the pending writes go out FIRST, the raw
        statement goes on top of them, and the invalidation is told NOT to
        flush again.
        """
        where, args = [], []
        if company_ids:
            where.append('company_id = ANY(%s)')
            args.append([int(c) for c in company_ids if c])
        if employee_ids:
            where.append('id = ANY(%s)')
            args.append([int(e) for e in employee_ids if e])
        if not where:
            where.append('TRUE')
        self.env.flush_all()
        self.env.cr.execute(
            'UPDATE hr_employee SET pb_paid_by_stale = TRUE WHERE %s'
            % ' AND '.join(where), args)
        self.env.invalidate_all(flush=False)
        return True

    @api.model
    def _pb_recompute_paid_by(self, company_ids=None, employee_ids=None,
                              only_stale=False, limit=None):
        """Work "Paid by" out again, in bulk. Returns how many CHANGED."""
        if 'pb.scheme.map' not in self.env:
            return 0
        domain = []
        if company_ids:
            domain.append(('company_id', 'in', [int(c) for c in company_ids]))
        if employee_ids:
            domain.append(('id', 'in', [int(e) for e in employee_ids]))
        if only_stale:
            domain.append(('pb_paid_by_stale', '=', True))
        people = self.sudo().search(domain, limit=limit or None)
        if not people:
            return 0
        Map = self.env['pb.scheme.map'].sudo()
        by_company = {}
        for employee in people:
            by_company.setdefault(employee.company_id.id, []).append(employee.id)

        changed = 0
        for company_id, ids in by_company.items():
            main_cycle = self._pb_main_cycle(company_id)
            main = Map.resolve_many(ids, main_cycle)
            advance = Map.resolve_many(ids, 'mid_cycle')
            # Group the writes: on the demo company this turns 4,533 writes
            # into a handful, one per distinct answer.
            buckets = {}
            for employee_id in ids:
                answer = main.get(employee_id) or {}
                second = advance.get(employee_id) or {}
                # The advance rung only counts when a mid-month scheme really
                # exists: "the only scheme in this company" would otherwise
                # make the end-of-month scheme pay the advance too, which is
                # the same person paid twice on paper.
                advance_id = (second.get('config_id') or 0
                              if second.get('rung') in ('department',
                                                        'division', 'rule')
                              else 0)
                key = (answer.get('config_id') or 0, advance_id,
                       answer.get('via') or '')
                buckets.setdefault(key, []).append(employee_id)
            for (config_id, advance_id, via), bucket in buckets.items():
                rows = self.sudo().browse(bucket)
                stale = rows.filtered(
                    lambda r, c=config_id, a=advance_id, v=via: (
                        r.pb_paid_by_id.id != c
                        or r.pb_paid_by_advance_id.id != a
                        or (r.pb_paid_by_rung or '') != v
                        or r.pb_paid_by_stale))
                if not stale:
                    continue
                really = stale.filtered(
                    lambda r, c=config_id, a=advance_id: (
                        r.pb_paid_by_id.id != c
                        or r.pb_paid_by_advance_id.id != a))
                changed += len(really)
                stale.write({
                    'pb_paid_by_id': config_id or False,
                    'pb_paid_by_advance_id': advance_id or False,
                    'pb_paid_by_rung': via,
                    'pb_paid_by_stale': False,
                })
        return changed

    @api.model
    def _pb_cron_recompute_paid_by(self):
        """Nightly: settle whatever the day's edits made stale."""
        changed = self._pb_recompute_paid_by(only_stale=True, limit=CRON_BATCH)
        _logger.info('Scheme map: "paid by" refreshed, %s people changed',
                     changed)
        return changed


class HrVersion(models.Model):
    """A person moving team changes who pays them."""
    _inherit = 'hr.version'

    def write(self, vals):
        res = super().write(vals)
        if 'department_id' in vals and 'hr.employee' in self.env:
            try:
                self.env['hr.employee'].sudo()._pb_mark_paid_by_stale(
                    employee_ids=self.mapped('employee_id').ids)
            except Exception:       # noqa: BLE001 — never block an HR edit
                _logger.exception('Could not flag "paid by" after a team move')
        return res


class HrContract(models.Model):
    """A contract that names a team, or stops running, changes who pays."""
    _inherit = 'hr.contract'

    def write(self, vals):
        res = super().write(vals)
        if ('department_id' in vals or 'state' in vals) \
                and 'hr.employee' in self.env:
            try:
                self.env['hr.employee'].sudo()._pb_mark_paid_by_stale(
                    employee_ids=self.mapped('employee_id').ids)
            except Exception:       # noqa: BLE001
                _logger.exception('Could not flag "paid by" after a contract '
                                  'change')
        return res


class HrFormulaConfig(models.Model):
    """A scheme switched off, or switched on, changes who it pays."""
    _inherit = 'hr.formula.config'

    def write(self, vals):
        res = super().write(vals)
        if ('state' in vals or 'cycle_type' in vals) \
                and 'hr.employee' in self.env:
            try:
                self.env['hr.employee'].sudo()._pb_mark_paid_by_stale(
                    company_ids=self.mapped('company_id').ids or None)
            except Exception:       # noqa: BLE001
                _logger.exception('Could not flag "paid by" after a scheme '
                                  'changed')
        return res


class PbDivisionLink(models.Model):
    """A department joining or leaving a division changes who pays it."""
    _inherit = 'pb.division.link'

    def _pb_flag(self):
        if 'hr.employee' not in self.env:
            return
        try:
            self.env['hr.employee'].sudo()._pb_mark_paid_by_stale(
                company_ids=self.mapped('company_id').ids or None)
        except Exception:       # noqa: BLE001
            _logger.exception('Could not flag "paid by" after a division '
                              'attachment changed')

    @api.model_create_multi
    def create(self, vals_list):
        rows = super().create(vals_list)
        rows._pb_flag()
        return rows

    def write(self, vals):
        res = super().write(vals)
        self._pb_flag()
        return res

    def unlink(self):
        companies = self.mapped('company_id').ids
        res = super().unlink()
        if companies and 'hr.employee' in self.env:
            self.env['hr.employee'].sudo()._pb_mark_paid_by_stale(
                company_ids=companies)
        return res
