# -*- coding: utf-8 -*-
"""Test 6 — every operator x value type of the "Show only when" table, and the
renderer's own guarantees (no evaluation, unreadable rules keep wording)."""
import datetime

from odoo.tests import BaseCase, tagged

from odoo.addons.pb_doc_studio.models.doc_common import OPS
from odoo.addons.pb_doc_studio.models.doc_render import (
    UnknownRule, apply_rules, field_keys, line_holds, substitute,
)

META = {
    'country': {'type': 'choice'},
    'name': {'type': 'text'},
    'pay': {'type': 'number'},
    'start': {'type': 'date'},
    'flag': {'type': 'bool'},
}

#: (field, actual, op, value, expected)
CASES = [
    # choice (ids/keys compared as text)
    ('country', 12, 'is', '12', True),
    ('country', 12, 'is', '13', False),
    ('country', 12, 'is_not', '13', True),
    ('country', 12, 'is_not', '12', False),
    ('country', 12, 'in', ['3', '12'], True),
    ('country', 12, 'in', ['3', '4'], False),
    ('country', False, 'in', ['3'], False),
    ('country', False, 'empty', None, True),
    ('country', 12, 'empty', None, False),
    ('country', 12, 'filled', None, True),
    ('country', False, 'filled', None, False),
    # text (trimmed, case-insensitive)
    ('name', ' Jakarta ', 'is', 'jakarta', True),
    ('name', 'Jakarta', 'is', 'Hanoi', False),
    ('name', 'Jakarta', 'is_not', 'Hanoi', True),
    ('name', 'Jakarta', 'is_not', 'JAKARTA', False),
    ('name', 'Jakarta', 'in', ['Hanoi', 'jakarta'], True),
    ('name', 'Jakarta', 'in', ['Hanoi'], False),
    ('name', '', 'empty', None, True),
    ('name', 'x', 'empty', None, False),
    ('name', 'x', 'filled', None, True),
    ('name', False, 'filled', None, False),
    # number
    ('pay', 1000, 'is', 1000, True),
    ('pay', 1000, 'is', '1000.0', True),
    ('pay', 1000, 'is_not', 999, True),
    ('pay', 1000, 'gt', 999, True),
    ('pay', 1000, 'gt', 1000, False),
    ('pay', 1000, 'lt', 1001, True),
    ('pay', 1000, 'lt', 10, False),
    ('pay', None, 'gt', 1, False),
    ('pay', None, 'is_not', 1, True),
    ('pay', 0, 'empty', None, False),
    ('pay', None, 'empty', None, True),
    ('pay', 5, 'filled', None, True),
    # date
    ('start', datetime.date(2026, 1, 15), 'is', '2026-01-15', True),
    ('start', '2026-01-15', 'is_not', '2026-01-16', True),
    ('start', datetime.date(2026, 1, 15), 'gt', '2025-12-31', True),
    ('start', datetime.date(2026, 1, 15), 'gt', '2026-02-01', False),
    ('start', datetime.datetime(2026, 1, 15, 8, 0), 'lt', '2026-02-01', True),
    ('start', datetime.date(2026, 1, 15), 'lt', '2026-01-01', False),
    ('start', False, 'empty', None, True),
    ('start', datetime.date(2026, 1, 15), 'filled', None, True),
    # yes / no
    ('flag', True, 'is', True, True),
    ('flag', False, 'is', True, False),
    ('flag', False, 'is', False, True),
]


@tagged('post_install', '-at_install', 'pb_doc_studio')
class TestRuleTable(BaseCase):

    def test_06_every_operator_and_type(self):
        seen = set()
        for field, actual, op, value, expected in CASES:
            with self.subTest(field=field, op=op, value=value):
                got = line_holds({'field': field, 'op': op, 'value': value},
                                 {field: actual}, META)
                self.assertIs(got, expected)
                seen.add((META[field]['type'], op))
        for kind, ops in OPS.items():
            for op in ops:
                self.assertIn((kind, op), seen, 'no case for %s / %s' % (kind, op))

    def test_06_refused_lines(self):
        with self.assertRaises(UnknownRule):
            line_holds({'field': 'nope', 'op': 'is', 'value': 1}, {}, META)
        with self.assertRaises(UnknownRule):
            line_holds({'field': 'flag', 'op': 'gt', 'value': 1}, {}, META)
        with self.assertRaises(UnknownRule):
            line_holds({'field': 'pay', 'op': 'gt', 'value': '__import__("os")'}, {'pay': 1}, META)

    def test_06_unreadable_rule_keeps_the_paragraph(self):
        body = '<p>a</p><div class="pbds-when pbds-r-r9"><p>kept</p></div><p>b</p>'
        html, hidden, bad = apply_rules(body, {}, {}, META)
        self.assertIn('kept', html)
        self.assertNotIn('pbds-when', html)
        self.assertEqual((hidden, bad), (0, 1))

    def test_06_hidden_block_keeps_following_text(self):
        body = '<div class="pbds-when pbds-r-r1"><p>gone</p></div>tail <p>after</p>'
        rules = {'r1': {'match': 'all', 'lines': [{'field': 'flag', 'op': 'is', 'value': True}]}}
        html, hidden, _bad = apply_rules(body, rules, {'flag': False}, META)
        self.assertNotIn('gone', html)
        self.assertIn('tail', html)
        self.assertIn('after', html)
        self.assertEqual(hidden, 1)
        ghost, n, _b = apply_rules(body, rules, {'flag': False}, META, ghost=True)
        self.assertIn('pbds-ghost', ghost)
        self.assertEqual(n, 1)

    def test_06_any_and_all(self):
        rule_all = {'match': 'all', 'lines': [
            {'field': 'flag', 'op': 'is', 'value': True},
            {'field': 'pay', 'op': 'gt', 'value': 10}]}
        rule_any = dict(rule_all, match='any')
        body = '<div class="pbds-when pbds-r-r1"><p>x</p></div>'
        facts = {'flag': True, 'pay': 5}
        self.assertNotIn('x', apply_rules(body, {'r1': rule_all}, facts, META)[0])
        self.assertIn('x', apply_rules(body, {'r1': rule_any}, facts, META)[0])

    def test_substitute_grammar(self):
        values = {'a': 'A&amp;B', 'empty': ''}
        out = substitute('${a} ${empty} ${gone} $$5 $bare $a', values)
        self.assertEqual(out, 'A&amp;B   $5 $bare A&amp;B')
        out = substitute('${gone}', values, missing=lambda k: '[%s]' % k)
        self.assertEqual(out, '[gone]')
        self.assertEqual(field_keys('${a} ${b} ${a} $c'), ['a', 'b'])
