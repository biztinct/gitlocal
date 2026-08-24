#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SOURCING S1 — the provenance vocabulary, on a bare interpreter.

`input_provenance` is plain Python with no ``odoo`` import for exactly this reason:
the translation from the resolver's internal words into the product's vocabulary is
the one piece of this phase that can be proven without a database, and MF7's lesson
is that a mandatory gate nobody can execute is not a gate. Run it with::

    python3 pb_hr_payroll_formula/tools/provenance_battery.py

Exit 0 = green. No dependencies, no fixtures, no server.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models'))

import input_provenance as ip  # noqa: E402


FAILURES = []


def check(label, got, want):
    if got != want:
        FAILURES.append("%s\n     got:  %r\n     want: %r" % (label, got, want))


def check_true(label, cond):
    if not cond:
        FAILURES.append(label)


# ---------------------------------------------------------------- test 1
# Every resolved_source the resolver can produce, both origins, plus garbage.
check("raw/excel", ip.provenance_token('raw', 'excel'), 'excel')
check("raw/feed", ip.provenance_token('raw', 'feed'), 'feed')
check("mapped", ip.provenance_token('mapped', 'excel'), 'employee_field')
check("contract_component",
      ip.provenance_token('contract_component', 'excel'), 'contract_component')
check("contract_component_default",
      ip.provenance_token('contract_component_default', 'excel'), 'contract_component')
check("default", ip.provenance_token('default', 'excel'), 'none')

# The resolver leaves resolved_source as None when a component never entered the
# loop. That must be a token, not a crash — this runs inside a payroll run.
check("None", ip.provenance_token(None), 'none')
check("garbage", ip.provenance_token('wat', 'excel'), 'none')
check("raw/garbage-origin", ip.provenance_token('raw', 'wat'), 'excel')

# Every token the translator can emit must be in the declared vocabulary, or a
# downstream chip renders a word no screen has a label for.
for rs in ('raw', 'mapped', 'contract_component', 'contract_component_default',
           'default', None, 'wat'):
    for origin in ('excel', 'feed', 'wat'):
        check_true("token in SOURCES for %r/%r" % (rs, origin),
                   ip.provenance_token(rs, origin) in ip.SOURCES)

# ---------------------------------------------------------------- test 2
# Fixed key order, empties omitted. These blobs are diffed literally by the
# neutrality gate; a dict whose keys wander produces a diff that is all noise.
plain = ip.entry('excel', key='Basic Salary', via='header')
check("plain keys", list(plain.keys()), ['src', 'key', 'via'])
check("plain", plain, {'src': 'excel', 'key': 'Basic Salary', 'via': 'header'})

check("no key -> None", ip.entry('none')['key'], None)
check("empty key -> None", ip.entry('excel', key='')['key'], None)
check_true("fell_back omitted when False", 'fell_back' not in ip.entry('excel'))
check_true("ignored omitted when None", 'ignored' not in ip.entry('excel'))
check_true("adj omitted when empty", 'adj' not in ip.entry('excel', adj=[]))

full = ip.entry('feed', key='ot_150', via='fallback', fell_back=True,
                ignored=ip.ignored_side('excel', 'OT Hours', 10.0),
                adj=['retro', 'proration', 'retro'])
check("full keys", list(full.keys()),
      ['src', 'key', 'via', 'fell_back', 'ignored', 'adj'])
# Deduplicated AND sorted: a re-run must produce the same bytes.
check("adj dedup+sorted", full['adj'], ['proration', 'retro'])
check("ignored shape", full['ignored'],
      {'src': 'excel', 'key': 'OT Hours', 'value': 10.0})

# ---------------------------------------------------------------- test 6
# An out-of-vocabulary word must degrade, never propagate.
check("bad src degrades", ip.entry('nonsense')['src'], 'none')
check("bad via degrades", ip.entry('excel', via='nonsense')['via'], 'default')
check("bad ignored src degrades", ip.ignored_side('nonsense', 'k', 1)['src'], 'none')

# src answers "from where", via answers "why this one". The two vocabularies overlap
# in exactly ONE word, and it is deliberate: a fixed value comes FROM being a
# constant and is chosen BECAUSE it is a constant, so `{src: constant, via: constant}`
# is the honest pairing rather than a collision. Pinned to that single word so a
# future addition that overlaps by accident fails here instead of quietly making a
# chip ambiguous.
check_true("SOURCES non-empty", len(ip.SOURCES) == 8)
check_true("VIAS non-empty", len(ip.VIAS) == 18)
check("vocabulary overlap is exactly {constant}",
      set(ip.SOURCES) & set(ip.VIAS), {'constant'})
check_true("no duplicate sources", len(set(ip.SOURCES)) == len(ip.SOURCES))
check_true("no duplicate vias", len(set(ip.VIAS)) == len(ip.VIAS))

# Every via the resolver and the batch-free producer can emit must be declared.
for via in ('header', 'column_letter', 'employee_mapping', 'contract',
            'contract_default', 'default', 'connector_mapping', 'constant',
            'contract_field', 'worked_days',
            'proration', 'retro', 'carryover',
            'overtime_request', 'business_trip',
            'binding', 'binding_empty', 'fallback'):
    check_true("via declared: %s" % via, via in ip.VIAS)

# ---------------------------------------------------------------- serialisable
# The blob is stored as Text via json.dumps; anything here that json cannot take
# would fail at write time, per payslip, in production.
try:
    json.dumps({'A': plain, 'B': full})
except (TypeError, ValueError) as exc:      # noqa: BLE001 — that is the assertion
    FAILURES.append("entries are not JSON-serialisable: %s" % exc)

# ---------------------------------------------------------------- report
if FAILURES:
    print("PROVENANCE BATTERY: %d FAILURE(S)\n" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    sys.exit(1)
print("PROVENANCE BATTERY: green")
sys.exit(0)
