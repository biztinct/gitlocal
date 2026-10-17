# -*- coding: utf-8 -*-
"""LEARNREV P1 — THE CONTENT ENGINE: a screen's help, read from the product.

`learn.guide.guide(screen_key, args)` returns one Guide (handover §4): what the
screen is for, where it sits (hub › tab, and the screens before and after it),
what needs doing on it right now, a card for every column and control on it,
the buttons and what they call, and the doors to the lesson, the walkthroughs
and the glossary — in the asking person's language.

THREE LAYERS, ONE SOURCE
------------------------
* GENERATED (the truth). Labels, help texts and choice labels come from
  `fields_get()` at call time, so they are the product's own words, already
  translated by the ORM. Nothing in a manifest may restate them.
* AUTHORED (the meaning). A screen MANIFEST — a plain dict in the module that
  owns the screen, `<module>/learn_manifest.py` — adds one sentence of purpose,
  how each field gets filled, which code reads it and what changing it does.
  Every authored sentence carries `en` AND `vi`.
* LIVE (right now). A manifest may name a provider, `model.method`, on the
  screen's own server model. It runs as the asking person and returns
  numbered things to do, each with an action the panel can wire.

WHY THE MANIFEST LIVES BESIDE THE SCREEN
----------------------------------------
Product modules never import pb_learn (the soft-dependency rule the router
already follows). pb_learn finds the manifests by importing
`odoo.addons.<module>.learn_manifest` for every LOADED module that ships one,
so a screen's help ships, upgrades and disappears with the screen.

RUNS AS THE PERSON. NEVER ELEVATED.
-----------------------------------
Field metadata is not secret; a provider's figures are, and the provider's own
access checks decide what this person may see. An access refusal becomes a
named reason in `missing`, never an exception (zero dead ends). The truth gate
(`tests/test_guide_truth.py`) greps this file and every manifest for the
elevation call and fails the build on one.
"""
import importlib
import importlib.util
import logging

from odoo import api, models
from odoo.exceptions import AccessError, UserError

from .learn_content import text

_logger = logging.getLogger(__name__)

MANIFEST_MODULE = 'learn_manifest'

#: LEARNREV P2 — the Guide panel, the (i) field cards and the Guide-backed
#: Explain / whatnext answers. OFF by default: with it off the drawer, Explain
#: and the whatnext answer are exactly what shipped before P2.
GUIDE_FLAG = 'pb_learn.guide_enabled'

#: Settings › Access and delegations and the left-menu editor (owner ruling
#: 2026-10-13, ONECHAT OC19): the Guide never offers a door into them, even
#: when a manifest names one. The client applies the same filter.
ACCESS_HUB_XMLID = 'pb_settings.action_pb_settings_hub'
ACCESS_TAG = 'pb_settings_hub'
ACCESS_LENSES = ('access', 'nav')

#: The one learn.event kind a field card's thumbs write (no free text).
FEEDBACK_KIND = 'guide_feedback'


def is_access_target(open_=None, tag=None, lens=None):
    """True for a door into Settings › Access and delegations / the menu
    editor: an `open` dict ({xmlid, lens}) or a manifest path (tag, lens)."""
    if open_:
        return (open_.get('xmlid') == ACCESS_HUB_XMLID
                and (open_.get('lens') or '') in ACCESS_LENSES)
    return tag == ACCESS_TAG and (lens or '') in ACCESS_LENSES

#: The reasons `missing` can hold. Plain words: a panel may show them.
NO_MANIFEST = 'no manifest for this screen yet'
RN_NONE = 'right_now: nothing live for this screen yet'
RN_NO_ACCESS = 'right_now: no access'
RN_UNAVAILABLE = 'right_now: not available on this database'
RN_FAILED = 'right_now: could not be read'

#: The attributes a field card needs. Asked for explicitly, so a field with
#: groups the person lacks is simply absent rather than half-described.
FIELD_ATTRS = ['string', 'help', 'selection', 'type']

_DISCOVERED = {}


