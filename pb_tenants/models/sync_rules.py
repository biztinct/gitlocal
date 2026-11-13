# -*- coding: utf-8 -*-
"""The decisions behind "in step with master", lifted out so a test can reach them.

WHY THIS FILE EXISTS AT ALL (rail R6, and the precedent is `currency_change`).
Everything the sync feature actually DOES happens against another database on
the cluster — a registry opened by hand, a module installed, a version read back.
None of that is reachable from a test suite, and a test that mocked it would only
assert that the mock was called. So every judgement the feature makes is a pure
function in this file, and the call sites in `service.py` are left holding two
reads and a write.

THE ONE THAT MATTERS MOST IS `norm_version` (ledger F1). Before it, the split was
computed on module NAMES only: a customer sitting two versions behind on a part
of the product it already had was reported as "in step", in green, on a screen
whose whole job is to say otherwise. `abm` sat like that for a fortnight.
"""
from datetime import date

#: Never installed on a customer's database, and the plain-English reason why.
#: The reason is shown ON SCREEN beside the module, so it is written for the
#: owner rather than for an engineer.
#:
# =============================================================================
# KEEPING A CUSTOMER'S DATABASE IN STEP WITH THE MASTER (ACCESS P8).
#
# THE OWNER'S RULE, IN HIS OWN WORDS (2026-09-02), AND IT IS THE WHOLE SPEC:
#
#   "From now on all tenant databases should get installed once master gets it,
#    except anything related to the platform cockpit or anything which can
#    interfere or be misused against the master tenant / platform functions."
#
# So the DEFAULT ANSWER IS YES. A part of the product that the master database
# has is a part every customer should have, and the list below is the short,
# argued set of exceptions — not a shortlist of what is allowed. Anything new
# ships to everybody unless somebody writes down here why it must not.
#
# WHY THE LIST LIVES IN THIS MODULE. `pb_tenants` is the platform cockpit, and
# it is the one module a customer's database is never allowed to have. A list of
# "what a customer must never be given" that shipped INSIDE a customer's
# database would be a map of the platform's soft spots, sitting in the hands of
# the people it is there to keep out.
#
# WHAT THIS IS NOT. It is not an automatic installer. Nothing here runs on an
# upgrade, on a cron, or on a master deploy: a customer's database must not gain
# a part of the product because somebody upgraded something else. The report
# says what is behind; a person presses the button. That sentence is on the
# screen too, in those words, so nobody has to read this comment to know it.
# =============================================================================
TENANT_SYNC_NEVER = {
    'pb_tenants':
        "The platform cockpit itself. It creates, backs up, restores and "
        "deletes every database on the fleet — including the master. Inside a "
        "customer's database it would be the controls to everybody else's.",
    'pb_demo':
        "Made-up employees, contracts and pay runs, used to demonstrate the "
        "product. It has no place in a real company's payroll, where it would "
        "be indistinguishable from staff who exist.",
    'pb_demo_portal':
        "The self-serve demo sign-up and its guided tour. It hands out logins "
        "to a demonstration world — not something a customer's database should "
        "be able to do.",
    'pb_website':
        "The public marketing site that sits at the front door of the product. "
        "A customer's database is not the product's shop window, and serving "
        "one from it would put our pages on their address.",
}

#: A module is also held back when its name starts with one of these. Nothing
#: uses it today; it is here so a future platform module is refused BY DEFAULT
#: rather than shipped to every customer the day it is written.
TENANT_SYNC_NEVER_PREFIXES = ('pb_platform',)

#: How many dotted parts a version string has once the framework has stamped its
#: series on the front. `19.0.1.7.0` is the series `19.0` plus our own `1.7.0`.
_SERIES_PARTS = 5


def is_never(name):
    """Is this part of the product one a customer's database never gets?"""
    return bool(name) and (name in TENANT_SYNC_NEVER
                           or name.startswith(TENANT_SYNC_NEVER_PREFIXES))


def sync_never_reason(name):
    """The plain-English reason a module is never put on a customer's database."""
    if name in TENANT_SYNC_NEVER:
        return TENANT_SYNC_NEVER[name]
    return ("Reserved for the platform. Parts of the product that run the "
            "fleet are never installed on a customer's database.")


def norm_version(v):
    """A version string as an int-tuple that can be compared across databases.

    THE TRAP THIS EXISTS FOR (ledger F1). The version a database records for a
    module carries the framework series on the front — `19.0.1.7.0` — while the
    version written in the module's own file is `1.7.0`. Comparing the two as
    strings says they differ; comparing them as text says `1.10.0` is older than
    `1.9.0`. Both answers are wrong and both are silent.

    The series is stripped only when the string has five or more parts, so a
    plain `1.7.0` is never mistaken for a series-prefixed one. Anything that is
    not a whole number counts as 0, which makes `19.0.1.7.0-rc1` an answer
    rather than a crash.
    """
    if not v:
        return (0,)
    parts = str(v).strip().split('.')
    if len(parts) >= _SERIES_PARTS:
        parts = parts[2:]
    out = []
    for p in parts:
        p = p.strip()
        out.append(int(p) if p.isdigit() else 0)
    return tuple(out) or (0,)


def _versions(mapping):
    """Accept either {name: version} or a bare list of names."""
    if mapping is None:
        return {}
    if isinstance(mapping, dict):
        return dict(mapping)
    return {n: '' for n in mapping}


