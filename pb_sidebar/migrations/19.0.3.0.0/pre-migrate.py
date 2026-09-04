# -*- coding: utf-8 -*-
"""IA redesign Cycle 5 — let the data files heal the rail cutover.

An upgrade runs `pre-migrate -> DATA FILES LOAD -> post-migrate`, and this is the
pre half for one reason: `ir_model_data.noupdate` is a stored PER-RECORD column
that Odoo never refreshes (W13.1). If any record below was ever written by a
loader that flagged it — an old file revision, a manual `ir.model.data` edit, a
restore from a database where it was frozen — the loader silently skips it
forever, `-u` returns EXIT 0, and the repo and the rail disagree with nothing in
the log to say so. This codebase has paid for that three times.

Clearing the flag HERE rather than hand-applying values in the post half is W27,
learned the expensive way in P1b: a post-migrate that clears the flag clears it
*after* the loader has already skipped the file, so only the fields the script
itself rewrites actually move. P1b changed two fields on one record that way and
shipped one of them, with EXIT 0 and a clean log. The cutover changes up to five
fields on some of these records (section, sequence, name, active, match lists),
so hand-applying them would be five chances to drift from the XML.

WHAT IS AND IS NOT HERE. Every record listed below comes from a data file that
is `<odoo noupdate="0">`, so unfreezing it is a repair and never a change of
policy — the file was always meant to own the value. The five rail items that
live in `noupdate="1"` files (Pay & Deliver, Audit, Tenants, Bank Verification,
Young Workers) are deliberately NOT unfrozen: their files are frozen on purpose,
and moving them is the post-migrate's job.

Idempotent and narrow: a fixed list of xmlids, one column, nothing written where
the flag is already clear.
"""
import logging

# The logger is NAMED rather than derived from `__name__`, and that is not
# cosmetic. Odoo loads a migration script through `importlib` with the FILE STEM
# as its module name, so `__name__` here is `pre-migrate` — a logger outside the
# `odoo.` namespace, which `--log-level=info` does not configure and which
# therefore inherits the root level and prints NOTHING. A migration that reports
# what it did into a logger nobody has configured is a migration you cannot audit
# after a production deploy, and the silence is indistinguishable from a script
# that never ran. (Found in Cycle 5 while trying to prove idempotency: the
# retirements had demonstrably landed and the log had not one line about them.)
_logger = logging.getLogger('odoo.addons.pb_sidebar.migrations')

# (module, model, name) of every record whose OWN data file must reach it in
# this upgrade. Grouped by the module that declares it.
XMLIDS = [
    # ---- pb_sidebar's own sections: four renamed/renumbered, five retired ----
    ('pb_sidebar', 'pb.sidebar.section', 'sec_overview'),
    ('pb_sidebar', 'pb.sidebar.section', 'sec_payrun'),        # -> Operate 20
    ('pb_sidebar', 'pb.sidebar.section', 'sec_insights'),      # -> Understand 30
    ('pb_sidebar', 'pb.sidebar.section', 'sec_admin'),         # -> System 50
    ('pb_sidebar', 'pb.sidebar.section', 'sec_setup'),
    ('pb_sidebar', 'pb.sidebar.section', 'sec_people'),
    ('pb_sidebar', 'pb.sidebar.section', 'sec_workforce'),
    ('pb_sidebar', 'pb.sidebar.section', 'sec_compliance'),
    ('pb_sidebar', 'pb.sidebar.section', 'sec_planning'),
    # ---- pb_sidebar's own items: every one of them retires ----
    ('pb_sidebar', 'pb.sidebar.item', 'item_dashboard'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_approvals'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_run_payroll'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_pay_runs'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_payslips'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_import'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_wf_payroll_report'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_full_final'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_proration'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_retro'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_formula'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_structures'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_statutory'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_integrations'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_emp_mapping'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_employees'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_contracts'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_analytics'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_explorer'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_workforce_insights'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_reports'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_govt_reports'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_wfp_dashboard'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_wfp_scenarios'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_wfp_forecasts'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_wfp_grades'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_wfp_merit'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_wfp_cycles'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_wfp_tags'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_roles'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_companies'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_menu_cfg'),
    ('pb_sidebar', 'pb.sidebar.item', 'item_section_cfg'),
    # ---- other modules whose data files are noupdate="0" ----
    ('pb_mission', 'pb.sidebar.item', 'item_workforce'),        # -> Operate 30
    ('pb_learn', 'pb.sidebar.section', 'sec_learn'),            # -> Grow 40
    ('pb_learn', 'pb.sidebar.item', 'item_learn_journey'),      # -> book-open
    ('pb_payrun_results', 'pb.sidebar.item', 'item_payrun_results'),
]


def migrate(cr, version):
    if not version:
        return

    cleared = []
    for module, model, name in XMLIDS:
        cr.execute("""
            UPDATE ir_model_data
               SET noupdate = false
             WHERE module = %s AND name = %s AND model = %s
               AND noupdate
        """, (module, name, model))
        if cr.rowcount:
            cleared.append('%s.%s' % (module, name))

    if cleared:
        _logger.info(
            "pb_sidebar C5: cleared the stored noupdate flag on %s record(s) so "
            "their own data files apply in this same upgrade (W13.1/W27): %s",
            len(cleared), ', '.join(cleared))
