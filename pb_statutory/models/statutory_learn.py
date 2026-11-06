# -*- coding: utf-8 -*-
"""LEARNREV P5a — "Right now" for the Statutory cockpit.

What the cockpit's two empty panels would tell a person, in the order they
should act: no active insurance policy for the company, then no tax table in
force today for the tax country. Read from `get_statutory_data`, so each item
is the screen's own empty state, and run as the person, so the company and
record rules are exactly the ones the cockpit applies to them. Nothing is
elevated and nothing is written.

Declared in `pb_statutory/learn_manifest.py` as
`pb.statutory.learn_right_now` and called by pb_learn's guide; this module
never imports pb_learn.
"""
from odoo import api, models

COCKPIT = 'pb_statutory.action_pb_statutory'


class PbStatutoryLearn(models.AbstractModel):
    _inherit = 'pb.statutory'

    @api.model
    def _learn_open(self, xmlid):
        """An `open` action when the target exists on this database, else None
        (a door that goes nowhere is worse than no door)."""
        if not self.env.ref(xmlid, raise_if_not_found=False):
            return None
        return {'kind': 'open', 'xmlid': xmlid, 'focus': None, 'context': {}}

    @api.model
    def learn_right_now(self, args=None):
        country = args.get('country_code') if isinstance(args, dict) else None
        data = self.get_statutory_data(country)
        code = data.get('tax_country') or 'VN'
        names = dict(data.get('tax_countries') or [])
        country_name = names.get(code) or code
        company = data.get('company') or ''
        items = []

        # Insurance policies are a Vietnam table: a company elsewhere has no
        # policy to be missing, so it is only asked about for Vietnam.
        if code == 'VN' and 'vietnam.insurance.policy' in self.env \
                and not data.get('policy'):
            items.append({
                'key': 'no_policy', 'count': 1, 'severity': 'warn',
                'text': {
                    'en': "%s has no active insurance policy. Add one with the "
                          "Insurance policy button, dated from the day it applies."
                          % company,
                    'vi': "%s chưa có chính sách bảo hiểm nào đang hoạt động. Hãy "
                          "thêm một chính sách bằng nút Chính sách bảo hiểm, đề "
                          "ngày bắt đầu áp dụng." % company,
                },
                'action': self._learn_open(COCKPIT),
            })

        if not data.get('tax'):
            items.append({
                'key': 'no_tax_table', 'count': 1, 'severity': 'warn',
                'text': {
                    'en': "There is no tax table in force today for %s. Add one with "
                          "the Tax table button, or publish a country table."
                          % country_name,
                    'vi': "Hôm nay chưa có bảng thuế nào đang hiệu lực cho %s. Hãy "
                          "thêm một bảng bằng nút Bảng thuế, hoặc phát hành một bảng "
                          "của quốc gia." % country_name,
                },
                'action': self._learn_open(COCKPIT),
            })

        if not items:
            items.append({
                'key': 'ok', 'count': 0, 'severity': 'ok',
                'text': {'en': "The insurance policy and tax table are in force. "
                               "Nothing here needs you right now.",
                         'vi': "Chính sách bảo hiểm và bảng thuế đang hiệu lực. Lúc "
                               "này ở đây không có việc gì cần bạn."},
                'action': None,
            })
        return items
