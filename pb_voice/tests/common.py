# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Shared fixture: one DEMO company of 27 people, each with an Employee
(portal) login.

    Sales (13): DEMO Mai (no manager), Sales 1-7 report to Mai (team of 7),
                Sales 8-12 report to nobody
    Ops (7):    DEMO Oanh (no manager), Ops 1-4 report to Oanh (team of 4,
                too small to be a group), Ops 5-6 report to nobody
    General (5, no department) + Tiny department (2)

Cells when a round goes out (floor 5):
    Sales + Mai's team : Sales 1-7               (7)
    Sales              : Mai, Sales 8-12         (6)
    Ops                : Oanh, Ops 1-6           (7)
    company only       : General 1-5, Tiny 1-2   (7)
"""
from odoo.tests import new_test_user
from odoo.tests.common import TransactionCase


class VoiceCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env['res.company'].create({'name': 'DEMO Voice Co'})
        co = cls.company.id
        cls.hr = new_test_user(env, login='s9c_hr', company_id=co,
                               company_ids=[(6, 0, [co])],
                               groups='base.group_user,hr.group_hr_user')
        Dept = env['hr.department']
        cls.sales = Dept.create({'name': 'DEMO Sales', 'company_id': co})
        cls.ops = Dept.create({'name': 'DEMO Ops', 'company_id': co})
        cls.tiny = Dept.create({'name': 'DEMO Tiny', 'company_id': co})
        cls.users = {}
        cls._n = 0

        def person(name, dept=None, parent=None):
            cls._n += 1
            user = new_test_user(env, login='s9c_p%02d' % cls._n, name=name,
                                 email='s9c_p%02d@example.com' % cls._n,
                                 company_id=co, company_ids=[(6, 0, [co])],
                                 groups='base.group_portal')
            emp = env['hr.employee'].create({
                'name': name, 'company_id': co,
                'department_id': dept.id if dept else False,
                'parent_id': parent.id if parent else False,
                'user_id': user.id,
                'work_email': 's9c_p%02d@example.com' % cls._n,
            })
            cls.users[emp.id] = user
            return emp

        cls.mai = person('DEMO Mai', cls.sales)
        cls.team_mai = [person('DEMO Sales %d' % i, cls.sales, cls.mai)
                        for i in range(1, 8)]
        cls.sales_rest = [person('DEMO Sales %d' % i, cls.sales)
                          for i in range(8, 13)]
        cls.oanh = person('DEMO Oanh', cls.ops)
        cls.team_oanh = [person('DEMO Ops %d' % i, cls.ops, cls.oanh)
                         for i in range(1, 5)]
        cls.ops_rest = [person('DEMO Ops %d' % i, cls.ops) for i in range(5, 7)]
        cls.general = [person('DEMO General %d' % i) for i in range(1, 6)]
        cls.tiny_people = [person('DEMO Tiny %d' % i, cls.tiny) for i in range(1, 3)]
        cls.everyone = ([cls.mai] + cls.team_mai + cls.sales_rest + [cls.oanh]
                        + cls.team_oanh + cls.ops_rest + cls.general
                        + cls.tiny_people)
        cls.Round = env['pb.voice.round']
        cls.Box = env['pb.voice.box']
        cls.Voice = env['pb.voice']
        cls._rounds = []

    @classmethod
    def tearDownClass(cls):
        for rid in cls._rounds:
            cls.env['pb.voice.box']._voice_destroy(rid)
        super().tearDownClass()

    # ------------------------------------------------------------ helpers
    def as_hr(self, model):
        return model.with_user(self.hr).with_context(
            allowed_company_ids=self.hr.company_ids.ids)

    def as_person(self, emp, model):
        return model.with_user(self.users[emp.id]).with_context(
            allowed_company_ids=[emp.company_id.id])

    def make_round(self, comment=True, choice=False, name='DEMO pulse',
                   company=None):
        company = company or self.company
        rnd = self.as_hr(self.Round).with_context(
            allowed_company_ids=[company.id]).create({
                'name': name, 'company_id': company.id,
                'company_ids': [(6, 0, [company.id])],
            })
        Q = self.as_hr(self.env['pb.voice.question'])
        self.q_scale = Q.create({'round_id': rnd.id, 'kind': 'scale',
                                 'theme': 'manager', 'sequence': 1,
                                 'text': 'My manager gives me useful feedback.'})
        self.q_enps = Q.create({'round_id': rnd.id, 'kind': 'enps',
                                'theme': 'engagement', 'sequence': 2,
                                'text': 'Would you recommend us?'})
        if choice:
            self.q_choice = Q.create({'round_id': rnd.id, 'kind': 'choice',
                                      'theme': 'other', 'sequence': 3,
                                      'text': 'Best day for a team meeting?',
                                      'options': 'Monday\nFriday'})
        if comment:
            self.q_text = Q.create({'round_id': rnd.id, 'kind': 'text',
                                    'theme': 'other', 'sequence': 4,
                                    'text': 'Anything else?'})
        type(self)._rounds.append(rnd.id)
        return rnd

    def open_round(self, **kw):
        rnd = self.make_round(**kw)
        rnd.action_open()
        return rnd

    def answer(self, rnd, emp, scale=4, enps=9, text='', choice=None):
        answers = {str(self.q_scale.id): scale, str(self.q_enps.id): enps}
        if choice is not None:
            answers[str(self.q_choice.id)] = choice
        comments = {}
        if text and getattr(self, 'q_text', None) and \
                self.q_text.round_id == rnd:
            comments[str(self.q_text.id)] = text
        r = self.as_person(emp, self.Round).browse(rnd.id)
        return r.voice_submit(emp, answers, comments)

    def close(self, rnd):
        self.as_hr(self.Round).browse(rnd.id).action_close()
        # what the commit would do: destroy the key and the sealed files
        self.Box._voice_destroy(rnd.id)

    def _assert_no_small_differences(self, rnd):
        sealed = self.Voice._sealed(rnd)
        n_of = {c: v['n'] for c, v in sealed['cells'].items()}
        groups, cells_of, resp, visible = self.Voice._plan(rnd, sealed)
        floor = rnd.floor
        for a in visible:
            for b in visible:
                if a == b or not (cells_of[a] & cells_of[b]):
                    continue
                diff = sum(n_of[c] for c in cells_of[a] - cells_of[b])
                self.assertFalse(0 < diff < floor, (a, b, diff))
        # parts of one kind AND any mix of kinds (VC1: HR sees all three)
        import itertools
        all_kinds = ('company', 'department', 'team')
        for p in visible:
            for size in (1, 2, 3):
                for kinds in itertools.combinations(all_kinds, size):
                    kids = [g for g in visible if g != 'all' and g != p
                            and groups[g].kind in kinds
                            and cells_of[g] <= cells_of[p]]
                    if not kids:
                        continue
                    left = cells_of[p] - frozenset().union(
                        *(cells_of[k] for k in kids))
                    rem = sum(n_of[c] for c in left)
                    self.assertFalse(0 < rem < floor, (p, kinds, rem))
                    if len(kinds) == 1 and kinds[0] != 'company':
                        # disjoint siblings: plain subtraction too
                        rem2 = resp[p] - sum(resp[k] for k in kids)
                        self.assertFalse(0 < rem2 < floor, (p, kinds, rem2))
