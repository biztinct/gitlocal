# -*- coding: utf-8 -*-
"""Component codes a human can read — one generator for every import path.

A salary structure's columns arrive as spreadsheet headers, and the code stamped on
each one is the identifier the formula engine, the payslip line, the contract
component and every mapping downstream will use forever. Until now four separate
generators produced it, and the oldest of them ran
``re.sub(r'[^A-Za-z0-9]', '', label)`` — an **ASCII-only** filter, so every accented
Vietnamese letter was DELETED rather than folded::

    "Chi trả phép năm chưa sử dụng"  ->  CHITRPHPNMCHASDNG   (lossy AND 17 chars)

This module replaces all four. It is DELIBERATELY plain Python — no ``odoo`` import,
stdlib only (plus the equally-plain ``column_role_classifier``) — so the wizards, the
Excel connector, the studio, the upgrade migration and the bare-``python3`` test
batteries all share one answer.

THE CONVERTER CONTRACT (docs/FORMULA_ENGINE_CONVENTIONS.md C5/C13, verified):

* **HARD — underscore-free.** The Excel->Python converter's code pass matches
  ``[A-Z][A-Z0-9]{1,}``, which excludes ``_``; a code like ``SI_EMP`` therefore
  survives raw into the eval, raises ``NameError`` and silently reads 0.
* **NOT a correctness issue — substring collisions.** The code pass is greedy
  (maximal munch) with a ``(?<!')`` lookbehind, so ``SI``/``SIEMP`` both resolve.
  Non-substring is a cosmetic preference, applied only when a short letter suffix
  achieves it.
* **>= MIN_LEN (6) normalized characters** keeps a code inside the fuzzy
  header-match fallback (``payroll_import_batch.py`` :2478/:2509).
* **>= 3 characters** keeps it visible to ``_compute_dependencies``' ``code_refs``.
* **Never equal to a column letter in its own config** — ``rename_component`` skips
  the formula rewrite in that case and the converter's letter pass hijacks the token.

Everything here is deterministic: the same label list in the same order always
produces the same code list.
"""

import re
import string

from .column_role_classifier import strip_accents

MAX_LEN = 12
MIN_LEN = 6

#: Words that carry little meaning inside a component name. "Total" in the middle of
#: "SI-HI-IU Total 10.5%" is already paid for out of the ordinary budget; this set
#: exists so the ranking below can tell filler from substance.
NOISE_WORDS = {
    'constant', 'const', 'total', 'amount', 'value', 'column', 'col',
    'cho', 'cua', 'va', 'theo', 'cac', 'nhan',
}

#: The subset actually stripped from the FRONT of a label, and only while something
#: meaningful survives. DELIBERATELY narrower than NOISE_WORDS: a leading "Constant"
#: is scaffolding, but a leading "Total" is the whole point of the column — dropping
#: it turned "Total Deduction" into DEDUCTION, sitting next to "Other Deduction",
#: which is exactly the confusion this programme exists to remove.
LEADING_NOISE = {
    'constant', 'const', 'column', 'col',
    'cho', 'cua', 'va', 'theo', 'cac',
}

#: House abbreviations for words that appear constantly and have one obvious short
#: form. A word listed here is emitted whole at its abbreviation and never truncated,
#: which is what turns "Employee Status" into EMPSTATUS rather than EMPLOYSTATU.
ABBREVIATIONS = {
    'employee': 'EMP',
    'employees': 'EMP',
    'employer': 'ER',
    'allowance': 'ALLOW',
    'allowances': 'ALLOW',
    'insurance': 'INS',
    'number': 'NO',
    'percentage': 'PCT',
    'percent': 'PCT',
    'department': 'DEPT',
    'quantity': 'QTY',
    'nhanvien': 'NV',
}

#: A word shorter than this is emitted whole; a longer one is cut to this many
#: characters before any leftover budget is handed back out. Four is the shortest
#: prefix that still reads as the word ("MEDI", "SOCI", "CONS").
_WORD_UNIT = 4
#: The smallest slice of a dropped word worth re-admitting when budget is left over.
_READD_MIN = 3

CODE_RE = re.compile(r'^[A-Z][A-Z0-9]*$')

_TOKEN_RE = re.compile(r'[A-Za-z]+|[0-9]+')
_LOWER_RE = re.compile(r'[a-z]')

_WORD, _ACRONYM, _NUMBER = 'w', 'a', 'n'


def is_valid_code(code):
    """True when ``code`` satisfies the HARD half of the contract: uppercase
    alphanumeric, starting with a letter, no underscore, no space."""
    return bool(code) and bool(CODE_RE.match(code))


