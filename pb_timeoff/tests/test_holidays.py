# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""RIZE W2 D1 — the public-holiday calendar, and the seams around it.

Half of what this phase promises cannot be seen by a behaviour test: that the
Mission Control registry category is spelt the same way in three files, that
the ⌘K rows sit in the block the wave plan gave them, and that no screen says
"Odoo". Only reading the source can tell those apart from silence, so half of
this file is a set of greps with a paragraph each.

Every source gate reads `_code(src)` — the file with its comments stripped —
because a word-shaped gate fails on the documentation that explains the rule
(R118: the obvious white-label test failed on the very sentence that stops the
next contributor reintroducing the bug).
"""

import os
import re
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _src(module, *parts):
    return _read(os.path.join(get_module_path(module), *parts))


def _code(src):
    """The file with its COMMENTS removed — both `//` and `/* … */`."""
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
        elif src.startswith('//', i):
            j = src.find('\n', i)
            i = n if j < 0 else j
        elif src[i] in '"\'`':
            quote = src[i]
            out.append(quote)
            i += 1
            while i < n and src[i] != quote:
                if src[i] == '\\':
                    out.append(src[i:i + 2])
                    i += 2
                    continue
                out.append(src[i])
                i += 1
            out.append(quote)
            i += 1
        else:
            out.append(src[i])
            i += 1
    return ''.join(out)


@tagged('post_install', '-at_install')
class TestHolidaysFacade(TransactionCase):
    """T2 — the facade answers, refuses and teaches."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Hol = cls.env['pb.holidays']
        # A DEDICATED company, so the assertions are about this fixture and
        # not about whatever the live demo database happens to hold (R221: a
        # test that asserts over a whole table only passes on an empty one).
        cls.company = cls.env['res.company'].create({'name': 'D1 Holidays Co'})
        cls.calendar = cls.company.resource_calendar_id
        cls.officer = cls.env.ref('base.user_admin')
        cls.officer.write({'company_ids': [(4, cls.company.id)]})
        cls.HolCo = cls.Hol.with_user(cls.officer).with_context(
            allowed_company_ids=[cls.company.id]).with_company(cls.company)
        # THE SERVER'S today, never the laptop's (R36).
        cls.today = cls.env['pb.holidays']._today()

    def _mine(self, data):
        """The fixture company's own column — it is first, because the facade
        puts the reader's own company first."""
        for column in data['companies']:
            if column['id'] == self.company.id:
                return column
        self.fail('the reader\'s own company is missing from the board')

    def test_a_company_with_a_calendar_can_be_given_a_day(self):
        self.assertTrue(self.calendar,
                        'the fixture company needs working hours')
        self.HolCo.add(self.company.id, 'DEMO Harvest festival',
                       (self.today + timedelta(days=30)).isoformat())
        column = self._mine(self.HolCo.year(self.today.year))
        names = [row['name'] for row in column['rows']]
        self.assertIn('DEMO Harvest festival', names)

    def test_the_same_day_twice_is_refused_by_name(self):
        day = (self.today + timedelta(days=31)).isoformat()
        self.HolCo.add(self.company.id, 'DEMO Founders day', day)
        with self.assertRaises(UserError) as caught:
            self.HolCo.add(self.company.id, 'DEMO Founders day', day)
        self.assertIn('DEMO Founders day', str(caught.exception),
                      'the refusal has to name the day it is about')

    def test_a_run_of_days_counts_as_a_run_of_days(self):
        start = self.today + timedelta(days=40)
        self.HolCo.add(self.company.id, 'DEMO Long weekend',
                       start.isoformat(), (start + timedelta(days=2)).isoformat())
        column = self._mine(self.HolCo.year(self.today.year))
        row = [r for r in column['rows'] if r['name'] == 'DEMO Long weekend'][0]
        self.assertEqual(row['days'], 3)
        self.assertEqual(row['date'], start.isoformat())

    def test_a_bad_line_is_refused_BY_LINE_and_nothing_is_written(self):
        """Half a year on the calendar and half a year in an error message is
        the worst of both: the reader cannot tell which half landed, and
        pasting it again would double the half that did."""
        before = len(self._mine(self.HolCo.year(self.today.year))['rows'])
        with self.assertRaises(UserError) as caught:
            self.HolCo.add_many(self.company.id,
                                'DEMO Good day | %s\nDEMO Bad day | the 4th'
                                % (self.today + timedelta(days=50)).isoformat())
        message = str(caught.exception)
        self.assertIn('Line 2', message, 'the refusal must name the line')
        after = len(self._mine(self.HolCo.year(self.today.year))['rows'])
        self.assertEqual(before, after, 'nothing may be written on a refusal')

    def test_pasting_the_same_list_twice_does_not_double_it(self):
        day = (self.today + timedelta(days=60)).isoformat()
        first = self.HolCo.add_many(self.company.id, 'DEMO Paste day | %s' % day)
        second = self.HolCo.add_many(self.company.id, 'DEMO Paste day | %s' % day)
        self.assertEqual(first['added'], 1)
        self.assertEqual(second['added'], 0)
        self.assertEqual(second['already'], ['DEMO Paste day'])

    def test_a_company_with_no_working_hours_is_told_why(self):
        bare = self.env['res.company'].create({'name': 'D1 No Hours Co'})
        bare.resource_calendar_id = False
        with self.assertRaises(UserError) as caught:
            self.HolCo.add(bare.id, 'DEMO Anything',
                           self.today.isoformat())
        self.assertIn('working hours', str(caught.exception))

    def test_the_read_never_shows_one_persons_own_time_off(self):
        """`resource_id` empty is the WHOLE of the filter and it is written
        into every search in the facade, never left to a caller. A row WITH a
        resource is somebody's own leave."""
        employee = self.env['hr.employee'].create({
            'name': 'DEMO Holiday Reader', 'company_id': self.company.id})
        resource = employee.resource_id
        self.assertTrue(resource, 'the fixture employee needs a resource')
        self.env['resource.calendar.leaves'].create({
            'name': 'DEMO Somebody private day',
            'calendar_id': self.calendar.id,
            'resource_id': resource.id,
            'date_from': '%s 01:00:00' % (self.today + timedelta(days=70)),
            'date_to': '%s 10:00:00' % (self.today + timedelta(days=70)),
        })
        column = self._mine(self.HolCo.year(self.today.year))
        self.assertNotIn('DEMO Somebody private day',
                         [row['name'] for row in column['rows']])

    def test_every_company_is_shown_and_the_readers_own_is_first(self):
        """The requirement that makes this screen worth building: all
        countries visible to all. Scoping it to `env.companies` would give a
        Vietnamese employee exactly the calendar they already knew about."""
        data = self.HolCo.year(self.today.year)
        self.assertGreater(len(data['companies']), 1,
                           'the board shows every company, not just one')
        self.assertEqual(data['companies'][0]['id'], self.company.id)

    def test_remove_refuses_a_row_that_is_not_a_public_holiday(self):
        employee = self.env['hr.employee'].create({
            'name': 'DEMO Holiday Reader 2', 'company_id': self.company.id})
        private = self.env['resource.calendar.leaves'].create({
            'name': 'DEMO Private again',
            'calendar_id': self.calendar.id,
            'resource_id': employee.resource_id.id,
            'date_from': '%s 01:00:00' % (self.today + timedelta(days=80)),
            'date_to': '%s 10:00:00' % (self.today + timedelta(days=80)),
        })
        with self.assertRaises(UserError):
            self.HolCo.remove(private.id)
        self.assertTrue(private.exists())

    def test_a_reader_who_is_not_an_officer_may_look_and_not_write(self):
        plain = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'DEMO Holiday Looker', 'login': 'demo.hol.look.d1',
                'company_id': self.company.id,
                'company_ids': [(6, 0, [self.company.id])],
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        data = self.Hol.with_user(plain).year(self.today.year)
        self.assertFalse(data['can_edit'],
                         'a reader must not be offered a door that refuses')
        self.assertTrue(data['companies'], 'but they must still see the list')
        with self.assertRaises(Exception):
            self.Hol.with_user(plain).add(
                self.company.id, 'DEMO Not allowed', self.today.isoformat())

    def test_the_next_holiday_is_worked_out_from_the_servers_clock(self):
        self.HolCo.add(self.company.id, 'DEMO Next one up',
                       (self.today + timedelta(days=3)).isoformat())
        column = self._mine(self.HolCo.year(self.today.year))
        self.assertTrue(column['next'], 'the column must name its next day')
        self.assertLessEqual(column['next']['days_away'], 3)


