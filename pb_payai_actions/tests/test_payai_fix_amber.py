# -*- coding: utf-8 -*-
"""PAYAI FIX-1, cluster B (Amber) — one test per confirmed P3 review finding:
wf-1, wf-2, wf-3, wf-4, wf-5, wf-6, wf-7, wf-11, crit-3
(`docs/handovers/payai/review/P3_REVIEW.json`).

Same rules as P1–P4: every gate is judged for an explicit user (PA12), no AI
provider is reached (the phrase table carries every sentence), fixtures use
2031 (PA40), and the P3 fixtures are reached through their module (PA56).

The status filter is NOT patched out here (wf-5): the population is the real
`_eligible_employees`, narrowed to this file's people, with the feed's
employment statuses stubbed at their source (`_employee_signals`).
"""
import json
from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from odoo.addons.pb_payai_actions.payai import registry
from odoo.addons.pb_payai_actions.payai.registry import ACTIONS
from odoo.addons.pb_payai_actions.payai.resolve import parse_period, resolve_scheme
from odoo.addons.pb_payai_actions.payai.runner import Ctx
# Through the module: a class imported by name would be collected twice.
from odoo.addons.pb_payai_actions.tests import test_payai_p3 as p3

STATUSES = [
    {'value': 'Active', 'label': 'Active', 'default': True},
    {'value': 'Thử việc', 'label': 'Thử việc', 'default': True},
    {'value': 'Resigned', 'label': 'Resigned', 'default': False},
    {'value': 'Đang làm việc', 'label': 'Đang làm việc', 'default': True},
    {'value': 'Probation', 'label': 'Probation', 'default': True},
]


