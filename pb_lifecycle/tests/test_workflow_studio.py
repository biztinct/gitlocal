"""Workflow contracts: real ORM, permissions, durable execution and native hooks."""
import copy
import uuid
from datetime import timedelta
from odoo import fields
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, UserError
from odoo.addons.pb_lifecycle.models import workflow_definition as D
from odoo.addons.pb_lifecycle.models.workflow_models import internal


@tagged('post_install', '-at_install')
class TestWorkflowStudio(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Cron tests must never advance pre-existing tenant runs. These changes
        # live only in the test transaction and roll back with the fixtures.
        cls.env['pb.workflow'].sudo().search([('enabled', '=', True)]).write({'enabled': False})
        internal(cls.env['pb.workflow.event'].search([('state', '=', 'pending')])).write({'state': 'excluded'})
        internal(cls.env['pb.workflow.run'].search([('state', 'in', ['running', 'waiting'])])).write({'state': 'held'})
        cls.company = cls.env.company
        cls.admin = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Workflow test publisher', 'login': 'wf-publisher-'+str(uuid.uuid4()),
            'company_id': cls.company.id, 'company_ids': [(6, 0, cls.company.ids)],
            'group_ids': [(6, 0, [cls.env.ref('base.group_system').id, cls.env.ref('pb_lifecycle.group_workflow_publisher').id])]})
        cls.service = cls.env['pb.workflow.studio'].with_user(cls.admin).with_company(cls.company)
        cls.staff = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Workflow test participant', 'login': 'wf-test-'+str(uuid.uuid4()),
            'company_id': cls.company.id, 'company_ids': [(6, 0, cls.company.ids)],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})

    def workflow(self, nodes=None, model='', trigger='manual'):
        row = self.service.create_workflow('Test workflow', model, 'Test')
        w = self.env['pb.workflow'].browse(row['id'])
        d = D.fresh('Test workflow')
        d['trigger']['kind'] = trigger
        for node in nodes or []:
            d['nodes'].append(node)
            d['order'].append(node['id'])
        return w, d

    def form(self, ident='details', fields_=None, owner=None):
        return {'id': ident, 'type': 'input', 'title': 'Collect details', 'stage': 0,
                'owner': owner or {'kind': 'initiator'}, 'due': 2,
                'form': {'fields': fields_ or [
                    {'id': 'purpose', 'type': 'text', 'label': 'Purpose', 'required': True},
                    {'id': 'amount', 'type': 'number', 'label': 'Amount', 'required': True, 'bind': 'amount'},
                    {'id': 'urgent', 'type': 'boolean', 'label': 'Urgent', 'required': True}]}}

    def publish(self, w, d, activate=True):
        self.service.save_draft(w.id, w.revision, d)
        self.service.publish(w.id, w.revision)
        if activate:
            self.service.activate(w.id, True)
        w.invalidate_recordset()

    def start(self, w, source=None):
        result = self.service.start(w.id, source.id if source else None, str(uuid.uuid4()))
        self.assertFalse(result['error'], result)
        return self.env['pb.workflow.run'].browse(result['run_id'])

    def test_new_process_has_no_native_model_dependency(self):
        w, d = self.workflow([self.form()]); self.publish(w, d)
        run = self.start(w)
        self.assertEqual(run.state, 'waiting')
        task = run.step_ids.filtered(lambda s: s.kind == 'input')
        self.assertTrue(task.activity_id)
        result = self.service.answer(task.id, {'purpose': 'Travel', 'amount': 250, 'urgent': False})
        self.assertTrue(result['ok'])
        self.assertEqual(run.state, 'done')
        self.assertFalse(task.activity_id)
        self.assertEqual(run._values()['amount'], 250)

    def test_required_fields_checked_server_side(self):
        w, d = self.workflow([self.form()]); self.publish(w, d); run = self.start(w)
        task = run.step_ids.filtered(lambda s: s.kind == 'input')
        self.assertFalse(self.service.answer(task.id, {})['ok'])
        self.assertEqual(task.state, 'waiting')
        self.assertTrue(self.service.answer(task.id, {'purpose': 'Saved'}, False)['ok'])
        self.assertEqual(task.answers['purpose'], 'Saved')
        self.assertEqual(run.state, 'waiting')

    def test_idempotent_start_and_explicit_repeat(self):
        w, d = self.workflow([self.form()]); self.publish(w, d)
        token = str(uuid.uuid4())
        a = self.service.start(w.id, token=token)
        b = self.service.start(w.id, token=token)
        self.assertEqual(a['run_id'], b['run_id'])
        self.assertNotEqual(a['run_id'], self.start(w).id)

    def test_publish_does_not_activate(self):
        w, d = self.workflow(); self.publish(w, d, False)
        self.assertFalse(w.enabled)
        with self.assertRaises(UserError): self.start(w)
        self.assertFalse(w.automation_id)

    def test_versions_are_pinned_and_immutable(self):
        w, d = self.workflow([self.form()]); self.publish(w, d); run = self.start(w)
        old = run.version_id
        d['nodes'][1]['title'] = 'New title'
        self.publish(w, d)
        self.assertNotEqual(old, w.published_id)
        self.assertEqual(run.step_ids.filtered(lambda s: s.kind == 'input').name, 'Collect details')
        with self.assertRaises(UserError): old.write({'definition': d})

    def test_draft_conflict(self):
        w, d = self.workflow(); revision = w.revision
        self.service.save_draft(w.id, revision, d)
        with self.assertRaises(UserError): self.service.save_draft(w.id, revision, d)

    def test_native_created_hook_captures_without_inline_effects(self):
        w, d = self.workflow([self.form()], model='res.partner', trigger='created')
        self.publish(w, d)
        self.assertEqual(w.automation_id.trigger, 'on_create')
        source = self.env['res.partner'].with_user(self.admin).create({'name': 'Workflow native trigger', 'company_id': self.company.id})
        event = self.env['pb.workflow.event'].search([('workflow_id', '=', w.id), ('source_id', '=', source.id)])
        self.assertEqual(len(event), 1)
        self.assertEqual(event.state, 'pending')
        event._process()
        self.assertEqual(event.run_id.state, 'waiting')
        event._process()
        self.assertEqual(len(event.run_id.step_ids.filtered(lambda s: s.activity_id)), 1)

    def test_native_changed_hook_ignores_create_and_unwatched_fields(self):
        w, d = self.workflow([self.form()], model='res.partner', trigger='changed')
        d['trigger']['fields'] = ['name']; self.publish(w, d)
        source = self.env['res.partner'].with_user(self.admin).create({'name': 'Before', 'company_id': self.company.id})
        events = lambda: self.env['pb.workflow.event'].search_count([('workflow_id', '=', w.id)])
        self.assertEqual(events(), 0)
        source.write({'phone': '123'})
        self.assertEqual(events(), 0)
        source.write({'name': 'After'})
        self.assertEqual(events(), 1)

    def test_pause_disables_only_generated_rule(self):
        w, d = self.workflow(model='res.partner', trigger='created'); self.publish(w, d)
        self.service.activate(w.id, False)
        self.assertFalse(w.automation_id.active)

    def test_typed_branch_and_parallel_join(self):
        a = {'id': 'a', 'title': 'A', 'type': 'task', 'stage': 0, 'owner': {'kind': 'initiator'}}
        b = dict(a, id='b', title='B')
        group = {'id': 'parallel', 'type': 'parallel', 'title': 'Together', 'stage': 0, 'join': 'all',
                 'branches': [{'id': 'left', 'label': 'Left', 'steps': ['a']}, {'id': 'right', 'label': 'Right', 'steps': ['b']}]}
        w, d = self.workflow([group]); d['nodes'] += [a, b]; self.publish(w, d); run = self.start(w)
        tasks = run.step_ids.filtered(lambda s: s.kind == 'task')
        self.assertEqual(len(tasks.filtered(lambda s: s.state == 'waiting')), 2)
        self.service.answer(tasks[0].id); self.assertEqual(run.state, 'waiting')
        self.service.answer(tasks[1].id); self.assertEqual(run.state, 'done')

    def test_wait_persists_and_worker_resumes(self):
        w, d = self.workflow([{'id': 'wait', 'type': 'wait', 'title': 'Wait', 'stage': 0, 'hours': 1}]); self.publish(w, d)
        run = self.start(w); step = run.step_ids.filtered(lambda s: s.kind == 'wait')
        self.assertEqual(run.state, 'waiting')
        internal(step).write({'wake_at': fields.Datetime.now()-timedelta(hours=2)})
        self.service._cron_workflows(); self.assertEqual(run.state, 'done')

    def test_progress_permission_is_not_edit_permission(self):
        w, d = self.workflow([self.form()]); self.publish(w, d); run = self.start(w)
        staff_service = self.service.with_user(self.staff)
        with self.assertRaises(AccessError): staff_service.progress(run.id)
        self.staff.write({'group_ids': [(4, self.env.ref('pb_lifecycle.group_workflow_viewer').id)]})
        data = staff_service.progress(run.id)
        self.assertEqual(data['version'], 1)
        self.assertNotIn('form', data['graph']['nodes'][1])
        self.assertNotIn('answers', data['steps'][1])
        with self.assertRaises(AccessError): staff_service.submission(run.id)
        with self.assertRaises(AccessError): staff_service.get_workflow(w.id)
        with self.assertRaises(AccessError): staff_service.publish(w.id, w.revision)

    def test_task_owner_and_direct_runtime_mutations(self):
        w, d = self.workflow([self.form(owner={'kind': 'user', 'id': self.staff.id})]); self.publish(w, d)
        run = self.start(w); task = run.step_ids.filtered(lambda s: s.kind == 'input')
        with self.assertRaises(AccessError): self.service.answer(task.id, {})
        service = self.service.with_user(self.staff)
        self.assertEqual(service.task_detail(task.id)['id'], task.id)
        with self.assertRaises(AccessError): task.with_user(self.staff).write({'state': 'done'})
        with self.assertRaises(UserError): task.activity_id.with_user(self.staff).action_feedback()
        with self.assertRaises(UserError): task.activity_id.with_user(self.staff).write({'workflow_step_id': False})

    def test_start_requires_explicit_grant(self):
        w, d = self.workflow(); self.publish(w, d)
        service = self.service.with_user(self.staff)
        with self.assertRaises(AccessError): service.start(w.id, token=str(uuid.uuid4()))
        self.service.save_draft(w.id, w.revision, d, starter_group_ids=[self.env.ref('base.group_user').id])
        with self.assertRaises(AccessError): service.start(w.id, token=str(uuid.uuid4()))
        self.service.publish(w.id, w.revision); self.service.activate(w.id, True)
        result = service.start(w.id, token=str(uuid.uuid4()))
        self.assertEqual(result['state'], 'done')

    def test_cross_company_progress_denied(self):
        w, d = self.workflow(); self.publish(w, d); run = self.start(w)
        other = self.env['res.company'].create({'name': 'Workflow test second company'})
        internal(run).write({'company_id': other.id})
        with self.assertRaises(AccessError): self.service.progress(run.id)

    def test_source_access_is_rechecked_on_progress(self):
        w, d = self.workflow([self.form()], model='res.partner'); self.publish(w, d)
        source = self.env['res.partner'].create({'name': 'Progress source', 'company_id': self.company.id})
        run = self.start(w, source)
        source.unlink()
        with self.assertRaises(UserError): self.service.progress(run.id)

    def test_invalid_shapes_and_typed_form_values(self):
        for bad in [None, [], {'nodes': None}, {'schema': D.SCHEMA, 'nodes': [1]}, float('nan')]:
            self.assertTrue(D.validate(bad))
        d = D.fresh(); n = self.form(); d['nodes'].append(n); d['order'].append(n['id'])
        for form in [None, [], {'fields': None}, {'fields': [3]}, {'fields': [{'id': [], 'type': 'text'}]}]:
            candidate = copy.deepcopy(d); candidate['nodes'][1]['form'] = form
            self.assertTrue(D.validate(candidate))
        self.assertTrue(D.validate_answers(n['form'], {'purpose': 'X', 'amount': float('inf'), 'urgent': 'yes'})[1])
        self.assertFalse(D.validate_answers(n['form'], {'purpose': 'X', 'amount': 0, 'urgent': False})[1])

    def test_form_visibility_ignores_hidden_payload(self):
        form = {'fields': [{'id': 'yes', 'type': 'boolean', 'label': 'Yes'}, {'id': 'detail', 'type': 'text', 'label': 'Detail', 'required': True, 'visible_if': {'field': 'yes', 'op': 'eq', 'value': True}}]}
        clean, errors = D.validate_answers(form, {'yes': False, 'detail': 'Hidden value'})
        self.assertFalse(errors); self.assertNotIn('detail', clean)
        self.assertIn('detail', D.validate_answers(form, {'yes': True})[1])

    def test_cycle_and_repeated_step_rejected(self):
        d = D.fresh(); d['order'].append('trigger'); self.assertTrue(D.validate(d))
        d = D.fresh(); d['nodes'].append({'id': 'group', 'type': 'subprocess', 'title': 'Group', 'stage': 0, 'steps': ['group']}); d['order'].append('group')
        self.assertTrue(D.validate(d))

    def test_native_approval_cannot_be_omitted(self):
        if 'pb.expense.claim' not in self.env: self.skipTest('Expenses not installed')
        w, d = self.workflow(model='pb.expense.claim')
        self.assertTrue(self.service._validate(w, d))
        with self.assertRaises(UserError): self.publish(w, d)

    def approval_route(self, w, fast=False):
        from odoo.addons.biz_approval_workflow.tests.common import build, fast_step, people_step
        route = self.env['biz.approval.workflow'].create({'name': 'Workflow test approval route',
            'company_id': self.company.id, 'process_id': w.process_id.id, 'owner_user_id': self.admin.id})
        version = self.env['biz.approval.workflow.version'].create({'workflow_id': route.id, 'revision': 1,
            'definition': build([fast_step()] if fast else [people_step('signoff', [self.staff.id])])})
        engine = self.env['biz.approval.engine']
        checks = engine.validate_for_publish(version.id)
        engine.publish(version.id, version.draft_revision, None, 'Test route', [x['code'] for x in checks['warnings']])
        self.env['biz.approval.binding'].create({'company_id': self.company.id, 'process_id': w.process_id.id,
            'scope_key': '', 'kind_key': 'any', 'workflow_id': route.id, 'mode': 'follow'})
        return route

    def test_custom_process_uses_native_matrix_and_frozen_answers(self):
        matrix = {'id': 'approval', 'type': 'matrix', 'title': 'Sign off', 'stage': 0}
        w, d = self.workflow([self.form(), matrix]); self.publish(w, d)
        self.approval_route(w)
        run = self.start(w); task = run.step_ids.filtered(lambda s: s.kind == 'input')
        self.service.answer(task.id, {'purpose': 'Train ticket', 'amount': 50, 'urgent': False})
        step = run.step_ids.filtered(lambda s: s.kind == 'matrix')
        self.assertEqual(step.state, 'waiting', step.error)
        self.assertEqual(step.approval_id.state, 'pending')
        detail = run.with_user(self.staff)._approval_detail(step.approval_id.with_user(self.staff))
        self.assertIn('Train ticket', str(detail))
        full = self.service.with_user(self.staff).submission(run.id)
        self.assertTrue(full['snapshot'])
        self.assertEqual(full['sections'][0]['rows'][0]['value'], 'Train ticket')
        self.env['biz.approval.engine'].with_user(self.staff).decide(step.approval_id.id, 'signoff', 'approve')
        self.service._cron_workflows()
        self.assertEqual(step.approval_id.state, 'applied')
        self.assertEqual(run.state, 'done')

    def test_no_approval_route_reuses_native_fast_path(self):
        w, d = self.workflow([{'id': 'approval', 'type': 'matrix', 'title': 'Check policy', 'stage': 0}])
        self.publish(w, d); self.approval_route(w, fast=True)
        run = self.start(w)
        step = run.step_ids.filtered(lambda s: s.kind == 'matrix')
        self.assertEqual(run.state, 'done', step.error)
        self.assertEqual(step.approval_id.state, 'applied')

    def test_returned_approval_reopens_information_without_repeating_steps(self):
        w, d = self.workflow([self.form(), {'id': 'approval', 'type': 'matrix', 'title': 'Sign off', 'stage': 0}])
        self.publish(w, d); self.approval_route(w)
        run = self.start(w); task = run.step_ids.filtered(lambda s: s.kind == 'input')
        self.service.answer(task.id, {'purpose': 'First answer', 'amount': 50, 'urgent': False})
        step = run.step_ids.filtered(lambda s: s.kind == 'matrix'); old = step.approval_id
        self.env['biz.approval.engine'].with_user(self.staff).decide(old.id, 'signoff', 'return', reason='Please clarify')
        self.service._cron_workflows(); self.assertEqual(run.state, 'failed')
        self.service.revise_information(run.id); self.assertEqual(task.state, 'waiting')
        self.service.answer(task.id, {'purpose': 'Corrected answer', 'amount': 25, 'urgent': False})
        self.assertNotEqual(step.approval_id, old)
        self.assertEqual(step.approval_id.amount, 25)
        self.assertEqual(old.facts['amount']['value'], 50)

    def test_email_uses_native_queue_and_retries_same_message(self):
        template = self.env['mail.template'].create({'name': 'Workflow test email',
            'model_id': self.env['ir.model']._get_id('pb.workflow.run'),
            'subject': 'Workflow test', 'body_html': '<p>Test</p>', 'email_from': 'test@example.invalid',
            'email_to': 'recipient@example.invalid'})
        w, d = self.workflow([{'id': 'email', 'type': 'email', 'title': 'Send update', 'stage': 0,
            'template_id': template.id, 'purpose': 'A separate process update'}]); self.publish(w, d)
        run = self.start(w); step = run.step_ids.filtered(lambda s: s.kind == 'email')
        self.assertEqual(step.state, 'waiting', step.error); original = step.mail_id
        original.write({'state': 'exception'}); self.service._cron_workflows()
        self.assertEqual(run.state, 'failed')
        self.service.run_action(run.id, 'retry', step.id)
        self.assertEqual(step.mail_id, original); self.assertEqual(original.state, 'outgoing')
        original.write({'state': 'sent'}); self.service._cron_workflows()
        self.assertEqual(run.state, 'done')

    def test_record_button_lists_actual_runs_and_respects_view_permission(self):
        w, d = self.workflow([self.form()], model='res.partner'); self.publish(w, d)
        source = self.env['res.partner'].create({'name': 'Progress button source', 'company_id': self.company.id})
        run = self.start(w, source)
        result = self.service.record_runs('res.partner', source.id)
        self.assertEqual([row['id'] for row in result['runs']], run.ids)
        self.assertEqual(self.service.with_user(self.staff).record_runs('res.partner', source.id)['runs'], [])

    def rule(self, field, value, op='eq'):
        return {'match': 'all', 'rules': [{'field': field, 'op': op, 'value': value}]}

    def todo(self, ident, stage=0, **kw):
        return {'id': ident, 'type': 'task', 'title': ident, 'stage': stage,
                'owner': {'kind': 'initiator'}, 'due': 2, **kw}

    def test_conditional_task_skips_without_activity(self):
        w, d = self.workflow([self.todo('skip', when=self.rule('person.user_id', self.staff.id)), self.todo('do')])
        self.publish(w, d); run = self.start(w)
        skipped = run.step_ids.filtered(lambda s: s.key == 'skip')
        self.assertEqual(skipped.state, 'skipped'); self.assertFalse(skipped.activity_id)
        self.assertEqual(run.step_ids.filtered(lambda s: s.key == 'do').state, 'waiting')
        self.assertIn('Filters', self.service.progress(run.id)['steps'][1]['reason'])

    def test_nested_filters_and_roles(self):
        task = self.todo('do', when={'match': 'any', 'rules': [self.rule('person.user_id', self.staff.id),
            {'match': 'all', 'rules': [{'field': 'person.group_ids', 'op': 'contains', 'value': self.env.ref('base.group_system').id},
                                     {'field': 'workflow.stage', 'op': 'eq', 'value': 0}]}]})
        w, d = self.workflow([task]); self.publish(w, d); run = self.start(w)
        self.assertEqual(run.step_ids.filtered(lambda s: s.key == 'do').state, 'waiting')

    def test_filtered_parallel_any_waits_for_eligible_work(self):
        group={'id':'both','type':'parallel','title':'Parallel','stage':0,'join':'any','branches':[
            {'id':'excluded','label':'Excluded','condition':self.rule('person.user_id',self.staff.id),'steps':['a']},
            {'id':'included','label':'Included','condition':self.rule('person.user_id',self.admin.id),'steps':['b']}]}
        w,d=self.workflow([group,self.todo('a'),self.todo('b'),self.todo('after')]);d['order']=['trigger','both','after']
        self.publish(w,d);run=self.start(w)
        steps={s.key:s for s in run.step_ids}
        self.assertEqual(steps['a'].state,'skipped');self.assertEqual(steps['b'].state,'waiting')
        self.assertEqual(steps['after'].state,'pending')
        self.service.answer(steps['b'].id,{})
        self.assertEqual(steps['after'].state,'waiting')

    def test_parallel_with_no_matches_continues(self):
        no=self.rule('person.user_id',self.staff.id)
        group={'id':'both','type':'parallel','title':'Parallel','stage':0,'join':'all','branches':[
            {'id':'a_path','label':'First','condition':no,'steps':['a']},
            {'id':'b_path','label':'Second','condition':no,'steps':['b']}]}
        w,d=self.workflow([group,self.todo('a'),self.todo('b')]);d['order']=['trigger','both']
        self.publish(w,d);run=self.start(w)
        self.assertEqual(run.state,'done');self.assertEqual(len(run.step_ids.filtered(lambda s:s.state=='skipped')),2)
        preview=self.service.preview(w.id,{'person.user_id':self.admin.id})
        self.assertEqual(sum(bool(x.get('skipped')) for x in preview['steps']),2)

    def test_wait_conditions_use_live_record_and_timeout(self):
        wait={'id':'wait','type':'wait','title':'Wait for readiness','stage':0,'hours':1,'wait_for':self.rule('name','Ready')}
        w,d=self.workflow([wait],model='res.partner');self.publish(w,d)
        source=self.env['res.partner'].create({'name':'Not yet','company_id':self.company.id})
        run=self.start(w,source);self.assertEqual(run.state,'waiting')
        source.name='Ready';self.service._cron_workflows();self.assertEqual(run.state,'done')
        source.name='Not yet';later=self.start(w,source)
        step=later.step_ids.filtered(lambda s:s.key=='wait');internal(step).write({'wake_at':fields.Datetime.now()-timedelta(hours=1)})
        self.service._cron_workflows();self.assertEqual(step.state,'failed');self.assertIn('deadline',step.error)

    def test_new_conditions_read_live_old_branches_keep_snapshot(self):
        w,d=self.workflow([self.todo('first'),self.todo('after',when=self.rule('name','New'))],model='res.partner')
        self.publish(w,d);source=self.env['res.partner'].create({'name':'Old','company_id':self.company.id})
        run=self.start(w,source);source.name='New'
        self.service.answer(run.step_ids.filtered(lambda s:s.key=='first').id,{})
        self.assertEqual(run.step_ids.filtered(lambda s:s.key=='after').state,'waiting')
        self.assertEqual(run._values()['name'],'Old')

    def test_native_before_and_after_domains(self):
        w,d=self.workflow([self.todo('do')],model='res.partner',trigger='changed')
        d['trigger'].update(fields=['name'],before=self.rule('name','Before'))
        d['scope']=self.rule('name','After');self.publish(w,d)
        source=self.env['res.partner'].with_user(self.admin).create({'name':'Wrong','company_id':self.company.id})
        events=lambda:self.env['pb.workflow.event'].search_count([('workflow_id','=',w.id)])
        source.name='After';self.assertEqual(events(),0)
        source.name='Before';source.name='After';self.assertEqual(events(),1)
        self.assertIn('Before',w.automation_id.filter_pre_domain);self.assertIn('After',w.automation_id.filter_domain)
        preview=self.service.preview(w.id,{'name':'After'},{'name':'Before'})
        self.assertTrue(preview['included'])
        self.assertFalse(self.service.preview(w.id,{'name':'After'},{'name':'Wrong'})['included'])

    def test_native_negative_before_filter_does_not_match_missing_value(self):
        w,d=self.workflow([self.todo('do')],model='res.partner',trigger='changed')
        d['trigger'].update(fields=['name'],before=self.rule('email','excluded@example.invalid','ne'))
        self.publish(w,d)
        source=self.env['res.partner'].with_user(self.admin).create({'name':'Empty email','company_id':self.company.id})
        source.name='Changed with no email'
        self.assertFalse(self.env['pb.workflow.event'].search([('workflow_id','=',w.id)]))
        source.email='included@example.invalid';source.name='Changed with an email'
        self.assertEqual(self.env['pb.workflow.event'].search_count([('workflow_id','=',w.id)]),1)

    def test_existing_record_stage_is_available_without_creating_stages(self):
        self.admin.write({'group_ids': [(4, self.env.ref('hr_recruitment.group_hr_recruitment_manager').id)]})
        meta=self.service.metadata('hr.applicant')
        stage=next(f for f in meta['fields'] if f['key']=='stage_id')
        self.assertEqual(stage['relation'],'hr.recruitment.stage')
        count=self.env['hr.recruitment.stage'].search_count([])
        w,d=self.workflow([self.todo('do')],model='hr.applicant')
        d['stages'].append({'name':'Workflow-only stage'})
        self.service.save_draft(w.id,w.revision,d)
        self.assertEqual(self.env['hr.recruitment.stage'].search_count([]),count)

    def test_native_activity_type_and_record_owner_reused(self):
        activity=self.env['mail.activity.type'].create({'name':'Workflow check','category':'default'})
        task=self.todo('do',owner={'kind':'field','field':'user_id'},activity_type_id=activity.id)
        w,d=self.workflow([task],model='res.partner');self.publish(w,d)
        source=self.env['res.partner'].create({'name':'Assigned','company_id':self.company.id,'user_id':self.admin.id})
        run=self.start(w,source);step=run.step_ids.filtered(lambda s:s.key=='do')
        self.assertEqual(step.assignee_id,self.admin);self.assertEqual(step.activity_id.activity_type_id,activity)

    def test_shared_template_editor_native_preview_and_concurrency(self):
        w,d=self.workflow(model='res.partner')
        payload={'name':'Native shared message','subject':'Hello {{ object.name }}','body_html':'<p>Hello <t t-out="object.name"/></p>','email_to':'preview@example.invalid'}
        created=self.service.save_template(w.id,payload)
        template=self.env['mail.template'].browse(created['id'])
        self.assertEqual(template.model,'res.partner');self.assertIn('t-out',template.body_html)
        source=self.env['res.partner'].create({'name':'Preview Person','company_id':self.company.id})
        count=self.env['mail.mail'].search_count([])
        preview=self.service.template_preview(w.id,payload,source.id)
        self.assertEqual(preview['subject'],'Hello Preview Person');self.assertIn('Preview Person',preview['body_html'])
        self.assertEqual(self.env['mail.mail'].search_count([]),count)
        changed=self.service.save_template(w.id,{**payload,'subject':'Updated'},template.id,created['revision'])
        self.assertEqual(changed['id'],template.id)
        with self.assertRaises(UserError):self.service.save_template(w.id,payload,template.id,'stale')
        with self.assertRaises(AccessError):self.service.with_user(self.staff).template_detail(w.id,template.id)
        other,_=self.workflow(model='hr.employee')
        with self.assertRaises(UserError):self.service.template_detail(other.id,template.id)

    def test_filters_cannot_bypass_required_approval(self):
        w,d=self.workflow([{'id':'approve','type':'matrix','title':'Approval','stage':0,'when':self.rule('amount',0)}])
        self.assertTrue(any('Approval decisions' in x['text'] for x in self.service._validate(w,d)))

    def test_filter_validation_rejects_wrong_types_and_forward_answers(self):
        task=self.todo('first',when=self.rule('step.details.amount',5));w,d=self.workflow([task,self.form()])
        self.assertTrue(self.service._validate(w,d))
        d['nodes'][1]['when']=self.rule('amount','five')
        self.assertTrue(self.service._validate(w,d))