@tagged('post_install', '-at_install')
class TestHolidaysSeams(TransactionCase):
    """The promises that are absences, and the three-file spelling."""

    def test_the_mission_registry_is_spelt_the_same_in_both_files(self):
        """THE ONE GATE THAT REPLACES AN IMPORT.

        Every other module in the product imports its hub's exported registry
        constant, so a rename is a compile error. This module cannot: Mission
        Control DEPENDS on `pb_timeoff` (it mounts the Leave cockpit as its
        Time Off lens), so importing it back would make the manifest graph a
        cycle. The literal string is therefore checked against the constant
        `pb_mission` actually exports.
        """
        hub = _code(_src('pb_mission', 'static', 'src', 'js', 'pb_mission.js'))
        match = re.search(
            r'export const MISSION_LENSES = "([^"]+)"', hub)
        self.assertTrue(match, 'pb_mission must export MISSION_LENSES')
        mine = _code(_src('pb_timeoff', 'static', 'src', 'js',
                          'timeoff_palette.js'))
        self.assertIn('const MISSION_LENSES = "%s"' % match.group(1), mine,
                      'the two spellings of the lens registry have drifted')
        self.assertIn('registry.category(MISSION_LENSES).add("holidays"', mine,
                      'the Holidays lens must join through the registry')
        self.assertNotIn('@pb_mission/', mine,
                         'importing the hub back would be a dependency cycle')

    def test_the_palette_rows_are_in_the_D_block(self):
        """⌘K blocks: A 3500, B 3600, C 3700, **D 3800**, E 3900."""
        mine = _code(_src('pb_timeoff', 'static', 'src', 'js',
                          'timeoff_palette.js'))
        for row, sequence in (('wf_holidays', 3800), ('wf_carry', 3820)):
            self.assertIn('palette.add("%s"' % row, mine)
            self.assertIn('{ sequence: %s }' % sequence, mine)

    def test_every_palette_door_is_an_xmlid_and_carries_a_probe(self):
        """A bare tag is synthesised with no action NAME, so anything
        returning through a breadcrumb reads "Unnamed" (R180); `requires` is
        what says this module's JS actually shipped (R110/R116)."""
        mine = _code(_src('pb_timeoff', 'static', 'src', 'js',
                          'timeoff_palette.js'))
        self.assertEqual(mine.count('requires:'), mine.count('palette.add('))
        self.assertNotIn('action: { tag:', mine)

    def test_no_screen_in_this_module_says_the_engines_name(self):
        """Binding rule 1. COMMENTS ARE STRIPPED FIRST (R118): the rule binds
        user-visible STRINGS, and the engineering notes have to be able to say
        the real name."""
        module = get_module_path('pb_timeoff')
        bad = []
        for root, dirs, files in os.walk(module):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
            for name in files:
                if not name.endswith(('.js', '.xml', '.py', '.scss', '.csv')):
                    continue
                if root.endswith('tests') or name.endswith('.po'):
                    continue
                path = os.path.join(root, name)
                text = _read(path)
                if name.endswith(('.js', '.scss')):
                    text = _code(text)
                elif name.endswith('.xml'):
                    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
                elif name.endswith('.py'):
                    text = re.sub(r'#.*', '', text)
                    text = re.sub(r'"""	?.*?"""', '', text, flags=re.S)
                for line in text.splitlines():
                    if re.search(r'\bodoo\b', line, re.I) \
                            and 'from odoo' not in line \
                            and 'odoo.addons' not in line \
                            and 'odoo-module' not in line \
                            and 'odoo/owl' not in line \
                            and '<odoo' not in line \
                            and '</odoo' not in line:
                        bad.append('%s: %s' % (path, line.strip()[:90]))
        self.assertFalse(bad, 'the product name must never reach a screen')

    def test_the_holidays_lens_carries_no_group_gate(self):
        """R209 from the other side: the obvious gate is the HR one and it is
        the wrong one, because the whole requirement is that everybody sees
        every country's holidays. The SERVER decides what the buttons may
        do."""
        mine = _code(_src('pb_timeoff', 'static', 'src', 'js',
                          'timeoff_palette.js'))
        block = mine[mine.index('registry.category(MISSION_LENSES)'):]
        block = block[:block.index('}, { sequence: 20 })')]
        self.assertIn('groups: []', block)

    def test_the_screen_asks_the_server_whether_it_may_write(self):
        board = _code(_src('pb_timeoff', 'static', 'src', 'js',
                           'pb_holidays.js'))
        self.assertIn('return !!this.d.can_edit;', board,
                      'the Add door is drawn from the server\'s own answer')

    def test_no_emoji_anywhere_in_this_module(self):
        """Design system: Lucide through the shared `ic()` set, never an
        emoji. Written as escapes so this file cannot trip its own gate."""
        emoji = re.compile('[\U0001F000-\U0001FAFF☀-➿️]')
        module = get_module_path('pb_timeoff')
        bad = []
        for root, dirs, files in os.walk(module):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
            for name in files:
                if not name.endswith(('.js', '.xml', '.scss')):
                    continue
                if emoji.search(_read(os.path.join(root, name))):
                    bad.append(os.path.join(root, name))
        self.assertFalse(bad)

    def test_every_icon_the_board_names_is_in_the_shared_registry(self):
        """`ic()` falls back to a plain circle with NO error for a name the
        set has never heard of, so a typo ships as a blank circle and nothing
        reports it (R146/R147). Checked against the INSTALLED copy, which is
        what a test running on the server reads."""
        registry_src = _src('pb_import_kit', 'static', 'src', 'js',
                            'import_icons.js')
        known = set(re.findall(r'^\s{4}(\w+):', registry_src, re.M))
        self.assertIn('sun', known)
        for source in ('pb_holidays.js', 'timeoff_palette.js'):
            text = _code(_src('pb_timeoff', 'static', 'src', 'js', source))
            for name in re.findall(r'\bic\(["\'](\w+)["\']', text):
                self.assertIn(name, known, '%s is not in the icon set' % name)
            for name in re.findall(r'icon: "(\w+)"', text):
                self.assertIn(name, known, '%s is not in the icon set' % name)

    def test_the_portal_helpers_all_carry_this_modules_prefix(self):
        """R186 — ALL `CustomerPortal` SUBCLASSES MERGE INTO ONE CLASS, so a
        helper called `_notice` here and `_notice` in `pb_rnr` are the same
        attribute and whichever module loads last silently wins. It has bitten
        this programme three times and every one was invisible at runtime."""
        import ast
        tree = ast.parse(_src('pb_timeoff', 'controllers', 'portal.py'))
        bad = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, ast.FunctionDef):
                    continue
                name = item.name
                if not name.startswith('_') or name.startswith('_lv_'):
                    continue
                # framework hooks are overridden on purpose
                if name.startswith(('_prepare_', '__')):
                    continue
                bad.append(name)
        self.assertFalse(bad, 'portal helpers need the _lv_ prefix: %s' % bad)

    def test_bracketed_plurals_are_nowhere_on_a_screen(self):
        """R46/R219 — "1 day(s)" is how a screen announces it was written by
        a programme rather than by a person."""
        module = get_module_path('pb_timeoff')
        bad = []
        for root, dirs, files in os.walk(module):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
            if root.endswith('tests'):
                continue
            for name in files:
                if not name.endswith(('.js', '.xml')):
                    continue
                text = _read(os.path.join(root, name))
                if re.search(r'\w\(s\)', text):
                    bad.append(os.path.join(root, name))
        self.assertFalse(bad)
