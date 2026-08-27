# -*- coding: utf-8 -*-
"""NETROLE — a component's category comes from what NET pay does with it.

The categoriser this replaces read the component's CODE and guessed:
``'SI' in code`` meant a deduction, so ``ACTUBASISALA`` (actual basic salary)
was filed as one; ``'TAX' in code`` meant a deduction, so the two TAXABLE
INCOME *bases* were filed as ones too. On ABM's June 2026 run that reported
₫5,058,029,390 of deductions against ₫1.9bn of gross, when the only sum an
employee actually loses is ₫199,500,000.

The truth was already in the scheme, one row down: ``NETPAY = BP-CD+CC``.
Whatever net pay SUBTRACTS is a deduction; whatever it ADDS is an earning;
whatever never reaches it at all is information, or a cost the employer bears.
This module derives exactly that, by parsing every formula in a scheme into a
signed reference graph and propagating backwards from the net-pay component.

Three things make it more than a sign walk:

* **Details.** ``SIHIIUTOT105`` is subtracted from net pay, and so is
  ``TOTALDEDUCTI`` — but only because the second one already contains the
  first. Counting both doubles the money. A component folded into a same-role
  roll-up is a `detail`: it keeps its category so a payslip still reads
  correctly, and it is excluded from the run's totals.
* **Bases are not contributions.** ``SALARYFORSI`` is what the 8% is charged
  ON; ``BASESALARY`` is what the prorated basic is derived FROM. A reference
  that only ever arrives multiplied, divided or capped is a *derived* edge, and
  a component that reaches net pay additively is read through that path first.
  Without this, every base salary in the world is simultaneously an earning
  (through gross) and a deduction (through the insurance it is charged on).
* **Employer cost.** ``TOTACOSTTOER = NETPAY + SIHIUITOT215 + TRADEUNIOER2``
  never reaches net pay; it CONTAINS it. Its other addends are what the
  employer pays on top, not what the employee loses.

Nothing here runs by itself. Classification is invoked — on import, on repair,
or from a screen — never ambiently, because a formula edit would otherwise
rewrite a person's category choices behind their back.
"""

import logging
import re

from odoo import _, api, fields, models

from ..formula_engine.column_manager import ColumnManager

_logger = logging.getLogger(__name__)

CERTAIN = 'certain'
LIKELY = 'likely'
REVIEW = 'review'

_CONF_RANK = {CERTAIN: 0, LIKELY: 1, REVIEW: 2}

#: Guard against a pathological scheme: the relaxation below is O(rounds x edges)
#: and a scheme with thousands of rules should degrade to "unclassified", never
#: to a hung worker.
_MAX_ROUNDS = 200

#: Functions whose FIRST argument carries the value through unchanged and whose
#: remaining arguments are precision/caps, not contributions.
_FIRST_ARG_FUNCS = {
    'ROUND', 'ROUNDUP', 'ROUNDDOWN', 'MROUND', 'INT', 'TRUNC',
    'FLOOR', 'CEILING', 'MIN', 'MAX',
}
#: Functions that are pure addition over their arguments.
_ADDITIVE_FUNCS = {'SUM', 'SUMPRODUCT', 'AVERAGE', 'SUBTOTAL'}
#: Functions whose arguments are a QUESTION, not money. Their references say
#: nothing about what net pay does with the component.
_PREDICATE_FUNCS = {
    'ISBLANK', 'ISNUMBER', 'ISTEXT', 'ISERROR', 'ISNA', 'AND', 'OR', 'NOT',
    'EXACT', 'COUNTA', 'COUNT', 'LEN',
}
#: Functions whose sign cannot be known from the formula text.
_SIGN_UNKNOWN_FUNCS = {'ABS', 'SIGN'}

_NET_NAME_HINTS = ('netpay', 'net pay', 'nettopay', 'thuclanh', 'thuc lanh',
                   'thựclãnh', 'thực lãnh', 'luongthucnhan')


