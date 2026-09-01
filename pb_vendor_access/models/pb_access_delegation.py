# -*- coding: utf-8 -*-
"""`pb.access.delegation` — one person's access, lent to another, and taken back
by the calendar rather than by somebody remembering.

THE WHOLE MODEL IN FOUR SENTENCES.
A delegation names who is lending, who is borrowing, which profiles, and until
when. Activating it adds the profiles' groups to the borrower — and NEVER a
group the lender does not hold themselves. What it actually added is written
down, exactly, on the record. Ending it removes precisely those groups and
nothing else.

WHY THE SNAPSHOT IS THE WHOLE DESIGN.
"Remove the profiles' groups at the end" is the obvious implementation and it is
wrong in both directions. It over-removes: a borrower who already held one of
those groups in their own right loses it, permanently, because a temporary loan
ended. And it under-describes: if somebody edits the profile between the loan
starting and ending, the end takes back something different from what the start
handed over. So `applied_group_ids` is the DIFFERENCE the activation actually
made — measured, not predicted — and the revert works from that.

AND IT ONLY EVER REMOVES WHAT IS STILL THERE. A group that was revoked by an
administrator during the window is not re-added and then removed; a group the
borrower has since been given permanently is not taken away. The log says which
of those happened, because "3 delegations ended" over a night that could not
actually take one of them back is the cheerful-number failure this ledger has
recorded five times (R54, R76, R92, R100, R101).

HISTORY IS NEVER DELETED. `unlink` is refused for everybody, including an
administrator, and the ACL grants it to nobody. An audit trail with a delete
button is a diary, not an audit trail.

THE AUDIT TRAIL IS ONE TABLE. A permanent grant made from the roles board is
also a row here — kind `permanent`, with the reason somebody typed. So the
question "how did this person come to hold that" has one place to look rather
than two.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import format_date

from .vendor_common import (DELEGATION_KINDS, DELEGATION_STATES, counted, flag,
                            forbidden_group_ids, param_int)

_logger = logging.getLogger(__name__)


class PbAccessDelegation(models.Model):
    _name = 'pb.access.delegation'
    _description = 'Access delegation'
    _inherit = ['mail.thread']
    _order = 'date_start desc, id desc'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)

    delegator_user_id = fields.Many2one(
        'res.users', string='Lent by', required=True, index=True,
        ondelete='restrict', tracking=True,
        default=lambda self: self.env.user)
    delegate_user_id = fields.Many2one(
        'res.users', string='Lent to', required=True, index=True,
        ondelete='restrict', tracking=True)
    profile_ids = fields.Many2many(
        'pb.role.profile', 'pb_access_delegation_profile_rel',
        'delegation_id', 'profile_id', string='What is being handed over')

    kind = fields.Selection(
        DELEGATION_KINDS, string='For how long', required=True,
        default='temporary', index=True, tracking=True)
    date_start = fields.Date(
        string='From', required=True, default=fields.Date.context_today,
        tracking=True)
    date_end = fields.Date(
        string='Until', tracking=True,
        help='The day it ends. On the morning after, the access is taken back '
             'automatically and both people are told.')
    reason = fields.Text(
        string='Why', help='"Two weeks in Da Nang", "covering the December pay '
                           'run". It is what the audit trail will show.')

    state = fields.Selection(
        DELEGATION_STATES, string='Where it is', required=True, default='draft',
        index=True, tracking=True, copy=False)

    #: EXACTLY the groups this delegation added. Measured at activation, never
    #: predicted from the profiles.
    applied_group_ids = fields.Many2many(
        'res.groups', 'pb_access_delegation_applied_rel',
        'delegation_id', 'group_id', string='Permissions actually added',
        readonly=True, copy=False)
    applied_on = fields.Datetime(string='Handed over at', readonly=True,
                                 copy=False)
    ended_on = fields.Datetime(string='Taken back at', readonly=True,
                               copy=False)
    ended_note = fields.Char(string='What happened at the end', readonly=True,
                             copy=False)

    #: The roles board's grants and removals are rows here too, so there is one
    #: audit trail rather than two. `origin` is what tells them apart on a
    #: screen; nothing in the machinery branches on it.
    origin = fields.Selection(
        [('delegation', 'Delegated'),
         ('board', 'Granted on the roles board'),
         ('board_removal', 'Removed on the roles board')],
        string='How it happened', required=True, default='delegation',
        index=True, readonly=True)

    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    # ---------------------------------------------------------------- computes
    @api.depends('delegator_user_id', 'delegate_user_id', 'date_start')
    def _compute_name(self):
        for rec in self:
            rec.name = _(
                "%(from)s to %(to)s, %(date)s",
                **{'from': rec.delegator_user_id.name or '?',
                   'to': rec.delegate_user_id.name or '?',
                   'date': rec.date_start or ''})

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Delegation')

    # ------------------------------------------------------------------- rails
    @api.constrains('kind', 'date_start', 'date_end')
    def _check_window(self):
        for rec in self:
            if rec.kind == 'temporary' and not rec.date_end:
                raise ValidationError(_(
                    "A hand-over for a while needs a day it ends on. If it is "
                    "not going to end, choose \"For good\" instead."))
            if rec.date_end and rec.date_start and rec.date_end < rec.date_start:
                raise ValidationError(_(
                    "It would end before it starts. Check the two dates."))

    @api.constrains('delegator_user_id', 'delegate_user_id')
    def _check_two_people(self):
        for rec in self:
            if (rec.delegator_user_id and rec.delegate_user_id
                    and rec.delegator_user_id == rec.delegate_user_id):
                raise ValidationError(_(
                    "You cannot hand your access to yourself."))

    def unlink(self):
        """HISTORY IS NEVER DELETED — not by a user, not by an administrator.

        The ACL grants unlink to nobody, which is the first lock; this is the
        second, because an ACL can be edited from a settings screen and this
        cannot. A delegation that was a mistake is REVOKED, and the revocation
        is part of the record.
        """
        raise UserError(_(
            "A hand-over is a record of something that happened, so it cannot "
            "be deleted. Take it back instead — that is written down too, and "
            "it is what an auditor needs to see."))

    # ================================================================ activate
    def action_activate(self):
        """Hand the access over, and write down exactly what was handed.

        Four refusals before anything is written, each of them naming what is
        wrong rather than saying no:
          * it is not in draft;
          * a profile points at the administrator permission (the absolute);
          * the lender does not hold something they are trying to lend;
          * there is nothing left to hand over.
        """
        for rec in self:
            rec._activate_one()
        return True

    def _activate_one(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_(
                "This hand-over is already %s.",
                dict(DELEGATION_STATES).get(self.state, self.state)))
        groups = self._groups_to_hand()

        delegate = self.delegate_user_id.sudo()
        before = set(delegate.group_ids.ids)
        delegate.write({'group_ids': [(4, g.id) for g in groups]})
        # THE SNAPSHOT IS MEASURED, NOT PREDICTED. Odoo may materialise implied
        # groups as direct memberships on write, or may not — it has done both
        # across versions — so what actually changed is read back rather than
        # assumed. `invalidate_recordset` is what makes the second read a real
        # one instead of the cached first.
        delegate.invalidate_recordset(['group_ids'])
        after = set(delegate.group_ids.ids)
        added = sorted(after - before)

        self.sudo().write({
            'state': 'active',
            'applied_group_ids': [(6, 0, added)],
            'applied_on': fields.Datetime.now(),
        })
        self._post(_(
            "%(who)s can now do this on %(whose)s behalf: %(what)s.",
            who=self.delegate_user_id.name or '',
            whose=self.delegator_user_id.name or '',
            what=self._profile_words()))
        if added != sorted(g.id for g in groups):
            # Honest, and worth saying: somebody already held part of it.
            self._post(_(
                "Some of that was already theirs, so this hand-over will only "
                "take back what it actually gave."))
        self._mail('handed')
        return True

    def _groups_to_hand(self):
        """The groups, checked three ways, before a single write.

        The lender check is the heart of it and it is SERVER-SIDE, here, rather
        than in the dialog: a screen that only offers what somebody holds is a
        courtesy, and the only thing that makes "you cannot lend what you do
        not have" true is a refusal on the way in.
        """
        self.ensure_one()
        if not self.profile_ids:
            raise UserError(_(
                "Choose at least one thing to hand over."))
        forbidden = forbidden_group_ids(self.env)
        bad = self.profile_ids.filtered(
            lambda p: p.group_id and p.group_id.id in forbidden)
        if bad:
            raise UserError(_(
                "\"%s\" is the administrator permission for the whole system. "
                "It is never handed over from this screen.",
                ', '.join(bad.mapped('name'))))

        # R7 — the transitive set. Direct membership misses everyone who holds
        # a group through a ladder, which is most people who hold one.
        held = set(self.delegator_user_id.sudo().all_group_ids.ids)
        missing = self.profile_ids.filtered(
            lambda p: p.group_id and p.group_id.id not in held)
        if missing:
            what = ', '.join('"%s"' % n for n in missing.mapped('name'))
            # The whole sentence branches, rather than swapping one word into
            # a fixed frame: "You does not have" is what a frame produces, and
            # a translator cannot fix a verb they were never given (W80).
            if self.delegator_user_id == self.env.user:
                raise UserError(_(
                    "You do not have %s, so you cannot hand it to anybody "
                    "else. You can only lend what you hold yourself.", what))
            raise UserError(_(
                "%(who)s does not have %(what)s, so it cannot be handed to "
                "anybody else. You can only lend what somebody holds "
                "themselves.",
                who=self.delegator_user_id.name or '', what=what))
        return self.profile_ids.mapped('group_id')

    # ================================================================== revoke
    def action_revoke(self, note=None):
        """Take it back now, by hand, mid-window."""
        for rec in self:
            if rec.state != 'active':
                raise UserError(_(
                    "Only a hand-over that is running can be taken back. This "
                    "one is %s.",
                    dict(DELEGATION_STATES).get(rec.state, rec.state)))
            rec._end('revoked', note or _("Taken back by %s.",
                                          self.env.user.name or ''))
        return True

    def _end(self, state, note):
        """Remove EXACTLY what was added, and only what is still there.

        Three outcomes, and each is written down rather than averaged into a
        count: taken back, already gone (somebody revoked it in the meantime),
        and kept (they have since been given it in their own right, so it is
        not this record's to remove).
        """
        self.ensure_one()
        delegate = self.delegate_user_id.sudo()
        held = set(delegate.group_ids.ids)
        applied = self.applied_group_ids
        still = applied.filtered(lambda g: g.id in held)
        gone = applied - still
        if still:
            delegate.write({'group_ids': [(3, g.id) for g in still]})
        self.sudo().write({
            'state': state,
            'ended_on': fields.Datetime.now(),
            'ended_note': note,
        })
        body = _("%(n)s taken back.", n=counted(
            len(still), _("1 permission was"), _("%s permissions were")))
        if gone:
            body = _("%(body)s %(n)s already been removed by somebody else.",
                     body=body,
                     n=counted(len(gone), _("1 had"), _("%s had")))
        self._post('%s %s' % (body, note or ''))
        self._mail('ended')
        return {'removed': len(still), 'already_gone': len(gone)}

    # ============================================================ the mail
    def _mail(self, kind):
        """Both people are told. The recipient is passed EXPLICITLY (R6)."""
        self.ensure_one()
        if not flag(self.env, 'pb_vendor_access.delegation_mail'):
            return False
        xmlid = ('pb_vendor_access.mail_template_delegation_ended'
                 if kind == 'ended'
                 else 'pb_vendor_access.mail_template_delegation_handed')
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            return False
        # Read the addresses AS THE SYSTEM (R56/R104): one field of a user
        # prefetches the lot, and a notification leg must never be able to
        # report a hand-over that worked as a hand-over that failed.
        to = []
        for user in (self.sudo().delegate_user_id,
                     self.sudo().delegator_user_id):
            if user.email and user.email not in to:
                to.append(user.email)
        if not to:
            return False
        try:
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={'email_to': ','.join(to)})
        except Exception:                       # noqa: BLE001
            _logger.warning(
                'pb.access.delegation: could not mail about %s', self.id,
                exc_info=True)
            return False
        return True

    def _post(self, body):
        try:
            self.message_post(body=body)
        except Exception:                       # noqa: BLE001
            _logger.warning('pb.access.delegation: could not post on %s',
                            self.id, exc_info=True)

    def _profile_words(self):
        self.ensure_one()
        names = self.profile_ids.mapped('name')
        if not names:
            return _("nothing")
        return ', '.join('"%s"' % n for n in names)

    # ============================================================== the night
    @api.model
    def cron_auto_revert(self):
        """The job. `limit=None` — R76: the cap that is right for a screen is a
        bug in a job."""
        return self.run_auto_revert(limit=None)

    @api.model
    def run_auto_revert(self, limit=None):
        """Every temporary hand-over whose last day has passed.

        IDEMPOTENT BY CONSTRUCTION. The search only finds `active` rows and the
        first thing `_end` does is move the state, so a second run the same
        night finds nothing. And even if it did, removing a group somebody no
        longer has is a no-op that the counters report as "already gone" rather
        than as work done.

        R36 — TODAY COMES FROM THE SERVER. The live box's clock has run a day
        behind the agent's; a job that took its date from anywhere else would
        find nothing and look broken while being fine.
        """
        today = fields.Date.context_today(self)
        cap = limit or None
        due = self.sudo().search([
            ('state', '=', 'active'),
            ('kind', '=', 'temporary'),
            ('date_end', '!=', False),
            ('date_end', '<', today),
        ], limit=cap, order='date_end')

        # R108 — `format_date(env, d)` with no pattern answers the LOCALE's
        # format, and for an `en_US` reader that is 09/02/2026: the second of
        # September to half the world and the ninth of February to the other
        # half. The board beside this note writes "2 Sept 2026", and two date
        # formats on one screen is one too many.
        pretty = format_date(self.env, today, date_format='d MMM y')

        ended = removed = already = failed = 0
        for rec in due:
            try:
                res = rec._end('expired', _(
                    "Ended on its own on %s, the day after it was due to "
                    "finish.", pretty))
                ended += 1
                removed += res['removed']
                already += res['already_gone']
            except Exception:                   # noqa: BLE001
                failed += 1
                _logger.warning(
                    'pb.access.delegation: %s could not be ended', rec.id,
                    exc_info=True)
        _logger.info(
            'pb.access.delegation: %s due, %s ended, %s permissions taken '
            'back, %s already gone, %s failed',
            len(due), ended, removed, already, failed)
        return {
            'due': len(due), 'ended': ended, 'removed': removed,
            'already_gone': already, 'failed': failed,
            'message': self._revert_message(ended, removed, already, failed),
        }

    @api.model
    def _revert_message(self, ended, removed, already, failed):
        if not ended and not failed:
            return _("Nothing was due to end. Every hand-over that is running "
                     "still has time on it.")
        # Zero gets its own sentence rather than "0 permissions were taken
        # back", which is a number a machine writes. Nothing needing removal
        # is a real and common outcome — the borrower had it in their own
        # right all along — and it deserves words a person would use.
        if removed:
            line = _("%(ended)s ended and %(removed)s taken back.",
                     ended=counted(ended, _("1 hand-over"), _("%s hand-overs")),
                     removed=counted(removed, _("1 permission was"),
                                     _("%s permissions were")))
        else:
            line = _("%s ended, and nothing needed taking back.",
                     counted(ended, _("1 hand-over"), _("%s hand-overs")))
        if already:
            line = _("%(line)s %(n)s already been removed by somebody else.",
                     line=line,
                     n=counted(already, _("1 had"), _("%s had")))
        if failed:
            line = _("%(line)s %(n)s could not be ended and %(still)s — an "
                     "administrator should look at %(them)s.",
                     line=line,
                     n=counted(failed, _("1 hand-over"), _("%s hand-overs")),
                     still=(_("is still running") if failed == 1
                            else _("are still running")),
                     them=_("it") if failed == 1 else _("them"))
        return line

    # ============================================================ the backstop
    @api.model
    def _assert_can_delegate(self, delegator):
        """Anybody internal may lend what they hold; nobody may lend somebody
        ELSE'S access unless they run the access board."""
        if delegator == self.env.user:
            return
        if self.env.user.has_group('base.group_system'):
            return
        for xmlid in ('pb_vendor_access.group_access_manager',):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group and self.env.user.has_group(xmlid):
                return
        raise AccessError(_(
            "You can hand over your own access. Handing over somebody else's "
            "is something the access team does."))

    @api.model
    def default_end_days(self):
        return param_int(self.env, 'pb_vendor_access.default_window_days', 14)
