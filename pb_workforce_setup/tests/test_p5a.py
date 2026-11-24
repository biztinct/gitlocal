# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WFSETUP P5a — takeover of the old doors, the trimmed Workforce menu,
Vietnamese and Indonesian wording, and the step 7 plan worked out once.

Handover §4: 1 Settings card, 2 trimmed menu, 4 translations, 5 no sentence
built from pieces around a number; plus the P4 carry-over (a): the per-week
plan sums to exactly what a direct N-week plan says, for N = 1, 4 and 12.
(3 is the suite run itself; 6 is the learning module's own checks.)
"""

import os
import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

from .test_golive import GoLiveFixture

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = os.path.dirname(HERE)
NUMBERS = ('people', 'new_shifts', 'already_planned', 'shifts', 'already_published', 'removed', 'skipped_total')
SETUP_ONLY = ['shifts', 'patterns', 'people', 'policies', 'rates', 'ceilings', 'calendars', 'holidays', 'connectors']


def _src(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as f:
        return f.read()


def _code(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'(^|\s)//[^\n]*', r'\1', text)


def _placeholders(text):
    """%s, %(name)s, %d … and {name} — what must survive a translation."""
    return sorted(re.findall(r'%\([a-z_]+\)[sd]|%[sd]|\{[a-z_]+\}', text or ''))


@tagged('post_install', '-at_install', 'wfsetup')
class TestP5aStatic(TransactionCase):

    # ------------------------------------------------------------ 1
    def test_01_settings_card_is_one_tag_card(self):
        js = _code(_src(HERE, 'static', 'src', 'js', 'takeover.js'))
        block = re.search(r'registry\.category\(SETTINGS_CATEGORIES\)\.add\("workforce_workspace",(.*?)\}, \{ sequence: 39, force: true \}\);',
                          js, flags=re.S)
        self.assertTrue(block, 'the Settings category is re-registered from this module, with force')
        cards = re.findall(r'\{ id: "([a-z_]+)", (tag|xmlid): ([A-Za-z_"\.]+)', block.group(1))
        self.assertEqual(cards, [('setup', 'tag', 'STUDIO_TAG')])
        self.assertIn('export const STUDIO_TAG = "pb_workforce_setup_studio";', js)
        self.assertIn('label: _t("Workforce setup")', block.group(1))
        # the old category's five doors are studio steps; it is removed
        self.assertIn('registry.category(SETTINGS_CATEGORIES).remove("attendance_calculation")', js)
        # the old action tag and lens open the studio
        self.assertIn('registry.category("actions").add("pb_workforce_setup", SetupStudio, { force: true });', js)
        self.assertIn('registry.category("pb_mission_lens").add("setup",', js)
        # every Settings redirect names a real step
        steps = set(re.findall(r'key: "([a-z]+)", n: \d', _src(HERE, 'static', 'src', 'js', 'setup_studio.js')))
        self.assertEqual(len(steps), 7)
        for xmlid, step in re.findall(r'"([a-z_]+\.[a-z_]+)": "([a-z]+)"', js):
            self.assertIn(step, steps, xmlid)

    # ------------------------------------------------------------ 2
    def test_02_trimmed_menu(self):
        js = _code(_src(ADDONS, 'pb_workforce_workspace', 'static', 'src', 'workspace.js'))
        body = re.search(r'const TRIMMED_GROUPS = \[(.*?)\n\];', js, flags=re.S).group(1)
        groups = re.findall(r"\{label:'([^']+)', keys:\[([^\]]*)\]\}", body)
        self.assertEqual([g[0] for g in groups], ['Overview', 'Roster', 'Timesheets', 'More'])
        keys = {g[0]: re.findall(r"'([a-z]+)'", g[1]) for g in groups}
        self.assertEqual(keys['Timesheets'], ['time', 'overtime', 'close'])
        listed = [k for v in keys.values() for k in v]
        removed = re.findall(r"'([a-z]+)'", re.search(r'const SETUP_ONLY = \[([^\]]*)\]', js).group(1))
        self.assertEqual(sorted(removed), sorted(SETUP_ONLY))
        self.assertFalse(set(removed) & set(listed), 'a removed tab is still listed')
        # "More" also collects unlisted lenses: the removed ones and "setup" are kept out
        self.assertIn("hidden=new Set(trimmed?[...SETUP_ONLY,'setup'", js)
        self.assertIn("!hidden.has(l.key)", js)
        # the trim switches on only when this module's studio is registered
        self.assertIn("registry.category('actions').contains(STUDIO_TAG)", js)
        self.assertIn("const STUDIO_TAG = 'pb_workforce_setup_studio';", js)

    # ------------------------------------------------------------ 4
    def test_04_translations(self):
        pot_ids = set()
        with open(os.path.join(HERE, 'i18n', 'pb_workforce_setup.pot'), 'rb') as f:
            for row in PoFileReader(f):
                pot_ids.add(row['src'])
        self.assertGreater(len(pot_ids), 300, 'the template carries the module sentences')
        vendor = re.compile(r'odoo', re.I)
        for lang in ('vi_VN', 'id_ID'):
            path = os.path.join(HERE, 'i18n', '%s.po' % lang)
            with open(path, 'rb') as f:
                rows = list(PoFileReader(f))           # the parse gate
            done = {}
            for row in rows:
                self.assertTrue((row['value'] or '').strip(), '%s: no translation for %r' % (lang, row['src']))
                self.assertNotRegex(row['value'], vendor, '%s: %r' % (lang, row['src']))
                self.assertEqual(_placeholders(row['src']), _placeholders(row['value']),
                                 '%s: placeholders differ for %r' % (lang, row['src']))
                done[row['src']] = row['value']
            missing = sorted(pot_ids - set(done))
            self.assertFalse(missing, '%s lacks %d sentences, e.g. %r' % (lang, len(missing), missing[:5]))
            # the three loading markers on every entry (facts I)
            entries = [e.strip() for e in _src(path).split('\n\n') if 'msgid "' in e]
            body = [e for e in entries if not re.search(r'^msgid ""\nmsgstr ""', e, flags=re.M)]
            for e in body:
                self.assertTrue(e.startswith('#. module: pb_workforce_setup'), e[:200])
                self.assertRegex(e, r'\n#: (code:addons/pb_workforce_setup/|model:)', e[:200])
                if '#: code:' in e:
                    self.assertRegex(e, r'\n#\. odoo-(python|javascript)\n', e[:200])

    # ------------------------------------------------------------ 5
    def test_05_no_sentence_built_from_pieces(self):
        """A translated piece is never glued to a number or another piece:
        word order must be free to change. Listed exceptions: the inline
        number boxes of step 4's rule sentences (a form, not a sentence
        built in code) and the panel's slider label + value pairs."""
        for name in sorted(os.listdir(os.path.join(HERE, 'static', 'src', 'js'))):
            js = _code(_src(HERE, 'static', 'src', 'js', name))
            self.assertFalse(re.search(r'_t\([^()]*(\([^()]*\))?[^()]*\)\s*\+', js), '%s: _t(...) + ...' % name)
            self.assertFalse(re.search(r'\+\s*_t\(', js), '%s: ... + _t(...)' % name)
        for name in sorted(os.listdir(os.path.join(HERE, 'models'))):
            if name.endswith('.py'):
                py = _src(HERE, 'models', name)
                self.assertFalse(re.search(r'\b_\("[^"]*"\)\s*\+', py), '%s: _(...) + ...' % name)
        xml = _src(HERE, 'static', 'src', 'xml', 'setup_studio.xml')
        # a value printed straight after a word, inside the same text run
        glued = re.findall(r'[a-z]\s+<[a-z]+[^>]*t-esc="[^"]*"\s*/>\s*[a-z]', xml)
        self.assertFalse(glued, glued[:3])


