# -*- coding: utf-8 -*-
"""The DEMO sweep: no customer's name in demo data, and every demo record on
the register.

WHY THIS EXISTS (owner ruling D18, 2026-09-16). The demo data built on the live
`payobook` database is KEPT — it is what the product is shown with. But the
owner may show that same database to the customer's competitors, so nothing a
viewer can read may carry the customer's name: not a record's name, not a
subject, not a note, not a chatter line, not a login, not an email address. And
everything that IS demo data belongs on the Demo data register, so that one
button can take it all out again the day the demo is over.

WHAT IT DOES, IN THREE PARTS
    1. RENAME. Every row that spells the customer's name is rewritten, whole
       word, case preserved: "RIZE W2 Site Agronomist" becomes "DEMO Site
       Agronomist", `rize.w2.thao@example.com` becomes `demo.thao@example.com`.
       The records whose names are MIRRORED somewhere else (a job title is
       translated, a person's name is copied onto their resource and their
       contact, a candidate's name is copied onto every interview) go through
       the ORM so the copies follow; the history behind them — chatter,
       activities, approval trails — is rewritten in SQL, because there is
       nothing to recompute and hundreds of rows to get through.
    2. REGISTER. Every demo record from waves 1 and 2 is written onto one
       "DEMO HR programme data" panel, in the order it was created, because
       creation order is dependency order and the removal walks it backwards.
    3. PROVE. The whole-word scan is run again over every text column in the
       database, and what is left is listed with the reason it is allowed to
       stay.

WHAT IT REFUSES TO TOUCH
    The tenant record "Rize Farms" and its backups (a REAL tenant, not demo
    data), the alerts that monitor that tenant (they name it because it is the
    one they are about), the Turkish province of the same name, and the
    transient bus rows that expire on their own. Module names, xmlids, code
    comments and commit messages keep the old word: they are engineering
    text, and nobody demonstrating the product reads them.

    It NEVER presses Load or Remove. It creates no demo data and deletes no
    record. Part 2 only writes register rows.

IDEMPOTENT. A second run renames nothing (there is nothing left spelling the
name), registers nothing (the register dedups per record) and says so.

USAGE (the service must be stopped — an Odoo shell wants the database to
itself)::

    sudo service odoo-server stop
    PB_SWEEP_DRY=1 sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell \\
        -c /etc/odoo-server.conf -d payobook --http-port=8199 \\
        --logfile=/tmp/sweep.log < tools/demo_sweep_payobook.py

`PB_SWEEP_DRY=1` counts everything and writes nothing — run it first and read
what it says it would do. Without it the script commits at the end of each
part. `PB_SWEEP_PART=1`, `=2` or `=3` runs one part on its own.
"""

import logging
import os
import re

_logger = logging.getLogger('demo_sweep')

DRY = os.environ.get('PB_SWEEP_DRY') == '1'
ONLY = os.environ.get('PB_SWEEP_PART') or ''

# =====================================================================
#  The rule: what the customer's name is replaced with
# =====================================================================
#
# CASE IS PART OF THE MEANING. "RIZE W2 Field Officer" is a job title in a
# list beside real ones, "rize.w2.thao@example.com" is an address somebody
# may have to type, and "Rize" mid-sentence is prose. Each keeps its shape.
#
# ORDER MATTERS. The dotted and hyphenated forms are addresses and URLs and
# must be matched before the bare word, or "rize.w2.thao" becomes
# "demo.w2.thao" and the address stops being one anybody recognises.
_RULES = (
    (re.compile(r'rize\.w2\.', re.I), 'demo.'),
    (re.compile(r'rize-w2-', re.I), 'demo-'),
    (re.compile(r'\bRIZE[ _-]?W2\b'), 'DEMO'),
    (re.compile(r'\bRize[ _-]?W2\b'), 'Demo'),
    (re.compile(r'\brize[ _-]?w2\b'), 'demo'),
    (re.compile(r'\bRIZE\b'), 'DEMO'),
    (re.compile(r'\bRize\b'), 'Demo'),
    (re.compile(r'\brize\b'), 'demo'),
)

