# -*- coding: utf-8 -*-
"""Small-group hiding (owner ruling P6): no figure under 5 people, and no
figure that can be worked out by subtraction.

PURE PYTHON, no ORM, so the rules can be tested exhaustively.

A report is a set of CELLS (id -> a count of people) plus three kinds of
relationship between them:

  * SETS  — `(total, [parts])`: the parts add up to the total (departments of
    a company, months of a period, age bands of a headcount). Totals are
    treated as public: the same total appears on other screens.
  * PAIRS — `(a, b)`: two cells whose DIFFERENCE is public (joiners and
    leavers of one month: their difference is the change in headcount, and
    both headcounts are on screen).
  * DERIVED — `(cell, [sources])`: a figure worked out from other cells (a
    turnover %, a share of the total). It is hidden whenever any source is.

THE RULES, applied until nothing changes (each pass only ever hides more, so
it always ends):

  1. Primary: a cell with 1-4 people is hidden. A zero is shown (it names
     nobody).
  2. A set whose total is hidden hides every non-zero part.
  3. A set with hidden parts must hide at least TWO non-zero parts, and they
     must add up to at least 5 and to more than their number (so they are not
     all ones). Otherwise the smallest shown non-zero part is hidden too; when
     there is none left, the total is hidden.
  4. A pair with one side hidden hides the other side, even a zero.
  5. Derived cells follow their sources.
  6. THE AUDIT (`solve`): the equations a reader can write down are solved
     exactly — first by elimination, then with what a reader knows about
     bounds (a hidden cell holds at least one person), then, when small, by
     trying every whole-number filling. Any hidden cell left with only one
     possible value gets a neighbour hidden too, and the rules run again.

The hidden VALUES never leave the server: the payload carries `None` for a
hidden cell, in the screen, the totals and the export alike.
"""

FLOOR = 5


