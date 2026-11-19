# -*- coding: utf-8 -*-
"""FS-6: the employee and contract pages in the current look, NOTHING lost.

Server side, the only thing this module may change on either form is the class
of the <form> root: what each role receives from get_views (every field,
label, button, page, group, invisible / readonly / required rule, and the field
definitions) must be byte-identical with and without it. The browser side
(what is drawn per tab, per role, per Country of Work) is proved by the
before/after dump in FS6_REPORT.md.
"""
from lxml import etree

from odoo.tests import TransactionCase, tagged

FORMS = [
    ('hr.employee', 'hr.view_employee_form', 'pb_form_native_look.view_employee_form_native_look', 'pb-nl-emp'),
    ('hr.contract', 'hr_contract.hr_contract_view_form', 'pb_form_native_look.view_contract_form_native_look', 'pb-nl-con'),
]

ROLES = {
    'administrator': ['base.group_system', 'hr.group_hr_manager', 'om_hr_payroll.group_hr_payroll_manager',
                      'hr_contract.group_hr_contract_manager'],
    'hr_manager': ['hr.group_hr_manager', 'hr_contract.group_hr_contract_manager'],
    'payroll_manager': ['hr.group_hr_user', 'om_hr_payroll.group_hr_payroll_manager'],
    'hr_user': ['hr.group_hr_user'],
}
# Groups that only exist where the payroll pack is installed: added when present.
OPTIONAL = {
    'administrator': ['pb_hr_payroll_base.group_payroll_base_manager', 'pb_hr_payroll_formula.group_formula_manager'],
    'hr_manager': ['pb_hr_payroll_base.group_payroll_base_user', 'pb_hr_payroll_formula.group_formula_user'],
    'payroll_manager': ['pb_hr_payroll_base.group_payroll_base_manager', 'pb_hr_payroll_formula.group_formula_manager'],
    'hr_user': ['pb_hr_payroll_base.group_payroll_base_user', 'pb_hr_payroll_formula.group_formula_user'],
}


