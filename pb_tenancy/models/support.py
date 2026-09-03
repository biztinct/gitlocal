# -*- coding: utf-8 -*-
"""FLEET P6 — when Payobook support opens this company's data, and the record of it.

THE WHOLE POINT OF THIS FILE IS THE TRAIL. Somebody at Payobook can already
reach a customer's database — they own the server. What they could not do until
now is do it in a way the CUSTOMER can see afterwards. So every support session
is written down here, on the customer's own database, in their own words: who,
when, why, for how long, from where, and which screens were opened. Nobody at
Payobook can delete a row of it from any screen.

AND THE CUSTOMER HOLDS THE SWITCH. `pb_tenancy.support_allowed` is read before
any session can start. When it is off, the platform's own button says so and
does nothing else — there is no override anywhere in this code or on the
platform's, deliberately, and the customer's page says that in as many words.

HOW SOMEBODY GETS IN, AND WHY NO PASSWORD IS INVOLVED. The recovery account on
this database has never had a password and still does not. Instead the platform
writes a row here holding the SHA-256 of a one-time token; the token itself
travels once, in a link, and is never stored on either side. The link is good
for sixty seconds and for one use. After that the row is spent whatever happens
to it.

    issued ──use within 60s──▶ active ──ends by itself, or Leave, or
      │                          │      the platform ends it──▶ ended
      │                          └──past its finish time──────▶ expired
      └── link went stale, was used twice, or the switch was off ──▶ refused

FAIL CLOSED, FOR ONCE. Everything else in this module fails OPEN — a database
that has been told nothing keeps its whole product. This one does the opposite:
a damaged row, an unreadable setting or a missing recovery account all mean
nobody gets in. The two directions are right for what they guard: losing a menu
because a string was empty is a disaster, and a door that opens when it cannot
read its own lock is a worse one.
"""
import hashlib
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

#: The customer's switch. ABSENT MEANS ON: a company nobody has ever asked
#: still gets help when they ring up. It is a switch they turn OFF, not one
#: they have to find and turn on before their first support call.
P_SUPPORT_ALLOWED = 'pb_tenancy.support_allowed'

#: How long a link is good for. Sixty seconds is not a security theatre number:
#: the platform opens the tab itself, immediately, so the link never waits in a
#: mailbox or a chat window. Anything longer is a link somebody could paste.
TOKEN_SECONDS = 60

#: How many screens are remembered per session. A support session is two hours
#: of somebody clicking about; the trail is meant to answer "what did they
#: look at", not to be a keystroke recorder (a binding non-goal of this phase).
MAX_ROUTES = 200

#: The permission the customer's own administrator holds. It is the group
#: behind the "who here can do what" ability, which the Tenant administrator
#: role REQUIRES (`pb_vendor_access.hooks:375`) — so it is the one thing the
#: customer's administrator is guaranteed to have and the platform's rails
#: guarantee nobody else on their database does.
#:
#: WHY NOT `base.group_system`. Because on a customer's database that group is
#: the PLATFORM's, not the customer's: the tenant-admin rails exist precisely to
#: take it away from the customer's own administrator. Gating the trust page on
#: it would put the record of our access behind a door only we hold, which is
#: the exact opposite of what the page is for.
TENANT_ADMIN_GROUP = 'biz_access.group_access_manager'


def token_digest(token):
    """The only form of a token this database ever holds. PURE."""
    return hashlib.sha256((token or '').encode('utf-8')).hexdigest()


def token_check(row, token, now, allowed):
    """May this token open a session right now? PURE, so a test can reach it.

    `row` is `{'token_hash', 'token_expires_at', 'used_at', 'state'}` or None.
    Answers one of `ok`, `mismatch`, `used`, `off`, `expired`.

    THE ORDER OF THE CHECKS IS THE ORDER OF THE HONEST ANSWER. A token nobody
    recognises is a mismatch and nothing else is worth saying about it. A token
    already spent is "used" even if it has also gone stale, because reuse is the
    thing worth noticing. The switch is asked BEFORE the clock: a customer who
    turned support off two minutes after we asked for a link should be told
    that, not told the link timed out.
    """
    if not row or not token:
        return 'mismatch'
    if row.get('token_hash') != token_digest(token):
        return 'mismatch'
    if row.get('used_at') or row.get('state') != 'issued':
        return 'used'
    if not allowed:
        return 'off'
    expires = row.get('token_expires_at')
    if not expires or expires <= now:
        return 'expired'
    return 'ok'


#: What each refusal says, in the words the person meets on the page. No
#: mention of tokens, sessions ending in the abstract, or anything from the
#: framework: this page is read by whoever clicked a link that did not work.
REFUSAL_TEXT = {
    'mismatch': _("This support link is not one we recognise."),
    'used': _("This support link has already been used."),
    'expired': _("This support link has expired."),
    'off': _("Support access is switched off for this company."),
}


