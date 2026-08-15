# -*- coding: utf-8 -*-
"""Names out on the way to a provider, names back on the way to the reader.

WHY THIS EXISTS
---------------
Two paths in this module put real records on a wire to an external model.

  * ``payroll_ai_engine._process_data_query`` serialised the whole query result
    into the prompt, and one of those results is a list of employees with their
    job titles and their wages.
  * ``payroll_ai_pulse._generate_ai_summaries`` put an alert's ``details`` in a
    prompt, and two kinds of alert list the people who joined or left this week
    by name.

Both are LEGACY paths and this module is not a licence for new ones. The rule
everything else in Payobook follows is the pb_learn rule — the corpus is our
own written material, and no record enters a prompt at all. These two predate
it and answer questions that genuinely need the data, so the compromise is
narrower: the ASKING USER was entitled to those names (the access gate in
``payroll_data_query`` has already run and can refuse), and the PROVIDER was
not. So the names travel as placeholders and come back as names.

THE PROPERTY, WRITTEN DOWN BEFORE THE EXAMPLES
----------------------------------------------
After ``redact_names``, **no string anywhere in the returned structure contains
any name that was in the original**, in either its accented or its
tone-folded spelling. Not "the keys we thought of are blanked" — the names are
collected by key and then removed from EVERY string, because a name that is
correctly redacted in ``employee`` and left standing inside a ``title`` has not
been redacted. ``tests/test_redaction.py`` asserts the property, and the
examples are checked against it rather than the other way round.

DUPLICATED FROM pb_learn ON PURPOSE — see pb_learn/models/learn_intent.py,
whose ``_ascii`` and ``_SCRUB`` family this copies. NOT imported: pb_learn does
not depend on this module and this module must not depend on pb_learn, and a
cross-addon import for four regexes would make each uninstallable without the
other for no gain. The two copies are ~30 lines and both carry a pointer to the
other; if one is fixed, fix both. (The Phase D review found a real bug in that
family — a trailing ``\\b`` after ``₫`` — and it is fixed in both copies here.)

WHAT THIS IS NOT
----------------
It is a REDUCTION, not a guarantee, and the residual is stated where the
mechanism is rather than only in a report:

  * a name the payload does not contain cannot be collected, so a person named
    in the QUESTION but absent from the result survives unless the generic
    patterns below happen to catch it;
  * **PRIOR-TURN NAMES IN CONVERSATION HISTORY.** Every history message now
    passes through ``generic_scrub`` on all four engine paths, which takes out
    emails, phones, record ids and money — but a REAL NAME that an earlier turn
    restored into an answer survives if that person is not in the CURRENT
    turn's mapping, because there is nothing to match them against. The mapping
    is per-call by construction. Closing it needs a mapping that lives as long
    as the conversation does, keyed on the session, and that is a schema change
    with its own retention question: it means storing the association between a
    placeholder and a real employee. **Phase 6, beside the voice and PDF-report
    egress work** — the three are one change, not three.
  * a department, a job title or a project name is not treated as personal
    data, because it is not, even though a one-person department identifies
    somebody;
  * **DICTIONARY KEYS ARE NEVER REDACTED, ONLY VALUES.** Keys are normally our
    own field names, so rewriting them would hand the model a payload it cannot
    read. Where a key is built FROM a record the guarantee does not hold —
    ``payroll_ai_pulse._detect_leave_anomalies`` keys ``by_type`` on the leave
    type's own name, and ``_detect_overtime_spikes`` keys on the department.
    Neither is a person today; a future detector that keys on an employee name
    would leak, and the guard comment sits at those sites as well as here;
  * **THE CURRENT USER MESSAGE GOES OUT RAW ON THE KNOWLEDGE, ONBOARDING AND
    GENERAL PATHS.** Only the ~20-token classification call sees the scrubbed
    form; one call later the same text leaves verbatim, because scrubbing a
    live question degrades the answer ("is 4.200.000 the right minimum
    wage?" must not become "[amount]"). The data path redacts it with the
    mapping. Stated here because the history scrub on those three paths
    therefore protects mainly ASSISTANT turns;
  * a BARE 7-8 DIGIT AMOUNT with no separators and no currency mark
    ("salary 15000000") survives every generic pattern — the marked, the
    grouped and the 9+-digit rules each need what it lacks. VND salaries
    typed without separators sit exactly in that gap;
  * a PARTIAL or MIXED-DIACRITIC spelling in free text survives. Both the
    stored form and the fully tone-folded form are matched, so
    "Nguyễn Thị Mai" and "Nguyen Thi Mai" both go — "Nguyên Thị Mai", with one
    mark wrong, does not, and neither does a first name alone unless it is
    stored as its own record;
  * a HYPHENATED or re-spaced name splits. The matcher is literal over the two
    stored spellings, so "Nguyen-Thi-Mai" is three tokens it has never seen;
  * the model still learns the SHAPE of the data — how many people, what the
    wages are, how they are distributed. That is what the question asked for.
"""
import re
import unicodedata

