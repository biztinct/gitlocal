# -*- coding: utf-8 -*-
"""WDGAP S9-B (P6) — the small-group hiding rules, tested on their own.

Test 70 is the strong one: for hundreds of random small tables it plays the
ATTACKER — it knows every shown cell, every total, that a hidden cell holds
at least one person, and it tries every possible filling of the hidden
cells. No hidden cell may come out with only one possible value.
"""

import itertools
import random

from odoo.tests import BaseCase, tagged

from ..models.suppress import Suppressor


def table(values):
    """A rows x cols table with row totals, column totals and a grand total."""
    S = Suppressor()
    rows, cols = len(values), len(values[0])
    for r in range(rows):
        for c in range(cols):
            S.cell((r, c), values[r][c])
        S.cell(('R', r), sum(values[r]))
        S.add_set(('R', r), [(r, c) for c in range(cols)])
    for c in range(cols):
        S.cell(('C', c), sum(values[r][c] for r in range(rows)))
        S.add_set(('C', c), [(r, c) for r in range(rows)])
    S.cell('T', sum(map(sum, values)))
    S.add_set('T', [('R', r) for r in range(rows)])
    S.add_set('T', [('C', c) for c in range(cols)])
    return S.solve()


def attack(S):
    """Every filling of the hidden cells that agrees with what is shown.
    Returns {cell: set of possible values}."""
    hidden = [k for k in S.values if S.is_hidden(k)]
    if not hidden:
        return {}
    # every hidden cell holds at least one person (zeros are shown)
    low = {k: (0 if S.values[k] == 0 else 1) for k in hidden}
    # the reader knows the grand total only when it is shown; otherwise give
    # the search a little room above the truth (still stricter than reality)
    cap = S.values['T'] + (0 if not S.is_hidden('T') else 5)
    possible = {k: set() for k in hidden}
    # a cell can never be more than any SHOWN total it is part of
    upper = {}
    for k in hidden:
        tops = [S.values[t] for t, parts in S.sets if k in parts and not S.is_hidden(t)]
        upper[k] = min(tops) if tops else cap

    def known(assign, k):
        if not S.is_hidden(k):
            return S.values[k]
        return assign.get(k)

    def propagate(assign):
        """Fill every set with one unknown left; False on a contradiction."""
        changed = True
        while changed:
            changed = False
            for t, parts in S.sets:
                cells = [t] + parts
                unknown = [c for c in cells if known(assign, c) is None]
                if len(unknown) != 1:
                    if not unknown:
                        if sum(known(assign, p) for p in parts) != known(assign, t):
                            return False
                    elif t not in unknown:
                        floor = sum(known(assign, p) if known(assign, p) is not None
                                    else low[p] for p in parts)
                        if floor > known(assign, t):
                            return False
                    continue
                u = unknown[0]
                psum = sum(known(assign, p) for p in parts if p != u)
                v = (psum if u == t else known(assign, t) - psum)
                if v < low[u] or v > upper[u]:
                    return False
                assign[u] = v
                changed = True
        return True

    def search(assign):
        assign = dict(assign)
        if not propagate(assign):
            return
        free = [k for k in hidden if k not in assign]
        if not free:
            for k in hidden:
                possible[k].add(assign[k])
            return
        k = sorted(free, key=str)[0]
        for v in range(low[k], upper[k] + 1):
            nxt = dict(assign)
            nxt[k] = v
            search(nxt)
    search({})
    return possible


