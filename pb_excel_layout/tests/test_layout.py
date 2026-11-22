# -*- coding: utf-8 -*-
"""DOCSTUDIO X — layouts on saved Explorer views, any other source, the
scheduled send, access, translations (handover §6 tests 12–16, 18).

The world is the QF2 one (`pb_explorer` tests): one company, two
departments in two divisions, three people paid in April, an owner, a second
reader of each half. Subclassed for its `setUpClass` and helpers only — the
loader runs only the tests a class defines itself (G98).
"""
import base64
import io
import os
import re
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools.translate import PoFileReader

from odoo.addons.pb_explorer.tests.test_wdgap_qf2 import TestWdgapQf2

from . import fixtures as fx

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pack(sheet='Data', start_row=5):
    """A simple board pack: a title, the team's heading at B5, a sum on a
    second sheet."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws['A1'] = 'Payroll board pack'
    ws.cell(start_row, 2, 'Our heading')
    wb.create_sheet('Summary')['A1'] = '=SUM(%s!C:C)' % sheet
    return fx.wb_bytes(wb)


def _b64(raw):
    return base64.b64encode(raw).decode('ascii')


def _rows(raw, sheet='Data'):
    from openpyxl import load_workbook
    ws = load_workbook(io.BytesIO(raw))[sheet]
    return [[c.value for c in row] for row in ws.iter_rows()]


@tagged('post_install', '-at_install', 'docstudio_x')
class TestExcelLayout(TestWdgapQf2):

    def _board(self, user):
        return self.env['pb.excel.layout.board'].with_user(user).with_context(
            allowed_company_ids=[self.company.id], lang='en_US')

    def _layout(self, view, user=None, raw=None, start='B6', headers=True,
                shared=False, name='Board pack'):
        payload = self._board(user or self.owner).save({
            'name': name, 'file_b64': _b64(raw or _pack()),
            'file_name': 'pack.xlsx', 'sheet': 'Data', 'start': start,
            'headers': headers, 'shared': shared,
            'source_model': 'pb.explorer.view', 'source_id': view.id})
        return self.env['pb.excel.layout'].browse(payload['id'])

    # ------------------------------------------------------------ T12
    def test_t12_c1_on_a_saved_view(self):
        view = self._view(spec={'measure': 'net',
                                'dimension': 'department_id'})
        table = view.with_user(self.owner).with_context(
            allowed_company_ids=[self.company.id])._pbxl_table()
        self.assertEqual(set(table), {'title', 'columns', 'rows', 'truncated',
                                      'note'})
        self.assertEqual(table['title'], 'Net by department')
        for col in table['columns']:
            self.assertEqual(set(col), {'key', 'label', 'type'})
            self.assertIn(col['type'], ('text', 'number', 'money', 'date',
                                        'datetime', 'bool'))
        self.assertEqual(table['columns'][0]['type'], 'text')
        self.assertEqual(table['columns'][-1]['label'], 'Total')
        for row in table['rows']:
            self.assertEqual(len(row), len(table['columns']))
        names = {row[0] for row in table['rows']}
        self.assertEqual(names, {'Explorer Dept', 'Explorer Dept 2'})
        self.assertEqual(sum(row[-1] for row in table['rows']), 4800.0)

        # two currencies: ONE flat table with a Currency column, no blocks
        payload = self._fake_payload(self._two_currency_parts())
        with self._patch_query(payload):
            table = view.with_user(self.owner).with_context(
                allowed_company_ids=[self.company.id])._pbxl_table()
        self.assertEqual([c['label'] for c in table['columns']],
                         ['Department', 'Currency', 'April 2026', 'Total'])
        self.assertEqual([c['type'] for c in table['columns']],
                         ['text', 'text', 'money', 'money'])
        self.assertEqual(table['rows'], [
            ['Retail', 'VND', 1000000.0, 1000000.0],
            ['Bakery', 'VND', 500000.0, 500000.0],
            ['Retail', 'USD', 40.5, 40.5]])
        # cut rows and unconverted amounts are said, not silent
        payload = self._fake_payload(self._two_currency_parts(), truncated=3,
                                     unconverted=[{'currency': {'name': 'THB'},
                                                   'period': 'April 2026',
                                                   'amount': 5.0, 'note': ''}])
        with self._patch_query(payload):
            table = view.with_user(self.owner).with_context(
                allowed_company_ids=[self.company.id])._pbxl_table()
        self.assertTrue(table['truncated'])
        self.assertIn('3 more were left out', table['note'])
        self.assertIn('1 amounts could not be converted', table['note'])

    # ------------------------------------------------------------ T13
    def test_t13_c2_any_source_with_a_table(self):
        """Contract C2 is a registry button; contract C1 works for any model
        that has `_pbxl_table` — here a stub on contacts."""
        js = open(os.path.join(HERE, 'static', 'src', 'js', 'excel_layout.js'),
                  encoding='utf-8').read()
        self.assertIn('registry.category("pb_excel_layout").add("button", '
                      'PbExcelLayoutButton)', js)
        for prop in ('sourceModel: String', 'sourceId: Number',
                     'disabledReason: { type: String, optional: true }'):
            self.assertIn(prop, js)
        explorer = open(os.path.join(os.path.dirname(HERE), 'pb_explorer',
                                     'static', 'src', 'xml', 'explorer.xml'),
                        encoding='utf-8').read()
        self.assertIn('t-component="excelLayoutButton"', explorer)

        partner = self.env['res.partner'].create({'name': 'Stub source'})
        table = {'title': 'People list', 'truncated': False, 'note': '',
                 'columns': [{'key': 'n', 'label': 'Name', 'type': 'text'},
                             {'key': 'a', 'label': 'Amount', 'type': 'money'}],
                 'rows': [['Ana', 10.0], ['Binh', 20.0]]}
        Partner = type(self.env['res.partner'])
        with patch.object(Partner, '_pbxl_table', lambda self_: table,
                          create=True):
            board = self._board(self.plain)
            listed = board.list_for('res.partner', partner.id)
            self.assertEqual(listed['layouts'], [])
            tried = board.try_it(_b64(_pack()), 'Data', 'B6', True,
                                 'res.partner', partner.id, 'pack.xlsx')
            self.assertTrue(tried['ok'])
            rows = _rows(base64.b64decode(tried['file_b64']))
            self.assertEqual(rows[5][1:3], ['Name', 'Amount'])
            self.assertEqual(rows[7][1:3], ['Binh', 20.0])
            self.assertTrue(tried['filename'].endswith('.xlsx'))
            self.assertNotIn('odoo', tried['filename'].lower())
            saved = board.save({'name': 'People', 'file_b64': _b64(_pack()),
                                'file_name': 'pack.xlsx', 'sheet': 'Data',
                                'start': 'b6', 'headers': True,
                                'source_model': 'res.partner',
                                'source_id': partner.id})
            self.assertEqual(saved['start'], 'B6')
            got = board.download(saved['id'])
            self.assertFalse(got['fallback'])
            self.assertEqual(_rows(base64.b64decode(got['file_b64']))[6][1],
                             'Ana')
            # the layout breaks → the plain standard Excel, with the reason
            layout = self.env['pb.excel.layout'].browse(saved['id'])
            layout.sheet_ok = False
            got = board.download(saved['id'])
            self.assertTrue(got['fallback'])
            self.assertIn('“Data” is not in this file', got['msg'])
            self.assertEqual(_rows(base64.b64decode(got['file_b64']),
                                   'People list')[2], ['Name', 'Amount'])
        # a model WITHOUT the contract is refused
        with self.assertRaises(UserError):
            self._board(self.plain).list_for('res.partner', partner.id)
        with self.assertRaises(UserError):
            self._board(self.plain).list_for('ir.config_parameter', 1)

    # ------------------------------------------------------- X2, X3, X5
    def test_t13b_set_up_use_and_manage(self):
        view = self._view()
        board = self._board(self.owner)
        answer = board.inspect(_b64(_pack()), 'pack.xlsx',
                               'pb.explorer.view', view.id)
        self.assertTrue(answer['ok'])
        self.assertEqual([s['name'] for s in answer['sheets']],
                         ['Data', 'Summary'])
        table = view.with_user(self.owner).with_context(
            allowed_company_ids=[self.company.id])._pbxl_table()
        self.assertEqual(answer['table']['cols'], len(table['columns']))
        self.assertEqual(answer['table']['rows'], 2)
        self.assertEqual(answer['table']['labels'][0], 'Department')
        self.assertEqual(answer['sheets'][0]['suggested']['cell'], 'A2')
        self.assertIn('whole columns', answer['coach'])
        self.assertFalse(answer['macro_note'])
        peek = board.peek(_b64(_pack()), 'Summary', 'pack.xlsx')
        self.assertEqual(peek['sheet']['name'], 'Summary')

        layout = self._layout(view)
        self.assertEqual((layout.sheet_name, layout.start_cell,
                          layout.user_id), ('Data', 'B6', self.owner))
        listed = board.list_for('pb.explorer.view', view.id)
        self.assertEqual([l['name'] for l in listed['layouts']],
                         ['Board pack'])
        got = board.download(layout.id)
        rows = _rows(base64.b64decode(got['file_b64']))
        self.assertEqual(rows[5][1], 'Department')
        self.assertEqual({rows[6][1], rows[7][1]},
                         {'Explorer Dept', 'Explorer Dept 2'})
        self.assertIn('_board_pack_', got['filename'])
        self.assertNotIn('odoo', got['filename'].lower())
        self.assertTrue(layout.last_used)

        # rename, change the place, share; caps and words
        board.rename(layout.id, '  Monthly   pack ')
        self.assertEqual(layout.name, 'Monthly pack')
        board.update(layout.id, {'start': 'C8', 'headers': False})
        self.assertEqual((layout.start_cell, layout.write_headers),
                         ('C8', False))
        with self.assertRaises(UserError):
            board.update(layout.id, {'start': 'nonsense'})
        with self.assertRaises(UserError):
            board.update(layout.id, {'sheet': 'Gone'})

        # X5 — replace the file: the sheet is kept while it exists...
        res = board.replace_file(layout.id, _b64(_pack()), 'pack v2.xlsx')
        self.assertTrue(res['ok'])
        self.assertTrue(layout.sheet_ok)
        self.assertEqual(layout.start_cell, 'C8')
        # ...and said plainly when the new file has no such sheet
        res = board.replace_file(layout.id, _b64(_pack(sheet='Figures')),
                                 'pack v3.xlsx')
        self.assertFalse(layout.sheet_ok)
        self.assertIn('“Data” is not in this file', res['layout']['problem'])
        got = board.download(layout.id)
        self.assertTrue(got['fallback'], 'never a broken file')
        board.update(layout.id, {'sheet': 'Figures', 'start': 'B6'})
        self.assertTrue(layout.sheet_ok)
        self.assertFalse(board.download(layout.id)['fallback'])

        # a refused file never replaces a good one
        res = board.replace_file(layout.id, _b64(fx.encrypted()), 'x.xlsx')
        self.assertFalse(res['ok'])
        self.assertEqual(layout.file_name, 'pack v3.xlsx')

        board.remove(layout.id)
        self.assertFalse(layout.exists())

    def test_t13c_caps_and_merged_cells_at_set_up(self):
        view = self._view()
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.title = 'Data'
        wb.active.merge_cells('C10:D10')
        with self.assertRaisesRegex(UserError, 'Merged cells .C10:D10.'):
            self._layout(view, raw=fx.wb_bytes(wb))
        with self.assertRaises(UserError):
            self._layout(view, name='   ')
        Layout = self.env['pb.excel.layout']
        for i in range(20):
            Layout.create({'name': 'L%d' % i, 'user_id': self.owner.id,
                           'source_model': 'pb.explorer.view',
                           'source_id': view.id, 'file': _b64(_pack()),
                           'sheet_name': 'Data'})
        with self.assertRaisesRegex(UserError, '20 Excel layouts'):
            self._layout(view)
        self.assertFalse(self._board(self.owner).list_for(
            'pb.explorer.view', view.id)['can_add'])

    # ------------------------------------------------------------ T14
    def test_t14_scheduled_send_in_my_layout(self):
        Visibility = self.env['pb.group.visibility'].sudo()
        Visibility.set_for(self.reader_one.id, 'division', self.div_one.id)
        Visibility.set_for(self.reader_two.id, 'division', self.div_two.id)
        view = self._view(name='People by department', spec={
            'measure': 'headcount', 'dimension': 'department_id',
            'grain': 'none'})
        layout = self._layout(view, shared=True)
        drawer = self._as(self.owner).schedule_drawer(view.id)
        self.assertEqual([l['name'] for l in drawer['layouts']],
                         ['Board pack'])
        vals = {'cadence': 'weekly', 'weekday': '0', 'monthday': 1,
                'recipient_ids': [self.reader_one.id, self.reader_two.id],
                'layout_id': layout.id}
        payload = self._as(self.owner).schedule_save(view.id, vals)
        self.assertEqual((payload['layout_id'], payload['layout_name']),
                         (layout.id, 'Board pack'))
        sched = self.env['pb.explorer.schedule'].browse(payload['id'])

        # mail off: logged as today, nothing built
        sched._send_one('now')
        self.assertEqual(set(sched.log_ids.mapped('state')), {'email_off'})

        self._mail_on()
        sched.with_context(allowed_company_ids=[self.company_b.id])._send_one(
            'now')
        logs = sched.log_ids.filtered(lambda l: l.batch == sched.send_count)
        self.assertEqual(set(logs.mapped('state')), {'queued'})
        seen = {}
        for log in logs:
            att = log.mail_id.attachment_ids
            self.assertEqual(len(att), 1)
            self.assertTrue(att.name.startswith('payobook_board_pack_')
                            or 'board_pack' in att.name)
            rows = _rows(base64.b64decode(att.datas))
            self.assertEqual(rows[0][0], 'Payroll board pack', 'their own file')
            self.assertEqual(rows[5][1], 'Department')
            seen[log.user_id.id] = {r[1] for r in rows[6:] if r[1]}
        self.assertEqual(seen[self.reader_one.id], {'Explorer Dept'})
        self.assertEqual(seen[self.reader_two.id], {'Explorer Dept 2'})

        # a broken layout: the standard Excel goes, the history says why
        layout.sheet_ok = False
        summary = sched._send_one('now')
        self.assertEqual(summary['sent'], 2)
        logs = sched.log_ids.filtered(lambda l: l.batch == sched.send_count)
        self.assertEqual(set(logs.mapped('state')), {'layout_failed'})
        self.assertEqual(set(logs.mapped('reason')), {'sheet_missing|Data'})
        for log in logs:
            att = log.mail_id.attachment_ids
            rows = _rows(base64.b64decode(att.datas),
                         'People by department')
            self.assertEqual(rows[0][0], 'People by department',
                             'the Explorer’s own workbook')
        hist = sched._pbx_payload()['history'][0]
        self.assertEqual(hist['summary'], 'Sent to 2 of 2')
        self.assertIn('Sent as the standard Excel', hist['lines'][0]['label'])
        self.assertIn('“Data” is not in this file', hist['lines'][0]['label'])
        self.assertFalse(sched._pbx_payload()['layout_ok'])

        # choosing the standard Excel again clears it; a layout of another
        # view is refused in words
        payload = self._as(self.owner).schedule_save(
            view.id, dict(vals, layout_id=False), payload['id'])
        self.assertFalse(payload['layout_id'])
        other_view = self._view(name='Another')
        other = self._layout(other_view, name='Other')
        with self.assertRaisesRegex(UserError, 'no longer available'):
            self._as(self.owner).schedule_save(
                view.id, dict(vals, layout_id=other.id), payload['id'])

    # ------------------------------------------------------------ T15
    def test_t15_the_seam_changes_nothing_by_itself(self):
        Sched = self.env['pb.explorer.schedule']
        base = type(Sched).__mro__
        # the seam exists in pb_explorer and hands the standard file back
        from odoo.addons.pb_explorer.models.pb_explorer_schedule import \
            PbExplorerSchedule as Core
        view = self._view()
        sched = self._schedule(view, [self.owner])
        standard = ('a.xlsx', b'bytes', 'mime')
        self.assertIs(Core._pbx_attachment(sched, self.owner, standard),
                      standard)
        self.assertIn(Core, base)
        # with no layout chosen, this module hands it back too
        self.assertIs(sched._pbx_attachment(self.owner, standard,
                                            explorer=None, spec=None),
                      standard)
        source = open(os.path.join(os.path.dirname(HERE), 'pb_explorer',
                                   'models', 'pb_explorer.py'),
                      encoding='utf-8').read()
        for forbidden in ('.write(', '.create(', '.unlink('):
            self.assertNotIn(forbidden, source)

    # ------------------------------------------------------------ T16
    def test_t16_no_view_no_layout(self):
        view = self._view()                     # private to the owner
        layout = self._layout(view, shared=True)
        b64 = _b64(_pack())
        for user in (self.other, self.plain):
            board = self._board(user)
            with self.assertRaises(AccessError):
                board.list_for('pb.explorer.view', view.id)
            with self.assertRaises(AccessError):
                board.download(layout.id)
            with self.assertRaises(AccessError):
                board.try_it(b64, 'Data', 'B6', True, 'pb.explorer.view',
                             view.id, 'pack.xlsx')
            with self.assertRaises(AccessError):
                board.inspect(b64, 'pack.xlsx', 'pb.explorer.view', view.id)
            with self.assertRaises(AccessError):
                board.detail(layout.id)
            # and not through the ORM either
            self.assertFalse(self.env['pb.excel.layout'].with_user(user)
                             .search([]))
        # shared view: the other analytics reader may use the shared layout,
        # but never change it
        view.shared = True
        board = self._board(self.other)
        self.assertEqual([l['name'] for l in board.list_for(
            'pb.explorer.view', view.id)['layouts']], ['Board pack'])
        self.assertTrue(board.download(layout.id)['file_b64'])
        for call in (lambda: board.rename(layout.id, 'Mine now'),
                     lambda: board.remove(layout.id),
                     lambda: board.replace_file(layout.id, b64, 'x.xlsx')):
            with self.assertRaises(AccessError):
                call()
        # a private layout on a shared view stays private
        layout.shared = False
        self.assertEqual(board.list_for('pb.explorer.view', view.id)
                         ['layouts'], [])
        with self.assertRaises(AccessError):
            board.download(layout.id)
        # without the Explorer gate, not even a shared view
        with self.assertRaises(AccessError):
            self._board(self.plain).list_for('pb.explorer.view', view.id)

    # ------------------------------------------------------------ T18
    def test_t18_translations_and_static_gates(self):
        import polib
        i18n = os.path.join(HERE, 'i18n')
        template = polib.pofile(os.path.join(i18n, 'pb_excel_layout.pot'))
        every = {e.msgid for e in template if e.msgid}
        pot = {e.msgid for e in template if e.msgid and (
            'odoo-python' in e.comment or 'odoo-javascript' in e.comment)}
        self.assertGreater(len(pot), 60)
        for lang in ('vi_VN', 'id_ID'):
            path = os.path.join(i18n, '%s.po' % lang)
            # The parse gate (memory po-translation-loading-rules): the
            # platform's own reader, and only rows that reach a screen.
            with open(path, 'rb') as fh:
                rows = list(PoFileReader(fh))
            reach = {r['src'] for r in rows if r['type'] == 'code'
                     and r['value'] and ('odoo-python' in r['comments']
                                         or 'odoo-javascript' in r['comments'])}
            missing = sorted(t for t in pot if t not in reach)
            self.assertFalse(missing, '%s lacks %s' % (lang, missing[:5]))
            done = {e.msgid for e in polib.pofile(path) if e.msgstr}
            self.assertFalse(sorted(every - done), lang)
            for e in polib.pofile(path):
                self.assertNotIn('Odoo', e.msgstr)
                self.assertTrue(e.comment.startswith('module: pb_excel_layout'))
                for name in re.findall(r'%\((\w+)\)s', e.msgid):
                    self.assertIn('%%(%s)s' % name, e.msgstr, e.msgid)
                self.assertEqual(e.msgid.count('%s'), e.msgstr.count('%s'),
                                 e.msgid)
        # static gates on every file a user can see
        sources = []
        for root, _dirs, files in os.walk(HERE):
            if '/tests' in root:
                continue
            for name in files:
                if name.endswith(('.py', '.js', '.xml', '.scss', '.po',
                                  '.pot', '.csv')):
                    sources.append(os.path.join(root, name))
        emoji = re.compile('[\U0001F300-\U0001FAFF☀-➿]')
        for path in sources:
            body = open(path, encoding='utf-8').read()
            rel = os.path.relpath(path, HERE)
            self.assertFalse(emoji.search(body), '%s has an emoji' % rel)
            if path.endswith(('.js', '.xml')):
                self.assertFalse(re.findall(r'[A-Za-z]\(s\)', body), rel)
                self.assertNotIn('%%', body, rel)
            if path.endswith('.scss'):
                self.assertNotIn('gradient(', body, rel)
                self.assertFalse(re.search(r'\b(min|max)\(', body), rel)
            if path.endswith(('.js', '.xml')):
                # user-visible strings never name the platform
                for text in re.findall(r'_t\("([^"]*)"', body) + re.findall(
                        r'>([^<>{}]+)<', body):
                    self.assertNotIn('Odoo', text, rel)
            if path.endswith('.py'):
                for text in re.findall(r'_\(\s*"((?:[^"\\]|\\.)*)"', body):
                    self.assertNotIn('Odoo', text, rel)

    # ------------------------------------------------------- X-b T19
    def test_t19_every_row_in_my_layout(self):
        """Owner ruling X-b: a filled layout carries EVERY row of the view
        (cap 20,000, said when hit); the chart and the standard Excel / CSV
        keep the largest 24 exactly as before; a scheduled send in a layout
        gets every row too, as the recipient."""
        may = self._mk_run('XB May', '2026-05-01', '2026-05-31')
        for i in range(30):
            dept = self.env['hr.department'].create({
                'name': 'XB Dept %02d' % i, 'company_id': self.company.id})
            person = self._mk_employee('XB Person %02d' % i, dept)
            self._mk_slip(may, person, basic=1000.0 + i, net=800.0 + i,
                          emp_cost=100.0)
        self.builder.build_runs([may.id])
        spec = {'measure': 'net', 'dimension': 'department_id',
                'grain': 'none'}
        view = self._view(name='Every department', spec=spec)
        owner_view = view.with_user(self.owner).with_context(
            allowed_company_ids=[self.company.id])
        table = owner_view._pbxl_table()
        self.assertEqual(len(table['rows']), 32)        # 30 + April's two
        self.assertFalse(table['truncated'])
        self.assertFalse(table['note'])
        # the chart and the standard downloads: unchanged, largest 24
        explorer = self._as(self.owner)
        answer = explorer.query(spec)
        self.assertEqual(len(answer['series']), 24)
        self.assertEqual(answer['truncated'], 8)
        xl = explorer.export_xlsx(spec, view.id)
        self.assertEqual((xl['rows'], xl['truncated']), (24, 8))
        csv = explorer.export_csv(spec)
        self.assertEqual((csv['rows'], csv['truncated']), (24, 8))
        self.assertEqual(explorer._pbx_series_cap(), 24)
        # Download in my layout: every row
        layout = self._layout(view, headers=True)
        got = self._board(self.owner).download(layout.id)
        self.assertEqual(got['rows'], 32)
        rows = _rows(base64.b64decode(got['file_b64']))
        self.assertEqual(len([r for r in rows[6:] if r[1]]), 32)
        # a scheduled send in the layout: every row, as the recipient
        self._mail_on()
        sched = self._schedule(view, [self.owner])
        sched.layout_id = layout.id
        sched._send_one('now')
        att = sched.log_ids.mail_id.attachment_ids
        rows = _rows(base64.b64decode(att.datas))
        self.assertEqual(len([r for r in rows[6:] if r[1]]), 32)
        # the cap is said, never silent
        with patch('odoo.addons.pb_excel_layout.models.pb_explorer_view.'
                   '_EXPORT_CAP', 10):
            table = owner_view._pbxl_table()
        self.assertEqual(len(table['rows']), 10)
        self.assertTrue(table['truncated'])
        self.assertIn('Only the largest 10 rows are in the file; 22 more',
                      table['note'])

    # ------------------------------------------------------- X-b T20
    def test_t20_currency_column_never_moves(self):
        labels = {}
        for mode in ('group', 'own'):
            view = self._view(name='Money %s' % mode, spec={
                'measure': 'net', 'dimension': 'department_id',
                'grain': 'none', 'currency': mode})
            table = view.with_user(self.owner).with_context(
                allowed_company_ids=[self.company.id])._pbxl_table()
            labels[mode] = [c['label'] for c in table['columns']]
            self.assertEqual(labels[mode][:2], ['Department', 'Currency'])
            self.assertEqual(table['columns'][1]['type'], 'text')
            self.assertTrue(table['rows'])
            self.assertTrue(all(row[1] for row in table['rows']),
                            'every row names its money')
        self.assertEqual(labels['group'], labels['own'])
        # a count is not money: no Currency column
        view = self._view(name='People', spec={
            'measure': 'headcount', 'dimension': 'department_id',
            'grain': 'none'})
        table = view.with_user(self.owner).with_context(
            allowed_company_ids=[self.company.id])._pbxl_table()
        self.assertNotIn('Currency', [c['label'] for c in table['columns']])
        # the set-up screen's outline counts it: N columns from the table
        answer = self._board(self.owner).inspect(
            _b64(_pack()), 'pack.xlsx', 'pb.explorer.view', view.id)
        self.assertEqual(answer['table']['cols'], len(table['columns']))

    # ------------------------------------------------------- X-b T21
    def test_t21_recalculate_note_in_three_languages(self):
        board = self.env['pb.excel.layout.board']
        raw = _pack()
        expected = {
            'en_US': 'Totals and charts in your file refresh when it is '
                     'opened in Excel. Some other spreadsheet programs need '
                     '“Recalculate” pressed.',
            'vi_VN': 'Tổng và biểu đồ trong tệp của bạn tự cập nhật khi mở '
                     'bằng Excel. Một số chương trình bảng tính khác cần bấm '
                     '“Tính lại”.',
            'id_ID': 'Total dan grafik di berkas Anda diperbarui saat dibuka '
                     'di Excel. Beberapa program lembar kerja lain perlu '
                     'menekan “Hitung ulang”.',
        }
        for lang, text in expected.items():
            if lang != 'en_US' and not self.env['res.lang']._lang_get(lang):
                self.env['res.lang']._activate_lang(lang)
            answer = board.with_context(lang=lang)._pbxl_file_answer(
                raw, 'pack.xlsx')
            self.assertEqual(answer['recalc'], text, lang)
        xml = open(os.path.join(HERE, 'static', 'src', 'xml',
                                'excel_layout.xml'), encoding='utf-8').read()
        self.assertIn('state.file.recalc', xml)

    # ------------------------------------------------------------ R6
    def test_r6_silent_install(self):
        self.assertFalse(self.env['ir.cron'].sudo().search(
            [('cron_name', 'ilike', 'excel layout')]))
        self.assertFalse(self.env['ir.model.data'].sudo().search(
            [('module', '=', 'pb_excel_layout'),
             ('model', 'in', ('ir.cron', 'mail.template', 'pb.excel.layout',
                              'ir.config_parameter'))]))
