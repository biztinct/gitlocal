#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WP-L / S-L1 row-machinery regression battery.

Runs the REAL ``formula_engine/cell_refs.shift_rows`` — pure python, no odoo,
no server. Guards the one function W41 (shift OUT at export) and W17 (normalize
IN at paste) both depend on: an off-by-one row shift silently corrupts EVERY
exported/pasted formula. Run after any change to ``cell_refs.py``.

    python3 pb_hr_payroll_formula/tools/cell_refs_battery.py

Exit 0 = green.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'formula_engine'))
import cell_refs  # noqa: E402

# (formula, to_row, expected)
CASES = [
    # --- W41: shift a canonical row-2 formula OUT to a data row --------------
    ('=A2+AB2', 3, '=A3+AB3'),
    ('=A2+AB2', 4, '=A4+AB4'),
    ('=A2+MAX(AB2,5000)*X2', 7, '=A7+MAX(AB7,5000)*X7'),
    # three-letter column (AAA) survives; 5000000 literal untouched
    ('=IF(A2>5000000,AAA2*0.1,B2)', 9, '=IF(A9>5000000,AAA9*0.1,B9)'),
    # --- W17: normalize a pasted formula (any row) back to row 2 -------------
    ('=B5*C5', 2, '=B2*C2'),
    ('=B5*C5-D5', 2, '=B2*C2-D2'),
    # $-row-absolute rewrites its digits too ($B$5 -> $B$2), $-col preserved
    ('=$B$5+C$5+$D5', 2, '=$B$2+C$2+$D2'),
    ('=$AA$11*2', 2, '=$AA$2*2'),
    # --- string literals are masked: "X2" keeps its digit -------------------
    ('=IF(A2="X2",B2,C2)', 5, '=IF(A5="X2",B5,C5)'),
    ("=IF(A2='row5',B2,0)", 3, "=IF(A3='row5',B3,0)"),
    # a literal that is ITSELF a cell-looking token stays frozen
    ('=CONCATENATE("A2",B2)', 4, '=CONCATENATE("A2",B4)'),
    # --- function names never match (no trailing digit after the letters) ---
    ('=ROUND(A2/B2,2)', 6, '=ROUND(A6/B6,2)'),
    ('=MIN(A2,B2)+MAX(C2,D2)', 8, '=MIN(A8,B8)+MAX(C8,D8)'),
    # --- expanded BRACKET (nested IF/MAX) round-trips cleanly ----------------
    ('=-MAX(0,IF((A2)>=5000000,0.1*((A2)-5000000),0.05*(A2)))', 3,
     '=-MAX(0,IF((A3)>=5000000,0.1*((A3)-5000000),0.05*(A3)))'),
    # --- idempotence: shifting to the same row is a no-op --------------------
    ('=A2+B2', 2, '=A2+B2'),
    # --- empty / falsy input -------------------------------------------------
    ('', 3, ''),
    (False, 3, False),
]


def main():
    fails = []
    for i, (formula, row, expected) in enumerate(CASES, 1):
        got = cell_refs.shift_rows(formula, row)
        status = 'ok ' if got == expected else 'FAIL'
        if got != expected:
            fails.append((i, formula, row, expected, got))
        print('  [%s] %2d  shift_rows(%r, %s) = %r' % (status, i, formula, row, got))

    # round-trip invariant: OUT to row N then IN to row 2 == normalize to row 2
    print('  --- round-trip (export row N -> normalize row 2) ---')
    for formula in ('=A2+AB2*X2', '=IF($B$2>0,C2,D2)', '=ROUND(MIN(A2,B2)*0.1,0)'):
        out5 = cell_refs.shift_rows(formula, 5)
        back = cell_refs.shift_rows(out5, 2)
        status = 'ok ' if back == formula else 'FAIL'
        if back != formula:
            fails.append(('rt', formula, 5, formula, back))
        print('  [%s]     %r --(5)--> %r --(2)--> %r' % (status, formula, out5, back))

    print()
    if fails:
        print('FAILED %d case(s):' % len(fails))
        for f in fails:
            print('   ', f)
        return 1
    print('ALL %d cases green.' % (len(CASES) + 3))
    return 0


if __name__ == '__main__':
    sys.exit(main())
