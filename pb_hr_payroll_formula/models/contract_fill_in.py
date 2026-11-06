# -*- coding: utf-8 -*-
"""FILLIN P1 — a new contract starts with the paying scheme's usual answers.

THE QUESTION THIS ANSWERS. A Rize client asked whether "BPJS TK covered" on a
new Indonesian hire is an amount or an ID number. The honest answer was worse:
a new contract carried NO line for it, so the engine read 0 — "not covered" —
for every person nobody had typed a value for. The owner ruled (FILLIN ledger,
2026-11-04): a new contract is FILLED IN with the scheme's usual answers, every
value Payobook fills in by itself is marked, and a person can see it, confirm
it or change it.

WHERE THE USUAL ANSWER LIVES (ledger D1). On the scheme RULE
(`hr.formula.rule.default_value`), never on the flat catalogue template: one
scheme is one country is one set of usual answers, and the catalogue is shared
by every scheme on the database (SCHEMECTX P2).

WHAT IS NEVER DONE (ledger rule 9 — the old fan-out must not come back).
A line is added only for a rule of the scheme that PAYS the person, only when
that rule's usual answer is a non-zero number, and only for a code the contract
does not already carry. "No" stays the absence of a line, exactly as the engine
already reads it (`payroll_import_batch.py` `contract_component_default` → 0).

FILLING IN NEVER BLOCKS A CONTRACT (ledger rule 10). Each contract is filled
inside its own savepoint and any failure is a WARNING with the traceback.

TWO TRIGGERS (ledger D5): `hr.contract.create` here, and `pb_scheme_map`'s
"Paid by" recompute when a person's paying scheme goes from unknown to known.
Neither ever overwrites a line.
"""

import json
import logging
import math
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

#: Contracts that are filled in. A closed or cancelled contract is history.
FILL_STATES = ('draft', 'open')

#: Value kinds a Float usual answer makes sense for. A text, reference or date
#: component is never filled from `default_value` (it is a number column).
NUMERIC_FILL_KINDS = ('money', 'decimal', 'integer', 'quantity', 'rate',
                      'boolean')

#: "Looks right" needs the same right as editing the contract — the contract
#: panel's `_cd_may_write` (`pb_contracts/models/pb_contract_360.py:245-260`),
#: mirrored here without importing `pb_contracts`, plus the payroll manager.
READ_GROUPS = ('hr.group_hr_user',
               'pb_hr_payroll_base.group_payroll_base_officer')
CHECK_GROUPS = ('hr_contract.group_hr_contract_manager',
                'om_hr_payroll.group_hr_payroll_manager')

_LABEL_PAIR = re.compile(r'^\s*(-?\d+(?:\.\d+)?)\s*=\s*(\S.*?)\s*$')


def parse_value_labels(text):
    """`'0=No;1=Yes'` → `[{'value': 0.0, 'label': 'No'}, …]`.

    Anything that is not a clean list of `number=words` pairs — a duplicate
    number, a pair with no words, a word where the number goes — gives `[]`.
    Never raises: a display layer must not fall over on a typo.
    """
    if not text or not isinstance(text, str):
        return []
    out, seen = [], set()
    for part in text.split(';'):
        if not part.strip():
            continue        # a trailing ";" is a habit, not an error
        match = _LABEL_PAIR.match(part)
        if not match:
            return []
        try:
            value = float(match.group(1))
        except (TypeError, ValueError):
            return []
        label = match.group(2).strip()
        if not label or value in seen:
            return []
        seen.add(value)
        out.append({'value': value, 'label': label})
    return out


def _yes_no(options):
    """True when the words are exactly No for 0 and Yes for 1 (any case)."""
    return (len(options) == 2
            and {(o['value'], o['label'].strip().casefold()) for o in options}
            == {(0.0, 'no'), (1.0, 'yes')})


