# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

# Server-side ping throttle: reject a second ping from the same user within
# this many seconds (battery courtesy + abuse guard). See C18.5 / safety rail 1.
_THROTTLE_SECONDS = 5

_DEFAULT_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
_DEFAULT_TILE_ATTRIBUTION = '© OpenStreetMap contributors'
_DEFAULT_RETENTION_DAYS = 90


class BizGeoTracker(models.AbstractModel):
    """Public, reusable API for the geo-tracking engine.

    Every consumer (driver check-in, field service, delivery) goes through this
    facade — it owns identity stamping, coordinate validation, throttling and
    the aggregate queries. Nothing here references hr.*, pb_* or Vietnam.
    """
    _name = 'biz.geo.tracker'
    _description = 'Geo Tracker Service'

    # ------------------------------------------------------------------ config
    @api.model
    def get_map_config(self):
        """Tile config, so switching to a keyed provider is a param swap."""
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'tile_url': ICP.get_param('biz_geo.tile_url', _DEFAULT_TILE_URL),
            'tile_attribution': ICP.get_param(
                'biz_geo.tile_attribution', _DEFAULT_TILE_ATTRIBUTION),
        }

    # -------------------------------------------------------------- write path
    @api.model
    def _coerce_float(self, val, field):
        """Server-side numeric validation — client values are never trusted."""
        if val in (None, False, ''):
            return 0.0
        try:
            return float(val)
        except (TypeError, ValueError):
            raise ValidationError(_("Field %(f)s must be numeric.", f=field))

    @api.model
    def register_ping(self, vals):
        """Create a ping for the CURRENT user.

        ``user_id`` is always stamped from the session — any ``user_id`` passed
        in ``vals`` is ignored (safety rail 1). Coordinates are range-checked
        and a sub-5s repeat from the same user is rejected.
        """
        vals = dict(vals or {})
        uid = self.env.uid

        lat = self._coerce_float(vals.get('latitude'), 'latitude')
        lon = self._coerce_float(vals.get('longitude'), 'longitude')
        if not (-90.0 <= lat <= 90.0):
            raise ValidationError(_("Latitude out of range."))
        if not (-180.0 <= lon <= 180.0):
            raise ValidationError(_("Longitude out of range."))

        # Throttle: one search_count on the composite index.
        cutoff = fields.Datetime.now() - timedelta(seconds=_THROTTLE_SECONDS)
        recent = self.env['biz.geo.ping'].sudo().search_count([
            ('user_id', '=', uid),
            ('ping_time', '>=', cutoff),
            ('source', '=', 'real'),
        ])
        if recent:
            raise UserError(_("Ping throttled — please wait a moment."))

        create_vals = {
            'user_id': uid,
            'latitude': lat,
            'longitude': lon,
            'accuracy_m': self._coerce_float(vals.get('accuracy_m'), 'accuracy_m'),
            'speed_mps': self._coerce_float(vals.get('speed_mps'), 'speed_mps'),
            'heading_deg': self._coerce_float(vals.get('heading_deg'), 'heading_deg'),
            'battery_pct': self._coerce_float(vals.get('battery_pct'), 'battery_pct'),
            'source': 'real',
            'session_model': vals.get('session_model') or False,
            'session_id': int(vals['session_id']) if vals.get('session_id') else False,
        }
        ping = self.env['biz.geo.ping'].create(create_vals)
        return {'id': ping.id, 'ping_time': fields.Datetime.to_string(ping.ping_time)}

    # --------------------------------------------------------------- read path
    @api.model
    def get_live_positions(self, user_ids):
        """Latest ping per user in ONE query (DISTINCT ON). Returns a dict
        keyed by user id → {lat, lon, ping_time, age_s, source, ...}."""
        user_ids = [int(u) for u in (user_ids or [])]
        if not user_ids:
            return {}
        self.env.cr.execute("""
            SELECT DISTINCT ON (user_id)
                   user_id, latitude, longitude, source, ping_time,
                   accuracy_m, speed_mps, heading_deg, battery_pct
            FROM biz_geo_ping
            WHERE user_id = ANY(%s)
            ORDER BY user_id, ping_time DESC
        """, (user_ids,))
        now = fields.Datetime.now()
        out = {}
        for row in self.env.cr.dictfetchall():
            pt = fields.Datetime.to_datetime(row['ping_time'])
            out[row['user_id']] = {
                'user_id': row['user_id'],
                'latitude': row['latitude'],
                'longitude': row['longitude'],
                'source': row['source'],
                'ping_time': fields.Datetime.to_string(pt),
                'age_s': int((now - pt).total_seconds()) if pt else None,
                'accuracy_m': row['accuracy_m'],
                'speed_mps': row['speed_mps'],
                'heading_deg': row['heading_deg'],
                'battery_pct': row['battery_pct'],
            }
        return out

    @api.model
    def get_trail(self, user_id, date_from, date_to, include_sim=False):
        """Ordered [lat, lon, iso_time] list for polylines."""
        domain = [
            ('user_id', '=', int(user_id)),
            ('ping_time', '>=', date_from),
            ('ping_time', '<=', date_to),
        ]
        if not include_sim:
            domain.append(('source', '=', 'real'))
        pings = self.env['biz.geo.ping'].search(domain, order='ping_time asc')
        return [
            [p.latitude, p.longitude, fields.Datetime.to_string(p.ping_time)]
            for p in pings
        ]

    # ----------------------------------------------------------- housekeeping
    @api.model
    def gc_pings(self):
        """Cron: delete pings older than biz_geo.retention_days (default 90)."""
        days = self.env['ir.config_parameter'].sudo().get_param(
            'biz_geo.retention_days', _DEFAULT_RETENTION_DAYS)
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = _DEFAULT_RETENTION_DAYS
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.env['biz.geo.ping'].sudo().search([('ping_time', '<', cutoff)])
        count = len(old)
        if old:
            old.unlink()
        _logger.info("biz.geo.tracker.gc_pings removed %s pings (< %s days)", count, days)
        return count
