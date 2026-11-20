# -*- coding: utf-8 -*-
"""FS-8 numbered tests (docs/handovers/formstudio/FS8_REPORT.md §4).

World: the Explorer's own fact-engine fixtures (one company, two departments,
three people paid in April — `pb_explorer` test_fact_engine), plus a May run,
a second contract for one person, Countries of Work, and own fields made with
the Form builder engine on the REAL employee and contract hosts (FS-2 / FS-3,
merged on 19.1). Subclassed for its `setUpClass` only — the loader runs only
the tests a class defines itself (G98). Names are DEMO-prefixed.
"""
import base64
import io
import json
import os
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.pb_explorer.tests.test_fact_engine import TestFactEngine

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def key(model, name, grain=None):
    return ':'.join(['field', model, name] + ([grain] if grain else []))


@tagged('post_install', '-at_install', 'pb_form_studio_explorer')
class TestFs8(TestFactEngine):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Studio = type(cls.env['pb.form.studio'])
        # Pay runs of OTHER local databases share table oids (FS5-1 / FS1-8):
        # never let them refuse a field here. The busy rail is FS-1's test 8.
        cls.startClassPatcher(patch.object(Studio, '_pbfs_busy', lambda s: ''))
        internal = cls.env.ref('base.group_user')
        gate = cls.env.ref('pb_hr_payroll_base.group_payroll_base_manager')
        hr = cls.env.ref('hr.group_hr_user')
        system = cls.env.ref('base.group_system')

        def mk(login, groups):
            return cls.env['res.users'].with_context(no_reset_password=True).create({
                'name': 'DEMO FS8 %s' % login.title(), 'login': 'fs8_%s' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [g.id for g in groups])]})
        cls.analyst = mk('analyst', [internal, gate])            # payroll, not HR
        cls.hr_analyst = mk('hranalyst', [internal, gate, hr])   # payroll + HR
        cls.admin = mk('admin', [internal, gate, hr, system])    # administrator

        cls.vn, cls.india = cls.env.ref('base.vn'), cls.env.ref('base.in')
        cls.emp1.write({'payroll_country': 'VN'})
        cls.emp2.write({'payroll_country': 'VN'})
        cls.emp3.write({'payroll_country': 'IN'})

        S = cls.env['pb.form.studio'].with_user(cls.admin)

        def make(host, kind, label, **kw):
            vals = dict({'type': kind, 'label': label, 'vis': 'all', 'list_ok': True}, **kw)
            return S.create_field(host, vals)['name']
        E, C = 'employee_detail', 'contract'
        cls.f_shirt = make(E, 'select', 'DEMO Shirt size', options=['Small', 'Medium', 'Large'])
        cls.f_course = make(E, 'date', 'DEMO Safety course on')
        cls.f_fork = make(E, 'bool', 'DEMO Drives a forklift')
        cls.f_site = make(E, 'text', 'DEMO Home site')
        cls.f_team = make(E, 'm2o', 'DEMO Buddy team', comodel='hr.department')
        cls.f_hr = make(E, 'select', 'DEMO Union member', vis='hr', options=['Yes', 'No'])
        cls.f_secret = make(E, 'select', 'DEMO Secret band', vis='admin', options=['A', 'B'])
        cls.f_vn = make(E, 'select', 'DEMO Shuttle route', options=['East', 'West'],
                        country_ids=[cls.vn.id])
        cls.f_unmarked = make(E, 'select', 'DEMO Locker row', list_ok=False, options=['1', '2'])
        cls.f_num = make(E, 'integer', 'DEMO Shoe number')
        cls.f_long = make(E, 'longtext', 'DEMO Long note')
        cls.c_zone = make(C, 'select', 'DEMO Pay zone', options=['North', 'South'])

        cls.emp1.write({cls.f_shirt: 'opt_2', cls.f_course: '2026-02-10', cls.f_fork: True,
                        cls.f_site: 'Dock', cls.f_team: cls.dept2.id, cls.f_hr: 'opt_1',
                        cls.f_secret: 'opt_1', cls.f_vn: 'opt_1', cls.f_num: 41})
        cls.emp2.write({cls.f_shirt: 'opt_3', cls.f_course: '2026-05-03', cls.f_site: 'Yard',
                        cls.f_vn: 'opt_2'})
        # Arjun is in India and still has a value for the Vietnam-only field:
        # the value is kept (R10), it is only shown as "—".
        cls.emp3.write({cls.f_shirt: 'opt_2', cls.f_site: 'Dock', cls.f_vn: 'opt_1'})

        # emp1: the April payslip was made on the OLD contract (North); the
        # May payslip on a NEW contract (South) — test 4.
        Contract = cls.env['hr.contract']
        cls.old_contract = Contract.search([('employee_id', '=', cls.emp1.id)], limit=1)
        cls.old_contract.write({cls.c_zone: 'opt_1'})
        cls.new_contract = Contract.create({
            'name': 'DEMO new contract', 'employee_id': cls.emp1.id,
            'company_id': cls.company.id, 'date_start': '2026-05-01', 'wage': 1000.0,
            'type_id': cls.ctype.id, 'resource_calendar_id': cls.calendar.id,
            cls.c_zone: 'opt_2'})
        Contract.search([('employee_id', '=', cls.emp2.id)], limit=1).write({cls.c_zone: 'opt_2'})
        cls.may = cls._mk_run('DEMO Run May', '2026-05-01', '2026-05-31')
        slip = cls._mk_slip(cls.may, cls.emp1, basic=1100.0, net=900.0, emp_cost=160.0)
        slip.write({'contract_id': cls.new_contract.id})
        cls._mk_slip(cls.may, cls.emp2, basic=2100.0, net=1700.0, emp_cost=310.0)
        cls.builder.build_runs([cls.april.id, cls.may.id])

    # ------------------------------------------------------------ helpers
    def _as(self, user, model='pb.explorer'):
        return self.env[model].with_user(user).with_context(
            allowed_company_ids=[self.company.id]).with_company(self.company)

    @staticmethod
    def _series(payload):
        return {s['key']: s for s in payload['series']}

    # ================================================================== 1
    def test_01_split_headcount_by_a_choice_field(self):
        ex = self._as(self.analyst)
        res = ex.query({'measure': 'headcount', 'dimension': key('hr.employee', self.f_shirt),
                        'grain': 'none'})
        self.assertEqual(res['spec']['dimension'], key('hr.employee', self.f_shirt))
        self.assertEqual(res['dimension_label'], 'DEMO Shirt size')
        got = {s['label']: s['total'] for s in res['series']}
        self.assertEqual(got, {'Medium': 2.0, 'Large': 1.0})      # Lan + Arjun, Binh
        self.assertEqual(res['heads']['people'], 3)
        # Money split the same way adds up to the built-in total, to the cent.
        net = ex.query({'measure': 'net', 'dimension': key('hr.employee', self.f_shirt),
                        'grain': 'none'})
        whole = ex.query({'measure': 'net', 'dimension': 'none', 'grain': 'none'})
        self.assertAlmostEqual(net['grand_total'], whole['grand_total'], places=2)
        self.assertEqual({s['label']: s['total'] for s in net['series']},
                         {'Medium': 800.0 + 900.0 + 2400.0, 'Large': 1600.0 + 1700.0})
        # Cost per person by the field (numerator and denominator per person).
        cph = ex.query({'measure': 'cost_per_head',
                        'dimension': key('hr.employee', self.f_shirt), 'grain': 'none'})
        self.assertTrue(cph['series'])
        # Yes / No, short text and a link split too, with their screen words.
        fork = ex.query({'measure': 'headcount', 'dimension': key('hr.employee', self.f_fork),
                         'grain': 'none'})
        self.assertEqual({s['label']: s['total'] for s in fork['series']}, {'Yes': 1.0, 'No': 2.0})
        site = ex.query({'measure': 'headcount', 'dimension': key('hr.employee', self.f_site),
                         'grain': 'none'})
        self.assertEqual({s['label']: s['total'] for s in site['series']}, {'Dock': 2.0, 'Yard': 1.0})
        team = ex.query({'measure': 'headcount', 'dimension': key('hr.employee', self.f_team),
                         'grain': 'none'})
        self.assertEqual({s['label']: s['total'] for s in team['series']},
                         {self.dept2.display_name: 1.0, 'Not filled in': 2.0})
        # Component-level questions are refused in words (one person, many components).
        with self.assertRaises(UserError):
            ex.query({'measure': 'component', 'dimension': key('hr.employee', self.f_shirt)})

    def test_01b_kinds_not_offered(self):
        dims = {d['value'] for d in self._as(self.admin).get_schema()['dimensions']}
        for name in (self.f_unmarked, self.f_num, self.f_long):
            self.assertFalse([d for d in dims if name in d], name)
        self.assertIn(key('hr.employee', self.f_shirt), dims)
        self.assertIn(key('hr.contract', self.c_zone), dims)
        for grain in ('month', 'quarter', 'year'):
            self.assertIn(key('hr.employee', self.f_course, grain), dims)

    # ================================================================== 2
    def test_02_filter_by_a_choice_field(self):
        ex = self._as(self.analyst)
        k = key('hr.employee', self.f_shirt)
        schema = ex.get_schema()
        self.assertIn(k, {f['key'] for f in schema['extra_filters']})
        self.assertEqual([o['label'] for o in schema['options'][k]],
                         ['Small', 'Medium', 'Large', 'Not filled in'])
        res = ex.query({'measure': 'headcount', 'dimension': 'department_id', 'grain': 'none',
                        'filters': {k: ['opt_2']}})
        self.assertEqual(res['spec']['filters'], {k: ['opt_2']})
        self.assertEqual(res['heads']['people'], 2)
        self.assertEqual(sum(s['total'] for s in res['series']), 2.0)
        net = ex.query({'measure': 'net', 'dimension': 'none', 'grain': 'month',
                        'filters': {k: ['opt_2']}})
        self.assertAlmostEqual(net['grand_total'], 800.0 + 2400.0 + 900.0, places=2)
        # The drill covers exactly the same people.
        drill = ex.drill({'measure': 'net', 'dimension': 'department_id',
                          'filters': {k: ['opt_2']}}, '_all', '_all', 0)
        self.assertEqual({r['employee_id'] for r in drill['rows']},
                         {self.emp1.id, self.emp3.id})
        # The drill of one split cell, too.
        cell = ex.drill({'measure': 'net', 'dimension': k, 'grain': 'none'}, 'opt_3', '_all', 0)
        self.assertEqual({r['employee_id'] for r in cell['rows']}, {self.emp2.id})
        # The movement story honours it (only the people kept by the filter).
        story = ex.narrate({'measure': 'net', 'dimension': 'none', 'filters': {k: ['opt_3']}})
        self.assertTrue(story['ok'])
        self.assertEqual(story['waterfall']['end'], 1700.0)

    # ================================================================== 3
    def test_03_date_field_by_quarter(self):
        ex = self._as(self.analyst)
        k = key('hr.employee', self.f_course, 'quarter')
        res = ex.query({'measure': 'headcount', 'dimension': k, 'grain': 'none'})
        self.assertEqual([(s['key'], s['label'], s['total']) for s in res['series']],
                         [('2026-Q1', 'Q1 2026', 1.0), ('2026-Q2', 'Q2 2026', 1.0),
                          ('__none__', 'Not filled in', 1.0)])
        self.assertIn('DEMO Safety course on', res['dimension_label'])
        month = ex.query({'measure': 'headcount',
                          'dimension': key('hr.employee', self.f_course, 'month'),
                          'grain': 'none'})
        self.assertEqual([s['key'] for s in month['series']], ['2026-02', '2026-05', '__none__'])
        year = ex.query({'measure': 'headcount',
                         'dimension': key('hr.employee', self.f_course, 'year'), 'grain': 'none'})
        self.assertEqual({s['key']: s['total'] for s in year['series']},
                         {'2026': 2.0, '__none__': 1.0})
        # Filter by a quarter.
        flt = ex.query({'measure': 'headcount', 'dimension': 'none', 'grain': 'none',
                        'filters': {k: ['2026-Q2']}})
        self.assertEqual(flt['heads']['people'], 1)

    # ================================================================== 4
    def test_04_contract_field_follows_each_payslip(self):
        """Lan's April payslip was made on the North contract, her May one on
        the South contract: April's money is North's even though her contract
        today says South."""
        ex = self._as(self.analyst)
        k = key('hr.contract', self.c_zone)
        res = ex.query({'measure': 'net', 'dimension': k, 'grain': 'run'})
        cats = [c['key'] for c in res['categories']]
        by = {s['label']: dict(zip(cats, s['values'])) for s in res['series']}
        april, may = str(self.april.id), str(self.may.id)
        self.assertEqual(by['North'][april], 800.0)
        self.assertEqual(by['North'].get(may, 0.0), 0.0)
        self.assertEqual(by['South'][may], 900.0 + 1700.0)
        self.assertEqual(by['South'][april], 1600.0)
        self.assertEqual(by['Not filled in'][april], 2400.0)       # Arjun's contract: empty
        self.assertIn('Contract', next(d['sub'] for d in ex.get_schema()['dimensions']
                                       if d['value'] == k))

    # ================================================================== 5
    def test_05_visibility_picker_and_direct_call(self):
        k_hr, k_secret = key('hr.employee', self.f_hr), key('hr.employee', self.f_secret)
        for user, seen, unseen in ((self.analyst, [], [k_hr, k_secret]),
                                   (self.hr_analyst, [k_hr], [k_secret]),
                                   (self.admin, [k_hr, k_secret], [])):
            ex = self._as(user)
            schema = ex.get_schema()
            dims = {d['value'] for d in schema['dimensions']}
            filters = {f['key'] for f in schema.get('extra_filters') or []}
            text = json.dumps(schema, default=str)
            for k in seen:
                self.assertIn(k, dims, (user.login, k))
                self.assertIn(k, filters, (user.login, k))
            for k, label in ((k_hr, 'DEMO Union member'), (k_secret, 'DEMO Secret band')):
                if k not in unseen:
                    continue
                self.assertNotIn(k, dims, (user.login, k))
                self.assertNotIn(label, text, (user.login, k))
                # Direct call: no split by it, no filter by it, nothing of it back.
                res = ex.query({'measure': 'headcount', 'dimension': k, 'grain': 'none',
                                'filters': {k: ['opt_1']}})
                self.assertEqual(res['spec']['dimension'], 'none')
                self.assertNotIn(k, res['spec']['filters'])
                self.assertEqual(res['heads']['people'], 3)       # the filter did nothing
                body = json.dumps(res, default=str)
                self.assertNotIn(label, body)
                self.assertNotIn(self.f_hr if k == k_hr else self.f_secret, body)
                drill = ex.drill({'measure': 'net', 'dimension': k}, 'opt_1', '_all', 0)
                self.assertEqual(len(drill['rows']), 3)
                out = ex.export_xlsx({'measure': 'net', 'dimension': k})
                self.assertNotIn(label, self._xlsx_text(out['file_b64']))
                self.assertNotIn('x_pbfs', out['filename'])
                spec = ex.resolve_spec(spec={'dimension': k})
                self.assertEqual(spec['dimension'], 'none')
        # The admin's split by the secret field works.
        res = self._as(self.admin).query({'measure': 'headcount', 'dimension': k_secret,
                                          'grain': 'none'})
        self.assertEqual({s['label']: s['total'] for s in res['series']},
                         {'A': 1.0, 'Not filled in': 2.0})

    # ================================================================== 6
    def test_06_country_limited_field_reads_dash_elsewhere(self):
        ex = self._as(self.analyst)
        k = key('hr.employee', self.f_vn)
        res = ex.query({'measure': 'headcount', 'dimension': k, 'grain': 'none'})
        got = {s['key']: (s['label'], s['total']) for s in res['series']}
        self.assertEqual(got['opt_1'], ('East', 1.0))         # Lan only — not Arjun (India)
        self.assertEqual(got['opt_2'], ('West', 1.0))
        self.assertEqual(got['__na__'], ('—', 1.0))
        # Nobody with no Country of Work is shown a limited field's value.
        self.emp2.write({'payroll_country': False})
        res = ex.query({'measure': 'headcount', 'dimension': k, 'grain': 'none'})
        got = {s['key']: s['total'] for s in res['series']}
        self.assertEqual(got, {'opt_1': 1.0, '__na__': 2.0})
        # Arjun's value is kept, only hidden (R10).
        self.assertEqual(self.emp3[self.f_vn], 'opt_1')

    # ================================================================== 7
    def test_07_delete_while_a_saved_view_uses_it(self):
        View = self._as(self.admin, 'pb.explorer.view')
        S = self.env['pb.form.studio'].with_user(self.admin)
        tmp = S.create_field('employee_detail', {'type': 'select', 'label': 'DEMO Canteen shift',
                                                 'vis': 'all', 'list_ok': True,
                                                 'options': ['Early', 'Late']})['name']
        self.emp1.write({tmp: 'opt_1'})
        k = key('hr.employee', tmp)
        mine = View.pbx_save('DEMO people by canteen shift',
                             {'measure': 'headcount', 'dimension': k, 'grain': 'none'})
        other = self._as(self.analyst, 'pb.explorer.view').pbx_save(
            'DEMO filtered by canteen shift',
            {'measure': 'net', 'dimension': 'department_id', 'filters': {k: ['opt_1']}})
        refs = S.field_references('hr.employee', tmp)
        ref = next(r for r in refs if r['kind'] == 'report_view')
        self.assertEqual(ref['label'], 'Saved report views')
        self.assertEqual(ref['count'], 2)
        self.assertIn('DEMO people by canteen shift (DEMO FS8 Admin)', ref['names'])
        # Used by shows it before anyone tries; the delete is refused, in words.
        with self.assertRaisesRegex(UserError, 'Saved report views'):
            S.delete_field('hr.employee', tmp, 'DEMO Canteen shift')
        # An unrelated field with a longer name that STARTS the same is not caught.
        self.assertFalse([r for r in S.field_references('hr.employee', self.f_shirt)
                          if r['kind'] == 'report_view'])

        # The field goes another way (here: straight from the field list).
        self.env['ir.model.fields'].sudo().search(
            [('model', '=', 'hr.employee'), ('name', '=', tmp)]).unlink()
        opened = self._as(self.admin).open_view(mine['id'])
        self.assertTrue(opened['ok'])
        self.assertEqual(opened['spec']['dimension'], 'none')
        self.assertIn('not available to you any more', opened['note'])
        # Said ONCE: the owner's view no longer carries the field.
        again = self._as(self.admin).open_view(mine['id'])
        self.assertEqual(again['note'], '')
        # The other person's view opens without the filter, and the board
        # answers the whole question rather than a raw key.
        theirs = self._as(self.analyst).open_view(other['id'])
        self.assertEqual(theirs['spec']['filters'], {})
        self.assertTrue(theirs['note'])
        res = self._as(self.analyst).query(theirs['spec'])
        self.assertTrue(res['ok'])

    def test_07b_unmarked_field_drops_out_of_a_shared_view(self):
        View = self._as(self.admin, 'pb.explorer.view')
        k = key('hr.employee', self.f_site)
        saved = View.pbx_save('DEMO by home site', {'measure': 'headcount', 'dimension': k},
                              True)
        self.env['pb.form.studio'].with_user(self.admin).update_field(
            'hr.employee', self.f_site, {'list_ok': False})
        opened = self._as(self.analyst).open_view(saved['id'])
        self.assertEqual(opened['spec']['dimension'], 'none')
        self.assertIn('not available to you any more', opened['note'])
        # Not deleted, only unmarked: the owner's stored question is kept, so
        # marking it again brings the split back.
        stored = self.env['pb.explorer.view'].browse(saved['id']).spec
        self.assertEqual(stored['dimension'], k)

    # ================================================================== 8
    @staticmethod
    def _xlsx_text(b64):
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(base64.b64decode(b64))).active
        return '\n'.join(' | '.join(str(c) for c in row if c is not None)
                         for row in ws.iter_rows(values_only=True))

    def test_08_download_names_and_heads_are_screen_words(self):
        ex = self._as(self.analyst)
        out = ex.export_xlsx({'measure': 'net', 'dimension': 'department_id',
                              'filters': {'basis': ['approved']}})
        self.assertIn('_net_pay_by_department_', out['filename'])
        self.assertNotIn('department_id', out['filename'])
        text = self._xlsx_text(out['file_b64'])
        self.assertIn('Basis: Approved', text)
        self.assertNotIn('basis:', text)
        csv = ex.export_csv({'measure': 'headcount', 'dimension': 'job_id'})
        self.assertIn('_people_by_job_position_', csv['filename'])
        k = key('hr.employee', self.f_shirt)
        own = ex.export_xlsx({'measure': 'headcount', 'dimension': k, 'grain': 'none',
                              'filters': {k: ['opt_2', 'opt_3']}})
        self.assertIn('_by_demo_shirt_size_', own['filename'])
        self.assertNotIn('x_pbfs', own['filename'])
        self.assertNotIn(':', own['filename'])
        text = self._xlsx_text(own['file_b64'])
        self.assertIn('DEMO Shirt size: Medium, Large', text)
        self.assertIn('Split by | DEMO Shirt size', text)
        for raw in ('x_pbfs', 'opt_2', 'field:', '__none__'):
            self.assertNotIn(raw, text)
        self.assertNotIn('odoo', own['filename'].lower())

    # ================================================================== 9
    def test_09_new_field_is_there_on_the_next_question(self):
        """Same process, no reload: made, marked, offered, answered. (The
        two-worker proof is in the report, §4 test 9.)"""
        ex = self._as(self.analyst)
        before = {d['value'] for d in ex.get_schema()['dimensions']}
        name = self.env['pb.form.studio'].with_user(self.admin).create_field(
            'employee_detail', {'type': 'bool', 'label': 'DEMO First aider',
                                'vis': 'all', 'list_ok': True})['name']
        self.emp2.write({name: True})
        after = {d['value'] for d in ex.get_schema()['dimensions']}
        self.assertEqual(after - before, {key('hr.employee', name)})
        res = ex.query({'measure': 'headcount', 'dimension': key('hr.employee', name),
                        'grain': 'none'})
        self.assertEqual({s['label']: s['total'] for s in res['series']}, {'Yes': 1.0, 'No': 2.0})

    # ================================================================= 10
    def test_10_built_in_reports_unchanged_and_silent(self):
        """Three shipped reports answer exactly the same with the own-field
        hooks switched off; with no marked field the schema carries nothing new."""
        from odoo.addons.pb_form_studio_explorer.models.explorer import PbExplorerOwnFields
        specs = [{'measure': 'total_cost', 'dimension': 'department_id', 'grain': 'month'},
                 {'measure': 'headcount', 'dimension': 'department_id', 'grain': 'month'},
                 {'measure': 'cost_per_head', 'dimension': 'department_id', 'grain': 'month'}]

        def strip(payload):
            payload = dict(payload)
            payload.pop('ms', None)
            return json.dumps(payload, sort_keys=True, default=str)
        ex = self._as(self.admin)
        with_hooks = [strip(ex.query(s)) for s in specs]
        schema_with = ex.get_schema()
        with patch.object(PbExplorerOwnFields, '_pbfx_fields', lambda self: {}):
            without = [strip(ex.query(s)) for s in specs]
            schema_without = ex.get_schema()
        self.assertEqual(with_hooks, without)
        self.assertNotIn('extra_filters', schema_without)
        self.assertNotIn('extra_group', schema_without)
        self.assertEqual([d for d in schema_with['dimensions'] if not d.get('group')],
                         schema_without['dimensions'])

    # ================================================================= 11
    def test_11_po_gate_and_no_vendor_word(self):
        """vi / id: every msgid of this module translated, three markers, no
        empty msgstr, no vendor word anywhere a user reads."""
        from odoo.tools.translate import PoFileReader
        for lang in ('vi_VN', 'id_ID'):
            path = os.path.join(HERE, 'i18n', '%s.po' % lang)
            with open(path, 'rb') as fh:
                rows = [r for r in PoFileReader(fh) if r['type'] == 'code']
            self.assertGreaterEqual(len(rows), 16, lang)
            for row in rows:
                self.assertTrue(row['value'], (lang, row['src']))
                self.assertTrue('odoo-python' in row['comments']
                                or 'odoo-javascript' in row['comments'], row['src'])
                self.assertNotIn('odoo', row['value'].lower(), (lang, row['src']))
            with open(path, encoding='utf-8') as fh:
                self.assertNotIn('odoo server', fh.read().lower())
        # Every user-visible word this module says is in the catalogue.
        with open(os.path.join(HERE, 'i18n', 'pb_form_studio_explorer.pot'),
                  encoding='utf-8') as fh:
            pot = fh.read()
        for word in ('Your own fields', 'Not filled in', 'Saved report views',
                     'Employee · as it is today', 'Contract · as on each payslip'):
            self.assertIn('msgid "%s"' % word, pot)
        for rel in ('models/explorer.py', 'models/form_studio.py', '__manifest__.py',
                    'static/src/xml/form_builder_wording.xml'):
            with open(os.path.join(HERE, rel), encoding='utf-8') as fh:
                src = fh.read()
            for line in src.splitlines():
                if line.lstrip().startswith(('from odoo', 'import odoo', '#')):
                    continue
                self.assertNotIn('Odoo', line, rel)
        # The Vietnamese words load.
        ex = self._as(self.analyst).with_context(lang='vi_VN')
        if self.env['res.lang']._lang_get('vi_VN'):
            group = ex._pbx_extra_group()
            self.assertNotEqual(group['title'], 'Your own fields')
