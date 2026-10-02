# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

_FRESH_S = 30      # green freshness dot
_IDLE_S = 300      # amber → grey / "idle > 5 min"


def _initials(name):
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    return ((parts[0][0] if parts else '?') + (parts[-1][0] if len(parts) > 1 else '')).upper()


class PbDriverMap(models.AbstractModel):
    """Manager Live-Map cockpit + PWA JSON helpers.

    Drivers are employees whose linked user is in ``group_pb_driver``. Every
    metric is wrapped with :meth:`_safe`; queries are scoped to
    ``self.env.companies.ids``. Simulated positions are labelled, never mixed
    into real aggregates unlabelled (C18.7 / safety rail 4)."""
    _name = 'pb.driver.map'
    _description = 'Payobook Driver Live Map'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Driver map metric failed: %s", e)
            return default

    @api.model
    def _driver_group(self):
        """THE BROAD GROUP, since RIZE W2 D1 (ruling D16).

        Driver now implies Field staff, so asking about Field staff is asking
        about every driver AND every agronomist, site visitor or anybody else
        the business has given the phone app to. Falls back to the Driver
        group on a database whose upgrade has not landed yet, so the map is
        never empty for the wrong reason.
        """
        return self.env.ref('pb_driver_checkin.group_pb_field_staff',
                            raise_if_not_found=False) \
            or self.env.ref('pb_driver_checkin.group_pb_driver',
                            raise_if_not_found=False)

    @api.model
    def _driver_users(self):
        """The users on the map.

        R7 — `res.users.group_ids` is DIRECT membership ONLY and misses
        everybody who holds a group through `implied_ids`, which since D16 is
        every driver on this database. `res.groups.all_user_ids` is the
        transitive set (`all_implied_by_ids.user_ids`) and is what this has to
        read, or the generalisation would have silently emptied the map of the
        very people it was built for.
        """
        grp = self._driver_group()
        if not grp:
            return self.env['res.users'].browse()
        return grp.sudo().all_user_ids.filtered('active')

    @api.model
    def _driver_employees(self):
        """Employees whose user is field staff, scoped to accessible
        companies."""
        users = self._driver_users()
        if not users:
            return self.env['hr.employee'].browse()
        co_ids = self.env.companies.ids or [self.env.company.id]
        return self.env['hr.employee'].search([
            ('user_id', 'in', users.ids),
            ('company_id', 'in', co_ids),
        ], order='name')

    @api.model
    def _leave_today(self, employees):
        """{employee id: what kind of time off} for today's APPROVED leave.

        Sudo, like the Today board's own leave read (`pb_today`): the chip is
        system-derived context and a viewer without `hr.leave.type` read would
        otherwise take the whole map down on the dereference. Only the KIND is
        exposed — never a note, never a date, never anything else on the
        request.
        """
        if not employees:
            return {}
        today = fields.Date.context_today(self)
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'validate'),
            ('request_date_from', '<=', today),
            ('request_date_to', '>=', today),
        ])
        return {lv.employee_id.id: (lv.holiday_status_id.name or _('Time off'))
                for lv in leaves}

    # ------------------------------------------------------------- cockpit API
    @api.model
    def _require_officer(self):
        u = self.env.user
        if not (u.has_group('hr_attendance.group_hr_attendance_officer')
                or u.has_group('base.group_system')):
            raise AccessError(_("Driver tracking is restricted to attendance officers."))

    @api.model
    def get_live_data(self):
        self._require_officer()
        emps = self._driver_employees()
        tracker = self.env['biz.geo.tracker']
        positions = self._safe(
            lambda: tracker.get_live_positions(emps.mapped('user_id').ids), default={})

        # WHO IS OFF TODAY, so the rail can say why somebody is not moving.
        # A field person on approved leave reads as "checked out" and looks
        # identical to one who has not started — which is the question an
        # officer opens this map to answer. Its own probe, its own default
        # (R92: never a shared try/except), so a leave model this build has
        # changed cannot take the whole map down with it.
        on_leave = self._safe(lambda: self._leave_today(emps), default={})

        drivers = []
        active = idle = checked_out = 0
        hours_sum = 0.0
        hours_n = 0
        for e in emps:
            try:
                uid = e.user_id.id
                pos = positions.get(uid) or {}
                att = e.last_attendance_id
                checked_in = e.attendance_state == 'checked_in'
                age = pos.get('age_s')
                if checked_in:
                    # mutually exclusive KPIs: a stale driver is idle, not active
                    if age is None or age > _IDLE_S:
                        idle += 1
                    else:
                        active += 1
                else:
                    checked_out += 1
                th = self._safe(lambda e=e: e.hours_today, 0.0) or 0.0
                if th:
                    hours_sum += th
                    hours_n += 1
                drivers.append({
                    'id': e.id,
                    'name': e.name or '—',
                    'initials': _initials(e.name),
                    'avatar_url': '/web/image/hr.employee/%s/avatar_128' % e.id,
                    'job': (e.job_title or (e.job_id.name if e.job_id else '') or '—'),
                    'phone': e.work_phone or e.mobile_phone or '',
                    'checked_in': checked_in,
                    'since': fields.Datetime.to_string(att.check_in) if (checked_in and att) else '',
                    'last_lat': pos.get('latitude'),
                    'last_lon': pos.get('longitude'),
                    'last_ping_age_s': age,
                    'source': pos.get('source') or '',
                    'today_hours': round(th, 2),
                    'has_selfie': bool(att and att.pb_selfie_attachment_id) if att else False,
                    'selfie_url': ('/web/image/ir.attachment/%s/datas' % att.pb_selfie_attachment_id.id)
                                  if (att and att.pb_selfie_attachment_id) else '',
                    # '' when they are working; the kind of time off when
                    # they are not. One string, so the template has one thing
                    # to test and the rail has one thing to draw.
                    'on_leave': on_leave.get(e.id, ''),
                })
            except Exception as ex:
                _logger.debug("Driver row failed: %s", ex)
                continue

        kpis = {
            'active': active,
            'idle_5m': idle,
            'checked_out': checked_out,
            'avg_hours': round(hours_sum / hours_n, 1) if hours_n else 0.0,
        }
        return {
            'drivers': drivers,
            'kpis': kpis,
            'map_config': self._safe(lambda: tracker.get_map_config(), default={}),
            'is_admin': self.env.user.has_group('base.group_system'),
        }

    @api.model
    def get_driver_trail(self, employee_id, date=None):
        """Today's polyline for the playback drawer. Includes sim (labelled)."""
        self._require_officer()
        e = self.env['hr.employee'].browse(int(employee_id))
        if not e.exists() or not e.user_id:
            return {'trail': []}
        d = fields.Date.to_date(date) if date else fields.Date.context_today(self)
        start = datetime.combine(d, time.min)
        end = datetime.combine(d, time.max)
        trail = self._safe(
            lambda: self.env['biz.geo.tracker'].get_trail(
                e.user_id.id, start, end, include_sim=True),
            default=[])
        return {'trail': trail}

    # ---------------------------------------------------------------- demo mode
    @api.model
    def toggle_demo(self, active):
        """Admin-only: flip the seed route simulators on/off. ON checks the
        demo drivers in via the REAL attendance path; OFF checks them out."""
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Demo mode is restricted to administrators."))
        Sim = self.env['biz.geo.route.sim'].sudo()
        seed_ids = []
        for xmlid in ('pb_driver_checkin.route_sim_hanoi', 'pb_driver_checkin.route_sim_hcmc'):
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec:
                seed_ids.append(rec.id)
        sims = Sim.browse(seed_ids)
        active = bool(active)
        for sim in sims:
            # active_test=False is load-bearing: the seed driver and employee ship
            # ARCHIVED (see data/demo_routes.xml) so no install carries a live
            # driver account. A plain search would silently find nothing here and
            # demo mode would do nothing at all, with no error to explain why.
            emp = self.env['hr.employee'].sudo().with_context(active_test=False).search(
                [('user_id', '=', sim.user_id.id)], limit=1)
            if not emp:
                continue
            # Wake the pair BEFORE punching: attendance on an archived employee is
            # not something to rely on.
            if active:
                sim.user_id.sudo().write({'active': True})
                emp.write({'active': True})
            # seed at the route's first point so check-in lands near the sim;
            # if the route can't be parsed, punch with no location (never 0,0)
            geo = {'mode': 'gps'}
            try:
                coords = sim._coords()
                geo['longitude'], geo['latitude'] = coords[0][0], coords[0][1]
            except Exception:
                pass
            if active and emp.attendance_state != 'checked_in':
                emp._attendance_action_change(geo)
            elif not active and emp.attendance_state == 'checked_in':
                emp._attendance_action_change(geo)
            sim.active = active
            if active:
                sim.progress_m = 0.0
            else:
                # Back to sleep — but only after the check-out above is recorded,
                # so demo mode leaves no driver account awake behind it.
                emp.write({'active': False})
                sim.user_id.sudo().write({'active': False})
        return {'ok': True, 'active': active, 'count': len(sims)}
