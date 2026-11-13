"""Workflow contracts: real ORM, permissions, durable execution and native hooks."""
import copy
import json
import os
import re
import uuid
from datetime import timedelta
from unittest.mock import patch
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
        self.assertNotIn('execution_user_id', run._fields)  # dropped in WF2 P6a (R3)
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

    # ------------------------------------------------------------------
    # WORKFLOW-2 phase 2: the module contract, "already happens" and its
    # double-up warnings, user-made stages, gates and the person a record
    # is about.
    # ------------------------------------------------------------------
    CLAIM = 'pb.expense.claim'
    # A user-visible sentence never names the framework, a model or a field.
    BANNED = re.compile(r'odoo|\bhr\.|\bpb\.|\bres\.|\w+_id\b|\bstate\b|\bmodel\b', re.I)

    def need(self, *models):
        for model in models:
            if model not in self.env:
                self.skipTest('%s is not installed' % model)

    def recruiter(self, admin=False):
        groups = [self.env.ref('hr_recruitment.group_hr_recruitment_manager').id]
        if admin:
            groups.append(self.env.ref('pb_hiring.group_hiring_admin').id)
        self.admin.write({'group_ids': [(4, g) for g in groups]})

    def expense_access(self, *users):
        group = self.env.ref('hr_expense.group_hr_expense_user')
        for user in users or (self.admin,):
            user.write({'group_ids': [(4, group.id)]})

    def employee(self, name, user=None, **vals):
        return self.env['hr.employee'].create(dict(
            {'name': name, 'company_id': self.company.id, 'user_id': user.id if user else False}, **vals))

    def claim(self, state='draft', employee=None, **vals):
        """A claim at a status, moved the way the approval route moves it
        (test fixture only; Studio code never does this)."""
        record = self.env[self.CLAIM].create(dict(
            {'employee_id': (employee or self.employee('WF2 P2 claimant')).id, 'company_id': self.company.id}, **vals))
        path = {'draft': [], 'submitted': ['submitted'], 'approved': ['submitted', 'approved'],
                'paid': ['submitted', 'approved', 'paid'], 'refused': ['submitted', 'refused']}[state]
        for step in path:
            record._chain_engine_write(step)
        return record

    def staged(self, model, sections, nodes, trigger='manual'):
        """A workflow whose sections after "Start" are (name, bind or None)."""
        w, d = self.workflow([], model=model, trigger=trigger)
        d['stages'] = [{'name': 'Start'}] + [dict({'name': name}, **({'bind': bind} if bind else {}))
                                             for name, bind in sections]
        for node in nodes:
            d['nodes'].append(node)
            d['order'].append(node['id'])
        return w, d

    def user_stage(self, name, anchor='approved', model=None, workflow=None, **values):
        model = self.CLAIM if model is None else model
        catalogue = self.service.stage_create(model, workflow.id if workflow else None,
                                              dict({'name': name, 'anchor_value': anchor if model else False}, **values))
        key = next(s['key'] for s in catalogue['stages'] if s['kind'] == 'yours' and s['name'] == name)
        return self.env['pb.workflow.stage'].browse(key)

    def yours(self, stage):
        return {'kind': 'yours', 'id': stage.id}

    def core(self, value):
        return {'kind': 'core', 'value': value}

    def positions(self, model, record_id):
        return self.env['pb.workflow.record.stage'].search([('res_model', '=', model), ('res_id', '=', record_id)])

    def test_wf2p2_t1_contracts_load_in_plain_words(self):
        self.need(self.CLAIM, 'hr.leave', 'pb.hiring')
        self.recruiter()
        expected = {self.CLAIM: {'refused'}, 'hr.leave': {'refuse', 'cancel'}}
        for model in (self.CLAIM, 'hr.leave', 'hr.applicant'):
            contract = self.service._contract(model)
            self.assertEqual(contract['source'], 'declared', model)
            self.assertTrue(contract['stages'], model)
            for stage in contract['stages']:
                self.assertTrue(stage['name'].strip(), stage)
                self.assertTrue(stage['enters'].strip(), stage)
            exits = [s['exit'] for s in contract['stages']]
            self.assertEqual(exits, sorted(exits), 'exits come last')
            found = {str(s['key']) for s in contract['stages'] if s['exit']}
            if model in expected:
                self.assertEqual(found, expected[model])
            else:
                self.assertIn('cv_reject', found)
                self.assertNotIn('joined', found)
            texts = [contract['label'], contract['area']] + [s['name'] for s in contract['stages']] + \
                [s['enters'] for s in contract['stages']]
            for row in self.service.existing_behaviour(model):
                if row['source'] in ('area', 'approvals'):
                    texts += [row['text'], row['owner'], row.get('detail', '')]
            for spec in self.service._actions(model).values():
                texts += [spec['label']] + [p.get('label', '') + ' ' + p.get('error', '') for p in spec.get('params', [])]
            for text in texts:
                self.assertFalse(self.BANNED.search(text or ''), '%s: %s' % (model, text))
        self.assertEqual([s['key'] for s in self.service._contract(self.CLAIM)['stages']],
                         ['draft', 'submitted', 'approved', 'paid', 'refused'])
        self.assertTrue(self.service._contract('hr.leave')['submits_itself'])
        meta = self.service.metadata(self.CLAIM)
        self.assertTrue(meta['contract']['has_subject'])
        self.assertEqual(meta['contract']['stage_field'], 'state')
        self.assertTrue(meta['stage_catalogue']['stages'])
        self.assertTrue(meta['record_stages'], 'the shipped key stays')

    def test_wf2p2_t2_record_type_without_contract_is_discovered(self):
        # WF2 P3b gave "Other request" a declared contract, so the
        # discovered case is shown on another record type with a status.
        model = next((m for m in ('pb.hr.letter', 'pb.journey.case', 'hr.payslip')
                      if m in self.env and self.service._contract(m)['source'] == 'discovered'
                      and self.service._contract(m)['stages']), None)
        if not model:
            self.skipTest('no record type with a discovered status here')
        contract = self.service._contract(model)
        self.assertEqual(contract['source'], 'discovered')
        self.assertEqual(contract['stage_field'], 'state')
        self.assertIn('draft', [s['key'] for s in contract['stages']])
        self.assertTrue(all(not s['enters'] for s in contract['stages']))
        partner = self.service._contract('res.partner')
        self.assertEqual((partner['source'], partner['stages']), ('discovered', []))
        catalogue = self.service.stage_catalogue(model)
        self.assertTrue(catalogue['stages'])
        self.assertTrue(all(s['kind'] == 'core' and s['locked'] for s in catalogue['stages']))
        self.assertEqual(self.service._actions('res.partner'), {})

    def test_wf2p2_t3_hiring_move_through_the_contract(self):
        self.need('pb.hiring')
        from unittest.mock import patch
        self.recruiter()
        Stage = self.env['hr.recruitment.stage']
        screening, shortlist = Stage._pb_stage('screening'), Stage._pb_stage('shortlist')
        applicant = self.env['hr.applicant'].create({'partner_name': 'WF2 P2 T3 candidate',
                                                     'company_id': self.company.id, 'stage_id': screening.id})
        move = {'id': 'move', 'type': 'action', 'title': 'Shortlist', 'stage': 0,
                'action_key': 'hiring.stage', 'stage_key': 'shortlist'}
        w, d = self.workflow([move], model='hr.applicant')
        self.publish(w, d)
        # Hiring's own rule dispatcher (the board's "enters a stage" hook).
        Rule = type(self.env['pb.hiring.automation.rule'])
        fired, real = [], Rule._fire

        def spy(rules, event, *args, **kwargs):
            fired.append(event)
            return real(rules, event, *args, **kwargs)
        with patch.object(Rule, '_fire', spy):
            run = self.start(w, applicant)
        self.assertEqual(run.state, 'done', run.step_ids.mapped('error'))
        self.assertEqual(applicant.stage_id, shortlist)
        self.assertEqual(fired.count('stage_entered'), 1)
        self.assertEqual(run.step_ids.filtered(lambda s: s.key == 'move').state, 'done')
        joined = dict(move, stage_key='joined')
        w2, d2 = self.workflow([joined], model='hr.applicant')
        self.assertIn('bad_hiring_stage', [i['code'] for i in self.service._validate(w2, d2)])
        with self.assertRaises(UserError):
            applicant.with_env(run._service().env)._workflow_execute('hiring.stage', {'stage_key': 'joined'})
        choices = [o['key'] for o in self.service.metadata('hr.applicant')['actions']['hiring.stage']['params'][0]['options']]
        self.assertIn('shortlist', choices)
        self.assertNotIn('joined', choices)

    def test_wf2p2_t4_shared_stage_rename_keeps_lock_revision_and_permission(self):
        self.need('pb.hiring')
        self.recruiter()
        stage = self.env['hr.recruitment.stage'].search([('pb_key', '!=', False)], limit=1)
        with self.assertRaises(AccessError):
            self.service.stage_rename_shared('hr.applicant', stage.pb_key, 'Renamed', str(stage.write_date))
        self.recruiter(admin=True)
        count = self.env['hr.recruitment.stage'].search_count([])
        catalogue = self.service.stage_rename_shared('hr.applicant', stage.pb_key, 'Contract renamed stage', str(stage.write_date))
        self.assertEqual(stage.name, 'Contract renamed stage')
        self.assertEqual(self.env['hr.recruitment.stage'].search_count([]), count)
        self.assertIn('Contract renamed stage', [s['name'] for s in catalogue['stages']])
        with self.assertRaises(UserError):
            self.service.stage_rename_shared('hr.applicant', stage.pb_key, 'Stale edit', 'old')
        with self.assertRaises(AccessError):
            self.service.with_user(self.staff).stage_rename_shared('hr.applicant', stage.pb_key, 'No', str(stage.write_date))
        self.need(self.CLAIM)
        with self.assertRaises(UserError):
            self.service.stage_rename_shared(self.CLAIM, 'draft', 'Not ours', '')

    def test_wf2p2_t5_existing_behaviour_for_leave_and_expense(self):
        self.need(self.CLAIM, 'hr.leave')
        area = [e for e in self.service.existing_behaviour('hr.leave') if e['source'] == 'area']
        shapes = {(e['stage'], e['kind'], e['audience']) for e in area}
        for shape in (('confirm', 'todo', 'approver'), ('validate', 'message', 'requester'),
                      ('refuse', 'message', 'requester'), ('validate', 'change', 'requester')):
            self.assertIn(shape, shapes)
        process = self.env['biz.approval.process']._by_key('expense')
        self.approval_route(process=process)
        rows = [e for e in self.service.existing_behaviour(self.CLAIM) if e['source'] == 'approvals']
        route = next(e for e in rows if e['kind'] == 'change')
        self.assertEqual(route['stage'], 'submitted')
        self.assertIn('Workflow test approval route', route['text'])
        self.assertIn(self.staff.name, route['text'])
        self.assertTrue(route.get('detail'))
        self.assertEqual((route['settings'] or {}).get('action'), 'pb_approval_config.action_pb_approval_matrix')
        shapes = {(e['stage'], e['kind'], e['audience']) for e in rows}
        for shape in (('submitted', 'message', 'approver'), ('submitted', 'reminder', 'approver')):
            self.assertIn(shape, shapes)
        # WF2 P2b (D6): Expenses tells the employee "approved" and "refused"
        # itself now, so the route's own copy is no longer listed; the
        # area's rows say it (and a repeat email step is still warned about).
        # WF2 P5a (D28): "sent back" too.
        for shape in (('approved', 'message', 'requester'), ('refused', 'message', 'requester'),
                      ('draft', 'message', 'requester')):
            self.assertNotIn(shape, shapes)
        own = {(e['stage'], e['kind'], e['audience']) for e in self.service.existing_behaviour(self.CLAIM)
               if e['source'] == 'area'}
        for shape in (('approved', 'message', 'requester'), ('refused', 'message', 'requester'),
                      ('paid', 'message', 'requester'), ('draft', 'message', 'requester')):
            self.assertIn(shape, own)
        self.env['biz.approval.binding'].search([('company_id', '=', self.company.id),
                                                 ('process_id', '=', process.id)]).write({'active': False})
        rows = [e for e in self.service.existing_behaviour(self.CLAIM) if e['source'] == 'approvals']
        self.assertEqual([e['text'] for e in rows], ['No approval route is set up for this yet.'])

    def test_wf2p2_t6_hiring_rules_are_listed_while_switched_on(self):
        self.need('pb.hiring')
        self.recruiter()
        shortlist = self.env['hr.recruitment.stage']._pb_stage('shortlist')
        rule = self.env['pb.hiring.automation.rule'].create({
            'company_id': self.company.id, 'event': 'stage_entered', 'stage_id': shortlist.id,
            'action': 'todo', 'recipient': 'recruiter', 'todo_text': 'WF2 P2 first look'})
        ref = 'hiring_rule:%s' % rule.id
        hit = [e for e in self.service.existing_behaviour('hr.applicant') if e.get('ref') == ref]
        self.assertEqual(len(hit), 1)
        self.assertEqual((hit[0]['stage'], hit[0]['kind'], hit[0]['source']), ('shortlist', 'todo', 'area'))
        self.assertIn('WF2 P2 first look', hit[0]['text'])
        rule.active = False
        self.assertFalse([e for e in self.service.existing_behaviour('hr.applicant') if e.get('ref') == ref])

    def test_wf2p2_t7_studio_rules_are_not_existing_automation(self):
        first, d1 = self.workflow([self.todo('do')], model='res.partner', trigger='created')
        self.publish(first, d1)
        generated = first.automation_id
        self.assertTrue(generated)
        second, d2 = self.workflow([self.todo('do')], model='res.partner', trigger='created')
        self.service.save_draft(second.id, second.revision, d2)
        review = self.service.review(second.id)
        self.assertNotIn(generated.id, [a['id'] for a in review['automations']])
        self.assertIn(first.id, [w['id'] for w in review['other_workflows']])
        self.assertNotIn(generated.id, [a['id'] for a in self.service.metadata('res.partner')['automations']])
        rows = self.service.existing_behaviour('res.partner')
        self.assertNotIn('rule:%s' % generated.id, [e.get('ref') for e in rows])
        self.assertTrue(any(e['source'] == 'workflow' and (e['settings'] or {}).get('workflow_id') == first.id for e in rows))

    def test_wf2p2_t8_repeat_warning_and_same_path_templates(self):
        self.need('hr.leave')
        template = self.env['mail.template'].create({
            'name': 'WF2 leave note', 'model_id': self.env['ir.model']._get_id('hr.leave'),
            'subject': 'Leave', 'body_html': '<p>Leave</p>'})
        tell = {'id': 'tell', 'type': 'email', 'title': 'Tell them', 'stage': 1,
                'template_id': template.id, 'purpose': 'A friendly extra note'}
        w, d = self.staged('hr.leave', [('Approved', self.core('validate'))], [tell])
        issues = self.service._validate(w, d)
        warnings = [i for i in issues if i['code'] == 'repeats_existing']
        self.assertEqual(len(warnings), 1, issues)
        self.assertEqual((warnings[0]['id'], warnings[0]['severity'], warnings[0]['acknowledged']), ('tell', 'warning', False))
        self.assertIn('Time off', warnings[0]['text'])
        self.assertFalse([i for i in issues if i['severity'] == 'error'], issues)
        self.service.save_draft(w.id, w.revision, d)
        self.assertEqual(self.service.review(w.id)['blocking'], 1)
        with self.assertRaises(UserError) as caught:
            self.service.publish(w.id, w.revision)
        self.assertIn('already does this here', str(caught.exception))
        d['nodes'][1]['ack_repeat'] = True
        self.service.save_draft(w.id, w.revision, d)
        review = self.service.review(w.id)
        self.assertEqual(review['blocking'], 0)
        self.assertTrue(next(i for i in review['issues'] if i['code'] == 'repeats_existing')['acknowledged'])
        self.service.publish(w.id, w.revision)
        self.assertTrue(w.published_id)
        # The same message on two exclusive paths is fine; twice on one path is not.
        message = self.env['mail.template'].create({
            'name': 'WF2 partner note', 'model_id': self.env['ir.model']._get_id('res.partner'),
            'subject': 'Hi', 'body_html': '<p>Hi</p>'})
        mail = lambda ident: {'id': ident, 'type': 'email', 'title': ident, 'stage': 0,
                              'template_id': message.id, 'purpose': 'Extra'}
        pick = {'id': 'pick', 'type': 'branch', 'title': 'Pick', 'stage': 0, 'branches': [
            {'id': 'p_a', 'label': 'Named', 'condition': self.rule('name', 'X'), 'steps': ['a']},
            {'id': 'p_b', 'label': 'Otherwise', 'steps': ['b']}]}
        wb, db = self.workflow([pick], model='res.partner')
        db['nodes'] += [mail('a'), mail('b')]
        self.assertNotIn('duplicate_email', [i['code'] for i in self.service._validate(wb, db)])
        ws, ds = self.workflow([mail('a'), mail('b')], model='res.partner')
        self.assertIn('duplicate_email', [i['code'] for i in self.service._validate(ws, ds)])
        both = {'id': 'both', 'type': 'parallel', 'title': 'Both', 'stage': 0, 'join': 'all', 'branches': [
            {'id': 'q_a', 'label': 'One', 'steps': ['a']}, {'id': 'q_b', 'label': 'Two', 'steps': ['b']}]}
        wp, dp = self.workflow([both], model='res.partner')
        dp['nodes'] += [mail('a'), mail('b')]
        self.assertIn('duplicate_email', [i['code'] for i in self.service._validate(wp, dp)])

    def test_wf2p2_t9_user_made_stages_lifecycle_permission_and_company(self):
        self.need(self.CLAIM)
        stage = self.user_stage('Payment scheduled')
        catalogue = self.service.stage_catalogue(self.CLAIM)
        order = [s['key'] for s in catalogue['stages']]
        self.assertEqual(order, ['draft', 'submitted', 'approved', stage.id, 'paid', 'refused'])
        row = next(s for s in catalogue['stages'] if s['kind'] == 'yours')
        self.assertEqual((row['counts_as'], row['count'], row['locked']), ('Approved', 0, False))
        self.assertTrue(row['enters'])
        self.service.stage_update(stage.id, {'name': 'Payment booked', 'target_hours': 24})
        self.assertEqual((stage.name, stage.target_hours), ('Payment booked', 24))
        catalogue = self.service.stage_reorder(self.CLAIM, None, ['draft', 'submitted', stage.id, 'approved', 'paid'])
        self.assertEqual(stage.anchor_value, 'submitted')
        with self.assertRaises(UserError):
            self.service.stage_reorder(self.CLAIM, None, ['submitted', 'draft', stage.id, 'approved', 'paid'])
        self.service.stage_reorder(self.CLAIM, None, ['draft', 'submitted', 'approved', stage.id, 'paid'])
        with self.assertRaises(UserError):
            self.service.stage_create(self.CLAIM, None, {'name': 'After refusal', 'anchor_value': 'refused'})
        with self.assertRaises(UserError):
            self.service.stage_create(self.CLAIM, None, {'name': 'Payment booked', 'anchor_value': 'approved'})
        with self.assertRaises(AccessError):
            self.service.with_user(self.staff).stage_create(self.CLAIM, None, {'name': 'Mine', 'anchor_value': 'approved'})
        with self.assertRaises(AccessError):
            stage.with_user(self.admin).write({'name': 'Direct'})
        # Not removable while a record is in it, nor while a workflow waits for it.
        claim = self.claim('approved')
        self.service._set_position(self.CLAIM, claim.id, stage, self.company)
        with self.assertRaises(UserError):
            self.service.stage_delete(stage.id)
        claim._chain_engine_write('paid')
        w, d = self.staged(self.CLAIM, [('Booked', self.yours(stage))], [self.todo('pay', stage=1)])
        self.publish(w, d)
        with self.assertRaises(UserError) as caught:
            self.service.stage_delete(stage.id)
        self.assertIn(w.name, str(caught.exception))
        self.service.activate(w.id, False)
        self.service.stage_delete(stage.id)
        self.assertFalse(stage.active)
        # Another company neither sees nor uses it.
        kept = self.user_stage('Kept here')
        other = self.env['res.company'].create({'name': 'WF2 P2 other company'})
        self.admin.write({'company_ids': [(4, other.id)]})
        elsewhere = self.service.with_company(other)
        with self.assertRaises(AccessError):
            elsewhere.stage_update(kept.id, {'name': 'Taken over'})
        self.assertNotIn(kept.id, [s['key'] for s in elsewhere.stage_catalogue(self.CLAIM)['stages']])
        self.assertFalse(self.env['pb.workflow.stage'].with_user(self.admin).with_context(
            allowed_company_ids=[other.id]).search([('id', '=', kept.id)]))

    def test_wf2p2_t10_section_bindings_are_checked_by_code(self):
        self.need(self.CLAIM)
        stage = self.user_stage('Payment scheduled')

        def codes(sections):
            w, d = self.staged(self.CLAIM, sections, [])
            return [i['code'] for i in self.service._validate(w, d)]
        self.assertIn('bind_unknown', codes([('Nowhere', self.core('nope'))]))
        self.assertIn('bind_unknown', codes([('Gone', {'kind': 'yours', 'id': 999999999})]))
        self.assertIn('bind_unknown', codes([('Bad', 'approved')]))
        self.assertIn('bind_exit', codes([('Refused', self.core('refused'))]))
        self.assertIn('bind_order', codes([('Approved', self.core('approved')), ('Waiting', self.core('submitted'))]))
        self.assertIn('bind_order', codes([('Scheduled', self.yours(stage)), ('Approved', self.core('approved'))]))
        self.assertIn('bind_duplicate', codes([('A', self.core('approved')), ('B', self.core('approved'))]))
        self.assertEqual(codes([('Heading', None), ('Approved', self.core('approved')), ('Another heading', None),
                                ('Scheduled', self.yours(stage)), ('Paid', self.core('paid'))]), [])
        w, d = self.staged('', [('Wrong', self.core('approved'))], [])
        self.assertIn('bind_unknown', [i['code'] for i in self.service._validate(w, d)])

    def test_wf2p2_t11_core_gate_waits_proceeds_and_stops(self):
        self.need(self.CLAIM)
        self.expense_access()
        w, d = self.staged(self.CLAIM, [('Waiting approval', self.core('submitted'))], [self.todo('check', stage=1)])
        self.publish(w, d)
        claim = self.claim('draft')
        run = self.start(w, claim)
        check = run.step_ids.filtered(lambda s: s.key == 'check')
        self.assertEqual((run.state, check.state), ('waiting', 'pending'))
        self.assertEqual(run.gate.get('section'), 1)
        self.assertIn('Waiting for this to reach', self.service.progress(run.id)['gate']['reason'])
        self.service._cron_workflows()
        self.service._cron_workflows()
        self.assertEqual(len(run.log_ids.filtered(lambda l: 'Waiting for this to reach' in l.message)), 1)
        claim._chain_engine_write('submitted')
        self.service._cron_workflows()
        self.assertEqual(check.state, 'waiting', check.error)
        early = self.start(w, self.claim('approved'))
        self.assertEqual(early.step_ids.filtered(lambda s: s.key == 'check').state, 'waiting')
        w2, d2 = self.staged(self.CLAIM, [('Approved', self.core('approved'))], [self.todo('pay', stage=1)])
        self.publish(w2, d2)
        pending = self.claim('submitted')
        stopped = self.start(w2, pending)
        self.assertEqual(stopped.state, 'waiting')
        pending._chain_engine_write('refused')
        self.service._cron_workflows()
        self.assertEqual(stopped.state, 'cancelled')
        self.assertTrue(any('Stopped: the record is now' in l.message for l in stopped.log_ids))
        self.assertEqual(pending.state, 'refused')

    def test_wf2p2_t12_auto_stage_writes_only_its_own_position(self):
        self.need(self.CLAIM)
        self.expense_access()
        stage = self.user_stage('Payment scheduled')
        w, d = self.staged(self.CLAIM, [('Scheduled', self.yours(stage))], [self.todo('pay', stage=1)])
        self.publish(w, d)
        claim = self.claim('approved')
        run = self.start(w, claim)
        self.assertEqual(run.step_ids.filtered(lambda s: s.key == 'pay').state, 'waiting')
        self.assertEqual(self.positions(self.CLAIM, claim.id).stage_id, stage)
        current = self.service.record_stage(self.CLAIM, claim.id)['current']
        self.assertEqual((current['kind'], current['key']), ('yours', stage.id))
        self.assertEqual(claim.state, 'approved')
        self.assertTrue(run.log_ids.filtered(lambda l: l.stage_id == stage))
        # No workflow code writes a record's status: Studio's files and the
        # three areas' contract files (P1's guard, extended).
        from odoo.modules.module import get_module_path
        files = [os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', name)
                 for name in ('workflow_contract.py', 'workflow_stage.py', 'workflow_models.py', 'workflow_studio.py',
                              'workflow_progress.py', 'workflow_record_context.py')]
        for module in ('pb_me_expense', 'pb_timeoff', 'pb_hiring'):
            path = get_module_path(module)
            if path:
                files.append(os.path.join(path, 'models', 'workflow_contract.py'))
        offenders = []
        for path in files:
            text = open(path, encoding='utf-8').read()
            text = re.sub(r'\n    def _execute_action\(.*?(?=\n    (?:@|def ))', '\n', text, flags=re.S)
            for number, line in enumerate(text.splitlines(), 1):
                if re.search(r'\b(source|record|records|rec|self)\b\.(state|stage_id)\s*=[^=]', line) or \
                        re.search(r'\b(source|record|records|rec)\b(\.\w+\([^)]*\))*\.write\(', line) or \
                        re.search(r'_chain_(engine|state)_write|_advance_state\(|action_approve\(|action_refuse\(', line):
                    offenders.append('%s:%s %s' % (os.path.basename(path), number, line.strip()))
        self.assertEqual(offenders, [])

    def test_wf2p2_t13_person_stage_right_person_designer_and_status(self):
        self.need(self.CLAIM)
        self.expense_access()
        owner = self.staff
        stage = self.user_stage('Ready to pay', enter='person', enter_owner={'kind': 'user', 'id': owner.id})
        w, d = self.staged(self.CLAIM, [('Ready', self.yours(stage))], [self.todo('pay', stage=1)])
        self.publish(w, d)
        claim = self.claim('approved', employee=self.employee('WF2 T13 claimant', user=owner))
        run = self.start(w, claim)
        pay = run.step_ids.filtered(lambda s: s.key == 'pay')
        self.assertEqual((run.state, pay.state), ('waiting', 'pending'))
        self.assertIn(owner.name, run.gate['reason'])
        wrong = self.person('Workflow T13 wrong', ['base.group_user'])
        self.expense_access(wrong)
        with self.assertRaises(AccessError):
            self.service.with_user(wrong).move_record_stage(self.CLAIM, claim.id, stage.id)
        self.assertFalse(self.positions(self.CLAIM, claim.id))
        result = self.service.with_user(owner).move_record_stage(self.CLAIM, claim.id, stage.id)
        self.assertEqual((result['current']['key'], result['current']['by']), (stage.id, owner.name))
        self.assertEqual(pay.state, 'waiting', pay.error)
        designer = self.person('Workflow T13 designer', ['base.group_user', 'pb_lifecycle.group_workflow_designer'])
        self.expense_access(designer)
        other = self.claim('approved')
        self.service.with_user(designer).move_record_stage(self.CLAIM, other.id, stage.id)
        self.assertEqual(self.positions(self.CLAIM, other.id).stage_id, stage)
        early = self.claim('submitted')
        with self.assertRaises(UserError):
            self.service.move_record_stage(self.CLAIM, early.id, stage.id)
        auto = self.user_stage('Booked automatically')
        with self.assertRaises(UserError):
            self.service.move_record_stage(self.CLAIM, self.claim('approved').id, auto.id)

    def test_wf2p2_t14_rule_stage_waits_until_the_rule_is_true(self):
        self.need(self.CLAIM)
        self.expense_access()
        stage = self.user_stage('Noted', enter='rule', enter_rule={'match': 'all', 'rules': [{'field': 'note', 'op': 'set'}]})
        with self.assertRaises(UserError):
            self.user_stage('Broken rule', enter='rule', enter_rule={'match': 'all', 'rules': [{'field': 'no_such_field', 'op': 'set'}]})
        w, d = self.staged(self.CLAIM, [('Noted', self.yours(stage))], [self.todo('after', stage=1)])
        self.publish(w, d)
        claim = self.claim('approved')
        run = self.start(w, claim)
        after = run.step_ids.filtered(lambda s: s.key == 'after')
        self.assertEqual(after.state, 'pending')
        self.service._cron_workflows()
        self.assertEqual(after.state, 'pending')
        self.assertFalse(self.positions(self.CLAIM, claim.id))
        claim.note = 'Paid by bank transfer'
        self.service._cron_workflows()
        self.assertEqual(after.state, 'waiting', after.error)
        self.assertEqual(self.positions(self.CLAIM, claim.id).stage_id, stage)

    def test_wf2p2_t15_position_is_dropped_when_the_status_moves_on(self):
        self.need(self.CLAIM)
        self.expense_access()
        stage = self.user_stage('Payment scheduled')
        w, d = self.staged(self.CLAIM, [('Scheduled', self.yours(stage))], [self.todo('pay', stage=1)])
        self.publish(w, d)
        claim = self.claim('approved')
        run = self.start(w, claim)
        self.assertEqual(len(self.positions(self.CLAIM, claim.id)), 1)
        claim._chain_engine_write('paid')
        current = self.service.record_stage(self.CLAIM, claim.id)['current']
        self.assertEqual((current['kind'], current['key']), ('core', 'paid'))
        self.assertFalse(self.positions(self.CLAIM, claim.id))
        self.assertTrue(any('moved on' in l.message for l in run.log_ids))

    def test_wf2p2_t16_record_stage_track_never_invents_history(self):
        self.need(self.CLAIM)
        self.expense_access()
        stage = self.user_stage('Payment scheduled')
        w, d = self.staged(self.CLAIM, [('Scheduled', self.yours(stage))], [self.todo('pay', stage=1)])
        self.publish(w, d)
        track = lambda claim: [(r['key'], r['state']) for r in self.service.record_stage(self.CLAIM, claim.id)['track']]
        entered = self.claim('approved')
        self.start(w, entered)
        self.assertEqual(track(entered), [('draft', 'done'), ('submitted', 'done'), ('approved', 'done'),
                                          (stage.id, 'here'), ('paid', 'later')])
        data = self.service.record_stage(self.CLAIM, entered.id)
        self.assertEqual(([e['key'] for e in data['exits']], data['exits'][0]['here'], data['approval_at']),
                         (['refused'], False, 'submitted'))
        entered._chain_engine_write('paid')
        self.assertEqual(track(entered)[3:], [(stage.id, 'done'), ('paid', 'here')])
        skipped = self.claim('paid')
        self.assertEqual(track(skipped)[3:], [(stage.id, 'passed'), ('paid', 'here')])
        refused = self.claim('refused')
        data = self.service.record_stage(self.CLAIM, refused.id)
        self.assertEqual({r['state'] for r in data['track']}, {'stopped'})
        self.assertEqual([e['here'] for e in data['exits']], [True])
        self.assertTrue(data['current']['exit'])
        self.need('hr.leave')
        leave_track = self.service._contract('hr.leave')['stages']
        self.assertTrue(next(s for s in leave_track if s['key'] == 'validate1')['optional'])

    def test_wf2p2_t17_subject_owner_and_the_areas_own_manager(self):
        self.need(self.CLAIM)
        self.expense_access()
        line_user = self.person('Workflow T17 line manager', ['base.group_user'])
        expense_user = self.person('Workflow T17 expense approver', ['base.group_user'])
        self.expense_access(line_user, expense_user)
        line = self.employee('WF2 T17 line', user=line_user)
        claimant = self.employee('WF2 T17 claimant', user=self.staff, parent_id=line.id, expense_manager_id=expense_user.id)
        w, d = self.workflow([self.todo('boss', owner={'kind': 'manager'}), self.todo('mine', owner={'kind': 'subject'})], model=self.CLAIM)
        self.publish(w, d)
        run = self.start(w, self.claim(employee=claimant))
        boss = run.step_ids.filtered(lambda s: s.key == 'boss')
        self.assertEqual(boss.assignee_id, expense_user, boss.error)
        self.service.with_user(expense_user).answer(boss.id, {})
        mine = run.step_ids.filtered(lambda s: s.key == 'mine')
        self.assertEqual((mine.state, mine.assignee_id), ('waiting', self.staff), mine.error)
        no_expense_approver = self.employee('WF2 T17 second', parent_id=line.id)
        run2 = self.start(w, self.claim(employee=no_expense_approver))
        self.assertEqual(run2.step_ids.filtered(lambda s: s.key == 'boss').assignee_id, line_user)
        w3, d3 = self.workflow([self.todo('mine', owner={'kind': 'subject'})], model=self.CLAIM)
        self.publish(w3, d3)
        nobody = self.employee('WF2 T17 no login')
        step = self.start(w3, self.claim(employee=nobody)).step_ids.filtered(lambda s: s.key == 'mine')
        self.assertEqual(step.state, 'failed')
        self.assertEqual(step.error, 'WF2 T17 no login has no staff login yet, so this task cannot be given to them.')
        w4, d4 = self.workflow([self.todo('mine', owner={'kind': 'subject'})], model='res.partner')
        self.assertIn('subject_not_available', [i['code'] for i in self.service._validate(w4, d4)])

    def test_wf2p2_t18_date_start_is_recorded_as_the_person_it_is_about(self):
        self.need(self.CLAIM)
        self.expense_access()
        w, d = self.workflow([self.todo('do')], model=self.CLAIM, trigger='date')
        d['trigger'].update(date_field='submitted_on', delay=1, unit='day', mode='after')
        self.publish(w, d)
        self.assertEqual(w.automation_id.trigger, 'on_time')
        system_service = self.env['pb.workflow.studio'].with_user(SUPERUSER_ID).with_company(self.company)
        events = lambda claim: self.env['pb.workflow.event'].search([('workflow_id', '=', w.id), ('source_id', '=', claim.id)])
        theirs = self.claim('submitted', employee=self.employee('WF2 T18 claimant', user=self.staff))
        system_service._capture(w.id, theirs)
        self.assertEqual(events(theirs).initiator_id, self.staff)
        nobody = self.claim('submitted', employee=self.employee('WF2 T18 no login'))
        system_service._capture(w.id, nobody)
        self.assertEqual(events(nobody).initiator_id.id, SUPERUSER_ID)
        person = self.claim('submitted', employee=self.employee('WF2 T18 by a person', user=self.person('Workflow T18 owner', ['base.group_user'])))
        self.service._capture(w.id, person)
        self.assertEqual(events(person).initiator_id, self.admin)

    def test_wf2p2_t19_new_process_stages_live_on_the_run(self):
        w, d = self.staged('', [], [])
        checked = self.user_stage('Checked', model='', workflow=w)
        signed = self.user_stage('Signed off', model='', workflow=w, enter='person',
                                 enter_owner={'kind': 'user', 'id': self.staff.id})
        d['stages'] += [{'name': 'Checked', 'bind': self.yours(checked)}, {'name': 'Signed off', 'bind': self.yours(signed)}]
        for node in (self.todo('check', stage=1, owner={'kind': 'user', 'id': self.staff.id}), self.todo('close', stage=2)):
            d['nodes'].append(node)
            d['order'].append(node['id'])
        self.publish(w, d)
        run = self.start(w)
        steps = {s.key: s for s in run.step_ids}
        self.assertEqual(steps['check'].state, 'waiting', steps['check'].error)
        self.assertEqual(self.positions('pb.workflow.run', run.id).stage_id, checked)
        staff = self.service.with_user(self.staff)
        staff.answer(steps['check'].id, {})
        self.assertEqual((run.state, steps['close'].state), ('waiting', 'pending'))
        result = staff.move_record_stage('pb.workflow.run', run.id, signed.id)
        self.assertEqual(result['current']['key'], signed.id)
        self.assertEqual([r['state'] for r in result['track']], ['done', 'here'])
        self.assertEqual(steps['close'].state, 'waiting', steps['close'].error)
        self.service.answer(steps['close'].id, {})
        self.assertEqual(run.state, 'done')

    def test_wf2p2_t20_paused_route_blocks_activation_of_a_new_process(self):
        w, d = self.workflow([{'id': 'approval', 'type': 'matrix', 'title': 'Sign off', 'stage': 0}])
        self.publish(w, d, False)
        self.approval_route(w)
        self.env['biz.approval.binding'].search([('company_id', '=', self.company.id), ('process_id', '=', w.process_id.id),
                                                 ('active', '=', True)]).write({'mode': 'paused'})
        with self.assertRaises(UserError) as caught:
            self.service.activate(w.id, True)
        self.assertIn('The approval route for this is paused', str(caught.exception))
        self.assertFalse(w.enabled)

    # ------------------------------------------------------------ WF2 P3a
    def test_wf2p3a_b1_candidates_keep_their_stages_in_hiring(self):
        self.need('pb.hiring')
        self.recruiter()
        contract = self.service.metadata('hr.applicant')['contract']
        self.assertTrue(contract['own_stage_rows'])
        self.assertFalse(self.service.metadata(self.CLAIM)['contract']['own_stage_rows'] if self.CLAIM in self.env else False)
        with self.assertRaises(UserError) as caught:
            self.service.stage_create('hr.applicant', None, {'name': 'WF2 P3a own row', 'anchor_value': 'screening'})
        self.assertEqual(str(caught.exception), 'Candidate stages are managed in Hiring.')
        self.assertFalse(self.env['pb.workflow.stage'].search([('name', '=', 'WF2 P3a own row')]))
        core = [s['key'] for s in self.service._contract('hr.applicant')['stages'] if not s.get('exit')]
        # A reorder that carries no user-made stage is still accepted; one
        # that carries a user-made stage is refused the same way.
        self.service.stage_reorder('hr.applicant', None, core)
        stray = internal(self.env['pb.workflow.stage']).create({
            'company_id': self.company.id, 'source_model': 'hr.applicant', 'name': 'WF2 P3a stray',
            'anchor_value': core[0]})
        with self.assertRaises(UserError) as caught:
            self.service.stage_reorder('hr.applicant', None, core[:1] + [stray.id] + core[1:])
        self.assertIn('managed in Hiring', str(caught.exception))
        # Headings stay allowed on a candidate workflow.
        w, d = self.staged('hr.applicant', [('Just a heading', None)], [])
        self.service.save_draft(w.id, w.revision, d)
        self.assertFalse([i for i in self.service.review(w.id)['issues'] if i['id'] == 'sections'])

    def test_wf2p3a_b2_no_approval_needed_lane_lists_only_the_route(self):
        self.need(self.CLAIM)
        process = self.env['biz.approval.process']._by_key('expense')
        self.approval_route(process=process, fast=True)
        rows = [e for e in self.service.existing_behaviour(self.CLAIM) if e['source'] == 'approvals']
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual((rows[0]['stage'], rows[0]['kind'], rows[0]['audience']), ('submitted', 'change', 'approver'))
        self.assertIn('No approval needed', rows[0]['text'])
        self.assertFalse([e for e in rows if e['kind'] in ('message', 'reminder')])
        # A route with people still lists its messages and reminders.
        self.approval_route(process=process)
        kinds = {e['kind'] for e in self.service.existing_behaviour(self.CLAIM) if e['source'] == 'approvals'}
        self.assertEqual(kinds, {'change', 'message', 'reminder'})

    def test_wf2p3a_b3_record_stage_says_who_may_move_it_next(self):
        self.need(self.CLAIM)
        self.expense_access()
        owner = self.staff
        stage = self.user_stage('WF2 P3a ready', enter='person', enter_owner={'kind': 'user', 'id': owner.id})
        claim = self.claim('approved', employee=self.employee('WF2 P3a claimant', user=owner))
        wrong = self.person('Workflow P3a wrong', ['base.group_user'])
        self.expense_access(owner, wrong)
        move = self.service.with_user(owner).record_stage(self.CLAIM, claim.id)['next_move']
        self.assertEqual((move['stage_id'], move['allowed'], move['reason']), (stage.id, True, ''))
        move = self.service.with_user(wrong).record_stage(self.CLAIM, claim.id)['next_move']
        self.assertFalse(move['allowed'])
        self.assertEqual(move['reason'], 'Only %s can move this to WF2 P3a ready.' % owner.name)
        # Not yet at its stage, or stopped: nothing to move.
        self.assertIsNone(self.service.record_stage(self.CLAIM, self.claim('submitted').id)['next_move'])
        self.assertIsNone(self.service.record_stage(self.CLAIM, self.claim('refused').id)['next_move'])
        # An automatic stage is never offered.
        auto = self.user_stage('WF2 P3a auto', anchor='paid')
        self.assertIsNone(self.service.record_stage(self.CLAIM, self.claim('paid').id)['next_move'])
        self.assertTrue(auto)

    def test_wf2p3a_b4_workbench_sentence_reads_the_review_filter_words(self):
        w, d = self.workflow(model='res.partner')
        self.assertEqual(self.service.get_workflow(w.id)['scope_summary'], 'Every record')
        d['scope'] = {'match': 'all', 'rules': [{'field': 'is_company', 'op': 'eq', 'value': True}]}
        result = self.service.save_draft(w.id, w.revision, d)
        self.assertEqual(result['scope_summary'], self.service._scope_summary('res.partner', d['scope']))
        self.assertTrue(result['scope_summary'].startswith('Records where '))

    # ================================================================ WF2 P3b
    def flow(self, nodes, order, model='', trigger='manual'):
        """A workflow whose main path is `order` (other nodes sit in paths)."""
        w, d = self.workflow([], model=model, trigger=trigger)
        d['nodes'] += nodes
        d['order'] += order
        return w, d

    def codes(self, w, d):
        return [i['code'] for i in self.service._validate(w, d)]

    def path(self, ident, cond, steps, label=None):
        return {'id': ident, 'label': label or ident, 'steps': steps, **({'condition': cond} if cond else {})}

    def choose(self, ident, paths):
        return {'id': ident, 'type': 'branch', 'title': ident, 'stage': 0, 'branches': paths}

    def step(self, run, key):
        run.invalidate_recordset()
        return run.step_ids.filtered(lambda s: s.key == key)

    BUTTONS = [{'key': 'fine', 'label': 'Looks fine'}, {'key': 'missing', 'label': 'Paper receipt missing'}]

    def test_wf2p3b_t1_task_buttons_choose_the_path(self):
        check = self.todo('check', buttons=self.BUTTONS)
        route = self.choose('route', [self.path('p_missing', self.rule('step.check.outcome', 'missing'), ['fix']),
                                      self.path('p_else', None, [])])
        w, d = self.flow([check, route, self.todo('fix')], ['check', 'route'])
        self.assertNotIn('bad_filter', self.codes(w, d))
        self.publish(w, d)
        run = self.start(w)
        task = self.step(run, 'check')
        self.assertEqual(self.service.task_detail(task.id)['buttons'], self.BUTTONS)
        self.assertEqual(self.service.answer(task.id, {})['errors'], {'_outcome': 'Choose one of the buttons.'})
        self.assertEqual(self.service.answer(task.id, {'outcome': 'missing', 'comment': 'No paper copy'})['ok'], True)
        self.assertEqual(task.sudo().answers, {'outcome': 'missing', 'outcome_label': 'Paper receipt missing',
                                               'comment': 'No paper copy'})
        self.assertEqual(self.step(run, 'fix').state, 'waiting')
        self.assertEqual(run._values()['step.check.outcome'], 'missing')
        row = next(r for r in self.service.progress(run.id)['steps'] if r['key'] == 'check')
        self.assertEqual(row['answer'], 'Paper receipt missing')
        # The other answer takes the other path.
        run2 = self.start(w)
        self.service.answer(self.step(run2, 'check').id, {'outcome': 'fine'})
        self.assertEqual(self.step(run2, 'fix').state, 'skipped')
        self.assertEqual(run2.state, 'done')
        # One button needs no choice.
        w3, d3 = self.workflow([self.todo('one')])
        self.publish(w3, d3)
        run3 = self.start(w3)
        self.assertTrue(self.service.answer(self.step(run3, 'one').id, {})['ok'])
        self.assertEqual(self.step(run3, 'one').sudo().answers['outcome'], 'done')
        # Bad buttons are refused by code.
        bad = self.todo('bad', buttons=[{'key': 'a', 'label': 'A'}, {'key': 'a', 'label': 'B'}])
        w4, d4 = self.workflow([bad])
        self.assertIn('bad_buttons', self.codes(w4, d4))

    def test_wf2p3b_t2_move_to_a_stage_follows_the_record(self):
        self.need(self.CLAIM)
        self.expense_access()
        stage = self.user_stage('WF2 P3b scheduled', enter='person', enter_owner={'kind': 'initiator'})
        move = {'id': 'move', 'type': 'stage_move', 'title': 'Schedule it', 'stage': 0,
                'target': self.yours(stage)}
        w, d = self.workflow([move, self.todo('after')], model=self.CLAIM)
        self.assertEqual(self.codes(w, d), [])
        self.publish(w, d)
        approved = self.claim('approved')
        run = self.start(w, approved)
        self.assertEqual(self.step(run, 'move').state, 'done')
        self.assertEqual(self.positions(self.CLAIM, approved.id).stage_id, stage)
        self.assertEqual(approved.state, 'approved')
        self.assertTrue(run.log_ids.filtered(lambda l: l.message == 'Moved to WF2 P3b scheduled by the workflow.'))
        # Earlier: it waits for the record to get there, then moves it.
        draft = self.claim('draft')
        run2 = self.start(w, draft)
        self.assertEqual((self.step(run2, 'move').state, self.step(run2, 'move').error),
                         ('waiting', 'Waiting for this to reach Approved.'))
        self.assertFalse(self.positions(self.CLAIM, draft.id))
        draft._chain_engine_write('submitted')
        draft._chain_engine_write('approved')
        self.service._cron_workflows()
        self.assertEqual(self.step(run2, 'move').state, 'done')
        self.assertEqual(self.positions(self.CLAIM, draft.id).stage_id, stage)
        self.assertEqual(self.step(run2, 'after').state, 'waiting')
        # Later: skipped with a reason, and the work carries on.
        paid = self.claim('paid')
        run3 = self.start(w, paid)
        self.assertEqual(self.step(run3, 'move').state, 'skipped')
        self.assertEqual(self.step(run3, 'move').error,
                         'This is already past Approved, so it was not moved to WF2 P3b scheduled.')
        self.assertEqual(self.step(run3, 'after').state, 'waiting')
        self.assertEqual(paid.state, 'paid')
        self.assertFalse(self.positions(self.CLAIM, paid.id))
        # A stage of another kind of record is refused by code.
        other = dict(move, target={'kind': 'yours', 'id': 0})
        w4, d4 = self.workflow([other], model=self.CLAIM)
        self.assertIn('stage_move_target', self.codes(w4, d4))

    def send_back_flow(self, reviewer, between=None):
        details = self.form('details', fields_=[{'id': 'receipt', 'type': 'text', 'label': 'Receipt', 'required': True}])
        review = self.todo('review', buttons=self.BUTTONS, owner={'kind': 'user', 'id': reviewer.id})
        back = {'id': 'back', 'type': 'send_back', 'title': 'Back to details', 'stage': 0, 'target': 'details'}
        route = self.choose('route', [self.path('p_missing', self.rule('step.review.outcome', 'missing'), ['back']),
                                      self.path('p_else', None, [])])
        mid = [between] if between else []
        return self.flow([details] + mid + [review, route, back, self.todo('after')],
                         ['details'] + [m['id'] for m in mid] + ['review', 'route', 'after'])

    def test_wf2p3b_t3_send_back_redoes_the_work_and_stops_after_three(self):
        reviewer = self.person('WF2 P3b reviewer', ['base.group_user'])
        w, d = self.send_back_flow(reviewer)
        self.assertEqual(self.codes(w, d), [])
        self.publish(w, d)
        run = self.start(w)
        as_reviewer = self.service.with_user(reviewer)
        details = self.step(run, 'details')
        self.service.answer(details.id, {'receipt': 'Taxi, 12 Nov'})
        review = self.step(run, 'review')
        self.assertEqual((review.state, review.assignee_id), ('waiting', reviewer))
        as_reviewer.answer(review.id, {'outcome': 'missing', 'comment': 'Please attach the paper receipt.'})
        details = self.step(run, 'details')
        self.assertEqual(details.state, 'waiting')
        detail = self.service.task_detail(details.id)
        self.assertEqual(detail['answers']['receipt'], 'Taxi, 12 Nov', 'answers are kept as prefill')
        self.assertEqual(detail['sent_back'], {'by': reviewer.name, 'note': 'Please attach the paper receipt.',
                                               'from': 'Back to details'})
        self.assertNotIn('_sent_back', detail['answers'])
        self.assertEqual(self.step(run, 'review').state, 'pending')
        self.assertFalse((self.step(run, 'review').sudo().answers or {}).get('outcome'))
        reason = next(r for r in self.service.progress(run.id)['steps'] if r['key'] == 'details')['reason']
        self.assertEqual(reason, 'Sent back by %s: Please attach the paper receipt.' % reviewer.name)
        # Redo, then carry on.
        self.service.answer(details.id, {'receipt': 'Taxi, 12 Nov, paper attached'})
        as_reviewer.answer(self.step(run, 'review').id, {'outcome': 'fine'})
        self.assertEqual(self.step(run, 'after').state, 'waiting')
        self.assertEqual(self.step(run, 'back').state, 'skipped')
        # Three times back, then the step asks for a person to look.
        run2 = self.start(w)
        for _round in range(3):
            self.service.answer(self.step(run2, 'details').id, {'receipt': 'Again'})
            as_reviewer.answer(self.step(run2, 'review').id, {'outcome': 'missing'})
            self.assertEqual(self.step(run2, 'details').state, 'waiting')
        self.service.answer(self.step(run2, 'details').id, {'receipt': 'Again'})
        as_reviewer.answer(self.step(run2, 'review').id, {'outcome': 'missing'})
        back = self.step(run2, 'back')
        self.assertEqual((back.state, back.error), ('failed', 'This has gone back three times. Someone should look at it.'))
        # Someone looks at it and lets it carry on.
        self.service.run_action(run2.id, 'retry', back.id)
        self.assertEqual(self.step(run2, 'back').state, 'done')
        self.assertEqual(self.step(run2, 'after').state, 'waiting')
        # Validation: an approval in between, and a send back that always runs.
        approval = {'id': 'approval', 'type': 'matrix', 'title': 'Approval', 'stage': 0}
        w3, d3 = self.send_back_flow(reviewer, between=approval)
        self.assertIn('send_back_effects', self.codes(w3, d3))
        bare = {'id': 'back', 'type': 'send_back', 'title': 'Back', 'stage': 0, 'target': 'details'}
        w4, d4 = self.flow([self.form('details'), bare], ['details', 'back'])
        self.assertIn('needs_condition', self.codes(w4, d4))
        # An email in between is a warning the designer keeps on purpose.
        self.assertIn('send_back_target', self.codes(*self.flow(
            [dict(bare, target='nowhere', when=self.rule('person.user_id', 0))], ['back'])))

    def test_wf2p3b_t4_update_sets_only_a_value_the_area_opened(self):
        self.need(self.CLAIM)
        self.expense_access()
        update = {'id': 'note', 'type': 'update', 'title': 'Add a note', 'stage': 0,
                  'field': 'note', 'value': 'Checked by the workflow'}
        w, d = self.workflow([update], model=self.CLAIM)
        self.assertEqual(self.codes(w, d), [])
        self.publish(w, d)
        claim = self.claim('approved')
        run = self.start(w, claim)
        self.assertEqual(self.step(run, 'note').state, 'done')
        self.assertEqual(claim.note, 'Checked by the workflow')
        self.assertEqual(claim.state, 'approved')
        self.assertTrue(run.log_ids.filtered(lambda l: l.message == 'Set Note to Checked by the workflow.'))
        for field in ('refusal_reason', 'state', 'total'):
            w2, d2 = self.workflow([dict(update, field=field)], model=self.CLAIM)
            self.assertIn('update_field', self.codes(w2, d2), field)
        # At run time too: the status and an undeclared value are refused.
        service = run._service()
        for field in ('state', 'refusal_reason'):
            with self.assertRaises(UserError):
                service._update_step(run.sudo(), self.step(run, 'note'), service._source(self.CLAIM, claim.id),
                                     dict(update, field=field))
        self.assertEqual(claim.state, 'approved')
        # A wrongly typed value and an earlier answer of the right kind.
        w5, d5 = self.workflow([dict(update, value=12.5)], model=self.CLAIM)
        self.assertNotIn('update_value', self.codes(w5, d5), 'a number reads as text')
        form = self.form('why', fields_=[{'id': 'reason', 'type': 'text', 'label': 'Why', 'required': True}])
        w6, d6 = self.workflow([form, dict(update, value_from='step.why.reason')], model=self.CLAIM)
        # The first workflow (now on) already sets the note: a double-up
        # the designer keeps on purpose.
        self.assertEqual(self.codes(w6, d6), ['repeats_existing'])
        d6['nodes'][-1]['ack_repeat'] = True
        self.publish(w6, d6)
        run6 = self.start(w6, claim)
        self.service.answer(self.step(run6, 'why').id, {'reason': 'Client dinner'})
        self.assertEqual(claim.note, 'Client dinner')
        # A record type that opened nothing says so plainly.
        if 'hr.leave' in self.env:
            w7, d7 = self.workflow([update], model='hr.leave')
            issue = next(i for i in self.service._validate(w7, d7) if i['code'] == 'update_not_open')
            self.assertEqual(issue['text'], 'Time off has not opened any values to workflows yet.')

    def test_wf2p3b_t5_create_makes_one_draft_and_never_sends_it(self):
        self.need(self.CLAIM, 'pb.hr.letter')
        self.expense_access()
        template = self.env['pb.letter.template'].create({
            'name': 'WF2 P3b letter', 'body_html': '<p>Dear ${employee_name}</p>', 'company_id': self.company.id})
        make = {'id': 'make', 'type': 'create', 'title': 'Write the letter', 'stage': 0,
                'creator': 'letter', 'template_id': template.id}
        w, d = self.workflow([make], model=self.CLAIM)
        self.assertEqual(self.codes(w, d), [])
        self.publish(w, d)
        claimant = self.employee('WF2 P3b letter claimant')
        claim = self.claim('approved', employee=claimant)
        run = self.start(w, claim)
        step = self.step(run, 'make')
        letters = self.env['pb.hr.letter'].search([('employee_id', '=', claimant.id)])
        self.assertEqual(len(letters), 1)
        self.assertEqual((letters.state, letters.template_id), ('draft', template))
        self.assertEqual(step.choice, 'pb.hr.letter,%s' % letters.id)
        # A retry never makes a second one.
        internal(step).write({'state': 'pending'})
        internal(run).write({'state': 'running'})
        run._advance()
        self.assertEqual(self.env['pb.hr.letter'].search_count([('employee_id', '=', claimant.id)]), 1)
        self.assertEqual(self.step(run, 'make').state, 'done')
        row = next(r for r in self.service.progress(run.id)['steps'] if r['key'] == 'make')
        self.assertEqual(row['link'], {'model': 'pb.hr.letter', 'id': letters.id, 'label': letters.display_name})
        self.assertEqual(letters.state, 'draft', 'Studio never sends it')
        # Not about an employee: a plain failure. No subject at all: refused.
        wg, dg = self.workflow([make], model=self.GENERIC)
        self.publish(wg, dg)
        failed = self.step(self.start(wg, self.generic('WF2 P3b no employee')), 'make')
        self.assertEqual((failed.state, failed.error),
                         ('failed', 'This is not about an employee, so there is nobody to write a letter for.'))
        wp, dp = self.workflow([make], model='res.partner')
        self.assertIn('create_needs_subject', self.codes(wp, dp))
        if 'pb.hr.comm.post' not in self.env:
            return  # Announcements are not installed in this database.
        poster = self.env['pb.hr.comm.template'].create({'name': 'WF2 P3b notice', 'subject': 'Office closed',
                                                         'body_html': '<p>Closed on Friday.</p>'})
        notice = dict(make, id='notice', creator='announcement', template_id=poster.id)
        wn, dn = self.workflow([notice], model=self.CLAIM)
        self.publish(wn, dn)
        runn = self.start(wn, claim)
        post = self.service._made(self.step(runn, 'notice'))
        self.assertEqual((post._name, post.state, post.subject), ('pb.hr.comm.post', 'draft', 'Office closed'))

    def test_wf2p3b_t6_notify_tells_the_person_in_the_app_only(self):
        self.need(self.CLAIM)
        self.expense_access()
        tell = {'id': 'tell', 'type': 'notify', 'title': 'Tell them', 'stage': 0,
                'owner': {'kind': 'subject'}, 'text': 'Your claim {{name}} is being looked at.'}
        w, d = self.workflow([tell], model=self.CLAIM)
        self.assertEqual(self.codes(w, d), [])
        self.publish(w, d)
        claim = self.claim('approved', employee=self.employee('WF2 P3b told', user=self.staff))
        mails = self.env['mail.mail'].sudo().search_count([])
        activities = self.env['mail.activity'].sudo().search_count([])
        run = self.start(w, claim)
        self.assertEqual(self.step(run, 'tell').state, 'done')
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), mails, 'no email is queued')
        self.assertEqual(self.env['mail.activity'].sudo().search_count([]), activities, 'no to-do')
        notes = self.env['mail.notification'].sudo().search([
            ('res_partner_id', '=', self.staff.partner_id.id), ('notification_type', '=', 'inbox')])
        self.assertTrue(notes)
        self.assertIn('Your claim %s is being looked at.' % claim.name, str(notes[-1].mail_message_id.body))
        # Nobody to show it to: skipped with the reason, the run carries on.
        nobody = self.claim('approved', employee=self.employee('WF2 P3b no login'))
        step = self.step(self.start(w, nobody), 'tell')
        self.assertEqual((step.state, step.error), ('skipped', 'WF2 P3b no login has no login to show this to.'))
        # A repeat of what the area already tells that person here.
        if 'hr.leave' in self.env:
            ws, ds = self.staged('hr.leave', [('Approved', self.core('validate'))], [dict(tell, stage=1)])
            warning = next(i for i in self.service._validate(ws, ds) if i['code'] == 'repeats_existing')
            self.assertIn('Time off already does this here', warning['text'])

    def test_wf2p3b_t7_only_the_assignee_confirms_and_it_is_recorded(self):
        confirm = {'id': 'agree', 'type': 'confirm', 'title': 'Read the policy', 'stage': 0, 'due': 2,
                   'owner': {'kind': 'user', 'id': self.staff.id}, 'text': 'I have read the travel policy.'}
        w, d = self.workflow([confirm])
        self.assertEqual(self.codes(w, d), [])
        self.assertIn('confirm_needs_text', self.codes(*self.workflow([dict(confirm, text=' ')])))
        self.publish(w, d)
        run = self.start(w)
        step = self.step(run, 'agree')
        self.assertEqual((step.state, step.assignee_id), ('waiting', self.staff))
        with self.assertRaises(AccessError):
            self.service.answer(step.id, {})
        detail = self.service.with_user(self.staff).task_detail(step.id)
        self.assertEqual((detail['kind'], detail['text'], detail['buttons']),
                         ('confirm', 'I have read the travel policy.', [{'key': 'confirm', 'label': 'I confirm'}]))
        self.assertIn(step.id, [t['id'] for t in self.service.with_user(self.staff).tasks()])
        self.service.with_user(self.staff).answer(step.id, {})
        step = self.step(run, 'agree')
        self.assertEqual((step.state, step.assignee_id, step.sudo().answers['outcome_label']),
                         ('done', self.staff, 'I confirm'))
        self.assertTrue(step.done_at)
        self.assertTrue(run.log_ids.filtered(lambda l: l.message == '%s confirmed: “I confirm”.' % self.staff.name))
        self.assertEqual(run.state, 'done')

    def test_wf2p3b_t8_start_hands_over_once_within_limits(self):
        def handover(name, target=None, extra=None):
            nodes = [{'id': 'go', 'type': 'start', 'title': 'Hand over', 'stage': 0, 'workflow_id': target.id}] if target else []
            w, d = self.workflow(nodes + (extra or []))
            w.name = name
            self.publish(w, d)
            return w
        target = handover('WF2 P3b next', extra=[self.todo('waitHere')])
        first = handover('WF2 P3b first', target)
        run = self.start(first)
        self.assertEqual(self.step(run, 'go').state, 'done')
        started = self.env['pb.workflow.run'].search([('workflow_id', '=', target.id)])
        self.assertEqual(len(started), 1)
        self.assertEqual(started.initiator_id, run.initiator_id)
        self.assertEqual(self.service._made(self.step(run, 'go')), started.sudo())
        # Itself, and a target that is paused.
        w2, d2 = self.workflow([{'id': 'go', 'type': 'start', 'title': 'Hand over', 'stage': 0, 'workflow_id': 0}])
        d2['nodes'][1]['workflow_id'] = w2.id
        self.assertIn('start_self', self.codes(w2, d2))
        self.service.activate(target.id, False)
        failed = self.step(self.start(first), 'go')
        self.assertEqual(failed.state, 'failed')
        self.assertIn('is not switched on', failed.error)
        self.service.activate(target.id, True)
        # Already running for this record: noted, not a second run.
        rtarget, rd = self.workflow([self.todo('busy')], model='res.partner')
        self.publish(rtarget, rd)
        rfirst, rfd = self.workflow([{'id': 'go', 'type': 'start', 'title': 'Hand over', 'stage': 0,
                                      'workflow_id': rtarget.id}], model='res.partner')
        self.publish(rfirst, rfd)
        partner = self.env['res.partner'].create({'name': 'WF2 P3b handover', 'company_id': self.company.id})
        self.start(rtarget, partner)
        step = self.step(self.start(rfirst, partner), 'go')
        self.assertEqual((step.state, step.error), ('done', '%s is already running for this record.' % rtarget.name))
        self.assertEqual(self.env['pb.workflow.run'].search_count([('workflow_id', '=', rtarget.id)]), 1)
        # At most three hand-overs in a row.
        last = handover('WF2 P3b chain 5', extra=[self.todo('endOfChain')])
        chain = [last]
        for n in (4, 3, 2, 1):
            chain.insert(0, handover('WF2 P3b chain %s' % n, chain[0]))
        self.start(chain[0])
        self.assertFalse(self.env['pb.workflow.run'].search([('workflow_id', '=', last.id)]))
        fourth = self.env['pb.workflow.run'].search([('workflow_id', '=', chain[3].id)])
        self.assertEqual(self.step(fourth, 'go').state, 'failed')
        self.assertIn('three times at most', self.step(fourth, 'go').error)

    def test_wf2p3b_t9_stop_here_ends_the_run_with_its_reason(self):
        stop = {'id': 'stop', 'type': 'end', 'title': 'Stop', 'stage': 0, 'reason': 'Nothing to pay'}
        route = self.choose('route', [self.path('p_me', self.rule('person.user_id', self.admin.id), ['stop']),
                                      self.path('p_else', None, [])])
        w, d = self.flow([route, stop, self.todo('after')], ['route', 'after'])
        self.assertEqual(self.codes(w, d), [])
        self.publish(w, d)
        run = self.start(w)
        self.assertEqual(run.state, 'done')
        self.assertEqual((self.step(run, 'after').state, self.step(run, 'after').error), ('skipped', 'Stopped by “Stop”.'))
        self.assertTrue(run.log_ids.filtered(lambda l: l.message == 'Stopped here: Stop. Nothing to pay'))
        self.assertIn('needs_condition', self.codes(*self.workflow([dict(stop)])))
        self.assertEqual(D.route_preview(d, {'person.user_id': self.admin.id})[-1]['id'], 'stop')

    def test_wf2p3b_t10_managers_manager_resolves_and_fails_plainly(self):
        self.need(self.CLAIM)
        self.expense_access()
        top_user = self.person('WF2 P3b top', ['base.group_user'])
        mid_user = self.person('WF2 P3b middle', ['base.group_user'])
        self.expense_access(top_user, mid_user)
        top = self.employee('WF2 P3b top', user=top_user)
        mid = self.employee('WF2 P3b middle', user=mid_user, parent_id=top.id)
        w, d = self.workflow([self.todo('up', owner={'kind': 'managers_manager'})], model=self.CLAIM)
        self.assertEqual(self.codes(w, d), [])
        self.publish(w, d)
        run = self.start(w, self.claim(employee=self.employee('WF2 P3b claimant', parent_id=mid.id)))
        self.assertEqual(self.step(run, 'up').assignee_id, top_user, self.step(run, 'up').error)
        alone_user = self.person('WF2 P3b alone', ['base.group_user'])
        alone = self.employee('WF2 P3b alone', user=alone_user)
        failed = self.step(self.start(w, self.claim(employee=self.employee('WF2 P3b second', parent_id=alone.id))), 'up')
        self.assertEqual((failed.state, failed.error), ('failed', 'WF2 P3b alone has no manager with a staff login, '
                                                                  'so this cannot go to their manager’s manager.'))
        self.assertIn('owner_needs_record', self.codes(*self.workflow([self.todo('up', owner={'kind': 'managers_manager'})])))

    def test_wf2p3b_t11_wait_can_carry_on_when_time_runs_out(self):
        never = self.rule('person.user_id', 0)
        wait = {'id': 'pause', 'type': 'wait', 'title': 'Wait', 'stage': 0, 'hours': 1, 'wait_for': never,
                'on_timeout': 'continue'}
        w, d = self.workflow([wait, self.todo('after')])
        self.assertEqual(self.codes(w, d), [])
        self.publish(w, d)
        run = self.start(w)
        self.wake(run, 'pause')
        self.service._cron_workflows()
        step = self.step(run, 'pause')
        self.assertEqual((step.state, step.error), ('done', 'Carried on after waiting 1 hour.'))
        self.assertEqual(self.step(run, 'after').state, 'waiting')
        # The default still flags it for attention.
        w2, d2 = self.workflow([dict(wait, on_timeout='flag'), self.todo('after')])
        self.publish(w2, d2)
        run2 = self.start(w2)
        self.wake(run2, 'pause')
        self.service._cron_workflows()
        self.assertEqual(self.step(run2, 'pause').state, 'failed')
        self.assertIn('bad_wait', self.codes(*self.workflow([dict(wait, on_timeout='later')])))
        # Working days follow the company calendar.
        if self.company.resource_calendar_id:
            node = dict(wait, unit='working', amount=2, hours=48)
            self.assertGreater(run._service()._wake_at(run.sudo(), node), fields.Datetime.now())

    def test_wf2p3b_t12_candidate_stage_added_through_hiring(self):
        self.need('pb.hiring')
        self.recruiter(admin=True)
        Stage = self.env['hr.recruitment.stage']
        shortlist = Stage._pb_stage('shortlist')
        catalogue = self.service.stage_add_area('hr.applicant', 'WF2 P3b culture chat', 'shortlist')
        made = Stage.search([('name', '=', 'WF2 P3b culture chat')])
        self.assertEqual(len(made), 1)
        self.assertTrue(made.pb_key.startswith('own_'))
        self.assertEqual((made.pb_family, made.pb_always_on), ('open', False))
        keys = [s['key'] for s in catalogue['stages']]
        self.assertEqual(keys[keys.index('shortlist') + 1], made.pb_key, 'straight after Shortlist')
        row = next(s for s in catalogue['stages'] if s['key'] == made.pb_key)
        self.assertEqual((row['kind'], row['exit']), ('core', False), 'a real Hiring stage, not Studio’s')
        presets = self.env['pb.hiring.stage.preset'].search([('stage_ids', 'in', shortlist.ids)])
        self.assertTrue(all(made in p.stage_ids for p in presets))
        # It survives the stage seeding every upgrade runs.
        Stage._ensure_journey_stages()
        made.invalidate_recordset()
        self.assertEqual((made.exists().name, made.pb_family), ('WF2 P3b culture chat', 'open'))
        # The existing verbs rename and reorder it.
        self.env['pb.hiring'].act('stage_rename', {'stage_id': made.id, 'name': 'WF2 P3b values chat'})
        self.assertEqual(made.name, 'WF2 P3b values chat')
        every = Stage.search([('pb_key', '!=', False)], order='sequence,id')
        ids = [s.id for s in every if s != made]
        ids.insert(0, made.id)
        self.env['pb.hiring'].act('stage_reorder', {'ids': ids})
        self.assertEqual(Stage.search([('pb_family', '=', 'open')], order='sequence,id')[:1], made)
        # Hiring's own permission decides; Studio still keeps no stage layer.
        designer = self.person('WF2 P3b designer', ['base.group_user', 'pb_lifecycle.group_workflow_designer',
                                                    'hr_recruitment.group_hr_recruitment_user'])
        with self.assertRaises(AccessError):
            self.env['pb.workflow.studio'].with_user(designer).stage_add_area('hr.applicant', 'WF2 P3b no', 'shortlist')
        with self.assertRaises(UserError):
            self.service.stage_create('hr.applicant', None, {'name': 'WF2 P3b own row', 'anchor_value': 'screening'})
        with self.assertRaises(UserError):
            self.service.stage_add_area('hr.applicant', 'WF2 P3b after joined', 'joined')
        # A move through the module action reaches it.
        options = self.service._actions('hr.applicant')['hiring.stage']['params'][0]['options']
        self.assertIn(made.pb_key, [o['key'] for o in options])

    def test_wf2p3b_t13_other_request_and_pay_run_contracts(self):
        expected = {self.GENERIC: ({'rejected', 'cancelled'}, 'pending'), 'hr.payslip.run': ({'cancel'}, 'approval_pending')}
        for model, (exits, approval) in expected.items():
            if model not in self.env:
                continue
            contract = self.service._contract(model)
            self.assertEqual(contract['source'], 'declared', model)
            found = {str(s['key']) for s in contract['stages'] if s['exit']}
            self.assertEqual(found, exits, model)
            flags = [s['exit'] for s in contract['stages']]
            self.assertEqual(flags, sorted(flags), 'exits come last')
            self.assertEqual([s['key'] for s in contract['stages'] if s['approval']], [approval])
            texts = [contract['label'], contract['area']] + [s['name'] for s in contract['stages']] + \
                [s['enters'] for s in contract['stages']]
            for row in self.service._existing(model, self.company):
                if row['source'] == 'area':
                    texts += [row['text'], row['owner']]
            for text in texts:
                self.assertTrue(str(text).strip(), model)
                self.assertFalse(self.BANNED.search(text or ''), '%s: %s' % (model, text))
        self.assertTrue(self.service._contract(self.GENERIC)['has_subject'])
        if 'hr.payslip.run' in self.env:
            run_contract = self.service._contract('hr.payslip.run')
            self.assertFalse(run_contract['has_subject'])
            self.assertEqual(run_contract['safe_fields'], [])
            self.assertEqual(len([r for r in self.service._existing('hr.payslip.run', self.company) if r['source'] == 'area']), 3)
        # The banned-word check covers the new step texts too.
        texts = [c['label'] + ' ' + c['hint'] for c in self.service._creators()]
        texts += [f['label'] for f in self.service._contract(self.GENERIC)['safe_fields']]
        for text in texts:
            self.assertFalse(self.BANNED.search(text), text)
        # No new Studio file and no new area contract writes a status.
        from odoo.modules.module import get_module_path
        files = [os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'workflow_steps.py')]
        for module in ('pb_payruns', 'biz_approval_workflow', 'pb_me_expense', 'pb_hiring'):
            path = get_module_path(module)
            if path:
                files.append(os.path.join(path, 'models', 'workflow_contract.py'))
        offenders = []
        for path in files:
            for number, line in enumerate(open(path, encoding='utf-8').read().splitlines(), 1):
                if re.search(r'\b(source|record|records|rec|self)\b\.(state|stage_id)\s*=[^=]', line) or \
                        re.search(r'\b(source|record|records|rec)\b(\.\w+\([^)]*\))*\.write\(', line) or \
                        re.search(r"write\(\{\s*'(state|stage_id)'", line) and 'internal(' not in line or \
                        re.search(r'_chain_(engine|state)_write|_advance_state\(|action_approve\(|action_refuse\(', line):
                    offenders.append('%s:%s %s' % (os.path.basename(path), number, line.strip()))
        self.assertEqual(offenders, [])

    def test_wf2p3b_t14_new_steps_stay_inside_their_company(self):
        other = self.env['res.company'].create({'name': 'WF2 P3b second company'})
        theirs = internal(self.env['pb.workflow.stage']).create({
            'company_id': other.id, 'source_model': False, 'name': 'WF2 P3b theirs', 'anchor_value': False})
        move = {'id': 'move', 'type': 'stage_move', 'title': 'Move', 'stage': 0, 'target': self.yours(theirs)}
        w, d = self.workflow([move])
        self.assertIn('stage_move_target', self.codes(w, d))
        foreign = internal(self.env['pb.workflow']).create({
            'name': 'WF2 P3b theirs', 'company_id': other.id, 'draft': D.fresh('x')})
        self.assertIn('start_target', self.codes(*self.workflow([{'id': 'go', 'type': 'start', 'title': 'Go', 'stage': 0,
                                                                 'workflow_id': foreign.id}])))
        outsider = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'WF2 P3b outsider', 'login': 'wf2p3b-out-%s' % uuid.uuid4(), 'company_id': other.id,
            'company_ids': [(6, 0, other.ids)], 'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        for kind in ('notify', 'confirm'):
            node = {'id': 'p', 'type': kind, 'title': 'P', 'stage': 0, 'due': 2, 'text': 'Read this',
                    'owner': {'kind': 'user', 'id': outsider.id}}
            self.assertIn('inactive_owner', self.codes(*self.workflow([node])), kind)
        if 'pb.letter.template' in self.env and self.CLAIM in self.env:
            letter = self.env['pb.letter.template'].create({'name': 'WF2 P3b theirs', 'company_id': other.id})
            make = {'id': 'make', 'type': 'create', 'title': 'Make', 'stage': 0, 'creator': 'letter', 'template_id': letter.id}
            self.assertIn('create_template', self.codes(*self.workflow([make], model=self.CLAIM)))
        # At run time too: a stage that moved to another company is refused.
        own, od = self.workflow([])
        stage = self.user_stage('WF2 P3b mine', model='', workflow=own)
        od['nodes'].append(dict(move, target=self.yours(stage)))
        od['order'].append('move')
        self.publish(own, od)
        internal(stage).write({'company_id': other.id})
        failed = self.step(self.start(own), 'move')
        self.assertEqual(failed.state, 'failed')
        self.assertIn('no longer exists', failed.error)

    # ================================================================ WF2 P4a
    def portal_person(self, name, company=None):
        """An employee-home login (portal) linked to an active employee."""
        company = company or self.company
        login = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': name, 'login': 'wf2p4a-%s-%s' % (name.lower().replace(' ', '-'), uuid.uuid4()),
            'company_id': company.id, 'company_ids': [(6, 0, company.ids)],
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        employee = self.env['hr.employee'].create({'name': name, 'company_id': company.id, 'user_id': login.id})
        return login, employee

    def team(self, name, members, company=None):
        role = self.env['biz.approval.role'].create({'key': 'wf2p4a_%s' % uuid.uuid4().hex[:10], 'name': name, 'is_pool': True})
        self.env['biz.approval.responsibility'].create({
            'company_id': (company or self.company).id, 'role_id': role.id, 'scope_key': '',
            'pool_user_ids': [(6, 0, [m.id for m in members])]})
        return role

    def staffer(self, name, extra=()):
        return self.person(name, ['base.group_user', *extra])

    def inbox(self, person):
        return self.env['pb.approval.inbox'].with_user(person).with_context(pbf_ctx={'scope': 'me'})

    def outbox(self, kind, person):
        return self.env['biz.approval.outbox'].sudo().search([('kind', '=', kind), ('user_id', '=', person.id)])

    def test_wf2p4a_t1_tasks_join_the_inbox_without_touching_approvals(self):
        before = self.inbox(self.staff).get_inbox_page(filters={'my_turn': ['yes']})
        counts_before = self.inbox(self.staff)._counts('me')
        w, d = self.workflow([self.todo('check', owner={'kind': 'user', 'id': self.staff.id}, title='Check the receipt')])
        self.publish(w, d)
        run = self.start(w)
        step = self.step(run, 'check')
        items = self.inbox(self.staff)._extra_items('me')
        card = next(c for c in items if c['id'] == step.id)
        self.assertEqual((card['kind'], card['source'], card['title'], card['state_label'], card['mine'], card['route']),
                         ('task', 'workflow', 'Check the receipt', 'To do', True, []))
        self.assertEqual(card['open'], {'type': 'workflow_task', 'id': step.id})
        self.assertNotIn(step.id, [c['id'] for c in self.inbox(self.admin)._extra_items('me')], 'assignee only')
        self.assertGreaterEqual(self.inbox(self.staff)._extra_counts('me')['mine'], 1)
        for words in (card['title'], card['state_label'], card['sub'], card['verb']):
            self.assertFalse(self.BANNED.search(words), words)
        # Approvals: same cards, same total, same counts, with the task there.
        after = self.inbox(self.staff).get_inbox_page(filters={'my_turn': ['yes']})
        self.assertEqual((after['cards'], after['total'], after['money']), (before['cards'], before['total'], before['money']))
        self.assertIn(step.id, [t['id'] for t in after['tasks']])
        counts = self.inbox(self.staff)._counts('me')
        self.assertEqual({k: counts[k] for k in ('mine', 'all', 'returned', 'done')},
                         {k: counts_before[k] for k in ('mine', 'all', 'returned', 'done')})
        self.assertGreaterEqual(counts['tasks'], 1)
        self.assertEqual(self.inbox(self.staff).get_inbox_page(filters={'my_turn': ['yes']}, offset=60)['tasks'], [])
        head = self.inbox(self.staff).get_inbox_head()
        self.assertGreaterEqual(head['task_counts']['mine'], 1)
        # Done: gone from the inbox.
        self.service.with_user(self.staff).answer(step.id, {})
        self.assertNotIn(step.id, [c['id'] for c in self.inbox(self.staff)._extra_items('me')])

    def test_wf2p4a_t2_team_and_company_views_follow_progress_rights(self):
        boss = self.staffer('WF2 P4a boss', ['pb_lifecycle.group_workflow_viewer'])
        boss_emp = self.employee('WF2 P4a boss', user=boss)
        self.employee('WF2 P4a report', user=self.staff, parent_id=boss_emp.id)
        w, d = self.workflow([self.todo('do', owner={'kind': 'user', 'id': self.staff.id})])
        self.publish(w, d)
        step = self.step(self.start(w), 'do')
        team = self.inbox(boss).with_context(pbf_ctx={'scope': 'team'})._extra_items('team')
        card = next(c for c in team if c['id'] == step.id)
        self.assertEqual((card['mine'], card['waiting_for']), (False, self.staff.name))
        self.assertEqual(card['open']['type'], 'workflow_progress', 'a read, not the task')
        plain = self.staffer('WF2 P4a no rights')
        self.employee('WF2 P4a plain boss', user=plain)
        self.assertEqual(self.env['pb.workflow.studio'].with_user(plain)._inbox_tasks('org', wide=True), [])
        self.assertEqual(self.env['pb.workflow.studio'].with_user(plain)._inbox_tasks('team', team_user_ids=[self.staff.id]), [])

    def test_wf2p4a_t3_late_tasks_are_reminded_then_passed_up_once(self):
        Engine = self.env['biz.approval.engine']
        boss = self.staffer('WF2 P4a line manager')
        self.employee('WF2 P4a reminded', user=self.staff, parent_id=self.employee('WF2 P4a lm', user=boss).id)
        w, d = self.workflow([self.todo('do', owner={'kind': 'user', 'id': self.staff.id})])
        self.publish(w, d)
        run = self.start(w)
        step = self.step(run, 'do')
        self.assertTrue(step.due_at, 'the deadline is kept on the step')
        now = fields.Datetime.now()
        internal(step).write({'due_at': now - timedelta(days=1, hours=1)})
        Engine._escalate_extra(now)
        self.assertEqual(len(self.outbox('task_reminder', self.staff).filtered(lambda o: o.payload.get('res_id') == run.id)), 1)
        self.assertFalse(self.outbox('task_passed_up', boss))
        Engine._escalate_extra(now + timedelta(hours=1))
        self.assertEqual(len(self.outbox('task_reminder', self.staff).filtered(lambda o: o.payload.get('res_id') == run.id)), 1, 'not repeated')
        internal(step).write({'due_at': now - timedelta(days=2, hours=1)})
        Engine._escalate_extra(now)
        passed = self.outbox('task_passed_up', boss)
        self.assertEqual(len(passed), 1)
        self.assertEqual(step.assignee_id, self.staff, 'passing up tells, it never moves the task')
        # Delivered the approvals way: a note on the run to that one person.
        passed._deliver()
        note = self.env['mail.message'].sudo().search([('model', '=', 'pb.workflow.run'), ('res_id', '=', run.id),
                                                       ('subject', '=', passed.payload['summary'])])
        self.assertTrue(note)
        self.assertIn(boss.partner_id, note.notification_ids.res_partner_id)
        # Nobody manages them: the person who published the workflow is told.
        w2, d2 = self.workflow([self.todo('do', owner={'kind': 'user', 'id': self.admin.id})])
        self.publish(w2, d2)
        step2 = self.step(self.start(w2), 'do')
        internal(step2).write({'due_at': now - timedelta(days=3)})
        Engine._escalate_extra(now)
        self.assertFalse(self.outbox('task_passed_up', self.admin).filtered(lambda o: o.payload.get('res_id') == step2.run_id.id),
                         'never the person it waits for')
        # A step with no deadline is never chased.
        internal(step2).write({'due_at': False, 'reminded_at': False, 'passed_up_at': False})
        Engine._escalate_extra(now)
        self.assertFalse(step2.reminded_at)
        # A fault here never stops the approvals job.
        with patch.object(type(self.env['pb.workflow.studio']), '_chase_late', side_effect=RuntimeError('boom')):
            self.assertTrue(Engine.escalate_cron())

    def test_wf2p4a_t4_a_stage_past_its_target_tells_once_per_entry(self):
        w, d = self.staged('', [], [])
        checked = self.user_stage('WF2 P4a checked', model='', workflow=w, target_hours=1)
        other = self.user_stage('WF2 P4a other', model='', workflow=w, enter='person',
                                enter_owner={'kind': 'user', 'id': self.staff.id})
        d['stages'] += [{'name': 'Checked', 'bind': self.yours(checked)}]
        node = self.todo('check', stage=1, owner={'kind': 'user', 'id': self.staff.id})
        d['nodes'].append(node)
        d['order'].append('check')
        self.publish(w, d)
        run = self.start(w)
        row = self.positions('pb.workflow.run', run.id)
        self.assertEqual(row.stage_id, checked)
        Studio = self.env['pb.workflow.studio'].sudo()
        now = fields.Datetime.now()
        Studio._chase_late_stages(now)
        self.assertFalse(self.outbox('stage_late', self.staff), 'not late yet')
        internal(row).write({'entered_at': now - timedelta(hours=2)})
        Studio._chase_late_stages(now)
        Studio._chase_late_stages(now)
        late = self.outbox('stage_late', self.staff)
        self.assertEqual(len(late), 1, 'told once, to the person it waits for')
        # Entering again arms it again.
        Studio._set_position('pb.workflow.run', run.id, other, self.company, run=run.sudo())
        Studio._set_position('pb.workflow.run', run.id, checked, self.company, run=run.sudo())
        row = self.positions('pb.workflow.run', run.id)
        self.assertFalse(row.late_told_at)
        internal(row).write({'entered_at': now - timedelta(hours=3)})
        Studio._chase_late_stages(now)
        self.assertEqual(len(self.outbox('stage_late', self.staff)), 2)

    def test_wf2p4a_t5_cover_while_away_goes_to_the_person_covering(self):
        cover = self.staffer('WF2 P4a covering')
        self.env['biz.approval.delegation'].create({
            'company_id': self.company.id, 'principal_user_id': self.staff.id, 'delegate_user_id': cover.id,
            'date_from': fields.Date.today(), 'date_to': fields.Date.today() + timedelta(days=5),
            'reason': 'Annual leave', 'state': 'active'})
        w, d = self.workflow([self.todo('do', owner={'kind': 'user', 'id': self.staff.id})])
        self.publish(w, d)
        run = self.start(w)
        step = self.step(run, 'do')
        self.assertEqual((step.assignee_id, step.covered_user_id), (cover, self.staff))
        self.assertTrue(run.log_ids.filtered(lambda l: l.message == 'Waiting for %s, covering for %s while they are away.'
                                             % (cover.name, self.staff.name)))
        card = next(c for c in self.inbox(cover)._extra_items('me') if c['id'] == step.id)
        self.assertEqual(card['covering_for'], self.staff.name)
        progress = self.service.progress(run.id)
        self.assertIn(self.staff.name, next(r for r in progress['steps'] if r['id'] == step.id)['covering'])
        with self.assertRaises(AccessError):
            self.service.with_user(self.staff).answer(step.id, {})
        self.service.with_user(cover).answer(step.id, {})
        self.assertEqual(self.step(run, 'do').state, 'done')

    def test_wf2p4a_t6_a_team_task_is_taken_by_the_first(self):
        a, b, c = self.staff, self.staffer('WF2 P4a b'), self.staffer('WF2 P4a outsider')
        role = self.team('WF2 P4a payroll', [a, b])
        node = self.todo('do', owner={'kind': 'team', 'id': role.id}, title='Check the pay file')
        w, d = self.workflow([node])
        self.assertEqual(self.codes(w, d), [])
        empty = self.team('WF2 P4a empty', [])
        self.assertIn('team_empty', self.codes(*self.workflow([dict(node, owner={'kind': 'team', 'id': empty.id})])))
        single = self.env['biz.approval.role'].create({'key': 'wf2p4a_one_%s' % uuid.uuid4().hex[:8], 'name': 'One'})
        self.assertIn('bad_team', self.codes(*self.workflow([dict(node, owner={'kind': 'team', 'id': single.id})])))
        tell = {'id': 'tell', 'type': 'notify', 'title': 'Tell', 'stage': 0, 'text': 'Hi', 'owner': {'kind': 'team', 'id': role.id}}
        self.assertIn('team_notice', self.codes(*self.workflow([tell])))
        self.publish(w, d)
        run = self.start(w)
        step = self.step(run, 'do')
        self.assertEqual((step.state, step.assignee_id, set(step.team_user_ids.ids)), ('waiting', self.env['res.users'], {a.id, b.id}))
        self.assertFalse(step.activity_id, 'no to-do until someone takes it')
        self.assertEqual(len(self.outbox('task_reminder', a) | self.outbox('task_reminder', b)), 2, 'each member told once')
        for member in (a, b):
            row = next(t for t in self.service.with_user(member).tasks() if t['id'] == step.id)
            self.assertTrue(row['can_take'])
            self.assertIn(step.id, [x['id'] for x in self.inbox(member)._extra_items('me')])
        self.service.with_user(a).take(step.id)
        self.assertEqual(self.step(run, 'do').assignee_id, a)
        with self.assertRaises(UserError) as lost:
            self.service.with_user(b).take(step.id)
        self.assertEqual(str(lost.exception.args[0]), '%s has just taken this.' % a.name)
        self.service.with_user(a).release(step.id)
        self.assertFalse(self.step(run, 'do').assignee_id)
        with self.assertRaises(AccessError):
            self.service.with_user(c).take(step.id)
        with self.assertRaises(AccessError):
            self.service.with_user(c).answer(step.id, {})
        self.service.with_user(b).answer(step.id, {})
        step = self.step(run, 'do')
        self.assertEqual((step.state, step.assignee_id), ('done', b), 'answering takes it')

    def employee_claim(self, employee):
        self.need(self.CLAIM)
        self.expense_access()
        return self.claim('approved', employee=employee)

    def test_wf2p4a_t7_an_employee_home_login_does_their_task_at_home(self):
        self.need(self.CLAIM)
        portal, emp = self.portal_person('WF2 P4a homer')
        confirm = {'id': 'agree', 'type': 'confirm', 'title': 'Read the policy', 'stage': 0, 'due': 2,
                   'owner': {'kind': 'subject'}, 'text': 'I have read the expense policy.'}
        w, d = self.workflow([confirm], model=self.CLAIM)
        self.publish(w, d)
        claim = self.employee_claim(emp)
        run = self.start(w, claim)
        step = self.step(run, 'agree')
        self.assertEqual((step.state, step.assignee_id, step.activity_id), ('waiting', portal, self.env['mail.activity']))
        self.assertEqual(step.person_employee_id, emp)
        Studio = self.env['pb.workflow.studio'].sudo().with_user(portal)
        self.assertEqual(Studio._home_tasks(portal), step)
        rows = {key: (url, kw) for key, _n, url, kw in self.env['pb.me.home'].with_user(portal)._wf_needs_rows(emp)}
        self.assertEqual(rows['wf_task_%s' % step.id][0], '/my/todo/%s' % step.id)
        self.assertEqual(rows['wf_task_%s' % step.id][1]['label'], 'Read and confirm: Read the policy')
        other, _emp = self.portal_person('WF2 P4a someone else')
        self.assertIsNone(Studio._home_task(other, step.id), 'never another person’s task')
        with self.assertRaises(AccessError):
            self.env['pb.workflow.studio'].with_user(portal).tasks()
        with self.assertRaises(AccessError):
            self.env['pb.workflow.studio'].with_user(portal).answer(step.id, {})
        result = Studio._complete_outside(Studio._home_task(portal, step.id), {}, actor_words=portal.name, person=portal)
        self.assertTrue(result['ok'])
        self.assertEqual(self.step(run, 'agree').state, 'done')
        self.assertTrue(run.log_ids.filtered(lambda l: l.message == '%s confirmed: “I confirm”.' % portal.name))

    def test_wf2p4a_t7b_an_employee_home_login_attaches_a_file(self):
        self.need(self.CLAIM)
        portal, emp = self.portal_person('WF2 P4a filer')
        form = self.form('files', fields_=[{'id': 'tickets', 'type': 'file', 'label': 'Tickets', 'required': True}],
                         owner={'kind': 'subject'})
        w, d = self.workflow([form], model=self.CLAIM)
        self.publish(w, d)
        run = self.start(w, self.employee_claim(emp))
        Studio = self.env['pb.workflow.studio'].sudo().with_user(portal)
        step = Studio._home_task(portal, self.step(run, 'files').id)

        class Upload:
            filename, mimetype = 'ticket.pdf', 'application/pdf'

            def read(self):
                return b'%PDF-1.4 ticket'
        other, _emp = self.portal_person('WF2 P4a not them')
        with self.assertRaises(AccessError):
            self.env['pb.workflow.studio'].sudo().with_user(other)._home_upload(portal, step, 'tickets', Upload())
        ident = Studio._home_upload(portal, step, 'tickets', Upload())
        att = self.env['ir.attachment'].browse(ident)
        self.assertEqual((att.res_model, att.res_id, att.create_uid), ('pb.workflow.step', step.id, portal))
        result = Studio._complete_outside(step, {'tickets': [ident]}, actor_words=portal.name, person=portal)
        self.assertTrue(result['ok'], result)
        self.assertEqual(self.step(run, 'files').sudo().answers['tickets'], [ident])

    def test_wf2p4a_t8_a_notice_reaches_the_employee_home(self):
        self.need(self.CLAIM)
        portal, emp = self.portal_person('WF2 P4a told at home')
        tell = {'id': 'tell', 'type': 'notify', 'title': 'Tell them', 'stage': 0,
                'owner': {'kind': 'subject'}, 'text': 'Your claim {{name}} is booked.'}
        w, d = self.workflow([tell], model=self.CLAIM)
        self.publish(w, d)
        claim = self.employee_claim(emp)
        mails = self.env['mail.mail'].sudo().search_count([])
        run = self.start(w, claim)
        self.assertEqual(self.step(run, 'tell').state, 'done')
        notices = self.env['pb.workflow.studio'].sudo()._home_notices(portal, unread_only=True)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices.body, 'Your claim %s is booked.' % claim.name)
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), mails, 'no email')
        card = self.env['pb.me.home'].with_user(portal)._wf_notice_card(emp)
        self.assertEqual(card['data']['rows'][0]['body'], 'Your claim %s is booked.' % claim.name)
        notices.write({'read_at': fields.Datetime.now()})
        self.assertFalse(self.env['pb.workflow.studio'].sudo()._home_notices(portal, unread_only=True))
        with self.assertRaises(AccessError):
            self.env['pb.workflow.notice'].with_user(portal).search([])

    def link_flow(self, nodes, email='mai.tran@example.com'):
        self.need(self.CLAIM)
        emp = self.employee('WF2 P4a by link', work_email=email)
        w, d = self.workflow(nodes, model=self.CLAIM)
        self.publish(w, d)
        claim = self.employee_claim(emp)
        return w, self.start(w, claim)

    CONFIRM = {'id': 'agree', 'type': 'confirm', 'title': 'Confirm your details', 'stage': 0, 'due': 2,
               'owner': {'kind': 'subject'}, 'text': 'My bank details are right.'}

    def test_wf2p4a_t9_someone_without_a_login_answers_by_link(self):
        Mail = self.env['mail.mail'].sudo()
        mails = Mail.search_count([])
        w, run = self.link_flow([self.CONFIRM])
        step = self.step(run, 'agree').sudo()
        token = step.access_token
        self.assertEqual((step.state, step.assignee_id), ('waiting', self.env['res.users']))
        self.assertGreaterEqual(len(token), 40)
        self.assertGreaterEqual(step.link_expires_at, step.due_at + timedelta(days=13))
        self.assertEqual(Mail.search_count([]), mails + 1, 'one email')
        mail = Mail.search([], order='id desc', limit=1)
        self.assertEqual(mail.subject, 'You have something to do: Confirm your details')
        self.assertIn('/workflow/t/%s' % token, mail.body_html)
        self.assertEqual(mail.email_to, 'mai.tran@example.com')
        self.assertNotRegex(mail.subject + mail.body_html, '(?i)odoo')
        self.assertNotIn(token, json.dumps(self.service.progress(run.id), default=str))
        Studio = self.env['pb.workflow.studio'].sudo()
        self.assertEqual(Studio._step_for_token(token)[1], 'ok')
        self.assertEqual(Studio._step_for_token('x' * 43)[1], 'missing')
        self.assertEqual(Studio._step_for_token('short')[1], 'missing')
        system = run._service()
        result = system._complete_outside(system.env['pb.workflow.step'].browse(step.id), {}, ip='203.0.113.9')
        self.assertTrue(result['ok'])
        self.assertEqual(self.step(run, 'agree').state, 'done')
        again = system._complete_outside(system.env['pb.workflow.step'].browse(step.id), {}, ip='203.0.113.9')
        self.assertEqual((again['ok'], again['state']), (False, 'done'), 'used once')
        self.assertEqual(Studio._step_for_token(token)[1], 'done')
        # Run out: the same answer as an unknown link on the page.
        _w2, run2 = self.link_flow([self.CONFIRM])
        step2 = self.step(run2, 'agree').sudo()
        internal(step2).write({'link_expires_at': fields.Datetime.now() - timedelta(minutes=1)})
        self.assertEqual(Studio._step_for_token(step2.access_token)[1], 'expired')
        # Sending again voids the old link.
        internal(step2).write({'link_expires_at': fields.Datetime.now() + timedelta(days=3)})
        old = step2.access_token
        sent = self.service.resend_link(step2.id)
        self.assertEqual(sent['sent_to'], 'm***@example.com')
        self.assertNotEqual(self.step(run2, 'agree').sudo().access_token, old)
        self.assertEqual(Studio._step_for_token(old)[1], 'missing')
        # Answers are checked by the app's own rules.
        form = self.form('bank', fields_=[{'id': 'n', 'type': 'number', 'label': 'Account number', 'required': True}],
                         owner={'kind': 'subject'})
        _w3, run3 = self.link_flow([form])
        step3 = self.step(run3, 'bank')
        sys3 = run3._service()
        bad = sys3._complete_outside(sys3.env['pb.workflow.step'].browse(step3.id), {'n': 'abc'}, ip='203.0.113.9')
        self.assertEqual((bad['ok'], bad['errors']), (False, {'n': 'Enter a number.'}))
        self.assertEqual(self.step(run3, 'bank').state, 'waiting')

    def test_wf2p4a_t9b_send_back_sends_a_new_link(self):
        form = self.form('bank', fields_=[{'id': 'acc', 'type': 'text', 'label': 'Account', 'required': True}],
                         owner={'kind': 'subject'})
        review = self.todo('review', owner={'kind': 'user', 'id': self.admin.id}, buttons=self.BUTTONS)
        back = {'id': 'back', 'type': 'send_back', 'title': 'Back', 'stage': 0, 'target': 'bank'}
        route = self.choose('route', [self.path('p_missing', self.rule('step.review.outcome', 'missing'), ['back']),
                                      self.path('p_fine', None, [])])
        self.need(self.CLAIM)
        emp = self.employee('WF2 P4a link again', work_email='lan@example.com')
        w, d = self.flow([form, review, route, back], ['bank', 'review', 'route'], model=self.CLAIM)
        self.publish(w, d)
        run = self.start(w, self.employee_claim(emp))
        first = self.step(run, 'bank').sudo().access_token
        system = run._service()
        system._complete_outside(system.env['pb.workflow.step'].browse(self.step(run, 'bank').id), {'acc': '123'}, ip='1.1.1.1')
        self.service.answer(self.step(run, 'review').id, {'outcome': 'missing', 'comment': 'Wrong bank'})
        again = self.step(run, 'bank').sudo()
        self.assertEqual(again.state, 'waiting')
        self.assertTrue(again.access_token and again.access_token != first)
        self.assertEqual(self.env['pb.workflow.studio'].sudo()._step_for_token(first)[1], 'missing')

    def test_wf2p4a_t10_done_by_link_never_names_the_public_visitor(self):
        _w, run = self.link_flow([self.CONFIRM])
        step = self.step(run, 'agree')
        system = run._service()
        system._complete_outside(system.env['pb.workflow.step'].browse(step.id), {}, ip='203.0.113.9')
        progress = self.service.progress(run.id)
        row = next(r for r in progress['steps'] if r['id'] == step.id)
        self.assertEqual(row['done_by'], 'Done by the link sent to m***@example.com')
        self.assertTrue(any(h['text'] == 'Confirmed by link sent to m***@example.com: “I confirm”.' for h in progress['history']))
        text = json.dumps(progress, default=str)
        public = self.env.ref('base.public_user')
        self.assertNotIn(public.name, text)
        self.assertNotIn('mai.tran@example.com', text, 'the address is masked everywhere')
        self.assertFalse(self.step(run, 'agree').assignee_id)
        self.assertNotIn(public, run.log_ids.mapped('actor_id'))

    def test_wf2p4a_t11_every_form_field_type_renders_and_round_trips(self):
        from werkzeug.datastructures import MultiDict
        from odoo.addons.pb_lifecycle.controllers.task_form import parse_answers
        from odoo.addons.pb_lifecycle.models.workflow_people import HOME_UNSUPPORTED, LINK_UNSUPPORTED
        fields_ = [
            {'id': 'head', 'type': 'section', 'label': 'About you'},
            {'id': 'name', 'type': 'text', 'label': 'Name', 'required': True},
            {'id': 'story', 'type': 'textarea', 'label': 'Story'},
            {'id': 'count', 'type': 'number', 'label': 'Count', 'min': 0},
            {'id': 'day', 'type': 'date', 'label': 'Day'},
            {'id': 'mail', 'type': 'email', 'label': 'Email'},
            {'id': 'size', 'type': 'select', 'label': 'Size', 'options': ['S', 'M']},
            {'id': 'tags', 'type': 'multiselect', 'label': 'Tags', 'options': ['A', 'B', 'C']},
            {'id': 'ok', 'type': 'boolean', 'label': 'Fine?'},
            {'id': 'files', 'type': 'file', 'label': 'Receipts'},
            {'id': 'lines', 'type': 'rows', 'label': 'Lines'},
            {'id': 'pick', 'type': 'lookup', 'label': 'Partner', 'lookup_model': 'res.partner'},
        ]
        self.assertEqual({f['type'] for f in fields_}, set(D.FORM_TYPES), 'the test walks every type Studio offers')
        form = MultiDict([('f_name', 'Mai'), ('f_story', 'Long'), ('f_count', '3'), ('f_day', '2026-11-12'),
                          ('f_mail', 'mai@example.com'), ('f_size', 'M'), ('f_tags', 'A'), ('f_tags', 'C'),
                          ('f_ok', 'yes'), ('rows_lines_description', 'Taxi'), ('rows_lines_amount', '12.5'),
                          ('rows_lines_description', ''), ('rows_lines_amount', '')])
        expected = {'name': 'Mai', 'story': 'Long', 'count': 3, 'day': '2026-11-12', 'mail': 'mai@example.com',
                    'size': 'M', 'tags': ['A', 'C'], 'ok': True, 'lines': [{'description': 'Taxi', 'amount': 12.5}]}
        for mode, unsupported in (('link', LINK_UNSUPPORTED), ('home', HOME_UNSUPPORTED)):
            rows = [dict(f, unsupported=f['type'] in unsupported) for f in fields_]
            keep = {'files': []} if mode == 'home' else None
            values = parse_answers(rows, form, keep_files=keep)
            cleaned, errors = D.validate_answers({'fields': fields_}, values)
            self.assertEqual((cleaned, errors), (expected, {}), mode)
            html = str(self.env['ir.qweb']._render('pb_lifecycle.workflow_task_body', {
                't': {'kind': 'input', 'name': 'Details', 'workflow': 'W', 'record': '', 'fields': rows,
                      'company': 'Acme', 'readonly': [], 'buttons': [], 'files': {}},
                'mode': mode, 'state': 'ok', 'errors': {}, 'values': cleaned, 'post_url': '/x'}))
            for f in fields_:
                if f['type'] == 'section':
                    self.assertIn('About you', html)
                elif f['type'] in unsupported:
                    self.assertIn('Ask Acme', html, f['type'])
                elif f['type'] == 'rows':
                    self.assertIn('name="rows_lines_description"', html)
                else:
                    self.assertIn('name="f_%s"' % f['id'], html, (mode, f['type']))
            self.assertIn('value="Mai"', html)
            self.assertNotRegex(html, '(?i)odoo')
        # Typed text is never markup.
        html = str(self.env['ir.qweb']._render('pb_lifecycle.workflow_task_body', {
            't': {'kind': 'input', 'name': '<b>x</b>', 'workflow': 'W', 'record': '', 'fields': [fields_[1]],
                  'company': '', 'readonly': [], 'buttons': [], 'files': {}},
            'mode': 'link', 'state': 'ok', 'errors': {}, 'values': {'name': '"><script>alert(1)</script>'}, 'post_url': '/x'}))
        self.assertNotIn('<script>', html)
        self.assertNotIn('<b>x</b>', html)

    def test_wf2p4a_t12_a_workflow_adds_a_hiring_tag_through_hiring(self):
        self.need('pb.hiring', 'hr.applicant.category')
        self.recruiter()
        tag = self.env['hr.applicant.category'].create({'name': 'WF2 P4a ready'})
        spec = self.service._safe_spec('hr.applicant', 'tag')
        self.assertEqual((spec['label'], spec['type']), ('Add a tag', 'choice'))
        self.assertIn(tag.id, [o['key'] for o in spec['options']])
        update = {'id': 'tag', 'type': 'update', 'title': 'Tag them', 'stage': 0, 'field': 'tag', 'value': str(tag.id)}
        w, d = self.workflow([update], model='hr.applicant')
        self.assertEqual(self.codes(w, d), [])
        self.publish(w, d)
        applicant = self.env['hr.applicant'].create({'partner_name': 'WF2 P4a candidate', 'company_id': self.company.id})
        run = self.start(w, applicant)
        self.assertEqual(self.step(run, 'tag').state, 'done', self.step(run, 'tag').error)
        self.assertIn(tag, applicant.categ_ids)
        self.assertTrue(run.log_ids.filtered(lambda l: l.message == 'Added the tag “WF2 P4a ready”.'))
        stars = next(i for i in self.service._validate(*self.workflow([dict(update, field='priority', value='2')], model='hr.applicant'))
                     if i['code'] == 'update_field')
        self.assertEqual(stars['text'], 'Hiring no longer offers this value. Choose another.')
        self.env['pb.hiring.automation.rule'].create({
            'name': 'WF2 P4a tagger', 'company_id': self.company.id, 'event': 'stage_entered',
            'stage_id': self.env['hr.recruitment.stage']._pb_stage('screening').id, 'action': 'tag', 'tag_id': tag.id})
        self.service.activate(w.id, False)     # only the Hiring automation does it now
        w2, d2 = self.workflow([update], model='hr.applicant')
        warning = next(i for i in self.service._validate(w2, d2) if i['code'] == 'repeats_existing')
        self.assertIn('WF2 P4a ready', warning['text'])

    def test_wf2p4a_t13_hiring_removes_a_company_stage_only(self):
        self.need('pb.hiring')
        self.recruiter(admin=True)
        Hiring, Stage = self.env['pb.hiring'], self.env['hr.recruitment.stage']
        shortlist = Stage._pb_stage('shortlist')
        made = Stage.browse(Hiring.act('stage_add', {'name': 'WF2 P4a gone soon', 'after_stage_id': shortlist.id})['id'])
        key = made.pb_key
        setup = Hiring.get_setup()
        self.assertTrue(next(s for s in setup['stages'] if s['id'] == made.id)['own'])
        used = setup['own_stages']['used']
        with self.assertRaises(UserError):
            Hiring.act('stage_remove', {'stage_id': shortlist.id})
        applicant = self.env['hr.applicant'].create({'partner_name': 'WF2 P4a sitting', 'company_id': self.company.id,
                                                     'stage_id': made.id})
        with self.assertRaises(UserError) as busy:
            Hiring.act('stage_remove', {'stage_id': made.id})
        self.assertEqual(busy.exception.args[0], '1 candidate is in this stage. Move them first.')
        applicant.write({'stage_id': shortlist.id})
        designer = self.person('WF2 P4a designer', ['base.group_user', 'pb_lifecycle.group_workflow_designer',
                                                    'hr_recruitment.group_hr_recruitment_user'])
        with self.assertRaises(AccessError):
            Hiring.with_user(designer).act('stage_remove', {'stage_id': made.id})
        # A workflow section waited for it: it becomes a heading.
        w, d = self.staged('hr.applicant', [('Culture', {'kind': 'core', 'value': key})], [self.todo('do', stage=1)])
        self.service.save_draft(w.id, w.revision, d)
        catalogue = self.service.stage_remove_area('hr.applicant', key)
        self.assertNotIn(key, [s['key'] for s in catalogue['stages']])
        self.assertFalse(made.pb_key)
        presets = self.env['pb.hiring.stage.preset'].search([])
        self.assertFalse(any(made in p.stage_ids for p in presets))
        self.assertIn('bind_removed', self.codes(w, d))
        self.assertEqual(Hiring.get_setup()['own_stages']['used'], used, 'the key stays taken: a workflow named it')
        self.assertIn(key, self.service._contract('hr.applicant')['removed_keys'])

    def test_wf2p4a_t14_people_from_another_company_are_never_used(self):
        other = self.env['res.company'].create({'name': 'WF2 P4a elsewhere'})
        outsider = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'WF2 P4a outsider', 'login': 'wf2p4a-out-%s' % uuid.uuid4(), 'company_id': other.id,
            'company_ids': [(6, 0, other.ids)], 'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        role = self.team('WF2 P4a far team', [outsider])
        self.assertIn('team_empty', self.codes(*self.workflow([self.todo('do', owner={'kind': 'team', 'id': role.id})])))
        self.env['biz.approval.delegation'].create({
            'company_id': self.company.id, 'principal_user_id': self.staff.id, 'delegate_user_id': outsider.id,
            'date_from': fields.Date.today(), 'date_to': fields.Date.today() + timedelta(days=2),
            'reason': 'Away', 'state': 'active'})
        w, d = self.workflow([self.todo('do', owner={'kind': 'user', 'id': self.staff.id})])
        self.publish(w, d)
        step = self.step(self.start(w), 'do')
        self.assertEqual((step.assignee_id, step.covered_user_id), (self.staff, self.env['res.users']), 'no cover from outside')
        boss_far = self.env['hr.employee'].create({'name': 'WF2 P4a far boss', 'company_id': other.id, 'user_id': outsider.id})
        report = self.employee('WF2 P4a near report', user=self.staffer('WF2 P4a near'), parent_id=boss_far.id)
        self.assertIsNone(self.env['pb.workflow.studio'].sudo()._manager_of(report.user_id, report, self.company))
        if self.CLAIM in self.env:
            far = self.env['hr.employee'].create({'name': 'WF2 P4a far employee', 'company_id': other.id,
                                                  'work_email': 'far@example.com'})
            self.expense_access()
            w2, d2 = self.workflow([self.CONFIRM], model=self.CLAIM)
            self.publish(w2, d2)
            claim = self.env[self.CLAIM].create({'employee_id': self.employee('WF2 P4a near claim').id,
                                                 'company_id': self.company.id})
            run = self.start(w2, claim)
            Studio = run._service()
            with patch.object(type(Studio), '_owner_person', lambda s, r, o: (s.env['res.users'], far)):
                with self.assertRaises(UserError):
                    Studio._resolve_people(run.sudo(), {'kind': 'subject'})

    def test_wf2p4a_t15_outside_routes_check_first_and_never_write_status(self):
        root = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'controllers')
        mine = open(os.path.join(root, 'my_tasks.py'), encoding='utf-8').read()
        for route in ('def my_todo_task', 'def my_todo_done'):
            body = mine.split(route, 1)[1].split('\n    @http.route', 1)[0]
            first_check = body.index('self._own(')
            for later in ('self._studio()', '.sudo()', 'request.env['):
                if later in body:
                    self.assertLess(first_check, body.index(later), (route, later))
        links = open(os.path.join(root, 'token_pages.py'), encoding='utf-8').read()
        for route in ('def workflow_link_view', 'def workflow_link_done'):
            body = links.split(route, 1)[1].split('\n    @http.route', 1)[0]
            first_check = body.index('self._wf_resolve(')
            for later in ('.sudo()', 'system(', 'request.env['):
                if later in body:
                    self.assertLess(first_check, body.index(later), (route, later))
        self.assertNotIn('csrf=False', links.split('# ===================================================== workflow links', 1)[1])
        self.assertNotIn('t-raw', open(os.path.join(os.path.dirname(root), 'views', 'workflow_task_page.xml')).read())
        # The status-write guard covers the new files too.
        models_root = os.path.join(os.path.dirname(root), 'models')
        for name in ('workflow_people.py', 'workflow_people_design.py', 'workflow_inbox.py', 'workflow_home.py'):
            text = open(os.path.join(models_root, name), encoding='utf-8').read()
            self.assertFalse(re.search(r'\b(source|record|records|rec)\b\.(state|stage_id)\s*=[^=]', text), name)
            self.assertFalse(re.search(r'\b(source|record|records|rec)\b(\.\w+\([^)]*\))*\.write\(', text), name)
        # The ownership checks themselves.
        Studio = self.env['pb.workflow.studio'].sudo()
        self.assertIsNone(Studio._home_task(self.staff, 0))
        self.assertEqual(Studio._step_for_token(None)[1], 'missing')

    # ================================================================ WF2 P4b
    def claim_flow(self, nodes, employee=None, state='approved'):
        """A published claim workflow and one claim with it running."""
        self.need(self.CLAIM)
        self.expense_access(self.admin, self.staff)
        w, d = self.workflow(nodes, model=self.CLAIM)
        self.publish(w, d)
        claim = self.claim(state, employee=employee)
        return w, claim, self.start(w, claim)

    def strip(self, person, model, record_id):
        return self.env['pb.workflow.studio'].with_user(person).with_company(self.company).record_runs(model, record_id)['strip']

    def test_wf2p4b_t1_the_strip_shows_only_when_there_is_something(self):
        self.need(self.CLAIM)
        self.expense_access(self.admin, self.staff)
        plain = self.claim('approved')
        self.assertIsNone(self.strip(self.admin, self.CLAIM, plain.id), 'nothing to show, no strip')
        w, claim, run = self.claim_flow([self.todo('check', owner={'kind': 'user', 'id': self.staff.id}, title='Check receipt')])
        step = self.step(run, 'check')
        mine = self.strip(self.staff, self.CLAIM, claim.id)
        self.assertEqual(len(mine['workflows']), 1)
        row = mine['workflows'][0]
        self.assertEqual((row['action'], row['task_id'], row['sentence']), ('do', step.id, 'Waiting for you: Check receipt'))
        self.assertTrue(mine['track'], 'the stage track comes with it')
        self.assertTrue(any(t['state'] == 'here' for t in mine['track']))
        full = self.strip(self.admin, self.CLAIM, claim.id)
        self.assertEqual(full['workflows'][0]['sentence'], 'Waiting for %s: Check receipt' % self.staff.name)
        self.assertEqual(full['workflows'][0]['action'], 'view')
        # Someone with no progress rights and nothing of their own: no strip.
        outsider = self.staffer('WF2 P4b outsider')
        self.expense_access(outsider)
        self.assertIsNone(self.strip(outsider, self.CLAIM, claim.id))
        # A person a company stage names may move it: the strip offers it.
        mover = self.staffer('WF2 P4b mover')
        self.expense_access(mover)
        stage = self.user_stage('WF2 P4b booked', anchor='approved', enter='person',
                                enter_owner={'kind': 'user', 'id': mover.id})
        moving = self.strip(mover, self.CLAIM, claim.id)
        self.assertEqual([m['name'] for m in moving['moves'] if m['allowed']], ['WF2 P4b booked'])
        self.assertEqual(moving['workflows'], [], 'no task of theirs, no workflow detail')
        self.assertEqual(moving['action'], 'move')
        self.assertEqual(self.strip(self.admin, self.CLAIM, claim.id)['workflows'][0]['action'], 'move', 'a designer may move')
        refused = next(m for m in self.strip(self.staff, self.CLAIM, claim.id)['moves'] if m['stage_id'] == stage.id)
        self.assertFalse(refused['allowed'])
        self.assertEqual(refused['reason'], 'Only %s can move this to WF2 P4b booked.' % mover.name)
        # Two workflows on one record: both.
        w2, d2 = self.workflow([self.todo('second', owner={'kind': 'user', 'id': self.admin.id})], model=self.CLAIM)
        self.publish(w2, d2)
        self.start(w2, claim)
        self.assertEqual(len(self.strip(self.admin, self.CLAIM, claim.id)['workflows']), 2)
        # A record with only a stage position (no workflow) still has a strip.
        lonely = self.claim('approved')
        self.service.with_user(mover).strip_move(self.CLAIM, lonely.id, stage.id)
        only = self.strip(self.admin, self.CLAIM, lonely.id)
        self.assertEqual(only['workflows'], [])
        self.assertTrue(only['sentence'].startswith('In WF2 P4b booked since'))

    def test_wf2p4b_t2_every_sentence_is_plain(self):
        self.need(self.CLAIM)
        self.expense_access(self.admin, self.staff)
        b = self.staffer('WF2 P4b teammate')
        role = self.team('WF2 P4b payroll', [self.staff, b])
        sentences = []
        # A team nobody has taken.
        w, claim, run = self.claim_flow([self.todo('team', owner={'kind': 'team', 'id': role.id}, title='Pay it')])
        row = self.strip(self.admin, self.CLAIM, claim.id)['workflows'][0]
        self.assertEqual(row['sentence'], 'Waiting for WF2 P4b payroll — nobody has taken it yet')
        sentences.append(row)
        # Late.
        step = self.step(run, 'team')
        internal(step).write({'due_at': fields.Datetime.now() - timedelta(days=2, hours=1)})
        row = self.strip(self.admin, self.CLAIM, claim.id)['workflows'][0]
        self.assertTrue(row['late'])
        self.assertEqual(row['tone'], 'late')
        self.assertRegex(row['meta'], r'^Late by \d+ days?$')
        sentences.append(row)
        # Covered while away.
        cover = self.staffer('WF2 P4b covering')
        self.expense_access(cover)
        self.env['biz.approval.delegation'].create({
            'company_id': self.company.id, 'principal_user_id': b.id, 'delegate_user_id': cover.id,
            'date_from': fields.Date.today(), 'date_to': fields.Date.today() + timedelta(days=5),
            'reason': 'Annual leave', 'state': 'active'})
        self.expense_access(b)
        w2, claim2, run2 = self.claim_flow([self.todo('cover', owner={'kind': 'user', 'id': b.id}, title='Check it')])
        row = self.strip(self.admin, self.CLAIM, claim2.id)['workflows'][0]
        self.assertEqual(row['sentence'], 'Waiting for %s, covering for %s: Check it' % (cover.name, b.name))
        sentences.append(row)
        # By link: the person has no login, only a work email (masked).
        nolog = self.employee('WF2 P4b no login', work_email='mai.tran@example.com')
        w3, claim3, run3 = self.claim_flow([{'id': 'ok', 'type': 'confirm', 'title': 'Confirm trip', 'stage': 0, 'due': 2,
                                             'owner': {'kind': 'subject'}, 'text': 'It was a work trip.'}], employee=nolog)
        row = self.strip(self.admin, self.CLAIM, claim3.id)['workflows'][0]
        self.assertEqual(row['sentence'], 'Waiting for WF2 P4b no login by email link (m***@example.com)')
        self.assertEqual(row['resend_id'], self.step(run3, 'ok').id, 'progress viewers may send it again')
        self.assertNotIn('mai.tran', str(row))
        sentences.append(row)
        # Stopped and done.
        internal(run3).write({'state': 'cancelled', 'ended_at': fields.Datetime.now()})
        row = self.strip(self.admin, self.CLAIM, claim3.id)['workflows'][0]
        self.assertTrue(row['sentence'].startswith('Stopped on '))
        self.assertEqual(row['tone'], 'stopped')
        sentences.append(row)
        internal(run2).write({'state': 'done', 'ended_at': fields.Datetime.now()})
        row = self.strip(self.admin, self.CLAIM, claim2.id)['workflows'][0]
        self.assertTrue(row['sentence'].startswith('Done on '))
        sentences.append(row)
        for row in sentences:
            for words in (row['sentence'], row['meta']):
                self.assertFalse(self.BANNED.search(words), words)
                self.assertNotIn('run', words.lower().split(), words)

    def test_wf2p4b_t3_a_fault_in_the_strip_never_breaks_the_form(self):
        w, claim, run = self.claim_flow([self.todo('check', owner={'kind': 'user', 'id': self.staff.id})])
        Studio = type(self.env['pb.workflow.studio'])
        with patch.object(Studio, '_strip_row', side_effect=RuntimeError('boom')), \
                self.assertLogs('odoo.addons.pb_lifecycle.models.workflow_strip', level='ERROR'):
            result = self.service.record_runs(self.CLAIM, claim.id)
        self.assertIsNone(result['strip'])
        self.assertEqual([r['id'] for r in result['runs']], [run.id], 'the rest of the answer is intact')
        with patch.object(Studio, '_strip_row', side_effect=RuntimeError('boom')), \
                self.assertLogs('odoo.addons.pb_lifecycle.models.workflow_strip', level='ERROR'):
            self.assertIsNone(self.service.record_strip(self.CLAIM, claim.id)['strip'])

    def test_wf2p4b_t4_the_employee_page_shows_only_their_own_and_its_own_words(self):
        self.need(self.CLAIM)
        portal, emp = self.portal_person('WF2 P4b claimant')
        w, claim, run = self.claim_flow([self.todo('check', owner={'kind': 'user', 'id': self.staff.id}, title='Check receipt')],
                                        employee=emp)
        home = self.env['pb.me.home'].with_user(portal)
        strip = home._wf_page_strip('expense_claim', claim.id)
        self.assertTrue(strip)
        self.assertEqual(set(strip), {'model', 'record_id', 'track', 'exits', 'compact', 'workflows', 'moves', 'sentence',
                                      'adds'})
        row = strip['workflows'][0]
        self.assertLessEqual(set(row), {'state', 'sentence', 'meta', 'tone', 'task_id', 'late', 'who', 'url'})
        self.assertEqual(row['sentence'], 'Waiting for %s: Check receipt' % self.staff.name)
        # Another employee: nothing.
        other, _emp = self.portal_person('WF2 P4b someone else')
        self.assertIsNone(self.env['pb.me.home'].with_user(other)._wf_page_strip('expense_claim', claim.id))
        # One word per status: the page's own word for "approved".
        words = self.env['pb.me.home']._wf_expense_words()
        here = next(t for t in strip['track'] if t['state'] == 'here')
        self.assertEqual(here['name'], words['approved'])
        html = str(self.env['ir.qweb']._render('pb_lifecycle.workflow_strip_page', {'s': strip, 'back': '/my/expenses/%s' % claim.id}))
        self.assertIn(words['approved'], html)
        contract_word = next(s['name'] for s in self.service._contract(self.CLAIM)['stages'] if s['key'] == 'approved')
        if contract_word != words['approved']:
            self.assertNotIn('>%s<' % contract_word, html, 'never two words for one status on a page')
        self.assertNotIn(w.name, html, 'no workflow name on the employee home')
        # My requests: one quiet line, the status word untouched.
        src = next(s for s in home._my_requests_sources() if s['model'] == self.CLAIM)
        rows = home._my_requests_rows(src, emp)
        line = next(r for r in rows if r['id'] == claim.id)
        self.assertRegex(line['wf_line'], r'^Stage \d+ of \d+ · with ')
        self.assertEqual(line['state_label'], src['states']['approved'][0])

    def test_wf2p4b_t5_the_employee_moves_it_only_when_the_stage_names_them(self):
        self.need(self.CLAIM)
        portal, emp = self.portal_person('WF2 P4b mover at home')
        stage = self.user_stage('WF2 P4b handed in', anchor='approved', enter='person', enter_owner={'kind': 'subject'})
        auto = self.user_stage('WF2 P4b by itself', anchor='approved')
        early = self.user_stage('WF2 P4b early', anchor='submitted', enter='person', enter_owner={'kind': 'subject'})
        self.expense_access()
        claim = self.claim('approved', employee=emp)
        Studio = self.env['pb.workflow.studio'].sudo().with_user(portal)
        strip = self.env['pb.me.home'].with_user(portal)._wf_page_strip('expense_claim', claim.id)
        self.assertIsNone(strip, 'nothing to show yet')
        other, _o = self.portal_person('WF2 P4b not them')
        self.assertEqual(self.env['pb.workflow.studio'].sudo().with_user(other)._home_move(other, self.CLAIM, claim.id, stage.id)['code'], 'who')
        self.assertEqual(Studio._home_move(portal, self.CLAIM, claim.id, early.id)['code'], 'gone', 'the rules forbid it')
        self.assertEqual(Studio._home_move(portal, self.CLAIM, claim.id, auto.id)['code'], 'auto')
        self.assertEqual(Studio._home_move(portal, 'res.partner', 1, stage.id)['code'], 'gone', 'only areas with a contract')
        result = Studio._home_move(portal, self.CLAIM, claim.id, stage.id)
        self.assertTrue(result['ok'], result)
        self.assertEqual(self.positions(self.CLAIM, claim.id).stage_id, stage)
        self.assertEqual(self.positions(self.CLAIM, claim.id).entered_by, portal)
        claim.invalidate_recordset()
        self.assertEqual(claim.state, 'approved', 'the area status is never written')
        strip = self.env['pb.me.home'].with_user(portal)._wf_page_strip('expense_claim', claim.id)
        self.assertEqual(next(t for t in strip['track'] if t['state'] == 'here')['name'], 'WF2 P4b handed in')

    def test_wf2p4b_t6_stays_are_counted_with_or_without_a_workflow(self):
        self.need(self.CLAIM)
        self.expense_access()
        a = self.user_stage('WF2 P4b first', anchor='approved', enter='person', enter_owner={'kind': 'user', 'id': self.admin.id})
        b = self.user_stage('WF2 P4b second', anchor='approved', enter='person', enter_owner={'kind': 'user', 'id': self.admin.id})
        claim = self.claim('approved')
        Visit = self.env['pb.workflow.stage.visit'].sudo()
        self.service.move_record_stage(self.CLAIM, claim.id, a.id)
        self.service.move_record_stage(self.CLAIM, claim.id, b.id)
        stays = Visit.search([('res_model', '=', self.CLAIM), ('res_id', '=', claim.id)], order='id')
        self.assertEqual(stays.mapped('stage_id'), a | b)
        self.assertTrue(stays[0].left_at and not stays[1].left_at)
        self.assertEqual(set(stays.mapped('company_id').ids), {self.company.id})
        self.assertEqual(stays[1].entered_by, self.admin)
        with self.assertRaises(AccessError):
            self.env['pb.workflow.stage.visit'].with_user(self.admin).create({
                'company_id': self.company.id, 'res_model': self.CLAIM, 'res_id': claim.id,
                'stage_id': a.id, 'entered_at': fields.Datetime.now()})
        # Leaving the status closes the stay (the stale row is removed).
        claim._chain_engine_write('paid')
        self.assertFalse(self.service._record_position(self.CLAIM, claim.id))
        stays.invalidate_recordset()
        self.assertTrue(stays[1].left_at)
        # Backfill makes only what the history proves.
        w, d = self.staged('', [], [])
        x = self.user_stage('WF2 P4b x', model='', workflow=w, enter='person', enter_owner={'kind': 'user', 'id': self.admin.id})
        y = self.user_stage('WF2 P4b y', model='', workflow=w, enter='person', enter_owner={'kind': 'user', 'id': self.admin.id})
        z = self.user_stage('WF2 P4b z', model='', workflow=w, enter='person', enter_owner={'kind': 'user', 'id': self.admin.id})
        self.publish(w, d)
        run = self.start(w)
        Studio = self.env['pb.workflow.studio'].sudo()
        Studio._set_position('pb.workflow.run', run.id, x, self.company, run=run.sudo())
        Studio._set_position('pb.workflow.run', run.id, y, self.company, run=run.sudo())
        self.env.cr.execute('DELETE FROM pb_workflow_stage_visit')
        self.env.invalidate_all()
        made = Visit._backfill()
        rebuilt = Visit.search([('res_model', '=', 'pb.workflow.run'), ('res_id', '=', run.id)], order='entered_at, id')
        self.assertEqual(rebuilt.mapped('stage_id'), x | y)
        self.assertTrue(rebuilt[0].left_at and not rebuilt[1].left_at, 'y is where it is today')
        self.assertTrue(all(rebuilt.mapped('backfilled')))
        self.assertGreaterEqual(made, 2)
        self.assertFalse(Visit.search([('stage_id', '=', z.id)]), 'never entered, never invented')
        self.assertEqual(Visit._backfill(), 0, 'once only')

    def test_wf2p4b_t7_where_time_goes_is_counted_right(self):
        self.need(self.CLAIM)
        self.expense_access()
        stage = self.user_stage('WF2 P4b checked', anchor='approved', target_hours=2)
        w, d = self.workflow([self.todo('check', owner={'kind': 'user', 'id': self.admin.id}, title='Check receipt')], model=self.CLAIM)
        self.publish(w, d)
        Visit = internal(self.env['pb.workflow.stage.visit'])
        base = fields.Datetime.now() - timedelta(days=3)
        for i, hours in enumerate((1, 2, 3, 4, 5)):
            claim = self.claim('approved')
            run = self.start(w, claim)
            step = self.step(run, 'check')
            self.assertEqual(step.assignee_id, self.admin, step.error)
            internal(step).write({'state': 'done', 'started_at': base, 'done_at': base + timedelta(hours=hours)})
            stay = (1, 1, 3, 3, 3)[i]
            Visit.create({'company_id': self.company.id, 'res_model': self.CLAIM, 'res_id': claim.id,
                          'stage_id': stage.id, 'entered_at': base, 'left_at': base + timedelta(hours=stay)})
        other = self.env['res.company'].create({'name': 'WF2 P4b elsewhere'})
        Visit.create({'company_id': other.id, 'res_model': self.CLAIM, 'res_id': claim.id, 'stage_id': stage.id,
                      'entered_at': base - timedelta(days=1), 'left_at': base + timedelta(hours=60)})
        w2, d2 = self.workflow([self.todo('check', owner={'kind': 'user', 'id': self.admin.id})], model=self.CLAIM)
        self.publish(w2, d2)
        run2 = self.start(w2, self.claim('approved'))
        internal(self.step(run2, 'check')).write({'state': 'done', 'started_at': base, 'done_at': base + timedelta(hours=1)})
        w3, d3 = self.workflow([self.todo('x')], model=self.CLAIM)
        self.publish(w3, d3)
        aw, _ad = self.approval_workflow()
        arun = self.start(aw, self.generic())
        # Whole hours from here on, so the numbers are exact by hand.
        self.company.resource_calendar_id = False
        report = self.service.time_report(w.id, '30')
        self.assertFalse(report['empty'])
        self.assertFalse(report['calendar'])
        step_row = next(s for s in report['steps'] if s['key'] == 'check')
        self.assertEqual((step_row['samples'], step_row['enough'], step_row['median_words']), (5, True, '3 h'))
        self.assertEqual(step_row['who'], self.admin.name)
        row = next(s for s in report['stages'] if s['kind'] == 'yours' and s['key'] == str(stage.id))
        self.assertEqual((row['samples'], row['median_words'], row['p90_words'], row['late_share']), (5, '3 h', '3 h', 60),
                         'the other company’s long stay is not counted')
        self.assertAlmostEqual(sum(s['share'] for s in report['stages']), 100.0, delta=0.5)
        # Under five: "not enough yet".
        few = next(s for s in self.service.time_report(w2.id, 'all')['steps'] if s['key'] == 'check')
        self.assertEqual((few['enough'], few['median_words']), (False, ''))
        # Nothing has run: the empty state.
        self.assertTrue(self.service.time_report(w3.id)['empty'])
        # Approval steps are read, never written.
        request = self.step(arun, 'approval').approval_id
        stamp = request.write_date
        arow = next(s for s in self.service.time_report(aw.id)['steps'] if s['key'] == 'approval')
        self.assertTrue(arow['approval'])
        self.assertEqual(arow['who'], 'Approvals')
        request.invalidate_recordset()
        self.assertEqual(request.write_date, stamp)
        with self.assertRaises(AccessError):
            self.service.with_user(self.staff).time_report(w.id)

    def test_wf2p4b_t8_the_candidate_takes_part_by_link(self):
        self.need('pb.hiring', 'hr.applicant')
        self.recruiter()
        confirm = {'id': 'agree', 'type': 'confirm', 'title': 'Confirm your details', 'stage': 1, 'due': 2,
                   'owner': {'kind': 'participant', 'key': 'candidate'}, 'text': 'My details are right.'}
        w, d = self.workflow([dict(confirm, stage=0)], model='hr.applicant')
        self.assertEqual(self.codes(w, d), [])
        meta = self.service.metadata('hr.applicant', w.id)
        self.assertEqual(meta['participants'], [{'key': 'candidate', 'label': 'The candidate'}])
        self.assertIn('participant_link', [n['code'] for n in self.service._people_notes(w, d)])
        self.publish(w, d)
        applicant = self.env['hr.applicant'].create({'partner_name': 'WF2 P4b candidate', 'email_from': 'cand@example.com',
                                                     'company_id': self.company.id})
        run = self.start(w, applicant)
        step = self.step(run, 'agree')
        self.assertEqual(step.state, 'waiting', step.error)
        self.assertEqual((step.sudo().link_email, step.link_name), ('cand@example.com', 'WF2 P4b candidate'))
        self.assertFalse(step.assignee_id, 'never a user')
        self.assertTrue(len(step.sudo().access_token) >= 32)
        mail = self.env['mail.mail'].sudo().search([('email_to', '=', 'cand@example.com')], order='id desc', limit=1)
        self.assertTrue(mail)
        # The link page shows the step and nothing of the record around it.
        page = self.env['pb.workflow.studio'].sudo()._page_data(step, ('file', 'lookup'))
        self.assertEqual(page['record'], '')
        self.assertNotIn(w.name, page['workflow'])
        # No email: since WF2 P2b (D24) the step waits and somebody is asked
        # to add the address (test_wf2p2b_t16); it no longer stops.
        quiet = self.env['hr.applicant'].create({'partner_name': 'WF2 P4b no email', 'company_id': self.company.id})
        waiting = self.step(self.start(w, quiet), 'agree')
        self.assertEqual(waiting.state, 'waiting', waiting.error)
        self.assertFalse(waiting.sudo().link_email)
        # A form with a file is refused; a notice too.
        form = self.form('papers', fields_=[{'id': 'cv', 'type': 'file', 'label': 'CV', 'required': True}],
                         owner={'kind': 'participant', 'key': 'candidate'})
        self.assertIn('participant_cannot', self.codes(*self.workflow([form], model='hr.applicant')))
        notice = {'id': 'tell', 'type': 'notify', 'title': 'Tell', 'stage': 0, 'text': 'Hello',
                  'owner': {'kind': 'participant', 'key': 'candidate'}}
        self.assertIn('participant_notice', self.codes(*self.workflow([notice], model='hr.applicant')))
        self.assertIn('bad_participant', self.codes(*self.workflow([dict(confirm, stage=0, owner={'kind': 'participant', 'key': 'boss'})],
                                                                   model='hr.applicant')))
        # Somewhere Hiring already emails the candidate: Review warns.
        self.env['pb.hiring.automation.rule'].create({
            'company_id': self.company.id, 'event': 'stage_entered', 'action': 'send_email', 'recipient': 'candidate',
            'stage_id': self.env['hr.recruitment.stage']._pb_stage('screening').id})
        w2, d2 = self.staged('hr.applicant', [('Screening', self.core('screening'))], [confirm])
        warning = next(i for i in self.service._validate(w2, d2) if i['code'] == 'repeats_existing' and i['id'] == 'agree')
        self.assertIn('already emails the candidate here', warning['text'])
        self.assertEqual(warning['severity'], 'warning')
        # A stage mover is always staff.
        with self.assertRaises(UserError):
            self.service._check_owner('hr.applicant', self.company, {'kind': 'participant', 'key': 'candidate'})

    def test_wf2p4b_t9_late_with_no_manager_tells_the_named_role(self):
        Studio = self.env['pb.workflow.studio'].sudo()
        now = fields.Datetime.now()
        lead = self.staffer('WF2 P4b HR lead')
        role = self.env['biz.approval.role'].create({'key': 'wf2p4b_%s' % uuid.uuid4().hex[:8], 'name': 'WF2 P4b HR lead'})
        self.env['biz.approval.responsibility'].create({'company_id': self.company.id, 'role_id': role.id,
                                                        'scope_key': '', 'user_id': lead.id})

        def late_step(owner, late_tell=None):
            w, d = self.workflow([self.todo('do', owner=owner)])
            if late_tell:
                d['late_tell'] = late_tell
            self.assertNotIn('late_tell', self.codes(w, d))
            self.publish(w, d)
            step = self.step(self.start(w), 'do')
            internal(step).write({'due_at': now - timedelta(days=3)})
            Studio._chase_late(now)
            return step
        # A line manager comes first, the role is not asked.
        boss = self.staffer('WF2 P4b boss')
        managed = self.staffer('WF2 P4b managed')
        self.employee('WF2 P4b managed', user=managed, parent_id=self.employee('WF2 P4b boss', user=boss).id)
        step = late_step({'kind': 'user', 'id': managed.id}, {'id': role.id})
        self.assertTrue(self.outbox('task_passed_up', boss))
        self.assertEqual(step.passed_up_to, 'manager')
        self.assertTrue(Studio._passed_up_words(step).startswith('Their manager was told on '))
        # Nobody manages them: the named role.
        step = late_step({'kind': 'user', 'id': self.staff.id}, {'id': role.id})
        told = self.outbox('task_passed_up', lead).filtered(lambda o: o.payload.get('res_id') == step.run_id.id)
        self.assertEqual(len(told), 1)
        self.assertEqual(step.passed_up_to, 'WF2 P4b HR lead')
        self.assertTrue(self.service.progress(step.run_id.id)['steps'][1]['passed_up'].startswith('WF2 P4b HR lead was told on '))
        # No role named: the publisher, as before.
        step = late_step({'kind': 'user', 'id': self.staff.id})
        self.assertTrue(self.outbox('task_passed_up', self.admin).filtered(lambda o: o.payload.get('res_id') == step.run_id.id))
        self.assertEqual(step.passed_up_to, 'publisher')
        # Never the person it waits for, never the system account.
        step = late_step({'kind': 'user', 'id': lead.id}, {'id': role.id})
        self.assertFalse(self.outbox('task_passed_up', lead).filtered(lambda o: o.payload.get('res_id') == step.run_id.id))
        # The role's holder in another company is never used.
        other = self.env['res.company'].create({'name': 'WF2 P4b other'})
        far = self.env['biz.approval.role'].create({'key': 'wf2p4b_%s' % uuid.uuid4().hex[:8], 'name': 'WF2 P4b far'})
        stranger = self.staffer('WF2 P4b stranger')
        stranger.write({'company_ids': [(4, other.id)]})
        self.env['biz.approval.responsibility'].create({'company_id': other.id, 'role_id': far.id,
                                                        'scope_key': '', 'user_id': stranger.id})
        step = late_step({'kind': 'user', 'id': self.staff.id}, {'id': far.id})
        self.assertFalse(self.outbox('task_passed_up', stranger))
        self.assertEqual(step.passed_up_to, 'publisher')
        # A role that does not exist is refused at design time.
        w, d = self.workflow([self.todo('do')])
        d['late_tell'] = {'id': 0}
        self.assertIn('late_tell', self.codes(w, d))
        self.assertIn('late_fallback', [n['code'] for n in self.service._people_notes(*self.workflow([self.todo('do')]))])

    def test_wf2p4b_t10_the_dock_line_counts_tasks_and_leaves_approvals_alone(self):
        Inbox = self.env['pb.approval.inbox'].with_user(self.staff)
        before = Inbox.get_team_data(scope='team', queues_only=True)
        counts_before = self.inbox(self.staff)._counts('me')
        w, d = self.workflow([self.todo('a', owner={'kind': 'user', 'id': self.staff.id}),
                              self.todo('b', owner={'kind': 'user', 'id': self.staff.id})])
        self.publish(w, d)
        self.start(w)
        after = Inbox.get_team_data(scope='team', queues_only=True)
        self.assertEqual(after['queues']['tasks'], before['queues'].get('tasks', 0) + 1, 'the first waiting task')
        self.assertEqual({k: v for k, v in after['queues'].items() if k != 'tasks'},
                         {k: v for k, v in before['queues'].items() if k != 'tasks'}, 'approvals untouched')
        counts = self.inbox(self.staff)._counts('me')
        self.assertEqual({k: counts[k] for k in ('mine', 'all', 'returned', 'done')},
                         {k: counts_before[k] for k in ('mine', 'all', 'returned', 'done')})

    def test_wf2p4b_t11_new_doors_check_first_and_never_write_status(self):
        root = os.path.join(os.path.dirname(os.path.dirname(__file__)))
        mine = open(os.path.join(root, 'controllers', 'my_tasks.py'), encoding='utf-8').read()
        body = mine.split('def my_todo_move', 1)[1].split('\n    @http.route', 1)[0]
        self.assertLess(body.index('_is_public()'), body.index('self._studio()'))
        self.assertIn('_home_move(person,', body)
        self.assertNotIn('csrf=False', mine)
        strip = open(os.path.join(root, 'models', 'workflow_strip.py'), encoding='utf-8').read()
        move = strip.split('def _home_move', 1)[1].split('\n    def ', 1)[0]
        for check in ("_workflow_capabilities", "stage.company_id != record.company_id", "_home_names(person"):
            self.assertLess(move.index(check), move.index('_set_position('), check)
        for name in ('workflow_strip.py', 'workflow_time.py', 'workflow_reach.py'):
            text = open(os.path.join(root, 'models', name), encoding='utf-8').read()
            self.assertFalse(re.search(r'\b(source|record|records|rec)\b\.(state|stage_id)\s*=[^=]', text), name)
            self.assertFalse(re.search(r'\b(source|record|records|rec)\b(\.\w+\([^)]*\))*\.write\(', text), name)
            self.assertNotIn('_chain_engine_write', text, name)
        for view in ('workflow_strip_page.xml', 'workflow_task_page.xml'):
            self.assertNotIn('t-raw', open(os.path.join(root, 'views', view), encoding='utf-8').read())
        # The employee page asks for a strip only on pages it knows.
        Home = self.env['pb.me.home'].with_user(self.staff)
        self.assertIsNone(Home._wf_page_strip('my_requests', 1))
        self.assertIsNone(self.env['pb.workflow.studio'].sudo()._home_strip(self.env.ref('base.public_user'), self.CLAIM, 1))

    # ================================================================ WF2 P2b
    def own_stage(self, name, anchor):
        self.service.stage_create(self.CLAIM, None, {'name': name, 'anchor_value': anchor})
        return self.env['pb.workflow.stage'].sudo().search([
            ('source_model', '=', self.CLAIM), ('name', '=', name), ('company_id', '=', self.company.id)], limit=1)

    def test_wf2p2b_t15_the_claim_page_strip_only_when_it_adds_something(self):
        self.need(self.CLAIM)
        portal, emp = self.portal_person('WF2 P2b claimant')
        w, claim, run = self.claim_flow([self.todo('check', owner={'kind': 'user', 'id': self.staff.id}, title='Check')],
                                        employee=emp)
        home = self.env['pb.me.home'].with_user(portal)
        # a person's step is involved: the strip shows
        self.assertTrue(home._wf_page_strip('expense_claim', claim.id))
        # nothing but the workflow's end (or an approval) left: the page's own
        # "With X" box is enough, so no strip
        internal(run).write({'state': 'done', 'ended_at': fields.Datetime.now()})
        self.assertIsNone(home._wf_page_strip('expense_claim', claim.id))
        # staff screens are unchanged: they still show the finished workflow
        self.assertTrue(self.strip(self.admin, self.CLAIM, claim.id))
        # a stage the company made is involved: the strip shows again
        stage = self.own_stage('WF2 P2b Booked', 'approved')
        self.service._set_position(self.CLAIM, claim.id, stage, self.company)
        shown = home._wf_page_strip('expense_claim', claim.id)
        self.assertTrue(shown and shown['adds'])

    def test_wf2p2b_t16_candidate_without_email_asks_the_recruiter(self):
        self.need('pb.hiring', 'hr.applicant')
        self.recruiter()
        recruiter = self.staffer('WF2 P2b recruiter', ['hr_recruitment.group_hr_recruitment_user'])
        confirm = {'id': 'agree', 'type': 'confirm', 'title': 'Confirm your details', 'stage': 0, 'due': 2,
                   'owner': {'kind': 'participant', 'key': 'candidate'}, 'text': 'My details are right.'}
        w, d = self.workflow([confirm], model='hr.applicant')
        self.publish(w, d)
        quiet = self.env['hr.applicant'].create({'partner_name': 'WF2 P2b no email', 'company_id': self.company.id,
                                                 'user_id': recruiter.id})
        run = self.start(w, quiet)
        step = self.step(run, 'agree')
        self.assertEqual(step.state, 'waiting', step.error)
        self.assertEqual(step.assignee_id, recruiter)
        self.assertFalse(step.sudo().link_email)
        todo = step.activity_id
        self.assertEqual((todo.res_model, todo.res_id, todo.user_id), ('hr.applicant', quiet.id, recruiter))
        self.assertEqual(todo.summary, 'Add an email for WF2 P2b no email')
        summary = todo.summary
        # one task in the Approvals inbox, that opens the candidate
        cards = [c for c in self.inbox(recruiter)._extra_items('me') if c['id'] == step.id]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['title'], 'Add an email for WF2 P2b no email')
        self.assertEqual(cards[0]['open'], {'type': 'record', 'model': 'hr.applicant', 'id': quiet.id})
        # the record's own strip says the same, with no "Do it now"
        row = self.strip(recruiter, 'hr.applicant', quiet.id)['workflows'][0]
        self.assertEqual(row['sentence'], 'Waiting for you: add an email for WF2 P2b no email')
        self.assertFalse(row['task_id'])
        # it cannot be "answered" on the candidate's behalf
        with self.assertRaises(UserError):
            self.service.with_user(recruiter).answer(step.id, {})
        # the worker looks again: still no email, nothing changes
        self.env['pb.workflow.studio'].sudo()._cron_workflows()
        self.assertEqual(self.step(run, 'agree').assignee_id, recruiter)
        # the email is added: the link goes out once and the helper task closes
        quiet.email_from = 'late.cand@example.com'
        self.env['pb.workflow.studio'].sudo()._cron_workflows()
        step = self.step(run, 'agree')
        self.assertEqual(step.state, 'waiting')
        self.assertEqual(step.sudo().link_email, 'late.cand@example.com')
        self.assertFalse(step.assignee_id)
        self.assertFalse(todo.exists())
        mails = self.env['mail.mail'].sudo().search([('email_to', '=', 'late.cand@example.com')])
        self.assertEqual(len(mails), 1)
        self.env['pb.workflow.studio'].sudo()._cron_workflows()
        self.assertEqual(len(self.env['mail.mail'].sudo().search([('email_to', '=', 'late.cand@example.com')])), 1,
                         'sent once')
        # nobody named on the record: whoever published the workflow is asked
        nobody = self.env['hr.applicant'].create({'partner_name': 'WF2 P2b nobody', 'company_id': self.company.id})
        other = self.step(self.start(w, nobody), 'agree')
        self.assertEqual(other.state, 'waiting', other.error)
        self.assertEqual(other.assignee_id, w.sudo().published_id.published_by)
        for words in (summary, cards[0]['title'], cards[0]['verb']):
            self.assertFalse(re.search(r'odoo', words, re.I), words)

    def test_wf2p2b_t12_studio_warns_before_a_second_claim_email(self):
        self.need(self.CLAIM)
        template = self.env['mail.template'].create({
            'name': 'WF2 P2b claim note', 'model_id': self.env['ir.model']._get_id(self.CLAIM),
            'subject': 'Claim', 'body_html': '<p>Claim</p>'})
        tell = {'id': 'tell', 'type': 'email', 'title': 'Tell them', 'stage': 1, 'audience': 'requester',
                'template_id': template.id, 'purpose': 'A second note'}
        w, d = self.staged(self.CLAIM, [('Approved', self.core('approved'))], [tell])
        warning = next(i for i in self.service._validate(w, d) if i['code'] == 'repeats_existing')
        self.assertIn('Expenses already does this here', warning['text'])
        self.assertIn('approved', warning['text'])

    def test_wf2p2b_t17_no_banned_words_in_this_phase(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        files = ['pb_me_expense/models/expense_messages.py', 'pb_me_expense/data/mail_template_data.xml',
                 'biz_approval_workflow/models/single_notice.py']
        for name in files:
            path = os.path.join(root, name)
            if not os.path.exists(path):
                continue
            text = open(path, encoding='utf-8').read()
            strings = re.findall(r"_\('([^']*)'", text) + re.findall(r'_\("([^"]*)"', text)
            for s in strings:
                self.assertNotRegex(s, r'(?i)odoo', name)
        reach = open(os.path.join(root, 'pb_lifecycle/models/workflow_reach.py'), encoding='utf-8').read()
        part = reach.split('# ================================================================ D24', 1)[1].split(
            '# ================================================================ D19', 1)[0]
        for s in re.findall(r"_\('([^']*)'", part):
            self.assertNotRegex(s, r'(?i)odoo|\bstep\b|\brun\b|\bnode\b', s)

    # ------------------------------------------------------------------
    # WORKFLOW-2 P5a: the instant email re-check (P2b leftover) and
    # "Start on a schedule".
    # ------------------------------------------------------------------
    def test_wf2p5a_t4b_candidate_email_saved_sends_the_link_at_once(self):
        self.need('pb.hiring', 'hr.applicant')
        self.recruiter()
        recruiter = self.staffer('WF2 P5a recruiter', ['hr_recruitment.group_hr_recruitment_user'])
        confirm = {'id': 'agree', 'type': 'confirm', 'title': 'Confirm your details', 'stage': 0, 'due': 2,
                   'owner': {'kind': 'participant', 'key': 'candidate'}, 'text': 'My details are right.'}
        w, d = self.workflow([confirm], model='hr.applicant')
        self.publish(w, d)
        quiet = self.env['hr.applicant'].create({'partner_name': 'WF2 P5a no email', 'company_id': self.company.id,
                                                 'user_id': recruiter.id})
        run = self.start(w, quiet)
        step = self.step(run, 'agree')
        self.assertEqual(step.assignee_id, recruiter)
        todo = step.activity_id
        # the recruiter types the address: no worker pass in between
        quiet.with_user(self.admin).write({'email_from': 'p5a.cand@example.com'})
        step = self.step(run, 'agree')
        self.assertEqual(step.sudo().link_email, 'p5a.cand@example.com')
        self.assertFalse(step.assignee_id)
        self.assertFalse(todo.exists())
        self.assertEqual(len(self.env['mail.mail'].sudo().search([('email_to', '=', 'p5a.cand@example.com')])), 1)
        # the worker afterwards changes nothing (sent once)
        self.env['pb.workflow.studio'].sudo()._cron_workflows()
        self.assertEqual(len(self.env['mail.mail'].sudo().search([('email_to', '=', 'p5a.cand@example.com')])), 1)
        # a save that is not about the email never looks
        with patch.object(type(self.env['pb.workflow.studio']), '_recheck_awaiting_email') as spy:
            quiet.write({'partner_name': 'WF2 P5a renamed'})
            spy.assert_not_called()

    def test_wf2p5a_t5_schedule_maths(self):
        from datetime import datetime
        from odoo.addons.pb_lifecycle.models import workflow_schedule as WS
        at = datetime(2026, 11, 11, 3, 0)
        nxt = lambda s, tz='UTC', n=5, working=None: WS.next_ticks(dict(s), tz, at, n, working)
        # every day / every Monday (Sydney: 9:00 local = 22:00 UTC the day before)
        self.assertEqual(nxt({'every': 'day', 'at': '09:00'}, n=2),
                         [datetime(2026, 11, 11, 9, 0), datetime(2026, 11, 12, 9, 0)])
        self.assertEqual(nxt({'every': 'week', 'at': '09:00', 'weekdays': [0]}, 'Australia/Sydney', 2),
                         [datetime(2026, 11, 15, 22, 0), datetime(2026, 11, 22, 22, 0)])
        # "31st" in a 30-day month = the last day; "last"
        self.assertEqual([t.date().isoformat() for t in nxt({'every': 'month', 'at': '12:00', 'day': 31}, n=4)],
                         ['2026-11-30', '2026-12-31', '2027-01-31', '2027-02-28'])
        self.assertEqual([t.day for t in nxt({'every': 'month', 'at': '12:00', 'day': 'last'}, n=3)], [30, 31, 31])
        # leap day: 28 Feb in common years, 29 Feb in 2028
        self.assertEqual([t.date().isoformat() for t in nxt({'every': 'year', 'at': '08:00', 'day': 29, 'month': 2}, n=3)],
                         ['2027-02-28', '2028-02-29', '2029-02-28'])
        # once: exactly one start, none after it has passed
        self.assertEqual(nxt({'every': 'once', 'at': '08:00', 'date': '2026-11-20'}), [datetime(2026, 11, 20, 8, 0)])
        self.assertEqual(nxt({'every': 'once', 'at': '08:00', 'date': '2026-11-01'}), [])
        # working days only: Saturday and Sunday move to Monday, once
        weekdays = lambda day: day.weekday() < 5
        got = WS.next_ticks({'every': 'day', 'at': '07:00', 'working_days': True}, 'UTC',
                            datetime(2026, 11, 13, 12, 0), 3, weekdays)
        self.assertEqual(got, [datetime(2026, 11, 16, 7, 0), datetime(2026, 11, 17, 7, 0), datetime(2026, 11, 18, 7, 0)])
        # clocks forward (Sydney, 4 Oct 2026): 2:30 does not exist → 3:30, once
        got = WS.next_ticks({'every': 'day', 'at': '02:30'}, 'Australia/Sydney', datetime(2026, 10, 2, 0, 0), 3)
        self.assertEqual(got, [datetime(2026, 10, 2, 16, 30), datetime(2026, 10, 3, 16, 30), datetime(2026, 10, 4, 15, 30)])
        # clocks back (Sydney, 5 Apr 2026): 2:30 happens twice → once, the first
        got = WS.ticks({'every': 'day', 'at': '02:30'}, 'Australia/Sydney', datetime(2026, 4, 4, 0, 0), datetime(2026, 4, 5, 12, 0))
        self.assertEqual(got, [datetime(2026, 4, 4, 15, 30)])
        # the worker's window: (after, until], latest last
        got = WS.ticks({'every': 'day', 'at': '09:00'}, 'UTC', datetime(2026, 11, 1, 9, 0), datetime(2026, 11, 8, 9, 0))
        self.assertEqual(len(got), 7)
        self.assertEqual(got[-1], datetime(2026, 11, 8, 9, 0))
        # words and checks
        self.assertEqual(WS.words({'every': 'week', 'at': '09:00', 'weekdays': [0]}), 'Every Monday at 9:00')
        self.assertEqual(WS.words({'every': 'week', 'at': '08:30', 'weekdays': [0, 1, 2, 3, 4]}), 'Every weekday at 8:30')
        self.assertEqual(WS.words({'every': 'month', 'at': '17:30', 'day': 'last'}), 'On the last day of each month at 17:30')
        self.assertEqual(WS.words({'every': 'year', 'at': '09:00', 'day': 1, 'month': 7}), 'Every year on 1 July at 9:00')
        codes = {c for c, _t in WS.issues({'every': 'week', 'at': '9', 'weekdays': [], 'starts': 'process'}, True)}
        self.assertEqual(codes, {'schedule_time', 'schedule_weekdays', 'schedule_starts'})
        self.assertFalse(WS.issues(WS.fresh(True), True))
        self.assertFalse(WS.issues(WS.fresh(False), False))

    def scheduled(self, nodes, model='', schedule=None, scope=None):
        w, d = self.workflow(nodes, model=model)
        d['trigger'] = {'kind': 'schedule', 'fields': [], 'date_field': '', 'delay': 0, 'unit': 'day',
                        'schedule': dict({'every': 'day', 'at': '09:00', 'working_days': False,
                                          'starts': 'each_record' if model else 'process'}, **(schedule or {}))}
        if scope:
            d['scope'] = scope
        return w, d

    def runs_of(self, w):
        return self.env['pb.workflow.run'].sudo().search([('workflow_id', '=', w.id)])

    def test_wf2p5a_t6_scheduled_new_process_starts_once_per_tick(self):
        node = self.todo('check', owner={'kind': 'user', 'id': self.staff.id}, title='Month-end checks')
        w, d = self.scheduled([node])
        self.publish(w, d)
        w = w.sudo()
        self.assertTrue(w.last_tick_at, 'switching on sets the clock to now')
        self.assertFalse(w.automation_id.active if w.automation_id else False, 'no rule, no new job')
        Studio = self.env['pb.workflow.studio'].sudo()
        # nothing due yet: nothing starts and nothing is written
        Studio._cron_workflows()
        self.assertFalse(self.runs_of(w))
        # a week with the system off: it starts once, and says so
        w.last_tick_at = fields.Datetime.now() - timedelta(days=7, hours=1)
        Studio._cron_workflows()
        runs = self.runs_of(w)
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs.scheduled_at)
        self.assertGreaterEqual(w.schedule_log[0]['missed'], 6)
        self.assertEqual(self.step(runs, 'check').assignee_id, self.staff)
        self.assertEqual(self.service.runs(w.id)[0]['initiator'], 'Started on schedule')
        rows = self.service.schedule_history(w.id)['rows']
        self.assertIn('earlier starts were missed while the system was off; it started once.', rows[0]['text'])
        # the same pass again (a retried job): nothing more
        Studio._cron_workflows()
        self.assertEqual(len(self.runs_of(w)), 1)
        # a window that reaches the same start again: its key makes no second run
        w.last_tick_at = fields.Datetime.now() - timedelta(hours=25)
        Studio._cron_workflows()
        self.assertEqual(len(self.runs_of(w)), 1)
        stamp = fields.Datetime.to_string(runs.scheduled_at)
        Studio._enqueue(w, 0, SUPERUSER_ID, 'schedule:%s:%s' % (w.id, stamp))
        Studio._cron_workflows()
        self.assertEqual(len(self.runs_of(w)), 1)
        # the next start (tomorrow's) is a new run
        w.last_tick_at = runs.scheduled_at - timedelta(days=1)
        w.schedule_log = []
        from odoo.addons.pb_lifecycle.models import workflow_schedule as WS
        with patch.object(WS, 'ticks', lambda *a, **k: [runs.scheduled_at + timedelta(days=1)]):
            Studio._cron_workflows()
        self.assertEqual(len(self.runs_of(w)), 2)

    def test_wf2p5a_t7_scheduled_each_record_filters_cap_pause(self):
        from odoo.addons.pb_lifecycle.models import workflow_schedule as WS
        node = self.todo('look', owner={'kind': 'user', 'id': self.staff.id}, title='Look at it')
        records = [self.generic('WF2 P5a sched %s' % n) for n in range(3)]
        self.generic('Not this one')
        scope = {'match': 'all', 'rules': [{'field': 'name', 'op': 'icontains', 'value': 'WF2 P5a sched'}]}
        w, d = self.scheduled([node], model=self.GENERIC, scope=scope)
        self.publish(w, d)
        w = w.sudo()
        Studio = self.env['pb.workflow.studio'].sudo()
        # preview: the same maths and the same filter as the worker
        preview = self.service.schedule_preview(w.id)
        self.assertTrue(preview['ok'])
        self.assertEqual(preview['count'], 3)
        self.assertEqual(len(preview['next']), 5)
        self.assertEqual(preview['names'][0], records[0].display_name)
        w.last_tick_at = fields.Datetime.now() - timedelta(hours=25)
        Studio._cron_workflows()
        runs = self.runs_of(w)
        self.assertEqual(sorted(runs.mapped('source_id')), sorted(r.id for r in records))
        self.assertTrue(all(runs.mapped('scheduled_at')))
        keys = self.env['pb.workflow.event'].sudo().search([('workflow_id', '=', w.id)]).mapped('key')
        self.assertTrue(all(k.startswith('schedule:%s:' % w.id) for k in keys))
        # the same start reached again: nothing more, no second history row
        w.last_tick_at = fields.Datetime.now() - timedelta(hours=25)
        Studio._cron_workflows()
        self.assertEqual(len(self.runs_of(w)), 3)
        self.assertEqual(len(w.schedule_log), 1)
        # the next start: each record still has its run going → none twice
        tick = runs[0].scheduled_at

        def later(*args, **kwargs):
            later.n += 1
            return [tick + timedelta(days=later.n)]
        later.n = 0
        with patch.object(WS, 'ticks', later):
            Studio._cron_workflows()
        self.assertEqual(len(self.runs_of(w)), 3)
        self.assertEqual(w.schedule_log[0]['reason'], 'already_running')
        # over the cap: nothing started, the reason kept, the publisher told once
        self.generic('WF2 P5a sched 4')
        with patch.object(WS, 'FAN_OUT_CAP', 3), patch.object(WS, 'ticks', later):
            Studio._cron_workflows()
            self.assertEqual(len(self.runs_of(w)), 3)
            self.assertEqual(w.schedule_log[0]['reason'], 'over_cap')
            told = self.outbox('schedule_problem', self.admin)
            self.assertEqual(len(told), 1)
            self.assertIn('4 records matched', told.payload['body'])
            # the same start looked at again: told once
            later.n -= 1
            Studio._cron_workflows()
            self.assertEqual(len(self.outbox('schedule_problem', self.admin)), 1)
            rows = self.service.schedule_history(w.id)['rows']
            self.assertTrue(rows[0]['problem'])
            told._deliver()
            note = self.env['mail.message'].sudo().search([
                ('model', '=', 'res.partner'), ('res_id', '=', self.admin.partner_id.id)], limit=1)
            self.assertIn('did not start on schedule', note.subject)
        # paused: nothing; switched on again: no catch-up
        self.service.activate(w.id, False)
        w.last_tick_at = fields.Datetime.now() - timedelta(days=3)
        Studio._cron_workflows()
        self.assertEqual(len(self.runs_of(w)), 3)
        self.service.activate(w.id, True)
        self.assertGreater(w.last_tick_at, fields.Datetime.now() - timedelta(minutes=5))
        Studio._cron_workflows()
        self.assertEqual(len(self.runs_of(w)), 3)

    def test_wf2p5a_t8_scheduled_design_rules_and_review(self):
        # nobody "starts" a scheduled workflow
        mine = self.todo('mine', title='Do it')   # owner: the person who starts it
        w, d = self.scheduled([mine])
        codes = {i['code'] for i in self.service._validate(w.sudo(), d)}
        self.assertIn('schedule_initiator', codes)
        # a record workflow starts for each record, a new process once
        node = self.todo('ok', owner={'kind': 'user', 'id': self.staff.id})
        w2, d2 = self.scheduled([node], model=self.GENERIC, schedule={'starts': 'process'})
        self.assertIn('schedule_starts', {i['code'] for i in self.service._validate(w2.sudo(), d2)})
        w3, d3 = self.scheduled([node], schedule={'every': 'week', 'weekdays': []})
        self.assertIn('schedule_weekdays', {i['code'] for i in self.service._validate(w3.sudo(), d3)})
        # Review: the twin on the same records with the same pattern
        scope = {'match': 'all', 'rules': [{'field': 'name', 'op': 'icontains', 'value': 'P5a twin'}]}
        a, da = self.scheduled([node], model=self.GENERIC, scope=scope)
        self.publish(a, da)
        b, db = self.scheduled([node], model=self.GENERIC, scope=scope)
        self.service.save_draft(b.id, b.revision, db)
        panel = self.service.review(b.id)['schedule']
        self.assertEqual(panel['words'], 'Every day at 9:00')
        self.assertIn('schedule_twin', {x['code'] for x in panel['warnings']})
        # the clock switched off (as on sudima): said plainly
        job = self.env.ref('pb_lifecycle.cron_workflow_progress').sudo()
        job.active = False
        panel = self.service.review(b.id)['schedule']
        texts = [x['text'] for x in panel['warnings']]
        self.assertIn("This site's workflow clock is switched off. Scheduled workflows here do not start "
                      "until it is switched on.", texts)
        job.active = True
        # an area that already chases on its own timetable (time off's carry-forward warning)
        if 'hr.leave' in self.env and 'hr.leave' in {r['key'] for r in self.service._models()}:
            c, dc = self.scheduled([node], model='hr.leave')
            self.service.save_draft(c.id, c.revision, dc)
            codes = {x['code'] for x in self.service.review(c.id)['schedule']['warnings']}
            self.assertIn('schedule_area_chaser', codes)
        # plain words only
        for text in texts + [panel['words']]:
            self.assertNotRegex(text, r'(?i)odoo|cron|expression|iteration|\bindex\b')

    def test_wf2p5a_t17_new_strings_are_plain(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for name in ('workflow_schedule_run.py', 'workflow_schedule.py'):
            source = open(os.path.join(root, 'pb_lifecycle/models', name), encoding='utf-8').read()
            strings = re.findall(r"_\(\s*'([^']*)'", source) + re.findall(r"return '([^']*)'", source) \
                + re.findall(r"_lt\(\s*'([^']*)'", source)     # P5b: the schedule's lazy sentences
            for s in strings:
                self.assertNotRegex(s, r'(?i)odoo|\bcron\b|schedule expression|sub-run|\bloop\b|iteration|\bindex\b|\bnode\b', s)

    # ================================================================ WF2 P5c
    # Small items first (D30, D31, D32), then "Repeat for each…".
    def test_wf2p5c_s1_around_a_date_switches_both_ways(self):
        """D30: "Around a date" switches to the shipped "At a record date"
        start (and back) with a valid definition and no filter lost. The
        screen does exactly these two edits (schedule.js)."""
        node = self.todo('look', owner={'kind': 'user', 'id': self.staff.id})
        scope = {'match': 'all', 'rules': [{'field': 'name', 'op': 'icontains', 'value': 'P5c around'}]}
        w, d = self.scheduled([node], model=self.GENERIC, scope=scope)
        self.service.save_draft(w.id, w.revision, d)
        date_field = next(f['key'] for f in self.service._source_fields(self.GENERIC) if f['type'] in ('date', 'datetime'))
        tr = d['trigger']
        tr.update(kind='date', date_field=date_field, delay=3, mode='before', unit='day')   # "Around a date"
        result = self.service.save_draft(w.id, w.revision, d)
        self.assertFalse([i for i in result['issues'] if i['id'] == 'trigger' and i.get('severity') != 'warning'], result['issues'])
        w.invalidate_recordset()
        self.assertEqual(w.draft['scope'], scope)
        self.assertEqual(w.draft['trigger']['schedule']['every'], 'day', 'the schedule is kept to go back to')
        tr.update(kind='schedule')
        tr['schedule'].update(every='week', weekdays=[0], starts='each_record')            # "Every week"
        result = self.service.save_draft(w.id, w.revision, d)
        self.assertFalse([i for i in result['issues'] if i['id'] == 'trigger' and i.get('severity') != 'warning'], result['issues'])
        w.invalidate_recordset()
        self.assertEqual(w.draft['scope'], scope)
        self.assertEqual(w.draft['trigger']['kind'], 'schedule')

    def test_wf2p5c_s2_area_timetables_declared_and_warned(self):
        """D31: contract end, trial period end and document expiry are
        declared from the areas' own settings, listed under "Already
        happens", and a workflow started around the same date that tells
        the same kind of person is warned. No job changes."""
        crons = self.env['ir.cron'].sudo().search([('active', '=', True)]).ids
        Param = self.env['ir.config_parameter'].sudo()
        expected = {'hr.contract': ('pb_contract_lifecycle.nag_days', '9', 'date_end', '9 days'),
                    'hr.employee': ('pb_probation.remind_days_far', '16', 'trial_date_end', '16 days'),
                    'pb.employee.document': ('pb_employee_vault.expiry_warn_days', '31', 'expiry_date', '31 days')}
        checked = 0
        for model, (param, value, field, words) in expected.items():
            if model not in self.env or not hasattr(self.env[model], '_workflow_effects') or \
                    model not in {r['key'] for r in self.service._models()}:
                continue
            Param.set_param(param, value)
            rows = [r for r in self.service._existing(model, self.company) if r['kind'] == 'reminder']
            self.assertTrue(any(words in r['text'] for r in rows), (model, rows))
            tables = self.service._timetables(model, self.company)
            self.assertTrue(any(t['timing']['field'] == field for t in tables), model)
            # a workflow around that date, giving a named person a task
            w, d = self.workflow([self.todo('chase', owner={'kind': 'user', 'id': self.staff.id})], model=model)
            d['trigger'].update(kind='date', date_field=field, delay=5, mode='before', unit='day')
            issues = self.service._validate(w.sudo(), d)
            hit = [i for i in issues if i['code'] == 'repeats_existing' and i['id'] == 'chase']
            self.assertTrue(hit, (model, issues))
            self.assertIn('already reminds people on its own timetable', hit[0]['text'])
            self.assertNotRegex(hit[0]['text'], r'(?i)odoo|_id\b|date_end|expiry_date')
            # another date: no warning; kept on purpose: acknowledged
            other = next((f['key'] for f in self.service._source_fields(model)
                          if f['type'] in ('date', 'datetime') and f['key'] != field), None)
            if other:
                d['trigger']['date_field'] = other
                self.assertFalse([i for i in self.service._validate(w.sudo(), d)
                                  if i['code'] == 'repeats_existing' and i['id'] == 'chase'])
                d['trigger']['date_field'] = field
            d['nodes'][-1]['ack_repeat'] = True
            kept = [i for i in self.service._validate(w.sudo(), d) if i['code'] == 'repeats_existing' and i['id'] == 'chase']
            self.assertTrue(kept[0]['acknowledged'])
            # a start long before the window: no warning
            d['nodes'][-1].pop('ack_repeat')
            d['trigger']['delay'] = 300
            self.assertFalse([i for i in self.service._validate(w.sudo(), d)
                              if i['code'] == 'repeats_existing' and i['id'] == 'chase'])
            checked += 1
        self.assertGreaterEqual(checked, 2, 'at least two of the three areas are installed here')
        self.assertEqual(self.env['ir.cron'].sudo().search([('active', '=', True)]).ids, crons)

    def see_everyone_fixture(self):
        self.approval_route(process=self.generic_process())
        record = self.generic('P5c everyone')
        sent = self.env['biz.approval.engine'].with_user(self.admin).submit(record.with_user(self.admin))
        viewer = self.staffer('WF2 P5c viewer')
        return self.env['biz.approval.request'].browse(sent['id']), viewer

    def test_wf2p5c_s3_see_everyones_approvals_reads_and_nothing_more(self):
        """D32: the narrow right sees Everyone and opens a request to read
        it; it cannot decide, repair, cancel or set anything up, and other
        companies stay hidden. Nobody has it after the upgrade."""
        group = self.env.ref('pb_lifecycle.group_approvals_see_everyone')
        ability = self.env.ref('pb_lifecycle.ability_approvals_see_everyone')
        self.assertEqual(ability.group_ids, group)
        self.assertNotRegex(ability.name + ability.description, r'(?i)odoo')
        request, viewer = self.see_everyone_fixture()
        Inbox = self.env['pb.approval.inbox'].with_user(viewer)
        Request = self.env['biz.approval.request'].with_user(viewer)
        self.assertFalse(Inbox._can_org())
        self.assertFalse(Request.search([('id', '=', request.id)]))
        with self.assertRaises(AccessError):
            Inbox.get_request(request.id, 'org')
        viewer.write({'group_ids': [(4, group.id)]})
        self.env.invalidate_all()
        Inbox = self.env['pb.approval.inbox'].with_user(viewer)
        Request = self.env['biz.approval.request'].with_user(viewer)
        self.assertTrue(Inbox._can_org())
        self.assertEqual(Request.search([('id', '=', request.id)]), request.with_user(viewer))
        drawer = Inbox.get_request(request.id, 'org')
        self.assertEqual(drawer['id'], request.id)
        self.assertTrue(Inbox.get_request(request.id, 'me'))
        Engine = self.env['biz.approval.engine'].with_user(viewer)
        def refused(call):
            try:
                with self.env.cr.savepoint():
                    call()
            except (AccessError, UserError):
                return True
            return False
        for call in (lambda: Engine.decide(request.id, 'signoff', 'approve'),
                     lambda: Inbox.decide(request.id, 'signoff', 'approve'),
                     lambda: Inbox.cancel(request.id, 'not mine'),
                     lambda: Inbox.repair(request.id),
                     lambda: Request.browse(request.id).write({'title': 'changed'}),
                     lambda: self.env['biz.approval.workflow'].with_user(viewer).create({
                         'name': 'P5c no', 'company_id': self.company.id, 'process_id': self.generic_process().id,
                         'owner_user_id': viewer.id})):
            self.assertTrue(refused(call))
        self.assertEqual(request.state, 'pending')
        self.assertFalse(viewer.has_group('biz_approval_workflow.group_approval_config'))
        self.assertFalse(viewer.has_group('hr.group_hr_manager'))
        # another company's request stays hidden
        other = self.env['res.company'].create({'name': 'WF2 P5c other company'})
        theirs = request.sudo().copy({'company_id': other.id, 'title': 'P5c other company'})
        self.assertFalse(Request.search([('id', '=', theirs.id)]))
        self.assertTrue(refused(lambda: Inbox.get_request(theirs.id, 'org')))
        # D26: with this right a pay manager counts as "can see Everyone"
        try:
            from odoo.addons.pb_pay.models.pay_single_notice import pay_group_rest
        except ImportError:
            return
        Engine = type(self.env['biz.approval.engine'])
        with patch.object(Engine, 'tells_approver', lambda self, record, *a, **k: True), \
                patch.object(Engine, '_latest_request', lambda self, record, *a, **k: request):
            plain = self.staffer('WF2 P5c pay person')
            rest = pay_group_rest(self.generic('P5c pay'), viewer | plain)
            self.assertEqual(rest, plain, 'the one who can see Everyone is not given the to-do')

    def test_wf2p5c_s4_nobody_has_the_new_right(self):
        group = self.env.ref('pb_lifecycle.group_approvals_see_everyone')
        self.assertFalse(group.sudo().user_ids.filtered(lambda u: not u.login.startswith('wf2-')))

    # ------------------------------------------------------- the repeat kit
    PICK = {'id': 'pick', 'type': 'input', 'title': 'What to check', 'stage': 0, 'owner': {'kind': 'initiator'},
            'due': 2, 'form': {'fields': [{'id': 'items', 'type': 'multiselect', 'label': 'Things',
                                           'options': ['A', 'B', 'C', 'D', 'E', 'F', 'G'], 'required': True}]}}

    def rep(self, ident='rep', steps=(), source=None, **kw):
        return dict({'id': ident, 'type': 'repeat', 'title': 'For each thing', 'stage': 0, 'steps': list(steps),
                     'source': source or {'kind': 'answers', 'step': 'pick', 'field': 'items'},
                     'mode': 'together', 'join': 'all', 'max_lines': 50}, **kw)

    def repeat_flow(self, inner, rep_kw=None, before=None, after=(), model='', publish=True):
        """[before…] → repeat(inner) → [after…], inner steps only in the repeat."""
        before = [copy.deepcopy(self.PICK)] if before is None else before
        w, d = self.workflow(before, model=model)
        rep = self.rep(steps=[n['id'] for n in inner if not n.get('_nested')], **(rep_kw or {}))
        d['nodes'] += [rep] + [{k: v for k, v in n.items() if k != '_nested'} for n in inner] + list(after)
        d['order'] += ['rep'] + [n['id'] for n in after]
        if publish:
            self.publish(w, d)
        return w, d

    def check(self, **kw):
        return self.todo('check', owner={'kind': 'user', 'id': self.staff.id}, title='Check it', **kw)

    def lines_of(self, run, key='rep'):
        return self.env['pb.workflow.run'].sudo().search([('parent_id', '=', run.id), ('parent_step_key', '=', key)],
                                                         order='line_round, line_number')

    def as_staff(self):
        return self.env['pb.workflow.studio'].with_user(self.staff).with_company(self.company)

    def answer_line(self, line, key='check', values=None):
        step = self.step(line, key)
        self.assertEqual(step.state, 'waiting', step.error)
        return self.as_staff().answer(step.id, values or {})

    def started(self, w, items):
        run = self.start(w)
        self.service.answer(self.step(run, 'pick').id, {'items': list(items)})
        return run

    def test_wf2p5c_t1_repeat_basics(self):
        after = self.todo('after', owner={'kind': 'user', 'id': self.admin.id}, title='After')
        w, d = self.repeat_flow([self.check(buttons=self.BUTTONS)], after=[after])
        run = self.started(w, ['A', 'B', 'C', 'D'])
        lines = self.lines_of(run)
        self.assertEqual(lines.mapped('line_label'), ['A', 'B', 'C', 'D'])
        self.assertEqual(lines.mapped('line_number'), [1, 2, 3, 4])
        self.assertTrue(all(l.state == 'waiting' and l.line_count == 4 for l in lines))
        self.assertEqual(self.step(run, 'rep').state, 'active')
        self.assertEqual(run.state, 'waiting')
        self.assertFalse(self.step(run, 'check'), 'the repeat\'s steps live on its lines only')
        self.assertEqual(self.step(run, 'after').state, 'pending')
        for line, choice in zip(lines, ['fine', 'fine', 'missing', 'fine']):
            self.answer_line(line, values={'outcome': choice})
        self.assertTrue(all(l.state == 'done' for l in lines))
        self.assertEqual(self.step(run, 'rep').state, 'done')
        self.assertEqual(self.step(run, 'after').state, 'waiting')
        values = run._values()
        self.assertEqual((values['step.rep.count'], values['step.rep.done']), (4, 4))
        self.assertEqual((values['step.rep.check__fine'], values['step.rep.check__missing']), (3, 1))
        self.assertNotIn('step.rep._lines', values)
        # "any": the first line done carries on, the others stop
        w2, _d2 = self.repeat_flow([self.check()], rep_kw={'join': 'any'}, after=[dict(after)])
        run2 = self.started(w2, ['A', 'B', 'C'])
        lines2 = self.lines_of(run2)
        self.answer_line(lines2[1])
        self.assertEqual(lines2.mapped('state'), ['cancelled', 'done', 'cancelled'])
        self.assertEqual(self.step(run2, 'after').state, 'waiting')
        self.assertFalse(lines2[0].step_ids.filtered('activity_id'), 'the stopped lines leave no to-do behind')
        # one by one: in order, the next when the previous is done
        w3, _d3 = self.repeat_flow([self.check()], rep_kw={'mode': 'one_by_one'})
        run3 = self.started(w3, ['A', 'B', 'C'])
        self.assertEqual(self.lines_of(run3).mapped('line_label'), ['A'])
        self.answer_line(self.lines_of(run3)[0])
        self.assertEqual(self.lines_of(run3).mapped('line_label'), ['A', 'B'])
        self.answer_line(self.lines_of(run3)[1])
        self.answer_line(self.lines_of(run3)[2])
        self.assertEqual(run3.state, 'done')
        self.assertEqual(run3._values()['step.rep.done'], 3)

    def receipts(self, claim, count):
        product = self.env['product.product'].create({'name': 'P5c Taxi', 'can_be_expensed': True, 'standard_price': 0.0})
        for i in range(count):
            self.env['hr.expense'].create({
                'name': 'P5c receipt %s' % (i + 1), 'employee_id': claim.employee_id.id, 'product_id': product.id,
                'total_amount_currency': 10.0 * (i + 1), 'company_id': self.company.id, 'pb_claim_id': claim.id,
                'date': fields.Date.today() - timedelta(days=count - i)})

    def claim_repeat(self, inner, rep_kw=None, receipts=4, after=()):
        self.need(self.CLAIM)
        self.expense_access(self.admin, self.staff)
        kw = dict({'source': {'kind': 'area', 'key': 'receipts', 'fields': ['description', 'date', 'category', 'amount']},
                   'title': 'For each receipt'}, **(rep_kw or {}))
        w, d = self.repeat_flow(inner, rep_kw=kw, before=[], after=after, model=self.CLAIM)
        claim = self.claim('draft')
        self.receipts(claim, receipts)
        return w, d, claim

    def test_wf2p5c_t1b_receipts_are_snapshotted_at_start(self):
        w, _d, claim = self.claim_repeat([self.check()])
        run = self.start(w, claim)
        lines = self.lines_of(run)
        self.assertEqual(lines.mapped('line_label')[0][:12], 'P5c receipt ')
        self.assertEqual(lines[0].line_values['amount'], 10.0)
        self.receipts(claim, 1)        # a fifth receipt, added later
        self.service._cron_workflows()
        self.assertEqual(len(self.lines_of(run)), 4)
        self.assertEqual(self.lines_of(run)[0].facts['line.amount'], 10.0)

    def test_wf2p5c_t2_repeat_limits_and_refusals(self):
        w, _d = self.repeat_flow([self.check()], rep_kw={'max_lines': 2})
        run = self.started(w, ['A', 'B', 'C'])
        step = self.step(run, 'rep')
        self.assertEqual(step.state, 'failed')
        self.assertIn('There are 3 answers, more than the 2 this repeats for', step.error)
        self.assertFalse(self.lines_of(run))
        self.assertEqual(run.state, 'failed')
        # each refused kind gives its own code
        role_w, _ = self.workflow()
        stage_target = {'kind': 'yours', 'id': 1}
        refused = {
            'repeat_matrix': {'id': 'x', 'type': 'matrix', 'title': 'Approve', 'stage': 0},
            'repeat_stage_move': {'id': 'x', 'type': 'stage_move', 'title': 'Move', 'stage': 0, 'target': stage_target},
            'repeat_start': {'id': 'x', 'type': 'start', 'title': 'Start', 'stage': 0, 'workflow_id': role_w.id},
            'repeat_update': {'id': 'x', 'type': 'update', 'title': 'Set', 'stage': 0, 'field': 'note', 'value': 'x'},
        }
        for code, node in refused.items():
            _w, d = self.repeat_flow([self.check(), node], publish=False)
            codes = {i['code'] for i in D.validate(d, {'amount', 'urgent'})}
            self.assertIn(code, codes, (code, codes))
        # nested repeat, parallel inside
        _w, d = self.repeat_flow([self.check()], publish=False)
        inner = self.rep('rep2', steps=['c2'])
        d['nodes'] += [inner, dict(self.check(), id='c2')]
        d['nodes'][[n['id'] for n in d['nodes']].index('rep')]['steps'].append('rep2')
        self.assertIn('repeat_nested', {i['code'] for i in D.validate(d, {'amount', 'urgent'})})
        _w, d = self.repeat_flow([self.check()], publish=False)
        par = {'id': 'par', 'type': 'parallel', 'title': 'Both', 'stage': 0, 'join': 'all', 'branches': [
            self.path('pa', None, ['c3']), self.path('pb', None, ['c4'])]}
        d['nodes'] += [par, dict(self.check(), id='c3'), dict(self.check(), id='c4')]
        d['nodes'][[n['id'] for n in d['nodes']].index('rep')]['steps'].append('par')
        self.assertIn('repeat_parallel', {i['code'] for i in D.validate(d, {'amount', 'urgent'})})
        # off the main path, a cap over 200, no source, empty
        _w, d = self.repeat_flow([self.check()], rep_kw={'max_lines': 201, 'source': {'kind': 'everything'}}, publish=False)
        codes = {i['code'] for i in D.validate(d, {'amount', 'urgent'})}
        self.assertTrue({'repeat_cap', 'repeat_source'} <= codes, codes)
        _w, d = self.repeat_flow([], publish=False)
        self.assertIn('empty_repeat', {i['code'] for i in D.validate(d, {'amount', 'urgent'})})
        # send back from inside to outside the repeat: refused
        back = {'id': 'back', 'type': 'send_back', 'title': 'Back', 'stage': 0, 'target': 'pick',
                'when': self.rule('line.value', 'A')}
        _w, d = self.repeat_flow([self.check(), back], publish=False)
        self.assertIn('repeat_send_back_outside', {i['code'] for i in D.validate(d, {'amount', 'urgent'})})
        # a person on the line only inside a repeat that names one
        mine = self.todo('mine', owner={'kind': 'line', 'field': 'person'})
        w5, d5 = self.repeat_flow([mine], publish=False)
        self.assertIn('line_owner', {i['code'] for i in self.service._validate(w5.sudo(), d5)})

    def test_wf2p5c_t3_repeat_people_inbox_and_pages(self):
        role = self.env['biz.approval.role'].create({'name': 'P5c checkers', 'key': 'p5c_checkers_%s' % uuid.uuid4().hex[:6],
                                                     'is_pool': True})
        other = self.staffer('WF2 P5c checker two')
        self.env['biz.approval.responsibility'].create({
            'company_id': self.company.id, 'role_id': role.id, 'scope_key': '', 'scope_label': self.company.name,
            'pool_user_ids': [(6, 0, (self.staff | other).ids)]})
        mine = self.todo('check', owner={'kind': 'line', 'field': 'person'}, title='Check in')
        w, d = self.repeat_flow([mine], before=[], rep_kw={'source': {'kind': 'team', 'id': role.id},
                                                           'title': 'For each checker'})
        self.assertFalse([i for i in self.service._validate(w.sudo(), d) if i.get('severity') != 'warning'])
        run = self.start(w)
        lines = self.lines_of(run)
        self.assertEqual(sorted(lines.mapped('line_label')), sorted([self.staff.name, other.name]))
        by_person = {l.line_values['person']: l for l in lines}
        step = self.step(by_person[self.staff.id], 'check')
        self.assertEqual(step.assignee_id, self.staff, 'the line names the person who does it')
        card = next(c for c in self.as_staff()._inbox_tasks('me') if c['id'] == step.id)
        self.assertEqual(card['title'], 'Check in · %s' % self.staff.name)
        self.assertRegex(card['line']['words'], r'^person [12] of 2$')
        self.assertTrue(card['group']['key'].startswith('rep-%s-' % run.id))
        # another person can neither see nor answer this line's task
        self.assertNotIn(step.id, [c['id'] for c in self.env['pb.workflow.studio'].with_user(other)._inbox_tasks('me')])
        with self.assertRaises(AccessError):
            self.env['pb.workflow.studio'].with_user(other).with_company(self.company).answer(step.id, {})
        self.assertEqual(self.as_staff().task_detail(step.id)['line']['label'], self.staff.name)
        page = self.env['pb.workflow.studio'].sudo()._page_data(step.sudo(), ())
        self.assertIn('person', page['record'])
        self.assertIn(self.staff.name, page['name'])
        # a team inside a repeat still works (first one wins)
        team_task = self.todo('check', owner={'kind': 'team', 'id': role.id}, title='Check')
        w2, _d2 = self.repeat_flow([team_task])
        run2 = self.started(w2, ['A', 'B'])
        t = self.step(self.lines_of(run2)[0], 'check')
        self.assertEqual(set(t.team_user_ids.ids), {self.staff.id, other.id})
        # six line tasks for one person: one card, "Do all in turn"
        w3, _d3 = self.repeat_flow([self.check()])
        run3 = self.started(w3, ['A', 'B', 'C', 'D', 'E', 'F'])
        items = self.env['pb.approval.inbox'].with_user(self.staff)._extra_items('me')
        grouped = [c for c in items if c.get('kind') == 'task_group']
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]['group_count'], 6)
        self.assertEqual(len(grouped[0]['group']['ids']), 6)
        self.assertEqual(grouped[0]['title'], 'Check it · 6 to do')
        self.assertEqual(self.lines_of(run3)[0].step_ids.filtered(lambda s: s.key == 'check').id, grouped[0]['id'])
        counts = self.env['pb.approval.inbox'].with_user(self.staff)._extra_counts('me')
        self.assertGreaterEqual(counts['mine'], 6 + 1, 'counts still count every task')

    def test_wf2p5c_t4_failed_line_and_stop_inside(self):
        absent = self.staffer('WF2 P5c away')
        guarded = self.todo('check', owner={'kind': 'user', 'id': absent.id}, title='Check it',
                            when=self.rule('line.value', 'B'))
        plain = self.todo('also', owner={'kind': 'user', 'id': self.staff.id}, title='Also')
        w, _d = self.repeat_flow([guarded, plain])
        w2, _d2 = self.repeat_flow([dict(guarded), dict(plain)])
        absent.write({'active': False})
        run = self.started(w, ['A', 'B', 'C'])
        lines = self.lines_of(run)
        self.assertEqual(lines.mapped('state'), ['waiting', 'failed', 'waiting'])
        rep = self.step(run, 'rep')
        self.assertEqual((rep.state, rep.error), ('failed', '1 of 3 lines needs attention.'))
        self.assertEqual(run.state, 'failed')
        progress = self.service.progress(run.id)
        row = next(r for r in progress['steps'] if r['key'] == 'rep')
        self.assertEqual([x['state'] for x in row['lines']], ['waiting', 'failed', 'waiting'])
        self.assertTrue(row['lines'][1]['failed_step_id'])
        # the healthy lines carry on meanwhile
        self.answer_line(lines[0], 'also')
        # Retry that line only
        absent.write({'active': True})
        self.service.run_action(lines[1].id, 'retry', row['lines'][1]['failed_step_id'])
        self.assertEqual(lines[1].state, 'waiting')
        self.assertEqual(self.step(run, 'rep').state, 'active')
        self.assertEqual(run.state, 'waiting')
        self.assertEqual(lines[0].state, 'done', 'the other lines were not touched')
        # Retry on the repeat itself retries every line that needs it
        absent.write({'active': False})
        run2 = self.started(w2, ['B', 'C'])
        absent.write({'active': True})
        self.service.run_action(run2.id, 'retry', self.step(run2, 'rep').id)
        self.assertEqual(self.lines_of(run2).mapped('state'), ['waiting', 'waiting'])
        # "Stop here" inside ends that line only
        stop = {'id': 'stop', 'type': 'end', 'title': 'Not needed', 'stage': 0, 'reason': 'Skip B',
                'when': self.rule('line.value', 'B')}
        w3, _d3 = self.repeat_flow([stop, self.check()], after=[self.todo('after', owner={'kind': 'user', 'id': self.admin.id})])
        run3 = self.started(w3, ['A', 'B'])
        lines3 = self.lines_of(run3)
        self.assertEqual(lines3.mapped('state'), ['waiting', 'done'])
        self.assertEqual(run3.state, 'waiting')
        self.answer_line(lines3[0])
        self.assertEqual(self.step(run3, 'after').state, 'waiting')
        self.assertEqual(run3._values()['step.rep.done'], 2)

    def test_wf2p5c_t5_line_values_in_rules_notices_and_after(self):
        tell = {'id': 'tell', 'type': 'notify', 'title': 'Tell', 'stage': 0, 'owner': {'kind': 'user', 'id': self.staff.id},
                'text': 'Please look at {{line.value}} ({{line.number}})'}
        branch = self.choose('which', [self.path('p_b', self.rule('line.value', 'B'), ['tell']),
                                       self.path('p_else', None, ['check'])])
        check = self.check(buttons=self.BUTTONS)
        after = self.choose('after', [
            self.path('p_many', {'match': 'all', 'rules': [{'field': 'step.rep.check__missing', 'op': 'gte', 'value': 1}]},
                      ['fix']),
            self.path('p_ok', None, ['done'])])
        fix = self.todo('fix', owner={'kind': 'user', 'id': self.admin.id}, title='Fix')
        done = self.todo('done', owner={'kind': 'user', 'id': self.admin.id}, title='All good')
        w, d = self.repeat_flow([dict(branch), dict(tell, _nested=True), dict(check, _nested=True)],
                                after=[after, fix, done], publish=False)
        d['order'] = [k for k in d['order'] if k not in ('fix', 'done')]
        self.assertFalse([i for i in D.validate(d, {'amount', 'urgent'})], D.validate(d, {'amount', 'urgent'}))
        self.publish(w, d)
        run = self.started(w, ['A', 'B'])
        a, b = self.lines_of(run)
        self.assertEqual(self.step(b, 'tell').state, 'done')
        note = self.env['mail.message'].sudo().search([('body', 'ilike', 'Please look at B (2)')], limit=1)
        self.assertTrue(note, 'the notice was filled with the line')
        self.answer_line(a, values={'outcome': 'missing'})
        self.assertEqual(self.step(run, 'fix').state, 'waiting')
        self.assertEqual(self.step(run, 'done').state, 'skipped')
        # Try it out walks one sample line and says the rest do the same
        rows = self.service.preview(w.id, {'step.pick.items': ['A']})['steps']
        self.assertTrue(any(r.get('reason', '').startswith('…and the same') for r in rows), rows)
        self.assertTrue(any(r['id'] == 'rep' and r.get('reason', '').startswith('For each answer to “Things”') for r in rows), rows)

    def test_wf2p5c_t6_generic_sources(self):
        form = {'id': 'pick', 'type': 'input', 'title': 'Costs', 'stage': 0, 'owner': {'kind': 'initiator'}, 'due': 2,
                'form': {'fields': [{'id': 'rows', 'type': 'rows', 'label': 'Cost lines', 'required': True}]}}
        check = self.check(when={'match': 'all', 'rules': [{'field': 'line.amount', 'op': 'gt', 'value': 50}]})
        w, d = self.repeat_flow([check], before=[form], rep_kw={'source': {'kind': 'answers', 'step': 'pick', 'field': 'rows'}})
        run = self.start(w)
        self.service.answer(self.step(run, 'pick').id, {'rows': [{'description': 'Hotel', 'amount': 120},
                                                                 {'description': 'Bus', 'amount': 5}]})
        lines = self.lines_of(run)
        self.assertEqual(lines.mapped('line_label'), ['Hotel', 'Bus'])
        self.assertEqual(lines.mapped('state'), ['waiting', 'done'], 'line.amount steers each line')
        words = self.service._repeat_words('', d['nodes'][[n['id'] for n in d['nodes']].index('rep')], d)
        self.assertEqual(words['each'], 'For each line of “Cost lines”')
        # no answers at all: nothing to repeat, carry on
        w2, _d2 = self.repeat_flow([self.check()], before=[dict(self.PICK, form={'fields': [dict(
            self.PICK['form']['fields'][0], required=False)]})], after=[self.todo('after', owner={'kind': 'user', 'id': self.admin.id})])
        run2 = self.start(w2)
        self.service.answer(self.step(run2, 'pick').id, {})
        self.assertEqual(self.step(run2, 'rep').state, 'done')
        self.assertEqual(self.step(run2, 'after').state, 'waiting')

    def test_wf2p5c_t7_lines_are_not_runs_anywhere_people_count_runs(self):
        w, _d, claim = self.claim_repeat([self.check()], receipts=3)
        run = self.start(w, claim)
        lines = self.lines_of(run)
        self.assertEqual(len(lines), 3)
        self.assertEqual([r['id'] for r in self.service.runs(w.id)], run.ids)
        shown = self.service.runs(w.id, show_lines=True)
        self.assertEqual(sorted(r['id'] for r in shown), sorted((run | lines).ids))
        self.assertTrue(all(r.get('line') for r in shown if r['id'] in lines.ids))
        self.assertEqual([r['id'] for r in self.service.record_runs(self.CLAIM, claim.id)['runs']], run.ids)
        strip = self.strip(self.admin, self.CLAIM, claim.id)
        self.assertEqual(len(strip['workflows']), 1)
        self.assertEqual(strip['workflows'][0]['sentence'], '0 of 3 receipts done')
        mine = self.strip(self.staff, self.CLAIM, claim.id)['workflows'][0]
        self.assertTrue(mine['task_id'])
        self.assertTrue(mine['sentence'].startswith('0 of 3 receipts done · next for you: Check it · P5c receipt 1'))
        self.answer_line(lines[0])
        self.assertEqual(self.strip(self.admin, self.CLAIM, claim.id)['workflows'][0]['sentence'], '1 of 3 receipts done')
        self.assertFalse(self.env['pb.workflow.event'].sudo().search([('run_id', 'in', lines.ids)]),
                         'a line has no start of its own, so it never counts as "already running"')
        self.answer_line(lines[1])
        self.answer_line(lines[2])
        report = self.service.time_report(w.id, 'all')
        self.assertEqual(report['runs'], 1, 'the lines are not counted as runs')
        self.assertFalse([s for s in report['steps'] if s['key'] == 'check'], 'line steps are not ranked one by one')

    def test_wf2p5c_t8_isolation_guards_and_plain_words(self):
        w, _d = self.repeat_flow([self.check()])
        run = self.started(w, ['A', 'B'])
        for line in self.lines_of(run):
            self.assertEqual((line.company_id, line.workflow_id, line.version_id, line.initiator_id),
                             (run.company_id, run.workflow_id, run.version_id, run.initiator_id))
        other_company = self.env['res.company'].create({'name': 'WF2 P5c elsewhere'})
        stranger = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'P5c stranger', 'login': 'wf2-p5c-stranger-%s' % uuid.uuid4(), 'company_id': other_company.id,
            'company_ids': [(6, 0, other_company.ids)], 'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        self.assertFalse(self.env['pb.workflow.studio'].with_user(stranger)._inbox_tasks('me'))
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for path in ('pb_lifecycle/models/workflow_repeat.py', 'pb_me_expense/models/workflow_lines.py',
                     'pb_lifecycle/models/workflow_timetable.py'):
            text = open(os.path.join(root, path), encoding='utf-8').read()
            self.assertFalse(re.search(r'\b(source|record|records|rec|exp)\b\.(state|stage_id)\s*=[^=]', text), path)
            self.assertFalse(re.search(r'\b(source|record|records|rec|exp)\b(\.\w+\([^)]*\))*\.write\(', text), path)
            for s in re.findall(r"_\(\s*'([^']*)'", text):
                self.assertNotRegex(s, r'(?i)odoo|\bcron\b|sub-run|\bloop\b|iteration|\bindex\b|\bnode\b|\bchild\b', s)
        schedule = open(os.path.join(root, 'pb_lifecycle/static/workflow/repeat.js'), encoding='utf-8').read()
        for s in re.findall(r"'([^'<>{}$]{12,})'", schedule):
            self.assertNotRegex(s, r'(?i)odoo|sub-run|\bloop\b|iteration|\bindex\b|\bchild\b', s)

    def test_wf2p5c_t9_scheduled_repeat_counts_parents_and_starts_lines_once(self):
        self.need(self.CLAIM)
        self.expense_access(self.admin, self.staff)
        claims = [self.claim('draft') for _i in range(2)]
        for c in claims:
            self.receipts(c, 3)
        scope = {'match': 'all', 'rules': [{'field': 'id', 'op': 'in', 'value': [c.id for c in claims]}]}
        w, d = self.scheduled([], model=self.CLAIM, scope=scope)
        rep = self.rep(steps=['check'], source={'kind': 'area', 'key': 'receipts', 'fields': ['amount']}, title='For each receipt')
        d['nodes'] += [rep, self.check()]
        d['order'].append('rep')
        self.publish(w, d)
        preview = self.service.schedule_preview(w.id)
        self.assertEqual(preview['count'], 2, 'records are counted, never lines')
        w.sudo().last_tick_at = fields.Datetime.now() - timedelta(hours=25)
        Studio = self.env['pb.workflow.studio'].sudo()
        Studio._cron_workflows()
        Studio._cron_workflows()
        parents = self.env['pb.workflow.run'].sudo().search([('workflow_id', '=', w.id), ('parent_id', '=', False)])
        self.assertEqual(len(parents), 2)
        lines = self.env['pb.workflow.run'].sudo().search([('workflow_id', '=', w.id), ('parent_id', '!=', False)])
        self.assertEqual(len(lines), 6, 'three lines each, started once over two worker passes')
        self.assertEqual(len(set(lines.mapped('line_start_key'))), 6)
        self.assertEqual(len(w.sudo().schedule_log), 1)

    def test_wf2p5c_t10_send_back_inside_a_line(self):
        form = {'id': 'note', 'type': 'input', 'title': 'Describe it', 'stage': 0, 'owner': {'kind': 'user', 'id': self.staff.id},
                'due': 2, 'form': {'fields': [{'id': 'words', 'type': 'text', 'label': 'Words', 'required': True}]}}
        check = self.todo('check', owner={'kind': 'user', 'id': self.admin.id}, title='Check it', buttons=self.BUTTONS)
        back = {'id': 'back', 'type': 'send_back', 'title': 'Back', 'stage': 0, 'target': 'note'}
        route = self.choose('route', [self.path('p_missing', self.rule('step.check.outcome', 'missing'), ['back']),
                                      self.path('p_ok', None, [])])
        w, d = self.repeat_flow([form, check, route, dict(back, _nested=True)], publish=False)
        self.assertFalse(D.validate(d, {'amount', 'urgent'}))
        self.publish(w, d)
        run = self.started(w, ['A', 'B'])
        a, b = self.lines_of(run)
        for line in (a, b):
            self.as_staff().answer(self.step(line, 'note').id, {'words': 'first try'})
        self.service.answer(self.step(a, 'check').id, {'outcome': 'missing', 'comment': 'Say more'})
        self.assertEqual(self.step(a, 'note').state, 'waiting', 'line A went back to its own form')
        self.assertEqual(self.step(a, 'note').answers['_sent_back']['note'], 'Say more')
        self.assertEqual(self.step(b, 'check').state, 'waiting', 'line B was not touched')
        self.assertEqual(self.step(b, 'note').state, 'done')
        self.assertEqual(self.step(run, 'rep').state, 'active')
        self.as_staff().answer(self.step(a, 'note').id, {'words': 'better'})
        self.service.answer(self.step(a, 'check').id, {'outcome': 'fine'})
        self.service.answer(self.step(b, 'check').id, {'outcome': 'fine'})
        self.assertEqual(run.state, 'done')

    def test_wf2p5c_t11_no_repeat_is_byte_identical(self):
        """Three definitions without a repeat: validation and Try it out
        output byte-identical to the code before this phase (golden file
        written from that code)."""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'wf2p5c_no_repeat_baseline.json')
        cases = json.load(open(path, encoding='utf-8'))
        self.assertEqual(len(cases), 3)
        for case in cases:
            d = case['definition']
            now = {'validate': D.validate(d, {'amount', 'urgent'}, {}),
                   'preview': [D.route_preview(d, v) for v in ({'amount': 50, 'urgent': False},
                                                               {'amount': 500, 'urgent': True, 'step.check.outcome': 'missing'})]}
            self.assertEqual(json.dumps(now, sort_keys=True), json.dumps({k: case[k] for k in ('validate', 'preview')}, sort_keys=True))

    def test_wf2p5c_t12_two_hundred_lines_in_one_pass(self):
        import time
        w, _d, claim = self.claim_repeat([self.check()], rep_kw={'max_lines': 200}, receipts=200)
        began = time.time()
        run = self.start(w, claim)
        started = time.time() - began
        self.assertEqual(len(self.lines_of(run)), 200)
        began = time.time()
        self.env['pb.workflow.studio'].sudo()._cron_workflows()
        worker = time.time() - began
        began = time.time()
        items = self.env['pb.approval.inbox'].with_user(self.staff)._extra_items('me')
        inbox = time.time() - began
        self.assertEqual(len([c for c in items if c.get('kind') == 'task_group']), 1)
        print('WF2P5C_PERF=' + json.dumps({'start_200_lines_s': round(started, 2), 'worker_pass_s': round(worker, 2),
                                           'inbox_200_tasks_s': round(inbox, 2), 'inbox_cards': len(items)}))
        self.assertLess(started, 120)
        self.assertLess(worker, 60)

    # ================================================================ WF2 P5b
    # Vietnamese and Indonesian. English must stay byte-identical: p1 renders
    # every people surface in English and compares it with a golden file
    # written by the code before this phase (WF2P5B_WRITE_GOLDEN=1 writes it).
    # p2 runs only where vi_VN and id_ID are installed (a live database after
    # the upgrade; a plain test database has no second language).
    P5B_SCHEDULES = [
        None, {}, {'every': 'day', 'at': '09:00'}, {'every': 'day', 'at': '7:05', 'working_days': True},
        {'every': 'week', 'at': '09:00', 'weekdays': [0]}, {'every': 'week', 'at': '08:30', 'weekdays': [0, 1, 2, 3, 4]},
        {'every': 'week', 'at': '18:00', 'weekdays': [0, 2, 4], 'working_days': True},
        {'every': 'week', 'at': '06:00', 'weekdays': [0, 1, 2, 3, 4, 5, 6]}, {'every': 'week', 'at': '10:00', 'weekdays': []},
        {'every': 'week', 'at': '10:00', 'weekdays': [5, 6]},
        {'every': 'month', 'at': '17:30', 'day': 'last'}, {'every': 'month', 'at': '12:00', 'day': 1},
        {'every': 'month', 'at': '12:00', 'day': 2}, {'every': 'month', 'at': '12:00', 'day': 3},
        {'every': 'month', 'at': '12:00', 'day': 11}, {'every': 'month', 'at': '12:00', 'day': 22, 'working_days': True},
        {'every': 'year', 'at': '09:00', 'day': 1, 'month': 7}, {'every': 'year', 'at': '09:00', 'day': 'last', 'month': 2},
        {'every': 'year', 'at': '09:00', 'day': 5, 'month': 13}, {'every': 'once', 'at': '08:00', 'date': '2026-11-20'},
        {'every': 'once', 'at': '08:00', 'date': '2027-05-02'}, {'every': 'once', 'at': '08:00', 'date': 'soon'},
        {'every': 'fortnight', 'at': '09:00'},
    ]
    P5B_BAD_SCHEDULES = [
        None, {'every': 'fortnight'}, {'every': 'week', 'at': '9', 'weekdays': [], 'starts': 'process'},
        {'every': 'month', 'at': '09:00', 'day': 40, 'starts': 'each_record'},
        {'every': 'year', 'at': '09:00', 'day': 1, 'month': 0, 'starts': 'process'},
        {'every': 'once', 'at': '09:00', 'date': '', 'starts': 'process', 'working_days': 'yes'},
        {'every': 'day', 'at': '09:00', 'starts': 'process'}, {'every': 'day', 'at': '09:00', 'starts': 'each_record'},
    ]
    P5B_MODELS = ('pb.expense.claim', 'hr.leave', 'hr.applicant', 'hr.payslip.run', 'biz.approval.generic.request',
                  'hr.contract', 'hr.employee', 'pb.employee.document')

    def _p5b_surfaces(self, lang):
        """Every people surface this programme added, in `lang`, as plain
        data. Works on the code before P5b too (English only there)."""
        import inspect
        from odoo.addons.pb_lifecycle.models import workflow_schedule as WS
        from odoo.addons.pb_lifecycle.models.workflow_people import HOME_UNSUPPORTED
        takes_lang = 'lang' in inspect.signature(WS.words).parameters
        words = (lambda s: WS.words(s, lang)) if takes_lang else WS.words
        issues = (lambda s, r: WS.issues(s, r, lang)) if takes_lang else WS.issues
        out = {'schedule_words': [words(s) for s in self.P5B_SCHEDULES],
               'schedule_issues': [[issues(s, r) for r in (None, True, False)] for s in self.P5B_BAD_SCHEDULES]}
        service = self.service.with_context(lang=lang)
        out['contracts'] = {m: service._contract(m) for m in self.P5B_MODELS if m in self.env}
        out['existing'] = {m: service._existing(m, self.company) for m in self.P5B_MODELS if m in self.env}
        out['durations'] = [service._duration_words(h, 8) for h in (0.5, 3, 8, 13, 40, 400)]
        # a claim with three receipts and a check for each
        w, d, claim = self.claim_repeat([self.check(buttons=self.BUTTONS)], receipts=3)
        run = self.start(w, claim)
        line = self.lines_of(run)[0]
        step = self.step(line, 'check')
        out['repeat_words'] = service._repeat_words(self.CLAIM, next(n for n in d['nodes'] if n['id'] == 'rep'), d)
        out['inbox'] = self.env['pb.approval.inbox'].with_user(self.staff).with_context(lang=lang)._extra_items('me')
        staff = self.env['pb.workflow.studio'].with_user(self.staff).with_company(self.company).with_context(lang=lang)
        out['strip'] = staff.record_runs(self.CLAIM, claim.id)['strip']
        page = staff._page_data(step, HOME_UNSUPPORTED)
        out['page'] = page
        out['task_body'] = str(self.env['ir.qweb'].with_context(lang=lang)._render('pb_lifecycle.workflow_task_body', {
            't': page, 'mode': 'home', 'state': 'ok', 'errors': {}, 'values': {}, 'post_url': '/x'}))
        system = self.env['pb.workflow.studio'].sudo().with_context(lang=lang)
        out['payloads'] = [system._task_payload(line, step, why) for why in ('new_team', 'reminder', 'passed_up', 'other')]
        out['progress'] = service.progress(run.id)
        template = self.env.ref('pb_lifecycle.mail_template_workflow_link').with_context(
            lang=lang, link_url='https://example.com/workflow/t/abc', link_company='Acme', link_name='Mai',
            link_due='2026-11-20', link_until='2026-12-01')
        out['link_mail'] = [template._render_field(f, [step.id])[step.id] for f in ('subject', 'body_html')]
        # the employee's own claim page
        portal, emp = self.portal_person('WF2 P5b claimant')
        portal.lang = lang          # the employee home speaks its reader's language
        _w2, claim2, _run2 = self.claim_flow([self.todo('look', owner={'kind': 'user', 'id': self.staff.id},
                                                        title='Check receipt')], employee=emp)
        home_strip = self.env['pb.me.home'].with_user(portal).with_context(lang=lang)._wf_page_strip('expense_claim', claim2.id)
        out['home_strip'] = home_strip
        out['home_strip_page'] = str(self.env['ir.qweb'].with_context(lang=lang)._render(
            'pb_lifecycle.workflow_strip_page', {'s': home_strip, 'back': '/my/expenses/x'}))
        return out

    @staticmethod
    def _p5b_norm(value):
        text = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
        text = re.sub(r'wf-(?:publisher|test)-[0-9a-f-]{36}|wf2p4a-[\w-]+', 'LOGIN', text)
        return re.sub(r'\d+', '#', text)

    def test_wf2p5b_p1_english_is_byte_identical(self):
        self.need(self.CLAIM)
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'wf2p5b_english_baseline.json')
        now = {k: self._p5b_norm(v) for k, v in self._p5b_surfaces('en_US').items()}
        if os.environ.get('WF2P5B_WRITE_GOLDEN'):
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(dict(now, _db=self.env.cr.dbname, _company=self.company.name), f,
                          ensure_ascii=False, indent=0, sort_keys=True)
            return
        golden = json.load(open(path, encoding='utf-8'))
        db, company = golden.pop('_db'), golden.pop('_company')
        self.assertEqual(sorted(now), sorted(golden))
        # What reads the database's own set-up (routes, reminders, Hiring
        # rules, company stages, the inbox) is compared on the database the
        # golden file was written on only; the rest everywhere.
        own = ('contracts', 'existing', 'inbox', 'strip', 'progress', 'home_strip', 'home_strip_page')
        for key in golden:
            if key in own and self.env.cr.dbname != db:
                continue
            mine = now[key].replace(json.dumps(self.company.name)[1:-1], 'COMPANY')
            self.assertEqual(mine, golden[key].replace(json.dumps(company)[1:-1], 'COMPANY'), key)

    def test_wf2p5b_p2_vietnamese_and_indonesian_reach_the_surfaces(self):
        self.need(self.CLAIM)
        Lang = self.env['res.lang']
        if not (Lang._lang_get('vi_VN') and Lang._lang_get('id_ID')):
            self.skipTest('vi_VN and id_ID are not installed here')
        english = self._p5b_surfaces('en_US')

        def leaves(value, path=''):
            if isinstance(value, dict):
                for k, v in sorted(value.items()):
                    yield from leaves(v, '%s.%s' % (path, k))
            elif isinstance(value, (list, tuple)):
                for i, v in enumerate(value):
                    yield from leaves(v, '%s[%s]' % (path, i))
            elif isinstance(value, str):
                yield path, value
        # every English sentence (three letters in a row), by where it sits
        base = {p: v for p, v in leaves(english) if re.search(r'[A-Za-z]{3}', v)}
        report = {}
        for lang in ('vi_VN', 'id_ID'):
            got = self._p5b_surfaces(lang)
            mine = dict(leaves(got))
            changed = {p for p, v in mine.items() if p in base and v != base[p]}
            per_surface = {key: len([p for p in changed if p.startswith('.' + key)]) for key in english}
            report[lang] = {'changed': len(changed), 'per_surface': per_surface}
            if os.environ.get('WF2P5B_SHOW_ENGLISH'):
                for p in sorted(set(base) - changed):
                    print('WF2P5B_SAME %s %s %r' % (lang, p, base[p][:160]))
            self.assertGreaterEqual(len(changed), 30, lang)
            for key in ('schedule_words', 'schedule_issues', 'contracts', 'existing', 'inbox', 'strip', 'page',
                        'task_body', 'payloads', 'progress', 'link_mail', 'home_strip', 'home_strip_page', 'durations'):
                self.assertTrue(per_surface.get(key), '%s: nothing translated on %s' % (lang, key))
            self.assertNotRegex(json.dumps(got, ensure_ascii=False, default=str), r'(?i)odoo')
        print('WF2P5B_LANG=' + json.dumps(report))

    def test_wf2p5b_p3_messages_go_out_in_the_readers_language(self):
        """Reminders, pass-ups and team notes are written in the language of
        the person they are for; the no-login link email in the language of
        the contact with that address (else the company's)."""
        w, _d, claim = self.claim_repeat([self.check()], receipts=1)
        run = self.start(w, claim)
        line = self.lines_of(run)[0]
        step = self.step(line, 'check')
        system = self.env['pb.workflow.studio'].sudo()
        english = system._task_payload(line, step, 'reminder')
        self.assertEqual(system._task_payload(line, step, 'reminder', self.staff), english, 'English reader: as before')
        self.assertEqual(system._link_lang(self.company, 'nobody-%s@example.com' % uuid.uuid4().hex),
                         self.company.partner_id.lang or 'en_US')
        self.assertEqual(system._link_lang_prefix(self.company, 'en_US') if 'website' in self.env else '', '')
        Lang = self.env['res.lang']
        if not (Lang._lang_get('vi_VN') and Lang._lang_get('id_ID')):
            return
        self.staff.lang = 'vi_VN'
        vi = system._task_payload(line, step, 'reminder', self.staff)
        self.assertNotEqual(vi['summary'], english['summary'])
        self.assertNotEqual(vi['body'], english['body'])
        self.assertEqual(vi['res_id'], english['res_id'])
        address = 'p5b-%s@example.com' % uuid.uuid4().hex
        self.env['res.partner'].create({'name': 'P5b no login', 'email': address, 'lang': 'id_ID'})
        self.assertEqual(system._link_lang(self.company, address), 'id_ID')

    # ============================================================ WF2 P6a
    def test_wf2p6a_l1_pay_runs_are_not_a_workflow_record_type(self):
        """Pay run → payslips was not built: a pay run carries no company, so
        Studio does not offer pay runs as a record type at all and a repeat
        over payslips could never be reached (reported, WF2 P6a §1)."""
        if 'hr.payslip.run' not in self.env:
            self.skipTest('pay runs are not installed here')
        self.assertNotIn('company_id', self.env['hr.payslip.run']._fields)
        self.assertNotIn('hr.payslip.run', {r['key'] for r in self.service._models()})
        self.assertNotIn('lines', self.env['hr.payslip.run']._workflow_capabilities())

    def test_wf2p6a_l2_repeat_for_each_day_of_time_off(self):
        """Time off → each working day of the request, counted the way the
        request's own length is counted."""
        self.need('hr.leave')
        self.admin.write({'group_ids': [(4, self.env.ref('hr_holidays.group_hr_holidays_manager').id)]})
        caps = self.env['hr.leave']._workflow_capabilities()
        self.assertEqual([l['key'] for l in caps['lines']], ['days'])
        employee = self.employee('WF2 P6a leave', self.staff)
        kind = self.env['hr.leave.type'].create({'name': 'P6a kind', 'requires_allocation': False,
                                                 'leave_validation_type': 'no_validation',
                                                 'company_id': self.company.id})
        anchor = fields.Date.today() + timedelta(days=28)
        monday = anchor - timedelta(days=anchor.weekday())
        leave = self.env['hr.leave'].sudo().create({
            'holiday_status_id': kind.id, 'employee_id': employee.id, 'name': 'P6a days',
            'request_date_from': monday, 'request_date_to': monday + timedelta(days=6)})
        rows = leave._workflow_lines('days')
        working = int(round(leave.number_of_days))
        self.assertEqual(len(rows), working, rows)
        self.assertEqual(rows[0]['id'], fields.Date.to_string(monday))
        self.assertTrue(all(fields.Date.from_string(r['id']).weekday() < 5 for r in rows)
                        if working == 5 else True)
        self.assertEqual(leave._workflow_line('days', rows[-1]['id']), rows[-1])
        self.assertIsNone(leave._workflow_line('days', '1999-01-01'))
        self.assertEqual(leave._workflow_lines('other'), [])
        # through the repeat: one line per day, labelled with the day
        w, _d = self.repeat_flow([self.check()], rep_kw={'source': {'kind': 'area', 'key': 'days', 'fields': ['date', 'hours']}},
                                 before=[], model='hr.leave')
        run = self.start(w, leave)
        self.assertEqual(self.lines_of(run).mapped('line_label'), [r['name'] for r in rows])
        self.assertEqual(self.service._line_words(self.lines_of(run)[0]), 'day 1 of %s' % working)

    def test_wf2p6a_l3_an_area_without_lines_is_skipped_cleanly(self):
        """Equipment requests and joining checklists declare no lines: the
        repeat says so in plain words and nothing is offered."""
        for model in ('pb.asset.request', 'pb.journey.case'):
            if model not in self.env or model not in {r['key'] for r in self.service._models()}:
                continue
            self.assertEqual(self.service.metadata(model)['line_sources']['area'], [])
            w, d = self.workflow([], model=model)
            rep = self.rep(source={'kind': 'area', 'key': 'items'}, steps=['check'])
            d['nodes'] += [rep, self.check()]
            d['order'].append('rep')
            issues = [i for i in self.service._validate(w.sudo(), d) if i['code'] == 'repeat_source']
            self.assertTrue(issues, model)
            self.assertIn('has no lines a workflow can repeat for', issues[0]['text'])
            self.assertNotRegex(issues[0]['text'], self.BANNED)

    def test_wf2p6a_t1_line_details_are_read_again_when_a_line_step_opens(self):
        """A receipt edited after the repeat started shows its current amount
        when the next line step opens; the start value stays in the history;
        a receipt that is gone closes its line with a plain note, the count
        updates and nothing fails."""
        second = self.todo('again', owner={'kind': 'user', 'id': self.staff.id}, title='Look again')
        w, d, claim = self.claim_repeat([self.check(), second], receipts=3)
        self.assertEqual(next(n for n in d['nodes'] if n['id'] == 'rep')['steps'], ['check', 'again'])
        run = self.start(w, claim)
        lines = self.lines_of(run)
        self.assertEqual(len(lines), 3)
        receipts = claim.expense_ids.sorted(lambda e: (e.date, e.id))
        # 1: edited after the start → current amount when "Look again" opens
        receipts[0].total_amount_currency = 99.0
        self.answer_line(lines[0])
        lines.invalidate_recordset()
        self.assertEqual(lines[0].line_values['amount'], 99.0)
        self.assertEqual(lines[0].facts['line.amount'], 99.0)
        logs = self.env['pb.workflow.log'].sudo().search([('run_id', '=', lines[0].id)]).mapped('message')
        said = [m for m in logs if m.startswith('Line details read again')]
        self.assertEqual(len(said), 1, logs)
        self.assertIn('Amount is now 99 (was 10 at the start).', said[0])
        self.assertEqual(self.step(lines[0], 'again').state, 'waiting')
        # 2: unchanged → read, nothing written to the history
        self.answer_line(lines[1])
        logs = self.env['pb.workflow.log'].sudo().search([('run_id', '=', lines[1].id)]).mapped('message')
        self.assertFalse([m for m in logs if m.startswith('Line details read again')])
        # 3: gone → its open steps close with a plain note, one line fewer
        receipts[2].unlink()
        self.answer_line(lines[2])
        lines.invalidate_recordset()
        self.assertEqual(lines[2].state, 'cancelled')
        gone = self.step(lines[2], 'again')
        self.assertEqual(gone.state, 'skipped')
        self.assertIn('no longer on the record', gone.error)
        self.assertNotRegex(gone.error, self.BANNED)
        parent = self.step(run, 'rep')
        self.assertEqual(json.loads(parent.choice)['count'], 2)
        self.assertEqual(len(parent.answers['_lines']), 2)
        self.assertEqual(lines[:2].mapped('line_count'), [2, 2])
        # the two lines left finish → the repeat finishes with the new count
        self.as_staff().answer(self.step(lines[0], 'again').id, {})
        self.as_staff().answer(self.step(lines[1], 'again').id, {})
        run.invalidate_recordset()
        self.assertEqual(self.step(run, 'rep').state, 'done')
        self.assertEqual((run._values()['step.rep.count'], run._values()['step.rep.done']), (2, 2))
        self.assertEqual(run.state, 'done')

    def test_wf2p6a_x1_the_run_as_person_is_gone(self):
        for model in ('pb.workflow', 'pb.workflow.version', 'pb.workflow.event', 'pb.workflow.run'):
            self.assertNotIn('execution_user_id', self.env[model]._fields, model)
            self.env.cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s "
                                "AND column_name = 'execution_user_id'", (self.env[model]._table,))
            self.assertFalse(self.env.cr.fetchall(), model)
        rules = self.env['ir.rule'].sudo().search([('model_id.model', 'like', 'pb.workflow%')])
        self.assertFalse([r.name for r in rules if 'execution_user_id' in (r.domain_force or '')])
        # an older screen that still sends the retired keyword is answered
        w, d = self.workflow([self.todo('a')])
        self.assertTrue(self.service.save_draft(w.id, w.revision, d, execution_user_id=self.admin.id))
        # a participant still reads their own run and its history
        w2, d2 = self.workflow([self.todo('mine', owner={'kind': 'user', 'id': self.staff.id})])
        self.publish(w2, d2)
        run = self.start(w2)
        self.assertTrue(self.env['pb.workflow.run'].with_user(self.staff).search([('id', '=', run.id)]))
