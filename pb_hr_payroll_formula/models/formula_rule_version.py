# -*- coding: utf-8 -*-
"""Formula version history (F7).

Append-only snapshots of a formula rule's versioned fields, captured by the
`write()` override on `hr.formula.rule`. Versions store the OUTGOING (pre-write)
state — i.e. each row is what the rule looked like *before* the edit that
created the row. The live rule always holds the newest state; the version rows
are its past. Config-level milestones anchor "compare to activation" views.

These live in the headless engine module (not the studio) so history is
captured no matter which caller mutates a rule — imports, shell fixes, the
cockpit, anything.
"""
from odoo import api, fields, models


class HrFormulaRuleVersion(models.Model):
    _name = 'hr.formula.rule.version'
    _description = 'Formula Rule Version Snapshot'
    _order = 'rule_id, seq desc, id desc'
    _rec_name = 'seq'

    rule_id = fields.Many2one(
        'hr.formula.rule', string='Rule', required=True,
        index=True, ondelete='cascade')
    config_id = fields.Many2one(
        'hr.formula.config', string='Configuration',
        related='rule_id.config_id', store=True, index=True)

    seq = fields.Integer(
        string='Version', required=True,
        help="Per-rule monotonic version number (1-based).")
    user_id = fields.Many2one(
        'res.users', string='Changed by', default=lambda s: s.env.user,
        readonly=True)
    # create_date / create_uid are provided by the ORM.

    # The outgoing formula as plain Excel text — kept in its own column so the
    # token diff can read it without unpacking JSON.
    excel_formula = fields.Text(string='Formula (Excel)')
    # Everything else about the rule at snapshot time: name/code/category/type/
    # number_format/appears_on_payslip/column_letter/constant_value.
    snapshot_json = fields.Text(string='Field Snapshot (JSON)')

    reason = fields.Selection([
        ('edit', 'Edited'),
        ('bulk', 'Bulk edit'),
        ('import', 'Excel import'),
        ('fill', 'Drag-fill'),
        ('restore', 'Restored'),
        ('lifecycle', 'Lifecycle'),
        ('rename', 'Renamed'),
        ('legislation', 'Legislation pack'),
        ('merge', 'Branch merge'),
        ('sync', 'Master sync'),
    ], string='Reason', default='edit', required=True, index=True)
    note = fields.Char(string='Note')


class HrFormulaConfigMilestone(models.Model):
    _name = 'hr.formula.config.milestone'
    _description = 'Formula Configuration Milestone'
    _order = 'milestone_date desc, id desc'

    config_id = fields.Many2one(
        'hr.formula.config', string='Configuration', required=True,
        index=True, ondelete='cascade')
    name = fields.Char(string='Milestone', required=True)
    milestone_date = fields.Datetime(
        string='Date', required=True, default=fields.Datetime.now, index=True)
    user_id = fields.Many2one(
        'res.users', string='By', default=lambda s: s.env.user, readonly=True)
    # W86 — version-id boundary at seal time. Odoo Datetime domain comparisons
    # are second-granular, so a milestone sealed in the SAME second as the edits
    # it caps cannot be separated from them by timestamp (fatal for one-action
    # rollback, which edits + seals atomically). The max hr.formula.rule.version
    # id at seal time is an exact, collision-free boundary: "changed since this
    # milestone" == versions with id > version_hwm. -1 = legacy milestone with no
    # hwm recorded → callers fall back to the timestamp boundary.
    version_hwm = fields.Integer(string='Version high-water mark', default=-1)

    @api.model
    def record(self, config, name):
        """Create a milestone for `config` (a record or id). Returns the row."""
        config_id = config.id if hasattr(config, 'id') else int(config)
        return self.create({'config_id': config_id, 'name': name})
