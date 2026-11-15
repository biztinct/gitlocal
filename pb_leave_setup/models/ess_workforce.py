# -*- coding: utf-8 -*-
"""My Leave, extended from here — never edited (WDGAP S5-A, collision list).

Two overrides of ``pb.ess.workforce``, both keeping the method names and the
return keys the self-service team relies on (owner contract C-4):

* ``get_my_leave`` — the balance tiles ignore days that have RUN OUT (and the
  days taken from them), with the one rule ``pb.timeoff._pb_balance_numbers``
  gives the HR board; a kind that builds up says what was earned so far and
  when the next days come (``pb_earned_label`` / ``pb_next_label``, new keys,
  read by the xpath in ``views/portal_templates.xml``).
* ``_my_appliable_types`` — a kind marked "Only HR can enter this" is not
  offered on the employee's own page. Every caller (the page, apply, the
  preview) asks this one method, so it cannot be asked for by a crafted post.
"""
from odoo import _, api, fields, models


def _num(value):
    return '{:g}'.format(round(value or 0.0, 2))


class PbEssWorkforce(models.AbstractModel):
    _inherit = 'pb.ess.workforce'

    @api.model
    def _my_appliable_types(self, emp):
        types = super()._my_appliable_types(emp)
        return types.filtered(lambda t: not t.pb_ls_hr_only)

    @api.model
    def get_my_leave(self):
        res = super().get_my_leave()
        balances = res.get('balances') or []
        if not balances:
            return res
        emp = self._require_own_employee()
        today = fields.Date.context_today(self)
        type_ids = [b['id'] for b in balances]
        TO = self.env['pb.timeoff'].sudo()
        nums = TO._pb_balance_numbers([emp.id], type_ids, today=today)
        gone = TO._pb_expired_parts([emp.id], type_ids, today=today)
        kinds = self.env['hr.leave.type'].sudo().browse(type_ids)
        by_id = {k.id: k for k in kinds}
        Earn = self.env['pb.leave.earning'].sudo()
        kept = []
        for b in balances:
            if (emp.id, b['id']) in gone:
                n = nums.get((emp.id, b['id'])) or {'allocated': 0.0, 'taken': 0.0, 'balance': 0.0}
                a, k = round(n['allocated'], 2), round(n['taken'], 2)
                if not (a or k):
                    # every day of this kind has run out and none was taken
                    # since: no longer a fact about this person (W64)
                    continue
                b.update({
                    'allocated': a, 'taken': k, 'balance': round(a - k, 2),
                    'balance_label': _('%(balance)s days left', balance=round(a - k, 2)),
                    'used_label': _('%(taken)s of %(allocated)s days used',
                                    taken=k, allocated=a),
                    'low': (a - k) <= 2.0 and a > 0,
                })
            kind = by_id.get(b['id'])
            if kind and kind._pb_ls_earns():
                b.update(self._pb_ls_tile_lines(Earn, kind, emp, today))
            kept.append(b)
        res['balances'] = kept
        return res

    @api.model
    def _pb_ls_tile_lines(self, Earn, kind, emp, today):
        """What a building-up kind adds to its tile, in plain words."""
        posted = Earn._posted(kind, emp, today.year)
        earned_raw = sum(posted.mapped('days'))
        earned = round(earned_raw, 2)
        out = {'pb_earned': earned, 'pb_earned_label': '', 'pb_next_label': ''}
        if kind.pb_ls_earning == 'monthly':
            out['pb_earned_label'] = _('%(days)s days earned so far this year', days=_num(earned))
        when, days = Earn._next_credit(kind, emp, today)
        if when and days:
            out['pb_next_label'] = _('Next: %(days)s on %(date)s',
                                     days=(_('1 day') if round(days, 2) == 1
                                           else _('%s days', _num(days))),
                                     date=self._pb_ls_date(when))
        alloc = Earn._year_allocation(kind, emp, today.year)
        ahead = round((alloc.number_of_days or 0.0) - earned_raw, 2) if alloc else 0.0
        if kind.pb_ls_take_ahead and ahead > 0:
            out['pb_ahead_label'] = _('Includes %(days)s days not earned yet', days=_num(ahead))
        return out

    @api.model
    def _pb_ls_date(self, day):
        from odoo.tools.misc import format_date
        return format_date(self.env, day, date_format='d MMM yyyy')
