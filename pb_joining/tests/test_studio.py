import base64
import hashlib
import io
from datetime import date
from unittest.mock import patch

from PIL import Image, ImageDraw
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.pdf import PdfFileReader, PdfFileWriter
from odoo.addons.pb_new_hire.tests.test_docs import DocsCommon
from odoo.addons.pb_hiring.tests.test_joining_p6 import JoiningCase
from .test_phone import TAG, catalogue_example


def pdf():
    buf = io.BytesIO()
    writer = PdfFileWriter()
    writer.addBlankPage(360, 480)
    writer.write(buf)
    return buf.getvalue()


def data(raw):
    return base64.b64encode(raw).decode()


def ink(blank=False):
    im = Image.new('RGB', (200, 80), 'white')
    if not blank:
        ImageDraw.Draw(im).line([(10, 15), (25, 55), (55, 12), (85, 59), (160, 19)], fill='black', width=3)
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return 'data:image/png;base64,' + data(buf.getvalue())


@tagged(*TAG)
class TestLanding(DocsCommon):
    def ready(self, country='SG', name='DEMO Checked Joiner'):
        d = self.docs_draft(name=name, payroll_country=country)
        j = (
            self.env['pb.joining']
            .sudo()
            .with_company(self.company)
            .create(
                {
                    'name': name,
                    'first_day': d['date_start'],
                    'job_title': 'DEMO Accountant',
                    'payroll_country': country,
                    'email': 'joining.demo@example.invalid',
                }
            )
        )
        j.write({'state': 'to_check', 'submitted_at': fields.Datetime.now(), 'day_opened': True})
        j.item_ids.write({'state': 'later'})
        return j, d

    def accepted(self, j, key, values=None, attachment=False, permanent=False):
        r = j.item_ids.filtered(lambda r: r.key == key)
        r.write(
            {
                'state': 'accepted',
                'values': values or {},
                'decided_by_id': self.maker.id,
                'decided_on': fields.Datetime.now(),
                'issue_date': date(2024, 1, 1),
                'expiry_date': False if permanent else date(2036, 1, 1),
                'no_expiry': permanent,
            }
        )
        if attachment:
            att = (
                self.env['ir.attachment']
                .sudo()
                .create({'name': 'DEMO card.pdf', 'raw': pdf(), 'res_model': r._name, 'res_id': r.id})
            )
            r.attachment_ids = att
        return r

    def send_joining(self, j, d):
        draft = self.studio().joining_draft(j.id)['draft']
        return self.studio().send(dict(d, joining_id=j.id, items=draft['items']))

    def test_t46_invite_draft(self):
        j, d = self.ready()
        info = self.studio().joining_draft(j.id)['draft']
        self.assertFalse(info['department_id'])
        self.assertFalse(info.get('wage'))
        self.assertEqual(info['name'], j.name)
        self.assertEqual(info['items']['bank'], 'ask')
        self.assertEqual(self.studio().send(info)['step'], 'role')

    def test_t47_same_as_have_each_country(self):
        self.fast_lane()
        for country in ('VN', 'ID', 'IN', 'SG'):
            j, d = self.ready(country, 'DEMO Joining ' + country)
            if country == 'VN':
                d.update(department_id=self.ops.id, job_id=self.agronomist.id)
            if country in ('ID', 'IN'):
                scheme = self.env['hr.formula.config'].create(
                    {
                        'name': 'DEMO Joining ' + country,
                        'code': 'DEMOJOIN' + country,
                        'country_code': country,
                        'state': 'active',
                        'company_id': self.company.id,
                    }
                )
                d.update(scheme_id=scheme.id)
            values, choices, files = {}, {}, []
            for spec in j._catalogue():
                key = spec['key']
                if key == 'bank':
                    continue  # T48 checks the separate bank approval path.
                sample = catalogue_example(spec, country, j.name)
                self.accepted(j, key, sample, attachment=bool(spec['upload']))
                choices[key] = 'have'
                values.update(sample)
                if spec['upload']:
                    files.append(
                        {
                            'key': key,
                            'name': 'DEMO card.pdf',
                            'mime': 'application/pdf',
                            'data': data(pdf()),
                            'expiry_date': '2036-01-01',
                            'issue_date': '2024-01-01',
                        }
                    )
            joined = self.send_joining(j, d)
            self.assertTrue(joined.get('applied'), joined.get('message'))
            direct = dict(d, name='DEMO Typed ' + country, items=choices, have=values)
            direct.pop('work_email', None)
            other = self.studio().send(direct, files)
            self.assertTrue(other.get('applied'), other.get('message'))
            employees = self.env['hr.employee'].sudo()
            staged, typed = employees.browse(joined['employee_id']), employees.browse(other['employee_id'])
            for key in values:
                self.assertTrue(staged[key], (country, key))
                self.assertEqual(staged[key], typed[key], (country, key))

    def test_t48_second_person_bank(self):
        from odoo.addons.pb_records.tests.bank_second import ensure_second_person

        ensure_second_person(self.env, self.company)
        j, d = self.ready()
        self.accepted(j, 'bank', {'bank_name': 'DBS', 'account_number': '012345678901', 'bank_format': 'SG'})
        out = self.send_joining(j, d)
        self.assertTrue(out.get('pending'), out.get('message'))
        self.approve(out)
        bank = self.env['pb.bank.change.request'].sudo().search([('employee_id', '=', j.employee_id.id)])
        self.assertEqual(bank.proposed_by_id, self.maker)
        self.assertIn(bank.state, ('hr_review', 'finance_review'))

    def test_t49_permanent_and_dated_cards(self):
        self.fast_lane()
        for perm in (True, False):
            j, d = self.ready(name='DEMO Permanent ' + str(perm))
            self.accepted(j, 'id_number', {'identification_id': 'S1234567D'}, attachment=True, permanent=perm)
            result = self.send_joining(j, d)
            self.assertTrue(result.get('applied'), result.get('message'))
            expected = self.env.ref('pb_joining.cat_permanent_id') if perm else self.cat_id
            doc = (
                self.env['pb.employee.document']
                .sudo()
                .search([('category_id', '=', expected.id), ('employee_id', '=', j.employee_id.id)])
            )
            self.assertEqual(len(doc), 1)
            self.assertEqual(doc.issue_date, date(2024, 1, 1))
            self.assertEqual(doc.expiry_date, False if perm else date(2036, 1, 1))
            self.assertEqual(doc.attachment_id.raw, pdf())

    def test_t51_close_once(self):
        self.fast_lane()
        j, d = self.ready()
        result = self.send_joining(j, d)
        self.assertTrue(result.get('applied'), result.get('message'))
        self.assertEqual(j.state, 'added')
        self.assertEqual(j.employee_id.id, result['employee_id'])
        self.assertTrue(j.added_at)
        with self.assertRaises(UserError):
            self.send_joining(j, d)

    def test_t51_filing_failure_leaves_the_hire_retryable(self):
        self.fast_lane()
        joining, draft = self.ready()
        self.accepted(joining, 'id_number', {'identification_id': 'S1234567D'}, attachment=True)
        legs = type(self.env['pb.new.hire.legs'])
        with patch.object(legs, '_vault_copy', side_effect=UserError('DEMO temporary filing failure')):
            result = self.send_joining(joining, draft)
        self.assertFalse(result.get('applied'))
        self.assertFalse(joining.employee_id)
        request = joining.proposal_id.approval_request_id
        self.assertEqual(request.state, 'approved')
        self.assertTrue(request.block_reason)
        self.assertFalse(self.env['hr.employee'].sudo().search_count([('name', '=', draft['name'])]))
        self.studio().env['biz.approval.engine'].retry_apply(request.id)
        self.assertEqual(request.state, 'applied')
        self.assertTrue(joining.employee_id)

    def test_t52_pending(self):
        j, d = self.ready()
        answer = self.send_joining(j, d)
        self.assertTrue(answer.get('pending'), answer.get('message'))
        self.assertFalse(j.employee_id)
        self.assertEqual((j.proposal_id.id, j.state), (answer['proposal_id'], 'to_check'))
        self.approve(answer)
        self.assertEqual(j.state, 'added')

    def test_t53_withdraw_and_reject(self):
        j, d = self.ready()
        a = self.send_joining(j, d)
        self.assertTrue(self.studio().withdraw(a['proposal_id'], 'DEMO correction')['ok'])
        self.assertFalse(j.proposal_id)
        self.assertTrue(j._can_add())
        b = self.send_joining(j, d)
        self.approve(b, action='reject')
        self.assertFalse(j.proposal_id)
        self.assertTrue(j._can_add())

    def test_t54_only_accepted_values(self):
        j, d = self.ready()
        self.accepted(j, 'personal', {'private_city': 'DEMO accepted city'})
        out = self.studio().send(
            dict(
                d, joining_id=j.id, items={'personal': 'joining'}, have={'private_city': 'DEMO browser city'}
            )
        )
        self.assertTrue(out.get('pending'), out.get('message'))
        self.assertEqual(
            self.proposal(out).payload()['values']['pb_nh_details']['private_city'], 'DEMO accepted city'
        )

    def signable(self):
        b = self.studio().env['pb.joining.board']
        b.papers_save(
            [
                {
                    'name': 'DEMO First-day policy',
                    'on': True,
                    'country': 'SG',
                    'data': data(pdf()),
                    'file': 'DEMO original.pdf',
                }
            ]
        )
        j, d = self.ready()
        j.write({'state': 'filling', 'submitted_at': False})
        return j, d, j.sign_ids[0]

    def test_t57_require_open_agree_ink_name(self):
        j, d, s = self.signable()
        with self.assertRaises(UserError):
            s._sign(ink(), 'DEMO Signer', '1', '127.0.0.1', 'DEMO')
        s._record_open()
        for png, name, tick in [
            (ink(), 'DEMO', ''),
            (ink(), '', '1'),
            (ink(True), 'DEMO', '1'),
            ('wrong', 'DEMO', '1'),
        ]:
            with self.assertRaises(UserError):
                s._sign(png, name, tick, '127.0.0.1', 'DEMO')
        self.assertFalse(s.signed_on)

    def test_t50_t58_t59_t60_verified_signed_copy(self):
        j, d, s = self.signable()
        s._record_open()
        s._sign(ink(), j.name, '1', '127.0.0.1', 'DEMO Chrome')
        self.assertEqual(s.paper_sha256, hashlib.sha256(s.original_id.raw).hexdigest())
        self.assertEqual(PdfFileReader(io.BytesIO(s.signed_attachment_id.raw)).getNumPages(), 2)
        with self.assertRaises(UserError):
            s._sign(ink(), j.name, '1', '', '')
        j.write({'state': 'to_check', 'submitted_at': fields.Datetime.now()})
        self.studio().env['pb.joining.board'].return_paper(j.id, s.id, 'Please sign again.')
        self.assertFalse(s.signed_on or s.signed_attachment_id)
        s._record_open()
        s._sign(ink(), j.name, '1', '127.0.0.1', 'DEMO Chrome')
        j.write({'state': 'to_check', 'submitted_at': fields.Datetime.now()})
        self.fast_lane()
        out = self.send_joining(j, d)
        self.assertTrue(out.get('applied'), out.get('message'))
        filed = (
            self.env['pb.employee.document']
            .sudo()
            .search([('employee_id', '=', j.employee_id.id), ('name', '=', s.paper_name)])
        )
        self.assertEqual(filed.attachment_id.raw, s.signed_attachment_id.raw)
        self.assertNotEqual(filed.attachment_id, s.signed_attachment_id)


@tagged(*TAG)
class TestHiringDraft(JoiningCase):
    def test_t45_t55_offer_and_tile(self):
        self.req.country_id = self.env.ref('base.vn')
        offer = self._signed()
        j = self.env['pb.joining'].search([('offer_id', '=', offer.id)])
        j.item_ids.write({'state': 'later'})
        j.write({'state': 'to_check', 'submitted_at': fields.Datetime.now()})
        item = j.item_ids.filtered(lambda r: r.key == 'personal')
        item.write(
            {
                'state': 'accepted',
                'values': {'private_city': 'DEMO City'},
                'decided_by_id': self.env.uid,
                'decided_on': fields.Datetime.now(),
            }
        )
        studio = self.env['pb.new.hire']
        origin = studio.offer_draft(offer.id)
        landed = studio.joining_draft(j.id)
        self.assertEqual(landed['draft']['offer_id'], origin['draft']['offer_id'])
        self.assertEqual(landed['draft']['items'][item.key], 'joining')
        self.assertTrue(landed['offer']['joining']['checked'])
        self.assertEqual(studio._offer_row(offer)['joining']['id'], j.id)
