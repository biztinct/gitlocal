import secrets
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged
from odoo.addons.pb_hiring.models.hiring_common import P_CANDIDATE_MAIL
from odoo.addons.pb_hiring.tests.test_joining_p6 import JoiningCase

from .test_phone import TAG, person


@tagged(*TAG)
class TestBoard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.j = person(cls.env)
        cls.board = cls.env['pb.joining.board']
        cls.recruiter = new_test_user(cls.env, login='joining.demo.recruiter', groups='base.group_user,pb_hiring.group_hiring_user')
        cls.plain = new_test_user(cls.env, login='joining.demo.colleague')
        cls.row = cls.j.item_ids.filtered(lambda r: r.key == 'id_number')
        cls.row.values = {'identification_id': 'DEMO-ID-123456'}

    def test_t23_role_payload(self):
        self.assertEqual(self.board.with_user(self.plain).get_board(), {'allowed': False})
        limited = self.board.with_user(self.recruiter).get_one(self.j.id)
        self.assertFalse(limited['can_manage'])
        self.assertTrue(all(set(r) == {'key','label','state'} for r in limited['items']))
        row = next(i for i in self.board.get_one(self.j.id)['items'] if i['key'] == 'id_number')
        self.assertEqual(row['fields'][0]['value'], '•••• 3456')
        self.assertFalse(limited['can_link'])
        with self.assertRaises(AccessError):
            self.board.with_user(self.recruiter).show_code(self.j.id)

    def test_t24_company(self):
        company = self.env['res.company'].create({'name': 'DEMO Another Joining Company'})
        other = person(self.env['pb.joining'].with_company(company).env)
        with self.assertRaises(AccessError):
            self.board.with_user(self.recruiter).get_one(other.id)

    def test_t25_counts(self):
        head = self.board.get_board()
        for key, count in head['steps'].items():
            self.assertEqual(self.board.get_page(filters={'step':[key]})['total'], count)
        self.assertEqual(head['kpis']['to_check'], head['steps']['to_check'])
        self.assertEqual(self.board.get_page(search=self.j.name)['rows'][0]['name'], self.j.name)

    def test_t26_chips(self):
        chips = self.board._card(self.j)['chips']
        self.assertEqual([c['icon'] for c in chips], ['alertTriangle','send','clock'])
        self.board.copy_link(self.j.id)
        self.assertNotIn('send', [c['icon'] for c in self.board._card(self.j)['chips']])

    def test_t27_decisions(self):
        self.j.state = 'to_check'
        self.j.item_ids.write({'state':'saved'})
        self.board.accept(self.j.id, self.row.key)
        self.assertEqual(self.row.state, 'accepted')
        self.board.undo(self.j.id, self.row.key)
        self.assertEqual(self.row.state, 'saved')
        self.assertTrue(self.board.accept_all(self.j.id)['foot']['can_add'])

    def test_t28_return(self):
        self.j.write({'state':'to_check','submitted_at':fields.Datetime.now()})
        self.j.item_ids.write({'state':'saved'})
        for note in ('', 'a'*201):
            with self.assertRaises(UserError):
                self.board.send_back(self.j.id, self.row.key, note)
        self.j.email = False
        self.board.send_back(self.j.id,self.row.key,'Please check the date.')
        self.assertEqual(self.j.state,'filling')
        self.assertEqual(self.row.return_note,'Please check the date.')
        self.assertEqual(self.j.item_ids.filtered(lambda r:r._editable()),self.row)
        self.assertTrue(self.j.activity_ids.filtered(lambda a:'fix' in a.summary))

    def test_t29_reveal(self):
        with self.assertRaises(AccessError):
            self.board.with_user(self.recruiter).reveal(self.j.id,self.row.key,'identification_id')
        self.assertEqual(self.board.reveal(self.j.id,self.row.key,'identification_id')['value'],self.row.values['identification_id'])
        notes = ''.join(self.j.message_ids.mapped('body'))
        self.assertIn('viewed a number', notes)
        self.assertNotIn(self.row.values['identification_id'],notes)

    def test_t30_limits(self):
        for name in ('copy_link','send_again','show_code','remind_now'):
            call = getattr(self.board,name)
            call(self.j.id)
            with self.assertRaises(UserError):
                call(self.j.id)

    def test_t31_invite(self):
        vals = {'name':'DEMO Invite','first_day':self.j.first_day,'job_title':'DEMO job','payroll_country':'VN'}
        with self.assertRaises(UserError):
            self.board.invite(vals)
        result = self.board.invite(dict(vals,phone='2025550160'))
        self.assertEqual(self.board.get_one(result['id'])['state'],'invited')

    def test_t32_day(self):
        result = self.board.set_day(self.j.id,{'day_time':'8 am','day_place':'Demo office'})
        self.assertEqual(result['day']['day_place'], self.j.day_place)
        self.assertEqual(self.j.day_time,'8 am')

    def test_t35_link_in_person_language(self):
        self.env['res.lang']._activate_lang('vi_VN')
        self.j.lang = 'vi_VN'
        self.env['pb.hiring.message.template']._joining_seed(self.j.company_id)
        self.env['ir.config_parameter'].set_param(P_CANDIDATE_MAIL,'1')
        with patch.object(type(self.j),'_can_email',return_value=True):
            self.j._send_link()
        msg = self.env['mail.mail'].search([('model','=','pb.joining'),('res_id','=',self.j.id)],limit=1)
        self.assertTrue(msg)
        self.assertTrue('Xin chào' in str(msg.body_html))
        self.assertTrue(self.j.token in str(msg.body_html))

    def test_t36_mail_off(self):
        self.j.email = False
        self.j._send_link()
        self.assertEqual(self.j.link_mode,'pass_on')
        self.assertTrue(self.j.activity_ids)

    def test_t37_deliver_code_now(self):
        self.env['ir.config_parameter'].set_param(P_CANDIDATE_MAIL,'1')
        sent = []
        def deliver(mail, **kw):
            sent.append(mail.subject)
            mail.state = 'sent'
        with patch.object(type(self.j),'_can_email',return_value=True), patch.object(type(self.env['mail.mail']),'send',deliver):
            self.assertEqual(self.j._issue()['status'],'issued')
        self.assertEqual(len(sent),1)
        self.assertRegex(sent[0],r'^\d{6} is your code$')
        self.assertFalse(self.env['mail.mail'].search([('subject','=',sent[0])]))

    def test_t38_missing_in_reminder(self):
        with patch.object(type(self.j),'_mail',autospec=True,return_value=False) as mail:
            msg=self.board.remind_now(self.j.id)['message']
            self.assertIn(self.j._remaining_labels()[0], msg)
            self.assertEqual(mail.call_args.args[1],'joining_reminder')

    def test_t39_hub_probes(self):
        src=(Path(get_module_path('pb_joining'))/'static/src/js/joining_board.js').read_text()
        for hub in ('hiring','people'):
            self.assertIn('category("pb_%s_hub_lens").add("joining"' % hub,src)
        self.assertIn('probe:{model:MODEL,method:"can_open"}',src)

    def test_t40_palette(self):
        src=(Path(get_module_path('pb_joining'))/'static/src/js/joining_board.js').read_text()
        self.assertIn('category("pb_hub_palette").add("joining_board"',src)
        self.assertIn('probe:lens.probe',src)

    def test_t41_added_read_only(self):
        self.j.state = 'added'
        self.assertFalse(self.board.get_one(self.j.id)['foot']['can_add'])
        with self.assertRaises(UserError):
            self.board.accept_all(self.j.id)
        with self.assertRaises(UserError):
            self.board.set_day(self.j.id,{'day_time':'9 am'})

    def test_t42_concurrent_accept(self):
        self.j.state = 'to_check'
        self.row.state = 'saved'
        rev = self.j.review_revision
        self.board.accept(self.j.id,self.row.key,rev)
        result = self.board.accept(self.j.id,self.row.key,rev)
        self.assertEqual(result['revision'],rev+1)
        self.assertIn('Updated by',result['message'])

    def test_t44_lock_card(self):
        board=self.board.with_user(self.plain)
        self.assertIn('refused',board.pbf_layout())
        src=(Path(get_module_path('pb_joining'))/'static/src/xml/joining_board.xml').read_text()
        self.assertIn('Joining is looked after by the hiring team',src)


