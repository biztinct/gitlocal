# -*- coding: utf-8 -*-
"""FS-15 numbered tests (docs/handovers/formstudio/FS15_REPORT.md), R31.

The product's country rule and its "taken off the screens" list become
defaults an administrator changes in the Form builder ("Shown for": All
countries / Only these Countries of Work / Hidden for everyone, Reset to
built-in). Widening is always allowed (screen only); narrowing or hiding keeps
the lock rule. Tests 1 (markup before/after on copies ×5), 6 (upgrade of the
host modules with settings in place) and 7 (payslips) are run by the scripts
the report names; the two-worker half of test 2 too.
"""
import unittest

from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.safe_eval import safe_eval

from odoo.addons.pb_form_studio_people.models.form_studio import HOST, MODEL, NATIVE_VIEW


@tagged('post_install', '-at_install', 'pb_form_studio_people', 'fs15')
class TestFs15ShownFor(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.form.studio']
        cls.vn, cls.india, cls.idn = cls.env.ref('base.vn'), cls.env.ref('base.in'), cls.env.ref('base.id')
        cls.admin = new_test_user(
            cls.env, 'fs15_admin', name='DEMO FS15 Admin',
            groups='base.group_user,base.group_system,hr.group_hr_manager,'
                   'om_hr_payroll.group_hr_payroll_manager')
        cls.hr = new_test_user(cls.env, 'fs15_hr', name='DEMO FS15 HR Manager',
                               groups='base.group_user,hr.group_hr_manager,'
                                      'om_hr_payroll.group_hr_payroll_manager')
        Emp = cls.env[MODEL]
        cls.emp_vn = Emp.create({'name': 'DEMO Lan Nguyen', 'payroll_country': 'VN'})
        cls.emp_id = Emp.create({'name': 'DEMO Siti Rahma', 'payroll_country': 'ID'})
        cls.emp_in = Emp.create({'name': 'DEMO Arjun Rao', 'payroll_country': 'IN'})
        cls.emp_none = Emp.create({'name': 'DEMO Nobody Country'})

    def setUp(self):
        super().setUp()
        if not hasattr(self.env[MODEL], '_pb_tidy_rules'):
            raise unittest.SkipTest('the built-in country rules are not installed here')

    # ---------------------------------------------------------------- utils
    def st(self, user=None):
        return self.Studio.with_user(user or self.admin)

    def arch(self):
        self.env.registry.clear_cache('templates')
        Emp = self.env[MODEL].with_user(self.hr)
        return etree.fromstring(Emp.get_view(self.env.ref(NATIVE_VIEW).id, 'form')['arch'])

    def node(self, arch, name):
        found = [n for n in arch.iter('field') if n.get('name') == name
                 and not any(a.tag == 'field' for a in n.iterancestors())]
        return found[0] if found else None

    def shown_for(self, arch, name, emp):
        """Is the box drawn for `emp` (its own rule and every section above it)?"""
        node = self.node(arch, name)
        if node is None:
            return False
        ctx = {'pbfs_country_of_work_id': emp.pbfs_country_of_work_id.id or False,
               'payroll_country': emp.payroll_country or False, 'id': emp.id,
               'vn_uses_payroll_profile': False}
        for el in [node] + list(node.iterancestors()):
            expr = (el.get('invisible') or '').strip()
            if not expr:
                continue
            if expr in ('1', 'True', 'true'):
                return False
            local = dict(ctx)
            for _try in range(30):
                try:
                    if safe_eval(expr, dict(local)):
                        return False
                    break
                except (NameError, ValueError) as err:
                    bits = str(err).split("'")
                    if len(bits) < 2:
                        raise
                    local[bits[1]] = False
        return True

    def desc(self, name):
        return self.st().get_studio(HOST)['fields'][name]['stdbox']

    # ------------------------------------------------------------------- 1
    def test_01_silent_nothing_changes_until_an_administrator_acts(self):
        """No setting row: the form is TIDY-E's own table, applied as before."""
        self.assertEqual(self.Studio._pbfs_std_tidy_overrides(MODEL), {})
        from odoo.addons.pb_employee_form_tidy.models.form_rules import FORM_RULES
        self.assertEqual(self.env[MODEL]._pb_tidy_rules(), FORM_RULES)
        arch = self.arch()
        self.assertTrue(self.shown_for(arch, 'pb_npwp_number', self.emp_id))
        self.assertFalse(self.shown_for(arch, 'pb_npwp_number', self.emp_vn))
        self.assertFalse(self.shown_for(arch, 'level_of_health_compensation', self.emp_vn))
        d = self.desc('pb_npwp_number')
        self.assertFalse(d['changed'])
        self.assertEqual(d['base']['mode'], 'only')
        self.assertEqual([c['code'] for c in d['base']['countries']], ['ID'])

    # ------------------------------------------------------------------- 2
    def test_02_widen_a_one_country_field_then_reset(self):
        # pb_safety_group: built-in "Only Vietnam", not locked
        name = 'pb_safety_group'
        if name not in self.env[MODEL]._fields:
            self.skipTest('pb_training not installed')
        arch = self.arch()
        self.assertTrue(self.shown_for(arch, name, self.emp_vn))
        self.assertFalse(self.shown_for(arch, name, self.emp_id))
        self.st().update_standard(MODEL, name, {'std_show': 'only',
                                                'std_show_country_ids': [self.vn.id, self.idn.id]})
        arch = self.arch()
        self.assertTrue(self.shown_for(arch, name, self.emp_vn))
        self.assertTrue(self.shown_for(arch, name, self.emp_id), 'widened to Indonesia')
        self.assertFalse(self.shown_for(arch, name, self.emp_in))
        self.assertFalse(self.shown_for(arch, name, self.emp_none))
        d = self.desc(name)
        self.assertTrue(d['changed'])
        self.assertEqual(sorted(c['code'] for c in d['show']['countries']), ['ID', 'VN'])
        # All countries: shown for everyone, people with no Country of Work too
        self.st().update_standard(MODEL, name, {'std_show': 'all'})
        arch = self.arch()
        for emp in (self.emp_vn, self.emp_id, self.emp_in, self.emp_none):
            self.assertTrue(self.shown_for(arch, name, emp), emp.name)
        # Reset to built-in
        self.st().update_standard(MODEL, name, {'std_show': 'builtin'})
        meta = self.Studio._pbfs_meta(MODEL, [name]).get(name)
        self.assertFalse(meta.std_show)
        arch = self.arch()
        self.assertTrue(self.shown_for(arch, name, self.emp_vn))
        self.assertFalse(self.shown_for(arch, name, self.emp_id))
        self.assertFalse(self.desc(name)['changed'])
        # every change leaves a history line
        lines = self.env['pb.form.audit'].sudo().search([('field_name', '=', name)])
        self.assertGreaterEqual(len(lines), 3)

    def test_02b_widen_through_publish(self):
        """The Studio's own path: draft → Publish."""
        name = 'pb_safety_group'
        if name not in self.env[MODEL]._fields:
            self.skipTest('pb_training not installed')
        st = self.st()
        data = st.get_studio(HOST)
        sections = [{'id': s['id'], 'fields': list(s['fields'])}
                    for s in data['sections'] if s['kind'] == 'open']
        updates = {name: {'std_show': 'only', 'std_show_country_ids': [self.vn.id, self.idn.id],
                          'std_show_unset': False}}
        res = st.publish(HOST, {'sections': sections, 'updates': updates, 'creates': [],
                                'deletes': [], 'base_version': data['version'],
                                'changes': ['DEMO change']})
        self.assertTrue(res.get('ok'), res)
        self.assertTrue(self.shown_for(self.arch(), name, self.emp_id))

    # ------------------------------------------------------------------- 3
    def test_03_locked_field_widens_never_narrows(self):
        name = 'pb_npwp_number'          # built-in Indonesia, locked (tax files)
        self.assertTrue(self.desc(name)['lock'])
        # widen: allowed
        self.st().update_standard(MODEL, name, {'std_show': 'only',
                                                'std_show_country_ids': [self.idn.id, self.vn.id]})
        arch = self.arch()
        self.assertTrue(self.shown_for(arch, name, self.emp_vn))
        self.assertTrue(self.shown_for(arch, name, self.emp_id))
        # narrow below the built-in set, or hide: refused by a direct call
        for vals in ({'std_show': 'none'},
                     {'std_show': 'only', 'std_show_country_ids': [self.vn.id]},
                     {'std_hidden': True},
                     {'std_country_ids': [self.idn.id]}):
            with self.assertRaises(UserError):
                self.st().update_standard(MODEL, name, vals)
        # ... and through Publish
        st = self.st()
        data = st.get_studio(HOST)
        with self.assertRaises(UserError):
            st.publish(HOST, {'sections': [], 'updates': {name: {'std_show': 'none'}},
                              'creates': [], 'deletes': [], 'base_version': data['version'],
                              'changes': ['x']})
        # All countries: allowed (wider still); back to built-in: allowed
        self.st().update_standard(MODEL, name, {'std_show': 'all'})
        self.assertTrue(self.shown_for(self.arch(), name, self.emp_in))
        self.st().update_standard(MODEL, name, {'std_show': 'builtin'})
        self.assertFalse(self.shown_for(self.arch(), name, self.emp_in))
        # a field locked for everyone ("All countries" built in) cannot be narrowed at all
        with self.assertRaises(UserError):
            self.st().update_standard(MODEL, 'birthday', {'std_show': 'only',
                                                          'std_show_country_ids': [self.vn.id]})

    def test_03b_narrower_rule_saved_before_the_lock_is_widened_back(self):
        """A rule saved before the field became locked never shows it less
        than the product does (screens), and the stored rule says so after
        the readers' save point."""
        name = 'pb_npwp_number'
        meta = self.Studio._pbfs_ensure_meta(MODEL, name)
        meta.write({'std_show': 'only', 'std_show_country_ids': [(6, 0, [self.vn.id])]})
        rules = self.Studio._pbfs_std_rules(MODEL)
        self.assertEqual(sorted(rules[name]['only']), sorted([self.vn.id, self.idn.id]))
        self.assertTrue(self.desc(name)['ignored'])
        self.assertTrue(self.shown_for(self.arch(), name, self.emp_id))
        names = self.Studio._pbfs_std_unhide_locked(MODEL)
        self.assertIn(name, names)
        self.assertEqual(sorted(meta.std_show_country_ids.ids), sorted([self.vn.id, self.idn.id]))

    # ------------------------------------------------------------------- 4
    def test_04_show_again_a_removed_field(self):
        name = 'level_of_health_compensation'
        if name not in self.env[MODEL]._fields:
            self.skipTest('legacy Vietnam payroll boxes not installed')
        d = self.desc(name)
        self.assertTrue(d['removed'] and d['off'])
        self.assertFalse(d['comeback'])
        self.assertEqual([c['code'] for c in d['propose']['countries']], ['VN'])
        self.assertTrue(d['tab'])
        full = {it['name'] for _sec, items in self.Studio._pbfs_full_sections(HOST) for it in items}
        self.assertNotIn(name, full, 'not listed on the canvas while it is off the screens')
        self.assertFalse(self.shown_for(self.arch(), name, self.emp_vn))
        self.st().update_standard(MODEL, name, {'std_show': 'only',
                                                'std_show_country_ids': [self.vn.id]})
        arch = self.arch()
        self.assertTrue(self.shown_for(arch, name, self.emp_vn), 'drawn in its old place')
        self.assertFalse(self.shown_for(arch, name, self.emp_id))
        full = {it['name'] for _sec, items in self.Studio._pbfs_full_sections(HOST) for it in items}
        self.assertIn(name, full)
        # undo: the Field library's "back to how the product shows it"
        self.st().update_standard(MODEL, name, {'std_show': 'builtin', 'std_labels': {}})
        self.assertFalse(self.shown_for(self.arch(), name, self.emp_vn))
        self.assertTrue(self.desc(name)['off'])

    def test_04b_fields_that_must_stay_off_refuse(self):
        comeback = self.Studio._pbfs_std_comeback(MODEL)
        for name in ('account_number', 'bank_name', 'contract_type_id', 'structure_type_id'):
            if name not in self.env[MODEL]._fields:
                continue
            self.assertIn(name, comeback)
            self.assertTrue(self.desc(name)['comeback'])
            self.assertIsNone(self.desc(name)['propose'])
            for vals in ({'std_show': 'all'},
                         {'std_show': 'only', 'std_show_country_ids': [self.vn.id]}):
                with self.assertRaises(UserError):
                    self.st().update_standard(MODEL, name, vals)
            self.assertFalse(self.shown_for(self.arch(), name, self.emp_vn))
        # computed summaries too
        for name in ('vn_employer_insurance_cost', 'vn_personal_tax_rate'):
            if name in self.env[MODEL]._fields:
                self.assertIn(name, comeback)

    # ------------------------------------------------------------------- 5
    def test_05_countries_in_use_match_the_people_filter(self):
        rows, none = self.st()._pbfs_countries_in_use()
        domain = self.env['pb.people'].with_user(self.admin)._pbf_base_domain()
        Emp = self.env[MODEL].sudo()
        by_code = {r['code']: r['n'] for r in rows}
        for code in ('VN', 'ID', 'IN'):
            self.assertEqual(by_code.get(code), Emp.search_count(domain + [('payroll_country', '=', code)]))
        self.assertEqual(none, Emp.search_count(domain + [('payroll_country', '=', False)]))
        ns = [r['n'] for r in rows]
        self.assertEqual(ns, sorted(ns, reverse=True), 'most people first')
        data = self.st().get_studio(HOST)
        self.assertEqual(data['countries_in_use'], rows)
        self.assertEqual(data['countries_none'], none)
        lib = self.st().library()
        self.assertEqual(lib['countries_in_use'], rows)

    # ------------------------------------------------------------------- 8
    def test_08_only_the_administrator(self):
        with self.assertRaises(AccessError):
            self.st(self.hr).update_standard(MODEL, 'pb_safety_group', {'std_show': 'all'})
        with self.assertRaises(AccessError):
            self.st(self.hr).get_studio(HOST)

    # ------------------------------------------------------------- FS-7 rows
    def test_09_an_older_hidden_in_rule_reads_the_same(self):
        """FS-7 "hidden in India" on a general field: shown for everyone else,
        people with no Country of Work included — exactly as before."""
        name = 'pb_blood_type'
        meta = self.Studio._pbfs_ensure_meta(MODEL, name)
        meta.write({'std_country_ids': [(6, 0, [self.india.id])]})
        arch = self.arch()
        self.assertFalse(self.shown_for(arch, name, self.emp_in))
        for emp in (self.emp_vn, self.emp_id, self.emp_none):
            self.assertTrue(self.shown_for(arch, name, emp), emp.name)
        d = self.desc(name)
        self.assertTrue(d['changed'] and d['show']['unset'])
        self.assertEqual([c['code'] for c in d['countries']], ['IN'])     # FS-7 words
        # the next save writes the new setting, nothing changes on screen
        self.st().update_standard(MODEL, name, {'std_labels': {'en_US': 'DEMO Blood group'}})
        meta.invalidate_recordset()
        self.assertFalse(meta.std_country_ids)
        self.assertEqual(meta.std_show, 'only')
        arch = self.arch()
        self.assertFalse(self.shown_for(arch, name, self.emp_in))
        self.assertTrue(self.shown_for(arch, name, self.emp_none))

    def test_10_side_panel_follows_a_narrowed_general_field(self):
        name = 'pb_blood_type'
        People = self.env['pb.people'].with_user(self.hr)

        def rows(emp):
            tabs = People.get_employee_360(emp.id).get('details') or {}
            return {r['key'] for tab in tabs.values() for g in tab for r in g['rows']}
        if name not in rows(self.emp_vn):
            self.skipTest('the side panel does not draw it here')
        self.st().update_standard(MODEL, name, {'std_show': 'only',
                                                'std_show_country_ids': [self.vn.id]})
        self.assertIn(name, rows(self.emp_vn))
        self.assertNotIn(name, rows(self.emp_id))
