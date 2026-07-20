# -*- coding: utf-8 -*-
"""WP-J — Progressive IF-chain detector (pure, no ORM).

The single shared detector powering **W54** (studio simplification suggestions)
and **W42** (import-time rate-table extraction). D-J1: one module, zero logic
duplication.

It recognizes the *canonical* progressive-tax shape only — a nested ``IF()``
ladder over ONE driver expression, ascending ``<=`` thresholds, each band a
linear ``driver*rate [- deduction]`` (the top band living in the final ``ELSE``),
optionally preceded by a ``IF(driver<=t, 0, …)`` non-negative guard. This is the
exact shape the VN-PIT demo chain and every hand-written statutory table carry::

    =-MAX(0,IF(TXBASE<=0,0,IF(TXBASE<=5000000,TXBASE*0.05,
        IF(TXBASE<=10000000,TXBASE*0.1-250000, … TXBASE*0.35-9850000))))

From that chain it recovers the marginal ``(lower, rate)`` brackets a
``hr.formula.rate.table`` would carry and — critically — checks the literal
quick-deductions against the cumulative bases ``formula_rate_table.compile_excel``
emits (``verify_consistency``). A chain whose deductions don't match the implied
cumulative table is reported **irregular** (listed with a reason, NEVER rewritten
— C7). Nothing here evaluates a formula: equivalence proof is the caller's job,
through the real evaluator (D-J3, C12).

Pure python, unit-tested standalone via ``tools/if_chain_battery.py``.
"""
import re

# A bare numeric literal (no scientific notation — statutory tables never use it,
# and the Excel→Python converter's tokeniser can't either).
_NUM = r'-?\d+(?:\.\d+)?'
_IF_RE = re.compile(r'\bIF\s*\(', re.IGNORECASE)


def _norm(s):
    """Normalize an expression fragment for identity comparison: drop all
    whitespace, uppercase. Driver text is compared this way so ``TXBASE`` and
    ``txbase `` match but ``TXBASE`` vs ``TXBASE2`` (near-miss driver) do not."""
    return re.sub(r'\s+', '', (s or '')).upper()


def _as_number(s):
    """Parse a bare numeric literal → float, else None (parentheses, refs, ops
    all fail — deliberately strict so only the canonical shape is accepted)."""
    s = (s or '').strip()
    if re.fullmatch(_NUM, s):
        return float(s)
    return None


def _match_paren(s, open_idx):
    """Index of the ``)`` matching the ``(`` at ``open_idx`` (string-literal
    aware), or -1 if unbalanced."""
    depth = 0
    in_str = None
    i = open_idx
    while i < len(s):
        ch = s[i]
        if in_str:
            if ch == in_str:
                in_str = None
        elif ch in '"\'':
            in_str = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_top_commas(s):
    """Split ``s`` at top-level commas (paren- and string-literal aware)."""
    parts = []
    depth = 0
    in_str = None
    start = 0
    for i, ch in enumerate(s):
        if in_str:
            if ch == in_str:
                in_str = None
        elif ch in '"\'':
            in_str = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            parts.append(s[start:i])
            start = i + 1
    parts.append(s[start:])
    return parts


def _parse_cond(cond, driver_norm):
    """Parse a band condition. Accepts only ``<driver> <= <number>`` (``<`` also
    accepted — boundary is measure-zero on a continuous progressive table). A
    ``>=``/``>`` direction, a non-numeric threshold, or a driver that differs
    from ``driver_norm`` (when one is already fixed) all yield None.

    Returns ``(driver_text, driver_norm, threshold_float)`` or None."""
    m = re.match(r'^(.*?)(<=|<)\s*(%s)\s*$' % _NUM, cond.strip())
    if not m:
        return None
    lhs = m.group(1).strip()
    thr = _as_number(m.group(3))
    if not lhs or thr is None:
        return None
    lhs_norm = _norm(lhs)
    if driver_norm is not None and lhs_norm != driver_norm:
        return None  # driver mismatch mid-chain — silently-different table
    return lhs, lhs_norm, thr


