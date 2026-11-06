# -*- coding: utf-8 -*-
"""What to learn next, and how many days in a row — executed, not described.

WHY THE RULES ARE PURE FUNCTIONS
--------------------------------
`learn.runtime.next_best()` is a DECISION, and a decision with five rules and a
tie-break is exactly the kind of thing that ships subtly wrong and is never
noticed: every state produces *a* suggestion, so nothing looks broken. The rule
therefore lives in `choose_next`, which takes plain lists and dicts, and the
model method is the twenty lines that fetch them. Same for the streak, whose
whole difficulty is time zones and whose whole answer is an integer.

That split is what lets the decision table below run in
`docs/tutorial_poc/author/tools/replay_tests.py` on a machine with no odoo-bin.
Everything here executes; nothing here needs a database.

WHAT IS NOT ASSERTED HERE, and where it is instead: that the method reads only
`learn.*` models is a MODEL-SCOPE contract check
(`contract.json::next-best-reads-learn-only`), because "no product model is
read" is a claim about a namespace, not about a return value, and a blocklist
of the models somebody thought of is the weakness the ledger keeps recording.
"""
import datetime
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_learn.models.learn_runtime import (
    choose_next, reading_order, streak_days,
)

MODULE = 'pb_learn'

LINE_ORDER = ['overview', 'payrun', 'people', 'insights', 'compliance', 'setup']

# A miniature map with the same SHAPE as the real one: two lines, required and
# optional stations, one lesson and one outline, plus the live capstone. Small
# on purpose — a decision table tested against the whole shipped content plane
# tests today's content, and the rules are supposed to outlive it.
STATIONS = [
    {'key': 'dashboard', 'line': 'overview', 'sequence': 1, 'required': True,
     'kind': 'lesson'},
    {'key': 'approvals', 'line': 'overview', 'sequence': 2, 'required': True,
     'kind': 'lesson'},
    {'key': 'runpayroll', 'line': 'payrun', 'sequence': 3, 'required': True,
     'kind': 'lesson'},
    {'key': 'payruns', 'line': 'payrun', 'sequence': 4, 'required': True,
     'kind': 'lesson'},
    {'key': 'retro', 'line': 'payrun', 'sequence': 5, 'required': False,
     'kind': 'outline'},
]
MISSIONS = [
    {'key': 'm1', 'kind': 'full', 'line': 'payrun'},
    {'key': 'mL1', 'kind': 'live', 'line': 'payrun'},
]


def _p(**states):
    """A progress payload: `_p(dashboard='done')`."""
    return {k: {'state': v} for k, v in states.items()}


