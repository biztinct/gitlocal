# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _

_TRIP_COLOR = '#7c3aed'


class AttendanceTimecardTrip(models.TransientModel):
    """Virtual trip-presence overlay for the Timecards Gantt (C18.4).

    Approved trip days are injected at READ time — never materialized as
    hr.attendance rows. An empty trip day gets a full-width violet 'Business
    Trip' bar; a day the traveller ALSO punched keeps its real bars plus a trip
    tag. A 'trip' legend entry appears whenever any trip bar is shown.
    """
    _inherit = 'hr.attendance.timecard'

    @api.model
    def get_timecard_data(self, employee_id=False, week_start_str=False,
                          department_id=False, show_only_with_hours=False):
        data = super().get_timecard_data(
            employee_id, week_start_str, department_id, show_only_with_hours)
        emps = data.get('employees') or []
        if not emps:
            return data
        trip_map = self.env['pb.business.trip']._get_trip_day_map(
            [e['id'] for e in emps], data.get('week_start'), data.get('week_end'))
        if not trip_map:
            return data

        any_trip = False
        for e in emps:
            days = trip_map.get(e['id'])
            if not days:
                continue
            e.setdefault('days', {})
            for iso in days:
                card = e['days'].get(iso)
                if not card:
                    card = {'entries': [], 'regular': 0, 'overtime': 0,
                            'total': 0, 'ot_type': False, 'ot_label': ''}
                    e['days'][iso] = card
                if not card.get('entries'):
                    card['entries'] = [{
                        'id': False, 'bar_type': 'trip', 'bar_left': 0,
                        'bar_width': 100, 'is_trip': True, 'is_active': False,
                        'check_in': '', 'check_out': '', 'worked': 0,
                        'label': _('Business Trip'),
                    }]
                    card['ot_type'] = 'trip'
                    card['ot_label'] = _('Business Trip')
                card['is_trip'] = True
                any_trip = True

        if any_trip:
            legend = data.setdefault('ot_legend', [])
            if not any(l.get('type') == 'trip' for l in legend):
                legend.append({'type': 'trip', 'name': _('Business Trip'),
                               'rate': '—', 'color': _TRIP_COLOR})
        return data