def _parse_band(value, driver_norm):
    """Parse a band value expression.

    Returns ``('const', c, 0.0)`` for a bare number, or ``('rate', rate, ded)``
    for ``driver*rate``, ``rate*driver``, or either ``± ded`` (tax = rate*driver
    − ded). Anything else (parentheses, a second reference, a non-matching
    driver) → None."""
    v = _norm(value)
    num = _as_number(value)
    if num is not None:
        return ('const', num, 0.0)
    d = re.escape(driver_norm)
    # driver*rate  [± ded]
    m = re.fullmatch(r'%s\*(%s)((?:[-+]\d+(?:\.\d+)?))?' % (d, _NUM), v)
    if not m:
        # rate*driver  [± ded]
        m = re.fullmatch(r'(%s)\*%s((?:[-+]\d+(?:\.\d+)?))?' % (_NUM, d), v)
    if not m:
        return None
    rate = float(m.group(1))
    ded = -float(m.group(2)) if m.group(2) else 0.0  # value = rate*driver + g2
    return ('rate', rate, ded)


def parse_progressive_chain(expr):
    """D-J1: recognize the canonical nested-IF progressive chain.

    Returns ``None`` when ``expr`` is not a structurally-valid progressive chain
    (not nested IFs over ONE driver, non-linear band, non-monotonic thresholds,
    fewer than 2 rate bands, unsupported direction). When it IS a chain, returns::

        {driver, driver_norm, brackets: [{lower, rate}], deductions: [d…],
         span: (start, end), wrapper_ok: bool, bands: int}

    Consistency (deductions == cumulative bases) is a SEPARATE gate —
    ``verify_consistency`` — so an irregular-but-shaped chain is still returned
    here and gets *listed* by the caller, never silently dropped (C7)."""
    if not expr or 'IF' not in expr.upper():
        return None
    m = _IF_RE.search(expr)
    if not m:
        return None
    start = m.start()
    open_idx = m.end() - 1
    end = _match_paren(expr, open_idx)
    if end == -1:
        return None
    span = (start, end + 1)

    # Unwrap the nested IF ladder into ordered (threshold, band) regions.
    regions = []          # [(threshold_or_None, band_tuple)]
    driver_text = None
    driver_norm = None
    body = expr[open_idx + 1:end]
    guard = 200
    while guard > 0:
        guard -= 1
        args = _split_top_commas(body)
        if len(args) != 3:
            return None
        cond, then, els = args[0], args[1], args[2]
        pc = _parse_cond(cond, driver_norm)
        if not pc:
            return None
        dtext, dnorm, thr = pc
        if driver_norm is None:
            driver_text, driver_norm = dtext, dnorm
        band = _parse_band(then, driver_norm)
        if band is None:
            return None
        regions.append((thr, band))
        # Descend into the ELSE: another IF → recurse; anything else → final band.
        els_s = els.strip()
        nested = _IF_RE.match(els_s)
        if nested and _match_paren(els_s, nested.end() - 1) == len(els_s) - 1:
            body = els_s[nested.end():len(els_s) - 1]
            continue
        final_band = _parse_band(els, driver_norm)
        if final_band is None:
            return None
        regions.append((None, final_band))
        break
    else:
        return None

    # Thresholds strictly increasing (guard the ordering that makes it a table).
    thresholds = [t for t, _ in regions if t is not None]
    for a, b in zip(thresholds, thresholds[1:]):
        if not (b > a):
            return None

    # Fold regions → marginal brackets. A leading ``<=t → 0`` region is the
    # non-negative guard: it is NOT a bracket (BRACKET()'s own MAX(0,…) reproduces
    # it), but its threshold is the first real bracket's lower bound.
    brackets = []
    deductions = []
    prev_threshold = None
    wrapper_ok = False
    for i, (thr, band) in enumerate(regions):
        kind = band[0]
        if i == 0 and kind == 'const':
            if band[1] != 0.0:
                return None  # a non-zero constant floor is not a progressive table
            if thr != 0.0:
                # Only the T=0 guard folds into BRACKET's own MAX(0,…). With a
                # non-zero threshold the chain's first rate band taxes the FULL
                # driver (v*rate) while compile_brackets_excel emits marginal
                # rate*(v−lower) — they diverge for every v above the guard, and
                # W42 rewrites staged text with no equivalence gate to catch it.
                return None
            wrapper_ok = True         # zero guard → below-floor evaluates to 0
            prev_threshold = thr
            continue
        if kind != 'rate':
            return None               # a const in the middle/top is not canonical
        rate, ded = band[1], band[2]
        if not brackets:
            # First rate bracket. Its lower is the guard threshold if one led, else 0.
            lower = prev_threshold if prev_threshold is not None else 0.0
            if prev_threshold is None:
                if ded != 0.0:
                    return None       # floor unknown without a guard → not canonical
                wrapper_ok = True     # tax = rate*driver, 0 at/below 0
        else:
            lower = prev_threshold
        brackets.append((lower, rate))
        deductions.append(ded)
        prev_threshold = thr          # None for the final ELSE band (fine — last)

    if len(brackets) < 2:
        return None

    return {
        'driver': driver_text,
        'driver_norm': driver_norm,
        'brackets': [{'lower': lo, 'rate': r} for lo, r in brackets],
        'deductions': deductions,
        'span': span,
        'wrapper_ok': wrapper_ok,
        'bands': len(regions),
    }