# ---------------------------------------------------------------------------
# A very small Excel expression parser.
#
# Regex alone cannot do this job: `SUM(AE5:AX5)+BM5` needs the range expanded,
# `-B5` needs the unary minus, `IF(AS5="YES",BQ5*8%,0)` needs the condition told
# apart from the branches, and `U5/AB5*AC5` needs to know which references sit
# under the division bar. All four appear in the very first scheme this ran on.
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?%?|\.\d+%?)
    | (?P<ident>[A-Za-z][A-Za-z0-9]*)
    | (?P<op><=|>=|<>|[-+*/^&(),:<>=])
    | (?P<other>.)
    """,
    re.VERBOSE,
)


def _tokenize(text):
    tokens = []
    for m in _TOKEN_RE.finditer(text):
        kind = m.lastgroup
        if kind in ('ws', 'other'):
            continue
        tokens.append((kind, m.group()))
    return tokens


class _ExcelExpressionParser:
    """Recursive descent over the operator grammar Excel actually uses."""

    def __init__(self, tokens):
        self._tokens = tokens
        self._pos = 0

    # -- token helpers ----------------------------------------------------
    def _peek(self):
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return (None, None)

    def _take(self):
        tok = self._peek()
        self._pos += 1
        return tok

    def _accept_op(self, *values):
        kind, value = self._peek()
        if kind == 'op' and value in values:
            self._pos += 1
            return value
        return None

    # -- grammar ----------------------------------------------------------
    def parse(self):
        node = self._comparison()
        # Anything left over is a formula shape this parser does not model;
        # the caller keeps what it understood and lowers its confidence.
        return node, self._pos >= len(self._tokens)

    def _comparison(self):
        left = self._concat()
        while True:
            op = self._accept_op('=', '<>', '<=', '>=', '<', '>')
            if not op:
                return left
            right = self._concat()
            left = ('cmp', left, right)

    def _concat(self):
        left = self._additive()
        while self._accept_op('&'):
            right = self._additive()
            left = ('cmp', left, right)  # text join carries no signed money
        return left

    def _additive(self):
        terms = [(1, self._multiplicative())]
        while True:
            op = self._accept_op('+', '-')
            if not op:
                break
            terms.append((1 if op == '+' else -1, self._multiplicative()))
        if len(terms) == 1 and terms[0][0] == 1:
            return terms[0][1]
        return ('add', terms)

    def _multiplicative(self):
        factors = [(False, self._unary())]
        while True:
            op = self._accept_op('*', '/')
            if not op:
                break
            factors.append((op == '/', self._unary()))
        if len(factors) == 1:
            return factors[0][1]
        return ('mul', factors)

    def _unary(self):
        op = self._accept_op('-', '+')
        if op == '-':
            return ('neg', self._unary())
        if op == '+':
            return self._unary()
        return self._power()

    def _power(self):
        base = self._primary()
        while self._accept_op('^'):
            exponent = self._primary()
            # A reference in an exponent is a shape, not a term.
            base = ('mul', [(False, base), (False, ('opaque', exponent))])
        return base

    def _primary(self):
        kind, value = self._peek()
        if kind == 'num':
            self._take()
            if value.endswith('%'):
                return ('num', float(value[:-1]) / 100.0)
            return ('num', float(value))
        if kind == 'op' and value == '(':
            self._take()
            node = self._comparison()
            self._accept_op(')')
            return node
        if kind == 'ident':
            self._take()
            nxt_kind, nxt_value = self._peek()
            if nxt_kind == 'op' and nxt_value == '(':
                self._take()
                args = self._arguments()
                return ('func', value.upper(), args)
            if nxt_kind == 'op' and nxt_value == ':':
                self._take()
                end_kind, end_value = self._peek()
                if end_kind == 'ident':
                    self._take()
                    return ('range', value, end_value)
                return ('ref', value)
            return ('ref', value)
        # Anything else (a stray comma, an unbalanced paren) ends this branch.
        self._take()
        return ('nil',)

    def _arguments(self):
        args = []
        kind, value = self._peek()
        if kind == 'op' and value == ')':
            self._take()
            return args
        while True:
            args.append(self._comparison())
            if self._accept_op(','):
                continue
            self._accept_op(')')
            return args


def parse_excel_expression(formula):
    """``formula`` -> (ast, fully_parsed). Never raises on malformed input."""
    if not formula:
        return ('nil',), True
    text = str(formula).strip()
    if text.startswith('='):
        text = text[1:]
    text = text.replace('$', '')
    # String literals are replaced wholesale: "La Nga" must never look like two
    # component references.
    text = re.sub(r'"([^"]|"")*"', ' 0 ', text)
    try:
        return _ExcelExpressionParser(_tokenize(text)).parse()
    except RecursionError:
        return ('nil',), False


def _flip(sign):
    return None if sign is None else -sign


def _combine(a, b):
    if a is None or b is None:
        return None
    return a * b


def _contains_reference(node):
    kind = node[0]
    if kind in ('ref', 'range'):
        return True
    if kind in ('num', 'nil'):
        return False
    if kind == 'add':
        return any(_contains_reference(sub) for _s, sub in node[1])
    if kind == 'mul':
        return any(_contains_reference(sub) for _d, sub in node[1])
    if kind in ('neg', 'opaque'):
        return _contains_reference(node[1])
    if kind == 'cmp':
        return _contains_reference(node[1]) or _contains_reference(node[2])
    if kind == 'func':
        return any(_contains_reference(arg) for arg in node[2])
    return False


def collect_signed_references(node, sign=1, derived=False, confidence=CERTAIN,
                             out=None):
    """Flatten an AST into ``[(token_or_range, sign, derived, confidence)]``.

    ``derived`` marks a reference that arrives scaled — multiplied by a rate,
    divided by a divisor, capped against something else. Its sign still
    propagates (8% of a deduction base is still subtracted), but a derived hop
    is evidence of a BASIS relationship, and the walk below prefers additive
    evidence when a component has both.
    """
    if out is None:
        out = []
    kind = node[0]
    if kind in ('num', 'nil'):
        return out
    if kind == 'ref':
        out.append((('ref', node[1]), sign, derived, confidence))
    elif kind == 'range':
        out.append((('range', node[1], node[2]), sign, derived, confidence))
    elif kind == 'neg':
        collect_signed_references(node[1], _flip(sign), derived, confidence, out)
    elif kind == 'opaque':
        collect_signed_references(node[1], None, True, LIKELY, out)
    elif kind == 'cmp':
        # An operand of a comparison is a question being asked, not money
        # moving. `IF(AC5=0, ...)` must not make ACTUWORKHOUR an earning.
        pass
    elif kind == 'add':
        for term_sign, sub in node[1]:
            collect_signed_references(sub, _combine(sign, term_sign), derived,
                                      confidence, out)
    elif kind == 'mul':
        literal_sign = 1
        for _is_div, sub in node[1]:
            if sub[0] == 'num' and sub[1] < 0:
                literal_sign = -literal_sign
        for _is_div, sub in node[1]:
            if not _contains_reference(sub):
                continue
            collect_signed_references(sub, _combine(sign, literal_sign), True,
                                      LIKELY, out)
    elif kind == 'func':
        _collect_function(node, sign, derived, confidence, out)
    return out


def _collect_function(node, sign, derived, confidence, out):
    name, args = node[1], node[2]
    if not args:
        return
    if name in _PREDICATE_FUNCS:
        return
    if name in _SIGN_UNKNOWN_FUNCS:
        for arg in args:
            collect_signed_references(arg, None, True, LIKELY, out)
        return
    if name in _ADDITIVE_FUNCS:
        for arg in args:
            collect_signed_references(arg, sign, derived, confidence, out)
        return
    if name in _FIRST_ARG_FUNCS:
        collect_signed_references(args[0], sign, derived, confidence, out)
        return
    if name == 'IF':
        # The condition decides WHICH branch pays, never HOW MUCH. Both
        # branches contribute, but conditionally — hence `likely`.
        weaker = LIKELY if _CONF_RANK[confidence] < _CONF_RANK[LIKELY] else confidence
        for arg in args[1:]:
            collect_signed_references(arg, sign, derived, weaker, out)
        return
    if name in ('IFERROR', 'IFNA'):
        collect_signed_references(args[0], sign, derived, confidence, out)
        for arg in args[1:]:
            collect_signed_references(arg, sign, derived, LIKELY, out)
        return
    # An unmodelled function: keep the references, admit the uncertainty.
    for arg in args:
        collect_signed_references(arg, sign, True, LIKELY, out)


# ---------------------------------------------------------------------------
# The classifier
# ---------------------------------------------------------------------------

class NetRoleClassification:
    """The result of reading one scheme's formulas as a signed graph."""

    def __init__(self, rules, net_rule):
        self.rules = rules
        self.net_rule = net_rule
        self.roles = {}
        self.details = {}
        self.reasons = {}
        self.confidences = {}


