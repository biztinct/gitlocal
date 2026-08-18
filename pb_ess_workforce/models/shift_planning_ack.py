# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Shift ACKNOWLEDGMENT on ``hr.shift.planning`` — the P4 descope, closed.

WHAT AN ACK IS
--------------
A published shift is a promise the company made TO somebody. Until P8 there was
no way for that somebody to say they had seen it, so a roster could be published
into silence and nobody found out until the shift was missed. ``ack_state`` is
the read receipt, and it has exactly two values because a read receipt has
exactly two values.

THE THREE FIELDS AND WHO MAY WRITE THEM
---------------------------------------
``ack_state`` / ``acked_at`` / ``ack_token`` are SENTINEL-GUARDED (C18.24): a
write is refused unless the context carries ``_ACK_TOKEN``, a module-level
``object()``. An ``object()`` identity cannot be expressed in JSON, so a crafted
``call_kw`` context cannot open the guard no matter what it contains — which is
what makes the login-less token URL safe to point at a sudo write. The three
legitimate writers are all in this file: publish mints, unpublish invalidates,
and the acknowledgment itself writes ``ack_state`` and ``acked_at`` AND NOTHING
ELSE. Not the state, not the times, not the employee.

ONE-TIME AND EXPIRING, WITHOUT DELETING THE TOKEN
-------------------------------------------------
``_ess_shift_for_token`` answers with a STATUS, not just a record, and only the
``ok`` status may write:

  ``invalid``  no shift carries that token (also: an empty token — a shift with
               ``ack_token = False`` must never be matched by an empty string,
               which is why the lookup refuses one before it searches);
  ``used``     the shift is already acknowledged. This is what makes the link
               one-time: the token stays on the record for the audit trail and
               simply stops being a door.
  ``expired``  the shift has already started. A confirmation that arrives after
               the shift began is not a confirmation of anything.
  ``stale``    the shift is no longer published (cancelled or pulled back to
               draft). Unpublishing MINTS A NEW TOKEN, so an old mailed link
               dies at that moment rather than confirming a shift that has since
               been withdrawn.

