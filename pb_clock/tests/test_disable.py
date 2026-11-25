"""WFSETUP P9 — a reversible "Disable" / "Enable" for a PC connection.

1. a manager disables and enables; an officer is refused; the pairing (token)
   is kept; one chatter line each; the "Send accepted records to attendance"
   tick is untouched;
2. the PC's API: disabled -> 423 with its own sentence, revoked -> still the
   401 revoke answer, connected -> accepted;
3. catch-up proof with the real Windows program (`tools/attendance_connector/
   connector.py`, its `sync` and `post`, with only the MDB read and the HTTPS
   transport replaced): records punched while disabled are refused, stay
   queued on the PC, and arrive after Enable — no gap, no duplicates;
4. the clock watch job raises nothing for a disabled connection.
"""
import contextlib
import io
import importlib.util
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from unittest.mock import patch
import urllib.error
import urllib.parse
import urllib.request

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged

from .common import ClockCase

DISABLED_TEXT = 'This connection is disabled in Payobook. Ask your Payobook administrator to enable it.'
CONNECTOR_PY = Path(__file__).resolve().parents[2] / 'tools' / 'attendance_connector' / 'connector.py'


def mitaco(code, stamp):
    return {'UserFullCode': '00' + code, 'UserEnrollNumber': code, 'TimeDate': stamp[:10] + ' 00:00:00',
            'TimeStr': stamp, 'TimeType': 'I', 'TimeSource': 'FP', 'MachineNo': '1', 'CardNo': ''}


@tagged('post_install', '-at_install', 'pb_clock_connector', 'wfsetup_p9')
class TestDisableEnable(ClockCase):
    def setUp(self):
        super().setUp()
        self.C = self.env['pb.clock.connector'].sudo()
        self.connector = self.C.create({'name': 'P9 PC', 'company_id': self.company.id,
            'source_group': 'P9 group', 'tz': 'Asia/Ho_Chi_Minh', 'history_from': '2026-09-01'})
        action = self.connector.action_pair()
        code = self.env['pb.clock.connector.pair'].browse(action['res_id']).code
        self.token = self.C._pair(code, 'p9-installation-0001')['token']
        Users = self.env['res.users'].sudo().with_context(no_reset_password=True)
        base = dict(company_id=self.company.id, company_ids=[(6, 0, [self.company.id])])
        self.manager = Users.create(dict(base, name='P9 manager', login='p9-manager', group_ids=[(6, 0, [
            self.env.ref('base.group_user').id, self.env.ref('hr_attendance.group_hr_attendance_manager').id])]))
        self.officer = Users.create(dict(base, name='P9 officer', login='p9-officer', group_ids=[(6, 0, [
            self.env.ref('base.group_user').id, self.env.ref('hr_attendance.group_hr_attendance_officer').id])]))

    def bodies(self):
        return [m.body for m in self.connector.message_ids]

    def test_01_manager_disables_and_enables(self):
        token_hash = self.connector.token_hash
        mine = self.connector.with_user(self.manager)
        mine.action_disable()
        self.assertEqual(self.connector.state, 'disabled')
        self.assertEqual(self.connector.token_hash, token_hash, 'the pairing is kept')
        self.assertEqual(self.connector.installation_id, 'p9-installation-0001')
        self.assertFalse(self.connector.publish_punches, 'the attendance tick is untouched')
        self.assertTrue(any('Disabled. This PC stops sending clock-ins' in b for b in self.bodies()))
        # recognised, still: the API answers 423 (test 2), not "re-pair"
        self.assertEqual(self.C._authenticate(self.token), self.connector)
        # pressing again does nothing more; a guided-setup code is refused (paired)
        n = len(self.connector.message_ids)
        mine.action_disable()
        self.assertEqual(len(self.connector.message_ids), n)
        with self.assertRaises(UserError):
            self.connector._setup_code()
        mine.action_enable()
        self.assertEqual(self.connector.state, 'connected')
        self.assertEqual(self.connector.token_hash, token_hash)
        self.assertTrue(any('Enabled. On its next sync' in b for b in self.bodies()))

    def test_02_tick_survives_both_ways(self):
        self.connector.publish_punches = True
        self.connector.with_user(self.manager).action_disable()
        self.assertTrue(self.connector.publish_punches)
        self.connector.with_user(self.manager).action_enable()
        self.assertTrue(self.connector.publish_punches)

    def test_03_officer_refused(self):
        with self.assertRaises(AccessError):
            self.connector.with_user(self.officer).action_disable()
        self.assertEqual(self.connector.state, 'connected')
        self.connector.with_user(self.manager).action_disable()
        with self.assertRaises(AccessError):
            self.connector.with_user(self.officer).action_enable()
        self.assertEqual(self.connector.state, 'disabled')
        # nor can anyone write the state directly
        with self.assertRaises(AccessError):
            self.connector.with_user(self.manager).write({'state': 'connected'})

    def test_04_only_from_the_right_state(self):
        fresh = self.C.create({'name': 'P9 new PC', 'company_id': self.company.id,
            'source_group': 'P9 group', 'tz': 'Asia/Ho_Chi_Minh', 'history_from': '2026-09-01'})
        with self.assertRaises(UserError):
            fresh.with_user(self.manager).action_disable()
        with self.assertRaises(UserError):
            fresh.with_user(self.manager).action_enable()
        # a disabled PC can still be revoked; the revoked one cannot be enabled
        self.connector.with_user(self.manager).action_disable()
        self.connector.with_user(self.manager).action_revoke()
        self.assertEqual(self.connector.state, 'revoked')
        self.assertFalse(self.C._authenticate(self.token))
        with self.assertRaises(UserError):
            self.connector.with_user(self.manager).action_enable()

    def test_05_watch_job_quiet_for_a_disabled_pc(self):
        self.connector._receive({'rows': [mitaco('885', '2026-11-02 07:30:00')], 'status': {'version': 'test'}})
        self.connector.publish_punches = True
        self.env['pb.clock.connector.event']._cron_process()
        self.assertTrue(self.connector.device_id, 'the PC has its collection device')
        self.connector.with_user(self.manager).action_disable()
        Alert = self.env['pb.clock.alert'].sudo()
        for days in (1, 3, 10):
            Alert._watch(now=datetime(2026, 11, 20, 3, 0) + timedelta(days=days),
                         company_ids=[self.company.id], mail=False)
        self.assertFalse(Alert.search([('company_id', '=', self.company.id),
                                       ('device_id', '=', self.connector.device_id.id)]))
        self.assertFalse(Alert.search([('company_id', '=', self.company.id),
                                       ('kind', 'in', ('silent', 'no_punches'))]).filtered(
            lambda a: a.device_id == self.connector.device_id))


