# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Young Worker Guard cockpit — RPC facade (Phase E §3).

An AbstractModel (no table) feeding the bespoke OWL screen: the under-18 roster
with days-to-18 countdowns and week-hour gauges, a 30-day violation feed, the KPI
strip, and the read-only VN band table. Everything is company-scoped and access
is gated to the HR tier; editing the rules is payroll-manager only.
"""

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

_HR_GROUP = 'om_hr_payroll.group_hr_payroll_user'
_MANAGER_GROUP = 'om_hr_payroll.group_hr_payroll_manager'
_ATT_OFFICER = 'hr_attendance.group_hr_attendance_officer'
_MISSING_LIST_CAP = 24


class PbYoungWorkerGuard(models.AbstractModel):
    _name = 'pb.young.worker.guard'
    _description = 'Young Worker Guard Cockpit'

    # ------------------------------------------------------------- access
    def _is_hr(self):
        u = self.env.user
        return (u._is_admin() or u.has_group(_HR_GROUP)
                or u.has_group(_ATT_OFFICER))

    def _can_edit(self):
        u = self.env.user
        return u._is_admin() or u.has_group(_MANAGER_GROUP)

    def _require_access(self):
        if not self._is_hr():
            raise AccessError(_("The Young Worker Guard is restricted to HR."))

    # ------------------------------------------------------------- payload
    @api.model
    def get_guard_data(self):
        self._require_access()
        Eng = self.env['pb.young.worker'].sudo()
        Emp = self.env['hr.employee'].sudo()
        companies = self.env.companies
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        feed_from = today - timedelta(days=30)

        rules = self.env['pb.young.worker.rule'].sudo().search(
            [('active', '=', True), ('company_id', 'in', companies.ids)])

        # --- resolve the banded (under-18) roster, per company rule ---
        minors = Emp.browse()
        max_age_by_co = {}
        for rule in rules:
            max_age = max(rule.band_ids.mapped('age_max') or [18])
            max_age_by_co[rule.company_id.id] = max_age
            cutoff = today - relativedelta(years=max_age)
            candidates = Emp.search([
                ('company_id', '=', rule.company_id.id), ('active', '=', True),
                ('birthday', '!=', False), ('birthday', '>', cutoff),
            ])
            for emp in candidates:
                if Eng.get_band(emp, today):
                    minors |= emp

        # --- violations once (30d), grouped for the feed + MTD counts ---
        viols = Eng.check_period(minors, feed_from, today, include_no_birthday=False) \
            if minors else []
        mtd_by_emp = {}
        for v in viols:
            if v['date'] >= month_start.isoformat():
                mtd_by_emp[v['employee_id']] = mtd_by_emp.get(v['employee_id'], 0) + 1

        roster, compliant = [], 0
        for emp in minors:
            band = Eng.get_band(emp, today)
            wk = Eng.check_week_hours(emp, today)
            bday = Eng._birthday(emp)
            max_age = max_age_by_co.get(emp.company_id.id, 18)
            adult_on = bday + relativedelta(years=max_age) if bday else False
            days_to_adult = (adult_on - today).days if adult_on else False
            age_years = Eng._age(emp, today)
            age_months = 0
            if bday:
                delta = relativedelta(today, bday)
                age_years, age_months = delta.years, delta.months
            over_cap = wk['actual'] > wk['cap'] if wk['cap'] else False
            if not over_cap and not mtd_by_emp.get(emp.id):
                compliant += 1
            roster.append({
                'id': emp.id,
                'name': emp.name,
                'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
                'department': emp.department_id.name if emp.department_id else '',
                'age_years': age_years,
                'age_months': age_months,
                'days_to_adult': days_to_adult,
                'adult_age': max_age,
                'band_label': band.note or (_("%(a)s–%(b)s yrs") % {'a': band.age_min, 'b': band.age_max}),
                'week_hours': wk['actual'],
                'week_cap': wk['cap'],
                'mtd_violations': mtd_by_emp.get(emp.id, 0),
            })
        roster.sort(key=lambda r: (r['days_to_adult'] if r['days_to_adult'] is not False else 1 << 30))

        # --- missing-birthday data-quality task (bounded) ---
        miss_dom = [('company_id', 'in', companies.ids), ('active', '=', True),
                    ('birthday', '=', False)]
        missing_count = Emp.search_count(miss_dom)
        missing = [{
            'id': e.id, 'name': e.name,
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % e.id,
            'department': e.department_id.name if e.department_id else '',
        } for e in Emp.search(miss_dom, limit=_MISSING_LIST_CAP, order='name')]

        # --- feed (newest first) ---
        feed = sorted(viols, key=lambda v: v['date'], reverse=True)

        return {
            'today': today.isoformat(),
            'can_edit': self._can_edit(),
            'kpis': {
                'protected': len(minors),
                'compliant': compliant,
                'violations_30d': len(viols),
                'missing_birthdays': missing_count,
            },
            'roster': roster,
            'feed': feed,
            'missing': missing,
            'missing_truncated': max(0, missing_count - len(missing)),
            'rules': self._rules_payload(rules),
            'has_rules': bool(rules),
        }

    def _rules_payload(self, rules):
        out = []
        for rule in rules:
            out.append({
                'id': rule.id,
                'company': rule.company_id.name,
                'night_from': rule.night_from,
                'night_to': rule.night_to,
                'bands': [{
                    'age_min': b.age_min, 'age_max': b.age_max,
                    'max_hours_day': b.max_hours_day, 'max_hours_week': b.max_hours_week,
                    'ot_blocked': b.ot_blocked, 'night_blocked': b.night_blocked,
                    'label': b.note or '',
                } for b in rule.band_ids.sorted(key=lambda x: x.age_min)],
            })
        return out

    @api.model
    def open_rules(self):
        """Return an act_window to the native rule config (payroll-manager gated)."""
        self._require_access()
        if not self._can_edit():
            raise AccessError(_("Only a payroll manager can edit the young-worker rules."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Young Worker Rules"),
            'res_model': 'pb.young.worker.rule',
            'view_mode': 'list,form',
            'target': 'current',
        }