def _tokenize(label):
    """Return ``[(kind, text), ...]`` for an accent-folded label.

    Adjacent numeric runs merge ("10.5%" -> one ``105`` token) so a rate keeps its
    digits together. A token counts as an ACRONYM only when the ORIGINAL label mixes
    case — an all-caps header is shouting, not a list of acronyms.
    """
    folded = strip_accents(str(label or ''))
    label_has_lower = bool(_LOWER_RE.search(folded))
    tokens = []
    for raw in _TOKEN_RE.findall(folded):
        if raw.isdigit():
            if tokens and tokens[-1][0] == _NUMBER:
                tokens[-1] = (_NUMBER, tokens[-1][1] + raw)
            else:
                tokens.append((_NUMBER, raw))
            continue
        upper = raw.upper()
        is_acronym = (label_has_lower and raw.isupper() and 2 <= len(raw) <= 5)
        tokens.append((_ACRONYM if is_acronym else _WORD, upper))
    return tokens


def _unit_for(word):
    """The shortest slice of ``word`` that still reads as the word."""
    abbrev = ABBREVIATIONS.get(word.lower())
    if abbrev:
        return abbrev
    return word[:_WORD_UNIT]


def _assemble(tokens):
    """Spend the MAX_LEN budget across ``tokens``, keeping order.

    Acronyms and numbers are identity — they are kept whole and paid for first.
    Words then take a readable unit each (their abbreviation, or a four-character
    prefix); if the units do not fit, words are dropped from the END, because the
    front of a header says what the thing IS and the tail qualifies it. Whatever
    budget survives grows the kept words back towards their full spelling,
    front-first, and only then re-admits the first dropped word.
    """
    fixed = sum(len(t) for kind, t in tokens if kind in (_ACRONYM, _NUMBER))
    words = [(i, t) for i, (kind, t) in enumerate(tokens) if kind == _WORD]
    budget = MAX_LEN - fixed

    if budget <= 0 or not words:
        return ''.join(t for _kind, t in tokens)[:MAX_LEN]

    units = {i: _unit_for(t) for i, t in words}
    kept = [i for i, _t in words]
    dropped = []
    while kept and sum(len(units[i]) for i in kept) > budget:
        dropped.insert(0, kept.pop())

    alloc = {i: units[i] for i in kept}
    spare = budget - sum(len(v) for v in alloc.values())

    # Grow kept words back towards their full spelling, front-first. An abbreviated
    # word is a deliberate short form and is never re-expanded.
    for i, word in words:
        if spare <= 0:
            break
        if i not in alloc or ABBREVIATIONS.get(word.lower()):
            continue
        grow = min(spare, len(word) - len(alloc[i]))
        if grow > 0:
            alloc[i] = word[:len(alloc[i]) + grow]
            spare -= grow

    # Re-admit the first dropped word if a meaningful slice of it still fits.
    if spare >= _READD_MIN and dropped:
        i = dropped[0]
        word = dict(words)[i]
        alloc[i] = word[:min(spare, len(word))]

    out = []
    for i, (kind, text) in enumerate(tokens):
        if kind in (_ACRONYM, _NUMBER):
            out.append(text)
        elif i in alloc:
            out.append(alloc[i])
    return ''.join(out)[:MAX_LEN]


def _pad(code, tokens):
    """Lift a too-short code towards MIN_LEN using the label's OWN letters.

    A code shorter than six characters drops out of the importer's fuzzy
    header-match fallback (exact and normalized matching still work, so this is a
    degradation and not a break). Where the label has more letters to give — an
    abbreviated word, a spelling the budget never needed — they are spent here.
    Where it genuinely has none ("NPT", "OT"), the code stays short rather than
    being inflated with filler that means nothing to the person reading it.
    """
    if len(code) >= MIN_LEN:
        return code
    pool = ''.join(t for _kind, t in tokens)
    if len(pool) >= MIN_LEN:
        return pool[:MIN_LEN]
    return pool if len(pool) > len(code) else code


def _finalize(code):
    code = re.sub(r'[^A-Z0-9]', '', (code or '').upper())
    if not code:
        return ''
    if code[0].isdigit():
        code = ('C' + code)[:MAX_LEN]
    return code


