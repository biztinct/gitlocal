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
    """Yield (path, {en, vi}) for every bilingual leaf under `node`."""
    if isinstance(node, dict):
        if set(node.keys()) == {"en", "vi"}:
            yield path, node
            return
        for k, v in node.items():
            yield from walk_pairs(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_pairs(v, "%s[%d]" % (path, i))


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