def discover(module_names, strict=False):
    """`{screen_key: manifest}` for every module in `module_names` that ships a
    `learn_manifest.py`. Each manifest gains `_module` (its owner).

    Cached per set of loaded modules: a registry reload with a different set
    rebuilds it, a request never does. `strict` re-raises a broken manifest
    (the truth gate wants the traceback); at run time a broken manifest is
    logged and skipped, so one bad file costs its own screens and no others.
    """
    key = frozenset(module_names or ())
    if not strict and key in _DISCOVERED:
        return _DISCOVERED[key]
    found = {}
    for name in sorted(key):
        dotted = 'odoo.addons.%s.%s' % (name, MANIFEST_MODULE)
        try:
            spec = importlib.util.find_spec(dotted)
        except (ImportError, ValueError):
            spec = None
        if spec is None:
            continue
        try:
            mod = importlib.import_module(dotted)
        except Exception:                                     # noqa: BLE001
            if strict:
                raise
            _logger.exception("pb_learn: cannot read %s — its screens have no "
                              "guide until it is fixed.", dotted)
            continue
        for screen_key, manifest in (getattr(mod, 'MANIFESTS', None) or {}).items():
            if screen_key in found:
                msg = ("pb_learn: screen %r is described twice (%s and %s); "
                       "the first one wins." % (screen_key,
                                               found[screen_key]['_module'], name))
                if strict:
                    raise ValueError(msg)
                _logger.warning(msg)
                continue
            found[screen_key] = dict(manifest, _module=name)
    if not strict:
        _DISCOVERED.clear()
        _DISCOVERED[key] = found
    return found


def is_vi(lang):
    return str(lang or '').startswith('vi')


def hub_screen(screens, tag):
    """The orientation screen of the hub whose action tag is `tag`, or None
    (precedent: `engine/places.js hubScreenOf`)."""
    for screen in screens or ():
        hub = screen.get('hub') or None
        if hub and hub.get('tag') == tag:
            return screen
    return None


def parse_place(place):
    """`"pb_pay_hub:runs"` → `("pb_pay_hub", "runs")`; anything else → None."""
    if not isinstance(place, str) or ':' not in place:
        return None
    tag, _sep, lens = place.partition(':')
    if not tag or not lens or '/' in lens:
        return None
    return tag, lens


