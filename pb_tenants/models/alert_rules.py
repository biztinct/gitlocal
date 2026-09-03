# -*- coding: utf-8 -*-
"""FLEET P3 — what counts as a problem, and how the platform says so.

Same shape as `sync_rules.py` and `rollout_rules.py`, and for the same reason
(rail R6): everything this feature DOES happens somewhere a test cannot go — a
customer's database, the mail server, a file nginx serves. So every JUDGEMENT
lives here, pure, with no import of the framework at all, and what is left at
the call site is a read, a write and a send.

THE FOUR JUDGEMENTS.
  * `readings_to_alerts` — a plain dict of measurements in, a list of problems
    out. Nothing else in the platform decides what is wrong.
  * `reconcile` — what is new, what is still going on, what is over.
  * `should_notify` — has this one earned an email yet.
  * `digest_lines` / `render_status_page` — the words.

EVERY ALERT CARRIES ITS NEXT STEP. Not "disk usage 87%" — "the disk is 87% full;
old backups are the usual cause, prune them under the customer's Backups tab".
An alert that tells somebody a number and leaves them to work out the rest is an
alert they learn to ignore.

AND NOTHING HERE NAMES A CUSTOMER ON THE PUBLIC PAGE. `status_state()` is the
one door between "what we know" and "what the world reads", and it copies only
kinds, levels and durations across it. That is asserted by a test which feeds it
a state full of names.
"""
import html
from datetime import datetime, timedelta

# =============================================================================
# Kinds, severities, thresholds
# =============================================================================

#: Every kind of problem the platform knows how to notice. The order is the
#: order they are looked for, which is also the order they read in a digest.
ALERT_KINDS = (
    'tenant_down',          # a customer's site did not answer
    'backup_failed',        # last backup attempt failed
    'backup_stale',         # no successful backup for too long
    'mail_failing',         # outgoing mail is bouncing or unconfigured
    'alert_channel_down',   # the email channel itself is broken
    'disk_low',
    'memory_high',
    'cert_expiring',
    'tenant_errors',        # a customer's database logged errors
    'rollout_paused',
    'drift',
    'master_behind_files',
    'template_hot_cron',
    'status_page_unwritable',
    # FLEET P5. Money and standing. None of these can be seen by a reading —
    # they come out of our own invoice table on the morning job — so all three
    # are self-managed below.
    'invoice_overdue',
    'suspend_candidate',
    'trial_ending',
    # FLEET P6. Somebody at Payobook opened a customer's data. It is INFO and
    # it is not a fault — it is here because access to a customer's payroll is
    # never allowed to be quiet, and this is what puts it in the daily summary
    # the owner already reads. Self-managed below: no reading can see it.
    'support_session',
)

SEVERITIES = ('critical', 'warning', 'info')
SEVERITY_ORDER = {'info': 0, 'warning': 1, 'critical': 2}

#: Kinds that are NEVER resolved by the sweep, because no reading can see them.
#: `alert_channel_down` is raised by the sender when a send fails and cleared by
#: the sender when one succeeds — the one alert that cannot email itself, and
#: therefore the one that has to be visible on screen instead.
#:
#: FLEET P5 adds three more for the same reason turned the other way round:
#: the sweep takes no reading that could ever see an unpaid invoice or a trial
#: running out, so if it were allowed to reconcile them it would close every
#: one of them fifteen minutes after the morning job raised it. They are
#: raised and cleared by `billing_service.py` — when the invoice is paid, when
#: the customer is resumed, when the trial is converted.
SELF_MANAGED_KINDS = ('alert_channel_down', 'invoice_overdue',
                      'suspend_candidate', 'trial_ending', 'support_session')

