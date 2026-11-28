# -*- coding: utf-8 -*-
"""WDGAP S2-F — Suggest on the Indonesian BPJS sheets and the monthly tax
line (numbered F2.x in the S2-F report).

Fixture: an Indonesian company whose scheme names its items the way a real
customer's Indonesian scheme does (plain English, every contribution a part
of the scheme's own total — `net_role_detail`), a second scheme that also
has a WHOLE item, and a Vietnamese scheme for the "other countries are
unchanged" check. DEMO names only.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_form_lines.models import suggest_s2f

OFFICER = ('base.group_user,om_hr_payroll.group_hr_payroll_user,'
           'pb_hr_payroll_base.group_payroll_base_officer')

#: (name, code, role, part of a total) — as the customer's scheme names them
CUSTOMER_ITEMS = (
    ('Basic Salary', 'IDBASICSALARY', 'earning', True),
    ('BPJS allowance', 'IDBPJSALLOW', 'earning', True),
    ('Life insurance income', 'IDLIFEINSINCOM', 'earning', True),
    ('Accident insurance income', 'IDACCIDINSINCO', 'earning', True),
    ('BPJS health company income', 'IDBPJSHEALCOMP', 'earning', True),
    ('Total income', 'IDTOTALINCOME', 'earning', False),
    ('Old age company', 'IDOLDAGECOMPAN', 'employer_cost', True),
    ('Pension company', 'IDPENSIONCOMPA', 'employer_cost', True),
    ('Life insurance deduction', 'IDLIFEINSDEDUC', 'deduction', True),
    ('Accident insurance deduction', 'IDACCIDINSDEDU', 'deduction', True),
    ('BPJS health company deduction', 'IDBPJSHEALCOMA', 'deduction', True),
    ('Old age employee', 'IDOLDAGEEMP', 'deduction', True),
    ('Pension employee', 'IDPENSIONEMP', 'deduction', True),
    ('BPJS health employee', 'IDBPJSHEALTEMP', 'deduction', True),
    ('Tax adjustment', 'IDTAXADJUSTMEN', 'deduction', True),
    ('Payable tax', 'PIT', 'deduction', True),
    ('Severance tax', 'IDSEVERANCETAX', 'deduction', True),
    ('Total deduction', 'IDTOTALDEDUCTI', 'deduction', False),
    ('Take home pay', 'IDTAKEHOMEPAY', 'net', False),
    ('BPJS TK wage base', 'IDBPJSTKWAGE', 'info', False),
    ('BPJS health wage base', 'IDBPJSHEALWAGE', 'info', False),
)

EXPECTED = {
    ('ID_BPJS_TK', 'JHT_EE'): 'IDOLDAGEEMP',
    ('ID_BPJS_TK', 'JHT_ER'): 'IDOLDAGECOMPAN',
    ('ID_BPJS_TK', 'JP_EE'): 'IDPENSIONEMP',
    ('ID_BPJS_TK', 'JP_ER'): 'IDPENSIONCOMPA',
    ('ID_BPJS_TK', 'JKK_ER'): 'IDACCIDINSINCO',
    ('ID_BPJS_TK', 'JKM_ER'): 'IDLIFEINSINCOM',
    ('ID_BPJS_TK', 'WAGE'): 'IDBPJSTKWAGE',
    ('ID_BPJS_KES', 'KES_EE'): 'IDBPJSHEALTEMP',
    ('ID_BPJS_KES', 'KES_ER'): 'IDBPJSHEALCOMP',
    ('ID_BPJS_KES', 'WAGE'): 'IDBPJSHEALWAGE',
    ('ID_BPMP', 'PPH21'): 'PIT',
}


@tagged('post_install', '-at_install', 'wdgap_s2f')
class TestS2fSuggest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.idr = cls.env.ref('base.IDR')
        cls.vnd = cls.env.ref('base.VND')
        (cls.idr | cls.vnd).write({'active': True})
        Company = cls.env['res.company']
        cls.co = Company.create({'name': 'DEMO S2F Indonesia', 'currency_id': cls.idr.id,
                                 'country_id': cls.env.ref('base.id').id})
        cls.co_vn = Company.create({'name': 'DEMO S2F Vietnam', 'currency_id': cls.vnd.id,
                                    'country_id': cls.env.ref('base.vn').id})
        both = [(6, 0, [cls.co.id, cls.co_vn.id])]
        cls.officer = new_test_user(cls.env, login='s2f_officer', groups=OFFICER,
                                    company_id=cls.co.id, company_ids=both)
        cls.cfg = cls._config(cls.co, 'DEMO S2F ID focused', 'SFIDA', 'ID')
        cls.items = {code: cls._rule(cls.cfg, name, code, role, detail)
                     for name, code, role, detail in CUSTOMER_ITEMS}
        # a second scheme with a WHOLE pension item and an employer-cost
        # health premium: those beat a part and an income item
        cls.cfg2 = cls._config(cls.co, 'DEMO S2F ID whole', 'SFIDB', 'ID')
        cls.whole = {code: cls._rule(cls.cfg2, name, code, role, detail) for name, code, role, detail in (
            ('Pension employee share', 'JPWHOLE', 'deduction', False),
            ('Pension employee', 'JPPART', 'deduction', True),
            ('BPJS health company income', 'KESINC', 'earning', True),
            ('BPJS Kesehatan perusahaan', 'KESER', 'employer_cost', True),
        )}
        cls.cfg_vn = cls._config(cls.co_vn, 'DEMO S2F VN', 'SFVN', 'VN')
        cls.vn_items = {code: cls._rule(cls.cfg_vn, name, code, role, detail)
                        for name, code, role, detail in (
                            ('Thu nhập chịu thuế', 'TNCT', 'info', False),
                            ('Thuế TNCN', 'PIT', 'deduction', True),       # a part: still skipped
                            ('Thuế TNCN phải nộp', 'PITDUE', 'deduction', False))}
        cls.Map = cls.env['pb.gov.form.map']

    @classmethod
    def _config(cls, company, name, code, country):
        return cls.env['hr.formula.config'].sudo().create({
            'name': name, 'code': code, 'cycle_type': 'end_cycle', 'country_code': country,
            'company_id': company.id, 'state': 'active'})

    @classmethod
    def _rule(cls, cfg, name, code, role, detail):
        return cls.env['hr.formula.rule'].sudo().create({
            'config_id': cfg.id, 'name': name, 'code': code, 'column_type': 'input',
            'sequence': 10 + len(cfg.rule_ids), 'default_value': 0.0, 'value_kind': 'money',
            'net_role': role, 'net_role_detail': detail,
            'appears_on_payslip': role != 'info'})

    def _suggest(self, form_xmlid, company=None):
        company = company or self.co
        board = self.env['pb.gov.form.board'].with_user(self.officer).with_context(
            allowed_company_ids=[company.id])
        return board.suggest(self.env.ref(form_xmlid).id)

    # ======================================================== F2.1 / F2.2
    def test_f2_1_customer_names_are_proposed_and_nothing_is_saved(self):
        before = self.Map.sudo().search_count([])
        got = {}
        for xmlid in ('pb_form_lines.form_id_bpjs_tk', 'pb_form_lines.form_id_bpjs_kes',
                      'pb_form_lines.form_id_bpmp'):
            form = self.env.ref(xmlid)
            for p in self._suggest(xmlid):
                if p['scheme'] == self.cfg.name:
                    self.assertNotIn((form.code, p['line_code']), got, 'one per scheme per line')
                    got[(form.code, p['line_code'])] = p['code']
        for key, code in EXPECTED.items():
            self.assertEqual(got.get(key), code, key)
        self.assertEqual(self.Map.sudo().search_count([]), before, 'Suggest never saves')
        # a total is never offered for a contribution line
        self.assertNotIn('IDTOTALDEDUCTI', got.values())

    def test_f2_2_a_whole_item_and_the_first_role_win(self):
        props = self._suggest('pb_form_lines.form_id_bpjs_tk') + \
            self._suggest('pb_form_lines.form_id_bpjs_kes')
        mine = {p['line_code']: p['code'] for p in props if p['scheme'] == self.cfg2.name}
        self.assertEqual(mine.get('JP_EE'), 'JPWHOLE', 'a whole item beats a part')
        self.assertEqual(mine.get('KES_ER'), 'KESER', 'employer cost beats income')

    # ================================================================ F2.3
    def test_f2_3_other_countries_unchanged(self):
        ours = set(suggest_s2f.S2F_LINES)
        lines = self.env['pb.gov.form.line'].sudo().search([])
        xmlids = lines.get_external_id()
        for line in lines:
            if xmlids.get(line.id) not in ours:
                self.assertFalse(line.suggest_parts, xmlids.get(line.id) or line.code)
            else:
                self.assertEqual(line.form_id.country_code, 'ID')
        # Vietnam: a part of a total is still never proposed, the whole one is
        vn = self._suggest('pb_form_lines.form_vn_05kk_tt89', self.co_vn)
        codes = {p['code'] for p in vn}
        self.assertNotIn('PIT', codes)
        self.assertIn('PITDUE', codes)

    # ================================================================ F2.4
    def test_f2_4_existing_databases_get_the_words_once(self):
        Line = self.env['pb.gov.form.line'].sudo()
        for xmlid, (old_w, old_r, _nw, _nr) in suggest_s2f.S2F_LINES.items():
            self.env.ref(xmlid).write({'suggest_words': old_w, 'suggest_roles': old_r,
                                       'suggest_parts': False})
        for xmlid, (old_w, _nw) in suggest_s2f.S2F_WORDS_ONLY.items():
            self.env.ref(xmlid).write({'suggest_words': old_w})
        # somebody changed one line's words: it is left alone
        mine = self.env.ref('pb_form_lines.form_id_bpjs_tk_jp_ee')
        mine.write({'suggest_words': 'iuran pensiun karyawan'})
        others = Line.search([('id', 'not in', [self.env.ref(x).id for x in
                                                list(suggest_s2f.S2F_LINES) + list(suggest_s2f.S2F_WORDS_ONLY)])])
        snap = {l.id: (l.suggest_words, l.suggest_roles, l.suggest_parts) for l in others}
        done = suggest_s2f.apply(self.env)
        self.assertEqual(done['pb_form_lines.form_id_bpjs_tk_jp_ee'], 'changed by someone - left')
        self.assertEqual(mine.suggest_words, 'iuran pensiun karyawan')
        self.assertFalse(mine.suggest_parts)
        for xmlid, (_ow, _or, new_w, new_r) in suggest_s2f.S2F_LINES.items():
            if xmlid.endswith('jp_ee'):
                continue
            line = self.env.ref(xmlid)
            self.assertEqual(done[xmlid], 'updated')
            self.assertEqual((line.suggest_words, line.suggest_roles, line.suggest_parts),
                             (new_w, new_r, True), xmlid)
        for xmlid, (_ow, new_w) in suggest_s2f.S2F_WORDS_ONLY.items():
            self.assertEqual(self.env.ref(xmlid).suggest_words, new_w)
        # nothing else touched; a second run changes nothing
        self.assertEqual({l.id: (l.suggest_words, l.suggest_roles, l.suggest_parts)
                          for l in others}, snap)
        again = suggest_s2f.apply(self.env)
        self.assertEqual({v for k, v in again.items() if not k.endswith('jp_ee')}, {'already'})

    def test_f2_5_migration_values_equal_the_shipped_data(self):
        root = get_module_path('pb_form_lines')
        text = ''.join(open(os.path.join(root, 'data', f), encoding='utf-8').read()
                       for f in ('forms_id.xml', 'forms_fund_id.xml'))

        def block(rid):
            return re.search(r'<record id="%s" model="pb.gov.form.line">(.*?)</record>' % rid,
                             text, re.S).group(1)
        for xmlid, (_ow, _or, new_w, new_r) in suggest_s2f.S2F_LINES.items():
            b = block(xmlid.split('.')[1])
            self.assertIn('<field name="suggest_words">%s</field>' % new_w, b)
            self.assertIn('<field name="suggest_roles">%s</field>' % new_r, b)
            self.assertIn('<field name="suggest_parts" eval="True"/>', b)
            line = self.env.ref(xmlid)
            self.assertEqual((line.suggest_words, line.suggest_roles, line.suggest_parts),
                             (new_w, new_r, True), 'a fresh install carries the new words')
        for xmlid, (_ow, new_w) in suggest_s2f.S2F_WORDS_ONLY.items():
            self.assertIn('<field name="suggest_words">%s</field>' % new_w,
                          block(xmlid.split('.')[1]))
