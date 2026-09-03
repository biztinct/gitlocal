# -*- coding: utf-8 -*-
"""Running a rollout: the worker, the health gate, and the buttons.

THE SHAPE OF THIS FILE. Every judgement is next door in `rollout_rules.py`,
pure and tested. What is left here is the acting: restore a copy, run P1's
"bring in step" unit on one database, probe the site, read the log, put a
message on somebody's screen and take it down again. Each of those is a few
lines, and every one of them is a thing that can only be done on a live box.

RAIL R1, WHICH IS THE WHOLE PHASE. Nothing here starts a rollout. A person
presses Start; that writes down the list of databases and the order; the worker
then does exactly that list and stops at the first failure. The hourly notice
cron only speaks to customers who are already on somebody's list. Every step
leaves a line in the customer's own provisioning trail, so the answer to "why
did my system pause last night" is on their record, not in a log file.
"""
import json
import logging
import os
import re
from datetime import datetime, timedelta

import odoo
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .rollout_rules import (
    CUSTOMER_RINGS, DEFAULT_HOURS, DEFAULT_START_HOUR, DEFAULT_TZ, PRE_NOTICE_HOURS,
    RING_LABEL, RING_MEANING, RING_ORDER, advance, health_verdict, next_window,
    filter_errors, notice_for, parse_ignore, plan_tasks, to_local,
    watch_hours_for, window_bounds,
)
from .tenancy_rules import render_range

_logger = logging.getLogger(__name__)

