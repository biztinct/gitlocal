# -*- coding: utf-8 -*-
"""Carrying the old planning screens' data into the new Pay area.

ONE ENTRY POINT, RUN TWICE
--------------------------
`pb.pay.migrate.run()` is called by the install hook and by the upgrade script,
and it is IDEMPOTENT: every piece marks what it has already carried, so running
it a second time reports zero and changes nothing. That is what makes it safe
to run on a database somebody has already upgraded, which is exactly what
happens when a tenant is restored from a backup taken half-way through.

WHAT IS CARRIED, AND WHAT IS NOT
--------------------------------
Carried: merit matrices (into guidance grids), compensation cycles and their
recommendations and approval steps (into read-only past reviews with a trail),
the performance score on the employee record, and the budget guardrails (into
the limit templates a new review starts from). Pay grades were carried in the
previous phase.

Not carried, on purpose: planning scenarios, forecasts, monthly projections and
the component tagging. The first three are replaced by the planning room, which
is a different product with a different model of the world and no sensible
mapping from the old one; the fourth was retired by a ruling of its own — the
payroll engine now classifies its own components and a hand-typed tag on every
rule of every scheme was never kept up to date.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

#: How a guardrail becomes a limit. `None` means there is no honest mapping.
GUARDRAIL_KINDS = {
    'max_increase_pct': ('max_raise_pct', 'threshold_value'),
    'max_increase_amount': ('max_raise_amount', 'threshold_amount'),
    'dept_budget_cap': ('division_budget', 'threshold_amount'),
    'compa_max': ('band_ceiling', None),
    'min_rating_for_increase': ('min_rating', 'threshold_value'),
    'compa_min': None,
    'total_budget_cap': None,
}


class PbPayMigrate(models.AbstractModel):
    _name = 'pb.pay.migrate'
    _description = 'Carry the old planning data into Pay'

    @api.model
    def run(self):
        report = {}
        for name, fn in (('guidance', self.migrate_guidance),
                         ('ratings', self.migrate_ratings),
                         ('reviews', self.migrate_reviews),
                         ('limits', self.migrate_limits)):
            try:
                report[name] = fn()
            except Exception as error:          # noqa: BLE001
                _logger.exception('pb_pay: could not carry over %s', name)
                report[name] = {'error': str(error)[:200]}
        _logger.info('pb_pay: carried over %s', report)
        return report

    # ------------------------------------------------------------- the parts
    @api.model
    def migrate_guidance(self):
        return self.env['pb.pay.guidance'].migrate_legacy()

    @api.model
    def migrate_ratings(self):
        return self.env['pb.pay.rating'].migrate_legacy()

    @api.model
    def migrate_limits(self):
        """Old guardrails become the limits a new review starts with.

        A guardrail belonged to a COMPANY and applied to whichever cycle
        somebody attached it to; a limit template belongs to a company's pay
        settings and is copied into every review that company starts. That is
        the same intent expressed once instead of every time.
        """
        report = {'found': 0, 'made': 0, 'skipped': 0, 'unmapped': []}
        if 'wfp.budget.guardrail' not in self.env:
            return report
        rails = self.env['wfp.budget.guardrail'].sudo().with_context(
            active_test=False).search([])
        report['found'] = len(rails)
        Limit = self.env['pb.pay.review.limit'].sudo()
        Settings = self.env['pb.pay.settings'].sudo()
        for rail in rails:
            mapped = GUARDRAIL_KINDS.get(rail.rule_type)
            if not mapped:
                report['unmapped'].append(rail.rule_type)
                continue
            kind, source = mapped
            value = float(rail[source] or 0.0) if source else 0.0
            settings = Settings.for_company(
                rail.company_id or self.env.company)
            if Limit.search([('settings_id', '=', settings.id),
                             ('kind', '=', kind)], limit=1):
                report['skipped'] += 1
                continue
            Limit.create({
                'settings_id': settings.id, 'kind': kind, 'value': value,
                'enforcement': rail.enforcement or 'warn',
            })
            report['made'] += 1
        report['unmapped'] = sorted(set(report['unmapped']))
        return report

    @api.model
    def migrate_reviews(self):
        """Every old compensation cycle becomes a past review, read only.

        It is kept because somebody will one day be asked "what did we give
        people in 2026 and who signed it off", and the answer has to survive
        the screen that produced it. Every recommendation becomes a row with
        the same two figures, and every approval step becomes an entry in the
        review's own trail so the signatures are not lost either.
        """
        report = {'cycles': 0, 'reviews': 0, 'lines': 0, 'steps': 0,
                  'skipped': 0}
        if 'wfp.compensation.cycle' not in self.env:
            return report
        Cycle = self.env['wfp.compensation.cycle'].sudo()
        cycles = Cycle.with_context(active_test=False).search([])
        report['cycles'] = len(cycles)
        if not cycles:
            return report
        Review = self.env['pb.pay.review'].sudo()
        Line = self.env['pb.pay.review.line'].sudo()
        Log = self.env['biz.approval.step.log'].sudo()
        for cycle in cycles:
            marker = 'wfp.compensation.cycle:%s;' % cycle.id
            if Review.search([('note', 'like', marker)], limit=1):
                report['skipped'] += 1
                continue
            company = cycle.company_id or self.env.company
            review = Review.create({
                'name': _('%(name)s (carried over)',
                          name=cycle.name or _('Pay round')),
                'scope_kind': 'company', 'scope_ref': company.id,
                'scope_label': company.display_name,
                'company_id': company.id,
                'company_ids': [(6, 0, company.ids)],
                'currency_id': company.currency_id.id,
                'year': int(cycle.fiscal_year or 0)
                or (cycle.effective_date.year if cycle.effective_date
                    else fields.Date.context_today(self).year),
                'effective_date': cycle.effective_date
                or fields.Date.context_today(self),
                'budget_amount': float(cycle.budget_amount or 0.0),
                'note': '%s carried over from the old Compensation Cycles '
                        'screen.' % marker,
            })
            report['reviews'] += 1
            made = []
            for rec in cycle.recommendation_ids:
                base = float(rec.current_base or 0.0)
                new = float(rec.new_base or 0.0)
                made.append({
                    'review_id': review.id,
                    'employee_id': rec.employee_id.id,
                    'person_id': rec.employee_id.id,
                    'contract_id': rec.contract_id.id or False,
                    'company_id': company.id,
                    'department_id': rec.department_id.id or False,
                    'manager_id': rec.manager_id.id or False,
                    'currency_id': company.currency_id.id,
                    'current_wage': base,
                    'proposal_pct': float(rec.recommended_pct or 0.0),
                    'proposal_amount': new - base,
                    'new_wage': new,
                    'annual_cost_delta': (new - base) * 12.0,
                    'manager_note': rec.recommendation_note or '',
                    'state': 'submitted',
                })
            if made:
                # A person can appear twice across two old cycles but only
                # once inside one, and the constraint says so; a duplicate
                # inside a single cycle is dropped rather than failing the
                # whole migration for a row nobody can act on.
                seen, unique = set(), []
                for row in made:
                    if row['employee_id'] in seen:
                        continue
                    seen.add(row['employee_id'])
                    unique.append(row)
                Line.create(unique)
                report['lines'] += len(unique)

            for step in cycle.approval_step_ids.sorted(
                    key=lambda s: (s.sequence, s.id)):
                Log.create({
                    'res_model': 'pb.pay.review', 'res_id': review.id,
                    'from_state': 'proposed',
                    'to_state': 'approved' if step.state == 'approved'
                    else ('refused' if step.state == 'rejected' else 'draft'),
                    'note': _('%(name)s — %(state)s',
                              name=step.name or '', state=step.state or ''),
                })
                report['steps'] += 1

            state = 'applied' if cycle.state in ('applied', 'closed') \
                else 'closed'
            review._chain_state_write(state)
            review.write({'is_legacy': True})
        return report
