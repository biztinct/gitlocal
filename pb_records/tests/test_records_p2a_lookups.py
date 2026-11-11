# -*- coding: utf-8 -*-
"""UPDATES P2a — typed names for linked records stop guessing, and the review
gets faster without changing a single answer.

Numbered as the handover (`docs/handovers/updates/UPDATES_P2A_HANDOVER.md` §6):

  A1-A8  the name look-up ladder in `_coerce` (current value first, company
         scope, a department's full path, namesakes refused, never a create
         from a slashed path; the on-screen picker unchanged);
  A9     the golden comparison: `preview_changes` over 200+ changes covering
         every card kind, compared with a copy captured BEFORE the speed work
         (`data/p2a_golden_preview.json`);
  A10    the look-up memo lives for one evaluation and dies with it.

Capture mode: with `PB_P2A_WRITE_GOLDEN=1` in the environment the golden test
WRITES the fixture instead of comparing. It was run that way exactly once,
before the optimisation, and the file is committed.

Every record read or written here is created by the transaction it runs in.
"""
import json
import os

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

GOLDEN = ('pb_records', 'tests', 'data', 'p2a_golden_preview.json')

DEPT = 'f:hr.employee:department_id'
MANAGER = 'f:hr.employee:parent_id'
JOB = 'f:hr.employee:job_title'
PHONE = 'f:hr.employee:work_phone'
BIRTHDAY = 'f:hr.employee:birthday'
SEX = 'f:hr.employee:sex'
WAGE = 'f:hr.contract:wage'
START = 'f:hr.contract:date_start'
HOURS = 'f:hr.contract:resource_calendar_id'


