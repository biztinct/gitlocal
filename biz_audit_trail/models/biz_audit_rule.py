# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Which fields to audit on which model — pure configuration (DATA per deploy).

The watched-field set is read on EVERY write of every consumer model, so it is
``ormcache``d per model name and the cache is cleared on any rule mutation
(create/write/unlink). A hot write path therefore pays one cached dict lookup,
never a table scan (the C18.41 registry-load lesson: a per-write scan is a
self-inflicted performance storm).
"""

from odoo import api, fields, models, tools


class BizAuditRule(models.Model):
    _name = 'biz.audit.rule'
    _description = 'Audit Rule'
    _order = 'model_name, id'

    name = fields.Char(required=True)
    model_name = fields.Char(
        string='Model', required=True, index=True,
        help="Technical model name whose fields are audited, e.g. hr.employee.")
    field_names = fields.Char(
        string='Fields', required=True,
        help="Comma-separated technical field names to audit, "
             "e.g. department_id,job_title,parent_id.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        help="Left blank, the rule applies to every company (the usual case). "
             "Field selection is company-agnostic; this is metadata for a future "
             "per-company console filter.")

    # ------------------------------------------------------------ cached lookup
    @api.model
    @tools.ormcache('model_name')
    def _watched_fields(self, model_name):
        """The union of field names any ACTIVE rule watches for ``model_name``.

        ormcached — cleared by create/write/unlink below. The mixin calls this on
        every consumer write; an empty result (no rule) caches too, so an
        unwatched model pays only a cached lookup + an empty-set intersection.
        """
        rules = self.sudo().search([
            ('model_name', '=', model_name), ('active', '=', True)])
        out = set()
        for rule in rules:
            for fname in (rule.field_names or '').split(','):
                fname = fname.strip()
                if fname:
                    out.add(fname)
        return frozenset(out)

    # rule changes must invalidate the cache immediately (belt-and-braces: the
    # registry cache is process-wide, so clear it rather than reason about keys)
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        self.env.registry.clear_cache()
        return recs

    def write(self, vals):
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res
