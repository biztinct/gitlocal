# -*- coding: utf-8 -*-
"""PSCHEME P4 B/C — "Usual pay scheme by country" on Mapping, and the empty card.

T1  country line detection: exact shape only, company scoping
T2  the board payload: people, "rely on this" counts, set / not set / no scheme
T3  `country_set` set / change / remove; fast lane and second approver; re-check; audit
T4  a person with no row and no team line is answered by the country line; an
    own row is unaffected; a named-people rule earlier in sequence still wins
T5  rights: an HR officer proposes and cannot carry out; portal refused
T6  other rules listed read-only with the right counts; Remove refused / allowed
T7  refusals (not active / other company / other country unconfirmed / advance)
T8  the empty card's two states (static: the template and the getter)
T9  static: no vendor word / rung / config / cycle on screen; vi + id complete
T10 the dependency rail (the formula engine never imports this module)
"""
import os
import re

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.pb_scheme_map.models.pb_country_lines import line_country

from .p2a_common import P2aCase

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = 'pb_scheme_main_question'


@tagged('post_install', '-at_install', 'pscheme', 'pscheme_p4')
class TestP4CountryLines(P2aCase):

    def country_line(self, config, code, company=None, **kw):
        company = company or self.company
        values = {'config_id': config.id, 'cycle_type': 'any', 'company_id': company.id,
                  'domain': "[('company_id', '=', %s), ('payroll_country', '=', '%s')]"
                            % (company.id, code)}
        values.update(kw)
        return self.Assign.create(values)

    def answer(self, employee, company=None):
        company = company or self.company
        Map = self.Map.with_company(company).with_context(allowed_company_ids=[company.id],
                                                          **{MAIN: True})
        kind = self.env['hr.employee']._pb_main_cycle(company.id)
        return Map.resolve_many(employee.ids, kind).get(employee.id) or {}

    def row_of(self, payload, code):
        return next(r for r in payload['rows'] if r['country'] == code)

    # ------------------------------------------------------------------ T1
    def test_t1_detection(self):
        good = self.country_line(self.vn_end, 'VN')
        self.assertEqual(line_country(good), 'VN')
        bare = self.Assign.create({'config_id': self.id_end.id, 'company_id': self.company.id,
                                   'domain': "[('payroll_country', '=', 'ID')]"})
        self.assertEqual(line_country(bare), 'ID')
        named = self.Assign.create({'config_id': self.vn_end.id, 'company_id': self.company.id,
                                    'domain': "[('company_id', '=', %s), ('barcode', 'in', ['A1', 'A2'])]"
                                              % self.company.id})
        self.assertEqual(line_country(named), '')
        wider = self.Assign.create({'config_id': self.sg_end.id, 'company_id': self.company.id,
                                    'domain': "[('payroll_country', '=', 'SG'), ('active', '=', True)]"})
        self.assertEqual(line_country(wider), '')
        other_co = self.Assign.create({'config_id': self.sg_end.id, 'company_id': self.company.id,
                                       'domain': "[('company_id', '=', 999999), ('payroll_country', '=', 'SG')]"})
        self.assertEqual(line_country(other_co), '', "another company's term is not this line's")
        country, other = self.Board._map_rules(self.company.id)
        self.assertEqual(set(country), {'VN', 'ID'})
        self.assertEqual({r.id for r in other}, {named.id, wider.id, other_co.id})

    # ------------------------------------------------------------------ T2
    def test_t2_payload(self):
        a = self._person('DEMO P4 Anh', self.loose, 'VN')
        b = self._person('DEMO P4 Binh', self.loose, 'VN')
        c = self._person('DEMO P4 Chi', self.team, 'VN')
        self._person('DEMO P4 Dewi', self.loose, 'ID')
        self.row(b, self.vn_end, self.first)
        self.line(self.vn_end, team=self.team)        # Chi is caught by her team
        data = self.board().country_lines(self.company.id)
        vn = self.row_of(data, 'VN')
        self.assertEqual((vn['people'], vn['rely'], vn['holes'], vn['state']), (3, 1, 1, 'not_set'))
        self.assertTrue(vn['options'])
        self.assertNotIn(self.vn_mid.id, [o['id'] for o in vn['options']], 'never an advance')
        self.assertEqual(self.row_of(data, 'ID')['state'], 'not_set')
        self.assertEqual(self.row_of(data, 'SG')['state'], 'not_set')   # a scheme, nobody there
        self.country_line(self.vn_end, 'VN')
        vn = self.row_of(self.board().country_lines(self.company.id), 'VN')
        self.assertEqual((vn['state'], vn['holes'], vn['rely']), ('set', 0, 1))
        self.assertEqual(vn['line']['config_id'], self.vn_end.id)
        # a country with people and no active scheme at all
        self._person('DEMO P4 Mei', self.loose, 'MY')
        my = self.row_of(self.board().country_lines(self.company.id), 'MY')
        self.assertEqual(my['state'], 'no_scheme')
        self.assertTrue(a)   # Anh is the one hole above

    # ------------------------------------------------------------------ T3
    def test_t3_set_change_remove_fast_lane(self):
        anh = self._person('DEMO P4 Anh', self.loose, 'VN')
        self.assertFalse(self.answer(anh).get('config_id'))
        out = self.board().country_set(self.company.id, 'VN', self.vn_end.id)
        self.assertTrue(out['saved'], out)
        self.assertEqual(out.get('caught'), 1)
        self.assertEqual(self.answer(anh)['config_id'], self.vn_end.id)
        line = self.Board._map_rules(self.company.id)[0]['VN'][0]
        self.assertEqual(line.company_id, self.company)
        self.assertIn("('payroll_country', '=', 'VN')", line.domain)
        # change: the same line, another scheme
        out = self.board().country_set(self.company.id, 'VN', self.vn_reg.id)
        self.assertTrue(out['saved'])
        self.assertEqual(self.Board._map_rules(self.company.id)[0]['VN'][0], line)
        self.assertEqual(line.config_id, self.vn_reg)
        # remove: archived, the person relies on nothing again
        out = self.board().country_set(self.company.id, 'VN', False)
        self.assertTrue(out['saved'])
        self.assertFalse(line.active)
        self.assertFalse(self.answer(anh).get('config_id'))
        # the audit: every change is a request of kind country_set
        reqs = self.env['pb.schememap.proposal'].sudo().search(
            [('kind', '=', 'country_set'), ('company_id', '=', self.company.id)])
        self.assertEqual(len(reqs), 3)
        self.assertTrue(all(r.applied for r in reqs))
        rows = reqs[-1]._proposal_rows() if reqs else []
        self.assertTrue(rows)

    def test_t3b_second_approver_and_recheck(self):
        company, hr, boss = self.routed('DEMO P4 Routed')
        self._person('DEMO P4 Routed person', None, 'VN', company=company)
        vn = self._config('DEMO P4 Routed Vietnam', 'DEMOP4RVN', 'end_cycle', 'VN', company)
        Board = self.Board.with_user(hr).with_context(allowed_company_ids=[company.id])
        out = Board.country_set(company.id, 'VN', vn.id)
        self.assertTrue(out['pending'], out)
        self.assertFalse(self.Board._map_rules(company.id)[0].get('VN'))
        self.approve(out, boss, company)
        self.assertEqual(self.Board._map_rules(company.id)[0]['VN'][0].config_id, vn)
        # re-check: somebody changed the line while a second request waited
        vn2 = self._config('DEMO P4 Routed Vietnam two', 'DEMOP4RVN2', 'regular', 'VN', company)
        out = Board.country_set(company.id, 'VN', vn2.id)
        self.assertTrue(out['pending'])
        line = self.Board._map_rules(company.id)[0]['VN'][0]
        vn3 = self._config('DEMO P4 Routed Vietnam three', 'DEMOP4RVN3', 'end_cycle', 'VN', company)
        line.config_id = vn3.id                      # somebody moved it meanwhile
        request = self.approve(out, boss, company)
        self.assertEqual(line.config_id, vn3, 'nothing was changed')
        self.assertIn('Vietnam', request.block_reason or '')

    # ------------------------------------------------------------------ T4
    def test_t4_who_the_line_answers(self):
        anh = self._person('DEMO P4 Anh', self.loose, 'VN')
        own = self._person('DEMO P4 Own', self.loose, 'VN')
        self.row(own, self.vn_reg, self.first)
        named = self._person('DEMO P4 Named', self.loose, 'VN')
        named.barcode = 'DEMOP4N1'
        self.Assign.create({'config_id': self.id_end.id, 'company_id': self.company.id,
                            'sequence': 5, 'domain': "[('company_id', '=', %s), ('barcode', 'in', ['DEMOP4N1'])]"
                                                     % self.company.id})
        self.board().country_set(self.company.id, 'VN', self.vn_end.id)
        self.assertEqual(self.answer(anh)['config_id'], self.vn_end.id)
        self.assertEqual(self.answer(own)['config_id'], self.vn_reg.id, 'an own row is unaffected')
        self.assertEqual(self.answer(named)['config_id'], self.id_end.id,
                         'a named-people rule earlier in sequence still wins')
        line = self.Board._map_rules(self.company.id)[0]['VN'][0]
        self.assertGreater(line.sequence, 5, 'written after the other rules')

    # ------------------------------------------------------------------ T5
    def test_t5_rights(self):
        company, hr, boss = self.routed('DEMO P4 Rights')
        vn = self._config('DEMO P4 Rights Vietnam', 'DEMOP4RTVN', 'end_cycle', 'VN', company)
        # the HR officer proposes, never carries out (nobody writes a line by himself)
        with self.assertRaises(AccessError):
            self.Board.with_user(hr).with_context(
                allowed_company_ids=[company.id], pb_schememap_approved_write=False
            )._country_write({'company_id': company.id, 'country': 'VN', 'config_id': vn.id})
        portal = new_test_user(self.env, login='p4_portal', groups='base.group_portal',
                               company_id=company.id, company_ids=[(6, 0, [company.id])])
        with self.assertRaises(AccessError):
            self.Board.with_user(portal).with_context(allowed_company_ids=[company.id]).country_set(
                company.id, 'VN', vn.id)
        with self.assertRaises(AccessError):
            self.Board.with_user(portal).with_context(allowed_company_ids=[company.id]).country_lines(
                company.id)

    # ------------------------------------------------------------------ T6
    def test_t6_other_rules(self):
        anh = self._person('DEMO P4 Anh', self.loose, 'VN')
        anh.barcode = 'DEMOP4A1'
        bao = self._person('DEMO P4 Bao', self.loose, 'VN')
        bao.barcode = 'DEMOP4B1'
        rule = self.Assign.create({
            'config_id': self.vn_end.id, 'company_id': self.company.id,
            'domain': "[('company_id', '=', %s), ('barcode', 'in', ['DEMOP4A1', 'DEMOP4B1', 'GONE'])]"
                      % self.company.id})
        data = self.board().country_lines(self.company.id)
        other = next(o for o in data['others'] if o['id'] == rule.id)
        self.assertIn('3', other['words'])
        self.assertEqual((other['reaches'], other['uncovered'], other['removable']), (2, 2, False))
        with self.assertRaises(UserError):
            self.board().other_rule_remove(rule.id, self.company.id)
        # once Vietnam's own line pays them the same way, the rule can go
        self.board().country_set(self.company.id, 'VN', self.vn_end.id)
        other = next(o for o in self.board().country_lines(self.company.id)['others']
                     if o['id'] == rule.id)
        self.assertTrue(other['removable'])
        out = self.board().other_rule_remove(rule.id, self.company.id)
        self.assertTrue(out['saved'])
        self.assertFalse(rule.active)
        self.assertEqual(self.answer(anh)['config_id'], self.vn_end.id)

    # ------------------------------------------------------------------ T7
    def test_t7_refusals(self):
        off = self._config('DEMO P4 Draft', 'DEMOP4OFF', 'end_cycle', 'VN')
        off.state = 'draft'
        other = self.env['res.company'].create({'name': 'DEMO P4 Elsewhere',
                                                'currency_id': self.company.currency_id.id})
        far = self._config('DEMO P4 Far', 'DEMOP4FAR', 'end_cycle', 'VN', other)
        cases = [(off, False), (far, False), (self.vn_mid, False), (self.sg_end, False)]
        for config, confirm in cases:
            with self.assertRaises(UserError, msg=config.name):
                self.board().country_set(self.company.id, 'VN', config.id, confirm)
        out = self.board().country_set(self.company.id, 'VN', self.sg_end.id, True)
        self.assertTrue(out['saved'], 'another country, confirmed')
        with self.assertRaises(UserError):
            self.board().country_set(self.company.id, 'VN', self.sg_end.id, True)   # already it
        with self.assertRaises(UserError):
            self.board().country_set(self.company.id, 'ID', False)                  # nothing to remove

    # ------------------------------------------------------------------ T8
    def test_t8_empty_card(self):
        xml = open(os.path.join(HERE, 'static', 'src', 'xml', 'scheme_map.xml')).read()
        self.assertIn('Everyone is paid by their own pay scheme', xml)
        self.assertIn('Giving a team a usual pay scheme is optional. It pre-fills new people in that team.', xml)
        self.assertNotIn('Nothing is attached to a scheme yet', xml)
        self.assertNotIn('the map already exists', xml)
        js = open(os.path.join(HERE, 'static', 'src', 'js', 'scheme_map_board.js')).read()
        self.assertIn('get everyoneOwn()', js)
        self.assertIn('without * 50 <= people', js)

    # ------------------------------------------------------------------ T9
    def test_t9_words_and_translations(self):
        import polib
        texts = []
        for rel in (('static', 'src', 'xml', 'country_lines.xml'), ('static', 'src', 'js', 'country_lines.js'),
                    ('models', 'pb_country_lines.py')):
            texts.append(open(os.path.join(HERE, *rel)).read())
        strings = []
        lit = r'"(?:[^"\\]|\\.)*"'
        for text in texts:
            for call in re.findall(r'(?<![A-Za-z0-9_])_t?\(((?:\s*%s)+)' % lit, text):
                strings.append(''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', call)))
        self.assertGreater(len(strings), 20)
        banned = re.compile(r'\b(odoo|rung|config|cycle)\b', re.I)
        self.assertFalse([s for s in strings if banned.search(s)], 'a technical word on screen')
        for lang in ('vi_VN', 'id_ID'):
            po = {e.msgid: e.msgstr for e in polib.pofile(os.path.join(HERE, 'i18n', '%s.po' % lang))}
            missing = [s for s in strings if not (po.get(s.replace('\\"', '"')) or '').strip()]
            self.assertFalse(missing, '%s lacks %s' % (lang, missing[:5]))
            self.assertFalse([v for v in po.values() if 'odoo' in (v or '').lower()])

    # ------------------------------------------------------------------ T10
    def test_t10_dependency_rail(self):
        formula = os.path.join(os.path.dirname(HERE), 'pb_hr_payroll_formula')
        for root, _dirs, files in os.walk(formula):
            for name in files:
                if name.endswith('.py'):
                    text = open(os.path.join(root, name), encoding='utf-8').read()
                    self.assertNotIn('pb_scheme_map.models.pb_country_lines', text)
                    self.assertNotIn('from odoo.addons.pb_scheme_map', text)
