# Part of Payobook. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta

from odoo import api, fields, models, _


class PbOtCeiling(models.Model):
    """Company-scoped overtime ceiling caps (labour-law budget).

    The Weekly Entry cockpit reads these as CONFIG — no OT-cap constants live in
    code (C18: engine reads config records). VN defaults ship in data:
    40 h/month, 200 h/year, 300 h/year for special-sector employees, plus a
    daily cap (Phase K). This model is THE single OT limit source (C18.55c) —
    ``hr.overtime.config.max_hours_*`` are legacy per-type metadata and are never
    enforced a second time.

    Multi-period limits (Phase K). Each cap 0.0 == "not enforced". Windows:
      * daily     — the request's own date;
      * weekly    — the ISO week (Mon–Sun) containing the date;
      * bi-weekly — the ISO-week PAIR anchored on odd ISO weeks (1-2, 3-4, …),
                    deterministic with no config;
      * monthly   — the calendar month;
      * annual    — the calendar year (special-sector cap when flagged).
    The day's OT ALLOWANCE is the tightest remaining slack across every ENFORCED
    period (``_allowance`` below); hours beyond it overflow to bonus_hours.
    """
    _name = 'pb.ot.ceiling'
    _description = 'Overtime Ceiling Configuration'
    _order = 'company_id'

    name = fields.Char(string='Name', default='Overtime Ceilings')
    company_id = fields.Many2one(
        'res.company', string='Company',
        help='Leave blank for a global fallback cap set.')
    daily_cap = fields.Float(
        string='Daily OT Cap (h)', default=0.0,
        help='Maximum OT hours in a single day before overflow-to-bonus. '
             '0 = not enforced.')
    weekly_cap = fields.Float(
        string='Weekly OT Cap (h)', default=0.0,
        help='Maximum OT hours in an ISO week (Mon–Sun). 0 = not enforced.')
    biweekly_cap = fields.Float(
        string='Bi-weekly OT Cap (h)', default=0.0,
        help='Maximum OT hours across an odd-week-anchored fortnight '
             '(weeks 1-2, 3-4, …). 0 = not enforced.')
    monthly_cap = fields.Float(string='Monthly OT Cap (h)', default=40.0)
    annual_cap = fields.Float(string='Annual OT Cap (h)', default=200.0)
    annual_cap_special = fields.Float(
        string='Annual OT Cap — Special Sector (h)', default=300.0,
        help='Annual cap applied to employees flagged as special-sector '
             '(higher statutory ceiling).')
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------ periods
    def _enforced_periods(self, on_date, special=False):
        """Return [(window_start, window_end, cap), …] for every ENFORCED period
        (cap > 0) on ``on_date``. Bounds are inclusive Dates. Special-sector
        employees get the higher annual cap."""
        self.ensure_one()
        out = []
        d = on_date
        if self.daily_cap > 0:
            out.append((d, d, self.daily_cap))
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        if self.weekly_cap > 0:
            out.append((monday, sunday, self.weekly_cap))
        if self.biweekly_cap > 0:
            # bi-weekly = the ISO-week pair anchored on the ODD week. If this
            # week's ISO number is odd it is the pair's first week (window =
            # [Mon, Mon+13]); if even it is the second (window = [Mon-7, Sun]).
            # ISO week 53 (odd) anchors a SOLO window clamped to its own ISO
            # year: the next week is week 1, itself odd and anchoring a fresh
            # pair — without the clamp the two windows overlap and hours are
            # double-counted across the year boundary (review K-F2; 2026 is a
            # 53-week ISO year).
            iso_week = d.isocalendar()[1]
            if iso_week % 2 == 1:
                end = sunday if iso_week == 53 else monday + timedelta(days=13)
                out.append((monday, end, self.biweekly_cap))
            else:
                out.append((monday - timedelta(days=7), sunday, self.biweekly_cap))
        if self.monthly_cap > 0:
            m_start = d.replace(day=1)
            if d.month == 12:
                m_end = date(d.year, 12, 31)
            else:
                m_end = date(d.year, d.month + 1, 1) - timedelta(days=1)
            out.append((m_start, m_end, self.monthly_cap))
        annual = self.annual_cap_special if special else self.annual_cap
        if annual > 0:
            out.append((date(d.year, 1, 1), date(d.year, 12, 31), annual))
        return out

    @api.model
    def _allowance(self, employee, on_date, exclude_ids=None):
        """The day's remaining OT allowance for ``employee`` on ``on_date``.

        The ONE allowance function (C18.55b). For each ENFORCED period it is
        cap − Σ(approved_hours of approved+submitted requests whose date is in
        the window), excluding ``exclude_ids``; the day's allowance is the
        MIN across periods (tightest wins). ``float('inf')`` when no period is
        enforced. The counting base is OT-countable ``approved_hours`` only —
        never ``bonus_hours`` (bonus is definitionally outside the caps, rail 2).
        """
        ceil = self._for_company(employee.company_id or self.env.company)
        # sudo the special-sector read: the field is groups='hr.group_hr_user',
        # so an attendance manager without the HR group CRASHED on approve
        # (review K-F8). It is system-derived budget context, exactly like the
        # request rows read below — one permission world (C18.17).
        special = employee.sudo().pb_ot_special_sector
        periods = ceil._enforced_periods(on_date, special)
        if not periods:
            return float('inf')
        exclude = {int(x) for x in (exclude_ids or [])}
        starts = [p[0] for p in periods]
        ends = [p[1] for p in periods]
        # sudo: the allowance is a system-derived budget read (same one-permission
        # -world posture as the OT bridge / weekentry, C18.17); a non-manager
        # editing a report's OT must still see the true cap usage.
        rows = self.env['hr.overtime.request'].sudo().search_read(
            [('employee_id', '=', employee.id),
             ('date', '>=', min(starts)), ('date', '<=', max(ends)),
             ('state', 'in', ('submitted', 'approved'))],
            ['id', 'date', 'approved_hours'])
        rows = [r for r in rows if r['id'] not in exclude]
        allowances = []
        for (start, end, cap) in periods:
            used = sum(r['approved_hours'] or 0.0 for r in rows
                       if start <= r['date'] <= end)
            allowances.append(cap - used)
        return min(allowances)

    @api.model
    def _split(self, employee, on_date, entry_hours, exclude_ids=None):
        """Split a raw OT entry into (approved_within_cap, bonus_overflow).

        ``approved`` = the slice inside the day's allowance (clamped ≥0), the
        rest overflows to ``bonus`` — never lost, never blocked (adults). The two
        writers (grid save + approve recompute) both go through here so the
        arithmetic is identical."""
        allowance = self._allowance(employee, on_date, exclude_ids=exclude_ids)
        approved = max(0.0, min(entry_hours, allowance))
        bonus = round(entry_hours - approved, 2)
        return round(approved, 2), bonus

    @api.model
    def _for_company(self, company):
        """Resolve the ceiling config for a company (company-specific first,
        then a global fallback, then a transient default record).

        Two explicit searches — NOT one ``order='company_id desc'`` search:
        Postgres sorts NULLs FIRST on DESC, so a single ordered query returns the
        GLOBAL (company_id NULL) row ahead of a company-specific one, silently
        giving every company the fallback caps (caught by the F8 per-company
        ceiling test)."""
        base = [('active', '=', True)]
        rec = self.search(base + [('company_id', '=', company.id)], limit=1)
        if not rec:
            rec = self.search(base + [('company_id', '=', False)], limit=1)
        # never None: hand back a NewId with the field defaults
        return rec or self.new({})


class HrEmployeeOtSector(models.Model):
    _inherit = 'hr.employee'

    pb_ot_special_sector = fields.Boolean(
        string='Special-Sector OT Ceiling',
        groups='hr.group_hr_user',
        help='When set, this employee is subject to the higher special-sector '
             'annual overtime cap instead of the standard annual cap.')
