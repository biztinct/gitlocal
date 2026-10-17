# -*- coding: utf-8 -*-
"""LEARNREV P5a - T3: the feedback loop, the path seat, the search ranking.

  (a) the report: thumbs per screen and per field, the helper's no-answer
      counts per screen, the top search phrases - counts only, no person
  (b) admins only: a plain user is refused; the CSV re-asks and guards cells
  (c) a search that finds nothing is logged as a keyed hash + the screen key
      `library`; the words are stored only with BOTH gates (tenant switch AND
      this person's own yes) - and then the report can print them
  (d) `learn.path` bootstrap carries the seat (`why`) for a GUESSED role only
  (e) the declared event kinds include the ones the Library already logged
  (f) source tests: the Library hooks the miss call once per phrase, the
      palette ranks a field's home screen first, the 16 manifests are found
  + the Library's node suite (tests/js/library.test.mjs)
"""
import os
import re
import shutil
import subprocess

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError

from odoo.addons.pb_learn.models import learn_feedback as fb
from odoo.addons.pb_learn.models import learn_path as lp
from odoo.addons.pb_learn.models.learn_intent import FIXTURE_NAMES
from odoo.addons.pb_learn.models.learn_question import COLLECT_FLAG

from .test_guide_truth import EXPECTED

HERE = os.path.dirname(os.path.abspath(__file__))