WHY THE TOKEN IS `groups='base.group_system'`
---------------------------------------------
The token is a credential. A field with a groups= restriction is stripped out of
every ORM read a non-member performs, so no cockpit payload, no export and no
``read()`` by a curious officer can ever hand somebody else's link over. The
writers here are sudo and are unaffected.
"""

import secrets

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# The sentinel (C18.24). Module-level identity — not a string, not a boolean,
# not anything JSON can carry.
_ACK_CTX = 'pb_ess_ack'
_ACK_TOKEN = object()

_ACK_FIELDS = frozenset({'ack_state', 'acked_at', 'ack_token'})

# 32 bytes of urandom, url-safe. `secrets.token_urlsafe` is the stdlib's
# cryptographic generator — `uuid4().hex` would also do, but a token is a
# credential and it should read like one at the call site.
_TOKEN_BYTES = 24

_PUBLISHED = 'published'


class HrShiftPlanningAck(models.Model):
    _inherit = 'hr.shift.planning'

    ack_state = fields.Selection([
        ('pending', 'Pending'),
        ('acked', 'Acknowledged'),
    ], string='Acknowledgment', default='pending', index=True, copy=False,
        readonly=True,
        help="Whether the employee has confirmed they have seen this shift.")
    acked_at = fields.Datetime(
        string='Acknowledged On', readonly=True, copy=False)
    ack_token = fields.Char(
        string='Acknowledgment Token', readonly=True, copy=False, index=True,
        groups='base.group_system',
        help="The credential behind this shift's login-less confirmation link. "
             "Restricted: it is never returned to a non-system reader.")

    # ------------------------------------------------------------- the guard
    def write(self, vals):
        """The three ack fields are writable ONLY through this file's helpers.

        Deliberately NOT relaxed for ``env.su`` or for the admin: the whole
        point is that there is exactly one code path, so an accidental
        ``shift.sudo().ack_state = 'acked'`` somewhere in a future phase fails
        loudly instead of quietly bypassing the audit stamp. Emergency shell
        surgery can still pass the context — it just has to say so.
        """
        touched = _ACK_FIELDS.intersection(vals)
        if touched and self.env.context.get(_ACK_CTX) is not _ACK_TOKEN:
            raise AccessError(_(
                "Shift acknowledgment (%(fields)s) is written only by the "
                "acknowledgment flow.", fields=', '.join(sorted(touched))))
        return super().write(vals)

    def _ess_ack_env(self):
        return self.sudo().with_context(**{_ACK_CTX: _ACK_TOKEN})

    # --------------------------------------------------------- mint / revoke
    def _ess_mint_tokens(self):
        """Give every record a FRESH token and reset it to pending.

        Called on publish (a shift becomes something to confirm) and on
        unpublish (the old mailed link must stop working). One token per shift:
        a per-week token would make a single leak confirm a whole roster, and a
        per-employee one would never expire.
        """
        for rec in self:
            rec._ess_ack_env().write({
                'ack_state': 'pending',
                'acked_at': False,
                'ack_token': secrets.token_urlsafe(_TOKEN_BYTES),
            })
        return True

    def action_publish(self):
        """Publish, then mint. The mint follows super() rather than preceding it
        so a shift that super() declined to publish (it was not draft) is not
        handed a token — the two can never disagree about what was published."""
        before = {r.id: r.state for r in self}
        res = super().action_publish()
        newly = self.filtered(
            lambda r: r.state == _PUBLISHED and before.get(r.id) != _PUBLISHED)
        if newly:
            newly._ess_mint_tokens()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        # A cancelled shift's link must die. Re-minting is the invalidation:
        # the record keeps a token shape (nothing downstream has to handle
        # False) while every link that was ever mailed stops resolving.
        self.filtered(lambda r: r.state == 'cancelled')._ess_mint_tokens()
        return res

    def action_reset_draft(self):
        res = super().action_reset_draft()
        self.filtered(lambda r: r.state == 'draft')._ess_mint_tokens()
        return res

    @api.model
    def _ess_backfill_tokens(self, limit=None):
        """Give already-published shifts a token. Idempotent; safe to re-run.

        Found by psql on the live world, not by a test: every gate was green
        and `tokens_minted` came back **0**. `action_publish` mints for the
        rows it moved from draft, which is exactly right — and it means a
        module installed onto a world whose roster was published LAST WEEK
        arrives with the token channel silently dead for every existing shift.
        Nothing errors: the portal ack still works, the badge still counts, and
        only the mailed link — the channel for the people who have no login,
        i.e. the ones the feature was built for — has nothing to point at.

        General form worth remembering: a feature that hooks a STATE TRANSITION
        only ever sees the future. If the records it is about already exist, the
        install has to catch them up, and the only way to notice is to count the
        live rows rather than to test the transition.

        Bounded to shifts that could still be acknowledged (published, and not
        yet started): back-filling history would mint thousands of credentials
        that can never be used, and a credential nobody needs is a credential
        somebody can leak.
        """
        domain = [('state', '=', _PUBLISHED),
                  ('ack_token', '=', False),
                  ('start_datetime', '>', fields.Datetime.now())]
        shifts = self.sudo().search(domain, limit=limit or None)
        for shift in shifts:
            shift._ess_ack_env().write({
                'ack_token': secrets.token_urlsafe(_TOKEN_BYTES),
            })
        return len(shifts)

    # ------------------------------------------------------------ the ack
    def _ess_can_ack(self, now=False):
        """The ONE predicate. The portal button, the token page and both write
        paths ask this same question, so a control can never offer what the
        server would refuse (W29)."""
        self.ensure_one()
        if self.state != _PUBLISHED or self.ack_state != 'pending':
            return False
        now = now or fields.Datetime.now()
        return bool(self.start_datetime and self.start_datetime > now)

    def _ess_ack(self, source='portal', now=False):
        """Write the acknowledgment. EXACTLY TWO FIELDS.

        Returns False (never raises) when the shift is not acknowledgeable, so a
        bulk "confirm week" over a mixed set is not an all-or-nothing gamble on
        the one shift that already started.
        """
        self.ensure_one()
        if not self._ess_can_ack(now=now):
            return False
        self._ess_ack_env().write({
            'ack_state': 'acked',
            'acked_at': now or fields.Datetime.now(),
        })
        # The chatter note is the human-readable trail and it is best-effort:
        # a mail.thread hiccup must never lose an acknowledgment the employee
        # believes they gave.
        try:
            self.sudo().message_post(
                body=_("Shift acknowledged by the employee (%s).", source),
                subtype_xmlid='mail.mt_note')
        except Exception:                                     # pragma: no cover
            pass
        return True

    # ------------------------------------------------------- token lookup
    @api.model
    def _ess_shift_for_token(self, token):
        """(shift, status) for a login-less token. See the module docstring.

        The empty-token refusal is first and it is not a formality: without it
        ``search([('ack_token', '=', '')])`` would match nothing today and every
        token-less shift the day somebody stores '' instead of False.
        """
        token = (token or '').strip()
        if not token or len(token) < 16:
            return (self.browse(), 'invalid')
        shift = self.sudo().search([('ack_token', '=', token)], limit=1)
        if not shift:
            return (self.browse(), 'invalid')
        if shift.state != _PUBLISHED:
            return (shift, 'stale')
        if shift.ack_state == 'acked':
            return (shift, 'used')
        if not shift.start_datetime or shift.start_datetime <= fields.Datetime.now():
            return (shift, 'expired')
        return (shift, 'ok')

    @api.model
    def _ess_ack_by_token(self, token):
        """Acknowledge from the token URL. The only public-reachable writer."""
        shift, status = self._ess_shift_for_token(token)
        if status != 'ok':
            return (shift, status)
        shift._ess_ack('link')
        return (shift, 'acked')
