import json
from datetime import datetime, timedelta
from odoo.tests import tagged
from odoo.exceptions import AccessError, UserError
from .common import ClockCase
from ..models.clock_connector import digest


@tagged('post_install', '-at_install', 'pb_clock_connector')
class TestDesktopConnector(ClockCase):
    def setUp(self):
        super().setUp()
        self.C = self.env['pb.clock.connector'].sudo()
        self.E = self.env['pb.clock.connector.event'].sudo()
        self.connector = self.C.create({'name':'Test PC','company_id':self.company.id,
            'source_group':'Test group','tz':'Asia/Ho_Chi_Minh','history_from':'2026-09-01'})
        self.row = {'UserFullCode':'00885','UserEnrollNumber':'885','TimeDate':'2026-11-01 00:00:00',
            'TimeStr':'2026-11-01 07:30:00','TimeType':'I','TimeSource':'FP','MachineNo':'1','CardNo':''}

    def receive(self, rows, connector=None):
        return (connector or self.connector)._receive({'rows':rows,'status':{'version':'test'}})

    def test_pairing_single_use_rotation_and_scope(self):
        action=self.connector.action_pair()
        code=self.env['pb.clock.connector.pair'].browse(action['res_id']).code
        first=self.C._pair(code,'test-installation-123')
        self.assertTrue(first['token'])
        self.assertFalse(self.C._pair(code,'test-installation-456'))
        self.assertEqual(self.C._authenticate(first['token']),self.connector)
        self.assertEqual(self.connector.company_id,self.company)
        self.connector.action_revoke()
        self.assertFalse(self.C._authenticate(first['token']))

    def test_invitation_expiry_rotation_and_revoke_preserve_installation(self):
        first = self.connector._new_invitation()
        self.assertEqual(self.C._invited(first), self.connector)
        second = self.connector._new_invitation()
        self.assertFalse(self.C._invited(first))
        code = self.connector._setup_code(invited=True)
        paired = self.C._pair(code, 'invited-windows-123')
        with self.assertRaises(UserError):
            self.connector._setup_code(invited=True)
        self.connector._revoke_invitation()
        self.assertFalse(self.C._invited(second))
        self.assertEqual(self.C._authenticate(paired['token']), self.connector)
        third = self.connector._new_invitation()
        self.connector.invitation_until = datetime.utcnow() - timedelta(seconds=1)
        self.assertFalse(self.C._invited(third))
        self.assertEqual(self.C._authenticate(paired['token']), self.connector)

    def test_invitation_revoke_invalidates_unspent_code(self):
        self.connector._new_invitation()
        code = self.connector._setup_code(invited=True)
        self.connector._revoke_invitation()
        self.assertFalse(self.C._pair(code, 'revoked-invited-pc'))
        self.connector._new_invitation()
        code = self.connector._setup_code(invited=True)
        self.connector._new_invitation()
        self.assertFalse(self.C._pair(code, 'replaced-invited-pc'))

    def test_setup_status_excludes_source_data_and_credentials(self):
        self.connector._new_invitation()
        self.receive([self.row])
        self.connector.last_error = 'PRIVATE path and employee detail'
        status = self.connector._setup_status()
        self.assertTrue(status['needs_attention'])
        self.assertNotIn('PRIVATE', json.dumps(status))
        self.assertNotIn('885', json.dumps(status))
        self.assertEqual(set(status), {'name', 'company', 'timezone', 'history_from', 'interval_minutes',
            'state', 'last_contact', 'last_read', 'pending', 'needs_attention', 'invitation_until'})

    def test_invitation_manager_and_company_access(self):
        user = self.env['res.users'].create({'name': 'Scoped connector manager', 'login': 'scoped-connector-manager',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('hr_attendance.group_hr_attendance_manager').id])]})
        token = self.connector.with_user(user)._new_invitation()
        self.assertEqual(self.C._invited(token), self.connector)
        self.connector.with_user(user)._revoke_invitation()
        outside = self.env['res.company'].create({'name': 'Invitation outside scope'})
        other = self.C.create({'name': 'Other setup', 'company_id': outside.id, 'source_group': 'Other',
                               'tz': 'UTC', 'history_from': '2026-09-01'})
        with self.assertRaises(AccessError):
            other.with_user(user)._new_invitation()
        with self.assertRaises(AccessError):
            self.connector.with_user(user).write({'invitation_until': datetime.utcnow()})

    def test_expired_pairing(self):
        self.connector.write({'pairing_hash':digest('testcode'), 'pairing_until':datetime.utcnow()-timedelta(minutes=1)})
        self.assertFalse(self.C._pair('testcode','test-installation'))

    def test_bad_business_row_acknowledged_and_next_batch_continues(self):
        result=self.receive([self.row, {'TimeStr':'bad'}, 'invalid source row'])
        self.assertEqual(result['acknowledged'],3)
        self.E._cron_process()
        self.assertEqual(self.connector.event_ids.filtered(lambda e:e.state=='review').__len__(),2)
        result=self.receive([dict(self.row,TimeStr='2026-11-02 07:30:00',TimeDate='2026-11-02 00:00:00')])
        self.assertEqual(result['stored'],1)
        self.E._cron_process()
        self.assertEqual(len(self.connector.event_ids.filtered(lambda e:e.state=='ready')),2)
        self.assertFalse(self.connector.event_ids.mapped('punch_id'))

    def test_retry_and_exact_duplicates(self):
        self.assertEqual(self.receive([self.row,self.row])['stored'],1)
        self.assertEqual(self.receive([self.row])['duplicates'],1)
        self.assertEqual(len(self.connector.event_ids),1)

    def test_source_local_display_does_not_shift_for_viewer(self):
        self.receive([dict(self.row, TimeStr='2026-11-01 23:59:59')])
        self.E._cron_process()
        event = self.connector.event_ids
        for timezone in ('Australia/Sydney', 'Asia/Ho_Chi_Minh', 'America/Los_Angeles', 'UTC'):
            viewed = event.with_context(tz=timezone)
            self.assertEqual(viewed.punch_local_display, '2026-11-01 23:59:59')
            self.assertEqual(viewed.source_timezone, 'Asia/Ho_Chi_Minh')

    def test_publication_timezone_leading_zero_and_conflict(self):
        self.connector.publish_punches=True
        self.receive([self.row]);self.E._cron_process()
        event=self.connector.event_ids
        self.assertEqual(event.state,'posted')
        self.assertEqual(event.punch_id.user_code,'885')
        self.assertEqual(event.punch_id.punch_utc,datetime(2026,11,1,0,30))
        self.assertEqual(event.punch_id.device_id.kind,'collection')
        self.assertIn('collection group',event.punch_id.device_id.name)
        self.receive([dict(self.row,TimeType='O')]);self.E._cron_process()
        self.assertEqual(self.connector.event_ids.filtered(lambda e:e.id!=event.id).state,'review')
        self.assertEqual(len(self.Punch.search([('device_id','=',event.punch_id.device_id.id)])),1)

    def test_same_group_across_pcs_not_double_counted(self):
        other=self.C.create({'name':'Standby PC','company_id':self.company.id,'source_group':'Test group',
                            'tz':'Asia/Ho_Chi_Minh','history_from':'2026-09-01','publish_punches':True})
        self.connector.publish_punches=True
        self.receive([self.row]);self.E._cron_process()
        self.receive([self.row],other);self.E._cron_process()
        self.assertEqual(other.event_ids.state,'duplicate')
        self.assertEqual(other.event_ids.punch_id,self.connector.event_ids.punch_id)

    def test_history_ignored_without_blocking_new_rows(self):
        self.receive([dict(self.row,TimeStr='2020-01-01 07:30:00',TimeDate='2020-01-01 00:00:00'),self.row]);self.E._cron_process()
        self.assertEqual(set(self.connector.event_ids.mapped('state')),{'historical','ready'})

    def test_received_interpretation_cannot_silently_change(self):
        self.receive([self.row])
        with self.assertRaises(UserError):self.connector.write({'source_group':'another group'})

    def test_cross_company_records_hidden(self):
        user=self.env['res.users'].create({'name':'Connector officer','login':'connector-test-officer',
            'company_id':self.company.id,'company_ids':[(6,0,[self.company.id])],
            'group_ids':[(6,0,[self.env.ref('hr_attendance.group_hr_attendance_officer').id])]})
        outside=self.env['res.company'].create({'name':'Unrelated connector company'})
        other=self.C.create({'name':'Other PC','company_id':outside.id,'source_group':'Other',
            'tz':'UTC','history_from':'2026-09-01'})
        visible=self.C.with_user(user).with_context(allowed_company_ids=[self.company.id]).search([])
        self.assertNotIn(other,visible)
        with self.assertRaises(AccessError):self.connector.with_user(user).action_pair()

