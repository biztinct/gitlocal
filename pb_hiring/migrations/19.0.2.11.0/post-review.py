from odoo import SUPERUSER_ID, api, fields


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    params = env['ir.config_parameter'].sudo()
    # The original product default added two days after the 24-working-hour
    # deadline. Preserve other explicitly chosen delays.
    if params.get_param('pb_hiring.lead_late_days') in (False, '2'):
        params.set_param('pb_hiring.lead_late_days', '0')
    tpl = env.ref('pb_hiring.mail_template_feedback_lead', raise_if_not_found=False)
    if tpl and 'two days late' in (tpl.name or ''):
        tpl.write({'name': 'Hiring: overdue interview feedback (to the talent lead)',
                   'subject': 'Feedback overdue: {{ object.panel_employee_id.name }} on {{ object.interview_id.candidate_name }}'})
    # Demonstration presets only; never replace a customer's chosen pipeline.
    if cr.dbname != 'payobook':
        return
    _review_demo(env)


def _review_demo(env):
    """Repair only named demonstration records, also callable in rehearsal."""
    lead = env['res.users'].search([('login', '=', 'demo.talentlead@example.com')], limit=1)
    if not lead:
        return
    demo_users = env['res.users'].search([('login', 'in', [
        'demo.talentlead@example.com', 'demo.recruiter@example.com'])])
    demo_users.write({'group_ids': [(4, env.ref('pb_hiring.group_hiring_only').id)]})
    # Repair the exact demonstration reported by the client. Production roles
    # are deliberately not transitioned by an upgrade.
    demo_roles = env['pb.hiring.requisition'].search([
        ('title', '=', 'DEMO Territory Manager'), ('company_id', '=', lead.company_id.id),
        ('state', '=', 'open')])
    for role in demo_roles:
        filled = role.offer_ids.filtered(lambda o: o.state in ('signed', 'joined'))
        if len(filled) < max(1, role.headcount):
            continue
        role.action_mark_filled()
        dates = sorted(o.signed_on or o.joined_on or fields.Date.today() for o in filled)
        role.write({'filled_on': dates[max(1, role.headcount) - 1]})
        filled[:1]._pb_close_other_finalists(force=True)
    Preset = env['pb.hiring.stage.preset'].with_context(active_test=False)
    presets = [
        ('DEMO Field roles', ['screening', 'shortlist', 'phone', 'discussion_1', 'reference', 'offer', 'post_offer']),
        ('DEMO Tech roles', ['screening', 'shortlist', 'phone', 'assignment', 'discussion_1', 'discussion_2', 'reference', 'offer', 'post_offer']),
        ('DEMO Commercial roles', ['screening', 'shortlist', 'phone', 'discussion_1', 'discussion_2', 'discussion_3', 'reference', 'offer', 'post_offer']),
    ]
    for name, keys in presets:
        if Preset.search_count([('name', '=', name), ('company_id', '=', lead.company_id.id)]):
            continue
        stages = env['hr.recruitment.stage'].search([('pb_key', 'in', keys)])
        row = Preset.create({'name': name, 'company_id': lead.company_id.id,
                             'stage_ids': [(6, 0, stages.ids)]})
        seed = env.get('pb.demo.seed')
        if seed is not None:
            seed.register(row, 'DEMO client review hiring presets')