def _candidate(label, keep_noise):
    tokens = _tokenize(label)
    if not tokens:
        return ''
    if not keep_noise:
        # Leading noise only, and only while a real WORD still follows. "Constant"
        # in front of "Social Ins. - 8%" is scaffolding; "COL" in front of "2024"
        # is the entire name of the column, and dropping it leaves a code that
        # starts with a digit and says nothing.
        trimmed = list(tokens)
        while (trimmed and trimmed[0][0] == _WORD
               and trimmed[0][1].lower() in LEADING_NOISE
               and any(kind == _WORD for kind, _t in trimmed[1:])):
            trimmed.pop(0)
        tokens = trimmed
    code = _finalize(_assemble(tokens))
    if not code:
        return ''
    return _finalize(_pad(code, tokens))


def _collision_tests(existing_codes, reserved):
    """Build the (is_exact, is_substring) pair used everywhere a code is checked.

    ``reserved`` (the config's COLUMN LETTERS) is tested for equality ONLY. A
    letter is one or two characters, so testing it as a substring would make every
    real code "collide" with column A.
    """
    existing = {c for c in (existing_codes or ()) if c}
    letters = {r for r in (reserved or ()) if r}

    def is_exact(cand):
        return cand in existing or cand in letters

    def is_substring(cand):
        return any(cand != e and (cand in e or e in cand) for e in existing)

    return is_exact, is_substring


def dedupe_code_c5(base, existing_codes, max_len=None, reserved=()):
    """Return a code derived from ``base`` that is safe under the C5 contract.

    The HARD guarantee is **underscore-free and unique**. Substring codes resolve
    correctly (maximal munch), so substring-avoidance is a preference here, applied
    only when a short letter suffix achieves it — it is mathematically impossible
    when the base equals an existing code, since every superstring contains it.

    Suffixes are LETTERS so the result stays underscore- and digit-free, and the
    search always terminates. When ``max_len`` is given the base is trimmed to make
    room for the suffix, so a length ceiling is never breached by de-duplication.
    """
    existing = {c for c in (existing_codes or ()) if c}
    is_exact, is_substring = _collision_tests(existing_codes, reserved)

    def _fit(cand, suffix):
        if max_len and len(cand) + len(suffix) > max_len:
            cand = cand[:max(1, max_len - len(suffix))]
        return cand + suffix

    if not is_exact(base) and not is_substring(base):
        return base

    suffixes = [''] + list(string.ascii_uppercase) + [
        a + b for a in string.ascii_uppercase for b in string.ascii_uppercase]
    first_unique = None
    for suffix in suffixes:
        cand = _fit(base, suffix)
        if is_exact(cand):
            continue
        if first_unique is None:
            first_unique = cand
        if not is_substring(cand):
            return cand
    if first_unique is not None:
        return first_unique

    cand = base
    while cand in existing:
        cand = _fit(cand, 'X') if max_len else cand + 'X'
    return cand


def normalize_code(code, label=None, existing_codes=(), reserved=()):
    """Keep a code that already honours the contract; rebuild the ones that do not.

    This is the predicate the upgrade migration skips on, and the guard for every
    path that copies a code in from somewhere else (a salary rule, an uploaded
    JSON structure). A conforming code is left EXACTLY as it is — churn on a code
    that was never broken is churn on live formulas, payslip history and contract
    components for no gain.
    """
    candidate = re.sub(r'\s+', '', (code or '')).upper()
    is_exact, _is_substring = _collision_tests(existing_codes, reserved)
    if is_valid_code(candidate) and len(candidate) <= MAX_LEN:
        if not is_exact(candidate):
            return candidate
        return dedupe_code_c5(candidate, existing_codes, max_len=MAX_LEN, reserved=reserved)
    return build_component_code(candidate or label or '', existing_codes, reserved)


def build_component_code(label, existing_codes=(), reserved=()):
    """Build a readable, converter-safe code for a column called ``label``.

    ``existing_codes`` are the codes already handed out (the code must differ from
    every one of them); ``reserved`` are the config's column LETTERS, which a code
    may never equal or the converter's letter pass hijacks it.

    Deterministic: same label + same seeds -> same code, every time.
    """
    is_exact, is_substring = _collision_tests(existing_codes, reserved)

    def clashes(cand):
        return is_exact(cand) or is_substring(cand)

    primary = _candidate(label, keep_noise=False)
    if not primary:
        primary = 'UNNAMED'
    if not clashes(primary):
        return primary

    # The label's leading noise word is what distinguishes it from the code already
    # taken ("Constant SI-HI-IU Total 10.5%" vs "SI-HI-IU Total 10.5%"). Putting the
    # word back reads far better than bolting a letter onto the end.
    secondary = _candidate(label, keep_noise=True)
    if secondary and secondary != primary and not clashes(secondary):
        return secondary

    return dedupe_code_c5(primary, existing_codes, max_len=MAX_LEN, reserved=reserved)
