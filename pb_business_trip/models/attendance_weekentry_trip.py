# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _


class AttendanceWeekEntryTrip(models.TransientModel):
    """Virtual trip-presence overlay for the Weekly Entry grid (C18.4).

    Trip days arrive on the row as ``flags.trip_days=[iso,…]`` (the grid renders
    an indigo BT chip and locks the REG cell) and a REG write on a trip day is
    refused SERVER-SIDE — trip presence is system-derived, never hand-entered.
    """
    _inherit = 'hr.attendance.weekentry'

    @api.model
    def get_week_entries(self, week_start_str=False, department_id=False, search=False):
        data = super().get_week_entries(week_start_str, department_id, search)
        rows = data.get('rows') or []
        if not rows:
            return data
        trip_map = self.env['pb.business.trip']._get_trip_day_map(
            [r['id'] for r in rows], data['week_start'], data['week_end'])
        if not trip_map:
            return data
        badge_title = _('On authorized trip — attendance is automatic.')
        for r in rows:
            days = trip_map.get(r['id'])
            if not days:
                continue
            flags = r.setdefault('flags', {})
            flags['trip_days'] = sorted(days)
            # indigo "BT" chip on each trip day — the generic WeekGrid renders
            # a consumer-supplied day badge from flags.day_badges (C18.1: the
            # engine stays product-neutral, the trip meaning lives here).
            badges = flags.setdefault('day_badges', {})
            for iso in days:
                badges[iso] = {'label': _('BT'), 'color': '#5A4BB0',
                               'title': badge_title}
                cell = (r.get('cells') or {}).get(iso)
                reg = (cell or {}).get('measures', {}).get('reg') if cell else None
                if reg:
                    reg['editable'] = False
                    reg['lock_reason'] = badge_title
        return data

    def _save_reg(self, emp, d, hours, token, att_map, shift_map):
        # a REG write on an approved trip day is refused (the grid already locks
        # the cell; a crafted RPC must not hand-enter attendance over a trip)
        trip_days = self.env['pb.business.trip']._get_trip_day_map([emp.id], d, d)
        if d.isoformat() in trip_days.get(emp.id, set()):
            return False, 'trip'
        return super()._save_reg(emp, d, hours, token, att_map, shift_map)