class LearnGuide(models.AbstractModel):
    """`learn.guide` — one Guide per screen, generated. Reads only."""
    _name = 'learn.guide'
    _description = 'Learn screen guide'

    # ------------------------------------------------------------ registry
    @api.model
    def _manifests(self):
        return discover(self.env.registry._init_modules)

    @api.model
    def manifest(self, screen_key):
        """The manifest for one screen key, or None."""
        return self._manifests().get(screen_key)

    @api.model
    def _lang(self):
        # `env.lang` raises for a language that is not installed; a guide
        # never raises, it answers in English instead.
        try:
            return self.env.lang or self.env.user.lang or 'en_US'
        except UserError:
            return 'en_US'

    # ------------------------------------------------------------ the call
    @api.model
    def rpc_guide(self, screen_key, args=None):
        """The public door the panel calls. Same answer as `guide()`."""
        return self.guide(screen_key, args=args)

    @api.model
    def guide(self, screen_key, args=None):
        """The Guide JSON for `screen_key` (handover §4), in the person's
        language. Never raises for a missing piece: `missing` names it."""
        lang = self._lang()
        args = dict(args or {})
        content = self.env['learn.content']
        screen = content.screen(screen_key) or {}
        man = self.manifest(screen_key)
        missing = []

        if not man:
            return {
                'screen': {
                    'key': screen_key,
                    'name': text(screen.get('name'), lang) or screen_key,
                    'purpose': text(screen.get('blurb'), lang),
                    'path': self._path_from_places(screen, lang),
                    'before': [], 'after': [],
                },
                'right_now': {'ok': False, 'items': []},
                'fields': [],
                'actions': [],
                'doors': self._doors_without_manifest(screen_key, lang),
                'lang': lang,
                'missing': [NO_MANIFEST],
            }

        out = {
            'screen': {
                'key': screen_key,
                'name': text(screen.get('name'), lang) or screen_key,
                'purpose': text(man.get('purpose'), lang),
                'path': self._path(man, screen, lang, missing),
                'before': self._neighbours(man.get('before'), lang),
                'after': self._neighbours(man.get('after'), lang),
            },
            'right_now': self._right_now(man, args, lang, missing),
            'fields': self._field_cards(man, lang, missing),
            'actions': [self._action(a, lang) for a in man.get('actions') or ()],
            'doors': self._doors(man, screen_key, lang),
            'lang': lang,
            'missing': missing,
        }
        return out

    # ------------------------------------------------------------ "You are here"
    @api.model
    def _place_path(self, tag, lens, lang, missing=None):
        screens = self.env['learn.content'].screens()
        hub = hub_screen(screens, tag)
        if not hub:
            if missing is not None:
                missing.append('path: the hub %s is not described yet' % tag)
            return []
        h = hub['hub']
        path = [{'label': text(hub.get('name'), lang),
                 'open': {'xmlid': h.get('xmlid')}}]
        if lens:
            tab = (h.get('tabs') or {}).get(lens)
            if not tab:
                if missing is not None:
                    missing.append('path: the tab %s is not described yet' % lens)
                return path
            path.append({'label': text(tab.get('name'), lang),
                         'open': {'xmlid': h.get('xmlid'), 'lens': lens,
                                  'lens_key': h.get('lens_key') or 'pb_lens'}})
        return path

    @api.model
    def _path(self, man, screen, lang, missing):
        p = man.get('path') or {}
        if is_access_target(tag=p.get('tag'), lens=p.get('lens')):
            # The Access ruling: never a door into Access and delegations.
            missing.append('path: not offered here')
            return []
        if p.get('tag'):
            return self._place_path(p['tag'], p.get('lens'), lang, missing)
        if p.get('xmlid'):
            return [{'label': text(screen.get('name'), lang),
                     'open': {'xmlid': p['xmlid']}}]
        missing.append('path: not declared')
        return []

    @api.model
    def _path_from_places(self, screen, lang):
        """For a screen with no manifest: the first hub tab it lives at, or the
        hub itself when the screen IS a hub page."""
        hub = screen.get('hub') or None
        if hub:
            return [{'label': text(screen.get('name'), lang),
                     'open': {'xmlid': hub.get('xmlid')}}]
        for place in screen.get('places') or ():
            parsed = parse_place(place)
            if parsed and not is_access_target(tag=parsed[0], lens=parsed[1]):
                return self._place_path(parsed[0], parsed[1], lang)
        return []

    @api.model
    def _screen_path(self, screen_key, lang):
        """Where another screen lives, as path labels: its manifest's path
        when it has one, else its first hub place (for "Next: Pay Run › Run")."""
        screen = self.env['learn.content'].screen(screen_key) or {}
        man = self.manifest(screen_key)
        if man:
            return self._path(man, screen, lang, [])
        return self._path_from_places(screen, lang)

    @api.model
    def _neighbours(self, items, lang):
        content = self.env['learn.content']
        out = []
        for item in items or ():
            other = content.screen(item.get('screen')) or {}
            places = [pp for pp in map(parse_place, other.get('places') or ()) if pp]
            if places and all(is_access_target(tag=t, lens=l) for t, l in places):
                # A neighbour that lives only behind the Access ruling.
                continue
            out.append({'screen': item.get('screen'),
                        'name': text(other.get('name'), lang) or item.get('screen'),
                        'why': text(item.get('why'), lang)})
        return out

    # ------------------------------------------------------------ fields
    @api.model
    def _field_cards(self, man, lang, missing):
        # NOT `_fields`: that name is every model's field registry, and a
        # method called `_fields` shadows it (LEARNREV ledger LR16).
        model = man.get('model')
        meta = {}
        if model:
            if model not in self.env:
                missing.append('fields: %s is not installed' % model)
                return []
            names = []
            for f in man.get('fields') or ():
                for attr in ('field', 'source_field'):
                    if f.get(attr):
                        names.append(f[attr])
            meta = self.env[model].with_context(lang=lang).fields_get(
                names, attributes=FIELD_ATTRS)
        out = []
        for f in man.get('fields') or ():
            col = f.get('column') or {}
            card = {'key': f['key'], 'column': text(col, lang),
                    # LEARNREV P2: both spellings, so the (i) finds its header
                    # whichever language the screen itself is drawn in.
                    'columns': [c for c in (text(col, 'en_US'), text(col, 'vi_VN')) if c],
                    'anchor': f.get('anchor') or '',
                    'if_changed': text(f.get('if_changed'), lang)}
            if f.get('derived'):
                card.update({
                    'derived': True,
                    'values': [{'value': k, 'label': text(v, lang)}
                               for k, v in (f.get('values') or {}).items()],
                    'filled_by': text(f.get('how'), lang),
                    'used_by': self._used_by(f, lang),
                })
                out.append(card)
                continue
            fmeta = meta.get(f.get('field'))
            if not fmeta:
                missing.append('fields: %s is not readable here' % f['key'])
                continue
            when = f.get('choices_when') or {}
            card.update({
                'derived': False,
                'field': f['field'],
                'type': fmeta.get('type') or '',
                'label': fmeta.get('string') or '',
                'help': fmeta.get('help') or '',
                'choices': [{'value': value, 'label': label,
                             'when': text(when.get(value), lang)}
                            for value, label in (fmeta.get('selection') or ())],
                'filled_by': text(f.get('filled_by'), lang),
                'source_values': [],
                'used_by': self._used_by(f, lang),
            })
            smeta = meta.get(f.get('source_field')) if f.get('source_field') else None
            if smeta:
                card['source_label'] = smeta.get('string') or ''
                card['source_values'] = [{'value': v, 'label': lab}
                                         for v, lab in (smeta.get('selection') or ())]
            out.append(card)
        return out

    @api.model
    def _used_by(self, f, lang):
        # `ref` (file:symbol) is the gate's evidence, not reading matter: it
        # stays out of the answer. `via` names the copied field it travels
        # through, for a reader that wants to follow it.
        return [{'label': text(u.get('label'), lang), 'via': u.get('via') or ''}
                for u in f.get('used_by') or ()]

    @api.model
    def _action(self, a, lang):
        return {'label': text(a.get('label'), lang),
                'method': a.get('method') or '',
                'effect': text(a.get('effect'), lang),
                'writes': bool(a.get('writes'))}

    # ------------------------------------------------------------ right now
    @api.model
    def _right_now(self, man, args, lang, missing):
        raw = self._right_now_raw(man, args, missing)
        if raw is None:
            return {'ok': False, 'items': [], 'provider': bool(man.get('right_now'))}
        items, ok = raw
        return {'ok': ok, 'items': [self._item(i, lang) for i in items],
                'provider': True}

    @api.model
    def right_now_pairs(self, screen_key, args=None):
        """LEARNREV P2 — the right-now items with their text kept in BOTH
        languages (`{en, vi}`), for an answer the drawer renders bilingually
        (the whatnext intent). None when the screen has no provider here."""
        man = self.manifest(screen_key)
        if not man or not man.get('right_now'):
            return None
        missing = []
        raw = self._right_now_raw(man, dict(args or {}), missing)
        if raw is None:
            return {'items': [], 'missing': missing}
        items, _ok = raw
        return {'items': [dict(self._item(i, 'en_US'),
                               text={'en': text(i.get('text'), 'en_US'),
                                     'vi': text(i.get('text'), 'vi_VN')})
                          for i in items], 'missing': missing}

    @api.model
    def _right_now_raw(self, man, args, missing):
        """(provider items as returned, ok) — or None, with the reason in
        `missing`, when there is nothing to show."""
        ref = man.get('right_now')
        if not ref:
            missing.append(RN_NONE)
            return None
        model, _dot, method = ref.rpartition('.')
        if model not in self.env or not hasattr(self.env[model], method):
            missing.append(RN_UNAVAILABLE)
            return None
        try:
            # A savepoint, because a provider that fails half-way through a
            # query would otherwise poison the request's transaction and the
            # rest of the Guide would never render (LEARNOS Phase 0 gotcha).
            with self.env.cr.savepoint():
                result = getattr(self.env[model], method)(dict(args))
        except AccessError:
            missing.append(RN_NO_ACCESS)
            return None
        except Exception:                                     # noqa: BLE001
            _logger.exception("pb_learn: right-now provider %s failed", ref)
            missing.append(RN_FAILED)
            return None
        # A provider returns a list of items, or {"items": [...], "missing":
        # "<reason>"} when it cannot answer for a reason worth naming (no
        # scheme selected, for instance).
        if isinstance(result, dict):
            for reason in ([result['missing']] if isinstance(result.get('missing'), str)
                           else result.get('missing') or ()):
                missing.append('right_now: %s' % reason)
            items = result.get('items') or []
            ok = not result.get('missing')
        else:
            items, ok = result or [], True
        return items, ok

    @api.model
    def _item(self, item, lang):
        action = item.get('action') or None
        if action and action.get('kind') == 'open' \
                and is_access_target({'xmlid': action.get('xmlid'),
                                      'lens': action.get('lens')}):
            action = None
        out = {'key': item.get('key') or '',
               'count': item.get('count') or 0,
               'severity': item.get('severity') or 'info',
               'text': text(item.get('text'), lang),
               'action': action}
        if item.get('names'):
            out['names'] = list(item['names'])
        return out

    # ------------------------------------------------------------ doors
    @api.model
    def _station_door(self, station_key, lang):
        content = self.env['learn.content']
        station = content.station(station_key) if station_key else None
        if not station:
            return {'station': None, 'station_name': '', 'lesson': None}
        lessons = station.get('lessons') or []
        return {'station': station['key'],
                'station_name': text(station.get('name'), lang),
                'lesson': lessons[0]['key'] if lessons else None}

    @api.model
    def _task(self, scenario, lang):
        return {'key': scenario['key'], 'name': text(scenario.get('name'), lang),
                'modes': list(scenario.get('modes') or [])}

    @api.model
    def _doors(self, man, screen_key, lang):
        content = self.env['learn.content']
        doors = self._station_door(man.get('station') or screen_key, lang)
        tasks = []
        for key in man.get('tasks') or ():
            scenario = content.scenario(key)
            if scenario and not scenario.get('retired'):
                tasks.append(self._task(scenario, lang))
        glossary = {g['key']: g for g in content.glossary()}
        terms = []
        for key in man.get('terms') or ():
            g = glossary.get(key)
            if g:
                terms.append({'key': key, 'term': text(g.get('term'), lang),
                              'definition': text(g.get('definition'), lang)})
        doors.update(tasks=tasks, terms=terms)
        return doors

    # ------------------------------------------------------------ P2
    @api.model
    def enabled(self):
        """The Guide switch (`learn.settings` 'guide')."""
        from .learn_question import _flag_on   # late: learn_question imports widely
        return _flag_on(self.env, GUIDE_FLAG)

    @api.model
    def rpc_feedback(self, screen_key, field_key, up):
        """A field card's thumbs. One `learn.event` row, the drawer's own
        logging seam: the screen, `<field>:up|down`, never any free text.
        A screen or field the manifests do not declare writes nothing."""
        man = self.manifest(str(screen_key or ''))
        keys = {f.get('key') for f in (man or {}).get('fields') or ()}
        if not man or field_key not in keys:
            return False
        detail = ('%s:%s' % (field_key, 'up' if up else 'down'))[:64]
        return bool(self.env['learn.event'].log(
            FEEDBACK_KIND, screen=str(screen_key)[:64], detail=detail,
            lang='vi' if is_vi(self._lang()) else 'en'))

    @api.model
    def explain_material(self, screen_key, columns=3):
        """What "Explain this screen" says from the Guide, in BOTH languages
        (the drawer picks): the purpose, "You are here", the first screen
        after this one, the first `columns` field cards as "Column — help",
        and whether a live right-now list exists. None without a manifest.
        Never runs the right-now provider (the panel shows the live list)."""
        man = self.manifest(screen_key)
        if not man:
            return None
        content = self.env['learn.content']
        screen = content.screen(screen_key) or {}
        out = {'purpose': {}, 'path': {}, 'next': {}, 'columns': [],
               'provider': bool(man.get('right_now'))}
        cols = {}
        for tag, lang in (('en', 'en_US'), ('vi', 'vi_VN')):
            out['purpose'][tag] = text(man.get('purpose'), lang)
            out['path'][tag] = ' › '.join(
                p['label'] for p in self._path(man, screen, lang, []) if p.get('label'))
            after = (man.get('after') or [{}])[0].get('screen')
            out['next'][tag] = ' › '.join(
                p['label'] for p in self._screen_path(after, lang) if p.get('label')) \
                if after else ''
            try:
                cards = self._field_cards(man, lang, [])[:columns]
            except UserError:
                # Vietnamese is not switched on here (LR28): English cards.
                cards = self._field_cards(man, 'en_US', [])[:columns]
            for card in cards:
                cols.setdefault(card['key'], {})[tag] = (
                    card.get('column') or '',
                    (card.get('help') or card.get('filled_by') or '').strip())
        out['columns'] = [cols[k] for k in cols if 'en' in cols[k]]
        return out

    @api.model
    def _doors_without_manifest(self, screen_key, lang):
        """What a screen with no manifest can still offer: its station (when it
        is one) and the walkthroughs that name it."""
        content = self.env['learn.content']
        doors = self._station_door(screen_key, lang)
        doors['tasks'] = [self._task(s, lang) for s in content.scenarios()
                          if not s.get('retired')
                          and screen_key in (s.get('screens') or ())]
        doors['terms'] = []
        return doors
