# -*- coding: utf-8 -*-
"""Who the company pays after a pay run — a fund or an office — and which pay
items of the pay schemes belong to it.

A PAYEE IS A LIST OF PAY ITEMS. The amount owed to it is never typed: it is the
sum of those items on the finished payslips of a month (`fund_payment.py`).
Each item is marked employee share (taken off the person's pay) or employer
share (paid by the company on top), so the owed figure splits the same way the
fund's own statement does.

ONE ITEM, ONE PAYEE. A pay item listed under two payees would be paid twice;
the constraint below refuses it among active payees.

"SUGGEST" READS THE ONE TYPING THE PRODUCT HAS. Components carry a pay role
derived from the scheme's own net-pay formula (`hr.formula.rule.net_role`,
VALUEKIND/NETROLE): "taken off net pay" or "employer cost", plus "included in
another total" for a part of a subtotal. There is no statutory flag and no
country table here (handover §1.1, binding non-goal): the suggestion pairs an
employer cost with the deduction of the same name ("Social insurance (EE)" /
"Social insurance (ER)") and proposes one payee per name. A person reviews,
merges and unticks before anything is created.

WHAT IS NEVER A FUND (WDGAP W2-F, F-3). A loan repayment and the mid-month
advance are taken off pay too, but nobody outside is paid them. They are left
out from the scheme's own settings — "Loan repayments go into" (pb_loans) and
the carry-over setting that types the advance — together with every component
that reads only those (`_pb_not_funds`). A scheme where neither is set says
nothing about them, and Suggest cannot tell them from a fund there.
"""
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

SHARES = [('employee', 'Employee share'), ('employer', 'Employer share')]

#: Pay roles that can be owed to an outside office, and the share they suggest.
ROLE_SHARE = {'deduction': 'employee', 'employer_cost': 'employer'}

#: Money kinds a pay item can be added up in (VALUEKIND `MONEY_ROLE_KINDS`).
MONEY_KINDS = ('money', 'decimal', 'integer')

#: Words that say WHOSE share a component is, not WHAT it is — dropped before
#: two components' names are compared. Plain words, no country codes.
SHARE_WORDS = frozenset("""
employee employees employer employers ee er emp empr company companies staff
worker workers share shares part portion contribution contributions paid by
the of nld nlđ dn người lao động doanh nghiệp công ty chủ sử dụng
karyawan pekerja perusahaan pemberi kerja pt tk
""".split())

#: The same idea for component CODES (SIEMP / SICOMP, EESI / ERSI).
CODE_MARKERS = ('EMPLOYEE', 'EMPLOYER', 'EMPR', 'COMP', 'EMP', 'NLD', 'EE',
                'ER', 'DN', 'CO')


def name_stem(name):
    """'Social Insurance (EE) 8%' -> 'social insurance'."""
    text = (name or '').lower()
    text = re.sub(r'[\d.,]+\s*%?', ' ', text)
    words = [w for w in re.split(r'[^\w]+', text) if w]
    return ' '.join(w for w in words if w not in SHARE_WORDS)


def code_stem(code):
    """'SIEMP' -> 'SI', 'ERSI' -> 'SI', 'HICOMP' -> 'HI'. Empty when nothing
    distinctive is left."""
    code = (code or '').upper()
    for marker in CODE_MARKERS:
        if len(code) > len(marker) + 1:
            if code.endswith(marker):
                return code[:-len(marker)]
            if code.startswith(marker):
                return code[len(marker):]
    return code


def nice_name(name):
    """The proposal's title from a component name, share words removed but the
    reader's own capitals kept: 'Social Insurance (EE)' -> 'Social Insurance'."""
    text = re.sub(r'\([^)]*\)', ' ', name or '')
    text = re.sub(r'[\d.,]+\s*%', ' ', text)
    words = [w for w in re.split(r'\s+', text) if w]
    kept = [w for w in words
            if re.sub(r'[^\w]', '', w).lower() not in SHARE_WORDS]
    out = ' '.join(kept).strip(' -–·:/')
    return out or (name or '').strip()