#: Every number this file judges by, in one dict, all overridable as settings.
#: They are ARGUMENTS and not constants so a test can sit exactly on the edge of
#: each one, and so the owner can move one without a deploy.
DEFAULT_THRESHOLDS = {
    # Disk: a payroll box with no room cannot write a backup or a pay run.
    'disk_free_pct': 15,
    'disk_free_gb': 5.0,
    'disk_critical_pct': 5,
    # Memory: MemAvailable, and the share of the machine this process holds.
    'mem_available_mb': 250,
    'mem_critical_mb': 120,
    'mem_rss_pct': 70,
    # Backups: nightly runs at 19:30, so 30 h means one was genuinely missed.
    'backup_stale_hours': 30,
    # Certificates. The wildcard does not auto-renew, hence the longer notice.
    'cert_wildcard_days': 21,
    'cert_tenant_days': 14,
    'cert_critical_days': 5,
    # Error lines in the server log for one database, in the last window.
    'error_lines': 3,
    # How far past a release a customer may sit before it is worth saying.
    'drift_days': 7,
    # Failed outgoing mails inside the mail window before the channel is called
    # broken.
    'mail_fail_count': 3,
    # How old the public status page may get before it is a problem.
    'status_page_minutes': 15,
}

#: The four things the public page reports on, in the order they are read.
COMPONENTS = (
    'Sign-in & web app',
    'Payroll processing',
    'Email delivery',
    'Customer sites',
)

#: ok < maintenance < degraded < down. Planned work ranks BELOW a fault on
#: purpose: a page that shouts the same colour for "we told you about this"
#: and "something broke" teaches its readers nothing.
LEVEL_ORDER = {'ok': 0, 'maintenance': 1, 'degraded': 2, 'down': 3}

_INDIGO = '#5A4BB0'


def _th(thresholds=None):
    """The thresholds, with anything not given falling back to the default."""
    out = dict(DEFAULT_THRESHOLDS)
    for key, val in (thresholds or {}).items():
        if key in out and val not in (None, ''):
            out[key] = val
    return out


def _alert(key, kind, severity, title, text, tenant_id=None):
    return {'key': key, 'kind': kind, 'severity': severity,
            'title': title, 'text': text, 'tenant_id': tenant_id}


def _hours_since(then, now):
    if not then or not now:
        return None
    return (now - then).total_seconds() / 3600.0


# =============================================================================
# READINGS -> ALERTS
# =============================================================================

def readings_to_alerts(readings, thresholds=None):
    """Every problem the platform can currently see, in one list.

    `readings` is a plain dict — see `pb.tenants._gather_readings()` for the
    shape. Missing keys mean "not measured" and are skipped rather than guessed
    at: a reading nobody took must never raise an alarm, and must never silence
    one either.
    """
    t = _th(thresholds)
    now = (readings or {}).get('now') or datetime.utcnow()
    out = []
    for row in (readings or {}).get('tenants') or ():
        out.extend(_tenant_alerts(row, t, now))
    out.extend(_platform_alerts(readings or {}, t, now))
    order = {k: i for i, k in enumerate(ALERT_KINDS)}
    out.sort(key=lambda a: (order.get(a['kind'], 99), a['key']))
    return out