def _read(rel):
    base = get_module_path(MODULE)
    if not base:
        return None
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestNextBest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.runtime_src = _read('models/learn_runtime.py')
        cls.journey_src = _read('static/src/journey/journey.js')

    # -- the decision table, one row per rule ------------------------------
    def test_01_an_empty_map_offers_the_first_required_station(self):
        """THE EMPTY-PROGRESS CASE, which is every new learner and is the one
        state a rule written from the middle outwards gets wrong."""
        key, kind, line, reason = choose_next(STATIONS, MISSIONS, {}, LINE_ORDER)
        self.assertEqual((key, kind, line, reason),
                         ('dashboard', 'station', 'overview', 'nbRequired'))

    def test_02_something_half_done_wins_over_everything(self):
        """Rule 1. Nothing can be more useful than the thing already started —
        including a section that is one lesson from finished."""
        progress = _p(dashboard='done', approvals='done', payruns='in_progress')
        key, _k, _l, reason = choose_next(STATIONS, MISSIONS, progress, LINE_ORDER)
        self.assertEqual((key, reason), ('payruns', 'nbResume'))

    def test_03_otherwise_finish_the_section_closest_to_done(self):
        """Rule 2, and the thing it counts. Payrun's REQUIRED work is complete
        (the outstanding `retro` is optional), so Payrun is finished as far as
        this rule is concerned and Overview — one required station short — is
        what gets offered. Counting the optional station too was the first
        draft, and it made the capstone unreachable: see the note on
        `choose_next`."""
        progress = _p(dashboard='done', runpayroll='done', payruns='done')
        key, _k, line, reason = choose_next(STATIONS, MISSIONS, progress, LINE_ORDER)
        self.assertEqual((key, line, reason), ('approvals', 'overview', 'nbFinishLine'))

    def test_03c_an_optional_station_does_not_hold_a_section_open(self):
        """The same rule from the other side, because this is the one that
        decides whether rule 4 is ever reached. Payrun has one required
        station done and one to go, so it IS partly done; `retro` is not what
        makes it so, and is not what is offered."""
        progress = _p(runpayroll='done')
        key, _k, line, reason = choose_next(STATIONS, MISSIONS, progress, LINE_ORDER)
        self.assertEqual((key, line, reason), ('payruns', 'payrun', 'nbFinishLine'))

    def test_03b_a_tie_between_sections_is_broken_by_reading_order(self):
        """A COIN TOSS IS NOT A DECISION. Two sections at 1/2 and 1/3… made
        equal: both at 50%. Overview is first in LINE_ORDER, so Overview wins,
        and it wins the same way on every reload and for every learner in the
        same state."""
        stations = [s for s in STATIONS if s['key'] != 'retro']
        progress = _p(dashboard='done', runpayroll='done')
        key, _k, line, _r = choose_next(stations, MISSIONS, progress, LINE_ORDER)
        self.assertEqual((key, line), ('approvals', 'overview'))
        # …and the tie-break is the ORDER, not the alphabet: reverse the
        # reading order and the other section wins.
        key, _k, line, _r = choose_next(
            stations, MISSIONS, progress, list(reversed(LINE_ORDER)))
        self.assertEqual((key, line), ('payruns', 'payrun'))

    def test_04_then_the_next_required_station_in_reading_order(self):
        """Rule 3, reached when no section is partly done: here Overview is
        complete and Payrun is untouched, so there is nothing to 'finish'."""
        progress = _p(dashboard='done', approvals='done')
        key, _k, _l, reason = choose_next(STATIONS, MISSIONS, progress, LINE_ORDER)
        self.assertEqual((key, reason), ('runpayroll', 'nbRequired'))

    def test_05_the_live_capstone_only_where_it_can_be_done(self):
        """Rule 4, and the gate is the whole point: everywhere but the demo
        world the capstone is a mission the learner could never finish, so
        offering it would be worse than offering nothing."""
        progress = _p(dashboard='done', approvals='done', runpayroll='done',
                      payruns='done')
        key, kind, _l, reason = choose_next(
            STATIONS, MISSIONS, progress, LINE_ORDER, gate_open=True)
        self.assertEqual((key, kind, reason), ('mL1', 'mission', 'nbCapstone'))
        # Same state, gate shut: the optional station instead, never the
        # capstone.
        key, kind, _l, reason = choose_next(
            STATIONS, MISSIONS, progress, LINE_ORDER, gate_open=False)
        self.assertEqual((key, kind, reason), ('retro', 'station', 'nbOptional'))

    def test_05b_a_finished_capstone_is_not_offered_again(self):
        progress = _p(dashboard='done', approvals='done', runpayroll='done',
                      payruns='done')
        progress['mission:mL1'] = {'state': 'done'}
        key, kind, _l, reason = choose_next(
            STATIONS, MISSIONS, progress, LINE_ORDER, gate_open=True)
        self.assertEqual((key, kind, reason), ('retro', 'station', 'nbOptional'))

    def test_06_everything_done_is_an_answer_not_a_random_card(self):
        """Rule 6. Somebody who has finished should be told so. Handing them a
        lesson they have already done would be the surface admitting it has
        nothing to say while pretending otherwise."""
        progress = _p(**{s['key']: 'done' for s in STATIONS})
        progress['mission:mL1'] = {'state': 'done'}
        key, kind, line, reason = choose_next(
            STATIONS, MISSIONS, progress, LINE_ORDER, gate_open=True)
        self.assertEqual((key, kind, line, reason), (None, 'none', None, 'nbAllDone'))

    def test_07_a_station_this_tenant_cannot_open_is_never_suggested(self):
        """A suggestion nobody can act on is worse than no suggestion. The
        skipped set is the stations whose sidebar leaf's module is not
        installed here — the same probe `bootstrap` uses for `missing`."""
        key, _k, _l, _r = choose_next(STATIONS, MISSIONS, {}, LINE_ORDER,
                                      skip={'dashboard'})
        self.assertEqual(key, 'approvals')
        # …and a skipped station does not count against its own section
        # either: with the only other Overview station done, Overview is
        # COMPLETE, not half-finished.
        progress = _p(approvals='done')
        key, _k, line, reason = choose_next(STATIONS, MISSIONS, progress,
                                            LINE_ORDER, skip={'dashboard'})
        self.assertEqual((key, line, reason), ('runpayroll', 'payrun', 'nbRequired'))

    def test_08_a_line_nobody_ordered_is_still_reachable(self):
        """The same rule journey.js applies to drawing: a section missing from
        the reading order sorts last rather than vanishing. A learner must
        never lose access to content because somebody forgot a second file."""
        stations = STATIONS + [{'key': 'newthing', 'line': 'brandnew',
                                'sequence': 9, 'required': True, 'kind': 'outline'}]
        ordered = [s['key'] for s in reading_order(stations, LINE_ORDER)]
        self.assertEqual(ordered[-1], 'newthing')
        progress = _p(**{s['key']: 'done' for s in STATIONS})
        key, _k, _l, reason = choose_next(stations, MISSIONS, progress, LINE_ORDER)
        self.assertEqual((key, reason), ('newthing', 'nbRequired'))

    def test_09_every_rule_has_an_authored_sentence_in_both_languages(self):
        """A reason key with no chrome string renders as its own key, which is
        the failure this module has shipped once already (a Journey line with
        no heading). Read off the CONTENT PLANE, so a rule added without its
        sentence fails here rather than on a learner's screen."""
        import json
        base = get_module_path(MODULE)
        with open(os.path.join(base, 'static/content/learn_content.json'),
                  encoding='utf-8') as fh:
            chrome = json.load(fh)['chrome']
        reasons = set(re.findall(r"'(nb[A-Z][A-Za-z]+)'", self.runtime_src))
        self.assertGreaterEqual(len(reasons), 6,
                                "the scan found no reason keys — it is broken")
        for key in sorted(reasons):
            self.assertIn(key, chrome, "no authored sentence for %s" % key)
            for lang in ('en', 'vi'):
                self.assertTrue((chrome[key] or {}).get(lang),
                                "%s has no %s sentence" % (key, lang))

    # -- the streak --------------------------------------------------------
    def test_10_a_streak_is_consecutive_days_ending_today(self):
        today = datetime.date(2026, 8, 16)
        days = {today, today - datetime.timedelta(days=1),
                today - datetime.timedelta(days=2)}
        self.assertEqual(streak_days(days, today), 3)

    def test_10b_yesterday_still_counts_because_today_is_not_over(self):
        """Ending the streak at midnight punishes the hour, not the habit."""
        today = datetime.date(2026, 8, 16)
        days = {today - datetime.timedelta(days=1),
                today - datetime.timedelta(days=2)}
        self.assertEqual(streak_days(days, today), 2)

    def test_10c_a_gap_ends_it_quietly(self):
        today = datetime.date(2026, 8, 16)
        days = {today - datetime.timedelta(days=2),
                today - datetime.timedelta(days=3)}
        self.assertEqual(streak_days(days, today), 0)
        self.assertEqual(streak_days(set(), today), 0)

    def test_10d_a_day_with_five_events_is_still_one_day(self):
        today = datetime.date(2026, 8, 16)
        self.assertEqual(streak_days([today, today, today], today), 1)

    def test_11_the_time_zone_is_the_learners_and_the_edge_is_real(self):
        """THE CASE THIS EXISTS FOR. A payroll officer in Ho Chi Minh City
        (UTC+7) studying at 21:00 is already on the NEXT day in UTC. Three
        evenings in a row is a streak of three for them and — counted in UTC —
        three days that each land on the following morning, which still reads
        as three consecutive days here. The one that breaks is a UTC-midnight
        boundary treated as the learner's: 2026-08-16 23:30 UTC is
        2026-08-17 06:30 in Ho Chi Minh City, and counting it as the 16th
        would leave a hole on the 17th.

        Asserted over the CONVERSION, with the same arithmetic the model does,
        because that is where the bug would be.
        """
        # `zoneinfo`, not pytz, and only in the TEST: the model uses pytz
        # because that is what Odoo ships and what `res.users.tz` is read with
        # everywhere else in the product, and the offline harness has no pytz
        # on this machine. Vietnam has no daylight saving, so the two agree to
        # the second here; what is being asserted is the ARITHMETIC.
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('Asia/Ho_Chi_Minh')
        utc_stamps = [
            datetime.datetime(2026, 8, 14, 23, 30),   # → 15 Aug, local
            datetime.datetime(2026, 8, 15, 23, 30),   # → 16 Aug, local
            datetime.datetime(2026, 8, 16, 23, 30),   # → 17 Aug, local
        ]
        days = {s.replace(tzinfo=datetime.timezone.utc).astimezone(tz).date()
                for s in utc_stamps}
        self.assertEqual(sorted(days), [datetime.date(2026, 8, 15),
                                        datetime.date(2026, 8, 16),
                                        datetime.date(2026, 8, 17)])
        self.assertEqual(streak_days(days, datetime.date(2026, 8, 17)), 3)
        # Counted in UTC instead, the same three evenings are the 14th, 15th
        # and 16th — a streak that ends the day before the learner's does.
        utc_days = {s.date() for s in utc_stamps}
        self.assertEqual(streak_days(utc_days, datetime.date(2026, 8, 17)), 3)
        self.assertEqual(streak_days(utc_days, datetime.date(2026, 8, 18)), 0)

    def test_12_the_display_cap_lives_on_the_server(self):
        """"7+" is a decision about what a long streak means, and it is made
        in one place so a second surface cannot show 43."""
        self.assertIn("'%d+' % STREAK_CAP if count > STREAK_CAP", self.runtime_src)
        self.assertIn('STREAK_CAP = 7', self.runtime_src)

    # -- the privacy properties, at source ---------------------------------
    def test_13_neither_answer_can_see_another_learner(self):
        """NO CROSS-USER DATA ANYWHERE. Both methods read own rows only, and
        the streak's own domain says so literally. A comparison, a ranking or
        a company-wide count would need a domain without `env.uid` in it —
        which is what this refuses."""
        body = self.runtime_src.split('def streak(')[1].split('\n    @api.model')[0]
        self.assertIn("('user_id', '=', self.env.uid)", body,
                      "the streak reads events that are not this learner's")
        nb = self.runtime_src.split('def next_best(')[1].split('\n    @api.model')[0]
        self.assertIn('my_progress()', nb,
                      "next_best no longer reads progress through the "
                      "own-rows accessor")
        for token in ('search_count', 'read_group', '.sudo('):
            self.assertNotIn(token, nb,
                             "next_best gained a %s — it must stay a read of "
                             "this learner's own rows" % token)

    def test_14_both_features_are_off_when_their_flag_is_absent(self):
        """Every flag in this program is off when absent, and these two are
        checked BEFORE any row is read — a switched-off feature must cost
        nothing, not merely show nothing."""
        for method, flag in (('next_best', 'NEXT_BEST_FLAG'),
                             ('streak', 'SKILL_TREE_FLAG')):
            body = self.runtime_src.split('def %s(' % method)[1]
            body = body.split('\n    @api.model')[0]
            guard = body.index('_flag_on(self.env, %s)' % flag)
            first_read = min(
                (body.index(t) for t in ("self.env['learn.progress']",
                                         "self.env['learn.event']",
                                         "self.env['learn.content']")
                 if t in body), default=len(body))
            self.assertLess(guard, first_read,
                            "%s reads rows before checking its flag" % method)

    def test_15_the_map_and_the_server_read_one_reading_order(self):
        """The constant moved into the authoring source in Phase 6 because the
        server needed it too. journey.js keeps a literal as the fallback for a
        stale bundle — and a fallback that has drifted from the real order is
        worse than none, so the two are pinned together here and in
        `contract.json::journey-line-order-is-authored-once`."""
        import json
        base = get_module_path(MODULE)
        with open(os.path.join(base, 'static/content/learn_content.json'),
                  encoding='utf-8') as fh:
            shipped = json.load(fh).get('line_order')
        self.assertTrue(shipped, "the content plane ships no reading order")
        found = re.search(r'const LINE_ORDER = \[(.*?)\];', self.journey_src)
        self.assertTrue(found, "journey.js no longer declares a fallback order")
        literal = [k.strip().strip('"\'') for k in found.group(1).split(',')]
        self.assertEqual(literal, shipped,
                         "the page's fallback order and the content plane's "
                         "order disagree")
