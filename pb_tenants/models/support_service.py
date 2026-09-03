# -*- coding: utf-8 -*-
"""FLEET P6 — "Open as support", from the platform's side.

THREE CALLS AND NOTHING ELSE.

    support_open(tenant, reason, minutes)  writes a one-time row on the
                                           customer's database and hands back a
                                           link that is good for a minute
    support_history(tenant)                reads their trail, so the owner sees
                                           the same record they do
    support_end(tenant, id)                ends a session from here

WHAT THIS FILE CANNOT DO, DELIBERATELY. It cannot open a customer who has
switched support access off, and there is no argument, setting or second button
that changes that. The switch is read from THEIR database on every press. That
is the whole product: a promise with a way round it is not a promise, and the
customer's own page says so in as many words.

RAIL R1 — never a silent write to a customer's database. Every one of the three
is a person pressing a button; each writes a line into the customer's own
provisioning log; and opening one raises an alert AND emails it at once, rather
than waiting for the fifteen-minute sweep — a session can be over before the
sweep next looks, and the owner would then never hear about it at all. Access to
somebody's payroll is never quiet.

RAIL R5 — the write goes through `_tenant_env`, so the customer's running
registry is told about it and the login seam sees the row on the very next
request (and, since P5, `signal_changes()` means that holds from a shell too —
ledger F56).
"""
import json
import logging
import secrets

import odoo

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.pb_tenancy.models.support import token_digest

from .sync_rules import is_never
from .support_rules import (
    ALLOWED_MINUTES, DEFAULT_MINUTES, DURATIONS, customer_blocker,
    session_sentence, support_refusal,
)

_logger = logging.getLogger(__name__)

#: The setting on the customer's database that holds their switch. Repeated
#: here rather than imported from `pb_tenancy`, which the master DOES have —
#: but the string is a contract between two databases, and a contract is
#: clearer written out at both ends.
T_SUPPORT_ALLOWED = 'pb_tenancy.support_allowed'

#: How many past sessions the cockpit shows for one customer.
HISTORY_LIMIT = 25


