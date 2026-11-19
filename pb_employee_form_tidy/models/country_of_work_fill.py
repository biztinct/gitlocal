# -*- coding: utf-8 -*-
"""TIDY-E item 3b/3c (owner rulings R12/R13) — "Fill empty Country of Work
from pay set-up", on screen, for HR managers.

Country of Work decides which country boxes a person's record shows. On the
databases where nobody ever set it (sudima, payobook: everyone "Not recorded")
those people would see no country box at all, so the empties are filled from
the pay set-up each person is paid under:

* the pay set-up(s) that pay the person (`hr.formula.config.schemes_for_employee`
  — the "Paid by" scheme, regular and advance), and
* the pay set-up of every payslip of the person's current contract,

each pay set-up carrying its country (`hr.formula.config.country_code`).
Exactly one country → that country. None → left empty, with the reason. Two
or more → left empty and listed (a person paid in two countries is a decision
for HR, not for a button).

Rules: only EMPTY Country of Work is written, never a set one; the write
re-reads emptiness in the same transaction; a second run finds nothing to
do; who, when and how many is kept (`pb.cow.fill.log`). The deployer runs this
same action on each database after go-live (`create({})` → `preview_json` →
`action_fill()`), not a private script.
"""

import json
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

MANAGER = 'hr.group_hr_manager'
LIST_CAP = 50


class PbCowFillLog(models.Model):
    _name = 'pb.cow.fill.log'
    _description = 'Country of Work fill — who, when, how many'
    _order = 'id desc'

    user_id = fields.Many2one('res.users', string='Filled by', required=True,
                              default=lambda self: self.env.user, readonly=True)
    company_ids = fields.Many2many('res.company', string='Companies', readonly=True)
    filled_count = fields.Integer(string='People filled', readonly=True)
    left_count = fields.Integer(string='People left empty', readonly=True)
    by_country = fields.Text(string='By country', readonly=True)