def verify_consistency(brackets, deductions, eps=0.5):
    """S-J1 consistency gate. ``brackets`` = ``[(lower_i, rate_i)]`` ascending;
    ``deductions[i]`` = the literal quick-deduction in band i (0 for the first).
    A chain is a TRUE progressive table iff each ``d_i`` equals the exact
    cumulative base ``compile_excel()`` would emit:

        d_i == lower_i*rate_i − Σ_{k<i} rate_k*(lower_{k+1} − lower_k)

    Compared within ``eps`` — statutory tables are integers, so 0.5 absorbs
    authoring rounding only. Returns ``(True, -1)`` if consistent, else
    ``(False, i)`` naming the first irregular band (LIST it, never rewrite)."""
    if brackets and abs(deductions[0]) > eps:
        return False, 0
    base = 0.0
    for i in range(1, len(brackets)):
        lo_prev, r_prev = brackets[i - 1]
        lo_i, r_i = brackets[i]
        base += r_prev * (lo_i - lo_prev)
        expected_d = lo_i * r_i - base
        if abs(expected_d - deductions[i]) > eps:
            return False, i
    return True, -1


_MAX_RE = re.compile(r'\bMAX\s*\(', re.IGNORECASE)


def _strip_outer_parens(s):
    s = (s or '').strip()
    while s.startswith('(') and _match_paren(s, 0) == len(s) - 1:
        s = s[1:-1].strip()
    return s


def _parse_cond_ge(cond, driver_norm):
    """``<driver> >= <number>`` (or ``>``) — the descending direction
    ``compile_brackets_excel`` emits. Mirror of ``_parse_cond``."""
    m = re.match(r'^(.*?)(>=|>)\s*(%s)\s*$' % _NUM, cond.strip())
    if not m:
        return None
    lhs = m.group(1).strip()
    thr = _as_number(m.group(3))
    if not lhs or thr is None:
        return None
    lhs_norm = _norm(lhs)
    if driver_norm is not None and lhs_norm != driver_norm:
        return None
    return lhs, lhs_norm, thr


