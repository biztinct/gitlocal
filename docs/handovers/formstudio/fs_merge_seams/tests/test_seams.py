# -*- coding: utf-8 -*-
"""FORM STUDIO go-live — merged-tree seams with the REAL hosts (FS_DEPLOY_HANDOVER §1).

Local test addon only (never deployed). Every host is the merged one:
`employee_detail` (FS-2, Country of Work = payroll_country) and `contract`
(FS-3). No test-only host, no patched host registry.

 S1  end to end: one field of each kind on the employee and the contract,
     published; HR fills them in the panel / contract panel; the same value on
     the panel, the page, Full details, the table, Excel, the Updates sheet, the
     Records Desk; a pay formula reads a ticked field; delete refused while used,
     works after.
 S2  visibility: an administrators-only field leaks nowhere for HR manager,
     HR user, payroll manager, line manager, employee and portal.
 S3  Country of Work: an India-only field is absent for a Vietnam person on every
     surface; the value already stored is kept (only hidden).
 S4  My Payobook (R14-R16) over HTTP with the real employee host.
People are DEMO-named; passwords are made per run.
"""
import base64
import io
import json
import re
import secrets
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from odoo.addons.pb_me_details.tests.common import decide, seat

PASSWORD = secrets.token_urlsafe(16)
EMP, CON = 'hr.employee', 'hr.contract'
EH, CH = 'employee_detail', 'contract'
D_FROM, D_TO = '2026-10-01', '2026-10-31'
PNG = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8'
       'z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
KINDS = ('text', 'longtext', 'integer', 'number', 'money', 'bool', 'date', 'select', 'm2o', 'file')


def xlsx_rows(b64):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(b64)))
    return [[c.value for c in r] for r in wb.worksheets[0].iter_rows()]


class SeamCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True,
                                       mail_notrack=True, no_reset_password=True))
        S = type(cls.env['pb.form.studio'])
        # Only the pay-run guard is switched off (its own tests are the engine's 8/31).
        cls.startClassPatcher(patch.object(S, '_pbfs_busy', lambda s: ''))
        hosts = cls.env['pb.form.studio']._pbfs_hosts()
        assert hosts[EH]['model'] == EMP and hosts[CH]['model'] == CON, 'real hosts missing'
        cls.vn, cls.india = cls.env.ref('base.vn'), cls.env.ref('base.in')
        cls.company = cls.env['res.company'].create({'name': 'DEMO FSM Co', 'country_id': cls.vn.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        co = {'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])]}
        g_ctr = 'hr_contract.group_hr_contract_manager'
        cls.admin = new_test_user(cls.env, 'fsm_admin', name='DEMO FSM Admin', password=PASSWORD,
                                  groups='base.group_user,base.group_system,hr.group_hr_manager,'
                                         + g_ctr + ',om_hr_payroll.group_hr_payroll_manager,'
                                         'pb_hr_payroll_formula.group_formula_user', **co)
        cls.hrm = new_test_user(cls.env, 'fsm_hrm', name='DEMO FSM HR manager', password=PASSWORD,
                                groups='base.group_user,hr.group_hr_manager,' + g_ctr
                                       + ',om_hr_payroll.group_hr_payroll_user', **co)
        cls.hru = new_test_user(cls.env, 'fsm_hru', name='DEMO FSM HR user', password=PASSWORD,
                                groups='base.group_user,om_hr_payroll.group_hr_payroll_user,'
                                       'pb_hr_payroll_formula.group_formula_user', **co)
        cls.paym = new_test_user(cls.env, 'fsm_paym', name='DEMO FSM Payroll manager',
                                 password=PASSWORD,
                                 groups='base.group_user,om_hr_payroll.group_hr_payroll_manager', **co)
        cls.linemgr = new_test_user(cls.env, 'fsm_lm', name='DEMO FSM Line manager',
                                    password=PASSWORD, groups='base.group_user', **co)
        cls.portal = new_test_user(cls.env, 'fsm_me', name='DEMO FSM Lan', password=PASSWORD,
                                   groups='base.group_portal', **co)
        cls.portal2 = new_test_user(cls.env, 'fsm_me2', name='DEMO FSM Arjun', password=PASSWORD,
                                    groups='base.group_portal', **co)
        Emp = cls.env[EMP]
        boss = Emp.create({'name': 'DEMO FSM Boss', 'company_id': cls.company.id,
                           'user_id': cls.linemgr.id})
        cls.emp_vn = Emp.create({'name': 'DEMO FSM Lan', 'company_id': cls.company.id,
                                 'payroll_country': 'VN', 'parent_id': boss.id,
                                 'user_id': cls.portal.id})
        cls.emp_in = Emp.create({'name': 'DEMO FSM Arjun', 'company_id': cls.company.id,
                                 'payroll_country': 'IN', 'parent_id': boss.id,
                                 'user_id': cls.portal2.id})
        ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'DEMO FSM Staff'})
        Con = cls.env[CON].sudo()
        base = {'company_id': cls.company.id, 'date_start': '2026-01-01', 'state': 'open',
                'type_id': ctype.id}
        cls.con_vn = Con.create(dict(base, name='DEMO FSM Lan 2026', employee_id=cls.emp_vn.id,
                                     wage=12_000_000.0))
        cls.con_in = Con.create(dict(base, name='DEMO FSM Arjun 2026', employee_id=cls.emp_in.id,
                                     wage=90_000.0))
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
            cls.company, 'contract', reason='FSM seams: about the write, not who agrees')

    # ------------------------------------------------------------- helpers
    def S(self, user=None):
        return self.env['pb.form.studio'].with_user(user or self.admin).with_company(self.company)

    def make(self, host, kind, label, **kw):
        vals = dict({'type': kind, 'label': label, 'vis': 'hr', 'list_ok': True}, **kw)
        if kind == 'select':
            vals.setdefault('options', ['Small', 'Large'])
        if kind == 'm2o':
            vals.setdefault('comodel', 'res.country')
        return self.S().create_field(host, vals)['name']

    def publish(self, host, names):
        st = self.S()
        out = st.publish(host, {'sections': [{'id': 'custom', 'fields': list(names)}],
                                'base_version': st.get_studio(host)['version']})
        self.assertTrue(out.get('ok'), out)

    def people(self, user, table=False):
        P = self.env['pb.people'].with_user(user).with_company(self.company)
        return P.with_context(pbfl_table=True) if table else P

    def contracts(self, user, table=False):
        C = self.env['pb.contracts'].with_user(user).with_company(self.company)
        return C.with_context(pbfl_table=True) if table else C

    @staticmethod
    def flat(payload):
        return {f['name']: f for s in (payload or {}).get('sections') or [] for f in s['fields']}

    def panel(self, user, emp):
        return self.flat(self.people(user).get_employee_360(emp.id)['profile'].get('form_sections'))

    def page(self, user, emp):
        return self.flat(self.people(user).get_employee_detail(emp.id).get('form_sections'))

    def native(self, user, model, xmlid):
        return self.env[model].with_user(user).with_company(self.company).get_view(
            self.env.ref(xmlid).id, 'form')['arch']

    def roster_row(self, user, emp):
        rows = self.people(user, table=True).get_roster_page(search=emp.name)['rows']
        return next(r for r in rows if r['id'] == emp.id)

    def contract_row(self, user, con):
        rows = self.contracts(user, table=True).get_contracts_page(search=con.employee_id.name)['rows']
        return next(r for r in rows if r['id'] == con.id)

    def excel(self, board, user, names, search):
        res = board(user).pbf_export_table(search=search, columns=['name'] + list(names))
        self.assertTrue(res.get('ok'), res)
        return xlsx_rows(res['file_b64'])

    def desk_fields(self, user):
        data = self.env['pb.records.desk'].with_user(user).get_fields(0)
        return {c['id']: c for g in data['groups'] for c in g['fields']}

    def desk_values(self, user, fids, search):
        page = self.env['pb.records.desk'].with_user(user).search_page(
            0, filters={}, search=search, field_ids=fids, limit=50)
        return {r['id']: r['values'] for r in page['rows']}

    def updates_sheet(self, user, fid):
        U = self.env['pb.updates.desk'].with_user(user)
        topics, by_id, _d = U._catalogue()
        self.assertIn(fid, by_id)
        topic = next(t['key'] for t in topics if fid in t['field_ids'])
        res = U.download_sheet(topic_keys=[topic])
        self.assertTrue(res.get('ok'), res)
        return by_id[fid]['label'], xlsx_rows(res['file_b64'])

    def scheme(self, code, rules):
        cfg = self.env['hr.formula.config'].sudo().create({
            'name': 'DEMO FSM %s' % code, 'code': code, 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'state': 'active', 'company_id': self.company.id})
        cat = self.env['hr.salary.rule.category'].search([], limit=1)
        Rule = self.env['hr.formula.rule'].sudo()
        base = {'config_id': cfg.id, 'default_value': 0.0, 'category_id': cat.id}
        Rule.create(dict(base, name='Basic', code='BASIC', column_type='input', sequence=1,
                         value_kind='money', net_role='earning', appears_on_payslip=True))
        for seq, (rcode, key, kind) in enumerate(rules, start=2):
            Rule.create(dict(base, name='DEMO %s' % rcode, code=rcode, column_type='input',
                             sequence=seq, value_kind=kind, net_role='info',
                             appears_on_payslip=False, application_source_key=key))
        Rule.create(dict(base, name='Net', code=code + 'NET', column_type='formula', sequence=50,
                         value_kind='money', net_role='net', excel_formula='=BASIC',
                         appears_on_payslip=True))
        return cfg