class Suppressor:

    def __init__(self, floor=FLOOR):
        self.floor = floor
        self.values = {}
        self.sets = []
        self.loose = []
        self.pairs = []
        self.derived = []
        self.hidden = set()
        self.forced = set()
        #: public identities Σ coef·cell = 0, e.g. "this month's headcount =
        #: last month's + joiners − leavers". Used by the audit and widening.
        self.equations = []
        #: cells hidden last when widening (totals that other screens show)
        self.protect = set()
        #: cells already shown on ANOTHER screen (a tile): hiding them here
        #: would protect nothing, so the rules hide parts instead
        self.public = set()

    # ------------------------------------------------------------ building
    def add_equation(self, coefs):
        coefs = {k: c for k, c in coefs.items() if k in self.values and c}
        if len(coefs) >= 2:
            self.equations.append(coefs)
    def cell(self, key, value):
        self.values[key] = int(value or 0)
        return key

    def add_set(self, total, parts):
        parts = [p for p in parts if p in self.values]
        if total in self.values and parts:
            if sum(self.values[p] for p in parts) != self.values[total]:
                # Not additive (one person in two companies of a group is
                # counted once in the group): a reader cannot use it as an
                # exact equation, so it is kept as "the total hides its parts"
                # only — rule 2 — and left out of the audit.
                self.loose.append((total, parts))
                return
            self.sets.append((total, parts))

    def add_pair(self, a, b):
        if a in self.values and b in self.values:
            self.pairs.append((a, b))

    def add_derived(self, key, sources):
        self.derived.append((key, list(sources)))

    def force(self, key):
        """Hide a cell because it is hidden on another screen."""
        if key in self.values:
            self.forced.add(key)

    # ------------------------------------------------------------ solving
    def _hide(self, key):
        if key not in self.hidden:
            self.hidden.add(key)
            return True
        return False

    def solve(self):
        """The rules, then the AUDIT, until the audit finds nothing.

        The rules alone are not enough (the classic case: a row total under 5
        is hidden, but the grand total minus the other rows gives it back, and
        its only non-zero cell with it). The audit writes down every equation
        a reader could write — each set's total equals its parts, each pair's
        difference is known — and, by exact elimination, finds any hidden cell
        whose value those equations pin down. It then hides one more cell next
        to it and runs again. Each round hides at least one more cell, so it
        always ends.
        """
        self._rules()
        for _round in range(len(self.values) + 1):
            pinned = self._audit()
            if not pinned:
                break
            if not self._widen(pinned):
                break
            self._rules()
        return self

    def _widen(self, pinned):
        """Hide one more cell, as close to a pinned cell as possible.

        Walks outwards from the pinned cell through the sets and pairs it
        belongs to (and the sets their hidden cells belong to): the first
        set met that still shows something non-zero loses its smallest shown
        part, or its total when no part is left."""
        # Walk the sets reachable from the pinned cells (through hidden cells
        # and pairs), in order of distance. A PART anywhere on that walk is
        # hidden before any TOTAL: a total is on other screens and is worth
        # more than one more hidden month or department.
        seen, sets_in_order, eqs_in_order = set(), [], []
        queue = sorted(pinned, key=str)
        while queue:
            key = queue.pop(0)
            if key in seen:
                continue
            seen.add(key)
            for idx, (total, parts) in enumerate(self.sets):
                if key != total and key not in parts:
                    continue
                if idx not in sets_in_order:
                    sets_in_order.append(idx)
                queue.extend(c for c in [total] + parts if c in self.hidden and c not in seen)
            for a, b in self.pairs:
                if key in (a, b):
                    other = b if key == a else a
                    if other not in self.hidden and other not in self.public:
                        self.hidden.add(other)
                        return True
                    if other not in seen:
                        queue.append(other)
            for eq in self.equations:
                if key in eq:
                    if eq not in eqs_in_order:
                        eqs_in_order.append(eq)
                    queue.extend(c for c in eq if c in self.hidden and c not in seen)
        for idx in sets_in_order:
            total, parts = self.sets[idx]
            shown = sorted((p for p in parts if p not in self.hidden and self.values[p] > 0),
                           key=lambda p: (self.values[p], str(p)))
            if shown:
                self.hidden.add(shown[0])
                return True
        # then a cell of a public identity that is not a protected total
        # (one month's headcount rather than the year's leavers)
        for eq in eqs_in_order:
            shown = sorted((c for c in eq if c not in self.hidden and c not in self.protect
                            and self.values[c] > 0), key=lambda c: (self.values[c], str(c)))
            if shown:
                self.hidden.add(shown[0])
                return True
        for idx in sets_in_order:
            total, _parts = self.sets[idx]
            if total not in self.hidden and total not in self.public and self.values[total] > 0:
                self.hidden.add(total)
                return True
        for eq in eqs_in_order:
            shown = sorted((c for c in eq if c not in self.hidden and self.values[c] > 0),
                           key=lambda c: (self.values[c], str(c)))
            if shown:
                self.hidden.add(shown[0])
                return True
        return False

    def _audit(self):
        """Hidden cells the public equations determine exactly."""
        from fractions import Fraction
        hidden = sorted((k for k in self.hidden if k in self.values), key=str)
        if not hidden:
            return set()
        col = {k: i for i, k in enumerate(hidden)}
        rows = []
        for total, parts in self.sets:
            row = [Fraction(0)] * len(hidden)
            any_hidden = False
            for k, coef in [(total, 1)] + [(p, -1) for p in parts]:
                if k in col:
                    row[col[k]] += coef
                    any_hidden = True
            if any_hidden:
                rows.append(row)
        for a, b in self.pairs:
            row = [Fraction(0)] * len(hidden)
            if a in col:
                row[col[a]] += 1
            if b in col:
                row[col[b]] -= 1
            if any(row):
                rows.append(row)
        for eq in self.equations:
            row = [Fraction(0)] * len(hidden)
            for k, c in eq.items():
                if k in col:
                    row[col[k]] += c
            if any(row):
                rows.append(row)
        # reduced row echelon form
        pivots = []
        r = 0
        ncol = len(hidden)
        for c in range(ncol):
            pr = next((i for i in range(r, len(rows)) if rows[i][c] != 0), None)
            if pr is None:
                continue
            rows[r], rows[pr] = rows[pr], rows[r]
            pv = rows[r][c]
            rows[r] = [x / pv for x in rows[r]]
            for i in range(len(rows)):
                if i != r and rows[i][c] != 0:
                    f = rows[i][c]
                    rows[i] = [x - f * y for x, y in zip(rows[i], rows[r])]
            pivots.append((r, c))
            r += 1
            if r == len(rows):
                break
        pinned = set()
        for ri, c in pivots:
            if all(v == 0 for j, v in enumerate(rows[ri]) if j != c):
                key = hidden[c]
                if self.values[key] != 0:
                    pinned.add(key)
        if pinned:
            return pinned
        pinned, lo, hi = self._bounds_pinned(hidden, rows[:r])
        if pinned:
            return pinned
        return self._exact_pinned(hidden, rows[:r], pivots, lo, hi)

    def _exact_pinned(self, hidden, reduced, pivots, lo, hi, budget=4000):
        """Last check, for small cases: try every whole-number value of the
        free cells inside their known bounds, work the others out, and see
        whether some hidden cell can only ever take one value. Skipped when
        the search would be too large (the bounds check above still ran)."""
        import itertools
        import math
        pivot_cols = {c for _r, c in pivots}
        free = [i for i in range(len(hidden)) if i not in pivot_cols]
        ranges = []
        size = 1
        for i in free:
            if hi[i] is None:
                return set()
            a, b = math.ceil(lo[i]), math.floor(hi[i])
            if b < a:
                return set()
            ranges.append(range(a, b + 1))
            size *= (b - a + 1)
            if size > budget:
                return set()
        truth = [self.values[k] for k in hidden]
        consts = [sum(row[j] * truth[j] for j in range(len(hidden))) for row in reduced]
        seen = {i: set() for i in range(len(hidden))}
        for combo in itertools.product(*ranges):
            x = [None] * len(hidden)
            for i, v in zip(free, combo):
                x[i] = v
            ok = True
            for (ri, c) in pivots:
                row = reduced[ri]
                val = consts[ri] - sum(row[f] * x[f] for f in free)
                if val.denominator != 1 or val < lo[c] or (hi[c] is not None and val > hi[c]):
                    ok = False
                    break
                x[c] = int(val)
            if ok:
                for i, v in enumerate(x):
                    seen[i].add(v)
        return {hidden[i] for i, vals in seen.items()
                if len(vals) == 1 and self.values[hidden[i]] != 0}

    def _bounds_pinned(self, hidden, reduced):
        """Hidden cells pinned by the equations TOGETHER WITH what a reader
        knows about bounds: a hidden cell outside any pair holds at least one
        person (zeros are shown), none is negative. Interval propagation over
        the original equations and their reduced forms, to a fixed point."""
        from fractions import Fraction
        col = {k: i for i, k in enumerate(hidden)}
        in_pair = {k for ab in self.pairs for k in ab}
        lo = [Fraction(0 if k in in_pair else 1) for k in hidden]
        hi = [None] * len(hidden)          # None = no upper bound known
        eqs = []
        for total, parts in self.sets:
            coef, const = [Fraction(0)] * len(hidden), Fraction(0)
            for k, a in [(total, 1)] + [(p, -1) for p in parts]:
                if k in col:
                    coef[col[k]] += a
                else:
                    const -= a * self.values[k]
            if any(coef):
                eqs.append((coef, const))
        for a, b in self.pairs:
            coef, const = [Fraction(0)] * len(hidden), Fraction(0)
            for k, s in ((a, 1), (b, -1)):
                if k in col:
                    coef[col[k]] += s
                else:
                    const -= s * self.values[k]
            const += self.values[a] - self.values[b]
            if any(coef):
                eqs.append((coef, const))
        for eq in self.equations:
            coef, const = [Fraction(0)] * len(hidden), Fraction(0)
            for k, c in eq.items():
                if k in col:
                    coef[col[k]] += c
                else:
                    const -= c * self.values[k]
            if any(coef):
                eqs.append((coef, const))
        # the reduced rows are combinations of the same equations: recompute
        # their constants from the true values (they are what a reader derives)
        for row in reduced:
            if any(row):
                const = sum(row[i] * self.values[hidden[i]] for i in range(len(hidden)))
                eqs.append((list(row), const))
        for _it in range(50):
            changed = False
            for coef, const in eqs:
                idx = [i for i, a in enumerate(coef) if a != 0]
                for i in idx:
                    # a_i x_i = const - sum_{j != i} a_j x_j
                    mn, mx = const, const
                    bounded_mn = bounded_mx = True
                    for j in idx:
                        if j == i:
                            continue
                        a = coef[j]
                        # subtract a_j * x_j: its range is [a*lo, a*hi] (or flipped)
                        if a > 0:
                            mx -= a * lo[j]
                            if hi[j] is None:
                                bounded_mn = False
                            else:
                                mn -= a * hi[j]
                        else:
                            mn -= a * lo[j]
                            if hi[j] is None:
                                bounded_mx = False
                            else:
                                mx -= a * hi[j]
                    a = coef[i]
                    if a > 0:
                        new_lo = mn / a if bounded_mn else None
                        new_hi = mx / a if bounded_mx else None
                    else:
                        new_lo = mx / a if bounded_mx else None
                        new_hi = mn / a if bounded_mn else None
                    if new_lo is not None and new_lo > lo[i]:
                        lo[i] = new_lo
                        changed = True
                    if new_hi is not None and (hi[i] is None or new_hi < hi[i]):
                        hi[i] = new_hi
                        changed = True
            if not changed:
                break
        import math
        pinned = set()
        for i, k in enumerate(hidden):
            if hi[i] is not None and self.values[k] != 0 and \
                    math.floor(hi[i]) <= math.ceil(lo[i]):
                pinned.add(k)
        return pinned, lo, hi

    def _rules(self):
        floor = self.floor
        for key, v in self.values.items():
            if 0 < v < floor:
                self.hidden.add(key)
        self.hidden |= self.forced
        changed = True
        while changed:
            changed = False
            for total, parts in self.sets + self.loose:
                nonzero = [p for p in parts if self.values[p] > 0]
                if total in self.hidden:
                    for p in nonzero:
                        changed |= self._hide(p)
                    continue
                hid = [p for p in nonzero if p in self.hidden]
                if not hid:
                    continue
                # a reader cannot tell a hidden zero (hidden through a pair)
                # from a hidden small number, so hidden zeros count here; the
                # audit afterwards checks the result exactly.
                hid_all = [p for p in parts if p in self.hidden]
                s = sum(self.values[p] for p in hid)
                if len(hid_all) >= 2 and s >= floor and \
                        (len(hid_all) > len(hid) or s >= len(hid) + 1):
                    continue
                shown = sorted((p for p in nonzero if p not in self.hidden),
                               key=lambda p: (self.values[p], str(p)))
                if shown:
                    changed |= self._hide(shown[0])
                else:
                    if total not in self.public:
                        changed |= self._hide(total)
            for a, b in self.pairs:
                if (a in self.hidden) != (b in self.hidden):
                    if a not in self.public:
                        changed |= self._hide(a)
                    if b not in self.public:
                        changed |= self._hide(b)
        return self

    # ------------------------------------------------------------ reading
    def is_hidden(self, key):
        if key in self.hidden:
            return True
        for dkey, sources in self.derived:
            if dkey == key:
                return any(self.is_hidden(s) for s in sources)
        return False

    def out(self, key, value=None):
        """The payload of one cell: its value, or None when hidden."""
        hidden = self.is_hidden(key)
        if value is None:
            value = self.values.get(key, 0)
        return {'v': None if hidden else value, 'h': hidden}