#: What a row has to look like to be worth reading. The whole-word test is the
#: one that counts (a substring test also finds "authorized"); the two other
#: forms are addresses and URLs, where the word has a dot or a hyphen beside it
#: rather than a space.
#:
#: TWO SPELLINGS OF THE SAME TEST, because Postgres and Python do not write a
#: word boundary the same way: `\m`/`\M` there, `\b` here. Postgres does the
#: finding (it is the one with the indexes and the rows), Python does the
#: replacing.
_FINDS = re.compile(r'(\brize\b)|(rize\.w2\.)|(rize-w2-)', re.I)
_SQL_FINDS = r"(%s ~* '\mrize\M' or %s ~* 'rize\.w2\.' or %s ~* 'rize-w2-')"


def swap(text):
    """The customer's name out, DEMO in, with the shape of the word kept."""
    if not text:
        return text
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text


# =====================================================================
#  Part 1 — rename
# =====================================================================
#
# THROUGH THE ORM, because the value is copied somewhere else and the copy has
# to follow: a job title is a translated column, a person's name is written
# onto their resource and their private contact, a candidate's name is stored
# on every interview and offer that mentions them, and a contact's e-mail is
# normalised into a second column. A raw UPDATE would leave every one of those
# spelling the old name with nothing to say it had gone stale.
#
# (model, table, columns) — the ids are found from the table, so a row that
# appears after this file was written is still caught.
ORM_TARGETS = (
    ('res.partner', 'res_partner', ('name', 'email')),
    ('res.users', 'res_users', ('login', 'signature')),
    ('hr.employee', 'hr_employee', ('name', 'legal_name', 'work_email')),
    ('hr.applicant', 'hr_applicant', ('partner_name', 'email_from')),
    ('hr.job', 'hr_job', ('name',)),
    ('pb.hiring.requisition', 'pb_hiring_requisition', ('title',)),
    ('pb.hiring.jd', 'pb_hiring_jd', ('title', 'body_html')),
    ('pb.hiring.posting', 'pb_hiring_posting', ('subject', 'body_html')),
    ('pb.hiring.referral', 'pb_hiring_referral',
     ('candidate_name', 'candidate_email')),
    ('pb.hiring.interview', 'pb_hiring_interview', ('location',)),
    ('pb.hiring.feedback', 'pb_hiring_feedback', ('notes',)),
    ('pb.hiring.country.rule', 'pb_hiring_country_rule', ('note',)),
    ('pb.hiring.offer', 'pb_hiring_offer', ('job_title',)),
    ('calendar.event', 'calendar_event', ('name', 'description', 'location')),
    ('project.task', 'project_task', ('name', 'description')),
    ('discuss.channel', 'discuss_channel', ('name',)),
)

#: Tables the sweep must NOT rewrite, and why.
#:
#: The first three are the same fact from three directions: there is a REAL
#: tenant of this product whose name is the word being swept, and a monitoring
#: alert that stops naming the thing it is about is a broken alert. The
#: province is a place in Turkey. The bus rows are the browser's push channel
#: and expire within the hour.
SURVIVORS = {
    'pb_tenant': 'a real tenant record — the customer has a live tenancy',
    'pb_tenant_backup': "the real tenant's backup paths on disk",
    'pb_alert': 'monitoring alerts ABOUT that real tenant, by name',
    'res_country_state': 'a province of Turkey, nothing to do with anybody',
    'bus_bus': 'the browser push channel — transient, expires within the hour',
    'mail_compose_message': 'a transient wizard row; it is vacuumed, not edited',
}


def _remember(backup, table, column, res_id, old, new):
    """One line of the undo log: where it was, what it said, what it says now."""
    if backup is None:
        return
    backup.write('%s\t%s\t%s\t%s\t%s\n' % (
        table, column, res_id,
        str(old).replace('\t', ' ').replace('\n', '\\n'),
        str(new).replace('\t', ' ').replace('\n', '\\n')))


