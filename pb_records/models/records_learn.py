# -*- coding: utf-8 -*-
"""LEARNREV P5a — "Right now" for the Records Desk.

Changes to people's details wait for an approver before they are applied. This
lists, in the order a person should act: changes waiting for THEIR decision,
changes of theirs that were sent back, changes of theirs still waiting for
someone else — or nothing.

Read as the asking person, never elevated: `pb.records.apply` already carries
the record rules that show a person only their own changes, the ones they were
asked to decide, or (HR and payroll) all of them. The desk's own read gate is
reused, so a person who cannot open the desk gets an access error the caller
handles.

Declared in `pb_records/learn_manifest.py` as `pb.records.desk.learn_right_now`
and called by pb_learn's guide; this module never imports pb_learn.
"""
from odoo import api, models
from odoo.exceptions import AccessError

NAMED = 3
INBOX = 'pb_approval_config.action_pb_approval_inbox'
DESK = 'pb_records.action_pb_records_desk'


def _names(names, lang):
    shown = ', '.join(names[:NAMED])
    rest = len(names) - NAMED
    if rest > 0:
        shown += (' và %d thay đổi khác' % rest) if lang == 'vi' else (' and %d more' % rest)
    return shown


class PbRecordsDeskLearn(models.AbstractModel):
    _inherit = 'pb.records.desk'

    @api.model
    def _learn_door(self, xmlid):
        """An `open` action when the target exists on this database, else None."""
        if not self.env.ref(xmlid, raise_if_not_found=False):
            return None
        return {'kind': 'open', 'xmlid': xmlid, 'focus': None, 'context': {}}

    @api.model
    def _learn_open_seat(self, rec, uid):
        """True when `rec`'s current approval step has an open seat for `uid`.
        When the seats cannot be read the change is NOT claimed as waiting
        for this person (a wrong "your decision" is worse than no line)."""
        try:
            request = rec.approval_request_id
            step = request.step_ids.filtered(
                lambda s: s.key == request.current_step_key)[:1]
            return any(seat.status == 'open' and seat.acting_user_id.id == uid
                       for seat in step.seat_ids)
        except AccessError:
            return False

    @api.model
    def learn_right_now(self, args=None):
        if not self._may_read():
            raise AccessError(self.env._("You do not have access to employee records."))
        Apply = self.env['pb.records.apply']
        uid = self.env.user.id
        base = [('state', '=', 'pending'),
                ('company_id', 'in', self.env.companies.ids)]
        items = []

        awaiting = Apply.search(
            base + [('seat_user_ids', 'in', [uid]), ('user_id', '!=', uid)],
            order='id desc')
        # A seat stays readable after it has decided, so keep only the changes
        # whose CURRENT step still has an open seat for this person.
        awaiting = awaiting.filtered(lambda rec: self._learn_open_seat(rec, uid))
        if awaiting:
            n = len(awaiting)
            names = awaiting.mapped('name')
            items.append({
                'key': 'awaiting_me', 'count': n, 'severity': 'warn',
                'names': names[:NAMED],
                'text': {
                    'en': ("Change %s is waiting for your decision." % names[0]) if n == 1
                          else ("%d changes to people's details are waiting for your "
                                "decision: %s." % (n, _names(names, 'en'))),
                    'vi': ("Thay đổi %s đang chờ bạn quyết định." % names[0]) if n == 1
                          else ("%d thay đổi thông tin nhân viên đang chờ bạn quyết "
                                "định: %s." % (n, _names(names, 'vi'))),
                },
                'action': self._learn_door(INBOX) or self._learn_door(DESK),
            })

        returned = Apply.search(
            [('state', '=', 'returned'), ('user_id', '=', uid),
             ('company_id', 'in', self.env.companies.ids)], order='id desc')
        if returned:
            n = len(returned)
            names = returned.mapped('name')
            items.append({
                'key': 'sent_back', 'count': n, 'severity': 'warn',
                'names': names[:NAMED],
                'text': {
                    'en': ("Your change %s was sent back. Open History to see why."
                           % names[0]) if n == 1
                          else ("%d of your changes were sent back: %s. Open History "
                                "to see why." % (n, _names(names, 'en'))),
                    'vi': ("Thay đổi %s của bạn đã bị gửi trả lại. Hãy mở Lịch sử để "
                           "xem lý do." % names[0]) if n == 1
                          else ("%d thay đổi của bạn đã bị gửi trả lại: %s. Hãy mở Lịch "
                                "sử để xem lý do." % (n, _names(names, 'vi'))),
                },
                'action': self._learn_door(DESK),
            })

        mine = Apply.search(base + [('user_id', '=', uid)], order='id desc')
        if mine:
            n = len(mine)
            names = mine.mapped('name')
            items.append({
                'key': 'waiting_mine', 'count': n, 'severity': 'info',
                'names': names[:NAMED],
                'text': {
                    'en': ("Your change %s is waiting for approval; nothing is applied "
                           "until it is approved." % names[0]) if n == 1
                          else ("%d of your changes are waiting for approval: %s. "
                                "Nothing is applied until they are approved."
                                % (n, _names(names, 'en'))),
                    'vi': ("Thay đổi %s của bạn đang chờ phê duyệt; chưa có gì được áp "
                           "dụng cho đến khi được duyệt." % names[0]) if n == 1
                          else ("%d thay đổi của bạn đang chờ phê duyệt: %s. Chưa có gì "
                                "được áp dụng cho đến khi được duyệt."
                                % (n, _names(names, 'vi'))),
                },
                'action': self._learn_door(DESK),
            })

        if not items:
            items.append({
                'key': 'ok', 'count': 0, 'severity': 'ok',
                'text': {'en': "No changes are waiting to be applied.",
                         'vi': "Không có thay đổi nào đang chờ được áp dụng."},
                'action': None,
            })
        return items
