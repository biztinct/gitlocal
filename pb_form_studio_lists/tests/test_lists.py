# -*- coding: utf-8 -*-
"""FS-4 numbered tests (docs/handovers/formstudio/FS4_REPORT.md §4).

FS-4 registers no host of its own: the employee and contract hosts belong to
FS-2 / FS-3. Where they are not installed, this suite lends the engine two
minimal hosts so custom fields can be made on `hr.employee` / `hr.contract`.
Case 11 (browser walk) is in the report.
"""
import base64
import io
import re
import time
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE_DIR = Path(__file__).resolve().parent.parent
KIT_DIR = MODULE_DIR.parent / 'pb_filter_kit'

FALLBACK_HOSTS = {
    'pbfl_employee': {
        'model': 'hr.employee', 'title': 'Employee', 'icon': 'user',
        'sections': [{'id': 'custom', 'title': 'Company details', 'icon': 'sparkles',
                      'tone': 'brand', 'kind': 'open'}],
        'default_layout': {'custom': []}, 'std_fields': [], 'custom_section': 'custom',
        'country_field': 'country_id', 'country_view_field': 'country_id',
        'copy_custom': False, 'native_views': [],
    },
    'pbfl_contract': {
        'model': 'hr.contract', 'title': 'Contract', 'icon': 'fileText',
        'sections': [{'id': 'custom', 'title': 'Company details', 'icon': 'sparkles',
                      'tone': 'brand', 'kind': 'open'}],
        'default_layout': {'custom': []}, 'std_fields': [], 'custom_section': 'custom',
        'country_field': 'employee_id.country_id', 'country_view_field': False,
        'copy_custom': True, 'native_views': [],
    },
}


def _xlsx(res):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(res['file_b64'])))
    ws = wb.active
    rows = [[c for c in r] for r in ws.iter_rows()]
    return ws, rows


