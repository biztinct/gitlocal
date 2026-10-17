# -*- coding: utf-8 -*-
"""LEARNREV P0 T5 (G24, ledger LR4) — a door answer never dead-ends.

When the browser sent no ⌘K rows, `resolve_door` used to answer "I cannot see
your list of screens yet. Close and reopen this panel, then ask again." — the
owner saw it on Rize. The server now builds the list itself
(`payai/catalogue.py`), offers only what the person can open, and a poor match
gets the closest screens as chips.
"""
import glob
import os

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_payai_actions.payai import catalogue, gate, i18n, resolve, runner

GONE = ("I cannot see your list of screens yet", "Close and reopen this panel",
        "Hãy đóng rồi mở lại khung này")


@tagged('post_install', '-at_install', 'payai')
class TestLearnrevDoors(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g = cls.env.ref
        base = g('base.group_user').id
        # PayAI's conversation needs "PayAI User". The module makes every
        # internal user one, but a database can take that away (payobook has),
        # so the fixture says it rather than inheriting it.
        payai = g('pb_payroll_ai_insights.group_payai_user').id
        company = cls.env.company
        cls.officer = Users.create({
            'name': 'Learnrev Officer', 'login': 'learnrev.officer@test.invalid',
            'lang': 'en_US', 'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
            'group_ids': [(6, 0, [base, payai,
                                  g('pb_hr_payroll_base.group_payroll_base_officer').id,
                                  g('om_hr_payroll.group_hr_payroll_user').id])]})
        cls.plain = Users.create({
            'name': 'Learnrev Plain', 'login': 'learnrev.plain@test.invalid',
            'lang': 'en_US', 'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
            'group_ids': [(6, 0, [base, payai])]})

    def _ctx(self, user):
        """A request context whose conversation carries NO ⌘K rows."""
        Conv = self.env['payroll.ai.conversation'].with_user(user)
        session = Conv.create({'name': 'Learnrev no doors', 'user_id': user.id})
        self.assertFalse(session.sudo().payai_doors())
        engine = self.env['payroll.ai.engine'].with_user(user)
        ctx = runner.Ctx(engine, {'conversation_id': session.id})
        self.assertEqual(ctx.doors, [])
        return ctx

    def setUp(self):
        super().setUp()
        token = i18n.set_lang('en_US')
        self.addCleanup(i18n.reset_lang, token)

    def test_01_pay_runs_board_without_doors(self):
        ctx = self._ctx(self.officer)
        res = resolve.resolve_door(ctx, 'open the pay runs board')
        self.assertEqual(res['status'], 'resolved', res)
        self.assertEqual(res['value'], 'pbdoor.pb_pay_hub.runs')
        row = ctx.door_row(res['value'])
        self.assertTrue(row)
        self.assertEqual(resolve.door_title(row), 'Pay Run › Runs')
        # It opens through its own destination (no ⌘K row in the browser).
        self.assertEqual(row['hub'], {'tag': 'pb_pay_hub',
                                      'xmlid': 'pb_payhub.action_pb_pay_hub',
                                      'lens': 'runs'})
        self.assertTrue(ctx.has_door(res['value']))

    def test_02_the_screen_is_found_by_its_own_name(self):
        ctx = self._ctx(self.officer)
        res = resolve.resolve_door(ctx, 'pay runs')
        self.assertEqual((res['status'], res['value']),
                         ('resolved', 'pbdoor.pb_pay_hub.runs'), res)

    def test_03_nothing_matches_is_said_plainly(self):
        ctx = self._ctx(self.officer)
        res = resolve.resolve_door(ctx, 'zebra okapi')
        self.assertEqual(res['status'], 'missing')
        self.assertIn('I could not find a screen called', res['note'])

    def test_04_a_poor_match_offers_the_closest_screens(self):
        ctx = self._ctx(self.officer)
        res = resolve.resolve_door(ctx, 'pay okapi')
        self.assertEqual(res['status'], 'ambiguous', res)
        self.assertTrue(1 <= len(res['candidates']) <= resolve.DOOR_MISS_CHIPS)
        self.assertIn('I could not find a screen called', res['note'])

    def test_05_only_screens_the_person_can_open(self):
        rows = catalogue.server_doors(self.env, self.plain)
        self.assertFalse([r for r in rows if (r.get('hub') or {}).get('tag') == 'pb_pay_hub'],
                         'Pay Run offered to a person who cannot see it')
        for row in catalogue.server_doors(self.env, self.officer):
            self.assertFalse(gate.door_denied(row), row['id'])
            self.assertFalse(gate.target_denied(row['hub']), row['id'])
            self.assertTrue(row['id'].startswith(catalogue.PREFIX))

    def test_06_the_dead_end_sentence_is_gone(self):
        base = get_module_path('pb_payai_actions')
        hits = []
        for ext in ('py', 'po', 'pot', 'js', 'xml'):
            for path in glob.glob(os.path.join(base, '**', '*.' + ext), recursive=True):
                if path.endswith('test_learnrev_doors.py'):
                    continue
                with open(path, encoding='utf-8') as fh:
                    text = fh.read()
                hits += ['%s: %s' % (os.path.relpath(path, base), s) for s in GONE if s in text]
        self.assertEqual(hits, [])
