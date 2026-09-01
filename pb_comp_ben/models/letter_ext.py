# -*- coding: utf-8 -*-
"""One placeholder on one letter type may carry markup. Exactly one.

The same hatch P6 opened for the improvement-plan letter
(`pb_pip/models/letter_ext.py`), COPIED rather than generalised — and the
copying is the point. P0's letter engine escapes every value it substitutes,
which is the right default: a letter body is written by an HR administrator in
a rich-text box, and the worst thing an administrator can do to a `${...}`
placeholder should be to misspell it.

An award letter has to print a small TABLE — what the award is, how much, which
month, why — and a table is markup. Escaped, the person receives
`&lt;table&gt;&lt;tr&gt;` on the page: the letter's own source code, as prose.

SO THE HATCH IS AS NARROW AS IT CAN BE MADE:

  * one letter type — `incentive`, and nothing else;
  * one placeholder name — `extra`, which is the only hole the seeded incentive
    body prints, and nothing else;
  * one producer — `pb.incentive._letter_extras`, which builds the markup itself
    with every interpolated value `escape()`d on the way in, so the only tags in
    it are tags this codebase wrote;
  * `pb.hr.letter` records of this type are created by `pb.incentive` and never
    by a user typing into a field, so `context_json` is not a user-controlled
    surface to begin with.

A general "raw placeholders" mechanism would have been three lines shorter and
would have handed every future phase a way to put unescaped strings into
somebody's letter. This is the version that cannot be reused by accident.
"""

import json
import logging

from markupsafe import Markup

from odoo import models

_logger = logging.getLogger(__name__)

#: The one letter type and the one key. Both, or neither.
RAW_LETTER_TYPE = 'incentive'
RAW_KEY = 'extra'


class PbHrLetter(models.Model):
    _inherit = 'pb.hr.letter'

    def _placeholder_values(self):
        values = super()._placeholder_values()
        self.ensure_one()
        if self.letter_type != RAW_LETTER_TYPE:
            return values
        try:
            extra = json.loads(self.context_json or '{}') or {}
        except Exception:               # noqa: BLE001 — a letter still prints
            _logger.warning('pb_comp_ben: letter %s has unreadable extra details',
                            self.id)
            return values
        raw = extra.get(RAW_KEY)
        if isinstance(raw, str) and raw:
            values[RAW_KEY] = Markup(raw)
        return values
