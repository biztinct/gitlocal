# -*- coding: utf-8 -*-
"""TIDY-E tests 1-4, 9, 11 — the employee "Full details" form.

1  each Country of Work (VN, ID, IN, SG, none) sees general boxes + own-country
   boxes, checked against the committed verdict table;
2  removed boxes are gone for everyone, their columns and values intact;
3  a save of the form with hidden boxes holding values changes none of them;
4  date boxes show the year;
9  nobody sees a box they could not see before;
11 installing wrote nothing on any employee.
"""

from odoo.tests import Form, TransactionCase, tagged

from . import common
from ..models import form_rules

REMOVE = 'REMOVE FROM SCREEN'
HIDE = 'HIDE BY COUNTRY'
KEEP = 'KEEP'


@tagged('post_install', '-at_install', 'tidy_e')
class TestTidyForm(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.table = common.verdict_table()
        cls.manager, cls.officer = common.make_hr_users(cls.env, 'form')
        Emp = cls.env['hr.employee'].sudo()
        cls.people = {}
        for code in common.COUNTRIES + ('',):
            cls.people[code or 'none'] = Emp.create({
                'name': 'DEMO Tidy %s' % (code or 'none'),
                'payroll_country': code or False,
                'company_id': cls.env.company.id,
            })

    # ----------------------------------------------------------- helpers
    def _views(self, user):
        env = self.env(user=user)
        return common.form_arch(env, tidy=True), common.form_arch(env, tidy=False)

    def _seen(self, user, person, arch):
        record = person.with_user(user)
        return common.visible_boxes(arch, record, set(self.table))

    # ------------------------------------------------------------ test 1
    def test_01_each_country_sees_general_plus_its_own(self):
        tidy, plain = self._views(self.manager)
        present = common.present_boxes(tidy, set(self.table))
        self.assertGreater(len(present), 100, "the form lost most of its boxes")
        for key, person in self.people.items():
            code = '' if key == 'none' else key
            with_rules = self._seen(self.manager, person, tidy)
            without = self._seen(self.manager, person, plain)
            for name in present:
                verdict, country = self.table[name]
                if verdict == REMOVE:
                    self.assertNotIn(name, with_rules, "%s still shows for %s" % (name, key))
                elif country != 'general':
                    if country != code:
                        self.assertNotIn(name, with_rules,
                                         "%s (%s) shows for a %s employee" % (name, country, key))
                    else:
                        self.assertEqual(name in with_rules, name in without,
                                         "%s changed for its own country %s" % (name, key))
                else:
                    self.assertEqual(name in with_rules, name in without,
                                     "general box %s changed for %s" % (name, key))

    def test_01b_no_indonesian_or_vietnamese_box_for_an_indian_employee(self):
        tidy, _plain = self._views(self.manager)
        seen = self._seen(self.manager, self.people['IN'], tidy)
        foreign = {n for n in seen if self.table[n][1] in ('ID', 'VN')}
        self.assertFalse(foreign, "an Indian employee sees %s" % sorted(foreign))
        own = {n for n in seen if self.table[n][1] == 'IN'}
        self.assertTrue(own, "an Indian employee sees no Indian box at all")

    def test_01c_no_country_sees_no_country_box_and_the_hint(self):
        tidy, _plain = self._views(self.manager)
        seen = self._seen(self.manager, self.people['none'], tidy)
        self.assertFalse({n for n in seen if self.table[n][1] != 'general'})
        hint = tidy.xpath("//div[hasclass('o_pb_cow_hint')]")
        self.assertTrue(hint, "the 'Set Country of Work' line is missing")
        self.assertEqual(hint[0].get('invisible'), 'payroll_country')

    def test_01d_country_tabs_close_for_other_countries(self):
        tidy, _plain = self._views(self.manager)
        pages = {p.get('name'): p for p in tidy.iter('page') if p.get('name')}
        for name in ('vietnam_insurance', 'vietnam_tax', 'pb_vn_payroll_facts'):
            if name in pages:
                self.assertEqual(pages[name].get('invisible'), "payroll_country != 'VN'")
        # the tabs that hold general boxes stay
        for name in ('payroll_info', 'pb_tax_details'):
            if name in pages:
                self.assertFalse(pages[name].get('invisible'))

    def test_01e_country_of_work_sits_at_the_top_with_its_screen_name(self):
        tidy, _plain = self._views(self.manager)
        top = tidy.xpath("//div[hasclass('oe_title')]//field[@name='payroll_country']")
        self.assertTrue(top, "Country of Work is not at the top of the record")
        settings = tidy.xpath("//page[@name='hr_settings']//field[@name='payroll_country']")
        self.assertFalse(settings, "Country of Work is still on the Settings tab too")
        self.assertEqual(self.env['hr.employee']._fields['payroll_country'].string,
                         'Country of Work')
        self.assertEqual(self.env['ir.model.fields']._get(
            'hr.employee', 'payroll_country').field_description, 'Country of Work')

    def test_01f_the_rule_table_matches_the_verdict_table(self):
        """The code's table and the committed audit copy agree, box for box."""
        for name, (verdict, country) in self.table.items():
            rule = form_rules.FORM_RULES.get(name)
            if verdict == REMOVE:
                self.assertEqual(rule, form_rules.REMOVE, name)
            elif verdict == HIDE:
                self.assertEqual(rule, country, name)
            elif country != 'general':
                self.assertIn(rule, (None, country), name)
            else:
                self.assertIsNone(rule, name)
        self.assertFalse(set(form_rules.FORM_RULES) - set(self.table),
                         "a rule names a box the audit did not list")

    # ------------------------------------------------------------ test 2
    def test_02_removed_boxes_keep_their_columns_and_values(self):
        removed = [n for n, (v, _c) in self.table.items() if v == REMOVE]
        Emp = self.env['hr.employee']
        person = self.people['VN']
        values = {}
        for name in removed:
            field = Emp._fields.get(name)
            if field is None:
                continue
            self.assertTrue(field.store or field.compute or field.related,
                            "%s is no longer a field" % name)
            if field.store and not field.compute and field.type == 'char':
                values[name] = 'DEMO-%s' % name[:10]
        self.assertTrue(values)
        person.write(values)
        self.env.cr.execute("SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'hr_employee'")
        columns = {r[0] for r in self.env.cr.fetchall()}
        for name in values:
            self.assertIn(name, columns, "%s lost its column" % name)
        person.invalidate_recordset()
        for name, value in values.items():
            self.assertEqual(person[name], value)

    # ------------------------------------------------------------ test 3
    def test_03_saving_the_form_keeps_hidden_values(self):
        person = self.people['IN']
        hidden = {
            'account_number': 'DEMO-000111',
            'osh_worker_code': 'DEMO-OSH',
            'pb_npwp_number': 'DEMO-NPWP',
            'vn_si_number': 'DEMO-SI',
            'pb_position_reference': 'DEMO-POS',
        }
        hidden = {k: v for k, v in hidden.items() if k in person._fields}
        person.sudo().write(hidden)
        with Form(person.with_user(self.manager)) as form:
            form.job_title = 'DEMO tidy job'
        person.invalidate_recordset()
        self.assertEqual(person.job_title, 'DEMO tidy job')
        for name, value in hidden.items():
            self.assertEqual(person.sudo()[name], value, "%s was changed by a save" % name)
        self.assertEqual(person.payroll_country, 'IN')

    # ------------------------------------------------------------ test 4
    def test_04_dates_show_the_year(self):
        tidy, _plain = self._views(self.manager)
        node = tidy.xpath("//field[@name='date_of_joining']")
        self.assertTrue(node)
        self.assertIn("'numeric': True", node[0].get('options') or '')
        Emp = self.env['hr.employee']
        for n in tidy.iter('field'):
            parent, sub = n.getparent(), False
            while parent is not None:
                if parent.tag == 'field':
                    sub = True
                    break
                parent = parent.getparent()
            field = Emp._fields.get(n.get('name'))
            if sub or field is None or field.type not in ('date', 'datetime') or n.get('widget') \
                    or (n.get('invisible') or '') in ('1', 'True'):
                continue
            self.assertIn("'numeric': True", n.get('options') or '',
                          "date box %s still drops the year" % n.get('name'))

    # ------------------------------------------------------------ test 9
    def test_09_nobody_sees_a_box_they_could_not_see_before(self):
        for user in (self.manager, self.officer):
            tidy, plain = self._views(user)
            for key, person in self.people.items():
                with_rules = self._seen(user, person, tidy)
                without = self._seen(user, person, plain)
                newly = with_rules - without
                self.assertFalse(newly, "%s newly sees %s for %s" % (
                    user.login, sorted(newly), key))

    # ------------------------------------------------------------ test 11
    def test_11_installing_wrote_no_employee_row(self):
        data = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'pb_employee_form_tidy'), ('model', '=', 'hr.employee')])
        self.assertFalse(data, "the module ships employee records")
        if 'pb.cow.fill.log' in self.env:
            self.assertFalse(self.env['pb.cow.fill.log'].sudo().search_count([]),
                             "a fill ran at install")
