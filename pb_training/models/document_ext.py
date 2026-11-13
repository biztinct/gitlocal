# -*- coding: utf-8 -*-
"""LEARNING L1 — the vault document IS the certificate record.

ONE REGISTER, NOT TWO. Every certificate and licence a person holds is a row
in the document vault (`pb.employee.document`), beside their contract and their
ID. This file adds the training facts to that row — where it came from, which
course and test it belongs to, who issued it, its number, and whether a newer
one has replaced it — so the training team can ask "who is about to lapse"
without a second table that would one day disagree with the first.

`training_source` EMPTY means "an ordinary vault file": the register and every
count here reads only rows where it is set.

THE STATE IS COMPUTED, NOT STORED, because it is a question about today. It is
also searchable (`_search_training_state`) so a register filter is a domain
and not a Python loop. "soon" is the RENEWAL window (`pb_training.
renew_before_days`, 60 by default), not the vault's own fixed 90 days: it is
the window in which the refresher course is put on the person by itself.

THE VERIFIED FLAG IS THE VAULT'S. It is HR testimony, sentinel-guarded in
`pb_employee_vault`; nothing here writes it directly. `_pb_training_verify`
goes through `action_verify` for an HR user and through the vault's own
sanctioned write (`_vault_sys_write`, the method `action_verify` itself calls)
for a training-team member who holds no HR group — the training gate is
checked by the caller first.
"""

import json
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools.misc import format_date

from .training_common import (
    ASSIGN_OPEN, P_RENEW_BEFORE, number, state_word, tr,
)

_logger = logging.getLogger(__name__)

#: Where a certificate came from. The words are the screen's.
TRAINING_SOURCES = [
    ('test', 'Passed a test here'),
    ('claim', 'Outside course, from a claim'),
    ('upload', 'Uploaded'),
    ('statutory', 'Statutory card or licence'),
    # LEARNING L4: attended a session of a course that files a certificate.
    # (`signoff` — a practical sign-off — is reserved for a later phase,
    # owner decision LD5, and deliberately not offered yet.)
    ('session', 'Attended a session'),
]
TRAINING_SOURCE_LABEL = dict(TRAINING_SOURCES)

#: Where a certificate stands today.
TRAINING_STATES = [
    ('valid', 'Valid'),
    ('soon', 'Expiring soon'),
    ('expired', 'Expired'),
    ('none', 'No expiry'),
    ('renewed', 'Renewed'),
]

#: The vault category codes a certificate may be filed under. CERT is the
#: vault's own "Degree / Certificate"; LIC is this module's "Licence /
#: permit", which requires a valid-until date.
KIND_CERT = 'CERT'
KIND_LIC = 'LIC'


def _renew_window(env):
    return max(number(env, P_RENEW_BEFORE, 60), 0)


