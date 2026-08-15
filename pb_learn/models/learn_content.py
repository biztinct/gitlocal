# -*- coding: utf-8 -*-
"""The one server-side door onto the static content plane.

WHERE THE CONTENT LIVES NOW
---------------------------
`pb_learn/static/content/learn_content.json`, generated from
docs/tutorial_poc/author/ by tools/gen_learn_data.py. There is no learn.station,
learn.lesson, learn.intent, learn.screen, learn.column, learn.string or
learn.glossary.term table any more, and that is the point of Phase 1a: content
is identical on an empty tenant, on the demo and on the apex, an upgrade cannot
half-apply it, and nothing a tenant does can corrupt it.

Every prose leaf in that file is already `{"en": ..., "vi": ...}` and every raw
scalar is already raw, so the runtime bilingual zip is gone with the records.
The rule the generator now applies at emission time is the one
`learn_station._zip_bilingual` used to apply at read time — an empty
translatable stays the empty STRING rather than becoming a truthy pair, and
`_RAW_KEYS` is no longer a list anybody has to maintain against the payload,
because the payload is written the way it is served.
`docs/tutorial_poc/author/tools/parity_check.py` is what proves the two agree.

WHY AN ABSTRACT MODEL AND NOT A PLAIN HELPER
--------------------------------------------
Same argument as `learn.live`: one auditable door. Everything that reads
content — the ask() resolver, the composer's corpus, the capstone predicates,
the runtime bootstrap — reaches it as `self.env['learn.content']`, so
`contract.json::composer-corpus-reads-learn-content-only` can keep asking its
general question (every model a method reaches is inside `learn.`) instead of
being rewritten into a blocklist of the product models somebody thought of.

CACHING
-------
`functools.lru_cache` on the module-level loader: parsed once per worker
process, and refreshed by a RESTART. That is the correct trade here because the
file only ever changes with a code deploy, and a deploy restarts the workers.
Editing the JSON on a running server and expecting the change to appear is the
one thing this will not do — and hand-editing a generated file is a build
failure anyway.
"""
import functools
import json
import logging

from odoo import api, models, tools

_logger = logging.getLogger(__name__)

CONTENT_PATH = 'pb_learn/static/content/learn_content.json'

# Returned when the asset is missing or unreadable. Every accessor below is
# total, so a broken deploy degrades to an empty Journey and an honest Coach
# miss rather than to a traceback on every screen in the product.
_EMPTY = {
    'version': '', 'chrome': {}, 'stations': [], 'missions': [], 'glossary': [],
    'intents': [], 'screens': [], 'columns': [], 'global_suggest': [],
    # LEARNOS Phase 6 — the reading order of the map's lines.
    'line_order': [],
    # LEARNOS Phase 1b. One authored walkthrough, three ways to take it.
    'scenarios': [],
}


@functools.lru_cache(maxsize=1)
def _load():
    try:
        with tools.file_open(CONTENT_PATH, 'r') as fh:
            tree = json.load(fh)
    except Exception:                                         # noqa: BLE001
        _logger.error("pb_learn: cannot read %s — the learning surfaces will be "
                      "empty until it is restored.", CONTENT_PATH, exc_info=True)
        return dict(_EMPTY)
    out = dict(_EMPTY)
    out.update(tree)
    return out


def text(pair, lang='en_US'):
    """One language out of a `{en, vi}` leaf.

    Accepts the empty string (an empty translatable) and a plain string (a raw
    scalar that turned out not to be prose after all), because a caller that
    has to type-check every leaf before printing it will eventually forget one.
    """
    if not pair:
        return ''
    if isinstance(pair, str):
        return pair
    return pair.get('vi' if str(lang or '').startswith('vi') else 'en') or \
        pair.get('en') or ''


class LearnContent(models.AbstractModel):
    """Read-only accessors over learn_content.json.

    Abstract on purpose: there is nothing to store. Nothing here writes, and
    nothing here reads a product model — `contract.json::learn-content-is-
    static-and-read-only` pins both.
    """
    _name = 'learn.content'
    _description = 'Learn static content plane'

    # -- the whole tree ---------------------------------------------------
    @api.model
    def tree(self):
        """The parsed asset. TREAT AS IMMUTABLE — it is one shared dict per
        process, so a caller that mutates it corrupts every later request."""
        return _load()

    @api.model
    def version(self):
        return _load().get('version') or ''

    # -- collections ------------------------------------------------------
    @api.model
    def stations(self):
        return _load()['stations']

    @api.model
    def missions(self):
        return _load()['missions']

    @api.model
    def scenarios(self):
        return _load()['scenarios']

    @api.model
    def glossary(self):
        return _load()['glossary']

    @api.model
    def intents(self):
        return _load()['intents']

    @api.model
    def screens(self):
        return _load()['screens']

    @api.model
    def columns(self):
        return _load()['columns']

    @api.model
    def chrome(self):
        return _load()['chrome']

    @api.model
    def line_order(self):
        """The READING order of the map's lines, authored in one place.

        LEARNOS Phase 6. It used to be a constant in journey.js alone, which
        was fine while only the page needed it; `learn.runtime.next_best()`
        needs the same order to answer "the next required station", and two
        copies of an order is the shape the ledger keeps recording. Emitted by
        the generator out of `docs/tutorial_poc/author/data.js`, and pinned
        against the frontend copy by
        `contract.json::journey-line-order-is-authored-once`.
        """
        return _load().get('line_order') or []

    @api.model
    def global_suggest(self):
        return _load()['global_suggest']

    # -- lookups ----------------------------------------------------------
    @api.model
    def station(self, key):
        return next((s for s in self.stations() if s['key'] == key), None)

    @api.model
    def mission(self, key):
        return next((m for m in self.missions() if m['key'] == key), None)

    @api.model
    def mission_step(self, mission_key, step_key):
        mission = self.mission(mission_key)
        if not mission:
            return None, None
        step = next((s for s in mission['steps'] if s['key'] == step_key), None)
        return mission, step

    @api.model
    def scenario(self, key):
        return next((s for s in self.scenarios() if s['key'] == key), None)

    @api.model
    def screen(self, key):
        if not key:
            return None
        return next((s for s in self.screens() if s['key'] == key), None)

    @api.model
    def intent(self, key):
        return next((i for i in self.intents() if i['key'] == key), None)

    @api.model
    def screen_columns(self, screen_key):
        return [c for c in self.columns() if c['screen'] == screen_key]

    @api.model
    def chrome_text(self, key, lang='en_US'):
        """One chrome string. Falls back to the KEY, never to silence: a
        learner who sees `live.noRun` can report it and one who sees nothing
        cannot."""
        return text(self.chrome().get(key), lang) or key
