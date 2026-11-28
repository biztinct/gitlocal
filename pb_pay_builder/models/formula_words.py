"""Read an expression for its explanation. All amounts come from the pay engine."""
import re

from odoo.tools import formatLang, format_amount
from odoo.addons.pb_hr_payroll_formula.formula_engine.parser import FormulaParser
from odoo.addons.pb_hr_payroll_formula.formula_engine.functions import FUNCTION_NAMES


def describe(rule, results, failed, currency, studio):
    env = rule.env
    _ = env._
    scheme = rule.config_id
    rules = scheme.rule_ids
    by_code = {r.code.upper(): r for r in rules if r.code}
    by_column = {r.column_letter.upper(): r for r in rules if r.column_letter}
    used = {}
    parts = []
    ladder = None

    def number(value):
        return formatLang(env, value, digits=0 if float(value).is_integer() else 2)

    def find_ref(key):
        # The shared parser appends row 1 to a bare name.
        key = key.upper()
        col = re.sub(r'\d+$', '', key)
        return by_code.get(key) or by_column.get(col) or by_code.get(key.removesuffix('1')) or by_code.get(col)

    def is_rate(r):
        # Older imported constants can retain the generic automatic money kind.
        # A percent-labelled multiplier still needs to show its fractional value as a rate.
        return (r.value_kind == 'rate' or
                (r.column_type == 'constant' and r.value_kind_source == 'auto'
                 and r.value_kind == 'money' and (r.name or '').strip().endswith('%')
                 and abs(results.get(r.code, 0)) <= 1))

    def ref_part(r):
        value = results.get(r.code, 0)
        text = (_("%s%%", number(value * 100)) if is_rate(r)
                    else format_amount(env, value, currency) if r.value_kind == 'money' else number(value))
        if r.column_type == 'constant':
            return {'t': 'fix', 'name': r._pbpb_name(), 'text': text}
        val = {'code': r.code, 'name': r._pbpb_name(), 'amount': value, 'text': text, 'period': r._pbpb_period_guess()}
        used[r.code] = val
        return dict(val, t='ref')

    def word(text):
        parts.append({'t': 'word', 'text': text})

    operators = {'*': '×', '/': '÷', '+': '+', '-': '−', '^': '^'}
    comparisons = {'=': _('is'), '<>': _('is not'), '<': _('is less than'), '>': _('is greater than'),
                   '>=': _('is at least'), '<=': _('is at most')}
    headings = {'MIN': _('the smaller of'), 'MAX': _('the larger of'), 'SUM': _('the total of'),
                'ABS': _('the absolute value of'), 'NOT': _('the opposite of'), 'AVERAGE': _('the average of')}
    rounding = {'ROUND': _('rounded'), 'ROUNDUP': _('rounded up'), 'CEILING': _('rounded up'),
                'ROUNDDOWN': _('rounded down'), 'INT': _('rounded down'), 'FLOOR': _('rounded down')}
    long_range = False

    def walk(node, parent=None):
        nonlocal ladder, long_range
        kind, value, children = node.type, node.value, node.children
        if kind == 'cell_ref':
            r = find_ref(value)
            if not r:
                raise ValueError('unknown reference')
            parts.append(ref_part(r))
        elif kind == 'range_ref':
            first, last = (find_ref(k) for k in value)
            if not first or not last:
                raise ValueError('unknown range')
            order = env['pb.formula.studio']._col_num
            lo, hi = sorted([order(first.column_letter), order(last.column_letter)])
            members = [ref_part(by_column[c]) for c in sorted(by_column, key=order) if lo <= order(c) <= hi]
            if len(members) > 8:
                long_range = True
                parts.append({'t': 'range', 'members': members,
                              'text': _('Show the %s lines', len(members))})
            else:
                parts.extend(members)
        elif kind == 'number':
            parts.append({'t': 'num', 'text': number(value)})
        elif kind == 'string':
            word(str(value))
        elif kind == 'boolean':
            word(_('Yes') if value else _('No'))
        elif kind in ('unary_op', 'binary_op'):
            bracket = parent in ('*', '/', '^', '-') and value in ('+', '-')
            if bracket:
                parts.append({'t': 'op', 'text': '('})
            if len(children) > 1:
                walk(children[0], value)
            if value in operators:
                parts.append({'t': 'op', 'text': operators[value]})
            else:
                word(comparisons[value])
            walk(children[-1], value)
            if bracket:
                parts.append({'t': 'op', 'text': ')'})
        elif kind == 'function':
            if value not in FUNCTION_NAMES:
                raise ValueError('unrecognized function')
            if value == 'BRACKET' and len(children) == 2 and children[0].type == 'cell_ref':
                table_key = children[0].value
                table = scheme.rate_table_ids.filtered(lambda t: t.code.upper() in (table_key, table_key.removesuffix('1')))[:1]
                word(_('in steps, using'))
                walk(children[1])
                if parent is None and table and children[1].type == 'cell_ref':
                    base = float(results.get(find_ref(children[1].value).code) or 0)
                    steps = table.line_ids.sorted('lower')
                    ladder = []
                    for i, step in enumerate(steps):
                        upper = steps[i + 1].lower if i + 1 < len(steps) else None
                        part = max(0, (min(base, upper) if upper is not None else base) - step.lower)
                        ladder.append({'from': step.lower, 'to': upper, 'rate': step.rate * 100,
                                       'part': part, 'amount': part * step.rate, 'hit': part > 0})
            elif value == 'IF' and len(children) == 3:
                for label, child in zip((_('if'), _('then'), _('otherwise')), children):
                    word(label)
                    walk(child, 'fn')
            elif value in rounding:
                walk(children[0], 'fn')
                word(rounding[value])
            else:
                if value not in ('AND', 'OR'):
                    word(headings.get(value, value.lower()))
                for i, child in enumerate(children):
                    if i:
                        word(_('or') if value == 'OR' else _('and'))
                    walk(child, 'fn')
        else:
            raise ValueError('unknown expression')

    fallback = False
    root = None
    try:
        text = rule.excel_formula or ''
        # Substitute named component references only outside quoted strings.
        chunks = re.split(r'("(?:[^"]|"")*")', text)
        for i in range(0, len(chunks), 2):
            chunks[i] = re.sub(r'\{([A-Za-z]\w*)\}', lambda m: by_code[m[1].upper()].column_letter + '5', chunks[i])
            chunks[i] = chunks[i].replace('$', '')
        parser = FormulaParser()
        root = parser.parse(''.join(chunks))
        if parser.position != len(parser.tokens):
            raise ValueError('partial expression')
        walk(root)
    except (ValueError, IndexError, KeyError, TypeError, RecursionError):
        fallback = True
        parts.clear()
        for key in (rule.formula_dependencies or '').split(','):
            source = find_ref(key.strip())
            if source and source != rule:
                ref_part(source)

    names = ', '.join(v['name'] for v in used.values())
    sentence = _('Worked out from %s.', names) if names else _('Set by the pay scheme.')
    def reference(node):
        return find_ref(node.value) if node.type == 'cell_ref' else None

    def percent(node):
        if node.type == 'number':
            return node.value
        rule = reference(node)
        if rule and rule.column_type == 'constant' and is_rate(rule):
            return results.get(rule.code)
        return None

    if root and not fallback:
        while root.type == 'function' and root.value in rounding and root.children:
            root = root.children[0]
        if root.type == 'function' and root.value == 'IF':
            sentence = _('Depends on %s.', names)
        elif root.type == 'function' and root.value == 'BRACKET':
            sentence = _('The rate rises in steps as %s grows.', names)
        elif root.type == 'function' and root.value == 'SUM':
            items = next((part['members'] for part in parts if part['t'] == 'range'), None)
            count = len(items) if len(root.children) == 1 and items else len(used)
            sentence = _('The total of %s lines.', count)
        elif root.type == 'binary_op':
            a, b = root.children
            spread = root.value == '/' and b.type == 'number' and b.value == 12
            expr = a if spread else root
            if spread and reference(a):
                sentence = _('%s spread over 12 months.', reference(a).name)
            if expr.type == 'binary_op' and expr.value == '*':
                base, multiplier = expr.children
                pct = percent(multiplier)
                if pct is None:
                    base, multiplier = multiplier, base
                    pct = percent(multiplier)
                source = reference(base)
                if source and pct is not None:
                    if spread:
                        sentence = _('%(rate)s%% of %(line)s, spread over 12 months.',
                                     rate=number(pct * 100), line=source._pbpb_name())
                    else:
                        sentence = _('%(rate)s%% of %(line)s.', rate=number(pct * 100), line=source._pbpb_name())
                elif pct is not None and base.type == 'function' and base.value == 'MIN' and len(base.children) == 2:
                    source, cap = (reference(child) for child in base.children)
                    if source and cap and cap.column_type == 'constant':
                        sentence = _('%(rate)s%% of %(line)s, counted up to %(cap)s.', rate=number(pct * 100),
                                     line=source._pbpb_name(), cap=format_amount(env, results.get(cap.code, 0), currency))
            elif root.value == '-':
                subtract = []
                remainder = root
                while remainder.type == 'binary_op' and remainder.value == '-' and reference(remainder.children[1]):
                    subtract.insert(0, reference(remainder.children[1]).name)
                    remainder = remainder.children[0]
                if subtract and reference(remainder):
                    sentence = _('%(line)s less %(others)s.', line=reference(remainder).name, others=', '.join(subtract))
            elif root.value == '+' and reference(a) and reference(b):
                sentence = _('%(first)s plus %(second)s.', first=reference(a).name, second=reference(b).name)

    reasons = {'zero': _('The formula for %s divides by zero.', rule.name),
               'unreadable': _('The sum for %s could not be read.', rule.name),
               'other': _('The sum for %s could not be worked out.', rule.name)}
    return {'code': rule.code, 'name': rule.name, 'sentence': sentence, 'parts': parts,
            'uses': list(used.values()), 'ladder': ladder, 'long': fallback or long_range or len(parts) > 14,
            'inline_ranges': long_range and not fallback and len(parts) <= 14,
            'result': None if failed else results.get(rule.code, 0),
            'failed': failed or False, 'failed_words': reasons.get(failed, ''),
            'studio': {'can_open': bool(studio), 'action': {'type': 'ir.actions.client',
                       'tag': 'pb_formula_studio', 'params': {'config_id': scheme.id, 'pbpb_show_component': rule.id}} if studio else False}}