def _finite(raw):
    """A number from a number or a plain numeric string, else None."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        number = float(raw)
    else:
        try:
            number = float(str(raw).strip())
        except (TypeError, ValueError):
            return None
    return number if math.isfinite(number) else None


def value_from_words(options, raw, name=''):
    """PDR P2 W2 — the ONE place a typed word becomes the stored number.

    `options` are a rule's parsed words. Accepts, any case and trimmed:
    Y / N / Yes / No when the words are a 0 / 1 pair, any word of the rule,
    or the number itself. Anything else raises ValueError with a plain
    sentence ("Final tax period needs Y or N."). Never returns a silent 0
    for a word it does not know. A blank is the caller's business (blank
    keeps its own meaning everywhere) and raises too.
    """
    pair = {o['value'] for o in options} == {0.0, 1.0}
    if isinstance(raw, bool) and pair:
        return 1.0 if raw else 0.0
    number = _finite(raw)
    if number is not None:
        return number
    text = str(raw if raw is not None else '').strip().casefold()
    if text:
        for option in options:
            if option['label'].strip().casefold() == text:
                return option['value']
        if pair:
            yes = {'y', 'yes', 'true'}
            no = {'n', 'no', 'false'}
            if text in yes:
                return 1.0
            if text in no:
                return 0.0
    who = name or _('This value')
    if _yes_no(options) or (pair and not text):
        raise ValueError(_('%s needs Y or N.') % who)
    raise ValueError(_('%(name)s needs one of: %(words)s.') % {
        'name': who, 'words': ', '.join(o['label'] for o in options)})


# =========================================================================
# Words for each value (ledger D4) — display only, the engine keeps numbers
# =========================================================================
class HrFormulaRuleValueLabels(models.Model):
    _inherit = 'hr.formula.rule'

    value_labels = fields.Char(
        string='Words for each value',
        help='Optional. How a value reads on screen, e.g. "0=No;1=Yes" or '
             '"0=None;1=Insurance tax;2=All tax". Screens and the pay data '
             'file show the words (Y / N for Yes / No); formulas keep using '
             'the numbers, and the file still accepts them.')
    # PDR P2 W3 — one plain line that explains the words, shown under the
    # choice on the pay data worksheet and the contract panel.
    value_labels_hint = fields.Char(
        string='What the words mean',
        help='Optional. One short line shown under the choice, e.g. "All tax '
             '= the company pays all the employee\'s tax (net salary)."')

    def value_label_is_yes_no(self):
        """Exactly No for 0 and Yes for 1 — written as Y / N in the file."""
        self.ensure_one()
        return _yes_no(self.value_label_options())

    def value_to_text(self, amount, short=False):
        """PDR P2 — how a stored number is shown: the word, `Y` / `N` when
        `short` and the words are Yes / No, the number when no word matches
        (a value is never hidden), and `''` for a blank."""
        self.ensure_one()
        if amount is None or amount == '' or amount is False:
            return ''
        word = self.value_label_for(amount)
        if not word:
            return amount
        if short and self.value_label_is_yes_no():
            return 'Y' if word.strip().casefold() == 'yes' else 'N'
        return word

    def value_from_text(self, raw, name=None):
        """PDR P2 W2 — a typed or uploaded word as the stored number (see
        `value_from_words`). Raises ValueError with a plain sentence."""
        self.ensure_one()
        return value_from_words(self.value_label_options(), raw,
                                name or self.name or self.code)

    def value_label_options(self):
        """The parsed words for ONE rule; `[]` when there are none or the text
        does not read."""
        self.ensure_one()
        return parse_value_labels(self.value_labels or '')

    def value_label_for(self, amount):
        """The words for one value, or `''`."""
        self.ensure_one()
        if isinstance(amount, str) and not amount.strip():
            return ''
        try:
            number = float(amount or 0.0)
        except (TypeError, ValueError):
            return ''
        for option in self.value_label_options():
            if abs(option['value'] - number) < 1e-9:
                return option['label']
        return ''

    def value_label_control(self):
        """How P2 should offer this value: `'toggle'` (exactly 0 and 1, or a
        Yes / No kind), `'select'` (any other set of words), or `''`."""
        self.ensure_one()
        options = self.value_label_options()
        if options and {o['value'] for o in options} == {0.0, 1.0}:
            return 'toggle'
        if options:
            return 'select'
        if self.value_kind == 'boolean':
            return 'toggle'
        return ''

    def value_word_choices(self):
        """The words as a screen offers them: Yes first for a 0 / 1 pair (as
        the contract panel does), file order otherwise."""
        self.ensure_one()
        options = self.value_label_options()
        if self.value_label_control() == 'toggle':
            options = sorted(options, key=lambda o: -o['value'])
        return options

    @api.model
    def _pb_component_rules(self, codes, company=None):
        """`{code: rule}` for contract component codes — the same join and
        the same preference as the contract panel (`pb_contracts`
        `_cd_rule_by_code`): the live scheme of the contract's own company
        first, id order only breaks a tie."""
        codes = [c for c in (codes or []) if c]
        out = {}
        if not codes:
            return out

        def preference(rule):
            config = rule.config_id
            same = bool(company and config and config.company_id.id == company.id)
            return (0 if same else 1, 0 if config and config.state == 'active' else 1, rule.id)

        for rule in sorted(self.sudo().search([('code', 'in', codes)], order='id'), key=preference):
            out.setdefault(rule.code, rule)
        return out


class HrFormulaConfigUsualAnswers(models.Model):
    _inherit = 'hr.formula.config'

    def _pb_apply_usual_answers(self, spec):
        """Set usual answers and words on this scheme's rules, idempotently.

        `spec` = `{code: {'default_value': float, 'value_labels': str}}`.
        Writes a field only when it differs, so a second run writes nothing.
        Returns `{'written': [codes], 'missing': [codes]}`. Touches the rules
        only — never a contract line (no backfill, ledger non-goal).
        """
        self.ensure_one()
        Rule = self.env['hr.formula.rule'].sudo()
        written, missing = [], []
        for code, wanted in spec.items():
            rule = Rule.search([('config_id', '=', self.id),
                                ('code', '=', code)], limit=1)
            if not rule:
                missing.append(code)
                continue
            vals = {}
            if 'default_value' in wanted and abs(
                    (rule.default_value or 0.0)
                    - float(wanted['default_value'] or 0.0)) > 1e-9:
                vals['default_value'] = float(wanted['default_value'] or 0.0)
            if 'value_labels' in wanted and (rule.value_labels or '') != (
                    wanted['value_labels'] or ''):
                vals['value_labels'] = wanted['value_labels'] or False
            if vals:
                rule.write(vals)
                written.append(code)
        return {'written': written, 'missing': missing}


# =========================================================================
# The catalogue row for a rule — ONE search-by-code
# =========================================================================
class HrContractAdvantageTemplateForRule(models.Model):
    _inherit = 'hr.contract.advantage.template'

    @api.model
    def template_for_rule(self, rule):
        """The catalogue row a rule's contract line files under, made when
        missing. Moved verbatim from
        `payroll_import_batch._get_or_create_advantage_template`, which now
        calls this."""
        template = self.search([('code', '=', rule.code)], limit=1)
        wanted_type = 'text' if getattr(rule, 'is_text_component', False) else 'amount'
        if not template:
            template = self.create({
                'name': rule.name or rule.code,
                'code': rule.code,
                'lower_bound': 0.0,
                'upper_bound': 0.0,
                'default_value': 0.0,
                'value_type': wanted_type,
            })
        elif 'value_type' in template._fields and template.value_type != wanted_type:
            # An existing template is NEVER flipped. Every line already filed under it
            # was written as the other kind, and re-typing the template would silently
            # reinterpret all of that history. The workbook is told, not obeyed.
            _logger.warning(
                "Contract component sync: rule %s wants value type %s but template %s "
                "is already %s — keeping the template as it is.",
                rule.code, wanted_type, template.code, template.value_type)
        return template


# =========================================================================
# The mark on a line (ledger D3)
# =========================================================================
class HrContractAdvantageFillIn(models.Model):
    _inherit = 'hr.contract.advantage'

    pb_fill = fields.Selection(
        [('auto', 'Filled in by Payobook')], string='Filled in by',
        copy=False)
    pb_checked_by = fields.Many2one('res.users', string='Checked by',
                                    copy=False)
    pb_checked_at = fields.Datetime(string='Checked on', copy=False)

    def write(self, vals):
        res = super().write(vals)
        # A person (drawer, Records Desk) or a pay data file wrote the value:
        # it is theirs now. `pb_fill_in_write` is the ONLY way to write a
        # line without clearing the mark (rail §4).
        if ({'amount', 'text_value'} & set(vals)) \
                and not self.env.context.get('pb_fill_in_write'):
            touched = self.filtered(lambda line: line.pb_fill)
            if touched:
                super(HrContractAdvantageFillIn, touched).write({
                    'pb_fill': False,
                    'pb_checked_by': self.env.uid,
                    'pb_checked_at': fields.Datetime.now(),
                })
        return res


# =========================================================================
# PDR P2 W3b — the full contract form's component list shows the words
# =========================================================================
class HrContractAdvantageWords(models.Model):
    _inherit = 'hr.contract.advantage'

    # JSON list of {value, label}; '' when the component's rule has no words.
    pb_value_words = fields.Char(compute='_compute_pb_value_words')
    pb_amount_word = fields.Char(
        string='Answer', compute='_compute_pb_amount_word',
        inverse='_inverse_pb_amount_word', readonly=False,
        help='The answer in words. The contract keeps the number behind it.')

    def _pb_word_rules(self):
        """`{line id or NewId: rule with words}` for these lines."""
        out = {}
        Rule = self.env['hr.formula.rule']
        by_company = {}
        for line in self:
            code = (line.advantage_template_id.code or '').strip()
            if code:
                company = line.contract_id.company_id or self.env.company
                by_company.setdefault(company, set()).add(code)
        rules = {}
        for company, codes in by_company.items():
            for code, rule in Rule._pb_component_rules(list(codes), company).items():
                rules[(company.id, code)] = rule
        for line in self:
            company = line.contract_id.company_id or self.env.company
            rule = rules.get((company.id, (line.advantage_template_id.code or '').strip()))
            if rule and (line.value_type or 'amount') != 'text' and rule.value_label_options():
                out[line.id] = rule
        return out

    @api.depends('advantage_template_id', 'contract_id.company_id')
    def _compute_pb_value_words(self):
        rules = self._pb_word_rules()
        for line in self:
            rule = rules.get(line.id)
            line.pb_value_words = json.dumps(rule.value_word_choices()) if rule else ''

    @api.depends('amount', 'advantage_template_id', 'contract_id.company_id')
    def _compute_pb_amount_word(self):
        rules = self._pb_word_rules()
        for line in self:
            rule = rules.get(line.id)
            if not rule:
                line.pb_amount_word = False
                continue
            shown = rule.value_to_text(line.amount or 0.0)
            # An unmatched number shows as itself, never hidden.
            line.pb_amount_word = shown if isinstance(shown, str) else ('%g' % shown)

    def _pb_words_to_amount(self):
        rules = self._pb_word_rules()
        for line in self:
            rule = rules.get(line.id)
            if not rule or line.pb_amount_word in (False, None, ''):
                continue
            try:
                amount = rule.value_from_text(line.pb_amount_word,
                                              line.advantage_template_id.name or rule.name)
            except ValueError as error:
                raise ValidationError(str(error)) from None
            if abs((line.amount or 0.0) - amount) > 1e-9:
                # "No" keeps today's meaning: a line holding 0, never deleted.
                line.amount = amount

    def _inverse_pb_amount_word(self):
        self._pb_words_to_amount()

    @api.onchange('pb_amount_word')
    def _onchange_pb_amount_word(self):
        self._pb_words_to_amount()


# =========================================================================
# The fill, and "Looks right"
# =========================================================================
class HrContractFillIn(models.Model):
    _inherit = 'hr.contract'

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        if not self.env.context.get('pb_skip_fill_in'):
            contracts._pb_fill_in_defaults()
        return contracts

    def _pb_fill_in_defaults(self):
        """Add the paying scheme's usual answers to every contract in self
        that lacks them. Never raises, never overwrites. Returns how many
        lines were written."""
        made = 0
        try:
            if not self._pb_fill_anything_to_fill():
                return 0
        except Exception:                           # noqa: BLE001
            _logger.warning('pb fill-in: could not read the usual answers',
                            exc_info=True)
            return 0
        for contract in self:
            try:
                # Own savepoint: a bound check or a broken map that fails half
                # way leaves nothing behind, and the contract still saves.
                with self.env.cr.savepoint():
                    made += self._pb_fill_one(contract)
            except Exception:                       # noqa: BLE001
                _logger.warning('pb fill-in: contract %s', contract.id,
                                exc_info=True)
        return made

    @api.model
    def _pb_fill_anything_to_fill(self):
        """Does ANY live scheme on this database carry a usual answer?

        One indexed count. On a database where nobody has set one (every
        database but rize Indonesia on the day this shipped) a contract create
        costs nothing more than it did — no map walk, no flush.
        """
        return bool(self.env['hr.formula.rule'].sudo().search_count([
            ('config_id.state', '=', 'active'),
            ('is_contract_component', '=', True),
            ('is_text_component', '=', False),
            ('default_value', '!=', 0.0),
        ], limit=1))

    def _pb_fill_schemes(self, employee):
        """The active scheme(s) that pay this person, or an empty recordset
        when nobody does or the answer is unknown (FI3)."""
        Config = self.env['hr.formula.config'].sudo()
        scope = Config.component_scope_for_employee(employee) or {}
        if not scope.get('known'):
            return Config.browse()
        ids = []
        for row in scope.get('schemes') or []:
            config_id = row.get('id') if isinstance(row, dict) else getattr(
                row, 'id', 0)
            if config_id and config_id not in ids:
                ids.append(config_id)
        # Only a LIVE scheme gives usual answers: an archived one can still
        # carry a stale default (rize 3938 holds a salary in one), and the
        # map never resolves to it anyway.
        return Config.browse(ids).exists().filtered(
            lambda c: c.state == 'active')

    def _pb_fill_one(self, contract):
        if not contract.employee_id or contract.state not in FILL_STATES:
            return 0
        # The map answers in raw SQL (`pb.scheme.map._departments_for`), so a
        # team written a moment ago in this transaction must reach the table
        # first or the person reads as covered by nobody.
        self.env.flush_all()
        schemes = self._pb_fill_schemes(contract.employee_id)
        if not schemes:
            return 0
        Template = self.env['hr.contract.advantage.template'].sudo()
        # Written with sudo: an HR officer may create a contract but holds
        # read-only access to its component lines (om_hr_payroll ACL).
        Line = self.env['hr.contract.advantage'].sudo().with_context(
            pb_fill_in_write=True)
        Change = self.env['hr.contract.advantage.change'].sudo()
        have = {(line.advantage_template_id.code or '').strip()
                for line in contract.sudo().advantages_ids}      # FI2
        made = 0
        for scheme in schemes:
            rules = scheme.rule_ids.filtered(
                lambda r: r.is_contract_component
                and not r.is_text_component
                and (r.value_kind or 'money') in NUMERIC_FILL_KINDS
                and (r.code or '').strip()
                and abs(r.default_value or 0.0) > 1e-9
            ).sorted(lambda r: (r.sequence, r.id))
            for rule in rules:
                code = rule.code.strip()
                if code in have:
                    continue        # first scheme wins; a line is never overwritten
                template = Template.template_for_rule(rule)
                if (template.value_type or 'amount') != 'amount':
                    continue        # never put a number on a text component
                Line.create({
                    'contract_id': contract.id,
                    'advantage_template_id': template.id,
                    'amount': rule.default_value,
                    'pb_fill': 'auto',
                })
                Change.log(
                    contract, template, 0.0, rule.default_value,
                    'auto_default',
                    notes='Filled in from the usual answer on %s'
                    % (scheme.name or ''),
                    user=self.env.user,
                    effective_date=contract.date_start or None)
                have.add(code)
                made += 1
        if made:
            _logger.info('pb fill-in: %s lines on contract %s for %s', made,
                         contract.id, ', '.join(schemes.mapped('name')))
        return made

    # ----------------------------------------------------------- the review
    def pb_fillin_unchecked(self):
        """The lines Payobook filled in that nobody has checked yet."""
        return self.mapped('advantages_ids').filtered(
            lambda line: line.pb_fill == 'auto' and not line.pb_checked_at)

    @api.model
    def _pb_has_group(self, xmlid):
        try:
            return bool(self.env.user.has_group(xmlid))
        except Exception:   # noqa: BLE001 — a group a build does not have
            return False

    @api.model
    def _pb_fillin_may_check(self):
        """Same right as saving the contract panel: may read contracts, holds
        the contract-manager (or payroll-manager) role, and the ACL allows a
        contract write."""
        if self.env.su:
            return True
        user = self.env.user
        if not (user._is_admin()
                or any(self._pb_has_group(g) for g in READ_GROUPS)):
            return False
        if not any(self._pb_has_group(g) for g in CHECK_GROUPS):
            return False
        try:
            self.env['hr.contract'].check_access('write')
            return True
        except Exception:   # noqa: BLE001 — an ACL question, not a crash
            return False

    def pb_fillin_check(self, line_ids=None):
        """"Looks right": stamp the unchecked filled-in lines of these
        contracts (all of them, or only `line_ids`). The value and the
        `pb_fill` mark stay; one `checked` row is written per line. Returns
        how many lines were stamped."""
        if not self._pb_fillin_may_check():
            raise AccessError(_(
                "You cannot confirm the answers on a contract. Ask an "
                "administrator for the right to change contracts."))
        if not self.env.su:
            self.check_access('write')
        lines = self.sudo().pb_fillin_unchecked()
        if line_ids is not None:
            wanted = {int(i) for i in (line_ids or []) if i}
            lines = lines.filtered(lambda line: line.id in wanted)
        if not lines:
            return 0
        now = fields.Datetime.now()
        lines.with_context(pb_fill_in_write=True).write({
            'pb_checked_by': self.env.uid,
            'pb_checked_at': now,
        })
        Change = self.env['hr.contract.advantage.change'].sudo()
        for line in lines:
            Change.log(line.contract_id, line.advantage_template_id,
                       line.amount, line.amount, 'checked',
                       notes='Checked by %s, no change' % (
                           self.env.user.name or ''),
                       user=self.env.user)
        return len(lines)
