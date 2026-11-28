# -*- coding: utf-8 -*-
"""TIDY-E item 3b/3c (owner rulings R12/R13) and TIDY-E2 (R17) — "Fill empty
Country of Work", on screen, for HR managers.

Country of Work decides which country boxes a person's record shows. Where
nobody ever set it, those people see no country box at all, so the empties are
filled — in this order (R17):

(a) the pay set-up the person is paid under: the pay set-up(s) that pay them
    (`hr.formula.config.schemes_for_employee` — "Paid by", regular and
    advance) and the pay set-up of every payslip of their current contract,
    each carrying its country (`hr.formula.config.country_code`). Read only
    for people with a contract. Exactly one country → that country. Two or
    more → left empty and listed (a decision for HR, not for a button).
(b) when (a) finds nothing: the country of the person's COMPANY (the company
    record's country). Live context: on one site the pay set-up was linked to
    nobody yet (650 of 651 "no pay set-up"); on the demo 66 people had no
    contract or no pay set-up — (b) decides them. The HR manager can untick
    this part before confirming.

Still undecided: two countries from (a); a company with no country; a company
whose country is not one of the Country of Work choices.

Rules: only EMPTY Country of Work is written, never a set one; the write
re-reads emptiness in the same transaction; a second run finds nothing to
do; who, when and how many (and how many from the company) is kept
(`pb.cow.fill.log`). The deployer runs this same action on each database
(`create({})` → `preview_json` → `action_fill()`), not a private script.
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
    company_count = fields.Integer(string='Of which from the company', readonly=True)
    left_count = fields.Integer(string='People left empty', readonly=True)
    by_country = fields.Text(string='By country', readonly=True)


class PbCowFillWizard(models.TransientModel):
    _name = 'pb.cow.fill.wizard'
    _description = 'Fill empty Country of Work'

    use_company = fields.Boolean(
        string="Also fill from the company's country", default=True,
        help="People whose pay set-up does not decide get their company's country. "
             "Untick to fill only from pay set-ups.")
    preview_json = fields.Text(compute='_compute_preview', readonly=True)
    preview_html = fields.Html(compute='_compute_preview', sanitize=False, readonly=True)
    fill_count = fields.Integer(compute='_compute_preview', readonly=True)
    company_count = fields.Integer(compute='_compute_preview', readonly=True)
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
        """`{'empty', 'pay': {code: [ids]}, 'company': {code: [ids]},
        'left': [{id, name, reason, countries}]}`.

        A read: nothing is written. Active people of the companies in use,
        whose Country of Work is empty. `company` is what rule (b) would
        decide; whether it is used is the caller's choice.
        """
        Emp = self.env['hr.employee'].sudo().with_context(active_test=True)
        companies = self.env.companies.ids or [self.env.company.id]
        people = Emp.search([('company_id', 'in', companies),
                             ('payroll_country', '=', False)], order='name, id')
        allowed = set(dict(Emp._fields['payroll_country']._description_selection(self.env)))
        Config = self.env.get('hr.formula.config')
        Slip = self.env.get('hr.payslip')
        plan = {'empty': len(people), 'pay': {}, 'company': {}, 'left': []}
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
            row = {'id': e.id, 'name': e.name or '', 'countries': []}
            # (a) the pay set-up — only for people with a contract
            countries = set()
            if current[e.id]:
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
                plan['pay'].setdefault(next(iter(countries)), []).append(e.id)
                continue
            if len(countries) > 1:
                plan['left'].append(dict(row, reason='two_countries', countries=sorted(countries)))
                continue
            # (b) the company's country
            code = (e.company_id.country_id.code or '').upper()
            if not code:
                plan['left'].append(dict(row, reason='company_no_country'))
            elif code not in allowed:
                plan['left'].append(dict(row, reason='company_country_not_offered',
                                         countries=[code]))
            else:
                plan['company'].setdefault(code, []).append(e.id)
        return plan

    @api.model
    def _pb_reason_text(self, reason):
        return {
            'two_countries': _("Paid under pay set-ups of two countries — choose by hand"),
            'company_no_country': _("No pay set-up decides, and the company has no country"),
            'company_country_not_offered': _(
                "No pay set-up decides, and the company's country is not one of the "
                "Country of Work choices"),
        }.get(reason, reason)

    @api.model
    def _pb_summary(self, plan, use_company):
        pay = {code: len(ids) for code, ids in plan['pay'].items()}
        company = {code: len(ids) for code, ids in plan['company'].items()}
        reasons = {}
        for row in plan['left']:
            reasons[row['reason']] = reasons.get(row['reason'], 0) + 1
        fill = dict(pay)
        if use_company:
            for code, n in company.items():
                fill[code] = fill.get(code, 0) + n
        two = [{'id': r['id'], 'name': r['name'], 'countries': r['countries']}
               for r in plan['left'] if r['reason'] == 'two_countries']
        return pay, company, fill, reasons, two

    @api.depends('done', 'use_company')
    def _compute_preview(self):
        for wizard in self:
            plan = self._pb_plan()
            pay, company, fill, reasons, two = self._pb_summary(plan, wizard.use_company)
            wizard.fill_count = sum(fill.values())
            wizard.company_count = sum(company.values())
            wizard.preview_json = json.dumps({
                'empty': plan['empty'], 'from_pay_setup': pay, 'from_company': company,
                'use_company': bool(wizard.use_company), 'fill': fill, 'left': reasons,
                'two_countries': [{'id': r['id'], 'countries': r['countries']} for r in two],
            }, sort_keys=True)
            wizard.preview_html = self._pb_preview_html(
                plan, pay, company, reasons, two, wizard.use_company)

    @api.model
    def _pb_rows(self, counts):
        return Markup('').join(
            Markup('<tr><td>%s</td><td class="text-end"><b>%s</b></td></tr>') % (
                self._pb_country_label(code), '{:,}'.format(n))
            for code, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    @api.model
    def _pb_table(self, head, rows, note=None):
        out = Markup(
            '<table class="table table-sm mb-1"><thead><tr><th>%s</th>'
            '<th class="text-end">%s</th></tr></thead><tbody>%s</tbody></table>') % (
            head, _("People"), rows)
        if note:
            out += Markup('<p class="text-muted small mb-3">%s</p>') % note
        else:
            out += Markup('<div class="mb-3"></div>')
        return out

    @api.model
    def _pb_preview_html(self, plan, pay, company, reasons, two, use_company):
        if not plan['empty']:
            return Markup('<p class="text-muted mb-0">%s</p>') % _(
                "Everyone already has a Country of Work. Nothing to fill.")
        out = Markup('<p>%s</p>') % _("%(n)s people have no Country of Work.",
                                      n='{:,}'.format(plan['empty']))
        pay_rows = self._pb_rows(pay) or Markup(
            '<tr><td colspan="2" class="text-muted">%s</td></tr>') % _(
            "Nobody can be filled from a pay set-up.")
        out += self._pb_table(_("From pay set-up"), pay_rows)
        if company:
            note = None if use_company else _(
                "Not ticked: these people stay empty this time.")
            out += self._pb_table(_("From the company's country"), self._pb_rows(company), note)
        left_rows = Markup('').join(
            Markup('<tr><td>%s</td><td class="text-end"><b>%s</b></td></tr>') % (
                self._pb_reason_text(reason), '{:,}'.format(n))
            for reason, n in sorted(reasons.items()))
        if left_rows:
            out += self._pb_table(_("Left empty, because"), left_rows)
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
        """Fill only the empties, from a fresh plan. Returns the counts.

        Rule (b) is used unless the wizard's "from the company" box is
        unticked (a bare model call, as a deployer's shell makes it, uses the
        default: ticked).
        """
        self._pb_require_manager()
        use_company = self[:1].use_company if self else True
        plan = self._pb_plan()
        Emp = self.env['hr.employee'].sudo()
        filled, from_company = {}, 0
        sources = [plan['pay']] + ([plan['company']] if use_company else [])
        for n, source in enumerate(sources):
            for code, ids in source.items():
                # never overwrite: re-read emptiness in this transaction
                todo = Emp.browse(ids).filtered(lambda e: not e.payroll_country)
                if todo:
                    todo.write({'payroll_country': code})
                    filled[code] = filled.get(code, 0) + len(todo)
                    if n == 1:
                        from_company += len(todo)
        total = sum(filled.values())
        left = len(plan['left']) + (0 if use_company else
                                    sum(len(ids) for ids in plan['company'].values()))
        self.env['pb.cow.fill.log'].sudo().create({
            'user_id': self.env.user.id,
            'company_ids': [(6, 0, self.env.companies.ids)],
            'filled_count': total,
            'company_count': from_company,
            'left_count': left,
            'by_country': json.dumps(filled, sort_keys=True),
        })
        _logger.info("Country of Work fill by user %s: %s filled %s (%s from the company), "
                     "%s left", self.env.uid, total, filled, from_company, left)
        result = (_("Country of Work filled for %(n)s people.", n='{:,}'.format(total))
                  if total else _("Nothing to fill — no empty Country of Work could be decided."))
        if self:
            self.write({'done': True, 'result_text': result})
        return {'filled': filled, 'total': total, 'from_company': from_company,
                'left': left, 'message': result}

    def action_fill_and_close(self):
        res = self.action_fill()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _("Country of Work"), 'message': res['message'],
                       'type': 'success' if res['total'] else 'info', 'sticky': False,
                       'next': {'type': 'ir.actions.act_window_close'}},
        }
