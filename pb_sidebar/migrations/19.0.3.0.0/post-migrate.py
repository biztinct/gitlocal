# -*- coding: utf-8 -*-
"""IA redesign Cycle 5 — the rail cutover, for records the data load cannot reach.

`-u pb_sidebar` reloads `pb_sidebar/data/pb_sidebar_data.xml`, and the pre-migrate
has just made sure nothing in it is frozen, so every section and every item this
module DECLARES lands declaratively. This script is for the rest of the rail,
which is spread over seven other modules:

  * five items live in `<odoo noupdate="1">` files (Pay & Deliver, Audit,
    Tenants, Bank Verification, Young Workers). Those files are frozen on
    purpose; a loader will never write them again on an existing database, so
    their new values are hand-applied here (W13.1);
  * four records live in `noupdate="0"` files belonging to modules that may
    simply not be in this upgrade's `-u` list — `pb_mission`'s Workforce item,
    `pb_learn`'s section and leaf, `pb_payrun_results`' Results Grid. Upgrading
    pb_sidebar alone must still produce the right rail, and `sec_learn` in
    particular MUST move: it sits on sequence 50, which is where the System
    section now is, and two sections on one number order themselves by id — a
    rail that differs between two databases with the same code (W70).

W27's warning about hand-applied values is the reason
`pb_sidebar/tests/test_ia_c5.py::test_the_migration_agrees_with_every_data_file`
exists: it reads each table below back out of the XML that owns the record and
fails on any disagreement, so this script cannot drift from the files it is
standing in for.

IDEMPOTENT, AND THAT IS A PROPERTY OF THE GUARD RATHER THAN OF THE RUN. Every
retirement writes only while the record is still on a PRE-cutover sequence
(< 900); every move writes only while the record is not already where it
belongs. A second run therefore writes nothing, which is what makes it safe to
re-run on a clone — and it also means an administrator who deliberately
re-enables a retired item afterwards is not overruled the next time a migration
happens to run.
"""
import logging

from odoo import SUPERUSER_ID, api

# The logger is NAMED rather than derived from `__name__`, and that is not
# cosmetic. Odoo loads a migration script through `importlib` with the FILE STEM
# as its module name, so `__name__` here is `post-migrate` — a logger outside the
# `odoo.` namespace, which `--log-level=info` does not configure and which
# therefore inherits the root level and prints NOTHING. A migration that reports
# what it did into a logger nobody has configured is a migration you cannot audit
# after a production deploy, and the silence is indistinguishable from a script
# that never ran. (Found in Cycle 5 while trying to prove idempotency: the
# retirements had demonstrably landed and the log had not one line about them.)
_logger = logging.getLogger('odoo.addons.pb_sidebar.migrations')

# The 900+ RETIRED BAND (W18). A deactivated item still OCCUPIES its sequence —
# `pb.sidebar.item` uniqueness is asserted with `active_test=False`, because a
# duplicate only has to matter the moment an admin re-enables one — and after
# this cutover almost every retired item's old number belongs to something else.
#
# (module, name, new_sequence). Items only; sections are below.
RETIRE_ITEMS = [
    # --- noupdate="1" files: nothing but this script can move them ---
    ('pb_pay_delivery', 'item_pay_deliver', 919),
    ('pb_audit', 'item_audit_console', 974),
    ('pb_tenants', 'item_tenants', 975),
    ('pb_bank_ocr', 'item_bank_verification', 951),
    ('pb_young_worker', 'item_young_workers', 952),
    # --- noupdate="0", but the owning module may not be in this `-u` ---
    ('pb_payrun_results', 'item_payrun_results', 918),
]

# Sections whose own module may not be upgraded beside pb_sidebar. `sec_learn`
# is the load-bearing one: leaving it on 50 collides with the System section.
MOVE_SECTIONS = [
    # (module, name, sequence, name_en)
    ('pb_learn', 'sec_learn', 40, 'Grow'),
]

# Items that MOVE rather than retire. `pb_mission`'s Workforce record leaves the
# retired WORKFORCE section for OPERATE, beside Pay Run and People.
MOVE_ITEMS = [
    # (module, name, section_xmlid, sequence, name_en, icon)
    ('pb_mission', 'item_workforce', 'pb_sidebar.sec_payrun', 30, 'Workforce',
     'compass'),
    ('pb_learn', 'item_learn_journey', 'pb_learn.sec_learn', 10, 'Learn',
     'book-open'),
]


def migrate(cr, version):
    if not version:
        return

    # `active_test=False` on the environment, because every record this script
    # touches is either already inactive or about to be, and a browse through an
    # active-only env is a browse that silently reads nothing back.
    env = api.Environment(cr, SUPERUSER_ID, {'active_test': False})

    retired = moved = 0

    # ------------------------------------------------------------ retirements
    for module, name, sequence in RETIRE_ITEMS:
        rec = env.ref('%s.%s' % (module, name), raise_if_not_found=False)
        if not rec:
            # The module is not installed here. Not an error: the rail simply
            # never had that entry.
            continue
        if rec.sequence >= 900:
            continue                    # already cut over — idempotent
        rec.write({'active': False, 'sequence': sequence})
        retired += 1
        _logger.info('pb_sidebar C5: retired %s.%s -> seq %s, inactive',
                     module, name, sequence)

    # ------------------------------------------------------------------ moves
    for module, name, sequence, label in MOVE_SECTIONS:
        rec = env.ref('%s.%s' % (module, name), raise_if_not_found=False)
        if not rec:
            continue
        if rec.sequence == sequence:
            continue                    # already cut over — idempotent
        # The English label is written alongside the sequence because the two
        # are one decision, and because a section renamed by its own module's
        # data file would otherwise be renamed only on databases that upgraded
        # that module (W27's shape).
        rec.write({'sequence': sequence, 'name': label})
        moved += 1
        _logger.info('pb_sidebar C5: moved section %s.%s -> "%s" seq %s',
                     module, name, label, sequence)

    for module, name, section_xmlid, sequence, label, icon in MOVE_ITEMS:
        rec = env.ref('%s.%s' % (module, name), raise_if_not_found=False)
        section = env.ref(section_xmlid, raise_if_not_found=False)
        if not rec or not section:
            continue
        if rec.section_id == section and rec.sequence == sequence \
                and rec.icon == icon:
            continue                    # already cut over — idempotent
        rec.write({'section_id': section.id, 'sequence': sequence,
                   'name': label, 'icon': icon})
        moved += 1
        _logger.info('pb_sidebar C5: moved %s.%s -> %s seq %s, "%s" (%s)',
                     module, name, section_xmlid, sequence, label, icon)

    _logger.info('pb_sidebar C5 cutover: %s item(s) retired, %s record(s) moved.',
                 retired, moved)
