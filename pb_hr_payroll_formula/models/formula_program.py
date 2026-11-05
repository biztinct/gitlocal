"""PDR S2 — compiled, exact evaluation for the two READ-ONLY evaluators.

``formula_sample_data._evaluate_rules_with_dependencies(readonly=True)`` (the
pay data worksheet preview, Formula Studio) and the application-mode branch of
``hr_payslip_formula._evaluate_rules_with_dependencies`` used to call
``rule._run_formula(results, rule.excel_formula, write_diagnostics=False)``
for every formula on every pass. Each call rebuilt the column map over every
rule of the scheme, re-converted Excel to Python, re-coerced every value and
evaluated the source text: 8.77 s per person on a 409-rule scheme.

Here the same work is split in two:

* ``build_steps`` — once per evaluator call (once per request memo across the
  people of one call): topological order, column map, Excel -> Python
  conversion, the safety check and ``compile()``.
* ``run_sample`` / ``run_payslip`` — the evaluation loops, unchanged in
  order, passes, error handling and log lines, evaluating the compiled code
  objects against a coerced-values dict kept up to date as results change.

``_run_formula`` itself is untouched in behaviour and signature; the
non-readonly path (``evaluate()``, which writes diagnostics) does not come
here. Results must equal the old loop exactly — same keys, values, types,
``errors`` and pass count (PDR E1/E3, test T7).
"""
import logging
import math

from ..formula_engine import excel_semantics

_logger = logging.getLogger(__name__)

# The names ``_run_formula`` puts in its eval globals besides values/raw_values.
_HELPERS = (('sum', '_sumlist'), ('min', '_minlist'), ('max', '_maxlist'))


def _sorted_rules(rules):
    try:
        from ..formula_engine import FormulaEvaluator
        return FormulaEvaluator()._topological_sort(rules)
    except Exception:
        return rules.sorted(key=lambda r: r.sequence)


def _column_map(config):
    column_map = {}
    for rule in config.rule_ids:
        if rule.column_letter and rule.code:
            column_map[rule.column_letter] = rule.code
    return column_map


def _compile(rule, excel_formula, column_map):
    """('ok', code) or ('zero', None): what ``_run_formula`` would evaluate.

    Every failure here is a formula ``_run_formula`` answers with 0.0 after
    logging (no text, a conversion error, no Python code, a forbidden token
    or a syntax error). The log line is written once, not per evaluation.
    """
    if not excel_formula:
        _logger.warning("No Excel formula defined for %s, returning 0", rule.code)
        return ('zero', None)
    try:
        python_code = rule._convert_excel_to_python(excel_formula, column_map)
    except Exception as e:     # noqa: BLE001 — same breadth as _run_formula
        _logger.error("Error converting formula for %s: %s", rule.code, e)
        return ('zero', None)
    if not python_code:
        _logger.warning("No Python code generated for %s, returning 0", rule.code)
        return ('zero', None)
    try:
        excel_semantics.assert_safe_expression(python_code)
        return ('ok', compile(python_code, '<formula %s>' % rule.code, 'eval'))
    except Exception as e:     # noqa: BLE001
        _logger.error("Formula evaluation error for %s: %s (%s)", rule.code, e, python_code)
        return ('zero', None)


def build_steps(rules):
    """The evaluation program for ``rules`` (any order; sorted here).

    One tuple per rule, in evaluation order:
    ``(rule, code, column_type, column_letter, default, constant,
    excel_formula, compiled, globals_template)``.
    """
    maps, compiled = {}, {}
    steps = []
    for rule in _sorted_rules(rules):
        ctype = rule.column_type
        excel_formula = rule.excel_formula
        entry, template = None, None
        if ctype == 'formula':
            config = rule.config_id
            if config.id not in maps:
                maps[config.id] = _column_map(config)
            key = (config.id, excel_formula)
            if key not in compiled:
                compiled[key] = _compile(rule, excel_formula, maps[config.id])
            entry = compiled[key]
            template = {'self': rule, 'math': math, 'abs': abs, 'round': round,
                        'pow': pow, 'all': all, 'any': any, '__builtins__': {}}
            for name, method in _HELPERS:
                template[name] = getattr(rule, method)
        steps.append((rule, rule.code, ctype, rule.column_letter, rule.default_value,
                      rule.constant_value, excel_formula, entry, template))
    return steps