@tagged('post_install', '-at_install', 'wfsetup')
class TestP5aPlan(GoLiveFixture, TransactionCase):
    """Carry-over (a): the 12-week plan, split per week, adds up to a direct
    plan for any N, and the fingerprint moves only when something the plan
    reads moves."""

    def _sum(self, full, n):
        out = {k: 0 for k in NUMBERS}
        skipped = {}
        for w in full['weeks'][:n]:
            for k in NUMBERS:
                out[k] += w[k]
            for code, c in w['skipped'].items():
                skipped[code] = skipped.get(code, 0) + c
        out['skipped'] = skipped
        return out

    def _direct(self, n):
        plan = self.facade().live_check(n, True)['plan']
        return {k: plan[k] for k in NUMBERS + ('skipped',)}

    def test_01_week_sums_equal_direct_plans(self):
        today = self.today()
        # a mixed roster so every number is non-zero somewhere:
        # drafts made by the engine for two weeks ...
        Eng = self.env['pb.shift.pattern.engine'].with_user(self.manager).with_context(
            allowed_company_ids=[self.company.id])
        Eng.apply(self.five | self.six | self.nights, today, self.monday + timedelta(days=13))
        # ... then Friday leaves the five-day week: those drafts are no longer wanted (removed)
        self.five.slot_ids.filtered(lambda s: s.day_index == 4).unlink()
        # a published shift in week 1 and a hand-made one-off in week 3
        week1 = [d for d in (self.monday + timedelta(days=i) for i in range(7)) if d >= today]
        self.roster(self.free, week1[0], state='published')
        self.roster(self.people[0], self.monday + timedelta(days=15), shift=self.night)
        # a company day off in week 5 (skipped for the day weeks, worked by the night week)
        self.facade().add_day_off(fields.Date.to_string(self.monday + timedelta(days=30)))
        full = self.facade().live_plan()
        self.assertEqual(len(full['weeks']), 12)
        for n in (1, 4, 12):
            with self.subTest(n=n):
                self.assertEqual(self._sum(full, n), self._direct(n))
        total = self._sum(full, 12)
        for k in ('people', 'new_shifts', 'already_planned', 'already_published', 'removed', 'skipped_total'):
            self.assertGreater(total[k], 0, k)
        self.assertIn('holiday', total['skipped'])
        self.assertIn('by_hand', total['skipped'])
        # the samples are the ones the direct check shows
        self.assertEqual(full['samples']['one'], self.facade().live_check(1, True)['sample'])
        self.assertEqual(full['samples']['more'], self.facade().live_check(4, True)['sample'])

    def test_02_fingerprint_moves_only_with_the_data(self):
        f = self.facade()
        quick = f.live_check(4, False)
        self.assertTrue(quick['plan_key'])
        self.assertEqual(len(quick['all_slices']), 12)
        self.assertEqual(quick['headcount'], 41)
        self.assertEqual(quick['plan_key'], self.facade().live_plan()['key'])
        # a plain read changes nothing
        self.assertEqual(self.facade().live_check(2, False)['plan_key'], quick['plan_key'])
        # each kind of change gives a new key
        def edit_shift():
            # a test runs in ONE transaction, so `write_date` (now()) never
            # moves inside it; a real edit is its own request, later in time
            self.day.write({'end_hour': 17.0})
            self.env.flush_all()
            self.env.cr.execute("UPDATE hr_shift_template SET write_date = now() + interval '1 minute' WHERE id = %s",
                                [self.day.id])
            self.env.invalidate_all()

        changes = [
            lambda: self.env['pb.shift.pattern.member'].create({
                'pattern_id': self.five.id, 'team_id': self.five.team_ids[:1].id, 'employee_id': self.free.id}),
            edit_shift,
            lambda: self.six.slot_ids[:1].unlink(),
            lambda: self.facade().add_day_off(fields.Date.to_string(self.monday + timedelta(days=20))),
            lambda: self.roster(self.people[1], self.monday + timedelta(days=8)),
        ]
        key = quick['plan_key']
        for i, change in enumerate(changes):
            change()
            new = self.facade().live_check(4, False)['plan_key']
            self.assertNotEqual(new, key, 'change %s left the key alone' % i)
            key = new
        # the other company's changes do not touch this company's key
        self.env['hr.shift.template'].create({'name': 'Theirs', 'code': 'THR', 'start_hour': 6.0, 'end_hour': 14.0,
                                              'company_id': self.other.id})
        self.assertEqual(self.facade().live_check(4, False)['plan_key'], key)

    def test_03_rights(self):
        with self.assertRaises(AccessError):
            self.facade(self.officer).live_plan()
        quick = self.facade(self.officer).live_check(4, False)
        self.assertFalse(quick['plan_key'])

    def test_04_panel_never_defaults_to_an_administrator(self):
        admin = self.env.ref('base.user_admin')
        admin.write({'company_ids': [(4, self.company.id)]})
        boss = self.env['hr.employee'].create({'name': 'Aaron Admin', 'company_id': self.company.id,
                                               'user_id': admin.id})
        self.env['pb.shift.pattern.member'].create({
            'pattern_id': self.five.id, 'team_id': self.five.team_ids[:1].id, 'employee_id': boss.id})
        person = self.facade().person_week()
        self.assertTrue(person)
        self.assertNotEqual(person['id'], boss.id)
        # a chosen person who is archived falls back to a default, never an error
        self.people[0].active = False
        again = self.facade().person_week(self.people[0].id)
        self.assertNotEqual(again['id'], self.people[0].id)
        self.assertNotEqual(again['id'], boss.id)

    def test_05_admin_menu_flag(self):
        data = self.facade().load()
        self.assertEqual(data['menu'], {'can_switch': False, 'grouped': False})
        self.company.pb_workforce_workspace_enabled = True
        admin = self.env.ref('base.user_admin')
        admin.write({'company_ids': [(4, self.company.id)]})
        as_admin = self.env['pb.workforce.setup'].with_user(admin).with_context(allowed_company_ids=[self.company.id])
        data = as_admin.load()
        self.assertEqual(data['menu'], {'can_switch': True, 'grouped': True})
        # the switch itself: administrators only, this company only
        with self.assertRaises(AccessError):
            self.facade().set_workforce_menu(False)
        self.assertFalse(as_admin.set_workforce_menu(False))
        self.assertFalse(self.company.pb_workforce_workspace_enabled)
        self.assertTrue(as_admin.set_workforce_menu(True))
        self.assertTrue(self.company.pb_workforce_workspace_enabled)
        self.assertFalse(self.other.pb_workforce_workspace_enabled)
