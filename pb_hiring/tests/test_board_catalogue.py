"""Tenant, publication and serialization boundaries for board distribution."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from lxml import etree

from odoo import fields
from odoo.http import Response
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_channels_p7 import ChannelCase
from ..services.board_catalogue import CATALOGUE
from ..services.board_feeds import render_feed
from ..controllers.board_feeds import HiringBoardFeeds


@tagged('post_install', '-at_install', 'recruit_catalogue')
class TestBoardCatalogue(ChannelCase):
    def setUp(self):
        super().setUp()
        self.admin_facade = self.env['pb.hiring'].with_user(self.lead)
        self.site = self.env['website'].sudo().create({
            'name': 'Board feed test', 'domain': 'https://boards.example.com',
            'company_id': self.company.id})
        self.req.sudo().write({'location': 'Hanoi'})
        self.req.job_id.sudo().write({'website_id': self.site.id, 'is_published': True,
                                     'website_description': '<p>Public role &amp; responsibilities.</p>'})
        self.ch = self._channel('careerjet')
        # Keep the disabled-feed baseline independent of real tenant setup.
        # TransactionCase rolls this back, preserving enabled feeds after tests.
        self.ch.write({'feed_enabled': False, 'feed_token': False})
        rows = self.facade.job_board_detail(self.req.id)['rows']
        self.rc = self.env['pb.hiring.role.channel'].sudo().browse(
            next(r['id'] for r in rows if r['key'] == 'careerjet'))
        self.expiry = fields.Date.today() + timedelta(days=30)

    def _enable(self):
        self.admin_facade.job_board_setup('careerjet', {'feed_enabled': True})

    def _select(self):
        self.facade.job_board_feed_select(self.rc.id, True, str(self.expiry))

    def test_catalogue_country_coverage_and_idempotency(self):
        result = self.facade.job_board_catalogue()
        self.assertEqual(len(result['boards']), 29)
        self.Channel._ensure_for(self.company)
        self.assertEqual(len(self.Channel.search([('company_id', '=', self.company.id), ('key', 'in', list(CATALOGUE))])), 29)
        self.assertEqual(self._channel('naukri').country_ids.code, 'IN')
        self.assertEqual(self._channel('foundit_id').country_ids.code, 'ID')
        self.assertEqual(set(self._channel('glints').country_ids.mapped('code')), {'VN', 'ID'})
        self.assertFalse(self._channel('naukri')._applies_to(self.req))
        self.assertTrue(self._channel('topcv')._applies_to(self.req))
        self._channel('topcv').write({'active': False, 'name': 'Our chosen TopCV label'})
        self.Channel._ensure_for(self.company)
        preserved = self.Channel.with_context(active_test=False).search([('company_id', '=', self.company.id), ('key', '=', 'topcv')])
        self.assertFalse(preserved.active)
        self.assertEqual(preserved.name, 'Our chosen TopCV label')

    def test_onboarding_cannot_claim_connection_or_request_delivery(self):
        guide = self.admin_facade.job_board_setup('topcv', {'onboarding_stage': 'response_received', 'onboarding_note': 'Contract location'})
        self.assertIn('Payobook', guide['request_text'])
        row = next(b for b in self.facade.job_board_catalogue()['boards'] if b['key'] == 'topcv')
        self.assertFalse(row['ready'])
        self.assertEqual(row['status'], 'Payobook integration pending')
        with self.assertRaises(UserError):
            self.admin_facade.job_board_setup('topcv', {'ready': True})
        with self.assertRaises(UserError):
            self.admin_facade.job_board_setup('topcv', {'feed_enabled': True})

    def test_setup_permissions_and_company_scope(self):
        with self.assertRaises(AccessError):
            self.facade.job_board_setup('careerjet', {'feed_enabled': True})
        self._enable()
        other = self.env['res.company'].sudo().create({'name': 'Other board tenant'})
        self.Channel._ensure_for(other)
        other_ch = self.Channel.search([('company_id', '=', other.id), ('key', '=', 'careerjet')])
        self.assertFalse(other_ch.feed_enabled)
        self.assertFalse(other_ch.feed_token)
        with self.assertRaises(AccessError):
            self.rc.with_user(self.recruiter).write({'feed_selected': True})
        self.assertEqual(self.facade.job_board_guide('careerjet')['feeds'], [])

    def test_feed_requires_explicit_selection_and_never_claims_live(self):
        self.assertEqual(self.ch._feed_items(self.site), [])
        with self.assertRaises(UserError):
            self._select()
        self._enable()
        self.assertEqual(self.ch._feed_items(self.site), [])
        self._select()
        items = self.ch._feed_items(self.site)
        self.assertEqual(len(items), 1)
        self.assertIn('utm_source=Careerjet', items[0]['url'])
        self.assertTrue(items[0]['url'].startswith(self.site.domain))
        self.assertEqual(self.rc.state, 'not_posted')
        self.assertEqual(self.rc.board_state, 'draft')
        self.facade.job_board_feed_select(self.rc.id, False)
        self.assertEqual(self.ch._feed_items(self.site), [])

    def test_feed_excludes_confidential_closed_unpublished_expired_and_wrong_site(self):
        self._enable(); self._select()
        self.req.sudo().write({'is_confidential': True})
        self.assertEqual(self.ch._feed_items(self.site), [])
        self.req.sudo().write({'is_confidential': False})
        self.req.job_id.is_published = False
        self.assertEqual(self.ch._feed_items(self.site), [])
        self.req.job_id.is_published = True
        self.req._chain_state_write('setup')
        self.assertEqual(self.ch._feed_items(self.site), [])
        self.req._chain_state_write('open')
        self.rc.feed_expires = fields.Date.today() - timedelta(days=1)
        self.assertEqual(self.ch._feed_items(self.site), [])
        self.rc.feed_expires = self.expiry
        self.assertEqual(len(self.ch._feed_items(self.site)), 1)
        other_site = self.site.copy({'domain': 'https://other.example.com'})
        self.assertEqual(self.ch._feed_items(other_site), [])
        self.ch.active = False
        self.assertEqual(self.ch._feed_items(self.site), [])

    def test_feed_uses_public_advert_not_private_board_draft(self):
        self._enable(); self._select()
        self.rc.board_values = {'description': '<p>Private draft pay information</p>'}
        first = self.ch._feed_items(self.site)[0]
        self.assertNotIn('Private', first['description'])
        self.req.job_id.website_description = '<p>Updated public advert.</p>'
        second = self.ch._feed_items(self.site)[0]
        self.assertEqual(second['id'], first['id'])
        self.assertEqual(second['published'], first['published'])
        self.assertIn('Updated public', second['description'])

    def test_feed_expiry_and_domain_validation(self):
        self._enable()
        for bad in ('garbage', '', str(fields.Date.today() + timedelta(days=91))):
            with self.assertRaises(UserError):
                self.facade.job_board_feed_select(self.rc.id, True, bad)
        self.site.domain = 'http://boards.example.com'
        with self.assertRaises(UserError):
            self._select()

    def test_feed_disable_and_reenable_rotates_link(self):
        self._enable(); self._select()
        old = self.ch.feed_token
        self.admin_facade.job_board_setup('careerjet', {'feed_enabled': False})
        self.assertEqual(self.ch._feed_items(self.site), [])
        self._enable()
        self.assertNotEqual(self.ch.feed_token, old)

    def test_provider_xml_roundtrip_and_no_private_fields(self):
        self._enable(); self._select()
        job = self.ch._feed_items(self.site)[0]
        job['description'] = '<p>A & B ]]> café tiếng Việt</p>'
        for provider in ('careerjet', 'jooble'):
            body = render_feed(provider, [job])
            root = etree.fromstring(body)
            self.assertEqual(root.findtext('job/description'), job['description'])
            self.assertNotIn(b'onboarding_note', body)
            self.assertNotIn(b'feed_token', body)
        jooble = etree.fromstring(render_feed('jooble', [job]))
        self.assertEqual(jooble.find('job').get('id'), job['id'])
        self.assertEqual(jooble.findtext('job/expire'), self.expiry.strftime('%d.%m.%Y'))

    def test_public_feed_route_checks_site_company_token_and_disable(self):
        self._enable(); self._select()
        fake = SimpleNamespace(env=self.env, website=self.site, not_found=lambda: Response(status=404),
                               make_response=lambda body, headers: Response(body, headers=headers))
        endpoint = HiringBoardFeeds().feed
        with patch('odoo.addons.pb_hiring.controllers.board_feeds.request', fake):
            self.assertEqual(endpoint(self.site.id, self.ch.id, 'wrong').status_code, 404)
            self.assertEqual(endpoint(self.site.id, self.ch.id, 'tiếng').status_code, 404)
            self.assertEqual(endpoint(self.site.id + 9999, self.ch.id, self.ch.feed_token).status_code, 404)
            response = endpoint(self.site.id, self.ch.id, self.ch.feed_token)
            body, headers = response.get_data(), response.headers
            self.assertEqual(len(etree.fromstring(body)), 1)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.ch.feed_enabled = False
            self.assertEqual(endpoint(self.site.id, self.ch.id, self.ch.feed_token).status_code, 404)