def _columns(env, table):
    """Every text-ish column of one table, with whether it is jsonb."""
    env.cr.execute("""
        SELECT column_name, data_type FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = %s
           AND data_type IN ('text', 'character varying', 'jsonb')
    """, (table,))
    return env.cr.fetchall()


def _has_id(env, table):
    env.cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = %s
           AND column_name = 'id'
    """, (table,))
    return bool(env.cr.fetchone())


def _text_tables(env):
    """Every real table with a text column, worst case for the scan."""
    env.cr.execute("""
        SELECT DISTINCT c.table_name
          FROM information_schema.columns c
          JOIN pg_tables p ON p.tablename = c.table_name
                          AND p.schemaname = 'public'
         WHERE c.table_schema = 'public'
           AND c.data_type IN ('text', 'character varying', 'jsonb')
           AND c.table_name NOT LIKE 'ir\\_%'
         ORDER BY 1
    """)
    return [row[0] for row in env.cr.fetchall()]


def scan(env):
    """Every column that still spells the customer's name, with a count.

    TWO STAGES, BECAUSE ONE WAS UNUSABLE. Asking the question column by column
    reads the whole of `hr_payslip_line` — seven hundred thousand rows — once
    for every text column it has, and the sweep spent a quarter of an hour
    proving that a payslip line has never mentioned anybody. Asking it once
    per TABLE, with every column ORed together, is one read; only the handful
    of tables that answer yes are then broken down by column. Same answer,
    minutes instead of hours.
    """
    found = []
    for table in _text_tables(env):
        columns = _columns(env, table)
        if not columns:
            continue
        whole = ' OR '.join(_SQL_FINDS % (('"%s"::text' % c,) * 3)
                            for c, _k in columns)
        try:
            env.cr.execute('SELECT 1 FROM "%s" WHERE %s LIMIT 1'
                           % (table, whole))
            hit = env.cr.fetchone()
        except Exception:                          # noqa: BLE001
            env.cr.rollback()
            continue
        if not hit:
            continue
        for column, kind in columns:
            test = _SQL_FINDS % (('"%s"::text' % column,) * 3)
            try:
                env.cr.execute('SELECT count(*) FROM "%s" WHERE %s'
                               % (table, test))
                count = env.cr.fetchone()[0]
            except Exception:                      # noqa: BLE001
                env.cr.rollback()
                continue
            if count:
                found.append((table, column, kind, count))
    return found


def rename(env):
    """Part 1. Returns the per-column before/after counts."""
    print('\n=== PART 1 — rename ===')
    # EVERY OLD VALUE IS WRITTEN DOWN FIRST. A rename over a live database is
    # not undone by running the rule backwards — "DEMO" cannot say whether it
    # used to be "RIZE" or "RIZE W2" — so the only honest undo is the list of
    # what each row said before. One tab-separated line per value changed.
    backup = None
    if not DRY:
        path = os.environ.get('PB_SWEEP_BACKUP', '/tmp/demo_sweep_backup.tsv')
        backup = open(path, 'a', encoding='utf-8')            # noqa: SIM115
        print('  the old values are being written to %s' % path)
    found = scan(env)
    before = {(t, c): n for t, c, _k, n in found}
    print('%s columns carry the name, %s rows in total'
          % (len(before), sum(before.values())))

    # -- the records whose name is mirrored somewhere else ---------------
    #
    # TRACKING OFF, ALWAYS. A tracked write posts a chatter line saying
    # "Title: RIZE W2 Field Officer → DEMO Field Officer" — which writes the
    # old name back into the database, in a message nobody can rename away
    # afterwards. The one thing this sweep must not do is create new work for
    # itself.
    touched = {}
    for model_name, table, columns in ORM_TARGETS:
        if model_name not in env:
            continue
        model = env[model_name].sudo().with_context(
            tracking_disable=True, mail_notrack=True, mail_create_nolog=True,
            active_test=False)
        present = {c for c, _k in _columns(env, table)} & set(columns)
        if not present:
            continue
        test = ' OR '.join(_SQL_FINDS % (('"%s"::text' % c,) * 3)
                           for c in sorted(present))
        env.cr.execute('SELECT id FROM "%s" WHERE %s' % (table, test))
        ids = [row[0] for row in env.cr.fetchall()]
        for record in model.browse(ids).exists():
            values = {}
            for column in sorted(present):
                if column not in record._fields:
                    continue
                old = record[column]
                if not isinstance(old, str):
                    continue
                new = swap(old)
                if new != old:
                    values[column] = new
            if not values or DRY:
                touched[model_name] = touched.get(model_name, 0) + bool(values)
                continue
            for column, new in values.items():
                _remember(backup, table, column, record.id, record[column], new)
            try:
                with env.cr.savepoint():
                    record.write(values)
                touched[model_name] = touched.get(model_name, 0) + 1
            except Exception as exc:               # noqa: BLE001
                print('  ! %s(%s) refused the rename: %s'
                      % (model_name, record.id, exc))
    if not DRY:
        env.flush_all()
        env.invalidate_all()
    for model_name, count in sorted(touched.items()):
        print('  %-28s %s record(s) renamed through the app'
              % (model_name, count))

    # -- everything else, in SQL ----------------------------------------
    #
    # Chatter bodies, activity notes, approval trails, tracking values, queued
    # mail. There is nothing to recompute in any of them and there are
    # hundreds of rows, so they are read, swapped in Python — by the SAME
    # function the records above used, so the rule cannot drift — and written
    # back one statement per row.
    rows_written = {}
    for table, column, kind, _count in (found if DRY else scan(env)):
        if table in SURVIVORS:
            continue
        if not _has_id(env, table):
            print('  ! %s.%s has no id column — left alone' % (table, column))
            continue
        test = _SQL_FINDS % (('"%s"::text' % column,) * 3)
        env.cr.execute('SELECT id, "%s"::text FROM "%s" WHERE %s'
                       % (column, table, test))
        for res_id, value in env.cr.fetchall():
            new = swap(value)
            if new == value:
                continue
            rows_written[(table, column)] = \
                rows_written.get((table, column), 0) + 1
            if DRY:
                continue
            _remember(backup, table, column, res_id, value, new)
            cast = '::jsonb' if kind == 'jsonb' else ''
            env.cr.execute('UPDATE "%s" SET "%s" = %%s%s WHERE id = %%s'
                           % (table, column, cast), (new, res_id))
    for (table, column), count in sorted(rows_written.items()):
        print('  %-44s %s row(s) rewritten' % ('%s.%s' % (table, column), count))

    if not DRY:
        backup.flush()
        backup.close()
        env.invalidate_all()
        env.cr.commit()
    after = {(t, c): n for t, c, _k, n in scan(env)}
    print('\n  column                                        before   after')
    for key in sorted(set(before) | set(after)):
        table, column = key
        mark = '  (allowed to stay)' if table in SURVIVORS else ''
        print('  %-44s %6s  %6s%s'
              % ('%s.%s' % (table, column), before.get(key, 0),
                 after.get(key, 0), mark))
    return before, after


# =====================================================================
#  Part 2 — register
# =====================================================================
#
# WHAT IS DEMO DATA AND WHAT IS NOT is the whole difficulty of this part, and
# spelling is not the answer (the module's own first paragraph says so: a rule
# about spelling pretending to be a rule about origin). So the demo records are
# named by ID, from the programme's own ledger and closeout, and everything the
# PRODUCT then made for them is found by following the pointers.

#: The people, teams and logins the programme made. Named by id, from
#: RIZE_CLOSEOUT.md and the ledger's per-phase "test cast" entries.
ROOTS = {
    # Wave 1 — the test cast (RIZE_CLOSEOUT.md "Demo data left in place").
    'hr.employee': list(range(17118, 17149)) + [17338, 19613, 19614],
    'res.users': [2326, 2333, 2336, 2337, 2338, 2339, 2340,   # wave 1
                  4446,                                        # A1 recruiter
                  5105, 5106],                                 # A3 portal
    'hr.department': [656, 657, 658],
    'pb.vendor': [12],
    # Wave 2 — hiring.
    'hr.job': [147, 148, 149, 150, 151, 153, 762],
    'pb.hiring.requisition': list(range(55, 64)) + [798],
    'hr.applicant': [54, 175, 176, 177, 552, 553, 554],
    'pb.hiring.country.rule': [8],
    'pb.hiring.step': [20, 21],
    'res.partner': [21912, 21913, 22960, 22961, 22962],
    'pb.journey.case': [2, 3],          # opened on real people while testing
    'pb.hiring.cover': [26],            # the stand-in A3 proved cover with
    'project.task': [5711],             # the to-do list a new login is given
}

#: Never follow a pointer AT one of these to decide that a record is demo data.
#:
#: THE DIFFERENCE IS SUBJECT AND ACTOR. A contract that points at a demo
#: employee is about that demo person, so it is demo data. A journey that
#: points at a demo LOGIN is a journey somebody ran while testing — it can
#: belong to anybody, and `create_uid` points at a user on every record in the
#: database. Following those would put real people's records on a list whose
#: button deletes them.
NO_INWARD_FROM = {'res.users', 'res.partner'}

#: Models the crawl may add records to. Everything else is either
#: configuration the product ships, or somebody's real record.
#:
#: NOTE WHAT IS NOT HERE. `res.users`, `hr.employee`, `hr.department`,
#: `hr.job`, `res.partner` and `pb.vendor` are ROOTS ONLY: a demo interview
#: points at the recruiter who ran it and at the panel who sat on it, and
#: following those pointers would put real colleagues on a register whose
#: button deletes things. Membership of those models is decided by hand, above.
CRAWL_MODELS = {
    'hr.contract', 'hr.applicant', 'calendar.event', 'calendar.attendee',
    'biz.approval.request', 'biz.approval.request.step',
    'biz.approval.request.seat', 'biz.approval.decision',
    'biz.approval.event', 'biz.approval.step.log',
    'pb.hiring.requisition', 'pb.hiring.jd', 'pb.hiring.posting',
    'pb.hiring.referral', 'pb.hiring.step', 'pb.hiring.interview',
    'pb.hiring.feedback', 'pb.hiring.reschedule', 'pb.hiring.stage.log',
    'pb.hiring.offer', 'pb.hiring.offer.line', 'pb.hiring.bgv',
    'pb.hiring.bgv.item', 'pb.hiring.docreq', 'pb.hiring.docreq.item',
    'pb.hiring.cover',
    'pb.journey.case', 'pb.journey.task', 'pb.employee.checkin',
    'pb.feedback.request', 'pb.hr.letter',
    'pb.asset', 'pb.asset.assignment', 'pb.asset.request',
    'pb.buddy.nomination', 'pb.orientation.batch', 'pb.newhire.pulse',
    'pb.resignation', 'pb.exit.clearance', 'pb.kt.item',
    'hr.full.final.settlement',
    'pb.probation.review', 'pb.verdict.proposal', 'pb.training.item',
    'pb.training.status',
    'pb.pip.case', 'pb.pip.objective',
    'pb.employee.comp', 'pb.employee.comp.line', 'pb.incentive',
    'pb.benefit.enrollment', 'pb.month.proposal',
    'pb.rnr.nomination', 'pb.rnr.celebration', 'pb.rnr.celebration.log',
    'pb.rnr.cycle',
    'pb.budget.line', 'pb.budget.expense',
    'pb.contract.review', 'pb.contract.extension',
    'pb.vendor.agreement',
    'pb.employee.document',
}
# `pb.budget.actuals` is deliberately absent: those rows are DERIVED — the
# nightly job rebuilds them from the pay runs — so they are not demo data and
# removing them would only make the job do its work again.

#: Configuration and other people's records: never registered, however they
#: are reached. A demo that deletes the letter library on its way out is worse
#: than a demo nobody cleaned up.
NEVER = {
    'res.company', 'res.groups', 'hr.version', 'hr.payslip', 'hr.payslip.run',
    'hr.payslip.line', 'pb.letter.template', 'pb.hiring.doc.template',
    'pb.hiring.criterion', 'pb.journey.template', 'pb.journey.template.step',
    'pb.probation.policy', 'pb.notice.policy', 'pb.hrbp.rule',
    'pb.pip.template', 'pb.pip.template.line', 'pb.company.value',
    'pb.payroll.calendar', 'pb.benefit.plan', 'pb.budget.fx',
    'pb.asset.category', 'pb.training.track', 'pb.tenant', 'pb.alert',
    'res.country.state', 'hr.contract.type', 'pb.hiring.bgv.template',
    'pb.budget.actuals',
}

#: Registered LAST, so the removal reaches them at the very end: a person's
#: private contact is made as a side effect of the person, and Odoo refuses to
#: delete a contact while an employee still points at it.
LATE_MODELS = ('res.partner',)


def _live(env, model_name, ids):
    if model_name not in env:
        return env['pb.demo.seed'].browse()
    return env[model_name].sudo().with_context(
        active_test=False).browse(ids).exists()


def _department_is_safe(env, department):
    """Only a team whose every member is a demo person may be registered.

    A department that still holds somebody real must not be on a list whose
    button deletes it — the delete would either be refused or would quietly
    empty a real person's team. `hr.employee.department_id` lives on the
    version record on this build (R14), so it is read through the app.
    """
    members = env['hr.employee'].sudo().with_context(active_test=False).search(
        [('department_id', '=', department.id)])
    strangers = members.filtered(lambda e: e.id not in ROOTS['hr.employee'])
    return not strangers, strangers


def collect(env):
    """Everything the programme made, found by following what points at what."""
    print('\n=== PART 2 — register ===')
    collected = {}
    for model_name, ids in ROOTS.items():
        records = _live(env, model_name, ids)
        if model_name == 'hr.department':
            keep = env['hr.department']
            for department in records:
                safe, strangers = _department_is_safe(env, department)
                if safe:
                    keep |= department
                else:
                    print('  ! %s is NOT registered — %s employee(s) who are '
                          'not demo people are in it'
                          % (department.display_name, len(strangers)))
            records = keep
        if records:
            collected[model_name] = set(records.ids)
        missing = set(ids) - set(records.ids)
        if missing:
            print('  ! %s %s are not on this database'
                  % (model_name, sorted(missing)))

    # -- the closure ----------------------------------------------------
    #
    # Two directions, both needed. INWARDS: everything of a demo kind that
    # points at something already collected — a requisition's steps, an
    # interview's opinions, an offer's lines. OUTWARDS: the records a
    # collected one points at, where those are of a demo kind too — the diary
    # entry an interview booked, the letter an offer produced. Repeat until
    # nothing new appears; on this database that is four or five passes.
    for pass_no in range(1, 9):
        added = 0
        for model_name in sorted(CRAWL_MODELS):
            if model_name not in env or model_name in NEVER:
                continue
            model = env[model_name]
            if model._abstract or model._transient:
                continue
            model = model.sudo().with_context(active_test=False)
            clauses = []
            for field_name, field in model._fields.items():
                if field.type != 'many2one' or not field.store:
                    continue
                target = field.comodel_name
                if (target not in collected or target in NEVER
                        or target in NO_INWARD_FROM):
                    continue
                clauses.append((field_name, 'in', sorted(collected[target])))
            if clauses:
                # Prefix notation: n clauses need n-1 leading ORs.
                domain = ['|'] * (len(clauses) - 1) + clauses
                found = set(model.search(domain).ids)
                new = found - collected.get(model_name, set())
                if new:
                    collected.setdefault(model_name, set()).update(new)
                    added += len(new)
            # outwards, into demo kinds only
            for field_name, field in model._fields.items():
                if field.type != 'many2one' or not field.store:
                    continue
                target = field.comodel_name
                if (target not in CRAWL_MODELS or target in NEVER
                        or target not in env):
                    continue
                here = collected.get(model_name)
                if not here:
                    continue
                values = model.browse(sorted(here)).exists().mapped(field_name)
                new = set(values.ids) - collected.get(target, set())
                if new:
                    collected.setdefault(target, set()).update(new)
                    added += len(new)
        # the approval trail is joined by (model, id), not by a pointer
        added += _approvals(env, collected)
        print('  pass %s: %s more record(s)' % (pass_no, added))
        if not added:
            break

    # the private contact behind each demo person
    contacts = set()
    for employee in _live(env, 'hr.employee', sorted(
            collected.get('hr.employee', ()))):
        for field_name in ('work_contact_id', 'address_home_id'):
            if field_name in employee._fields and employee[field_name]:
                contacts.add(employee[field_name].id)
    for user in _live(env, 'res.users', sorted(collected.get('res.users', ()))):
        if user.partner_id:
            contacts.add(user.partner_id.id)
    collected.setdefault('res.partner', set()).update(contacts)

    for model_name in list(collected):
        if model_name in NEVER:
            print('  ! %s reached the list and was dropped (never registered)'
                  % model_name)
            collected.pop(model_name)
    return collected


#: Joined to the record they are about by (model, id) rather than by a
#: pointer, so the ordinary crawl cannot see them.
BY_MODEL_AND_ID = ('biz.approval.request', 'biz.approval.step.log')


def _approvals(env, collected):
    """What is filed AGAINST a record rather than pointing at it."""
    added = 0
    pairs = [(m, sorted(ids)) for m, ids in collected.items()
             if not m.startswith('biz.approval')]
    if not pairs:
        return 0
    # Prefix notation again: each pair is an AND of two terms, and the pairs
    # are ORed together.
    domain = ['|'] * (len(pairs) - 1)
    for model_name, ids in pairs:
        domain += ['&', ('res_model', '=', model_name), ('res_id', 'in', ids)]
    for model_name in BY_MODEL_AND_ID:
        model = env.get(model_name)
        if model is None:
            continue
        found = set(model.sudo().with_context(active_test=False)
                    .search(domain).ids)
        new = found - collected.get(model_name, set())
        if new:
            collected.setdefault(model_name, set()).update(new)
            added += len(new)
    return added


def point_the_shipped_panel_at_the_real_company(env):
    """The empty "Demo data" panel belongs to the company people work in.

    A module installs as whoever ran the install, and `company_id` defaults to
    theirs — which here was company 1, the empty shell the first install left
    (R16). Nobody works there, so pressing Load on that panel would build five
    demo people into a company with nothing else in it and the screens would
    show an empty demo. Only ever moved while the panel is EMPTY: once a world
    is loaded the company is where its people live and must not change.
    """
    seed = env['pb.demo.seed'].sudo()
    company = seed._programme_company()
    panel = env.ref('pb_demo_seed.demo_seed_default', raise_if_not_found=False)
    if not panel or panel.state != 'empty' or panel.company_id == company:
        return
    print('  the empty "%s" panel moves from %s to %s'
          % (panel.name, panel.company_id.display_name, company.display_name))
    if not DRY:
        panel.sudo().company_id = company


def register(env, collected):
    """Write them onto the programme panel, oldest first."""
    point_the_shipped_panel_at_the_real_company(env)
    seed = env['pb.demo.seed'].sudo().programme_seed()
    print('  panel: %s (company %s), %s row(s) already on it'
          % (seed.name, seed.company_id.display_name, seed.record_count))

    # OLDEST FIRST, because creation order is dependency order and the
    # removal walks the register backwards. A record with no creation stamp
    # (a handful of models keep none) is treated as having been made when the
    # panel was, which puts it first — the safest end to be at.
    ordered, late = [], []
    for model_name, ids in collected.items():
        for record in _live(env, model_name, sorted(ids)):
            when = getattr(record, 'create_date', False) or seed.create_date
            (late if model_name in LATE_MODELS else ordered).append(
                (when, record.id, model_name, record))
    ordered.sort(key=lambda row: (row[0], row[1]))
    late.sort(key=lambda row: (row[0], row[1]))

    counts, added = {}, 0
    for rows, at_the_end in ((ordered, False), (late, True)):
        batch, batch_model = None, None
        for _when, _res_id, model_name, record in rows + [(None, 0, None, None)]:
            counts[model_name] = counts.get(model_name, 0) + 1
            if model_name == batch_model:
                batch |= record
                continue
            # A RUN OF ONE KIND AT A TIME. Registering record by record would
            # be right and slow; registering all of one kind together would
            # lose the order. Consecutive records of the same kind are one
            # call, which keeps both.
            if batch is not None and not DRY:
                added += seed.register(batch, last=at_the_end)
            batch, batch_model = record, model_name
    counts.pop(None, None)

    # THE LIST ITSELF, not only its shape. `PB_SWEEP_DUMP=/tmp/x.txt` writes
    # every id out, because "981 records" is a number somebody has to take on
    # trust and a list is something they can check.
    dump = os.environ.get('PB_SWEEP_DUMP')
    if dump:
        with open(dump, 'w', encoding='utf-8') as handle:
            for model_name in sorted(collected):
                handle.write('%s: %s\n' % (
                    model_name, sorted(collected[model_name])))
        print('  every id written to %s' % dump)

    total = sum(counts.values())
    print('\n  kind                                    found   ')
    for model_name, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print('  %-40s %5s' % (model_name, count))
    print('  %-40s %5s' % ('TOTAL', total))
    print('  %s row(s) newly added to the register' % added)
    if not DRY:
        # The panel says what it holds in the words the screens use, not in
        # model names — `summarise_register()` is the same sentence the door
        # writes for any other module that registers something.
        seed.sudo().write({'summary': seed.summarise_register()})
        env.cr.commit()
        preview = seed.preview_remove()
        print('  "What would be removed" now answers: %s record(s), '
              '%s login(s) switched off, %s already gone'
              % (preview['total'], len(preview['users']), preview['gone']))
    return counts


# =====================================================================
#  Part 3 — prove
# =====================================================================
def prove(env):
    print('\n=== PART 3 — prove ===')
    left = scan(env)
    if not left:
        print('  nothing anywhere spells the name.')
        return left
    print('  what is left, and why it is allowed to stay:')
    for table, column, _kind, count in left:
        reason = SURVIVORS.get(table)
        print('  %-44s %5s  %s'
              % ('%s.%s' % (table, column), count,
                 reason or '*** NOT ALLOWED — look at this ***'))
    return left


# =====================================================================
if 'env' in dir():                                 # inside an Odoo shell
    print('DEMO sweep on %s%s'
          % (env.cr.dbname, ' (DRY RUN — nothing is written)' if DRY else ''))
    if env.cr.dbname != 'payobook' and not os.environ.get('PB_SWEEP_ANY_DB'):
        raise SystemExit(
            'This sweep is written for the payobook database. Set '
            'PB_SWEEP_ANY_DB=1 if another one really is meant.')
    if ONLY in ('', '1'):
        rename(env)
    if ONLY in ('', '2'):
        register(env, collect(env))
    if ONLY in ('', '3'):
        prove(env)
    print('\nDone%s.' % (' (dry run)' if DRY else ''))
