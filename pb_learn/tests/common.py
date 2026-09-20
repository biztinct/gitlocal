# -*- coding: utf-8 -*-
"""Shared helpers for reading the static content plane in tests.

Since LEARNOS Phase 1a there are no content records to search, so the tests
read the same asset the server reads and the browser fetches. They go through
`learn.content` wherever a test is about BEHAVIOUR, and through `load_content()`
where a test is about the FILE — an offline replay harness has no environment.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
CONTENT_PATH = os.path.join(ADDON, 'static', 'content', 'learn_content.json')

_cache = {}


def load_content():
    """The parsed content plane. Read once per process; treat as immutable."""
    if 'tree' not in _cache:
        with open(CONTENT_PATH, encoding='utf-8') as fh:
            _cache['tree'] = json.load(fh)
    return _cache['tree']


def one(pair, lang='en'):
    """One language out of a `{en, vi}` leaf. Tolerates '' and a raw string."""
    if not pair:
        return ''
    if isinstance(pair, str):
        return pair
    return pair.get(lang) or pair.get('en') or ''


def walk_pairs(node, path=""):
    """Yield (path, {en, vi}) for every bilingual PROSE leaf under `node`.

    `{en, vi}` is a SHAPE, and Phase 2 gave it a second meaning: a glossary
    entry's `match` block is `{en: [...aliases], vi: [...aliases]}` — the same
    two keys carrying lists of match terms rather than a sentence in each
    language. Every caller here does string work (`.strip()`, a regex), so
    yielding those crashed four bundle invariants — and a check that raises is
    a check that is no longer checking, which is the expensive half of the bug.

    A non-string leaf is therefore skipped rather than yielded, and it is NOT
    skipped silently: `test_bundle.test_04c` asserts that every non-string
    `{en, vi}` leaf in the corpus is a glossary `match` list, so a prose field
    that accidentally becomes a list still fails loudly instead of vanishing
    from the walk.
    """
    if isinstance(node, dict):
        if set(node.keys()) == {"en", "vi"}:
            if isinstance(node.get("en"), str) and isinstance(node.get("vi"), str):
                yield path, node
            return
        for k, v in node.items():
            yield from walk_pairs(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_pairs(v, "%s[%d]" % (path, i))


def walk_all_pairs(node, path=""):
    """`walk_pairs` without the prose filter — every `{en, vi}` leaf, string
    or not. Exists for the one test that audits what the filter removed
    (`test_bundle.test_04c`); production-shaped checks want `walk_pairs`."""
    if isinstance(node, dict):
        if set(node.keys()) == {"en", "vi"}:
            yield path, node
            return
        for k, v in node.items():
            yield from walk_all_pairs(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_all_pairs(v, "%s[%d]" % (path, i))


def lessons(tree=None):
    tree = tree or load_content()
    for station in tree['stations']:
        for lesson in station.get('lessons') or []:
            yield station, lesson


def lesson_steps(tree=None):
    for _station, lesson in lessons(tree):
        for step in lesson.get('steps') or []:
            yield lesson, step


def mission_steps(tree=None):
    tree = tree or load_content()
    for mission in tree['missions']:
        for step in mission.get('steps') or []:
            yield mission, step


def scenarios(tree=None):
    """LEARNOS Phase 1b. `.get`, not `[...]`: the offline replay harness can be
    pointed at an older content plane and a missing section must read as an
    empty one rather than a KeyError three tests deep."""
    tree = tree or load_content()
    return tree.get('scenarios') or []


def scenario_steps(tree=None):
    for scenario in scenarios(tree):
        for step in scenario.get('steps') or []:
            yield scenario, step
