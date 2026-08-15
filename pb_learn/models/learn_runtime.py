# -*- coding: utf-8 -*-
"""Everything about the learning surfaces that is IRREDUCIBLY runtime.

Content left the database in Phase 1a; this is what could not go with it,
because none of it is a fact about the content:

  * which stations the reader can actually reach — their sidebar, their groups;
  * how to recognise each screen — read off the live `pb.sidebar.item` records,
    so the Coach and the sidebar can never disagree;
  * a screen's `next_step` with its `{{live:…}}` tokens resolved;
  * the tenant's override slots, this learner's progress and confidence, who
    they are, and whether question mining is switched on.

ONE RPC. The browser fetches the static tree itself and composes the shapes the
views have always read (`static/src/content/content_loader.js`). Phase A shipped
two content-bearing calls — `learn.station.get_bundle` and
`learn.intent.coach_bundle` — and both are gone: the Journey used to wait on a
round trip that rebuilt 1,260 bilingual leaves out of the ORM on every open.
"""
from odoo import api, models


class LearnRuntime(models.AbstractModel):
    """The runtime half of the old bundles. Abstract: nothing to store."""
    _name = 'learn.runtime'
    _description = 'Learn runtime bootstrap'

    # ------------------------------------------------------------- sidebar
    @api.model
    def _visible_sidebar_item_ids(self):
        """Exactly what the real sidebar shows this user.

        Computed by CALLING get_sidebar_data rather than re-implementing its
        role rule. Re-implementing it would work today and drift the first time
        the gate changes — and the gate lives in the database, where a reader of
        this file cannot see it.
        """
        ids = set()

        def walk(items):
            for item in items:
                ids.add(item['id'])
                walk(item.get('children') or [])

        for section in self.env['pb.sidebar.item'].get_sidebar_data():
            walk(section.get('items') or [])
        return ids

    @api.model
    def _leaf(self, sidebar_key):
        if not sidebar_key:
            return None
        item = self.env.ref(sidebar_key, raise_if_not_found=False)
        return item.sudo() if item else None

    @staticmethod
    def _split(val):
        return {v.strip() for v in (val or '').split(',') if v.strip()}

    # ------------------------------------------------------- screen matchers
    @api.model
    def _raw_models(self, screen):
        """The models this screen's LEAF declares, before any tie-break."""
        item = self._leaf(screen.get('sidebar_key'))
        return self._split(item.match_models) if item else set()

    @api.model
    def _contested_models(self):
        """Models that more than one screen's leaf claims.

        `hr.integration.connector` is claimed by BOTH the Import Data leaf and
        the Integrations leaf, and BOTH are right for the sidebar: a connector
        form opened from either place should leave that leaf lit. It is not
        right for the Coach. A model two screens answer to makes the broad third
        pass pick whichever the search returned first — wrong, and wrong
        differently on different databases, which is the exact 'confidently
        wrong' failure the three-pass resolver exists to prevent.

        So a contested model is not a matcher for EITHER screen. The tags and
        xml-ids still resolve both cockpits exactly, and what is lost is only
        the bare list/form view of the contested model — where the honest answer
        really is "I do not have lessons for this screen".

        `hr.payslip.run` (Pay Runs / Approvals) and `hr.contract` (Employees /
        Contracts) are the other two, and the mechanism absorbed both without a
        line of new code.

        NOT cached any more, and it no longer needs to be. It used to walk
        every learn.screen RECORD once per screen — a quadratic sweep of the
        sidebar on every bundle build, which is why it carried an `ormcache`
        and why learn.screen had to clear the registry cache on write. The
        screen list is now a list in memory; the only database work left is one
        `env.ref` per screen, which `bootstrap` does exactly once per call.
        """
        seen, contested = set(), set()
        for screen in self.env['learn.content'].screens():
            for model in self._raw_models(screen):
                if model in seen:
                    contested.add(model)
                seen.add(model)
        return contested

    @api.model
    def _matchers(self, screen, contested):
        """How to tell that THIS screen is the one on display.

        Read from the sidebar leaf rather than hard-coded in the content. Not
        every Pay Run leaf is a client action with a tag — Pay Runs is an
        act_window matched by xml-id and by a product model — so a tag-only map
        silently fails to detect some screens, and the Coach then tells the
        learner it has no lessons for a screen it has a full lesson for.
        """
        tags = self._split(screen.get('action_tags'))
        xmlids, models_ = set(), set()
        item = self._leaf(screen.get('sidebar_key'))
        if item:
            tags |= self._split(item.action_tag) | self._split(item.match_action_tags)
            xmlids |= (self._split(item.action_xmlid)
                       | self._split(item.match_action_xmlids))
            models_ |= self._split(item.match_models)
        return sorted(tags), sorted(xmlids), sorted(models_ - contested)

    @api.model
    def _primary(self, screen):
        """The leaf's OWN action — the one that IS this screen.

        A parent leaf legitimately lists its children's actions in
        match_action_xmlids so the sidebar highlights the parent while a child
        is open. That is right for the sidebar and wrong for the Coach: opening
        Cash In Transit grounded it on AR Management, because the parent matched
        first. The primary pair breaks that tie without changing what the
        sidebar does.
        """
        item = self._leaf(screen.get('sidebar_key'))
        if not item:
            return None, None
        return (item.action_tag or None), (item.action_xmlid or None)

    @api.model
    def next_step_live(self, screen):
        """`next_step` with its live tokens resolved, in BOTH languages.

        `whatnext` is the most-asked question on any screen, and on the demo
        world the useful answer names the state the prospect's OWN June run is
        actually in — which no static sentence can. Everywhere else the authored
        sentence is shown unchanged, which is why the generator refuses a live
        token that ships without a fallback.

        Resolved per language rather than once, because a live VALUE is itself
        language-aware: a Vietnamese reader gets a Vietnamese run state, not an
        English one substituted into a Vietnamese sentence.
        """
        text = screen.get('next_step') or ''
        fallback = screen.get('live_fallback') or ''
        if not text:
            return ''
        if isinstance(text, str):
            # A raw scalar cannot carry a language; render it once.
            return self.env['learn.live'].render(text, fallback or '')
        out = {}
        for tag, lang in (('en', 'en_US'), ('vi', 'vi_VN')):
            Live = self.env['learn.live'].with_context(lang=lang)
            # A fallback authored as a raw string carries no language; use it
            # for both. Total on every shape, like learn.content.text().
            if isinstance(fallback, dict):
                fb = fallback.get(tag) or ''
            else:
                fb = fallback or ''
            out[tag] = Live.render(text.get(tag) or '', fb)
        return out

    # ------------------------------------------------------------ the call
    @api.model
    def bootstrap(self):
        """The ONE runtime call the learning surfaces make.

        Deliberately carries no prose the content plane already ships. The one
        exception is `screens_runtime[].next_step`, which is content with a live
        value substituted into it — that substitution is a database read, so it
        cannot be static, and it degrades to the authored fallback everywhere
        the live value does not resolve.
        """
        Content = self.env['learn.content']

        visible = self._visible_sidebar_item_ids()
        stations = {}
        for station in Content.stations():
            key = station.get('sidebar_key')
            if not key:
                # Teaches something other than a leaf. Visible by definition.
                stations[station['key']] = {'visible': True, 'missing': False}
                continue
            item = self.env.ref(key, raise_if_not_found=False)
            if not item:
                # The leaf's module is not installed here. Say so rather than
                # showing a station that opens nothing — an honest "not on this
                # tenant" beats a dead node the learner blames themselves for.
                stations[station['key']] = {'visible': False, 'missing': True}
            else:
                stations[station['key']] = {'visible': item.id in visible,
                                            'missing': False}

        contested = self._contested_models()
        screens = {}
        for screen in Content.screens():
            tags, xmlids, models_ = self._matchers(screen, contested)
            own_tag, own_xmlid = self._primary(screen)
            screens[screen['key']] = {
                'action_tags': tags,
                'action_xmlids': xmlids,
                'models': models_,
                'own_tag': own_tag or '',
                'own_xmlid': own_xmlid or '',
                'next_step': self.next_step_live(screen),
            }

        user = self.env.user
        return {
            'content_version': Content.version(),
            'visible_stations': stations,
            'screens_runtime': screens,
            'tokens': self.env['learn.tenant.override'].resolved_tokens(),
            'progress': self.env['learn.progress'].my_progress(),
            'confidence': self.env['learn.confidence'].my_scores(),
            'user': {
                'name': user.name,
                'lang': (user.lang or 'en_US').startswith('vi') and 'vi' or 'en',
                # Whether live capstones are offered at all. Asked of the real
                # group and the real company, exactly as the predicates do — the
                # frontend uses it to decide what to DRAW, and the server
                # re-asks on every check, so a browser that lied would get a
                # mission it could never complete rather than a live action it
                # should not have had.
                'is_demo': self.env['learn.live'].gate_open(),
            },
            # Rides along with the bundle the Coach already fetches, so a tenant
            # who never switched question mining on pays NOTHING for it. It is a
            # hint, not a control — `learn.question.create` is the gate, and a
            # stale bootstrap can only ever fail closed.
            'collect_questions': self.env['learn.question']._collect_enabled(),
        }