def _tenant_alerts(row, t, now):
    """One customer's problems. `row` is a reading, not a record."""
    out = []
    if (row.get('state') or '') != 'live':
        return out
    name = row.get('name') or row.get('slug') or 'a customer'
    slug = row.get('slug') or str(row.get('id') or '')
    tid = row.get('id')

    # --- is their site answering at all
    if row.get('health') == 'down':
        out.append(_alert(
            'tenant_down:%s' % slug, 'tenant_down', 'critical',
            "%s cannot be reached" % name,
            "Their site did not answer when we asked it for a page. Nobody at "
            "%s can sign in right now. Next: open them in Mission Control and "
            "press Refresh health; if it is still down, check the server is "
            "running and then restore last night's backup." % name, tid))

    # --- backups. A payroll customer without one is the worst state to be in.
    if row.get('last_backup_failed'):
        out.append(_alert(
            'backup_failed:%s' % slug, 'backup_failed', 'critical',
            "The backup of %s failed" % name,
            "The last attempt to back %s up did not finish — the reason is on "
            "their Backups tab. Next: open them in Mission Control and press "
            "Back up now; if it fails again, check free disk space." % name,
            tid))
    else:
        age = _hours_since(row.get('last_backup_at'), now)
        if age is None or age > t['backup_stale_hours']:
            when = ("never been backed up" if age is None
                    else "not been backed up for %d hours" % int(age))
            out.append(_alert(
                'backup_stale:%s' % slug, 'backup_stale', 'critical',
                "%s has no recent backup" % name,
                "%s has %s. The nightly backup runs at 19:30. Next: open them "
                "in Mission Control and press Back up now, then check the "
                "nightly job ran." % (name, when), tid))

    # --- their certificate
    days = row.get('cert_days_left')
    if isinstance(days, int) and 0 <= days < t['cert_tenant_days']:
        sev = 'critical' if days < t['cert_critical_days'] else 'warning'
        out.append(_alert(
            'cert_expiring:%s' % slug, 'cert_expiring', sev,
            "%s's certificate expires in %d days" % (name, days),
            "After that their browser will warn every user away from the site. "
            "It normally renews itself. Next: nothing to do yet — the platform "
            "retries every night at 03:15; if it is still counting down "
            "tomorrow, reissue it from the deploy runbook.", tid))

    # --- their database complaining in the log
    lines = row.get('error_lines') or 0
    if lines >= t['error_lines']:
        out.append(_alert(
            'tenant_errors:%s' % slug, 'tenant_errors', 'warning',
            "%s is logging errors" % name,
            "%d errors came from %s in the last quarter of an hour. That is "
            "usually one screen or one scheduled job failing, not the whole "
            "system. Next: open them in Mission Control, look at the Updates "
            "tab for anything that changed recently." % (lines, name), tid))

    # --- how far behind the release they are
    behind_days = row.get('release_age_days')
    if (row.get('release_state') == 'behind' and isinstance(behind_days, int)
            and behind_days > t['drift_days']):
        out.append(_alert(
            'drift:%s' % slug, 'drift', 'warning',
            "%s is %d days behind the release" % (name, behind_days),
            "They are missing %d part(s) of the product and %d are at an older "
            "version. Next: open 'In step with master' and either roll the "
            "release out or bring this customer in step on their own."
            % (row.get('behind_count') or 0, row.get('stale_count') or 0), tid))
    return out


