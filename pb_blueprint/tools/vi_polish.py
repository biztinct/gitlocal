#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repair and validate a generated Vietnamese catalogue.

`tools/refresh_pb_vi.py` merges the POT with the shared translation memory and
fills the gaps; this is the pass after it, and it exists because of two things
that pass silently:

1. **The shared tool STRIPS edge whitespace from a msgid it extracted from
   source** (`refresh_pb_vi.py:406`), so `_t(" and ")` is stored as `and` and
   never matches at runtime — the screen keeps the English word and nothing
   reports it. Every msgid the POT holds is restored exactly, and the
   translation is re-padded with the same spaces.
2. **A translatable FIELD can be a JSON document.** The Vietnam · Complete
   starter's `components_json` is 54,000 characters of data, and a "translated"
   copy of it would be a corrupted starter. Anything that big is dropped.

Then it validates what a `.po` must satisfy before it goes anywhere near a
database: every entry carries `#. module: <name>` (GR5 — a missing one is an
`AttributeError` inside `_update_translations` and the registry does not load),
and no translation contains a word a user may never read.

    .venv/bin/python pb_blueprint/tools/vi_polish.py \\
        --po pb_blueprint/i18n/vi_VN.po --pot /tmp/bp6_pots/pb_blueprint.pot
"""
import argparse
import re
import sys

import polib

MODULE_RE = re.compile(r"(module[s]?): (\w+)")
BANNED = ('odoo', 'blueprint')
#: Longer than this and it is data, not a sentence.
MAX_MSGID = 1500


def polish(po_path, pot_path=None, quiet=False):
    catalog = polib.pofile(po_path)
    say = (lambda *a: None) if quiet else print

    # ---- 1. data is not language ------------------------------------
    for entry in [e for e in catalog if len(e.msgid) > MAX_MSGID]:
        say("dropping %s characters of data (%s)"
            % (len(entry.msgid), (entry.occurrences or [('?', '')])[0][0]))
        catalog.remove(entry)

    # ---- 2. a msgid is what the source actually asks for -------------
    if pot_path:
        template = polib.pofile(pot_path)
        by_stripped = {}
        for entry in catalog:
            by_stripped.setdefault(entry.msgid.strip(), entry)
        for wanted in template:
            if not wanted.msgid or wanted.msgid == wanted.msgid.strip():
                continue
            if catalog.find(wanted.msgid):
                continue
            entry = by_stripped.get(wanted.msgid.strip())
            if not entry or not entry.msgstr:
                continue
            lead = wanted.msgid[:len(wanted.msgid) - len(wanted.msgid.lstrip())]
            tail = wanted.msgid[len(wanted.msgid.rstrip()):]
            say("restoring the spaces around %r" % wanted.msgid)
            entry.msgid = wanted.msgid
            entry.msgstr = '%s%s%s' % (lead, entry.msgstr.strip(), tail)

    catalog.save(po_path)

    # ---- 3. the checks that stand between this file and an outage ----
    problems = []
    for entry in catalog:
        if not MODULE_RE.match(entry.comment or ''):
            problems.append('no "#. module:" comment: %r' % entry.msgid[:60])
        low = (entry.msgstr or '').lower()
        for word in BANNED:
            if word in low:
                problems.append('%r translates to something containing "%s"'
                                % (entry.msgid[:40], word))
    say("%s entries; %s empty; %s problems"
        % (len(catalog), sum(1 for e in catalog if not e.msgstr.strip()),
           len(problems)))
    for problem in problems[:10]:
        say("  !", problem)
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--po', required=True)
    parser.add_argument('--pot')
    args = parser.parse_args()
    return 1 if polish(args.po, args.pot) else 0


if __name__ == '__main__':
    sys.exit(main())