@tagged('post_install', '-at_install', 'payai')
class TestPayaiFixAmber(p3._P3Case):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Config = cls.env.get('hr.formula.config')
        if Config is not None:
            def cfg(name, code):
                return Config.create({'name': name, 'code': code, 'country_code': 'VN',
                                      'state': 'active', 'company_id': cls.company.id})
            # Every scheme here shares "Payai" with every person here — the
            # one-shared-word trap of wf-1.
            cls.office = cfg('Payai Lương khối văn phòng', 'PAYAIVP')
            cls.pfp = cfg('Payai Pay for Performance', 'PAYAIPFP')
        Emp = cls.env['hr.employee']

        def person(name, **extra):
            emp = Emp.create(dict({'name': name, 'company_id': cls.company.id}, **extra))
            cls.env['hr.contract'].create({
                'name': '%s contract' % name, 'employee_id': emp.id, 'wage': 1000.0,
                'state': 'open', 'date_start': '2020-01-01', 'company_id': cls.company.id})
            return emp
        cls.an = person('Payai Nguyễn Văn An')
        cls.may = person('Payai Nguyễn Thị Mây')
        cls.thu = person('Payai Nguyễn Thị Thu')
        cls.lam = person('Payai Trần Văn Lâm')
        # Not in the run's people unless a test adds him (`self.ours`): his
        # given name is the last word of "Payai Lương khối văn phòng".
        cls.phong = person('Payai Trần Thanh Phong')
        if 'departure_date' in Emp._fields:
            try:
                with cls.env.cr.savepoint():
                    cls.lam.write({'departure_date': '2031-05-31'})
            except Exception:                           # noqa: BLE001
                pass        # the note then says "is marked Resigned" instead

    def setUp(self):
        super().setUp()
        Wizard = self.registry['pb.payrun.wizard']
        real = self.real_eligible
        self.ours = {self.e1.id, self.e2.id, self.chi.id,
                     self.an.id, self.may.id, self.thu.id, self.lam.id}
        ours = self.ours

        def eligible(self_, statuses=None, employee_ids=None, formula_config_id=None,
                     date_start=None, date_end=None):
            # The wizard's own filter (statuses and shortlist), narrowed to
            # this file's people — never the stub's opinion.
            return [e for e in real(self_, statuses=statuses, employee_ids=employee_ids,
                                    formula_config_id=formula_config_id,
                                    date_start=date_start, date_end=date_end)
                    if e in ours]
        signals = {e: {'status': 'Active', 'hours': 0.0} for e in ours}
        signals[self.lam.id] = {'status': 'Resigned', 'hours': 0.0}
        for p in (patch.object(Wizard, '_eligible_employees', eligible),
                  patch.object(Wizard, '_employee_signals', lambda self_: dict(signals)),
                  patch.object(Wizard, 'employment_status_options',
                               lambda self_: [dict(s) for s in STATUSES])):
            p.start()
            self.addCleanup(p.stop)

    # -------------------------------------------------------------- helpers
    def _ctx(self, user=None, scheme=None):
        ctx = Ctx(self.env['payroll.ai.engine'].with_user(user or self.officer), {})
        if scheme is not None:
            ctx.params = {'scheme': {'value': scheme.id}}
        return ctx

    def _norm(self, texts):
        return ACTIONS['run_payroll'].normalise_texts(self._ctx(), dict(texts))

    def _people(self, text, scheme=None):
        RP = ACTIONS['run_payroll']
        slot = next(s for s in RP.slots if s.key == 'people')
        return RP.resolve_slot(self._ctx(scheme=scheme or self.retail_end), slot, text)

    def _slots(self, card):
        return {s['key']: s for s in card['slots']}

    # ================================================================ wf-1
    def test_wf1_a_name_sharing_one_word_with_a_scheme_stays_a_person(self):
        RP = ACTIONS['run_payroll']
        # "Payai" is in every scheme's name; one shared word is not a scheme.
        self.assertFalse(RP._covers_scheme(self._ctx(), 'Payai Nguyễn Văn An'))
        self.assertTrue(RP._covers_scheme(self._ctx(), 'Payai Lương khối văn phòng'))
        texts = self._norm({'period': 'December 2031', 'scheme': 'Payai Nguyễn Văn An only'})
        self.assertEqual((texts['scheme'], texts['people']), ('', 'Payai Nguyễn Văn An only'))
        texts = self._norm({'period': 'December 2031',
                            'scheme': 'Payai Lương khối văn phòng for Payai Nguyễn Văn An only'})
        self.assertEqual((texts['scheme'], texts['people']),
                         ('Payai Lương khối văn phòng', 'Payai Nguyễn Văn An only'))
        # End to end: the plan names him, never "All N covered by this scheme".
        card, _s = self._send(
            self.officer, 'Run December 2031 payroll for Payai Retail End-Month '
                          'for Payai Nguyễn Văn An only')
        self.assertEqual(card['kind'], 'plan', card)
        people = self._slots(card)['people']
        self.assertTrue(people['value_label'].startswith('Payai Nguyễn Văn An (1 of '), people)
        self.assertEqual(json.loads(self._task(card).params_json)['vals']['employee_ids'],
                         [self.an.id])

    def test_wf1_one_name_word_a_scheme_also_has_is_the_person(self):
        # Second pass: "Phong" is Trần Thanh Phong's name AND the last word
        # of "Lương khối văn phòng". Before: scheme "Phong" → that scheme,
        # 'said', the person dropped and the plan covering everyone.
        self.ours.add(self.phong.id)
        RP = ACTIONS['run_payroll']
        ctx = self._ctx()
        self.assertTrue(RP._covers_scheme(ctx, 'Phong'))
        self.assertFalse(RP._covers_scheme(ctx, 'Phong', whole=True))
        self.assertTrue(RP._covers_scheme(ctx, 'Payai Lương khối văn phòng', whole=True))
        for said in ('Phong only', 'Phong'):
            texts = self._norm({'period': 'December 2031', 'scheme': said})
            self.assertEqual((texts['scheme'], texts.get('people')), ('', said), said)
        texts = self._norm({'scheme': 'Phong for December 2031'})
        self.assertEqual((texts['scheme'], texts['period'], texts['people']),
                         ('', 'December 2031', 'Phong'))
        texts = self._norm({'period': 'December 2031',
                            'scheme': 'Payai Retail End-Month for Phong only'})
        self.assertEqual((texts['scheme'], texts['people']),
                         ('Payai Retail End-Month', 'Phong only'))
        # The scheme named in full is still the scheme.
        texts = self._norm({'period': 'December 2031',
                            'scheme': 'Payai Lương khối văn phòng only'})
        self.assertEqual(texts['scheme'], 'Payai Lương khối văn phòng')
        self.assertFalse(texts.get('people'))
        res = self._people('Phong only')
        self.assertEqual((res['status'], res['value']['employee_ids'], res['origin']),
                         ('resolved', [self.phong.id], 'assumed'))
        # End to end: never the office scheme "said" for everyone.
        card, _s = self._send(self.officer, 'Run December 2031 payroll for Phong only')
        scheme = {r['key']: r for r in card.get('slots') or []}.get('scheme') or {}
        self.assertFalse(scheme.get('value_label') == 'Payai Lương khối văn phòng'
                         and scheme.get('origin') == 'said', card)

    # ================================================================ wf-2
    def test_wf2_a_scheme_name_with_for_stays_whole(self):
        texts = self._norm({'period': 'June 2031', 'scheme': 'Payai Pay for Performance'})
        self.assertEqual(texts['scheme'], 'Payai Pay for Performance')
        self.assertFalse(texts.get('people'))
        texts = self._norm({'period': 'June 2031',
                            'scheme': 'Payai Pay for Performance for Vũ Khánh Chi only'})
        self.assertEqual((texts['scheme'], texts['people']),
                         ('Payai Pay for Performance', 'Vũ Khánh Chi only'))
        card, _s = self._send(self.officer, 'Run June 2031 payroll for Payai Pay for Performance')
        self.assertNotIn('could not find', json.dumps(card))
        self.assertEqual(card['kind'], 'plan', card)
        self.assertEqual(self._slots(card)['scheme']['value_label'], 'Payai Pay for Performance')

    def test_wf2_a_month_riding_on_a_for_scheme_keeps_it_whole(self):
        # FIX-1 third pass: the month at either end of a scheme name with
        # "for" in it is the period — "Pay" alone is never the scheme and
        # "Performance December" never a person.
        for said in ('Payai Pay for Performance December 2031',
                     'December 2031 Payai Pay for Performance'):
            texts = self._norm({'scheme': said})
            self.assertEqual(texts['scheme'], 'Payai Pay for Performance', texts)
            self.assertIn('December 2031', texts.get('period') or '', texts)
            self.assertFalse(texts.get('people'), texts)
        texts = self._norm({'scheme': 'Payai Pay for Performance June 2031 for Vũ Khánh Chi only'})
        self.assertEqual((texts['scheme'], texts['people']),
                         ('Payai Pay for Performance', 'Vũ Khánh Chi only'))
        self.assertIn('June 2031', texts.get('period') or '', texts)
        card, _s = self._send(self.officer,
                              'Run payroll for Payai Pay for Performance December 2031')
        self.assertNotIn('could not find', json.dumps(card))
        self.assertEqual(card['kind'], 'plan', card)
        self.assertEqual(self._slots(card)['scheme']['value_label'], 'Payai Pay for Performance')

    def test_wf2_just_for_is_one_cut(self):
        # "… just for Chi" left "for Chi" as the person's name.
        for said in ('Payai Retail End-Month just for Vũ Khánh Chi',
                     'Payai Retail End-Month only for Vũ Khánh Chi',
                     'Payai Retail End-Month just with Vũ Khánh Chi'):
            texts = self._norm({'period': 'June 2031', 'scheme': said})
            self.assertEqual((texts['scheme'], texts['people']),
                             ('Payai Retail End-Month', 'Vũ Khánh Chi'), said)

    def test_wf2_with_a_wish_is_not_taken_for_a_person(self):
        # "with overtime" is nobody's name and no status: the run is not
        # quietly run without it, and the reply says what a run can narrow to.
        texts = self._norm({'period': 'June 2031',
                            'scheme': 'Payai Retail End-Month with overtime'})
        self.assertEqual(texts['scheme'], 'Payai Retail End-Month')
        card, _s = self._send(self.officer,
                              'Run June 2031 payroll for Payai Retail End-Month with overtime')
        self.assertNotEqual(card['kind'], 'plan', card)
        self.assertIn('can only be narrowed to people or an employment status', json.dumps(card))
        # People and statuses after "with" still read as before.
        self.assertEqual(self._norm({'period': 'June 2031',
                                     'scheme': 'Payai Retail End-Month with Vũ Khánh Chi'})
                         ['people'], 'Vũ Khánh Chi')
        card, _s = self._send(self.officer,
                              'Run June 2031 payroll for Payai Retail End-Month for Payai Quang Nobody')
        self.assertNotIn('can only be narrowed', json.dumps(card))

    # ================================================================ wf-3
    def test_wf3_scheme_only_resolves_without_a_question(self):
        texts = self._norm({'period': 'June 2031', 'scheme': 'Payai Retail End-Month only'})
        self.assertEqual(texts['scheme'], 'Payai Retail End-Month')
        self.assertFalse(texts.get('people'))
        card, _s = self._send(self.officer, 'Run June 2031 payroll for Payai Retail End-Month only')
        self.assertEqual(card['kind'], 'plan', card)
        slots = self._slots(card)
        self.assertEqual(slots['scheme']['value_label'], 'Payai Retail End-Month')
        self.assertEqual(slots['scheme']['origin'], 'said')
        self.assertEqual(slots['people']['origin'], 'default')

    def test_wf3_scheme_only_with_people_in_their_own_slot(self):
        """FIX-1 fifth pass: when the people come in their own slot (the model
        fills the slots), "<scheme> only" and "<scheme> for May only" lose
        their "only" too — the scheme resolves without a question and the
        period is the month's own words, never the whole text."""
        later = date(2031, 7, 1)
        for said, scheme, period in (
                ('Payai Retail End-Month only', 'Payai Retail End-Month', None),
                ('Payai Retail End-Month just', 'Payai Retail End-Month', None),
                ('only Payai Retail End-Month', 'Payai Retail End-Month', None),
                ('Payai Retail End-Month for May only', 'Payai Retail End-Month', 'May'),
                ('Payai Retail End-Month for May 2031 only', 'Payai Retail End-Month',
                 'May 2031'),
                ('Payai Retail End-Month for May', 'Payai Retail End-Month', 'May'),
                ('June Payai Retail End-Month only', 'Payai Retail End-Month', 'June')):
            texts = self._norm({'scheme': said, 'people': 'Vũ Khánh Chi'})
            self.assertEqual((texts['scheme'], texts.get('period')), (scheme, period),
                             (said, texts))
            self.assertEqual(texts['people'], 'Vũ Khánh Chi', (said, texts))
            r = resolve_scheme(self._ctx(), texts['scheme'])
            self.assertEqual((r['status'], r.get('value')), ('resolved', self.retail_end.id),
                             (said, r))
            if period:
                got = parse_period(texts['period'], later)
                self.assertTrue(got, (said, texts))
                self.assertEqual(got[0].month, 5 if 'May' in period else 6, said)
        # A period the person gave is kept as given.
        texts = self._norm({'scheme': 'Payai Retail End-Month only', 'people': 'Vũ Khánh Chi',
                            'period': 'June 2031'})
        self.assertEqual((texts['scheme'], texts['period']),
                         ('Payai Retail End-Month', 'June 2031'), texts)

    # ================================================================ wf-4
    def test_wf4_may_the_name_is_never_the_month(self):
        texts = self._norm({'scheme': 'Payai Retail End-Month for Mây only'})
        self.assertFalse(texts.get('period'), texts)
        self.assertEqual((texts['scheme'], texts['people']),
                         ('Payai Retail End-Month', 'Mây only'))
        texts = self._norm({'scheme': 'Payai Retail End-Month for Payai Nguyễn Thị Mây'})
        self.assertFalse(texts.get('period'), texts)
        self.assertEqual((texts['scheme'], texts['people']),
                         ('Payai Retail End-Month', 'Payai Nguyễn Thị Mây'))
        # The month written as a month still is one.
        texts = self._norm({'scheme': 'Payai Retail End-Month for May 2031 for Payai Nguyễn Thị Mây'})
        self.assertEqual((texts['scheme'], texts['period'], texts['people']),
                         ('Payai Retail End-Month', 'May 2031', 'Payai Nguyễn Thị Mây'))

    def test_wf4_a_month_followed_by_only_stays_that_month(self):
        """FIX-1 fourth pass: "… for May only" kept "May only" as the period's
        words; "May" with a word after it is no month to the reader, so the
        run silently became this month's. The period keeps the bare words."""
        later = date(2031, 7, 1)
        for said, period in (('Payai Retail End-Month for May only', 'May'),
                             ('Payai Retail End-Month for may only', 'may'),
                             ('Payai Retail End-Month for May just', 'May'),
                             ('Payai Retail End-Month for June only', 'June'),
                             ('Payai Retail End-Month for May 2031 only', 'May 2031'),
                             ('Payai Retail End-Month only for May', 'May')):
            texts = self._norm({'scheme': said})
            self.assertEqual((texts['scheme'], texts.get('period')),
                             ('Payai Retail End-Month', period), (said, texts))
            self.assertFalse(texts.get('people'), (said, texts))
            got = parse_period(texts['period'], later)
            self.assertTrue(got, (said, texts))
            self.assertEqual(got[0].month, 5 if 'may' in period.lower() else 6, said)
        # A name that folds to "may" is still a person, never the month.
        texts = self._norm({'scheme': 'Payai Retail End-Month for Mây just'})
        self.assertFalse(texts.get('period'), texts)
        self.assertEqual(texts['people'], 'Mây just')
        # End to end: the plan says May 2031, not this month.
        card, _s = self._send(self.officer,
                              'Run payroll for Payai Retail End-Month for May 2031 only')
        self.assertEqual(card['kind'], 'plan', card)
        slots = self._slots(card)
        self.assertEqual(slots['period']['origin'], 'said', slots['period'])
        self.assertIn('2031', slots['period']['value_label'], slots['period'])

    # ================================================================ wf-5
    def test_wf5_a_named_leaver_is_in_the_run_and_the_card_says_so(self):
        card, _s = self._send(
            self.officer, 'Run December 2031 payroll for Payai Retail End-Month '
                          'for Payai Trần Văn Lâm only')
        self.assertEqual(card['kind'], 'plan', card)
        people = self._slots(card)['people']
        # Before: "(0 of 6)" and "This scheme covers nobody yet".
        self.assertEqual(people['value_label'], 'Payai Trần Văn Lâm (1 of 6)')
        texts = [n['text'] for n in card['notes']]
        self.assertFalse([t for t in texts if 'covers nobody' in t], texts)
        self.assertTrue([t for t in texts if t.startswith('Payai Trần Văn Lâm ')
                         and 'Resigned' in t
                         and t.endswith('They are in this run because you named them.')], texts)
        self.assertIn('do', [a['id'] for a in card['actions']])
        vals = json.loads(self._task(card).params_json)['vals']
        self.assertEqual(vals['employee_ids'], [self.lam.id])
        self.assertIn('Resigned', vals['statuses'])
        # The wizard's own filter, as Do it will run it: exactly him.
        W = self.env['pb.payrun.wizard'].with_user(self.officer)
        self.assertEqual(W.plan_preview(dict(vals))['total'], 1)
        # Somebody the usual ticks keep gets no such note, and no extra tick.
        card, _s = self._send(
            self.officer, 'Run December 2031 payroll for Payai Retail End-Month '
                          'for Vũ Khánh Chi only')
        self.assertEqual(card['kind'], 'plan', card)
        self.assertFalse([n for n in card['notes'] if 'because you named them' in n['text']])
        vals = json.loads(self._task(card).params_json)['vals']
        self.assertNotIn('Resigned', vals['statuses'])

    # ================================================================ wf-6
    def test_wf6_names_found_in_everyone_without_marks_and_not_capped(self):
        # Without marks: the same person, said in full.
        res = self._people('payai nguyen van an only')
        self.assertEqual((res['status'], res['value']['employee_ids'], res['origin']),
                         ('resolved', [self.an.id], 'said'))
        # Some of the name only: found, but never "said".
        res = self._people('Van An only')
        self.assertEqual((res['status'], res['value']['employee_ids'], res['origin']),
                         ('resolved', [self.an.id], 'assumed'))
        # Forty-five "Anh"s sort before him: the screen search's first 40 rows
        # would never have reached him.
        Emp = self.env['hr.employee']
        crowd = Emp.create([{'name': 'Payai Anh %02d' % i, 'company_id': self.company.id}
                            for i in range(45)])
        everyone = sorted(self.ours | set(crowd.ids))
        with patch.object(self.registry['pb.payrun.wizard'], '_eligible_employees',
                          lambda self_, **kw: list(everyone)):
            res = self._people('An only')
            self.assertEqual((res['status'], res['value']['employee_ids'], res['origin']),
                             ('resolved', [self.an.id], 'assumed'))
            # More matches than chips: ask for more of the name, never pick one.
            res = self._people('Payai Anh')
            self.assertEqual(res['status'], 'missing', res)
            self.assertIn('Type more of the name', res['note'])

    # ================================================================ wf-7
    def test_wf7_a_name_sharing_a_word_with_a_status_is_a_person(self):
        RP = ACTIONS['run_payroll']
        self.assertFalse(RP._status_hit(self._ctx(), 'Payai Nguyễn Thị Thu only'))
        res = self._people('Payai Nguyễn Thị Thu only')
        self.assertEqual((res['status'], res['value']['employee_ids']),
                         ('resolved', [self.thu.id]))
        # A status said in full is still a status.
        res = self._people('Thử việc only')
        self.assertEqual((res['status'], res['value']['text'], res['value']['employee_ids']),
                         ('resolved', 'Thử việc only', []))
        res = self._people('active staff only')
        self.assertEqual(res['value']['employee_ids'], [])

    def test_wf7_a_first_name_alone_is_a_person_and_statuses_still_read(self):
        # Second pass: one name word that is also a status word ("thu" of
        # "Thử việc", "lam" of "Đang làm việc") finds the person — 'assumed'.
        for said, emp in (('Thu only', self.thu), ('Lâm only', self.lam)):
            res = self._people(said)
            self.assertEqual((res['status'], res['value']['employee_ids'], res['origin']),
                             ('resolved', [emp.id], 'assumed'), said)
        card, _s = self._send(
            self.officer, 'Run December 2031 payroll for Payai Retail End-Month for Thu only')
        self.assertEqual(card['kind'], 'plan', card)
        vals = json.loads(self._task(card).params_json)['vals']
        self.assertEqual(vals['employee_ids'], [self.thu.id])
        # Statuses with the words people put around them, both languages.
        for said in ('staff on probation', 'people on probation only',
                     'nhân viên thử việc thôi', 'nhân viên đang làm việc', 'everyone'):
            res = self._people(said)
            self.assertEqual((res['status'], res['value']['employee_ids'], res['value']['text']),
                             ('resolved', [], ' '.join(said.split())), said)
        # A status said in full ticks that status alone, not every "việc".
        RP = ACTIONS['run_payroll']
        self.assertEqual(RP._statuses(self._ctx(), 'nhân viên thử việc thôi'),
                         (['Thử việc'], 'Thử việc'))
        self.assertEqual(RP._statuses(self._ctx(), 'staff on probation')[0], ['Probation'])

    # =============================================================== wf-11
    def test_wf11_an_unreadable_value_never_reads_not_set(self):
        UP = ACTIONS['update_pay_data']
        cards_ = {'c1': {'id': 'c1'}, 'f1': {'id': 'f1'}, 'c2': {'id': 'c2'}}
        test = self

        class Desk:
            page = False

            def search_people(self, config_id=0, filters=None, field_ids=None, **kw):
                if not Desk.page:
                    raise AccessError('the page')
                test.assertEqual(filters, {'employee_ids': [test.chi.id]})
                return {'rows': [{'id': test.chi.id, 'values': {
                    'c1': {'label': '500,000'}, 'c2': {'label': ''}}}]}

            def _probe(self, config_id):
                class Probe:
                    def _get_latest_contract(self, emp):
                        return False
                return Probe()

            def _read_cell(self, probe, card, emp, contract):
                if card['id'] == 'f1':
                    raise AccessError('identification_id')
                return {'label': '500,000' if card['id'] == 'c1' else ''}

        rows = [{'value': k, 'label': 'Payai %s' % k, 'words': 'Payai %s' % k}
                for k in ('c1', 'f1', 'c2')]
        ctx = self._ctx()
        with patch.object(type(UP), '_desk', lambda self_, ctx_: Desk()), \
                patch.object(type(UP), '_cards', lambda self_, ctx_, cid: cards_):
            # Records' page refused: cell by cell, one failure blanks only itself.
            self.assertEqual(UP._current_labels(ctx, self.retail_end.id, self.chi.id,
                                                ['c1', 'f1', 'c2']),
                             {'c1': '500,000', 'c2': ''})
            out = UP._closest_fields(ctx, 'Payai zz', rows, self.chi.id, self.retail_end.id)
            subs = {c['value']: c['sublabel'] for c in out['candidates']}
            self.assertEqual(subs, {'c1': 'now 500,000', 'f1': '', 'c2': 'not set'})
            # Records' own page read: what the screen shows, nothing invented.
            Desk.page = True
            self.assertEqual(UP._current_labels(ctx, self.retail_end.id, self.chi.id,
                                                ['c1', 'f1', 'c2']),
                             {'c1': '500,000', 'c2': ''})

    # ============================================================== crit-3
    def test_crit3_a_send_back_mentioning_payslips_is_a_send_back(self):
        for text in ('Send back the June 2031 Retail run because two payslips are missing',
                     'send the june run back because the payslips show the wrong overtime',
                     'Send back the back pay run because the payslips are wrong',
                     'send back the June run for approval'):
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], 'send_back_item', (text, got))
        # The comma form is no longer an email of payslips (it goes to the
        # model, which knows the send-back).
        got = registry.match('Send the June run back, the payslips are wrong')
        self.assertNotIn((got or ('',))[0], ('send_payslips', 'submit_run'))
        # The sends themselves are unchanged — "back pay" is a run's name.
        for text, key in (('Send the June 2031 payslips', 'send_payslips'),
                          ('Send the back pay payslips', 'send_payslips'),
                          ('Email the backpay payslips', 'send_payslips'),
                          ('Send the June run for approval', 'submit_run'),
                          ('Send the back pay run for approval', 'submit_run')):
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], key, (text, got))
        # Second pass: a "back" that is a name, or not the item's, is no
        # send-back; "email … back" is no send-back verb at all.
        for text, key in (('Send the Back Office run for approval', 'submit_run'),
                          ('Send the Back Office payslips', 'send_payslips'),
                          ('Send the June payslips to the back office', 'send_payslips'),
                          ('send the back-office payslips', 'send_payslips'),
                          ('Send the payslips for back office', 'send_payslips'),
                          ('Send the payslips back to me', 'send_payslips'),
                          ('Send the payslips for June, then come back', 'send_payslips'),
                          ('Send the Back Office run back because the payslips are wrong',
                           'send_back_item'),
                          ('Send the June run back to Lan because the payslips are wrong',
                           'send_back_item'),
                          ('send back the back office run', 'send_back_item')):
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], key, (text, got))
        # Third pass: ANY standalone "back" after "send" is a send-back,
        # whatever words follow it — never an email of payslips.
        for text in ('Send the June run back as two payslips are missing',
                     'Send the June Retail run back as the payslips are wrong',
                     'Send the June run back. The payslips are wrong',
                     'Send the June run back. Payslips missing.',
                     'Send the June run back please, two payslips are missing',
                     'Send the June run back for fixing, the payslips are wrong',
                     'Send the June run back for the payslips to be fixed',
                     'Send the June run back and fix the payslips',
                     'Send the June run back so they can fix the payslips',
                     'Send the Back Office run back as the payslips are wrong',
                     'Send the June payslips back',
                     # FIX-1 eighth pass: "email … back" sends back as
                     # much as "send … back" does.
                     'email the payslips back'):
            got = registry.match(text)
            self.assertNotIn((got or ('',))[0], ('send_payslips', 'submit_run'), (text, got))
        for text, key in (('Send the June payslips back to me', 'send_payslips'),
                          ('Send the June payslips to the team, then get back to me',
                           'send_payslips'),
                          ('Send the June Back Office payslips', 'send_payslips'),
                          ('send the June Retail payslips, please', 'send_payslips'),
                          ('Send the June payslips since the run is approved', 'send_payslips'),
                          ('send the back office run for approval', 'submit_run')):
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], key, (text, got))
        # End to end: the Send back card, never "Send payslips".
        card, _s = self._send(
            self.manager, 'Send back the June 2031 Payai Retail run because two payslips '
                          'are missing')
        self.assertNotEqual(card.get('subtitle'), 'Send payslips', card)
        self.assertNotEqual(card.get('title'), 'Send payslips', card)

    def test_crit3_only_a_real_send_back_refuses_send_payslips(self):
        """FIX-1 fourth pass: a "back" that belongs to somebody else ("now that
        Mai is back", "I am back", "they want them back by Friday") is an
        ordinary payslip send. Only "send back <it>" / "send <it> back …" /
        "return <it> …" is the Red send-back."""
        sends = (
            'Send the June payslips now that Mai is back',
            'Send the June payslips, I am back',
            'Send the June payslips to the staff who are back',
            'Send June payslips to staff, they want them back by Friday',
            'Send the June payslips to Mai, she is back from leave',
            'Send the June payslips to everyone and let me know when they are back',
            'Send the June payslips and send me a note back',
            'Send the June payslips once Lan is back',
            'Send the June payslips when everyone is back from leave',
            'Send the June payslips, everyone is back',
            'Send the June payslips so people have them when they get back',
            'Send out the June payslips now that Mai is back',
            'Email the June payslips now that Mai is back',
            'Send the June payslips to people who came back',
            'Send the June payslips, Mai and Lan are back',
            'Send the June payslips; we are back to normal',
            'Send the June payslips; I will check back later',
            'Send the June payslips, and report back',
            'Send the June payslips back to me please',
            'Send the June payslips back to us',
            'Send the June payslips to Back Office',
            'Send the June back pay payslips',
            'Send the June Back-Office payslips',
            'Send the payslips to the team that came back',
        )
        for text in sends:
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], 'send_payslips', (text, got))
        send_backs = (
            'Send back the June run',
            'Send the June run back',
            'Send back the June payslips',
            'Send the June payslips back',
            'Send back the June payslips because the overtime is wrong',
            'Send the June payslips back to Mai because the totals are wrong',
            'Send the June payslips back to the preparer',
            'Send the June payslips back to Retail because two are missing',
            'Send the payslips for the June run back to Mai',
            'Send the June Retail pay run back to the approver because two payslips are missing',
            'Send the June 2031 Retail End-Month pay run back because the payslips are wrong',
            'Send it back because the payslips are wrong',
            'Return the June payslips to Mai because the totals are wrong',
            'Send back the June Retail run because two payslips are missing',
            'Send the June run back because the payslips show the wrong overtime',
        )
        for text in send_backs:
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], 'send_back_item', (text, got))
        # Send-backs the phrase table leaves to the model: never a payslip
        # email, never a send for approval.
        for text in ('Send the June run back, the payslips are wrong',
                     'Send the June run back for fixing, payslips wrong',
                     'Send the June Retail run back to Mai, the payslips are wrong',
                     'Send them back, the payslips are wrong'):
            got = registry.match(text)
            self.assertNotIn((got or ('',))[0], ('send_payslips', 'submit_run'), (text, got))

    def test_crit3_a_send_back_whose_item_has_and_to_that_is_a_send_back(self):
        """FIX-1 fifth pass: words like "and", "to", "that" inside the thing
        being sent back ("the Sales and Marketing run") never turn a
        send-back into a payslip email (which cannot be undone). When "back"
        is followed by a reason, a break or the end of the sentence, it is a
        send-back whatever came before it."""
        send_backs = (
            'Send the Sales and Marketing run back because the payslips are wrong',
            'Send the June Retail and Office runs back because two payslips are missing',
            'Send the run that Mai prepared back because the payslips are wrong',
            'Send the June run that Lan prepared back because payslips are wrong',
            'Send the Office and Admin run back because payslips missing',
            'Send the June run to Mai back because the payslips are wrong',
            'Send the Sales and Marketing payslips back',
            'Send the Sales and Marketing run back',
            'Send the Sales and Marketing run back: the payslips are wrong',
            'Send the Sales and Marketing run back - the payslips are wrong',
            'Send the Sales and Marketing run back — the payslips are wrong',
            'Send the Sales and Marketing run back since the payslips are wrong',
            'Send the Sales and Marketing run back to Mai because the payslips are wrong',
            'Send the Sales and Marketing payslips back to the preparer',
            'Send the Sales and Marketing run back to the preparer because two payslips '
            'are missing',
            'Send the Sales & Marketing run back because the payslips are wrong',
            'Send the run I prepared back because the payslips are wrong',
            'Send them back because the payslips are wrong',
        )
        for text in send_backs:
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], 'send_back_item', (text, got))
        # Send-backs the phrase table leaves to the model: never a payslip
        # email, never a send for approval.
        for text in ('Send the Sales and Marketing run back as the payslips are wrong',
                     'Send the Sales and Marketing payslips back please',
                     'Send the Sales and Marketing payslips back now',
                     'Send the Sales and Marketing run back, the payslips are wrong',
                     'Send the Sales and Marketing run back for fixing, the payslips are wrong',
                     'Send the Sales and Marketing run back and fix the payslips',
                     'Send the Sales and Marketing run back so they can fix the payslips',
                     'Send the run that Mai prepared back so she can fix the payslips',
                     'Send the June run to Mai back, the payslips are wrong'):
            got = registry.match(text)
            self.assertNotIn((got or ('',))[0], ('send_payslips', 'submit_run'), (text, got))
        # Still ordinary payslip sends: "back" is somebody's ("is back",
        # "came back", "Mai's back"), a place ("at the back"), or another
        # order ("call me back", "I want them back").
        for text in ('Send the June payslips for the people at the back',
                     'Send the June payslips to the people sitting at the back',
                     'Send the June payslips and call me back',
                     'Send the June payslips and text me back',
                     'Send the June payslips and get them back',
                     'Send the June payslips, I want them back',
                     'Send the June payslips now Mai is back',
                     "Send the June payslips now that Mai's back",
                     "Send the June payslips as they're back",
                     'Send the June payslips because Lan is back',
                     'Send the June payslips to Lan and Mai since they are back',
                     'Send the June payslips to Mai and Lan who are back',
                     'Send the June payslips and I will be back',
                     'Send the June payslips before Mai goes back',
                     'Send the June payslips and I am heading back',
                     'Send the June payslips to the staff who are back now',
                     'Send the June payslips to people coming back now',
                     'Send the June payslips to everyone back from leave',
                     'Send the June payslips to the back row',
                     'Send the June payslips so they get back to work'):
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], 'send_payslips', (text, got))
        # Sends for approval are unchanged.
        for text in ('Send the Sales and Marketing run for approval',
                     'Send the Back Office run for approval'):
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], 'submit_run', (text, got))

    def test_crit3_a_word_before_back_that_says_who_is_back_is_a_payslip_send(self):
        """FIX-1 sixth pass: in a long sentence ("to", "who", "when" … in
        it) "back" is a send-back only when the words right before it end the
        thing being sent ("the Sales and Marketing run", "the run Lan made",
        "the June run to Mai"). A word that says how or when somebody is back
        ("now", "just", "finally", "not yet", "two weeks"), or a time ago ("from
        two months back"), keeps an ordinary payslip send."""
        for text in ('Send the June payslips to everyone who is now back',
                     'Send the June payslips to the staff that are finally back',
                     'Send the June payslips to the drivers who are already back',
                     'Send the payslips when the team is all back',
                     'Send the June payslips to Mai since she is finally back',
                     'Send the June payslips to people just back',
                     'Send the June payslips to the people who are safely back',
                     'Send the June payslips to staff now back',
                     'Send payslips to staff who are fully back, please',
                     'Send the payslips to the team when they are all back.',
                     'Send the June payslips to Mai who is also back',
                     'Send the June payslips to staff recently back',
                     'Send the June payslips to the workers newly back',
                     'Send the June payslips to returning staff and anyone else back',
                     'Send the June payslips to employees not yet back',
                     'Send the June payslips to employees still not back',
                     'Send the June payslips to staff two weeks back',
                     'Send the June payslips to the warehouse staff round back',
                     'Send June payslips to the back',
                     'Send the June payslips to anyone back',
                     'Send the June payslips to the whole team back',
                     'Send the June payslips to everyone and bring them back',
                     'Send the payslips from two months back',
                     'Send the payslips from a month back',
                     'Send me the payslips from three months back',
                     'Send the payslips from 2 months back please',
                     'Send the payslips from one week back please',
                     'Send the payslips from a while back'):
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], 'send_payslips', (text, got))
        # Still send-backs: the thing sent ends right before "back".
        for text in ('Send the June run straight back because payslips are missing',
                     'Send the June payslips straight back',
                     'Send it straight back because the payslips are wrong',
                     'Send the payslips from last month back because two are wrong',
                     'Send the June run Lan made back because the payslips are wrong',
                     'Send the run that the preparer set up back because payslips are wrong',
                     'Send the June run to the preparer back because the payslips are wrong',
                     'Send the June payslips that Lan approved back because two are wrong',
                     'Send the June run and the July run back because the payslips are wrong',
                     'Send the June and July runs back because payslips missing'):
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], 'send_back_item', (text, got))

    def test_crit3_a_vietnamese_send_back_is_never_a_payslip_send(self):
        """FIX-1 sixth pass (the Vietnamese half of crit-3): "trả lại" /
        "trả về" in a sentence about payslips sends something back — never
        an email of the payslips or a send for approval. Plain sends and
        "trả lời" (answer) / "trở lại" (come back) are unchanged."""
        for text in ('Gửi phiếu lương tháng 6 trả lại cho Mai vì sai',
                     'gui phieu luong thang 6 tra lai cho Mai vi sai',
                     'Gửi phiếu lương tháng 6 trả về cho người lập vì thiếu hai phiếu',
                     'Gửi bảng lương tháng 6 trả lại cho chị Hoa duyệt'):
            got = registry.match(text)
            self.assertNotIn(got and got[0], ('send_payslips', 'submit_run'), (text, got))
        for text, key in (('Gửi phiếu lương tháng 6', 'send_payslips'),
                          ('gui phieu luong thang 6', 'send_payslips'),
                          ('Gửi phiếu lương tháng 6 và trả lời Mai', 'send_payslips'),
                          ('Gửi phiếu lương tháng 6 cho nhân viên đã trở lại làm việc',
                           'send_payslips'),
                          ('Gửi bảng lương tháng 6 đi duyệt', 'submit_run'),
                          ('Trả lại bảng lương tháng 6 vì sai', 'send_back_item'),
                          ('Gửi trả bảng lương tháng 6 vì sai', 'send_back_item')):
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], key, (text, got))

    def test_wf4_a_month_leading_the_scheme_or_a_polite_word_keeps_the_month(self):
        """FIX-1 sixth pass: "May Retail End-Month only" is the month May and
        the scheme — never a person called "May Retail End-Month"; "… for May
        only please" keeps May (the polite word is nobody's name)."""
        for said, period in (('May Payai Retail End-Month only', 'May'),
                             ('may Payai Retail End-Month only', 'may'),
                             ('May Payai Retail End-Month', 'May'),
                             ('Payai Retail End-Month for May only please', 'May'),
                             ('Payai Retail End-Month for May please', 'May')):
            texts = self._norm({'scheme': said})
            self.assertEqual((texts['scheme'], texts.get('period')),
                             ('Payai Retail End-Month', period), (said, texts))
            self.assertFalse(texts.get('people'), (said, texts))
        texts = self._norm({'scheme': 'Payai Retail End-Month please'})
        self.assertEqual(texts['scheme'], 'Payai Retail End-Month', texts)
        self.assertFalse(texts.get('people'), texts)
        # A name that folds to "may" leading the words is still no month.
        texts = self._norm({'scheme': 'Mây Payai Retail End-Month'})
        self.assertFalse(texts.get('period'), texts)

    # ======================================================= seventh pass
    def test_wf4_scheme_words_before_payroll_keep_the_said_month(self):
        """FIX-1 seventh pass (regression of the wf-4 fix): "Run Retail
        End-Month payroll for May" puts the scheme's words where the month
        goes and the month where the scheme goes. The scheme was blanked and
        the month thrown away — a ready plan for this month on the default
        scheme. The words that are no month now go to the scheme."""
        for texts, scheme, period, people in (
                ({'period': 'Payai Retail End-Month', 'scheme': 'May'},
                 'Payai Retail End-Month', 'May', ''),
                ({'period': 'Payai Retail End-Month', 'scheme': 'June'},
                 'Payai Retail End-Month', 'June', ''),
                ({'period': 'Payai Retail End-Month', 'scheme': 'May only'},
                 'Payai Retail End-Month', 'May', ''),
                ({'period': 'Payai Pay for Performance', 'scheme': 'May only'},
                 'Payai Pay for Performance', 'May', ''),
                ({'period': 'Payai Retail End-Month', 'scheme': 'tháng 5'},
                 'Payai Retail End-Month', 'tháng 5', ''),
                ({'period': 'Payai Retail End-Month', 'scheme': 'tháng 5 thôi'},
                 'Payai Retail End-Month', 'tháng 5', ''),
                ({'period': 'June 2031 Payai Retail End-Month'},
                 'Payai Retail End-Month', 'June 2031', ''),
                ({'period': 'Payai Retail End-Month'}, 'Payai Retail End-Month', '', ''),
                ({'period': 'Payai Retail End-Month', 'scheme': 'May 2031 for Payai Nguyễn Thị Mây'},
                 'Payai Retail End-Month', 'May 2031', 'Payai Nguyễn Thị Mây'),
                # The model's slots: the people in their own slot.
                ({'period': 'Payai Retail End-Month', 'scheme': 'May', 'people': 'Payai Nguyễn Văn An'},
                 'Payai Retail End-Month', 'May', 'Payai Nguyễn Văn An')):
            got = self._norm(texts)
            self.assertEqual((got.get('scheme'), got.get('period') or '', got.get('people') or ''),
                             (scheme, period, people), (texts, got))
        # A name in the month's place is a person; the month is kept.
        got = self._norm({'period': 'Payai Nguyễn Thị Mây', 'scheme': 'May 2031'})
        self.assertEqual((got.get('period'), got.get('people')), ('May 2031', 'Payai Nguyễn Thị Mây'))
        # Words before "payroll" that are no scheme stay as they were.
        for said in ('monthly', 'my', "this month's", 'June 2031'):
            got = self._norm({'period': said})
            self.assertEqual(got.get('period'), said, got)
            self.assertFalse(got.get('scheme'), got)
        # End to end: the month said and the scheme said, never the defaults.
        for text in ('Run Payai Retail End-Month payroll for September 2031',
                     'Run the Payai Retail End-Month payroll for September 2031 only'):
            card, _s = self._send(self.officer, text)
            self.assertEqual(card['kind'], 'plan', (text, card))
            slots = self._slots(card)
            self.assertEqual(slots['period']['origin'], 'said', (text, slots['period']))
            self.assertIn('2031', slots['period']['value_label'], (text, slots['period']))
            self.assertIn('September', slots['period']['value_label'], (text, slots['period']))
            self.assertEqual(slots['scheme']['value_label'], 'Payai Retail End-Month', text)
            self.assertEqual(slots['scheme']['origin'], 'said', text)

    def test_crit3_any_send_back_with_a_reason_is_never_a_payslip_send(self):
        """FIX-1 seventh pass: a send-back whose thing ends in a word the
        lists said could not come before "back" ("sent", "me", "all", "that",
        "is" …) still opened Send payslips, and "email/mail/deliver … back to
        Mai because …" had no guard at all. A reason after a standalone
        "back" now keeps the sentence off Send payslips."""
        send_backs = (
            'Send it all back because the payslips are wrong',
            'Send the June run you sent back because two payslips are missing',
            'Send the June run Mai sent in back because payslips are wrong',
            'Send the June run Mai gave me back because the payslips are wrong',
            'Send the run waiting for me back because the payslips are wrong',
            'Send the run that is waiting on me back because the payslips are wrong',
            'Send the June run (the one Mai sent) back because payslips are wrong',
            'Send the June run Lan sent over back because payslips are wrong',
            'Send the run that came in from Mai back because the payslips are wrong',
            'Send the June run to be fixed back because of the payslips',
            'Send the payslips for everyone back because they are wrong',
            'Send the payslips for the people in Retail back to Mai',
        )
        for text in send_backs:
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], 'send_back_item', (text, got))
        # Left to the model (which knows the send-back): never a payslip email.
        for text in send_backs + (
                'Send that back, the payslips are wrong',
                'Send the June run Mai needs to fix back, payslips wrong',
                'Email the June payslips back to Mai because they are wrong',
                'Mail the June payslips back to Mai because they are wrong',
                'Deliver the June payslips back to the preparer, they are wrong',
                'Email back the June payslips because they are wrong'):
            got = registry.match(text)
            self.assertNotIn((got or ('',))[0], ('send_payslips', 'submit_run'), (text, got))
        # Ordinary payslip sends — "back" is somebody's, a place, or a time —
        # even with a reason or a fix word in the sentence.
        for text in ('Send the June payslips for staff back from leave',
                     'Send the June payslips for people back at work',
                     'Send the June payslips for the team back from leave',
                     'Send the June payslips - Mai back Monday',
                     'Email the June payslips - Mai back Monday',
                     'Send the June payslips now that Mai is back and fixed them',
                     "Send the June payslips, I'm back and the mistakes are fixed",
                     'Send the June payslips; Mai came back and corrected the errors',
                     'Send the June payslips to the staff at the back, the errors are fixed',
                     'Send the June payslips to the people at the back because they missed out',
                     'Send the June payslips from two weeks back, the errors are fixed',
                     'Email the June payslips to everyone who got back, the mistakes are fixed',
                     'Send the June payslips, Mai is back because her leave ended',
                     'Send the fixed June payslips with the back pay',
                     'Send the Back Office payslips, the errors are fixed',
                     'Email the June payslips now that Mai is back',
                     'Email the June payslips back to me',
                     'Email the back pay payslips'):
            got = registry.match(text)
            self.assertTrue(got, text)
            self.assertEqual(got[0], 'send_payslips', (text, got))

    # ======================================================== eighth pass
    def test_wf4_month_phrase_words_stay_in_the_period(self):
        """FIX-1 eighth pass (regressions of the seventh): the words of the
        month phrase itself ("the end of May", "mid-month", "cuối tháng 5",
        "kỳ 1", "June and July", "2031") moved to the scheme, the real scheme
        was cut off and read as a person's name, and the plan was refused —
        on the phrase path AND on the model's and the pencil's slots. They
        stay in the period now; only words that are no part of a month
        phrase move, and only the ones around them that one scheme covers."""
        # The model's / the pencil's slots: nothing moves.
        for period in ('the month of May 2031', 'May month', 'month of May 2031',
                       'May of this year', 'end of May 2031', 'mid May 2031',
                       'early May 2031', 'May 1 to May 31', '1-31 May 2031',
                       'pay period May 2031', 'the May period', 'this pay period',
                       "this pay period's", 'cuối tháng 5', 'giữa tháng 5',
                       'kỳ 1 tháng 5', 'đợt 2 tháng 5', 'tháng 5 năm 2031',
                       "June '31", 'June and July', '2031', '13th month',
                       'mid-month', 'end-month', 'end of month'):
            for scheme in ('Payai Retail End-Month', 'Payai Retail'):
                got = self._norm({'period': period, 'scheme': scheme})
                self.assertEqual((got.get('period'), got.get('scheme')), (period, scheme),
                                 (period, scheme, got))
                self.assertFalse(got.get('people'), (period, scheme, got))
        # The phrase path: the month phrase stays whole, the scheme is read.
        for text, period, scheme in (
                ('Run the end of May 2031 payroll for Payai Retail End-Month',
                 'end of May 2031', 'Payai Retail End-Month'),
                ('Run the May 2031 month payroll for Payai Retail End-Month',
                 'May 2031 month', 'Payai Retail End-Month'),
                ("Run June '31 payroll for Payai Retail End-Month",
                 "June '31", 'Payai Retail End-Month'),
                ('Run June and July payroll for Payai Retail End-Month',
                 'June and July', 'Payai Retail End-Month'),
                ('Chạy lương cuối tháng 5 cho Payai Retail End-Month',
                 'cuối tháng 5', 'Payai Retail End-Month'),
                ('Chạy lương kỳ 1 tháng 5 cho Payai Retail End-Month',
                 'kỳ 1 tháng 5', 'Payai Retail End-Month'),
                # Not joined with "for": the two halves are one scheme.
                ('Run mid-month payroll for Payai Retail', 'mid-month', 'Payai Retail'),
                ('Run Payai Retail payroll for Mid-Month', '', 'Payai Retail Mid-Month'),
                ('Run Payai Retail Mid-Month payroll for May 2031',
                 'May 2031', 'Payai Retail Mid-Month'),
                ('Run end of May 2031 Payai Retail End-Month payroll',
                 'end of May 2031', 'Payai Retail End-Month'),
                # A month phrase after "payroll" is no person either.
                ('Run payroll for Payai Retail End-Month for the month of May 2031',
                 'the month of May 2031', 'Payai Retail End-Month'),
                ('Run Payai Retail End-Month payroll for the end of May 2031',
                 'the end of May 2031', 'Payai Retail End-Month')):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
            texts = self._norm(got[1])
            self.assertEqual((texts.get('period') or '', texts.get('scheme')),
                             (period, scheme), (text, texts))
            self.assertFalse(texts.get('people'), (text, texts))
        # End to end: a plan for the month and the scheme said, no person.
        card, _s = self._send(self.officer,
                              'Run the end of September 2031 payroll for Payai Retail End-Month')
        self.assertEqual(card['kind'], 'plan', card)
        slots = self._slots(card)
        self.assertIn('September', slots['period']['value_label'], slots['period'])
        self.assertIn('2031', slots['period']['value_label'], slots['period'])
        self.assertEqual(slots['scheme']['value_label'], 'Payai Retail End-Month', slots)
        self.assertNotEqual((slots.get('people') or {}).get('origin'), 'said', slots)

    def test_crit3_a_send_back_with_any_reason_or_none_is_never_a_payslip_send(self):
        """FIX-1 eighth pass: a send-back whose reason has none of the fix
        words still reached Send payslips ("Send it all back, the payslips
        show last month's rates" → run "it all back, the"), and "Email the
        June payslips back to Mai to update" offered to email an approved
        run's payslips. A "back" before the payslips, or "email … back", now
        keeps the sentence off Send payslips."""
        for text in (
                "Send it all back, the payslips show last month's rates",
                'Send them all back as the payslips have the old overtime rate',
                "Send that back, payslips aren't right",
                "Send the stuff that's waiting back, the payslips are off",
                'Send the run Mai sent in back, the payslips need another look',
                'Send the June run you sent me back, payslips have old rates',
                'Send what Mai sent back to her, two payslips have old rates',
                "Send the one that's pending back, payslips look off",
                'Send the June run that is pending back to Mai, payslips have old rates',
                'Send all that back, the payslips show the old rate',
                'Send all back, payslips show old rates',
                "Send the run that's waiting on me back, payslips need updating",
                'Send everyone back from leave their June payslips',
                'Email the June payslips back to Mai to update',
                'Email the June payslips back to Mai please',
                'Mail the June payslips back to Mai',
                'Deliver the June payslips back to Mai, she needs to redo them',
                'Email it all back, the payslips are off',
                'Email them all back, payslips have old rates'):
            got = registry.match(text)
            self.assertNotIn((got or ('',))[0], ('send_payslips', 'submit_run'), (text, got))
        # A "back" that is a name, or comes after the payslips and is
        # somebody's, is still an ordinary payslip send.
        for text, run in (('Send the back pay payslips for June', 'back pay'),
                          ('Send the back-pay payslips', 'back-pay'),
                          ('Send the Back Office payslips', 'Back Office'),
                          ('Send out the payback payslips', 'payback'),
                          ('Email the June payslips now that Mai is back', 'June'),
                          ('Email the June payslips to the staff who are back from leave',
                           'June'),
                          ('Email the June payslips and call me back', 'June'),
                          ('Email the June payslips back to me', 'June'),
                          ('Send the June payslips to Mai, then come back to me', 'June'),
                          ("Send the June payslips, Mai's back and fixed the errors", 'June')):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'send_payslips', (text, got))
            self.assertEqual(got[1].get('run'), run, (text, got))

    def test_crit3_people_who_are_back_with_a_reason_still_get_their_payslips(self):
        """FIX-1 ninth pass (regressions of the seventh): a payslip send that
        names who is back and then says the errors are fixed reached Send
        payslips before FIX-1 and went to the model after it. It sends again;
        a real send-back with a reason still never does."""
        for verb in ('Send', 'Email'):
            for tail in (', welcome back everyone, mistakes fixed',
                         ' to everyone back at work, errors corrected',
                         ' to those back from leave, errors corrected',
                         ' to people who were away, now back, errors fixed',
                         ' to the team who returned back, errors fixed',
                         ' to staff back in the office, errors fixed'):
                text = '%s the June 2031 payslips%s' % (verb, tail)
                got = registry.match(text)
                self.assertEqual((got or ('',))[0], 'send_payslips', (text, got))
                self.assertEqual(got[1].get('run'), 'June 2031', (text, got))
        for text in ('Send the June payslips Mai sent in back because the rates are wrong',
                     'Send the June payslips waiting for me back because overtime is wrong',
                     'Send them back to those who made them because they are wrong',
                     'Send it all back because the payslips are wrong',
                     'Email the June payslips back to Mai because they are wrong'):
            got = registry.match(text)
            self.assertNotIn((got or ('',))[0], ('send_payslips', 'submit_run'), (text, got))

    def test_wf4_only_a_scheme_or_a_name_leaves_the_period(self):
        """FIX-1 ninth pass (regressions of the seventh and eighth): every
        word of the period that was no month moved to the scheme — on the
        model's and the pencil's slots too — so "May 2031 bonus", "salaries
        for May 2031", "tháng 5 nhé" lost the scheme said and refused on a
        "person" called "bonus". Only words that one scheme covers, or
        somebody's name, leave the period now; and never when the scheme
        slot already names that scheme."""
        for period in ('May 2031 bonus', 'salaries for May 2031', 'May 2031 wages',
                       'May 2031, please', 'salary May 2031', 'May 2031 overtime',
                       'tháng 5 năm 2031 nhé', 'tháng 5 năm 2031 nha',
                       'May 2031 Payai Retail End-Month', 'May 2031 payroll Payai Retail'):
            got = self._norm({'period': period, 'scheme': 'Payai Retail End-Month'})
            self.assertEqual((got.get('period'), got.get('scheme')),
                             (period, 'Payai Retail End-Month'), (period, got))
            self.assertFalse(got.get('people'), (period, got))
        for period in ('May 2031 bonus', 'May 2031 please', 'tháng 5 năm 2031 nhé',
                       'nhân viên tháng 5 năm 2031'):
            got = self._norm({'period': period})
            self.assertEqual(got.get('period'), period, got)
            self.assertFalse(got.get('scheme'), got)
            self.assertFalse(got.get('people'), got)
        # The phrase path keeps what the seventh pass fixed.
        for text, period, scheme, people in (
                ('Run Payai Retail End-Month payroll for May 2031', 'May 2031',
                 'Payai Retail End-Month', ''),
                ('Run Payai Nguyễn Thị Mây payroll for May 2031', 'May 2031', '',
                 'Payai Nguyễn Thị Mây'),
                ('Run Payai Retail payroll for Mid-Month', '', 'Payai Retail Mid-Month', ''),
                ('Run Warehouse payroll for May 2031', 'May 2031', 'Warehouse', '')):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
            texts = self._norm(got[1])
            self.assertEqual((texts.get('period') or '', texts.get('scheme') or '',
                              texts.get('people') or ''), (period, scheme, people),
                             (text, texts))

    # ========================================================= tenth pass
    def test_wf4_month_phrase_after_payroll_is_never_a_person(self):
        """FIX-1 tenth pass (regression of the seventh): "Run Payai Retail
        End-Month payroll for 13th month" moved the scheme out of the period
        slot and joined it with "for", so "13th month" / "this pay period" /
        "2031" / "May month" were cut off as a person's name and the plan was
        refused. Month-phrase words after "payroll" are the period."""
        for text, period in (
                ('Run Payai Retail End-Month payroll for 13th month', '13th month'),
                ('Run Payai Retail End-Month payroll for this pay period', 'this pay period'),
                ('Run Payai Retail End-Month payroll for 2031', '2031'),
                ('Run Payai Pay for Performance payroll for May month', 'May'),
                ('Run Payai Retail End-Month payroll for May 2031', 'May 2031')):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
            texts = self._norm(got[1])
            self.assertEqual(texts.get('period') or '', period, (text, texts))
            self.assertIn(texts.get('scheme'), ('Payai Retail End-Month',
                                                'Payai Pay for Performance'), (text, texts))
            self.assertFalse(texts.get('people'), (text, texts))
        # The model's / the pencil's slots are left as they were.
        for period in ('13th month', 'this pay period', '2031', 'May month'):
            got = self._norm({'period': period, 'scheme': 'Payai Retail End-Month'})
            self.assertEqual((got.get('period'), got.get('scheme')),
                             (period, 'Payai Retail End-Month'), (period, got))
            self.assertFalse(got.get('people'), (period, got))

    # ====================================================== eleventh pass
    def test_wf4_a_scheme_or_month_after_payroll_keeps_the_people(self):
        """FIX-1 eleventh pass (regression of the eighth): the scheme's
        words before "payroll" were joined to everything after it with
        "for" — "Retail for Mid-Month for Mai" — so the scheme was cut short
        and "Mid-Month" / "this pay period" / "2031" became a person's name
        and the plan was refused. Only the first part after "payroll" is
        read with the words before it; the people keep their own cut."""
        for text, period, scheme, people in (
                ('Run the Payai Retail payroll for Mid-Month for Payai Nguyễn Văn An',
                 '', 'Payai Retail Mid-Month', 'Payai Nguyễn Văn An'),
                ('Run Payai Retail payroll for End-Month, for Payai Nguyễn Văn An',
                 '', 'Payai Retail End-Month', 'Payai Nguyễn Văn An'),
                ('Run Payai Retail payroll for Mid-Month for Payai Nguyễn Văn An only',
                 '', 'Payai Retail Mid-Month', 'Payai Nguyễn Văn An only'),
                ('Run Payai Retail payroll for End-Month for active staff',
                 '', 'Payai Retail End-Month', 'active staff'),
                ('Run Payai payroll for Retail End-Month for Payai Nguyễn Văn An',
                 '', 'Payai Retail End-Month', 'Payai Nguyễn Văn An'),
                ('Run Payai Retail End-Month payroll for this pay period for Payai Nguyễn Văn An',
                 'this pay period', 'Payai Retail End-Month', 'Payai Nguyễn Văn An'),
                ('Run Payai Retail End-Month payroll for 13th month for Payai Nguyễn Văn An',
                 '13th month', 'Payai Retail End-Month', 'Payai Nguyễn Văn An'),
                ('Run Payai Retail End-Month payroll for 2031 for Payai Nguyễn Văn An',
                 '2031', 'Payai Retail End-Month', 'Payai Nguyễn Văn An'),
                # A whole name, never cut at a word a month phrase also has
                # ("An" — "an").
                ('Run Payai Nguyễn Văn An payroll for May 2031',
                 'May 2031', '', 'Payai Nguyễn Văn An')):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
            texts = self._norm(got[1])
            self.assertEqual((texts.get('period') or '', texts.get('scheme') or '',
                              texts.get('people') or ''), (period, scheme, people),
                             (text, texts))
        # A month said before "payroll" stays that month; the month-phrase
        # words after it are nobody's name.
        for text, start, scheme in (
                ('Run May 2031 Payai Retail End-Month payroll for this pay period',
                 date(2031, 5, 1), 'Payai Retail End-Month'),
                ('Run the June 2031 Payai Pay for Performance payroll for this pay period',
                 date(2031, 6, 1), 'Payai Pay for Performance')):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
            texts = self._norm(got[1])
            self.assertEqual(texts.get('scheme'), scheme, (text, texts))
            self.assertFalse(texts.get('people'), (text, texts))
            month = parse_period(texts.get('period') or '', date(2031, 1, 15))
            self.assertEqual((month or (None,))[0], start, (text, texts))

    def test_crit3_people_back_or_a_call_back_with_a_reason_get_their_payslips(self):
        """FIX-1 eleventh pass (regressions of the seventh): a payslip send to
        people who are back ("to employees back from leave", "to the drivers
        back on shift"), or with a second order's own "back" ("report back
        if …", "call me back if …"), then a fix word, reached Send payslips
        before FIX-1 and went to the model after it. It sends again; a real
        send-back with a reason still never does."""
        for text, run in (
                ('Send the June payslips to people back from leave, the errors are fixed', 'June'),
                ('Send the June payslips to the people back from leave, errors fixed', 'June'),
                ('Send the June payslips to employees back from leave, errors corrected', 'June'),
                ('Send the June payslips to workers back from leave with the corrected rates',
                 'June'),
                ('Send the June payslips to the drivers back on shift, mistakes fixed', 'June'),
                ('Send the June payslips to the guys back from leave since errors are fixed',
                 'June'),
                ('Send the June payslips, back from leave staff included, errors fixed', 'June'),
                ('Send the June payslips and report back if anything is wrong', 'June'),
                ('Send the June payslips, call me back if something is wrong', 'June'),
                ('Email the payslips and write back if any are wrong', None)):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'send_payslips', (text, got))
            self.assertEqual(got[1].get('run'), run, (text, got))
        for text in ('Send the June payslips to the drivers back to Mai, they are wrong',
                     'Send the June payslips to the team back to Lan for corrections',
                     'Send the June payslips for the drivers back with the wrong rates marked',
                     'Email the June payslips for the drivers back to Mai to fix',
                     'Send the June payslips I had to report back because the rates are wrong',
                     'Send the June payslips Mai sent in back because the rates are wrong',
                     'Email the June payslips back to Mai because they are wrong'):
            got = registry.match(text)
            self.assertNotIn((got or ('',))[0], ('send_payslips', 'submit_run'), (text, got))

    # ====================================================== twelfth pass
    def test_wf4_words_after_payroll_that_are_nobody_stay_for_the_scheme_question(self):
        """FIX-1 twelfth pass (regression of the eleventh): the scheme's
        words before "payroll" were joined to the words after it with "for"
        even when those were no name, no status and no month ("Run Retail
        payroll for End-Month staff", "… for the store team"), or another
        scheme ("Run Pay for Performance payroll for Retail for …"). They were
        cut off as a person nobody is called and the plan was refused. They
        stay where they were said now, as before FIX-1: the scheme question
        asks which."""
        for text, period, scheme in (
                ('Run Payai Retail payroll for End-Month staff', 'Payai Retail', 'End-Month staff'),
                ('Run the Payai Retail payroll for the End-Month crew',
                 'Payai Retail', 'the End-Month crew'),
                ('Run the Payai Retail payroll for the store team',
                 'Payai Retail', 'the store team'),
                ('Run Payai Retail payroll for the End-Month one',
                 'Payai Retail', 'the End-Month one')):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
            texts = self._norm(got[1])
            self.assertFalse(texts.get('people'), (text, texts))
            self.assertEqual((texts.get('period'), texts.get('scheme')), (period, scheme),
                             (text, texts))
        # Two schemes said: the second is never a person; the person said is.
        got = registry.match('Run the Payai Pay for Performance payroll for Payai Retail '
                             'for Payai Nguyễn Văn An')
        texts = self._norm(got[1])
        self.assertEqual(texts.get('people'), 'Payai Nguyễn Văn An', texts)
        # A name, a status or a month after "payroll" still reads as before.
        for text, period, scheme, people in (
                ('Run Payai Retail End-Month payroll for Payai Nguyễn Văn An',
                 '', 'Payai Retail End-Month', 'Payai Nguyễn Văn An'),
                ('Run Payai Retail End-Month payroll for active staff',
                 '', 'Payai Retail End-Month', 'active staff'),
                ('Run Payai Retail End-Month payroll for May 2031',
                 'May 2031', 'Payai Retail End-Month', ''),
                ('Run Payai Retail payroll for Mid-Month', '', 'Payai Retail Mid-Month', ''),
                ('Run Warehouse payroll for May 2031', 'May 2031', 'Warehouse', '')):
            got = registry.match(text)
            texts = self._norm(got[1])
            self.assertEqual((texts.get('period') or '', texts.get('scheme') or '',
                              texts.get('people') or ''), (period, scheme, people),
                             (text, texts))

    def test_wf4_a_filler_word_in_the_period_is_never_a_scheme(self):
        """FIX-1 twelfth pass (regression of the seventh): a Vietnamese word
        one letter or one mark off a scheme's word — "luôn" (right away) ≈
        "Lương …", "lẹ" (quickly) / "lễ" (holiday) ≈ "Bán lẻ" — left the
        period and became the scheme; the scheme said became a person and the
        plan was refused, or a scheme nobody said was picked. Only a scheme's
        own words, as written, leave the period now."""
        for text, scheme, people in (
                ('Chạy lương tháng 5 luôn cho Payai Retail End-Month chỉ Vũ Khánh Chi',
                 'Payai Retail End-Month', 'Vũ Khánh Chi'),
                ('Chạy lương tháng 5 luôn cho Payai Lương khối văn phòng chỉ Vũ Khánh Chi',
                 'Payai Lương khối văn phòng', 'Vũ Khánh Chi')):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
            texts = self._norm(got[1])
            self.assertEqual((texts.get('scheme'), texts.get('people')), (scheme, people),
                             (text, texts))
            self.assertIn('tháng 5', texts.get('period') or '', (text, texts))
        for text in ('Chạy lương tháng 5 lẹ', 'Chạy lương tháng 5 lẹ giùm',
                     'Chạy lương lễ tháng 5'):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
            texts = self._norm(got[1])
            self.assertFalse(texts.get('scheme'), (text, texts))
            self.assertFalse(texts.get('people'), (text, texts))
        # A scheme's own words still leave the period.
        got = registry.match('Chạy lương Payai Retail End-Month tháng 5')
        texts = self._norm(got[1])
        self.assertEqual((texts.get('period'), texts.get('scheme')),
                         ('tháng 5', 'Payai Retail End-Month'), texts)

    def test_wf4_a_name_in_the_period_moves_only_to_an_empty_people_slot(self):
        """FIX-1 twelfth pass (regression of the seventh): a name in the
        period slot moved into the scheme's words even when the people slot
        was already filled (the model's or the pencil's slots), so the scheme
        said came back as a question; and "mai" in small letters ("tomorrow")
        became the only person of the run. The people slot already filled,
        or a name word in small letters, leaves the words in the period."""
        Emp = self.env['hr.employee']
        mai = Emp.create({'name': 'Payai Lê Thị Mai', 'company_id': self.company.id})
        self.env['hr.contract'].create({
            'name': 'Payai Lê Thị Mai contract', 'employee_id': mai.id, 'wage': 1000.0,
            'state': 'open', 'date_start': '2020-01-01', 'company_id': self.company.id})
        self.ours.add(mai.id)
        for texts in (
                {'period': 'Payai Nguyễn Thị Mây', 'scheme': 'Payai Retail End-Month',
                 'people': 'Payai Nguyễn Thị Mây'},
                {'period': 'May 2031 Mây', 'scheme': 'Payai Retail End-Month', 'people': 'Mây'},
                {'period': 'May 2031, for Mây', 'scheme': 'Payai Retail End-Month',
                 'people': 'active only'}):
            got = self._norm(texts)
            self.assertEqual(got.get('scheme'), 'Payai Retail End-Month', (texts, got))
            self.assertEqual(got.get('people'), texts['people'], (texts, got))
        got = registry.match('Chạy lương tháng 5 mai nhé')
        self.assertEqual((got or ('',))[0], 'run_payroll', got)
        texts = self._norm(got[1])
        self.assertFalse(texts.get('people'), texts)
        # A name written as a name, with the people slot empty, still moves.
        for texts, people in (({'period': 'Payai Nguyễn Thị Mây', 'scheme': 'May 2031'},
                               'Payai Nguyễn Thị Mây'),
                              ({'period': 'tháng 5 Payai Lê Thị Mai'}, 'Payai Lê Thị Mai')):
            got = self._norm(texts)
            self.assertEqual(got.get('people'), people, (texts, got))

    # ================================================= final round (PA59)
    def _final_round_world(self):
        """Two more schemes and two more people for the final-round repros:
        "Bán lẻ" (whose "lẻ" is one mark off "lẹ" / "lễ"), "Vận tải" (whose
        "tải" is somebody's given name), Lê Thị Mai and Nguyễn Văn Tài."""
        Config = self.env['hr.formula.config']
        for name, code in (('Payai Bán lẻ', 'PAYAIBL'), ('Payai Vận tải', 'PAYAIVT')):
            Config.create({'name': name, 'code': code, 'country_code': 'VN',
                           'state': 'active', 'company_id': self.company.id})
        Emp = self.env['hr.employee']
        for name in ('Payai Lê Thị Mai', 'Payai Nguyễn Văn Tài'):
            emp = Emp.create({'name': name, 'company_id': self.company.id})
            self.env['hr.contract'].create({
                'name': '%s contract' % name, 'employee_id': emp.id, 'wage': 1000.0,
                'state': 'open', 'date_start': '2020-01-01', 'company_id': self.company.id})
            self.ours.add(emp.id)

    def test_final_words_after_payroll_that_are_nobody_read_as_said(self):
        """FIX-1 final round (FIX1_OPEN2 amber item 1): words after "payroll"
        that are no name, no status and no month are never cut off as a
        person nobody is called — the period and scheme slots stay as said,
        as live today, and the scheme question asks which."""
        for text, period, scheme in (
                ('Run Payai Retail payroll for End-Month staff', 'Payai Retail', 'End-Month staff'),
                ('Run the Payai Retail payroll for End-Month employees',
                 'Payai Retail', 'End-Month employees'),
                ('Run the Payai Retail payroll for End-Month workers',
                 'Payai Retail', 'End-Month workers'),
                ('Run the Payai Retail payroll for End-Month people',
                 'Payai Retail', 'End-Month people'),
                ('Run the Payai Retail payroll for our End-Month team',
                 'Payai Retail', 'our End-Month team'),
                ('Run the Payai Retail payroll for the End-Month crew',
                 'Payai Retail', 'the End-Month crew'),
                ('Run the Payai Retail payroll for the Payai Retail team',
                 'Payai Retail', 'the Payai Retail team'),
                ('Run the Payai Retail payroll for the store team', 'Payai Retail', 'the store team'),
                ('Run Payai Retail payroll for the End-Month one', 'Payai Retail', 'the End-Month one'),
                ('Run Retail payroll for End-Month staff', 'Retail', 'End-Month staff'),
                ('Run the Retail payroll for the Retail team', 'Retail', 'the Retail team')):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
            texts = self._norm(got[1])
            self.assertFalse(texts.get('people'), (text, texts))
            self.assertEqual((texts.get('period'), texts.get('scheme')), (period, scheme),
                             (text, texts))

    def test_final_a_filler_word_one_mark_off_a_scheme_stays_in_the_period(self):
        """FIX-1 final round (FIX1_OPEN2 amber item 2): "luôn" (right away),
        "lẹ" (quickly) and "lễ" (holiday) are no scheme. The scheme said
        after "cho" stays the scheme, the person after "chỉ / riêng / với /
        cho … thôi" stays the person, and with no scheme said the scheme
        question is asked — never Bán lẻ picked silently."""
        self._final_round_world()
        tails = ('tháng 5 luôn cho Payai Bán lẻ chỉ Mai', 'tháng 5 luôn cho Payai Bán lẻ, riêng Mai',
                 'tháng 5 luôn cho Payai Bán lẻ với Mai',
                 'tháng 5 luôn cho Payai Bán lẻ cho Mai thôi')
        for verb in ('Chạy lương', 'Tính lương', 'Làm lương', 'Chạy bảng lương', 'chay luong',
                     'Tạo kỳ lương'):
            for tail in tails:
                text = '%s %s' % (verb, tail)
                got = registry.match(text)
                self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
                texts = self._norm(got[1])
                self.assertEqual(texts.get('scheme'), 'Payai Bán lẻ', (text, texts))
                self.assertIn('Mai', texts.get('people') or '', (text, texts))
                self.assertNotIn('Bán lẻ', texts.get('people') or '', (text, texts))
                self.assertIn('tháng 5', texts.get('period') or '', (text, texts))
        for text, scheme, people in (
                ('Chạy lương tháng 5 luôn cho Payai Retail End-Month chỉ Vũ Khánh Chi',
                 'Payai Retail End-Month', 'Vũ Khánh Chi'),
                ('Chạy lương tháng 5 luôn cho Payai Vận tải chỉ Vũ Khánh Chi',
                 'Payai Vận tải', 'Vũ Khánh Chi')):
            got = registry.match(text)
            texts = self._norm(got[1])
            self.assertEqual((texts.get('scheme'), texts.get('people')), (scheme, people),
                             (text, texts))
        # "Vận tải" never adds Nguyễn Văn Tài to the run.
        got = registry.match('Chạy lương tháng 5 luôn cho Payai Vận tải chỉ Vũ Khánh Chi')
        texts = self._norm(got[1])
        found = self._people(texts['people'])
        self.assertEqual(found['status'], 'resolved', found)
        self.assertEqual(found['value']['employee_ids'], [self.chi.id], found)
        for text in ('Chạy lương tháng 5 lẹ', 'Chạy lương tháng 5 lẹ giùm',
                     'Chạy lương lễ tháng 5'):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
            texts = self._norm(got[1])
            self.assertFalse(texts.get('scheme'), (text, texts))
            self.assertFalse(texts.get('people'), (text, texts))

    def test_final_a_name_in_the_period_with_people_filled_stays_put(self):
        """FIX-1 final round (FIX1_OPEN2 amber item 3): the model's or the
        pencil's slots with a name in the period and the people slot already
        filled keep the scheme said — no scheme question — and the people
        said; "mai" (tomorrow) in small letters is nobody."""
        self._final_round_world()
        for texts in (
                {'period': 'Mai', 'scheme': 'Payai Retail End-Month', 'people': 'Mai'},
                {'period': 'May 2031 Mai', 'scheme': 'Payai Retail End-Month', 'people': 'Mai'},
                {'period': 'May 2031 Mai', 'scheme': 'Payai Pay for Performance',
                 'people': 'active only'},
                {'period': 'May 2031 Mai', 'scheme': 'Payai Bán lẻ', 'people': 'Mai'},
                {'period': 'May 2031, for Mai', 'scheme': 'Payai Retail End-Month', 'people': 'Mai'},
                {'period': 'May 2031, for Mai', 'scheme': 'Payai Vận tải', 'people': 'active only'},
                {'period': 'May 2031, for Mai', 'scheme': 'Payai Lương khối văn phòng',
                 'people': 'Mai'}):
            got = self._norm(texts)
            self.assertEqual(got.get('scheme'), texts['scheme'], (texts, got))
            self.assertEqual(got.get('people'), texts['people'], (texts, got))
        got = registry.match('Chạy lương tháng 5 mai nhé')
        self.assertEqual((got or ('',))[0], 'run_payroll', got)
        texts = self._norm(got[1])
        self.assertFalse(texts.get('people'), texts)
        self.assertFalse(texts.get('scheme'), texts)

    def test_final_safety_a_label_with_its_number_stays_in_the_period(self):
        """FIX-1 final round, safety check (HEAD vs tree): "chạy lương khối 2
        tháng trước" is last month's run for team 2. "khối 2" stays in the
        period with its number, as before FIX-1 — never the scheme "Lương
        khối văn phòng" picked by its one word "khối", with "2 tháng trước"
        (two months ago) left behind. A scheme's own words still move."""
        for text in ('chạy lương khối 2 tháng trước', 'chạy lương khoi 2 tháng trước',
                     'Chạy lương tổ 1 tháng sau', 'chạy lương nhóm 3 tháng 5', 'chạy lương khối 2'):
            got = registry.match(text)
            self.assertEqual((got or ('',))[0], 'run_payroll', (text, got))
            texts = self._norm(got[1])
            self.assertEqual(texts.get('period'), got[1]['period'], (text, texts))
            self.assertFalse(texts.get('scheme'), (text, texts))
        texts = self._norm({'period': 'khối 2 tháng trước'})
        self.assertEqual(texts, {'period': 'khối 2 tháng trước'})
        got = parse_period(texts['period'], date(2026, 10, 13))
        self.assertEqual((got[0].year, got[0].month), (2026, 9))
        got = registry.match('chạy lương khối văn phòng tháng 5')
        texts = self._norm(got[1])
        self.assertEqual((texts.get('period'), texts.get('scheme')), ('tháng 5', 'khối văn phòng'))
