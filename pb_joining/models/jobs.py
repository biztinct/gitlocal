import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class JoiningDaily(models.Model):
    _inherit = 'pb.joining'

    erased_at = fields.Datetime(copy=False, readonly=True, index=True)

    def _erase_staging(self, now):
        """Employee documents and the company's original paper are independent records."""
        items = self.item_ids
        signatures = self.sign_ids
        attachments = items.attachment_ids | signatures.signed_attachment_id
        if signatures:
            attachments |= (
                self.env['ir.attachment']
                .sudo()
                .search(
                    [
                        ('res_model', '=', signatures._name),
                        ('res_id', 'in', signatures.ids),
                        ('res_field', '=', 'signature'),
                    ]
                )
            )
        items.write(
            {
                'values': False,
                'draft': False,
                'none_fields': False,
                'attachment_ids': [(5, 0, 0)],
                'return_note': False,
                'issue_date': False,
                'expiry_date': False,
                'no_expiry': False,
            }
        )
        signatures.unlink()
        attachments.exists().unlink()
        self.write(
            {
                'erased_at': now,
                'email': False,
                'phone': False,
                'code_hash': False,
                'code_until': False,
                'code_by_hr': False,
                'code_tries': 0,
                'code_issues': [],
                'code_locked_until': False,
                'code_window_start': False,
                'code_issue_count': 0,
            }
        )

    def _notify_hr(self, now):
        company = self.company_id
        users = self.env['res.users'].sudo()
        for group in ('hr.group_hr_manager', 'hr.group_hr_user'):
            users = self.env.ref(group).all_user_ids.filtered(
                lambda u: u.active and not u.share and company in u.company_ids
            )
            if users:
                break
        for user in users | self._contact().filtered(
            lambda u: u.active and not u.share and company in u.company_ids
        ):
            summary = self.with_context(lang=user.lang).env._(
                'Check what %(name)s still needs before their first day', name=self.name
            )
            self.activity_schedule('mail.mail_activity_data_todo', user_id=user.id, summary=summary)
        self.hr_nudged_at = now

    def _daily_one(self, now):
        self._lock()
        if self.code_until and self.code_until <= now:
            self.write({'code_hash': False, 'code_until': False, 'code_by_hr': False})
        closed = self.cancelled_at if self.state == 'cancelled' else self.added_at
        if self.state in ('cancelled', 'added'):
            if (
                not self.erased_at
                and closed
                and closed + timedelta(days=self._param_days('erase_days', 30)) <= now
            ):
                self._erase_staging(now)
            return
        self._compute_status()
        if self._today() > self.first_day + timedelta(days=self._param_days('link_days_after_start', 14)):
            return
        if self.at_risk and not self.hr_nudged_at:
            self._notify_hr(now)
        if self.state not in ('invited', 'filling') or self.remind_count >= self._param_days('remind_max', 4):
            return
        last = self.reminded_at or self.link_sent_at or self.create_date
        if not last or last + timedelta(days=self._param_days('remind_days', 3)) > now:
            return
        if self.reminded_at and self.reminded_at.date() == now.date():
            return
        localized = self.with_context(lang=self.lang or self.company_id.partner_id.lang or 'en_US')
        if not localized._reminder()['sent']:
            contact = self._contact()
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=contact.id,
                summary=self.with_context(lang=contact.lang).env._(
                    'Remind %(name)s — copy the message from the Joining board', name=self.name
                ),
            )

    @api.model
    def _cron_daily(self):
        now = fields.Datetime.now()
        domain = ['|', ('erased_at', '=', False), ('code_until', '<=', now)]
        last_id = 0
        while rows := self.sudo().search(domain + [('id', '>', last_id)], order='id', limit=200):
            for joining in rows:
                try:
                    with self.env.cr.savepoint():
                        joining.with_company(joining.company_id)._daily_one(now)
                except Exception as error:
                    # Never put a private form value or full link into the job log.
                    _logger.warning(
                        'Joining daily check skipped record %s (%s)', joining.id, type(error).__name__
                    )
            last_id = rows[-1].id