class HrFormulaRuleNetRole(models.Model):
    _inherit = 'hr.formula.rule'

    # No default and no `@api.depends`: an empty value means "nobody has asked
    # yet", and a formula edit must not silently re-decide a category a person
    # accepted. Classification is a verb here, not a reflex.
    net_role = fields.Selection(
        [
            ('earning', 'Added to net pay'),
            ('deduction', 'Taken off net pay'),
            ('net', 'Net pay itself'),
            ('employer_cost', 'Employer cost'),
            ('info', 'Information only'),
            ('mixed', 'Both added and taken off'),
        ],
        string='Net Pay Role',
        help="What the net pay formula does with this component. Derived from "
             "the scheme's own formulas, not from the component's name.",
    )
    net_role_detail = fields.Boolean(
        string='Folded Into a Total',
        help="This component is already included in another component of the "
             "same kind, so a pay run counts the total and not this line. The "
             "line still shows on the payslip.",
    )
    net_role_reason = fields.Char(
        string='Net Pay Role Reason',
        help="The path through the scheme's formulas that decided this role.",
    )
    net_role_confidence = fields.Selection(
        [
            ('certain', 'Certain'),
            ('likely', 'Likely'),
            ('review', 'Needs review'),
        ],
        string='Role Confidence',
        help="How firmly the formulas decide this role. 'Needs review' means a "
             "person has to choose.",
    )