def _split_top_level_last(s, op):
    """Index of the LAST top-level occurrence of ``op`` in ``s`` (paren- and
    string-aware), or -1."""
    depth = 0
    in_str = None
    cut = -1
    for i, ch in enumerate(s):
        if in_str:
            if ch == in_str:
                in_str = None
        elif ch in '"\'':
            in_str = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == op and depth == 0 and i > 0:
            cut = i
    return cut


def _parse_marginal_band(value, driver_norm):
    """Parse ``[base+]rate*(<driver>-lower)`` — the exact band shape
    ``compile_brackets_excel`` emits. Returns ``(base, rate, lower, driver_text,
    driver_norm)`` or None."""
    s = (value or '').strip()
    base = 0.0
    # Optional leading 'base+' — the base seam is the FIRST top-level '+' whose
    # left side is a bare number (rate*… also starts with a number, but then
    # there is no top-level '+' before the '*').
    depth = 0
    in_str = None
    for i, ch in enumerate(s):
        if in_str:
            if ch == in_str:
                in_str = None
        elif ch in '"\'':
            in_str = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == '+' and depth == 0:
            lhs = s[:i]
            if _as_number(lhs) is not None:
                base = float(lhs)
                s = s[i + 1:].strip()
            break
    m = re.match(r'^(%s)\s*\*\s*\(' % _NUM, s)
    if not m:
        return None
    rate = float(m.group(1))
    open_idx = s.index('(', len(m.group(1)))
    close = _match_paren(s, open_idx)
    if close != len(s.rstrip()) - 1:
        return None
    inner = s[open_idx + 1:close]
    cut = _split_top_level_last(inner, '-')
    if cut < 0:
        return None
    dtext = inner[:cut].strip()
    lower = _as_number(inner[cut + 1:])
    if not dtext or lower is None:
        return None
    dnorm = _norm(dtext)
    if driver_norm is not None and dnorm != driver_norm:
        return None
    return base, rate, lower, dtext, dnorm