class _LocalOpener:
    """Stands in for the program's HTTPS opener: the same request (body,
    bearer token, content type), sent to the test server with the proxy
    headers the live nginx adds. A refused call is raised exactly as the
    real opener raises it (urllib HTTPError), so the program's own `post`
    error path runs."""
    def __init__(self, case):
        self.case = case

    def open(self, req, timeout=None):
        path = urllib.parse.urlsplit(req.full_url).path
        headers = {k: v for k, v in req.header_items()}
        headers.update({'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': self.case.base_url().split('://', 1)[1]})
        res = self.case.url_open(path, data=req.data, headers=headers, method='POST', allow_redirects=False)
        if res.status_code >= 400:
            raise urllib.error.HTTPError(req.full_url, res.status_code, res.text[:200], {}, io.BytesIO(res.content))
        return contextlib.closing(io.BytesIO(res.content))


@tagged('post_install', '-at_install', 'pb_clock_connector', 'wfsetup_p9')
class TestDisableHttp(HttpCase):
    def setUp(self):
        super().setUp()
        self.authenticate(None, None)
        self.connector = self.env['pb.clock.connector'].sudo().create({'name': 'P9 HTTP PC',
            'source_group': 'P9 HTTP group', 'tz': 'UTC', 'history_from': '2026-09-01'})
        a = self.connector.action_pair()
        self.code = self.env['pb.clock.connector.pair'].browse(a['res_id']).code

    def call(self, operation, data, token=None):
        headers = {'Content-Type': 'application/json', 'X-Forwarded-Proto': 'https',
                   'X-Forwarded-Host': self.base_url().split('://', 1)[1]}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        return self.url_open('/clock-bridge/v1/' + operation, data=json.dumps(data), headers=headers,
                             method='POST', allow_redirects=False)

    def pair(self):
        r = self.call('pair', {'code': self.code, 'installation_id': 'p9-http-installation'})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_01_disabled_423_revoked_401_connected_200(self):
        token = self.pair()['token']
        row = mitaco('885', '2026-11-02 07:30:00')
        r = self.call('sync', {'rows': [row]}, token)
        self.assertEqual((r.status_code, r.json()['stored']), (200, 1), r.text)
        self.connector.action_disable()
        r = self.call('sync', {'rows': [mitaco('885', '2026-11-02 17:30:00')]}, token)
        self.assertEqual(r.status_code, 423, r.text)
        self.assertEqual(r.json()['error'], DISABLED_TEXT)
        self.connector.invalidate_recordset()
        self.assertEqual(len(self.connector.event_ids), 1, 'nothing taken in while disabled')
        r = self.call('sync', {'rows': []}, 'wrong-token')
        self.assertEqual(r.status_code, 401, 'a wrong token is still refused as before')
        self.connector.action_enable()
        r = self.call('sync', {'rows': [mitaco('885', '2026-11-02 17:30:00')]}, token)
        self.assertEqual((r.status_code, r.json()['stored']), (200, 1), r.text)
        self.connector.action_revoke()
        r = self.call('sync', {'rows': []}, token)
        self.assertEqual(r.status_code, 401)
        self.assertNotIn('disabled', r.text)

    def test_02_catch_up_with_the_windows_program(self):
        """The real `connector.sync`/`post`: a refused upload leaves the rows
        queued; Enable -> the same rows arrive once; repeats add nothing."""
        if not CONNECTOR_PY.is_file():
            self.skipTest('the Windows program source is not beside this module (server copy)')
        old_env = os.environ.get('PAYOBOOK_LOCAL_TEST')
        os.environ['PAYOBOOK_LOCAL_TEST'] = '1'
        self.addCleanup(lambda: os.environ.pop('PAYOBOOK_LOCAL_TEST') if old_env is None
                        else os.environ.__setitem__('PAYOBOOK_LOCAL_TEST', old_env))
        spec = importlib.util.spec_from_file_location('p9_attendance_connector', CONNECTOR_PY)
        program = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(program)
        paired = self.pair()
        home = Path(tempfile.mkdtemp(prefix='p9-connector-'))
        self.addCleanup(lambda: __import__('shutil').rmtree(home, ignore_errors=True))
        config = {'server': 'https://payobook.invalid', 'database': 'unused', 'installation_id': 'p9-http-installation',
                  'token': paired['token'], 'remote': paired['config']}
        mdb = [mitaco('885', '2026-11-02 07:30:00'), mitaco('227', '2026-11-02 07:41:00')]

        def run():
            with patch.object(program, 'extract', return_value=(list(mdb), {'read_ok': True, 'source_rows': len(mdb),
                                                                              'latest_punch': mdb[-1]['TimeStr']})), \
                    patch.object(program.urllib.request, 'build_opener', lambda *a: _LocalOpener(self)):
                return program.sync(home, config)

        def queued():
            q = program.Queue(program.queue_home(home, config))
            try:
                return q.count()
            finally:
                q.close()

        def hashes():
            self.connector.invalidate_recordset()
            return sorted(self.connector.event_ids.mapped('row_hash'))

        self.assertEqual(run()['sent'], 2)
        self.assertEqual(len(hashes()), 2)
        # disabled: two more punches reach the MDB; the upload is refused
        self.connector.action_disable()
        mdb += [mitaco('885', '2026-11-02 17:30:00'), mitaco('227', '2026-11-02 17:02:00')]
        with self.assertRaises(RuntimeError) as refused:
            run()
        self.assertIn('HTTP 423', str(refused.exception))
        self.assertEqual(queued(), 2, 'the refused rows stay queued on the PC')
        self.assertEqual(len(hashes()), 2, 'nothing was taken in while disabled')
        with self.assertRaises(RuntimeError):
            run()                                       # a second refused run loses nothing either
        self.assertEqual(queued(), 2)
        # enabled: the next sync catches up exactly the missing rows
        self.connector.action_enable()
        self.assertEqual(run()['sent'], 2)
        self.assertEqual(queued(), 0)
        received = hashes()
        self.assertEqual(len(received), 4)
        expected = sorted(program.hashlib.sha256(program.canonical(r).encode()).hexdigest() for r in mdb)
        self.assertEqual(received, expected, 'exactly the four MDB rows, each once')
        # repeats: the same MDB again, and even a full re-send, add nothing
        self.assertEqual(run()['sent'], 0)
        q = program.Queue(program.queue_home(home, config)); q.replay(); q.close()
        self.assertEqual(run()['sent'], 4)
        self.assertEqual(hashes(), expected, 'a full re-send is all duplicates')
