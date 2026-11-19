# -*- coding: utf-8 -*-
"""FS-3 numbered tests (docs/handovers/formstudio/FS_HOSTS_HANDOVER.md, FS-3).

 1  each field type: add → edit in the side panel → value on the page and
    the full form
 2  approval: route published → waits, approver reads label + old → new,
    approve writes / refuse leaves; "No approval needed" → saves at once
 3  renewal by the wizard, by "Make it permanent" and by the import's copy
    all carry the values; golden of the wizard with no custom field
 4  visibility + access matrix (screen + RPC), forged saves, Country of Work
 5  the panel's other tabs and payload keys are unaffected
 6  one payslip recomputed identical (field added, edited, deleted)
 7  delete → gone everywhere, the full form still opens
 9  silent install
10  PO gate + no "Odoo" anywhere a user reads
(8 `-u` keeps everything and 11 the browser walk are run outside this suite —
 see FS3_REPORT.md.)

The engine's "a pay run is being worked out" guard is switched off in this
suite: it reads `pg_locks` for the WHOLE database cluster, so another
database's pay run (another builder's test suite on this Mac) makes every
field creation refuse (FS3_REPORT, merge-time task M2).
"""
import base64
import re
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

HOST = 'contract'
MODEL = 'hr.contract'
MODULE_DIR = Path(__file__).resolve().parent.parent
PNG = base64.b64decode(
    b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
PNG_URL = 'data:image/png;base64,' + base64.b64encode(PNG).decode()


@tagged('post_install', '-at_install', 'pb_form_studio_contracts')
class TestFs3Contracts(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True,
                                       mail_notrack=True, no_reset_password=True))
        cls.vn = cls.env.ref('base.vn')
        cls.india = cls.env.ref('base.in')
        cls.company = cls.env['res.company'].create({'name': 'DEMO FS3 Co'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        co = {'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])]}
        mgr = ('base.group_user,hr.group_hr_manager,hr_contract.group_hr_contract_manager,'
               'om_hr_payroll.group_hr_payroll_manager')
        cls.admin = new_test_user(cls.env, 'fs3_admin', groups=mgr + ',base.group_system',
                                  name='DEMO FS3 Admin', **co)
        cls.hr = new_test_user(cls.env, 'fs3_hr', groups=mgr, name='DEMO FS3 Contract manager', **co)
        cls.lead = new_test_user(cls.env, 'fs3_lead', groups=mgr, name='DEMO FS3 Lead', **co)
        cls.officer = new_test_user(cls.env, 'fs3_officer', groups='base.group_user,hr.group_hr_user',
                                    name='DEMO FS3 HR officer', **co)
        cls.payroll = new_test_user(
            cls.env, 'fs3_payroll',
            groups='base.group_user,pb_hr_payroll_base.group_payroll_base_officer',
            name='DEMO FS3 Payroll officer', **co)
        cls.linemgr = new_test_user(cls.env, 'fs3_linemgr', groups='base.group_user',
                                    name='DEMO FS3 Line manager', **co)
        cls.worker = new_test_user(cls.env, 'fs3_worker', groups='base.group_user',
                                   name='DEMO FS3 Worker', **co)
        cls.portal = new_test_user(cls.env, 'fs3_portal', groups='base.group_portal',
                                   name='DEMO FS3 Portal', **co)

        cls.Proposal = cls.env['pb.contract.proposal']
        cls.engine = cls.env['biz.approval.engine']
        cls.Proposal._approval_seed_default(cls.company)
        cls._seat('hr_lead', cls.lead)
        cls._seat('finance', cls.lead)

        cls.calendar = cls.env['resource.calendar'].create(
            {'name': 'DEMO FS3 Hours', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'DEMO FS3 Staff'})
        boss = cls.env['hr.employee'].create({'name': 'DEMO FS3 Boss', 'company_id': cls.company.id,
                                              'user_id': cls.linemgr.id})
        cls.emp_vn = cls.env['hr.employee'].create({
            'name': 'DEMO FS3 Lan', 'company_id': cls.company.id, 'payroll_country': 'VN',
            'parent_id': boss.id, 'user_id': cls.worker.id})
        cls.emp_in = cls.env['hr.employee'].create({
            'name': 'DEMO FS3 Arjun', 'company_id': cls.company.id, 'payroll_country': 'IN'})
        cls.c_vn = cls._contract(cls.emp_vn, 'DEMO FS3 Lan 2026')
        cls.c_in = cls._contract(cls.emp_in, 'DEMO FS3 Arjun 2026')

    @classmethod
    def _contract(cls, emp, name, **kw):
        vals = {'name': name, 'employee_id': emp.id, 'company_id': cls.company.id,
                'date_start': '2026-01-01', 'wage': 10_000_000.0, 'state': 'open',
                'type_id': cls.ctype.id, 'resource_calendar_id': cls.calendar.id}
        vals.update(kw)
        return cls.env['hr.contract'].create(vals)

    @classmethod
    def _seat(cls, role_key, user):
        role = cls.env['biz.approval.role'].sudo().search([('key', '=', role_key)], limit=1)
        if not role:
            return False
        cls.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', cls.company.id), ('role_id', '=', role.id),
            ('scope_key', '=', '')]).write({'active': False})
        return cls.env['biz.approval.responsibility'].sudo().create({
            'company_id': cls.company.id, 'role_id': role.id, 'scope_key': '',
            'scope_label': cls.company.name, 'user_id': user.id})

    def setUp(self):
        super().setUp()
        # Cluster-wide lock probe in the engine (see the module docstring).
        self.startPatcher(patch.object(type(self.env['pb.form.studio']), '_pbfs_busy',
                                       lambda self_: ''))

    # ---------------------------------------------------------------- utils
    def studio(self, user=None):
        return self.env['pb.form.studio'].with_user(user or self.admin).with_company(self.company)

    def facade(self, user=None):
        return self.env['pb.contracts'].with_user(user or self.hr).with_company(self.company)

    def make(self, kind, label, **kw):
        vals = dict({'type': kind, 'label': label, 'vis': 'hr'}, **kw)
        return self.studio().create_field(HOST, vals)['name']

    def publish(self, names):
        st = self.studio()
        out = st.publish(HOST, {'sections': [{'id': 'custom', 'fields': list(names)}],
                                'base_version': st.get_studio(HOST)['version']})
        self.assertTrue(out.get('ok'), out)
        return out

    def fast_lane(self):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(
            self.company, 'contract', reason='FS3 suite: about the write, not who agrees')

    def panel(self, contract, user=None):
        return self.facade(user).get_contract_360(contract.id)

    def custom_entries(self, payload):
        return {f['name']: f for g in payload.get('terms') or [] if g.get('pbfs')
                for f in g['fields']}

    def save(self, contract, terms, user=None):
        return self.facade(user).save_contract_360(contract.id, terms, [], '')

    def native_arch(self, user=None):
        view = self.env.ref('hr_contract.hr_contract_view_form')
        return self.env[MODEL].with_user(user or self.hr).with_company(self.company).get_view(
            view.id, 'form')['arch']

    def approve_all(self, request):
        for _guard in range(6):
            request.invalidate_recordset()
            if request.state != 'pending':
                return
            step = request.sudo().step_ids.filtered(lambda s: s.key == request.current_step_key)[:1]
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            self.engine.with_user(seat.acting_user_id or self.lead).decide(
                request, request.current_step_key, 'approve', 'Agreed')

    # =================================================================== 1
    def test_01_each_type_panel_page_and_full_form(self):
        self.env['res.lang']._activate_lang('vi_VN')
        names = {
            'text': self.make('text', 'DEMO Locker', labels={'vi_VN': 'Tủ đồ'}),
            'longtext': self.make('longtext', 'DEMO Notes'),
            'integer': self.make('integer', 'DEMO Union number'),
            'number': self.make('number', 'DEMO Hours share'),
            'money': self.make('money', 'DEMO Bond'),
            'bool': self.make('bool', 'DEMO Signed copy'),
            'date': self.make('date', 'DEMO Medical check'),
            'select': self.make('select', 'DEMO Uniform size', options=['Small', 'Large']),
            'm2o': self.make('m2o', 'DEMO Home country', comodel='res.country'),
            'file': self.make('file', 'DEMO Signed scan'),
        }
        self.publish(names.values())
        payload = self.panel(self.c_vn)
        entries = self.custom_entries(payload)
        self.assertEqual(set(entries), set(names.values()))
        group = [g for g in payload['terms'] if g.get('pbfs')][0]
        self.assertEqual(group['label'], 'Company details')
        want_kind = {'text': 'text', 'longtext': 'longtext', 'integer': 'integer',
                     'number': 'number', 'money': 'money', 'bool': 'bool', 'date': 'date',
                     'select': 'select', 'm2o': 'm2o', 'file': 'file'}
        for kind, name in names.items():
            self.assertEqual(entries[name]['kind'], want_kind[kind], kind)
            self.assertTrue(entries[name]['writable'], kind)
        # The picker offers what a custom link points at, with the reader's rights.
        found = self.facade().lookup_contract_m2o('res.country', 'Viet')
        self.assertIn(self.vn.id, [r['id'] for r in found])
        self.assertEqual(self.facade().lookup_contract_m2o('res.users', ''),
                         self.env['pb.contracts'].with_user(self.hr).with_company(self.company)
                         .lookup_contract_m2o('res.users', ''), 'the stock picker is unchanged')
        self.assertEqual(self.facade().lookup_contract_m2o('ir.config_parameter', ''), [],
                         'a comodel no field points at stays closed')

        self.fast_lane()
        vals = {names['text']: 'B-12', names['longtext']: 'Line one\nLine two',
                names['integer']: '1,204', names['number']: '2.5', names['money']: '1500000',
                names['bool']: True, names['date']: '2026-07-01', names['select']: 'opt_2',
                names['m2o']: self.india.id, names['file']: PNG_URL}
        answer = self.save(self.c_vn, vals)
        self.assertTrue(answer['ok'], answer)
        self.assertFalse(answer.get('pending'))
        self.assertFalse(answer['refusals'], answer['refusals'])
        c = self.c_vn
        c.invalidate_recordset()
        self.assertEqual(c[names['text']], 'B-12')
        self.assertEqual(c[names['longtext']], 'Line one\nLine two')
        self.assertEqual(c[names['integer']], 1204)
        self.assertEqual(c[names['number']], 2.5)
        self.assertEqual(c[names['money']], 1500000.0)
        self.assertTrue(c[names['bool']])
        self.assertEqual(c[names['date']], date(2026, 7, 1))
        self.assertEqual(c[names['select']], 'opt_2')
        self.assertEqual(c[names['m2o']], self.india)
        self.assertEqual(base64.b64decode(c[names['file']]), PNG)
        # The panel re-reads them in words.
        entries = self.custom_entries(answer['detail'])
        self.assertEqual(entries[names['select']]['display'], 'Large')
        self.assertEqual(entries[names['bool']]['display'], 'Yes')
        self.assertEqual(entries[names['integer']]['display'], '1,204')
        self.assertTrue(entries[names['file']]['url'])
        # A bad value is refused in words and nothing is written for it.
        bad = self.save(self.c_vn, {names['integer']: '2.5', names['date']: 'soon'})
        keys = {r['key'] for r in bad['refusals']}
        self.assertEqual(keys, {names['integer'], names['date']})
        self.assertEqual(c[names['integer']], 1204)
        # The contract page: same sections, look-only.
        detail = self.facade().get_contract_detail(self.c_vn.id)
        shown = {f['name']: f for s in detail['pbfs']['sections'] for f in s['fields']}
        self.assertEqual(set(shown), set(names.values()))
        self.assertEqual(shown[names['select']]['display'], 'Large')
        # The full form: a "Company details" page with every field.
        arch = self.native_arch()
        self.assertIn('Company details', arch)
        for name in names.values():
            self.assertIn('name="%s"' % name, arch)
        # In Vietnamese the label follows.
        vi = self.facade().with_context(lang='vi_VN').get_contract_360(self.c_vn.id)
        self.assertEqual(self.custom_entries(vi)[names['text']]['label'], 'Tủ đồ')

    def test_01b_required_refused_in_words(self):
        name = self.make('text', 'DEMO Badge', is_required=True)
        self.publish([name])
        self.fast_lane()
        answer = self.save(self.c_vn, {name: ''})
        self.assertEqual([r['key'] for r in answer['refusals']], [name])
        self.assertIn('required', answer['refusals'][0]['why'])

    # =================================================================== 2
    def test_02_route_published_waits_then_approve_writes(self):
        name = self.make('select', 'DEMO Uniform size', options=['Small', 'Large'])
        self.publish([name])
        answer = self.save(self.c_vn, {name: 'opt_2', 'location': 'DEMO Site B'})
        self.assertTrue(answer.get('pending'), answer)
        self.assertEqual(answer['saved'], 1, 'the location lands, the custom field waits')
        self.c_vn.invalidate_recordset()
        self.assertFalse(self.c_vn[name])
        self.assertEqual(self.c_vn.location, 'DEMO Site B')
        proposal = self.Proposal.sudo().search([('target_id', '=', self.c_vn.id)],
                                               order='id desc', limit=1)
        detail = proposal.with_user(self.lead)._approval_detail(proposal.approval_request_id)
        rows = {r['head']: r['cells'] for r in detail['rows']}
        self.assertIn('DEMO Uniform size', rows, rows)
        self.assertEqual(rows['DEMO Uniform size'], ['', 'Large'])
        self.assertNotIn(name, rows, 'the approver must never read the field code')
        self.approve_all(proposal.approval_request_id)
        self.c_vn.invalidate_recordset()
        proposal.invalidate_recordset()
        self.assertEqual(self.c_vn[name], 'opt_2',
                         (proposal.state, proposal.block_note, proposal.result()))
        proposal.invalidate_recordset()
        self.assertEqual(proposal.state, 'applied')

    def test_02b_refused_leaves_the_contract(self):
        name = self.make('text', 'DEMO Locker')
        self.publish([name])
        self.c_vn.sudo().write({name: 'A-1'})
        answer = self.save(self.c_vn, {name: 'B-2'})
        self.assertTrue(answer.get('pending'))
        proposal = self.Proposal.sudo().search([('target_id', '=', self.c_vn.id)],
                                               order='id desc', limit=1)
        rows = {r['head']: r['cells'] for r in proposal._approval_detail(
            proposal.approval_request_id)['rows']}
        self.assertEqual(rows['DEMO Locker'], ['A-1', 'B-2'])
        request = proposal.approval_request_id
        self.engine.with_user(self.lead).decide(request, request.current_step_key, 'reject',
                                                'Not now')
        self.c_vn.invalidate_recordset()
        self.assertEqual(self.c_vn[name], 'A-1')

    def test_02c_moved_underneath_is_not_written(self):
        name = self.make('m2o', 'DEMO Home country', comodel='res.country')
        self.publish([name])
        answer = self.save(self.c_vn, {name: self.india.id})
        self.assertTrue(answer.get('pending'))
        # Nobody moved it: the snapshot and the re-read agree (a link is an id
        # on both sides, never "res.country(…)" on one).
        proposal = self.Proposal.sudo().search([('target_id', '=', self.c_vn.id)],
                                               order='id desc', limit=1)
        self.assertEqual(proposal._proposal_moved(), [])
        self.c_vn.sudo().write({name: self.vn.id})
        self.assertTrue(proposal._proposal_moved(), 'a value moved underneath is named')

    def test_02d_no_approval_needed_saves_at_once(self):
        name = self.make('text', 'DEMO Locker')
        self.publish([name])
        self.fast_lane()
        answer = self.save(self.c_vn, {name: 'C-3'})
        self.assertFalse(answer.get('pending'))
        self.assertEqual(answer['saved'], 1)
        self.c_vn.invalidate_recordset()
        self.assertEqual(self.c_vn[name], 'C-3')

    def test_02e_a_press_without_custom_fields_is_untouched(self):
        name = self.make('text', 'DEMO Locker')
        self.publish([name])
        with patch.object(type(self.env['pb.contracts']), '_cd_propose',
                          autospec=True, side_effect=type(self.env['pb.contracts'])._cd_propose) as spy:
            answer = self.save(self.c_vn, {'wage': 12_000_000.0})
        self.assertTrue(answer.get('pending'))
        self.assertEqual(spy.call_count, 1)
        proposal = self.Proposal.sudo().search([('target_id', '=', self.c_vn.id)],
                                               order='id desc', limit=1)
        self.assertEqual(sorted(proposal.payload()['terms']), ['wage'])

    # =================================================================== 3
    def _with_values(self, contract):
        names = {
            'text': self.make('text', 'DEMO Locker'),
            'select': self.make('select', 'DEMO Uniform size', options=['Small', 'Large']),
            'm2o': self.make('m2o', 'DEMO Home country', comodel='res.country'),
            'bool': self.make('bool', 'DEMO Signed copy'),
            'money': self.make('money', 'DEMO Bond'),
            'file': self.make('file', 'DEMO Signed scan'),
            'admin': self.make('text', 'DEMO Board note', vis='admin'),
        }
        self.publish(names.values())
        contract.sudo().write({names['text']: 'B-12', names['select']: 'opt_2',
                               names['m2o']: self.india.id, names['bool']: True,
                               names['money']: 2_500_000.0, names['file']: base64.b64encode(PNG),
                               names['admin']: 'Only for the board'})
        return names

    def _values(self, contract, names):
        out = {}
        for key, name in names.items():
            value = contract.sudo()[name]
            out[key] = value.id if hasattr(value, 'ids') else value
        return out

    def test_03_renewal_wizard_permanent_and_import_copy_agree(self):
        from odoo.addons.pb_people_advanced.models.newhire_approval import NEWHIRE_PROCESS_KEY
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, NEWHIRE_PROCESS_KEY)
        old = self.c_vn
        names = self._with_values(old)
        want = self._values(old, names)
        Wizard = self.env['pb.people.contract.wizard'].with_user(self.hr).with_company(self.company)
        res = Wizard.create_contract({
            'employee_id': self.emp_vn.id, 'name': 'DEMO FS3 renewed', 'wage': old.wage,
            'date_start': '2027-01-01', 'renew_from': old.id})
        self.assertTrue(res.get('contract_id'), res)
        by_wizard = self.env[MODEL].browse(res['contract_id'])
        self.assertEqual(self._values(by_wizard, names), want,
                         'the Renew form carries every custom value, hidden ones too')
        by_import = old.sudo().copy({'date_start': '2027-02-01', 'state': 'draft'})
        self.assertEqual(self._values(by_import, names), want,
                         "the pay data import's replacement contract carries them")
        self.assertEqual(self._values(by_wizard, names), self._values(by_import, names))
        self.assertEqual(self._values(old, names), want, 'nothing written on the old contract')
        if 'pb.contract.review' in self.env:
            review = self.env['pb.contract.review'].with_company(self.company).create(
                {'contract_id': old.id, 'company_id': self.company.id})
            perm = review._build_new_contract(date(2027, 3, 1), False,
                                              contract_type=review._permanent_contract_type())
            self.assertTrue(perm)
            self.assertEqual(self._values(perm, names), want, '"Make it permanent" carries them')

    def test_03b_golden_wizard_without_custom_fields(self):
        from odoo.addons.pb_people_advanced.models.newhire_approval import NEWHIRE_PROCESS_KEY
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, NEWHIRE_PROCESS_KEY)
        emp = self.env['hr.employee'].create({'name': 'DEMO FS3 Mai', 'company_id': self.company.id,
                                              'payroll_country': 'VN'})
        old = self._contract(emp, 'DEMO FS3 fixed', date_end='2026-12-31',
                             trial_date_end='2026-02-28')
        Wizard = self.env['pb.people.contract.wizard'].with_user(self.hr).with_company(self.company)
        Contract = type(self.env['pb.people.contract.wizard'])
        base = {'employee_id': emp.id, 'wage': 11_000_000.0,
                'date_start': '2027-01-01', 'date_end': '2027-12-31', 'renew_from': old.id}
        res_a = Wizard.create_contract(dict(base, name='DEMO FS3 golden A'))
        with patch.object(Contract, '_fs3_carry_custom', lambda *a, **k: []):
            res_b = Wizard.create_contract(dict(base, name='DEMO FS3 golden B'))
        a, b = self.env[MODEL].browse(res_a['contract_id']), self.env[MODEL].browse(res_b['contract_id'])
        skip = {'id', 'name', 'display_name', 'create_date', 'write_date', 'create_uid',
                'write_uid', '__last_update'}
        stored = [n for n, f in self.env[MODEL]._fields.items()
                  if f.store and n not in skip and f.type not in ('one2many', 'many2many', 'binary')]
        ra, rb = a.sudo().read(stored)[0], b.sudo().read(stored)[0]
        for key in ('id',):
            ra.pop(key, None)
            rb.pop(key, None)
        self.assertEqual(ra, rb, 'with no custom field the renewal is exactly as before')
        self.assertFalse(a.trial_date_end, 'a renewal is never a trial (unchanged rule)')

    # =================================================================== 4
    def test_04_visibility_and_access_matrix(self):
        hr_f = self.make('text', 'DEMO Locker', vis='hr')
        admin_f = self.make('text', 'DEMO Board note', vis='admin')
        self.publish([hr_f, admin_f])
        self.c_vn.sudo().write({hr_f: 'B-12', admin_f: 'Secret'})

        # Contract manager: the HR field, editable; never the administrators' one.
        p = self.panel(self.c_vn)
        e = self.custom_entries(p)
        self.assertIn(hr_f, e, ([g['key'] for g in p.get('terms') or []],
                                self.env['pb.form.studio'].with_user(self.hr).with_company(
                                    self.company).render(HOST, self.c_vn.id)))
        self.assertTrue(e[hr_f]['writable'])
        self.assertNotIn(admin_f, e)
        self.assertNotIn('DEMO Board note', str(p))
        self.assertNotIn('Secret', str(p))
        detail = self.facade().get_contract_detail(self.c_vn.id)
        self.assertNotIn('Secret', str(detail))
        self.assertNotIn(admin_f, self.native_arch())
        with self.assertRaises(AccessError):
            self.c_vn.with_user(self.hr).read([admin_f])
        # A forged save of the hidden field: refused, never written.
        self.fast_lane()
        forged = self.save(self.c_vn, {admin_f: 'Changed'})
        self.assertEqual([r['key'] for r in forged['refusals']], [admin_f])
        self.assertEqual(self.c_vn.sudo()[admin_f], 'Secret')

        # The administrator sees both.
        e = self.custom_entries(self.panel(self.c_vn, self.admin))
        self.assertIn(admin_f, e)
        self.assertIn(admin_f, self.native_arch(self.admin))

        # HR without contract rights: look-only.
        e = self.custom_entries(self.panel(self.c_vn, self.officer))
        self.assertIn(hr_f, e)
        self.assertFalse(e[hr_f]['writable'])
        refused = self.save(self.c_vn, {hr_f: 'X'}, user=self.officer)
        self.assertFalse(refused['ok'])
        self.assertEqual(self.c_vn.sudo()[hr_f], 'B-12')

        # Payroll officer: the panel opens; the HR field only if they are HR staff.
        e = self.custom_entries(self.panel(self.c_vn, self.payroll))
        self.assertEqual(hr_f in e, self.payroll.has_group('hr.group_hr_user'))
        self.assertNotIn(admin_f, e)

        # Line manager, the employee, a portal user: no panel, no value by RPC.
        for user in (self.linemgr, self.worker, self.portal):
            with self.assertRaises((UserError, AccessError)):
                self.panel(self.c_vn, user)
            with self.assertRaises(AccessError):
                self.c_vn.with_user(user).read([hr_f])
            with self.assertRaises(AccessError):
                self.env['pb.form.studio'].with_user(user).render(HOST, self.c_vn.id)

        # Filters: the HR field is offered to HR, the administrators' one is not.
        spec = {s['key'] for s in self.facade()._pbf_clean_spec()}
        sel = self.make('select', 'DEMO Shift', options=['Day', 'Night'])
        self.publish([hr_f, admin_f, sel])
        spec = {s['key'] for s in self.facade()._pbf_clean_spec()}
        self.assertIn(sel, spec)
        self.assertNotIn(admin_f, spec)
        self.assertNotIn(hr_f, spec, 'text is not a filter kind')

    def test_04b_country_of_work(self):
        india_only = self.make('text', 'DEMO PF number', country_ids=[self.india.id])
        self.publish([india_only])
        self.assertEqual(self.c_in.pb_country_of_work_id, self.india)
        self.assertEqual(self.c_vn.pb_country_of_work_id, self.vn)
        self.assertIn(india_only, self.custom_entries(self.panel(self.c_in)))
        self.assertNotIn(india_only, self.custom_entries(self.panel(self.c_vn)))
        detail_vn = self.facade().get_contract_detail(self.c_vn.id)
        self.assertNotIn(india_only, str(detail_vn['pbfs']))
        self.fast_lane()
        refused = self.save(self.c_vn, {india_only: 'X'})
        self.assertEqual([r['key'] for r in refused['refusals']], [india_only])
        self.assertTrue(self.save(self.c_in, {india_only: 'PF-1'})['ok'])
        self.c_in.invalidate_recordset()
        self.assertEqual(self.c_in[india_only], 'PF-1')
        arch = self.native_arch()
        self.assertRegex(arch, r'pb_country_of_work_id not in \[%s\]' % self.india.id)
        # The person moves country: the field follows the person.
        self.emp_vn.payroll_country = 'IN'
        self.c_vn.invalidate_recordset()
        self.assertIn(india_only, self.custom_entries(self.panel(self.c_vn)))

    # =================================================================== 5
    def test_05_other_tabs_and_keys_unaffected(self):
        before = self.panel(self.c_vn)
        name = self.make('text', 'DEMO Locker')
        self.publish([name])
        after = self.panel(self.c_vn)
        self.assertEqual(set(before), set(after))
        for key in ('header', 'readiness', 'components', 'history'):
            self.assertEqual(before[key], after[key], key)
        stock = [g['key'] for g in before['terms']]
        self.assertEqual([g['key'] for g in after['terms']], stock + ['pbfs_custom'])
        self.assertFalse([g for g in before['terms'] if g.get('pbfs')],
                         'no field, no extra group')

    # =================================================================== 6
    def test_06_one_payslip_recomputed_identical(self):
        Cat = self.env['hr.salary.rule.category']
        basic = Cat.create({'name': 'DEMO FS3 Basic', 'code': 'FS3BASIC'})
        net = Cat.create({'name': 'DEMO FS3 Net', 'code': 'FS3NET'})
        Rule = self.env['hr.salary.rule']
        r1 = Rule.create({'name': 'DEMO FS3 Basic', 'code': 'FS3B', 'category_id': basic.id,
                          'sequence': 1, 'amount_select': 'code',
                          'amount_python_compute': 'result = contract.wage'})
        r2 = Rule.create({'name': 'DEMO FS3 Net', 'code': 'FS3N', 'category_id': net.id,
                          'sequence': 9, 'amount_select': 'code',
                          'amount_python_compute': 'result = categories.FS3BASIC * 0.9'})
        struct = self.env['hr.payroll.structure'].create({
            'name': 'DEMO FS3 Structure', 'code': 'FS3S', 'company_id': self.company.id,
            'rule_ids': [(6, 0, [r1.id, r2.id])]})
        self.c_vn.struct_id = struct
        slip = self.env['hr.payslip'].with_company(self.company).create({
            'name': 'DEMO FS3 slip', 'employee_id': self.emp_vn.id, 'contract_id': self.c_vn.id,
            'struct_id': struct.id, 'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'company_id': self.company.id})

        def lines():
            slip.compute_sheet()
            slip.invalidate_recordset()
            return sorted((l.code, round(l.total, 2)) for l in slip.line_ids)

        before = lines()
        self.assertIn(('FS3B', 10_000_000.0), before)
        name = self.make('money', 'DEMO Bond')
        self.publish([name])
        self.assertEqual(lines(), before, 'a field added')
        self.fast_lane()
        self.assertTrue(self.save(self.c_vn, {name: '999999'})['ok'])
        self.assertEqual(lines(), before, 'a field edited')
        self.studio().delete_field(MODEL, name, 'DEMO Bond')
        self.assertEqual(lines(), before, 'a field deleted')

    # =================================================================== 7
    def test_07_delete_gone_everywhere(self):
        name = self.make('select', 'DEMO Uniform size', options=['Small', 'Large'])
        other = self.make('text', 'DEMO Locker')
        self.publish([name, other])
        self.c_vn.sudo().write({name: 'opt_1'})
        self.assertIn(name, self.native_arch())
        self.studio().delete_field(MODEL, name, 'DEMO Uniform size')
        self.assertNotIn(name, self.env[MODEL]._fields)
        self.assertNotIn(name, self.custom_entries(self.panel(self.c_vn)))
        self.assertNotIn(name, str(self.facade().get_contract_detail(self.c_vn.id)))
        self.assertNotIn(name, {s['key'] for s in self.facade()._pbf_clean_spec()})
        arch = self.native_arch()
        self.assertNotIn(name, arch)
        self.assertIn(other, arch, 'the page stays for the remaining field')
        # The last one goes → the page goes, the full form still opens.
        self.studio().delete_field(MODEL, other, 'DEMO Locker')
        arch = self.native_arch()
        self.assertNotIn('Company details', arch)
        self.assertIn('<form', arch)
        self.assertFalse([g for g in self.panel(self.c_vn)['terms'] if g.get('pbfs')])

    # =================================================================== 9
    def test_09_silent_install(self):
        made = self.env['ir.model.fields'].sudo().search_count(
            [('model', '=', MODEL), ('name', '=like', 'x_pbfs_%')])
        if made:
            self.skipTest('this database already has contract fields (walk database)')
        self.assertFalse(self.env['pb.form.layout'].sudo().search_count([('host_key', '=', HOST)]))
        self.assertFalse(self.env['pb.form.native.view'].sudo().search_count([('model', '=', MODEL)]))
        self.assertFalse(self.env['ir.ui.view'].sudo().search_count(
            [('model', '=', MODEL), ('name', '=like', 'Form builder page%')]))
        data = self.env['ir.model.data'].sudo().search([('module', '=', 'pb_form_studio_contracts')])
        kinds = set(data.mapped('model'))
        for bad in ('ir.cron', 'mail.template', 'ir.actions.server', 'ir.mail_server',
                    'ir.ui.view', 'pb.form.layout'):
            self.assertNotIn(bad, kinds)
        field = self.env[MODEL]._fields['pb_country_of_work_id']
        self.assertFalse(field.store, 'the Country of Work helper never adds a column')

    # ================================================================== 10
    def test_10_po_gate_and_no_platform_name(self):
        pot = (MODULE_DIR / 'i18n' / 'pb_form_studio_contracts.pot').read_text(encoding='utf-8')
        ids = set(re.findall(r'^msgid "(.+)"$', pot, re.M))
        self.assertTrue(ids)
        for lang in ('vi_VN', 'id_ID'):
            text = (MODULE_DIR / 'i18n' / ('%s.po' % lang)).read_text(encoding='utf-8')
            blocks = re.findall(r'^msgid "(.*)"\nmsgstr "(.*)"$', text, re.M)
            done = {mid for mid, mstr in blocks if mid and mstr}
            self.assertFalse(ids - done, '%s: missing %s' % (lang, sorted(ids - done)[:5]))
            self.assertNotRegex(text.split('msgid', 2)[-1], r'(?i)\bodoo\b')
            for _mid, mstr in blocks:
                self.assertNotRegex(mstr, r'(?i)odoo')
        for path in list((MODULE_DIR / 'static').rglob('*.xml')) + list((MODULE_DIR / 'static').rglob('*.js')):
            body = path.read_text(encoding='utf-8')
            visible = re.sub(r'<!--.*?-->', '', body, flags=re.S)
            visible = re.sub(r'/\*.*?\*/', '', visible, flags=re.S)
            visible = re.sub(r'//[^\n]*', '', visible)
            visible = re.sub(r'@odoo/owl|@odoo-module', '', visible)
            self.assertNotRegex(visible, r'(?i)odoo', path.name)
        for path in (MODULE_DIR / 'models').glob('*.py'):
            for literal in re.findall(r'_\(\s*["\'](.+?)["\']', path.read_text(encoding='utf-8')):
                self.assertNotRegex(literal, r'(?i)odoo', path.name)
