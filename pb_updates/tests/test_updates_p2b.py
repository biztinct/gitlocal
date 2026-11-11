# -*- coding: utf-8 -*-
"""UPDATES P2b — pay items by pay scheme, CLEAR, and one contract (B1-B11).

The handover's numbered cases, one test each (two where a case has two
halves). Everything runs in a company of its own, so the pay schemes, the
scheme map and the people are exactly the ones made here:

    team A  → "P2B Monthly staff"            pay items X, Y, T (text)
    team B  → "P2B Daily rate"               pay item  Y
    team C  → "P2B Field monthly" (end of month)  pay item W
              "P2B Field advance" (mid-month)     pay item Z
    team N  → no line on the map; five schemes in the company, two per kind
              of run, so "the company's only scheme" never answers for them.

X has no contract line anywhere (B6). Somebody in team B already has a line
for X (B2). Nothing here touches a payslip.
"""
import base64
import csv
import io

from odoo.tests import TransactionCase, tagged

try:
    import openpyxl
except ImportError:            # pragma: no cover — a declared dependency
    openpyxl = None

JOB = 'f:hr.employee:job_title'
MANAGER = 'f:hr.employee:parent_id'
END = 'f:hr.contract:date_end'
START = 'f:hr.contract:date_start'
WAGE = 'f:hr.contract:wage'
BANK_NAME = 'b:bank_name'
X, Y, T, W, Z = 'c:P2BX', 'c:P2BY', 'c:P2BT', 'c:P2BW', 'c:P2BZ'