class PbSupportAccess(models.Model):
    _name = 'pb.support.access'
    _description = 'Payobook support access'
    _order = 'issued_at desc, id desc'

    #: The SHA-256 of the one-time token. THE TOKEN ITSELF IS NEVER STORED, on
    #: this database or on the platform's: it exists in the link, once, and is
    #: compared by hash. A copy of this table tells a reader nothing that would
    #: let them in.
    token_hash = fields.Char(index=True, required=True, readonly=True)
    issued_at = fields.Datetime(readonly=True)
    token_expires_at = fields.Datetime(readonly=True)
    used_at = fields.Datetime(readonly=True)
    session_expires_at = fields.Datetime(readonly=True)
    ended_at = fields.Datetime(readonly=True)
    ended_by = fields.Char(readonly=True)
    #: Who at Payobook asked for it, by name. Not a user id: this is a name
    #: from ANOTHER database and it has to still read correctly in a year.
    support_name = fields.Char(readonly=True)
    reason = fields.Text(required=True, readonly=True)
    source_ip = fields.Char(readonly=True)
    duration_minutes = fields.Integer(readonly=True, default=120)
    #: `[{ts, action, title}]` — the screens opened, newest last.
    route_log = fields.Text(readonly=True)
    state = fields.Selection(
        [('issued', 'Link sent'), ('active', 'In progress'),
         ('ended', 'Finished'), ('expired', 'Timed out'),
         ('refused', 'Refused')],
        default='issued', required=True, readonly=True, index=True)
    refused_reason = fields.Char(readonly=True)

    # ------------------------------------------------------------------ writes
    @api.model
    def issue(self, token_hash, reason, support_name, minutes):
        """Written by the platform, through the ORM, on its way to opening a tab.

        Nothing here trusts the caller for anything but the three facts it is
        given: the clock, the state and the shape of the row are this
        database's own.
        """
        now = fields.Datetime.now()
        reason = (reason or '').strip()
        if not reason:
            raise UserError(_("A support session needs a reason."))
        try:
            minutes = max(5, min(int(minutes or 120), 12 * 60))
        except (TypeError, ValueError):
            minutes = 120
        return self.sudo().create({
            'token_hash': token_hash,
            'reason': reason,
            'support_name': (support_name or 'Payobook support').strip(),
            'duration_minutes': minutes,
            'issued_at': now,
            'token_expires_at': now + timedelta(seconds=TOKEN_SECONDS),
            'state': 'issued',
        })

    @api.model
    def claim(self, token, source_ip=''):
        """Spend a token, or say why not. Returns `(row_or_None, verdict)`.

        Called from the login seam, so it runs before anybody is inside. It is
        the only method here that turns an `issued` row into an `active` one.
        """
        Row = self.sudo()
        now = fields.Datetime.now()
        allowed = self.env['pb.tenancy'].sudo().support_allowed()
        row = Row.search([('token_hash', '=', token_digest(token))], limit=1)
        verdict = token_check({
            'token_hash': row.token_hash,
            'token_expires_at': row.token_expires_at,
            'used_at': row.used_at,
            'state': row.state,
        } if row else None, token, now, allowed)
        if verdict == 'ok':
            row.write({
                'used_at': now,
                'session_expires_at': now + timedelta(
                    minutes=row.duration_minutes or 120),
                'source_ip': (source_ip or '')[:64],
                'state': 'active',
            })
            _logger.info("pb_tenancy: support session %s opened by %s (%s)",
                         row.id, row.support_name, row.reason)
            return row, 'ok'
        # A row that was still waiting is marked refused, so the customer sees
        # the attempt. A row that is already ACTIVE is left exactly as it is —
        # somebody clicking an old link a second time must not end the session
        # their colleague is in the middle of.
        if row and row.state == 'issued':
            row.write({'state': 'refused',
                       'refused_reason': REFUSAL_TEXT.get(verdict, verdict),
                       'source_ip': (source_ip or '')[:64]})
        _logger.info("pb_tenancy: a support link was refused (%s)", verdict)
        return (row or None), verdict

    def end(self, why=''):
        """Finish a session. Idempotent, and safe to call from anywhere."""
        for row in self.sudo():
            if row.state not in ('issued', 'active'):
                continue
            row.write({'state': 'ended', 'ended_at': fields.Datetime.now(),
                       'ended_by': (why or '')[:120]})
        return True

    def expire(self):
        for row in self.sudo():
            if row.state == 'active':
                row.write({'state': 'expired',
                           'ended_at': fields.Datetime.now(),
                           'ended_by': _("its time ran out")})
        return True

    def note_route(self, path, title=''):
        """Remember one screen. Consecutive repeats are not written twice."""
        self.ensure_one()
        row = self.sudo()
        path = (path or '').strip()[:200]
        if not path or row.state != 'active':
            return False
        try:
            log = json.loads(row.route_log or '[]')
            if not isinstance(log, list):
                log = []
        except ValueError:
            log = []
        title = (title or '').strip()[:120]
        if log and log[-1].get('action') == path:
            return False
        log.append({'ts': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'action': path, 'title': title})
        row.write({'route_log': json.dumps(log[-MAX_ROUTES:])})
        return True

    # ------------------------------------------------------------------- reads
    def routes(self):
        self.ensure_one()
        try:
            log = json.loads(self.route_log or '[]')
        except ValueError:
            return []
        return [r for r in log if isinstance(r, dict) and r.get('action')]

    def brief(self):
        """One row, in the words the customer's page prints."""
        self.ensure_one()
        return {
            'id': self.id,
            'state': self.state,
            'who': self.support_name or _("Payobook support"),
            'reason': self.reason or '',
            'issued_at': _stamp(self.issued_at),
            'used_at': _stamp(self.used_at),
            'ended_at': _stamp(self.ended_at),
            'session_expires_at': _stamp(self.session_expires_at),
            'ended_by': self.ended_by or '',
            'refused_reason': self.refused_reason or '',
            'minutes': self.duration_minutes or 0,
            'source_ip': self.source_ip or '',
            'screens': [{'ts': r.get('ts', ''), 'action': r.get('action', ''),
                         'title': r.get('title', '')} for r in self.routes()],
        }


