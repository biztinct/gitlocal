# -*- coding: utf-8 -*-
"""FS follow-up 1 (2026-11-20) — the employee "Full details" form.

F1 Payroll tab: "Contract Type" and "Pay Category" are hidden for every
   Country of Work (and for no country); the fields stay on the form, so a
   save keeps their values.
F2 The tab names "Employment profile" and "Payroll facts" read in Vietnamese
   and Indonesian; English is unchanged.
"""

from lxml import etree

from odoo.tests import Form, TransactionCase, tagged

from . import common

BOXES = ('contract_type_id', 'structure_type_id')
TABS = {
    'vi_VN': {'Employment profile': 'Hồ sơ việc làm', 'Payroll facts': 'Dữ kiện tính lương'},
    'id_ID': {'Employment profile': 'Profil kepegawaian', 'Payroll facts': 'Data penggajian'},
}


@tagged('post_install', '-at_install', 'tidy_e')
class TestFollowup1(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager, cls.officer = common.make_hr_users(cls.env, 'fu1')
        Emp = cls.env['hr.employee'].sudo()
        cls.people = {}
        for code in common.COUNTRIES + ('',):
            cls.people[code or 'none'] = Emp.create({
                'name': 'DEMO Follow-up %s' % (code or 'none'),
                'payroll_country': code or False,
                'company_id': cls.env.company.id,
            })
        for lang in TABS:
            cls.env['res.lang']._activate_lang(lang)

    # ------------------------------------------------------------- F1
    def test_f1_payroll_tab_boxes_hidden_for_every_country(self):
        env = self.env(user=self.manager)
        tidy = common.form_arch(env, tidy=True)
        plain = common.form_arch(env, tidy=False)
        page = tidy.xpath("//page[@name='payroll_information']")
        self.assertTrue(page, "the Payroll tab is missing")
        for name in BOXES:
            # still on the form (loads and saves as before), only hidden
            self.assertTrue(page[0].xpath(".//field[@name='%s']" % name), name)
        for key, person in self.people.items():
            record = person.with_user(self.manager)
            seen = common.visible_boxes(tidy, record, set(BOXES))
            before = common.visible_boxes(plain, record, set(BOXES))
            self.assertFalse(seen, "%s still shows for %s" % (sorted(seen), key))
            self.assertEqual(before, set(BOXES),
                             "the boxes were not on the Payroll tab before for %s" % key)
        # the tab itself stays (Employee Type, Schedule, the contract line)
        self.assertFalse(page[0].get('invisible'))
        for name in ('employee_type', 'resource_calendar_id'):
            self.assertIn(name, common.visible_boxes(
                tidy, self.people['VN'].with_user(self.manager), {name}))

    def test_f1b_a_save_keeps_the_hidden_values(self):
        person = self.people['ID']
        ctype = self.env['hr.contract.type'].sudo().create({'name': 'DEMO follow-up type'})
        stype = self.env['hr.payroll.structure.type'].sudo().create({'name': 'DEMO follow-up category'})
        person.sudo().write({'contract_type_id': ctype.id, 'structure_type_id': stype.id})
        with Form(person.with_user(self.manager)) as form:
            form.job_title = 'DEMO follow-up job'
        person.invalidate_recordset()
        self.assertEqual(person.job_title, 'DEMO follow-up job')
        self.assertEqual(person.sudo().contract_type_id, ctype)
        self.assertEqual(person.sudo().structure_type_id, stype)

    # ------------------------------------------------------------- F2
    def test_f2_tab_names_in_vietnamese_and_indonesian(self):
        Emp = self.env['hr.employee'].with_user(self.manager)
        en = {p.get('string') for p in common.form_arch(Emp.env).iter('page')}
        self.assertIn('Employment profile', en, "the Employment profile tab is missing")
        for lang, words in TABS.items():
            arch = common.form_arch(Emp.with_context(lang=lang).env)
            names = {p.get('string') for p in arch.iter('page')}
            self.assertIn(words['Employment profile'], names, lang)
            self.assertNotIn('Employment profile', names, lang)
            if 'Payroll facts' in en:      # the Vietnam payroll facts tab is installed
                self.assertIn(words['Payroll facts'], names, lang)
                self.assertNotIn('Payroll facts', names, lang)

    def test_f2b_both_names_on_a_drawn_form(self):
        """Both owners need not be installed here: the renaming itself, on a
        form that has both tabs, in both languages and in English."""
        def draw(lang):
            arch = etree.fromstring(
                '<form><sheet><notebook><page string="Employment profile"/>'
                '<page string="Payroll facts" name="pb_vn_payroll_facts"/>'
                '<page string="Payroll" name="payroll_information"/></notebook></sheet></form>')
            self.env['hr.employee'].with_context(lang=lang)._pb_tidy_tab_names(arch)
            return [p.get('string') for p in arch.iter('page')]
        self.assertEqual(draw('en_US'), ['Employment profile', 'Payroll facts', 'Payroll'])
        for lang, words in TABS.items():
            self.assertEqual(draw(lang), [words['Employment profile'], words['Payroll facts'],
                                          'Payroll'], lang)
