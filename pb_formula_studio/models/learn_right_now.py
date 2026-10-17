# -*- coding: utf-8 -*-
"""LEARNREV P1 — "Right now" for Component treatment.

What the board would tell a person if it could talk, as numbered things to do,
each with the action a help panel can wire (handover §5). Declared in
`pb_formula_studio/learn_manifest.py` as `hr.formula.config.learn_right_now`
and called by pb_learn's guide; this module never imports pb_learn.

It reads the board's own data (`value_kind_board`), so the counts are the
chips' counts by construction, and it inherits the board's access check: a
person without payroll officer access gets an AccessError, which the guide
turns into a named reason.

"COMPUTED BEFORE YOUR LAST CHANGE" HAS NO MARKER
------------------------------------------------
None of the treatment fields is versioned and nothing records when a payslip
was last evaluated against them (ledger LR10). The one honest signal is the
write date: a run whose newest payslip write is older than the scheme's newest
component write was computed before that change. It over-reports (any write to
a component counts), never under-reports, and it only looks at runs that can
still be recomputed (draft, waiting for approval).
"""
import logging

from odoo import api, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

#: How many names a sentence lists before it says "and N more".
NAMED = 3
#: Run states a person can still recompute.
OPEN_RUN_STATES = ('draft', 'approval_pending')
PAY_HUB = 'pb_payhub.action_pb_pay_hub'


def _names(names, lang, vi_noun='thành phần'):
    shown = ', '.join(names[:NAMED])
    rest = len(names) - NAMED
    if rest > 0:
        shown += (' và %d %s khác' % (rest, vi_noun)) if lang == 'vi' \
            else (' and %d more' % rest)
    return shown


def _pair(en, vi):
    return {'en': en, 'vi': vi}


