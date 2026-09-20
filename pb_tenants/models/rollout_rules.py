# -*- coding: utf-8 -*-
"""The decisions behind a rollout, lifted out so a test can reach them.

Rail R6, and the third file in this family after `sync_rules.py` and
`tenancy_rules.py`. Everything a rollout DOES happens on somebody else's
database — restore a copy, install parts of the product, read a log, drop the
copy again — and none of it is reachable from a test suite. So the judgements
are here, pure, and the worker in `rollout_service.py` is left holding the acts.

The one that earns its keep is `advance()`. It is the whole state machine of a
rollout — which task runs next, whether the watch period is over, whether the
whole thing should stop — as a function of a plain dictionary and the time. The
worker calls it; the tests hammer it; nobody has to start a rollout on a live
customer to find out what it will do at 3 a.m.

NOTHING HERE IMPORTS ODOO.
"""
from datetime import datetime, timedelta, timezone

try:                                                 # pragma: no cover
    from zoneinfo import ZoneInfo
except ImportError:                                  # pragma: no cover
    ZoneInfo = None

from .tenancy_rules import fmt_stamp, notice_payload, parse_stamp

#: The waves, in the order they happen, and the order is the whole safety
#: argument: a practice run on a copy, then the blank database new customers
#: are made from, then ONE customer, then the customers who volunteered to be
#: early, then everybody. Nothing skips a place in this queue.
RING_ORDER = ('rehearsal', 'template', 'canary', 'early', 'everyone')

#: The three a customer can be put in. `rehearsal` and `template` are not
#: places a customer can sit; they are things the platform does to itself.
CUSTOMER_RINGS = ('canary', 'early', 'everyone')

#: What each wave is called on screen, said the way a person would say it.
RING_LABEL = {
    'rehearsal': "Rehearsal",
    'template': "New-customer template",
    'canary': "Canary customer",
    'early': "Early group",
    'everyone': "Everyone else",
}

#: One line each, for the tooltips. "Canary" is the only word here somebody
#: might not know, so it is the one that gets explained rather than renamed:
#: the owner will meet it in every other release tool he ever uses.
RING_MEANING = {
    'rehearsal': ("A practice run on a throwaway copy of a customer's data. "
                  "Nobody sees it and the copy is deleted afterwards, whatever "
                  "happens."),
    'template': ("The blank database every new customer is created from. It "
                 "goes next so a customer who signs up tomorrow starts on the "
                 "new version."),
    'canary': ("The first real customer to get it — one, on their own, with a "
               "watch period afterwards. Named after the bird miners took "
               "underground: if something is wrong, one customer finds it "
               "instead of all of them."),
    'early': ("Customers happy to get changes a day or two ahead of the rest."),
    'everyone': ("The rest of the fleet, once the earlier waves have been "
                 "quiet for the watch period."),
}

#: Waves that wait afterwards, and the setting that says how long. Rehearsal
#: and the template have no watch period: nobody is using them.
WATCH_RINGS = ('canary', 'early')

DEFAULT_WATCH = {'canary': 24, 'early': 48}

#: A window nobody typed. 22:00 for three hours is when a payroll office is
#: empty in every country this product is sold in.
DEFAULT_START_HOUR = 22
DEFAULT_HOURS = 3
DEFAULT_TZ = 'Asia/Ho_Chi_Minh'

#: A task that says it is running and has been saying so for longer than this
#: was interrupted — the process was restarted mid-update, most likely. It is
#: not left spinning for ever; the rollout stops and says so.
STUCK_MINUTES = 90

#: How far ahead the pre-notice looks. A day's warning is enough for a payroll
#: office to move a pay run and short enough that the bar is still relevant.
PRE_NOTICE_HOURS = 24


# ---------------------------------------------------------------- time helpers
def _zone(tz):
    """The time zone, or UTC when the name is missing or unknown.

    A customer with an unreadable time zone gets updated at 22:00 UTC rather
    than not at all. It is the wrong hour for them; it is not a rollout that
    silently stops.
    """
    if not tz or ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(str(tz))
    except Exception:                                # noqa: BLE001
        return timezone.utc


