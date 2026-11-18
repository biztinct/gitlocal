# -*- coding: utf-8 -*-
"""Which pay item feeds which line of a government form.

THE CUSTOMER'S OWN FIGURES (owner ruling G2). A line is filled from the pay
items of the customer's own pay schemes — what their pay runs worked out —
never from a ready-made country pack. HR says once which item goes where; the
reader adds those items up on the finished payslips.

ONE ITEM, SEVERAL LINES. Unlike a fund payee (`pb.fund.payee.item`, one item
one payee — a fund would be paid twice), a form may report the same figure on
two lines and two forms may report the same item: "Income tax" is both the
tax withheld on the monthly return and, later, a line of the year-end
certificate. So the only uniqueness is (line, item).

WHERE A FIGURE IS READ FROM (`source`):

  payslip_line    the payslip line the item printed (by the payslip's scheme
                  and the line's code, as fund payments reads it);
  computed_value  the value the scheme worked out, stored on the payslip
                  (`hr.payslip.formula_computed_values`) — for items that are
                  not printed on the payslip (tax bases, a tax status), WDGAP
                  S2F-6.

COMPANY AND SCHEME. A mapping row belongs to the item's scheme and so to the
scheme's company; the record rule keeps a company's rows to its own people.

SUGGEST NEVER SAVES. It proposes (line, item) pairs from the line's own words
and pay roles; HR ticks what is right and saves.
"""
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

SOURCES = [('payslip_line', 'Payslip line'),
           ('computed_value', 'Worked-out value')]
SIGNS = [('add', 'Add'), ('subtract', 'Take away')]

#: Value kinds a payslip line exists for (VALUEKIND).
NUMBER_KINDS = ('money', 'decimal', 'integer', 'quantity', 'rate')


def _norm(text):
    text = (text or '').lower()
    text = re.sub(r'[\s_\-./()%:]+', ' ', text)
    return ' '.join(text.split())