from odoo.tests import HttpCase

@tagged('post_install', '-at_install', 'pb_clock_connector')
class TestConnectorHttp(HttpCase):
    def setUp(self):
        super().setUp()
        self.authenticate(None,None)
        self.connector=self.env['pb.clock.connector'].sudo().create({'name':'HTTP Test PC',
            'source_group':'HTTP collection','tz':'UTC','history_from':'2026-09-01'})
        a=self.connector.action_pair()
        self.code=self.env['pb.clock.connector.pair'].browse(a['res_id']).code

    def call(self, operation, data, token=None, secure=True):
        headers={'Content-Type':'application/json','X-Forwarded-Proto':'https' if secure else 'http',
                 'X-Forwarded-Host':self.base_url().split('://',1)[1]}
        if token:headers['Authorization']='Bearer '+token
        return self.url_open('/clock-bridge/v1/'+operation,data=json.dumps(data),headers=headers,method='POST',allow_redirects=False)

    def test_http_pair_ack_retry_bad_record_revocation(self):
        r=self.call('pair',{'code':self.code,'installation_id':'http-test-installation'})
        self.assertEqual(r.status_code,200,r.text)
        token=r.json()['token']
        r=self.call('sync',{'rows':[{'TimeStr':'invalid'}]},token)
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['acknowledged'],1)
        r=self.call('sync',{'rows':[{'TimeStr':'invalid'}]},token)
        self.assertEqual(r.json()['duplicates'],1)
        r=self.call('sync',{'rows':[]},'wrong-token');self.assertEqual(r.status_code,401)
        self.connector.action_revoke()
        r=self.call('sync',{'rows':[]},token);self.assertEqual(r.status_code,401)

    def test_http_refuses_plaintext_and_bad_envelope(self):
        r=self.call('pair',{'code':self.code,'installation_id':'http-test-installation'},secure=False)
        self.assertEqual(r.status_code,400)
        r=self.call('pair',{'code':self.code,'installation_id':'http-test-installation'})
        self.assertEqual(r.status_code,200,r.text)
        r=self.call('sync',{'rows':[{}]*501},r.json()['token'])
        self.assertEqual(r.status_code,400)

    def setup_call(self, operation, token='', secure=True):
        return self.url_open('/clock-bridge/setup/' + operation, data='', method='POST',
            headers={'Authorization': 'Bearer ' + token, 'X-Forwarded-Proto': 'https' if secure else 'http',
                     'X-Forwarded-Host': self.base_url().split('://', 1)[1]}, allow_redirects=False)

    def test_invitation_http_shell_and_capability_boundary(self):
        token = self.connector._new_invitation()
        page = self.url_open('/clock-bridge/setup')
        self.assertEqual(page.status_code, 200, page.text[:500])
        self.assertNotIn('HTTP Test PC', page.text)
        self.assertIn('frame-ancestors', page.headers['Content-Security-Policy'])
        self.assertEqual(page.headers['Referrer-Policy'], 'no-referrer')
        self.assertEqual(self.setup_call('status').status_code, 401)
        self.assertEqual(self.setup_call('status', token, secure=False).status_code, 400)
        status = self.setup_call('status', token)
        self.assertEqual(status.status_code, 200, status.text)
        self.assertEqual(status.json()['name'], 'HTTP Test PC')
        for action in ('invite', 'revoke-invite', 'records', 'publish'):
            self.assertEqual(self.setup_call(action, token).status_code, 403)
        code = self.setup_call('code', token).json()['code']
        self.connector._revoke_invitation()
        self.assertEqual(self.setup_call('status', token).status_code, 401)
        self.assertEqual(self.call('pair', {'code': code, 'installation_id': 'revoked-invitation-test'}).status_code, 401)

    def test_invitation_http_pair_and_expiry_do_not_stop_sync(self):
        token = self.connector._new_invitation()
        code = self.setup_call('code', token).json()['code']
        pair = self.call('pair', {'code': code, 'installation_id': 'invitation-http-test'})
        self.assertEqual(pair.status_code, 200, pair.text)
        self.assertEqual(self.setup_call('code', token).status_code, 409)
        self.connector.invitation_until = datetime.utcnow() - timedelta(seconds=1)
        self.assertEqual(self.setup_call('status', token).status_code, 401)
        self.assertEqual(self.call('sync', {'rows': []}, pair.json()['token']).status_code, 200)

    def test_management_requires_login_and_csrf(self):
        page = self.url_open('/clock-bridge/manage/%s' % self.connector.id, allow_redirects=False)
        self.assertIn(page.status_code, (302, 303))
        manager = self.env['res.users'].create({'name': 'HTTP setup manager', 'login': 'http-setup-manager',
            'password': 'test-only-setup-password', 'company_id': self.connector.company_id.id,
            'company_ids': [(6, 0, [self.connector.company_id.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr_attendance.group_hr_attendance_manager').id])]})
        self.authenticate(manager.login, 'test-only-setup-password')
        r = self.url_open('/clock-bridge/manage/%s/invite' % self.connector.id, data='', method='POST', allow_redirects=False)
        self.assertEqual(r.status_code, 400)
        page = self.url_open('/clock-bridge/manage/%s' % self.connector.id)
        self.assertEqual(page.status_code, 200, page.text[:500])
        from lxml import html
        csrf = html.fromstring(page.content).xpath('//body/@data-csrf')[0]
        headers = {'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': self.base_url().split('://', 1)[1]}
        r = self.url_open('/clock-bridge/manage/%s/invite' % self.connector.id,
                         data={'csrf_token': csrf}, headers=headers, method='POST')
        self.assertEqual(r.status_code, 200, r.text)
        token = r.json()['invitation']
        self.assertEqual(self.setup_call('status', token).status_code, 200)
        r = self.url_open('/clock-bridge/manage/%s/revoke-invite' % self.connector.id,
                         data={'csrf_token': csrf}, headers=headers, method='POST')
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.setup_call('status', token).status_code, 401)
