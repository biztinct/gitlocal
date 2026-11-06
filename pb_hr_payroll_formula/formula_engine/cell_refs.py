# -*- coding: utf-8 -*-
"""WP-L / S-L1 — the row machinery (pure, no ORM).

The Formula Studio grid stores exactly ONE canonical formula row: every
``excel_formula`` is written against row 2 (``=A2+AB2``) and references
components by COLUMN LETTER only (F13). Two features need to move those row
digits — and they must move them the SAME way or a formula silently corrupts:

* **W41 living-workbook export** shifts a stored formula OUT to the sheet row it
  lives on (row 2 → row 3 for the first sample, → row 4 for the second…), so the
  exported cell is a real, self-contained Excel formula.
* **W17 smart paste** normalizes a pasted formula IN from whatever row Excel
  copied it against (``B5*C5``) back to the canonical row 2 (``B2*C2``), so it
  can be stored on the single grid row.

Both are ``shift_rows(formula, to_row)`` — one regex, one string-literal mask,
two thin call sites (S-I1 / D-J1 lesson: never two regexes). String literals are
masked FIRST so a literal like ``IF(A2="X2",…)`` keeps its ``"X2"`` verbatim.
Function names never match: the pattern requires a digit run immediately after
the letter run, and ``MAX(`` / ``ROUND(`` carry no row digit.
"""
import re

# (col-$?)(1-3 letters)(row-$?)(digits) — matches D2, $D2, D$2, $D$2, AA11.
# Column letters cap at 3 (A..ZZZ = 18,278 columns, far beyond any real config)
# so a longer bare identifier can never be mistaken for a cell reference.
_CELL_RE = re.compile(r'(\$?)([A-Za-z]{1,3})(\$?)(\d+)')


def _mask_literals(formula):
    """Replace every quoted string literal with an opaque, letter/digit-free
    placeholder so the cell-ref regex can never touch literal content. Returns
    ``(masked, restore)`` where ``restore(s)`` re-inserts the literals."""
    lits = []

    def _stash(m):
        lits.append(m.group(0))
        return '\x00%d\x00' % (len(lits) - 1)

    masked = re.sub(r'"[^"]*"', _stash, formula)
    masked = re.sub(r"'[^']*'", _stash, masked)

    def restore(s):
        for i, lit in enumerate(lits):
            s = s.replace('\x00%d\x00' % i, lit)
        return s

    return masked, restore


def shift_rows(formula, to_row):
    """Rewrite EVERY cell-reference row digit in ``formula`` to ``to_row``.

    Column letters and their ``$`` absolutes are preserved; the row ``$``
    absolute is preserved but its digits are rewritten (``$B$5`` → ``$B$2`` when
    normalizing to row 2 — the grid has ONE formula row, so keeping ``$5`` would
    point at a nonexistent sample row after commit, S-L1 W17 gotcha). A leading
    ``=`` and all surrounding text survive verbatim. ``to_row`` must be >= 1."""
    if not formula:
        return formula
    to_row = int(to_row)
    masked, restore = _mask_literals(formula)

    def _repl(m):
        col_dollar, col, row_dollar, _digits = m.groups()
        return '%s%s%s%d' % (col_dollar, col, row_dollar, to_row)

    return restore(_CELL_RE.sub(_repl, masked))