class PbGovFormMap(models.Model):
    _name = 'pb.gov.form.map'
    _description = 'Pay item on a government form line'
    _order = 'form_id, line_id, id'

    line_id = fields.Many2one('pb.gov.form.line', string='Form line',
                              required=True, index=True, ondelete='cascade')
    form_id = fields.Many2one(related='line_id.form_id', store=True, index=True)
    rule_id = fields.Many2one('hr.formula.rule', string='Pay item', required=True,
                              index=True, ondelete='cascade')
    config_id = fields.Many2one(related='rule_id.config_id', store=True,
                                string='Pay scheme', index=True)
    company_id = fields.Many2one('res.company', compute='_compute_company',
                                 store=True, index=True)
    code = fields.Char(related='rule_id.code', store=True)
    source = fields.Selection(SOURCES, required=True, default='payslip_line')
    sign = fields.Selection(SIGNS, required=True, default='add')
    share_pct = fields.Float(string='Share (%)', default=100.0, digits=(16, 4))

    _line_rule_uniq = models.Constraint(
        'unique(line_id, rule_id)', 'This pay item is already on this line.')

    @api.depends('rule_id.config_id.company_id')
    def _compute_company(self):
        for row in self:
            row.company_id = row.rule_id.config_id.company_id

    @api.constrains('share_pct')
    def _check_share(self):
        for row in self:
            if not 0 < (row.share_pct or 0) <= 100:
                raise ValidationError(_("The share is a percentage above 0 and up to 100."))

    @api.constrains('line_id', 'rule_id')
    def _check_line(self):
        for row in self:
            if not row.line_id.mappable or row.line_id.base_line_id:
                raise ValidationError(_(
                    "“%s” is worked out from other lines, so no pay item can be put on it.",
                    row.line_id.label))
            if not row.rule_id.config_id.company_id:
                raise ValidationError(_("“%s” belongs to no company.",
                                        row.rule_id.name or row.rule_id.code))

    def _pb_factor(self):
        self.ensure_one()
        factor = (self.share_pct or 100.0) / 100.0
        return -factor if self.sign == 'subtract' else factor

    # ------------------------------------------------------------- helpers
    @api.model
    def _pb_default_source(self, rule):
        """Not printed on the payslip, or not a number → only the scheme's
        own worked-out value can be read (S2F-6)."""
        kind = rule.value_kind or 'money'
        if not rule.appears_on_payslip or kind not in NUMBER_KINDS:
            return 'computed_value'
        return 'payslip_line'

    @api.model
    def _pb_item_warning(self, rule, source):
        if source == 'payslip_line' and self._pb_default_source(rule) == 'computed_value':
            return _("This item is not printed on payslips, so it is read from the value the scheme worked out.")
        return ''

    @api.model
    def _pb_candidate_rules(self, company, form):
        """Pay items of the company's pay schemes for the form's country."""
        configs = self.env['hr.formula.config'].sudo().with_context(active_test=False).search([
            ('company_id', '=', company.id)])
        configs = configs.filtered(
            lambda c: (c.country_code or '').upper() == (form.country_code or '').upper())
        if not configs:
            return self.env['hr.formula.rule'].sudo()
        return self.env['hr.formula.rule'].sudo().search(
            [('config_id', 'in', configs.ids)], order='config_id, sequence, id')

    @api.model
    def _pb_suggest(self, form, company):
        """[{line_id, line_code, line_label, rule_id, label, code, scheme,
        source, reason}] — nothing is created."""
        rules = self._pb_candidate_rules(company, form)
        taken = {(m.line_id.id, m.rule_id.id) for m in self.sudo().search([
            ('form_id', '=', form.id), ('company_id', '=', company.id)])}
        on_line = {m.line_id.id for m in self.sudo().search([
            ('form_id', '=', form.id), ('company_id', '=', company.id)])}
        out = []
        for line in form._pb_ordered_lines():
            if not line.mappable or line.base_line_id or not line.suggest_words:
                continue
            if line.id in on_line:
                continue
            words = [_norm(w) for w in line.suggest_words.split(',') if _norm(w)]
            roles = [r.strip() for r in (line.suggest_roles or '').split(',') if r.strip()]
            per_scheme = {}
            for rule in rules:
                if (line.id, rule.id) in taken:
                    continue
                if roles and (rule.net_role or '') not in roles:
                    continue
                if line.kind == 'text':
                    if (rule.value_kind or '') not in ('text', 'identifier'):
                        continue
                elif (rule.value_kind or 'money') not in NUMBER_KINDS:
                    continue
                if rule.net_role_detail and not line.suggest_parts:
                    # a part already counted inside another total
                    continue
                name = _norm(rule.name)
                code = _norm(rule.code)
                hit = next((w for w in words if w and (w == code or w in name)), None)
                if not hit:
                    continue
                # one proposal per scheme per line: the closest name wins.
                # WDGAP S2-F — on a line that accepts parts, a whole item beats
                # a part and the first role listed beats the next; on every
                # other line both ranks are 0, so its order is unchanged.
                best = per_scheme.get(rule.config_id.id)
                parts = line.suggest_parts
                score = (1 if parts and rule.net_role_detail else 0,
                         roles.index(rule.net_role) if parts and rule.net_role in roles else 0,
                         0 if name == hit or code == hit else 1, len(name))
                if best and best[0] <= score:
                    continue
                per_scheme[rule.config_id.id] = (score, rule, hit)
            for _score, rule, hit in sorted(per_scheme.values(), key=lambda v: v[1].id):
                source = self._pb_default_source(rule)
                out.append({
                    'line_id': line.id, 'line_code': line.code,
                    'line_label': line.label, 'rule_id': rule.id,
                    'label': rule.name or rule.code, 'code': rule.code,
                    'scheme': rule.config_id.name or '', 'source': source,
                    'reason': _("Its name contains “%s”.", hit),
                })
        return out

    @api.model
    def _pb_clean(self, form, company, rows):
        """[{line_id, rule_id, source, sign, share_pct}] from the browser —
        every id re-read and checked (form, company, mappable)."""
        Line = self.env['pb.gov.form.line'].sudo()
        Rule = self.env['hr.formula.rule'].sudo()
        out = []
        for row in rows or []:
            try:
                line = Line.browse(int(row.get('line_id') or 0)).exists()
                rule = Rule.browse(int(row.get('rule_id') or 0)).exists()
            except (TypeError, ValueError, AttributeError):
                continue
            if not line or not rule:
                continue
            if line.form_id != form:
                raise UserError(_("That line belongs to another form."))
            if rule.config_id.company_id != company:
                raise UserError(_("“%s” belongs to a pay scheme of another company.",
                                  rule.name or rule.code))
            source = row.get('source') if row.get('source') in dict(SOURCES) \
                else self._pb_default_source(rule)
            sign = row.get('sign') if row.get('sign') in dict(SIGNS) else 'add'
            try:
                share = float(row.get('share_pct') or 100.0)
            except (TypeError, ValueError):
                share = 100.0
            out.append({'line_id': line.id, 'rule_id': rule.id, 'source': source,
                        'sign': sign, 'share_pct': share})
        return out
