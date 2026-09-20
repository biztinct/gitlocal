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

LEARNOS PHASE 6 ADDS TWO ANSWERS, AND BOTH ARE COMPUTED HERE FOR THE SAME
REASON: they are about ONE learner and they must not leave the server.

  * `next_best()` — "what should I learn next". A decision over this user's own
    progress rows and the content plane. No model is asked; no prompt is built;
    nothing about it is sent anywhere. The reason sentence is AUTHORED, one per
    rule, in both languages, so the learner is told why this one.
  * `streak()` — consecutive days with at least one learning event, counted in
    the learner's own time zone from their own rows.

NO CROSS-USER DATA, ANYWHERE IN EITHER. Neither reads another person's rows,
neither compares, and there is no ranking, no league and no notification. A
broken streak resets quietly and nothing says a word about it.

Both are behind their own tenant flags and both are OFF when the flag is
absent, which is what an untouched database has.
"""
from datetime import timedelta

import pytz

from odoo import api, fields, models

from .learn_progress import MISSION_PREFIX
from .learn_question import _flag_on

# Tenant flags. Absent means off — see `_flag_on` (learn_question.py), which is
# the same reader the composer and question mining use.
NEXT_BEST_FLAG = 'pb_learn.next_best_enabled'
SKILL_TREE_FLAG = 'pb_learn.skill_tree_enabled'

# How far back the streak counter looks. A streak longer than this is still
# reported as "at least this many", which is well past the point where the
# number stops being information — the display caps at 7 anyway.
STREAK_WINDOW_DAYS = 60
STREAK_CAP = 7


# ---------------------------------------------------------------------------
# THE TWO DECISIONS, AS PURE FUNCTIONS
#
# Module level, taking plain data, for the reason the prompt builders in PayAI
# are: there is no odoo-bin on the authoring machine, and a rule nobody has
# ever executed is a rule nobody has checked. `tests/test_nextbest.py` runs
# every row of the decision table and every time-zone edge of the streak
# against these, offline, with no database anywhere near them.
# ---------------------------------------------------------------------------
def reading_order(stations, line_order):
    """Stations in the order the map draws them.

    A line missing from `line_order` sorts AFTER the ones in it rather than
    disappearing — the same rule journey.js applies, and for the same reason:
    a section must never be able to vanish because somebody forgot a file.
    """
    order = {key: i for i, key in enumerate(line_order or [])}
    return sorted(
        stations,
        key=lambda s: (order.get(s.get('line'), len(order)),
                       s.get('sequence') or 0, s.get('key') or ''))


def choose_next(stations, missions, progress, line_order,
                gate_open=False, skip=()):
    """THE DECISION TABLE. Returns (key, kind, line, reason_key).

    Five rules, tried in order, and the order is the teaching:

      1. RESUME     something is half-done. Nothing else can be more useful
                    than the thing the learner already started.
      2. FINISH THE LINE   the section closest to having its REQUIRED work
                    done, so the map gains a finished row rather than five
                    half-finished ones.
      3. REQUIRED   the next station the map asks for, in reading order.
      4. CAPSTONE   the live mission — offered ONLY when the demo-world gate is
                    open, because everywhere else it is a mission the learner
                    could never complete.
      5. OPTIONAL   the required work is done; here is something useful.

    …and then `none`, which is a real answer: somebody who has finished
    everything should be told so, not handed a card at random.

    RULES 2 AND 3 COUNT REQUIRED STATIONS ONLY, and that is a decision worth
    stating rather than a detail. Counting optional ones too was the first
    draft and it made rule 4 unreachable in practice: with six sections and an
    optional station in most of them, SOME line is always partly done, so
    "finish the line" fired forever and the live capstone — the one piece of
    real work in the whole programme — was never offered until every last
    outline had been read. A section is finished when it has taught what it
    says it must; the extras are rule 5's job.

    TIES ARE BROKEN BY READING ORDER, always, so two learners in the same state
    get the same suggestion and a reload does not shuffle it.

    `skip` is the set of stations this tenant cannot open at all (their leaf's
    module is not installed). A suggestion nobody can act on is worse than no
    suggestion.
    """
    skip = set(skip or ())
    ordered = [s for s in reading_order(stations, line_order)
               if s.get('key') not in skip]

    def state(key):
        return (progress.get(key) or {}).get('state') or 'not_started'

    # 1. resume
    for station in ordered:
        if state(station['key']) == 'in_progress':
            return station['key'], 'station', station.get('line'), 'nbResume'

    # 2. finish the line the learner is closest to finishing
    lines = {}
    for station in ordered:
        if station.get('required'):
            lines.setdefault(station.get('line'), []).append(station)
    best_line, best_ratio = None, 0.0
    for line, bucket in lines.items():
        done = sum(1 for s in bucket if state(s['key']) == 'done')
        if not done or done == len(bucket):
            continue
        ratio = done / float(len(bucket))
        # STRICTLY GREATER, so a tie keeps the FIRST line in reading order —
        # `ordered` built the buckets, and Python keeps insertion order. Two
        # learners in the same state get the same suggestion, and so does the
        # same learner after a reload.
        if ratio > best_ratio:
            best_line, best_ratio = line, ratio
    if best_line is not None:
        for station in lines[best_line]:
            if state(station['key']) != 'done':
                return station['key'], 'station', best_line, 'nbFinishLine'

    # 3. the next required station
    for station in ordered:
        if station.get('required') and state(station['key']) != 'done':
            return station['key'], 'station', station.get('line'), 'nbRequired'

    # 4. the live capstone, and only where it can actually be done
    if gate_open:
        for mission in missions or []:
            if mission.get('kind') != 'live':
                continue
            if state(MISSION_PREFIX + mission['key']) != 'done':
                return mission['key'], 'mission', mission.get('line'), 'nbCapstone'

    # 5. anything left
    for station in ordered:
        if state(station['key']) != 'done':
            return station['key'], 'station', station.get('line'), 'nbOptional'

    return None, 'none', None, 'nbAllDone'


def streak_days(days, today):
    """Consecutive days ending today — or ending yesterday, because the day is
    not over yet.

    `days` is a set of `date`s in the LEARNER's time zone; `today` is their
    today. Somebody who learned yesterday and has not opened the app yet this
    morning still has their streak: ending it at midnight would punish the
    hour, not the habit. Somebody who last learned two days ago has none, and
    nothing anywhere says so — a broken streak just is not there.
    """
    days = set(days or ())
    if not days:
        return 0
    cursor = today if today in days else today - timedelta(days=1)
    if cursor not in days:
        return 0
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


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

    # --------------------------------------------------------- reachability
    #
    # SCREEN IDENTITY and RAIL REACHABILITY are two different questions about
    # the same leaf, and until IA Cycle 5 one record answered both.
    #
    #   identity      "which action IS this screen"   → _primary / _matchers
    #   reachability  "how does a reader GET there"   → this block
    #
    # They agreed for as long as every screen had its own rail item. The
    # cutover retired thirty-four of them into eight hubs, and the two answers
    # came apart: `_leaf` still resolves a retired record (env.ref is
    # active-agnostic), so identity kept working perfectly, while
    # `_visible_sidebar_item_ids` — which searches active=True — stopped
    # containing any of them. Every station went dark and `_capability`
    # answered `no_access` for every screen (W108).
    #
    # The obvious repair, re-pointing each station's `sidebar_key` at its hub,
    # is the wrong one and W108 says why: seven pay-run screens sharing one Pay
    # Run leaf would make `_primary` ground all seven on whichever resolved
    # first — a confidently wrong answer traded for a wrong label. So the
    # sidebar_key stays where it is, and reachability gets its own resolver.
    #
    # That resolver asks the SAME question the rail itself asks. `pb_sidebar.js`
    # `_buildIndex` folds every LIVE item's four match dimensions into three
    # flat maps and `_isClaimed` probes them to decide whether the rail belongs
    # on a surface at all (W109). This is that index, server-side, built from
    # the same `get_sidebar_data()` payload `_visible_sidebar_item_ids` already
    # fetches — so "the rail is here", "this item is lit" and "you can reach
    # this station" can never disagree.

    @api.model
    def _reach_index(self):
        """{'tags': {tag: reach}, 'xmlids': {...}, 'models': {...}}.

        `reach` is a plain dict — the payload crosses JSON-RPC, and a recordset
        would not.
        """
        idx = {'tags': {}, 'xmlids': {}, 'models': {}}

        def add(item, section, parent):
            reach = {
                'item_id': item['id'],
                'item': item.get('name') or '',
                'section': section.get('name') or '',
                'parent': parent,
            }
            if item.get('action_tag'):
                idx['tags'].setdefault(item['action_tag'], reach)
            if item.get('action_xmlid'):
                idx['xmlids'].setdefault(item['action_xmlid'], reach)
            for tag in item.get('match_action_tags') or []:
                idx['tags'].setdefault(tag, reach)
            for xmlid in item.get('match_action_xmlids') or []:
                idx['xmlids'].setdefault(xmlid, reach)
            for model in item.get('match_models') or []:
                idx['models'].setdefault(model, reach)

        # setdefault, not assignment: the rail's own index is last-writer-wins
        # (W71) and a double claim there is a bug the sidebar tests forbid.
        # Here first-writer-wins is the safer half of the same coin — a reader
        # is sent to the item that declared the surface first rather than to
        # whichever happened to be indexed last.
        for section in self.env['pb.sidebar.item'].get_sidebar_data():
            for item in section.get('items') or []:
                add(item, section, '')
                for child in item.get('children') or []:
                    add(child, section, item.get('name') or '')
        return idx

    @api.model
    def _reaching(self, item, index=None):
        """The LIVE rail item a reader opens to get to this leaf's screen.

        `item` may perfectly well be a retired record — that is the whole
        point. Returns the reach dict, or None when nothing on the rail claims
        this surface (a genuinely unreachable screen, which the map should
        still say so about).

        Probe order is TAG FIRST, deliberately, and it differs from
        `_resolveActive`'s xmlid-first order for a reason worth stating: four of
        the retired leaves (Full & Final, Proration, Retro, Government Reports)
        declare an `action_xmlid` that no live item claims, while every one of
        the thirty-four is claimed by tag. Resolving by xmlid first would answer
        None for those four and look like "these really are unreachable".
        """
        if not item:
            return None
        idx = index if index is not None else self._reach_index()
        item = item.sudo()

        for tag in [item.action_tag] + sorted(self._split(item.match_action_tags)):
            if tag and tag in idx['tags']:
                return idx['tags'][tag]
        for xmlid in [item.action_xmlid] + sorted(self._split(item.match_action_xmlids)):
            if xmlid and xmlid in idx['xmlids']:
                return idx['xmlids'][xmlid]
        for model in sorted(self._split(item.match_models)):
            if model in idx['models']:
                return idx['models'][model]
        return None

    @api.model
    def _reach_path(self, reach):
        """The rail path a reader follows, as one string: "Pay Run"."""
        if not reach:
            return ''
        parts = [p for p in (reach.get('parent'), reach.get('item')) if p]
        return ' → '.join(parts)

    @api.model
    def _station_reach(self, sidebar_key, visible_ids=None, index=None):
        """(visible, missing, reach) for one station's leaf.

        The single place the three verdicts are decided, so `bootstrap` and
        `learn.intent._capability` cannot answer differently about one screen —
        which is exactly what happened before: the map said "not in your menu"
        and the Coach said `no_access`, from two separate readings of the same
        set.
        """
        if not sidebar_key:
            # Teaches something other than a leaf. Visible by definition.
            return True, False, None
        item = self.env.ref(sidebar_key, raise_if_not_found=False)
        if not item:
            # The leaf's module is not installed here. Say so rather than
            # showing a station that opens nothing — an honest "not on this
            # tenant" beats a dead node the learner blames themselves for.
            return False, True, None
        ids = visible_ids if visible_ids is not None else self._visible_sidebar_item_ids()
        if item.id in ids:
            return True, False, None
        reach = self._reaching(item, index=index)
        # Reachable through a hub is REACHABLE. The station is open, and the
        # map names the door instead of telling a payroll manager they cannot
        # see Payslips on a database where they can.
        return bool(reach), False, reach

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

    # -------------------------------------------- what to learn next (P6)
    @api.model
    def next_best(self, skip=None):
        """One suggestion, with the reason it was chosen, in both languages.

        EVERY MODEL THIS METHOD TOUCHES IS `learn.*`.
        `contract.json::next-best-reads-learn-only` parses this method and the
        helpers it calls as `self.x(...)` — one level — and refuses any
        `self.env['x.y']` outside the namespace. **That is a TRIPWIRE, not
        containment**, and the difference is worth stating where somebody
        might rely on it: a read two helpers down, behind a variable, or on
        another model's method is outside what the scan can see. What makes
        the promise true is this method being short enough to read; what the
        check does is stop it drifting by accident.
        The one delegation that leaves the namespace by design is
        `learn.live.gate_open()`, which asks the real group and the real
        company — the same question the capstone's own predicates ask, and the
        reason the capstone is not offered to somebody who could never finish
        it.

        Own rows only: `learn.progress.my_progress()` filters on `env.uid` and
        the record rule filters again underneath it. No other learner's state
        is read, compared or counted anywhere in this file.

        Returns `{}` when the flag is off, so the surfaces draw nothing rather
        than a strip explaining that a feature is unavailable.
        """
        if not _flag_on(self.env, NEXT_BEST_FLAG):
            return {}
        Content = self.env['learn.content']
        progress = self.env['learn.progress'].my_progress()
        gate_open = self.env['learn.live'].gate_open()
        key, kind, line, reason_key = choose_next(
            Content.stations(), Content.missions(), progress,
            Content.line_order(), gate_open, skip or self._unreachable_keys())
        return {
            'key': key or '',
            'kind': kind,
            'line': line or '',
            'reason_key': reason_key,
            # The sentence is AUTHORED, one per rule, and shipped in both
            # languages like every other string a learner reads. Both are sent
            # because the Journey's own toggle decides which one is shown, and
            # it can change without another round trip.
            'reason': {
                'en': Content.chrome_text(reason_key, 'en_US'),
                'vi': Content.chrome_text(reason_key, 'vi_VN'),
            },
        }

    @api.model
    def _unreachable_keys(self):
        """Stations whose sidebar leaf's module is not installed here.

        A suggestion the learner cannot act on is worse than none. Reuses the
        same `env.ref` probe `bootstrap` uses for `missing`.
        """
        out = set()
        for station in self.env['learn.content'].stations():
            key = station.get('sidebar_key')
            if key and not self.env.ref(key, raise_if_not_found=False):
                out.add(station['key'])
        return out

    # ------------------------------------------------------- streaks (P6)
    @api.model
    def streak(self):
        """`{'days': n, 'display': '7+'|str(n)}` for THIS learner.

        COMPUTED IN THE LEARNER'S OWN TIME ZONE, and the choice matters: a
        payroll officer in Ho Chi Minh City who studies at nine in the evening
        is on the next UTC day, so a UTC count would break their streak every
        single night. `occurred_at` is stored UTC-naive, as everything in Odoo
        is; `res.users.tz` is what turns it into a day. A user with no tz set
        falls back to UTC, which is the same answer Odoo gives everywhere else.

        DERIVED, NEVER STORED. There is no streak column, no "best streak",
        nothing to lose and nothing to be told off about.
        """
        if not _flag_on(self.env, SKILL_TREE_FLAG):
            return {}
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        since = fields.Datetime.subtract(fields.Datetime.now(),
                                         days=STREAK_WINDOW_DAYS)
        rows = self.env['learn.event'].search_read(
            [('user_id', '=', self.env.uid), ('occurred_at', '>=', since)],
            ['occurred_at'])
        days = {pytz.utc.localize(r['occurred_at']).astimezone(tz).date()
                for r in rows if r.get('occurred_at')}
        today = pytz.utc.localize(fields.Datetime.now()).astimezone(tz).date()
        count = streak_days(days, today)
        return {
            'days': count,
            # The cap lives here rather than in the page, so the one place that
            # decides what a long streak looks like is also the place a test
            # can read.
            'display': '%d+' % STREAK_CAP if count > STREAK_CAP else str(count),
        }

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
        index = self._reach_index()
        stations = {}
        for station in Content.stations():
            is_visible, missing, reach = self._station_reach(
                station.get('sidebar_key'), visible_ids=visible, index=index)
            stations[station['key']] = {
                'visible': is_visible,
                'missing': missing,
                # Empty when the leaf is on the rail in its own right — there is
                # no path worth naming for a screen the reader can already see.
                'reach': self._reach_path(reach),
            }

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
            # LEARNOS Phase 3 — which first-run greeting this database gets.
            # NOT `user.is_demo`: that is a statement about this SESSION (the
            # group AND the company), and the greeting is a statement about the
            # DATABASE. An administrator on the demo world is not a new tenant.
            'demo_world': self.env['learn.live'].world_is_demo(),
            # Rides along with the bundle the Coach already fetches, so a tenant
            # who never switched question mining on pays NOTHING for it. It is a
            # hint, not a control — `learn.question.create` is the gate, and a
            # stale bootstrap can only ever fail closed.
            'collect_questions': self.env['learn.question']._collect_enabled(),
            # LEARNOS Phase 6. Both ride along with the call the Journey and
            # the Coach already make, so a tenant with the flags off pays for
            # neither: `next_best` and `streak` return `{}` before touching a
            # row, and the surfaces draw nothing at all. No extra round trip
            # anywhere, which is also why the Coach's "not sure" state can
            # offer the same suggestion the map does without asking again.
            'next_best': self.next_best(),
            'streak': self.streak(),
            'line_order': Content.line_order(),
            'skill_tree': _flag_on(self.env, SKILL_TREE_FLAG),
        }
