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

The hidden VALUES never leave the server: the payload carries `None` for a
hidden cell, in the screen, the totals and the export alike.
"""

FLOOR = 5


class Suppressor:

    def __init__(self, floor=FLOOR):
        self.floor = floor
        self.values = {}
        self.sets = []
        self.pairs = []
        self.derived = []
        self.hidden = set()
        self.forced = set()

    # ------------------------------------------------------------ building
    def cell(self, key, value):
        self.values[key] = int(value or 0)
        return key

    def add_set(self, total, parts):
        parts = [p for p in parts if p in self.values]
        if total in self.values and parts:
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
        floor = self.floor
        for key, v in self.values.items():
            if 0 < v < floor:
                self.hidden.add(key)
        self.hidden |= self.forced
        changed = True
        while changed:
            changed = False
            for total, parts in self.sets:
                nonzero = [p for p in parts if self.values[p] > 0]
                if total in self.hidden:
                    for p in nonzero:
                        changed |= self._hide(p)
                    continue
                hid = [p for p in nonzero if p in self.hidden]
                if not hid:
                    continue
                s = sum(self.values[p] for p in hid)
                if len(hid) >= 2 and s >= max(floor, len(hid) + 1):
                    continue
                shown = sorted((p for p in nonzero if p not in self.hidden),
                               key=lambda p: (self.values[p], str(p)))
                if shown:
                    changed |= self._hide(shown[0])
                else:
                    changed |= self._hide(total)
            for a, b in self.pairs:
                if (a in self.hidden) != (b in self.hidden):
                    changed |= self._hide(a)
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
