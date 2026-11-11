# -*- coding: utf-8 -*-
"""UPDATES P1 — the numbered cases of the handover (T1-T18), one test each
(two where a case has two halves).

Everything runs in Master records mode (`config_id = 0`), which is the only
mode Updates uses: the scheme-free catalogue of employee, contract, bank and
contract-component fields. Every record read or written here is created by the
transaction the test runs in. `hr.payslip` is never touched.

Fixtures follow `pb_records/tests/test_records_r3_roundtrip.py`: the company
publishes "No approval needed" for Records Desk changes (the approval path is
`pb_records`' own test), employees get badge codes, contracts are open.
"""
import base64
import csv
import io
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_updates.models.updates_batch import heading_fingerprint

try:
    import openpyxl
except ImportError:            # pragma: no cover — a declared dependency
    openpyxl = None

JOB = 'f:hr.employee:job_title'
PHONE = 'f:hr.employee:work_phone'
WAGE = 'f:hr.contract:wage'


def csv_b64(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    for row in rows:
        writer.writerow(row)
    return base64.b64encode(out.getvalue().encode('utf-8')).decode()


def xlsx_b64(wb):
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return base64.b64encode(out.read()).decode()


@tagged('post_install', '-at_install', 'pb_updates')
class TestUpdates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
            cls.env.company, 'records')
        cls.Desk = cls.env['pb.records.desk']
        cls.Upd = cls.env['pb.updates.desk']
        # UPDATES P2b: these cases predate pay-scheme awareness and are about
        # everything else, so nobody here is known to a pay scheme — on a
        # database whose main company has one, T18's "a pay item for a
        # contract without that line" would otherwise be greyed out by
        # design. Pay schemes have their own cases (test_updates_p2b.py).
        cls.startClassPatcher(patch.object(
            type(cls.Upd), '_people_schemes',
            lambda self, emp_ids: {int(i): {'ids': set(), 'name': '', 'via': ''}
                                   for i in (emp_ids or []) if i}))
        cls.Employee = cls.env['hr.employee']
        cls.Contract = cls.env['hr.contract']
        cls.company = cls.env.company

        def employee(name, code, **vals):
            return cls.Employee.create(dict({
                'name': name, 'barcode': code, 'company_id': cls.company.id,
                'work_email': '%s@updates.test' % code.lower(),
                'job_title': 'Operator', 'work_phone': '100'}, **vals))

        def contract(emp):
            return cls.Contract.create({
                'name': '%s contract' % emp.name, 'employee_id': emp.id,
                'wage': 1000.0, 'state': 'open', 'date_start': '2026-01-01'})

        cls.e1 = employee('Upd One', 'UPD0001')
        cls.e2 = employee('Upd Two', 'UPD0002')
        cls.e3 = employee('Upd Three', 'UPD0003')
        cls.c1, cls.c2, cls.c3 = contract(cls.e1), contract(cls.e2), contract(cls.e3)

        # A contract component the Master catalogue offers (it has a line on
        # SOME contract — U1), for T18.
        cls.template = cls.env['hr.contract.advantage.template'].create({
            'name': 'Updates site allowance', 'code': 'UPDSITE',
            'lower_bound': 0.0, 'upper_bound': 0.0, 'default_value': 0.0,
            'value_type': 'amount'})
        cls.env['hr.contract.advantage'].create({
            'contract_id': cls.c1.id, 'advantage_template_id': cls.template.id,
            'amount': 500.0})
        cls.everyone = {'employee_ids': [cls.e1.id, cls.e2.id, cls.e3.id]}

    # ---------------------------------------------------------------- helpers
    def foreign(self, rows=None):
        """A client's own file: Indonesian headings the desk does not know."""
        return csv_b64(rows or [
            ['NIK', 'Nama', 'Jabatan', 'Catatan'],
            ['UPD0001', 'Upd One', 'Line Lead', 'promoted'],
            ['UPD0002', 'Upd Two', 'Operator', ''],
            ['UPD0003', 'Upd Three', '', 'no change'],
        ])

    def cols(self, used, code=1, name=0, email=0, heads=None):
        return {'used': {str(k): v for k, v in used.items()},
                'identity': {'code': code, 'name': name, 'email': email},
                'heads': heads or {}}

    def export(self, fields=(JOB, PHONE)):
        res = self.Desk.export_records(0, self.everyone, list(fields), 'data')
        self.assertTrue(res.get('ok'), res.get('msg'))
        return res

    def label(self, field_id):
        for group in self.Desk.get_fields(0)['groups']:
            for card in group['fields']:
                if card['id'] == field_id:
                    return card['label']
        raise AssertionError('%s is not a Master records card' % field_id)

    def make_user(self, login, groups, company=None):
        company = company or self.company
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login,
            'company_id': company.id, 'company_ids': [(6, 0, company.ids)],
            'group_ids': [(6, 0, [self.env.ref(g).id for g in groups])]})

    def foreign_layout(self):
        """The remembered matching for `foreign()`'s headings — looked up by
        its own fingerprint, so a database holding other layouts is fine."""
        return self.env['pb.updates.layout'].search([
            ('company_id', '=', self.company.id),
            ('fingerprint', '=', heading_fingerprint(['NIK', 'Nama', 'Jabatan', 'Catatan']))])

    def apply_foreign(self, name='November pay changes'):
        b64 = self.foreign()
        columns = self.cols({3: JOB}, heads={1: 'NIK', 2: 'Nama', 3: 'Jabatan',
                                             4: 'Catatan'})
        review = self.Upd.review(b64, 'gaji.csv', columns)
        self.assertTrue(review['ok'], review.get('msg'))
        return self.Upd.apply(name, b64, 'gaji.csv', columns, review['changes'],
                              {'rows': 3, 'unmatched': 0, 'left_out': 0})

    # =====================================================================
    # pb_records seams
    # =====================================================================
    def test_T01_peek_without_columns_is_unchanged(self):
        res = self.export()
        peek = self.Desk.import_peek(0, res['file_b64'], 'sheet.xlsx')
        again = self.Desk.import_peek(0, res['file_b64'], 'sheet.xlsx', columns=None)
        self.assertTrue(peek['ok'], peek.get('msg'))
        self.assertEqual(peek, again)
        # The same contract as before the seam: a file just exported changes
        # nothing and matches everybody by code…
        self.assertEqual(peek['summary']['changes_ok'], 0)
        self.assertEqual(peek['summary']['people_unmatched'], 0)
        self.assertEqual(peek['identity'], 'code')
        self.assertEqual(peek['summary']['columns_used'], 2)
        # …plus the one additive key, in file order with file row numbers.
        self.assertEqual([m['row'] for m in peek['matched']], [2, 3, 4])
        self.assertEqual({m['emp_id'] for m in peek['matched']},
                         {self.e1.id, self.e2.id, self.e3.id})
        self.assertTrue(all(m['method'] == 'code' for m in peek['matched']))
        self.assertEqual(sum(m['cells'] for m in peek['matched']),
                         len(peek['changes']))

    def test_T02_columns_map_foreign_headings(self):
        peek = self.Desk.import_peek(0, self.foreign(), 'gaji.csv',
                                     columns=self.cols({3: JOB}))
        self.assertTrue(peek['ok'], peek.get('msg'))
        self.assertEqual({c['field_id'] for c in peek['changes']}, {JOB})
        ok = [i for i in peek['items'] if i['status'] == 'ok']
        self.assertEqual([(i['emp_id'], i['new_label']) for i in ok],
                         [(self.e1.id, 'Line Lead')])
        self.assertIn('Catatan', peek['summary']['columns_ignored'])
        self.assertEqual(self.e1.job_title, 'Operator', "a peek writes nothing")

    def test_T03_unknown_card_is_ignored_by_heading(self):
        peek = self.Desk.import_peek(
            0, self.foreign(), 'gaji.csv',
            columns=self.cols({3: JOB, 4: 'f:hr.employee:no_such_field'}))
        self.assertTrue(peek['ok'], peek.get('msg'))
        self.assertIn('Catatan', peek['summary']['columns_ignored'])
        self.assertEqual({c['field_id'] for c in peek['changes']}, {JOB})
        # Only an unknown card, nothing usable: a sentence, never an exception.
        alone = self.Desk.import_peek(
            0, self.foreign(), 'gaji.csv',
            columns=self.cols({4: 'f:hr.employee:no_such_field'}))
        self.assertFalse(alone['ok'])
        self.assertIn('Catatan', alone['columns_ignored'])

    def test_T04_same_card_on_two_columns_first_wins(self):
        b64 = csv_b64([
            ['NIK', 'Jabatan', 'Posisi'],
            ['UPD0001', 'From the first', 'From the second'],
        ])
        peek = self.Desk.import_peek(0, b64, 'two.csv',
                                     columns=self.cols({3: JOB, 2: JOB}))
        self.assertTrue(peek['ok'], peek.get('msg'))
        self.assertEqual(peek['changes'], [
            {'emp_id': self.e1.id, 'field_id': JOB, 'value': 'From the first'}])
        self.assertIn('Posisi', peek['summary']['columns_ignored'])

    def test_T05_import_columns_on_a_desk_export(self):
        res = self.export()
        out = self.Desk.import_columns(0, res['file_b64'], 'sheet.xlsx')
        self.assertTrue(out['ok'], out.get('msg'))
        self.assertEqual(out['rows'], 3)
        by_head = {c['head']: c for c in out['columns']}
        for head, key in (('Employee code', 'code'), ('Name', 'name'),
                          ('Work email', 'email')):
            self.assertEqual(by_head[head]['how'], 'identity')
            self.assertEqual(by_head[head]['identity'], key)
        data = [c for c in out['columns'] if c['how'] != 'identity']
        self.assertEqual([c['field_id'] for c in data], [JOB, PHONE])
        self.assertTrue(all(c['how'] == 'id' for c in data))
        self.assertEqual(by_head['Employee code']['samples'],
                         ['UPD0001', 'UPD0003', 'UPD0002'])
        self.assertTrue(all(len(c['samples']) == 3 for c in out['columns']))

    def test_T06_import_columns_on_foreign_headings(self):
        out = self.Desk.import_columns(0, self.foreign(), 'gaji.csv')
        self.assertTrue(out['ok'], out.get('msg'))
        by_head = {c['head']: c for c in out['columns']}
        for head in ('NIK', 'Nama', 'Jabatan', 'Catatan'):
            self.assertEqual(by_head[head]['how'], '', head)
            self.assertEqual(by_head[head]['field_id'], '', head)
        self.assertEqual(by_head['Jabatan']['samples'], ['Line Lead', 'Operator'])
        bad = self.Desk.import_columns(0, base64.b64encode(b'not a sheet').decode(),
                                       'file.pdf')
        self.assertFalse(bad['ok'])
        self.assertTrue(bad['msg'])

    # =====================================================================
    # pb_updates
    # =====================================================================
    def test_T07_matching_is_remembered(self):
        before = self.Upd.read_columns(self.foreign(), 'gaji.csv')
        self.assertTrue(before['ok'], before.get('msg'))
        self.assertFalse(before['layout_known'])
        answer = self.apply_foreign()
        self.assertTrue(answer.get('batch_id'))
        after = self.Upd.read_columns(self.foreign(), 'gaji.csv')
        self.assertTrue(after['layout_known'])
        by_head = {c['head']: c for c in after['columns']}
        self.assertEqual(by_head['NIK']['how'], 'memory')
        self.assertEqual(by_head['NIK']['identity'], 'code')
        self.assertEqual(by_head['Jabatan']['how'], 'memory')
        self.assertEqual(by_head['Jabatan']['field_id'], JOB)
        self.assertEqual(by_head['Catatan']['target'], 'ignore')
        layout = self.foreign_layout()
        self.assertEqual(len(layout), 1)
        self.assertEqual(layout.use_count, 1)
        # A different file that shares one heading still finds it.
        other = csv_b64([['NIK', 'Jabatan', 'Lain'], ['UPD0001', 'X', 'Y']])
        partial = self.Upd.read_columns(other, 'other.csv')
        self.assertFalse(partial['layout_known'])
        self.assertEqual({c['head']: c['how'] for c in partial['columns']}['Jabatan'],
                         'memory')

    def test_T08_near_miss_heading_is_a_guess(self):
        self.assertEqual(self.label(JOB), 'Job Title')
        b64 = csv_b64([['NIK', 'Job Titel', 'Zzqx Wibble'],
                       ['UPD0001', 'Lead', 'x']])
        out = self.Upd.read_columns(b64, 'near.csv')
        by_head = {c['head']: c for c in out['columns']}
        self.assertEqual(by_head['Job Titel']['how'], 'guess')
        self.assertEqual(by_head['Job Titel']['field_id'], JOB)
        self.assertEqual(by_head['Zzqx Wibble']['how'], '')
        self.assertEqual(by_head['Zzqx Wibble']['field_id'], '')

    def test_T08b_a_heading_that_names_the_person_finds_the_person(self):
        b64 = csv_b64([['Employee Name', 'Jabatan'], ['Upd One', 'Lead']])
        out = self.Upd.read_columns(b64, 'names.csv')
        col = {c['head']: c for c in out['columns']}['Employee Name']
        self.assertEqual((col['how'], col['identity'], col['field_id']),
                         ('identity', 'name', ''))

    def test_T09_review_payload(self):
        b64 = csv_b64([
            ['NIK', 'Jabatan', 'Telp'],
            ['UPD0003', 'Fitter', ''],
            ['UPD0001', 'Operator', '555'],
            ['', '', ''],
            ['UPD0002', '', '100'],
        ])
        review = self.Upd.review(b64, 'grid.csv', self.cols({2: JOB, 3: PHONE}))
        self.assertTrue(review['ok'], review.get('msg'))
        self.assertEqual([c['field_id'] for c in review['columns']], [JOB, PHONE])
        rows = review['rows']
        self.assertEqual([r['row'] for r in rows], [2, 3, 5], "file order, file rows")
        self.assertEqual([r['emp_id'] for r in rows],
                         [self.e3.id, self.e1.id, self.e2.id])
        first, second, third = rows
        self.assertEqual(first['name'], 'Upd Three')
        self.assertEqual(first['code'], 'UPD0003')
        self.assertEqual(first['cells'][JOB]['status'], 'ok')
        self.assertEqual(first['cells'][JOB]['old'], 'Operator')
        self.assertEqual(first['cells'][JOB]['new'], 'Fitter')
        self.assertNotIn(PHONE, first['cells'], "a blank cell is absent")
        self.assertEqual(second['cells'][JOB]['status'], 'same')
        self.assertEqual(second['cells'][PHONE]['status'], 'ok')
        self.assertEqual(second['cells'][PHONE]['new'], '555')
        self.assertNotIn(JOB, third['cells'])
        self.assertEqual(third['cells'][PHONE]['status'], 'same')
        self.assertEqual(sorted((c['emp_id'], c['field_id']) for c in review['changes']),
                         sorted([(self.e3.id, JOB), (self.e1.id, PHONE)]))
        self.assertEqual(self.e3.job_title, 'Operator', "a review writes nothing")

    def test_T09b_same_person_twice(self):
        """R3: two file rows for one person. The desk evaluates both and would
        write both in file order, so the LOWER row wins; Updates shows the
        earlier cell as overridden and does not send it."""
        b64 = csv_b64([['NIK', 'Jabatan'],
                       ['UPD0001', 'First try'],
                       ['UPD0001', 'Second try']])
        peek = self.Desk.import_peek(0, b64, 'twice.csv', columns=self.cols({2: JOB}))
        self.assertEqual([i['status'] for i in peek['items']], ['ok', 'ok'])
        desk_answer = self.Desk.apply_changes(0, peek['changes'], note='twice')
        self.assertEqual(desk_answer['written'], 2)
        self.assertEqual(self.e1.job_title, 'Second try', "the desk: the lower row wins")
        self.Desk.undo_apply(desk_answer['apply_id'])
        self.assertEqual(self.e1.job_title, 'Operator')

        review = self.Upd.review(b64, 'twice.csv', self.cols({2: JOB}))
        top, bottom = review['rows']
        self.assertTrue(top['twice'] and bottom['twice'])
        self.assertEqual(top['cells'][JOB]['status'], 'dup')
        self.assertEqual(bottom['cells'][JOB]['status'], 'ok')
        self.assertEqual(review['changes'], [
            {'emp_id': self.e1.id, 'field_id': JOB, 'value': 'Second try'}])

    def test_T10_unmatched_row_is_listed_never_created(self):
        count = self.Employee.search_count([])
        b64 = csv_b64([['NIK', 'Jabatan'],
                       ['UPD0001', 'Lead'],
                       ['NOBODY99', 'Ghost']])
        review = self.Upd.review(b64, 'ghost.csv', self.cols({2: JOB}))
        self.assertTrue(review['ok'], review.get('msg'))
        self.assertEqual(len(review['unmatched']), 1)
        row = review['unmatched'][0]
        self.assertEqual(row['row'], 3)
        self.assertEqual(row['code'], 'NOBODY99')
        self.assertIn('NOBODY99', row['why'])
        self.assertEqual(row['values'], {JOB: 'Ghost'})
        answer = self.Upd.apply('Ghost test', b64, 'ghost.csv', self.cols({2: JOB}),
                                review['changes'])
        self.assertTrue(answer['batch_id'])
        self.assertEqual(self.Employee.search_count([]), count,
                         "an unmatched row never becomes an employee")
        # Bound by hand, its values are judged like any other.
        rechecked = self.Upd.recheck([{'emp_id': self.e2.id, 'field_id': JOB,
                                       'value': 'Ghost'}])
        self.assertEqual(rechecked['items'][0]['status'], 'ok')

    def test_T11_apply(self):
        answer = self.apply_foreign()
        self.assertTrue(answer['ok'])
        self.assertEqual(answer['written'], 1)
        self.assertEqual(self.e1.job_title, 'Line Lead')
        batch = self.env['pb.updates.batch'].browse(answer['batch_id'])
        self.assertEqual(batch.name, 'November pay changes')
        self.assertEqual(batch.filename, 'gaji.csv')
        self.assertEqual(batch.company_id, self.company)
        self.assertEqual(batch.rows_total, 3)
        self.assertEqual(batch.apply_ids.ids, [answer['apply_id']])
        self.assertEqual(batch.apply_ids.source, 'import')
        self.assertEqual(batch.apply_ids.note, 'November pay changes')
        att = batch.attachment_id
        self.assertTrue(att)
        self.assertEqual((att.res_model, att.res_id), ('pb.updates.batch', batch.id))
        self.assertFalse(att.public)
        self.assertEqual(base64.b64decode(att.datas), base64.b64decode(self.foreign()))
        layout = self.foreign_layout()
        self.assertEqual(layout.get_map(), {'nik': 'identity:code', 'nama': 'ignore',
                                            'jabatan': JOB, 'catatan': 'ignore'})
        history = self.Upd.get_history()['batches']
        self.assertEqual(history[0]['id'], batch.id)
        self.assertEqual(history[0]['state'], 'applied')
        self.assertEqual((history[0]['people'], history[0]['values']), (1, 1))
        self.assertTrue(history[0]['can_undo'])
        self.assertEqual(history[0]['file_id'], att.id)
        self.assertFalse(self.env['hr.payslip'].search_count(
            [('employee_id', 'in', [self.e1.id, self.e2.id, self.e3.id])]))

    def test_T12_apply_with_nothing_to_change(self):
        before = self.env['pb.updates.batch'].search_count([])
        same = [{'emp_id': self.e1.id, 'field_id': JOB, 'value': 'Operator'}]
        answer = self.Upd.apply('Nothing', self.foreign(), 'gaji.csv',
                                self.cols({3: JOB}), same)
        self.assertTrue(answer['ok'])
        self.assertEqual(answer['batch_id'], 0)
        self.assertTrue(answer['nothing'])
        self.assertTrue(answer['msg'])
        self.assertEqual(self.env['pb.updates.batch'].search_count([]), before)
        empty = self.Upd.apply('Nothing', self.foreign(), 'gaji.csv',
                               self.cols({3: JOB}), [])
        self.assertFalse(empty['ok'])
        self.assertTrue(empty['msg'])

    def test_T13_blank_name_is_refused(self):
        before = self.env['pb.updates.batch'].search_count([])
        changes = [{'emp_id': self.e1.id, 'field_id': JOB, 'value': 'Lead'}]
        for name in ('', '   ', None):
            answer = self.Upd.apply(name, self.foreign(), 'gaji.csv',
                                    self.cols({3: JOB}), changes)
            self.assertFalse(answer['ok'])
            self.assertTrue(answer['msg'])
        self.assertEqual(self.e1.job_title, 'Operator')
        self.assertEqual(self.env['pb.updates.batch'].search_count([]), before)

    def test_T14_undo(self):
        answer = self.apply_foreign()
        undo = self.Upd.undo(answer['batch_id'])
        self.assertTrue(undo['ok'], undo.get('msg'))
        self.assertEqual(undo['restored'], 1)
        self.assertEqual(self.e1.job_title, 'Operator')
        row = self.Upd.get_history()['batches'][0]
        self.assertEqual(row['state'], 'undone')
        self.assertFalse(row['can_undo'])
        again = self.Upd.undo(answer['batch_id'])
        self.assertFalse(again['ok'])
        self.assertTrue(again['msg'])
        missing = self.Upd.undo(999999999)
        self.assertFalse(missing['ok'])

    def test_T15_undo_keeps_a_value_changed_since(self):
        answer = self.apply_foreign()
        self.e1.job_title = 'Changed by someone else'
        undo = self.Upd.undo(answer['batch_id'])
        self.assertTrue(undo['ok'])
        self.assertEqual(undo['restored'], 0)
        self.assertEqual(undo['skipped_changed_since'], 1)
        self.assertEqual(self.e1.job_title, 'Changed by someone else')

    def test_T16_viewer_may_review_but_not_apply(self):
        before = self.env['pb.updates.batch'].search_count([])
        viewer = self.make_user('updates-viewer', ['pb_records.group_records_viewer'])
        upd = self.Upd.with_user(viewer)
        home = upd.get_home()
        self.assertFalse(home['can_write'])
        self.assertFalse(home['can_export'])
        self.assertFalse(upd.download_sheet(['employee'])['ok'])
        cols = upd.read_columns(self.foreign(), 'gaji.csv')
        self.assertTrue(cols['ok'], cols.get('msg'))
        review = upd.review(self.foreign(), 'gaji.csv', self.cols({3: JOB}))
        self.assertTrue(review['ok'], review.get('msg'))
        cell = review['rows'][0]['cells'][JOB]
        self.assertEqual(cell['status'], 'refused')
        self.assertTrue(cell['why'])
        answer = upd.apply('Viewer try', self.foreign(), 'gaji.csv', self.cols({3: JOB}),
                           [{'emp_id': self.e1.id, 'field_id': JOB, 'value': 'Lead'}])
        self.assertFalse(answer['ok'])
        self.assertIn('permission', answer['msg'])
        self.assertEqual(self.e1.job_title, 'Operator')
        self.assertEqual(self.env['pb.updates.batch'].search_count([]), before)

    def test_T16b_hr_user_applies_and_undoes(self):
        hr_user = self.make_user('updates-hr', ['hr.group_hr_user'])
        upd = self.Upd.with_user(hr_user)
        b64 = self.foreign()
        columns = self.cols({3: JOB}, heads={1: 'NIK', 3: 'Jabatan'})
        review = upd.review(b64, 'gaji.csv', columns)
        answer = upd.apply('HR user update', b64, 'gaji.csv', columns, review['changes'])
        self.assertTrue(answer.get('batch_id'), answer)
        self.assertEqual(self.e1.job_title, 'Line Lead')
        self.assertEqual(upd.get_history()['batches'][0]['name'], 'HR user update')
        self.assertTrue(upd.undo(answer['batch_id'])['ok'])
        self.assertEqual(self.e1.job_title, 'Operator')

    def test_T17_other_company_sees_nothing(self):
        self.apply_foreign('Company one update')
        other = self.env['res.company'].create({'name': 'Updates Other Co'})
        stranger = self.make_user('updates-other', ['hr.group_hr_user'], company=other)
        upd = self.Upd.with_user(stranger).with_company(other)
        self.assertEqual(upd.get_history()['batches'], [])
        self.assertFalse(self.env['pb.updates.batch'].with_user(stranger).search([]))
        self.assertFalse(self.env['pb.updates.layout'].with_user(stranger).search([]))
        cols = upd.read_columns(self.foreign(), 'gaji.csv')
        self.assertFalse(cols['layout_known'])
        self.assertFalse([c for c in cols['columns'] if c['how'] == 'memory'])
        mine = self.env['pb.updates.batch'].search([], limit=1)
        self.assertFalse(upd.undo(mine.id)['ok'])

    def test_T18_component_for_a_contract_without_that_line(self):
        """R3 / T18: the desk ADDS the line. The catalogue offers `c:UPDSITE`
        because e1's contract has it; e2's contract does not, and the desk
        creates the line on apply (and Undo removes it again)."""
        card = 'c:UPDSITE'
        self.assertIn(card, self.Desk._cards(0))
        Line = self.env['hr.contract.advantage']
        self.assertFalse(Line.search([('contract_id', '=', self.c2.id)]))
        b64 = csv_b64([['NIK', 'Site'], ['UPD0002', '750']])
        review = self.Upd.review(b64, 'site.csv', self.cols({2: card}))
        cell = review['rows'][0]['cells'][card]
        self.assertEqual((cell['status'], cell['old']), ('ok', ''))
        answer = self.Upd.apply('Site allowance', b64, 'site.csv',
                                self.cols({2: card}), review['changes'])
        self.assertEqual(answer['written'], 1)
        line = Line.search([('contract_id', '=', self.c2.id),
                            ('advantage_template_id', '=', self.template.id)])
        self.assertEqual(len(line), 1)
        self.assertEqual(line.amount, 750.0)
        self.assertTrue(self.Upd.undo(answer['batch_id'])['ok'])
        self.assertFalse(Line.search([('contract_id', '=', self.c2.id)]),
                         "undo takes a first entry back to absence")

    # =====================================================================
    # Edges the screens rely on
    # =====================================================================
    def test_home_topics_and_download(self):
        home = self.Upd.get_home()
        keys = [t['key'] for t in home['topics']]
        self.assertEqual(keys[:3], ['employee', 'contract', 'bank'])
        self.assertIn('component', keys)
        self.assertEqual({t['key']: t['label'] for t in home['topics']}['component'],
                         'Ongoing pay items')
        self.assertTrue(home['can_write'] and home['can_export'])
        self.assertGreaterEqual(home['people_count'], 3)
        sheet = self.Upd.download_sheet(['bank'], self.everyone)
        self.assertTrue(sheet['ok'], sheet.get('msg'))
        self.assertTrue(sheet['filename'].endswith('.xlsx'))
        self.assertIn('update sheet', sheet['filename'])
        self.assertEqual(sheet['columns'], 4)
        self.assertFalse(self.Upd.download_sheet([])['ok'])

    def test_payobook_sheet_skips_matching(self):
        res = self.export()
        out = self.Upd.read_columns(res['file_b64'], 'sheet.xlsx')
        self.assertTrue(out['from_sheet'])
        foreign = self.Upd.read_columns(self.foreign(), 'gaji.csv')
        self.assertFalse(foreign['from_sheet'])

    def test_read_only_fields_are_not_offered_and_not_flagged(self):
        """A field read-only on the record is never in the sheet nor in the
        "Goes to" list; and a sheet that still carries one, unchanged, shows
        it as staying the same rather than as something to fix."""
        readonly = [c['id'] for g in self.Desk.get_fields(0)['groups']
                    for c in g['fields'] if not c['editable'] and not c.get('locked')]
        offered = {f['id'] for t in self.Upd.get_home()['topics'] for f in t['fields']}
        self.assertFalse(set(readonly) & offered)
        if not readonly:
            self.skipTest("no read-only Master records field on this build")
        res = self.export(fields=(JOB, readonly[0]))
        cols = self.Upd.read_columns(res['file_b64'], 'sheet.xlsx')
        self.assertTrue(cols['from_sheet'])
        columns = {'used': {}, 'identity': {}, 'heads': {}}
        for c in cols['columns']:
            if c['identity']:
                columns['identity'][c['identity']] = c['idx']
            elif c['field_id']:
                columns['used'][str(c['idx'])] = c['field_id']
        review = self.Upd.review(res['file_b64'], 'sheet.xlsx', columns)
        statuses = {cell['status'] for row in review['rows'] for cell in row['cells'].values()}
        self.assertNotIn('refused', statuses)
        self.assertEqual(review['changes'], [])

    def test_text_equal_to_today_is_never_a_change(self):
        """Live finding (ledger G11): a named reference is matched by NAME, so
        a namesake record or a department's full path came back as a change
        from an untouched sheet. Text equal to what is shown today stays the
        same and is never sent; a real change still goes through."""
        Cal = self.env['resource.calendar']
        mine = Cal.create({'name': 'Updates Twin Hours', 'company_id': self.company.id})
        Cal.create({'name': 'Updates Twin Hours', 'company_id': self.company.id})
        self.e1.resource_calendar_id = mine
        parent = self.env['hr.department'].create({'name': 'Upd Parent', 'company_id': self.company.id})
        child = self.env['hr.department'].create({'name': 'Upd Child', 'parent_id': parent.id,
                                                  'company_id': self.company.id})
        self.e1.department_id = child
        cal_card, dept_card = 'f:hr.employee:resource_calendar_id', 'f:hr.employee:department_id'
        cards = self.Desk._cards(0)
        self.assertIn(cal_card, cards)
        self.assertIn(dept_card, cards)
        res = self.export(fields=(cal_card, dept_card, JOB))
        cols = self.Upd.read_columns(res['file_b64'], 'sheet.xlsx')
        columns = {'used': {}, 'identity': {}, 'heads': {}}
        for c in cols['columns']:
            if c['identity']:
                columns['identity'][c['identity']] = c['idx']
            elif c['field_id']:
                columns['used'][str(c['idx'])] = c['field_id']
        # What the desk alone would say about the same untouched file.
        peek = self.Desk.import_peek(0, res['file_b64'], 'sheet.xlsx')
        desk_says = {(i['emp_id'], i['field_id']): i for i in peek['items']}
        review = self.Upd.review(res['file_b64'], 'sheet.xlsx', columns)
        row = next(r for r in review['rows'] if r['emp_id'] == self.e1.id)
        for card in (cal_card, dept_card):
            self.assertEqual(row['cells'][card]['status'], 'same',
                             (card, desk_says.get((self.e1.id, card))))
        self.assertEqual(review['changes'], [])
        # A real edit in the same file is still a change.
        b64 = csv_b64([['NIK', 'Jabatan'], ['UPD0001', 'operator']])
        real = self.Upd.review(b64, 'case.csv', self.cols({2: JOB}))
        self.assertEqual(real['rows'][0]['cells'][JOB]['status'], 'ok')

    def test_unreadable_and_headings_only(self):
        bad = self.Upd.read_columns(base64.b64encode(b'\x00\x01garbage').decode(),
                                    'broken.xlsx')
        self.assertFalse(bad['ok'])
        self.assertTrue(bad['msg'])
        only = self.Upd.read_columns(csv_b64([['NIK', 'Jabatan']]), 'empty.csv')
        self.assertFalse(only['ok'])
        self.assertTrue(only['empty'])
        no_identity = self.Upd.review(self.foreign(), 'gaji.csv',
                                      self.cols({3: JOB}, code=0))
        self.assertFalse(no_identity['ok'])
        nothing = self.Upd.review(self.foreign(), 'gaji.csv', self.cols({}))
        self.assertFalse(nothing['ok'])

    def test_no_odoo_in_visible_strings(self):
        """White-label: no user-visible string of this module says the word."""
        import os
        import re
        from odoo.modules.module import get_module_path
        root = get_module_path('pb_updates')
        pattern = re.compile(r'odoo', re.I)
        for rel in ('static/src/xml/updates_desk.xml',):
            with open(os.path.join(root, rel), encoding='utf-8') as fh:
                text = fh.read()
            # Template text and attribute values only; technical names
            # (`t-name="pb_updates…"`) never contain the word anyway.
            for line in text.splitlines():
                if 'odoo' in line.lower() and 't-name' not in line and 'templates' not in line:
                    self.fail("visible 'Odoo' in %s: %s" % (rel, line.strip()))
        with open(os.path.join(root, 'i18n', 'vi_VN.po'), encoding='utf-8') as fh:
            for line in fh:
                if line.startswith(('msgid', 'msgstr')) and pattern.search(line):
                    self.fail("'Odoo' in a translation: %s" % line.strip())
