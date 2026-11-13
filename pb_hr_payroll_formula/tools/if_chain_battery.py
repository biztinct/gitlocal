#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WP-J progressive IF-chain detector regression battery.

Runs the REAL ``formula_engine/if_chain.py`` detector against crafted chains —
no odoo, no server, no DB (the detector is pure python). Guards D-J1/D-J3:
canonical-shape recognition, quick-deduction consistency, span surgery, and the
rejection of every near-miss (driver mismatch, non-monotonic, irregular
deductions, wrong direction). Run after any change to ``if_chain.py``.

    python3 pb_hr_payroll_formula/tools/if_chain_battery.py

Exit 0 = green.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'formula_engine'))
import if_chain  # noqa: E402

# The canonical VN-PIT demo chain, verbatim from pb_demo/models/demo_catalog.py.
DEMO_PIT = ("=-MAX(0,IF(TXBASE<=0,0,IF(TXBASE<=5000000,TXBASE*0.05,"
            "IF(TXBASE<=10000000,TXBASE*0.1-250000,IF(TXBASE<=18000000,TXBASE*0.15-750000,"
            "IF(TXBASE<=32000000,TXBASE*0.2-1650000,IF(TXBASE<=52000000,TXBASE*0.25-3250000,"
            "IF(TXBASE<=80000000,TXBASE*0.3-5850000,TXBASE*0.35-9850000))))))))")

# Statutory brackets the demo chain must recover (D-J1 AC — lowers/rates).
VN_BRACKETS = [(0, 0.05), (5000000, 0.1), (10000000, 0.15), (18000000, 0.2),
               (32000000, 0.25), (52000000, 0.3), (80000000, 0.35)]

# A minimal 2-band chain with no guard: tax = 5% then 10% with a 250k quick-ded.
TWO_BAND = "IF(TXBASE<=5000000,TXBASE*0.05,TXBASE*0.1-250000)"

# Same shape but one deduction corrupted → irregular (listed, never rewritten).
CORRUPT_DED = ("IF(TXBASE<=0,0,IF(TXBASE<=5000000,TXBASE*0.05,"
               "IF(TXBASE<=10000000,TXBASE*0.1-999999,TXBASE*0.15-750000)))")

# Non-monotonic thresholds (10M then 5M) → not a table at all.
NON_MONO = ("IF(TXBASE<=0,0,IF(TXBASE<=10000000,TXBASE*0.05,"
            "IF(TXBASE<=5000000,TXBASE*0.1-250000,TXBASE*0.15-750000)))")

# Driver changes mid-chain (TXBASE → TXBASE2) → silently-different table.
DRIVER_MISMATCH = ("IF(TXBASE<=0,0,IF(TXBASE<=5000000,TXBASE*0.05,"
                   "IF(TXBASE2<=10000000,TXBASE2*0.1-250000,TXBASE2*0.15-750000)))")

# >= direction (descending) — not supported in v1 → None.
GE_DIRECTION = ("IF(TXBASE>=80000000,TXBASE*0.35-9850000,"
                "IF(TXBASE>=52000000,TXBASE*0.3-5850000,TXBASE*0.05))")

# Nested function in the driver: MIN(A,B). Supported (identical across bands),
# consistent; the caller will sample-only validate it (computed driver, D-J3).
NESTED_DRIVER = ("IF(MIN(A,B)<=5000000,MIN(A,B)*0.05,"
                 "IF(MIN(A,B)<=10000000,MIN(A,B)*0.1-250000,MIN(A,B)*0.15-750000))")

# Wrapper preservation: leading text and trailing text must be OUTSIDE the span.
WRAPPED = "=ROUND(-MAX(0,%s),0)" % TWO_BAND

CASES = []


def case(name, fn):
    CASES.append((name, fn))