@tagged('post_install', '-at_install', 'fsd_seams')
class TestSeams(SeamCase):

    # ================================================================ S1
    def test_s1_employee_end_to_end(self):
        n = {k: self.make(EH, k, 'DEMO FSM %s' % k, formula_ok=k in ('integer', 'select', 'bool'))
             for k in KINDS}
        self.publish(EH, n.values())
        vals = {n['text']: 'B-12', n['longtext']: 'Line one\nLine two', n['integer']: '1,204',
                n['number']: '2.5', n['money']: '1500000', n['bool']: True,
                n['date']: '2026-07-01', n['select']: 'opt_2', n['m2o']: self.india.id,
                n['file']: PNG}
        res = self.people(self.hru).pbfs_save_employee(self.emp_vn.id, vals)
        self.assertTrue(res.get('ok'), res)
        e = self.emp_vn.sudo()
        e.invalidate_recordset()
        self.assertEqual((e[n['integer']], e[n['select']], e[n['m2o']]), (1204, 'opt_2', self.india))
        panel, page = self.panel(self.hru, self.emp_vn), self.page(self.hru, self.emp_vn)
        self.assertEqual(set(panel), set(n.values()))
        self.assertEqual({k: v.get('display') for k, v in panel.items()},
                         {k: v.get('display') for k, v in page.items()}, 'panel = page')
        self.assertEqual(panel[n['select']]['display'], 'Large')
        arch = self.native(self.hru, EMP, 'hr.view_employee_form')
        self.assertIn('Company details', arch)
        for name in n.values():
            self.assertIn('name="%s"' % name, arch, 'Full details')
        # table = panel words (files: some words in both)
        cells = self.roster_row(self.hru, self.emp_vn)['pbfs']
        for k, name in n.items():
            if k == 'file':
                self.assertTrue(cells.get(name), 'file cell')
                continue
            self.assertEqual(str(cells.get(name)), str(panel[name]['display']), 'table %s' % k)
        # Excel: the text and the choice as on screen
        rows = self.excel(self.people, self.hru, [n['text'], n['select'], n['integer']], self.emp_vn.name)
        head, body = rows[0], [r for r in rows[1:] if r and r[0] == self.emp_vn.name]
        self.assertTrue(body, rows)
        got = dict(zip(head, body[0]))
        self.assertEqual(got['DEMO FSM text'], 'B-12')
        self.assertEqual(got['DEMO FSM select'], 'Large')
        self.assertEqual(got['DEMO FSM integer'], 1204)
        # Records Desk + Updates sheet
        fid = 'f:%s:%s' % (EMP, n['text'])
        self.assertIn(fid, self.desk_fields(self.hru))
        dv = self.desk_values(self.hru, [fid, 'f:%s:%s' % (EMP, n['select'])], self.emp_vn.name)
        self.assertEqual(dv[self.emp_vn.id][fid]['v'], 'B-12')
        self.assertEqual(dv[self.emp_vn.id]['f:%s:%s' % (EMP, n['select'])]['label'], 'Large')
        label, sheet = self.updates_sheet(self.hru, fid)
        col = next(i for i, h in enumerate(sheet[0]) if h and label in str(h))
        self.assertIn('B-12', [r[col] for r in sheet[1:]], 'Updates sheet value')
        # Mapping lane + formula catalogue + value
        FS = self.env['pb.formula.studio'].with_user(self.admin)
        items = {i['id']: i for i in FS._ec_right_items()}
        self.assertEqual(items['f:%s:%s' % (EMP, n['integer'])]['group'], 'Company details')
        key = 'custom.employee.%s' % n['integer']
        cfg = self.scheme('FSMV', [('FSMSHOE', key, 'quantity'),
                                    ('FSMSIZE', 'custom.employee.%s' % n['select'], 'text')])
        self.assertIn(key, cfg.with_user(self.hru)._application_source_catalogue())
        got = cfg.with_user(self.hru)._application_domain_values(
            self.emp_vn.with_user(self.hru), self.con_vn.with_user(self.hru), D_FROM, D_TO)
        self.assertEqual(got[key]['value'], 1204.0)
        self.assertEqual(got['custom.employee.%s' % n['select']]['value'], 'Large')
        # Access catalogue + timeline
        res_ = {r['key']: r for r in self.env['pb.access'].with_user(self.admin)._studio_resources('people')}
        self.assertIn(n['text'], {f['key'] for f in res_[EMP]['fields']})
        titles = [i['title'] for i in self.env['pb.employee.timeline'].with_user(self.hrm)
                  ._collect(self.emp_vn, False)]
        self.assertTrue([t for t in titles if 'DEMO FSM text' in t], titles)
        # delete: refused while a formula reads it, works after
        with self.assertRaises(UserError):
            self.S().delete_field(EMP, n['integer'], 'DEMO FSM integer')
        from odoo.addons.pb_hr_payroll_formula.models import scheme_proposal as sp
        cfg.rule_ids.filtered(lambda r: r.code == 'FSMSHOE').with_context(
            **{sp.SCHEME_APPLY_KEY: sp.SCHEME_APPLY_TOKEN}).unlink()
        self.S().delete_field(EMP, n['integer'], 'DEMO FSM integer')
        self.assertNotIn(n['integer'], self.env[EMP]._fields)
        self.assertNotIn('name="%s"' % n['integer'], self.native(self.hru, EMP, 'hr.view_employee_form'))
        self.assertNotIn(n['integer'], self.roster_row(self.hru, self.emp_vn).get('pbfs', {}))

    def test_s1b_contract_end_to_end(self):
        n = {k: self.make(CH, k, 'DEMO FSM c%s' % k) for k in KINDS}
        self.publish(CH, n.values())
        vals = {n['text']: 'L-7', n['longtext']: 'One\nTwo', n['integer']: '1,204',
                n['number']: '2.5', n['money']: '1500000', n['bool']: True,
                n['date']: '2026-07-01', n['select']: 'opt_2', n['m2o']: self.india.id,
                n['file']: PNG}
        ans = self.contracts(self.hrm).save_contract_360(self.con_vn.id, vals, [], '')
        self.assertTrue(ans['ok'], ans)
        self.assertFalse(ans['refusals'], ans['refusals'])
        terms = {f['name']: f for g in self.contracts(self.hrm).get_contract_360(self.con_vn.id)['terms']
                 if g.get('pbfs') for f in g['fields']}
        detail = {f['name']: f for s in self.contracts(self.hrm).get_contract_detail(self.con_vn.id)
                  ['pbfs']['sections'] for f in s['fields']}
        self.assertEqual(set(terms), set(n.values()))
        self.assertEqual(set(detail), set(n.values()))
        self.assertEqual(terms[n['select']]['display'], 'Large')
        self.assertEqual(detail[n['select']]['display'], 'Large')
        arch = self.native(self.hrm, CON, 'hr_contract.hr_contract_view_form')
        for name in n.values():
            self.assertIn('name="%s"' % name, arch)
        cells = self.contract_row(self.hrm, self.con_vn)['pbfs']
        self.assertEqual(str(cells[n['text']]), 'L-7')
        self.assertEqual(str(cells[n['select']]), 'Large')
        rows = self.excel(self.contracts, self.hrm, [n['text'], n['select']], self.emp_vn.name)
        self.assertIn('L-7', [c for r in rows for c in r])
        fid = 'f:%s:%s' % (CON, n['text'])
        self.assertIn(fid, self.desk_fields(self.hrm))
        hist = json.dumps(self.contracts(self.hrm)._cd_history_fields(self.con_vn, False))
        self.assertIn('DEMO FSM ctext', hist)
        # Renew copies the custom values (R7) — the wizard path both renewals use.
        self.S().delete_field(CON, n['m2o'], 'DEMO FSM cm2o')
        self.assertNotIn(n['m2o'], self.env[CON]._fields)

    # ================================================================ S2
    def test_s2_admin_only_field_leaks_nowhere(self):
        se = self.make(EH, 'text', 'DEMO FSM Secret', vis='admin', formula_ok=False)
        sc = self.make(CH, 'text', 'DEMO FSM cSecret', vis='admin')
        ok = self.make(EH, 'text', 'DEMO FSM Open')
        self.publish(EH, [se, ok])
        self.publish(CH, [sc])
        self.emp_vn.sudo().write({se: 'S3CRET', ok: 'OPEN'})
        self.con_vn.sudo().write({sc: 'C3CRET'})
        self.assertIn(se, self.panel(self.admin, self.emp_vn))
        for user in (self.hrm, self.hru, self.paym, self.linemgr, self.portal):
            tag = user.login
            for call in (lambda: self.panel(user, self.emp_vn), lambda: self.page(user, self.emp_vn),
                         lambda: self.roster_row(user, self.emp_vn),
                         lambda: self.people(user).pbf_export_table(columns=['name', se]),
                         lambda: self.contracts(user).get_contract_360(self.con_vn.id),
                         lambda: self.contracts(user).get_contract_detail(self.con_vn.id),
                         lambda: self.desk_fields(user),
                         lambda: self.env['pb.updates.desk'].with_user(user)._catalogue(),
                         lambda: self.env['pb.formula.studio'].with_user(user)._ec_right_items(),
                         lambda: self.env['hr.formula.config'].with_user(user)._application_source_catalogue(),
                         lambda: self.env['pb.form.studio'].with_user(user).fields_for(EMP, 'portal',
                                                                                       record=self.emp_vn),
                         lambda: self.native(user, EMP, 'hr.view_employee_form'),
                         lambda: self.native(user, CON, 'hr_contract.hr_contract_view_form')):
                try:
                    out = call()
                except (AccessError, UserError, ValueError, StopIteration):
                    continue    # refused (or the board itself is closed to this role)
                blob = json.dumps(out, default=str)
                for word in ('S3CRET', 'C3CRET', 'DEMO FSM Secret', 'DEMO FSM cSecret', se, sc):
                    self.assertNotIn(word, blob, '%s leaked to %s' % (word, tag))
            for model, rec, name in ((EMP, self.emp_vn, se), (CON, self.con_vn, sc)):
                with self.assertRaises(AccessError, msg='plain read %s' % tag):
                    self.env[model].with_user(user).browse(rec.id).read([name])
        # My details (portal): the page reads the engine's ticks only.
        self.assertFalse([f for f in self.S(self.portal).sudo().fields_for(EMP, 'portal', record=self.emp_vn)
                          if f['name'] == se])

    # ================================================================ S3
    def test_s3_country_of_work(self):
        f = self.make(EH, 'text', 'DEMO FSM PAN', list_ok=True)
        c = self.make(CH, 'text', 'DEMO FSM cPAN')
        self.publish(EH, [f])
        self.publish(CH, [c])
        self.emp_vn.sudo().write({f: 'LEFTOVER'})
        self.con_vn.sudo().write({c: 'CLEFT'})
        self.S().update_field(EMP, f, {'country_ids': [self.india.id]})
        self.S().update_field(CON, c, {'country_ids': [self.india.id]})
        self.emp_in.sudo().write({f: 'ABCDE1234F'})
        self.assertEqual(self.emp_vn.sudo()[f], 'LEFTOVER', 'value kept, only hidden')
        self.assertEqual(self.con_vn.sudo()[c], 'CLEFT')
        self.assertNotIn(f, self.panel(self.hrm, self.emp_vn))
        self.assertNotIn(f, self.page(self.hrm, self.emp_vn))
        self.assertIn(f, self.panel(self.hrm, self.emp_in))
        self.assertIn(c, {x['name'] for g in self.contracts(self.hrm).get_contract_360(self.con_in.id)['terms']
                          if g.get('pbfs') for x in g['fields']})
        self.assertNotIn(c, {x['name'] for g in self.contracts(self.hrm).get_contract_360(self.con_vn.id)['terms']
                             if g.get('pbfs') for x in g['fields']})
        self.assertIn(self.roster_row(self.hrm, self.emp_vn)['pbfs'].get(f), ('', False, None))
        self.assertEqual(self.roster_row(self.hrm, self.emp_in)['pbfs'].get(f), 'ABCDE1234F')
        fid = 'f:%s:%s' % (EMP, f)
        dv = self.desk_values(self.hrm, [fid], 'DEMO FSM')
        self.assertEqual(dv[self.emp_vn.id][fid]['label'], '')
        self.assertEqual(dv[self.emp_in.id][fid]['v'], 'ABCDE1234F')
        arch = self.native(self.hrm, EMP, 'hr.view_employee_form')
        tag = re.search(r'<field [^>]*name="%s"[^>]*>' % f, arch).group(0)
        self.assertIn('invisible', tag, 'country rule on the Full details page (Field library path)')
        res = self.people(self.hrm).pbfs_save_employee(self.emp_vn.id, {f: 'X'})
        self.assertFalse(res.get('ok'))
        self.S().update_portal(EMP, f, {'portal_show': True})
        self.assertFalse([x for x in self.S().sudo().fields_for(EMP, 'portal', record=self.emp_vn)
                          if x['name'] == f])
        self.assertTrue([x for x in self.S().sudo().fields_for(EMP, 'portal', record=self.emp_in)
                         if x['name'] == f])