class HrFormulaConfigNetRole(models.Model):
    _inherit = 'hr.formula.config'

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def classify_net_roles(self):
        """Derive and STORE every rule's net-pay role for this scheme.

        Returns a summary dict per config id::

            {config_id: {'counts': {role: n}, 'details': n, 'review': [codes],
                         'net_code': 'NETPAY', 'error': None}}
        """
        summary = {}
        for config in self:
            result = config._build_net_role_classification()
            if result.get('error'):
                summary[config.id] = result
                continue
            classification = result.pop('_classification')
            for rule in config.rule_ids:
                rule.write({
                    'net_role': classification.roles.get(rule.id) or False,
                    'net_role_detail': classification.details.get(rule.id, False),
                    'net_role_reason': classification.reasons.get(rule.id) or False,
                    'net_role_confidence': classification.confidences.get(rule.id) or False,
                })
            summary[config.id] = result
        return summary

    def suggest_categories(self):
        """Return the categories the formulas imply — and write NOTHING.

        Phase 2's review popup feeds on this; a suggestion a person has not
        seen yet must never already be the truth.
        """
        suggestions = []
        for config in self:
            result = config._build_net_role_classification()
            if result.get('error'):
                continue
            classification = result['_classification']
            aggregates = config._net_role_earning_aggregates(classification)
            for rule in config.rule_ids:
                role = classification.roles.get(rule.id)
                if not role:
                    continue
                suggested = config._net_role_category_code(
                    rule, role, classification, aggregates)
                current = rule.category_id.code or ''
                suggestions.append({
                    'rule_id': rule.id,
                    'code': rule.code or '',
                    'name': rule.name or '',
                    'current_category': current,
                    'suggested_category_code': suggested,
                    'role': role,
                    'detail': classification.details.get(rule.id, False),
                    'reason': classification.reasons.get(rule.id) or '',
                    'confidence': classification.confidences.get(rule.id) or REVIEW,
                    'agrees': bool(current) and current == suggested,
                })
        return suggestions

    def apply_suggested_categories(self, rule_ids=None):
        """Write the suggested category onto the rule and its salary rule.

        Payslip lines already created are deliberately NOT touched: a line is a
        historical record of what a payslip said, and rewriting one is a repair
        with its own authorisation, not a side effect of accepting a suggestion.
        """
        applied = 0
        wanted = set(rule_ids or [])
        for config in self:
            result = config._build_net_role_classification()
            if result.get('error'):
                continue
            classification = result['_classification']
            aggregates = config._net_role_earning_aggregates(classification)
            for rule in config.rule_ids:
                if wanted and rule.id not in wanted:
                    continue
                role = classification.roles.get(rule.id)
                if not role:
                    continue
                code = config._net_role_category_code(
                    rule, role, classification, aggregates)
                category = config._net_role_category(code)
                if not category:
                    continue
                if rule.category_id.id != category.id:
                    rule.category_id = category.id
                    applied += 1
                if rule.salary_rule_id and rule.salary_rule_id.category_id.id != category.id:
                    rule.salary_rule_id.category_id = category.id
        return applied

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------
    def _net_role_rules(self):
        self.ensure_one()
        return self.rule_ids.sorted(key=lambda r: (r.sequence, r.id))

    def _net_role_find_net_rule(self, rules):
        """The net-pay component, or an empty recordset. Never a guess."""
        for rule in rules:
            if rule.category_id and (rule.category_id.code or '').upper() == 'NET':
                return rule
        for rule in rules:
            if (rule.code or '').upper() in ('NET', 'NETPAY', 'NETSALARY'):
                return rule
        for rule in rules:
            name = (rule.name or '').strip().lower()
            squashed = name.replace(' ', '')
            if squashed in ('netpay', 'netsalary', 'net') or name in _NET_NAME_HINTS \
                    or squashed in _NET_NAME_HINTS:
                return rule
        return self.env['hr.formula.rule']

    def _net_role_resolvers(self, rules):
        """(code -> rule, letter -> rule, letter_index -> rule)."""
        by_code, by_letter, by_index = {}, {}, {}
        for rule in rules:
            if rule.code:
                by_code.setdefault(rule.code.upper(), rule)
            letter = (rule.column_letter or '').upper()
            if letter:
                by_letter.setdefault(letter, rule)
                try:
                    by_index.setdefault(ColumnManager.letter_to_index(letter), rule)
                except Exception:
                    pass
        return by_code, by_letter, by_index

    @staticmethod
    def _net_role_resolve_token(token, by_code, by_letter):
        """A token is a code first, then a column letter with its row number.

        Order matters: `OT15AMOUNT` is a CODE whose tail is digits, and
        stripping them first would look up column `OT` instead.
        """
        upper = (token or '').upper()
        if not upper:
            return None
        if upper in by_code:
            return by_code[upper]
        if upper in by_letter:
            return by_letter[upper]
        bare = upper.rstrip('0123456789')
        if bare and bare in by_letter:
            return by_letter[bare]
        if bare and bare in by_code:
            return by_code[bare]
        return None

    def _net_role_expand_range(self, start, end, by_index):
        try:
            first = ColumnManager.letter_to_index(
                (start or '').upper().rstrip('0123456789'))
            last = ColumnManager.letter_to_index(
                (end or '').upper().rstrip('0123456789'))
        except Exception:
            return []
        if first > last:
            first, last = last, first
        return [by_index[i] for i in range(first, last + 1) if i in by_index]

    def _net_role_edges(self, rules):
        """``{target_rule_id: [(source_rule_id, sign, derived, confidence)]}``.

        An edge means "the source contributes to the target"; it points the way
        money flows, so the walk below runs it backwards from net pay.
        """
        self.ensure_one()
        by_code, by_letter, by_index = self._net_role_resolvers(rules)
        incoming = {}
        RateTable = self.env['hr.formula.rate.table']
        for rule in rules:
            if rule.column_type != 'formula' or not rule.excel_formula:
                continue
            formula = rule.excel_formula
            if 'BRACKET' in formula.upper():
                # Same expansion `_compute_dependencies` does, and for the same
                # reason: the table CODE is not a component reference.
                try:
                    formula = RateTable.expand_brackets(formula, self)
                except Exception:
                    _logger.warning(
                        "NETROLE: could not expand BRACKET() in %s; reading the "
                        "formula as written", rule.code)
            ast, complete = parse_excel_expression(formula)
            contributions = collect_signed_references(ast)
            base_conf = CERTAIN if complete else LIKELY
            for ref, sign, derived, confidence in contributions:
                if ref[0] == 'ref':
                    source = self._net_role_resolve_token(ref[1], by_code, by_letter)
                    sources = [source] if source else []
                else:
                    sources = self._net_role_expand_range(ref[1], ref[2], by_index)
                for source in sources:
                    if not source or source.id == rule.id:
                        continue
                    conf = confidence if _CONF_RANK[confidence] >= _CONF_RANK[base_conf] \
                        else base_conf
                    incoming.setdefault(rule.id, []).append(
                        (source.id, sign, derived, conf))
        return incoming

    # ------------------------------------------------------------------
    # The walk
    # ------------------------------------------------------------------
    def _build_net_role_classification(self):
        """Everything the three public methods share, computed once."""
        self.ensure_one()
        rules = self._net_role_rules()
        net_rule = self._net_role_find_net_rule(rules)
        if not net_rule:
            return {
                'error': _(
                    "This scheme has no net pay component, so there is nothing "
                    "to read a component's role from. Give one component the "
                    "Net category (or the code NETPAY) and try again."
                ),
                'counts': {}, 'details': 0, 'review': [], 'net_code': '',
            }
        incoming = self._net_role_edges(rules)
        outgoing = {}
        for target, edges in incoming.items():
            for source, sign, derived, conf in edges:
                outgoing.setdefault(source, []).append((target, sign, derived, conf))

        best, best_signs, best_conf = self._net_role_walk(net_rule.id, incoming)
        all_signs = self._net_role_all_signs(net_rule.id, incoming)

        classification = NetRoleClassification(rules, net_rule)
        for rule in rules:
            if rule.id == net_rule.id:
                classification.roles[rule.id] = 'net'
                classification.confidences[rule.id] = CERTAIN
                classification.reasons[rule.id] = _("This is the net pay component.")
                continue
            if rule.id in best_signs:
                signs = best_signs[rule.id]
                if signs == {1}:
                    role = 'earning'
                elif signs == {-1}:
                    role = 'deduction'
                else:
                    role = 'mixed'
                classification.roles[rule.id] = role
                if role == 'mixed':
                    confidence = REVIEW
                elif best[rule.id][0] == 0 and best_conf.get(rule.id) == CERTAIN \
                        and all_signs.get(rule.id) == signs:
                    confidence = CERTAIN
                else:
                    confidence = LIKELY
                classification.confidences[rule.id] = confidence
            else:
                classification.roles[rule.id] = 'info'
                classification.confidences[rule.id] = CERTAIN

        self._net_role_mark_employer_cost(
            classification, net_rule, incoming, outgoing)
        self._net_role_mark_details(classification, net_rule, outgoing)
        self._net_role_write_reasons(classification, net_rule, outgoing, best)

        # A component whose formulas refer to each other in a circle cannot be
        # trusted to a rule of thumb — the walk terminates (costs only grow, so
        # a lap never wins), but what it reports is an artefact of where the lap
        # was entered. Say so rather than sounding sure. (C7: no silent guess.)
        for rule_id in self._net_role_cycle_members(outgoing):
            if rule_id != net_rule.id:
                classification.confidences[rule_id] = REVIEW

        counts = {}
        for role in classification.roles.values():
            counts[role] = counts.get(role, 0) + 1
        review = [r.code for r in rules
                  if classification.confidences.get(r.id) == REVIEW]
        return {
            'error': None,
            'counts': counts,
            'details': sum(1 for v in classification.details.values() if v),
            'review': review,
            'net_code': net_rule.code or '',
            '_classification': classification,
        }

    @staticmethod
    def _net_role_walk(net_id, incoming):
        """Cheapest signed path from every component to net pay.

        Cost is ``(derived hops, hops)``, compared lexicographically, and the
        cheapest cost wins the role. That ordering is the whole reason a base
        salary is an earning: it reaches net pay additively through gross in
        three hops with one scaled hop, and reaches it negatively only through
        the insurance charged ON it — a longer route with the same or more
        scaling. Ties keep BOTH signs, which is what `mixed` means.

        Relaxation rather than Dijkstra: costs only ever grow along an edge, so
        a cycle can never improve one, and a bounded number of rounds gives the
        cycle guard for free.
        """
        best = {net_id: (0, 0)}
        best_signs = {net_id: {1}}
        best_conf = {net_id: CERTAIN}
        for _round in range(_MAX_ROUNDS):
            changed = False
            for target, edges in incoming.items():
                if target not in best:
                    continue
                t_cost = best[target]
                t_signs = best_signs[target]
                t_conf = best_conf[target]
                for source, sign, derived, conf in edges:
                    cost = (t_cost[0] + (1 if derived else 0), t_cost[1] + 1)
                    signs = {_combine(sign, s) for s in t_signs}
                    edge_conf = conf if _CONF_RANK[conf] >= _CONF_RANK[t_conf] else t_conf
                    known = best.get(source)
                    if known is None or cost < known:
                        best[source] = cost
                        best_signs[source] = set(signs)
                        best_conf[source] = edge_conf
                        changed = True
                    elif cost == known:
                        merged = best_signs[source] | signs
                        if merged != best_signs[source]:
                            best_signs[source] = merged
                            changed = True
                        if _CONF_RANK[edge_conf] > _CONF_RANK[best_conf[source]]:
                            best_conf[source] = edge_conf
                            changed = True
            if not changed:
                break
        else:
            _logger.warning("NETROLE: net-pay walk hit the round cap; the "
                            "scheme's formulas may be deeply cyclic.")
        best.pop(net_id, None)
        best_signs.pop(net_id, None)
        best_conf.pop(net_id, None)
        return best, best_signs, best_conf

    @staticmethod
    def _net_role_cycle_members(outgoing):
        """Rule ids sitting on a reference cycle (iterative DFS, no recursion)."""
        WHITE, GREY, BLACK = 0, 1, 2
        colour = {}
        members = set()
        nodes = set(outgoing)
        for edges in outgoing.values():
            nodes.update(target for target, *_rest in edges)
        for start in nodes:
            if colour.get(start, WHITE) != WHITE:
                continue
            stack = [(start, iter([t for t, *_r in outgoing.get(start, [])]))]
            path = [start]
            on_path = {start}
            colour[start] = GREY
            while stack:
                node, it = stack[-1]
                advanced = False
                for nxt in it:
                    if nxt in on_path:
                        members.update(path[path.index(nxt):])
                        continue
                    if colour.get(nxt, WHITE) == WHITE:
                        colour[nxt] = GREY
                        path.append(nxt)
                        on_path.add(nxt)
                        stack.append(
                            (nxt, iter([t for t, *_r in outgoing.get(nxt, [])])))
                        advanced = True
                        break
                if not advanced:
                    colour[node] = BLACK
                    stack.pop()
                    on_path.discard(node)
                    if path and path[-1] == node:
                        path.pop()
        return members

    @staticmethod
    def _net_role_all_signs(net_id, incoming):
        """Every sign reachable by ANY path — the honesty check on the cheapest
        one. A component whose cheap path says 'earning' while a longer one says
        'deduction' is `likely`, never `certain`."""
        signs = {net_id: {1}}
        for _round in range(_MAX_ROUNDS):
            changed = False
            for target, edges in incoming.items():
                if target not in signs:
                    continue
                for source, sign, _derived, _conf in edges:
                    produced = {_combine(sign, s) for s in signs[target]}
                    have = signs.setdefault(source, set())
                    if not produced <= have:
                        have |= produced
                        changed = True
            if not changed:
                break
        signs.pop(net_id, None)
        return signs

    def _net_role_mark_employer_cost(self, classification, net_rule, incoming,
                                     outgoing):
        """``TOTACOSTTOER = NETPAY + SIHIUITOT215 + TRADEUNIOER2``.

        A component that ADDS net pay to something else is not paid to the
        employee — it is a total the employer carries, and everything else it
        adds up is what the employer pays on top. Those addends never reach net
        pay themselves, which is exactly why the walk above left them as `info`.
        """
        seeds = set()
        totals = set()
        for target, edges in incoming.items():
            references_net_positively = any(
                source == net_rule.id and sign == 1 and not derived
                for source, sign, derived, _conf in edges)
            if not references_net_positively:
                continue
            if classification.roles.get(target) not in (None, 'info'):
                continue
            totals.add(target)
            for source, _sign, _derived, _conf in edges:
                if source == net_rule.id:
                    continue
                if classification.roles.get(source) == 'info':
                    seeds.add(source)
        if not seeds and not totals:
            return
        # Walk BACK from the seeds: whatever feeds an employer contribution and
        # never reaches net pay is employer cost too (the 17.5% / 3% / 1% parts
        # behind a 21.5% total).
        pending = list(seeds)
        reached = set(seeds)
        while pending:
            node = pending.pop()
            for source, _sign, _derived, _conf in incoming.get(node, []):
                if source in reached:
                    continue
                if classification.roles.get(source) != 'info':
                    continue
                reached.add(source)
                pending.append(source)
        for rule_id in reached | totals:
            classification.roles[rule_id] = 'employer_cost'
        for rule_id in totals:
            # A grand total that already contains net pay must never be summed
            # into a pay run's KPI band: every dong in it is counted elsewhere.
            classification.details[rule_id] = True

    def _net_role_mark_details(self, classification, net_rule, outgoing):
        """A component folded into a same-role roll-up is a detail.

        `SIHIIUTOT105` is subtracted from net pay and so is `TOTALDEDUCTI`,
        because the second one is the first one plus two more. A run that sums
        both reports the same money twice.
        """
        for rule_id, role in classification.roles.items():
            if role in ('net',) or classification.details.get(rule_id):
                continue
            for target, sign, _derived, _conf in outgoing.get(rule_id, []):
                if target == net_rule.id or sign != 1:
                    continue
                if classification.roles.get(target) == role:
                    classification.details[rule_id] = True
                    break

    def _net_role_write_reasons(self, classification, net_rule, outgoing, best):
        net_name = net_rule.name or net_rule.code or _("net pay")
        rules_by_id = {r.id: r for r in classification.rules}
        for rule in classification.rules:
            if rule.id == net_rule.id:
                continue
            role = classification.roles.get(rule.id)
            via = ''
            hop = None
            cheapest = None
            for target, sign, derived, _conf in outgoing.get(rule.id, []):
                if target == net_rule.id:
                    hop = None
                    cheapest = (0, 0)
                    break
                cost = best.get(target)
                if cost is None:
                    continue
                if cheapest is None or cost < cheapest:
                    cheapest = cost
                    hop = rules_by_id.get(target)
            if hop is not None:
                via = hop.name or hop.code or ''
            detail = classification.details.get(rule.id)
            if role == 'earning':
                reason = (_("Added into %(net)s through %(via)s.",
                            net=net_name, via=via) if via
                          else _("Added straight into %(net)s.", net=net_name))
            elif role == 'deduction':
                reason = (_("Subtracted from %(net)s through %(via)s.",
                            net=net_name, via=via) if via
                          else _("Subtracted straight from %(net)s.", net=net_name))
            elif role == 'employer_cost':
                reason = _("Never reaches %(net)s — it is a cost the employer "
                           "carries on top of pay.", net=net_name)
            elif role == 'mixed':
                reason = _("Reaches %(net)s both as an addition and as a "
                           "subtraction, so a person has to decide what it is.",
                           net=net_name)
            else:
                reason = _("Never reaches %(net)s, so it is information rather "
                           "than pay.", net=net_name)
            if detail and via and role != 'info':
                reason = _("%(reason)s Already counted inside %(via)s, so a pay "
                           "run does not add it again.", reason=reason, via=via)
            elif detail and role == 'employer_cost':
                reason = _("%(reason)s It already contains %(net)s, so a pay run "
                           "does not add it again.", reason=reason, net=net_name)
            classification.reasons[rule.id] = reason

    # ------------------------------------------------------------------
    # Role -> category
    # ------------------------------------------------------------------
    _NET_ROLE_BASE_TOKENS = ('BASE', 'BASIC', 'BASISALA')

    def _net_role_is_base_pay(self, rule):
        code = (rule.code or '').upper()
        name = (rule.name or '').upper()
        if any(token in code for token in self._NET_ROLE_BASE_TOKENS):
            return True
        return 'LUONG CO BAN' in name or 'BASIC SALARY' in name or 'BASE SALARY' in name

    @staticmethod
    def _net_role_is_pure_sum(rule):
        """True when the formula only ADDS things up — the shape of a total."""
        if rule.column_type != 'formula' or not rule.excel_formula:
            return False
        ast, complete = parse_excel_expression(rule.excel_formula)
        if not complete:
            return False

        def pure(node):
            kind = node[0]
            if kind in ('ref', 'range', 'num'):
                return True
            if kind == 'add':
                return all(pure(sub) for _s, sub in node[1])
            if kind == 'neg':
                return pure(node[1])
            if kind == 'func' and node[1] in ('SUM', 'ROUND'):
                return pure(node[2][0]) if node[2] else False
            return False

        return pure(ast) and _contains_reference(ast)

    def _net_role_earning_aggregates(self, classification):
        """The non-detail earnings that are plainly a roll-up of other ones."""
        aggregates = set()
        for rule in classification.rules:
            if classification.roles.get(rule.id) != 'earning':
                continue
            if classification.details.get(rule.id):
                continue
            if self._net_role_is_pure_sum(rule):
                aggregates.add(rule.id)
        return aggregates

    def _net_role_category_code(self, rule, role, classification, aggregates):
        if role == 'net':
            return 'NET'
        if role == 'deduction':
            return 'DED'
        if role == 'employer_cost':
            return 'COMP'
        if role in ('info', 'mixed'):
            return 'OTH'
        # earning
        if self._net_role_is_base_pay(rule):
            return 'BASIC'
        if rule.id in aggregates:
            return 'GROSS'
        return 'ALW'

    def _net_role_category(self, code):
        Category = self.env['hr.salary.rule.category']
        category = Category.search([('code', '=', code)], limit=1)
        if category or code != 'OTH':
            return category
        return Category.create({'name': 'Other', 'code': 'OTH'})

    # ------------------------------------------------------------------
    # Used by both payslip-line producers
    # ------------------------------------------------------------------
    @api.model
    def net_role_line_flag(self, rule):
        return bool(rule.net_role_detail)