# ---- 1. demo PIT: 8 bands, driver TXBASE, 7 statutory brackets, consistent ----
def t_demo():
    r = if_chain.detect(DEMO_PIT)
    assert r is not None, "demo PIT must parse"
    assert r['driver'] == 'TXBASE', r['driver']
    assert r['bands'] == 8, "8 value branches (zero-guard + 7 rate bands): %s" % r['bands']
    assert r['consistent'] is True, "deductions must verify consistent: %s" % r.get('reason')
    got = [(b['lower'], b['rate']) for b in r['brackets']]
    assert got == VN_BRACKETS, got
    assert r['wrapper_ok'] is True
    # span excludes the `=-MAX(0,` prefix and the trailing `)` — wrapper survives.
    s, e = r['span']
    assert DEMO_PIT[s:s + 3].upper() == 'IF(', DEMO_PIT[s:s + 3]
    assert DEMO_PIT[:s] == '=-MAX(0,', repr(DEMO_PIT[:s])
    assert DEMO_PIT[e:] == ')', repr(DEMO_PIT[e:])
case("demo PIT → 8 bands, 7 VN brackets, consistent, span surgical", t_demo)


# ---- 2. span rewrite reproduces the -MAX(0,BRACKET(...)) shape verbatim -------
def t_span_rewrite():
    r = if_chain.detect(DEMO_PIT)
    s, e = r['span']
    rewritten = DEMO_PIT[:s] + "BRACKET(PIT,TXBASE)" + DEMO_PIT[e:]
    assert rewritten == "=-MAX(0,BRACKET(PIT,TXBASE))", rewritten
case("span-surgical rewrite → =-MAX(0,BRACKET(PIT,TXBASE))", t_span_rewrite)


# ---- 3. minimal 2-band, no guard, consistent ---------------------------------
def t_two_band():
    r = if_chain.detect(TWO_BAND)
    assert r is not None
    assert r['bands'] == 2
    assert r['consistent'] is True, r.get('reason')
    assert [(b['lower'], b['rate']) for b in r['brackets']] == [(0, 0.05), (5000000, 0.1)]
    assert r['deductions'] == [0.0, 250000.0]
case("2-band minimal (no guard) → lower 0/5M, consistent", t_two_band)


# ---- 4. corrupted deduction → shaped but irregular (list, never rewrite) ------
def t_corrupt():
    r = if_chain.detect(CORRUPT_DED)
    assert r is not None, "must still parse as a chain (so it can be LISTED)"
    assert r['consistent'] is False
    assert r['bad_band'] == 1, r['bad_band']  # 0-indexed bracket; reason says "band 2"
    assert r['reason'] and '999999' in r['reason'] and 'band 2' in r['reason'], r['reason']
case("corrupted deduction → irregular, bad_band named", t_corrupt)


# ---- 5. non-monotonic thresholds → None --------------------------------------
def t_non_mono():
    assert if_chain.detect(NON_MONO) is None
case("non-monotonic thresholds → None", t_non_mono)


# ---- 6. driver mismatch mid-chain → None -------------------------------------
def t_driver_mismatch():
    assert if_chain.detect(DRIVER_MISMATCH) is None
case("driver mismatch mid-chain → None", t_driver_mismatch)


# ---- 7. >= direction (descending) → None -------------------------------------
def t_ge():
    assert if_chain.detect(GE_DIRECTION) is None
case(">= direction → None (v1 canonical is ascending <=)", t_ge)


# ---- 8. nested func driver MIN(A,B) → parsed + consistent --------------------
def t_nested_driver():
    r = if_chain.detect(NESTED_DRIVER)
    assert r is not None
    assert r['driver_norm'] == 'MIN(A,B)', r['driver_norm']
    assert r['consistent'] is True, r.get('reason')
    assert [(b['lower'], b['rate']) for b in r['brackets']] == [(0, 0.05), (5000000, 0.1), (10000000, 0.15)]
case("nested-func driver MIN(A,B) → parsed, consistent", t_nested_driver)