class HrFormulaConfigLearnRightNow(models.Model):
    _inherit = 'hr.formula.config'

    @api.model
    def learn_right_now(self, args=None):
        """`[{key, count, severity, text: {en, vi}, action, names}]`, most
        urgent first — or `{"items": [], "missing": reason}`."""
        args = dict(args or {})
        try:
            config_id = int(args.get('config_id') or 0)
        except (TypeError, ValueError):
            config_id = 0
        if not config_id:
            return {'items': [], 'missing': 'no scheme selected'}
        config = self.browse(config_id).exists()
        if not config:
            return {'items': [], 'missing': 'that scheme no longer exists'}
        # The board's own gate: raises AccessError for anyone below payroll
        # officer, exactly as the screen itself does.
        board = config.value_kind_board(run_id=args.get('run_id') or None)
        rows = board.get('rows') or []
        items = []

        review = [r['name'] for r in rows if r.get('needs_review')]
        if review:
            n = len(review)
            items.append({
                'key': 'needs_answer', 'count': n, 'severity': 'warn',
                'names': review[:NAMED],
                'text': _pair(
                    "%d %s your answer on Pay role: %s." % (
                        n, 'row still needs' if n == 1 else 'rows still need',
                        _names(review, 'en')),
                    "%d dòng vẫn cần câu trả lời của bạn ở cột Vai trò trong "
                    "lương: %s." % (n, _names(review, 'vi'))),
                'action': {'kind': 'filter', 'value': 'review'},
            })

        clash = [r['name'] for r in rows if r.get('role_conflict')]
        if clash:
            n = len(clash)
            items.append({
                'key': 'type_conflict', 'count': n, 'severity': 'warn',
                'names': clash[:NAMED],
                'text': _pair(
                    ("1 row's value type says otherwise: %s is not an amount, yet "
                     "its pay role adds to or takes off net pay. Set it to "
                     "Information only." % _names(clash, 'en')) if n == 1 else
                    ("%d rows' value types say otherwise: %s are not amounts, yet "
                     "their pay roles add to or take off net pay. Set them to "
                     "Information only." % (n, _names(clash, 'en'))),
                    "%d dòng có loại giá trị nói khác: %s không phải là số tiền, "
                    "nhưng vai trò trong lương lại cộng vào hoặc trừ khỏi thực "
                    "nhận. Hãy đặt thành Chỉ để tham khảo." % (n, _names(clash, 'vi'))),
                'action': {'kind': 'filter', 'value': 'conflict'},
            })

        drift = [r['name'] for r in rows if r.get('drift')]
        if drift:
            n = len(drift)
            items.append({
                'key': 'drift', 'count': n, 'severity': 'warn',
                'names': drift[:NAMED],
                'text': _pair(
                    "%d %s as text but %s as a number on the payslips: %s. Set "
                    "the right value type, then recompute the run." % (
                        n, 'component arrived' if n == 1 else 'components arrived',
                        'is stored' if n == 1 else 'are stored',
                        _names(drift, 'en')),
                    "%d thành phần đi vào dưới dạng chữ nhưng được lưu dưới dạng số "
                    "trên phiếu lương: %s. Hãy đặt đúng loại giá trị, rồi tính lại "
                    "đợt lương." % (n, _names(drift, 'vi'))),
                'action': {'kind': 'filter', 'value': 'drift'},
            })

        stale = self._learn_stale_runs(config)
        if stale:
            n = len(stale)
            names = [run.name or '' for run in stale]
            # LEARNREV P2 (§6.3): the shape the panel's openHub takes — the
            # Runs board highlights the `focus` run's card on arrival.
            action = ({'kind': 'open', 'xmlid': PAY_HUB, 'lens': 'runs',
                       'lens_key': 'pb_lens', 'focus': str(stale[0].id), 'context': {}}
                      if self.env.ref(PAY_HUB, raise_if_not_found=False) else
                      {'kind': 'open_record', 'res_model': 'hr.payslip.run',
                       'res_id': stale[0].id})
            items.append({
                'key': 'recompute', 'count': n, 'severity': 'warn',
                'names': names[:NAMED],
                'text': _pair(
                    ("%s was computed before your last change to this scheme. "
                     "Recompute it so its figures use the change."
                     % _names(names, 'en')) if n == 1 else
                    ("%d pay runs were computed before your last change to this "
                     "scheme: %s. Recompute them so their figures use the change."
                     % (n, _names(names, 'en'))),
                    ("Đợt lương %s được tính trước lần thay đổi gần nhất của bạn "
                     "cho chương trình lương này. Hãy tính lại để số liệu dùng "
                     "thay đổi đó." % _names(names, 'vi', 'đợt')) if n == 1 else
                    ("%d đợt lương được tính trước lần thay đổi gần nhất của bạn "
                     "cho chương trình lương này: %s. Hãy tính lại để số liệu dùng "
                     "thay đổi đó." % (n, _names(names, 'vi', 'đợt')))),
                'action': action,
            })

        if not items:
            items.append({
                'key': 'ok', 'count': 0, 'severity': 'ok',
                'text': _pair(
                    "Nothing needs you here. Save is enabled only when you change "
                    "a row.",
                    "Ở đây không có việc gì cần bạn. Nút Lưu chỉ bật khi bạn thay "
                    "đổi một dòng."),
                'action': None,
            })
        return items

    def _learn_stale_runs(self, config):
        """Open runs whose newest payslip write is older than the scheme's
        newest component write, newest run first. A person who may not read
        payslips simply gets no item here (the other items still stand)."""
        last_change = max((d for d in config.rule_ids.mapped('write_date') if d),
                          default=None)
        if not last_change:
            return []
        Slip = self.env['hr.payslip']
        try:
            groups = Slip._read_group(
                [('formula_config_id', '=', config.id),
                 ('payslip_run_id', '!=', False),
                 ('payslip_run_id.state', 'in', OPEN_RUN_STATES)],
                ['payslip_run_id'], ['write_date:max'])
        except AccessError:
            return []
        stale = [run for run, last in groups if last and last < last_change]
        return sorted(stale, key=lambda r: (r.date_end or r.date_start or
                                            r.create_date.date(), r.id),
                      reverse=True)
