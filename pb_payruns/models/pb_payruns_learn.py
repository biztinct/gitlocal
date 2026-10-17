# -*- coding: utf-8 -*-
"""LEARNREV P1 — "Right now" for the Runs board.

What the board's flags would tell a person, in the order they should act
(handover §5): a run waiting on YOU, a run whose figures do not add up, a run
whose payslips have no source data, drafts ready to send in — or nothing. Read
from `get_board_data`, so every count is the board's own count, and run as the
person, so they see exactly the runs the board shows them.

Declared in `pb_payruns/learn_manifest.py` as `pb.payruns.learn_right_now` and
called by pb_learn's guide; this module never imports pb_learn.
"""
from odoo import api, models

NAMED = 3
INBOX = 'pb_approval_config.action_pb_approval_inbox'
PAY_HUB = 'pb_payhub.action_pb_pay_hub'
MAPPING = 'pb_formula_studio.action_pb_mapping_studio'


def _names(names, lang):
    shown = ', '.join(names[:NAMED])
    rest = len(names) - NAMED
    if rest > 0:
        shown += (' và %d đợt khác' % rest) if lang == 'vi' else (' and %d more' % rest)
    return shown


def _money(amount, symbol, lang):
    text = '{:,.0f}'.format(abs(amount or 0.0))
    if lang == 'vi':
        text = text.replace(',', '.')
    return ('%s %s' % (text, symbol)).strip() if symbol else text


