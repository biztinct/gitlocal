# -*- coding: utf-8 -*-
"""The one answer to "what does the scale say for this joiner?", and the
writes that place a NEW contract on the scale.

Resolution (blueprint Part C, without the policy layer that comes later):
the person's job → its job-to-band link in force on the start date → the
grade on that link → the grade's scale (active, serving the contract's
company, same money as the person is paid in) → the version in force on the
start date → step 1 (owner ruling J4: new joiners start on step 1 unless the
recruiter types another amount).

Every write here happens on CREATE of a contract only (FACTS §3 "only on
CREATE, only an empty box"). Package lines are written only for pay items the
person's own pay scheme has (SCHEMECTX: never another scheme's component) and
each one is logged with `hr.contract.advantage.change.log`, dated the
contract's start date.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

#: The input codes the no-file pay run fills from the contract wage.
WAGE_CODES = ('BASIC', 'WAGE', 'BASE')


class PbPayScales(models.AbstractModel):
    _name = 'pb.pay.scales'
    _description = 'Pay scales'

    # ================================================================ helpers
    @api.model
    def _bands(self):
        return self.env['pb.pay.bands']

    @api.model
    def _money(self, amount, currency):
        return self._bands()._money(amount, currency)

    @api.model
    def _day(self, value=None):
        if value:
            try:
                return fields.Date.to_date(value)
            except (TypeError, ValueError):
                pass
        return fields.Date.context_today(self)

    @api.model
    def _same(self, a, b, decimals):
        return a is not None and b is not None \
            and abs(float(a) - float(b)) < 0.5 * 10.0 ** (-int(decimals or 0))

    @api.model
    def _schemes_for(self, employee):
        Config = self.env.get('hr.formula.config')
        if Config is None or not employee or not hasattr(Config, 'schemes_for_employee'):
            return self.env['hr.formula.config'].browse() if Config is not None else None
        try:
            return Config.sudo().schemes_for_employee(employee)
        except Exception:       # noqa: BLE001 — an optional answer
            _logger.debug("pb_pay_scales: schemes unreadable", exc_info=True)
            return Config.browse()

    @api.model
    def _pay_currency(self, employee, company):
        schemes = self._schemes_for(employee) if employee else None
        if schemes:
            currency = schemes[:1].currency_id
            if currency:
                return currency
        return (company or self.env.company).currency_id

    # ============================================================ resolution
    @api.model
    def _grade_for_job(self, job, day=None, company=None):
        """The grade a job sits on, read from the job-to-band link in force."""
        if not job:
            return self.env['pb.pay.scale.grade']
        day = self._day(day)
        links = self.env['pb.pay.band.job'].sudo().search([
            ('job_id', '=', job.id), ('pb_scale_grade_id', '!=', False)])
        for link in links:
            band = link.band_id
            if not band.active or band.date_from > day \
                    or (band.date_to and band.date_to < day):
                continue
            grade = link.pb_scale_grade_id
            scale = grade.scale_id
            if not scale.active:
                continue
            if company and not scale.serves_company(company):
                continue
            return grade
        return self.env['pb.pay.scale.grade']

    @api.model
    def resolve(self, job, company=None, day=None, employee=None):
        """``{found, why, grade, scale, version, step, amount, sentence,
        steps}`` — what the scale says for a joiner on ``day``."""
        day = self._day(day)
        company = company or (employee.company_id if employee else self.env.company)
        out = {'found': False, 'why': '', 'grade': None, 'scale': None,
               'version': None, 'step': 1, 'amount': 0.0, 'sentence': '',
               'steps': []}
        if not job:
            out['why'] = _("No job is set, so no scale applies.")
            return out
        grade = self._grade_for_job(job, day, company)
        if not grade:
            out['why'] = _("%(job)s is not on a pay scale.", job=job.display_name)
            return out
        scale = grade.scale_id.sudo()
        # Known from here on: the hire screen may say WHY the scale is not used.
        out.update(grade=grade, scale=scale)
        version = scale.version_on(day)
        if not version:
            out['why'] = _("%(scale)s has no amounts in force on %(day)s.",
                           scale=scale.name, day=fields.Date.to_string(day))
            return out
        # The person's money is the money of the scheme that pays them
        # (SCHEMECTX). Before the person exists (a joiner typed on a sheet or
        # in the new-employee form) nobody pays them yet, so the scale's own
        # country, checked through the company above, is the only test.
        currency = self._pay_currency(employee, company) if employee else None
        if currency and scale.currency_id and currency != scale.currency_id:
            out['why'] = _(
                "%(scale)s is written in %(scale_money)s but this person is "
                "paid in %(pay_money)s, so it is not used.", scale=scale.name,
                scale_money=scale.currency_id.name, pay_money=currency.name)
            return out
        steps = []
        for step in range(1, (scale.step_count or 1) + 1):
            value = version.value_of(grade, step)
            if value is not None:
                steps.append({'step': step, 'amount': value,
                              'label': self._money(value, scale.currency_id)})
        first = version.value_of(grade, 1)
        if first is None:
            out['why'] = _("%(grade)s has no amount for step 1 yet.", grade=grade.name)
            out['steps'] = steps
            return out
        out.update({
            'found': True, 'grade': grade, 'scale': scale, 'version': version,
            'step': 1, 'amount': first, 'steps': steps,
            'sentence': _(
                "%(amount)s — %(grade)s, step 1 of %(scale)s",
                amount=self._money(first, scale.currency_id), grade=grade.name,
                scale=scale.name),
        })
        return out

    @api.model
    def step_matching(self, answer, wage):
        """The step whose amount equals ``wage``, or 0."""
        scale = answer.get('scale')
        if not scale:
            return 0
        for row in answer.get('steps') or []:
            if self._same(row['amount'], wage, scale.decimals()):
                return row['step']
        return 0

    # ======================================================= contract create
    @api.model
    def place_new_contract(self, contract, reason=None, source='hire', note=None):
        """Place a JUST-CREATED contract on its job's scale, and fill the
        grade's allowances when it is on a step. Returns the placement or an
        empty recordset. Never raises: a hire must not fail on a scale."""
        Placement = self.env['pb.pay.scale.placement'].sudo()
        try:
            contract = contract.sudo()
            if not contract or Placement.search_count([('contract_id', '=', contract.id)]):
                return Placement.browse()
            job = contract.job_id or contract.employee_id.job_id
            answer = self.resolve(job, contract.company_id, contract.date_start,
                                  contract.employee_id)
            if not answer['found']:
                return Placement.browse()
            step = self.step_matching(answer, contract.wage)
            vals = {'contract_id': contract.id, 'grade_id': answer['grade'].id,
                    'step_no': step or 1, 'source': source,
                    'placed_on': fields.Date.context_today(self)}
            if not step:
                vals.update(pinned=True, pin_reason=reason or 'typed',
                            pin_note=note or False)
            row = Placement.create(vals)
            if step:
                self._fill_package(contract, answer['version'], answer['grade'])
            return row
        except Exception:       # noqa: BLE001 — never block a hire
            _logger.warning("pb_pay_scales: could not place contract %s",
                            contract.id if contract else 0, exc_info=True)
            return Placement.browse()

    @api.model
    def _scheme_codes(self, employee):
        """Number input codes of the scheme(s) that pay this person."""
        schemes = self._schemes_for(employee)
        codes = set()
        for config in (schemes or []):
            for rule in config.sudo().rule_ids:
                if rule.column_type == 'input' and rule.code \
                        and not getattr(rule, 'is_text_component', False):
                    codes.add(rule.code)
        return codes

    @api.model
    def _fill_package(self, contract, version, grade):
        """Write the grade's allowances onto a NEW contract (get-or-create one
        line per pay item, only for items the person's scheme has)."""
        lines = version.package_ids.filtered(lambda p: p.grade_id == grade)
        if not lines:
            return 0
        codes = self._scheme_codes(contract.employee_id)
        Line = self.env['hr.contract.advantage'].sudo()
        Change = self.env['hr.contract.advantage.change'].sudo()
        written = 0
        for pkg in lines:
            template = pkg.template_id
            if not template or template.code not in codes:
                continue
            line = Line.search([('contract_id', '=', contract.id),
                                ('advantage_template_id', '=', template.id)], limit=1)
            old = line.amount if line else 0.0
            if line:
                if self._same(old, pkg.amount, 2):
                    continue
                line.write({'amount': pkg.amount})
            else:
                Line.create({'contract_id': contract.id,
                             'advantage_template_id': template.id,
                             'amount': pkg.amount})
            Change.log(contract, template, old, pkg.amount, 'pay_scale',
                       notes=_("From %(grade)s on %(scale)s", grade=grade.name,
                               scale=grade.scale_id.name),
                       effective_date=contract.date_start)
            written += 1
        return written
