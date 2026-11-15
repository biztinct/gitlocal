# -*- coding: utf-8 -*-
"""WDGAP W2-C — "work back from take-home": the search itself, with no ORM.

Given ``net_of(x)`` — the scheme's take-home when ONE pay item is ``x`` — and a
target take-home, find the lowest value of the item that reaches the target,
on the currency's own grid (whole dong, cents).

Why a separate, ORM-free module: the search is the part that must provably
terminate (R3) and must never invent arithmetic of its own (R2). Keeping it a
pure function of ``net_of`` lets the tests drive it with flat, stepped,
falling and garbage functions directly, and keeps the ORM layer
(``take_home.py``) responsible for exactly one thing — answering ``net_of``
the way the product answers it for a real payslip.

The method (handover §1.1):

1. bracket: start from [target, target x 1.6]; widen the top x2 up to 8 times
   until take-home there reaches the target. When take-home at the target is
   ALREADY above it, the answer lies below: the bottom drops to 0;
2. sample 12 evenly spaced points across the bracket (from where the search
   started to the top it reached). If take-home ever FALLS
   as the item rises, say so, and carry on inside the lowest stretch that
   crosses the target — the answer is then "the lowest value found", with a
   note, never a loop;
3. bisect on the currency grid until the two ends are one smallest unit apart
   (at most 60 halvings);
4. the answer is the upper end: the lowest value whose take-home reaches the
   target. "Exact" when its take-home, written in the currency, IS the target;
   otherwise "closest possible", with both neighbours.

Every evaluation is counted; 200 is the ceiling for one request.

Rounding is Excel's (half away from zero, ``excel_semantics.excel_round``),
never Python's ``round()`` on money (ledger C12).
"""
import math

from odoo.addons.pb_hr_payroll_formula.formula_engine import excel_semantics

MAX_EVALS = 200
MAX_BISECT = 60
GRID_POINTS = 12
WIDEN_TIMES = 8
START_FACTOR = 1.6

# Outcomes. The ORM layer turns each into one plain sentence.
EXACT = 'exact'
CLOSEST = 'closest'
NOT_POSSIBLE = 'not_possible'
GARBAGE = 'garbage'
LIMIT = 'limit'
BAD_TARGET = 'bad_target'

# Why something is not possible.
WHY_FLAT = 'flat'              # take-home does not move with this item
WHY_NEVER = 'never'            # it moves, but never as far as the target
WHY_ABOVE = 'already_above'    # even at 0 take-home is above the target


class _OutOfTries(Exception):
    """The evaluation budget is spent."""


class _NotANumber(Exception):
    """``net_of`` answered something that is not a finite number."""

    def __init__(self, value, item_value):
        super().__init__(repr(value))
        self.value = value
        self.item_value = item_value


class _Net:
    """``net_of`` on the currency grid: snapped, cached, counted, checked."""

    def __init__(self, net_of, decimals, max_evals):
        self.net_of = net_of
        self.decimals = decimals
        self.max_evals = max_evals
        self.evals = 0
        self.cache = {}

    def snap(self, value):
        return excel_semantics.excel_round(value, self.decimals)

    def __call__(self, x):
        x = self.snap(x)
        if x in self.cache:
            return self.cache[x]
        if self.evals >= self.max_evals:
            raise _OutOfTries()
        self.evals += 1
        raw = self.net_of(x)
        if isinstance(raw, bool):
            raise _NotANumber(raw, x)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise _NotANumber(raw, x) from None
        if not math.isfinite(value):
            raise _NotANumber(raw, x)
        self.cache[x] = value
        return value