class PbPayrunsLearn(models.AbstractModel):
    _inherit = 'pb.payruns'

    @api.model
    def _learn_open(self, xmlid, lens=None, lens_key=None, ids=None, config_id=None):
        """An `open` action when the target exists on this database, else None
        (a door that goes nowhere is worse than no door).

        LEARNREV P2 (§6.3): the shape the panel hands to `openHub` — `focus`
        is the first run's id (the Runs board highlights that card on
        arrival) and `context` carries `pb_config` for Mapping, which opens
        on that scheme. Never `ids` / `config_id` on the wire."""
        if not self.env.ref(xmlid, raise_if_not_found=False):
            return None
        out = {'kind': 'open', 'xmlid': xmlid,
               'focus': str(ids[0]) if ids else None,
               'context': {'pb_config': config_id} if config_id else {}}
        if lens:
            out['lens'] = lens
            out['lens_key'] = lens_key or 'pb_lens'
        return out

    @api.model
    def _learn_record(self, run_id):
        """Open that pay run's own form (§6.4)."""
        return {'kind': 'open_record', 'res_model': 'hr.payslip.run', 'res_id': run_id}

    @api.model
    def _learn_scheme(self, run_id):
        """(id, name) of the pay scheme a run was run for, or (False, '')."""
        run = self.env['hr.payslip.run'].browse(run_id)
        config = run.pb_formula_config_id if 'pb_formula_config_id' in run._fields \
            else False
        if not config:
            config = run.slip_ids.mapped('formula_config_id')[:1] \
                if 'formula_config_id' in self.env['hr.payslip']._fields else False
        return (config.id, config.name or '') if config else (False, '')

    @api.model
    def learn_right_now(self, args=None):
        board = self.get_board_data()
        batches = board.get('batches') or []
        open_runs = [b for b in batches if b.get('state') in ('draft', 'approval_pending')]
        items = []

        mine = [b for b in batches if b.get('awaiting_me')]
        if mine:
            n = len(mine)
            names = [b['name'] for b in mine]
            items.append({
                'key': 'awaiting_me', 'count': n, 'severity': 'warn',
                'names': names[:NAMED],
                'text': {
                    'en': ("%s is waiting for your decision." % names[0]) if n == 1 else
                          ("%d pay runs are waiting for your decision: %s."
                           % (n, _names(names, 'en'))),
                    'vi': ("Đợt lương %s đang chờ bạn quyết định." % names[0]) if n == 1 else
                          ("%d đợt lương đang chờ bạn quyết định: %s."
                           % (n, _names(names, 'vi'))),
                },
                'action': self._learn_open(INBOX) or self._learn_record(mine[0]['id']),
            })

        unbalanced = [b for b in open_runs if b.get('balance_ok') is False]
        for b in unbalanced[:NAMED]:
            config_id, scheme = self._learn_scheme(b['id'])
            gap_en = _money(b.get('balance_gap'), b.get('currency'), 'en')
            gap_vi = _money(b.get('balance_gap'), b.get('currency'), 'vi')
            where_en = scheme or 'its pay scheme'
            where_vi = scheme or 'chương trình lương của đợt này'
            items.append({
                'key': 'not_balanced', 'count': 1, 'severity': 'warn',
                'names': [b['name']], 'scheme': scheme,
                'text': {
                    'en': "%s: figures don't add up — %s is unaccounted for between "
                          "gross, deductions and net. Open Component treatment for "
                          "%s." % (b['name'], gap_en, where_en),
                    'vi': "%s: số liệu không khớp — còn %s chưa được tính giữa tổng "
                          "thu nhập, khấu trừ và thực nhận. Hãy mở Xử lý thành phần "
                          "của %s." % (b['name'], gap_vi, where_vi),
                },
                'action': self._learn_open(MAPPING, lens='treatment', lens_key='pb_mode',
                                           config_id=config_id or None)
                          or self._learn_record(b['id']),
            })

        unsourced = [b for b in open_runs if b.get('unsourced')]
        if unsourced:
            n = sum(b['unsourced'] for b in unsourced)
            names = [b['name'] for b in unsourced]
            items.append({
                'key': 'unsourced', 'count': n, 'severity': 'warn',
                'names': names[:NAMED],
                'text': {
                    'en': "%d %s in %s %s no source data, so %s figures are the "
                          "scheme's defaults, not real pay. Check Mapping › "
                          "Connections before you submit." % (
                              n, 'payslip' if n == 1 else 'payslips',
                              _names(names, 'en'), 'has' if n == 1 else 'have',
                              'its' if n == 1 else 'their'),
                    'vi': "%d phiếu lương trong %s không có dữ liệu nguồn, nên số "
                          "liệu là giá trị mặc định của chương trình lương, không phải "
                          "lương thật. Hãy kiểm tra Ánh xạ › Liên kết trước khi gửi."
                          % (n, _names(names, 'vi')),
                },
                'action': self._learn_open(MAPPING, lens='desk', lens_key='pb_mode')
                          or self._learn_record(unsourced[0]['id']),
            })

        flagged = {b['id'] for b in unbalanced} | {b['id'] for b in unsourced}
        ready = [b for b in batches if b.get('state') == 'draft'
                 and b.get('next_action') == 'submit' and b['id'] not in flagged]
        if ready:
            n = len(ready)
            names = [b['name'] for b in ready]
            items.append({
                'key': 'submit', 'count': n, 'severity': 'info',
                'names': names[:NAMED],
                'text': {
                    'en': ("%s is a draft. Check it, then submit it for approval."
                           % names[0]) if n == 1 else
                          ("%d draft pay runs can be checked and submitted for "
                           "approval: %s." % (n, _names(names, 'en'))),
                    'vi': ("Đợt lương %s đang là bản nháp. Hãy kiểm tra rồi gửi phê "
                           "duyệt." % names[0]) if n == 1 else
                          ("%d đợt lương nháp có thể được kiểm tra và gửi phê duyệt: "
                           "%s." % (n, _names(names, 'vi'))),
                },
                'action': self._learn_open(PAY_HUB, lens='runs', lens_key='pb_lens',
                                           ids=[b['id'] for b in ready])
                          or self._learn_record(ready[0]['id']),
            })

        if not items:
            items.append({
                'key': 'ok', 'count': 0, 'severity': 'ok',
                'text': {'en': "Nothing on the board needs you right now.",
                         'vi': "Lúc này trên bảng không có việc gì cần bạn."},
                'action': None,
            })
        return items
