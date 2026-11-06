# -*- coding: utf-8 -*-
"""B4 — Legislation packs.

A payroll bureau runs the same national statutory rules across every client
configuration: personal-income-tax relief, social/health/unemployment insurance
rates and caps, minimum wages. When the legislature changes one of those numbers
(a decree, a resolution) the bureau must not hand-edit twenty configurations.

A *legislation pack* is a country-scoped, versioned, effective-dated bundle of
statutory parameter values. Applying a pack to a configuration writes the
matching statutory constants (matched by rule ``code``) — recording an F7
version row per change and sealing a B3 milestone so the rollout is auditable
and releasable (D-B4.1). A pack never invents structure: it only sets values on
constants that already exist in the target config, so an unmatched code is a
skipped item, never a new rule (D-B4.2).

The pack is a *reference*, not live state: a config is "aligned" to a pack when
its current constant values equal the pack's items — computed by comparison,
never stored — exactly the derive-don't-duplicate rule the release engine uses.
"""
from odoo import _, api, fields, models

# The country selection mirrors hr.formula.config so a pack and a config speak
# the same country vocabulary.
_COUNTRY = [
    ('VN', 'Vietnam'), ('ID', 'Indonesia'), ('IN', 'India'), ('SG', 'Singapore'),
    ('MY', 'Malaysia'), ('TH', 'Thailand'), ('KH', 'Cambodia'), ('PH', 'Philippines'),
]


class HrFormulaLegislationPack(models.Model):
    _name = 'hr.formula.legislation.pack'
    _description = 'Statutory Legislation Pack'
    _order = 'country_code, effective_date desc, id desc'

    name = fields.Char(required=True)
    country_code = fields.Selection(_COUNTRY, string='Country', required=True, index=True)
    version = fields.Char(required=True, help="Human label, e.g. '2025' or '2026-01'.")
    effective_date = fields.Date(string='Effective from', index=True)
    authority = fields.Char(help="The instrument the values come from "
                                 "(e.g. 'Resolution 954/2020/UBTVQH14').")
    description = fields.Text()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('superseded', 'Superseded'),
    ], default='draft', required=True, index=True, tracking=False)
    item_ids = fields.One2many('hr.formula.legislation.item', 'pack_id',
                               string='Statutory Values', copy=True)
    item_count = fields.Integer(compute='_compute_item_count')
    sequence = fields.Integer(default=10)

    def _compute_item_count(self):
        for p in self:
            p.item_count = len(p.item_ids)

    def name_get(self):
        return [(p.id, '%s · %s' % (p.name, p.version)) for p in self]


class HrFormulaLegislationItem(models.Model):
    _name = 'hr.formula.legislation.item'
    _description = 'Legislation Pack Statutory Value'
    _order = 'pack_id, sequence, id'

    pack_id = fields.Many2one('hr.formula.legislation.pack', required=True,
                              ondelete='cascade', index=True)
    # The target statutory constant is matched by this code against a config's
    # constant rules (hr.formula.rule.code, column_type='constant').
    code = fields.Char(required=True, help="Target constant code (e.g. DEDUCTSELF).")
    label = fields.Char(required=True, help="Readable name of the statutory value.")
    kind = fields.Selection([
        ('constant', 'Constant value'),
    ], default='constant', required=True)
    value = fields.Float(digits=(16, 6), help="The statutory value to set.")
    number_format = fields.Selection([
        ('number', 'Number'),
        ('currency', 'Currency'),
        ('percentage', 'Percentage'),
        ('integer', 'Integer'),
    ], default='currency', help="Display hint only — governs formatting in the cockpit.")
    note = fields.Char()
    sequence = fields.Integer(default=10)


class HrFormulaLegislationApplication(models.Model):
    _name = 'hr.formula.legislation.application'
    _description = 'Legislation Pack Application (audit)'
    _order = 'applied_date desc, id desc'

    pack_id = fields.Many2one('hr.formula.legislation.pack', required=True,
                              ondelete='cascade', index=True)
    config_id = fields.Many2one('hr.formula.config', required=True,
                                ondelete='cascade', index=True)
    applied_by_id = fields.Many2one('res.users', string='Applied by',
                                    default=lambda s: s.env.user, readonly=True)
    applied_date = fields.Datetime(default=fields.Datetime.now, readonly=True, index=True)
    item_count = fields.Integer(string='Values changed')
    milestone_id = fields.Many2one('hr.formula.config.milestone',
                                   string='Sealed milestone', ondelete='set null')