@tagged('post_install', '-at_install', 'pb_people_reports')
class TestSuppress(BaseCase):

    def test_71_primary_hides_one_to_four_shows_zero(self):
        S = Suppressor()
        for i, v in enumerate([0, 1, 4, 5, 9]):
            S.cell(i, v)
        S.solve()
        self.assertEqual([S.is_hidden(i) for i in range(5)], [False, True, True, False, False])
        self.assertEqual(S.out(1), {'v': None, 'h': True})
        self.assertEqual(S.out(3), {'v': 5, 'h': False})

    def test_72_complementary_cell_is_hidden(self):
        # a department of 7: 6 women, 1 man. Showing 6 and 7 names the man.
        S = Suppressor()
        S.cell('T', 7)
        S.cell('w', 6)
        S.cell('m', 1)
        S.add_set('T', ['w', 'm'])
        S.solve()
        self.assertTrue(S.is_hidden('m'))
        self.assertTrue(S.is_hidden('w'))        # the complement
        self.assertFalse(S.is_hidden('T'))       # the total stays (it is public elsewhere)

    def test_73_two_hidden_that_add_to_under_five(self):
        # 1 + 2 hidden, total 20 shown: 20 - 17 = 3 would leak "both tiny"
        S = Suppressor()
        S.cell('T', 20)
        for k, v in (('a', 1), ('b', 2), ('c', 9), ('d', 8)):
            S.cell(k, v)
        S.add_set('T', ['a', 'b', 'c', 'd'])
        S.solve()
        hid = [k for k in 'abcd' if S.is_hidden(k)]
        self.assertGreaterEqual(sum(S.values[k] for k in hid), 5)
        self.assertGreaterEqual(len(hid), 3)

    def test_74_all_ones_are_not_left_alone(self):
        # five months with one joiner each: hidden sum 5 == count, all ones -> one more
        S = Suppressor()
        S.cell('T', 12)
        months = [1, 1, 1, 1, 1, 7]
        for i, v in enumerate(months):
            S.cell(i, v)
        S.add_set('T', list(range(6)))
        S.solve()
        self.assertTrue(S.is_hidden(5) or S.is_hidden('T'))

    def test_75_small_total_hides_everything_under_it(self):
        S = Suppressor()
        S.cell('T', 3)
        S.cell('a', 3)
        S.cell('b', 0)
        S.add_set('T', ['a', 'b'])
        S.solve()
        self.assertTrue(S.is_hidden('T'))
        self.assertTrue(S.is_hidden('a'))
        self.assertFalse(S.is_hidden('b'))       # zero names nobody

    def test_76_pair_hides_the_other_side_even_a_zero(self):
        # joiners 7, leavers 2, headcounts shown: 7 - change = 2 would leak
        S = Suppressor()
        S.cell('j', 7)
        S.cell('l', 2)
        S.add_pair('j', 'l')
        S.cell('j2', 3)
        S.cell('l2', 0)
        S.add_pair('j2', 'l2')
        S.solve()
        self.assertTrue(S.is_hidden('j'))
        self.assertTrue(S.is_hidden('l2'))

    def test_77_derived_follow_their_sources(self):
        S = Suppressor()
        S.cell('l', 3)
        S.cell('h', 50)
        S.add_derived('rate', ['l', 'h'])
        S.solve()
        self.assertTrue(S.is_hidden('rate'))
        self.assertEqual(S.out('rate', 6.0), {'v': None, 'h': True})

    def test_78_forced_cells_cascade(self):
        S = Suppressor()
        S.cell('T', 40)
        for k, v in (('a', 20), ('b', 20)):
            S.cell(k, v)
        S.add_set('T', ['a', 'b'])
        S.force('a')                 # hidden on another screen
        S.solve()
        self.assertTrue(S.is_hidden('b'))   # else 40 - 20 = a

    def test_70_nothing_hidden_can_be_worked_out(self):
        rnd = random.Random(20261116)
        checked = 0
        for _i in range(300):
            rows, cols = rnd.choice([(2, 2), (2, 3), (3, 2), (3, 3)])
            values = [[rnd.choice([0, 0, 1, 2, 3, 4, 5, 6, 8, 11]) for _c in range(cols)]
                      for _r in range(rows)]
            S = table(values)
            hidden = [k for k in S.values if S.is_hidden(k)]
            if not hidden or len(hidden) > 9:
                continue
            possible = attack(S)
            for k, vals in possible.items():
                if S.values[k] == 0 and len(vals) <= 1:
                    continue
                self.assertGreater(len(vals), 1, 'table %s: cell %s = %s can be worked out'
                                   % (values, k, S.values[k]))
            checked += 1
        self.assertGreater(checked, 50)
