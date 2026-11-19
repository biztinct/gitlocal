# -*- coding: utf-8 -*-
"""FS-2 numbered tests (docs/handovers/formstudio/FS2_REPORT.md §4).

Three places show an employee's custom fields: the side panel's "Company
details" tab (`get_employee_360` → `profile.form_sections`, reloaded by
`pbfs_employee_sections`), the full page (`get_employee_detail` →
`form_sections`) and Full details (the native form + the engine's page).
Test 7 (`-u` keeps everything) needs a second process and test 12 is the
browser walk: both are run by the scripts named in the report.
"""
import re
from pathlib import Path

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.translate import PoFileReader

from odoo.addons.pb_form_studio_people.models.form_studio import HOST, MODEL, NATIVE_VIEW

MODULE_DIR = Path(__file__).resolve().parent.parent


@tagged('post_install', '-at_install', 'pb_form_studio_people')
class TestPeopleHost(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.form.studio']
        cls.People = cls.env['pb.people']
        cls.vn = cls.env.ref('base.vn')
        cls.india = cls.env.ref('base.in')
        cls.admin = new_test_user(
            cls.env, 'pbfp_admin', name='DEMO Form Admin',
            groups='base.group_user,base.group_system,hr.group_hr_manager,'
                   'om_hr_payroll.group_hr_payroll_manager')
        # HR as tenants set it up: the payroll officer role brings employees
        # AND contracts (om_hr_payroll implies hr.group_hr_user and the
        # contract role); not a payroll manager, so amounts are masked.
        cls.hr = new_test_user(cls.env, 'pbfp_hr', name='DEMO HR Officer',
                               groups='base.group_user,om_hr_payroll.group_hr_payroll_user')
        cls.payroll = new_test_user(cls.env, 'pbfp_payroll', name='DEMO Payroll Manager',
                                    groups='base.group_user,om_hr_payroll.group_hr_payroll_manager')
        # The same HR role, but an access rule lets them read employees and
        # change none: the look-only reader.
        no_write = cls.env['res.groups'].create({'name': 'DEMO employees look-only'})
        cls.env['ir.rule'].create({
            'name': 'DEMO employees look-only', 'model_id': cls.env['ir.model']._get_id(MODEL),
            'groups': [(4, no_write.id)], 'domain_force': "[('id', '=', 0)]",
            'perm_read': False, 'perm_write': True, 'perm_create': True, 'perm_unlink': True})
        cls.reader = new_test_user(cls.env, 'pbfp_reader', name='DEMO Look-only HR',
                                   groups='base.group_user,om_hr_payroll.group_hr_payroll_user')
        cls.reader.write({'group_ids': [(4, no_write.id)]})
        cls.staff = new_test_user(cls.env, 'pbfp_staff', name='DEMO Staff',
                                  groups='base.group_user')
        cls.boss = new_test_user(cls.env, 'pbfp_boss', name='DEMO Line Manager',
                                 groups='base.group_user')
        cls.portal = new_test_user(cls.env, 'pbfp_portal', name='DEMO Portal',
                                   groups='base.group_portal')
        Emp = cls.env[MODEL]
        cls.boss_emp = Emp.create({'name': 'DEMO Line Manager', 'user_id': cls.boss.id})
        cls.emp_vn = Emp.create({'name': 'DEMO Lan Nguyen', 'payroll_country': 'VN',
                                 'parent_id': cls.boss_emp.id})
        cls.emp_in = Emp.create({'name': 'DEMO Arjun Rao', 'payroll_country': 'IN',
                                 'parent_id': cls.boss_emp.id})
        cls.emp_none = Emp.create({'name': 'DEMO No Country'})
        cls.staff_emp = Emp.create({'name': 'DEMO Staff', 'user_id': cls.staff.id,
                                    'parent_id': cls.boss_emp.id})

    # ---------------------------------------------------------------- utils
    def publish(self, sections, creates=None, user=None):
        st = self.Studio.with_user(user or self.admin)
        payload = {'sections': [{'id': sid, 'fields': list(names)} for sid, names in sections],
                   'creates': creates or [], 'base_version': st.get_studio(HOST)['version'],
                   'changes': []}
        res = st.publish(HOST, payload)
        self.assertTrue(res.get('ok'), res)
        return res

    def add(self, kind, label, section='custom', **kw):
        """One new field, made the way the wand's Publish makes it."""
        spec = dict({'tmp': '1', 'type': kind, 'label': label, 'vis': 'hr'}, **kw)
        placed = self.placed()
        placed.setdefault(section, []).append('new:1')
        res = self.publish(list(placed.items()), creates=[spec])
        return res['created']['1']

    def placed(self):
        lay = self.Studio._pbfs_layout(HOST)
        return {s['id']: list(s['fields']) for s in (lay.sections if lay else [])}

    def names_in(self, payload):
        return [f['name'] for s in (payload or {}).get('sections') or [] for f in s['fields']]

    def field_of(self, payload, name):
        for s in (payload or {}).get('sections') or []:
            for f in s['fields']:
                if f['name'] == name:
                    return f
        return None

    def panel(self, emp, user=None):
        return self.People.with_user(user or self.hr).get_employee_360(emp.id)['profile'].get(
            'form_sections')

    def full_page(self, emp, user=None):
        return self.People.with_user(user or self.hr).get_employee_detail(emp.id).get('form_sections')

    def native_arch(self, user=None, lang=None):
        parent = self.env.ref(NATIVE_VIEW)
        Emp = self.env[MODEL].with_user(user or self.hr)
        if lang:
            Emp = Emp.with_context(lang=lang)
        return Emp.get_view(parent.id, 'form')['arch']

    def studio_view(self):
        return self.env['pb.form.native.view'].sudo().search(
            [('model', '=', MODEL), ('parent_xmlid', '=', NATIVE_VIEW)]).view_id

    # ------------------------------------------------------------------- 1
    def test_01_wand_field_reaches_tab_full_page_full_details_in_three_languages(self):
        for lang in ('vi_VN', 'id_ID'):
            self.env['res.lang']._activate_lang(lang)
        name = self.add('select', 'DEMO Uniform size', options=['Small', 'Large'],
                        labels={'vi_VN': 'Cỡ đồng phục', 'id_ID': 'Ukuran seragam'})
        self.assertTrue(name.startswith('x_pbfs_'))
        self.assertIn(name, self.env[MODEL]._fields, 'made on the employee itself')
        self.assertNotIn(name, self.env['hr.version']._fields, 'never on the version')
        # the tab (side panel) and the full page
        self.assertIn(name, self.names_in(self.panel(self.emp_vn)))
        self.assertIn(name, self.names_in(self.full_page(self.emp_vn)))
        self.assertEqual(self.panel(self.emp_vn), self.full_page(self.emp_vn))
        # Full details: the engine's page, inside the notebook
        arch = self.native_arch()
        self.assertIn('name="pbfs_company_details"', arch)
        self.assertIn('name="%s"' % name, arch)
        for lang, label, page in (('en_US', 'DEMO Uniform size', 'Company details'),
                                  ('vi_VN', 'Cỡ đồng phục', 'Thông tin công ty'),
                                  ('id_ID', 'Ukuran seragam', 'Detail perusahaan')):
            People = self.People.with_user(self.hr).with_context(lang=lang)
            tab = People.get_employee_detail(self.emp_vn.id)['form_sections']
            self.assertEqual(self.field_of(tab, name)['label'], label, lang)
            self.assertIn(page, self.native_arch(lang=lang), lang)
            got = self.env[MODEL].with_user(self.hr).with_context(lang=lang).fields_get([name])
            self.assertEqual(got[name]['string'], label, lang)
        # The tab never carries the panel's own (locked) sections.
        kinds = {s['kind'] for s in self.panel(self.emp_vn)['sections']}
        self.assertEqual(kinds, {'open'})

    # ------------------------------------------------------------------- 2
    def test_02_hr_saves_once_same_value_everywhere_and_refusals_in_words(self):
        size = self.add('select', 'DEMO Uniform size', options=['Small', 'Large'])
        lockers = self.add('integer', 'DEMO Locker number', is_required=True)
        badge = self.add('text', 'DEMO Badge name', section='person_more')
        People = self.People.with_user(self.hr)
        res = People.pbfs_save_employee(self.emp_vn.id, {size: 'opt_2', lockers: '1,204',
                                                         badge: 'Lan N.'})
        self.assertTrue(res['ok'], res)
        for payload in (res['data'], self.panel(self.emp_vn), self.full_page(self.emp_vn)):
            self.assertEqual(self.field_of(payload, size)['display'], 'Large')
            self.assertEqual(self.field_of(payload, lockers)['value'], 1204)
            self.assertEqual(self.field_of(payload, badge)['display'], 'Lan N.')
        row = self.emp_vn.with_user(self.hr).read([size, lockers, badge])[0]   # Full details reads this
        self.assertEqual((row[size], row[lockers], row[badge]), ('opt_2', 1204, 'Lan N.'))
        # Required and the type, refused field by field in plain words; nothing written.
        bad = People.pbfs_save_employee(self.emp_vn.id, {lockers: '', badge: 'Other'})
        self.assertFalse(bad['ok'])
        self.assertEqual(bad['errors'][lockers], 'Fill this in: it is required.')
        bad = People.pbfs_save_employee(self.emp_vn.id, {lockers: '2.5', size: 'opt_9'})
        self.assertEqual(bad['errors'][lockers], 'Enter a whole number.')
        self.assertEqual(bad['errors'][size], 'Pick one of the choices.')
        self.assertEqual(self.emp_vn[badge], 'Lan N.', 'nothing written when anything fails')
        self.assertEqual(self.emp_vn[lockers], 1204)
        # A standard field cannot be written through the tab.
        bad = People.pbfs_save_employee(self.emp_vn.id, {'name': 'X'})
        self.assertFalse(bad['ok'])
        self.assertEqual(self.emp_vn.name, 'DEMO Lan Nguyen')

    # ------------------------------------------------------------------- 3
    def test_03_who_can_see_it_in_all_three_places_and_by_rpc(self):
        hr_f = self.add('text', 'DEMO HR note', vis='hr')
        admin_f = self.add('text', 'DEMO Admin note', vis='admin')
        everyone = self.add('text', 'DEMO Shirt colour', vis='all')
        self.emp_vn.sudo().write({hr_f: 'h', admin_f: 'a', everyone: 'blue'})
        # the administrator sees all three
        self.assertEqual(set(self.names_in(self.panel(self.emp_vn, self.admin))) & {hr_f, admin_f, everyone},
                         {hr_f, admin_f, everyone})
        # HR: no label, no value of the administrators' field, anywhere
        for payload in (self.panel(self.emp_vn), self.full_page(self.emp_vn),
                        self.People.with_user(self.hr).pbfs_employee_sections(self.emp_vn.id),
                        self.Studio.with_user(self.hr).render(HOST, self.emp_vn.id)):
            names = self.names_in(payload)
            self.assertIn(hr_f, names)
            self.assertNotIn(admin_f, names)
            self.assertNotIn('DEMO Admin note', str(payload))
        self.assertNotIn(admin_f, self.native_arch(self.hr))
        self.assertIn(admin_f, self.native_arch(self.admin))
        with self.assertRaises(AccessError):
            self.emp_vn.with_user(self.hr).read([admin_f])
        self.assertNotIn(admin_f, self.env[MODEL].with_user(self.hr).fields_get())
        res = self.People.with_user(self.hr).pbfs_save_employee(self.emp_vn.id, {admin_f: 'x'})
        self.assertFalse(res['ok'])
        self.assertEqual(self.emp_vn.sudo()[admin_f], 'a')
        # People list filters follow the same rule (fields_for, never a plain read)
        self.emp_in.sudo().write({hr_f: 'k', admin_f: 'b'})
        keys = [s['key'] for s in self.People.with_user(self.hr)._pbf_clean_spec()]
        self.assertNotIn(admin_f, keys)

    # ------------------------------------------------------------------- 4
    def test_04_look_only_reader_money_mask_and_nobody_else(self):
        note = self.add('text', 'DEMO Note', vis='all')
        pay = self.add('money', 'DEMO Shoe allowance', vis='hr')
        self.emp_vn.sudo().write({note: 'n', pay: 150000})
        # A reader who cannot change the employee: look-only, and Save refused.
        tab = self.People.with_user(self.reader).get_employee_detail(self.emp_vn.id)['form_sections']
        self.assertTrue(self.field_of(tab, note))
        self.assertFalse(tab['editable'])
        self.assertFalse(any(f['writable'] for s in tab['sections'] for f in s['fields']))
        res = self.People.with_user(self.reader).pbfs_save_employee(self.emp_vn.id, {note: 'm'})
        self.assertFalse(res['ok'])
        self.assertEqual(self.emp_vn[note], 'n')
        # Money: masked for HR who is not a payroll manager, like the wage.
        f = self.field_of(self.panel(self.emp_vn), pay)
        self.assertTrue(f['masked'])
        self.assertFalse(f['value'])
        self.assertFalse(f['writable'])
        self.assertNotIn('150', str(self.panel(self.emp_vn)))
        res = self.People.with_user(self.hr).pbfs_save_employee(self.emp_vn.id, {pay: '1'})
        self.assertFalse(res['ok'])
        self.assertEqual(self.emp_vn[pay], 150000)
        f = self.field_of(self.panel(self.emp_vn, self.payroll), pay)
        self.assertEqual(f['value'], 150000)
        self.assertTrue(f['writable'])
        # A line manager, an employee and a portal user reach nothing.
        for user in (self.boss, self.staff, self.portal):
            for call in (lambda u: self.People.with_user(u).get_employee_360(self.emp_vn.id),
                         lambda u: self.People.with_user(u).pbfs_employee_sections(self.emp_vn.id),
                         lambda u: self.People.with_user(u).pbfs_save_employee(self.emp_vn.id, {note: 'z'}),
                         lambda u: self.Studio.with_user(u).render(HOST, self.emp_vn.id)):
                with self.assertRaises(AccessError, msg=user.login):
                    call(user)
            try:
                page = self.People.with_user(user).get_employee_detail(self.emp_vn.id)
            except AccessError:
                page = {}
            self.assertNotIn('form_sections', page, user.login)
        self.assertEqual(self.emp_vn[note], 'n')

    # ------------------------------------------------------------------- 5
    def test_05_reorder_after_publish_reaches_open_screens(self):
        a = self.add('text', 'DEMO First')
        b = self.add('text', 'DEMO Second')
        mine = lambda payload: [n for n in self.names_in(payload) if n in (a, b)]
        self.assertEqual(mine(self.panel(self.emp_vn)), [a, b])
        v0 = self.panel(self.emp_vn)['version']
        Bus = self.env['bus.bus'].sudo()
        before = Bus.search_count([('message', 'like', 'pb_form_studio/published')])
        placed = self.placed()
        placed['custom'] = [n for n in placed['custom'] if n not in (a, b)] + [b, a]
        self.publish(list(placed.items()))
        after = self.panel(self.emp_vn)
        self.assertEqual(mine(after), [b, a])
        self.assertEqual(after['version'], v0 + 1)
        # every open copy is told (bus), so the panel re-reads without a server reload
        msgs = Bus.search([('message', 'like', 'pb_form_studio/published')])
        self.assertGreater(len(msgs), before)
        self.assertTrue(any(HOST in m.message and str(self.hr.partner_id.id) in m.channel for m in msgs))
        # the Full details page follows the same order
        arch = self.native_arch()
        self.assertLess(arch.index(b), arch.index(a))
        # moving a field to another open section
        placed = self.placed()
        placed['custom'].remove(a)
        placed.setdefault('job_more', []).append(a)
        self.publish(list(placed.items()))
        where = {f['name']: s['id'] for s in self.panel(self.emp_vn)['sections'] for f in s['fields']}
        self.assertEqual(where[a], 'job_more')

    # ------------------------------------------------------------------- 6
    def test_06_delete_gone_everywhere_full_details_still_opens(self):
        keep = self.add('text', 'DEMO Keep')
        gone = self.add('date', 'DEMO Visa end')
        self.emp_vn.sudo().write({gone: '2027-01-31'})
        self.assertIn(gone, self.native_arch())
        self.Studio.with_user(self.admin).delete_field(MODEL, gone, 'DEMO Visa end')
        self.assertNotIn(gone, self.env[MODEL]._fields)
        for payload in (self.panel(self.emp_vn), self.full_page(self.emp_vn)):
            self.assertNotIn(gone, self.names_in(payload))
            self.assertIn(keep, self.names_in(payload))
        arch = self.native_arch()
        self.assertNotIn(gone, arch)
        self.assertIn(keep, arch)
        self.Studio.with_user(self.admin).delete_field(MODEL, keep, 'DEMO Keep')
        arch = self.native_arch()                     # Full details still opens
        self.assertNotIn(keep, arch)
        self.assertNotIn(keep, self.names_in(self.panel(self.emp_vn)))
        if not self.Studio._pbfs_custom_names(MODEL):
            # on a database with no other custom field, the page goes too
            self.assertFalse(self.studio_view().exists(), 'the last field takes the page with it')
            self.assertNotIn('pbfs_company_details', arch)
            self.assertFalse(self.panel(self.emp_vn)['total'])

    # ------------------------------------------------------------------- 8
    def test_08_filter_by_custom_field_and_saved_view_blocks_delete(self):
        size = self.add('select', 'DEMO Uniform size', options=['Small', 'Large'])
        flag = self.add('bool', 'DEMO Union member')
        link = self.add('m2o', 'DEMO Home country', comodel='res.country')
        day = self.add('date', 'DEMO Visa end')
        self.add('text', 'DEMO Free text')           # not a filterable type
        self.emp_vn.sudo().write({size: 'opt_1', flag: True, link: self.vn.id})
        self.emp_in.sudo().write({size: 'opt_2', link: self.india.id,
                                  day: self.env['pb.people']._pbf_today()})
        People = self.People.with_user(self.hr)
        layout = People.pbf_layout()
        by_key = {s['key']: s for s in layout['sections']}
        self.assertEqual({by_key[n]['type'] for n in (size, flag, link, day)},
                         {'selection', 'choice', 'many2one', 'date'})
        self.assertTrue(all(by_key[n]['group'] == 'pbfs' for n in (size, flag, link, day)))
        self.assertIn('pbfs', [g['key'] for g in layout['groups']])
        self.assertTrue(by_key[size]['shown'])
        self.assertEqual(len([k for k in by_key if k.startswith('x_pbfs_demo_free')]), 0)

        def ids(filters):
            rows = People.get_roster_page(filters=filters, limit=200)['rows']
            return {r['id'] for r in rows} & {self.emp_vn.id, self.emp_in.id, self.emp_none.id}

        self.assertEqual(ids({size: ['opt_1']}), {self.emp_vn.id})
        self.assertEqual(ids({flag: ['yes']}), {self.emp_vn.id})
        self.assertEqual(ids({flag: ['no']}), {self.emp_in.id, self.emp_none.id})
        self.assertEqual(ids({link: [self.india.id]}), {self.emp_in.id})
        self.assertEqual(ids({day: {'preset': 'next_30'}}), {self.emp_in.id})
        # a saved view on the People list that uses the field blocks its delete
        view = self.env['pb.filter.view'].with_user(self.hr).create({
            'name': 'DEMO Large uniforms', 'screen': 'employees', 'user_id': self.hr.id,
            'filters': {size: ['opt_2']}})
        refs = self.Studio.with_user(self.admin).field_references(MODEL, size)
        self.assertTrue(any(r['kind'] == 'saved_view' and 'DEMO Large uniforms' in r['names']
                            for r in refs), refs)
        with self.assertRaises(UserError):
            self.Studio.with_user(self.admin).delete_field(MODEL, size, 'DEMO Uniform size')
        self.assertIn(size, self.env[MODEL]._fields)
        view.unlink()
        self.Studio.with_user(self.admin).delete_field(MODEL, size, 'DEMO Uniform size')
        self.assertNotIn(size, [s['key'] for s in People._pbf_clean_spec()])

    # --------------------------------------------------------- R10 country
    def test_08b_country_of_work_on_every_surface(self):
        pan = self.add('text', 'DEMO PAN number', country_ids=[self.india.id])
        allc = self.add('text', 'DEMO Shirt colour')
        self.assertEqual(self.emp_in.pbfs_country_of_work_id, self.india)
        self.assertFalse(self.emp_none.pbfs_country_of_work_id)
        for emp, shown in ((self.emp_in, True), (self.emp_vn, False), (self.emp_none, False)):
            for payload in (self.panel(emp), self.full_page(emp)):
                self.assertEqual(pan in self.names_in(payload), shown, emp.name)
                self.assertIn(allc, self.names_in(payload))
        # Full details: hidden by the Country of Work box itself
        arch = self.native_arch()
        self.assertIn('pbfs_country_of_work_id not in [%s]' % self.india.id, arch)
        # Save: refused where it does not apply, kept where it does
        res = self.People.with_user(self.hr).pbfs_save_employee(self.emp_vn.id, {pan: 'X1'})
        self.assertFalse(res['ok'])
        self.assertFalse(self.emp_vn[pan])
        res = self.People.with_user(self.hr).pbfs_save_employee(self.emp_in.id, {pan: 'ABCDE1234F'})
        self.assertTrue(res['ok'], res)
        # The box changes → the field follows at once
        self.emp_vn.write({'payroll_country': 'IN'})
        self.assertIn(pan, self.names_in(self.panel(self.emp_vn)))

    # ------------------------------------------------------------- 13 R14
    def test_13_my_payobook_host_flags_and_locked_list(self):
        host = self.Studio._pbfs_hosts()[HOST]
        self.assertIs(host['portal'], True)
        std = host['standard_fields']
        for name in ('name', 'birthday', 'private_phone', 'department_id', 'payroll_country'):
            self.assertIn(name, std)
        for name in ('image_1920', 'child_ids', 'employee_properties', 'version_id'):
            self.assertNotIn(name, std)
        self.assertTrue(all(n in self.env[MODEL]._fields for n in std))
        self.assertEqual(host['std_fields'], [], 'standard boxes stay where the panel draws them')
        plain = self.add('text', 'DEMO Shirt colour')
        formula = self.add('integer', 'DEMO Shift points', formula_ok=True)
        money = self.add('money', 'DEMO Shoe allowance')
        hidden = self.Studio._pbfs_portal_hidden(MODEL)
        locked = self.Studio._pbfs_portal_locked(MODEL)
        self.assertIn('wage', hidden)
        self.assertIn(money, hidden, 'a pay figure is never shown')
        for name in ('payroll_country', 'company_id', 'parent_id', 'department_id', 'job_id',
                     'user_id', 'contract_date_start', 'bank_name', formula):
            self.assertIn(name, locked, name)
        self.assertNotIn(plain, locked)
        self.assertNotIn(plain, hidden)
        self.assertNotIn('spouse_complete_name', locked, 'an ordinary box may be offered')
        if 'pb.me.detail.request' in self.env:
            self.assertIn('Already on My details', locked['marital'])
        if 'pb.profile.change.request' in self.env:
            self.assertIn('Already on My details', locked['private_phone'])
        # other record types are not touched by this host
        self.assertNotIn('wage', self.Studio._pbfs_portal_hidden('pb.form.sample'))

    def test_13b_engine_refuses_forbidden_ticks_for_the_employee(self):
        """The real engine (fs-1 R14) applies this host's lists on save."""
        St = self.Studio.with_user(self.admin)
        with self.assertRaises(UserError):
            St.update_portal(MODEL, 'wage', {'portal_show': True})           # never shown
        St.update_portal(MODEL, 'payroll_country', {'portal_show': True})    # shown is fine...
        with self.assertRaises(UserError):
            St.update_portal(MODEL, 'payroll_country', {'portal_edit': True})  # ...changed is not
        with self.assertRaises(UserError):
            St.update_portal(MODEL, 'department_id', {'portal_edit': True})
        # an ordinary box the employee may change: stored, typed in by hand
        hidden = self.Studio._pbfs_portal_hidden(MODEL)
        locked = self.Studio._pbfs_portal_locked(MODEL)
        Emp = self.env[MODEL]

        def plain(n):
            f = Emp._fields[n]
            return (n not in hidden and n not in locked and f.store and not f.readonly
                    and not (f.compute and not f.inverse) and f.type in ('char', 'text', 'date'))
        box = next(n for n in self.Studio._pbfs_hosts()[HOST]['standard_fields'] if plain(n))
        d = St.update_portal(MODEL, box,
                             {'portal_show': True, 'portal_edit': True, 'portal_mode': 'instant'})
        self.assertTrue(d['portal']['show'] and d['portal']['edit'])
        studio = St.get_studio(HOST)['fields']
        self.assertFalse(studio['payroll_country']['portal']['can_edit'])
        self.assertTrue(studio['payroll_country']['portal']['edit_reason'])
        self.assertFalse(studio['wage']['portal']['can_show'])
        rows = {r['name']: r for r in St.fields_for(MODEL, 'portal', record=self.emp_vn)}
        self.assertTrue(rows[box]['edit'])
        self.assertFalse(rows['payroll_country']['edit'])
        self.assertNotIn('wage', rows)
        # a forged change of a locked box from My Payobook is refused by the engine
        res = St.portal_check(MODEL, self.emp_vn, {'payroll_country': 'IN'})
        self.assertIn('payroll_country', res.get('errors') or {})
        self.assertEqual(self.emp_vn.payroll_country, 'VN')

    # ------------------------------------------------------------------ 10
    def test_10_silent_install(self):
        self.env.cr.execute("SELECT count(*) FROM pb_form_audit WHERE create_date < now()")
        if self.env.cr.fetchone()[0]:
            self.skipTest('the Form builder has been used on this database')
        since = self.admin.create_date
        for model in ('pb.form.field.meta', 'pb.form.layout', 'pb.form.native.view'):
            self.env.cr.execute('SELECT count(*) FROM %s WHERE create_date < %%s'
                                % self.env[model]._table, [since])
            self.assertEqual(self.env.cr.fetchone()[0], 0, model)
        self.env.cr.execute("SELECT count(*) FROM ir_model_fields WHERE model = 'hr.employee' "
                            "AND name LIKE 'x\\_pbfs\\_%%'")
        self.assertEqual(self.env.cr.fetchone()[0], 0)
        self.env.cr.execute("SELECT count(*) FROM ir_ui_view WHERE name LIKE 'Form builder page%%'")
        self.assertEqual(self.env.cr.fetchone()[0], 0)
        data = self.env['ir.model.data'].search([('module', '=', 'pb_form_studio_people')])
        self.assertFalse(data.filtered(lambda d: d.model in (
            'ir.cron', 'mail.template', 'ir.actions.server', 'ir.ui.view', 'ir.rule')))
        # The one field this module adds is not stored: no column on the employee.
        self.env.cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = "
                            "'hr_employee' AND column_name = 'pbfs_country_of_work_id'")
        self.assertFalse(self.env.cr.fetchone())

    # ------------------------------------------------------------------ 11
    def test_11_translations_and_no_platform_name(self):
        bad = re.compile(r'odoo', re.I)
        pot = MODULE_DIR / 'i18n' / 'pb_form_studio_people.pot'
        wanted = set()
        with open(pot, 'rb') as fh:
            for row in PoFileReader(fh):
                wanted.add(row['src'])
        self.assertTrue(wanted)
        for lang in ('vi_VN', 'id_ID'):
            got = {}
            with open(MODULE_DIR / 'i18n' / ('%s.po' % lang), 'rb') as fh:
                for row in PoFileReader(fh):          # parses: module, marker, occurrence
                    got[row['src']] = row['value']
            missing = [m for m in wanted if not got.get(m)]
            self.assertFalse(missing, '%s: %s' % (lang, missing[:5]))
            for src, value in got.items():
                self.assertFalse(bad.search(src) or bad.search(value or ''), (lang, src))
        for path in (MODULE_DIR / 'static/src/xml').glob('*.xml'):
            text = re.sub(r'<!--.*?-->', '', path.read_text(), flags=re.S)
            self.assertFalse(bad.search(text), path.name)
        for path in (MODULE_DIR / 'static/src/js').glob('*.js'):
            for lit in re.findall(r'_t\("([^"]*)"', path.read_text()):
                self.assertFalse(bad.search(lit), lit)
        for path in (MODULE_DIR / 'models').glob('*.py'):
            for lit in re.findall(r"_\('([^']*)'", path.read_text()):
                self.assertFalse(bad.search(lit), lit)
        manifest = (MODULE_DIR / '__manifest__.py').read_text()
        self.assertFalse(bad.search(re.search(r"'name': '([^']*)'", manifest).group(1)))