def _aware(dt):
    """A datetime as UTC-aware. The framework hands out naive UTC.

    AN EMPTY DATE FIELD READS AS `False`, NOT `None`. Every unset Datetime the
    ORM hands over is the boolean, so a plain `if dt is None` lets it through
    and the next line asks a boolean for its `tzinfo`. Falsy of any shape means
    "there is no such moment".
    """
    if not dt:
        return None
    if isinstance(dt, str):
        dt = parse_stamp(dt)
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _naive(dt):
    """Back to the naive UTC the framework stores."""
    aware = _aware(dt)
    if aware is None:
        return None
    return aware.astimezone(timezone.utc).replace(tzinfo=None)


def _clean_window(start_hour, hours):
    start = int(start_hour if start_hour not in (None, False, '') else DEFAULT_START_HOUR)
    span = int(hours if hours not in (None, False, '') else DEFAULT_HOURS)
    return start % 24, max(1, min(24, span))


def window_open(now_utc, tz, start_hour, hours):
    """Is this customer's night-time window open right now, where they are?

    The window is a wall-clock band in the customer's own zone, so it survives
    daylight saving without arithmetic: we ask what time it is THERE and
    compare the hour. A band that runs past midnight (22:00 for three hours)
    wraps, which is the case that gets written wrong everywhere.
    """
    start, span = _clean_window(start_hour, hours)
    local = _aware(now_utc).astimezone(_zone(tz))
    mins = local.hour * 60 + local.minute
    a, b = start * 60, start * 60 + span * 60
    if b <= 24 * 60:
        return a <= mins < b
    return mins >= a or mins < (b - 24 * 60)


def next_window(now_utc, tz, start_hour, hours):
    """When this customer's window opens next, as naive UTC.

    Now, if it is already open. Otherwise today's opening if that is still
    ahead of them, else tomorrow's. Built from the LOCAL wall clock and then
    converted, so on the two days a year a zone shifts, "22:00" still means
    22:00 to the person reading the bar.
    """
    start, span = _clean_window(start_hour, hours)
    if window_open(now_utc, tz, start, span):
        return _naive(now_utc)
    zone = _zone(tz)
    local = _aware(now_utc).astimezone(zone)
    todays = local.replace(hour=start, minute=0, second=0, microsecond=0)
    if todays <= local:
        todays = todays + timedelta(days=1)
        # Re-attach the zone to the NEW wall clock: adding a day to an aware
        # datetime keeps the old offset, which is an hour out on the day a
        # zone shifts. Re-stating the wall clock is what makes this DST-safe.
        todays = datetime(todays.year, todays.month, todays.day, start, 0,
                          tzinfo=zone)
    return _naive(todays)


def to_local(dt, tz):
    """A UTC moment as the naive wall clock in `tz`.

    For SAYING a window out loud. The phrase on the platform owner's screen is
    "tonight 22:00–01:00 (their time)", and the only way to get 22:00 out of a
    renderer that formats whatever it is handed is to hand it the customer's
    own clock rather than the server's.
    """
    aware = _aware(dt)
    if aware is None:
        return None
    return aware.astimezone(_zone(tz)).replace(tzinfo=None)


def window_bounds(now_utc, tz, start_hour, hours):
    """`(opens, closes)` for the next window, as naive UTC — for the notice."""
    start, span = _clean_window(start_hour, hours)
    opens = next_window(now_utc, tz, start, span)
    zone = _zone(tz)
    local_open = _aware(opens).astimezone(zone)
    local_close = local_open + timedelta(hours=span)
    return opens, _naive(local_close)


