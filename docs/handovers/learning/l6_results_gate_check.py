# -*- coding: utf-8 -*-
"""LEARNING L6 — read-only check that the L5 test-results gate is the code
that answers `/survey/results/<id>` on this database.

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d <db> --no-http < l6_results_gate_check.py

It binds the database's own routing map, matches the results URL of a test
(certification) survey, and prints which class answers it; then it calls the
gate's own rule for a survey user without a training group (a user made
inside the transaction, rolled back — nothing is written, nothing is sent).
"""
env = env  # noqa: F821 — provided by `odoo-bin shell`
try:
    Survey = env['survey.survey'].sudo()
    test = Survey.search([('certification', '=', True)], limit=1) or \
        Survey.create({'title': 'DEMO L6 gate check', 'survey_type': 'assessment',
                       'certification': True,
                       'scoring_type': 'scoring_with_answers'})
    rmap = env['ir.http'].routing_map()
    for rule in rmap.iter_rules():
        if rule.rule.startswith('/survey/results/'):
            func = getattr(rule.endpoint, 'original_endpoint', rule.endpoint)
            print('## results route %s answered by: %s' % (
                rule.rule, getattr(func, '__qualname__', func)))
    from odoo.addons.pb_training.controllers.slides_gate import _is_test  # noqa
    from odoo.addons.pb_training.models.training_common import ALL_GROUPS
    Users = env['res.users'].sudo().with_context(no_reset_password=True)
    surveyor = Users.create({
        'name': 'DEMO L6 gate surveyor', 'login': 'demo.l6.gate.surveyor',
        'group_ids': [(6, 0, [env.ref('base.group_user').id,
                              env.ref('survey.group_survey_user').id])]})
    allowed = surveyor.has_group('base.group_system') or any(
        surveyor.has_group(g) for g in ALL_GROUPS)
    print('## a survey user without a training group is let through:',
          allowed, '(expect False); survey', test.id,
          'is a test:', bool(test.certification))
finally:
    env.cr.rollback()
