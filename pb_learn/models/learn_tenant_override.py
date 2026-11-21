# -*- coding: utf-8 -*-
"""Named slots a tenant may fill with its own facts.

Two tiers in one table:

* ``company_id = False`` — the **shipped default**, in a module data file,
  translated through ``vi_VN.po`` like every other piece of content. This is
  also the *declaration*: a key with no default row does not exist.
* ``company_id = <a company>`` — that tenant's **override**.

The hard rule, and the reason this table is deliberately small: overrides fill
NAMED SLOTS. They can never replace a lesson step, a quiz option, a consequence
card or a coach answer. The moment a tenant can edit prose you have twelve
divergent tutorials and no check can guard any of them.

Nothing here reads or writes an employee, a payslip or a pay run, which is
what makes it safe to hand to a tenant administrator.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LearnTenantOverride(models.Model):
    _name = 'learn.tenant.override'
    _description = 'Learn tenant override slot'
    _order = 'company_id, key'

    key = fields.Char(required=True, index=True)
    value = fields.Char(required=True, translate=True)
    company_id = fields.Many2one(
        'res.company', string='Company', ondelete='cascade',
        help="Empty means the shipped default for every tenant. "
             "A row with a company set overrides that default for it alone.")
    note = fields.Char(
        translate=True,
        help="What this slot is for. Shown to the tenant administrator.")

    _sql_constraints = [
        ('key_company_uniq', 'unique(key, company_id)',
         'A company can override each slot only once.'),
    ]

    @api.constrains('key', 'company_id')
    def _check_declared(self):
        """An override must fill a slot that exists.

        Without this, a typo'd key is silently inert: the tenant admin sees a
        row they filled in, the learner sees the shipped default, and nothing
        anywhere says why.
        """
        for rec in self:
            if not rec.company_id:
                continue
            declared = self.sudo().search_count([
                ('key', '=', rec.key), ('company_id', '=', False)])
            if not declared:
                raise ValidationError(self.env._(
                    "'%s' is not a tenant slot. Overrides may only fill slots the "
                    "product declares; they can never introduce new content.", rec.key))

    # ------------------------------------------------------------------
    @api.model
    def _tokens_for_lang(self, lang):
        """{key: value} for one language, defaults merged with this company's
        overrides.

        Layered in Python rather than by SQL ordering: Odoo's ``order=`` parser
        does not accept ``NULLS FIRST``, and getting the precedence wrong here
        fails silently in the direction that matters least visibly — the tenant
        sees the shipped default and nobody can tell it was ignored.
        """
        recs = self.sudo().with_context(lang=lang).search(
            [('company_id', 'in', [False, self.env.company.id])])
        tokens = {r.key: r.value for r in recs if not r.company_id}
        tokens.update({r.key: r.value for r in recs if r.company_id})
        return tokens

    @api.model
    def resolved_tokens(self):
        """{key: {en, vi}} — what the frontend's tx() substitutes into {{key}}."""
        en = self._tokens_for_lang('en_US')
        vi = self._tokens_for_lang('vi_VN')
        return {k: {'en': v, 'vi': vi.get(k) or v} for k, v in en.items()}

    @api.model
    def declared_keys(self):
        return set(self.sudo().search([('company_id', '=', False)]).mapped('key'))
