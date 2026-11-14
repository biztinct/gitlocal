# -*- coding: utf-8 -*-
"""WDGAP PR-A — date functions in the pay formula engine, and one function list.

Numbered after the handover's §4:

  T1  every function gives Excel's answer (the shared battery file);
  T2  a date component inside YEAR/DATEDIF/DAYS reads the date, outside it is 0;
  T3  years of service for a 29-Feb joiner, on the period end, one day after;
  T4  TODAY()/NOW() refused with the plain sentence; FOO( refused naming FOO;
      a stored formula with TODAY() still loads and is not altered;
  T5  the function table is the single source of every list;
  T6  a NEW component code YEAR is refused; existing DAY / ENDDAY codes work;
  T7  R1 — the golden conversion of every repo formula is unchanged;
  T8  R3 — the same answer in all three evaluation places;
  R4  every emitted helper passes assert_safe_expression;
  JS  the Studio flowchart's JS mirror passes the same cases (node).
"""
import json
import os
import re
import shutil
import subprocess

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from ..formula_engine import excel_semantics, functions
from ..formula_engine.evaluator import FormulaEvaluator
from ..formula_engine.parser import FormulaParser
from ..formula_engine.validator import FormulaValidator
from ..models import component_code, formula_program

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.dirname(HERE)
REPO = os.path.dirname(MODULE)

with open(os.path.join(MODULE, 'tools', 'date_function_cases.json'), encoding='utf-8') as _fh:
    SPEC = json.load(_fh)

PERIOD_SENTENCE = ("A payslip must give the same answer whenever it is worked out. "
                   "Use the pay period instead, for example DATE(PAYYEAR, PAYMONTH, ENDDAY).")


