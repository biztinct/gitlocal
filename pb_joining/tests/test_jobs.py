from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged
from .test_phone import TAG, person
from .test_studio import data, ink, pdf


@tagged(*TAG)
class TestDaily(TransactionCase):
    def setUp(self):
        super().setUp()
        self.now = fields.Datetime.now()
        self.j = person(self.env)

    def test_t61_cadence_cap_and_code_expiry(self):
        j = self.j
        j.first_day = j._today() + timedelta(days=25)
        j._issue(by_hr=True)
        j.code_until = self.now - timedelta(minutes=1)
        with patch.object(type(j), '_mail', return_value=False):
            for count in range(5):
                j.reminded_at = self.now - timedelta(days=2)
                j._daily_one(self.now)
                self.assertEqual(j.remind_count, min(count, 4))
                j.reminded_at = self.now - timedelta(days=3)
                j._daily_one(self.now)
                self.assertEqual(j.remind_count, min(count + 1, 4))
            self.assertEqual(len(j.activity_ids.filtered(lambda a: 'copy the message' in a.summary)), 4)
        self.assertFalse(j.code_hash or j.code_until)
        self.assertTrue(self.env.ref('pb_joining.cron_joining_daily').active)

    def test_t62_risk_and_one_nudge(self):
        inviter = new_test_user(
            self.env, login='demo.joining.reminders', groups='base.group_user,hr.group_hr_user'
        )
        self.j = person(self.env['pb.joining'].with_user(inviter).env)
        self.j.first_day = self.j._today() + timedelta(days=8)
        self.j._daily_one(self.now)
        self.assertFalse(self.j.hr_nudged_at)
        self.j.first_day -= timedelta(days=1)
        self.j._daily_one(self.now)
        self.assertTrue(self.j.hr_nudged_at)
        self.assertTrue(self.j.at_risk)
        recipients = self.j.activity_ids.user_id
        self.assertIn(self.j._contact(), recipients)
        count = len(self.j.activity_ids)
        self.j._daily_one(self.now)
        self.assertEqual(len(self.j.activity_ids), count)

    def test_t63_erase_at_thirty_days_for_both_closed_states(self):
        self.env['pb.joining.board'].papers_save(
            [{'name': 'DEMO Retention policy', 'on': True, 'data': data(pdf()), 'file': 'DEMO policy.pdf'}]
        )
        for state, timestamp in [('added', 'added_at'), ('cancelled', 'cancelled_at')]:
            j = person(self.env)
            row = j.item_ids.filtered(lambda r: r.key == 'id_number')
            spec = next(s for s in j._catalogue() if s['key'] == row.key)
            uploaded = row._upload(spec, 'DEMO Retention.pdf', pdf())
            row.write(
                {
                    'draft': {'fields': {'identification_id': 'DEMO value'}},
                    'values': {'identification_id': 'DEMO'},
                }
            )
            sign = j.sign_ids[:1]
            sign._record_open()
            sign._sign(ink(), j.name, '1', '127.0.0.1', 'DEMO Chrome')
            signed, original = sign.signed_attachment_id, sign.original_id
            canonical = signed.copy(
                {'res_model': 'res.company', 'res_id': j.company_id.id, 'name': 'DEMO separate copy'}
            )
            ink_files = (
                self.env['ir.attachment']
                .sudo()
                .search(
                    [
                        ('res_model', '=', sign._name),
                        ('res_id', '=', sign.id),
                        ('res_field', '=', 'signature'),
                    ]
                )
            )
            self.assertTrue(ink_files)
            j.write({'state': state, timestamp: self.now - timedelta(days=29)})
            j._daily_one(self.now)
            self.assertTrue(row.values and uploaded.exists())
            j[timestamp] -= timedelta(days=1)
            j._daily_one(self.now)
            self.assertTrue(j.exists() and j.name and j.erased_at)
            self.assertFalse(row.values or row.draft or row.attachment_ids or j.sign_ids)
            self.assertFalse((uploaded | signed | ink_files).exists())
            self.assertTrue(original.exists() and canonical.raw)
            j._daily_one(self.now)
            self.assertEqual(j.state, state)

    def test_t64_skip_one_failed_record(self):
        second = person(self.env)
        daily = type(self.j)._daily_one

        def fail_one(record, now):
            if record == self.j:
                record.remind_count = 99
                raise ValueError('DEMO temporary failure')
            return daily(record, now)

        with (
            patch.object(type(self.j), '_daily_one', fail_one),
            self.assertLogs('odoo.addons.pb_joining.models.jobs', level='WARNING'),
        ):
            self.env['pb.joining']._cron_daily()
        self.assertEqual(self.j.remind_count, 0)
        self.assertTrue(second.hr_nudged_at)
