# -*- coding: utf-8 -*-
"""Where a payroll input value came from — one vocabulary, one translation.

The import resolver has always KNOWN this. `_transform_data_to_formula_inputs`
computes a `resolved_source` for every component of every employee, and
`lookup_raw_value_with_key` hands back the header key that actually matched — and
then both were logged for two hardcoded component names and dropped on the floor.
The owner could not answer "where does this number come from?" about their own
payroll because the answer was computed, printed to a log nobody reads, and
discarded, roughly forty thousand times a run.

This module is the vocabulary that answer is expressed in, and the single place the
resolver's internal words are translated into it. It is DELIBERATELY plain Python —
no ``odoo`` import, stdlib only, exactly like ``component_code`` — so the bare-
``python3`` regression battery can exercise it without a database (MF7: a mandatory
gate nobody can execute is not a gate).

TWO AXES, NEVER CONFLATED:

* ``src`` answers **from where** — one of :data:`SOURCES`, eight values, fixed.
* ``via`` answers **why this one** — one of :data:`VIAS`.

They are separate because "Spreadsheet, because you bound it there" and
"Spreadsheet, because its name happened to match a header" are the difference
between a configured system and a lucky one, and only the first is worth trusting.

Nothing here raises. It runs inside a payroll computation; an unknown word must
degrade to "no source" and let the run finish, never take a payslip down with it.
"""

#: What a value came FROM. The product's vocabulary, used identically by the
#: serializer, the components rail, the cards, the Cell Editor, the grid headers,
#: both mapping boards and the cockpit. User-facing LABELS deliberately do not live
#: here — they need translation, and this module must stay import-free.
SOURCES = (
    'excel',               # a column of the uploaded workbook
    'feed',                # a key delivered by a connected system's feed
    'rule',                # a key computed by a transformation rule before payroll
    'contract_component',  # the amount stored on the employee's contract
    'employee_field',      # a field read off the employee or contract record
    'calculated',          # computed by this scheme's own formula
    'constant',            # the same number for everyone
    'none',                # nothing feeds it; it fell back to its default
)

#: Why THIS source won. Ordered roughly strongest-to-weakest.
VIAS = (
    'binding',            # an explicit per-component binding chose it        (S3)
    'binding_empty',      # a binding was set but neither side carried a value (S3)
    'fallback',           # the bound side was empty, the other one had it     (S3)
    'header',             # a header/key matched the rule's name or code
    'column_letter',      # matched by spreadsheet column letter
    'connector_mapping',  # a connected system's field mapping supplied it
    'employee_mapping',   # read off the employee/contract via a field mapping
    'contract',           # the contract carried this component's amount
    'contract_default',   # it is a contract component, and the contract had none
    'contract_field',     # read directly off a contract field (e.g. the wage)
    'worked_days',        # taken from a worked-days line
    # Approved-workflow streams, injected by the bridge modules. They are the
    # employee's own records rather than anything imported, which is why they carry
    # src 'employee_field' — `via` is what says WHICH record, and a chip that only
    # said "Employee record" for an overtime total would send the reader to the
    # wrong screen.
    'overtime_request',
    'business_trip',
    'constant',           # it is a fixed value
    # The three adjustments, as the reason a code EXISTS at all. An adjustment that
    # merely rewrites an already-resolved value does not change its `via` — it adds
    # itself to `adj` and the entry keeps saying where the number came from. These
    # are only used when the adjustment INVENTED the code, which has no other source.
    'proration',
    'retro',
    'carryover',
    'default',            # nothing matched; the component's own default was used
)

#: The resolver's internal words -> :data:`SOURCES`. `raw` is the interesting one:
#: it means "it was in the imported row", which until a run can carry two sources
#: is always the spreadsheet, and from S3 onward depends on which blob it came from.
#: That is why the caller passes `origin` rather than this module assuming it.
_RESOLVED = {
    'raw': None,                                     # -> origin
    'mapped': 'employee_field',
    'contract_component': 'contract_component',
    'contract_component_default': 'contract_component',
    'default': 'none',
}

#: Adjustments that may rewrite a value after it has been resolved.
ADJUSTMENTS = ('proration', 'retro', 'carryover')


def provenance_token(resolved_source, origin='excel'):
    """Translate the resolver's ``resolved_source`` into a :data:`SOURCES` value.

    THE ONLY PLACE THIS TRANSLATION HAPPENS (design §4.4). A second copy would be
    a second vocabulary, and MF31's lesson is that a duplicated predicate is a
    predicate that will be half-fixed.

    ``origin`` is which blob the row came from — ``'excel'`` or ``'feed'`` — and is
    consulted only for ``'raw'``. Unknown input degrades to ``'none'``; this runs
    inside a payroll run and must not be the thing that stops it.
    """
    if resolved_source not in _RESOLVED:
        return 'none'
    token = _RESOLVED[resolved_source]
    if token is not None:
        return token
    return origin if origin in SOURCES else 'excel'


def entry(src, key=None, via='default', fell_back=False, ignored=None, adj=None):
    """One component's provenance, in a fixed key order with the empties omitted.

    Fixed order because these blobs are diffed against each other — the neutrality
    gate compares them literally — and a dict whose keys wander produces a diff
    that is all noise. Empties are omitted because the common case (a value that
    simply matched its header) should cost four keys, not seven, across tens of
    thousands of payslips.
    """
    out = {
        'src': src if src in SOURCES else 'none',
        'key': key if key else None,
        'via': via if via in VIAS else 'default',
    }
    if fell_back:
        out['fell_back'] = True
    if ignored:
        out['ignored'] = ignored
    if adj:
        # Sorted so a re-run produces the same bytes; ADJUSTMENTS order is not
        # meaningful, and an unstable list would break the byte-identity gate.
        out['adj'] = sorted(set(adj))
    return out


def ignored_side(src, key, value):
    """The value the binding did NOT use, recorded rather than dropped.

    The owner's decision was that the unused side is *reported*. Recording only
    that it existed would make the report untriageable — "the feed also sent
    something" is not actionable, "the feed also sent 12,000,000 and you used
    11,500,000" is. Unreachable until S3; defined here so its shape is fixed once.
    """
    return {'src': src if src in SOURCES else 'none',
            'key': key if key else None,
            'value': value}
