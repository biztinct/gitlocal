# -*- coding: utf-8 -*-
"""FLEET P4 — the catalogue of switchable parts, and one customer's answers.

TWO RECORDS AND NOTHING ELSE.

`pb.feature` is the CATALOGUE: every part of the product that can be sold
separately, in plain words, with how it should behave when a customer has not
bought it. It lives on the platform's database only. Nobody's payroll depends
on it; it is a price list with a switch attached.

`pb.tenant.feature` is one customer's ANSWER to one line of that catalogue —
and only when it disagrees with the default, or when somebody deliberately
wrote the default down with a reason. No row means "whatever the catalogue
says", which is why a fleet of eleven customers who all take everything has
zero rows in this table.

WHY DEPLOY IS NOT RELEASE, WHICH IS THE WHOLE POINT OF THE PHASE. Until now the
only way to keep a half-finished part of the product away from customers was to
not ship it. That makes every release a negotiation with itself: the thing is
written, tested and sitting in the repository, and it cannot go to the one
customer who asked for it without going to the ten who did not. With a
catalogue, the code ships everywhere (P1 puts it there) and the DOOR opens for
one customer at a time — which is the same trade every serious platform makes
and the reason they can release on a Tuesday afternoon.

AND THE THING IT IS NOT. A switch takes doors off a screen. It does not put a
lock on the data behind them. Everything a person may read or write on their
own database is still decided by the roles they hold there, and a switch has
never been consulted about it. The cockpit says so on the screen; this says so
to the next person who reads the code.
"""
from odoo import api, fields, models

from .feature_rules import AREAS, DEFAULT_LOCK_TEXT, MODES, SOURCES


class PbFeature(models.Model):
    _name = 'pb.feature'
    _description = 'Payobook switchable feature'
    _order = 'sequence, id'

    #: The name the platform, the customer's database and the browser all use
    #: for the same thing. Written once and never renamed: it is stamped into
    #: every customer's settings, so a rename would silently switch a feature
    #: back on everywhere it had been switched off.
    key = fields.Char(required=True, index=True,
                      help="Short name, lower case with underscores. Never "
                           "change it once customers have been pushed.")
    name = fields.Char(required=True, translate=True,
                       help="What this is called on the screen.")
    blurb = fields.Char(translate=True,
                        help="One plain sentence: what the customer gets.")
    area = fields.Selection([(a, a.title()) for a in AREAS], default='platform',
                            required=True)
    default_on = fields.Boolean(
        default=True,
        help="Whether a customer nobody has decided about gets this.")
    mode = fields.Selection(
        [('hide', 'Hidden'), ('lock', 'Shown locked')], default='hide',
        required=True,
        help="How it looks to a customer who does not have it: gone, or on "
             "screen with a padlock and a line about how to get it.")
    lock_text = fields.Char(
        translate=True,
        help="The line under the padlock. Left empty, a standard one is used.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('key_unique', 'unique(key)', 'That feature key is already in use.'),
    ]

    @api.model
    def catalogue(self):
        """The catalogue as plain dicts, for the pure rules (rail R6)."""
        rows = self.sudo().search([])
        return [{
            'id': f.id, 'key': f.key, 'name': f.name, 'blurb': f.blurb or '',
            'area': f.area, 'default_on': f.default_on, 'mode': f.mode,
            'lock_text': f.lock_text or '', 'sequence': f.sequence,
        } for f in rows]

    def lock_sentence(self):
        self.ensure_one()
        return (self.lock_text or '').strip() or DEFAULT_LOCK_TEXT

    @api.constrains('mode')
    def _check_mode(self):
        for rec in self:
            if rec.mode not in MODES:
                raise ValueError('unknown mode %s' % rec.mode)


class PbTenantFeature(models.Model):
    _name = 'pb.tenant.feature'
    _description = 'Feature switched on or off for one customer'
    _order = 'tenant_id, feature_id'

    tenant_id = fields.Many2one('pb.tenant', required=True, ondelete='cascade',
                                index=True)
    feature_id = fields.Many2one('pb.feature', required=True, ondelete='cascade',
                                 index=True)
    #: The stored key, so a read of this table does not need the catalogue.
    #: Related and stored rather than computed on the fly: the push reads
    #: thousands of these over a fleet's lifetime and none of them should cost
    #: a join.
    key = fields.Char(related='feature_id.key', store=True, index=True)
    on = fields.Boolean(default=True)
    source = fields.Selection(
        [(s, s.title()) for s in SOURCES], default='manual', required=True,
        help="Manual is somebody deciding. Plan is reserved for the billing "
             "phase, which will set switches from what a customer pays for.")
    reason = fields.Char(help="Why, in one line. Read by whoever asks later.")
    changed_by = fields.Many2one('res.users', ondelete='set null')
    changed_at = fields.Datetime(default=fields.Datetime.now)

    _sql_constraints = [
        ('one_per_tenant_feature', 'unique(tenant_id, feature_id)',
         'That customer already has an answer for that feature.'),
    ]

    @api.model
    def overrides_for(self, tenant):
        """`{key: {'on', 'source', 'reason', …}}` for one customer."""
        rows = self.sudo().search([('tenant_id', '=', tenant.id)])
        return {r.key: {
            'on': r.on, 'source': r.source, 'reason': r.reason or '',
            'changed_by': r.changed_by.name or '',
            'changed_at': (r.changed_at.isoformat(sep=' ', timespec='minutes')
                           if r.changed_at else ''),
        } for r in rows if r.key}