def _platform_alerts(r, t, now):
    """Everything that is about the machine rather than about a customer."""
    out = []

    # --- the wildcard certificate, which does NOT renew itself
    wdays = r.get('wildcard_cert_days')
    if isinstance(wdays, int) and 0 <= wdays < t['cert_wildcard_days']:
        sev = 'critical' if wdays < t['cert_critical_days'] else 'warning'
        out.append(_alert(
            'cert_expiring:wildcard', 'cert_expiring', sev,
            "The wildcard certificate expires in %d days" % wdays,
            "This one does NOT renew itself, and when it lapses every customer "
            "subdomain without its own certificate stops being trusted. Next: "
            "reissue it with the DNS-01 step in docs/SAAS_RUNBOOK.md — it needs "
            "one temporary record at the registrar."))

    # --- disk
    disk = r.get('disk') or {}
    free_pct = disk.get('free_pct')
    free_gb = disk.get('free_gb')
    if free_pct is not None and (free_pct < t['disk_free_pct']
                                 or (free_gb is not None and free_gb < t['disk_free_gb'])):
        sev = 'critical' if free_pct < t['disk_critical_pct'] else 'warning'
        out.append(_alert(
            'disk_low', 'disk_low', sev,
            "The server is running out of disk",
            "%s%% free (%s GB). Backups and pay runs both write to this disk, "
            "and a full disk stops both. Next: the usual cause is kept "
            "backups — open a customer's Backups tab and remove old ones, or "
            "move them off the box."
            % (free_pct, ('%.1f' % free_gb) if free_gb is not None else '?')))

    # --- memory
    mem = r.get('memory') or {}
    avail = mem.get('available_mb')
    total = mem.get('total_mb') or 0
    rss = mem.get('rss_mb') or 0
    rss_pct = (rss * 100.0 / total) if total else 0
    if avail is not None and (avail < t['mem_available_mb'] or rss_pct > t['mem_rss_pct']):
        sev = ('critical' if (avail < t['mem_critical_mb']) else 'warning')
        out.append(_alert(
            'memory_high', 'memory_high', sev,
            "The server is low on memory",
            "%d MB free of %d MB, and the application itself is holding %d MB. "
            "When this runs out the whole platform restarts and everybody is "
            "signed out. Next: this machine is at its size — see "
            "docs/SAAS_RESIZE_RUNBOOK.md for the one-page resize."
            % (avail, total, rss)))

    # --- outgoing mail
    mail = r.get('mail') or {}
    if mail:
        missing = []
        if not mail.get('default_from'):
            missing.append("no default sender address is set")
        fails = mail.get('failed_recent') or 0
        if fails >= t['mail_fail_count']:
            missing.append("%d messages failed to go out recently" % fails)
        if missing:
            out.append(_alert(
                'mail_failing', 'mail_failing', 'critical',
                "Outgoing email is not working",
                "%s. Every message this platform sends — including these "
                "alerts — depends on it. Next: open Alert settings in Mission "
                "Control, check the sender address, and press Send a test "
                "email." % (' and '.join(missing).capitalize())))

    # --- a rollout that stopped
    roll = r.get('rollout') or {}
    if roll.get('state') == 'paused':
        out.append(_alert(
            'rollout_paused', 'rollout_paused', 'warning',
            "Release %s stopped part-way" % (roll.get('release') or ''),
            "%s Customers after the one it stopped on are still on the old "
            "release. Next: open 'In step with master', read the reason on the "
            "wave that stopped, then either put it right and press Resume or "
            "call the rollout off."
            % (roll.get('reason') or 'It stopped and is waiting for a person.')))

    # --- the master running a mixture of old data and new files
    behind = r.get('master_behind_files') or []
    if behind:
        out.append(_alert(
            'master_behind_files', 'master_behind_files', 'warning',
            "This platform has not applied its own update",
            "%d part(s) of the product have newer files on the server than this "
            "database has applied (%s). Nothing may go out to a customer until "
            "that is done. Next: run the update on this database from the "
            "deploy runbook." % (len(behind), ', '.join(behind[:5]))))

    # --- a template with live scheduled jobs is a template with a hot registry
    hot = r.get('template_hot_crons') or 0
    if hot:
        out.append(_alert(
            'template_hot_cron', 'template_hot_cron', 'warning',
            "The blank customer template has %d live scheduled job(s)" % hot,
            "The template is the copy every new customer is made from; jobs "
            "running inside it hold memory and can change it. Next: open 'In "
            "step with master' and press Bring in step on the template — it "
            "switches them back off at the end."))

    # --- the public page
    sp = r.get('status_page') or {}
    if sp and not sp.get('writable', True):
        out.append(_alert(
            'status_page_unwritable', 'status_page_unwritable', 'warning',
            "The public status page cannot be written",
            "%s Customers checking payobook.com/status are reading an old page "
            "or none at all. Next: on the server, create /var/www/pb-status and "
            "let the application write to it." % (sp.get('reason') or '')))
    return out


# =============================================================================
# RECONCILING WHAT WE ALREADY KNEW
# =============================================================================

def reconcile(open_alerts, fresh, now):
    """What is new, what is still true, and what is over.

    Returns `(to_create, to_bump, to_resolve)`:
      * `to_create` — alert dicts that nothing open matches, with their first
        and last sighting stamped;
      * `to_bump` — `(id, values)` for one that is still going on: its count
        goes up and its wording is refreshed, because the numbers inside it
        (days left, error count) move while the problem stays the same;
      * `to_resolve` — ids of alerts nothing measured any more.

    ONE ROW PER PROBLEM, EVER. The key is the identity: `backup_failed:abm` is
    the same problem tonight as it was this morning, and mailing about it twice
    an hour is how an owner learns to filter the sender.
    """
    fresh_by_key = {}
    for f in fresh or ():
        fresh_by_key.setdefault(f['key'], f)
    open_by_key = {}
    for a in open_alerts or ():
        if (a.get('state') or 'open') in ('open', 'acknowledged'):
            open_by_key.setdefault(a['key'], a)

    to_create, to_bump, to_resolve = [], [], []
    for key in sorted(fresh_by_key):
        f = fresh_by_key[key]
        known = open_by_key.get(key)
        if not known:
            row = dict(f)
            row.update({'first_seen': now, 'last_seen': now, 'count': 1,
                        'state': 'open'})
            to_create.append(row)
            continue
        to_bump.append((known['id'], {
            'last_seen': now,
            'count': int(known.get('count') or 0) + 1,
            'severity': f['severity'],
            'title': f['title'],
            'text': f['text'],
        }))
    for key in sorted(open_by_key):
        a = open_by_key[key]
        if key in fresh_by_key:
            continue
        if a.get('kind') in SELF_MANAGED_KINDS:
            continue
        to_resolve.append(a['id'])
    return to_create, to_bump, to_resolve


