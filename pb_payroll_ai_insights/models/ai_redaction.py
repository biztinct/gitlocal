# -*- coding: utf-8 -*-
"""Names out on the way to a provider, names back on the way to the reader.

WHY THIS EXISTS
---------------
Three paths in this module put real records on a wire to an external model.

  * ``payroll_ai_engine._process_data_query`` serialised the whole query result
    into the prompt, and one of those results is a list of employees with their
    job titles and their wages.
  * ``payroll_ai_pulse._generate_ai_summaries`` put an alert's ``details`` in a
    prompt, and two kinds of alert list the people who joined or left this week
    by name.
  * ``payroll_ai_report`` — the PDF's section narratives and its executive
    summary — puts ``json.dumps(section['data'])`` in a prompt, and the salary
    section's data is the same employee list. That path spent four phases
    DEAD, because it asked ``payroll.ai.config`` for a factory method that does
    not exist and a bare ``except`` swallowed the AttributeError. LEARNOS
    Phase 6 repaired the lookup and redacted the payload IN THE SAME CHANGE,
    which is the Phase-4 ruling written down: repairing a dead provider call is
    switching an egress path ON, so the fix and the redaction are one change or
    neither.

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
  * **PRIOR-TURN NAMES IN CONVERSATION HISTORY — CLOSED IN LEARNOS PHASE 6,
    and what closed it is worth stating because the residual used to live
    here.** The mapping used to be per-CALL: a person restored into an earlier
    answer survived the next turn's history scrub, because there was nothing
    to match them against. The mapping is now per-CONVERSATION
    (``payroll.ai.conversation.redaction_map``, a JSON column on the row) —
    every turn loads it, extends it and saves it, and all four engine paths
    redact their history turns THROUGH it. A name this conversation has ever
    seen is therefore removed from every later turn, on every path, and keeps
    the SAME placeholder so "[person-2] again" is still about the same person.
    What that buys costs a stored association between a placeholder and a real
    employee name; the retention rule sits on the field that holds it, in
    ``payroll_ai_conversation.py``, and the mapping dies with the conversation
    and with "clear chat".
    Still open, one step further out: a person named in the very FIRST turn
    they appear in, before any query has read them, is not yet in the mapping
    — see the raw-current-message residual below;
  * a department, a job title or a project name is not treated as personal
    data, because it is not, even though a one-person department identifies
    somebody;
  * **DICTIONARY KEYS: SUBSTITUTED, NEVER COLLECTED FROM.** Phase 6 changed
    half of this. A key that CONTAINS an already-collected name is rewritten
    like any other string, so the guarantee at the top ("no string anywhere in
    the returned structure") now includes keys. What is still true is that a
    key is never a place a name is FOUND: keys are normally our own field
    names, and a heuristic that guessed which of them are people would blank
    ``department`` and hand the model a payload it cannot read.
    So a name that appears ONLY as a key and nowhere else is not collected and
    therefore not removed. Two sites key on a record value today —
    ``payroll_ai_pulse._detect_leave_anomalies`` keys ``by_type`` on the leave
    type's name and ``_detect_overtime_spikes`` keys on the department — and
    neither is a person. That is held by a TEST rather than by a comment:
    ``tests/test_egress.py::test_02d`` parses the pulse and refuses any
    detector that keys a map on anything derived from an employee;
  * **A NAME IN FREE TEXT UNDER A NON-PERSON KEY IS INVISIBLE TO THE
    COLLECTOR, and one of those shipped.** `payroll.ai.pulse.summary` is a
    sentence a model wrote which this module then put the names back INTO
    before storing — correct for the database, which is inside the trust
    boundary, and fatal the moment that row is put in another prompt. `summary`
    is not in ``PERSON_KEYS``, so ``collect_names`` walked straight past it and
    the PDF report's Anomaly Alerts section went out with the week's joiners
    named in full (found in the Phase 6 review). There is no general fix here:
    a collector cannot find a name in prose without something to match it
    against. What the CALLER can do is establish provenance — every name a
    generated sentence can contain came from the record it was generated from,
    so that record is redacted first and the sentence is redacted against the
    resulting mapping, and where the provenance cannot be checked the sentence
    is dropped. `payroll_ai_report.alert_rows` is the worked example.
    **THE RULE FOR THE NEXT CALLER: a string that this module has ever run
    ``restore_names`` over is a person key in everything but name. Treat it as
    one, or do not put it in a prompt;**
  * **RAW AUDIO LEAVES THIS SERVER ON THE VOICE PATH.** ``rpc_transcribe_voice``
    posts the recording itself to the provider's speech-to-text endpoint. A
    recording is not redactable — it is a person's voice saying a colleague's
    name, and there is no placeholder for either. Nothing here can reduce it,
    so it is GATED instead: a tenant flag (``payai.voice_enabled``, absent
    means off) AND that user's own recorded consent, both re-asked server-side
    on every call, with the consent text naming the audio and the provider.
    The transcribed TEXT then enters the ordinary engine path and is redacted
    exactly like a typed question. The reply is spoken by the BROWSER's own
    speech synthesiser, so no answer text goes back out to be read aloud;
  * **THE CURRENT USER MESSAGE GOES OUT RAW ON THE KNOWLEDGE, ONBOARDING AND
    GENERAL PATHS.** Only the ~20-token classification call sees the scrubbed
    form; one call later the same text leaves verbatim, because scrubbing a
    live question degrades the answer ("is 4.200.000 the right minimum
    wage?" must not become "[amount]"). The data path redacts it with the
    mapping. Stated here because the history redaction on those three paths
    therefore protects mainly ASSISTANT turns — and note that Phase 6 did NOT
    change this: a name in the current message goes out on those three paths
    even when the conversation mapping already knows that person. Deliberate,
    because the fix is not free (it is the same "degrades the answer"
    argument), and left as a stated residual rather than a quiet one;
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


def _walk_strings(node, fn, key=None, key_fn=None):
    """Rebuild `node` with `fn(value, key)` applied to every string LEAF.

    ``key_fn``, when given, is applied to every string KEY as well — and it is
    NOT the same function. A key is one of our own field names in almost every
    payload this module builds (``employee``, ``total_salary``), so the generic
    patterns must not run over it: a key rewritten to ``[number]`` is a payload
    the model cannot read and an answer nobody can parse. What ``key_fn`` does
    is substitute names that have ALREADY been collected, which is the one
    rewrite that is always safe — the name is going out either way, and a key
    built from a record is the one shape where it would otherwise survive.

    A COLLISION IS NOT SILENTLY MERGED. Two different keys can only redact to
    the same string if they carried the same name, but "cannot happen" is how
    a dict comprehension quietly loses a row, so the loop below discriminates
    instead of overwriting.
    """
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            new_k = key_fn(k) if (key_fn and isinstance(k, str)) else k
            if new_k in out and new_k != k:
                suffix = 2
                while '%s~%d' % (new_k, suffix) in out:
                    suffix += 1
                new_k = '%s~%d' % (new_k, suffix)
            out[new_k] = _walk_strings(v, fn, k, key_fn)
        return out
    if isinstance(node, (list, tuple)):
        return [_walk_strings(v, fn, key, key_fn) for v in node]
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


def extend_mapping(names, mapping=None):
    """Add any unseen name to `mapping`, keeping every placeholder it had.

    THE POINT OF ITS EXISTING (LEARNOS Phase 6). The mapping used to be built
    from scratch on every call, which made "[person-1]" mean a different
    person on every turn of the same conversation — coherent inside one
    prompt, incoherent across three. A conversation now carries its mapping,
    and this is what grows it: an existing person keeps their number and a new
    one takes the next free one.

    THE DEDUPE KEY IS THE ACCENTED FORM, AND THE FIRST DRAFT GOT THIS WRONG IN
    THE ONE DIRECTION THAT LEAKS.

    It filed a name as "already known" if EITHER its stored spelling or its
    tone-folded spelling had been seen. Tone folding is not injective in
    Vietnamese: **Hùng and Hưng both fold to Hung**, and so do Dũng/Dụng,
    Lân/Lấn, Trâm/Trầm. Two different colleagues would therefore share one
    entry — and only the FIRST of them was in the mapping, so the second one's
    real name matched nothing and went into the prompt in full. A dedupe rule
    that silently merges two people is an egress bug wearing a tidiness
    argument.

    So:

      * the PRIMARY key is the stored, accented spelling (casefolded). Two
        distinct accented spellings are always two people;
      * the folded spelling is a SECONDARY lookup, and it is accepted only
        while it is UNAMBIGUOUS. The moment a second distinct accented
        spelling folds onto it, that fold entry stops matching anybody, and a
        later unaccented mention takes a fresh placeholder rather than being
        attached to whichever of the two came first;
      * a fold match is accepted only for an incoming spelling that carries no
        tone marks of its own — "NGUYEN THI MAI" out of an import, or the same
        name typed in a hurry. An incoming spelling that HAS marks and differs
        from the stored one is a different person as far as this function is
        concerned, and gets its own placeholder. Over-issuing a placeholder
        costs a little coherence; under-issuing one costs a name.

    RESIDUAL, stated here because it is the price of the rule above: when two
    mapped people do share a folded spelling, an UNACCENTED mention of it in
    free text is still replaced — by one of their two placeholders, chosen by
    the pattern builder. It is redacted either way; it may be attributed to the
    wrong one of the two. The alternative (leaving it alone) is the name.
    """
    out = dict(mapping or {})
    exact = {}          # casefolded accented spelling -> placeholder
    folded = {}         # casefolded folded spelling  -> placeholder, or None
    highest = 0

    def remember(name, placeholder):
        key = name.casefold()
        exact[key] = placeholder
        fold = _ascii(name).casefold()
        if not fold:
            return
        if fold in folded and folded[fold] != placeholder:
            folded[fold] = None                     # ambiguous from now on
        elif fold not in folded:
            folded[fold] = placeholder

    for placeholder, original in out.items():
        found = _PERSON_RE.fullmatch(placeholder or '')
        if found:
            highest = max(highest, int(found.group(1)))
        if original:
            remember(original, placeholder)

    for name in names:
        key = name.casefold()
        if key in exact:
            continue
        fold = _ascii(name).casefold()
        known = folded.get(fold)
        if known and fold == key:
            # A tone-free respelling of somebody already mapped, and no second
            # person has claimed that fold. Same placeholder; remember the
            # spelling so the same string is not re-tested next turn.
            exact[key] = known
            continue
        highest += 1
        placeholder = _PERSON_FMT % highest
        out[placeholder] = name
        remember(name, placeholder)
    return out


def redact_names(payload, person_keys=None, mapping=None):
    """(redacted payload, {placeholder: original}).

    The mapping is what ``restore_names`` needs and it never leaves this
    server. Nothing is mutated: the payload handed in is returned unchanged
    and a new structure comes back, because the caller keeps using the
    original for the fields it answers from.

    `mapping` is the conversation's accumulated table, or None for a one-shot
    caller (the PDF report, the pulse). The mapping that comes back is the
    WHOLE table, extended — callers persist it and hand it back next turn.
    """
    names = collect_names(payload, person_keys)
    mapping = extend_mapping(names, mapping)
    pattern, spellings = _name_pattern(mapping)

    def scrub(value, _key):
        if pattern is not None:
            value = _sub_names(pattern, spellings, value)
        return _apply_scrub(value)

    def scrub_key(key):
        # NAMES ONLY. See `_walk_strings`: the generic patterns are for values.
        if pattern is None:
            return key
        return _sub_names(pattern, spellings, key)

    return _walk_strings(payload, scrub, key_fn=scrub_key), mapping


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