def _read(module, rel):
    with open(os.path.join(get_module_path(module), rel), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install', 'learnrev')
class TestLearnrevP5(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_user = cls.env.ref('base.group_user')
        cls.person = cls.env['res.users'].create({
            'name': 'LR P5 Reader', 'login': 'lr_p5_reader',
            'group_ids': [(6, 0, [group_user.id])],
        })
        cls.admin = cls.env['res.users'].create({
            'name': 'LR P5 Admin', 'login': 'lr_p5_admin',
            'group_ids': [(6, 0, [group_user.id,
                                  cls.env.ref('base.group_system').id])],
        })
        # Start from an empty log for the kinds this reads.
        cls.env.cr.execute(
            "DELETE FROM learn_event WHERE kind IN %s",
            [('guide_feedback', 'library_miss', 'coach_miss')])
        cls.env['ir.config_parameter'].sudo().set_param(COLLECT_FLAG, 'False')

    # ------------------------------------------------------------ helpers
    def _thumb(self, user, field, up, screen='treatment'):
        return self.env['learn.guide'].with_user(user).rpc_feedback(screen, field, up)

    def _report(self, **kw):
        return self.env['learn.feedback'].with_user(self.admin).report(
            kw.get('days', 30), kw.get('lang', 'en'))

    # ---------------------------------------------------------------- (a)
    def test_a_report_counts_by_screen_and_field(self):
        self.assertTrue(self._thumb(self.person, 'pay_role', False))
        self.assertTrue(self._thumb(self.person, 'pay_role', False))
        self.assertTrue(self._thumb(self.person, 'pay_role', True))
        self.assertTrue(self._thumb(self.person, 'lane', True))
        self.env['learn.event'].with_user(self.person).log('coach_miss', screen='payruns')
        self.env['learn.event'].with_user(self.person).log('coach_miss', screen='payruns')
        r = self._report()
        self.assertEqual(set(r), {'days', 'collect', 'lang', 'totals', 'thumbs',
                                  'helper', 'search'})
        t = next(x for x in r['thumbs'] if x['screen'] == 'treatment')
        self.assertEqual((t['up'], t['down']), (2, 2))
        pay_role = next(f for f in t['fields'] if f['key'] == 'pay_role')
        self.assertEqual((pay_role['up'], pay_role['down']), (1, 2))
        self.assertEqual(pay_role['label'], 'Pay role')       # the column as shown
        self.assertEqual(t['fields'][0]['key'], 'pay_role')   # most "not helpful" first
        h = next(x for x in r['helper'] if x['screen'] == 'payruns')
        self.assertEqual(h['count'], 2)
        self.assertEqual(r['totals']['down'], 2)
        self.assertEqual(r['totals']['helper_miss'], 2)
        # Vietnamese reads the same numbers with the Vietnamese column.
        rv = self._report(lang='vi')
        tv = next(x for x in rv['thumbs'] if x['screen'] == 'treatment')
        self.assertEqual((tv['up'], tv['down']), (2, 2))
        self.assertNotEqual(next(f for f in tv['fields'] if f['key'] == 'pay_role')['label'], 'Pay role')

    def test_a2_counts_only_no_person(self):
        self._thumb(self.person, 'pay_role', False)
        blob = repr(self._report()) + self.env['learn.feedback'].with_user(
            self.admin).export_csv(30, 'en')['csv']
        for who in (self.person.login, self.person.name):
            self.assertNotIn(who, blob)

    def test_a3_the_window_is_the_days_asked(self):
        self._thumb(self.person, 'lane', False)
        self.env.cr.execute(
            "UPDATE learn_event SET occurred_at = now() - interval '45 days' "
            "WHERE kind = 'guide_feedback'")
        self.env.invalidate_all()
        self.assertEqual(self._report(days=30)['totals']['down'], 0)
        self.assertEqual(self._report(days=90)['totals']['down'], 1)

    # ---------------------------------------------------------------- (b)
    def test_b_admin_only(self):
        for method, args in (('report', (30, 'en')), ('export_csv', (30, 'en'))):
            with self.assertRaises(AccessError):
                getattr(self.env['learn.feedback'].with_user(self.person), method)(*args)

    def test_b2_csv_shape_and_formula_guard(self):
        self._thumb(self.person, 'pay_role', False)
        out = self.env['learn.feedback'].with_user(self.admin).export_csv(30, 'en')
        self.assertEqual(out['filename'], 'learn-feedback-30-days.csv')
        lines = out['csv'].splitlines()
        self.assertEqual(lines[0], 'section,screen,item,thumbs_up,thumbs_down,count')
        self.assertTrue(any(l.startswith('rating,') and ',Pay role,' in l for l in lines))
        self.assertEqual(fb.csv_cell('=HYPERLINK("x")'), "'=HYPERLINK(\"x\")")
        self.assertEqual(fb.csv_cell('+1'), "'+1")
        self.assertEqual(fb.csv_cell('-1'), "'-1")
        self.assertEqual(fb.csv_cell('@a'), "'@a")
        self.assertEqual(fb.csv_cell('plain'), 'plain')

    def test_b3_unknown_field_writes_nothing(self):
        self.assertFalse(self._thumb(self.person, 'not_a_field', False))
        self.assertFalse(self._thumb(self.person, 'pay_role', False, screen='no_such_screen'))

    # ---------------------------------------------------------------- (c)
    def _miss(self, user, query):
        return self.env['learn.feedback'].with_user(user).rpc_search_miss(query, 'en')

    def _miss_rows(self):
        self.env.cr.execute(
            "SELECT screen, detail FROM learn_event WHERE kind = 'library_miss'")
        return self.env.cr.fetchall()

    def test_c_miss_is_a_hash_and_a_screen_key(self):
        self.assertTrue(self._miss(self.person, 'Quarterly  Bonus Matrix'))
        rows = self._miss_rows()
        self.assertEqual(len(rows), 1)
        screen, detail = rows[0]
        self.assertEqual(screen, 'library')
        self.assertTrue(re.fullmatch(r'h:[0-9a-f]{12}', detail), detail)
        # Nothing the person typed is anywhere in the log...
        self.env.cr.execute("SELECT count(*) FROM learn_event WHERE detail ILIKE '%bonus%'"
                            " OR screen ILIKE '%bonus%'")
        self.assertEqual(self.env.cr.fetchone()[0], 0)
        # ...and no question row exists (the switch is off).
        self.assertFalse(self.env['learn.question'].sudo().search(
            [('screen', '=', 'library')]))
        # The same phrase spelled differently is the same hash.
        self._miss(self.person, 'quarterly bonus  matrix')
        self.assertEqual(len({d for _s, d in self._miss_rows()}), 1)
        self.assertFalse(self._miss(self.person, 'ab'), 'two letters is not a search')

    def test_c2_report_shows_counts_not_words_when_off(self):
        for _i in range(3):
            self._miss(self.person, 'where is my bonus matrix')
        self._miss(self.person, 'overtime cap')
        r = self._report()
        self.assertFalse(r['collect'])
        self.assertEqual(r['totals']['search_miss'], 4)
        self.assertEqual([s['count'] for s in r['search']], [3, 1])
        self.assertTrue(all(s['phrase'] == '' for s in r['search']))
        self.assertTrue(all(s['id'].startswith('h:') for s in r['search']))

    def test_c3_words_only_with_both_gates(self):
        Param = self.env['ir.config_parameter'].sudo()
        # switch on, but this person has not agreed: still no words.
        Param.set_param(COLLECT_FLAG, 'True')
        self._miss(self.person, 'overtime cap')
        self.assertFalse(self.env['learn.question'].sudo().search(
            [('screen', '=', 'library')]))
        # now they agree.
        self.env['learn.consent'].with_user(self.person).set_questions(True)
        self._miss(self.person, 'overtime cap')
        q = self.env['learn.question'].sudo().search([('screen', '=', 'library')])
        self.assertEqual(len(q), 1)
        self.assertFalse(q.matched)
        r = self._report()
        self.assertTrue(r['collect'])
        words = {s['phrase'] for s in r['search']}
        self.assertIn('overtime cap', words)
        # switch off again: the report goes back to counts only.
        Param.set_param(COLLECT_FLAG, 'False')
        self.assertTrue(all(s['phrase'] == '' for s in self._report()['search']))

    def test_c4_scrub_runs_before_the_hash(self):
        # A phrase that is only a named person scrubs to the same token, so two
        # different names do not become two different "phrases".
        names = list(FIXTURE_NAMES)[:2]
        self._miss(self.person, 'salary of %s' % names[0])
        self._miss(self.person, 'salary of %s' % names[1])
        self.assertEqual(len({d for _s, d in self._miss_rows()}), 1)

    # ---------------------------------------------------------------- (d)
    def test_d_path_why_only_for_a_guessed_role(self):
        Path = self.env['learn.path']
        user = self.env['res.users'].create({
            'name': 'LR P5 Approver', 'login': 'lr_p5_approver',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('pb_hr_payroll_base.group_payroll_final_approver').id])],
        })
        extra = Path.with_user(user).bootstrap_extra()
        self.assertEqual(extra['role'], 'approver')
        self.assertFalse(extra['role_chosen'])
        self.assertEqual(extra['why'], lp.ROLE_WHY['approver'])
        self.assertIn('approval seat', extra['why']['en'])
        picked = Path.with_user(user).set_role('approver')
        self.assertEqual(picked['why'], {}, 'a role the person picked names no seat')
        # Every role's rule carries both languages, in plain words, no brand.
        for role, why in lp.ROLE_WHY.items():
            self.assertIn(role, lp.ROLES)
            self.assertTrue(why['en'] and why['vi'])
            self.assertNotIn('odoo', (why['en'] + why['vi']).lower())

    # ---------------------------------------------------------------- (e)
    def test_e_event_kinds_are_declared(self):
        kinds = {k for k, _l in self.env['learn.event']._selection_kind()}
        self.assertTrue({'library_guide', 'library_search_open', 'library_miss',
                         'guide_feedback', 'coach_miss'} <= kinds)
        # Every kind the Library's page logs is declared (LR63: an undeclared
        # kind is dropped without a word).
        src = _read('pb_learn', 'static/src/journey/journey.js')
        used = set(re.findall(r'this\._log\("([a-z_]+)"', src))
        self.assertFalse(used - kinds, "undeclared event kinds: %s" % sorted(used - kinds))

    # ---------------------------------------------------------------- (f)
    def test_f_sources(self):
        journey = _read('pb_learn', 'static/src/journey/journey.js')
        self.assertIn('"learn.feedback", "rpc_search_miss"', journey)
        self.assertEqual(journey.count('rpc_search_miss'), 1)
        self.assertIn('_missSeen', journey)        # once per phrase per visit
        coach = _read('pb_learn', 'static/src/coach/coach.js')
        self.assertRegex(coach, r'registerFieldRows\(rows,[\s\S]{0,200}content\)')
        palette = _read('pb_learn', 'static/src/hub/learn_palette.js')
        self.assertIn('export function homeFirst', palette)
        # The report is administrator-only on the server.
        src = _read('pb_learn', 'models/learn_feedback.py')
        self.assertIn("has_group('base.group_system')", src)
        self.assertNotIn('.sudo().search(', src.split('def report')[0].split('def _check_admin')[0])

    def test_f2_sixteen_manifests(self):
        man = self.env['learn.guide']._manifests()
        self.assertTrue(EXPECTED <= set(man), sorted(EXPECTED - set(man)))
        self.assertEqual(len(EXPECTED), 16)

    # --------------------------------------------------------------- node
    def test_h_library_node_suite(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed here')
        out = subprocess.run([node, os.path.join(HERE, 'js', 'library.test.mjs')],
                             capture_output=True, text=True, timeout=300)
        tail = (out.stdout or '')[-1500:] + (out.stderr or '')[-800:]
        self.assertEqual(out.returncode, 0, tail)
        self.assertRegex(out.stdout, r'\d+ passed, 0 failed')