def should_notify(alert, now, interval_critical=2, interval_warning=6):
    """Has this alert earned an email right now?

    The rules, in order, and each one is there for a reason somebody lived:
      * an acknowledged alert never mails again — acknowledging IS "I know";
      * a resolved one never mails as a reminder (its own "it is over" note is
        sent by the caller, once);
      * one that has never been mailed always mails;
      * one that got WORSE since it was mailed mails again immediately, whatever
        the interval says — "the thing I told you about is now critical" is new
        information;
      * otherwise it waits out its interval, in hours, by severity.

    An interval of 0 or less means "never remind", which is a setting somebody
    will want the week they are already looking at a known problem.
    """
    if not alert:
        return False
    if (alert.get('state') or 'open') != 'open':
        return False
    last = alert.get('notified_at')
    if not last:
        return True
    sev = alert.get('severity') or 'warning'
    was = alert.get('notified_severity') or sev
    if SEVERITY_ORDER.get(sev, 1) > SEVERITY_ORDER.get(was, 1):
        return True
    hours = interval_critical if sev == 'critical' else interval_warning
    try:
        hours = float(hours)
    except (TypeError, ValueError):
        hours = 6.0
    if hours <= 0:
        return False
    return (now - last) >= timedelta(hours=hours)


def digest_lines(open_alerts, now=None):
    """The morning summary, one line each, worst first.

    Empty list when nothing is open — the caller writes the reassuring sentence,
    because only the caller knows how many customers there are to reassure about.
    """
    now = now or datetime.utcnow()
    rows = [a for a in (open_alerts or ())
            if (a.get('state') or 'open') in ('open', 'acknowledged')]
    rows.sort(key=lambda a: (-SEVERITY_ORDER.get(a.get('severity'), 1),
                             a.get('first_seen') or now, a.get('key') or ''))
    out = []
    for a in rows:
        word = {'critical': 'Needs attention now',
                'warning': 'Worth a look',
                'info': 'For information'}.get(a.get('severity'), 'Worth a look')
        since = a.get('first_seen')
        age = _hours_since(since, now)
        if age is None:
            when = ''
        elif age < 1:
            when = ' — started less than an hour ago'
        elif age < 48:
            when = ' — going on for %d hours' % int(age)
        else:
            when = ' — going on for %d days' % int(age / 24)
        seen = a.get('count') or 1
        seen_txt = '' if seen <= 1 else ', seen %d times' % seen
        ack = ' (you have acknowledged this)' if a.get('state') == 'acknowledged' else ''
        out.append('%s: %s%s%s%s' % (word, a.get('title') or '', when, seen_txt, ack))
    return out


# =============================================================================
# CAPACITY
# =============================================================================

