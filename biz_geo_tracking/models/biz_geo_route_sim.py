# -*- coding: utf-8 -*-
"""Route simulator — the demo / testing utility (C18.7: quarantined by design).

Sim pings are always ``source='sim'`` and flow through the SAME ping table the
real pipeline uses, so a demo exercises the real product path (never a bypass).
Routes ship ``active=False`` and are toggled on only by an admin-gated action.
"""
import json
import logging
import math
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

_EARTH_R = 6371000.0  # metres
_PINGS_PER_TICK = 4
_TICK_SECONDS = 60
_PING_SPACING = _TICK_SECONDS // _PINGS_PER_TICK  # 15 s apart


def _haversine(lon1, lat1, lon2, lat2):
    """Great-circle distance between two lon/lat points, in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * _EARTH_R * math.asin(min(1.0, math.sqrt(a)))


def _segment_lengths(coords):
    """List of segment lengths (m) and the total length of the polyline."""
    lens = []
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        lens.append(_haversine(lon1, lat1, lon2, lat2))
    return lens, sum(lens)


def _point_at_distance(coords, dist, seg_lens):
    """Linear-interpolate a [lon, lat] point ``dist`` metres along the line."""
    if dist <= 0 or len(coords) < 2:
        return list(coords[0])
    walked = 0.0
    for i, seglen in enumerate(seg_lens):
        if seglen <= 0:
            continue
        if walked + seglen >= dist:
            frac = (dist - walked) / seglen
            lon1, lat1 = coords[i]
            lon2, lat2 = coords[i + 1]
            return [lon1 + (lon2 - lon1) * frac, lat1 + (lat2 - lat1) * frac]
        walked += seglen
    return list(coords[-1])


class BizGeoRouteSim(models.Model):
    _name = 'biz.geo.route.sim'
    _description = 'Geo Route Simulator'
    _order = 'name, id'

    name = fields.Char(required=True)
    user_id = fields.Many2one('res.users', string='Driven As', required=True,
                              ondelete='cascade')
    route_geojson = fields.Text(
        string='Route (GeoJSON LineString)', required=True,
        help='A GeoJSON LineString: {"type":"LineString","coordinates":[[lon,lat],...]}')
    speed_kmh = fields.Float(string='Speed (km/h)', default=30.0)
    progress_m = fields.Float(string='Progress (m)', default=0.0)
    loop = fields.Boolean(string='Loop at end', default=True)
    active = fields.Boolean(default=True)
    session_model = fields.Char(string='Session Model')
    session_id = fields.Integer(string='Session Record ID')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

    def _coords(self):
        """Parse the GeoJSON LineString into a [[lon, lat], ...] list."""
        self.ensure_one()
        try:
            data = json.loads(self.route_geojson or '{}')
        except (ValueError, TypeError):
            raise ValidationError(_("Route %s: invalid GeoJSON.", self.name))
        coords = data.get('coordinates') if isinstance(data, dict) else data
        if not coords or len(coords) < 2:
            raise ValidationError(_("Route %s needs at least 2 points.", self.name))
        return [[float(c[0]), float(c[1])] for c in coords]

    @api.model
    def cron_advance(self):
        """Advance every active sim over the elapsed tick and emit interpolated
        ``source='sim'`` pings (throttle-bypassed internal create)."""
        Ping = self.env['biz.geo.ping'].sudo()
        now = fields.Datetime.now()
        emitted = 0
        for sim in self.search([('active', '=', True)]):
            try:
                coords = sim._coords()
            except ValidationError as e:
                _logger.warning("Route sim %s skipped: %s", sim.name, e)
                continue
            seg_lens, total = _segment_lengths(coords)
            if total <= 0:
                continue
            meters_per_tick = (sim.speed_kmh or 0.0) * 1000.0 / 60.0 * (_TICK_SECONDS / 60.0)
            start = sim.progress_m or 0.0
            for i in range(1, _PINGS_PER_TICK + 1):
                frac = i / float(_PINGS_PER_TICK)
                prog = start + meters_per_tick * frac
                if sim.loop:
                    prog = prog % total
                else:
                    prog = min(prog, total)
                lon, lat = _point_at_distance(coords, prog, seg_lens)
                Ping.create({
                    'user_id': sim.user_id.id,
                    'latitude': lat,
                    'longitude': lon,
                    'source': 'sim',
                    'session_model': sim.session_model or False,
                    'session_id': sim.session_id or False,
                    'ping_time': now - timedelta(seconds=(_PINGS_PER_TICK - i) * _PING_SPACING),
                    'company_id': sim.company_id.id,
                })
                emitted += 1
            new_prog = start + meters_per_tick
            sim.progress_m = (new_prog % total) if sim.loop else min(new_prog, total)
        if emitted:
            _logger.info("biz.geo.route.sim emitted %s simulated pings", emitted)
        return emitted