# ---------------------------------------------------------------- the plan
def plan_tasks(release, tenants, rehearsal_source, template_db='payobook_template'):
    """Every task of one rollout, in the order they will happen.

    `release` is `{'id', 'name'}`. `tenants` is a list of dicts carrying
    `id, name, slug, state, ring`. `rehearsal_source` is the customer whose
    latest backup the practice run is restored from, or None.

    Returns `{'tasks': [...], 'excluded': [...], 'warnings': [...]}`.

    THE REHEARSAL IS FIRST AND IT IS NOT OPTIONAL (rail R4). A release that
    cannot be practised on a copy is a release nobody has ever seen applied,
    and the first database to find out would be a customer's.

    A customer still being set up, or one that has been closed down, is left
    out with a reason — silence about a customer that did not get the update
    is the failure mode this list exists to prevent.
    """
    tasks, excluded, warnings = [], [], []
    seq = 0

    def add(ring, target_db, label, tenant_id=None, source_tenant_id=None):
        nonlocal seq
        seq += 10
        tasks.append({
            'sequence': seq, 'ring': ring, 'target_db': target_db,
            'label': label, 'tenant_id': tenant_id,
            'source_tenant_id': source_tenant_id,
        })

    if rehearsal_source:
        add('rehearsal', '%s-staging' % rehearsal_source['slug'],
            "%s (practice copy)" % rehearsal_source['name'],
            source_tenant_id=rehearsal_source['id'])
    else:
        warnings.append(
            "There is no customer with a backup to practise on, so this "
            "rollout starts at the new-customer template.")

    add('template', template_db, "Golden template")

    ranked = {r: [] for r in CUSTOMER_RINGS}
    for t in tenants or ():
        state = t.get('state')
        if state == 'decommissioned':
            excluded.append({'id': t.get('id'), 'name': t.get('name'),
                             'reason': "Closed down."})
            continue
        if state in ('draft', 'provisioning'):
            excluded.append({'id': t.get('id'), 'name': t.get('name'),
                             'reason': "Still being set up — it will be "
                                       "created on the new version anyway."})
            continue
        if state == 'error':
            excluded.append({'id': t.get('id'), 'name': t.get('name'),
                             'reason': "This customer is in trouble already. "
                                       "Put it right first, then roll out to "
                                       "it on its own."})
            continue
        ring = t.get('ring') or 'everyone'
        if ring not in ranked:
            ring = 'everyone'
        ranked[ring].append(t)

    for ring in CUSTOMER_RINGS:
        for t in sorted(ranked[ring], key=lambda r: (r.get('name') or '').lower()):
            add(ring, t.get('slug'), t.get('name'), tenant_id=t.get('id'))

    if not any(ranked[r] for r in CUSTOMER_RINGS):
        warnings.append("No customers are being updated — there are none live "
                        "yet. The practice run and the template still run.")
    elif not ranked['canary']:
        warnings.append("No customer is marked as the canary, so the first "
                        "real customer to get this is in the early group. "
                        "Marking one canary means one customer meets a "
                        "problem instead of several.")
    return {'tasks': tasks, 'excluded': excluded, 'warnings': warnings,
            'release': release}


def eligible(task, now_utc):
    """May this queued task run at this moment?

    Three ways to be yes: somebody pressed "Run now", it is one of the two
    waves with nobody looking at it, or the customer's own night-time window
    is open where they are.
    """
    if task.get('run_now'):
        return True
    if task.get('ring') in ('rehearsal', 'template'):
        return True
    return window_open(now_utc, task.get('tz'),
                       task.get('maintenance_start'),
                       task.get('maintenance_hours'))


#: Log lines that are always there and never mean the update went wrong. Each
#: one is a substring, matched case-insensitively, and each one is here because
#: somebody looked at it and decided it was noise — not because it was
#: convenient. They are still RECORDED on the task; they simply do not stop a
#: rollout.
#:
#: The first entry is the reason this list exists. A vendor module on this
#: build writes one ERROR every time any database loads its registry, saying it
#: cannot find a licence file that has never been installed. It fired on the
#: very first rehearsal of the very first rollout and stopped it, on a copy that
#: was in perfect health. A gate that cries wolf on every run is a gate the
#: owner learns to click past, which is worse than no gate.
DEFAULT_LOG_IGNORE = (
    'License check FAILED',
)


