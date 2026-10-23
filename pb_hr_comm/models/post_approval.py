# -*- coding: utf-8 -*-
"""An announcement travels the route the business published — when it is asked to.

ONE RUNG, AND IT SHIPS SWITCHED OFF. Most companies do not ask anybody to
agree a canteen notice, so `pb_hr_comm.signoff` is 0 and `action_schedule`
never enters the route: the post goes straight to Scheduled and its own
history says why, naming the switch (R54). Turn the switch on and the same
published route picks it up with nothing else to set up — which is the whole
reason the route is seeded on install rather than the day somebody wants it.

WHAT AN APPROVER IS AGREEING TO is the words, the audience and the moment.
Change any of the three after they agreed and the approval that was given was
given to a different announcement, so the revision stamp is exactly those —
never `write_date` (AM32), and never the recipient COUNT, which is true of the
world rather than of the record: somebody joins, somebody leaves, and a stamp
over a live number would refuse to carry out a perfectly good approval (R202,
reached from the same direction as the goal sheet's weights).

NO `date_field` (R192). The shim hands `_chain_date()` to
`responsibility.resolve(..., on_date)`, so naming a field would ask "who held
the HR-lead seat on the day this is scheduled for" — which for an announcement
booked three months out is a seat nobody holds yet, and the request would
block with a named refusal over a seat that is sitting right there. An
approval asks who holds the seat NOW, because now is when the decision is
being made.
"""

import hashlib
import logging
import re

from odoo import _, api, fields, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_chain, role_step, route,
)

from .comm_common import GROUP_MANAGER, company_words

_logger = logging.getLogger(__name__)

COMM_PROCESS_KEY = 'hr_comm_post'

register_chain(
    'pb.hr.comm.post', COMM_PROCESS_KEY,
    submit_state='submitted',
    driven=('scheduled',),
    draft_state='draft',
    refuse_state='cancelled',
    employee_field='responsible_employee_id',
)


def comm_route():
    """Today's ladder, written as a route somebody can read and change."""
    return route(
        role_step(_('HR lead'), 'hr_lead', key='hr'),
        due_days=1,
    )