def parse_marginal_chain(expr, eps=0.5):
    """WP-L review M3: recognize the marginal-band form that
    ``compile_brackets_excel`` itself emits (a W41 export expands ``BRACKET``
    into exactly this, so without this parser a rate-table config could never
    round-trip back to a rate-table offer)::

        MAX(0, IF((v)>=l_n, base_n+r_n*((v)-l_n), … , r_0*((v)-l_0)))

    Descending ``>=`` ladder, innermost ELSE = band 0, explicit cumulative
    bases. Same return contract as ``parse_progressive_chain`` PLUS
    ``consistent``/``bad_band``/``reason`` (the consistency check here is that
    each parsed base equals the cumulative base the bracket table implies —
    checked directly; the progressive form's quick-deduction rule does not
    apply to marginal bands). ``deductions`` carries the equivalent
    quick-deductions for display. The span covers the whole ``MAX(0,…)`` —
    ``BRACKET()`` compiles to exactly that, so the rewrite replaces it 1:1."""
    if not expr or 'MAX' not in expr.upper():
        return None
    for m in _MAX_RE.finditer(expr):
        open_idx = m.end() - 1
        end = _match_paren(expr, open_idx)
        if end == -1:
            continue
        args = _split_top_commas(expr[open_idx + 1:end])
        if len(args) != 2 or _as_number(args[0]) != 0.0:
            continue

        # Walk the descending IF ladder.
        bands_desc = []          # [(lower, rate, base)] as encountered (top first)
        driver_text = driver_norm = None
        s = args[1].strip()
        ok = True
        guard = 200
        while guard > 0:
            guard -= 1
            mif = _IF_RE.match(s)
            if mif and _match_paren(s, mif.end() - 1) == len(s) - 1:
                ifargs = _split_top_commas(s[mif.end():len(s) - 1])
                if len(ifargs) != 3:
                    ok = False
                    break
                pc = _parse_cond_ge(ifargs[0], driver_norm)
                if not pc:
                    ok = False
                    break
                dtext, dnorm, thr = pc
                if driver_norm is None:
                    driver_text, driver_norm = dtext, dnorm
                band = _parse_marginal_band(ifargs[1], driver_norm)
                if band is None or abs(band[2] - thr) > 1e-9:
                    ok = False   # band's lower must equal its own >= threshold
                    break
                bands_desc.append((band[2], band[1], band[0]))
                s = ifargs[2].strip()
                continue
            band = _parse_marginal_band(s, driver_norm)
            if band is None:
                ok = False
                break
            if driver_norm is None:
                driver_text, driver_norm = band[3], band[4]
            bands_desc.append((band[2], band[1], band[0]))
            break
        else:
            ok = False
        if not ok or len(bands_desc) < 2:
            continue

        bands = list(reversed(bands_desc))     # ascending
        lowers = [b[0] for b in bands]
        if any(not (b > a) for a, b in zip(lowers, lowers[1:])):
            continue

        # Consistency: parsed bases must equal the cumulative bases the
        # (lowers, rates) table implies — irregular bases are LISTED (C7).
        consistent, bad, reason = True, -1, None
        expected = 0.0
        for i in range(1, len(bands)):
            expected += bands[i - 1][1] * (bands[i][0] - bands[i - 1][0])
            if abs(bands[i][2] - expected) > eps:
                consistent, bad = False, i
                reason = ("band %d base %s ≠ the cumulative-table value %s"
                          % (i + 1, _fmt(bands[i][2]), _fmt(expected)))
                break
        if consistent and abs(bands[0][2]) > eps:
            consistent, bad = False, 0
            reason = "band 1 must have no base (found %s)" % _fmt(bands[0][2])

        driver_clean = _strip_outer_parens(driver_text)
        return {
            'driver': driver_clean,
            'driver_norm': _norm(driver_clean),
            'brackets': [{'lower': lo, 'rate': r} for lo, r, _ in bands],
            'deductions': [lo * r - b for lo, r, b in bands],
            'span': (m.start(), end + 1),
            'wrapper_ok': True,      # BRACKET() compiles to this exact MAX(0,…)
            'bands': len(bands),
            'form': 'marginal',
            'consistent': consistent,
            'bad_band': bad,
            'reason': reason,
        }
    return None


def detect(expr, eps=0.5):
    """Shared entry point for W54 and W42. Tries ``parse_progressive_chain``
    (+ ``verify_consistency``), then ``parse_marginal_chain`` (which carries
    its own base-consistency verdict), or None if ``expr`` is neither form.
    The dict carries ``consistent`` (bool), ``bad_band`` (int, -1 if
    consistent), ``form`` ('progressive'|'marginal') and a human ``reason``
    for irregular chains — so callers list irregular chains identically, with
    zero re-derivation (D-J1)."""
    parsed = parse_progressive_chain(expr)
    if not parsed:
        return parse_marginal_chain(expr, eps=eps)
    parsed['form'] = 'progressive'
    brackets = [(b['lower'], b['rate']) for b in parsed['brackets']]
    ok, bad = verify_consistency(brackets, parsed['deductions'], eps=eps)
    parsed['consistent'] = ok
    parsed['bad_band'] = bad
    if ok:
        parsed['reason'] = None
    else:
        actual = parsed['deductions'][bad]
        if bad == 0:
            parsed['reason'] = (
                "band 1 must have no quick-deduction (found %s)" % _fmt(actual))
        else:
            lo_i, r_i = brackets[bad]
            base = 0.0
            for k in range(1, bad + 1):
                lo_p, r_p = brackets[k - 1]
                base += r_p * (brackets[k][0] - lo_p)
            expected = lo_i * r_i - base
            parsed['reason'] = (
                "band %d quick-deduction %s ≠ the cumulative-table value %s"
                % (bad + 1, _fmt(actual), _fmt(expected)))
    return parsed


def _fmt(x):
    x = float(x)
    return str(int(x)) if x == int(x) else repr(round(x, 4))