class PbCowFillWizard(models.TransientModel):
    _name = 'pb.cow.fill.wizard'
    _description = 'Fill empty Country of Work from pay set-up'

    preview_json = fields.Text(compute='_compute_preview', readonly=True)
    preview_html = fields.Html(compute='_compute_preview', sanitize=False, readonly=True)
    fill_count = fields.Integer(compute='_compute_preview', readonly=True)
    done = fields.Boolean(readonly=True)
    result_text = fields.Char(readonly=True)

    # ------------------------------------------------------------ access
    @api.model
    def _pb_require_manager(self):
        if not self.env.user.has_group(MANAGER):
            raise AccessError(_("Only HR managers can fill Country of Work for everyone."))

    @api.model_create_multi
    def create(self, vals_list):
        self._pb_require_manager()
        return super().create(vals_list)

    # ------------------------------------------------------------ the plan
    @api.model
    def _pb_country_label(self, code):
        sel = dict(self.env['hr.employee']._fields['payroll_country']._description_selection(self.env))
        return sel.get(code, code)

    @api.model
    def _pb_plan(self):
        """`{'empty', 'fill': {code: [ids]}, 'left': [{id, name, reason, countries}]}`.

        A read: nothing is written. Active people of the companies in use,
        whose Country of Work is empty.
        """
        Emp = self.env['hr.employee'].sudo().with_context(active_test=True)
        companies = self.env.companies.ids or [self.env.company.id]
        people = Emp.search([('company_id', 'in', companies),
                             ('payroll_country', '=', False)], order='name, id')
        allowed = set(dict(Emp._fields['payroll_country']._description_selection(self.env)))
        Config = self.env.get('hr.formula.config')
        Slip = self.env.get('hr.payslip')
        plan = {'empty': len(people), 'fill': {}, 'left': []}
        if not people:
            return plan

        current = {}
        for e in people:
            contract = e.contract_id or e.contract_ids.sorted(
                key=lambda c: (c.date_start or fields.Date.from_string('1900-01-01'), c.id))[-1:]
            current[e.id] = contract
        slip_countries = {}
        if Slip is not None and 'formula_config_id' in Slip._fields:
            contract_ids = [c.id for c in current.values() if c]
            if contract_ids:
                groups = Slip.sudo()._read_group(
                    [('contract_id', 'in', contract_ids), ('state', '!=', 'cancel'),
                     ('formula_config_id', '!=', False)],
                    ['employee_id', 'contract_id', 'formula_config_id'], ['__count'])
                for employee, contract, config, _count in groups:
                    if current.get(employee.id) == contract and config.country_code:
                        slip_countries.setdefault(employee.id, set()).add(config.country_code)

        for e in people:
            if not current[e.id]:
                plan['left'].append({'id': e.id, 'name': e.name or '',
                                     'reason': 'no_contract', 'countries': []})
                continue
            countries = set(slip_countries.get(e.id, set()))
            if Config is not None and hasattr(Config, 'schemes_for_employee'):
                try:
                    for config in Config.sudo().schemes_for_employee(e):
                        if config.country_code:
                            countries.add(config.country_code)
                except Exception:       # noqa: BLE001 — one person never stops the plan
                    _logger.warning("Country of Work fill: pay set-up of employee %s "
                                    "could not be read", e.id, exc_info=True)
            countries = {c for c in countries if c in allowed}
            if len(countries) == 1:
                plan['fill'].setdefault(next(iter(countries)), []).append(e.id)
            elif not countries:
                plan['left'].append({'id': e.id, 'name': e.name or '',
                                     'reason': 'no_scheme', 'countries': []})
            else:
                plan['left'].append({'id': e.id, 'name': e.name or '',
                                     'reason': 'two_countries',
                                     'countries': sorted(countries)})
        return plan

    @api.model
    def _pb_reason_text(self, reason):
        return {
            'no_contract': _("No contract, so no pay set-up to read"),
            'no_scheme': _("No pay set-up pays this person yet"),
            'two_countries': _("Paid under pay set-ups of two countries — choose by hand"),
        }.get(reason, reason)

    @api.depends('done')
    def _compute_preview(self):
        for wizard in self:
            plan = self._pb_plan()
            fill = {code: len(ids) for code, ids in plan['fill'].items()}
            reasons = {}
            for row in plan['left']:
                reasons[row['reason']] = reasons.get(row['reason'], 0) + 1
            two = [{'id': r['id'], 'name': r['name'], 'countries': r['countries']}
                   for r in plan['left'] if r['reason'] == 'two_countries']
            wizard.fill_count = sum(fill.values())
            wizard.preview_json = json.dumps({
                'empty': plan['empty'], 'fill': fill, 'left': reasons,
                'two_countries': [{'id': r['id'], 'countries': r['countries']} for r in two],
            }, sort_keys=True)
            wizard.preview_html = self._pb_preview_html(plan, fill, reasons, two)

    @api.model
    def _pb_preview_html(self, plan, fill, reasons, two):
        if not plan['empty']:
            return Markup('<p class="text-muted mb-0">%s</p>') % _(
                "Everyone already has a Country of Work. Nothing to fill.")
        rows = Markup('').join(
            Markup('<tr><td>%s</td><td class="text-end"><b>%s</b></td></tr>') % (
                self._pb_country_label(code), '{:,}'.format(n))
            for code, n in sorted(fill.items(), key=lambda kv: (-kv[1], kv[0])))
        if not rows:
            rows = Markup('<tr><td colspan="2" class="text-muted">%s</td></tr>') % _(
                "Nobody can be filled from a pay set-up.")
        left_rows = Markup('').join(
            Markup('<tr><td>%s</td><td class="text-end"><b>%s</b></td></tr>') % (
                self._pb_reason_text(reason), '{:,}'.format(n))
            for reason, n in sorted(reasons.items()))
        out = Markup(
            '<p>%s</p>'
            '<table class="table table-sm mb-3"><thead><tr><th>%s</th>'
            '<th class="text-end">%s</th></tr></thead><tbody>%s</tbody></table>') % (
            _("%(n)s people have no Country of Work.", n='{:,}'.format(plan['empty'])),
            _("Will be set to"), _("People"), rows)
        if left_rows:
            out += Markup(
                '<table class="table table-sm mb-3"><thead><tr><th>%s</th>'
                '<th class="text-end">%s</th></tr></thead><tbody>%s</tbody></table>') % (
                _("Left empty, because"), _("People"), left_rows)
        if two:
            names = Markup('').join(
                Markup('<li>%s — %s</li>') % (
                    r['name'], ', '.join(self._pb_country_label(c) for c in r['countries']))
                for r in two[:LIST_CAP])
            more = Markup('<li class="text-muted">%s</li>') % _(
                "and %(n)s more", n=len(two) - LIST_CAP) if len(two) > LIST_CAP else Markup('')
            out += Markup('<p class="mb-1"><b>%s</b></p><ul>%s%s</ul>') % (
                _("Paid under pay set-ups of two countries:"), names, more)
        last = self.env['pb.cow.fill.log'].sudo().search([], limit=1)
        if last:
            out += Markup('<p class="text-muted small mb-0">%s</p>') % _(
                "Last filled by %(who)s on %(when)s: %(n)s people.",
                who=last.user_id.name or '', when=fields.Date.to_string(
                    fields.Datetime.context_timestamp(self, last.create_date).date()),
                n='{:,}'.format(last.filled_count))
        return out

    # ------------------------------------------------------------ the fill
    def action_fill(self):
        """Fill only the empties, from a fresh plan. Returns the counts."""
        self._pb_require_manager()
        plan = self._pb_plan()
        Emp = self.env['hr.employee'].sudo()
        filled = {}
        for code, ids in plan['fill'].items():
            # never overwrite: re-read emptiness in this transaction
            todo = Emp.browse(ids).filtered(lambda e: not e.payroll_country)
            if todo:
                todo.write({'payroll_country': code})
                filled[code] = len(todo)
        total = sum(filled.values())
        self.env['pb.cow.fill.log'].sudo().create({
            'user_id': self.env.user.id,
            'company_ids': [(6, 0, self.env.companies.ids)],
            'filled_count': total,
            'left_count': len(plan['left']),
            'by_country': json.dumps(filled, sort_keys=True),
        })
        _logger.info("Country of Work fill by user %s: %s filled %s, %s left",
                     self.env.uid, total, filled, len(plan['left']))
        result = (_("Country of Work filled for %(n)s people.", n='{:,}'.format(total))
                  if total else _("Nothing to fill — no empty Country of Work could be decided."))
        if self:
            self.write({'done': True, 'result_text': result})
        return {'filled': filled, 'total': total, 'left': len(plan['left']),
                'message': result}

    def action_fill_and_close(self):
        res = self.action_fill()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _("Country of Work"), 'message': res['message'],
                       'type': 'success' if res['total'] else 'info', 'sticky': False,
                       'next': {'type': 'ir.actions.act_window_close'}},
        }