#: `2026-09-02 14:11:54,601 2811793 INFO p9clone odoo.modules.loading: …`
LOG_RE = re.compile(
    r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ \d+ (\w+) (\S+) ([^:]+): (.*)$')

#: How much of the log to read. The file is ~80 MB and grows; the last 20 MB is
#: several hours of a busy box, and a task is minutes.
LOG_TAIL_BYTES = 20 * 1024 * 1024

#: The levels that count as "something went wrong" for the health gate.
LOG_BAD_LEVELS = ('ERROR', 'CRITICAL')

#: How many error lines to keep on the task. Enough to read; not a log viewer.
LOG_KEEP = 12


class PbTenantsRollout(models.AbstractModel):
    """The rollout half of the Tenant Mission Control facade."""
    _inherit = 'pb.tenants'

    # ============================================================ small helpers
    def _tenant_tz(self, tenant):
        """What time is it where this customer is?

        Read once off their own company's record — plain SQL, read-only, no
        registry opened — and then kept on our side. A customer with nothing
        set falls back to the zone every customer of this product has so far
        been in, which is a better guess than the server's UTC.
        """
        if tenant.tz:
            return tenant.tz
        tz = ''
        try:
            with self._pg_cursor(tenant.slug) as cr:
                cr.execute("SELECT p.tz FROM res_company c "
                           "JOIN res_partner p ON p.id = c.partner_id "
                           "WHERE p.tz IS NOT NULL ORDER BY c.id LIMIT 1")
                row = cr.fetchone()
                tz = (row and row[0]) or ''
        except Exception:                            # noqa: BLE001
            _logger.warning("pb_tenants: could not read the time zone of %s",
                            tenant.slug, exc_info=True)
        tz = tz or DEFAULT_TZ
        tenant.sudo().write({'tz': tz})
        return tz

    def _task_window(self, task, now=None):
        """`(tz, start_hour, hours)` for one task's customer."""
        t = task.tenant_id
        if not t:
            return DEFAULT_TZ, DEFAULT_START_HOUR, DEFAULT_HOURS
        return (self._tenant_tz(t),
                t.maintenance_start or DEFAULT_START_HOUR,
                t.maintenance_hours or DEFAULT_HOURS)

    def _task_snapshot(self, task):
        """One task as the pure state machine reads it."""
        tz, start, hours = self._task_window(task)
        return {
            'id': task.id, 'ring': task.ring, 'state': task.state,
            'run_now': task.run_now, 'label': task.label,
            'tz': tz, 'maintenance_start': start, 'maintenance_hours': hours,
            'started_at': task.started_at, 'error': task.error or '',
        }

    def _rollout_snapshot(self, rollout, watch_health=None):
        return {
            'state': rollout.state,
            'current_ring': rollout.current_ring,
            'ring_done_at': rollout.ring_done_at,
            'watch_skipped': rollout.watch_skipped,
            'watch_hours': {'canary': rollout.watch_hours_canary,
                            'early': rollout.watch_hours_early},
            'watch_health': watch_health or [],
            'tasks': [self._task_snapshot(t) for t in rollout.task_ids],
        }

    # ============================================================ the log gate
    def _logfile(self):
        return odoo.tools.config['logfile'] or '/var/log/odoo/odoo-server.log'

    def _log_errors_since(self, dbname, since):
        """Errors this database logged since a moment. Read-only, tail only.

        THE EXACT QUESTION: lines whose timestamp is at or after `since`, whose
        level is ERROR or CRITICAL, and whose database column is this database.
        The server writes UTC (its clock is UTC) and the framework stores UTC,
        so the two compare directly with no arithmetic — a fact worth stating,
        because the day this box is moved to a local zone this comparison is
        the thing that quietly stops working.

        Never fatal: a log we cannot read is reported as "could not check",
        not as a healthy zero.
        """
        path = self._logfile()
        out, read_ok = [], False
        try:
            size = os.path.getsize(path)
            with open(path, 'rb') as fh:
                if size > LOG_TAIL_BYTES:
                    fh.seek(size - LOG_TAIL_BYTES)
                    fh.readline()               # drop the half line we landed in
                read_ok = True
                stamp = (since or datetime.min).strftime('%Y-%m-%d %H:%M:%S')
                for raw in fh:
                    line = raw.decode('utf-8', 'replace').rstrip('\n')
                    m = LOG_RE.match(line)
                    if not m:
                        continue
                    ts, level, db, logger_name, msg = m.groups()
                    if db != dbname or level not in LOG_BAD_LEVELS:
                        continue
                    if ts < stamp:
                        continue
                    # The logger's name is kept because it is the only thing on
                    # the line that says WHICH part of the product complained,
                    # which is the first question anybody reading it asks.
                    out.append('%s %s %s: %s'
                               % (ts, level, logger_name.strip(), msg[:200]))
        except Exception:                            # noqa: BLE001
            _logger.warning("pb_tenants: could not read %s", path, exc_info=True)
            return None
        return out if read_ok else None

    def _health_gate(self, dbname, since, skipped, host=None):
        """Is this database well after its update? The three checks, together.

        Returns the dict stored on the task: what was measured and the verdict
        in one sentence.
        """
        code, ms = (None, -1)
        if host:
            code, ms = self._probe(host)
        raw = self._log_errors_since(dbname, since)
        # Lines that are always there are set aside rather than deleted: they
        # stay on the task where somebody can read them, they simply do not
        # stop a rollout. Emptying the setting restores the strict behaviour.
        errors, ignored = filter_errors(raw or [], self._log_ignore())
        ok, reason = health_verdict(code, skipped,
                                    errors if raw is not None else [])
        if raw is None and ok:
            reason = reason or _("The server log could not be read, so nothing "
                                 "could be checked in it.")
        return {
            'ok': bool(ok), 'reason': reason,
            'probe_code': code, 'probe_ms': ms, 'host': host or '',
            'skipped': -1 if skipped is None else int(skipped),
            'errors': errors[:LOG_KEEP],
            'error_count': -1 if raw is None else len(errors),
            'ignored': ignored[:LOG_KEEP],
            'ignored_count': len(ignored),
            'checked_at': fields.Datetime.now().isoformat(sep=' ', timespec='seconds'),
        }

    def _log_ignore(self):
        """Log lines that are always there. A setting, so it needs no deploy.

        `pb_tenants.health_ignore` — one substring per line. Absent means the
        list that ships with the product; present and empty means ignore
        nothing, which is the setting to use when something is being chased.
        """
        # READ THE ROW, NOT `get_param`, AND BOTH HALVES OF THAT COST A LIVE
        # REHEARSAL. `get_param` answers **False** for a key that is not there,
        # which `parse_ignore` reads as the one-line list ["False"] — a list
        # that ignores nothing while looking exactly like a working one. And
        # `get_param` ends in `or default`, so a value deliberately set to
        # empty comes back as the default as well: through that method "ignore
        # nothing" cannot be said at all. The row itself can say both.
        row = self.env['ir.config_parameter'].sudo().search(
            [('key', '=', 'pb_tenants.health_ignore')], limit=1)
        if not row:
            return parse_ignore(None)
        return parse_ignore(row.value or '')

    # ============================================================ planning
    def _rehearsal_source(self):
        """Whose data the practice run is done on.

        The first canary with a usable backup, then the biggest live customer
        with one. "Biggest" because the practice run's job is to find the slow,
        awkward migration, and the database most likely to have one is the
        database with the most in it.
        """
        Tenant = self.env['pb.tenant'].sudo()
        live = Tenant.search([('state', '=', 'live')])
        def usable(t):
            b = self.env['pb.tenant.backup'].sudo().search(
                [('tenant_id', '=', t.id), ('state', '=', 'done')], limit=1)
            return bool(b and b.path and os.path.exists(b.path))
        canaries = [t for t in live if t.ring == 'canary' and usable(t)]
        pool = canaries or sorted([t for t in live if usable(t)],
                                  key=lambda t: -(t.db_size or 0))
        if not pool:
            return None
        t = pool[0]
        return {'id': t.id, 'name': t.name, 'slug': t.slug}

    def _plan_for(self, rel):
        Tenant = self.env['pb.tenant'].sudo()
        tenants = [{'id': t.id, 'name': t.name, 'slug': t.slug,
                    'state': t.state, 'ring': t.ring} for t in Tenant.search([])]
        return plan_tasks({'id': rel.id, 'name': rel.name}, tenants,
                          self._rehearsal_source(), self._template_db())

    @api.model
    def rollout_plan(self, release_id=None):
        """What a rollout WOULD do. Reads only, and refuses nothing.

        The dialog's whole content: every task in order, when each one would
        happen in the customer's own words, what is being left out and why, and
        the reasons this could not be started right now.
        """
        self._require_admin()
        Release = self.env['pb.release'].sudo()
        rel = (Release.browse(int(release_id)).exists() if release_id
               else Release.current())
        if not rel:
            raise UserError(_("Cut a release first — a rollout ships a release, "
                              "and there is not one yet."))
        plan = self._plan_for(rel)
        now = fields.Datetime.now()
        rows, missing_link = [], []
        for task in plan['tasks']:
            row = dict(task)
            row['ring_label'] = RING_LABEL.get(task['ring'], task['ring'])
            if task['ring'] in CUSTOMER_RINGS and task['tenant_id']:
                t = self.env['pb.tenant'].sudo().browse(task['tenant_id'])
                tz = self._tenant_tz(t)
                opens, closes = window_bounds(
                    now, tz, t.maintenance_start or DEFAULT_START_HOUR,
                    t.maintenance_hours or DEFAULT_HOURS)
                # SAID IN THEIR CLOCK, not the platform's. "Tonight
                # 22:00-01:00" is the sentence the customer's own bar will
                # show them; the owner reading this plan has to be looking at
                # the same window they are, or the two screens disagree about
                # what was scheduled (ledger F17, the other direction).
                row['when'] = render_range(to_local(opens, tz),
                                           to_local(closes, tz),
                                           to_local(now, tz))
                row['tz'] = tz
                if not self._tenancy_installed(t.slug):
                    missing_link.append(t.name)
            else:
                row['when'] = _("right away")
                row['tz'] = ''
            rows.append(row)
        return {
            'release': {'id': rel.id, 'name': rel.name, 'notes': rel.notes or '',
                        'module_count': rel.module_count},
            'tasks': rows,
            'excluded': plan['excluded'],
            'warnings': plan['warnings'],
            'blockers': self._rollout_blockers(rel, missing_link, plan),
            'watch_canary': 24, 'watch_early': 48,
            'ring_meaning': RING_MEANING,
        }

    def _rollout_blockers(self, rel, missing_link=None, plan=None):
        """Everything that stops Start, each with the next step in the sentence."""
        out = []
        # RAIL R4, ENFORCED RATHER THAN HOPED FOR. Found in live validation:
        # with the only usable backup file moved aside, the planner shrugged,
        # left the practice run out and offered to update a real customer with
        # nobody having rehearsed anything. A warning is not enough for this
        # one — the practice run is the reason the first customer is not the
        # experiment.
        if plan is not None:
            customers = [t for t in plan['tasks'] if t['ring'] in CUSTOMER_RINGS]
            rehearsal = any(t['ring'] == 'rehearsal' for t in plan['tasks'])
            if customers and not rehearsal:
                out.append(_(
                    "There is no backup to practise on, and a release never "
                    "reaches a customer without a practice run first. Take a "
                    "backup of %(who)s (their page, Backups, \"Backup now\") "
                    "and start again.",
                    who=customers[0]['label']))
        if not (rel.notes or '').strip():
            out.append(_("Write what changed on this release first — the "
                         "customers read it. The notes box is just above."))
        behind = self._master_behind_files()
        if behind:
            out.append(_("The master has not applied its own files yet "
                         "(%(n)s part(s), starting with %(first)s). Nothing "
                         "goes out until it has.",
                         n=len(behind), first=behind[0]))
        busy = self.env['pb.rollout'].sudo().search(
            [('state', 'in', ('running', 'waiting', 'paused'))], limit=1)
        if busy:
            out.append(_("Release %(name)s is already going out (%(state)s). "
                         "Finish or call that one off first.",
                         name=busy.release_id.name,
                         state=dict(busy._fields['state'].selection).get(busy.state)))
        for name in (missing_link or ()):
            out.append(_("%s cannot be told anything yet — bring it in step "
                         "once by hand first, which installs the Platform "
                         "Link.") % name)
        return out

    # ============================================================ start
    @api.model
    def rollout_start(self, release_id=None, watch_canary=24, watch_early=48):
        """A person presses this, and nothing else ever does.

        Writes the list down, then runs the first task — the practice run —
        while they watch, so the answer to "did that work" is on screen rather
        than in an hour's time.
        """
        self._require_admin()
        # ONE PERSON, TWICE, IS TWO ROLLOUTS — AND THEY FIGHT OVER THE PRACTICE
        # COPY. "Release X is already going out" is checked below, but this
        # whole call runs the practice run before it commits, which takes a
        # minute and a half. A second press inside that minute cannot see the
        # first rollout at all, writes a second one, and the two then restore
        # and drop the same throwaway database underneath each other: the first
        # dies with "connection already closed", the second with "could not
        # serialize access", and both stop with nothing having reached a
        # customer. Seen exactly that way on the live platform, 2026-09-03.
        #
        # This lock is held to the end of the transaction, so the second press
        # waits for the first to finish and then gets the refusal it should
        # have had. Advisory rather than a row lock: there is no row to lock
        # until the very thing being guarded has happened.
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtext('pb_tenants.rollout_start'))")
        Release = self.env['pb.release'].sudo()
        rel = (Release.browse(int(release_id)).exists() if release_id
               else Release.current())
        if not rel:
            raise UserError(_("Cut a release first."))
        plan = self._plan_for(rel)
        missing = []
        for task in plan['tasks']:
            if task['ring'] in CUSTOMER_RINGS and task['tenant_id']:
                t = self.env['pb.tenant'].sudo().browse(task['tenant_id'])
                if not self._tenancy_installed(t.slug):
                    missing.append(t.name)
        blockers = self._rollout_blockers(rel, missing, plan)
        if blockers:
            raise UserError('\n\n'.join(blockers))

        rollout = self.env['pb.rollout'].sudo().create({
            'release_id': rel.id,
            'state': 'running',
            'current_ring': plan['tasks'][0]['ring'] if plan['tasks'] else 'everyone',
            'watch_hours_canary': max(0, int(watch_canary or 0)),
            'watch_hours_early': max(0, int(watch_early or 0)),
            'started_at': fields.Datetime.now(),
            'ring_started_at': fields.Datetime.now(),
            'started_by': self.env.user.id,
        })
        for task in plan['tasks']:
            self.env['pb.rollout.task'].sudo().create({
                'rollout_id': rollout.id,
                'sequence': task['sequence'], 'ring': task['ring'],
                'tenant_id': task['tenant_id'] or False,
                'source_tenant_id': task['source_tenant_id'] or False,
                'label': task['label'], 'target_db': task['target_db'],
            })
        rollout.log_line(_("%(who)s started release %(name)s going out to "
                           "%(n)s database(s).",
                           who=self.env.user.name, name=rel.name,
                           n=len(plan['tasks'])))
        for w in plan['warnings']:
            rollout.log_line(w, 'warn')
        self._refresh_schedule(rollout)
        # The first task is the practice run, and it needs nobody's window: run
        # it now so the person who pressed Start sees the answer.
        self._rollout_tick(rollout)
        return self.rollout_state()

    def _refresh_schedule(self, rollout):
        """When each queued customer's window next opens. For the screen."""
        now = fields.Datetime.now()
        for task in rollout.task_ids:
            if task.state != 'queued' or task.ring not in CUSTOMER_RINGS:
                continue
            tz, start, hours = self._task_window(task)
            task.sudo().write({'scheduled_for': next_window(now, tz, start, hours)})

    # ============================================================ the worker
    def _lock_rollout(self, rollout):
        """Nobody works on this rollout twice at once.

        The scheduled worker and a person pressing "Run now" are two different
        threads reaching for the same customer, and the second one would find a
        registry being rebuilt underneath it. `SKIP LOCKED` means the loser
        walks away rather than queueing behind a job that takes minutes.
        """
        self.env.cr.execute(
            "SELECT id FROM pb_rollout WHERE id = %s FOR UPDATE SKIP LOCKED",
            (rollout.id,))
        return bool(self.env.cr.fetchone())

    @api.model
    def rollout_tick(self, rollout_id=None):
        """One step of the worker, asked for by a person. Returns the screen."""
        self._require_admin()
        rollout = self._current_rollout(rollout_id)
        if not rollout:
            return self.rollout_state()
        self._rollout_tick(rollout)
        return self.rollout_state()

    def _current_rollout(self, rollout_id=None):
        R = self.env['pb.rollout'].sudo()
        if rollout_id:
            return R.browse(int(rollout_id)).exists()
        return R.search([('state', 'in', ('running', 'waiting'))],
                        order='id desc', limit=1)

    def _rollout_tick(self, rollout):
        """THE WORKER. One decision, one act, and back for another look."""
        if rollout.state not in ('running', 'waiting'):
            return {'ok': False, 'reason': 'not running'}
        if not self._lock_rollout(rollout):
            _logger.info("pb_tenants: rollout %s is already being worked on",
                         rollout.id)
            return {'ok': False, 'reason': 'busy'}
        now = fields.Datetime.now()
        watch = self._watch_probes(rollout, now)
        decision = advance(self._rollout_snapshot(rollout, watch), now)
        kind = decision[0]

        if kind == 'run':
            task = self.env['pb.rollout.task'].sudo().browse(decision[1]['id'])
            rollout.sudo().write({'state': 'running'})
            self._run_task(task)
            # Look again immediately: a finished task usually means the next
            # one may start, and waiting five minutes to notice is five
            # minutes of a maintenance window spent idle.
            return self._rollout_tick(rollout)
        if kind == 'ring_done':
            rollout.sudo().write({'ring_done_at': now})
            rollout.log_line(_("%s finished.") % RING_LABEL.get(decision[1], decision[1]))
            return self._rollout_tick(rollout)
        if kind == 'advance_ring':
            ring = decision[1]
            rollout.sudo().write({'current_ring': ring, 'state': 'running',
                                  'ring_started_at': now, 'ring_done_at': False,
                                  'watch_skipped': False})
            rollout.log_line(_("Moving on to %s.") % RING_LABEL.get(ring, ring))
            self._refresh_schedule(rollout)
            return self._rollout_tick(rollout)
        if kind == 'wait':
            rollout.sudo().write({'state': 'waiting'})
            self._refresh_schedule(rollout)
            return {'ok': True, 'reason': 'waiting', 'until': decision[1]}
        if kind == 'pause':
            self._pause(rollout, decision[1])
            return {'ok': False, 'reason': decision[1]}
        if kind == 'done':
            rollout.sudo().write({'state': 'done', 'finished_at': now})
            rollout.log_line(_("Release %s is out.") % rollout.release_id.name)
            return {'ok': True, 'reason': 'done'}
        return {'ok': False, 'reason': 'nothing to do'}

    def _pause(self, rollout, reason):
        rollout.sudo().write({'state': 'paused', 'reason': reason})
        rollout.log_line(reason, 'error')
        _logger.warning("pb_tenants: rollout %s stopped: %s", rollout.id, reason)

    def _watch_probes(self, rollout, now):
        """Is the wave we are watching still healthy?

        Only asked while a watch period is actually running, and only of the
        customers that wave updated. A probe and a look at the log — no writes
        anywhere.
        """
        if rollout.state != 'waiting' or not rollout.ring_done_at:
            return []
        if not watch_hours_for(rollout.current_ring,
                               {'canary': rollout.watch_hours_canary,
                                'early': rollout.watch_hours_early}):
            return []
        out = []
        for task in rollout.task_ids:
            if task.ring != rollout.current_ring or task.state != 'done':
                continue
            if not task.tenant_id:
                continue
            # THE PROBE ONLY, AND DELIBERATELY. Straight after an update, an
            # error in the log is evidence the update broke something. A day
            # later it is evidence somebody typed something odd into a form,
            # and stopping a fleet-wide rollout for that would teach the owner
            # to ignore the watch period. What is being watched here is "is
            # this customer still answering".
            host = '%s.%s' % (task.tenant_id.slug, self._base_domain())
            code, ms = self._probe(host)
            ok, reason = health_verdict(code, 0, [])
            out.append({'name': task.label, 'ok': ok, 'reason': reason,
                        'ms': ms})
        return out

    # ------------------------------------------------------------ one task
    def _run_task(self, task):
        rollout = task.rollout_id
        started = fields.Datetime.now()
        task.sudo().write({'state': 'running', 'started_at': started,
                           'attempts': (task.attempts or 0) + 1,
                           'error': False})
        rollout.log_line(_("Updating %s…") % task.label)
        try:
            if task.ring == 'rehearsal':
                res, health = self._run_rehearsal(task, started)
            elif task.ring == 'template':
                res, health = self._run_template(task, started)
            else:
                res, health = self._run_tenant(task, started)
        except Exception as exc:                     # noqa: BLE001
            _logger.exception("pb_tenants: rollout task %s failed", task.id)
            msg = str(exc).strip().split('\n')[0][:400] or _("It did not finish.")
            self._finish_task(task, 'failed', {}, {}, msg, started)
            self._pause(rollout, _("%(who)s could not be updated: %(why)s",
                                   who=task.label, why=msg))
            return
        if health.get('ok'):
            self._finish_task(task, 'done', res, health, '', started)
            rollout.log_line(_("%(who)s is done (%(secs)ss).",
                               who=task.label,
                               secs=task.duration_s))
        else:
            self._finish_task(task, 'failed', res, health,
                              health.get('reason') or _("It did not look well "
                                                        "afterwards."), started)
            self._pause(rollout, _("%(who)s: %(why)s", who=task.label,
                                   why=health.get('reason') or ''))

    def _finish_task(self, task, state, result, health, error, started):
        end = fields.Datetime.now()
        task.sudo().write({
            'state': state, 'finished_at': end,
            'duration_s': int((end - started).total_seconds()),
            'result': json.dumps(result or {}, default=str)[:200000],
            'health': json.dumps(health or {}, default=str)[:60000],
            'error': error or False,
        })

    def _run_unit(self, target):
        """P1's whole "bring one database in step" unit, on one target.

        A method of its own so a test can replace it with something that does
        not need another database (T7).

        The release stamp is DEFERRED: the unit would normally tell the
        database it is on the new release the moment the install finishes, but
        in a rollout that announcement has to wait until the health checks have
        passed. A customer must never be shown "you are on release X — see
        what's new" about an update that is about to be called a failure.
        """
        return self.with_context(pb_defer_release_stamp=True).sync_bring_in_step(
            target, dry_run=False)

    def _run_rehearsal(self, task, started):
        """Rail R4: practise on a copy, then delete the copy. Always."""
        rollout = task.rollout_id
        src = task.source_tenant_id
        if not src:
            raise UserError(_("There is no customer to practise on."))
        res, health = {}, {}
        # THE RESTORE IS INSIDE THE `try`, and that is rail R4 rather than
        # tidiness: a restore that falls over half way leaves a part-built
        # database behind, and the `finally` below is the only thing that takes
        # it away again. With the restore outside, a broken backup left a
        # multi-gigabyte corpse on a box with 1.9 GB of memory.
        try:
            rollout.log_line(_("Restoring a throwaway copy of %s…") % src.name)
            try:
                restored = self.restore_staging(src.id)
            except Exception as exc:                 # noqa: BLE001
                # The framework's own words here are "Couldn't restore
                # database", which tells the owner nothing about what to do
                # next. The backup file is the thing to look at, and there is
                # a button that makes a fresh one.
                _logger.exception("pb_tenants: rehearsal restore failed")
                raise UserError(_(
                    "The practice copy of %(who)s could not be made from "
                    "their last backup — the file may be damaged or "
                    "half-written. Take a fresh backup of %(who)s (their "
                    "page, Backups, \"Backup now\") and try this step again. "
                    "Nothing has been done to %(who)s themselves.",
                    who=src.name)) from exc
            rollout.log_line(_("Copy restored from %s.")
                             % restored.get('from_backup', '?'))
            # THE CLOCK STARTS AFTER THE RESTORE, NOT BEFORE IT — and this cost
            # a rehearsal to learn. Restoring a database writes an ERROR of its
            # own ("bad query … FROM ir_module_module") because the framework
            # asks a half-built database what version it is on. That is the
            # restore talking, not the update, and counting it failed a
            # practice run whose copy was in perfect health. What is being
            # judged here is what the UPDATE did.
            since = fields.Datetime.now()
            res = self._run_unit(task.target_db)
            host = '%s.%s' % (task.target_db, self._base_domain())
            health = self._health_gate(task.target_db, since,
                                       res.get('skipped_count'), host)
        finally:
            # THE COPY GOES, WHATEVER HAPPENED. A failed rehearsal that left
            # a 2 GB database behind would cost the box its memory headroom on
            # the day it is least able to spare it.
            try:
                self.drop_staging(src.id)
                rollout.log_line(_("Practice copy deleted."))
            except Exception:                        # noqa: BLE001
                _logger.exception("pb_tenants: could not drop %s", task.target_db)
                rollout.log_line(_("The practice copy %s could NOT be deleted — "
                                   "drop it by hand.") % task.target_db, 'error')
        return res, health

    def _run_template(self, task, started):
        """The blank database new customers are made from. Nobody is looking."""
        res = self._run_unit('template')
        # No address, so no probe: the template is never served to anybody.
        health = self._health_gate(task.target_db, started,
                                   res.get('skipped_count'), None)
        # Rail R8, checked rather than assumed. The unit switches the jobs off;
        # this reads the database back and says what it found.
        crons, recorded = self._template_cron_state()
        res['template_active_crons'] = crons
        res['template_recorded_crons'] = recorded
        if crons and health.get('ok'):
            health['ok'] = False
            health['reason'] = _(
                "%s scheduled job(s) are still switched on in the template. A "
                "template with a live job wakes itself up and holds memory.") % crons
        task.rollout_id.log_line(
            _("Template checked: %(c)s scheduled job(s) still on, %(r)s "
              "recorded for new customers.", c=crons, r=recorded))
        return res, health

    def _template_cron_state(self):
        """How many of the template's jobs are on, and how many are written down."""
        db = self._template_db()
        try:
            with self._pg_cursor(db) as cr:
                cr.execute("SELECT count(*) FROM ir_cron WHERE active")
                active = cr.fetchone()[0]
                cr.execute("SELECT value FROM ir_config_parameter "
                           "WHERE key = 'pb_tenants.template_active_crons'")
                row = cr.fetchone()
                recorded = len([c for c in ((row and row[0]) or '').split(',')
                                if c.strip()])
            return active, recorded
        except Exception:                            # noqa: BLE001
            _logger.warning("pb_tenants: could not read the template's jobs",
                            exc_info=True)
            return -1, -1

    def _run_tenant(self, task, started):
        """A real customer: tell them, do it, check it, take the message down."""
        t = task.tenant_id
        rollout = task.rollout_id
        self._notice_now(task)
        try:
            res = self._run_unit(t.id)
            host = '%s.%s' % (t.slug, self._base_domain())
            health = self._health_gate(t.slug, started,
                                       res.get('skipped_count'), host)
        finally:
            # The "being updated right now" bar comes down whatever happened.
            # Leaving it up on a customer whose update failed would tell them
            # their payroll was mid-update for the rest of the week.
            try:
                self.notice_clear(t.id)
            except Exception:                        # noqa: BLE001
                _logger.warning("pb_tenants: could not take the bar down on %s",
                                t.slug, exc_info=True)
        if health.get('ok'):
            # ONLY NOW. The release stamp — and with it the "see what's new"
            # note their users get — is the last thing that happens, after the
            # checks have passed (deferred above).
            try:
                self._push_release_stamp(
                    t.id, {'release_state': res.get('release_state')},
                    rollout.release_id,
                    lambda line, level='info': rollout.log_line(line, level))
            except Exception:                        # noqa: BLE001
                _logger.warning("pb_tenants: could not stamp the release on %s",
                                t.slug, exc_info=True)
        return res, health

    def _notice_now(self, task):
        """The "being updated right now" bar."""
        t = task.tenant_id
        try:
            payload = notice_for('now', notice_id='ro%s-%s' % (task.rollout_id.id, task.id))
            self.notice_send(t.id, payload['kind'], payload['title'],
                             payload['text'], '', '',
                             live=bool(payload.get('live')))
        except Exception:                            # noqa: BLE001
            _logger.warning("pb_tenants: could not put the bar up on %s",
                            t.slug, exc_info=True)

    # ============================================================ pre-notices
    @api.model
    def _cron_rollout_notices(self):
        """Tell tomorrow's customers, the evening before.

        RAIL R1. This only ever speaks to a customer who is already on a list
        somebody made: a queued task, in a rollout a person started. It sends
        nothing to anybody else, and it installs nothing anywhere.
        """
        now = fields.Datetime.now()
        horizon = now + timedelta(hours=PRE_NOTICE_HOURS)
        tasks = self.env['pb.rollout.task'].sudo().search([
            ('state', '=', 'queued'),
            ('ring', 'in', list(CUSTOMER_RINGS)),
            ('notified_at', '=', False),
            ('rollout_id.state', 'in', ('running', 'waiting')),
        ])
        sent = 0
        for task in tasks:
            t = task.tenant_id
            if not t:
                continue
            tz, start, hours = self._task_window(task)
            opens, closes = window_bounds(now, tz, start, hours)
            if not task.run_now and opens > horizon:
                continue
            try:
                payload = notice_for('pre', opens, closes,
                                     'ro%s-%s-pre' % (task.rollout_id.id, task.id))
                self.notice_send(t.id, payload['kind'], payload['title'],
                                 payload['text'], payload['starts_at'],
                                 payload['ends_at'])
            except Exception:                        # noqa: BLE001
                _logger.warning("pb_tenants: could not warn %s", t.slug,
                                exc_info=True)
                continue
            task.write({'notified_at': now, 'scheduled_for': opens})
            task.rollout_id.log_line(
                _("%(who)s told their users the update is coming — %(when)s.",
                  who=task.label, when=render_range(opens, closes, now)))
            sent += 1
            self.env.cr.commit()
        return sent

    @api.model
    def _cron_rollout_worker(self):
        """Every five minutes: one step of whatever a person started.

        Does nothing at all when nobody has started anything, which is most of
        the time and is the point.
        """
        rollout = self._current_rollout()
        if not rollout:
            return False
        self._rollout_tick(rollout)
        self.env.cr.commit()
        return True

    # ============================================================ the controls
    def _get_rollout(self, rollout_id):
        r = self.env['pb.rollout'].sudo().browse(int(rollout_id)).exists()
        if not r:
            raise UserError(_("That rollout is not on the list any more."))
        return r

    @api.model
    def rollout_pause(self, rollout_id, reason=''):
        self._require_admin()
        r = self._get_rollout(rollout_id)
        if r.state not in ('running', 'waiting'):
            raise UserError(_("It is not running."))
        self._pause(r, (reason or '').strip()
                    or _("%s stopped it by hand.") % self.env.user.name)
        return self.rollout_state()

    @api.model
    def rollout_resume(self, rollout_id):
        """Carry on. A failed task has to be dealt with first, by name."""
        self._require_admin()
        r = self._get_rollout(rollout_id)
        if r.state != 'paused':
            raise UserError(_("It is not stopped."))
        stuck = r.task_ids.filtered(lambda t: t.state == 'failed')
        if stuck:
            raise UserError(_(
                "%(who)s is still marked failed. Try it again, or skip it, "
                "before carrying on — carrying on around a failure is how a "
                "customer gets forgotten.", who=stuck[0].label))
        r.sudo().write({'state': 'running', 'reason': False})
        r.log_line(_("%s carried on with it.") % self.env.user.name)
        self._rollout_tick(r)
        return self.rollout_state()

    @api.model
    def rollout_continue_now(self, rollout_id):
        """End the watch period early, on purpose, with a name against it."""
        self._require_admin()
        r = self._get_rollout(rollout_id)
        if r.state != 'waiting':
            raise UserError(_("Nothing is being watched right now."))
        r.sudo().write({'watch_skipped': True, 'state': 'running'})
        r.log_line(_("%(who)s ended the watch period on %(ring)s early.",
                     who=self.env.user.name,
                     ring=RING_LABEL.get(r.current_ring, r.current_ring)))
        self._rollout_tick(r)
        return self.rollout_state()

    def _get_task(self, task_id):
        t = self.env['pb.rollout.task'].sudo().browse(int(task_id)).exists()
        if not t:
            raise UserError(_("That step is not on the list any more."))
        return t

    @api.model
    def task_retry(self, task_id):
        self._require_admin()
        task = self._get_task(task_id)
        if task.state not in ('failed', 'skipped'):
            raise UserError(_("That step has not failed."))
        task.write({'state': 'queued', 'error': False})
        task.rollout_id.log_line(_("%(who)s put %(what)s back in the queue.",
                                   who=self.env.user.name, what=task.label))
        if task.rollout_id.state == 'paused':
            task.rollout_id.sudo().write({'state': 'running', 'reason': False})
        self._rollout_tick(task.rollout_id)
        return self.rollout_state()

    @api.model
    def task_skip(self, task_id, confirm=''):
        """Leave one database behind. A CUSTOMER has to be named to do it."""
        self._require_admin()
        task = self._get_task(task_id)
        if task.state in ('done', 'skipped'):
            raise UserError(_("Nothing to skip."))
        if task.tenant_id and (confirm or '').strip().lower() != task.tenant_id.slug:
            raise UserError(_(
                'Type "%s" to leave this customer behind. They will stay on '
                'the old release until somebody brings them in step.')
                % task.tenant_id.slug)
        task.write({'state': 'skipped'})
        task.rollout_id.log_line(
            _("%(who)s left %(what)s behind — it stays on the old release.",
              who=self.env.user.name, what=task.label), 'warn')
        if task.rollout_id.state == 'paused':
            task.rollout_id.sudo().write({'state': 'running', 'reason': False})
        self._rollout_tick(task.rollout_id)
        return self.rollout_state()

    @api.model
    def task_run_now(self, task_id):
        """Do not wait for their night. Recorded, because somebody chose it.

        IT SKIPS THE WINDOW, NOT THE QUEUE. The order of the waves is the whole
        safety argument of a rollout, so a customer in a later wave cannot be
        pulled forward with this — the way to move a wave along is to end its
        watch period on purpose, which is a different button with a different
        confirmation.
        """
        self._require_admin()
        task = self._get_task(task_id)
        if task.state != 'queued':
            raise UserError(_("That step is not waiting."))
        if task.ring != task.rollout_id.current_ring:
            raise UserError(_(
                "%(who)s is in a later wave (%(ring)s), and the waves happen "
                "in order — that is what makes a rollout safe. To get there "
                "sooner, end the watch period on the %(now)s with "
                "\"Continue now\".",
                who=task.label, ring=RING_LABEL.get(task.ring, task.ring),
                now=RING_LABEL.get(task.rollout_id.current_ring, '').lower()))
        task.write({'run_now': True, 'run_now_by': self.env.user.id})
        task.rollout_id.log_line(
            _("%(who)s asked for %(what)s to be updated now rather than in "
              "their own window.", who=self.env.user.name, what=task.label),
            'warn')
        self._rollout_tick(task.rollout_id)
        return self.rollout_state()

    @api.model
    def rollout_abort(self, rollout_id, confirm=''):
        """Call the whole thing off. Everything not yet done is left behind."""
        self._require_admin()
        r = self._get_rollout(rollout_id)
        if r.state in ('done', 'aborted'):
            raise UserError(_("It is already over."))
        if (confirm or '').strip() != r.release_id.name:
            raise UserError(_('Type "%s" to call this rollout off.')
                            % r.release_id.name)
        left = r.task_ids.filtered(lambda t: t.state in ('queued', 'failed'))
        left.write({'state': 'skipped'})
        r.sudo().write({'state': 'aborted', 'finished_at': fields.Datetime.now(),
                        'reason': _("%s called it off.") % self.env.user.name})
        r.log_line(_("%(who)s called it off — %(n)s database(s) left on the "
                     "old release.", who=self.env.user.name, n=len(left)), 'warn')
        return self.rollout_state()

    # ============================================================ the screen
    @api.model
    def rollout_state(self):
        """Everything the rings need. Read-only, and cheap enough to poll."""
        self._require_admin()
        R = self.env['pb.rollout'].sudo()
        rel = self.env['pb.release'].sudo().current()
        # WHAT "CURRENT" MEANS, AND WHY IT IS NOT "STILL RUNNING". A rollout
        # that has just finished is the thing the person watching it most wants
        # to see: "Release X is on 1 of 1 customers, took 14 minutes." Scoping
        # this to unfinished rollouts made the whole panel vanish the second
        # the last wave landed, and the screen went back to inviting them to
        # roll out a release they had just rolled out. So: whatever is still
        # going anywhere, else the last rollout OF THE CURRENT RELEASE, which
        # stays up until a new release is cut.
        current = R.search(
            [('state', 'in', ('running', 'waiting', 'paused', 'draft'))],
            order='id desc', limit=1)
        if not current and rel:
            current = R.search([('release_id', '=', rel.id)],
                               order='id desc', limit=1)
        past = R.search([('id', '!=', current.id or 0),
                         ('state', 'in', ('done', 'aborted'))], limit=8)
        return {
            'current': self._rollout_brief(current) if current else None,
            'past': [{
                'id': p.id, 'release': p.release_id.name, 'state': p.state,
                'when': (p.finished_at or p.create_date).isoformat(
                    sep=' ', timespec='minutes'),
                'minutes': self._rollout_minutes(p),
                'done': p.done_count, 'total': p.task_count,
            } for p in past],
            'release': ({'id': rel.id, 'name': rel.name,
                         'notes': rel.notes or ''} if rel else None),
            'ring_order': list(RING_ORDER),
            'ring_label': dict(RING_LABEL),
            'ring_meaning': dict(RING_MEANING),
        }

    @staticmethod
    def _rollout_minutes(r):
        if not r.started_at:
            return 0
        end = r.finished_at or fields.Datetime.now()
        return max(0, int((end - r.started_at).total_seconds() // 60))

    def _rollout_brief(self, r):
        now = fields.Datetime.now()
        rings = []
        for ring in RING_ORDER:
            tasks = r.task_ids.filtered(lambda t, ring=ring: t.ring == ring)
            if not tasks:
                continue
            rings.append({
                'ring': ring, 'label': RING_LABEL[ring],
                'meaning': RING_MEANING[ring],
                'active': r.current_ring == ring and r.state != 'done',
                'passed': RING_ORDER.index(ring) < RING_ORDER.index(r.current_ring or 'rehearsal'),
                'tasks': [self._task_brief(t) for t in tasks],
            })
        watch = watch_hours_for(r.current_ring,
                                {'canary': r.watch_hours_canary,
                                 'early': r.watch_hours_early})
        watch_until = None
        if r.state == 'waiting' and r.ring_done_at and watch and not r.watch_skipped:
            watch_until = r.ring_done_at + timedelta(hours=watch)
        upcoming = [t.scheduled_for for t in r.task_ids
                    if t.state == 'queued' and t.scheduled_for]
        next_at = min(upcoming) if upcoming else None
        return {
            'id': r.id, 'release': r.release_id.name,
            'notes': r.release_id.notes or '',
            'state': r.state,
            'state_label': dict(r._fields['state'].selection).get(r.state, r.state),
            'current_ring': r.current_ring,
            'current_ring_label': RING_LABEL.get(r.current_ring, ''),
            'reason': r.reason or '',
            'started_at': r.started_at and r.started_at.isoformat(sep=' ', timespec='minutes'),
            'finished_at': r.finished_at and r.finished_at.isoformat(sep=' ', timespec='minutes'),
            'minutes': self._rollout_minutes(r),
            'started_by': r.started_by.name or '',
            'rings': rings,
            'task_count': r.task_count, 'done_count': r.done_count,
            'failed_count': r.failed_count, 'queued_count': r.queued_count,
            'customer_total': r.customer_total, 'customer_done': r.customer_done,
            'watch_hours': watch,
            'watch_until': watch_until and watch_until.isoformat(sep=' ', timespec='minutes'),
            'watch_left_h': (max(0, round((watch_until - now).total_seconds() / 3600, 1))
                             if watch_until else 0),
            'watch_skipped': r.watch_skipped,
            'next_at': next_at and next_at.isoformat(sep=' ', timespec='minutes'),
            'log': r.log_rows()[-60:],
        }

    def _task_brief(self, t):
        health = t.health_dict()
        res = t.result_dict()
        return {
            'id': t.id, 'ring': t.ring, 'label': t.label,
            'target_db': t.target_db, 'state': t.state,
            'tenant_id': t.tenant_id.id or 0,
            'slug': t.tenant_id.slug or '',
            'initial': (t.label or '?')[0].upper(),
            'run_now': t.run_now,
            'notified_at': t.notified_at and t.notified_at.isoformat(sep=' ', timespec='minutes'),
            'scheduled_for': t.scheduled_for and t.scheduled_for.isoformat(sep=' ', timespec='minutes'),
            'started_at': t.started_at and t.started_at.isoformat(sep=' ', timespec='minutes'),
            'finished_at': t.finished_at and t.finished_at.isoformat(sep=' ', timespec='minutes'),
            'duration_s': t.duration_s, 'attempts': t.attempts,
            'error': t.error or '',
            'health_ok': health.get('ok'),
            'health_reason': health.get('reason', ''),
            'health': health,
            'added': len(res.get('installed') or []),
            'updated': len(res.get('updated') or []),
            'skipped_count': res.get('skipped_count', -1),
        }

    # ------------------------------------------------------ the Updates tab
    @api.model
    def tenant_updates(self, tenant_id):
        """One customer's wave, window and history of updates. Read-only."""
        self._require_admin()
        t = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not t:
            raise UserError(_("That customer is not on the list any more."))
        now = fields.Datetime.now()
        tz = self._tenant_tz(t)
        opens, closes = window_bounds(now, tz, t.maintenance_start or DEFAULT_START_HOUR,
                                      t.maintenance_hours or DEFAULT_HOURS)
        tasks = self.env['pb.rollout.task'].sudo().search(
            [('tenant_id', '=', t.id)], order='id desc', limit=40)
        return {
            'id': t.id, 'name': t.name, 'slug': t.slug,
            'ring': t.ring, 'ring_label': RING_LABEL.get(t.ring, ''),
            'ring_meaning': dict(RING_MEANING),
            'rings': [{'key': r, 'label': RING_LABEL[r], 'meaning': RING_MEANING[r]}
                      for r in CUSTOMER_RINGS],
            'maintenance_start': t.maintenance_start or DEFAULT_START_HOUR,
            'maintenance_hours': t.maintenance_hours or DEFAULT_HOURS,
            'tz': tz,
            'next_window': render_range(to_local(opens, tz),
                                        to_local(closes, tz),
                                        to_local(now, tz)),
            'next_window_at': opens.isoformat(sep=' ', timespec='minutes'),
            'release': t.release_id.name or '',
            'release_state': t.release_state,
            'tenancy_linked': self._tenancy_installed(t.slug),
            'history': [{
                **self._task_brief(task),
                'rollout_id': task.rollout_id.id,
                'release': task.rollout_id.release_id.name,
                'rollout_state': task.rollout_id.state,
            } for task in tasks],
        }

    @api.model
    def tenant_set_window(self, tenant_id, ring=None, start_hour=None, hours=None):
        """Which wave this customer is in, and when their night is."""
        self._require_admin()
        t = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not t:
            raise UserError(_("That customer is not on the list any more."))
        vals = {}
        if ring is not None:
            if ring not in CUSTOMER_RINGS:
                raise UserError(_("That is not one of the waves."))
            vals['ring'] = ring
        if start_hour is not None:
            h = int(start_hour)
            if not 0 <= h <= 23:
                raise UserError(_("The hour has to be between 0 and 23."))
            vals['maintenance_start'] = h
        if hours is not None:
            n = int(hours)
            if not 1 <= n <= 12:
                raise UserError(_("A window between 1 and 12 hours, please — "
                                  "longer than that is not a window."))
            vals['maintenance_hours'] = n
        if vals:
            t.write(vals)
            self._log_line(t, 'rollout', _(
                "Update settings changed: %(ring)s, %(hour)02d:00 for "
                "%(hours)s hours (%(tz)s).",
                ring=RING_LABEL.get(t.ring, t.ring),
                hour=t.maintenance_start, hours=t.maintenance_hours,
                tz=self._tenant_tz(t)))
        return self.tenant_updates(t.id)

    @api.model
    def tenant_update_now(self, tenant_id, dry_run=True):
        """Update this one customer, outside any rollout. Same unit, same guards."""
        self._require_admin()
        t = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not t:
            raise UserError(_("That customer is not on the list any more."))
        return self.sync_bring_in_step(t.id, dry_run=dry_run)
