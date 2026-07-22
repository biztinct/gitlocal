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
        return self.env.ref('pb_driver_checkin.group_pb_driver', raise_if_not_found=False)

    @api.model
    def _driver_users(self):
        """res.users in the driver group. Query via the searchable direct
        group_ids M2M (Odoo 19; res.groups.users is unreliable)."""
        grp = self._driver_group()
        if not grp:
            return self.env['res.users'].browse()
        return self.env['res.users'].sudo().search([('group_ids', 'in', grp.ids)])

    @api.model
    def _driver_employees(self):
        """Employees whose user is a driver, scoped to accessible companies."""
        users = self._driver_users()
        if not users:
            return self.env['hr.employee'].browse()
        co_ids = self.env.companies.ids or [self.env.company.id]
        return self.env['hr.employee'].search([
            ('user_id', 'in', users.ids),
            ('company_id', 'in', co_ids),
        ], order='name')

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
                    if age is None or age > _IDLE_S:
                        idle += 1
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
            emp = self.env['hr.employee'].sudo().search(
                [('user_id', '=', sim.user_id.id)], limit=1)
            if not emp:
                continue
            geo = {'latitude': 0.0, 'longitude': 0.0, 'mode': 'gps'}
            # seed at the route's first point so check-in lands near the sim
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
        return {'ok': True, 'active': active, 'count': len(sims)}