@tagged('post_install', '-at_install')
class TestRecordsP2aLookups(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
            cls.env.company, 'records')
        cls.company = cls.env.company
        cls.other = cls.env['res.company'].create({'name': 'P2A Other Co'})
        cls.Desk = cls.env['pb.records.desk'].with_context(
            allowed_company_ids=[cls.company.id])
        Dept = cls.env['hr.department']
        cls.Employee = cls.env['hr.employee']

        def dept(name, **vals):
            return Dept.create(dict({'name': name, 'company_id': cls.company.id}, **vals))

        cls.d_sales = dept('P2A Sales')
        cls.d_root = dept('P2A Root')
        cls.d_ops = dept('P2A Ops', parent_id=cls.d_root.id)
        cls.d_twin1 = dept('P2A Twin')
        cls.d_twin2 = dept('P2A Twin')
        cls.d_lone = dept('P2A Lone')
        # A5: the same name in another company — never offered to company A.
        cls.d_ops_b = Dept.create({'name': 'P2A Shared', 'company_id': cls.other.id})
        cls.d_ops_a = dept('P2A Shared')

        Cal = cls.env['resource.calendar']
        cls.cal40 = Cal.create({'name': 'P2A 40h', 'company_id': cls.company.id})
        cls.cal35 = Cal.create({'name': 'P2A 35h', 'company_id': cls.company.id})

        def emp(name, **vals):
            return cls.Employee.create(dict({'name': name, 'company_id': cls.company.id}, **vals))

        cls.boss = emp('P2A Boss')
        cls.same1 = emp('P2A Same')
        cls.same2 = emp('P2A Same')

        depts = [cls.d_sales, cls.d_ops, cls.d_twin1, cls.d_twin2]
        cls.people = []
        for i in range(20):
            cls.people.append(emp(
                'P2A Person %02d' % i, barcode='P2A%04d' % i,
                job_title='Operator', work_phone='100', birthday='1990-01-01',
                sex='male' if i % 2 else 'female',
                department_id=depts[i % 4].id,
                parent_id=(cls.boss if i % 2 == 0 else cls.same2).id))
        cls.contracts = {}
        for i, person in enumerate(cls.people[:18]):
            cls.contracts[i] = cls.env['hr.contract'].create({
                'name': '%s contract' % person.name, 'employee_id': person.id,
                'wage': 1000.0, 'state': 'open', 'date_start': '2026-01-01',
                'resource_calendar_id': cls.cal40.id})
        cls.outsider = cls.Employee.create({'name': 'P2A Outsider',
                                            'company_id': cls.other.id})

        Tpl = cls.env['hr.contract.advantage.template']
        cls.t_amount = Tpl.create({
            'name': 'P2A allowance', 'code': 'P2AAMT', 'lower_bound': 0.0,
            'upper_bound': 0.0, 'default_value': 0.0, 'value_type': 'amount'})
        cls.t_text = Tpl.create({
            'name': 'P2A note', 'code': 'P2ATXT', 'lower_bound': 0.0,
            'upper_bound': 0.0, 'default_value': 0.0, 'value_type': 'text'})
        Line = cls.env['hr.contract.advantage']
        Line.create({'contract_id': cls.contracts[0].id,
                     'advantage_template_id': cls.t_amount.id, 'amount': 500.0})
        Line.create({'contract_id': cls.contracts[0].id,
                     'advantage_template_id': cls.t_text.id, 'text_value': 'Kept'})
        Line.create({'contract_id': cls.contracts[1].id,
                     'advantage_template_id': cls.t_amount.id, 'amount': 0.0})

        # One existing bank account, so the bank judgement has a "same".
        cls.Desk.apply_changes(0, [
            {'emp_id': cls.people[0].id, 'field_id': 'b:acc_number', 'value': '55500001'},
            {'emp_id': cls.people[0].id, 'field_id': 'b:bank_name', 'value': 'P2A Bank'},
        ], note='P2A fixture')

    # ---------------------------------------------------------------- helpers
    def one(self, emp, field_id, value, desk=None):
        res = (desk or self.Desk).preview_changes(
            0, [{'emp_id': emp.id, 'field_id': field_id, 'value': value}])
        self.assertEqual(len(res['items']), 1, res)
        return res['items'][0]

    def plan_value(self, emp, field_id, value, desk=None):
        _items, plan, _counts = (desk or self.Desk)._evaluate(
            0, [{'emp_id': emp.id, 'field_id': field_id, 'value': value}])
        return plan[0]['value'] if plan else None

    # =====================================================================
    # A1-A8 — the ladder
    # =====================================================================
    def test_A1_namesake_never_displaces_the_current_value(self):
        person = self.people[3]                      # in the SECOND "P2A Twin"
        self.assertEqual(person.department_id, self.d_twin2)
        item = self.one(person, DEPT, 'P2A Twin')
        self.assertEqual(item['status'], 'same', item)
        item = self.one(person, DEPT, '  p2a   twin ')   # case + spaces
        self.assertEqual(item['status'], 'same', item)

    def test_A2_namesake_for_somebody_in_neither_is_refused(self):
        person = self.people[0]                      # in P2A Sales
        item = self.one(person, DEPT, 'P2A Twin')
        self.assertEqual(item['status'], 'refused', item)
        self.assertIn("are called 'P2A Twin'", item['why'])
        self.assertTrue(item['why'].startswith('2 '), item['why'])
        self.assertIn('Pick the right one on the Records screen', item['why'])
        self.assertIsNone(self.plan_value(person, DEPT, 'P2A Twin'))

    def test_A3_full_path_resolves_to_the_child_without_a_create(self):
        person = self.people[0]
        count = self.env['hr.department'].search_count([])
        item = self.one(person, DEPT, 'P2A Root / P2A Ops')
        self.assertEqual(item['status'], 'ok', item)
        self.assertNotIn('(new)', item['new_label'])
        self.assertEqual(self.plan_value(person, DEPT, 'P2A Root / P2A Ops'),
                         self.d_ops.id)
        # Somebody already there: the path is what the screen shows → same.
        item = self.one(self.people[1], DEPT, 'P2A Root / P2A Ops')
        self.assertEqual(item['status'], 'same', item)
        self.Desk.apply_changes(0, [{'emp_id': person.id, 'field_id': DEPT,
                                     'value': 'P2A Root / P2A Ops'}], note='A3')
        self.assertEqual(person.department_id, self.d_ops)
        self.assertEqual(self.env['hr.department'].search_count([]), count)

    def test_A4_full_path_matching_nothing_is_refused_never_created(self):
        person = self.people[0]
        count = self.env['hr.department'].search_count([])
        item = self.one(person, DEPT, 'P2A Root / Nowhere')
        self.assertEqual(item['status'], 'refused', item)
        self.assertIn("is called 'P2A Root / Nowhere'", item['why'])
        self.assertIn('including the part before the slash', item['why'])
        self.assertIsNone(self.plan_value(person, DEPT, 'P2A Root / Nowhere'))
        res = self.Desk.apply_changes(0, [{'emp_id': person.id, 'field_id': DEPT,
                                           'value': 'P2A Root / Nowhere'}], note='A4')
        self.assertFalse(res['apply_id'])
        self.assertEqual(self.env['hr.department'].search_count([]), count)
        self.assertEqual(person.department_id, self.d_sales)
        # A plain new name (no slash) is still proposed as new — unchanged.
        item = self.one(person, DEPT, 'P2A Brand New')
        self.assertEqual(item['status'], 'ok', item)
        self.assertIn('(new)', item['new_label'])

    def test_A5_another_companys_namesake_is_not_seen(self):
        person = self.people[0]
        self.assertEqual(self.plan_value(person, DEPT, 'P2A Shared'), self.d_ops_a.id)
        item = self.one(person, DEPT, 'P2A Shared')
        self.assertEqual(item['status'], 'ok', item)
        # Company B's record alone (A's archived away) is still never picked.
        self.d_ops_a.active = False
        item = self.one(person, DEPT, 'P2A Shared')
        self.assertNotEqual(self.plan_value(person, DEPT, 'P2A Shared'), self.d_ops_b.id)
        self.assertIn('(new)', item['new_label'])

    def test_A6_unique_name_any_case_and_stray_spaces(self):
        person = self.people[0]
        for text in ('p2a lone', '  P2A LONE  ', 'P2A Lone'):
            self.assertEqual(self.plan_value(person, DEPT, text), self.d_lone.id, text)
            item = self.one(person, DEPT, text)
            self.assertEqual(item['status'], 'ok', item)
            self.assertEqual(item['new_label'], 'P2A Lone')

    def test_A7_the_on_screen_picker_is_exact(self):
        person = self.people[0]
        self.assertEqual(self.plan_value(person, DEPT, {'id': self.d_twin1.id}),
                         self.d_twin1.id)
        item = self.one(person, DEPT, {'id': self.d_twin2.id, 'label': 'P2A Twin'})
        self.assertEqual(item['status'], 'ok', item)
        item = self.one(person, DEPT, {'id': 999999999})
        self.assertEqual(item['status'], 'refused')
        self.assertEqual(item['why'], 'That choice no longer exists.')
        item = self.one(self.people[3], DEPT, {'id': self.d_twin2.id})
        self.assertEqual(item['status'], 'same', item)

    def test_A8_manager_named_by_a_shared_name_is_refused(self):
        person = self.people[0]                      # manager: P2A Boss
        item = self.one(person, MANAGER, 'P2A Same')
        self.assertEqual(item['status'], 'refused', item)
        self.assertIn("are called 'P2A Same'", item['why'])
        self.assertIsNone(self.plan_value(person, MANAGER, 'P2A Same'))
        # The person already under the second namesake stays put.
        item = self.one(self.people[1], MANAGER, 'P2A Same')
        self.assertEqual(item['status'], 'same', item)
        # A unique manager name still resolves.
        self.assertEqual(self.plan_value(self.people[1], MANAGER, 'p2a boss'),
                         self.boss.id)

    def test_working_hours_namesake_keeps_the_current_one(self):
        """The live case (ledger G11): two calendars, one name."""
        self.env['resource.calendar'].create({'name': 'P2A 40h',
                                              'company_id': self.company.id})
        item = self.one(self.people[0], HOURS, 'P2A 40h')
        self.assertEqual(item['status'], 'same', item)
        item = self.one(self.people[0], HOURS, 'P2A 35h')
        self.assertEqual(item['status'], 'ok', item)

    # =====================================================================
    # A10 — the memo does not outlive one evaluation
    # =====================================================================
    def test_A10_memo_dies_with_the_evaluation(self):
        person, other = self.people[0], self.people[4]
        first = self.Desk.preview_changes(0, [
            {'emp_id': person.id, 'field_id': DEPT, 'value': 'P2A Renamed'},
            {'emp_id': other.id, 'field_id': DEPT, 'value': 'P2A Renamed'}])
        self.assertTrue(all('(new)' in i['new_label'] for i in first['items']), first)
        self.d_lone.name = 'P2A Renamed'
        second = self.Desk.preview_changes(0, [
            {'emp_id': person.id, 'field_id': DEPT, 'value': 'P2A Renamed'},
            {'emp_id': other.id, 'field_id': DEPT, 'value': 'P2A Renamed'}])
        self.assertEqual([i['new_label'] for i in second['items']],
                         ['P2A Renamed', 'P2A Renamed'], second)
        self.assertEqual(self.plan_value(person, DEPT, 'P2A Renamed'), self.d_lone.id)

    def test_memo_is_shared_inside_one_evaluation(self):
        """Thirty people naming one department ask the database once."""
        changes = [{'emp_id': p.id, 'field_id': DEPT, 'value': 'P2A Lone'}
                   for p in self.people]
        Dept = type(self.env['hr.department'])
        calls = []
        original = Dept.search

        def counting(records, domain, *args, **kwargs):
            if any(isinstance(t, (list, tuple)) and t and t[0] in ('name', 'complete_name')
                   for t in (domain or [])):
                calls.append(domain)
            return original(records, domain, *args, **kwargs)

        from unittest.mock import patch
        with patch.object(Dept, 'search', counting):
            res = self.Desk.preview_changes(0, changes)
        self.assertEqual(res['counts']['ok'], 20)
        self.assertEqual(len(calls), 1, calls)

    # =====================================================================
    # A9 — the golden comparison
    # =====================================================================
    def _golden_changes(self):
        P = self.people
        dept_texts = ['P2A Sales', '  p2a sales ', 'P2A Root / P2A Ops', 'P2A Twin',
                      'P2A Nowhere', 'P2A Root / Nope', None]
        out = []
        for i, person in enumerate(P):
            def add(field_id, value):
                out.append({'emp_id': person.id, 'field_id': field_id, 'value': value})
            add(JOB, ['Line Lead', 'Operator', 'Supervisor'][i % 3])
            add(PHONE, '100' if i % 4 == 0 else str(200 + i))
            add(BIRTHDAY, ['1991-05-0%d' % (i % 9 + 1), 'not a date', '1990-01-01'][i % 3])
            add(SEX, ['Female', 'male', 'Maybe', 'MALE'][i % 4])
            text = dept_texts[i % 7]
            add(DEPT, text if text is not None else person.department_id.display_name)
            add(MANAGER, ['P2A Boss', 'P2A Same', 'Nobody P2A'][i % 3])
            add(WAGE, ['1500', '1,750.50', 'abc', '1000'][i % 4])
            add(START, ['2026-02-01', '2026-01-01', '01/02/2026'][i % 3])
            add(HOURS, ['P2A 40h', 'P2A 35h', 'p2a 35H'][i % 3])
            add('c:P2AAMT', ['250000', 'abc', '0', '1,000', '500'][i % 5])
            add('c:P2ATXT', ['Note %d' % i, 'Kept'][i % 2])
            if i % 3 == 0:
                add('b:acc_number', '55500001' if i == 0 else '9900%02d' % i)
                add('b:bank_name', 'P2A Bank')
            elif i % 3 == 1:
                add('b:bank_name', 'Orphan Bank')       # no account number
            else:
                add('b:acc_number', '12-34 5%02d' % i)
                add('b:acc_holder_name', 'Holder %d' % i)
                add('b:bank_bic', 'P2ABIC%d' % i)
        for field_id, value in ((JOB, 'Nope'), (DEPT, 'P2A Sales'), (WAGE, '1')):
            out.append({'emp_id': self.outsider.id, 'field_id': field_id, 'value': value})
        return out

    def _scheme_changes(self):
        """A pay scheme's own catalogue: a boolean, a rule component, a
        many2one — the kinds Master records does not carry."""
        IrModel, IrField = self.env['ir.model'], self.env['ir.model.fields']
        Mapping = self.env['hr.payslip.import.mapping']
        bool_field = next(
            (f for f in ('birthday_public_display', 'vn_hi_enrolled',
                         'manually_set_presence') if f in self.Employee._fields
             and not self.Employee._fields[f].readonly), None)
        cfg = self.env['hr.formula.config'].create({
            'name': 'P2A Scheme', 'code': 'P2ASCHEME', 'country_code': 'VN',
            'state': 'active', 'company_id': self.company.id})

        def rule(name, code, **extra):
            return self.env['hr.formula.rule'].create(dict({
                'config_id': cfg.id, 'name': name, 'code': code,
                'column_type': 'input', 'sequence': 1, 'default_value': 0.0}, **extra))

        def field_map(r, model, fname):
            Mapping.create({
                'salary_structure_id': cfg.id, 'component_id': r.id,
                'destination_type': 'field',
                'target_model_id': IrModel._get(model).id,
                'target_field_id': IrField._get(model, fname).id})

        if bool_field:
            field_map(rule('P2A flag', 'P2AFLAG'), 'hr.employee', bool_field)
        field_map(rule('P2A dept', 'P2ADEPT'), 'hr.contract', 'department_id')
        rule('P2A bonus', 'P2ABONUS', is_contract_component=True)
        out = []
        for i, person in enumerate(self.people):
            if bool_field:
                out.append({'emp_id': person.id, 'field_id': 'f:hr.employee:%s' % bool_field,
                            'value': ['Yes', 'no', 'perhaps', '1'][i % 4]})
            out.append({'emp_id': person.id, 'field_id': 'f:hr.contract:department_id',
                        'value': ['P2A Lone', 'P2A Twin', 'P2A Root / P2A Ops'][i % 3]})
            out.append({'emp_id': person.id, 'field_id': 'c:P2ABONUS',
                        'value': ['300', 'x', '0'][i % 3]})
        return cfg, out, bool_field

    def _normalise(self, items, cards):
        """Database ids out, card labels checked then replaced by a token —
        the comparison must not depend on which build the test runs on."""
        names = {p.id: 'P%02d' % i for i, p in enumerate(self.people)}
        names[self.outsider.id] = 'OUT'
        out = []
        for item in items:
            row = dict(item)
            row['emp_id'] = names.get(row['emp_id'], row['emp_id'])
            self.assertEqual(row.pop('field_label'), cards[row['field_id']]['label'])
            out.append(row)
        return out

    def test_A9_golden_preview_is_identical(self):
        changes = self._golden_changes()
        self.assertGreaterEqual(len(changes), 200)
        master_cards = self.Desk._cards(0)
        master = self._normalise(self.Desk.preview_changes(0, changes)['items'],
                                 master_cards)
        cfg, scheme_changes, bool_field = self._scheme_changes()
        scheme_cards = self.Desk._cards(cfg.id)
        scheme = self._normalise(
            self.Desk.preview_changes(cfg.id, scheme_changes)['items'], scheme_cards)
        kinds = {c['field_id'] for c in changes + scheme_changes}
        self.assertTrue({JOB, BIRTHDAY, SEX, DEPT, WAGE, 'b:acc_number',
                         'c:P2AAMT', 'c:P2ATXT', 'c:P2ABONUS'} <= kinds)
        if bool_field:
            # The boolean's field name differs between builds; one token.
            for row in scheme:
                if row['field_id'] == 'f:hr.employee:%s' % bool_field:
                    row['field_id'] = 'f:hr.employee:<bool>'
        got = {'master': master, 'scheme': scheme}
        path = os.path.join(get_module_path(GOLDEN[0]), *GOLDEN[1:])
        if os.environ.get('PB_P2A_WRITE_GOLDEN') == '1':
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(got, fh, indent=1, sort_keys=True, ensure_ascii=False)
                fh.write('\n')
            return
        with open(path, encoding='utf-8') as fh:
            golden = json.load(fh)
        if not bool_field:
            golden['scheme'] = [r for r in golden['scheme']
                                if r['field_id'] != 'f:hr.employee:<bool>']
        self.assertEqual(len(got['master']), len(golden['master']))
        for mine, theirs in zip(got['master'], golden['master']):
            self.assertEqual(mine, theirs)
        self.assertEqual(got['scheme'], golden['scheme'])