def capacity_verdict(mem_total_mb, mem_available_mb, rss_mb, loaded_registries,
                     live_tenants, cost_per_tenant_mb, reserve_mb=400):
    """How many more customers this machine can safely hold.

    MEASURED, NOT ASSUMED. `cost_per_tenant_mb` is a number somebody weighed on
    this box (see the ledger) — the resident memory the application gains when
    it opens one more customer's database — and it is a setting so it can be
    re-weighed after a resize without a deploy.

    `reserve_mb` is what must be left alone: the database server, the operating
    system and enough head for a pay run to spike into. Spending it is how a box
    with "plenty free" dies at 09:00 on a Monday.

    Levels: `full` at nought room left, `warn` at one, `ok` above that. The
    guard on new customers reads this and nothing else.
    """
    total = float(mem_total_mb or 0)
    avail = float(mem_available_mb or 0)
    rss = float(rss_mb or 0)
    cost = float(cost_per_tenant_mb or 0)
    if cost <= 0:                     # never divide by a setting somebody cleared
        cost = 60.0
    reserve = float(reserve_mb or 0)
    spare = avail - reserve
    raw = int(spare // cost)
    headroom = max(0, raw)
    rss_pct = (rss * 100.0 / total) if total else 0.0
    level = 'ok'
    if headroom <= 0:
        level = 'full'
    elif headroom <= 1 or rss_pct > 70:
        level = 'warn'
    if level == 'full':
        reason = ("This machine cannot safely hold another customer. "
                  "%d MB of memory is free and %d MB has to stay free for the "
                  "database server and the operating system."
                  % (int(avail), int(reserve)))
    elif level == 'warn':
        reason = ("Room for %d more customer%s. Each one costs about %d MB of "
                  "memory and %d MB is free. Plan the resize before the next "
                  "sale." % (headroom, '' if headroom == 1 else 's',
                             int(cost), int(avail)))
    else:
        reason = ("Room for %d more customers. %d MB of memory is free, each "
                  "customer costs about %d MB, and %d MB is kept back for the "
                  "database server and the operating system."
                  % (headroom, int(avail), int(cost), int(reserve)))
    return {
        'level': level,
        'headroom': headroom,
        'reason': reason,
        'mem_total_mb': int(total),
        'mem_available_mb': int(avail),
        'rss_mb': int(rss),
        'rss_pct': int(rss_pct),
        'cost_per_tenant_mb': int(cost),
        'reserve_mb': int(reserve),
        'loaded_registries': int(loaded_registries or 0),
        'live_tenants': int(live_tenants or 0),
    }


# =============================================================================
# THE PUBLIC PAGE
# =============================================================================

#: What each kind of problem is called in public. NO CUSTOMER IS EVER NAMED, and
#: the phrasing is deliberately about the SERVICE rather than about the incident:
#: the reader is somebody's payroll officer wondering whether to keep working.
_PUBLIC_PHRASE = {
    'tenant_down': ('Customer sites', 'degraded', 'A customer site was unreachable'),
    'tenant_errors': ('Payroll processing', 'degraded', 'Errors during payroll processing'),
    'mail_failing': ('Email delivery', 'degraded', 'Email delivery was interrupted'),
    'alert_channel_down': ('Email delivery', 'degraded', 'Email delivery was interrupted'),
    'backup_failed': ('Payroll processing', 'ok', 'A scheduled backup did not complete'),
    'backup_stale': ('Payroll processing', 'ok', 'A scheduled backup did not complete'),
    'disk_low': ('Sign-in & web app', 'degraded', 'Reduced capacity on the platform'),
    'memory_high': ('Sign-in & web app', 'degraded', 'Reduced capacity on the platform'),
    'master_behind_files': ('Sign-in & web app', 'degraded', 'Reduced capacity on the platform'),
    'cert_expiring': ('Sign-in & web app', 'ok', 'Certificate renewal'),
}


def _worse(a, b):
    return a if LEVEL_ORDER.get(a, 0) >= LEVEL_ORDER.get(b, 0) else b


def status_state(open_alerts, notices, incidents, now, maintenance=False,
                 updated_at=None):
    """Everything we know, reduced to what the world may read.

    THIS FUNCTION IS THE BOUNDARY. On the way in: alerts that name customers,
    a rollout that names the customer it is on, notices addressed to one
    company. On the way out: four component names, four levels, the notices the
    owner explicitly ticked as public, and last week's incidents as durations.
    A test feeds it names and asserts the output has none.

    `maintenance` is True while a rollout is walking across the customer rings —
    planned work, which is a different colour from a fault and says so.
    """
    levels = {name: 'ok' for name in COMPONENTS}
    only_critical = [a for a in (open_alerts or ())
                     if (a.get('state') or 'open') in ('open', 'acknowledged')]
    for a in only_critical:
        comp, lvl, _phrase = _PUBLIC_PHRASE.get(a.get('kind'), (None, None, None))
        if not comp or lvl == 'ok':
            continue
        # A warning about one customer is not a degraded service for everybody;
        # only a critical is allowed to colour a component.
        if a.get('severity') != 'critical':
            continue
        levels[comp] = _worse(levels[comp], lvl)
    if maintenance:
        levels['Customer sites'] = _worse(levels['Customer sites'], 'maintenance')

    overall = 'ok'
    for lvl in levels.values():
        overall = _worse(overall, lvl)

    pub_notices = []
    for n in (notices or ()):
        pub_notices.append({
            'kind': n.get('kind') or 'info',
            'title': n.get('title') or '',
            'text': n.get('text') or '',
            'range': n.get('range') or '',
        })

    rows = []
    for inc in (incidents or ()):
        phrase = _PUBLIC_PHRASE.get(inc.get('kind'), (None, None, 'A service issue'))[2]
        mins = int(inc.get('minutes') or 0)
        if mins <= 0:
            length = 'briefly'
        elif mins < 60:
            length = 'for %d minutes' % mins
        elif mins < 60 * 36:
            length = 'for %d hours' % max(1, int(round(mins / 60.0)))
        else:
            length = 'for %d days' % max(1, int(round(mins / 1440.0)))
        rows.append({'when': str(inc.get('ended') or '')[:10],
                     'what': '%s %s' % (phrase, length)})

    return {
        'level': overall,
        'headline': {
            'ok': 'All systems operational',
            'maintenance': 'Planned maintenance in progress',
            'degraded': 'Some systems are degraded',
            'down': 'Major outage',
        }[overall],
        'components': [{'name': n, 'level': levels[n]} for n in COMPONENTS],
        'notices': pub_notices,
        'incidents': rows,
        'updated_at': updated_at or (now.strftime('%Y-%m-%d %H:%M:%S')
                                     if isinstance(now, datetime) else str(now)),
    }


_LEVEL_WORD = {
    'ok': 'Operational',
    'maintenance': 'Planned maintenance',
    'degraded': 'Degraded',
    'down': 'Outage',
}
_LEVEL_COLOR = {
    'ok': '#2E7D4F',
    'maintenance': '#2563EB',
    'degraded': '#D97706',
    'down': '#DC2668',
}


def render_status_page(state, now=None):
    """The whole public page as one self-contained file.

    No external request of any kind — no font, no script, no image — because the
    page's entire job is to be readable on the day the platform is not. nginx
    serves it off disk and never touches the application.

    It checks its OWN freshness. The file carries the moment it was written; a
    few lines of script in the browser compare that with the reader's clock and
    say so when it is more than a quarter of an hour old. A status page that
    quietly stops updating is worse than none at all, so it is made to admit it.
    """
    state = state or {}
    now = now or datetime.utcnow()
    level = state.get('level') or 'ok'
    e = html.escape
    updated = state.get('updated_at') or now.strftime('%Y-%m-%d %H:%M:%S')

    comps = []
    for c in state.get('components') or ():
        lvl = c.get('level') or 'ok'
        comps.append(
            '<li class="c"><span class="n">%s</span>'
            '<span class="s" style="color:%s"><i style="background:%s"></i>%s</span></li>'
            % (e(c.get('name') or ''), _LEVEL_COLOR.get(lvl, '#2E7D4F'),
               _LEVEL_COLOR.get(lvl, '#2E7D4F'), e(_LEVEL_WORD.get(lvl, 'Operational'))))

    notices = []
    for n in state.get('notices') or ():
        when = (' <span class="w">%s</span>' % e(n['range'])) if n.get('range') else ''
        body = ('<p>%s</p>' % e(n['text'])) if n.get('text') else ''
        notices.append(
            '<div class="note %s"><h3>%s%s</h3>%s</div>'
            % (e(n.get('kind') or 'info'), e(n.get('title') or ''), when, body))

    incidents = []
    for i in state.get('incidents') or ():
        incidents.append('<li><span class="d">%s</span>%s</li>'
                         % (e(i.get('when') or ''), e(i.get('what') or '')))
    if not incidents:
        incidents.append('<li class="none">No incidents in the last seven days.</li>')

    return """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Payobook status</title>
<style>
:root{--ink:#12121a;--dim:#5c5c6b;--line:#e6e4f0;--bg:#faf9fd;--card:#fff;--accent:%(indigo)s}
@media (prefers-color-scheme:dark){:root{--ink:#f2f1f7;--dim:#a09eb4;--line:#2a2836;--bg:#101018;--card:#181722}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased}
.wrap{max-width:720px;margin:0 auto;padding:56px 20px 72px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:-.02em;
 color:var(--accent);font-size:17px;margin-bottom:38px}
.brand b{width:10px;height:10px;border-radius:3px;background:var(--accent);display:block}
.hero{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px 24px;
 display:flex;align-items:center;gap:16px}
.hero .dot{width:14px;height:14px;border-radius:50%%;background:%(color)s;flex:none;
 box-shadow:0 0 0 5px %(color)s22}
.hero h1{margin:0;font-size:22px;letter-spacing:-.02em;font-weight:650}
.hero .sub{color:var(--dim);font-size:13px;margin-top:3px}
.note{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
 border-radius:12px;padding:16px 18px;margin-top:14px}
.note.maintenance{border-left-color:#2563EB}
.note h3{margin:0;font-size:15px;font-weight:640}
.note .w{color:var(--dim);font-weight:450;font-size:13px;margin-left:6px}
.note p{margin:6px 0 0;color:var(--dim);font-size:14px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.09em;color:var(--dim);
 margin:34px 0 10px;font-weight:600}
ul{list-style:none;margin:0;padding:0;background:var(--card);border:1px solid var(--line);
 border-radius:12px;overflow:hidden}
li{padding:13px 18px;border-top:1px solid var(--line);font-size:14px}
li:first-child{border-top:0}
.c{display:flex;align-items:center;justify-content:space-between;gap:12px}
.c .s{font-size:13px;font-weight:560;display:flex;align-items:center;gap:7px}
.c .s i{width:7px;height:7px;border-radius:50%%;display:block}
li .d{color:var(--dim);font-variant-numeric:tabular-nums;margin-right:12px}
li.none{color:var(--dim)}
.foot{margin-top:30px;color:var(--dim);font-size:12.5px;text-align:center}
#stale{display:none;margin-top:14px;background:#D9760615;border:1px solid #D9760655;
 color:#D97706;border-radius:10px;padding:11px 14px;font-size:13.5px}
</style></head>
<body>
<div class="wrap">
  <div class="brand"><b></b>Payobook</div>
  <div class="hero">
    <span class="dot"></span>
    <div><h1>%(headline)s</h1>
    <div class="sub">Live status of the Payobook payroll service.</div></div>
  </div>
  %(notices)s
  <div id="stale">This page has not refreshed for a while, so it may be out of
  date. If something is not working for you, please email support.</div>
  <h2>Services</h2>
  <ul>%(components)s</ul>
  <h2>Last seven days</h2>
  <ul>%(incidents)s</ul>
  <div class="foot">Updated <span id="when">%(updated)s</span> UTC ·
  This page is served separately from the application, so it stays up when the
  application does not.</div>
</div>
<script>
(function(){
  var stamp = "%(updated)s".replace(" ", "T") + "Z";
  var t = Date.parse(stamp);
  if (isNaN(t)) { return; }
  function check(){
    var mins = (Date.now() - t) / 60000;
    document.getElementById("stale").style.display = mins > %(stale)d ? "block" : "none";
  }
  check(); setInterval(check, 30000);
})();
</script>
</body></html>
""" % {
        'indigo': _INDIGO,
        'color': _LEVEL_COLOR.get(level, '#2E7D4F'),
        'headline': e(state.get('headline') or 'All systems operational'),
        'notices': '\n  '.join(notices),
        'components': ''.join(comps),
        'incidents': ''.join(incidents),
        'updated': e(updated),
        'stale': int(DEFAULT_THRESHOLDS['status_page_minutes']),
    }
