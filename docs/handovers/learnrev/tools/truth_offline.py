#!/usr/bin/env python3
"""LEARNREV P5b — the truth gate's file half and replica half, offline, over
this checkout (no database). The database half (fields, choices, methods)
still runs as TestGuideTruth on a clone.

    python3 docs/handovers/learnrev/tools/truth_offline.py      # exit 1 on any error
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, os.path.join(REPO, 'pb_learn', 'tests'))
sys.path.insert(0, os.path.join(REPO, 'docs', 'tutorial_poc', 'author', 'tools'))

import guide_truth as gt          # noqa: E402
import export_manifests as em     # noqa: E402


def read_rel(rel):
    path = os.path.join(REPO, rel or '')
    if not rel or not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


_PO = {}


def po_for(module):
    if module not in _PO:
        _PO[module] = gt.live_po(read_rel('%s/i18n/vi_VN.po' % module),
                                 read_rel('%s/i18n/%s.pot' % (module, module)))
    return _PO[module]


def main():
    manifests = em.load_manifests(REPO)
    content = json.loads(read_rel('pb_learn/static/content/learn_content.json'))
    anchors = json.loads(read_rel('pb_learn/static/src/anchors.json'))
    errors = []
    for key, man in sorted(manifests.items()):
        errors += gt.check_files(key, man, read_rel, content, anchors, po_for)
        errors += gt.check_replica(key, man, read_rel)
    for e in errors:
        print(e)
    print('%d manifests, %d error(s)' % (len(manifests), len(errors)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