class PbFundPayee(models.Model):
    _name = 'pb.fund.payee'
    _description = 'Fund or office the company pays'
    _order = 'sequence, name, id'

    name = fields.Char(string='Pay to', required=True,
                       help="The fund or office, as the person paying it knows it "
                            "(for example Social insurance office, Tax office).")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda s: s.env.company)
    currency_id = fields.Many2one(
        'res.currency', string='Usual currency',
        default=lambda s: s.env.company.currency_id,
        help="The money this fund is usually paid in. A pay item from a pay "
             "scheme in another currency is worked out as its own payment — "
             "two currencies are never added together.")
    due_day = fields.Integer(
        string='Due by day', default=15,
        help="The payment is due by this day of the month after the pay month.")
    bank_details = fields.Text(
        string='How to pay them',
        help="Bank, account and anything else the person making the payment "
             "needs. Shown on the board; no bank file is made from it.")
    reference_text = fields.Char(
        string='Reference to quote',
        help="What to write in the payment reference, for example the "
             "company's code at the fund.")
    item_ids = fields.One2many('pb.fund.payee.item', 'payee_id',
                               string='Pay items')
    item_count = fields.Integer(compute='_compute_item_count')

    @api.depends('item_ids')
    def _compute_item_count(self):
        for payee in self:
            payee.item_count = len(payee.item_ids)

    @api.constrains('due_day')
    def _check_due_day(self):
        for payee in self:
            if not 1 <= (payee.due_day or 0) <= 31:
                raise ValidationError(_("The due day is a day of the month, from 1 to 31."))

    @api.constrains('active')
    def _check_items_free(self):
        # Re-activating a payee must not make an item belong to two of them.
        self.mapped('item_ids')._check_one_payee()

    # ------------------------------------------------------------ suggestion
    @api.model
    def _pb_candidate_rules(self, companies):
        """Components of the companies' active pay schemes that can be owed to
        an outside office: printed on the payslip (so there is a line to add
        up), counted in money, taken off net pay or an employer cost, and not
        a part already counted inside another total."""
        rules = self.env['hr.formula.rule'].sudo().search([
            ('config_id.state', '=', 'active'),
            ('config_id.company_id', 'in', companies.ids),
            ('net_role', 'in', list(ROLE_SHARE)),
            ('appears_on_payslip', '=', True),
        ], order='config_id, sequence, id').filtered(
            lambda r: (r.value_kind or 'money') in MONEY_KINDS
            and not r.net_role_detail)
        not_funds = self._pb_not_funds(rules.mapped('config_id'))
        return rules - not_funds

    # WDGAP W2-F (F-3) — what is never a fund, from the scheme's own settings.
    @api.model
    def _pb_not_funds(self, configs):
        """Components Suggest never offers: a scheme's "Loan repayments go
        into" item (pb_loans, read by probe — no dependency), the items its
        carry-over setting types as the mid-month advance (W2-F F-1), and
        every component whose formula reads nothing but those (and fixed
        values) — the "Loan repayment" line an instalment input feeds."""
        Rule = self.env['hr.formula.rule'].sudo()
        out = Rule.browse()
        for config in configs:
            seeds = Rule.browse()
            if 'pb_loan_rule_id' in config._fields and config.pb_loan_rule_id:
                seeds |= config.pb_loan_rule_id
            if hasattr(config, '_pb_advance_rules'):
                seeds |= config._pb_advance_rules()
            if seeds:
                out |= self._pb_read_only_from(config, seeds)
        return out

    @api.model
    def _pb_read_only_from(self, config, seeds):
        """`seeds` plus, to a fixed point, every component of `config` whose
        formula reads at least one of them and otherwise only fixed values."""
        rules = config.rule_ids
        by_ref = {}
        for rule in rules:
            for ref in (rule.code, rule.column_letter):
                if ref:
                    by_ref.setdefault(ref.upper(), rule)
        fixed = rules.filtered(lambda r: r.column_type == 'constant')
        out = seeds & rules
        changed = True
        while changed:
            changed = False
            for rule in rules - out:
                if rule.column_type == 'input' or not rule.formula_dependencies:
                    continue
                reads = rule.browse()
                for ref in rule.formula_dependencies.split(','):
                    hit = by_ref.get(ref.strip().upper())
                    if hit and hit != rule:
                        reads |= hit
                if reads & out and not (reads - out - fixed):
                    out |= rule
                    changed = True
        return out | seeds

    @api.model
    def _pb_suggest(self, companies):
        """Proposed payees, nothing created.

        [{'key', 'name', 'company_id', 'items': [{'rule_id', 'share', 'label',
          'scheme', 'currency'}], 'paired': bool, 'note'}]

        Components already paid to an active payee are left out, so pressing
        Suggest again after accepting proposes only what is still loose.
        """
        taken = set(self.env['pb.fund.payee.item'].sudo().search([
            ('payee_id.active', '=', True),
            ('company_id', 'in', companies.ids)]).mapped('rule_id').ids)
        rules = self._pb_candidate_rules(companies).filtered(
            lambda r: r.id not in taken)
        groups = {}

        def key_for(company, stem):
            return '%s:%s' % (company.id, stem)

        # 1. Within each scheme, pair every employer cost with the deduction
        #    that has the same name (or code) once the share words are gone.
        for config in rules.mapped('config_id'):
            mine = rules.filtered(lambda r, c=config: r.config_id == c)
            deductions = mine.filtered(lambda r: r.net_role == 'deduction')
            employer = mine.filtered(lambda r: r.net_role == 'employer_cost')
            used = set()
            for er in employer:
                stem = name_stem(er.name)
                twin = deductions.filtered(
                    lambda d, s=stem: d.id not in used and s and name_stem(d.name) == s)[:1]
                if not twin:
                    cstem = code_stem(er.code)
                    twin = deductions.filtered(
                        lambda d, c=cstem: d.id not in used and len(c) >= 2
                        and code_stem(d.code) == c)[:1]
                group_stem = stem or code_stem(er.code).lower() or er.code.lower()
                entry = groups.setdefault(key_for(config.company_id, group_stem), {
                    'name': nice_name(er.name), 'company': config.company_id,
                    'rules': [], 'paired': False})
                entry['rules'].append((er, 'employer'))
                if twin:
                    used.add(twin.id)
                    entry['rules'].append((twin, 'employee'))
                    entry['paired'] = True
            for ded in deductions.filtered(lambda d: d.id not in used):
                stem = name_stem(ded.name) or ded.code.lower()
                entry = groups.setdefault(key_for(config.company_id, stem), {
                    'name': nice_name(ded.name), 'company': config.company_id,
                    'rules': [], 'paired': False})
                entry['rules'].append((ded, 'employee'))
        out = []
        for key, entry in sorted(groups.items(), key=lambda kv: kv[1]['name'].lower()):
            items = []
            for rule, share in sorted(entry['rules'], key=lambda rs: (
                    rs[1] != 'employee', rs[0].config_id.name or '', rs[0].sequence)):
                items.append({
                    'rule_id': rule.id, 'share': share,
                    'label': rule.name or rule.code, 'code': rule.code,
                    'scheme': rule.config_id.name or '',
                    'currency': rule.config_id.currency_id.name or '',
                })
            # WDGAP W2-F (F-3): loan repayments and the mid-month advance are
            # left out above, so the old "untick it" note is gone.
            note = ''
            out.append({'key': key, 'name': entry['name'],
                        'company_id': entry['company'].id,
                        'items': items, 'paired': entry['paired'], 'note': note})
        return out