class PbEmployeeDocumentTraining(models.Model):
    _inherit = 'pb.employee.document'

    training_source = fields.Selection(
        TRAINING_SOURCES, string='Where it came from', index=True, copy=False,
        help='Empty for an ordinary document. Set for a certificate or '
             'licence the Learning register counts.')
    channel_id = fields.Many2one(
        'slide.channel', string='Course', index=True, copy=False,
        ondelete='set null')
    survey_id = fields.Many2one(
        'survey.survey', string='Test', index=True, copy=False,
        ondelete='set null')
    attempt_id = fields.Many2one(
        'survey.user_input', string='Passed attempt', index=True, copy=False,
        ondelete='set null')
    claim_id = fields.Many2one(
        'pb.training.claim', string='Training claim', index=True, copy=False,
        ondelete='set null')
    issuer = fields.Char(string='Issued by', copy=False)
    reference = fields.Char(string='Certificate number', copy=False)
    renewed_by_id = fields.Many2one(
        'pb.employee.document', string='Renewed by', index=True, copy=False,
        ondelete='set null')
    renewal_assignment_id = fields.Many2one(
        'pb.training.assignment', string='Renewal course', index=True,
        copy=False, ondelete='set null')
    pb_training_reminder_log = fields.Text(
        string='Certificate reminders sent', copy=False, default='{}',
        help='One key per reminder that has gone out, so a second run of the '
             'day sends nothing twice.')

    training_state = fields.Selection(
        TRAINING_STATES, string='Certificate state',
        compute='_compute_training_words', search='_search_training_state')
    source_words = fields.Char(string='Where it came from in words',
                               compute='_compute_training_words')
    valid_words = fields.Char(string='Valid until in words',
                              compute='_compute_training_words')

    # =====================================================================
    #  the state and its words
    # =====================================================================
    @api.depends('expiry_date', 'renewed_by_id', 'training_source')
    def _compute_training_words(self):
        today = fields.Date.today()
        window = _renew_window(self.env)
        for rec in self:
            state = rec._pb_state(today, window)
            rec.training_state = state
            rec.source_words = tr(
                self.env, TRAINING_SOURCE_LABEL[rec.training_source]) \
                if rec.training_source else ''
            rec.valid_words = rec._pb_valid_words(state, today)

    def _pb_state(self, today, window):
        self.ensure_one()
        if self.renewed_by_id:
            return 'renewed'
        if not self.expiry_date:
            return 'none'
        if self.expiry_date < today:
            return 'expired'
        if (self.expiry_date - today).days <= window:
            return 'soon'
        return 'valid'

    def _pb_valid_words(self, state, today):
        """"Valid until 14 Nov 2026", "Expires in 12 days", "Expired 3 days
        ago", "Never expires", "Renewed" — whole sentences (R117)."""
        self.ensure_one()
        env = self.env
        if state == 'renewed':
            return tr(env, 'Renewed')
        if state == 'none':
            return tr(env, 'Never expires')
        days = (self.expiry_date - today).days
        if state == 'expired':
            if days == -1:
                return tr(env, 'Expired yesterday')
            return tr(env, 'Expired %s days ago', -days)
        if state == 'soon':
            if days == 0:
                return tr(env, 'Expires today')
            if days == 1:
                return tr(env, 'Expires tomorrow')
            return tr(env, 'Expires in %s days', days)
        return tr(env, 'Valid until %s', self._pb_date_words(self.expiry_date))

    def _pb_date_words(self, day):
        """A date as people say it: "14 Nov 2026" (localised month)."""
        if not day:
            return ''
        try:
            return format_date(self.env, day, date_format='d MMM y')
        except Exception:                   # noqa: BLE001 — a date is not fatal
            return fields.Date.to_string(day)

    def _search_training_state(self, operator, value):
        if operator not in ('in', 'not in', '=', '!='):
            return NotImplemented
        # The ORM hands `in` an OrderedSet, `=` a plain value.
        values = [value] if isinstance(value, str) or not hasattr(
            value, '__iter__') else list(value)
        today = fields.Date.today()
        horizon = today + timedelta(days=_renew_window(self.env))
        live = Domain('renewed_by_id', '=', False)
        pieces = {
            'renewed': Domain('renewed_by_id', '!=', False),
            'none': live & Domain('expiry_date', '=', False),
            'expired': live & Domain('expiry_date', '<', today),
            'soon': live & Domain('expiry_date', '>=', today)
            & Domain('expiry_date', '<=', horizon),
            'valid': live & Domain('expiry_date', '>', horizon),
        }
        domain = Domain.OR([pieces[v] for v in values if v in pieces]) \
            if any(v in pieces for v in values) else Domain.FALSE
        if operator in ('not in', '!='):
            domain = ~domain
        return domain

    # =====================================================================
    #  what a screen reads
    # =====================================================================
    def _pb_kind(self):
        self.ensure_one()
        return KIND_LIC if (self.category_id.sudo().code or '') == KIND_LIC \
            else KIND_CERT

    def _pb_download_url(self):
        """A download link that works for every kind of login (the vault
        portal's own shape, `pb_me_portal` `_doc_download_url`): the
        attachment's access token, because an employee login holds no ACL
        on `ir.attachment`. Only ever built for a row the caller has already
        been proved to be allowed to see."""
        self.ensure_one()
        attachment = self.attachment_id.sudo()
        if not attachment:
            return ''
        token = attachment.generate_access_token()[0]
        return ('/web/content/ir.attachment/%s/datas?download=true'
                '&access_token=%s' % (attachment.id, token))

    def _pb_renewal(self):
        """The renewal course, as a screen shows it, or None."""
        self.ensure_one()
        row = self.renewal_assignment_id.sudo()
        if not row:
            return None
        is_open = row.state in ASSIGN_OPEN
        if is_open:
            words = tr(self.env, 'Renewal course assigned, due %s',
                       self._pb_date_words(row.due_date))
        else:
            words = tr(self.env, 'Renewal course finished')
        return {
            'assignment_id': row.id,
            'channel_id': row.channel_id.id,
            'state': row.state or 'assigned',
            'state_word': state_word(self.env, row.state),
            'open': is_open,
            'due': fields.Date.to_string(row.due_date) or '',
            'words': words,
        }

    def _pb_next_words(self, state, renewal):
        """What happens next, so no state is a dead end."""
        self.ensure_one()
        env = self.env
        if state == 'renewed':
            return tr(env, 'A newer certificate replaced this one.')
        if state not in ('soon', 'expired'):
            return ''
        if renewal:
            return renewal['words']
        if self.training_source == 'test' and self.channel_id:
            if state == 'soon':
                return tr(env, 'The refresher course is put on by itself.')
            return tr(env, 'Not renewed yet.')
        return tr(env, 'Add the new one when it is issued.')

    def _pb_cert_payload(self):
        """One certificate, as a row on the register or a card in a wallet."""
        self.ensure_one()
        emp = self.employee_id.sudo()
        state = self.training_state
        renewal = self._pb_renewal()
        kind = self._pb_kind()
        return {
            'id': self.id,
            'name': self.name or '',
            'employee_id': emp.id,
            'employee': emp.name or '',
            'department': emp.department_id.name or '',
            'job': emp.job_id.name or emp.job_title or '',
            'kind': kind,
            'kind_words': tr(self.env, 'Licence') if kind == KIND_LIC
            else tr(self.env, 'Certificate'),
            'source': self.training_source or '',
            'source_words': self.source_words or '',
            'issuer': self.issuer or '',
            'reference': self.reference or '',
            'issued': fields.Date.to_string(self.issue_date) or '',
            'issued_words': self._pb_date_words(self.issue_date),
            'expiry': fields.Date.to_string(self.expiry_date) or '',
            'expiry_words': self._pb_date_words(self.expiry_date),
            'valid_words': self.valid_words or '',
            'next_words': self._pb_next_words(state, renewal),
            'state': state,
            'verified': bool(self.verified),
            'channel_id': self.channel_id.id,
            'renewal': renewal,
            'download_url': self._pb_download_url(),
        }

    # =====================================================================
    #  verifying, the vault's way
    # =====================================================================
    def _pb_training_verify(self):
        """Mark verified through the vault's own path. The caller has
        already proved the reader is in the training team (or HR)."""
        for rec in self:
            if rec.verified:
                continue
            if rec._is_hr():
                rec.action_verify()
            else:
                # The vault's sanctioned write, with the same three values
                # `action_verify` writes — the testimony names the person who
                # pressed Verify, never the system.
                rec._vault_sys_write({
                    'verified': True, 'verified_by': self.env.uid,
                    'verified_at': fields.Datetime.now()})
        return True

    # =====================================================================
    #  the reminder ledger and the mail (the assignment's own shape, F7)
    # =====================================================================
    def _pb_sent(self):
        self.ensure_one()
        try:
            data = json.loads(self.pb_training_reminder_log or '{}')
            return data if isinstance(data, dict) else {}
        except (TypeError, ValueError):
            return {}

    def _pb_mark_sent(self, key, today=None):
        self.ensure_one()
        data = self._pb_sent()
        data[key] = fields.Date.to_string(today or fields.Date.today())
        self.sudo().write(
            {'pb_training_reminder_log': json.dumps(data, sort_keys=True)})
        return True

    def _pb_their_email(self):
        self.ensure_one()
        emp = self.employee_id.sudo()
        return (emp.work_email or '').strip() or \
            (emp.user_id.email or '').strip()

    def _pb_manager_email(self):
        self.ensure_one()
        manager = self.employee_id.sudo().parent_id
        if not manager:
            return ''
        return (manager.work_email or '').strip() or \
            (manager.user_id.email or '').strip()

    def _pb_training_mail(self, xmlid, email_to):
        """Queue one email. Never raises, never queues a dead letter (R6) —
        `assignment._mail`, cloned onto the document."""
        self.ensure_one()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_training: %s is missing', xmlid)
            return False
        if not email_to:
            return False
        try:
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={'email_to': email_to, 'auto_delete': False})
            return True
        except Exception:                   # noqa: BLE001 — a nudge is not fatal
            _logger.warning('pb_training: %s could not be queued for '
                            'document %s', xmlid, self.id, exc_info=True)
            return False
