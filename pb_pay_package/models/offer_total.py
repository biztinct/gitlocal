# -*- coding: utf-8 -*-
"""WDGAP S8-D (owner ruling SC3) — "Build from a total" on a Hiring offer.

The recruiter types the yearly (or monthly) total on the offer; the same
search the contract drawer uses (`pb.pay.package._solve_for`) splits it
through the chosen pay scheme's own formulas. "Use these figures" writes the
split onto the offer as its MONTHLY pay lines — basic pay, the allowances the
scheme works out from it, the item that takes the rest, and the employer's
contributions — so the offer letter (whose `${lines}` table is the offer's
lines) shows the split. Bonuses, benefits and one-off lines stay as typed.

Each line that is a pay item the contract holds carries its item code. When
the person joins, the contract starts with those figures through the normal
joiner path (`_ensure_contract`, the offer route already agreed them): the
wage from the basic pay line, and the contract pay lines — only the items the
person's own pay scheme has (SCHEMECTX), each logged in the pay-line trail.

An offer without it behaves exactly as before: nothing here runs unless a
line carries an item code.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.pb_formula_studio.models.take_home import _Engine, _num

from .package import EMPLOYER_BAND, GROSS_BANDS

_logger = logging.getLogger(__name__)

#: Bands whose lines are the person's monthly pay. Only lines the totals
#: count are taken (`counts`), so a scheme's own gross total line — no pay
#: role, or a detail of another — is never added on top of its parts.
PAY_BANDS = GROSS_BANDS


class PbHiringOfferLineTotal(models.Model):
    _inherit = 'pb.hiring.offer.line'

    pb_item_code = fields.Char(
        string='Pay item', readonly=True, copy=True,
        help='The pay item this line fills on the contract when the person joins.')
    pb_item_wage = fields.Boolean(
        string='Is the monthly wage', readonly=True, copy=True)
    pb_from_total = fields.Boolean(
        string='From the total package', readonly=True, copy=True)


class PbHiringOfferTotal(models.Model):
    _inherit = 'pb.hiring.offer'

    pb_total_config_id = fields.Many2one(
        'hr.formula.config', string='Split with pay scheme', readonly=True,
        copy=True, ondelete='set null')
    pb_total_note = fields.Char(string='Built from a total', readonly=True,
                                copy=True)

    # ------------------------------------------------------------ joining
    def _basic_line(self):
        """The wage comes from the basic pay line the split wrote, when there
        is one; otherwise exactly as before (the biggest monthly earning)."""
        self.ensure_one()
        tagged = self.line_ids.filtered(
            lambda ln: ln.pb_item_wage and ln.period == 'monthly'
            and (ln.amount or 0.0) > 0)
        if tagged:
            return tagged[:1]
        return super()._basic_line()

    def _ensure_contract(self):
        had = self.contract_id
        contract = super()._ensure_contract()
        if had or not contract:
            return contract
        try:
            with self.env.cr.savepoint():
                self._pbpk_contract_lines(contract)
        except Exception:       # noqa: BLE001 — joining never fails on a split
            _logger.warning('pb_pay_package: offer %s pay lines not written', self.id,
                            exc_info=True)
        return contract

    def _pbpk_contract_lines(self, contract):
        """Write the offer's pay-item lines onto the NEW contract. Only items
        of the scheme that pays the person (or, before anybody's map reaches
        them, the scheme the split was made with)."""
        self.ensure_one()
        tagged = self.line_ids.filtered(
            lambda ln: ln.pb_item_code and not ln.pb_item_wage and ln.period == 'monthly')
        if not tagged:
            return 0
        contract = contract.sudo()
        Config = self.env['hr.formula.config'].sudo()
        schemes = Config.browse()
        if hasattr(Config, 'schemes_for_employee'):
            try:
                schemes = Config.schemes_for_employee(contract.employee_id)
            except Exception:   # noqa: BLE001
                schemes = Config.browse()
        schemes = schemes or self.sudo().pb_total_config_id
        codes = set()
        for config in schemes:
            for rule in config.rule_ids:
                if rule.column_type == 'input' and rule.code:
                    codes.add(rule.code)
        Template = self.env['hr.contract.advantage.template'].sudo()
        Line = self.env['hr.contract.advantage'].sudo()
        Change = self.env['hr.contract.advantage.change'].sudo()
        written, skipped = 0, []
        for line in tagged:
            code = line.pb_item_code
            if code not in codes:
                skipped.append(line.name or code)
                continue
            template = Template.search([('code', '=', code)], limit=1) or Template.create({
                'name': line.name or code, 'code': code, 'lower_bound': 0.0,
                'upper_bound': 0.0, 'default_value': 0.0})
            existing = Line.search([('contract_id', '=', contract.id),
                                    ('advantage_template_id', '=', template.id)], limit=1)
            old = existing.amount if existing else 0.0
            if existing:
                if abs((existing.amount or 0.0) - (line.amount or 0.0)) < 1e-9:
                    continue
                existing.write({'amount': line.amount})
            else:
                Line.create({'contract_id': contract.id, 'advantage_template_id': template.id,
                             'amount': line.amount})
            Change.log(contract, template, old, line.amount, 'manual',
                       notes=_("From offer %s", self.name or ''),
                       effective_date=contract.date_start)
            written += 1
        if skipped:
            self.sudo().message_post(body=_(
                "The contract was written without %(items)s: the pay scheme that pays "
                "them has no such pay item. Add it on the contract if it is still "
                "agreed.", items=', '.join(skipped)))
        return written


class PbPayPackageOffer(models.AbstractModel):
    _inherit = 'pb.pay.package'

    # ============================================================== gates
    @api.model
    def _offer_get(self, offer_id):
        offer = self.env['pb.hiring.offer'].sudo().browse(int(offer_id or 0)).exists()
        if not offer:
            raise UserError(_("That offer is no longer there."))
        Hiring = self.env['pb.hiring']
        req = offer.requisition_id
        Hiring._require_recruit(req)
        if hasattr(Hiring, '_is_hiring_reader') and not Hiring._is_hiring_reader(req):
            raise AccessError(_("The offer's figures are with the hiring team."))
        if offer.company_id and offer.company_id not in self.env.user.company_ids:
            raise AccessError(_("This offer belongs to a company you do not work in."))
        return offer

    @api.model
    def _offer_country(self, offer):
        """The Country of work of the person this offer is for: the
        requisition's country, else the company's (the letter reads the same
        two, `pb.hiring.offer`)."""
        req = offer.requisition_id.sudo()
        country = req.country_id or offer.company_id.country_id
        return (country.code or '').upper() if country else ''

    @api.model
    def _offer_schemes(self, offer):
        """The live pay schemes of the offer's company, the default first.

        PSCHEME P2b C (owner ruling R1): the default is the usual pay scheme
        of the offer's Country of work — the same answer Add employee gives
        (`pb.scheme.map.usual_scheme`: the country's only or usual scheme,
        the team's usual scheme only to break a tie). Reached by a soft probe:
        this module does not depend on the scheme map."""
        Config = self.env['hr.formula.config'].sudo()
        company = offer.company_id
        schemes = Config.search([('state', '=', 'active'), '|',
                                 ('company_id', '=', False),
                                 ('company_id', '=', company.id)], order='id')
        first = Config.browse()
        Map = self.env.get('pb.scheme.map')
        dept = offer.requisition_id.sudo().department_id
        if Map is not None and hasattr(Map, 'usual_scheme'):
            try:
                found = Map.sudo().usual_scheme(company.id, self._offer_country(offer),
                                                dept.id if dept else 0)
                first = found['config'] or Config.browse()
            except Exception:   # noqa: BLE001 — a default is only a default
                _logger.debug('pb_pay_package: map unreadable for an offer', exc_info=True)
        if not first and Map is not None:
            try:
                first = Map.sudo()._only_scheme(company.id)
            except Exception:   # noqa: BLE001
                first = Config.browse()
        if first and first in schemes:
            schemes = first | (schemes - first)
        return schemes

    @api.model
    def _offer_subject(self, offer, config_id=False):
        """``(subject, refusal)`` — the scheme's own usual figures (nobody is
        paid yet), the wage items, the offer."""
        schemes = self._offer_schemes(offer)
        Studio = self._studio()
        config = schemes.filtered(lambda c: c.id == int(config_id or 0))[:1]
        if not config:
            # The first scheme that can split this offer: the offer's money and
            # at least a basic pay and one item that takes the rest (found on
            # the walk: the company's first scheme had one item, and the card
            # opened on a refusal with no way to pick another scheme).
            money = offer.currency_id.name or ''
            usable = schemes.filtered(
                lambda c: (c.scheme_currency().get('name') or '') == money
                and len(Studio._th_items(c)) >= 2)
            config = usable[:1] or schemes[:1]
        if not config:
            return None, self._studio()._th_refusal('no_scheme', _(
                "This company has no pay scheme yet, so there is nothing to split the "
                "total with."))
        Studio = self._studio()
        return {'config': config, 'inputs': {}, 'employee': None, 'contract': None,
                'offer': offer, 'slip': None, 'source': 'defaults',
                'wage_codes': Studio._th_wage_codes(config)}, None

    # ================================================================ open
    @api.model
    def offer_open(self, offer_id, config_id=False):
        """What the card needs before anything is typed. Read-only."""
        offer = self._offer_get(offer_id)
        subject, refusal = self._offer_subject(offer, config_id)
        if refusal:
            return refusal
        Studio = self._studio()
        config = subject['config']
        currency = config.scheme_currency()
        items = Studio._th_items(config)
        if len(items) < 2:
            return Studio._th_refusal('no_items', _(
                "This pay scheme does not have the pay items a total can be split "
                "into (it needs at least a basic pay and one item that takes the "
                "rest)."))
        engine = _Engine(self.env, config)
        if not any(s['band'] in GROSS_BANDS for s in engine.specs):
            return Studio._th_refusal('no_gross', _(
                "This pay scheme has no gross pay line, so a total package cannot be "
                "worked out on it."))
        basic = Studio._th_default_item(config, subject['wage_codes'])
        month = float(offer.monthly_total or 0.0)
        return {
            'ok': True, 'offer': True,
            'who': offer.candidate_name or offer.name or '',
            'scheme': {'id': config.id, 'name': config.display_name or config.name or ''},
            'schemes': [{'id': s.id, 'name': s.display_name or s.name or ''}
                        for s in self._offer_schemes(offer)],
            'currency': currency,
            'offer_currency': offer.currency_id.name or '',
            'same_money': (offer.currency_id.name or '') == (currency.get('name') or ''),
            'items': [{'code': r.code, 'name': r.name or r.code, 'current': 0.0,
                       'is_wage': r.code in subject['wage_codes']} for r in items],
            'basic': basic,
            'balance': self._default_balance(items, basic),
            'basic_share': 50,
            'now': {'total': month, 'year': float(offer.annual_total or 0.0)},
            'source_label': _("The offer as it stands now, a month and a year."),
            'editable': offer.state == 'draft',
            'note': offer.pb_total_note or '',
        }

    # =============================================================== solve
    @api.model
    def offer_solve(self, offer_id, total=0.0, period='year', basic_mode='share',
                    basic_value=50.0, basic_code=False, balance_code=False, config_id=False):
        offer = self._offer_get(offer_id)
        subject, refusal = self._offer_subject(offer, config_id)
        if refusal:
            return refusal
        config = subject['config']
        if (offer.currency_id.name or '') != (config.scheme_currency().get('name') or ''):
            return self._studio()._th_refusal('money', _(
                "This offer is in %(offer)s but the pay scheme pays in %(scheme)s. "
                "Change the offer's money or pick another scheme.",
                offer=offer.currency_id.name or '',
                scheme=config.scheme_currency().get('name') or ''))
        out = self._solve_for(subject, total=total, period=period, basic_mode=basic_mode,
                              basic_value=basic_value, basic_code=basic_code,
                              balance_code=balance_code)
        if out.get('can_use'):
            out['use_note'] = _(
                "These become the offer's monthly pay lines; bonuses, benefits and "
                "one-off lines stay. The letter shows them, and the contract starts "
                "with them when the person joins.")
        return out

    # ================================================================= use
    @api.model
    def offer_use(self, offer_id, total=0.0, period='year', basic_mode='share',
                  basic_value=50.0, basic_code=False, balance_code=False, config_id=False):
        """Work it out once more and write the split on the offer as its
        monthly pay lines. The offer must still be in preparation (the same
        rule the offer's own line editor keeps)."""
        offer = self._offer_get(offer_id)
        if offer.state != 'draft':
            raise UserError(_(
                "This offer has been sent for sign-off, and the numbers are what "
                "somebody is agreeing to. Ask whoever it is waiting on to send it "
                "back, then change it and send it again."))
        out = self.offer_solve(offer.id, total=total, period=period, basic_mode=basic_mode,
                               basic_value=basic_value, basic_code=basic_code,
                               balance_code=balance_code, config_id=config_id)
        if not out.get('ok') or not out.get('can_use'):
            raise UserError(out.get('msg') or out.get('sentence') or _(
                "These figures cannot be used on the offer."))
        subject, _refusal = self._offer_subject(offer, config_id)
        config = subject['config']
        use = out['use']
        bands = out.get('bands') or {}
        wage_codes = set(subject['wage_codes'])
        item_codes = {it['code'] for it in use.get('items') or []}
        if out.get('basic', {}).get('code') in wage_codes:
            item_codes.add(out['basic']['code'])
        left_out = set((out.get('after') or {}).get('left_out') or [])
        decimals = int((out.get('currency') or {}).get('decimals') or 0)
        unit = 10.0 ** (-decimals)
        new_lines, seen = [], set()
        for row in out.get('lines') or []:
            code, band = row['code'], bands.get(row['code']) or ''
            amount = _num(row.get('after'))
            if not row.get('counts') or abs(amount) < unit / 2.0:
                continue
            if band in PAY_BANDS:
                kind = 'earning'
            elif band == EMPLOYER_BAND and row['name'] not in left_out:
                kind = 'statutory'
            else:
                continue
            tagged = code in item_codes and kind == 'earning'
            new_lines.append({'name': row['name'] or code, 'kind': kind, 'amount': amount,
                              'code': code if tagged else False,
                              'wage': bool(tagged and code in wage_codes)})
            seen.add(code)
        # A pay item the contract holds that the payslip does not print.
        for item in use.get('items') or []:
            if item['code'] not in seen and abs(item['amount']) >= unit / 2.0:
                new_lines.append({'name': item['name'], 'kind': 'earning',
                                  'amount': item['amount'], 'code': item['code'],
                                  'wage': False})
        if use.get('wage') and not any(l['wage'] for l in new_lines):
            code = out['basic']['code']
            new_lines.insert(0, {'name': out['basic']['name'], 'kind': 'earning',
                                 'amount': use['wage'], 'code': code, 'wage': True})
        Line = self.env['pb.hiring.offer.line'].sudo()
        offer.line_ids.filtered(
            lambda ln: ln.period == 'monthly' and ln.kind in ('earning', 'statutory')).unlink()
        sequence = 1
        for line in new_lines:
            Line.create({
                'offer_id': offer.id, 'sequence': sequence, 'name': line['name'],
                'kind': line['kind'], 'amount': line['amount'], 'period': 'monthly',
                'pb_item_code': line['code'] or False, 'pb_item_wage': line['wage'],
                'pb_from_total': True,
                'note': _("Paid by the company on top of pay")
                if line['kind'] == 'statutory' else '',
            })
            sequence += 1
        money = self._studio()._th_money
        note = _("Built from a total of %(year)s a year (%(month)s a month) with %(scheme)s.",
                 year=money(out['target_year'], out['currency']),
                 month=money(out['target'], out['currency']),
                 scheme=config.display_name or config.name or '')
        offer.write({'pb_total_config_id': config.id, 'pb_total_note': note, 'pbpb_values': False,
                     'pbpb_has_net': False, 'pbpb_net': 0, 'pbpb_gross': 0})
        offer.invalidate_recordset(['monthly_total', 'annual_total'])
        offer.message_post(body=note)
        return {'ok': True, 'note': note, 'lines': len(new_lines)}


class PbHiringOfferRowTotal(models.AbstractModel):
    """The board's offer row says when the lines came from a total."""
    _inherit = 'pb.hiring'

    @api.model
    def _offer_row(self, offer, full=False):
        row = super()._offer_row(offer, full=full)
        if full and not row.get('money_locked'):
            row['total_note'] = offer.sudo().pb_total_note or ''
        return row