class PbFundPayeeItem(models.Model):
    _name = 'pb.fund.payee.item'
    _description = 'Pay item owed to a fund or office'
    _order = 'payee_id, share, id'

    payee_id = fields.Many2one('pb.fund.payee', required=True, index=True,
                               ondelete='cascade')
    rule_id = fields.Many2one('hr.formula.rule', string='Pay item', required=True,
                              index=True, ondelete='cascade')
    share = fields.Selection(SHARES, required=True, default='employee')
    config_id = fields.Many2one(related='rule_id.config_id', store=True,
                                string='Pay scheme', index=True)
    code = fields.Char(related='rule_id.code', store=True)
    company_id = fields.Many2one(related='payee_id.company_id', store=True, index=True)

    _payee_rule_uniq = models.Constraint(
        'unique(payee_id, rule_id)',
        'This pay item is already listed for this payee.')

    @api.constrains('rule_id', 'payee_id')
    def _check_one_payee(self):
        for item in self:
            if not item.payee_id.active:
                continue
            other = self.sudo().search([
                ('rule_id', '=', item.rule_id.id),
                ('id', '!=', item.id),
                ('payee_id.active', '=', True)], limit=1)
            if other:
                raise ValidationError(_(
                    "“%(item)s” is already paid to %(payee)s. A pay item can "
                    "belong to one payee only, or it would be paid twice.",
                    item=item.rule_id.name or item.rule_id.code,
                    payee=other.payee_id.name))
            if item.rule_id.config_id.company_id != item.payee_id.company_id:
                raise ValidationError(_(
                    "“%s” belongs to a pay scheme of another company.",
                    item.rule_id.name or item.rule_id.code))

    @api.model
    def _pb_clean_items(self, items, company):
        """[(0, 0, vals)] from [{'rule_id', 'share'}] sent by the board —
        every rule re-read and checked (company, money, exists)."""
        out, seen = [], set()
        Rule = self.env['hr.formula.rule'].sudo()
        for row in items or []:
            try:
                rule = Rule.browse(int(row.get('rule_id') or 0)).exists()
            except (TypeError, ValueError, AttributeError):
                rule = Rule
            if not rule or rule.id in seen:
                continue
            if rule.config_id.company_id != company:
                raise UserError(_("“%s” belongs to a pay scheme of another company.",
                                  rule.name or rule.code))
            share = row.get('share') if row.get('share') in dict(SHARES) else \
                ROLE_SHARE.get(rule.net_role, 'employee')
            seen.add(rule.id)
            out.append({'rule_id': rule.id, 'share': share})
        return out
