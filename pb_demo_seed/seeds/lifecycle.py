"""Additive lifecycle examples, owned by a dedicated removable register."""
from datetime import timedelta
from odoo import fields
from odoo.exceptions import UserError
from ..models.demo_seed import SeedContext

NAME = 'DEMO Lifecycle journeys'


def find(env):
    return env['pb.demo.seed'].sudo().search([
        ('name', '=', NAME), ('company_id', '=', env.company.id)], limit=1)


def load(env):
    for model in ('pb.hiring.requisition', 'pb.holiday.batch'):
        if model not in env:
            raise UserError('Install Hiring and the holiday journey before loading these examples.')
    seed = find(env)
    if seed and seed.record_ids:
        return seed  # Additive and repeatable; never rebuild the existing world.
    seed = seed or env['pb.demo.seed'].sudo().create({
        'name': NAME, 'profile': 'adopted', 'company_id': env.company.id})
    ctx = SeedContext(seed)
    manager = ctx.create('hr.employee', {'name': 'DEMO Lifecycle Manager',
        'work_email': 'demo-manager@example.invalid', 'employee_type': 'employee'})
    ctx.track(manager.work_contact_id, label='DEMO manager contact', last=True)
    department = ctx.create('hr.department', {'name': 'DEMO Product & Operations', 'manager_id': manager.id})
    manager.department_id = department
    country = env.company.country_id or env.ref('base.sg')
    for index, (title, opened) in enumerate([('DEMO Product Designer', True), ('DEMO Operations Associate', False)], 1):
        req = ctx.create('pb.hiring.requisition', {
            'name': 'DEMO-LIFECYCLE-%s' % index, 'title': title,
            'requested_by_id': manager.id, 'reporting_manager_id': manager.id,
            'department_id': department.id, 'country_id': country.id,
            'location': country.name, 'budget_cost': 120000,
            'pb_role_level': 'Senior' if opened else 'Associate',
            'pb_target_close_date': ctx.today + timedelta(days=35),
            'requirements': 'DEMO role: simplify team workflows and deliver clear, accessible experiences.',
        })
        for round_no, focus in enumerate(['Experience and craft', 'Collaboration and judgement', 'Role expectations'], 1):
            stage = env['hr.recruitment.stage'].sudo().search([('pb_key', '=', 'discussion_%s' % round_no)], limit=1)
            ctx.create('pb.hiring.step', {'name': 'DEMO Discussion %s' % round_no,
                'requisition_id': req.id, 'sequence': round_no * 10, 'kind': 'interview',
                'owner_id': env.user.id, 'notes': 'DEMO focus: ' + focus, 'stage_id': stage.id})
        ctx.create('pb.hiring.jd', {'requisition_id': req.id, 'title': title,
            'body': '<h2>DEMO role</h2><p>A sample role description for demonstrating the approval workflow.</p>'})
        if not opened:
            continue
        job = ctx.create('hr.job', {'name': title, 'department_id': department.id,
            'user_id': env.user.id, 'is_published': False, 'no_of_recruitment': 1})
        req.sudo().write({'job_id': job.id, 'recruiter_id': env.user.id})
        req._chain_state_write('open')
        for person, key in [('DEMO Alex Morgan', 'screening'), ('DEMO Sam Rivera', 'discussion_1'), ('DEMO Casey Lee', 'on_hold')]:
            stage = env['hr.recruitment.stage'].sudo().search([('pb_key', '=', key)], limit=1)
            ctx.create('hr.applicant', {'partner_name': person, 'email_from': person.split()[1].lower() + '@example.invalid',
                'job_id': job.id, 'pb_requisition_id': req.id, 'stage_id': stage.id,
                'pb_location': country.name, 'pb_linkedin': 'https://example.invalid/profile',
                'pb_first_touch': {'source': 'DEMO careers campaign', 'medium': 'demo'},
                'pb_application_touch': {'source': 'DEMO careers campaign', 'medium': 'demo'},
                'pb_stage_reason': 'DEMO awaiting availability' if key == 'on_hold' else False,
                'pb_hold_until': ctx.today + timedelta(days=3) if key == 'on_hold' else False})
    colleague = ctx.create('hr.employee', {'name': 'DEMO Probation Colleague',
        'department_id': department.id, 'parent_id': manager.id,
        'work_email': 'demo-probation@example.invalid', 'employee_type': 'employee',
        'pb_probation_state': 'in_probation', 'trial_date_end': ctx.today + timedelta(days=15)})
    ctx.track(colleague.work_contact_id, label='DEMO colleague contact', last=True)
    review = ctx.create('pb.probation.review', {'employee_id': colleague.id, 'kind': 'probation',
        'trial_end': colleague.trial_date_end, 'manager_user_id': env.user.id, 'state': 'verdict',
        'pb_manager_quality': '3', 'pb_manager_culture': '4', 'pb_manager_adaptability': '3', 'pb_manager_initiative': '3'})
    review._ensure_one_on_one()
    checkin = review.one_on_one_checkin_id
    checkin.sudo().write({'state': 'done', 'notes': 'DEMO completed manager conversation; ready to propose an outcome.'})
    ctx.track(checkin, label='DEMO manager conversation')
    ctx.create('pb.holiday.batch', {'name': 'DEMO Calendar review', 'year': ctx.today.year,
        'source': 'DEMO illustrative dates — review before publishing', 'rows_json': [
            {'id': 0, 'name': 'DEMO Team day', 'date': str(ctx.today), 'date_to': str(ctx.today),
             'kind': 'company', 'decision': 'review', 'conflict': False, 'issue': 'DEMO date; choose an appropriate date before use.'}]})
    seed.sudo().write({'state': 'loaded', 'loaded_on': fields.Datetime.now(),
        'loaded_by': env.uid, 'summary': ctx.summary()})
    return seed


def remove(env):
    seed = find(env)
    if not seed:
        return (0, 0, [])
    # Published DEMO versions can acquire calendar rows through the real UI.
    # Adopt only rows attached to this register's exact batch IDs, never a prefix search.
    ctx = SeedContext(seed)
    for review in seed._registered('pb.probation.review'):
        letter = review.letter_id
        if letter:
            ctx.track(letter, label='DEMO probation outcome letter')
            ctx.track(letter.attachment_id, label='DEMO probation PDF')
            if letter.document_id:
                ctx.track(letter.document_id, label='DEMO filed probation letter')
                ctx.track(letter.document_id.attachment_id, label='DEMO filed letter PDF')
    for batch in seed._registered('pb.holiday.batch'):
        leaves = env['resource.calendar.leaves'].sudo().search([('pb_holiday_batch_id', '=', batch.id)])
        if not batch.name.startswith('DEMO') or any(not leaf.name.startswith('DEMO') for leaf in leaves):
            raise UserError('A demo calendar contains renamed records. Review them before removing this demo.')
        for leaf in leaves:
            ctx.track(leaf, label=leaf.name)
        if batch.state == 'published':
            batch.sudo().write({'state': 'draft'})
    return seed.remove_demo()