@tagged(*TAG)
class TestHiringBoard(JoiningCase):
    def test_t33_hiring_date_and_assigned_recruiter(self):
        offer=self._signed()
        j=self.env['pb.joining'].search([('offer_id','=',offer.id)])
        day=self.today+timedelta(days=21)
        offer.action_change_join_date(day,'DEMO request')
        self.assertEqual(j.first_day,day)
        self.assertEqual(self.env['pb.joining.board'].with_user(self.recruiter).show_code(j.id)['status'],'issued')

    def test_t34_hiring_closes(self):
        offer=self._signed()
        j=self.env['pb.joining'].search([('offer_id','=',offer.id)])
        self.env['pb.joining.board'].not_joining(j.id,'DEMO reason')
        self.assertEqual(j.state,'cancelled')
        self.assertEqual(offer.join_status,'dropped')


@tagged(*TAG)
class TestFileGate(HttpCase):
    def test_t43_private_files(self):
        j=person(self.env)
        row=j.item_ids[0]
        a=self.env['ir.attachment'].create({'name':'DEMO.pdf','raw':b'%PDF-1.4 sample','res_model':row._name,'res_id':row.id})
        row.attachment_ids=a
        path='/pb_joining/file/%s/%s' % (j.id,a.id)
        for group, expected in [('pb_hiring.group_hiring_user',404),('hr.group_hr_user',200)]:
            password=secrets.token_urlsafe(24)
            user=new_test_user(self.env,login='joining.demo.file.'+str(expected),groups='base.group_user,'+group,password=password)
            self.authenticate(user.login,password)
            response=self.url_open(path)
            self.assertEqual(response.status_code,expected)
            if expected == 200:
                self.assertEqual(response.content,a.raw)
