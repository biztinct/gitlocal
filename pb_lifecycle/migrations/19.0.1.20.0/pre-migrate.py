# -*- coding: utf-8 -*-
"""1.19.0 -> 1.20.0 (WF2 P6a, closeout item 5) — the per-workflow "run as"
person is gone.

Since WF2 P1 workflows run at system level (R3) and `execution_user_id` was
only filled, never read. The two record rules that still named it
(`workflow_run_participant`, `workflow_log_participant`, ledger G7) are
rewritten by this version's security file; this script first rewrites their
stored domains here, so nothing evaluates a rule on a dropped column while the
module loads, then drops the four columns. Guarded: a column or rule that is
already gone is skipped, so running it twice does nothing.
"""
import logging

_logger = logging.getLogger(__name__)

TABLES = ('pb_workflow', 'pb_workflow_version', 'pb_workflow_event', 'pb_workflow_run')
RULES = {
    'workflow_run_participant': "['|', '|', ('initiator_id', '=', user.id), ('step_ids.assignee_id', '=', user.id), "
                                "('step_ids.approval_id.seat_ids.acting_user_id', '=', user.id)]",
    'workflow_log_participant': "[('run_id.initiator_id', '=', user.id)]",
}


def migrate(cr, version):
    for name, domain in RULES.items():
        cr.execute("""
            UPDATE ir_rule SET domain_force = %s
             WHERE id = (SELECT res_id FROM ir_model_data
                          WHERE module = 'pb_lifecycle' AND name = %s AND model = 'ir.rule')
               AND domain_force LIKE %s""", (domain, name, '%execution_user_id%'))
        if cr.rowcount:
            _logger.info('pb_lifecycle 1.20.0: rule %s no longer names the run-as person', name)
    for table in TABLES:
        cr.execute("""SELECT 1 FROM information_schema.columns
                       WHERE table_name = %s AND column_name = 'execution_user_id'""", (table,))
        if cr.fetchone():
            cr.execute('ALTER TABLE "%s" DROP COLUMN execution_user_id CASCADE' % table)
            _logger.info('pb_lifecycle 1.20.0: dropped %s.execution_user_id', table)
