# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""RPC facade for the "My Team" (MSS) cockpit — Sudima Phase I §3.

An AbstractModel (no table) that assembles a manager's approval queues, team
metrics and roster, and routes one-click approve/refuse through each source
model's OWN gated action, AS THE REAL CLICKING USER (no sudo — the C18.17
one-permission-world rail). The facade NEVER writes a `state` field itself
(C18.24/55): every mutation rides `action_approve` / `_advance_state` /
`action_refuse_chain` on the target model, so a tier the user lacks is refused
BY THE MODEL and the cockpit surfaces that message (safety rail 1).

Defense in depth (safety rail 4): a crafted `act()` on a record outside the
caller's team is rejected here AND would still hit the model's own gates; a
non-whitelisted model or action string raises.
"""

import logging

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

_HR_GROUPS = ('om_hr_payroll.group_hr_payroll_user',
              'om_hr_payroll.group_hr_payroll_manager',
              'hr.group_hr_user', 'hr.group_hr_manager')

# Whitelisted (model, action) → the target model's OWN method. `note` = whether
# the method accepts a refusal note. NOTHING else is callable through act().
# Source models are existence-checked at call time (soft-hooked phases).
_ACT_MAP = {
    'hr.overtime.request': {
        'approve': {'method': 'action_approve', 'note': False},
        'refuse': {'method': 'action_refuse', 'note': False},
    },
    'pb.business.trip': {
        # manager tier only — submitted → manager_approved (the specific
        # employee.parent_id.user_id passes without a group; the model decides).
        'approve': {'method': 'action_manager_approve', 'note': False},
        'refuse': {'method': 'action_refuse_chain', 'note': True},
    },
    'hr.attendance.correction': {
        'approve': {'method': 'action_approve', 'note': False},
        'refuse': {'method': 'action_refuse', 'note': True},
    },
    'hr.leave': {
        'approve': {'method': 'action_approve', 'note': False},
        'refuse': {'method': 'action_refuse', 'note': False},
    },
}

# left-border colour per source (matches the OT grid legend / handover §4.1)
_SOURCE_META = {
    'hr.overtime.request': {'key': 'ot', 'label': 'Overtime', 'colour': 'ot'},
    'pb.business.trip': {'key': 'trip', 'label': 'Business Trip', 'colour': 'trip'},
    'hr.attendance.correction': {'key': 'correction', 'label': 'Attendance', 'colour': 'correction'},
    'hr.leave': {'key': 'leave', 'label': 'Time Off', 'colour': 'leave'},
}


class PbTeam(models.AbstractModel):
    _name = 'pb.team'
    _description = 'My Team (MSS) Cockpit'

    # ------------------------------------------------------------- identity
    def _is_hr(self):
        u = self.env.user
        if u._is_admin():
            return True
        for g in _HR_GROUPS:
            try:
                if u.has_group(g):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    def _my_team(self, recursive=False):
        """Direct reports (default) or the whole sub-tree (skip-level).

        Team = the `parent_id` hierarchy (trips/OT/corrections all key off it).
        Resolved by explicit search on the session user (C18.26 — never
        `env.user.employee_id`, which is company-dependent)."""
        Emp = self.env['hr.employee'].sudo()
        me = Emp.search([('user_id', '=', self.env.uid)], limit=1)
        if not me:
            return Emp.browse()
        if recursive:
            # the whole sub-tree below me, excluding myself
            return Emp.search([('id', 'child_of', me.id), ('id', '!=', me.id)])
        return Emp.search([('parent_id', '=', me.id)])

    # ------------------------------------------------------------ card bits
    def _emp_card(self, emp):
        return {
            'id': emp.id,
            'name': emp.name,
            'job': emp.job_title or (emp.job_id.name if emp.job_id else ''),
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
        }

    # --------------------------------------------------------- queue data
    @api.model
    def get_team_data(self, recursive=False):
        team = self._my_team(recursive=recursive)
        is_hr = self._is_hr()
        return {
            'has_team': bool(team),
            'is_hr': is_hr,
            'recursive': bool(recursive),
            'me': self._me_card(),
            'team_size': len(team),
            'queues': self._build_queues(team),
            'metrics': self._build_metrics(team),
            'roster': self._build_roster(team),
        }

    def _me_card(self):
        me = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        return {
            'name': me.name or self.env.user.name,
            'avatar_url': ('/web/image/hr.employee/%s/avatar_128' % me.id)
            if me else '/web/image/res.users/%s/avatar_128' % self.env.uid,
        }

    def _build_queues(self, team):
        """One flat, source-tagged list of everything awaiting THIS user's
        action for THIS team, plus per-source counts. Each item reuses the
        record's own `can_*` compute where present (never re-derived)."""
        from odoo import fields as _f
        now = _f.Datetime.now()
        items = []
        if not team:
            return {'items': items, 'counts': {}}
        tids = team.ids

        def age(rec):
            cd = rec.create_date
            return max(0, (now - cd).days) if cd else 0

        # --- OT (no chain mixin; manager acts via action_approve) ---
        OT = self.env['hr.overtime.request']
        for r in OT.search([('state', '=', 'submitted'),
                            ('employee_id', 'in', tids)], order='create_date'):
            items.append({
                'model': 'hr.overtime.request', 'res_id': r.id,
                'source': 'ot',
                'title': _('%(h)s h · %(t)s OT',
                           h=('%g' % (r.planned_hours or 0)),
                           t=dict(OT._fields['overtime_type'].selection).get(
                               r.overtime_type, r.overtime_type)),
                'subtitle': (r.reason or '')[:120],
                'when': r.date and r.date.strftime('%d %b') or '',
                'employee': self._emp_card(r.employee_id),
                'age': age(r),
                'can_approve': True, 'can_refuse': True,
            })

        # --- business trips (chain; manager tier) — soft ---
        if 'pb.business.trip' in self.env:
            Trip = self.env['pb.business.trip']
            for r in Trip.search([('state', '=', 'submitted'),
                                  ('employee_id', 'in', tids)], order='create_date'):
                items.append({
                    'model': 'pb.business.trip', 'res_id': r.id,
                    'source': 'trip',
                    'title': r.destination if 'destination' in r._fields and r.destination
                    else (r.name or _('Business trip')),
                    'subtitle': (r.purpose if 'purpose' in r._fields else '') or '',
                    'when': self._date_span(r),
                    'employee': self._emp_card(r.employee_id),
                    'age': age(r),
                    'can_approve': bool(getattr(r, 'can_manager_approve', True)),
                    'can_refuse': bool(getattr(r, 'can_refuse', True)),
                })

        # --- attendance corrections (chain) — soft ---
        if 'hr.attendance.correction' in self.env:
            Corr = self.env['hr.attendance.correction']
            for r in Corr.search([('state', '=', 'submitted'),
                                  ('employee_id', 'in', tids)], order='create_date'):
                items.append({
                    'model': 'hr.attendance.correction', 'res_id': r.id,
                    'source': 'correction',
                    'title': _('Attendance correction'),
                    'subtitle': (getattr(r, 'reason', '') or '')[:120],
                    'when': r.date.strftime('%d %b') if getattr(r, 'date', False) else '',
                    'employee': self._emp_card(r.employee_id),
                    'age': age(r),
                    'can_approve': bool(getattr(r, 'can_approve', True)),
                    'can_refuse': bool(getattr(r, 'can_refuse', True)),
                })

        # --- leaves (core; confirm state awaiting validation) — soft ---
        if 'hr.leave' in self.env:
            Leave = self.env['hr.leave']
            leaves = Leave.search([('state', '=', 'confirm'),
                                   ('employee_id', 'in', tids)], order='create_date')
            for r in leaves:
                items.append({
                    'model': 'hr.leave', 'res_id': r.id,
                    'source': 'leave',
                    'title': r.holiday_status_id.name or _('Time off'),
                    'subtitle': (r.name or '')[:120],
                    'when': self._date_span(r),
                    'employee': self._emp_card(r.employee_id),
                    'age': age(r),
                    'can_approve': True, 'can_refuse': True,
                })

        counts = {}
        for it in items:
            counts[it['source']] = counts.get(it['source'], 0) + 1
        return {'items': items, 'counts': counts, 'total': len(items)}

    def _date_span(self, rec):
        f = rec._fields
        pairs = [('date_from', 'date_to'), ('date_start', 'date_end'),
                 ('request_date_from', 'request_date_to')]
        for a, b in pairs:
            if a in f and b in f and rec[a]:
                da, db = rec[a], rec[b]
                sa = da.strftime('%d %b') if da else ''
                sb = db.strftime('%d %b') if db else ''
                return '%s → %s' % (sa, sb) if sb and sb != sa else sa
        return ''

    # ----------------------------------------------------------- metrics
    def _build_metrics(self, team):
        m = {'headcount': len(team), 'compliance': {}, 'ot': {},
             'exceptions': 0, 'upcoming_leaves': []}
        if not team:
            return m
        tids = team.ids
        from odoo import fields as _f
        today = _f.Date.context_today(self)

        # --- OT budget vs caps (sum of the team) ---
        try:
            ceil = self.env['hr.attendance.weekentry'].sudo().get_ot_ceilings(
                tids, today)
            mtd = sum((ceil.get(i, {}) or {}).get('mtd', 0) for i in tids)
            cap_m = sum((ceil.get(i, {}) or {}).get('cap_month', 0) for i in tids)
            ytd = sum((ceil.get(i, {}) or {}).get('ytd', 0) for i in tids)
            m['ot'] = {'mtd': round(mtd, 1), 'cap_month': round(cap_m, 1),
                       'ytd': round(ytd, 1),
                       'pct': round(100.0 * mtd / cap_m) if cap_m else 0}
        except Exception:
            _logger.debug('pb.team: OT ceilings unavailable', exc_info=True)

        # --- this-week shift compliance mix ---
        if 'hr.shift.planning' in self.env:
            try:
                week_start = today - _timedelta_days(today.weekday())
                week_end = week_start + _timedelta_days(6)
                Shift = self.env['hr.shift.planning'].sudo()
                shifts = Shift.search([('employee_id', 'in', tids),
                                       ('date', '>=', week_start),
                                       ('date', '<=', week_end)])
                mix = {}
                for s in shifts:
                    st = s.compliance_status or 'pending'
                    mix[st] = mix.get(st, 0) + 1
                m['compliance'] = mix
            except Exception:
                _logger.debug('pb.team: compliance unavailable', exc_info=True)

        # --- Phase-G open exceptions (soft) ---
        if 'pb.attendance.exception.engine' in self.env:
            try:
                frm = today - _timedelta_days(30)
                exc = self.env['pb.attendance.exception.engine'].sudo().get_exceptions(
                    team.sudo(), frm, today)
                m['exceptions'] = len(exc or [])
            except Exception:
                _logger.debug('pb.team: exceptions unavailable', exc_info=True)

        # --- upcoming approved leaves (next 7 days) ---
        if 'hr.leave' in self.env:
            try:
                horizon = today + _timedelta_days(7)
                Leave = self.env['hr.leave'].sudo()
                up = Leave.search([('employee_id', 'in', tids),
                                   ('state', '=', 'validate'),
                                   ('date_from', '<=', horizon),
                                   ('date_to', '>=', today)], order='date_from', limit=12)
                m['upcoming_leaves'] = [{
                    'employee': l.employee_id.name,
                    'type': l.holiday_status_id.name or '',
                    'when': self._date_span(l),
                } for l in up]
            except Exception:
                _logger.debug('pb.team: upcoming leaves unavailable', exc_info=True)
        return m

    # ------------------------------------------------------------- roster
    def _build_roster(self, team):
        if not team:
            return []
        tids = team.ids
        from odoo import fields as _f
        today = _f.Date.context_today(self)
        # per-member exception counts (soft)
        exc_by_emp = {}
        if 'pb.attendance.exception.engine' in self.env:
            try:
                frm = today - _timedelta_days(30)
                for e in self.env['pb.attendance.exception.engine'].sudo().get_exceptions(
                        team.sudo(), frm, today) or []:
                    eid = e.get('employee_id')
                    if eid:
                        exc_by_emp[eid] = exc_by_emp.get(eid, 0) + 1
            except Exception:
                _logger.debug('pb.team: roster exceptions unavailable', exc_info=True)
        # per-member week compliance gauge (soft)
        gauge_by_emp = {}
        if 'hr.shift.planning' in self.env:
            try:
                week_start = today - _timedelta_days(today.weekday())
                week_end = week_start + _timedelta_days(6)
                Shift = self.env['hr.shift.planning'].sudo()
                for s in Shift.search([('employee_id', 'in', tids),
                                       ('date', '>=', week_start),
                                       ('date', '<=', week_end)]):
                    g = gauge_by_emp.setdefault(s.employee_id.id, {'ok': 0, 'total': 0})
                    g['total'] += 1
                    if s.compliance_status in ('on_time', 'overtime'):
                        g['ok'] += 1
            except Exception:
                _logger.debug('pb.team: roster gauge unavailable', exc_info=True)
        out = []
        for emp in team.sudo():
            g = gauge_by_emp.get(emp.id)
            out.append({
                **self._emp_card(emp),
                'exceptions': exc_by_emp.get(emp.id, 0),
                'gauge': round(100.0 * g['ok'] / g['total']) if g and g['total'] else None,
            })
        out.sort(key=lambda r: (-r['exceptions'], r['name']))
        return out

    # --------------------------------------------------------------- act
    @api.model
    def act(self, model, res_id, action, note=False):
        """The ONE mutation entry point. Whitelisted (model, action) → the
        target model's OWN gated method, called AS THE REAL USER (no sudo).

        * a non-whitelisted model/action RAISES (programming/forgery guard);
        * a record outside the caller's team RAISES (defense in depth);
        * a MODEL business refusal (tier lacked, young-worker gate, …) is
          CAUGHT and returned so the cockpit shows a toast and keeps the row.
        """
        spec = _ACT_MAP.get(model)
        if not spec or action not in spec:
            raise AccessError(_(
                "Action '%(a)s' on '%(m)s' is not permitted from My Team.",
                a=action, m=model))
        if model not in self.env:
            raise UserError(_("This request type is not available."))
        rec = self.env[model].browse(int(res_id)).exists()
        if not rec:
            raise UserError(_("This request no longer exists."))

        # team scoping — the record's employee must be in MY team (or I am HR)
        emp = rec.employee_id if 'employee_id' in rec._fields else False
        if not self._is_hr():
            team = self._my_team(recursive=True)
            if not emp or emp.id not in team.ids:
                raise AccessError(_(
                    "This request is not for a member of your team."))

        call = spec[action]
        method = getattr(rec, call['method'], None)
        if method is None:
            raise UserError(_("This request type does not support that action."))
        try:
            if call['note']:
                method(note=note or False)
            else:
                method()
        except (UserError, ValidationError, AccessError) as e:
            # the model refused (tier lacked, gate hit) — surface its own words
            return {'ok': False, 'error': _extract_msg(e)}
        return {'ok': True, 'state': rec.read(['state'])[0].get('state')
                if 'state' in rec._fields else 'done'}


def _timedelta_days(n):
    from datetime import timedelta
    return timedelta(days=n)


def _extract_msg(exc):
    return getattr(exc, 'args', None) and exc.args[0] or str(exc)