@tagged('post_install', '-at_install', 'pb_form_studio_lists')
class TestLists(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Studio = type(cls.env['pb.form.studio'])
        orig_hosts = Studio._pbfs_hosts

        def hosts(self):
            out = orig_hosts(self)
            for key, host in FALLBACK_HOSTS.items():
                if not any(h['model'] == host['model'] for h in out.values()):
                    out[key] = dict(host)
            return out
        cls.startClassPatcher(patch.object(Studio, '_pbfs_hosts', hosts))
        # The engine's "pay run busy" probe reads pg_locks across EVERY
        # database of the cluster (report gotcha FS4-1): another builder's
        # test run must not refuse our fields.
        cls.startClassPatcher(patch.object(Studio, '_pbfs_busy', lambda self: ''))

        cls.Studio = cls.env['pb.form.studio']
        hosts_now = cls.Studio._pbfs_hosts()
        cls.emp_host = next(k for k, h in hosts_now.items() if h['model'] == 'hr.employee')
        cls.con_host = next(k for k, h in hosts_now.items() if h['model'] == 'hr.contract')

        base = 'base.group_user,hr.group_hr_user,hr_contract.group_hr_contract_manager'
        cls.admin = new_test_user(cls.env, 'pbfl_admin', groups=base + ',base.group_system',
                                  name='DEMO List Admin')
        cls.hr = new_test_user(cls.env, 'pbfl_hr', groups=base, name='DEMO List HR')
        cls.hr2 = new_test_user(cls.env, 'pbfl_hr2', groups=base, name='DEMO List HR Two')
        cls.vn = cls.env.ref('base.vn')
        cls.india = cls.env.ref('base.in')
        cls.dept = cls.env['hr.department'].create({'name': 'DEMO Lists Dept'})
        Emp = cls.env['hr.employee']
        cls.emps = Emp.browse()
        today = date.today()
        for i, (name, ends) in enumerate([('DEMO Lan', 12), ('DEMO Arjun', None),
                                          ('DEMO Binh', 200), ('=HYPERLINK("x")', None)]):
            e = Emp.create({'name': name, 'department_id': cls.dept.id if i % 2 == 0 else False,
                            'country_id': (cls.vn if i % 2 == 0 else cls.india).id})
            c = cls.env['hr.contract'].create({
                'name': 'DEMO-C-%d' % i, 'employee_id': e.id, 'wage': 1000000 * (i + 1),
                'date_start': today - timedelta(days=100 + i),
                'date_end': (today + timedelta(days=ends)) if ends else False,
            })
            c.state = 'open'
            cls.emps |= e

    # ---------------------------------------------------------------- utils
    def make(self, host, label, kind='text', **kw):
        vals = dict({'type': kind, 'label': label, 'vis': 'all', 'list_ok': True}, **kw)
        return self.Studio.with_user(self.admin).create_field(host, vals)['name']

    def people(self, user=None, table=False):
        P = self.env['pb.people'].with_user(user or self.hr)
        return P.with_context(pbfl_table=True) if table else P

    def contracts(self, user=None, table=False):
        C = self.env['pb.contracts'].with_user(user or self.hr)
        return C.with_context(pbfl_table=True) if table else C

    def keys(self, Board):
        return [c['key'] for c in Board.pbf_columns()['columns']]

    # ------------------------------------------------------------------- 1
    def test_01_table_shows_the_same_rows_and_counts_as_the_cards(self):
        name = self.make(self.emp_host, 'DEMO Locker')
        cname = self.make(self.con_host, 'DEMO Site code')
        self.emps[0].write({name: 'L-12'})
        for filters, search in [({}, None), ({'status': ['open']}, None),
                                ({'department': [self.dept.id]}, None), ({}, 'DEMO'),
                                ({'ends': {'preset': 'next_30'}}, None), ({'ready': ['no']}, None)]:
            for sort in ('name', 'name_desc'):
                cards = self.people().get_roster_page(filters=filters, search=search, sort=sort)
                table = self.people(table=True).get_roster_page(filters=filters, search=search, sort=sort)
                self.assertEqual([r['id'] for r in cards['rows']], [r['id'] for r in table['rows']])
                self.assertEqual(cards['total'], table['total'])
                for a, b in zip(cards['rows'], table['rows']):
                    self.assertNotIn('pbfs', a, 'the cards get nothing new')
                    self.assertEqual(a, {k: v for k, v in b.items() if k != 'pbfs'},
                                     'same row, same wage, same everything')
        row = next(r for r in self.people(table=True).get_roster_page(search='DEMO Lan')['rows'])
        self.assertEqual(row['pbfs'][name], 'L-12')
        for filters in ({}, {'status': ['open']}, {'step': ['ending']}, {'structure': [False]}):
            cards = self.contracts().get_contracts_page(filters=filters)
            table = self.contracts(table=True).get_contracts_page(filters=filters)
            self.assertEqual([r['id'] for r in cards['rows']], [r['id'] for r in table['rows']])
            self.assertEqual(cards['total'], table['total'])
            self.assertEqual(cards.get('steps'), table.get('steps'))
            for r in table['rows']:
                self.assertIn(cname, r['pbfs'])

    # ------------------------------------------------------------------- 2
    def test_02_choose_reorder_reset_per_person_and_company_default(self):
        V = self.env['pb.filter.view']
        screen = self.people()._pbf_screen()
        mine = [{'key': 'name', 'on': True}, {'key': 'wage', 'on': True}, {'key': 'dept', 'on': False}]
        res = V.with_user(self.hr).pbf_columns_save(screen, columns=mine)
        self.assertEqual(res['mine'], mine)
        self.assertFalse(res['can_company'])
        self.assertIsNone(V.with_user(self.hr2).pbf_columns_read(screen)['mine'], 'per person')
        # junk is dropped, never refused
        res = V.with_user(self.hr).pbf_columns_save(screen, columns=[{'key': 'wage'}, 'dept', 'dept',
                                                                     {'key': None}, 7, True])
        self.assertEqual(res['mine'], [{'key': 'wage', 'on': True}, {'key': 'dept', 'on': True},
                                       {'key': 7, 'on': True}])
        # mode is remembered with the person's choice
        res = V.with_user(self.hr).pbf_columns_save(screen, mode='table')
        self.assertEqual(res['mode'], 'table')
        self.assertTrue(res['mine'], 'saving the mode keeps the columns')
        # company default: administrator only
        with self.assertRaises(AccessError):
            V.with_user(self.hr).pbf_columns_save(screen, columns=mine, scope='company')
        with self.assertRaises(AccessError):
            self.env['pb.list.layout'].with_user(self.hr).create({'screen': screen})
        company = [{'key': 'name', 'on': True}, {'key': 'ready', 'on': True}]
        res = V.with_user(self.admin).pbf_columns_save(screen, columns=company, scope='company')
        self.assertTrue(res['can_company'])
        self.assertEqual(V.with_user(self.hr2).pbf_columns_read(screen)['company'], company)
        # reset "Just me" → the company's columns show again; mode kept
        res = V.with_user(self.hr).pbf_columns_reset(screen)
        self.assertIsNone(res['mine'])
        self.assertEqual(res['mode'], 'table')
        self.assertEqual(res['company'], company)
        with self.assertRaises(AccessError):
            V.with_user(self.hr).pbf_columns_reset(screen, scope='company')
        V.with_user(self.admin).pbf_columns_reset(screen, scope='company')
        self.assertIsNone(V.with_user(self.hr2).pbf_columns_read(screen)['company'])
        # the person's column row is never a view tab
        row = V.with_user(self.hr)._pbf_columns_row(screen)
        self.assertTrue(row)
        tabs = [v['key'] for v in self.people(self.hr).pbf_layout()['views']]
        self.assertNotIn('v%d' % row.id, tabs)
        with self.assertRaises(UserError):
            V.with_user(self.hr).pbf_columns_read(screen + '::columns')

    # ------------------------------------------------------------------- 3
    def test_03_custom_column_follows_show_in_lists_and_delete_never_breaks(self):
        name = self.make(self.emp_host, 'DEMO Shirt size', list_ok=False)
        self.assertNotIn(name, self.keys(self.people()))
        self.Studio.with_user(self.admin).update_field('hr.employee', name, {'list_ok': True})
        cols = {c['key']: c for c in self.people().pbf_columns()['columns']}
        self.assertIn(name, cols)
        self.assertTrue(cols[name]['custom'] and cols[name]['default'])
        self.assertEqual(cols[name]['label'], 'DEMO Shirt size')
        screen = self.people()._pbf_screen()
        V = self.env['pb.filter.view']
        V.with_user(self.hr).pbf_columns_save(screen, columns=[{'key': name, 'on': True},
                                                               {'key': 'name', 'on': True}])
        V.with_user(self.admin).pbf_columns_save(screen, columns=[{'key': name, 'on': False}],
                                                 scope='company')
        self.Studio.with_user(self.admin).update_field('hr.employee', name, {'list_ok': False})
        self.assertNotIn(name, self.keys(self.people()))
        self.Studio.with_user(self.admin).update_field('hr.employee', name, {'list_ok': True})
        # a saved column set is NOT a reason to keep a field
        refs = self.Studio.with_user(self.admin).field_references('hr.employee', name)
        self.assertFalse([r for r in refs if r['kind'] == 'saved_view'], refs)
        self.Studio.with_user(self.admin).delete_field('hr.employee', name, confirm='DEMO Shirt size')
        self.assertNotIn(name, self.keys(self.people()))
        # the stored sets still name it; nothing breaks
        self.assertEqual(V.with_user(self.hr).pbf_columns_read(screen)['mine'][0]['key'], name)
        page = self.people(table=True).get_roster_page()
        self.assertTrue(page['rows'])
        res = self.people().pbf_export_table(columns=[name, 'name', 'wage'])
        self.assertTrue(res['ok'])
        ws, rows = _xlsx(res)
        self.assertEqual([c.value for c in rows[0]], ['Name', 'Monthly wage'])

    # ------------------------------------------------------------------- 4
    def test_04_visibility_country_and_money_in_table_and_excel(self):
        secret = self.make(self.emp_host, 'DEMO Admin note', vis='admin')
        open_f = self.make(self.emp_host, 'DEMO Badge colour')
        india = self.make(self.emp_host, 'DEMO PAN', country_ids=[self.india.id])
        money = self.make(self.emp_host, 'DEMO Allowance', kind='integer')
        lan = self.emps[0]          # VN
        arjun = self.emps[1]        # IN
        lan.sudo().write({secret: 'S3CRET', open_f: 'Blue', money: 1204})
        arjun.sudo().write({india: 'ABCDE1234F', secret: 'S3CRET2'})
        lan.sudo().write({india: 'leftover'})       # not for a Vietnam record
        # who sees the column
        self.assertNotIn(secret, self.keys(self.people(self.hr)))
        self.assertIn(secret, self.keys(self.people(self.admin)))
        # the page never carries it for the HR reader
        rows = self.people(self.hr, table=True).get_roster_page(search='DEMO')['rows']
        for r in rows:
            self.assertNotIn(secret, r['pbfs'])
            self.assertNotIn('S3CRET', str(r))
        # Country of Work: blank where the field does not apply. The record's
        # country is read by the engine through the host's path; pinned here
        # so the test holds whichever host (FS-2 or the fallback) is installed.
        Studio = type(self.env['pb.form.studio'])
        countries = {lan.id: self.vn.id, arjun.id: self.india.id}
        with patch.object(Studio, '_pbfs_record_countries',
                          lambda self, recs: {r.id: countries.get(r.id, False) for r in recs}):
            by_id = {r['id']: r for r in self.people(self.hr, table=True)
                     .get_roster_page(search='DEMO')['rows']}
            self.assertEqual(by_id[arjun.id]['pbfs'][india], 'ABCDE1234F')
            self.assertEqual(by_id[lan.id]['pbfs'][india], '')
            self.assertEqual(by_id[lan.id]['pbfs'][money], '1,204')
            # Excel: a forged column key is ignored, values as on screen
            res = self.people(self.hr).pbf_export_table(
                search='DEMO', sort='name', columns=['name', secret, india, money, 'wage', open_f])
            ws, rows = _xlsx(res)
            head = [c.value for c in rows[0]]
            self.assertEqual(head, ['Name', 'DEMO PAN', 'DEMO Allowance', 'Monthly wage',
                                    'DEMO Badge colour'])
            body = {r[0].value: r for r in rows[1:]}
            self.assertEqual(body['DEMO Arjun'][1].value, 'ABCDE1234F')
            self.assertIsNone(body['DEMO Lan'][1].value, 'not for a Vietnam record')
            self.assertEqual(body['DEMO Lan'][2].value, 1204)
            self.assertNotIn('S3CRET', str([[c.value for c in r] for r in rows]))
            # the money column is the card's wage, with the card's money sign
            card = {r['name']: r for r in self.people(self.hr).get_roster_page(search='DEMO')['rows']}
            self.assertEqual(body['DEMO Lan'][3].value, card['DEMO Lan']['wage'])
            self.assertIn(card['DEMO Lan']['currency'] or '#', body['DEMO Lan'][3].number_format)
            # the administrator's file has the admin field
            res = self.people(self.admin).pbf_export_table(search='DEMO', columns=['name', secret])
            self.assertIn('S3CRET', str([[c.value for c in r] for r in _xlsx(res)[1]]))

    def test_04b_excel_is_formula_safe_and_named_plainly(self):
        res = self.people(self.hr).pbf_export_table(search='HYPERLINK', columns=['name', 'dept'])
        self.assertTrue(res['ok'])
        self.assertRegex(res['filename'], r'^Employees \d{4}-\d{2}-\d{2}\.xlsx$')
        self.assertNotIn('odoo', (res['filename'] + res['mimetype']).lower())
        ws, rows = _xlsx(res)
        self.assertEqual(ws.title, 'Employees')
        cell = rows[1][0]
        self.assertEqual(cell.value, '=HYPERLINK("x")')
        self.assertEqual(cell.data_type, 's', 'text, never a formula')
        self.assertTrue(cell.quotePrefix)
        res = self.contracts(self.hr).pbf_export_table(columns=['employee', 'date_end', 'wage'])
        ws, rows = _xlsx(res)
        self.assertEqual(ws.title, 'Contracts')
        self.assertEqual(res['rows'], res['total'])
        self.assertFalse(res['truncated'])

    # ------------------------------------------------------------------- 5
    def test_05_paging_and_sort_unchanged(self):
        P, T = self.people(), self.people(table=True)
        for sort in [s['key'] for s in P.pbf_layout()['sorts']]:
            for offset in (0, 1, 2):
                a = P.get_roster_page(sort=sort, offset=offset, limit=2)
                b = T.get_roster_page(sort=sort, offset=offset, limit=2)
                self.assertEqual([r['id'] for r in a['rows']], [r['id'] for r in b['rows']])
                self.assertEqual(a['offset'], b['offset'])
        C, CT = self.contracts(), self.contracts(table=True)
        for sort in [s['key'] for s in C.pbf_layout()['sorts']]:
            a = C.get_contracts_page(sort=sort, offset=1, limit=2)
            b = CT.get_contracts_page(sort=sort, offset=1, limit=2)
            self.assertEqual([r['id'] for r in a['rows']], [r['id'] for r in b['rows']])
        # every heading's sort names a real sort of its board
        for Board in (P, C):
            sorts = {s['key'] for s in Board.pbf_layout()['sorts']}
            for col in Board.pbf_columns()['columns']:
                for key in (col.get('sort') or {}).values():
                    self.assertIn(key, sorts, (Board._name, col['key']))
        # bulk "Move to department" is the board's own, untouched
        res = self.env['pb.people'].with_user(self.hr).bulk_apply(self.emps[:2].ids, 'set_department',
                                                                  self.dept.id)
        self.assertTrue(res.get('ok'))

    # ------------------------------------------------------------------- 6
    def test_06_records_desk_choice_lives_in_the_store(self):
        V = self.env['pb.filter.view']
        cols = [{'key': 'emp_code', 'on': False}, {'key': 'f:hr.contract:wage', 'on': True},
                {'key': 41, 'on': True}]
        V.with_user(self.hr).pbf_columns_save('records.0', columns=cols)
        # "a new browser" = nothing but the server: the same person reads it back
        self.assertEqual(V.with_user(self.hr).pbf_columns_read('records.0')['mine'], cols)
        self.assertIsNone(V.with_user(self.hr2).pbf_columns_read('records.0')['mine'])
        self.assertIsNone(V.with_user(self.hr).pbf_columns_read('records.7')['mine'],
                          'one choice per scheme')
        js = (MODULE_DIR / 'static/src/js/records_columns.js').read_text()
        for needle in ('pb_records.fields.', 'pb_records.column_order.', 'pbf_columns_read',
                       'pbf_columns_save', 'records.'):
            self.assertIn(needle, js)

    # ------------------------------------------------------------------- 7
    def test_07_performance_500_people_10_custom_columns(self):
        names = [self.make(self.emp_host, 'DEMO Col %02d' % i,
                           kind='integer' if i % 3 == 0 else 'text') for i in range(10)]
        Emp = self.env['hr.employee']
        vals = []
        for i in range(500):
            v = {'name': 'DEMO Perf %03d' % i}
            for j, n in enumerate(names):
                v[n] = (i * j) if j % 3 == 0 else 'v%d' % i
            vals.append(v)
        Emp.create(vals)
        self.env.flush_all()
        P = self.people(self.hr)
        timings = {}
        counts = {}
        for label, Board in (('cards', P), ('table', P.with_context(pbfl_table=True))):
            best_q, best_t = None, None
            for _run in range(3):
                self.env.invalidate_all()
                q0 = self.env.cr.sql_log_count
                t0 = time.perf_counter()
                res = Board.get_roster_page(search='DEMO Perf', limit=60)
                dt = time.perf_counter() - t0
                q = self.env.cr.sql_log_count - q0
                best_q = q if best_q is None else min(best_q, q)
                best_t = dt if best_t is None else min(best_t, dt)
            counts[label], timings[label] = best_q, best_t
            self.assertEqual(len(res['rows']), 60)
        rows = P.with_context(pbfl_table=True).get_roster_page(search='DEMO Perf', limit=60)['rows']
        self.assertTrue(all(len(r['pbfs']) >= 10 for r in rows))
        extra = counts['table'] - counts['cards']
        print('FS4-PERF queries cards=%s table=%s extra=%s; seconds cards=%.3f table=%.3f'
              % (counts['cards'], counts['table'], extra, timings['cards'], timings['table']))
        # the values themselves come with the page's own read; the extra
        # queries are the engine's field settings, never one per row or column
        self.assertLessEqual(extra, 6)
        t0 = time.perf_counter()
        res = P.pbf_export_table(search='DEMO Perf', columns=['name'] + names)
        print('FS4-PERF excel 500 rows x 11 columns: %.2f s' % (time.perf_counter() - t0))
        self.assertEqual(res['rows'], 500)

    # ------------------------------------------------------------------- 8
    def test_08_other_boards_are_unchanged(self):
        Desk = self.env['pb.records.desk'].with_user(self.hr)
        self.assertEqual(Desk._pbf_columns(), [])
        info = Desk.pbf_columns()
        self.assertEqual(info['columns'], [])
        self.assertIsNone(info['mine'])
        self.assertFalse(Desk.pbf_export_table(columns=['x'])['ok'])
        layout = self.people(self.hr).pbf_layout()
        self.assertEqual(set(layout), {'screen', 'sections', 'groups', 'sorts', 'views', 'total',
                                       'extra'}, 'the panel payload is the same shape')
        # every other board on the kit has no table at all
        boards = list(self.env.registry['pb.filter.mixin']._inherit_children)
        self.assertIn('pb.people', boards)
        self.assertGreater(len(boards), 10)
        for n in boards:
            if n in ('pb.people', 'pb.contracts'):
                continue
            self.assertEqual(self.env[n]._pbf_columns(), [], n)

    # ------------------------------------------------------------------- 9
    def test_09_silent_install(self):
        self.assertEqual(self.env['pb.list.layout'].sudo().search_count([]), 0)
        self.assertEqual(self.env['pb.filter.view'].sudo().search_count(
            [('screen', '=like', '%::columns')]), 0)
        data = self.env['ir.model.data'].sudo().search([('module', '=', 'pb_form_studio_lists')])
        kinds = set(data.mapped('model'))
        self.assertFalse(kinds & {'ir.cron', 'mail.template', 'ir.actions.server', 'ir.ui.view',
                                  'ir.ui.menu', 'ir.model.fields.selection'}, kinds)
        fields = self.env['ir.model.fields'].sudo().search([('name', '=like', 'x_pbfs_%')])
        self.assertFalse(fields, 'no custom field is made by installing')

    # ------------------------------------------------------------------ 10
    def test_10_po_gate_and_no_platform_name(self):
        bad = re.compile(r'odoo', re.I)
        for root in (MODULE_DIR, KIT_DIR):
            for path in list((root / 'i18n').glob('*.po')) + list((root / 'i18n').glob('*.pot')):
                for line in path.read_text().splitlines():
                    if line.startswith(('msgid', 'msgstr')):
                        self.assertFalse(bad.search(line), '%s: %s' % (path.name, line))
        files = [MODULE_DIR / 'static/src/xml/people_table.xml',
                 MODULE_DIR / 'static/src/xml/contracts_table.xml',
                 KIT_DIR / 'static/src/xml/list_table.xml']
        for path in files:
            text = re.sub(r'<!--.*?-->', '', path.read_text(), flags=re.S)
            self.assertFalse(bad.search(text), path.name)
        js = list((MODULE_DIR / 'static/src/js').glob('*.js')) + [KIT_DIR / 'static/src/js/list_table.js']
        for path in js:
            for lit in re.findall(r'_t\("([^"]*)"', path.read_text()):
                self.assertFalse(bad.search(lit), '%s: %s' % (path.name, lit))
        for path in list((MODULE_DIR / 'models').glob('*.py')) + [KIT_DIR / 'models/filter_view.py',
                                                                  KIT_DIR / 'models/filter_mixin.py']:
            for lit in re.findall(r"_\('([^']*)'", path.read_text()):
                self.assertFalse(bad.search(lit), '%s: %s' % (path.name, lit))
        needles = {
            MODULE_DIR: ['msgid "Monthly wage"', 'msgid "Contract ends"', 'msgid "Employees"',
                         'msgid "Answers to check"', 'msgid "No bank details"'],
            KIT_DIR: ['msgid "Just me"', 'msgid "For everyone"', 'msgid "Save for everyone"',
                      'msgid "Columns"', 'msgid "Only an administrator can choose the columns '
                      'for everyone."'],
        }
        for root, wanted in needles.items():
            for lang in ('vi_VN', 'id_ID'):
                po = (root / 'i18n' / ('%s.po' % lang)).read_text()
                for needle in wanted:
                    self.assertIn(needle, po, '%s %s' % (root.name, lang))
                    block = po.split(needle, 1)[1].split('\n\n', 1)[0]
                    self.assertRegex(block, r'msgstr "[^"]+"', '%s %s %s' % (root.name, lang, needle))