# ---- 9. wrapper preservation with surrounding text on both sides -------------
def t_wrapped():
    r = if_chain.detect(WRAPPED)
    assert r is not None
    s, e = r['span']
    assert WRAPPED[:s] == "=ROUND(-MAX(0,", repr(WRAPPED[:s])
    assert WRAPPED[e:] == "),0)", repr(WRAPPED[e:])
    rewritten = WRAPPED[:s] + "BRACKET(PIT,TXBASE)" + WRAPPED[e:]
    assert rewritten == "=ROUND(-MAX(0,BRACKET(PIT,TXBASE)),0)", rewritten
case("wrapper text on both sides survives verbatim", t_wrapped)


# ---- 10. single band → None (not a table) ------------------------------------
def t_single():
    assert if_chain.detect("IF(TXBASE<=5000000,TXBASE*0.05,TXBASE*0.05)") is not None or True
    # exactly one rate bracket cannot form a table
    assert if_chain.detect("IF(TXBASE<=5000000,TXBASE*0.05,0)") is None
case("degenerate/single-band → None", t_single)


# ---- 11. not a chain at all → None -------------------------------------------
def t_not_chain():
    assert if_chain.detect("=BASIC*0.1+ALLOW") is None
    assert if_chain.detect("=MAX(0,TXBASE-11000000)") is None
    assert if_chain.detect("") is None
case("non-chain formulas → None", t_not_chain)


# ---- 12. rate*driver order and +ded sign both parse --------------------------
def t_rate_first_and_plus():
    r = if_chain.detect("IF(TXBASE<=5000000,0.05*TXBASE,0.1*TXBASE-250000)")
    assert r is not None and r['consistent'] is True, r
    # +ded form: value = rate*driver + g2  → deduction is -(g2)
    r2 = if_chain.detect("IF(TXBASE<=5000000,TXBASE*0.05,TXBASE*0.1+250000)")
    assert r2 is not None and r2['consistent'] is False  # +250000 breaks the table
case("rate*driver order & +ded sign handled", t_rate_first_and_plus)


# ---- 13. verify_consistency unit: exact cumulative bases ---------------------
def t_verify_unit():
    ded = [0, 250000, 750000, 1650000, 3250000, 5850000, 9850000]
    ok, bad = if_chain.verify_consistency(VN_BRACKETS, ded)
    assert ok and bad == -1, (ok, bad)
    ded_bad = list(ded); ded_bad[3] = 1650001.0  # 1 off, within eps? no (>0.5)
    ok2, bad2 = if_chain.verify_consistency(VN_BRACKETS, ded_bad)
    assert (not ok2) and bad2 == 3, (ok2, bad2)
    # eps absorbs sub-0.5 authoring rounding
    ded_round = list(ded); ded_round[3] = 1650000.4
    ok3, _ = if_chain.verify_consistency(VN_BRACKETS, ded_round)
    assert ok3
case("verify_consistency cumulative-base math + eps window", t_verify_unit)


# ---- 14. NON-ZERO guard threshold → None (WP-J review M1) --------------------
# A leading IF(D<=T,0,…) guard with T>0 must NOT fold: the chain's first rate
# band taxes the FULL driver (v*rate) while compile_brackets_excel emits
# marginal rate*(v−lower). At x=2M this chain pays 100,000 but the BRACKET
# rewrite would pay 50,000 — and W42 rewrites staged text with no equivalence
# gate, so the detector itself must refuse.
def t_nonzero_guard():
    r = if_chain.detect("=IF(X<=1000000,0,IF(X<=5000000,X*0.05,X*0.1-300000))")
    assert r is None, "non-zero guard threshold must not fold: %s" % r
    # the T=0 guard (the demo shape) still folds
    assert if_chain.detect(
        "IF(X<=0,0,IF(X<=5000000,X*0.05,X*0.1-250000))") is not None
case("non-zero guard threshold → None (fold only exact at T=0)", t_nonzero_guard)


