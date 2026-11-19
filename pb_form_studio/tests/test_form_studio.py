# -*- coding: utf-8 -*-
"""FS-1 numbered tests (see docs/handovers/formstudio/FS1_REPORT.md).

Tests 11 (multi-worker registry) and 12 (upgrade keeps fields and data) need
a running multi-worker server / a second process and are run by the scripts
named in the report; 16 is the browser walk.
"""
import base64
import re
from pathlib import Path
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_form_studio.models import form_studio as fs

HOST = 'pbfs_sample'
MODEL = 'pb.form.sample'
MODULE_DIR = Path(__file__).resolve().parent.parent


@tagged('post_install', '-at_install', 'pb_form_studio')
class TestFormStudio(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.form.studio']
        cls.vn = cls.env.ref('base.vn')
        cls.india = cls.env.ref('base.in')
        cls.admin = new_test_user(cls.env, 'pbfs_admin', groups='base.group_user,base.group_system',
                                  name='DEMO Studio Admin')
        cls.hr = new_test_user(cls.env, 'pbfs_hr', groups='base.group_user,hr.group_hr_user',
                               name='DEMO HR Officer')
        cls.staff = new_test_user(cls.env, 'pbfs_staff', groups='base.group_user',
                                  name='DEMO Staff')
        cls.portal = new_test_user(cls.env, 'pbfs_portal', groups='base.group_portal',
                                   name='DEMO Portal')
        cls.rec_vn = cls.env[MODEL].create({'name': 'DEMO Lan', 'country_id': cls.vn.id})
        cls.rec_in = cls.env[MODEL].create({'name': 'DEMO Arjun', 'country_id': cls.india.id})
        cls.rec_none = cls.env[MODEL].create({'name': 'DEMO Nobody'})

    # ---------------------------------------------------------------- utils
    def studio(self, user=None):
        return self.Studio.with_user(user or self.admin)

    def make(self, kind, label, **kw):
        vals = dict({'type': kind, 'label': label, 'vis': 'all'}, **kw)
        return self.studio().create_field(HOST, vals)

    def publish(self, fields_in_custom, **kw):
        st = self.studio()
        payload = dict({'sections': [{'id': 'custom', 'fields': fields_in_custom}],
                        'base_version': st.get_studio(HOST)['version']}, **kw)
        return st.publish(HOST, payload)

    # ------------------------------------------------------------------- 1
    def test_01_create_each_type_real_column_and_labels(self):
        self.env['res.lang']._activate_lang('vi_VN')
        self.env['res.lang']._activate_lang('id_ID')
        specs = [('text', {}), ('longtext', {}), ('integer', {}), ('number', {}),
                 ('money', {}), ('bool', {}), ('date', {}),
                 ('select', {'options': ['Small', 'Large']}),
                 ('m2o', {'comodel': 'res.country'}), ('file', {})]
        expect = {'text': 'char', 'longtext': 'text', 'integer': 'integer', 'number': 'float',
                  'money': 'monetary', 'bool': 'boolean', 'date': 'date',
                  'select': 'selection', 'm2o': 'many2one', 'file': 'binary'}
        for i, (kind, extra) in enumerate(specs):
            d = self.make(kind, 'DEMO Field %s' % i,
                          labels={'vi_VN': 'Trường %s' % i, 'id_ID': 'Kolom %s' % i}, **extra)
            name = d['name']
            self.assertTrue(name.startswith('x_pbfs_demo_field_'))
            field = self.env[MODEL]._fields[name]
            self.assertEqual(field.type, expect[kind])
            if kind != 'file':
                self.env.cr.execute("SELECT 1 FROM information_schema.columns "
                                    "WHERE table_name='pb_form_sample' AND column_name=%s", [name])
                self.assertTrue(self.env.cr.fetchone(), name)
            for lang, want in (('en_US', 'DEMO Field %s' % i), ('vi_VN', 'Trường %s' % i),
                               ('id_ID', 'Kolom %s' % i)):
                got = self.env[MODEL].with_context(lang=lang).fields_get([name])[name]['string']
                self.assertEqual(got, want)
        # Slug: ASCII from the label, collisions numbered.
        a = self.make('text', 'Đồng phục')
        b = self.make('text', 'Đồng phục!')
        self.assertEqual(a['name'], 'x_pbfs_dong_phuc')
        self.assertEqual(b['name'], 'x_pbfs_dong_phuc_2')

    # ------------------------------------------------------------------- 2
    def test_02_update_label_help_options_visibility(self):
        d = self.make('select', 'DEMO Size', options=['S', 'M'])
        name = d['name']
        self.env[MODEL].browse(self.rec_vn.id).write({name: 'opt_1'})
        out = self.studio().update_field(MODEL, name, {
            'label': 'DEMO Uniform size', 'help': 'For the store',
            'options': [{'value': 'opt_1', 'label': 'Small'}, {'value': 'opt_2', 'label': 'Medium'},
                        {'label': 'Large'}]})
        self.assertEqual(out['label'], 'DEMO Uniform size')
        self.assertEqual(out['help'], 'For the store')
        self.assertEqual([o['label'] for o in out['options']], ['Small', 'Medium', 'Large'])
        self.assertEqual(self.rec_vn[name], 'opt_1', 'existing answers keep their meaning')
        # A choice still in use cannot be removed.
        with self.assertRaises(UserError):
            self.studio().update_field(MODEL, name, {'options': [{'value': 'opt_2', 'label': 'M'}]})
        # Visibility: everyone → HR staff → the plain staff login loses it.
        self.assertIn(name, self.env[MODEL].with_user(self.staff).fields_get())
        self.studio().update_field(MODEL, name, {'vis': 'hr'})
        self.assertIn(name, self.env[MODEL].with_user(self.hr).fields_get())
        self.assertNotIn(name, self.env[MODEL].with_user(self.staff).fields_get())
        self.assertNotIn(name, self.rec_vn.with_user(self.staff).read()[0])
        with self.assertRaises(AccessError):
            self.rec_vn.with_user(self.staff).read([name])
        with self.assertRaises(AccessError):
            self.env[MODEL].with_user(self.staff).search_read([], [name])
        # Administrators only → HR loses it too; changing back re-opens it.
        self.studio().update_field(MODEL, name, {'vis': 'admin'})
        self.assertNotIn(name, self.env[MODEL].with_user(self.hr).fields_get())
        self.studio().update_field(MODEL, name, {'vis': 'all'})
        self.assertIn(name, self.env[MODEL].with_user(self.staff).fields_get())

    # ------------------------------------------------------------------- 3
    def test_03_type_change_refused(self):
        d = self.make('integer', 'DEMO Count')
        for vals in ({'type': 'text'}, {'ttype': 'char'}, {'comodel': 'res.country'}):
            with self.assertRaises(UserError):
                self.studio().update_field(MODEL, d['name'], vals)
        with self.assertRaises(UserError):
            self.env['ir.model.fields'].search([('model', '=', MODEL), ('name', '=', d['name'])]) \
                .write({'ttype': 'char'})
        self.assertEqual(self.env[MODEL]._fields[d['name']].type, 'integer')
        # Standard fields: never changed or deleted here.
        with self.assertRaises(UserError):
            self.studio().update_field(MODEL, 'email', {'label': 'x'})
        with self.assertRaises(UserError):
            self.studio().delete_field(MODEL, 'email', 'Email')

    # ------------------------------------------------------------------- 4
    def test_04_delete_blockers_then_clean_delete(self):
        d = self.make('text', 'DEMO Badge')
        name = d['name']
        self.rec_vn.write({name: 'B-17'})
        self.publish([name])
        filt = self.env['ir.filters'].create({'name': 'DEMO badge search', 'model_id': MODEL,
                                              'domain': "[('%s', '!=', False)]" % name})
        refs = self.studio().field_references(MODEL, name)
        self.assertTrue(any(r['kind'] == 'filter' and 'DEMO badge search' in r['names'] for r in refs))
        with self.assertRaises(UserError):
            self.studio().delete_field(MODEL, name, 'DEMO Badge')
        filt.unlink()
        # Wrong confirmation text refused.
        with self.assertRaises(UserError):
            self.studio().delete_field(MODEL, name, 'DELETE')
        res = self.studio().delete_field(MODEL, name, 'demo badge')
        self.assertNotIn(name, self.env[MODEL]._fields)
        self.env.cr.execute("SELECT 1 FROM information_schema.columns "
                            "WHERE table_name='pb_form_sample' AND column_name=%s", [name])
        self.assertFalse(self.env.cr.fetchone())
        audit = self.env['pb.form.audit'].search([('action', '=', 'delete_field'),
                                                  ('field_name', '=', name)])
        self.assertEqual(audit.attachment_id.id, res['attachment_id'])
        csv_text = base64.b64decode(audit.attachment_id.datas).decode('utf-8-sig')
        self.assertIn('B-17', csv_text)
        self.assertIn('DEMO Lan', csv_text)
        # The published layout no longer names it.
        lay = self.Studio._pbfs_layout(HOST)
        self.assertNotIn(name, str(lay.sections))

    def test_04b_import_mapping_blocks_delete(self):
        """Pay-data import mappings would be deleted silently with the field."""
        if 'hr.payslip.import.mapping' not in self.env:
            self.skipTest('pay data import is not installed')
        d = self.make('integer', 'DEMO Mapped')
        row = self.env['ir.model.fields'].search([('model', '=', MODEL), ('name', '=', d['name'])])
        with patch.object(type(self.Studio), '_pbfs_refs_import_mappings',
                          lambda s, m, n: [s._pbfs_ref('import_mapping', 'Pay data import mappings',
                                                       ['DEMO scheme'], count=1)]):
            refs = self.studio().field_references(MODEL, d['name'])
            self.assertEqual(refs[0]['kind'], 'import_mapping')
            with self.assertRaises(UserError):
                self.studio().delete_field(MODEL, d['name'], 'DEMO Mapped')
        self.assertTrue(row.exists())

    # ------------------------------------------------------------------- 5
    def test_05_draft_per_user_publish_version_stale(self):
        admin2 = new_test_user(self.env, 'pbfs_admin2', groups='base.group_user,base.group_system',
                               name='DEMO Second Admin')
        st1, st2 = self.studio(), self.studio(admin2)
        v0 = st1.get_studio(HOST)['version']
        st1.save_draft(HOST, {'sections': [{'id': 'custom', 'fields': ['email']}], 'base_version': v0})
        st2.save_draft(HOST, {'sections': [{'id': 'custom', 'fields': ['phone']}], 'base_version': v0})
        self.assertEqual(st1.get_studio(HOST)['draft']['payload']['sections'][0]['fields'], ['email'])
        self.assertEqual(st2.get_studio(HOST)['draft']['payload']['sections'][0]['fields'], ['phone'])
        res = st1.publish(HOST, {'sections': [{'id': 'custom', 'fields': ['email']}],
                                 'base_version': v0, 'changes': ['Moved Email']})
        self.assertTrue(res['ok'])
        self.assertEqual(res['version'], v0 + 1)
        self.assertIsNone(st1.get_studio(HOST)['draft'])
        self.assertTrue(self.env['pb.form.audit'].search([('action', '=', 'publish')]))
        # Admin 2's draft is now stale: told plainly, nothing changes.
        self.assertTrue(st2.get_studio(HOST)['draft']['stale'])
        stale = st2.publish(HOST, {'sections': [{'id': 'custom', 'fields': ['phone']}],
                                   'base_version': v0})
        self.assertFalse(stale['ok'])
        self.assertTrue(stale['stale'])
        self.assertIn('DEMO Studio Admin', stale['message'])
        self.assertIn('email', self.Studio._pbfs_layout(HOST).sections[-1]['fields'])
        ok = st2.publish(HOST, {'sections': [{'id': 'custom', 'fields': ['phone']}],
                                'base_version': v0, 'overwrite': True})
        self.assertEqual(ok['version'], v0 + 2)

    def test_05b_publish_creates_and_places(self):
        res = self.publish(['new:1'], creates=[{'tmp': '1', 'type': 'text', 'label': 'DEMO Locker'}])
        name = res['created']['1']
        sec = [s for s in self.Studio._pbfs_effective(HOST) if s['id'] == 'custom'][0]
        self.assertIn(name, sec['fields'])

    # ------------------------------------------------------------------- 6
    def test_06_layout_fallback(self):
        d = self.make('text', 'DEMO Lost')
        eff = self.Studio._pbfs_effective(HOST, stored=[
            {'id': 'gone_section', 'fields': [d['name'], 'email']},
            {'id': 'pay', 'fields': ['phone']},          # locked: never holds fields
            {'id': 'about', 'fields': ['email', 'nonexistent_field']},
        ])
        by = {s['id']: s['fields'] for s in eff}
        self.assertIn(d['name'], by['custom'])
        self.assertIn('phone', by['custom'])
        self.assertEqual(by['pay'], [])
        self.assertIn('name', by['about'], 'locked field returns to its home')
        all_names = [n for s in eff for n in s['fields']]
        self.assertNotIn('nonexistent_field', all_names)
        self.assertEqual(len(all_names), len(set(all_names)))

    # ------------------------------------------------------------------- 7
    def test_07_write_values_whitelist_coercion_required_rules(self):
        num = self.make('integer', 'DEMO Kids', is_required=True)['name']
        day = self.make('date', 'DEMO Review')['name']
        pick = self.make('select', 'DEMO Shirt', options=['S', 'M'])['name']
        link = self.make('m2o', 'DEMO Home country', comodel='res.country')['name']
        hr_only = self.make('text', 'DEMO Note', vis='hr')['name']
        W = self.Studio.with_user(self.hr)
        ok = W.write_values(MODEL, self.rec_vn.id, {num: '1,204', day: '2026-12-01', pick: 'opt_2',
                                                    link: self.vn.id})
        self.assertTrue(ok['ok'], ok)
        self.assertEqual(self.rec_vn[num], 1204)
        self.assertEqual(str(self.rec_vn[day]), '2026-12-01')
        self.assertEqual(ok['values'][pick]['display'], 'M')
        bad = W.write_values(MODEL, self.rec_vn.id, {num: '2.5', pick: 'nope', 'name': 'Hacked',
                                                     day: 'soon'})
        self.assertFalse(bad['ok'])
        self.assertEqual(set(bad['errors']), {num, pick, 'name', day})
        self.assertEqual(self.rec_vn.name, 'DEMO Lan', 'nothing written when anything fails')
        req = W.write_values(MODEL, self.rec_vn.id, {num: ''})
        self.assertIn(num, req['errors'])
        # A user who cannot write the record is refused (ACL)…
        no = self.Studio.with_user(self.staff).write_values(MODEL, self.rec_vn.id, {day: '2026-01-01'})
        self.assertFalse(no['ok'])
        # …and record rules apply: another company's record is not reachable.
        other = self.env['res.company'].create({'name': 'DEMO Other Co'})
        rec_other = self.env[MODEL].create({'name': 'DEMO Other', 'company_id': other.id})
        no2 = W.write_values(MODEL, rec_other.id, {day: '2026-01-01'})
        self.assertFalse(no2['ok'])
        # A field the writer may not see cannot be written.
        no3 = self.Studio.with_user(self.staff).write_values(MODEL, self.rec_vn.id, {hr_only: 'x'})
        self.assertFalse(no3['ok'])
        # Not a host model → refused.
        self.assertFalse(W.write_values('res.partner', self.env.user.partner_id.id, {'name': 'x'})['ok'])

    # ------------------------------------------------------------------- 8
    def test_08_refused_while_pay_run_worked_out(self):
        with patch.object(type(self.Studio), '_pbfs_busy',
                          lambda s: 'A pay run is being worked out right now. Try again in a few minutes.'):
            with self.assertRaisesRegex(UserError, 'pay run is being worked out'):
                self.make('text', 'DEMO Busy')
        d = self.make('text', 'DEMO Busy later')
        with patch.object(type(self.Studio), '_pbfs_busy', lambda s: 'busy'):
            with self.assertRaises(UserError):
                self.studio().delete_field(MODEL, d['name'], 'DEMO Busy later')
        # The real signal: a draft run's payslip written just now.
        if 'hr.payslip.run' in self.env and 'hr.payslip' in self.env:
            self.assertEqual(self.Studio._pbfs_busy(), '')
            emp = self.env['hr.employee'].create({'name': 'DEMO Payee'})
            run = self.env['hr.payslip.run'].create({'name': 'DEMO run', 'date_start': '2026-11-01',
                                                     'date_end': '2026-11-30'})
            vals = {'name': 'DEMO slip', 'employee_id': emp.id, 'payslip_run_id': run.id,
                    'date_from': '2026-11-01', 'date_to': '2026-11-30'}
            try:
                with self.env.cr.savepoint():
                    self.env['hr.payslip'].create(vals)
            except Exception:                           # noqa: BLE001
                self.skipTest('a payslip cannot be made without a contract on this database')
            self.assertIn('pay run', self.Studio._pbfs_busy())

    # ------------------------------------------------------------------- 9
    def test_09_forbidden_models(self):
        for model in ('res.users', 'res.groups', 'ir.model', 'ir.ui.view', 'hr.payslip',
                      'hr.payslip.line', 'res.partner', 'hr.version'):
            self.assertTrue(self.Studio._pbfs_model_forbidden(model), model)
        with patch.object(type(self.Studio), '_pbfs_hosts', lambda s: {
                'bad': {'model': 'res.users', 'title': 'x', 'sections': []}}):
            with self.assertRaises(UserError):
                self.studio().create_field('bad', {'type': 'text', 'label': 'DEMO'})
        with self.assertRaises(UserError):
            self.studio().create_field('no_such_host', {'type': 'text', 'label': 'DEMO'})
        with self.assertRaises(UserError):
            self.make('m2o', 'DEMO Bad link', comodel='res.users')

    # ------------------------------------------------------------------ 10
    def test_10_access_matrix(self):
        d = self.make('text', 'DEMO Matrix')
        studio_calls = [
            ('get_studio', (HOST,)), ('create_field', (HOST, {'type': 'text', 'label': 'DEMO'})),
            ('update_field', (MODEL, d['name'], {'label': 'x'})),
            ('delete_field', (MODEL, d['name'], 'DEMO Matrix')),
            ('field_references', (MODEL, d['name'])), ('save_draft', (HOST, {})),
            ('discard_draft', (HOST,)), ('publish', (HOST, {})), ('library', ()),
            ('dev_sample', ()),
        ]
        for user in (self.hr, self.staff, self.portal):
            S = self.Studio.with_user(user)
            self.assertFalse(S.can_edit(HOST))
            for method, args in studio_calls:
                with self.assertRaises(AccessError, msg='%s %s' % (user.login, method)):
                    getattr(S, method)(*args)
        self.assertTrue(self.studio().can_edit(HOST))
        # The card is the administrator's only (resolve_gates answers on the
        # groups the registered descriptor names).
        card = (MODULE_DIR / 'static/src/js/settings_card.js').read_text()
        self.assertIn('groups: ["base.group_system"]', card)
        # The dev host's screen asks the same gate.
        dev = (MODULE_DIR / 'static/src/js/dev_host.js').read_text()
        self.assertIn('can_edit', dev)
        # Portal users cannot read sample records at all.
        with self.assertRaises(AccessError):
            self.Studio.with_user(self.portal).render(HOST, self.rec_vn.id)

    # ------------------------------------------------------------------ 13
    def test_13_silent_install(self):
        # Meaningful on a database where the Form builder was only just
        # installed (the report's run is a fresh install). Once somebody has
        # used it, its own history says so and there is nothing to prove.
        self.env.cr.execute("SELECT count(*) FROM pb_form_audit WHERE create_date < now()")
        if self.env.cr.fetchone()[0]:
            self.skipTest('the Form builder has been used on this database')
        # Everything older than this class's first record was made by the install.
        since = self.admin.create_date
        for model in ('pb.form.field.meta', 'pb.form.layout', 'pb.form.layout.draft',
                      'pb.form.native.view', 'pb.form.audit', 'pb.form.sample'):
            self.env.cr.execute("SELECT count(*) FROM %s WHERE create_date < %%s"
                                % self.env[model]._table, [since])
            self.assertEqual(self.env.cr.fetchone()[0], 0, model)
        self.env.cr.execute("SELECT count(*) FROM ir_model_fields WHERE name LIKE 'x\\_pbfs\\_%%' "
                            "AND create_date < %s", [since])
        self.assertEqual(self.env.cr.fetchone()[0], 0)
        data = self.env['ir.model.data'].search([('module', '=', 'pb_form_studio')])
        self.assertFalse(data.filtered(lambda d: d.model in ('ir.cron', 'mail.template',
                                                             'ir.actions.server')))
        self.assertFalse(self.env['pb.form.sample'].search([('name', 'not like', 'DEMO%')]))

    # ------------------------------------------------------------------ 14
    def test_14_caps(self):
        with self.assertRaisesRegex(UserError, 'at most 60'):
            self.make('text', 'x' * 61)
        already = len(self.Studio._pbfs_custom_names(MODEL))
        with patch.object(fs, 'MAX_PER_MODEL', already + 2):
            self.make('text', 'DEMO A')
            self.make('text', 'DEMO B')
            with self.assertRaisesRegex(UserError, 'most it can have'):
                self.make('text', 'DEMO C')
        names = [self.make('bool', 'DEMO Flag %s' % i)['name'] for i in range(3)]
        with patch.object(fs, 'MAX_PER_SECTION', 2):
            with self.assertRaisesRegex(UserError, 'at most 2 fields'):
                self.publish(names)

    # ------------------------------------------------------------------ 15
    def test_15_no_platform_name_in_user_strings(self):
        bad = re.compile(r'odoo', re.I)
        for path in list((MODULE_DIR / 'i18n').glob('*.po')):
            for line in path.read_text().splitlines():
                if line.startswith(('msgid', 'msgstr')):
                    self.assertFalse(bad.search(line), '%s: %s' % (path.name, line))
        for path in list((MODULE_DIR / 'static/src/xml').glob('*.xml')):
            text = re.sub(r'<!--.*?-->', '', path.read_text(), flags=re.S)
            self.assertFalse(bad.search(text), path.name)
        for path in list((MODULE_DIR / 'static/src/js').glob('*.js')):
            for lit in re.findall(r'_t\("([^"]*)"', path.read_text()):
                self.assertFalse(bad.search(lit), '%s: %s' % (path.name, lit))
        for path in list((MODULE_DIR / 'models').glob('*.py')):
            for lit in re.findall(r"_\('([^']*)'", path.read_text()):
                self.assertFalse(bad.search(lit), '%s: %s' % (path.name, lit))
        # Every code string the module translates has vi and id entries.
        for lang in ('vi_VN', 'id_ID'):
            po = (MODULE_DIR / 'i18n' / ('%s.po' % lang)).read_text()
            self.assertIn('msgid "Only the administrator can change forms."', po)
            self.assertIn('msgid "Form builder"', po)

    # --------------------------------------------------------- R10 country
    def test_20_country_limits(self):
        india = self.make('text', 'DEMO PAN', country_ids=[self.india.id])['name']
        every = self.make('text', 'DEMO Locker no')['name']
        self.publish([india, every])
        def names_in(rec, user=None):
            out = self.Studio.with_user(user or self.hr).render(HOST, rec.id)
            return [f['name'] for s in out['sections'] for f in s['fields']]
        self.assertIn(india, names_in(self.rec_in))
        self.assertNotIn(india, names_in(self.rec_vn))
        self.assertNotIn(india, names_in(self.rec_none), 'no country recorded → only all-countries')
        for rec in (self.rec_in, self.rec_vn, self.rec_none):
            self.assertIn(every, names_in(rec))
        W = self.Studio.with_user(self.hr)
        self.assertTrue(W.write_values(MODEL, self.rec_in.id, {india: 'ABCDE1234F'})['ok'])
        refused = W.write_values(MODEL, self.rec_vn.id, {india: 'X'})
        self.assertFalse(refused['ok'])
        self.assertIn(india, refused['errors'])
        self.assertFalse(W.write_values(MODEL, self.rec_none.id, {india: 'X'})['ok'])
        self.assertTrue(W.write_values(MODEL, self.rec_vn.id, {every: '12'})['ok'])
        # Lists / exports: the column exists, the cell is blank elsewhere.
        self.studio().update_field(MODEL, india, {'list_ok': True})
        spec = {s['name']: s for s in W.fields_for(MODEL, 'list')}
        self.assertIn(india, spec)
        self.assertNotIn(every, spec, 'not marked "Show in lists"')
        self.assertEqual(spec[india]['countries'], [self.india.id])
        self.rec_vn.sudo().write({india: 'leftover'})
        vals = W.values_for(MODEL, [self.rec_in.id, self.rec_vn.id], 'list')
        self.assertEqual(vals[self.rec_in.id][india]['display'], 'ABCDE1234F')
        self.assertEqual(vals[self.rec_vn.id][india]['display'], '')
        # Required applies only where the field applies.
        self.studio().update_field(MODEL, india, {'is_required': True})
        self.assertTrue(W.write_values(MODEL, self.rec_vn.id, {every: '13'})['ok'])

    # ------------------------------------------------ hidden values, all paths
    def test_21_hidden_value_never_reaches_a_reader(self):
        secret = self.make('text', 'DEMO Secret', vis='admin')['name']
        hr_f = self.make('text', 'DEMO HR note', vis='hr')['name']
        open_f = self.make('text', 'DEMO Open', vis='all')['name']
        self.rec_vn.write({secret: 'S3CRET', hr_f: 'HRONLY', open_f: 'OPEN'})
        self.studio().update_field(MODEL, secret, {'list_ok': True})
        self.studio().update_field(MODEL, hr_f, {'list_ok': True})
        self.studio().update_field(MODEL, open_f, {'list_ok': True})
        self.publish([secret, hr_f, open_f])
        staff_render = str(self.Studio.with_user(self.staff).render(HOST, self.rec_vn.id))
        self.assertNotIn('S3CRET', staff_render)
        self.assertNotIn('HRONLY', staff_render)
        self.assertIn('OPEN', staff_render)
        hr_render = str(self.Studio.with_user(self.hr).render(HOST, self.rec_vn.id))
        self.assertNotIn('S3CRET', hr_render)
        self.assertIn('HRONLY', hr_render)
        staff_list = [f['name'] for f in self.Studio.with_user(self.staff).fields_for(MODEL, 'list')]
        self.assertIn(open_f, staff_list)
        self.assertNotIn(secret, staff_list)
        self.assertNotIn(hr_f, staff_list)
        self.assertNotIn('S3CRET', str(self.Studio.with_user(self.hr).values_for(
            MODEL, [self.rec_vn.id], 'list')))
        # 'everyone' is decided by the setting, even around a sudo record.
        ev = self.Studio._pbfs_values_for(self.rec_vn.sudo(), 'everyone')
        self.assertIn(open_f, ev[self.rec_vn.id])
        self.assertNotIn(secret, ev[self.rec_vn.id])
        self.assertNotIn(hr_f, ev[self.rec_vn.id])
        metas = self.Studio._pbfs_meta(MODEL, list(ev[self.rec_vn.id]))
        self.assertEqual({m.vis for m in metas.values()}, {'all'})
        # Plain RPC reads.
        Rec = self.env[MODEL].with_user(self.staff)
        self.assertNotIn(secret, Rec.browse(self.rec_vn.id).read()[0])
        for call in (lambda: Rec.browse(self.rec_vn.id).read([secret]),
                     lambda: Rec.search_read([], [hr_f]),
                     lambda: Rec.web_search_read([], {secret: {}}),
                     lambda: Rec.search([(secret, '=', 'S3CRET')])):
            with self.assertRaises(AccessError):
                call()
        with self.assertRaises(AccessError):
            self.env[MODEL].with_user(self.hr).browse(self.rec_vn.id).write({secret: 'x'})
        # Native page: the field is stripped from the screen design for them.
        parent = self.env['ir.ui.view'].create({
            'name': 'DEMO sample form', 'model': MODEL, 'type': 'form',
            'arch': '<form><sheet><field name="name"/><notebook><page string="Main" name="main">'
                    '<field name="email"/></page></notebook></sheet></form>'})
        self.env['ir.model.data'].create({'module': '__pbfs_test__', 'name': 'sample_form',
                                          'model': 'ir.ui.view', 'res_id': parent.id})
        view = self.Studio._pbfs_sync_native_view(MODEL, '__pbfs_test__.sample_form',
                                                  'Company details', HOST)
        self.assertTrue(view)
        arch_staff = self.env[MODEL].with_user(self.staff).get_view(parent.id, 'form')['arch']
        self.assertIn(open_f, arch_staff)
        self.assertNotIn(secret, arch_staff)
        self.assertNotIn(hr_f, arch_staff)
        arch_admin = self.env[MODEL].with_user(self.admin).get_view(parent.id, 'form')['arch']
        self.assertIn(secret, arch_admin)

    # ------------------------------------------------------- native-view sync
    def test_22_native_view_sync(self):
        parent = self.env['ir.ui.view'].create({
            'name': 'DEMO sample form 2', 'model': MODEL, 'type': 'form',
            'arch': '<form><sheet><field name="name"/><field name="country_id"/></sheet></form>'})
        self.env['ir.model.data'].create({'module': '__pbfs_test__', 'name': 'sample_form2',
                                          'model': 'ir.ui.view', 'res_id': parent.id})
        xmlid = '__pbfs_test__.sample_form2'
        self.publish([])      # a layout with no custom field placed (a used database may have some)
        self.assertFalse(self.Studio._pbfs_sync_native_view(MODEL, xmlid, 'Company details', HOST),
                         'no custom field → no view content')
        a = self.make('text', 'DEMO First')['name']
        b = self.make('text', 'DEMO Indian', country_ids=[self.india.id])['name']
        self.publish([b, a])
        view = self.env['pb.form.native.view'].search([('parent_xmlid', '=', xmlid)]).view_id
        self.assertTrue(view, 'publish regenerated the registered page')
        arch = view.arch_db
        self.assertLess(arch.index(b), arch.index(a), 'layout order')
        self.assertIn('notebook', arch, 'a notebook is added where the screen has none')
        self.assertIn('country_id not in [%s]' % self.india.id, arch)
        self.env[MODEL].get_view(parent.id, 'form')          # the parent still renders
        # A broken arch never replaces a good one.
        rec = self.env['pb.form.native.view'].search([('parent_xmlid', '=', xmlid)])
        good = view.arch_db
        with patch.object(type(rec), '_pbfs_arch', lambda s, *a, **k: '<data><xpath expr="//nope" '
                                                                       'position="inside"/></data>'):
            rec._pbfs_regenerate()
        self.assertEqual(view.arch_db, good)
        # Delete: the page drops the field before the column goes; last one
        # removes the page.
        self.studio().delete_field(MODEL, a, 'DEMO First')
        self.assertNotIn(a, view.arch_db)
        self.studio().delete_field(MODEL, b, 'DEMO Indian')
        self.assertFalse(view.exists())

    # ---------------------------------------------------------- copy names
    def test_23_copy_names_and_copied_default(self):
        a = self.make('text', 'DEMO Carry')['name']
        self.assertIn(a, self.Studio.copy_field_names(MODEL))
        row = self.env['ir.model.fields'].search([('model', '=', MODEL), ('name', '=', a)])
        self.assertFalse(row.copied, 'sample host copies nothing by default')
        b = self.make('text', 'DEMO Carry 2', copied=True)['name']
        self.assertTrue(self.env['ir.model.fields'].search([('model', '=', MODEL), ('name', '=', b)]).copied)
        self.rec_vn.write({b: 'kept', a: 'dropped'})
        dup = self.rec_vn.copy()
        self.assertEqual(dup[b], 'kept')
        self.assertFalse(dup[a])

    def test_24_used_by_in_studio_and_library(self):
        d = self.make('text', 'DEMO Used')
        self.env['ir.filters'].create({'name': 'DEMO used search', 'model_id': MODEL,
                                       'domain': "[('%s', '=', 'x')]" % d['name']})
        studio = self.studio().get_studio(HOST)
        self.assertTrue(studio['fields'][d['name']]['used_by'])
        lib = self.studio().library()
        row = [f for f in lib['fields'] if f['name'] == d['name']][0]
        self.assertTrue(row['used_by'])
        self.assertEqual(row['record_type'], 'Sample record')
