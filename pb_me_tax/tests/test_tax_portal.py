# -*- coding: utf-8 -*-
"""WDGAP S2-D — the /my/tax pages over HTTP, as a real portal login.

H1 every page answers for every country (and for nobody's scheme) with no
vendor word and no full number; H2 a send over HTTP is for the session's own
employee only, a crafted id of somebody else's change shows nothing; H3 the
My details doors send tax changes to the tax page; H4 the home tile sits
under "Me"; H5 a proof file cannot be downloaded by another employee.
"""
from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from .common import PASSWORD, PDF, TaxCase, decide


@tagged('post_install', '-at_install', 'wdgap_s2d')
class TestS2dTaxPortal(TaxCase, HttpCase):

    def setUp(self):
        super().setUp()
        # a published privacy notice would send every /my page to it first
        # (ledger S6A-8); none exists in this suite's company
        if 'pb.privacy.notice' in self.env:
            self.env['pb.privacy.notice'].sudo().search(
                [('state', '=', 'published')]).write({'state': 'replaced'})

    def _csrf(self):
        import re
        page = self.url_open('/my/details/family/new').text
        return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)

    def _clean(self, res):
        self.assertEqual(res.status_code, 200, res.url)
        self.assertNotIn('Odoo', res.text.replace('odoo', ''), res.url)
        return res.text

    def test_h1_pages_for_every_country(self):
        self.emp.sudo().write({'vietnam_tax_code': '0312345678',
                               'pb_npwp_number': '092542943407000',
                               'pb_in_pan_number': 'ABCDE1234F',
                               'identification_id': 'S1234567D'})
        self.authenticate('s2d_tax_me', PASSWORD)
        for code, kinds in (('VN', ['tax_number']), ('ID', ['tax_number', 'tax_status']),
                            ('IN', ['tax_number', 'tax_regime']), ('SG', ['tax_fund'])):
            self._pay_by(self.emp, code)
            text = self._clean(self.url_open('/my/tax'))
            for full in ('0312345678', '092542943407000', 'ABCDE1234F', 'S1234567D'):
                self.assertNotIn(full, text, '%s page shows %s' % (code, full))
            for kind in kinds:
                self.assertIn('/my/tax/change/%s' % kind, text, code)
                self._clean(self.url_open('/my/tax/change/%s' % kind))
            # a kind the country does not offer goes back to the page
            res = self.url_open('/my/tax/change/tax_regime' if code != 'IN'
                                else '/my/tax/change/tax_fund', allow_redirects=False)
            self.assertIn(res.status_code, (302, 303))
        self._pay_by(self.emp, 'MY')
        self.assertIn('are not on My Payobook yet', self._clean(self.url_open('/my/tax')))
        Config = type(self.env['hr.formula.config'])
        with patch.object(Config, 'schemes_for_employee',
                          lambda self, employee: self.browse()):
            text = self._clean(self.url_open('/my/tax'))
            self.assertIn('cannot be shown yet', text)

    def test_h2_send_own_only_and_crafted_ids(self):
        self.authenticate('s2d_tax_me', PASSWORD)
        res = self.url_open('/my/tax/send', data={
            'kind': 'tax_number', 't_number': '0312345678',
            'employee_id': self.other.id, 'csrf_token': self._csrf()},
            files={'file': ('proof.pdf', PDF, 'application/pdf')})
        self.assertEqual(res.status_code, 200)
        mine = self.Req.sudo().search([('employee_id', '=', self.emp.id)])
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine.state, 'hr_review')
        self.assertFalse(self.Req.sudo().search_count([('employee_id', '=', self.other.id)]))
        self.assertFalse(self.emp.sudo().vietnam_tax_code, 'nothing written yet')
        self.assertIn('Change waiting for HR', self._clean(self.url_open('/my/tax')))
        # the change's own page: masked, can be taken back
        text = self._clean(self.url_open('/my/tax/request/%s' % mine.id))
        self.assertNotIn('0312345678', text)
        self.assertIn('5678', text)
        # somebody else's change by id shows nothing
        theirs = self._ask('tax_number', {'t_number': '0398765432'},
                           upload=self._pdf(), emp=self.other, user=self.portal2)
        for url in ('/my/tax/request/%s' % theirs.id, '/my/details/request/%s' % theirs.id):
            res = self.url_open(url, allow_redirects=False)
            self.assertIn(res.status_code, (302, 303), url)
            self.assertNotIn('/request/%s' % theirs.id, res.headers.get('Location', ''))
        res = self.url_open('/my/tax/request/%s/withdraw' % theirs.id,
                            data={'csrf_token': self._csrf()})
        self.assertEqual(theirs.state, 'hr_review', 'not theirs to take back')
        self.url_open('/my/tax/request/%s/withdraw' % mine.id,
                      data={'csrf_token': self._csrf()})
        mine.invalidate_recordset()
        self.assertEqual(mine.state, 'draft')

    def test_h3_my_details_doors_send_tax_changes_here(self):
        req = self._ask('tax_number', {'t_number': '0312345678'},
                        upload=self._pdf())
        decide(self.env, req, 'return', 'Clearer scan please')
        self.authenticate('s2d_tax_me', PASSWORD)
        res = self.url_open('/my/details/request/%s' % req.id, allow_redirects=False)
        self.assertIn('/my/tax/request/%s' % req.id, res.headers.get('Location', ''))
        # a sent-back tax change opens its form with HR's reason
        text = self._clean(self.url_open('/my/tax/request/%s' % req.id))
        self.assertIn('Clearer scan please', text)
        self.assertIn('name="request_id"', text)
        # My details no longer lists it; its door for tax kinds goes to /my/tax
        self.assertNotIn('/my/details/request/%s' % req.id,
                         self._clean(self.url_open('/my/details')))
        res = self.url_open('/my/details/send', data={
            'kind': 'tax_number', 't_number': '0312345678',
            'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertIn('/my/tax', res.headers.get('Location', ''))

    def test_h4_home_tile_under_me(self):
        from lxml import html as lxml_html
        self.authenticate('s2d_tax_me', PASSWORD)
        doc = lxml_html.fromstring(self._clean(self.url_open('/my')))
        groups = {}
        for card in doc.xpath('//*[@data-pbme-group]'):
            for a in card.xpath('.//a[@href]'):
                groups.setdefault(a.get('href').split('?')[0], card.get('data-pbme-group'))
        self.assertEqual(groups.get('/my/tax'), 'me')

    def test_h5_proof_not_downloadable_by_someone_else(self):
        req = self._ask('tax_number', {'t_number': '0312345678'},
                        upload=self._pdf())
        att = req.attachment_id
        self.authenticate('s2d_tax_other', PASSWORD)
        res = self.url_open('/web/content/%s?download=true' % att.id)
        self.assertNotEqual(res.content, PDF)
        self.assertIn(res.status_code, (403, 404))