def csv_b64(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    for row in rows:
        writer.writerow(row)
    return base64.b64encode(out.getvalue().encode('utf-8')).decode()


@tagged('post_install', '-at_install', 'pb_updates')
class TestUpdatesP2b(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        cls.company = cls.env['res.company'].create(
            {'name': 'P2B Fixture Co', 'currency_id': vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(cls.env.context,
                                       allowed_company_ids=[cls.company.id]))
        for process in ('records', 'schememap'):
            try:
                cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
                    cls.company, process)
            except Exception:   # noqa: BLE001 — a fixture must not die here
                pass
        cls.Desk = cls.env['pb.records.desk']
        cls.Upd = cls.env['pb.updates.desk']
        cls.Door = cls.Upd._desk()

        Department = cls.env['hr.department']
        cls.team_a = Department.create({'name': 'P2B Team A', 'company_id': cls.company.id})
        cls.team_b = Department.create({'name': 'P2B Team B', 'company_id': cls.company.id})
        cls.team_c = Department.create({'name': 'P2B Team C', 'company_id': cls.company.id})
        cls.team_n = Department.create({'name': 'P2B Team N', 'company_id': cls.company.id})

        cls.monthly = cls._config('P2B Monthly staff', 'P2BMONTHLY', 'end_cycle')
        cls.daily = cls._config('P2B Daily rate', 'P2BDAILY', 'end_cycle')
        cls.field_end = cls._config('P2B Field monthly', 'P2BFIELDEND', 'end_cycle')
        cls.field_mid = cls._config('P2B Field advance', 'P2BFIELDMID', 'mid_cycle')
        cls.spare_mid = cls._config('P2B Spare advance', 'P2BSPAREMID', 'mid_cycle')

        cls._rule(cls.monthly, 'P2B Site allowance', 'P2BX', is_contract_component=True)
        cls._rule(cls.monthly, 'P2B Transport', 'P2BY', is_contract_component=True)
        cls._rule(cls.monthly, 'P2B Uniform size', 'P2BT', is_text_component=True)
        cls._rule(cls.daily, 'P2B Transport', 'P2BY', is_contract_component=True)
        cls._rule(cls.field_end, 'P2B Field bonus', 'P2BW', is_contract_component=True)
        cls._rule(cls.field_mid, 'P2B Advance cap', 'P2BZ', is_contract_component=True)

        Assign = cls.env['hr.formula.scheme.assignment']
        Assign.create({'config_id': cls.monthly.id, 'department_id': cls.team_a.id,
                       'cycle_type': 'any'})
        Assign.create({'config_id': cls.daily.id, 'department_id': cls.team_b.id,
                       'cycle_type': 'any'})
        Assign.create({'config_id': cls.field_end.id, 'department_id': cls.team_c.id,
                       'cycle_type': 'end_cycle'})
        Assign.create({'config_id': cls.field_mid.id, 'department_id': cls.team_c.id,
                       'cycle_type': 'mid_cycle'})

        cls.calendar = cls.company.resource_calendar_id or cls.env[
            'resource.calendar'].create({'name': 'P2B Hours', 'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'P2B Kind'})

        cls.boss = cls._person('P2B Boss', 'P2B0000', cls.team_a)
        cls.ann = cls._person('P2B Ann', 'P2B0001', cls.team_a)      # Monthly staff
        cls.bob = cls._person('P2B Bob', 'P2B0002', cls.team_b)      # Daily rate
        cls.bea = cls._person('P2B Bea', 'P2B0003', cls.team_b)      # Daily rate, has X
        cls.cat = cls._person('P2B Cat', 'P2B0004', cls.team_c)      # both field schemes
        cls.ned = cls._person('P2B Ned', 'P2B0005', cls.team_n)      # no scheme
        cls.ann.parent_id = cls.boss
        cls.contracts = {p.id: cls._contract(p) for p in
                         (cls.boss, cls.ann, cls.bob, cls.bea, cls.cat, cls.ned)}
        cls.contracts[cls.ann.id].date_end = '2027-12-31'
        template = cls.env['hr.contract.advantage.template'].create({
            'name': 'P2B Site allowance', 'code': 'P2BX', 'lower_bound': 0.0,
            'upper_bound': 0.0, 'default_value': 0.0, 'value_type': 'amount'})
        cls.bea_x = cls.env['hr.contract.advantage'].create({
            'contract_id': cls.contracts[cls.bea.id].id,
            'advantage_template_id': template.id, 'amount': 250.0})
        # B6 needs X with no line ANYWHERE on a contract a person can see —
        # Bea's line is the one exception, and it is created above on
        # purpose; the Master catalogue alone would offer X only because of it.

    # ---------------------------------------------------------------- fixtures
    @classmethod
    def _config(cls, name, code, cycle):
        return cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'cycle_type': cycle, 'country_code': 'VN',
            'company_id': cls.company.id, 'state': 'active'})

    @classmethod
    def _rule(cls, cfg, name, code, **extra):
        return cls.env['hr.formula.rule'].create(dict({
            'config_id': cfg.id, 'name': name, 'code': code,
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0}, **extra))

    @classmethod
    def _person(cls, name, code, team):
        employee = cls.env['hr.employee'].create({
            'name': name, 'barcode': code, 'company_id': cls.company.id,
            'job_title': 'Operator'})
        version = employee.current_version_id if 'current_version_id' in employee._fields else None
        if version and 'department_id' in version._fields:
            version.department_id = team.id
        else:
            employee.department_id = team.id
        return employee

    @classmethod
    def _contract(cls, employee, **vals):
        return cls.env['hr.contract'].create(dict({
            'name': 'P2B contract %s' % employee.name, 'employee_id': employee.id,
            'company_id': cls.company.id, 'wage': 1000.0, 'state': 'open',
            'date_start': '2026-01-01', 'resource_calendar_id': cls.calendar.id,
            'type_id': cls.kind.id}, **vals))

    def cols(self, used, code=1):
        return {'used': {str(k): v for k, v in used.items()},
                'identity': {'code': code, 'name': 0, 'email': 0}, 'heads': {}}

    def review(self, rows, used):
        answer = self.Upd.review(csv_b64(rows), 'p2b.csv', self.cols(used))
        self.assertTrue(answer['ok'], answer.get('msg'))
        return answer

    def row_of(self, answer, employee):
        return next(r for r in answer['rows'] if r['emp_id'] == employee.id)

    def line(self, employee, code):
        contract = self.contracts[employee.id]
        return contract.advantages_ids.filtered(
            lambda l: l.advantage_template_id.code == code)

    # =====================================================================
    # B1-B7 — pay items by pay scheme
    # =====================================================================
    def test_B1_item_only_in_one_scheme(self):
        answer = self.review([['Code', 'Site allowance'],
                              ['P2B0001', '700'], ['P2B0002', '700']], {2: X})
        ann, bob = self.row_of(answer, self.ann), self.row_of(answer, self.bob)
        self.assertEqual(ann['cells'][X]['status'], 'ok')
        cell = bob['cells'][X]
        self.assertEqual(cell['status'], 'off_scheme')
        self.assertEqual(cell['new'], '700')
        self.assertIn('P2B Daily rate', cell['why'])
        self.assertIn('P2B Site allowance', cell['why'])
        self.assertIn('P2B Bob', cell['why'])
        self.assertNotIn('P2BX', cell['why'], "never a rule code in a sentence")
        self.assertEqual(answer['changes'], [
            {'emp_id': self.ann.id, 'field_id': X, 'value': '700'}])
        self.assertEqual(ann['scheme'], 'P2B Monthly staff')
        self.assertEqual(bob['scheme'], 'P2B Daily rate')
        self.assertFalse(ann['no_scheme'])

    def test_B2_a_line_already_on_the_contract_stands(self):
        answer = self.review([['Code', 'Site allowance'], ['P2B0003', '300']], {2: X})
        cell = self.row_of(answer, self.bea)['cells'][X]
        self.assertEqual(cell['status'], 'ok', cell.get('why'))
        self.assertEqual(cell['old'], '250')
        self.assertEqual(answer['changes'], [
            {'emp_id': self.bea.id, 'field_id': X, 'value': '300'}])

    def test_B3_nobody_covers_the_person(self):
        answer = self.review([['Code', 'Site allowance', 'Job'],
                              ['P2B0005', '400', 'Fitter']], {2: X, 3: JOB})
        row = self.row_of(answer, self.ned)
        self.assertEqual(row['cells'][X]['status'], 'ok', "desk verdict stands")
        self.assertTrue(row['no_scheme'])
        self.assertEqual(row['scheme'], '')
        self.assertEqual(answer['no_scheme'], 1)

    def test_B4_monthly_and_off_cycle_schemes(self):
        answer = self.review([['Code', 'Advance cap', 'Field bonus', 'Transport'],
                              ['P2B0004', '900', '50', '10']], {2: Z, 3: W, 4: Y})
        row = self.row_of(answer, self.cat)
        self.assertEqual(row['cells'][Z]['status'], 'ok', row['cells'][Z].get('why'))
        self.assertEqual(row['cells'][W]['status'], 'ok')
        self.assertEqual(row['cells'][Y]['status'], 'off_scheme')
        why = row['cells'][Y]['why']
        self.assertIn('P2B Field monthly', why)
        self.assertIn('P2B Field advance', why)
        self.assertEqual(sorted(row['scheme_ids']),
                         sorted([self.field_end.id, self.field_mid.id]))

    def test_B5_apply_drops_an_off_scheme_change(self):
        before = self.line(self.bob, 'P2BX')
        self.assertFalse(before)
        answer = self.Upd.apply(
            'P2B bypass', csv_b64([['Code', 'X'], ['P2B0002', '700']]), 'b5.csv',
            self.cols({2: X}),
            [{'emp_id': self.bob.id, 'field_id': X, 'value': '700'}], {'rows': 1})
        self.assertTrue(answer['ok'])
        self.assertTrue(answer.get('nothing'))
        self.assertEqual(answer['skipped_off_scheme'], 1)
        self.assertIn('pay scheme', answer['msg'])
        self.assertFalse(self.line(self.bob, 'P2BX'), "nothing written")
        # With an in-scheme change beside it, only the off-scheme one drops.
        mixed = self.Upd.apply(
            'P2B mixed', '', '', self.cols({2: X}),
            [{'emp_id': self.bob.id, 'field_id': X, 'value': '700'},
             {'emp_id': self.ann.id, 'field_id': X, 'value': '800'}],
            {'rows': 2, 'off_scheme': 0})
        self.assertEqual(mixed['written'], 1)
        self.assertEqual(mixed['skipped_off_scheme'], 1)
        self.assertEqual(mixed['off_scheme'], 1)
        self.assertFalse(self.line(self.bob, 'P2BX'))
        self.assertEqual(self.line(self.ann, 'P2BX').amount, 800.0)
        batch = self.env['pb.updates.batch'].browse(mixed['batch_id'])
        self.assertEqual(batch.values_off_scheme, 1)
        row = self.Upd._batch_row(batch, True)
        self.assertEqual(row['values_off_scheme'], 1)

    def test_B6_a_scheme_item_with_no_line_anywhere(self):
        plain = {c['id'] for g in self.Desk.get_fields(0)['groups'] for c in g['fields']}
        self.assertNotIn(Z, plain, "the Records screen never offers it")
        topics = {t['key']: t for t in self.Upd.get_home()['topics']}
        offered = {f['id']: f for f in topics['component']['fields']}
        self.assertIn(Z, offered)
        self.assertEqual([s['name'] for s in offered[Z]['schemes']], ['P2B Field advance'])
        answer = self.review([['Code', 'Advance cap'], ['P2B0004', '1200']], {2: Z})
        self.assertEqual(answer['changes'], [
            {'emp_id': self.cat.id, 'field_id': Z, 'value': '1200'}])
        done = self.Upd.apply('P2B new line', '', '', self.cols({2: Z}),
                              answer['changes'], {'rows': 1})
        self.assertEqual(done['written'], 1, done.get('refused'))
        self.assertEqual(self.line(self.cat, 'P2BZ').amount, 1200.0)
        # …and the Records screen's History can undo it (the door follows
        # the apply, not the screen).
        undo = self.Desk.undo_apply(done['apply_id'])
        self.assertTrue(undo['ok'])
        self.assertEqual(undo['restored'], 1)
        self.assertFalse(self.line(self.cat, 'P2BZ'), "back to no line")

    def test_B7_read_columns_counts_the_schemes_in_the_file(self):
        b64 = csv_b64([['Code', 'Site allowance'],
                       ['P2B0001', '1'], ['P2B0002', '1'], ['P2B0003', '1'],
                       ['P2B0004', '1'], ['P2B0005', '1'], ['NOBODY', '1']])
        out = self.Upd.read_columns(b64, 'b7.csv')
        self.assertTrue(out['ok'], out.get('msg'))
        counts = {s['name']: s['count'] for s in out['schemes']}
        self.assertEqual(counts, {'P2B Daily rate': 2, 'P2B Monthly staff': 1,
                                  'P2B Field monthly': 1, 'P2B Field advance': 1})
        self.assertEqual(out['schemes'][0]['name'], 'P2B Daily rate', "biggest first")
        self.assertEqual(out['no_scheme'], 1)
        pay = next(t for t in out['fields'] if t['key'] == 'component')['fields']
        by_id = {f['id']: f for f in pay}
        self.assertEqual(sorted(s['name'] for s in by_id[Y]['schemes']),
                         ['P2B Daily rate', 'P2B Monthly staff'])
        self.assertEqual([s['name'] for s in by_id[T]['schemes']], ['P2B Monthly staff'])
        # The same counts once the column that finds the person is chosen by
        # hand (the match screen asks again).
        again = self.Upd.file_schemes(b64, 'b7.csv', {'code': 1})
        self.assertEqual({s['name']: s['count'] for s in again['schemes']}, counts)
        self.assertEqual(again['no_scheme'], 1)
        self.assertEqual(self.Upd.file_schemes(b64, 'b7.csv', {})['schemes'], [])

    def test_B7b_recheck_and_the_sheet(self):
        res = self.Upd.recheck([{'emp_id': self.bob.id, 'field_id': X, 'value': '5'},
                                {'emp_id': self.ann.id, 'field_id': X, 'value': '5'}])
        by_emp = {i['emp_id']: i for i in res['items']}
        self.assertEqual(by_emp[self.bob.id]['status'], 'off_scheme')
        self.assertEqual(by_emp[self.ann.id]['status'], 'ok')
        self.assertEqual(res['people'][str(self.bob.id)]['scheme'], 'P2B Daily rate')
        if openpyxl is None:
            return
        sheet = self.Upd.download_sheet(['component'], {'employee_ids': [
            self.ann.id, self.bob.id, self.bea.id]})
        self.assertTrue(sheet['ok'], sheet.get('msg'))
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(sheet['file_b64'])))
        ws = wb['Records']
        heads = {ws.cell(row=1, column=c).value: c for c in range(1, ws.max_column + 1)}
        self.assertIn('P2B Site allowance', heads)
        self.assertNotIn('P2B Field bonus', heads, "nobody here is paid under it")
        rows = {ws.cell(row=r, column=1).value: r for r in range(2, ws.max_row + 1)}
        cell = ws.cell(row=rows['P2B0002'], column=heads['P2B Site allowance'])
        self.assertIsNone(cell.value)
        self.assertEqual(cell.fill.fgColor.rgb[-6:], 'EEEEF2', "greyed for Bob")
        bea = ws.cell(row=rows['P2B0003'], column=heads['P2B Site allowance'])
        self.assertEqual(bea.value, 250, "Bea's real line is shown, not greyed")
        self.assertEqual(wb.sheetnames[0], 'Records')
        notes = wb[wb.sheetnames[-1]]
        text = ' '.join(str(c.value or '') for c in notes['A'])
        self.assertIn('CLEAR', text)
        self.assertIn('Grey cells', text)
        self.assertNotIn('Odoo', text)
        # The sheet comes back through the same door unchanged: 0 changes.
        back = self.Upd.read_columns(sheet['file_b64'], sheet['filename'])
        columns = {'used': {}, 'identity': {}, 'heads': {}}
        for col in back['columns']:
            target = col.get('target') or ''
            if target.startswith('identity:'):
                columns['identity'][target.split(':')[1]] = col['idx']
            elif target:
                columns['used'][str(col['idx'])] = target
        again = self.Upd.review(sheet['file_b64'], sheet['filename'], columns)
        self.assertEqual(again['changes'], [])

    # =====================================================================
    # B8-B9 — CLEAR
    # =====================================================================
    def test_B8_clear_then_undo_restores_everything(self):
        ann = self.ann
        contract = self.contracts[ann.id]
        self.Upd.apply('P2B seed', '', '', self.cols({2: Y}), [
            {'emp_id': ann.id, 'field_id': Y, 'value': '120'},
            {'emp_id': ann.id, 'field_id': T, 'value': 'XL'}], {'rows': 1})
        self.assertEqual(self.line(ann, 'P2BY').amount, 120.0)
        self.assertEqual(self.line(ann, 'P2BT').text_value, 'XL')
        before = (ann.job_title, ann.parent_id, contract.date_end)
        self.assertTrue(all(before))
        rows = [['Code', 'Job', 'Manager', 'End', 'Transport', 'Uniform'],
                ['P2B0001', 'CLEAR', 'clear', ' Clear ', 'CLEAR', 'CLEAR']]
        used = {2: JOB, 3: MANAGER, 4: END, 5: Y, 6: T}
        answer = self.review(rows, used)
        cells = self.row_of(answer, ann)['cells']
        for fid in (JOB, MANAGER, END, Y, T):
            self.assertEqual(cells[fid]['status'], 'ok', (fid, cells[fid].get('why')))
            self.assertTrue(cells[fid].get('cleared'), fid)
            self.assertEqual(cells[fid]['value'], '')
        self.assertEqual(cells[Y]['new'], '0', "an amount clears to 0")
        self.assertEqual(cells[Y]['old'], '120')
        self.assertEqual(cells[JOB]['old'], 'Operator')
        done = self.Upd.apply('P2B clear', csv_b64(rows), 'clear.csv',
                              self.cols(used), answer['changes'], {'rows': 1})
        self.assertEqual(done['written'], 5, done.get('refused'))
        contract.invalidate_recordset()
        ann.invalidate_recordset()
        self.assertFalse(ann.job_title)
        self.assertFalse(ann.parent_id)
        self.assertFalse(contract.date_end)
        self.assertEqual(self.line(ann, 'P2BY').amount, 0.0)
        self.assertFalse(self.line(ann, 'P2BT').text_value)
        undo = self.Upd.undo(done['batch_id'])
        self.assertTrue(undo['ok'])
        self.assertEqual(undo['restored'], 5)
        contract.invalidate_recordset()
        ann.invalidate_recordset()
        self.assertEqual((ann.job_title, ann.parent_id, contract.date_end), before)
        self.assertEqual(self.line(ann, 'P2BY').amount, 120.0)
        self.assertEqual(self.line(ann, 'P2BT').text_value, 'XL')

    def test_B8b_clearing_what_is_empty_is_the_same(self):
        answer = self.review([['Code', 'Field bonus', 'End'],
                              ['P2B0004', 'CLEAR', 'CLEAR']], {2: W, 3: END})
        cells = self.row_of(answer, self.cat)['cells']
        self.assertEqual(cells[W]['status'], 'same', "no line, nothing to clear")
        self.assertEqual(cells[END]['status'], 'same')
        self.assertEqual(answer['changes'], [])

    def test_B9_clear_refused_on_required_and_bank(self):
        answer = self.review([['Code', 'Wage', 'Start', 'Bank'],
                              ['P2B0001', 'CLEAR', 'CLEAR', 'CLEAR']],
                             {2: WAGE, 3: START, 4: BANK_NAME})
        cells = self.row_of(answer, self.ann)['cells']
        self.assertEqual(cells[WAGE]['status'], 'refused')
        self.assertEqual(cells[WAGE]['why'], 'Wage cannot be empty.')
        self.assertEqual(cells[START]['status'], 'refused')
        self.assertTrue(cells[START]['why'].endswith('cannot be empty.'))
        self.assertEqual(cells[BANK_NAME]['status'], 'refused')
        self.assertEqual(cells[BANK_NAME]['why'],
                         "Bank details cannot be removed from a file. Change them "
                         "on the employee record.")
        self.assertEqual(answer['changes'], [])
        # The fix row's own check reads CLEAR the same way.
        res = self.Upd.recheck([{'emp_id': self.ann.id, 'field_id': WAGE, 'value': 'clear'}])
        self.assertEqual(res['items'][0]['status'], 'refused')

    # =====================================================================
    # B10 — the Records screen is unchanged
    # =====================================================================
    def test_B10_records_screen_keeps_its_rules(self):
        plain = {c['id']: c for g in self.Desk.get_fields(0)['groups'] for c in g['fields']}
        door = {c['id']: c for g in self.Door.get_fields(0)['groups'] for c in g['fields']}
        for fid, card in plain.items():
            self.assertEqual(door.get(fid), card, fid)
        self.assertTrue({Y, Z, W, T} <= set(door) - set(plain))
        self.assertIn(X, plain, "X is offered on Records only because Bea has a line")
        # CLEAR is text on the Records screen's own import…
        peek = self.Desk.import_peek(0, csv_b64([['Code', 'Job'], ['P2B0001', 'CLEAR']]),
                                     'r.csv', columns=self.cols({2: JOB}))
        self.assertEqual(peek['changes'], [
            {'emp_id': self.ann.id, 'field_id': JOB, 'value': 'CLEAR'}])
        self.assertEqual(peek['items'][0]['new_label'], 'CLEAR')
        # …an emptied wage on the Records grid still clears it to 0 (today's
        # behaviour, untouched), and a scheme-only pay item is still unknown.
        wage = self.Desk.preview_changes(0, [{'emp_id': self.ann.id, 'field_id': WAGE, 'value': ''}])
        self.assertEqual(wage['items'][0]['status'], 'ok')
        with self.assertRaises(Exception):
            self.Desk.preview_changes(0, [{'emp_id': self.cat.id, 'field_id': Z, 'value': '1'}])

    # =====================================================================
    # B11 — one contract for the sheet and the check
    # =====================================================================
    def test_B11_two_contracts_with_the_same_start(self):
        person = self._person('P2B Tie', 'P2B0099', self.team_a)
        first = self._contract(person, wage=1000.0)
        second = self._contract(person, wage=2000.0, state='draft')
        self.assertLess(first.id, second.id)
        probe = self.Desk._probe(0)
        self.assertEqual(probe._get_latest_contract(person), first)
        self.assertEqual(self.Desk._io_contracts(person)[person.id], first)
        if openpyxl is None:
            return
        sheet = self.Desk.export_records(0, {'employee_ids': person.ids}, [WAGE], 'data')
        peek = self.Desk.import_peek(0, sheet['file_b64'], 'tie.xlsx')
        self.assertTrue(peek['ok'], peek.get('msg'))
        self.assertEqual(peek['summary']['changes_ok'], 0)
        self.assertEqual([i['status'] for i in peek['items']], ['same'])
