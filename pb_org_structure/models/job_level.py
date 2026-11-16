# -*- coding: utf-8 -*-
"""`pb.job.level` — the named ladder of job levels, set once.

The order of the ladder is `sequence` (lowest level first). A level with no
company is offered to every company; one with a company only there. Levels are
words a company chooses ("Associate", "Senior", "Lead", "Head of"), not
numbers, so nothing about pay is implied by them in this phase.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PbJobLevel(models.Model):
    _name = 'pb.job.level'
    _description = 'Job level'
    _order = 'sequence, id'

    name = fields.Char(string='Level', required=True, translate=True)
    sequence = fields.Integer(string='Order', default=10)
    description = fields.Text(string='What this level means')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help='Leave empty to offer this level to every company.')
    active = fields.Boolean(default=True)
    job_ids = fields.One2many('hr.job', 'pb_level_id', string='Jobs at this level')
    job_count = fields.Integer(string='Jobs', compute='_compute_job_count')

    @api.depends('job_ids')
    def _compute_job_count(self):
        for level in self:
            level.job_count = len(level.job_ids)

    @api.constrains('name', 'company_id')
    def _check_unique_name(self):
        for level in self:
            clash = self.search_count([
                ('id', '!=', level.id),
                ('name', '=ilike', (level.name or '').strip()),
                ('company_id', '=', level.company_id.id or False),
            ])
            if clash:
                raise ValidationError(_(
                    "There is already a level called \"%s\".", level.name))

    def unlink(self):
        used = self.with_context(active_test=False).filtered(
            lambda lv: lv.sudo().with_context(active_test=False).job_ids)
        if used:
            raise UserError(_(
                "\"%s\" is used by a job. Move the job to another level first, "
                "or archive the level instead.", used[0].name))
        return super().unlink()
