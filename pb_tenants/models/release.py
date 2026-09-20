# -*- coding: utf-8 -*-
"""A named release: a photograph of what the master ran at one moment.

WHY A RECORD AND NOT A NUMBER SOMEWHERE. Before this, "in step" meant "the same
as the master, right now" — a moving target. The master gets a fix at 11:00 and
every customer is behind at 11:01, through no decision of anybody's. A release
freezes the answer: this list, at these versions, is what the fleet is aiming
at, and it changes when somebody cuts a new one.

The photograph includes the parts a customer never gets. The reader is the
platform owner, and showing him an edited master would make the count on the
screen disagree with the count on his own database.
"""
import json

from odoo import api, fields, models


class PbRelease(models.Model):
    _name = 'pb.release'
    _description = 'Payobook release'
    _order = 'captured_at desc, id desc'

    name = fields.Char(required=True, index=True,
                       help="Dated name, e.g. 2026.09.03.")
    captured_at = fields.Datetime(default=fields.Datetime.now, required=True)
    notes = fields.Text(help="What changed, in plain words. Customers read this.")
    #: JSON `{module name: version}` for everything installed on the master when
    #: the release was cut. Text rather than a typed column so the record can be
    #: read back on a database whose framework has moved on.
    snapshot = fields.Text(default='{}')
    module_count = fields.Integer()
    is_current = fields.Boolean(
        index=True, help="Exactly one release is current; cutting a new one "
                         "stands the previous one down.")
    cut_by = fields.Many2one('res.users', ondelete='set null')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'A release with that name already exists.'),
    ]

    def snapshot_dict(self):
        """The photograph, as a plain dict. Never raises on a damaged record."""
        self.ensure_one()
        try:
            data = json.loads(self.snapshot or '{}')
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    @api.model
    def current(self):
        """The release the fleet is aiming at, or an empty recordset."""
        return self.sudo().search([('is_current', '=', True)], limit=1)

    def make_current(self):
        """Become the one current release. The only way that field is written."""
        self.ensure_one()
        others = self.sudo().search([('is_current', '=', True), ('id', '!=', self.id)])
        if others:
            others.write({'is_current': False})
        self.sudo().write({'is_current': True})
        return self