def sync_diff(master_modules, tenant_modules):
    """What one customer's database is missing OR behind on, split four ways.

    `master_modules` and `tenant_modules` are `{module name: version}` (a bare
    list of names is accepted too, and then only the missing/present question
    can be answered).

    Returns a dict:
      * `to_install` — sorted names the master has and this database has not.
      * `to_update`  — `[{'module', 'have', 'want'}]`, sorted by name: present
        on both, older here.
      * `held_back`  — sorted names, on either side, that a customer's database
        never gets. Read off BOTH lists on purpose: a database that somehow
        already holds one must not be quietly upgraded either.
      * `ahead`      — `[{'module', 'have', 'want'}]` the customer has NEWER
        than the master. Reported so nobody is surprised by it, and never
        touched: taking a part of the product back is not a sync.
    """
    master = _versions(master_modules)
    tenant = _versions(tenant_modules)
    held, to_install, to_update, ahead = [], [], [], []
    for name in set(master) | set(tenant):
        if is_never(name):
            held.append(name)
            continue
        if name not in master:
            continue                     # theirs alone — never our business
        if name not in tenant:
            to_install.append(name)
            continue
        have, want = norm_version(tenant[name]), norm_version(master[name])
        if want > have:
            to_update.append({'module': name, 'have': tenant[name] or '',
                              'want': master[name] or ''})
        elif have > want:
            ahead.append({'module': name, 'have': tenant[name] or '',
                          'want': master[name] or ''})
    return {
        'to_install': sorted(to_install),
        'to_update': sorted(to_update, key=lambda r: r['module']),
        'held_back': sorted(held),
        'ahead': sorted(ahead, key=lambda r: r['module']),
    }


def sync_split(master_modules, tenant_modules):
    """What is behind on one customer's database, split in two. NAMES ONLY.

    The original shape of this decision, kept because it is what the older
    callers and their tests ask for. It answers "what is MISSING", which is why
    a customer two versions behind on something it already had came out green —
    see `norm_version`. New code asks `sync_diff`.

    Returns `(to_install, held_back)`, both sorted lists of module names.
    """
    master = set(_versions(master_modules))
    tenant = set(_versions(tenant_modules))
    diff = sync_diff({n: '' for n in master}, {n: '' for n in tenant})
    held = [n for n in diff['held_back'] if n in master and n not in tenant]
    return diff['to_install'], sorted(held)


def release_state(snapshot, tenant_modules, never=None):
    """Is this database on the release, behind it, or nowhere near it?

      * `on`     — it has every part of the release, at that version or newer.
      * `behind` — it has most of them, but something is missing or older.
      * `none`   — it holds less than half of the release. A database nobody
                   has ever brought in step, or one that is not ours at all;
                   calling that "behind" would put it one button-press away
                   from an install nobody has thought about.

    Parts a customer never gets are ignored on both sides — a release contains
    the whole master, including the platform's own, so that the person reading
    it sees what the master runs rather than an edited version of it.
    """
    never = never if never is not None else set()
    snap = {n: v for n, v in _versions(snapshot).items()
            if not is_never(n) and n not in never}
    have = _versions(tenant_modules)
    if not snap:
        return 'none'
    present = [n for n in snap if n in have]
    if len(present) * 2 < len(snap):
        return 'none'
    for name, want in snap.items():
        if name not in have or norm_version(have[name]) < norm_version(want):
            return 'behind'
    return 'on'


def master_behind_files(rows):
    """The master's own parts whose files on the server are newer than itself.

    RAIL R3 LIVES OR DIES HERE. Python and template code reach every database
    the moment the server restarts, because they share one directory of files;
    only data, screens and table changes wait to be applied per database
    (ledger F2). So a master whose files have moved on but which has not applied
    them yet is a master running a mixture — and cutting a release from it, or
    measuring a customer against it, would ship that mixture to the fleet.

    `rows` is `[(name, version_this_database_has, version_in_the_file)]`.
    Returns the sorted names where the file is newer. Empty is the good answer.
    """
    out = []
    for name, in_db, on_disk in rows or ():
        if not on_disk:
            continue
        if norm_version(on_disk) > norm_version(in_db):
            out.append(name)
    return sorted(out)


def release_name(today=None, existing=None):
    """The name of a release cut today: `2026.09.03`, then `-2`, `-3`, …

    Dated rather than numbered because the only question anybody asks of a
    release name is "how old is this?".
    """
    today = today or date.today()
    base = '%04d.%02d.%02d' % (today.year, today.month, today.day)
    taken = set(existing or ())
    if base not in taken:
        return base
    n = 2
    while '%s-%d' % (base, n) in taken:
        n += 1
    return '%s-%d' % (base, n)


def template_cron_plan(active_ids, recorded):
    """Which of the golden template's scheduled jobs to switch off, and what to
    write down so a new customer gets them back (rail R8).

    THE TEMPLATE IS NOT A DATABASE THAT RUNS. It sits cold on a box with 1.9 GB
    of memory, and a scheduled job is exactly the thing that would wake it up
    and keep a whole registry resident for nothing. So everything is switched
    off there, and the list of what WAS on is written down; provisioning turns
    that list back on inside the clone and clears it.

    Installing a part of the product on the template creates its jobs switched
    ON, so this runs after every template install.

    `recorded` is the comma-separated list already written down. Returns
    `(to_disable, new_param)`. Everything active is switched off — an already
    recorded job that is running again still has to go off — while the written
    list only gains what it does not already hold, in the order it was found.
    """
    recorded_ids, seen = [], set()
    for chunk in (recorded or '').split(','):
        chunk = chunk.strip()
        if chunk.isdigit() and int(chunk) not in seen:
            recorded_ids.append(int(chunk))
            seen.add(int(chunk))
    to_disable, appended = [], []
    for raw in active_ids or ():
        i = int(raw)
        if i not in to_disable:
            to_disable.append(i)
        if i not in seen:
            seen.add(i)
            appended.append(i)
    new_param = ','.join(str(i) for i in recorded_ids + appended)
    return to_disable, new_param
