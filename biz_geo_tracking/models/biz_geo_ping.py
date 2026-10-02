# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class BizGeoPing(models.Model):
    """Append-only stream of geo-location pings.

    Deliberately generic: it carries a polymorphic ``session_model`` /
    ``session_id`` binding so any consuming module (driver check-in, field
    service, delivery) can attach a ping to whatever record owns it, without
    this engine knowing anything about that model. No ``mail.thread`` — this is
    a high-volume table.
    """
    _name = 'biz.geo.ping'
    _description = 'Geo Tracking Ping'
    _order = 'ping_time desc, id desc'
    _rec_name = 'ping_time'

    user_id = fields.Many2one(
        'res.users', string='User', required=True, index=True,
        ondelete='cascade')
    session_model = fields.Char(string='Session Model', index=True)
    session_id = fields.Integer(string='Session Record ID', index=True)

    latitude = fields.Float(string='Latitude', digits=(10, 7), required=True)
    longitude = fields.Float(string='Longitude', digits=(10, 7), required=True)
    accuracy_m = fields.Float(string='Accuracy (m)')
    speed_mps = fields.Float(string='Speed (m/s)')
    heading_deg = fields.Float(string='Heading (deg)')
    battery_pct = fields.Float(string='Battery (%)')

    source = fields.Selection(
        [('real', 'Real'), ('sim', 'Simulated')],
        string='Source', default='real', required=True, index=True)
    ping_time = fields.Datetime(
        string='Ping Time', required=True, index=True,
        default=fields.Datetime.now)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    @api.constrains('latitude', 'longitude')
    def _check_coords(self):
        for ping in self:
            if not (-90.0 <= ping.latitude <= 90.0):
                raise ValidationError(_(
                    "Latitude %(lat)s is out of range [-90, 90].",
                    lat=ping.latitude))
            if not (-180.0 <= ping.longitude <= 180.0):
                raise ValidationError(_(
                    "Longitude %(lon)s is out of range [-180, 180].",
                    lon=ping.longitude))

    def init(self):
        # Composite index for "latest ping(s) per user" — the hot query for
        # both get_live_positions and the throttle search_count.
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS biz_geo_ping_user_time_idx
            ON biz_geo_ping (user_id, ping_time DESC)
        """)