def _evaluate(step, results, coerced):
    """``rule._run_formula(results, excel_formula, write_diagnostics=False)``."""
    entry = step[7]
    if entry[0] != 'ok':
        return 0.0
    scope = dict(step[8])
    # Copies, as before: a formula can never change the live results. A
    # C-level dict copy is cheap; re-coercing every value was not.
    scope['values'] = coerced.copy()
    scope['raw_values'] = results.copy()
    try:
        result = eval(entry[1], scope)       # noqa: S307 — checked by assert_safe_expression
    except Exception as e:     # noqa: BLE001 — _run_formula answers 0.0 for any error
        _logger.error("Formula evaluation error for %s: %s", step[1], e)
        return 0.0
    if result is None:
        return 0.0
    if isinstance(result, str):
        return result
    try:
        return float(result)
    except (TypeError, ValueError):
        return result


def run_sample(steps, input_values, errors=None):
    """``formula_sample_data._evaluate_rules_with_dependencies(readonly=True)``."""
    coerce = excel_semantics.coerce_value
    results = input_values.copy()
    coerced = {k: coerce(v) for k, v in results.items()}
    for step in steps:
        code, ctype = step[1], step[2]
        if ctype == 'input':
            if code not in results:
                results[code] = step[4] or 0.0
                coerced[code] = coerce(results[code])
        elif ctype == 'constant':
            results[code] = step[5] or 0.0
            coerced[code] = coerce(results[code])
        elif ctype == 'formula':
            try:
                value = _evaluate(step, results, coerced)
                results[code] = value
            except Exception as e:     # noqa: BLE001
                _logger.warning("Formula evaluation error for %s: %s", code, e)
                results[code] = 0.0
                if errors is not None:
                    errors[code] = str(e)
            coerced[code] = coerce(results[code])
    # Second pass to resolve forward references not captured in dependency parsing.
    for _pass in range(2):
        changed = False
        for step in steps:
            code = step[1]
            if step[2] != 'formula':
                continue
            try:
                value = _evaluate(step, results, coerced)
            except Exception as e:     # noqa: BLE001
                _logger.warning("Formula re-evaluation error for %s: %s", code, e)
                value = 0.0
                if errors is not None:
                    errors[code] = str(e)
            else:
                if errors is not None:
                    errors.pop(code, None)
            if results.get(code) != value:
                results[code] = value
                coerced[code] = coerce(value)
                changed = True
        if not changed:
            break
    return results


def run_payslip(steps, input_values):
    """The application-mode (read-only) branch of
    ``hr_payslip_formula._evaluate_rules_with_dependencies``: results, log."""
    coerce = excel_semantics.coerce_value
    results = input_values.copy()
    coerced = {k: coerce(v) for k, v in results.items()}
    computation_log = []

    def put(key, value):
        results[key] = value
        coerced[key] = coerce(value)

    for step in steps:
        code, ctype, letter = step[1], step[2], step[3]
        try:
            if ctype == 'input':
                if code not in results:
                    put(code, step[4] or 0.0)
                value = results.get(code, 0.0)
                computation_log.append(f"[{letter}] {code} (input) = {value}")
            elif ctype == 'constant':
                value = step[5] or 0.0
                put(code, value)
                computation_log.append(f"[{letter}] {code} (constant) = {value}")
            elif ctype == 'formula':
                value = _evaluate(step, results, coerced)
                put(code, value)
                computation_log.append(f"[{letter}] {code} = {step[6]} -> {value}")
        except Exception as e:     # noqa: BLE001
            computation_log.append(f"[ERROR] Error in {code}: {str(e)}")
            put(code, 0.0)
        if letter:
            put(letter, results.get(code, 0.0))
    # Second pass to resolve forward references not captured in dependency parsing.
    for _pass in range(2):
        changed = False
        for step in steps:
            code, letter = step[1], step[3]
            if step[2] != 'formula':
                continue
            try:
                value = _evaluate(step, results, coerced)
            except Exception as e:     # noqa: BLE001
                computation_log.append(f"[ERROR] Error in {code}: {str(e)}")
                value = 0.0
            if results.get(code) != value:
                put(code, value)
                if letter:
                    put(letter, value)
                changed = True
        if not changed:
            break
    return results, computation_log