# Placeholders. Numbered from 1, in order of first appearance, and stable
# within one call so that "[person-1] earns more than [person-2]" survives the
# round trip as a sentence about the same two people.
_PERSON_FMT = '[person-%d]'
_PERSON_RE = re.compile(r'\[person-(\d+)\]')

# The keys whose VALUES are somebody's name in the two payload shapes this
# module produces: ``payroll_data_query._query_individual_data`` writes
# ``employee``; ``payroll_ai_pulse._detect_headcount_changes`` writes ``name``
# inside its ``details`` JSON.
#
# THIS LIST IS A COLLECTOR, NOT THE GUARD. It decides which strings are
# gathered as names; the guard is that every gathered name is then removed from
# the whole structure. A key missing from here is a real gap, and the test that
# would catch it is the property test over a payload built by the real query
# layer — not this list being reviewed for completeness, which is the failure
# mode the ledger keeps recording.
#
# ``department`` is deliberately absent. It is not a person, and blanking it
# turns "Overtime rose in Retail" into a sentence with no subject.
PERSON_KEYS = frozenset((
    'employee', 'employee_name', 'employees',
    'name', 'full_name', 'person', 'staff',
    'holder', 'account_holder', 'created_by', 'manager', 'reports_to',
))

# Everything below is the pb_learn family, copied. See the module docstring.
#
# TWO SCRUBS, NOT ONE, AND THE DIFFERENCE IS MONEY.
#
# `_VALUE_SCRUB` runs over the strings INSIDE a payload we built. Every figure
# in one of those is a JSON number, so it is never seen here — and that is
# correct, because the totals are the answer the question asked for. Blanking
# them would be a refusal wearing a redaction's clothes.
#
# `_FREETEXT_SCRUB` runs over text a PERSON typed: the message handed to the
# intent classifier, and every turn of the conversation history. There a
# money-shaped number is not the answer, it is somebody's pay written into a
# help box, so the two amount rules from pb_learn's `_scrub` are added.
_VALUE_SCRUB = (
    (re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b'), '[email]'),
    # A Vietnamese number is written "+84 912 345 678" as often as
    # "+84912345678"; health_learn's original demanded a digit immediately
    # after the country code and the spaced form walked straight through.
    (re.compile(r'(?:\+?84|0)[\s.-]?\d[\d\s.-]{7,}\d'), '[phone]'),
    (re.compile(r'#\d{2,}'), '[record]'),
    # A long bare digit run is an id, not a figure.
    (re.compile(r'\b\d{9,}\b'), '[number]'),
)

# A number wearing a currency mark is money whatever its size, and this rule
# runs BEFORE the grouped-digit one — the other way round the digits are
# replaced first and the mark is left stranded beside the placeholder.
#
# THE TRAILING BOUNDARY MUST NOT BE `\b`. `₫` is not a word character, so `\b`
# after it requires a word character to follow, which at the end of a sentence
# there never is. pb_learn shipped that bug and its own ledger bullet claimed
# the case worked; `(?!\w)` is what was meant. Fixed in both copies.
_CURRENCY_AMOUNT = re.compile(
    r'\b\d[\d.,]*\s*(?:₫|vnđ|vnd|đồng|dong|đ)(?!\w)', re.IGNORECASE)

# Digit groups written the way money is written — 4.200.000 or 4,200,000.
# Applied through a callback so a bare "10,5" (a rate, in Vietnamese decimal
# notation) survives: a rate is not personal data, and scrubbing it makes the
# question meaningless while protecting nobody.
_GROUPED_DIGITS = re.compile(r'\b\d{1,3}(?:[.,]\d{3})+\b')


def _ascii(text):
    """Tone marks stripped, đ folded, case PRESERVED.

    The second spelling of a name a person might type or a system might store.
    Copied from pb_learn's ``_ascii``; see the module docstring.
    """
    s = (text or '').replace('đ', 'd').replace('Đ', 'D')
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


# THE BOUNDARY, and why it is not ``\b``. That class is ASCII word characters,
# so a Vietnamese name ending in a tone-marked vowel has no boundary after it
# and a name beginning with one has none before it. Lookarounds on the
# letter/digit class — the shape pb_learn's jargon gate settled on after the
# same discovery — do what the boundary was meant to. Built once, inside
# ``_name_pattern``, over the whole alternation.
_BOUNDARY_BEFORE = r'(?<![0-9A-Za-zÀ-ỹ])'
_BOUNDARY_AFTER = r'(?![0-9A-Za-zÀ-ỹ])'


def _walk_strings(node, fn, key=None):
    """Rebuild `node` with `fn(value, key)` applied to every string LEAF.

    Keys are never rewritten. They are our own field names — ``employee``,
    ``total_salary`` — and a prompt whose keys have been redacted is a prompt
    the model cannot read.
    """
    if isinstance(node, dict):
        return {k: _walk_strings(v, fn, k) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [_walk_strings(v, fn, key) for v in node]
    if isinstance(node, str):
        return fn(node, key)
    return node


def collect_names(payload, person_keys=None):
    """Every distinct person name in the payload, in order of first appearance."""
    keys = PERSON_KEYS if person_keys is None else person_keys
    found = []
    seen = set()

    def visit(value, key):
        if (str(key or '').lower() in keys and value.strip()
                and value.strip() not in seen):
            seen.add(value.strip())
            found.append(value.strip())
        return value

    _walk_strings(payload, visit)
    return found


def _name_pattern(mapping):
    """One regex over every spelling of every mapped name, LONGEST FIRST.

    Longest first is not a tidiness preference. "Hùng" is a substring of
    "Trần Văn Hùng", and the short one matching first leaves
    "Trần Văn [person-2]" — a redaction that reads as a bug and hands the
    provider two thirds of the name.

    CASE-INSENSITIVE, and the lookup is folded to match. A payroll import
    writes "NGUYEN THI MAI", a person typing a question writes "nguyen thi
    mai", and the employee record says "Nguyễn Thị Mai" — a matcher that only
    knows the stored casing lets the two commonest spellings through. The
    lookup table is keyed on the CASEFOLDED spelling for the same reason: with
    IGNORECASE on and an exact-cased dict, a match on "NGUYEN THI MAI" would
    not be a key, and the substitution would raise rather than redact. A
    redactor that can be made to raise is not a redactor.
    """
    spellings = {}
    for placeholder, original in mapping.items():
        for form in (original, _ascii(original)):
            if form:
                spellings[form.casefold()] = placeholder
    if not spellings:
        return None, {}
    body = '|'.join(re.escape(s) for s in
                    sorted(spellings, key=lambda s: (-len(s), s)))
    return re.compile('%s(?:%s)%s' % (_BOUNDARY_BEFORE, body, _BOUNDARY_AFTER),
                      re.IGNORECASE), spellings


def _sub_names(pattern, spellings, text):
    """Replace every matched spelling, folding the match to find its
    placeholder. `.get` with the raw match as a last resort so an unfoldable
    edge case degrades to leaving the text alone rather than to a traceback."""
    return pattern.sub(
        lambda m: spellings.get(m.group(0).casefold(),
                                spellings.get(m.group(0), m.group(0))), text)


def _apply_scrub(text):
    for pattern, replacement in _VALUE_SCRUB:
        text = pattern.sub(replacement, text)
    return text


def generic_scrub(text):
    """Contact details and money out of FREE TEXT, with no mapping needed.

    THE POINT OF ITS EXISTING SEPARATELY: there are places on the wire where
    no mapping is available yet. The intent classifier runs BEFORE any query,
    so nothing has been read and there are no names to map; the three
    non-data paths never build a mapping at all. Those calls still must not
    carry somebody's email, phone or salary, and this is what they get.

    It cannot remove a NAME — that needs something to match against. What it
    covers is stated, and what it does not is in the residual list at the top
    of this module rather than left to be discovered.
    """
    if not isinstance(text, str) or not text:
        # A truthy non-string (a client sending 5, True, a list) must come
        # back unharmed, not raise: a scrub that can be made to raise is a
        # scrub somebody will wrap in a try that swallows more than this.
        return text
    text = _apply_scrub(text)
    text = _CURRENCY_AMOUNT.sub('[amount]', text)
    return _GROUPED_DIGITS.sub(
        lambda m: ('[amount]' if sum(c.isdigit() for c in m.group(0)) >= 5
                   else m.group(0)),
        text)


def redact_text(text, mapping):
    """One string, ready for a prompt: mapped names out, everything generic too.

    Used for the parts of a request that are not the payload — the user's own
    message and the recent conversation turns on the data path, where a
    mapping exists. Everywhere else `generic_scrub` is what is available.
    """
    if not isinstance(text, str) or not text:
        return text
    pattern, spellings = _name_pattern(mapping)
    if pattern is not None:
        text = _sub_names(pattern, spellings, text)
    return generic_scrub(text)


def redact_names(payload, person_keys=None):
    """(redacted payload, {placeholder: original}).

    The mapping is what ``restore_names`` needs and it never leaves this
    server. Nothing is mutated: the payload handed in is returned unchanged
    and a new structure comes back, because the caller keeps using the
    original for the fields it answers from.
    """
    names = collect_names(payload, person_keys)
    mapping = {_PERSON_FMT % (i + 1): name for i, name in enumerate(names)}
    pattern, spellings = _name_pattern(mapping)

    def scrub(value, _key):
        if pattern is not None:
            value = _sub_names(pattern, spellings, value)
        return _apply_scrub(value)

    return _walk_strings(payload, scrub), mapping


def restore_names(text, mapping):
    """Put the people back, for the reader who was allowed to see them.

    Matched as a WHOLE placeholder through one regex rather than by replacing
    each key in turn: ``[person-1]`` is a prefix of ``[person-10]``, so a
    naive loop over the mapping renames the eleventh person to
    "Nguyễn Thị Mai0". An unknown number is left exactly as the model wrote
    it — inventing a name for a placeholder nobody issued is the one outcome
    worse than a visible placeholder.
    """
    if not text or not mapping:
        return text
    return _PERSON_RE.sub(
        lambda m: mapping.get(_PERSON_FMT % int(m.group(1)), m.group(0)), text)


def restore_deep(node, mapping):
    """`restore_names` over every string in a structure.

    The model's reply is not only prose: a chart's ``labels`` are the names it
    was given, and an insight is a sentence about them. Restoring the narrative
    and leaving "[person-1]" along the x-axis would be a worse outcome than not
    redacting at all, because it looks like a rendering bug rather than a
    privacy control.
    """
    if not mapping:
        return node
    return _walk_strings(node, lambda v, _k: restore_names(v, mapping))