def filter_errors(lines, ignore=None):
    """Split log lines into the ones that matter and the ones that always fire.

    Returns `(kept, ignored)`. `ignore` is an iterable of substrings; empty or
    None means nothing is ignored, so the strict behaviour is always one empty
    setting away.
    """
    patterns = [str(p).strip().lower() for p in (ignore or ()) if str(p).strip()]
    kept, skipped = [], []
    for line in (lines or ()):
        text = str(line).lower()
        (skipped if any(p in text for p in patterns) else kept).append(line)
    return kept, skipped


def parse_ignore(raw):
    """The ignore list as the setting holds it: one substring per line."""
    if raw is None:
        return list(DEFAULT_LOG_IGNORE)
    return [p.strip() for p in str(raw).splitlines() if p.strip()]


def health_verdict(probe_code, skipped, error_lines):
    """Did the database survive its update? `(ok, plain-English reason)`.

    Three questions, asked worst-first, because the first "no" is the one worth
    reading. `probe_code` is an HTTP status, 0 for no answer at all, and None
    when there was nothing to probe (the template has no address). `skipped` is
    -1 when the framework could not tell us.
    """
    lines = [str(x) for x in (error_lines or ())]
    if probe_code == 0:
        return False, "The site did not answer after the update."
    if probe_code not in (None, 0) and int(probe_code) >= 500:
        return False, ("The site answered with an error (%s) after the update."
                       % probe_code)
    skipped = -1 if skipped is None else int(skipped)
    if skipped > 0:
        return False, ("%s part%s of the product said it was installed but did "
                       "not load at start-up." % (skipped, '' if skipped == 1 else 's'))
    if lines:
        return False, ("%s error%s in the log while it was updating."
                       % (len(lines), '' if len(lines) == 1 else 's'))
    if skipped < 0:
        return True, "Could not tell whether anything was skipped."
    return True, ""


def watch_hours_for(ring, watch_hours=None):
    """How long to sit and watch after a wave. 0 for the waves nobody uses."""
    if ring not in WATCH_RINGS:
        return 0
    hours = (watch_hours or {}).get(ring, DEFAULT_WATCH.get(ring, 24))
    try:
        return max(0, int(hours))
    except (TypeError, ValueError):
        return DEFAULT_WATCH.get(ring, 24)


def _ring_tasks(snapshot, ring):
    return [t for t in snapshot.get('tasks', ()) if t.get('ring') == ring]


def _next_ring_with_tasks(snapshot, ring):
    try:
        idx = RING_ORDER.index(ring)
    except ValueError:
        return None
    for nxt in RING_ORDER[idx + 1:]:
        if _ring_tasks(snapshot, nxt):
            return nxt
    return None


