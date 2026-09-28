# -*- coding: utf-8 -*-
"""LEARN REFRESH step 5 — the final station set, the role paths over it, the
folded keys and their progress migration, and the whitelist Ask Payobook
chooses lessons from."""
import importlib.util
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from ..models.learn_path import MILESTONES, ROLE_GUESS, ROLE_PATHS
from .common import load_content


@tagged('post_install', '-at_install')
class TestRefreshPaths(TransactionCase):

    def setUp(self):
        super().setUp()
        self.content = load_content()
        self.keys = {s['key'] for s in self.content['stations']}

    def test_01_every_path_station_exists(self):
        for role, keys in ROLE_PATHS.items():
            missing = [k for k in keys if k not in self.keys]
            self.assertFalse(missing, '%s path names no station: %s' % (role, missing))
        self.assertEqual([r for r, _g in ROLE_GUESS], list(ROLE_PATHS))
        for _key, station in MILESTONES:
            self.assertIn(station, self.keys)

    def test_02_no_outline_only_station_is_left(self):
        for s in self.content['stations']:
            self.assertEqual(s['kind'], 'lesson', '%s has no lesson' % s['key'])
            steps = len(s['lessons'][0]['steps'])
            self.assertTrue(5 <= steps <= 10, '%s has %s steps' % (s['key'], steps))

    def test_03_retired_keys_land_on_their_new_station(self):
        aliases = self.content['station_aliases']
        self.assertEqual(aliases, {'contracts': 'employees', 'proration': 'adjust',
                                   'retro': 'adjust'})
        Content = self.env['learn.content']
        for old, new in aliases.items():
            self.assertNotIn(old, self.keys)
            self.assertEqual(Content.station(old)['key'], new)
        Progress = self.env['learn.progress']
        self.assertTrue(Progress.record('contracts', {'state': 'in_progress'}))
        row = Progress.search([('user_id', '=', self.env.uid), ('key', '=', 'employees')])
        self.assertEqual(row.state, 'in_progress')
        self.assertFalse(Progress.search([('key', '=', 'contracts')]))

    def test_04_the_migration_moves_and_merges_without_claiming_done(self):
        user = self.env.user
        cr = self.env.cr
        Progress = self.env['learn.progress'].sudo()
        Progress.search([('user_id', '=', user.id)]).unlink()
        cid = self.env.company.id
        for key, state in (('contracts', 'done'), ('proration', 'in_progress'),
                           ('retro', 'done')):
            cr.execute("""INSERT INTO learn_progress (user_id, company_id, key, state,
                                  step_index, attempts, first_try_correct)
                          VALUES (%s, %s, %s, %s, 3, 0, false)""", (user.id, cid, key, state))
        path = os.path.join(get_module_path('pb_learn'), 'migrations',
                            '19.0.19.0.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('pb_learn_m19', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.migrate(cr, '19.0.18.0.0')
        mod.migrate(cr, '19.0.18.0.0')        # idempotent
        Progress.invalidate_model()
        rows = {r.key: r.state for r in Progress.search([('user_id', '=', user.id)])}
        self.assertEqual(rows, {'employees': 'in_progress', 'adjust': 'in_progress'})

    def test_05_ask_payobook_whitelist_is_every_lesson(self):
        lessons = {l['key'] for s in self.content['stations'] for l in s['lessons']}
        base = get_module_path('pb_payroll_ai_insights')
        if not base:
            self.skipTest('pb_payroll_ai_insights is not on this database')
        src = open(os.path.join(base, 'models', 'payroll_ai_engine.py'),
                   encoding='utf-8').read()
        block = re.search(r'_KNOWN_LESSONS = \((.*?)\)\n', src, re.S).group(1)
        listed = set(re.findall(r"'([A-Z0-9]+)'", block))
        self.assertEqual(listed, lessons)

    def test_06_every_line_is_in_a_chapter(self):
        src = open(os.path.join(get_module_path('pb_learn'), 'static', 'src', 'journey',
                                'journey.js'), encoding='utf-8').read()
        block = re.search(r'const CHAPTERS = \[(.*?)\];', src, re.S).group(1)
        lines = set(re.findall(r'"([a-z]+)"', re.sub(r'key: "ch\d"', '', block)))
        self.assertEqual(lines, set(self.content['line_order']))