@tagged('post_install', '-at_install', 'wdgap_pra')
class TestWdgapPraDates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rule = cls.env['hr.formula.rule']
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'WDGAP PR-A dates', 'code': 'WDGAPPRA',
            'country_code': 'VN', 'state': 'draft',
        })
        # The battery's columns: B is coded DAYS, I..M the date columns. DAY
        # and DAYS are function names now, so a NEW component may not take
        # them — these two stand for components made BEFORE PR-A, written the
        # way an old database holds them (straight into the table).
        letters = dict(SPEC['columns'])
        letters['B'] = 'DAYS'
        cls.inputs = {}
        for letter, code in sorted(letters.items()):
            safe = code if code not in functions.RESERVED_CODE_NAMES else code + 'OLD'
            rule = cls.Rule.create({
                'config_id': cls.config.id, 'name': code, 'code': safe,
                'column_type': 'input', 'forced_column_letter': letter,
                'value_kind': 'date' if code == 'JOIN' else 'integer',
            })
            if safe != code:
                cls.env.cr.execute("UPDATE hr_formula_rule SET code = %s WHERE id = %s",
                                   (code, rule.id))
                rule.invalidate_recordset(['code'])
            cls.inputs[code] = rule
        cls.cases = [c for c in SPEC['cases']]
        cls.case_rules = {}
        for i, case in enumerate(cls.cases):
            cls.case_rules[case['id']] = cls.Rule.create({
                'config_id': cls.config.id, 'name': case['id'],
                'code': 'PRACASE%d' % i, 'column_type': 'formula',
                'excel_formula': case['formula'],
            })
        cls.config.invalidate_recordset()

    # -- helpers --------------------------------------------------------------

    def _values(self, case):
        values = {SPEC['columns'][k]: v for k, v in SPEC['defaults'].items()}
        values['DAYS'] = 2
        for letter, v in (case.get('values') or {}).items():
            values[SPEC['columns'][letter]] = v
        return values

    def _column_map(self):
        return {r.column_letter: r.code for r in self.config.rule_ids
                if r.column_letter and r.code}

    def _three_paths(self, case, steps):
        rule = self.case_rules[case['id']]
        values = self._values(case)
        primary = rule._run_formula(dict(values), case['formula'], write_diagnostics=False)
        compiled = formula_program.run_sample(steps, dict(values))[rule.code]
        python = rule._convert_excel_to_python(case['formula'][1:], self._column_map())
        try:
            evaluator = FormulaEvaluator().evaluate_single(python, dict(values))
        except Exception:   # noqa: BLE001 — evaluate_all records 0 for these
            evaluator = 0.0
        return primary, compiled, evaluator

    # -- T1 / T2 / T3 / T8 ----------------------------------------------------

    def test_01_08_every_case_same_answer_in_all_three_places(self):
        """T1 + T8 (R3): each battery case gives Excel's answer through
        _run_formula, the compiled program and evaluate_single."""
        steps = formula_program.build_steps(self.config.rule_ids)
        for case in self.cases:
            with self.subTest(case=case['id'], formula=case['formula']):
                primary, compiled, evaluator = self._three_paths(case, steps)
                self.assertAlmostEqual(float(primary), case['expected'], places=9)
                self.assertAlmostEqual(float(compiled), case['expected'], places=9)
                self.assertAlmostEqual(float(evaluator), case['expected'], places=9)

    def test_02_date_component_inside_and_outside_date_functions(self):
        """T2: JOIN (a date component) is read as a date inside YEAR, DATEDIF
        and DAYS; on its own it is still 0, exactly as before."""
        rule = self.case_rules['ref-year-iso']
        values = {'JOIN': '2024-01-15', 'PAYYEAR': 2024, 'PAYMONTH': 2, 'ENDDAY': 29}
        for formula, expected in (
                ('=YEAR(JOIN)', 2024),
                ('=DATEDIF(JOIN,DATE(2025,1,15),"Y")', 1),
                ('=DAYS(DATE(2024,2,1),JOIN)', 17),
                ('=JOIN', 0),
                ('=JOIN*2', 0)):
            with self.subTest(formula=formula):
                self.assertEqual(rule._run_formula(dict(values), formula, write_diagnostics=False),
                                 expected)
        python = rule._convert_excel_to_python('JOIN+YEAR(JOIN)', self._column_map())
        self.assertTrue(python.startswith("values.get('JOIN', 0)+"), python)
        self.assertIn("self._dateval(values.get('JOIN', 0), raw_values.get('JOIN'))", python)

    def test_03_years_of_service(self):
        """T3: DATEDIF(JOIN, DATE(PAYYEAR,PAYMONTH,ENDDAY), "Y")."""
        rule = self.case_rules['code-service']
        formula = '=DATEDIF(JOIN,DATE(PAYYEAR,PAYMONTH,ENDDAY),"Y")'
        for join, period, expected in (
                ('2020-02-29', (2024, 2, 29), 4),    # 29 Feb joiner, leap year end
                ('2020-02-29', (2025, 2, 28), 4),    # 29 Feb joiner, not yet 5
                ('2023-02-28', (2024, 2, 28), 1),    # joined on the period-end date
                ('2023-03-01', (2024, 2, 29), 0)):   # joined one day after it
            values = {'JOIN': join, 'PAYYEAR': period[0], 'PAYMONTH': period[1],
                      'ENDDAY': period[2]}
            with self.subTest(join=join, period=period):
                self.assertEqual(rule._run_formula(values, formula, write_diagnostics=False),
                                 expected)

    # -- T4 --------------------------------------------------------------------

    def test_04_today_now_and_unknown_functions_are_refused_on_save(self):
        for name in ('TODAY', 'NOW'):
            msg = self.Rule._pb_formula_refusal('=IF(A1>0,%s(),0)' % name)
            self.assertIn('%s() can\'t be used in a formula.' % name, msg)
            self.assertIn(PERIOD_SENTENCE, msg)
        msg = self.Rule._pb_formula_refusal('=FOO(A1,2)')
        self.assertIn('FOO is not a function formulas can use', msg)
        self.assertIn('Did you mean FLOOR?', msg)
        self.assertIn('DATEDIF has the wrong number of values',
                      self.Rule._pb_formula_refusal('=DATEDIF(A1,B1)'))
        self.assertEqual(self.Rule._pb_formula_refusal(
            '=DATEDIF(JOIN,DATE(PAYYEAR,PAYMONTH,ENDDAY),"Y")+INT(2.5)'), '')
        # quoted text is not a call
        self.assertEqual(self.Rule._pb_formula_refusal('=IF(D1="TODAY()",1,0)'), '')
        # the engine's validators say the same, never "Invalid column reference"
        ok, message = FormulaValidator().validate_formula('=YEAR(A2)+FOO(A2)', {'A': 'BASIC'})
        self.assertFalse(ok)
        self.assertIn('FOO is not a function', message)
        self.assertNotIn('YEAR', message)
        rule = self.case_rules['ref-year-iso']
        rule.excel_formula = '=YEAR(I2)+ROUNDUP(J2,0)'
        valid, message = rule.validate_formula()
        self.assertTrue(valid, message)
        rule.excel_formula = '=TODAY()'
        valid, message = rule.validate_formula()
        self.assertFalse(valid)
        self.assertIn(PERIOD_SENTENCE, message)
        self.assertNotIn('Invalid column reference', message)

    def test_04b_a_stored_today_formula_still_loads_unchanged(self):
        """Stored formulas are not re-validated: one holding TODAY() is created,
        read, written around and converted exactly as before (it computes 0)."""
        rule = self.Rule.create({
            'config_id': self.config.id, 'name': 'Old today', 'code': 'OLDTODAY',
            'column_type': 'formula', 'excel_formula': '=TODAY()',
        })
        rule.write({'name': 'Old today (renamed)'})
        self.assertEqual(rule.excel_formula, '=TODAY()')
        self.assertEqual(rule._convert_excel_to_python('TODAY()', self._column_map()), 'TODAY()')
        self.assertEqual(rule._run_formula({}, rule.excel_formula, write_diagnostics=False), 0.0)

    # -- T5 --------------------------------------------------------------------

    def test_05_the_function_table_is_the_single_source(self):
        names = functions.FUNCTION_NAMES
        converter = {k[3:-2] for k in functions.converter_function_map()} \
            | functions.converter_special_names()
        self.assertEqual(converter, names)
        self.assertEqual(set(FormulaValidator.SUPPORTED_FUNCTIONS), names)
        self.assertEqual(set(FormulaParser.SUPPORTED_FUNCTIONS), names)
        listed = self.Rule.pb_formula_functions()
        self.assertEqual({f['name'] for f in listed}, names)
        self.assertEqual(len(listed), len(names))
        for f in listed:
            self.assertTrue(f['help'] and f['signature'] and f['example'], f)
            self.assertNotIn('odoo', (f['help'] + f['category_label']).lower())
        # nothing the old lists offered without computing is offered now
        for gone in ('TODAY', 'NOW', 'IFS', 'LEFT', 'RIGHT', 'MID', 'COUNT', 'CONCATENATE'):
            self.assertNotIn(gone, names)
        # every listed function is accepted by the rule validator, converted by
        # the converter, and never reported as a column reference
        cmap = self._column_map()
        rule = self.case_rules['ref-year-iso']
        for row in functions.rows():
            args = ', '.join(['1'] * row['min_args'])
            formula = '=%s(%s)' % (row['name'], args)
            if row['name'] == 'BRACKET':
                continue   # needs a band table; expanded before conversion
            with self.subTest(name=row['name']):
                self.assertEqual(self.Rule._pb_formula_refusal(formula), '')
                rule.excel_formula = formula
                _valid, message = rule.validate_formula()
                self.assertNotIn('Invalid column reference: %s' % row['name'], message or '')
                if row['kind'] == 'call':
                    python = rule._convert_excel_to_python(formula[1:], cmap)
                    self.assertNotIn('%s(' % row['name'], python)
                    self.assertIn(row['emit'], python)
                    # R4: the emitted helper passes the eval guard
                    excel_semantics.assert_safe_expression(python)
        excel_semantics.assert_safe_expression(
            rule._convert_excel_to_python('YEAR(JOIN)', cmap))

    # -- T6 --------------------------------------------------------------------

    def test_06_function_names_are_not_new_component_codes(self):
        with self.assertRaises(ValidationError) as caught:
            self.Rule.create({'config_id': self.config.id, 'name': 'Year',
                              'code': 'YEAR', 'column_type': 'input'})
        self.assertIn('YEAR is the name of a formula function', str(caught.exception))
        other = self.Rule.create({'config_id': self.config.id, 'name': 'Month no',
                                  'code': 'MONTHNO', 'column_type': 'input'})
        with self.assertRaises(ValidationError):
            other.write({'code': 'MONTH'})
        # the existing DAY component keeps its code through an ordinary write …
        day = self.inputs['DAY']
        day.write({'code': 'DAY', 'name': 'Day (kept)'})
        self.assertEqual(day.code, 'DAY')
        # (a copy of a scheme carrying it: test_06b)
        # generators never mint one
        for label in ('Year', 'Day', 'Days', 'Date', 'Int', 'Month'):
            code = component_code.build_component_code(label)
            self.assertNotIn(code, functions.RESERVED_CODE_NAMES, label)
        self.assertNotIn(component_code.normalize_code('DATE'), functions.RESERVED_CODE_NAMES)
        self.assertEqual(component_code.normalize_code('BASIC'), 'BASIC')
        # existing codes DAY / ENDDAY convert and evaluate as before
        rule = self.case_rules['code-day-endday']
        cmap = self._column_map()
        self.assertEqual(rule._convert_excel_to_python('ENDDAY+DAY', cmap),
                         "values.get('ENDDAY', 0)+values.get('DAY', 0)")
        values = {'ENDDAY': 29, 'DAY': 3, 'PAYYEAR': 2024, 'PAYMONTH': 2}
        self.assertEqual(rule._run_formula(values, '=ENDDAY+DAY', write_diagnostics=False), 32)
        self.assertEqual(rule._run_formula(
            values, '=DAY(DATE(PAYYEAR,PAYMONTH,ENDDAY))+DAY', write_diagnostics=False), 32)

    def test_06b_a_copied_scheme_keeps_an_existing_function_code(self):
        """A copy of a scheme whose component is coded DAY (made before PR-A)
        copies: the code already exists, so it is not a NEW name."""
        copy = self.config.copy({'code': 'WDGAPPRACOPY', 'name': 'copy'})
        self.assertIn('DAY', copy.rule_ids.mapped('code'))

    # -- T7 --------------------------------------------------------------------

    def test_07_golden_conversion_is_unchanged(self):
        """R1: every formula in the repo's data, demo catalogue, templates and
        tests converts byte-identically to the pre-PR-A code; the only formulas
        allowed to differ are the ones calling a function PR-A added (they
        could not compute before)."""
        path = os.path.join(HERE, 'data', 'wdgap_golden_conversion.json')
        with open(path, encoding='utf-8') as fh:
            golden = json.load(fh)
        probe = self.Rule.new({'name': 'golden', 'code': 'GOLDEN'})
        total = changed = expected = 0
        for src in golden:
            cmap = {letter: code for letter, code in src['column_map']}
            for formula, before in src['converted'].items():
                total += 1
                text = formula[1:] if formula.startswith('=') else formula
                try:
                    after = probe._convert_excel_to_python(text, cmap)
                except Exception as e:  # noqa: BLE001
                    after = '<ERROR %s: %s>' % (type(e).__name__, e)
                if after == before:
                    continue
                body = re.sub(r'"(?:[^"]|"")*"', '""', formula).upper()
                if any(re.search(r'(?<![A-Z0-9_])%s\s*\(' % n, body) for n in functions.NEW_IN_PRA):
                    expected += 1
                    continue
                changed += 1
                self.fail('%s: %r converted differently\n before %s\n after  %s'
                          % (src['source'], formula, before, after))
        self.assertGreater(total, 500)
        self.assertEqual(changed, 0)
        self.assertLessEqual(expected, 1)

    # -- JS mirror ----------------------------------------------------------------

    def test_09_js_mirror_passes_the_same_cases(self):
        node = shutil.which('node')
        script = os.path.join(REPO, 'pb_formula_studio', 'tools', 'date_functions_battery.mjs')
        if not node or not os.path.exists(script):
            self.skipTest('node or pb_formula_studio not available')
        proc = subprocess.run([node, script], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr[-2000:])
        self.assertIn('ALL GREEN', proc.stdout)
