from datetime import timedelta
import hashlib
import hmac
import re
import secrets
import time

from odoo import _, fields, models
from odoo.tools.misc import hmac as database_hmac

from .joining import SYSTEM


class JoiningCode(models.Model):
    _inherit = 'pb.joining'

    code_hash = fields.Char(groups=SYSTEM, copy=False)
    code_until = fields.Datetime(groups=SYSTEM, copy=False)
    code_tries = fields.Integer(groups=SYSTEM, copy=False)
    code_issued_at = fields.Datetime(groups=SYSTEM, copy=False)
    code_issue_count = fields.Integer(groups=SYSTEM, copy=False)
    code_window_start = fields.Datetime(groups=SYSTEM, copy=False)
    code_issues = fields.Json(groups=SYSTEM, copy=False)
    code_delivery_failed = fields.Boolean(groups=SYSTEM, copy=False)
    code_locked_until = fields.Datetime(groups=SYSTEM, copy=False)
    code_by_hr = fields.Boolean(groups=SYSTEM, copy=False)

    def _digest(self, code):
        return hashlib.sha256(f'{self.token}:{code}'.encode()).hexdigest()

    def _issue(self, *, by_hr=False, automatic=False):
        self._lock()
        now = fields.Datetime.now()
        if self.code_locked_until and self.code_locked_until > now:
            return {'status': 'locked'}
        if automatic and self.code_hash and self.code_until and self.code_until > now:
            return {'status': 'live'}
        if not by_hr and not self._can_email():
            return {'status': 'pass_on'}
        recent = [v for v in self.code_issues or [] if fields.Datetime.to_datetime(v) > now - timedelta(hours=1)]
        if not by_hr and (len(recent) >= 5 or (recent and fields.Datetime.to_datetime(recent[-1]) > now - timedelta(minutes=1))):
            return {'status': 'wait'}
        code = f'{secrets.randbelow(10**6):06d}'
        if not by_hr:
            recent.append(fields.Datetime.to_string(now))
            self.write({'code_issues': recent, 'code_issue_count': len(recent), 'code_window_start': recent[0]})
            try:
                with self.env.cr.savepoint():
                    delivered = self._mail('joining_code', {'code': code})
            except Exception:
                delivered = False
            if not delivered:
                if not self.code_delivery_failed:
                    self.activity_schedule('mail.mail_activity_data_todo', user_id=self._contact().id,
                                           summary=_('Show a joining code to %(name)s', name=self.name))
                self.write({'code_delivery_failed': True, 'link_mode': 'pass_on'})
                return {'status': 'pass_on'}
        self.write({'code_hash': self._digest(code),
                    'code_until': now + (timedelta(hours=48) if by_hr else timedelta(minutes=10)),
                    'code_by_hr': by_hr, 'code_delivery_failed': False, 'code_issued_at': now,
                    'code_issue_count': len(recent), 'code_issues': recent,
                    'code_window_start': recent[0] if recent else False, 'code_locked_until': False,
                    'code_tries': 0 if self.code_locked_until else self.code_tries})
        if by_hr:
            self.message_post(body=_('Code shown by %(name)s', name=self.env.user.name))
            return {'status': 'issued', 'code': code}
        return {'status': 'issued'}

    def _verify(self, supplied):
        self._lock()
        now = fields.Datetime.now()
        if self.code_locked_until and self.code_locked_until > now:
            return 'locked'
        if not self.code_hash or not self.code_until or self.code_until <= now:
            return 'expired'
        tries = self.code_tries + 1
        self.code_tries = tries
        valid = isinstance(supplied, str) and re.fullmatch('[0-9]{6}', supplied)
        if valid and hmac.compare_digest(self.code_hash, self._digest(supplied)):
            self.write({'opened_at': self.opened_at or now, 'last_seen_at': now, 'code_hash': False,
                        'code_until': False, 'code_by_hr': False, 'code_tries': 0,
                        'state': 'filling' if self.state == 'invited' else self.state})
            return 'ok'
        if tries >= 5:
            self.write({'code_hash': False, 'code_until': False, 'code_locked_until': now + timedelta(minutes=15)})
            return 'locked'
        return 'wrong'

    def _device_cookie(self, until):
        # Bind the confirmation to this database, link and joining. Rotating the link invalidates it.
        signature = database_hmac(self.sudo().env,
                                  'pb_joining.device', (self.id, self.token, until))
        return f'{until}.{signature}'

    def _restore_device(self, session, cookie):
        if not isinstance(cookie, str) or not re.fullmatch(r'[0-9]{1,12}\.[a-f0-9]{64}', cookie):
            return False
        until = int(cookie.partition('.')[0])
        now = int(time.time())
        if not now < until <= now + 14 * 86400:
            return False
        if not hmac.compare_digest(cookie, self._device_cookie(until)):
            return False
        self._remember(session, until)
        return True

    def _remember(self, session, until=None):
        now = int(time.time())
        sessions = {k: v for k, v in (session.get('pbj') or {}).items() if v > now}
        sessions[str(self.id)] = until or now + 14 * 86400
        session['pbj'] = sessions
        return sessions[str(self.id)]

    def _remembered(self, session):
        return (session.get('pbj') or {}).get(str(self.id), 0) > time.time()
