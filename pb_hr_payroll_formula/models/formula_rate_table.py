# -*- coding: utf-8 -*-
"""F11 — Rate (bracket) tables.

A progressive rate table (e.g. a PIT tax schedule) is a list of brackets, each
a lower bound + a marginal rate. A formula references it with the pseudo-function
``BRACKET(table_code, value_expr)`` which is compiled — at conversion time, before
the Excel→Python step — into a nested ``IF()`` expression. The evaluator stays
table-ignorant: it only ever runs ordinary Python (D-F11.1).

Compilation implements the standard piecewise-linear progressive tax:

    for value v in band k  (lower_k <= v < lower_{k+1}):
        tax(v) = base_k + rate_k * (v - lower_k)

where ``base_k`` is the cumulative tax that fills every lower band. This is
exactly the "rate × income − quick-deduction" schedule used by e.g. Vietnam PIT,
so one BRACKET call replaces the hand-written 7-deep IF chain (and the duplicated
threshold constants the Problems-rail lint flags).
"""
import re

from odoo import _, api, fields, models


def _num(x):
    """Compact, round-trip-safe numeric literal (never scientific notation,
    which would break the Excel→Python converter's tokeniser)."""
    x = float(x or 0.0)
    if x == int(x):
        return str(int(x))
    return repr(round(x, 10))


def _split_first_comma(s):
    """Split ``s`` at its first TOP-LEVEL comma → (before, after). Respects
    nested parentheses so BRACKET(PIT, MIN(A,B)) keeps MIN(A,B) intact."""
    depth = 0
    for i, ch in enumerate(s):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            return s[:i], s[i + 1:]
    return s, ''


