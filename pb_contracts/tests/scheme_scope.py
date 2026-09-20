# -*- coding: utf-8 -*-
"""Two fixture helpers the CD suites need after SCHEMECTX P2.

WHAT CHANGED UNDER THEM. Until this phase `hr.contract.create` created one
`hr.contract.advantage` per row of the shared catalogue, so a test could make a
template, make a contract and find a line waiting for it. That fan-out is gone
(it is what put Indian components on Vietnamese people), and the components tab
now follows the scheme that pays the person.

So a fixture has to say two things it never had to say before: put the lines on
the contract, and say who pays this person. Both are one call each.
"""


def catalogue_lines(env, contract):
    """Give this contract one line per catalogue row — the old fan-out, by hand.

    Idempotent, and it never touches a line that is already there.
    """
    Template = env['hr.contract.advantage.template'].sudo()
    Advantage = env['hr.contract.advantage'].sudo()
    held = set(Advantage.search([('contract_id', '=', contract.id)])
               .mapped('advantage_template_id').ids)
    for template in Template.search([]):
        if template.id in held:
            continue
        Advantage.create({'contract_id': contract.id,
                          'advantage_template_id': template.id})
    return contract.advantages_ids


def paid_by(env, employees, config):
    """Say which payroll scheme pays these people, without a map.

    The drawer asks `hr.formula.config.schemes_for_employee`, which reads the
    stored "Paid by" and only falls back to the map when it is marked as
    needing working out again. Stamping both fields is therefore the whole of
    the fixture — and it is what the scheme map's own cron would write.
    """
    if 'pb_paid_by_id' not in env['hr.employee']._fields or not config:
        return False
    employees.sudo().write({'pb_paid_by_id': config.id,
                            'pb_paid_by_stale': False})
    return True
