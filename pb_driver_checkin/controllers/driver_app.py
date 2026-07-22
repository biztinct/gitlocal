# -*- coding: utf-8 -*-
import base64
import logging

from odoo import fields, http
from odoo.http import request
from odoo.exceptions import AccessError, UserError

from odoo.addons.biz_geo_tracking.controllers.pwa_shell import GeoPwaShell

_logger = logging.getLogger(__name__)

_SCOPE = '/driver'
_THEME = '#0b1f3a'
_MAX_SELFIE_BYTES = 5 * 1024 * 1024
_IMAGE_MIMES = ('image/jpeg', 'image/png', 'image/webp')


class DriverApp(http.Controller, GeoPwaShell):

    # ------------------------------------------------------------- helpers
    def _is_driver(self):
        u = request.env.user
        return (u.has_group('pb_driver_checkin.group_pb_driver')
                or u.has_group('hr_attendance.group_hr_attendance_officer'))

    def _employee(self):
        return request.env.user.employee_id

    def _require_driver_employee(self):
        if not self._is_driver():
            raise AccessError("You do not have driver access.")
        emp = self._employee()
        if not emp:
            raise UserError("No employee is linked to your user account.")
        return emp

    def _state_payload(self, emp):
        att = emp.last_attendance_id
        checked_in = emp.attendance_state == 'checked_in'
        last_ping = request.env['biz.geo.ping'].sudo().search(
            [('user_id', '=', request.env.uid)], order='ping_time desc', limit=1)
        age = None
        if last_ping:
            age = int((fields.Datetime.now() - last_ping.ping_time).total_seconds())
        return {
            'employee': emp.name,
            'employee_id': emp.id,
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
            'attendance_state': emp.attendance_state,
            'checked_in': checked_in,
            'checked_in_since': fields.Datetime.to_string(att.check_in) if (checked_in and att and att.check_in) else '',
            'today_hours': round(emp.hours_today or 0.0, 2),
            'last_ping_age': age,
            'has_selfie': bool(att and att.pb_selfie_attachment_id) if att else False,
        }

    # ------------------------------------------------------------- PWA shell
    @http.route('/driver', type='http', auth='user', methods=['GET'], website=False)
    def driver_home(self, **kw):
        if not self._is_driver():
            return request.render('pb_driver_checkin.driver_no_access')
        if not self._employee():
            return request.render('pb_driver_checkin.driver_no_employee')
        return request.render('pb_driver_checkin.driver_app_page', {
            'user_name': request.env.user.name,
            'lang': (request.env.lang or 'en_US').split('_')[0],
        })

    @http.route('/driver/manifest.webmanifest', type='http', auth='public',
                methods=['GET'], website=False, sitemap=False)
    def driver_manifest(self, **kw):
        icons = [
            {'src': '/pb_driver_checkin/static/description/icon-192.png',
             'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'},
            {'src': '/pb_driver_checkin/static/description/icon-512.png',
             'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
        ]
        return self._make_manifest(
            'Payobook Driver', 'Driver', _SCOPE, _SCOPE,
            theme_color=_THEME, bg_color='#0b1f3a', icons=icons)

    @http.route('/driver/service-worker.js', type='http', auth='public',
                methods=['GET'], website=False, sitemap=False)
    def driver_sw(self, **kw):
        return self._make_service_worker(_SCOPE)

    # ------------------------------------------------------------- JSON API
    @http.route('/driver/state', type='jsonrpc', auth='user')
    def driver_state(self, **kw):
        emp = self._require_driver_employee()
        return self._state_payload(emp)

    @http.route('/driver/check_in_out', type='jsonrpc', auth='user')
    def driver_check_in_out(self, latitude=None, longitude=None, accuracy=None, **kw):
        emp = self._require_driver_employee()
        tracker = request.env['biz.geo.tracker']
        lat = tracker._coerce_float(latitude, 'latitude')
        lon = tracker._coerce_float(longitude, 'longitude')
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            raise UserError("Invalid GPS coordinates.")
        # geo_information keys map to in_<key>/out_<key>; 'mode' → in_mode/out_mode
        emp._attendance_action_change({
            'latitude': lat, 'longitude': lon, 'mode': 'gps',
        })
        return self._state_payload(emp)

    @http.route('/driver/ping', type='jsonrpc', auth='user')
    def driver_ping(self, latitude=None, longitude=None, accuracy=None,
                    speed=None, heading=None, battery=None, **kw):
        emp = self._require_driver_employee()
        if emp.attendance_state != 'checked_in':
            return {'error': 'not_checked_in'}
        att = emp.last_attendance_id
        try:
            res = request.env['biz.geo.tracker'].register_ping({
                'latitude': latitude, 'longitude': longitude,
                'accuracy_m': accuracy, 'speed_mps': speed,
                'heading_deg': heading, 'battery_pct': battery,
                'session_model': 'hr.attendance',
                'session_id': att.id if att else False,
            })
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e)}
        return {'ok': True, 'ping': res}

    @http.route('/driver/selfie', type='jsonrpc', auth='user')
    def driver_selfie(self, image_b64=None, mimetype=None, **kw):
        emp = self._require_driver_employee()
        att = emp.last_attendance_id
        if not att or att.check_out:
            return {'error': 'no_active_checkin'}
        if not image_b64:
            return {'error': 'no_image'}
        if mimetype not in _IMAGE_MIMES:
            return {'error': 'bad_mimetype'}
        try:
            raw = base64.b64decode(image_b64)
        except Exception:
            return {'error': 'bad_image'}
        if len(raw) > _MAX_SELFIE_BYTES:
            return {'error': 'too_large'}
        ext = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}[mimetype]
        attach = request.env['ir.attachment'].sudo().create({
            'name': 'driver_selfie_%s.%s' % (att.id, ext),
            'datas': image_b64,
            'mimetype': mimetype,
            'res_model': 'hr.attendance',
            'res_id': att.id,
        })
        att.sudo().pb_selfie_attachment_id = attach.id
        return {'ok': True, 'attachment_id': attach.id}