@tagged('post_install', '-at_install', 'pb_form_native_look')
class TestNativeLook(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.users = {}
        for role, xmlids in ROLES.items():
            groups = [cls.env.ref('base.group_user')]
            groups += [cls.env.ref(x) for x in xmlids]
            groups += [g for g in (cls.env.ref(x, raise_if_not_found=False) for x in OPTIONAL[role]) if g]
            cls.users[role] = cls.env['res.users'].with_context(no_reset_password=True).create({
                'name': 'DEMO FS6 %s' % role, 'login': 'demo.fs6.%s' % role,
                'group_ids': [(6, 0, [g.id for g in groups])],
            })

    def _form(self, model, user):
        self.env.registry.clear_cache('templates')
        self.env.invalidate_all()
        res = self.env[model].with_user(user).get_views([(False, 'form')])
        return res['views']['form'], res['models']

    @staticmethod
    def _root_class(arch):
        return (etree.fromstring(arch).get('class') or '').split()

    @staticmethod
    def _without_root_class(arch):
        root = etree.fromstring(arch)
        root.attrib.pop('class', None)
        return etree.tostring(root, encoding='unicode')

    def test_01_opt_out_lifted_on_both_forms(self):
        for model, _parent, _view, marker in FORMS:
            form, _m = self._form(model, self.users['administrator'])
            classes = self._root_class(form['arch'])
            self.assertNotIn('vu-form-native', classes, model)
            self.assertIn('pb-nl', classes, model)
            self.assertIn(marker, classes, model)

    def test_02_every_role_gets_the_same_form_except_the_root_class(self):
        """With the module's views switched off the forms are what pb_theme
        makes them (stock look); switched on, the arch each role receives
        differs ONLY by the root class - same fields, pages, buttons, groups,
        rules, field definitions."""
        for model, _parent, view_xmlid, _marker in FORMS:
            view = self.env.ref(view_xmlid)
            after = {role: self._form(model, u) for role, u in self.users.items()}
            view.active = False
            before = {role: self._form(model, u) for role, u in self.users.items()}
            view.active = True
            for role in self.users:
                b_form, b_models = before[role]
                a_form, a_models = after[role]
                self.assertIn('vu-form-native', self._root_class(b_form['arch']), (model, role))
                self.assertEqual(self._without_root_class(b_form['arch']),
                                 self._without_root_class(a_form['arch']), (model, role))
                self.assertEqual(b_models, a_models, (model, role))

    def test_03_only_the_class_attribute_is_touched(self):
        """The module's two views carry one `attributes` spec on /form and
        nothing else - no field, page or group can come from here."""
        for _model, _parent, view_xmlid, _marker in FORMS:
            arch = etree.fromstring(self.env.ref(view_xmlid).arch_db)
            specs = arch.xpath('//xpath')
            self.assertEqual(len(specs), 1)
            self.assertEqual(specs[0].get('expr'), '/form')
            self.assertEqual(specs[0].get('position'), 'attributes')
            self.assertEqual([a.get('name') for a in specs[0]], ['class'])
            self.assertFalse(arch.xpath('//field|//page|//group|//button'))

    def test_05_employee_screen_fixes(self):
        """Addendum: the version record's always-empty Contract / Wage rows are
        hidden (their fields stay in the form), one line says where the
        contract's dates and wage are, two labels are corrected - and no field
        definition or stored label changes."""
        form, models = self._form('hr.employee', self.users['administrator'])
        root = etree.fromstring(form['arch'])
        page = root.xpath("//page[@name='payroll_information']")
        self.assertTrue(page)
        page = page[0]
        for xp in ("//label[@for='contract_date_start']", "//div[@name='contract_dates']",
                   "//label[@for='wage']", "//div[@name='wage']"):
            nodes = page.xpath('.' + xp)
            self.assertTrue(nodes, xp)
            self.assertIn(nodes[0].get('invisible'), ('1', 'True'), xp)
        # the fields are still part of the form (values load and save as before)
        for name in ('contract_date_start', 'contract_date_end', 'wage'):
            self.assertTrue(page.xpath(".//field[@name='%s']" % name), name)
        note = page.xpath(".//div[hasclass('o_pb_nl_contract_note')]")
        self.assertTrue(note)
        self.assertIn('Current Contract', note[0].text)
        self.assertEqual(root.xpath("//field[@name='tham_gia_bhxh']")[0].get('string'),
                         'Social insurance (BHXH)')
        emp_id = root.xpath("//field[@name='parent_id']/following-sibling::field[@name='employee_id']")
        self.assertEqual(emp_id[0].get('string'), 'Employee ID')
        # stored field labels untouched (other screens keep theirs)
        fields = self.env['ir.model.fields']._get('hr.employee', 'tham_gia_bhxh')
        self.assertEqual(fields.with_context(lang='en_US').field_description, 'Tham gia BHXH')
        self.assertEqual(self.env['hr.employee']._fields['employee_id'].string, 'Employee Id')

    def test_06_screen_fixes_change_no_value(self):
        """Saving the employee through the form with the fixes keeps the
        version record's contract dates and wage exactly as they were."""
        from odoo.tests import Form
        emp = self.env['hr.employee'].create({'name': 'DEMO FS6 values'})
        before = emp.read(['contract_date_start', 'contract_date_end', 'wage', 'tham_gia_bhxh', 'employee_id'])[0]
        with Form(emp.with_user(self.users['administrator'])) as f:
            f.job_title = 'DEMO FS6 saved'
        emp.invalidate_recordset()
        after = emp.read(['contract_date_start', 'contract_date_end', 'wage', 'tham_gia_bhxh', 'employee_id'])[0]
        self.assertEqual(before, after)
        self.assertEqual(emp.job_title, 'DEMO FS6 saved')

    def test_04_other_native_forms_keep_their_arch(self):
        """Five other native forms are not touched by this module."""
        mine = {self.env.ref(v).id for _m, _p, v, _k in FORMS}
        for model in ('res.partner', 'res.users', 'hr.department', 'hr.job', 'res.company'):
            if model not in self.env:
                continue
            form, _m = self._form(model, self.users['administrator'])
            self.assertNotIn('pb-nl', self._root_class(form['arch']), model)
            views = self.env['ir.ui.view'].search([('model', '=', model), ('id', 'in', list(mine))])
            self.assertFalse(views, model)