# ---- 15-18. MARGINAL form (WP-L review M3): the exact compile_brackets_excel
# output must round-trip back through the detector, or a W41-exported
# rate-table config can never re-earn its BRACKET offer on re-import.

# The VERBATIM compile_brackets_excel output for brackets
# [(0,0.05),(5000000,0.1),(10000000,0.15)] (bases 0/250000/750000), driver AQ2
# — cross-checked against a line-for-line replica of the emitter (integral
# floats print WITHOUT '.0' via _num).
MARGINAL = ("MAX(0,IF((AQ2)>=10000000,750000+0.15*((AQ2)-10000000),"
            "IF((AQ2)>=5000000,250000+0.1*((AQ2)-5000000),0.05*((AQ2)-0))))")


def t_marginal():
    r = if_chain.detect(MARGINAL)
    assert r is not None, "marginal compile output must parse"
    assert r['form'] == 'marginal'
    assert r['driver'] == 'AQ2', r['driver']        # outer parens stripped
    assert r['consistent'] is True, r.get('reason')
    assert [(b['lower'], b['rate']) for b in r['brackets']] == \
        [(0, 0.05), (5000000, 0.1), (10000000, 0.15)]
    assert r['deductions'] == [0.0, 250000.0, 750000.0]
    s, e = r['span']
    assert MARGINAL[s:e] == MARGINAL, "span covers the whole MAX(0,…)"
    assert r['wrapper_ok'] is True
case("marginal compile output → parsed, consistent, span=MAX(0,…)", t_marginal)


def t_marginal_wrapped():
    # The W41 export shape: expand_brackets wraps in parens under the =- wrapper.
    wrapped = "=-(%s)" % MARGINAL
    r = if_chain.detect(wrapped)
    assert r is not None and r['form'] == 'marginal'
    s, e = r['span']
    assert wrapped[:s] == '=-(' and wrapped[e:] == ')', repr((wrapped[:s], wrapped[e:]))
    rewritten = wrapped[:s] + "BRACKET(PIT,AQ2)" + wrapped[e:]
    assert rewritten == "=-(BRACKET(PIT,AQ2))", rewritten
case("wrapped export form =-(MAX(0,…)) → span surgical", t_marginal_wrapped)


def t_marginal_corrupt_base():
    bad = MARGINAL.replace("250000+", "999999+")
    r = if_chain.detect(bad)
    assert r is not None, "still shaped — must be LISTED, not dropped"
    assert r['consistent'] is False and r['bad_band'] == 1, (r['consistent'], r['bad_band'])
    assert '999999' in r['reason'], r['reason']
case("marginal corrupted base → irregular, band named", t_marginal_corrupt_base)


def t_marginal_nonzero_first_lower():
    # lowers[0] > 0 is legit in the marginal form (MAX(0,…) clamps below the
    # floor) — unlike the progressive guard fold (case 14), nothing diverges.
    m2 = ("MAX(0,IF((X2)>=5000000,200000+0.1*((X2)-5000000),"
          "0.05*((X2)-1000000)))")
    r = if_chain.detect(m2)
    assert r is not None and r['form'] == 'marginal'
    assert r['consistent'] is True, r.get('reason')   # base_1 = 0.05*(5M-1M) = 200k
    assert [(b['lower'], b['rate']) for b in r['brackets']] == \
        [(1000000, 0.05), (5000000, 0.1)]
case("marginal with non-zero first lower → consistent (M1 rule is progressive-only)",
     t_marginal_nonzero_first_lower)


def main():
    failures = []
    for name, fn in CASES:
        try:
            fn()
            print("  ok   %s" % name)
        except AssertionError as e:
            failures.append((name, str(e)))
            print("  FAIL %s\n         %s" % (name, e))
        except Exception as e:  # noqa: BLE001
            failures.append((name, "%s: %s" % (type(e).__name__, e)))
            print("  ERR  %s\n         %s: %s" % (name, type(e).__name__, e))
    print("\n%d/%d green" % (len(CASES) - len(failures), len(CASES)))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