def advance(snapshot, now_utc):
    """What should the worker do at this instant? THE WHOLE STATE MACHINE.

    `snapshot` is a plain dict:
        state, current_ring, ring_done_at, watch_skipped, watch_hours,
        watch_health (list of {'name', 'ok', 'reason'} re-probes taken during
        the watch period), and `tasks`: a list of
        {id, ring, state, run_now, tz, maintenance_start, maintenance_hours,
         started_at, error, label}.

    Returns one of:
        ('run', task)            run this task now
        ('wait', until_utc)      nothing to do until then
        ('ring_done', ring)      every task in this wave is finished
        ('advance_ring', ring)   move to this wave
        ('done',)                the whole rollout is finished
        ('pause', reason)        stop, and this is what a person must read

    ONE TASK AT A TIME, ALWAYS. Not because the server could not manage two,
    but because a rollout that has gone wrong should have gone wrong on one
    customer.
    """
    now = _aware(now_utc)
    tasks = list(snapshot.get('tasks') or ())
    if not tasks:
        return ('done',)

    ring = snapshot.get('current_ring') or RING_ORDER[0]
    mine = _ring_tasks(snapshot, ring)

    # A wave with nothing in it is not a wave to sit in.
    if not mine:
        nxt = _next_ring_with_tasks(snapshot, ring)
        return ('advance_ring', nxt) if nxt else ('done',)

    # 1. Anything that has already failed stops everything. It is the whole
    #    point of the ordering: one customer met the problem, and the next one
    #    does not.
    failed = [t for t in mine if t.get('state') == 'failed']
    if failed:
        return ('pause', failed[0].get('error') or
                ("%s could not be updated." % (failed[0].get('label') or 'A customer')))

    # 2. Something already running. Either it is genuinely in flight — a task
    #    is minutes, not seconds — or the process died holding it, and a
    #    rollout that waits for ever is worse than one that says so.
    running = [t for t in mine if t.get('state') == 'running']
    if running:
        started = _aware(running[0].get('started_at')) or now
        if now - started > timedelta(minutes=STUCK_MINUTES):
            return ('pause',
                    "The update of %s started %s minutes ago and never "
                    "finished. Check the server, then retry it or skip it."
                    % (running[0].get('label') or 'a customer',
                       int((now - started).total_seconds() // 60)))
        return ('wait', _naive(min(started + timedelta(minutes=STUCK_MINUTES),
                                   now + timedelta(minutes=5))))

    # 3. Anything left to run in this wave?
    queued = [t for t in mine if t.get('state') == 'queued']
    if queued:
        for t in queued:
            if eligible(t, now):
                return ('run', t)
        whens = [next_window(now, t.get('tz'), t.get('maintenance_start'),
                             t.get('maintenance_hours')) for t in queued]
        return ('wait', min(whens))

    # 4. The wave is finished. Stamp it, then serve the watch period.
    done_at = _aware(snapshot.get('ring_done_at'))
    if not done_at:
        return ('ring_done', ring)

    hours = watch_hours_for(ring, snapshot.get('watch_hours'))
    if hours and not snapshot.get('watch_skipped'):
        # A customer that went quiet during the watch period is the reason the
        # watch period exists. One bad re-probe stops the rollout where it is.
        for probe in (snapshot.get('watch_health') or ()):
            if not probe.get('ok'):
                return ('pause',
                        "%s stopped looking healthy during the watch period: "
                        "%s" % (probe.get('name') or 'A customer',
                                probe.get('reason') or 'unknown'))
        until = done_at + timedelta(hours=hours)
        if now < until:
            return ('wait', _naive(until))

    nxt = _next_ring_with_tasks(snapshot, ring)
    return ('advance_ring', nxt) if nxt else ('done',)


# ---------------------------------------------------------------- the notices
def notice_for(phase, starts_at=None, ends_at=None, notice_id='preview'):
    """The message a customer's users see, before and during their update.

    Two phases and no others. `pre` goes out the evening before, or up to a day
    ahead; `now` goes up while the work is actually happening and comes down
    when it is over.

    Returns the same payload shape the manual composer produces, validated by
    the same function, so a notice the platform sends itself can never be a
    shape the customer's bar has not been taught to read.
    """
    if phase == 'pre':
        title = "Payobook will be updated"
        text = ("Your service pauses for a minute or two inside this window. "
                "You do not need to do anything.")
    elif phase == 'now':
        title = "Payobook is being updated right now"
        text = "A minute or two. This page will keep working when it is done."
    else:
        raise ValueError("A rollout only sends two kinds of message.")
    payload = notice_payload('maintenance', title, text,
                             fmt_stamp(parse_stamp(starts_at)) if starts_at else '',
                             fmt_stamp(parse_stamp(ends_at)) if ends_at else '',
                             notice_id or 'preview')
    if phase == 'now':
        # THE ONE MESSAGE A READER MAY NOT HIDE. Everything else on that bar is
        # information they can take or leave; this one is the explanation for a
        # pause they are about to experience. Somebody who closes it and then
        # watches their payslip screen stall for a minute has been left with a
        # fault instead of a notice. Read by the customer's own bar, which
        # swaps the close button for a live dot.
        payload['live'] = True
    return payload
