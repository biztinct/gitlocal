# -*- coding: utf-8 -*-
"""LEARNREV P0 (G24, ledger LR4) — the screens PayAI can open when the browser
sent no ⌘K rows.

The chat registers the person's ⌘K rows on their conversation when it mounts
(`rpc_register_doors`). When none arrived — a fresh conversation after Clear,
the rows not loaded yet, a failed call — `resolve_door` used to ask the
person to shut the panel and open it again: to repair the product. Instead
the server builds the same kind of list itself, from what it already knows:

  * the hubs and their tabs, from the Learn content plane
    (`learn_content.json` `screens[key=hub_*].hub` — tag, xmlid, lens key and
    every tab's name in both languages), which is the server-side mirror of
    the hubs' ⌘K rows;
  * the Learn content screens that live on a hub tab (`screens[].places`,
    "pb_pay_hub:runs"), so a screen is found by its own name too
    ("Component treatment").

Every row carries its destination (`hub`), because the browser's
`pb_hub_palette.run(id)` knows none of these ids: the door opens through
`openHub`, the path ⌘K's own rows take. Navigation only (PA19) — every screen
keeps its own server gates. A row is offered only when the person can see the
screen: its left-menu entry is 'on' for them (`pb.sidebar.item.visibility_for`,
the rule the left menu is drawn from), or, for a screen with no left-menu
entry (Mapping opens from Settings), the screen's own permissions let them in.
The Access deny-list (`gate.door_denied`) applies as everywhere else.
"""
import logging

from . import gate
from .i18n import is_vi

_logger = logging.getLogger(__name__)

#: Ids of the server's rows. Never a ⌘K id, so nothing that asks
#: `ctx.has_door('payhub_runs')` changes meaning.
PREFIX = 'pbdoor.'

#: The ⌘K id prefix of a hub's tab rows (pay_hub_palette.js "payhub_runs",
#: home_hub_palette.js "homehub_approvals" …) — only to borrow the words
#: people use for them (`resolve.DOOR_ALIASES`), never as an id.
_PALETTE_PREFIX = {
    'pb_pay_hub': 'payhub',
    'pb_home_hub': 'homehub',
    'pb_compliance_hub': 'cmphub',
    'pb_insights_hub': 'inshub',
    'pb_people_hub': 'peoplehub',
}

#: The lens key a plain hub reads (`openHub`'s default).
_PLAIN_LENS_KEY = 'pb_lens'


def _pair(value):
    if isinstance(value, dict):
        en = value.get('en') or ''
        return en, value.get('vi') or en
    return str(value or ''), str(value or '')


def _target(hub, lens):
    """`openHub` options for this hub (and tab)."""
    out = {'tag': hub.get('tag') or '', 'xmlid': hub.get('xmlid') or ''}
    if lens:
        key = hub.get('lens_key') or _PLAIN_LENS_KEY
        if key == _PLAIN_LENS_KEY:
            out['lens'] = lens
        else:
            # pb_mission reads `pb_shell_lens`, the Mapping studio `pb_mode`;
            # the chat's door hands `context` to openHub as it is.
            out['context'] = {key: lens}
    return {k: v for k, v in out.items() if v}


def _visible_hubs(env, user, hubs):
    """{hub tag: True} for the hubs this person can open."""
    out = {}
    Item = env['pb.sidebar.item'].sudo()
    try:
        vis = env['pb.sidebar.item'].visibility_for(user)
    except Exception:                                       # noqa: BLE001
        _logger.warning("payai: left-menu visibility unavailable", exc_info=True)
        return out
    items = vis.get('items') or {}
    sections = vis.get('sections') or {}
    for hub in hubs:
        tag, xmlid = hub.get('tag') or '', hub.get('xmlid') or ''
        entries = Item.search(['|', ('action_tag', '=', tag or '-'),
                               ('action_xmlid', '=', xmlid or '-')])
        if entries:
            out[tag] = any(
                items.get(e.id) == 'on'
                and sections.get(e.section_id.id, 'on') == 'on'
                and (not e.parent_id or items.get(e.parent_id.id) == 'on')
                for e in entries)
            continue
        # No left-menu entry of its own: the screen's own permissions.
        act = env.ref(xmlid, raise_if_not_found=False) if xmlid else None
        if not act:
            out[tag] = False
            continue
        act = act.sudo()
        groups = act.group_ids if 'group_ids' in act._fields else env['res.groups']
        out[tag] = not groups or bool(groups & user.sudo().all_group_ids)
    return out


def server_doors(env, user=None):
    """The rows, in the shape `rpc_register_doors` stores (plus `hub`,
    `aliases` and `names`), for the screens this person can open."""
    user = user or env.user
    Content = env.get('learn.content') if hasattr(env, 'get') else None
    if Content is None:
        return []
    try:
        screens = Content.screens() or []
    except Exception:                                       # noqa: BLE001
        return []
    from .resolve import DOOR_ALIASES, fold
    vi = is_vi(user.lang or 'en_US')
    hubs = {}
    for s in screens:
        hub = s.get('hub') or {}
        if str(s.get('key') or '').startswith('hub_') and hub.get('tag'):
            hubs[hub['tag']] = dict(hub, name=s.get('name'))
    if not hubs:
        return []
    visible = _visible_hubs(env, user, hubs.values())
    rows = {}

    def add(rid, name, hub, lens, kind, extra_names=()):
        en, vi_name = _pair(name)
        hub_en, hub_vi = _pair(hub.get('name'))
        if not lens:
            hub_en = hub_vi = ''
        row = rows.get(rid)
        if row is None:
            prefix = _PALETTE_PREFIX.get(hub.get('tag'))
            aliases = list(DOOR_ALIASES.get('%s_%s' % (prefix, lens), ())) \
                if prefix and lens else []
            row = rows[rid] = {
                'id': rid,
                'label': vi_name if vi else en,
                'sublabel': hub_vi if vi else hub_en,
                'group': '',
                'groups': [],
                'kind': kind,
                'target': _target(hub, lens),
                'hub': _target(hub, lens),
                'aliases': aliases,
                'names': {'en': (en, hub_en), 'vi': (vi_name, hub_vi)},
                'server': True,
            }
        # Both languages' words find the row, whichever the screens show.
        for word in (en, vi_name) + tuple(extra_names):
            if word and fold(word) != fold(row['label']) and word not in row['aliases']:
                row['aliases'].append(word)

    for tag, hub in hubs.items():
        if not visible.get(tag):
            continue
        add('%s%s' % (PREFIX, tag), hub.get('name'), hub, '', 'mission')
        for lens, tab in sorted((hub.get('tabs') or {}).items()):
            add('%s%s.%s' % (PREFIX, tag, lens), (tab or {}).get('name'), hub, lens, 'lens')
    for s in screens:
        if str(s.get('key') or '').startswith('hub_'):
            continue
        for place in s.get('places') or []:
            tag, _sep, lens = str(place).partition(':')
            hub = hubs.get(tag)
            if not hub or not lens or not visible.get(tag):
                continue
            rid = '%s%s.%s' % (PREFIX, tag, lens)
            if rid in rows:
                # The tab's row, found by the screen's own name as well.
                add(rid, (hub.get('tabs') or {}).get(lens, {}).get('name') or s.get('name'),
                    hub, lens, 'lens', extra_names=_pair(s.get('name')))
            else:
                add(rid, s.get('name'), hub, lens, 'lens')
            break
    return [r for r in rows.values() if not gate.door_denied(r)]
