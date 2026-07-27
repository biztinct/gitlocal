# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""pb.ot.desk — RPC facade for the Overtime Desk cockpit (Phase K §3c).

An AbstractModel (no table) exposing the org-wide OT approval queue with ceiling
context + a live Bonus-Hours split preview, bulk approve with per-row results, a
config gallery, and a RESTRICTED Bonus Hours review (payroll-manager tier).

Facade doctrine (C18.17 / C18.55a): this surface NEVER writes a state field and
NEVER sudo's a mutation — approvals ride ``hr.overtime.request``'s OWN gated
actions as the real clicking user; reads that must span the org use sudo behind
a manager gate (one-permission-world). The Bonus review is read-only and
server-gated regardless of what the client renders.
"""

from datetime import date, timedelta

from odoo import _, api, models
from odoo.exceptions import AccessError

_OT_TYPES = ('weekday', 'weekend', 'holiday', 'night')
_OT_COLORS = {'weekday': '#e74c3c', 'weekend': '#9b59b6',
              'holiday': '#e67e22', 'night': '#2c3e50'}
_BONUS_PAGE = 100          # bonus review rows per page
_BONUS_SCAN_CAP = 5000     # hard cap on the bonus scan (surfaced, never silent)
_CSV_CAP = 20000           # export row cap (surfaced)


class PbOtDesk(models.AbstractModel):
    _name = 'pb.ot.desk'
    _description = 'Overtime Desk Cockpit'

    # ------------------------------------------------------------- access
    @api.model
    def _require_manager(self):
        """The queue + approvals are attendance-manager only (clone of
        hr.attendance.weekentry._require_manager)."""
        u = self.env.user
        if not (u.has_group('hr_attendance.group_hr_attendance_manager')
                or u.has_group('base.group_system')):
            raise AccessError(_("The Overtime Desk is restricted to attendance managers."))

    def _is_bonus_viewer(self):
        """The Bonus Hours review is a RESTRICTED slice — payroll-manager tier
        only (the owner-mandated restriction). Approver-tier managers do NOT see
        it."""
        u = self.env.user
        for g in ('om_hr_payroll.group_hr_payroll_manager',
                  'pb_hr_payroll_base.group_payroll_super_admin',
                  'base.group_system'):
            try:
                if u.has_group(g):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    @api.model
    def _require_bonus_viewer(self):
        if not self._is_bonus_viewer():
            raise AccessError(_(
                "Bonus Hours review is restricted to payroll managers."))

    # ------------------------------------------------------------- helpers
    def _co_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    def _emp_card(self, emp):
        return {
            'id': emp.id,
            'name': emp.name,
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
            'department': emp.department_id.name if emp.department_id else '',
        }

    def _split_preview(self, req):
        """Live split for a submitted request: what approval would store right
        now. Exclude the request's own id (it is 'submitted' and thus counted by
        _allowance)."""
        entry = req.actual_hours or req.planned_hours or 0.0
        approved, bonus = self.env['pb.ot.ceiling']._split(
            req.employee_id, req.date, entry, exclude_ids=[req.id])
        return {'entry': round(entry, 2), 'approved': approved, 'bonus': bonus}

    # ------------------------------------------------------------- desk load
    @api.model
    def get_desk(self):
        # Review K-F5: the sidebar admits BOTH tiers, so the entry gate must
        # too. A pure bonus viewer (payroll manager without the attendance
        # role) gets the Bonus review surface with an EMPTY approval queue —
        # the queue and its actions stay attendance-manager territory.
        can_act = True
        try:
            self._require_manager()
        except AccessError:
            can_act = False
            self._require_bonus_viewer()
        co_ids = self._co_ids()
        # queue: submitted requests org-wide, company-scoped (C18.11/18). sudo:
        # one-permission-world read behind the manager gate (the officer record
        # rule is own-only, so a plain read would hide other people's requests).
        Req = self.env['hr.overtime.request'].sudo()
        reqs = Req.search([
            ('state', '=', 'submitted'),
            ('employee_id.company_id', 'in', co_ids),
        ], order='date desc, id desc') if can_act else Req.browse()

        emp_ids = reqs.mapped('employee_id').ids
        # ONE batched ceiling read for every employee in the queue
        ceilings = self.env['hr.attendance.weekentry'].get_ot_ceilings(
            emp_ids, date.today().isoformat()) if emp_ids else {}

        queue = []
        for r in reqs:
            split = self._split_preview(r)
            queue.append({
                'id': r.id,
                'employee': self._emp_card(r.employee_id),
                'date': r.date.isoformat() if r.date else '',
                'type': r.overtime_type,
                'type_label': dict(Req._fields['overtime_type'].selection).get(
                    r.overtime_type, r.overtime_type),
                'color': _OT_COLORS.get(r.overtime_type, '#5A4BB0'),
                'rate': r.rate_display or '',
                'planned': round(r.planned_hours or 0.0, 2),
                'split': split,
                'ceiling': ceilings.get(r.employee_id.id, {}),
                'reason': r.reason or '',
            })

        return {
            'can_view_bonus': self._is_bonus_viewer(),
            'can_act': can_act,
            'kpis': self._kpis(co_ids),
            'queue': queue,
            'configs': self._config_gallery(),
            'bonus_presets': self._preset_list(),
        }

    def _kpis(self, co_ids):
        Req = self.env['hr.overtime.request'].sudo()
        today = date.today()
        m_start = today.replace(day=1)
        # month OT by type (submitted+approved approved_hours)
        by_type = {t: 0.0 for t in _OT_TYPES}
        groups = Req.read_group(
            [('date', '>=', m_start), ('date', '<=', today),
             ('state', 'in', ('submitted', 'approved')),
             ('employee_id.company_id', 'in', co_ids)],
            ['approved_hours:sum', 'overtime_type'], ['overtime_type'])
        for g in groups:
            t = g.get('overtime_type')
            if t in by_type:
                by_type[t] = round(g.get('approved_hours') or 0.0, 2)
        pending = Req.search_count([
            ('state', '=', 'submitted'),
            ('employee_id.company_id', 'in', co_ids)])

        # over-90%-of-ANY-enforced-ceiling employees (month/year gauge proxy)
        over_ceiling = self._over_ceiling_count(co_ids)

        out = {
            'pending': pending,
            'by_type': [{'type': t, 'label': t.title(),
                         'color': _OT_COLORS[t], 'hours': by_type[t]}
                        for t in _OT_TYPES],
            'month_total': round(sum(by_type.values()), 2),
            'over_ceiling': over_ceiling,
        }
        # month bonus-hours total — bonus viewers only (rail 2 / restriction)
        if self._is_bonus_viewer():
            bgroups = Req.read_group(
                [('date', '>=', m_start), ('date', '<=', today),
                 ('state', '=', 'approved'),
                 ('bonus_hours', '>', 0),
                 ('employee_id.company_id', 'in', co_ids)],
                ['bonus_hours:sum'], [])
            out['bonus_month'] = round(
                (bgroups[0].get('bonus_hours') if bgroups else 0.0) or 0.0, 2)
        return out

    def _over_ceiling_count(self, co_ids):
        """How many employees with OT this month are within 10% of (or over)
        their monthly cap — the red-pulse KPI."""
        Req = self.env['hr.overtime.request'].sudo()
        today = date.today()
        m_start = today.replace(day=1)
        groups = Req.read_group(
            [('date', '>=', m_start), ('date', '<=', today),
             ('state', 'in', ('submitted', 'approved')),
             ('employee_id.company_id', 'in', co_ids)],
            ['approved_hours:sum'], ['employee_id'])
        emp_ids = [g['employee_id'][0] for g in groups
                   if g.get('employee_id')]
        if not emp_ids:
            return 0
        ceilings = self.env['hr.attendance.weekentry'].get_ot_ceilings(
            emp_ids, today.isoformat())
        n = 0
        for g in groups:
            eid = g['employee_id'][0] if g.get('employee_id') else False
            cap = (ceilings.get(eid) or {}).get('cap_month') or 0.0
            used = g.get('approved_hours') or 0.0
            if cap and used >= 0.9 * cap:
                n += 1
        return n

    def _config_gallery(self):
        """The active OT configs + the resolved period ceilings (read-only
        gallery; native VU-skinned forms open from a card for editing)."""
        cfgs = self.env['hr.overtime.config'].sudo().search(
            [('active', '=', True)], order='sequence, id')
        ceil = self.env['pb.ot.ceiling']._for_company(self.env.company)
        cards = []
        for c in cfgs:
            cards.append({
                'id': c.id,
                'name': c.name,
                'type': c.overtime_type,
                'color': _OT_COLORS.get(c.overtime_type, '#5A4BB0'),
                'rate': c.rate_display or '',
                'rate_multiplier': c.rate_multiplier,
                'days': c.applicable_days_display or '',
                'window': c.time_display or '',
                'threshold': c.threshold_hours,
                'requires_approval': c.requires_approval,
                'day_dots': [bool(getattr(c, f)) for f in (
                    'apply_monday', 'apply_tuesday', 'apply_wednesday',
                    'apply_thursday', 'apply_friday', 'apply_saturday',
                    'apply_sunday')],
            })
        return {
            'cards': cards,
            'caps': {
                'daily': ceil.daily_cap,
                'weekly': ceil.weekly_cap,
                'biweekly': ceil.biweekly_cap,
                'monthly': ceil.monthly_cap,
                'annual': ceil.annual_cap,
                'annual_special': ceil.annual_cap_special,
            },
        }

    # ------------------------------------------------------------- act
    @api.model
    def act(self, request_ids, action, note=False):
        """Approve/refuse submitted requests AS THE REAL USER (no sudo). Bulk =
        per-row results; a young-worker block (or any model refusal) is caught
        per row and the batch never aborts (§3c)."""
        self._require_manager()
        if action not in ('approve', 'refuse'):
            raise AccessError(_("Unknown action."))
        ids = [int(x) for x in (request_ids or [])]
        results = []
        Req = self.env['hr.overtime.request']
        for rid in ids:
            rec = Req.browse(rid).exists()
            if not rec:
                results.append({'id': rid, 'ok': False, 'error': _("No longer exists.")})
                continue
            name = rec.employee_id.name
            try:
                with self.env.cr.savepoint():
                    if action == 'approve':
                        rec.action_approve()
                    else:
                        rec.action_refuse()
                results.append({'id': rid, 'ok': True, 'name': name})
            except Exception as e:  # model refusal → per-row chip, batch survives
                results.append({'id': rid, 'ok': False, 'name': name,
                                'error': self._msg(e)})
        return {'results': results}

    # ------------------------------------------------------- bonus review
    def _preset_list(self):
        return [
            {'key': 'today', 'label': _("Today")},
            {'key': 'week', 'label': _("This week")},
            {'key': 'month', 'label': _("This month")},
            {'key': 'custom', 'label': _("Custom range")},
        ]

    def _preset_range(self, preset):
        today = date.today()
        if preset == 'today':
            return today, today
        if preset == 'week':
            monday = today - timedelta(days=today.weekday())
            return monday, monday + timedelta(days=6)
        if preset == 'month':
            m_start = today.replace(day=1)
            return m_start, today
        return None, None

    def _bonus_domain(self, filters):
        filters = filters or {}
        dom = [('state', '=', 'approved'), ('bonus_hours', '>', 0),
               ('employee_id.company_id', 'in', self._co_ids())]
        preset = filters.get('preset')
        df, dt = None, None
        if preset and preset != 'custom':
            df, dt = self._preset_range(preset)
        else:
            df = filters.get('date_from') or None
            dt = filters.get('date_to') or None
        if df:
            dom.append(('date', '>=', df))
        if dt:
            dom.append(('date', '<=', dt))
        # employees/departments accept either an id list (programmatic) or a
        # free-text name (the cockpit's filter rail).
        if filters.get('employee_ids'):
            dom.append(('employee_id', 'in',
                        [int(x) for x in filters['employee_ids']]))
        elif filters.get('employee'):
            dom.append(('employee_id.name', 'ilike', filters['employee']))
        if filters.get('department_ids'):
            dom.append(('department_id', 'in',
                        [int(x) for x in filters['department_ids']]))
        elif filters.get('department'):
            dom.append(('department_id.name', 'ilike', filters['department']))
        if filters.get('overtime_type'):
            dom.append(('overtime_type', '=', filters['overtime_type']))
        if filters.get('company_id'):
            dom.append(('employee_id.company_id', '=', int(filters['company_id'])))
        if filters.get('min_hours'):
            try:
                dom.append(('bonus_hours', '>=', float(filters['min_hours'])))
            except (TypeError, ValueError):
                pass
        return dom

    def _group_key(self, r, group_by):
        d = r.date
        if group_by == 'department':
            dep = r.department_id
            return (dep.id if dep else 0, dep.name if dep else _("No department"))
        if group_by == 'day':
            return (d.isoformat(), d.strftime('%d %b %Y'))
        if group_by == 'week':
            iso = d.isocalendar()
            return ('%s-W%02d' % (iso[0], iso[1]), _("Week %s") % iso[1])
        if group_by == 'month':
            return (d.strftime('%Y-%m'), d.strftime('%b %Y'))
        # default: employee
        return (r.employee_id.id, r.employee_id.name)

    @api.model
    def get_bonus_hours(self, filters=None, page=0, group_by='employee'):
        self._require_bonus_viewer()
        if group_by not in ('employee', 'department', 'day', 'week', 'month'):
            group_by = 'employee'
        Req = self.env['hr.overtime.request'].sudo()
        dom = self._bonus_domain(filters)
        total_count = Req.search_count(dom)
        capped = total_count > _BONUS_SCAN_CAP
        recs = Req.search(dom, order='date desc, id desc', limit=_BONUS_SCAN_CAP)

        # grand totals + group aggregates over the (capped) scan
        grand_hours = 0.0
        agg = {}
        for r in recs:
            b = r.bonus_hours or 0.0
            grand_hours += b
            key, label = self._group_key(r, group_by)
            a = agg.setdefault(key, {'label': label, 'hours': 0.0, 'count': 0})
            a['hours'] += b
            a['count'] += 1
        groups = sorted(agg.values(), key=lambda x: -x['hours'])
        for g in groups:
            g['hours'] = round(g['hours'], 2)

        # paged detail rows
        start = max(0, int(page)) * _BONUS_PAGE
        page_recs = recs[start:start + _BONUS_PAGE]
        rows = [{
            'id': r.id,
            'employee': r.employee_id.name,
            'employee_id': r.employee_id.id,
            'department': r.department_id.name if r.department_id else '',
            'date': r.date.isoformat() if r.date else '',
            'type': r.overtime_type,
            'type_label': dict(Req._fields['overtime_type'].selection).get(
                r.overtime_type, r.overtime_type),
            'approved': round(r.approved_hours or 0.0, 2),
            'bonus': round(r.bonus_hours or 0.0, 2),
        } for r in page_recs]

        return {
            'rows': rows,
            'groups': groups,
            'group_by': group_by,
            'grand_hours': round(grand_hours, 2),
            'grand_count': len(recs),
            'total_count': total_count,
            'page': int(page),
            'page_size': _BONUS_PAGE,
            'has_more': start + _BONUS_PAGE < len(recs),
            'capped': capped,
            'cap': _BONUS_SCAN_CAP,
        }

    @api.model
    def export_bonus_csv(self, filters=None):
        """Capped CSV of the bonus rows (row cap surfaced, never silent). Returns
        a base64 payload the cockpit downloads via a data-URI anchor — no
        ir.attachment persisted (the console stays read-only)."""
        self._require_bonus_viewer()
        import base64
        import csv
        import io
        Req = self.env['hr.overtime.request'].sudo()
        dom = self._bonus_domain(filters)
        total = Req.search_count(dom)
        truncated = total > _CSV_CAP
        recs = Req.search(dom, order='date desc, id desc', limit=_CSV_CAP)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['Employee', 'Department', 'Date', 'OT Type',
                    'Approved Hours', 'Bonus Hours'])
        for r in recs:
            w.writerow([
                r.employee_id.name,
                r.department_id.name if r.department_id else '',
                r.date.isoformat() if r.date else '',
                r.overtime_type,
                round(r.approved_hours or 0.0, 2),
                round(r.bonus_hours or 0.0, 2),
            ])
        data = buf.getvalue().encode('utf-8')
        return {
            'csv_b64': base64.b64encode(data).decode('ascii'),
            'filename': 'bonus_hours_%s.csv' % date.today().isoformat(),
            'count': len(recs),
            'truncated': truncated,
            'cap': _CSV_CAP,
        }

    # ------------------------------------------------------------- misc
    def _msg(self, e):
        return getattr(e, 'name', None) or (
            e.args[0] if getattr(e, 'args', None) else str(e))