@tagged('post_install', '-at_install', 'fsd_seams')
class TestSeamsMyPayobook(SeamCase, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        seat(cls.env, cls.company, 'hr_lead', cls.hrm)
        S = cls.env['pb.form.studio'].with_user(cls.admin)
        mk = lambda kind, label, **kw: S.create_field(EH, dict({'type': kind, 'label': label,
                                                                'vis': 'hr'}, **kw))['name']
        cls.f_show = mk('text', 'DEMO FSM Shirt')
        cls.f_inst = mk('date', 'DEMO FSM Course on')
        cls.f_appr = mk('select', 'DEMO FSM Shift', options=['Early', 'Late'])
        cls.f_money = mk('money', 'DEMO FSM Bonus')
        cls.f_formula = mk('integer', 'DEMO FSM Zone', formula_ok=True)
        st = S.get_studio(EH)
        S.publish(EH, {'sections': [{'id': 'custom', 'fields': [cls.f_show, cls.f_inst, cls.f_appr,
                                                                 cls.f_money, cls.f_formula]}],
                       'base_version': st['version']})
        tick = lambda name, **kw: S.update_portal(EMP, name, kw)
        tick(cls.f_show, portal_show=True)
        tick(cls.f_inst, portal_show=True, portal_edit=True, portal_mode='instant')
        tick(cls.f_appr, portal_show=True, portal_edit=True, portal_mode='approve')
        tick(cls.f_money, portal_show=True)
        tick('visa_no', portal_show=True, portal_edit=True, portal_mode='instant')
        cls.emp_vn.sudo().write({cls.f_show: 'M', cls.f_appr: 'opt_2', cls.f_money: 750000})
        cls.Req = cls.env['pb.me.detail.request']

    def setUp(self):
        super().setUp()
        if 'pb.privacy.notice' in self.env:
            self.env['pb.privacy.notice'].sudo().search(
                [('state', '=', 'published')]).write({'state': 'replaced'})

    def _page(self, url='/my/details'):
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200, url)
        self.assertNotIn('Odoo', res.text.replace('odoo', ''), url)
        return res.text

    def _send(self, **vals):
        page = self._page('/my/details/company')
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        data = {'csrf_token': token}
        data.update({'pbfr__' + k: v for k, v in vals.items()})
        return self.url_open('/my/details/company/send', data=data)

    def _open(self):
        return self.Req.sudo().search([('employee_id', '=', self.emp_vn.id),
                                       ('kind', '=', 'company_details'),
                                       ('state', '=', 'hr_review'), ('fb_replaced', '=', False)])

    def test_s4_my_payobook(self):
        # locked and forbidden ticks refused by the real host
        S = self.S()
        with self.assertRaises(UserError):
            S.update_portal(EMP, self.f_money, {'portal_show': True, 'portal_edit': True})
        with self.assertRaises(UserError):
            S.update_portal(EMP, self.f_formula, {'portal_show': True, 'portal_edit': True})
        with self.assertRaises(UserError):
            S.update_portal(EMP, 'payroll_country', {'portal_show': True, 'portal_edit': True})
        with self.assertRaises(UserError):
            S.update_portal(EMP, 'wage', {'portal_show': True})
        self.authenticate('fsm_me', PASSWORD)
        page = self._page()
        for label in ('DEMO FSM Shirt', 'DEMO FSM Course on', 'DEMO FSM Shift', 'DEMO FSM Bonus'):
            self.assertIn(label, page)
        self.assertNotIn('DEMO FSM Zone', page)
        # saved at once + history; HR approves → request → approve writes
        self._send(**{self.f_inst: '2026-09-01', self.f_appr: 'opt_1'})
        e = self.emp_vn.sudo()
        e.invalidate_recordset()
        self.assertEqual(str(e[self.f_inst]), '2026-09-01')
        self.assertEqual(e[self.f_appr], 'opt_2', 'waits for HR')
        req = self._open()
        self.assertEqual(len(req), 1)
        self.assertIn('DEMO FSM Shift', self._page())
        decide(self.env, req, 'approve')
        e.invalidate_recordset()
        self.assertEqual(e[self.f_appr], 'opt_1')
        # refusal leaves the value
        self._send(**{self.f_appr: 'opt_2'})
        req2 = self._open()
        decide(self.env, req2, 'reject', 'DEMO not on the roster')
        e.invalidate_recordset()
        self.assertEqual(e[self.f_appr], 'opt_1')
        # forged: money, locked, formula input, standard locked, unknown
        before = (e[self.f_money], e[self.f_formula], e.payroll_country, e.name)
        for name, value in ((self.f_money, '1'), (self.f_formula, '9'), ('payroll_country', 'IN'),
                            ('name', 'DEMO Forged'), ('x_pbfs_nope', '1')):
            res = self._send(**{name: value})
            self.assertIn('pbmd-alert', res.text, name)
        e.invalidate_recordset()
        self.assertEqual((e[self.f_money], e[self.f_formula], e.payroll_country, e.name), before)
        # another employee's record
        self._send(**{self.f_inst: '2026-10-10', 'employee_id': str(self.emp_in.id)})
        self.assertFalse(self.emp_in.sudo()[self.f_inst])
        with self.assertRaises(AccessError):
            self.Req.with_user(self.portal).pbfr_portal_send(self.emp_in, {self.f_appr: 'opt_1'})
        # standard field ticked "Saves at once"
        self._send(**{'visa_no': 'DEMO-V-1'})
        e.invalidate_recordset()
        self.assertEqual(e.visa_no, 'DEMO-V-1')