def solve(net_of, target, decimals=0, max_evals=MAX_EVALS):
    """Find the lowest item value whose take-home reaches ``target``.

    Returns a dict, always with ``outcome`` and ``evals``:

    * ``exact``        — ``value``, ``net``;
    * ``closest``      — ``value``/``net`` (the lowest value ABOVE the target)
                         and ``below`` = ``{'value', 'net'}`` (the highest
                         value under it);
    * ``not_possible`` — ``why`` (flat / never / already_above), ``value`` and
                         ``net`` of the probe that proves it;
    * ``garbage``      — take-home was not a number at ``value``;
    * ``limit``        — the 200 tries ran out; ``value``/``net`` and
                         ``below`` are the best bracket so far (or absent);
    * ``bad_target``   — the target is not a positive amount.

    ``falls`` (``{'from': (x, n), 'to': (x, n)}``) is added whenever take-home
    was seen to drop while the item rose.
    """
    decimals = int(decimals or 0)
    unit = 10.0 ** (-decimals)
    half = unit / 2.0
    f = _Net(net_of, decimals, max_evals)
    try:
        t = f.snap(float(target))
    except (TypeError, ValueError):
        return {'outcome': BAD_TARGET, 'evals': 0}
    if not math.isfinite(t) or t <= 0:
        return {'outcome': BAD_TARGET, 'evals': 0}

    def reached(n):
        # Compared as the currency writes it: 11,999,999.6 dong IS 12,000,000.
        return f.snap(n) >= t - half / 2

    def equal(n):
        return abs(f.snap(n) - t) < half

    state = {'lo': None, 'hi': None, 'falls': None}

    def result(outcome, **extra):
        out = {'outcome': outcome, 'evals': f.evals}
        if state['falls']:
            out['falls'] = state['falls']
        out.update(extra)
        return out

    try:
        # ---------------------------------------------------------- 1. bracket
        lo = t
        n_lo = f(lo)
        # The grid in step 2 spans from where the search STARTED, not from
        # where widening left the bottom: a take-home that rises, falls and
        # rises again must be seen falling, or the answer would be a value
        # far above the lowest one that works.
        floor = (lo, n_lo)
        if reached(n_lo):
            hi, n_hi = lo, n_lo
            lo = 0.0
            n_lo = f(lo)
            floor = (lo, n_lo)
            if reached(n_lo):
                if equal(n_lo):
                    return result(EXACT, value=lo, net=n_lo)
                return result(NOT_POSSIBLE, why=WHY_ABOVE, value=lo, net=n_lo)
        else:
            hi = f.snap(t * START_FACTOR)
            n_hi = f(hi)
            widened = 0
            while not reached(n_hi) and widened < WIDEN_TIMES:
                lo, n_lo = hi, n_hi
                hi = f.snap(hi * 2)
                n_hi = f(hi)
                widened += 1
            if not reached(n_hi):
                # "Does not move" must be true below the target too: a capped
                # take-home is flat up here and moves further down.
                f(0.0)
                seen = list(f.cache.values())
                flat = (max(seen) - min(seen)) < half
                return result(NOT_POSSIBLE, why=WHY_FLAT if flat else WHY_NEVER,
                              value=hi, net=n_hi)
        state['lo'], state['hi'] = (lo, n_lo), (hi, n_hi)

        # ------------------------------------------- 2. the non-monotonic guard
        lo, n_lo = floor
        points = []
        for i in range(GRID_POINTS):
            x = f.snap(lo + (hi - lo) * i / (GRID_POINTS - 1))
            if not points or x > points[-1][0]:
                points.append((x, f(x)))
        for (xa, na), (xb, nb) in zip(points, points[1:]):
            if nb < na - half:
                state['falls'] = {'from': (xa, na), 'to': (xb, nb)}
                break
        for (xa, na), (xb, nb) in zip(points, points[1:]):
            if not reached(na) and reached(nb):
                lo, n_lo, hi, n_hi = xa, na, xb, nb
                break
        state['lo'], state['hi'] = (lo, n_lo), (hi, n_hi)

        # ------------------------------------------------------------ 3. bisect
        halvings = 0
        while hi - lo > unit + half / 2 and halvings < MAX_BISECT:
            mid = f.snap((lo + hi) / 2.0)
            if mid <= lo or mid >= hi:
                break
            n_mid = f(mid)
            if reached(n_mid):
                hi, n_hi = mid, n_mid
            else:
                lo, n_lo = mid, n_mid
            state['lo'], state['hi'] = (lo, n_lo), (hi, n_hi)
            halvings += 1
    except _OutOfTries:
        extra = {}
        if state['hi']:
            extra.update(value=state['hi'][0], net=state['hi'][1])
        if state['lo']:
            extra['below'] = {'value': state['lo'][0], 'net': state['lo'][1]}
        return result(LIMIT, **extra)
    except _NotANumber as bad:
        return result(GARBAGE, value=bad.item_value, net=None)

    # ---------------------------------------------------------------- 4. answer
    if equal(n_hi):
        return result(EXACT, value=hi, net=n_hi, halvings=halvings)
    return result(CLOSEST, value=hi, net=n_hi, halvings=halvings,
                  below={'value': lo, 'net': n_lo})
