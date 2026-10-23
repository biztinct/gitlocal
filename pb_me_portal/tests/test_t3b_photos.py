# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T3b — colleague photos (D5, test T3b.8) and the home's extra-card
hook (§2).

`/my/photo/<id>/<size>` serves the person's own photo or an ACTIVE colleague
of one of their own employee records' companies; anything else is a 404.
`pb.me.home._colleague_photo_url` is the same route for a face the reader may
see and the grey silhouette otherwise. `_pbme_extra_cards` is the registry
other modules add home cards through; a broken card never blanks the home.
"""
import logging
from unittest.mock import patch

from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pb_me_portal.models import pb_me_home

from .test_portal_accounts import _make_share, _pin_dbfilter

_logger = logging.getLogger(__name__)

PASSWORD = 'tiers-t3b-photo-probe-2026'


def _colleagues(env, prefix):
    """A same-company colleague, an archived one, and another company's
    person (each with a photo-less record: the avatar is generated)."""
    Emp = env['hr.employee'].sudo()
    same = Emp.create({'name': '%s Same Co' % prefix, 'company_id': env.company.id})
    gone = Emp.create({'name': '%s Archived' % prefix, 'company_id': env.company.id})
    gone.write({'active': False})
    far_co = env['res.company'].sudo().create({'name': '%s Far Co' % prefix})
    far = Emp.create({'name': '%s Far Person' % prefix, 'company_id': far_co.id})
    return same, gone, far


@tagged('post_install', '-at_install')
class TestT3bPhotoRule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t3b_photo_rule', 'Quinn Photo Rule')
        cls.same, cls.gone, cls.far = _colleagues(cls.env, 'T3b Rule')
        cls.Home = cls.env['pb.me.home'].with_user(cls.share)

    def test_t3b_8_rule_and_colleague_url(self):
        self.assertTrue(self.Home._pbme_photo_allowed(self.share_emp))
        self.assertTrue(self.Home._pbme_photo_allowed(self.same))
        self.assertFalse(self.Home._pbme_photo_allowed(self.gone))
        self.assertFalse(self.Home._pbme_photo_allowed(self.far))
        self.assertEqual(self.Home._colleague_photo_url(self.same),
                         '/my/photo/%s/avatar_128' % self.same.id)
        self.assertEqual(self.Home._colleague_photo_url(self.same, 'avatar_256'),
                         '/my/photo/%s/avatar_256' % self.same.id)
        self.assertEqual(self.Home._colleague_photo_url(self.far),
                         pb_me_home.PHOTO_PLACEHOLDER)
        self.assertEqual(self.Home._colleague_photo_url(self.gone),
                         pb_me_home.PHOTO_PLACEHOLDER)
        self.assertEqual(self.Home._colleague_photo_url(self.env['hr.employee']), '')
        # a login with no employee sees nobody
        nobody, _none = _make_share(self.env, 'test_t3b_photo_nobody',
                                    'T3b Photo Nobody', employee=False)
        self.assertFalse(self.env['pb.me.home'].with_user(nobody)
                         ._pbme_photo_allowed(self.same))

    def test_t3b_extra_cards_hook(self):
        """No card by default here unless a module adds one; a card without a
        template is dropped; a raising override loses the extras, not the
        home (logged)."""
        Home = type(self.env['pb.me.home'])
        with patch.object(Home, '_pbme_extra_cards',
                          lambda this, emp: [{'key': 'probe', 'template': 'x.y', 'data': {}},
                                             {'key': 'bad'}]):
            cards = self.Home._pbme_extra_cards_safe(self.share_emp)
        self.assertEqual([c['key'] for c in cards], ['probe'])

        def boom(this, emp):
            raise ValueError('T3b probe: a broken card')
        with patch.object(Home, '_pbme_extra_cards', boom), \
                self.assertLogs('odoo.addons.pb_me_portal.models.pb_me_home',
                                level='WARNING'):
            self.assertEqual(self.Home._pbme_extra_cards_safe(self.share_emp), [])
            data = self.Home.get_home_data(self.share_emp)
        self.assertTrue(data, 'the home still builds')
        self.assertEqual(data['extra_cards'], [])

    def test_t3b_tiles_registered(self):
        clock = self.Home.tile_meta('/my/work/clock')
        self.assertEqual((clock['group'], clock['icon']), ('time', 'timer'))
        self.assertEqual(clock['title'], 'Clock in / out')
        notices = self.Home.tile_meta('/my/notices')
        self.assertEqual((notices['group'], notices['icon']), ('people', 'megaphone'))
        self.assertEqual(notices['text'], 'What the company announced')


@tagged('post_install', '-at_install')
class TestT3bPhotoRoute(HttpCase):
    """T3b.8 over HTTP, as an employee login."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t3b_photo_http', 'Quinn Photo Http', PASSWORD)
        cls.same, cls.gone, cls.far = _colleagues(cls.env, 'T3b Http')

    def _get(self, emp_id, size='avatar_128'):
        return self.url_open('/my/photo/%s/%s' % (emp_id, size), timeout=60)

    # T3b.8
    def test_t3b_8_photo_widening(self):
        self.authenticate(self.share.login, PASSWORD)
        own = self._get(self.share_emp.id)
        self.assertEqual(own.status_code, 200)
        self.assertTrue(own.headers.get('Content-Type', '').startswith('image/'))
        same = self._get(self.same.id)
        self.assertEqual(same.status_code, 200, 'a colleague of the same company')
        self.assertTrue(same.headers.get('Content-Type', '').startswith('image/'))
        self.assertEqual(self._get(self.far.id).status_code, 404, 'another company')
        self.assertEqual(self._get(self.gone.id).status_code, 404, 'archived')
        self.assertEqual(self._get(999999999).status_code, 404, 'no such person')
        self.assertEqual(self._get(self.same.id, 'image_1920').status_code, 404,
                         'only the two avatar sizes')

    def test_t3b_8b_neighbour_pages_draw_the_route(self):
        """The pages that show colleagues to an employee login (pb_onboarding's
        org chart, pb_rnr's recognition wall) draw faces through the route
        (soft: skipped where the module is absent)."""
        installed = self.env['ir.module.module']._installed()
        self.authenticate(self.share.login, PASSWORD)
        checked = []
        if 'pb_onboarding' in installed:
            page = self.url_open('/my/orgchart', timeout=60)
            self.assertEqual(page.status_code, 200)
            self.assertNotIn('/web/image/hr.employee', page.text)
            checked.append('/my/orgchart')
        if 'pb_rnr' in installed:
            page = self.url_open('/my/recognition', timeout=60)
            self.assertIn(page.status_code, (200, 303))
            self.assertNotIn('/web/image/hr.employee', page.text)
            checked.append('/my/recognition')
        _logger.info('T3b.8b | pages checked: %s', checked)
