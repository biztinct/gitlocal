"""Workflow contracts: real ORM, permissions, durable execution and native hooks."""
import copy
import os
import re
import uuid
from datetime import timedelta
from odoo import SUPERUSER_ID, fields
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
        # The worker also resumes "needs attention" runs that still have a
        # waiting step (WF2 P1), so those are held too.
        internal(cls.env['pb.workflow.run'].search([('state', 'in', ['running', 'waiting', 'failed'])])).write({'state': 'held'})
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

    def test_t5_approval_capable_model_runs_without_approval_step(self):
        # Rewritten from test_native_approval_cannot_be_omitted (WF2 P1, F1):
        # the record's own module keeps its approval; Studio no longer forces
        # an approval step on it.
        process = self.generic_process()
        self.assertTrue(process.connected)
        w, d = self.workflow([self.todo('do')], model=self.GENERIC)
        self.assertEqual(self.service._validate(w, d), [])
        self.publish(w, d)
        self.assertTrue(w.enabled)
        self.assertFalse(w.process_id)
        run = self.start(w, self.generic())
        self.assertEqual(run.step_ids.filtered(lambda s: s.key == 'do').state, 'waiting')

    def approval_route(self, w=None, fast=False, process=None):
        from odoo.addons.biz_approval_workflow.tests.common import build, fast_step, people_step
        process = process or w.process_id
        # A tenant's own route for this process would make the test's route
        # ambiguous; switched off inside the test transaction only.
        self.env['biz.approval.binding'].search([('company_id', '=', self.company.id),
            ('process_id', '=', process.id)]).write({'active': False})
        route = self.env['biz.approval.workflow'].create({'name': 'Workflow test approval route',
            'company_id': self.company.id, 'process_id': process.id, 'owner_user_id': self.admin.id})
        version = self.env['biz.approval.workflow.version'].create({'workflow_id': route.id, 'revision': 1,
            'definition': build([fast_step()] if fast else [people_step('signoff', [self.staff.id])])})
        engine = self.env['biz.approval.engine']
        checks = engine.validate_for_publish(version.id)
        engine.publish(version.id, version.draft_revision, None, 'Test route', [x['code'] for x in checks['warnings']])
        self.env['biz.approval.binding'].create({'company_id': self.company.id, 'process_id': process.id,
            'scope_key': '', 'kind_key': 'any', 'workflow_id': route.id, 'mode': 'follow'})
        return route

    def publish_with_route(self, w, d, fast=False):
        # A new process with an approval step needs its route before it can
        # be turned on (WF2 P1, F14): publish, set the route, then activate.
        self.publish(w, d, False)
        self.approval_route(w, fast=fast)
        self.service.activate(w.id, True)
        w.invalidate_recordset()

    def test_custom_process_uses_native_matrix_and_frozen_answers(self):
        matrix = {'id': 'approval', 'type': 'matrix', 'title': 'Sign off', 'stage': 0}
        w, d = self.workflow([self.form(), matrix]); self.publish_with_route(w, d)
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
        self.publish_with_route(w, d, fast=True)
        run = self.start(w)
        step = run.step_ids.filtered(lambda s: s.kind == 'matrix')
        self.assertEqual(run.state, 'done', step.error)
        self.assertEqual(step.approval_id.state, 'applied')

    def test_returned_approval_reopens_information_without_repeating_steps(self):
        w, d = self.workflow([self.form(), {'id': 'approval', 'type': 'matrix', 'title': 'Sign off', 'stage': 0}])
        self.publish_with_route(w, d)
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

    def test_record_setup_reuses_workflows_and_enforces_design_permission(self):
        source = self.env['res.partner'].create({'name': 'Setup source', 'company_id': self.company.id})
        w, _d = self.workflow(model='res.partner')
        result = self.service.record_setup('res.partner', source.id)
        self.assertIn(w.id, [row['id'] for row in result['workflows']])
        self.assertEqual(result['record_id'], source.id)
        self.assertTrue(self.service.record_runs('res.partner', source.id)['can_design'])
        with self.assertRaises(AccessError):
            self.service.with_user(self.staff).record_setup('res.partner', source.id)
        with self.assertRaises(AccessError):
            self.service.record_setup('ir.config_parameter')
        other = self.env['res.company'].create({'name': 'Other setup company'})
        source.company_id = other
        with self.assertRaises(AccessError):
            self.service.record_setup('res.partner', source.id)

    def test_record_only_scope_excludes_other_records_and_native_triggers(self):
        source = self.env['res.partner'].create({'name': 'Only this one', 'company_id': self.company.id})
        other = self.env['res.partner'].create({'name': 'Another one', 'company_id': self.company.id})
        result = self.service.create_for_record('res.partner', source.id, 'One record workflow', True)
        w = self.env['pb.workflow'].browse(result['id'])
        self.assertFalse(w.enabled)
        self.assertFalse(w.version_ids)
        d = copy.deepcopy(w.draft)
        d['trigger'].update(kind='changed', fields=['name'])
        d['nodes'].append(self.todo('check')); d['order'].append('check')
        self.publish(w, d)
        other.name = 'Other changed'
        source.name = 'Selected changed'
        events = self.env['pb.workflow.event'].search([('workflow_id', '=', w.id)])
        self.assertEqual(events.mapped('source_id'), source.ids)
        self.assertEqual(self.service._facts(source)['id'], source.id)
        self.assertFalse(D.matches(d['scope'], self.service._facts(other)))
        self.assertTrue(D.matches(d['scope'], self.service._facts(source)))

    def test_record_stages_reuse_native_statusbar_and_do_not_imply_history(self):
        if 'pb.expense.claim' not in self.env: self.skipTest('Expenses not installed')
        employee = self.env['hr.employee'].create({'name': 'Stage context employee', 'company_id': self.company.id})
        claim = self.env['pb.expense.claim'].create({'employee_id': employee.id})
        service = self.service.sudo()
        before = self.env['pb.expense.claim'].search_count([])
        tracks = service._record_stages('pb.expense.claim', claim)
        track = next(t for t in tracks if t['field'] == 'state')
        self.assertEqual(track['current'], 'draft')
        self.assertEqual(track['visible'], ['draft', 'submitted', 'approved', 'paid'])
        self.assertEqual(track['approval_value'], 'submitted')
        self.assertTrue(track['fixed'])
        self.assertIn('refused', [o['key'] for o in track['options']])
        self.assertFalse(any('completed' in o for o in track['options']))
        self.assertEqual(self.env['pb.expense.claim'].search_count([]), before)
        self.assertEqual(claim.state, 'draft')

    def test_shared_stage_rename_uses_hiring_authority_and_same_record(self):
        if 'pb.hiring' not in self.env: self.skipTest('Hiring not installed')
        self.admin.write({'group_ids': [(4, self.env.ref('hr_recruitment.group_hr_recruitment_manager').id)]})
        w, _d = self.workflow(model='hr.applicant')
        stage = self.env['hr.recruitment.stage'].search([('pb_key', '!=', False)], limit=1)
        with self.assertRaises(AccessError):
            self.service.rename_record_stage(w.id, 'stage_id', stage.id, 'Renamed', str(stage.write_date))
        self.admin.write({'group_ids': [(4, self.env.ref('pb_hiring.group_hiring_admin').id)]})
        original_count = self.env['hr.recruitment.stage'].search_count([])
        self.service.rename_record_stage(w.id, 'stage_id', stage.id, 'Shared renamed stage', str(stage.write_date))
        self.assertEqual(stage.name, 'Shared renamed stage')
        self.assertEqual(self.env['hr.recruitment.stage'].search_count([]), original_count)
        with self.assertRaises(UserError):
            self.service.rename_record_stage(w.id, 'stage_id', stage.id, 'Stale edit', 'old')
        with self.assertRaises(UserError):
            self.service.rename_record_stage(w.id, 'state', stage.id, 'Status', str(stage.write_date))

    # ------------------------------------------------------------------
    # WORKFLOW-2 phase 1: system-level execution, optional and following
    # approval steps, coexistence, one timing rule, error codes, worker.
    # ------------------------------------------------------------------
    GENERIC = 'biz.approval.generic.request'

    def generic_process(self):
        return self.env['biz.approval.process']._by_key('generic')

    def generic(self, name='Workflow generic source', company=None):
        return self.env[self.GENERIC].create({'name': name, 'company_id': (company or self.company).id})

    def person(self, name, groups):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': name, 'login': 'wf2-%s-%s' % (name.lower().replace(' ', '-'), uuid.uuid4()),
            'company_id': self.company.id, 'company_ids': [(6, 0, self.company.ids)],
            'group_ids': [(6, 0, [self.env.ref(g).id for g in groups])]})

    def approval_workflow(self, mode=None, route=True, fast=False):
        """A workflow on an existing approval-capable record with one approval step."""
        matrix = {'id': 'approval', 'type': 'matrix', 'title': 'Approval', 'stage': 0}
        if mode:
            matrix['mode'] = mode
        w, d = self.workflow([matrix], model=self.GENERIC)
        self.service.save_draft(w.id, w.revision, d, process_id=self.generic_process().id)
        if route:
            self.approval_route(process=self.generic_process(), fast=fast)
        self.publish(w, d)
        return w, d

    def wake(self, run, key):
        step = run.step_ids.filtered(lambda s: s.key == key)
        internal(step).write({'wake_at': fields.Datetime.now() - timedelta(hours=2)})
        return step

    def test_t1_run_keeps_advancing_after_creator_and_publisher_leave(self):
        owner = self.person('Workflow T1 owner', ['base.group_system', 'pb_lifecycle.group_workflow_publisher'])
        service = self.env['pb.workflow.studio'].with_user(owner).with_company(self.company)
        row = service.create_workflow('Owner leaves', '', 'Test')
        w = self.env['pb.workflow'].browse(row['id'])
        d = D.fresh('Owner leaves')
        for node in [{'id': 'pause', 'type': 'wait', 'title': 'Pause', 'stage': 0, 'hours': 1}, self.todo('after')]:
            d['nodes'].append(node); d['order'].append(node['id'])
        service.save_draft(w.id, w.revision, d); service.publish(w.id, w.revision); service.activate(w.id, True)
        run = self.start(w)
        self.assertEqual(run.execution_user_id, owner)  # column still filled, never read
        owner.write({'active': False})
        self.wake(run, 'pause')
        self.service._cron_workflows()
        after = run.step_ids.filtered(lambda s: s.key == 'after')
        self.assertEqual(after.state, 'waiting', after.error)
        self.assertEqual(after.assignee_id, self.admin)
        # A start after they left is processed too.
        self.assertEqual(self.start(w).state, 'waiting')

    def test_t2_system_execution_stays_inside_the_runs_company(self):
        other = self.env['res.company'].create({'name': 'Workflow T2 second company'})
        w, d = self.workflow([{'id': 'pause', 'type': 'wait', 'title': 'Pause', 'stage': 0, 'hours': 1},
                              self.todo('after')], model='res.partner')
        self.publish(w, d)
        source = self.env['res.partner'].create({'name': 'T2 record', 'company_id': self.company.id})
        run = self.start(w, source)
        service = run._service()
        self.assertEqual(service.env.company, self.company)
        self.assertTrue(service.env.su)
        self.assertEqual(service.env.uid, SUPERUSER_ID)
        foreign = self.env['res.partner'].create({'name': 'T2 other company', 'company_id': other.id})
        with self.assertRaises(AccessError):
            service._source('res.partner', foreign.id)
        # The record moves to the other company: the run stops, nothing is assigned.
        source.company_id = other
        self.wake(run, 'pause')
        self.service._cron_workflows()
        after = run.step_ids.filtered(lambda s: s.key == 'after')
        self.assertEqual(after.state, 'failed')
        self.assertFalse(after.activity_id)
        # A company-A trigger ignores a company-B record.
        auto, d2 = self.workflow([self.todo('do')], model='res.partner', trigger='created')
        self.publish(auto, d2)
        self.service._capture(auto.id, foreign)
        self.assertFalse(self.env['pb.workflow.event'].search([('workflow_id', '=', auto.id)]))
        # Following an approval never adopts another company's request.
        fw, _d = self.approval_workflow('follow')
        mine = self.generic('T2 follow')
        self.env['biz.approval.request'].sudo().create({
            'title': 'Other company request', 'process_id': self.generic_process().id,
            'company_id': other.id, 'res_model': self.GENERIC, 'res_id': mine.id, 'state': 'pending'})
        frun = self.start(fw, mine)
        self.service._cron_workflows()
        step = frun.step_ids.filtered(lambda s: s.kind == 'matrix')
        self.assertEqual(step.state, 'waiting')
        self.assertFalse(step.approval_id)

    def test_t3_design_time_access_stays_with_the_designer(self):
        designer = self.person('Workflow T3 designer', ['base.group_user', 'pb_lifecycle.group_workflow_designer'])
        service = self.env['pb.workflow.studio'].with_user(designer).with_company(self.company)
        offered = {r['key'] for r in service._models()}
        admin_models = [r['key'] for r in self.service._models()]
        hidden_model = next((name for name in admin_models
                             if name not in offered and not self.env[name].with_user(designer).has_access('read')), None)
        self.assertTrue(hidden_model, 'Expected a record type the designer cannot read.')
        with self.assertRaises(AccessError):
            service.create_workflow('Not allowed', hidden_model, 'Test')
        supported = ('char', 'text', 'integer', 'float', 'monetary', 'boolean', 'date', 'datetime', 'selection')
        found = None
        for model in sorted(offered):
            obj = self.env[model]
            for key, field in obj._fields.items():
                if (field.store and field.groups and field.type in supported and
                        key not in obj.with_user(designer).fields_get(attributes=['type'])):
                    found = (model, key)
                    break
            if found:
                break
        if not found:
            self.skipTest('No field on an offered record type is hidden from this designer.')
        model, key = found
        self.assertNotIn(key, {f['key'] for f in service._source_fields(model)})
        row = service.create_workflow('Hidden field', model, 'Test')
        w = self.env['pb.workflow'].browse(row['id'])
        d = D.fresh('Hidden field')
        d['scope'] = {'match': 'all', 'rules': [{'field': key, 'op': 'set'}]}
        issues = service._validate(w, d)
        self.assertIn('bad_filter', [i['code'] for i in issues])

    def test_t4_assignee_who_cannot_read_the_record_is_not_assigned(self):
        if 'hr.applicant' not in self.env: self.skipTest('Recruitment not installed')
        self.admin.write({'group_ids': [(4, self.env.ref('hr_recruitment.group_hr_recruitment_manager').id)]})
        self.assertFalse(self.env['hr.applicant'].with_user(self.staff).has_access('read'))
        w, d = self.workflow([self.todo('do', owner={'kind': 'user', 'id': self.staff.id})], model='hr.applicant')
        self.publish(w, d)
        applicant = self.env['hr.applicant'].create({'partner_name': 'Workflow T4 candidate', 'company_id': self.company.id})
        result = self.service.start(w.id, applicant.id, str(uuid.uuid4()))
        run = self.env['pb.workflow.run'].browse(result['run_id'])
        step = run.step_ids.filtered(lambda s: s.key == 'do')
        self.assertEqual(step.state, 'failed')
        self.assertTrue(step.error)
        self.assertFalse(step.activity_id)
        self.assertEqual(run.state, 'failed')

    def test_t6_studio_never_writes_a_records_status(self):
        root = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
        offenders = []
        for name in sorted(os.listdir(root)):
            if not name.startswith('workflow_') or not name.endswith('.py'):
                continue
            text = open(os.path.join(root, name), encoding='utf-8').read()
            # The one sanctioned path: a registered module operation.
            text = re.sub(r'\n    def _execute_action\(.*?(?=\n    (?:@|def ))', '\n', text, flags=re.S)
            for number, line in enumerate(text.splitlines(), 1):
                if re.search(r'\b(source|record|records|rec)\b\.(state|stage_id)\s*=[^=]', line) or \
                        re.search(r'\b(source|record|records|rec)\b(\.\w+\([^)]*\))*\.write\(', line):
                    offenders.append('%s:%s %s' % (name, number, line.strip()))
        self.assertEqual(offenders, [])

    def test_t7_follow_waits_adopts_and_finishes_without_submitting(self):
        w, _d = self.approval_workflow('follow')
        record = self.generic('T7 follow')
        Request = self.env['biz.approval.request'].sudo()
        run = self.start(w, record)
        step = run.step_ids.filtered(lambda s: s.kind == 'matrix')
        self.assertEqual(step.state, 'waiting')
        self.assertFalse(step.approval_id)
        self.assertFalse(Request.search([('res_model', '=', self.GENERIC), ('res_id', '=', record.id)]))
        self.assertEqual(self.service.progress(run.id)['steps'][1]['reason'], 'Waiting for this record to be sent for approval.')
        self.service._cron_workflows()
        self.assertFalse(Request.search([('res_model', '=', self.GENERIC), ('res_id', '=', record.id)]))
        sent = self.env['biz.approval.engine'].with_user(self.admin).submit(record.with_user(self.admin))
        self.service._cron_workflows()
        self.assertEqual(step.approval_id.id, sent['id'])
        self.env['biz.approval.engine'].with_user(self.staff).decide(step.approval_id.id, 'signoff', 'approve')
        self.service._cron_workflows()
        self.assertEqual(step.approval_id.state, 'applied')
        self.assertEqual(step.state, 'done')
        self.assertEqual(run.state, 'done')
        self.assertEqual(Request.search_count([('res_model', '=', self.GENERIC), ('res_id', '=', record.id)]), 1)

    def test_t8_follow_finishes_when_the_record_is_already_approved(self):
        w, _d = self.approval_workflow('follow', fast=True)
        record = self.generic('T8 already approved')
        self.env['biz.approval.engine'].with_user(self.admin).submit(record.with_user(self.admin))
        Request = self.env['biz.approval.request'].sudo()
        before = Request.search([('res_model', '=', self.GENERIC), ('res_id', '=', record.id)])
        self.assertEqual(before.state, 'applied')
        run = self.start(w, record)
        self.assertEqual(run.step_ids.filtered(lambda s: s.kind == 'matrix').state, 'done')
        self.assertEqual(run.state, 'done')
        self.assertEqual(Request.search([('res_model', '=', self.GENERIC), ('res_id', '=', record.id)]), before)

    def test_t9_submit_is_sent_by_the_person_who_started(self):
        w, _d = self.approval_workflow('submit')
        run = self.start(w, self.generic('T9 valid'))
        request = run.step_ids.filtered(lambda s: s.kind == 'matrix').approval_id
        self.assertTrue(request)
        self.assertEqual(request.submitter_uid.id if hasattr(request.submitter_uid, 'id') else request.submitter_uid, self.admin.id)
        # Nobody usable recorded as the starter: the step stops with a plain message.
        matrix = {'id': 'approval', 'type': 'matrix', 'title': 'Approval', 'stage': 0, 'mode': 'submit'}
        pause = {'id': 'pause', 'type': 'wait', 'title': 'Pause', 'stage': 0, 'hours': 1}
        w2, d2 = self.workflow([pause, matrix], model=self.GENERIC)
        self.service.save_draft(w2.id, w2.revision, d2, process_id=self.generic_process().id)
        self.publish(w2, d2)
        starter = self.person('Workflow T9 starter', ['base.group_system', 'pb_lifecycle.group_workflow_publisher'])
        gone = self.env['pb.workflow.studio'].with_user(starter).with_company(self.company).start(
            w2.id, self.generic('T9 starter left').id, str(uuid.uuid4()))
        system_run = self.start(w2, self.generic('T9 system'))
        internal(system_run).write({'initiator_id': SUPERUSER_ID})
        starter.write({'active': False})
        for r in (self.env['pb.workflow.run'].browse(gone['run_id']), system_run):
            self.wake(r, 'pause')
        self.service._cron_workflows()
        for r in (self.env['pb.workflow.run'].browse(gone['run_id']), system_run):
            step = r.step_ids.filtered(lambda s: s.kind == 'matrix')
            self.assertEqual(step.state, 'failed')
            self.assertIn('Nobody is recorded as having started this', step.error)
            self.assertFalse(step.approval_id)

    def test_t10_version_without_mode_still_submits(self):
        w, _d = self.approval_workflow(None)
        self.assertNotIn('mode', w.published_id.definition['nodes'][1])
        record = self.generic('T10 old version')
        run = self.start(w, record)
        step = run.step_ids.filtered(lambda s: s.kind == 'matrix')
        self.assertTrue(step.approval_id)
        self.assertEqual(step.approval_id.res_id, record.id)
        self.assertEqual(step.state, 'waiting')

    def test_t11_several_automatic_workflows_share_a_record_type(self):
        first, d1 = self.workflow([self.todo('do')], model='res.partner', trigger='created')
        d1['scope'] = self.rule('name', 'Workflow T11 Alpha'); self.publish(first, d1)
        second, d2 = self.workflow([self.todo('do')], model='res.partner', trigger='created')
        d2['scope'] = self.rule('name', 'Workflow T11 Beta'); self.publish(second, d2, False)
        with self.assertRaises(UserError) as caught:
            self.service.activate(second.id, True)
        self.assertIn('Other workflows also start', str(caught.exception))
        review = self.service.review(second.id)['other_workflows']
        row = next(r for r in review if r['id'] == first.id)
        self.assertEqual(row['trigger_label'], 'When a record is created')
        self.assertIn('Workflow T11 Alpha', row['scope_summary'])
        self.service.activate(second.id, True, True)
        self.assertTrue(second.enabled)
        events = lambda w: self.env['pb.workflow.event'].search([('workflow_id', '=', w.id)])
        alpha = self.env['res.partner'].with_user(self.admin).create({'name': 'Workflow T11 Alpha', 'company_id': self.company.id})
        beta = self.env['res.partner'].with_user(self.admin).create({'name': 'Workflow T11 Beta', 'company_id': self.company.id})
        self.assertEqual(events(first).mapped('source_id'), alpha.ids)
        self.assertEqual(events(second).mapped('source_id'), beta.ids)
        copy_, d3 = self.workflow([self.todo('other')], model='res.partner', trigger='created')
        d3['scope'] = self.rule('name', 'Workflow T11 Alpha'); self.publish(copy_, d3, False)
        with self.assertRaises(UserError) as caught:
            self.service.activate(copy_.id, True, True)
        self.assertIn('exactly the same records and event', str(caught.exception))

    def timing_workflow(self, grouped):
        leaf = {'field': 'name', 'op': 'eq', 'value': 'New'}
        pick = {'id': 'pick', 'type': 'branch', 'title': 'Pick', 'stage': 0, 'branches': [
            {'id': 'p_new', 'label': 'New name', 'condition': {'match': 'all', 'rules': [leaf]} if grouped else leaf, 'steps': ['a']},
            {'id': 'p_other', 'label': 'Otherwise', 'steps': ['b']}]}
        w, d = self.workflow([self.todo('first')], model='res.partner')
        d['nodes'] += [pick, self.todo('a'), self.todo('b')]
        d['order'].append('pick')
        self.publish(w, d)
        return w

    def path_after_change(self, w):
        source = self.env['res.partner'].create({'name': 'Old', 'company_id': self.company.id})
        run = self.start(w, source)
        source.name = 'New'
        self.service.answer(run.step_ids.filtered(lambda s: s.key == 'first').id, {})
        return run.step_ids.filtered(lambda s: s.key == 'pick').choice

    def test_t12_one_timing_rule_for_path_decisions(self):
        flat, grouped = self.timing_workflow(False), self.timing_workflow(True)
        self.assertEqual(flat.published_id.definition['timing'], 'live')
        self.assertEqual(self.path_after_change(flat), 'p_new')
        self.assertEqual(self.path_after_change(grouped), 'p_new')
        # A version published before the rule existed keeps its start snapshot.
        old = self.timing_workflow(False)
        self.env.cr.execute("UPDATE pb_workflow_version SET definition = definition - 'timing' WHERE id = %s", [old.published_id.id])
        old.published_id.invalidate_recordset()
        self.assertNotIn('timing', old.published_id.definition)
        self.assertEqual(self.path_after_change(old), 'p_other')

    def test_t13_drafts_are_refused_by_code_not_wording(self):
        w, d = self.workflow([self.todo('late', stage=1), self.todo('early', stage=0)])
        self.assertIn('section_order', [i['code'] for i in D.validate(d)])
        with self.assertRaises(UserError):
            self.service.save_draft(w.id, w.revision, d)
        unfinished = self.form()
        unfinished['form']['fields'] = []
        email = {'id': 'message', 'type': 'email', 'title': 'Message', 'stage': 0, 'purpose': 'Later'}
        w2, d2 = self.workflow([unfinished, email])
        result = self.service.save_draft(w2.id, w2.revision, d2)
        codes = [i['code'] for i in result['issues']]
        self.assertIn('form_empty', codes)
        self.assertIn('email_needs_template', codes)
        self.assertEqual(w2.draft['timing'], 'live')
        self.assertTrue(all(i.get('code') for i in result['issues']))

    def test_t14_healthy_path_keeps_moving_beside_a_failed_one(self):
        leaver = self.person('Workflow T14 owner', ['base.group_user'])
        group = {'id': 'both', 'type': 'parallel', 'title': 'Together', 'stage': 0, 'join': 'all', 'branches': [
            {'id': 'p_task', 'label': 'Task', 'steps': ['task']},
            {'id': 'p_wait', 'label': 'Wait', 'steps': ['pause']}]}
        w, d = self.workflow([group])
        d['nodes'] += [self.todo('task', owner={'kind': 'user', 'id': leaver.id}),
                       {'id': 'pause', 'type': 'wait', 'title': 'Pause', 'stage': 0, 'hours': 1}]
        self.publish(w, d)
        leaver.write({'active': False})
        run = self.start(w)
        self.assertEqual(run.state, 'failed')
        self.assertEqual(run.step_ids.filtered(lambda s: s.key == 'task').state, 'failed')
        pause = self.wake(run, 'pause')
        self.assertEqual(pause.state, 'waiting')
        self.service._cron_workflows()
        self.assertEqual(pause.state, 'done')
        self.assertEqual(run.state, 'failed')

    def test_t15_new_process_approval_needs_a_route_before_activation(self):
        w, d = self.workflow([{'id': 'approval', 'type': 'matrix', 'title': 'Sign off', 'stage': 0}])
        self.publish(w, d, False)
        with self.assertRaises(UserError) as caught:
            self.service.activate(w.id, True)
        self.assertIn('Set up who approves this in Approval Matrix', str(caught.exception))
        self.assertFalse(w.enabled)
        self.approval_route(w)
        self.service.activate(w.id, True)
        self.assertTrue(w.enabled)