class PbTenantsSupport(models.AbstractModel):
    _inherit = 'pb.tenants'

    # ------------------------------------------------------------- the switch
    def _support_allowed_on(self, dbname):
        """Has this customer switched us off? Read-only SQL on their database.

        A PLAIN CURSOR, NOT `_tenant_env`. Opening a registry on another
        database costs about five megabytes and a second (ledger F34) and this
        question is asked every time somebody opens a customer's page. It is one
        settings row, it is a read, and rail R5 is about WRITES.

        ABSENT MEANS YES, exactly as it does on their side: a customer nobody
        has ever asked still gets help when they ring up.
        """
        try:
            with self._pg_cursor(dbname) as cr:
                cr.execute("SELECT to_regclass('public.ir_config_parameter')")
                if not (cr.fetchone() or [None])[0]:
                    return True
                cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s",
                           (T_SUPPORT_ALLOWED,))
                row = cr.fetchone()
        except Exception:                                    # noqa: BLE001
            _logger.warning("pb_tenants: could not read the support switch on "
                            "%s", dbname, exc_info=True)
            # THE ONE PLACE THIS FAILS CLOSED. Everything about a customer's own
            # standing fails open, because the cost of being wrong is a payroll
            # office locked out. Here the cost of being wrong is opening
            # somebody's data against their wishes, so an unreadable answer is
            # a no.
            return False
        value = (row[0] if row else '') or ''
        return value.strip().lower() not in ('0', 'off', 'false', 'no')

    # -------------------------------------------------------------- the trail
    def _support_rows_on(self, dbname, limit=HISTORY_LIMIT):
        """Their record, read straight off their database. Read-only SQL."""
        out = []
        try:
            with self._pg_cursor(dbname) as cr:
                cr.execute("SELECT to_regclass('public.pb_support_access')")
                if not (cr.fetchone() or [None])[0]:
                    return out
                cr.execute(
                    "SELECT id, state, support_name, reason, issued_at, "
                    "used_at, ended_at, session_expires_at, duration_minutes, "
                    "source_ip, route_log, ended_by, refused_reason "
                    "FROM pb_support_access "
                    "ORDER BY issued_at DESC NULLS LAST, id DESC LIMIT %s",
                    (int(limit),))
                for r in cr.fetchall():
                    try:
                        log = json.loads(r[10] or '[]')
                    except (ValueError, TypeError):
                        log = []
                    out.append({
                        'id': r[0], 'state': r[1],
                        'who': r[2] or _("Payobook support"),
                        'reason': r[3] or '',
                        'issued_at': _iso(r[4]), 'used_at': _iso(r[5]),
                        'ended_at': _iso(r[6]),
                        'session_expires_at': _iso(r[7]),
                        'minutes': r[8] or 0, 'source_ip': r[9] or '',
                        'screens': [s for s in log if isinstance(s, dict)],
                        'ended_by': r[11] or '',
                        'refused_reason': r[12] or '',
                    })
        except Exception:                                    # noqa: BLE001
            _logger.warning("pb_tenants: could not read the support trail on "
                            "%s", dbname, exc_info=True)
        return out

    # ------------------------------------------------- what the screen draws
    def _support_brief(self, tenant):
        """One customer's support standing, for the Overview row.

        Two facts and a refusal sentence, so the button and the words beside it
        can never disagree: the screen never composes its own reason.
        """
        if tenant.state in ('decommissioned', 'draft', 'provisioning', 'error'):
            return {'allowed': False, 'linked': False, 'live': None,
                    'pending': False,
                    'rows': [], 'blocked': _(
                        "This customer has no live database to open."),
                    'durations': _durations()}
        linked = self._tenancy_installed(tenant.slug)
        allowed = linked and self._support_allowed_on(tenant.slug)
        rows = self._support_rows_on(tenant.slug) if linked else []
        live = next((r for r in rows if r['state'] == 'active'), None)
        return {
            'allowed': bool(allowed),
            'linked': bool(linked),
            'live': live,
            # A LINK THAT HAS BEEN SENT BUT NOT YET FOLLOWED IS STILL SOMETHING
            # IN FLIGHT. Reading it as "nothing is happening" closed the alert
            # about a session in the second between the button and the tab
            # opening — so the owner's own screen said a session had finished
            # before it had begun.
            'pending': bool([r for r in rows
                             if r['state'] in ('issued', 'active')]),
            'rows': rows,
            'blocked': customer_blocker(tenant.state, linked, allowed) or '',
            'durations': _durations(),
        }

    @api.model
    def support_history(self, tenant_id):
        """The customer's own record, read by the platform. RECONCILES TOO.

        A session that ended by itself — the clock ran out, or somebody pressed
        Leave — is news only their database has. So the informational alert this
        phase raises is closed here, when the platform next looks and sees that
        nothing is running. Nothing else on the platform can know.
        """
        self._require_admin()
        tenant = self._tenant(tenant_id)
        brief = self._support_brief(tenant)
        if not brief.get('pending'):
            self._clear_alert('support_session:%s' % tenant.slug,
                              _("The support session finished."))
        return brief

    # ============================================================ opening one
    @api.model
    def support_open(self, tenant_id, reason, minutes=DEFAULT_MINUTES,
                     on_staging=False):
        """Write a one-time row on the customer's database and return the link.

        THE LINK IS GOOD FOR SIXTY SECONDS, so the cockpit opens it itself, in a
        new tab, the moment this returns. It is never emailed, never copied to a
        clipboard and never shown on a screen — a link somebody can paste is a
        link somebody can paste to the wrong person.

        THE TOKEN IS NOT KEPT HERE EITHER. It exists in this method's local
        variable and in the URL that goes back to the browser. What is stored,
        on their side only, is its SHA-256.

        `on_staging` OPENS THE PRACTICE COPY INSTEAD (rail R4). Every phase in
        this programme rehearses on `<slug>-staging` before it touches a real
        customer, and `sync_bring_in_step` has taken that target since P1
        (ledger F12). This is the same door for this button: same code, same
        row, same login seam, on a throwaway copy of their data — and nobody is
        alerted, because nobody's real data was opened.
        """
        self._require_admin()
        tenant = self._tenant(tenant_id)
        reason = (reason or '').strip()
        try:
            minutes = int(minutes or DEFAULT_MINUTES)
        except (TypeError, ValueError):
            minutes = DEFAULT_MINUTES
        dbname = tenant.slug
        if on_staging:
            dbname = '%s-staging' % tenant.slug
            if not self._db_exists(dbname):
                raise UserError(_(
                    "There is no practice copy of this customer to open. Make "
                    "one on the Backups tab first — \"Restore latest → "
                    "staging\"."))
        linked = self._tenancy_installed(dbname)
        allowed = linked and self._support_allowed_on(dbname)
        refusal = support_refusal(tenant.state, linked, allowed, reason, minutes)
        if refusal:
            raise UserError(refusal)

        # Belt and braces on top of the customer row (rail R2): the literal
        # database about to be written is re-asked the never question, because
        # that list is what actually runs.
        if dbname == self.env.cr.dbname or is_never(dbname):
            raise UserError(_(
                "This is the platform's own database. Support sessions are "
                "opened ON customers, not on it."))

        token = secrets.token_urlsafe(32)
        name = self.env.user.name or self.env.user.login
        notes = []

        def say(line, level='info'):
            notes.append(line)

        with self._tenant_env(dbname) as env:
            # THE RECOVERY ACCOUNT IS MADE SURE OF FIRST, and it is not a
            # formality: `abm` was adopted rather than provisioned, so the rails
            # never ran there and the account genuinely was not present on the
            # fleet's only live customer. Without this the very first support
            # session would have failed at the login with nothing to explain it.
            self._ensure_break_glass(env, say)
            env['pb.support.access'].issue(
                token_digest(token), reason, name, minutes)
        for note in notes:
            self._log_line(tenant, 'support', note)
        label = (_("%s (practice copy)") % tenant.name) if on_staging \
            else tenant.name
        sentence = session_sentence(name, label, minutes)
        self._log_line(tenant, 'support', '%s Reason: %s' % (sentence, reason))
        # NO ALERT FOR A PRACTICE RUN. The alert exists because access to a
        # customer's real payroll is never allowed to be quiet; a throwaway copy
        # is not their payroll, and an alert about one would teach the owner to
        # scroll past the ones that matter.
        if not on_staging:
            alert = self._raise_alert(
                'support_session:%s' % tenant.slug, 'support_session', 'info',
                _("Payobook support opened %s") % tenant.name,
                _('%s Reason given: "%s". It is written on their own screen '
                  'under Settings > About Payobook > Support access, where '
                  'their administrator can read it.') % (sentence, reason),
                tenant=tenant)
            self._support_speak_now(alert)
        url = '%s/pb_tenancy/support/%s' % (self._tenant_url(dbname), token)
        _logger.info("pb_tenants: %s", sentence)
        return {'ok': True, 'url': url, 'minutes': minutes,
                'staging': bool(on_staging),
                'data': self._support_brief(tenant)}

    def _support_speak_now(self, alert):
        """Say it AT ONCE, not on the next sweep.

        THE FIFTEEN-MINUTE SWEEP IS THE WRONG CHANNEL FOR THIS ONE. Everything
        else it mails is a fault that will still be a fault in a quarter of an
        hour; a support session is a THING THAT JUST HAPPENED, and it may well
        be over before the sweep next looks — which is exactly what happened the
        first time this was tried, and the owner heard nothing at all about a
        session on a live customer. So the mail goes out here, on the press of
        the button, and the row is stamped as told so the sweep does not repeat
        it.

        THE STAMP IS WRITTEN ONLY IF THE MESSAGE WENT (ledger F40): a failed
        send leaves the row un-stamped, so the sweep chases it fifteen minutes
        later rather than the whole thing falling silent.

        AND IT NEVER STOPS THE SESSION. A mail server that is down is not a
        reason to refuse somebody help with their payroll — the record on the
        customer's own database is written either way, and that is the part
        that matters.
        """
        if not alert:
            return False
        # NOT DURING A TEST RUN. The suite opens sessions against a fabricated
        # customer inside a transaction that is thrown away — but an email is
        # not in that transaction, and every one of those attempts wrote an
        # ERROR line into the server log on a live box. That log is what the
        # rollout health gate reads (ledger F25), so a suite that fills it with
        # its own noise is a suite that stops the next release. Guarded at the
        # SENDER rather than in each test, exactly as F44 guards the status page.
        if odoo.tools.config['test_enable']:
            return False
        try:
            made = self._mail_new_alerts(alert)
            if not made:
                return False
            res = self._send_alert_mail(made[0], made[1], kind='alert')
            if res.get('ok'):
                alert.write({'notified_at': fields.Datetime.now(),
                             'notified_severity': alert.severity})
                return True
        except Exception:                                    # noqa: BLE001
            _logger.warning("pb_tenants: the support session was opened but "
                            "the note about it could not be sent",
                            exc_info=True)
        return False

    # ============================================================ ending one
    @api.model
    def support_end(self, tenant_id, access_id=None, on_staging=False):
        """End a session from here. Their next click meets the finished page."""
        self._require_admin()
        tenant = self._tenant(tenant_id)
        dbname = ('%s-staging' % tenant.slug) if on_staging else tenant.slug
        if not self._tenancy_installed(dbname):
            raise UserError(_("There is nothing to end on this customer."))
        ended = 0
        with self._tenant_env(dbname) as env:
            Row = env['pb.support.access'].sudo()
            rows = (Row.browse(int(access_id)).exists() if access_id
                    else Row.search([('state', '=', 'active')]))
            rows = rows.filtered(lambda r: r.state in ('issued', 'active'))
            ended = len(rows)
            rows.end(_("Payobook ended it from the platform"))
        if ended:
            self._log_line(tenant, 'support', _(
                "%s ended the support session from the platform.")
                % (self.env.user.name or self.env.user.login))
        self._clear_alert('support_session:%s' % tenant.slug,
                          _("The support session was ended from the platform."))
        return {'ok': True, 'ended': ended,
                'data': self._support_brief(tenant)}


def _durations():
    return [{'minutes': m, 'label': l, 'blurb': b} for m, l, b in DURATIONS]


def _iso(value):
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else ''


# Re-exported so the cockpit's tests and any later caller can reach the three
# lengths without importing a rules module by path.
SUPPORT_DURATIONS = ALLOWED_MINUTES