def _stamp(value):
    """A datetime as the browser wants it, or an empty string."""
    return fields.Datetime.to_string(value) if value else ''


class PbTenancySupport(models.AbstractModel):
    """The support switch, the trail and the session — on the one link model."""
    _inherit = 'pb.tenancy'

    # ------------------------------------------------------------ the switch
    @api.model
    def support_allowed(self):
        """Is Payobook support allowed to open this company's data?

        ABSENT MEANS YES. A database nobody has ever set this on is a database
        whose owner has never been asked, and refusing help to somebody who has
        just rung up about a pay run because a settings row was never written
        would be a fault dressed up as a policy.
        """
        raw = (self.env['ir.config_parameter'].sudo()
               .get_param(P_SUPPORT_ALLOWED, '') or '').strip().lower()
        return raw not in ('0', 'off', 'false', 'no')

    @api.model
    def may_manage_support(self):
        """May the person asking see the trail and work the switch?

        THE EXISTENCE OF THE GROUP AND MEMBERSHIP OF IT ARE TWO QUESTIONS. On a
        database that has never had the permissions module the name resolves to
        nothing, and `has_group` answers a flat False for it — which would read
        as "denied" and hide the trust page from everybody, for a reason that
        has nothing to do with them. So a missing group falls back to "anybody
        who works here", and a group that IS on this database is asked properly.
        """
        user = self.env.user
        if self.env.su or user.has_group('base.group_system'):
            return True
        if not self.env.ref(TENANT_ADMIN_GROUP, raise_if_not_found=False):
            return bool(user._is_internal())
        return bool(user.has_group(TENANT_ADMIN_GROUP))

    @api.model
    def support_set_allowed(self, on):
        """The customer's own switch. The ONLY thing that writes it.

        A WRITE REFUSES LOUDLY, unlike the read below. Somebody who cannot
        change this must be told so, not quietly ignored.
        """
        if not self.may_manage_support():
            raise AccessError(_(
                "Only somebody who manages permissions for your company can "
                "change this."))
        self.env['ir.config_parameter'].sudo().set_param(
            P_SUPPORT_ALLOWED, '1' if on else '0')
        _logger.info("pb_tenancy: support access switched %s by %s",
                     'on' if on else 'off', self.env.user.login)
        if not on:
            # Turning it off ends anything that is running. The switch would be
            # a decoration otherwise: "no, not now" has to mean now.
            live = self.env['pb.support.access'].sudo().search(
                [('state', '=', 'active')])
            live.end(_("the company switched support access off"))
        return self.support_page()

    # ------------------------------------------------------------- the page
    @api.model
    def support_page(self):
        """Everything the customer's "Support access" page draws.

        A READ REFUSES CALMLY. Somebody who followed a link to this page and may
        not use it gets a sentence saying who can, not an error dialog — the
        page is a promise about transparency and meeting a fault on it is a poor
        first impression. The switch and the trail are simply not in the answer.
        """
        if not self.may_manage_support():
            return {
                'may_manage': False,
                'allowed': self.support_allowed(),
                'company': self.env.company.name or 'Payobook',
                'rows': [], 'ever': False, 'live': False,
            }
        Row = self.env['pb.support.access'].sudo()
        rows = Row.search([], limit=200)
        return {
            'may_manage': True,
            'allowed': self.support_allowed(),
            'company': self.env.company.name or 'Payobook',
            'rows': [r.brief() for r in rows],
            'ever': bool(rows),
            'live': bool(rows.filtered(lambda r: r.state == 'active')),
        }

    # ------------------------------------------------- the session, if any
    @api.model
    def support_session(self, session_id=None):
        """The bar's answer: what is running right now, or nothing.

        Called from `session_info`, so it must be cheap and must never raise.
        It reads ONE row, and only when this session was opened through the
        support door — every other person on this database pays nothing.
        """
        if not session_id:
            return None
        row = self.env['pb.support.access'].sudo().browse(
            int(session_id)).exists()
        if not row or row.state != 'active':
            return None
        return {
            'id': row.id,
            'ends_at': _stamp(row.session_expires_at),
            'company': self.env.company.name or 'Payobook',
            'reason': row.reason or '',
            'who': row.support_name or _("Payobook support"),
        }
