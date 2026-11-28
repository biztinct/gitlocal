# -*- coding: utf-8 -*-
"""PSCHEME P2a — Mapping, "Set for everyone in this team", the country net.

T1  board payload: usual / own counts per team; the own list; coverage reasons
T2  team drawer plan: the groups, country-mismatch rows unticked, sub-teams
    with their own usual scheme left out
T3  team apply, fast lane: only ticked people; fills from the 1st of this
    month, moves from the given date (old row ended the day before); the
    advance per A13 / R7; no line on the map created or changed; idempotent
T4  team apply with a second approver: nothing until approved; a person
    changed in between -> the WHOLE request refused, the person named;
    waiting shows on each person's panel
T10 the country net: true / false / fixed by a later row / fixed by a
    waiting change; the board's list and count
T12 rights: an HR officer asks (B and C) but cannot carry out; a portal user
    is refused everywhere; a payroll manager does both
"""

from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import new_test_user, tagged

from .p2a_common import P2aCase


@tagged('post_install', '-at_install', 'pscheme', 'pscheme_p2a')
class TestP2aBoard(P2aCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ana = cls._person('DEMO P2A Ana', cls.team, 'VN')
        cls.budi = cls._person('DEMO P2A Budi', cls.team, 'ID')
        cls.chi = cls._person('DEMO P2A Chi', cls.sub, 'VN')
        cls.dan = cls._person('DEMO P2A Dan', cls.sub2, 'VN')
        cls.eka = cls._person('DEMO P2A Eka', cls.loose, 'SG')

    # ==================================================================== T1
    def test_t1_board_counts_own_list_and_reasons(self):
        self.line(self.vn_end, team=self.team)
        self.row(self.budi, self.id_end, self.first - timedelta(days=60))
        board = self.board().get_board(self.company.id)
        persons = board['persons']
        self.assertEqual(persons['own'], 1)
        self.assertEqual(persons['without'], persons['people'] - 1)
        rows = {}
        for segment in board['segments']:
            for item in [segment] + list(segment.get('children') or []):
                rows[item['id']] = item
        team = rows[self.team.id]
        # Ana, Chi, Dan follow the team's usual scheme; Budi has her own
        self.assertEqual(team['usual'], 3)
        self.assertEqual(team['own'], 1)
        self.assertEqual(rows[self.top.id]['own'], 1)
        own = self.board().team_own_people(self.team.id, self.company.id)
        self.assertEqual([p['name'] for p in own['people']], ['DEMO P2A Budi'])
        self.assertEqual(own['people'][0]['scheme'], self.id_end.name)
        self.assertTrue(own['people'][0]['since_words'])
        # coverage reasons: an own scheme that ended, and a team with no line
        self.Row.sudo().search([('employee_id', '=', self.budi.id)]).date_to = \
            self.first - timedelta(days=1)
        cover = self.Map.coverage(self.company.id, 'end_cycle')
        reasons = {p['name']: p['reason'] for p in cover['not_covered']}
        self.assertIn('own pay scheme has ended', reasons['DEMO P2A Budi'])
        self.assertIn('no pay scheme of their own', reasons['DEMO P2A Eka'])
        self.assertIn('no usual pay scheme', reasons['DEMO P2A Eka'])

    # ==================================================================== T2
    def test_t2_team_plan(self):
        self.line(self.vn_end, team=self.team)
        self.line(self.id_end, team=self.sub2)        # Sub own has its own usual scheme
        self.row(self.budi, self.id_end, self.first)
        plan = self.board().team_plan(self.team.id, self.company.id)
        names = {p['name']: p for p in plan['people']}
        self.assertEqual(set(names), {'DEMO P2A Ana', 'DEMO P2A Budi', 'DEMO P2A Chi'})
        self.assertNotIn('DEMO P2A Dan', names)        # sub-team with its own line
        self.assertEqual(plan['default_id'], self.vn_end.id)
        self.assertEqual(plan['usual_id'], self.vn_end.id)
        # without a scheme: ticked; with their own: never ticked by default
        self.assertTrue(names['DEMO P2A Ana']['tick'])
        self.assertTrue(names['DEMO P2A Chi']['tick'])
        self.assertIsNone(names['DEMO P2A Ana']['own'])
        self.assertFalse(names['DEMO P2A Budi']['tick'])
        self.assertEqual(names['DEMO P2A Budi']['own']['config_id'], self.id_end.id)
        # a Country of work that is not the scheme's: shown unticked
        frank = self._person('DEMO P2A Frank', self.team, 'SG')
        plan = self.board().team_plan(self.team.id, self.company.id)
        frank_row = next(p for p in plan['people'] if p['id'] == frank.id)
        self.assertFalse(frank_row['fits'])
        self.assertFalse(frank_row['tick'])
        # the majority country's schemes come first in the chooser
        self.assertEqual(plan['country'], 'VN')
        self.assertEqual(plan['choices'][0]['country_code'], 'VN')
        self.assertEqual(plan['fill_date'], str(self.first))
        self.assertEqual(plan['move_date'], str(self.next_first))

    # ==================================================================== T3
    def test_t3_team_apply_fast_lane(self):
        line = self.line(self.vn_end, team=self.team)
        self.line(self.vn_mid, cycle='mid_cycle', team=self.loose)   # not ours
        self.row(self.budi, self.id_end, self.first - timedelta(days=90))
        lines_before = [(r.id, r.config_id.id, r.cycle_type, r.department_id.id)
                        for r in self.Assign.search([('company_id', '=', self.company.id)])]
        Board = self.board()
        out = Board.team_apply(self.team.id, self.vn_end.id, False,
                               fill_ids=[self.ana.id], move_ids=[], company_id=self.company.id)
        self.assertTrue(out['applied'], out)
        self.assertEqual(out['filled'], 1)
        self.assertEqual(self.rows_of(self.ana), [(self.vn_end, self.first, False, 'team')])
        self.assertFalse(self.rows_of(self.chi))                    # not ticked
        self.assertEqual(len(self.rows_of(self.budi)), 1)           # not moved
        # move Budi from a date: the old row ends the day before; the advance
        out = Board.team_apply(self.team.id, self.vn_end.id, self.vn_mid.id,
                               fill_ids=[self.chi.id], move_ids=[self.budi.id],
                               move_date=str(self.next_first), company_id=self.company.id)
        self.assertEqual((out['filled'], out['moved']), (1, 1))
        budi = self.rows_of(self.budi)
        self.assertIn((self.id_end, self.first - timedelta(days=90),
                       self.next_first - timedelta(days=1), 'hand'), budi)
        self.assertIn((self.vn_end, self.next_first, False, 'team'), budi)
        self.assertIn((self.vn_mid, self.next_first, False, 'team'), budi)
        self.assertIn((self.vn_mid, self.first, False, 'team'), self.rows_of(self.chi))
        # R7 / A13: Ana was given no advance, and the team's advance never reaches her
        answer = self.Map.resolve_many(self.ana.ids, 'mid_cycle')[self.ana.id]
        self.assertEqual(answer['config_id'], 0)
        # no line on the map created or changed
        self.assertEqual(lines_before, [(r.id, r.config_id.id, r.cycle_type, r.department_id.id)
                                        for r in self.Assign.search(
                                            [('company_id', '=', self.company.id)])])
        self.assertTrue(line.exists())
        # idempotent: asking again changes nothing, and says why
        before = self.Row.sudo().search_count([])
        with self.assertRaisesRegex(UserError, 'Nobody is ticked'):
            Board.team_apply(self.team.id, self.vn_end.id, self.vn_mid.id,
                             fill_ids=[self.ana.id, self.chi.id], move_ids=[self.budi.id],
                             move_date=str(self.next_first), company_id=self.company.id)
        self.assertEqual(self.Row.sudo().search_count([]), before)

    # ==================================================================== T4
    def test_t4_team_apply_second_approver(self):
        company, hr, boss = self.routed('DEMO P2A Routed T4')
        team = self.env['hr.department'].create({'name': 'DEMO P2A R team',
                                                 'company_id': company.id})
        main = self._config('DEMO P2A R monthly', 'DEMOP2ARM', 'end_cycle', 'VN', company=company)
        other = self._config('DEMO P2A R other', 'DEMOP2ARO', 'end_cycle', 'VN', company=company)
        ann = self._person('DEMO P2A R Ann', team, 'VN', company=company)
        bob = self._person('DEMO P2A R Bob', team, 'VN', company=company)
        Board = self.Board.with_user(hr).with_context(allowed_company_ids=[company.id])
        out = Board.team_apply(team.id, main.id, False, fill_ids=[ann.id, bob.id],
                               company_id=company.id)
        self.assertTrue(out['pending'], out)
        self.assertFalse(self.Row.sudo().search_count([('employee_id', 'in', (ann | bob).ids)]))
        for person in (ann, bob):
            waiting = Board.person_scheme(person.id)['waiting']
            self.assertTrue(waiting, person.name)
            self.assertEqual(waiting['scheme'], main.name)
        # somebody changes Bob while it waits: the whole request is refused,
        # Bob named (an approver approved exactly this list)
        self.row(bob, other, self.first)
        request = self.approve(out, boss, company)
        self.assertFalse(self.Row.sudo().search_count([('employee_id', '=', ann.id)]))
        self.assertIn('DEMO P2A R Bob', request.block_reason or '')
        self.assertNotRegex(request.block_reason or '', r'\b%d\b' % bob.id)
        # asked again from what is there now: carried out on approval
        out = Board.team_apply(team.id, main.id, False, fill_ids=[ann.id],
                               company_id=company.id)
        self.approve(out, boss, company)
        self.assertEqual([r[0] for r in self.rows_of(ann)], [main])

    # =================================================================== T10
    def test_t10_country_net(self):
        self.line(self.vn_end, team=self.team)            # Ana (VN) is fine
        # Eka works in Singapore and her own pay scheme is Vietnam's
        own = self.row(self.eka, self.vn_end, self.first - timedelta(days=60))
        Board = self.board()
        net = Board.person_scheme(self.eka.id)['country_mismatch']
        self.assertTrue(net)
        self.assertIn('works in Singapore', net['line'])
        self.assertIn(self.vn_end.name, net['line'])
        self.assertEqual(net['target_id'], self.sg_end.id)      # the only SG scheme
        self.assertEqual(net['date'], str(self.next_first))
        self.assertIsNone(Board.person_scheme(self.ana.id)['country_mismatch'])
        self.assertIn('Singapore', Board.paid_by(self.eka.id)['mismatch'])
        # Budi works in Indonesia and follows the team's Vietnamese scheme
        listed = Board.mismatch_people(self.company.id)
        self.assertEqual(listed['total'], 2)
        targets = {p['employee_id']: p['target_id'] for p in listed['people']}
        self.assertEqual(targets, {self.eka.id: self.sg_end.id, self.budi.id: self.id_end.id})
        self.assertEqual(listed['one_target_id'], 0)            # two schemes fit: no bulk
        self.assertEqual(Board.get_board(self.company.id)['persons']['mismatch'], 2)
        # fixed by a later row
        own.date_to = self.next_first - timedelta(days=1)
        later = self.row(self.eka, self.sg_end, self.next_first)
        self.assertIsNone(Board.person_scheme(self.eka.id)['country_mismatch'])
        listed = Board.mismatch_people(self.company.id)
        self.assertEqual([p['employee_id'] for p in listed['people']], [self.budi.id])
        self.assertEqual(listed['one_target_id'], self.id_end.id)   # one scheme fits all
        later.unlink()
        own.date_to = False
        self.assertTrue(Board.person_scheme(self.eka.id)['country_mismatch'])
        # fixed by a waiting change (a second-approver company)
        company, hr, _boss = self.routed('DEMO P2A Routed T10')
        team = self.env['hr.department'].create({'name': 'DEMO P2A R10', 'company_id': company.id})
        vn = self._config('DEMO P2A R10 VN', 'DEMOP2AR10V', 'end_cycle', 'VN', company=company)
        sg = self._config('DEMO P2A R10 SG', 'DEMOP2AR10S', 'end_cycle', 'SG', company=company)
        self.Assign.create({'config_id': vn.id, 'cycle_type': 'any', 'department_id': team.id,
                            'company_id': company.id})
        gus = self._person('DEMO P2A R10 Gus', team, 'SG', company=company)
        As = self.Board.with_user(hr).with_context(allowed_company_ids=[company.id])
        self.assertTrue(As.person_scheme(gus.id)['country_mismatch'])
        out = As.mismatch_change([gus.id], sg.id, company_id=company.id)
        self.assertTrue(out['pending'], out)
        self.assertIsNone(As.person_scheme(gus.id)['country_mismatch'])
        self.assertEqual(As.mismatch_people(company.id)['total'], 0)
        # the bulk change, fast lane: one request, from the 1st of next month
        out = Board.mismatch_change([self.eka.id], self.sg_end.id, company_id=self.company.id)
        self.assertTrue(out['applied'], out)
        self.assertEqual(self.rows_of(self.eka), [
            (self.vn_end, self.first - timedelta(days=60), self.next_first - timedelta(days=1), 'hand'),
            (self.sg_end, self.next_first, False, 'hand')])

    # =================================================================== T12
    def test_t12_rights(self):
        co = {'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])]}
        hr = new_test_user(self.env, login='p2a_hr_fast', groups='base.group_user,hr.group_hr_user',
                           name='DEMO P2A HR fast', **co)
        worker = new_test_user(self.env, login='p2a_worker', groups='base.group_portal',
                               name='DEMO P2A Worker', **co)
        boss = new_test_user(self.env, login='p2a_boss_fast', name='DEMO P2A Payroll fast',
                             groups='base.group_user,hr.group_hr_user,'
                                    'pb_hr_payroll_formula.group_formula_manager', **co)
        self.line(self.vn_end, team=self.team)
        # fast lane: the HR officer may look and ask, never carry out
        As = self.board(hr)
        self.assertTrue(As.team_plan(self.team.id, self.company.id)['blocked'])
        self.assertTrue(As.fill_plan(self.company.id)['blocked'])
        with self.assertRaisesRegex(UserError, 'payroll manager'):
            As.team_apply(self.team.id, self.vn_end.id, False, fill_ids=[self.ana.id],
                          company_id=self.company.id)
        with self.assertRaisesRegex(UserError, 'payroll manager'):
            As.fill_apply(self.company.id)
        # second-approver company: the HR officer's requests are sent
        company, rhr, _rboss = self.routed('DEMO P2A Routed T12')
        team = self.env['hr.department'].create({'name': 'DEMO P2A R12', 'company_id': company.id})
        vn = self._config('DEMO P2A R12 VN', 'DEMOP2AR12V', 'end_cycle', 'VN', company=company)
        self.Assign.create({'config_id': vn.id, 'cycle_type': 'any', 'department_id': team.id,
                            'company_id': company.id})
        hal = self._person('DEMO P2A R12 Hal', team, 'VN', company=company)
        ivy = self._person('DEMO P2A R12 Ivy', team, 'VN', company=company)
        R = self.Board.with_user(rhr).with_context(allowed_company_ids=[company.id])
        self.assertTrue(R.team_apply(team.id, vn.id, False, fill_ids=[hal.id],
                                     company_id=company.id)['pending'])
        self.assertTrue(R.fill_apply(company.id, employee_ids=[ivy.id])['pending'])
        # a portal user: refused everywhere
        Portal = self.Board.with_user(worker)
        for call in (lambda b: b.fill_plan(self.company.id),
                     lambda b: b.fill_apply(self.company.id, dry=True),
                     lambda b: b.fill_undo(company_id=self.company.id),
                     lambda b: b.team_plan(self.team.id, self.company.id),
                     lambda b: b.team_apply(self.team.id, self.vn_end.id, False, [self.ana.id]),
                     lambda b: b.team_own_people(self.team.id, self.company.id),
                     lambda b: b.mismatch_people(self.company.id),
                     lambda b: b.mismatch_change([self.ana.id], self.vn_end.id),
                     lambda b: b.contract_note_dismiss(0)):
            with self.assertRaises(AccessError):
                call(Portal)
        # the payroll manager does both
        Boss = self.board(boss)
        self.assertFalse(Boss.team_plan(self.team.id, self.company.id)['blocked'])
        out = Boss.team_apply(self.team.id, self.vn_end.id, False, fill_ids=[self.ana.id],
                              company_id=self.company.id)
        self.assertTrue(out['applied'], out)
        out = Boss.fill_apply(self.company.id, employee_ids=[self.chi.id])
        self.assertTrue(out['applied'], out)
