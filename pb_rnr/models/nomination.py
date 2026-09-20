# -*- coding: utf-8 -*-
"""`pb.rnr.nomination` — one piece of praise, and the two people who agreed it.

=====================================================================
TWO HANDS, AND WHY THEY ARE THESE TWO
=====================================================================
Recognition that anybody can publish about anybody is worth nothing within a
month. Recognition that only HR can start never happens at all, because HR was
not in the room. So the story is written by the COLLEAGUE who saw it, agreed by
the nominee's own MANAGER — the one person who can say whether it is true — and
decided by HR, who is the only one who can attach money to it.

`state` is that ladder and it runs on `biz.approval.chain.mixin`, not on a
fourth hand-rolled state machine. `outcome` is a SECOND column, because "how far
did it get" and "what came of it" are different questions and a board that
cannot show praise that was agreed but not paid for is a board nobody uses.

THE MANAGER USUALLY HOLDS NO GROUP. `_approval_can` therefore admits the
nominee's manager BY NAME for their own step — the mixin's own safety rail 4,
which exists for exactly this. Everything after that step needs the HR tier.

=====================================================================
CASH GOES THROUGH P7'S DOOR AND NOWHERE ELSE
=====================================================================
When HR attaches an amount this model creates a `pb.incentive` with
`source='rnr'` and stops. The award then rides P7's approval, P7's letter and
P7's pay feed exactly as one somebody typed by hand — same ladder, same paper,
same lane. **Nothing here ever queues money into a pay run.** That is one
explicit press on the Awards lens, by a human, on a run that is still being
prepared, and P8 does not get to shortcut it.

=====================================================================
PRIVACY IS A PROPERTY OF THE RECORD, NOT OF THE SCREEN
=====================================================================
`_public_domain()` is the single definition of "may be seen by everybody":
decided, agreed, and marked public by the person who wrote it. The wall, the
portal page and the digest all call it. A declined story cannot leak, because
there is no second opinion about what public means.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .rnr_common import (
    GROUP_MANAGER, GROUP_USER, NOMINATION_STATES, OUTCOMES, P_AWARD_KIND,
    P_HR_ALERT_MAIL, P_HR_ALERT_TO, P_THANKS_MAIL, PUBLIC_OUTCOMES, excerpt,
    flag, param,
)

_logger = logging.getLogger(__name__)


class PbRnrNomination(models.Model):
    _name = 'pb.rnr.nomination'
    _description = 'Praise'
    _inherit = ['mail.thread', 'biz.approval.chain.mixin']
    _order = 'decided_at desc, id desc'

    #: Who may move it along. The manager step is `None` — open by the mixin's
    #: rules and then NARROWED by `_approval_can` to the nominee's own manager
    #: (plus the HR tier, who can always unstick a queue). The decision is the
    #: HR tier and nobody else, because it is the step that can spend money.
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'manager'): GROUP_USER,
        ('submitted', 'refused'): GROUP_USER,
        ('manager', 'done'): GROUP_MANAGER,
        ('manager', 'refused'): GROUP_MANAGER,
        ('draft', 'refused'): None,
    }

    name = fields.Char(compute='_compute_name', store=True, string='Reference')
    nominee_id = fields.Many2one(
        'hr.employee', string='Who deserves it', required=True, index=True,
        ondelete='cascade', tracking=True)
    nominator_id = fields.Many2one(
        'hr.employee', string='Who said so', required=True, index=True,
        ondelete='cascade', tracking=True)
    value_id = fields.Many2one(
        'pb.company.value', string='Which value', required=True, index=True,
        ondelete='restrict', tracking=True)
    story = fields.Text(
        string='What they did', required=True, tracking=True,
        help='The actual thing that happened. One real example beats three '
             'adjectives, and it is what everybody else will read.')
    submitted_at = fields.Datetime(string='Written on', readonly=True,
                                   copy=False)
    decided_at = fields.Datetime(string='Decided on', readonly=True, copy=False)

    state = fields.Selection(NOMINATION_STATES, default='draft', required=True,
                             tracking=True, string='How far it has got')
    outcome = fields.Selection(OUTCOMES, string='What was decided', copy=False,
                               tracking=True)
    decision_note = fields.Text(string='Note with the decision', copy=False)

    award_amount = fields.Monetary(
        string='Cash with it', currency_field='currency_id', tracking=True,
        help='Leave this empty for praise on its own. An amount raises an '
             'award, which is approved and paid the same way as any other.')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    incentive_id = fields.Many2one('pb.incentive', string='The award',
                                   readonly=True, copy=False,
                                   ondelete='set null')
    cycle_id = fields.Many2one('pb.rnr.cycle', string='Quarter', index=True,
                               ondelete='set null', copy=False)
    is_winner = fields.Boolean(string='Chosen for the quarter', copy=False,
                               tracking=True)

    public = fields.Boolean(
        string='Show it to everybody', default=True, tracking=True,
        help='On, this appears on the recognition wall once it is agreed. Off, '
             'only the person, their manager and HR ever see it.')
    company_id = fields.Many2one('res.company', string='Company', index=True,
                                 default=lambda self: self.env.company)

    # ------------------------------------------------------------------ name
    @api.depends('nominee_id', 'value_id')
    def _compute_name(self):
        for rec in self:
            who = rec._person(rec.nominee_id).name or _('Praise')
            val = rec.value_id.sudo().name or ''
            rec.name = ('%s — %s' % (who, val)).strip(' —')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Praise')

    # ------------------------------------------------------------------- R56
    @api.model
    def _person(self, employee):
        """An employee read AS THE SYSTEM.

        Reading one field of an `hr.employee` prefetches forty, and about forty
        of those sit behind payroll groups a recognition reader has no reason to
        hold (R56). The security boundary stays the search that found the
        record, exactly as `pb.pip.case._person` and `pb.incentive._person`.

        R43 — over the wire a record argument arrives as a plain integer, so
        this coerces at the door and every public method can hand it whatever
        it has.
        """
        Emp = self.env['hr.employee'].sudo()
        if isinstance(employee, models.BaseModel):
            return Emp.browse(employee.ids[:1])
        try:
            return Emp.browse(int(employee or 0)).exists()
        except (TypeError, ValueError):
            return Emp.browse()

    # ----------------------------------------------------------- constraints
    @api.constrains('nominee_id', 'nominator_id')
    def _check_not_self(self):
        """Nobody praises themselves. Said kindly, because it is a mistake
        anybody can make on a form with two name boxes on it."""
        for rec in self:
            if rec.nominee_id and rec.nominee_id == rec.nominator_id:
                raise ValidationError(_(
                    "Praise goes to somebody else. Pick the colleague you want "
                    "to say thank you to."))

    @api.constrains('award_amount')
    def _check_amount(self):
        for rec in self:
            if rec.award_amount and rec.award_amount < 0:
                raise ValidationError(_(
                    "An award cannot be a negative amount."))

    # ------------------------------------------------------ who may do what
    def _manager_user_ids(self):
        """The nominee's own manager, as user ids. Read as the system (R56)."""
        self.ensure_one()
        emp = self._person(self.nominee_id)
        boss = emp.parent_id if emp else emp
        out = set()
        if boss and boss.user_id:
            out.add(boss.user_id.id)
        return out

    def _approval_can(self, from_state, to_state):
        """The mixin's rule, plus the one person it cannot know about.

        The nominee's manager holds no group and never will — they are a line
        manager, not an HR administrator. Safety rail 4 of the chain exists for
        exactly this: a consumer admits a SPECIFIC person by name for a specific
        step. Nothing else is widened; the decision step is still the HR tier.
        """
        self.ensure_one()
        if super()._approval_can(from_state, to_state):
            return True
        if from_state == 'submitted' and to_state in ('manager', 'refused'):
            return self.env.user.id in self._manager_user_ids()
        return False

    def can_be_decided_by(self, user=None):
        """A plain answer for the portal, which has no view logic to hide."""
        self.ensure_one()
        who = user or self.env.user
        return self.state == 'submitted' and who.id in self._manager_user_ids()

    # ------------------------------------------------------------ the buttons
    def action_submit(self):
        """The colleague sends it to the nominee's manager."""
        for rec in self:
            if not (rec.story or '').strip():
                raise UserError(_(
                    "Write the story first — what actually happened. That is "
                    "the part everybody reads."))
            rec._advance_state('submitted')
            rec.submitted_at = fields.Datetime.now()
            rec._notify_hr_arrived()
        return True

    def action_manager_agree(self, note=False):
        """The manager says yes: it goes to HR."""
        for rec in self:
            rec._advance_state('manager', note=note or False)
        return True

    def action_recognise(self, amount=0.0, note=False):
        """HR's decision — praise, and optionally money with it."""
        for rec in self:
            value = float(amount or 0.0)
            if value:
                rec.award_amount = value
            rec._advance_state('done', note=note or False)
            if note:
                rec.decision_note = note
        return True

    def action_decline(self, note=False):
        """Not this time. It never appears anywhere public — that is the
        whole of the privacy rule, expressed once."""
        for rec in self:
            rec.action_refuse_chain(note=note or False)
            if note:
                rec.decision_note = note
        return True

    # ------------------------------------------------------------- the hooks
    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        for rec in self:
            if to_state == 'refused':
                rec.write({'outcome': 'declined',
                           'decided_at': fields.Datetime.now()})
                continue
            if to_state != 'done':
                continue
            rec.decided_at = fields.Datetime.now()
            awarded = False
            if rec.award_amount:
                try:
                    awarded = bool(rec._make_award())
                except Exception:           # noqa: BLE001
                    # An award that will not raise must never undo a decision a
                    # person has made. The praise stands; the money is retried
                    # from the record.
                    _logger.exception(
                        'pb_rnr: praise %s was recognised but its award could '
                        'not be raised', rec.id)
                    rec.message_post(body=_(
                        "Recognised. The award could not be raised just now — "
                        "it can be raised again from this record."))
            rec.outcome = 'awarded' if awarded else 'recognised'
            rec._notify_nominee()
        return res

    # -------------------------------------------------------------- the award
    def action_make_award(self):
        """Raise (or re-raise) the award by hand."""
        for rec in self:
            rec._make_award()
        return True

    def _make_award(self):
        """ONE `pb.incentive`, and then hands off completely.

        Everything after this — the approval, the letter, the pay feed — is P7's
        and is not reimplemented, wrapped or shortcut here. The award is created
        DRAFT: recognising somebody is not the same act as agreeing to spend the
        company's money, and the head of pay is the one who does the second.
        """
        self.ensure_one()
        if not self.award_amount:
            return False
        if self.incentive_id:
            return self.incentive_id
        emp = self._person(self.nominee_id)
        if not emp:
            return False
        kind = (param(self.env, P_AWARD_KIND) or 'spot').strip() or 'spot'
        today = fields.Date.context_today(self)
        award = self.env['pb.incentive'].sudo().create({
            'employee_id': emp.id,
            'kind': kind,
            'amount': self.award_amount,
            'currency_id': (self.currency_id
                            or self.env.company.currency_id).id,
            'period_month': today.replace(day=1),
            'reason': self._award_reason(),
            'source': 'rnr',
            'company_id': (self.company_id or emp.company_id
                           or self.env.company).id,
        })
        self.incentive_id = award.id
        self.message_post(body=_(
            "An award of %(amount)s was raised. It still has to be approved by "
            "the pay team and put into a pay run by hand — nothing has been "
            "paid yet.",
            amount='{:,.0f}'.format(self.award_amount or 0.0)))
        return award

    def _award_reason(self):
        """What the award letter will say this was for — the colleague's own
        words, because a letter that says "spot award" says nothing."""
        self.ensure_one()
        val = self.value_id.sudo().name or ''
        who = self._person(self.nominator_id).name or _('a colleague')
        return _(
            "Recognised for %(value)s, nominated by %(who)s. %(story)s",
            value=val, who=who, story=excerpt(self.story, 400))

    # -------------------------------------------------------------- the mails
    def _notify_hr_arrived(self):
        """Tell HR a new story has come in. Behind its own switch, off."""
        self.ensure_one()
        if not flag(self.env, P_HR_ALERT_MAIL):
            _logger.info(
                'pb_rnr: praise %s arrived; the HR alert is switched off, so '
                'nothing was emailed.', self.id)
            return False
        to = (param(self.env, P_HR_ALERT_TO) or '').strip()
        if not to:
            _logger.info(
                'pb_rnr: praise %s arrived but no HR address is set, so '
                'nothing was emailed.', self.id)
            return False
        return self._send('pb_rnr.mail_template_rnr_hr_alert', to)

    def _notify_nominee(self):
        """Tell the person they were praised. Behind its own switch, off."""
        self.ensure_one()
        if not flag(self.env, P_THANKS_MAIL):
            _logger.info(
                'pb_rnr: praise %s was recognised; the thank-you email is '
                'switched off, so nothing was sent.', self.id)
            return False
        emp = self._person(self.nominee_id)
        to = (emp.work_email or '').strip() if emp else ''
        if not to:
            return False
        return self._send('pb_rnr.mail_template_rnr_thanks', to)

    def _send(self, xmlid, to):
        """One queued message, best effort, ALWAYS with an explicit address.

        R6 — a template's own rendered `email_to` can reach `mail.mail` empty,
        and the message is then created, queued and addressed to nobody with no
        error anywhere. The address is passed in `email_values` every time; the
        template's own field is documentation.
        """
        self.ensure_one()
        try:
            template = self.env.ref(xmlid, raise_if_not_found=False)
            if not template:
                return False
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={'email_to': to})
        except Exception:                   # noqa: BLE001 — a courtesy, never a block
            _logger.exception('pb_rnr: could not queue %s for praise %s',
                              xmlid, self.id)
            return False
        return True

    # ------------------------------------------------------------ the reads
    @api.model
    def _public_domain(self, company_ids=None):
        """THE ONE DEFINITION of "everybody may see this".

        The wall, the portal page and the monthly digest all call this. There is
        deliberately no second opinion anywhere: a declined story, or one the
        writer marked private, cannot leak through a surface that was written
        later and forgot a clause.
        """
        domain = [
            ('state', '=', 'done'),
            ('outcome', 'in', list(PUBLIC_OUTCOMES)),
            ('public', '=', True),
        ]
        ids = company_ids if company_ids is not None else self.env.companies.ids
        if ids:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', 'in', list(ids))]
        return domain

    def greeting(self):
        """The name at the top of an email about this praise."""
        self.ensure_one()
        return self._person(self.nominee_id).name or ''

    def nominator_name(self):
        self.ensure_one()
        return self._person(self.nominator_id).name or ''

    def value_name(self):
        self.ensure_one()
        return self.value_id.sudo().name or ''

    def story_excerpt(self):
        self.ensure_one()
        return excerpt(self.story, 400)