class HrFormulaRateTable(models.Model):
    _name = 'hr.formula.rate.table'
    _description = 'Formula Rate (Bracket) Table'
    _order = 'sequence, id'

    name = fields.Char(required=True, default=lambda s: _('Rate Table'))
    # Referenced in formulas as BRACKET(<code>, value). Plain identifier — the
    # same converter contract as component codes (no spaces/underscores).
    code = fields.Char(required=True, help="Used in formulas: BRACKET(code, value)")
    config_id = fields.Many2one('hr.formula.config', required=True,
                                ondelete='cascade', index=True)
    kind = fields.Selection([
        ('progressive', 'Progressive (marginal brackets)'),
    ], default='progressive', required=True)
    line_ids = fields.One2many('hr.formula.rate.bracket', 'table_id',
                               string='Brackets', copy=True)
    sequence = fields.Integer(default=10)
    note = fields.Char()

    # Odoo 19: legacy _sql_constraints is silently IGNORED (model_classes.py
    # logs "no longer supported") — constraints must be models.Constraint
    # class attributes or they never reach the database (ledger C9).
    _code_uniq = models.Constraint(
        'unique(config_id, code)',
        'A rate table code must be unique within a configuration.')

    @api.constrains('code')
    def _check_code(self):
        for t in self:
            if t.code and not re.match(r'^[A-Za-z][A-Za-z0-9]*$', t.code):
                raise models.ValidationError(_(
                    "Rate table code '%s' must be letters and digits only, "
                    "starting with a letter (no spaces or underscores).") % t.code)

    # ------------------------------------------------------------------
    # compilation
    # ------------------------------------------------------------------
    def compile_excel(self, value_expr):
        """Return an Excel string computing this table's progressive value for
        ``value_expr``. The result is plain Excel (IF/MAX/arithmetic) so the
        normal converter turns it into Python. Empty table → ``0``."""
        self.ensure_one()
        brackets = self.line_ids.sorted(key=lambda b: b.lower)
        if not brackets:
            return '0'
        lowers = [b.lower for b in brackets]
        rates = [b.rate for b in brackets]
        n = len(brackets)
        # cumulative base filling every lower band
        base = [0.0] * n
        for i in range(1, n):
            base[i] = base[i - 1] + rates[i - 1] * (lowers[i] - lowers[i - 1])
        v = '(' + (value_expr or '0').strip() + ')'

        def band(i):
            # base_i + rate_i * (v - lower_i)
            piece = '%s*(%s-%s)' % (_num(rates[i]), v, _num(lowers[i]))
            if base[i]:
                return '%s+%s' % (_num(base[i]), piece)
            return piece

        expr = band(0)
        for i in range(1, n):
            expr = 'IF(%s>=%s,%s,%s)' % (v, _num(lowers[i]), band(i), expr)
        # tax is never negative (guards value_expr < first lower bound)
        return 'MAX(0,%s)' % expr

    # ------------------------------------------------------------------
    # BRACKET(...) expansion — shared by the converter and the validator
    # ------------------------------------------------------------------
    @api.model
    def expand_brackets(self, formula, config):
        """Replace every ``BRACKET(code, value)`` in ``formula`` with the
        compiled Excel string for that table in ``config``. Unknown table →
        ``0`` (keeps evaluation safe; the Problems rail surfaces it separately).
        Balanced-paren aware so nested calls in the value expression survive."""
        if not formula or 'BRACKET' not in formula.upper():
            return formula
        tables = {(t.code or '').upper(): t for t in config.rate_table_ids if t.code}
        s = formula
        idx = 0
        guard = 0
        while guard < 200:
            guard += 1
            m = re.search(r'\bBRACKET\s*\(', s[idx:], re.IGNORECASE)
            if not m:
                break
            start = idx + m.start()
            open_paren = idx + m.end() - 1
            depth = 0
            end = -1
            for i in range(open_paren, len(s)):
                if s[i] == '(':
                    depth += 1
                elif s[i] == ')':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end == -1:
                break  # unbalanced — leave the rest untouched
            inner = s[open_paren + 1:end]
            code, val = _split_first_comma(inner)
            table = tables.get((code or '').strip().upper())
            repl = table.compile_excel(val) if table else '0'
            s = s[:start] + '(' + repl + ')' + s[end + 1:]
            idx = start + len(repl) + 2
        return s

    def _dependent_rules(self):
        """Formula rules in the same config that call BRACKET(<thisCode>)."""
        self.ensure_one()
        if not self.code:
            return self.env['hr.formula.rule']
        pat = re.compile(r'\bBRACKET\s*\(\s*%s\b' % re.escape(self.code), re.IGNORECASE)
        return self.config_id.rule_ids.filtered(
            lambda r: r.column_type == 'formula' and r.excel_formula
            and pat.search(r.excel_formula))

    def _refresh_dependent_rules(self):
        """Recompute the cached python_formula of rules using this table, so the
        card/grid reflect a bracket edit immediately (the evaluator already
        recompiles fresh at compute time)."""
        rules = self.env['hr.formula.rule']
        for t in self:
            rules |= t._dependent_rules()
        if rules and hasattr(rules, '_compute_python_formula'):
            rules._compute_python_formula()


class HrFormulaRateBracket(models.Model):
    _name = 'hr.formula.rate.bracket'
    _description = 'Formula Rate Table Bracket'
    _order = 'lower, id'

    table_id = fields.Many2one('hr.formula.rate.table', required=True,
                               ondelete='cascade', index=True)
    lower = fields.Float(string='From', digits=(16, 2), default=0.0,
                         help="Lower bound of this band (inclusive). The band "
                              "runs up to the next bracket's lower bound.")
    rate = fields.Float(string='Rate', digits=(16, 6), default=0.0,
                        help="Marginal rate as a fraction (0.05 = 5%).")

    def write(self, vals):
        res = super().write(vals)
        self.table_id._refresh_dependent_rules()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.table_id._refresh_dependent_rules()
        return recs

    def unlink(self):
        tables = self.table_id
        res = super().unlink()
        tables._refresh_dependent_rules()
        return res
