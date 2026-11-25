# -*- coding: utf-8 -*-
"""NEWHIRE P5a — languages, the reader's language, the old window's
dependants. Test numbers match the handover: T1 PO parse gate, T2 no vendor
name anywhere, T3 a Vietnamese reader reads Vietnamese paper and item names,
T4 asked items in the reader's language, T5 emails in the recipient's
language, T7 the old window's dependants, T8 the old window without this
module; plus the §5 "reminders do no harm where email is off" proof. (T6 is
pb_learn's own suite; §6 lives in test_hiring.py, F1-F3.)"""
import importlib.util
import os
import re

from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.translate import PoFileReader

from odoo.addons.pb_people_advanced.models.newhire_approval import NEWHIRE_WRITE

from .test_invite import InviteMixin, PRIVATE
from .test_docs import DocsCommon

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = os.path.dirname(HERE)
LANGS = ('vi_VN', 'id_ID')
VENDOR = re.compile(r'odoo', re.I)
#: The two loading markers are technical words the reader needs (FACTS_CORE §I).
MARKERS = re.compile(r'#\. odoo-(python|javascript)')


def _src(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as f:
        return f.read()


def _placeholders(text):
    return sorted(re.findall(r'%\([a-z_]+\)[sd]|%[sd]|\{[a-zA-Z_]+\}', text or ''))


def _po(lang):
    """`{msgid: msgstr}` of this module's catalogue, read by the product's reader."""
    with open(os.path.join(HERE, 'i18n', '%s.po' % lang), 'rb') as f:
        return {row['src']: row['value'] for row in PoFileReader(f)}


@tagged('post_install', '-at_install', 'newhire')
class TestP5aCatalogues(TransactionCase):

    # ------------------------------------------------------------------ T1
    def test_t1_po_parse_gate(self):
        with open(os.path.join(HERE, 'i18n', 'pb_new_hire.pot'), 'rb') as f:
            pot = {row['src'] for row in PoFileReader(f)}
        self.assertGreater(len(pot), 800, 'the template carries every screen sentence')
        for lang in LANGS:
            path = os.path.join(HERE, 'i18n', '%s.po' % lang)
            with open(path, 'rb') as f:
                rows = list(PoFileReader(f))            # the parse gate itself
            done = {}
            for row in rows:
                value = row['value'] or ''
                self.assertTrue(value.strip(), '%s: no translation for %r' % (lang, row['src']))
                self.assertEqual(_placeholders(row['src']), _placeholders(value),
                                 '%s: placeholders differ for %r' % (lang, row['src']))
                self.assertEqual(sorted(re.findall(r'<[^>]+>', row['src'])), sorted(re.findall(r'<[^>]+>', value)),
                                 '%s: markup differs for %r' % (lang, row['src'][:80]))
                done[row['src']] = value
            missing = sorted(pot - set(done))
            self.assertFalse(missing, '%s lacks %d sentences, e.g. %r' % (lang, len(missing), missing[:5]))
            # the three loading markers on every entry (memory: PO loading rules)
            entries = [e.strip() for e in _src(path).split('\n\n') if 'msgid "' in e]
            body = [e for e in entries if not re.search(r'^msgid ""\nmsgstr ""\n"Project', e, flags=re.M)]
            self.assertEqual(len(body), len(pot))
            for e in body:
                self.assertTrue(e.startswith('#. module: pb_new_hire\n'), e[:200])
                self.assertRegex(e, r'\n#: (code:addons/pb_new_hire/|model:|model_terms:)', e[:200])
                if '#: code:' in e:
                    self.assertRegex(e, r'\n#\. odoo-(python|javascript)\n', e[:200])
            self.assertIn('"Language: %s\\n"' % lang, _src(path), 'the file names its language')
        # code rows that will reach a screen (odoo-python / odoo-javascript)
        with open(os.path.join(HERE, 'i18n', 'vi_VN.po'), 'rb') as f:
            code = [r for r in PoFileReader(f) if r['type'] == 'code' and r['value']
                    and ('odoo-python' in r['comments'] or 'odoo-javascript' in r['comments'])]
        self.assertGreater(len(code), 700)

    # ------------------------------------------------------------------ T2
    def test_t2_no_vendor_name_anywhere(self):
        """Both catalogues and the template, whole files (the two loading
        markers aside); every Python message; the mail template; every
        screen file (test_static S1 covers js/xml/scss line by line)."""
        for name in ('pb_new_hire.pot',) + tuple('%s.po' % l for l in LANGS):
            text = MARKERS.sub('', _src(HERE, 'i18n', name))
            hit = VENDOR.search(text)
            self.assertFalse(hit, '%s names the vendor near %r' % (
                name, text[max(0, hit.start() - 60):hit.end() + 20] if hit else ''))
        for lang in LANGS:
            for src, value in _po(lang).items():
                self.assertNotRegex(value, VENDOR, '%s: %r' % (lang, src))
        for root, _dirs, files in os.walk(HERE):
            for fname in files:
                if not fname.endswith('.py') or '/tests' in root:
                    continue
                py = _src(root, fname)
                for msg in re.findall(r'_\(\s*"((?:[^"\\]|\\.)*)"', py) + re.findall(r"_\(\s*'((?:[^'\\]|\\.)*)'", py):
                    self.assertNotRegex(msg, VENDOR, '%s: %s' % (fname, msg))
        mail = re.sub(r'<!--.*?-->', '', _src(HERE, 'data', 'mail_template.xml'), flags=re.S)
        self.assertNotRegex(re.sub(r'</?odoo>', '', mail), VENDOR)
        welcome = re.sub(r'<!--.*?-->', '', _src(HERE, 'views', 'welcome_templates.xml'), flags=re.S)
        self.assertNotRegex(re.sub(r'</?odoo>', '', welcome), VENDOR)


class LangMixin:
    """Activate the two languages and load this module's catalogues the way an
    install does (a test database has no second language: without this no
    `.po` is ever read — memory: PO loading rules)."""

    @classmethod
    def _langs(cls):
        Lang = cls.env['res.lang']
        for code in LANGS:
            Lang._activate_lang(code)
        cls.env['ir.module.module']._load_module_terms(['pb_new_hire'], list(LANGS), overwrite=True)
        cls.vi = _po('vi_VN')
        cls.idn = _po('id_ID')


@tagged('post_install', '-at_install', 'newhire')
class TestP5aReaderLanguage(LangMixin, InviteMixin, DocsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._langs()
        cls.server = cls._mail_server()
        co = {'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])]}
        cls.hr_vi = new_test_user(cls.env, login='nh_hr_vi', groups='base.group_user,hr.group_hr_user',
                                  name='DEMO NH HR vi', lang='vi_VN', **co)

    # ------------------------------------------------------------------ T3
    def test_t3_vi_reader_reads_vi_paper_and_item_names(self):
        Paper = self.env['pb.new.hire.paper']
        for code, english in (('SG', 'NRIC or work pass'), ('ID', 'KTP (identity card)'),
                              ('VN', 'Citizen ID card')):
            row = Paper.for_country(code, self.company)[:1]
            self.assertEqual(row.display_label(), english)
            self.assertEqual(row.with_context(lang='vi_VN').display_label(), self.vi[english])
            self.assertEqual(row.with_context(lang='id_ID').display_label(), self.idn[english])
            self.assertNotEqual(self.vi[english], english)
        # the shipped rows carry the translation in the stored value itself
        # (LOOK: a translation fix is the .po AND the stored value)
        ktp = self.env.ref('pb_new_hire.paper_id_ktp')
        self.env.cr.execute("SELECT label->>'vi_VN' FROM pb_new_hire_paper WHERE id = %s", [ktp.id])
        self.assertEqual(self.env.cr.fetchone()[0], self.vi['KTP (identity card)'])
        # an HR officer reading in Vietnamese (the browser sends the user's
        # language in every call's context): step 5's list in Vietnamese
        out = self.studio(self.hr_vi).with_context(lang='vi_VN').details_options(
            {'payroll_country': 'VN', 'name': 'DEMO NH An'})
        items = {i['key']: i for i in out['items']}
        self.assertEqual(items['personal']['label'], self.vi['Personal details'])
        self.assertEqual(items['bank']['label'], self.vi['Bank account'])
        self.assertEqual(items['id_number']['upload']['label'], self.vi['Citizen ID card'])
        # an unlabelled paper's plain name follows the reader too
        cert = self.env.ref('pb_employee_vault.cat_certificate')
        self.assertEqual(Paper.with_context(lang='vi_VN').plain_name(cert), self.vi['Highest certificate'])

    # ------------------------------------------------------------------ T4
    def _hire_asked(self, **items):
        """An English HR maker sends, an English approver approves; the new
        person signs in with their personal email."""
        out = self.studio().send(self.invite_draft(
            items=dict({'personal': 'ask', 'bank': 'ask', 'id_number': 'number'}, **items),
            have={'identification_id': 'S7654321A'}))
        self.assertTrue(out.get('pending'), out)
        self.approve(out)
        emp = self.hires()
        self.assertEqual(len(emp), 1)
        return emp

    def test_t4_asked_items_in_the_readers_language(self):
        emp = self._hire_asked()
        Ask = self.env['pb.new.hire.ask'].sudo()
        rows = Ask.search([('employee_id', '=', emp.id)])
        card = rows.filtered(lambda r: r.key == 'id_number')
        self.assertEqual(card.label_kind, 'card', 'number typed: the card only is asked')
        self.assertEqual(card.label, 'NRIC or work pass', 'stored in the approver\'s language')
        # the person reads Vietnamese
        user = emp.user_id or emp.pb_portal_user_id
        self.assertTrue(user)
        user.sudo().lang = 'vi_VN'
        page = self.env['pb.new.hire.welcome'].with_user(user).with_context(lang='vi_VN').page(emp)
        labels = {c['key']: c['label'] for c in page['cards']}
        self.assertEqual(labels['personal'], self.vi['Personal details'])
        self.assertEqual(labels['bank'], self.vi['Bank account'])
        self.assertEqual(labels['id_number'], self.vi['NRIC or work pass'])
        # the home row and its words follow too
        rows_put = {}
        self.env['pb.me.home'].with_user(user).with_context(lang='vi_VN')._pbnh_needs_row(
            emp, lambda key, n, url, **kw: rows_put.setdefault(key, kw))
        self.assertEqual(rows_put['nh_welcome']['label'], self.vi['Finish your joining details'])
        # HR on the New joiners board reads English; an HR officer in Vietnamese reads Vietnamese
        board = self.Invite().with_context(lang='en_US')._board([emp.id])[emp.id]
        self.assertIn('Personal details', [i['label'] for i in board['items']])
        summary = Ask.with_context(lang='vi_VN').summary(emp)
        self.assertIn(self.vi['Personal details'], [i['label'] for i in summary['items']])
        # Indonesian too
        summary = Ask.with_context(lang='id_ID').summary(emp)
        self.assertIn(self.idn['Bank account'], [i['label'] for i in summary['items']])

    def test_t4b_an_item_no_longer_listed_keeps_its_words(self):
        emp = self._hire_asked()
        Ask = self.env['pb.new.hire.ask'].sudo()
        cert = self.env.ref('pb_employee_vault.cat_other')
        gone = Ask.create({'employee_id': emp.id, 'key': 'paper-999999', 'label': 'DEMO NH old paper',
                           'need': 'optional', 'company_id': self.company.id})
        self.assertEqual(gone._labels()[gone.id], 'DEMO NH old paper', 'the stored words are the fallback')
        gone.category_id = cert
        self.assertEqual(gone.with_context(lang='vi_VN')._labels()[gone.id], self.vi['Other paper'],
                         'a paper keeps its plain name in the reader\'s language')

    def test_t4c_migration_finds_card_and_number_rows(self):
        emp = self._hire_asked()
        Ask = self.env['pb.new.hire.ask'].sudo()
        card = Ask.search([('employee_id', '=', emp.id), ('key', '=', 'id_number')])
        card.label_kind = 'item'                    # a row made before 1.5.0
        personal = Ask.search([('employee_id', '=', emp.id), ('key', '=', 'personal')])
        spec = importlib.util.spec_from_file_location(
            'pb_nh_150', os.path.join(HERE, 'migrations', '19.0.1.5.0', 'post-migrate.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.migrate(self.env.cr, '19.0.1.4.0')
        self.env.invalidate_all()
        self.assertEqual(card.label_kind, 'card')
        self.assertEqual(personal.label_kind, 'item')
        # a row stored in Vietnamese words is recognised as well
        card.write({'label_kind': 'item', 'label': self.vi['NRIC or work pass']})
        mod.migrate(self.env.cr, '19.0.1.4.0')
        self.env.invalidate_all()
        self.assertEqual(card.label_kind, 'card')

    # ------------------------------------------------------------------ T5
    def test_t5_email_in_the_recipients_language(self):
        """The maker and the approver read English; the person's sign-in is
        Vietnamese: the welcome message (subject, body, the items) is
        Vietnamese. Sent by the very call the welcome leg and "Send again"
        make (`pb.new.hire.invite.send`)."""
        emp = self._hire_asked()
        user = emp.user_id or emp.pb_portal_user_id
        self.assertTrue(user)
        user.sudo().lang = 'vi_VN'
        before = self.mail_ids()
        answer = self.Invite().with_context(lang='en_US').send(emp, 'welcome')
        self.assertTrue(answer['sent'], answer)
        self.assertEqual(answer['message'], 'Welcome message sent to %s.' % PRIVATE,
                         "the sender's own answer stays in the sender's language")
        mail = self.queued(before).filtered(lambda m: m.email_to == PRIVATE)
        self.assertEqual(len(mail), 1)
        self.assertFalse(mail.subject.startswith('Welcome to'), mail.subject)
        self.assertIn('DEMO NH Company', mail.subject)
        body = mail.body_html
        self.assertNotIn('Please finish these before your first day', body)
        self.assertNotIn('Get started', body)
        for english in ('Personal details', 'Bank account', 'NRIC or work pass'):
            self.assertIn(self.vi[english], body, english)
        self.assertNotRegex(body, VENDOR)
        # an Indonesian reader gets Indonesian
        user.sudo().lang = 'id_ID'
        emp.sudo().nh_sent_at = False
        before = self.mail_ids()
        self.Invite().send(emp, 'reminder')
        mail = self.queued(before).filtered(lambda m: m.email_to == PRIVATE)
        self.assertEqual(len(mail), 1)
        self.assertIn(self.idn['Bank account'], mail.body_html)
        self.assertNotIn('A quick reminder', mail.body_html)

    def test_t5b_hr_note_in_the_hr_persons_language(self):
        from datetime import date, timedelta
        self.fast_lane()
        self.maker.sudo().lang = 'id_ID'
        self.studio().send(self.invite_draft())
        emp = self.hires()
        Invite = self.env['pb.new.hire.invite'].sudo().with_context(lang='en_US')
        Invite._nh_remind_asks(today=date(2026, 12, 7) - timedelta(days=3))
        act = self.env['mail.activity'].sudo().search(
            [('res_model', '=', 'hr.employee'), ('res_id', '=', emp.id)])
        self.assertEqual(len(act), 1)
        self.assertEqual(act.summary, self.idn['Joining details missing'])
        self.assertNotIn('starts on', act.note or '')
        self.assertIn('DEMO NH Sari Wulandari', act.note or '')

    # ------------------------------------------------------------------ §5
    def test_reminders_do_no_harm_where_email_is_off(self):
        """Three live sites have no outgoing email on purpose: the lifecycle
        job's reminder piece sends nothing, queues nothing and writes nothing
        on the person; it never raises."""
        self.fast_lane()
        self.studio().send(self.invite_draft())
        emp = self.hires()
        self.env['ir.mail_server'].sudo().search([]).write({'active': False})
        last = emp.nh_reminded_on
        emp.nh_reminded_on = False
        before = self.mail_ids()
        counts = self.env['pb.journey.case'].sudo()._cron_lifecycle_reminders()
        self.assertIn('new_hire_asks', counts)
        self.assertEqual(counts['new_hire_asks'].get('reminded', 0), 0)
        self.assertFalse(self.queued(before).filtered(lambda m: m.email_to == PRIVATE), 'nothing queued')
        self.assertFalse(emp.nh_reminded_on, 'nothing written on the person')
        self.assertTrue(last, 'the welcome leg had stamped it before')


@tagged('post_install', '-at_install', 'newhire')
class TestP5aDependants(DocsCommon):
    """T7 — what the old window gave the modules that lean on it, through the
    studio (P1's T09 / T10 already prove pay scales and the org chart's
    "fill this role" through a real send)."""

    def test_t7_org_chart_door_prefills_manager_and_team(self):
        # the keys orgchart_edit.js `openNewStarter` sends, unchanged
        prefill = {'fill_job_id': self.accountant.id, 'parent_id': self.boss.id, 'parent_name': 'x',
                   'department_id': self.finance.id, 'department_name': 'x',
                   'job_id': self.accountant.id, 'job_title': 'x'}
        draft = self.studio().load(prefill)['draft']
        self.assertEqual(draft['parent_id'], self.boss.id)
        self.assertEqual(draft['parent_name'], self.boss.name)
        self.assertEqual(draft['department_id'], self.finance.id)
        self.assertEqual(draft['job_id'], self.accountant.id)
        self.assertEqual(draft['fill_job_id'], self.accountant.id)
        # "Add a person here" (a manager, no role): the manager and team only
        draft = self.studio().load({'parent_id': self.boss.id, 'department_id': self.finance.id})['draft']
        self.assertEqual((draft['parent_id'], draft['department_id']), (self.boss.id, self.finance.id))
        self.assertNotIn('fill_job_id', draft)
        self.assertNotIn('job_id', draft)
        js = _src(ADDONS, 'pb_orgchart', 'static', 'src', 'js', 'orgchart_edit.js')
        self.assertIn('tag: "pb_onboard_wizard"', js, 'the chart still opens the old tag (taken over)')

    def test_t7b_pay_scale_hint_and_reason_reach_the_studio(self):
        if 'pb.pay.scales' not in self.env:
            self.skipTest('pay scales are not installed')
        hint = self.studio().pay_hint(self.accountant.id, '2026-12-07', None, 'SG')
        self.assertIn('scale', hint, 'the pay-scale line the old window showed (joiner_hint.js)')
        from odoo.addons.pb_new_hire.models.studio import DRAFT_KEYS
        for key in ('pb_scale_pin_reason', 'pb_scale_pin_note', 'fill_job_id'):
            self.assertIn(key, DRAFT_KEYS, 'the old window\'s key still travels')

    def test_t7c_updates_joiners_sheet_call_is_untouched(self):
        """The Updates sheet calls `create_employee` with the old keys only
        (`pb_updates/models/updates_joiners.py`): no studio key, no leg."""
        self.fast_lane()
        Onboard = self.env['pb.people.onboard.wizard'].with_user(self.maker).with_context(
            allowed_company_ids=[self.company.id], **{NEWHIRE_WRITE: False})
        answer = Onboard.create_employee({
            'name': 'DEMO NH Sheet Person', 'department_id': self.finance.id,
            'job_id': self.accountant.id, 'work_email': 'demo.nh.sheet@example.com',
            'with_contract': True, 'wage': 3000.0, 'date_start': '2026-12-07'})
        emp = self.hires('DEMO NH Sheet Person')
        self.assertEqual(len(emp), 1, answer)
        self.assertFalse(answer.get('legs'), 'no studio leg runs for an old caller')
        self.assertFalse(self.env['pb.new.hire.ask'].sudo().search_count([('employee_id', '=', emp.id)]))
        self.assertFalse(emp.nh_remind)

    # ------------------------------------------------------------------ T8
    def test_t8_old_window_is_untouched_where_the_studio_is_absent(self):
        """The takeover lives ONLY in this module's assets: the old window's
        own registration is unchanged in pb_people_advanced, so a database
        without pb_new_hire keeps it (walked in the P5a report, W-T8)."""
        old = _src(ADDONS, 'pb_people_advanced', 'static', 'src', 'js', 'onboard_wizard.js')
        self.assertRegex(old, r'registry\.category\("actions"\)\.add\("pb_onboard_wizard", OnboardWizard\)')
        takeover = _src(HERE, 'static', 'src', 'js', 'takeover.js')
        self.assertIn('add("pb_onboard_wizard", NewHireDoor, { force: true })', takeover)
        manifest = _src(HERE, '__manifest__.py')
        self.assertIn("'pb_new_hire/static/src/js/takeover.js'", manifest)
        for module in ('pb_people', 'pb_people_advanced', 'pb_orgchart', 'pb_pay_scales', 'pb_updates'):
            text = _src(ADDONS, module, '__manifest__.py')
            self.assertNotIn('pb_new_hire', text, '%s must not depend on the studio' % module)
