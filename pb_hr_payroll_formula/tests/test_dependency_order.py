"""Dependency ordering regressions, runnable without Odoo or a database.

    python3 pb_hr_payroll_formula/tests/test_dependency_order.py

Like the classifier tables, this standalone suite is not imported by Odoo's
test package. The field-read budget catches the repeated ORM scans that made
opening Rize's imported 367-column payroll scheme take several seconds.
"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from types import SimpleNamespace


def load_evaluator():
    engine = Path(__file__).resolve().parents[1] / 'formula_engine'
    package = types.ModuleType('_dependency_order_engine')
    package.__path__ = [str(engine)]
    sys.modules[package.__name__] = package
    name = package.__name__ + '.evaluator'
    spec = importlib.util.spec_from_file_location(name, engine / 'evaluator.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.FormulaEvaluator


FormulaEvaluator = load_evaluator()


def rule(code, letter, deps='', formula='', kind='formula'):
    return SimpleNamespace(code=code, column_letter=letter, column_type=kind,
                           formula_dependencies=deps, python_formula=formula,
                           default_value=0, constant_value=0)


class TestDependencyOrder(unittest.TestCase):
    def setUp(self):
        self.evaluator = FormulaEvaluator()

    def test_forward_references_by_letter_and_code(self):
        rules = [rule('NET', 'D', ' C, TAX, C, missing, '),
                 rule('TAX', 'B', 'A'), rule('GROSS', 'C', 'BASE'),
                 rule('BASE', 'A', kind='input')]
        ordered = self.evaluator._topological_sort(rules)
        positions = {r.code: i for i, r in enumerate(ordered)}
        self.assertEqual(len(ordered), 4)
        for before, after in [('BASE', 'TAX'), ('BASE', 'GROSS'),
                              ('TAX', 'NET'), ('GROSS', 'NET')]:
            self.assertLess(positions[before], positions[after])

    def test_column_letter_takes_precedence_over_a_code(self):
        rules = [rule('TOTAL', 'C', 'A', "values['BASE'] + 2"),
                 rule('A', 'B', kind='input'),
                 rule('BASE', 'A', kind='input')]
        self.assertEqual(self.evaluator.evaluate_all(rules, {'BASE': 10, 'A': 99})['TOTAL'], 12)

    def test_first_matching_column_wins(self):
        rules = [rule('TOTAL', 'B', 'A'), rule('FIRST', 'A', kind='input'),
                 rule('SECOND', 'A', 'B')]
        self.assertEqual([r.code for r in self.evaluator._topological_sort(rules)],
                         ['FIRST', 'TOTAL', 'SECOND'])

    def test_unknown_references_and_empty_graph_preserve_order(self):
        rules = [rule('FIRST', 'A', 'missing'), rule('SECOND', 'B', ' , ')]
        self.assertEqual(self.evaluator._topological_sort(rules), rules)
        self.assertEqual(self.evaluator._topological_sort([]), [])

    def test_cycles_keep_every_rule_in_the_existing_fallback_order(self):
        rules = [rule('LEFT', 'A', 'B'), rule('RIGHT', 'B', 'A'),
                 rule('FREE', 'C', kind='input'), rule('SELF', 'D', 'D')]
        with self.assertLogs(level='WARNING'):
            self.assertEqual([r.code for r in self.evaluator._topological_sort(rules)],
                             ['FREE', 'LEFT', 'RIGHT', 'SELF'])

    def test_evaluated_values_follow_the_dependency_order(self):
        rules = [rule('NET', 'D', 'B,C', "values['GROSS'] - values['TAX']"),
                 rule('TAX', 'C', 'GROSS', "values['GROSS'] * 0.1"),
                 rule('GROSS', 'B', 'A', "values['BASE'] * 2"),
                 rule('BASE', 'A', kind='input')]
        self.assertEqual(self.evaluator.evaluate_all(rules, {'BASE': 100}),
                         {'BASE': 100, 'GROSS': 200, 'TAX': 20, 'NET': 180})

    def test_large_scheme_does_not_rescan_fields_for_every_reference(self):
        class CountedRule:
            reads = 0

            def __init__(self, index):
                self.code = 'R%s' % index
                self.column_type = 'formula'
                self.formula_dependencies = ','.join(
                    ['COL%s' % (index - 1)] * 4 + ['unknown%s' % index]) if index else ''
                self.letter = 'COL%s' % index

            @property
            def column_letter(self):
                type(self).reads += 1
                return self.letter

        rules = [CountedRule(i) for i in range(400)]
        self.assertEqual(self.evaluator._topological_sort(list(reversed(rules))), rules)
        self.assertLess(CountedRule.reads, len(rules) * 10,
                        'Dependency ordering must not repeatedly scan ORM fields')


if __name__ == '__main__':
    unittest.main()