class PbHrCommPostApproval(models.Model):
    _inherit = 'pb.hr.comm.post'

    _approval_process_key = COMM_PROCESS_KEY

    # ==================================================================
    #  What the engine is told
    # ==================================================================
    def _chain_title(self):
        self.ensure_one()
        return _("Announcement · %s", self.subject or '')

    def _chain_company(self):
        self.ensure_one()
        return self.sudo().company_id[:1] or self.env.company

    def _chain_facts(self):
        """Read AS THE SYSTEM (AM40).

        The facts a route is CHOSEN on must be readable by the engine whoever
        the maker is, and the maker here may be a country HR user who cannot
        open another company's audience.
        """
        self.ensure_one()
        record = self.sudo()
        return {
            'people': {'value': int(record.recipient_count or 0),
                       'unit': _('people')},
            'audience': {'value': record.audience_word(), 'unit': ''},
            'company': {'value': record.company_id.name or '', 'unit': ''},
            'everyone': {'value': record.audience_kind in ('everyone',
                                                           'country'),
                         'unit': ''},
            'recurring': {'value': record.recurrence != 'none', 'unit': ''},
            'has_poster': {'value': bool(record.poster_ids), 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'people': {'type': 'int', 'label': _('How many people get it')},
            'audience': {'type': 'char', 'label': _('Who it goes to')},
            'company': {'type': 'char', 'label': _('Which company')},
            'everyone': {'type': 'bool',
                         'label': _('Goes to everybody, not one team')},
            'recurring': {'type': 'bool', 'label': _('It comes round again')},
            'has_poster': {'type': 'bool', 'label': _('It carries a poster')},
        }

    def _chain_revision_values(self):
        """The words, the audience and the moment — and nothing that moves.

        The body is stamped as a HASH of its text rather than as the text: an
        approver is agreeing to what it SAYS, and a stamp that carries the
        whole of a long announcement makes every revision comparison a
        paragraph-sized string compare over something the editor may have
        reformatted without changing a word. The tags are stripped for the
        same reason.
        """
        self.ensure_one()
        return {
            'subject': (self.subject or '').strip(),
            'body': self._hc_body_fingerprint(),
            'send_at': fields.Datetime.to_string(self.send_at) or '',
            'audience': self.audience_kind or '',
            'departments': sorted(self.department_ids.ids),
            'jobs': sorted(self.job_ids.ids),
        }

    def _hc_body_fingerprint(self):
        """What the announcement says, as sixteen characters."""
        self.ensure_one()
        text = re.sub(r'<[^>]+>', ' ', self.body_html or '')
        text = re.sub(r'\s+', ' ', text).strip()
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    def _approval_detail(self, request):
        """What the HR lead reads without opening anything (AM49).

        A DRAWER ROW IS A DICT AND A LIST IS SILENTLY DISCARDED (R212). The
        one inbox skips anything that is not `{'head', 'sub', 'cells'}` and
        drops the table entirely when there are no chips either — so a
        consumer that hands it lists gets a drawer that reads as "there was
        nothing to show" rather than as a mistake.
        """
        self.ensure_one()
        record = self.sudo()
        chips = [
            {'label': _('Company'), 'value': record.company_id.name or ''},
            {'label': _('Who gets it'), 'value': record.audience_note or ''},
            {'label': _('How many'),
             'value': str(record.recipient_count or 0)},
            # IN THE APPROVER'S OWN TIME AND IN WORDS. A drawer that says
            # "2026-09-22 09:01:46" to somebody in Ho Chi Minh City is the
            # right moment written in the wrong time zone, and the person
            # deciding is exactly the person who needs to know which working
            # day it lands on.
            {'label': _('Goes out'),
             'value': company_words(self.env, record.send_at,
                                    record.company_id)},
        ]
        if record.recurrence != 'none':
            chips.append({'label': _('How often'),
                          'value': dict(
                              self._fields['recurrence'].selection).get(
                                  record.recurrence, '')})
        rows = [{
            'head': record.subject or '',
            'sub': record.audience_note or '',
            'cells': [record.channels or '',
                      str(record.recipient_count or 0),
                      company_words(self.env, record.send_at,
                                    record.company_id)],
        }]
        note = re.sub(r'<[^>]+>', ' ', record.body_html or '')
        note = re.sub(r'\s+', ' ', note).strip()
        return {'title': _('What is going out'),
                'columns': [_('How'), _('People'), _('When')],
                'rows': rows, 'chips': chips,
                'note': note[:600]}

    # ==================================================================
    #  The rung, as it lands on the record
    # ==================================================================
    def _chain_engine_write(self, state):
        """R132 — THE ROUTE WRITES THE RECORD AS THE PERSON WHO DECIDED.

        The HR lead who agrees an announcement may hold no announcements group
        at all — on this database the seat is frequently a country director —
        and a rule that refuses the write leaves the post one rung behind for
        ever, with one line in the server log as the only trace. The trail is
        unaffected: `_chain_log` still runs as the acting user, so the
        approval log keeps the real name.
        """
        self.ensure_one()
        return super(PbHrCommPostApproval,
                     self.sudo())._chain_engine_write(state)

    def _approval_reject(self, request, reason):
        """Turned down: cancelled, with the reason where a person will read it.

        A REFUSAL'S REASON STAYS ON THE REQUEST UNLESS THE CONSUMER TAKES IT
        (R216). The person who has to act on it opens the announcement, not an
        approval inbox, so the sentence is written into the post's own history
        BEFORE `super()` — which is what sends the email.
        """
        self.ensure_one()
        if reason:
            self._hc_note(_("Turned down by the HR lead: %s", reason))
        return super()._approval_reject(request, reason)

    def _approval_return(self, request, reason):
        """Sent back to be rewritten, with the note on the record."""
        self.ensure_one()
        if reason:
            self._hc_note(_("Sent back: %s", reason))
        result = super()._approval_return(request, reason)
        # THE SHIM'S OWN `_approval_return` DOES NOT CALL THE AFTER-HOOK
        # (`chain_shim.py`, where every other transition does), so the one
        # place every consequence lives has to be reached by hand from here.
        self._after_approval_transition('draft')
        return result

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        # The HR-lead seat, filled from whoever already holds the head-HR tier
        # for announcements — so a company that has not named one explicitly
        # still has somebody to ask, rather than a route that blocks on an
        # empty seat the first time anybody turns sign-off on.
        Seed.fill_role_from_group(company, 'hr_lead', GROUP_MANAGER)
        return Seed.lay(
            company, COMM_PROCESS_KEY, 'Announcement', comm_route(),
            binding_note='The route an announcement follows when sign-off is '
                         'switched on. It ships switched off — most companies '
                         'do not ask anybody to agree a notice — and turning '
                         'pb_hr_comm.signoff on is all it takes to start '
                         'using this.',
            model_name='pb.hr.comm.post',
            role_keys=('hr_lead',),
            reason='Set up when announcements were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.hr.comm.post']._approval_seed_default(company):
                done += 1
        except Exception:               # noqa: BLE001 — never die on a seed
            _logger.exception('pb_hr_comm: %s has no route for announcements',
                              company.name)
    return done
