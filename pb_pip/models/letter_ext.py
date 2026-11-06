# -*- coding: utf-8 -*-
"""One placeholder on one letter type may carry markup. Exactly one.

P0's letter engine ESCAPES every value it substitutes, and that is the right
default and must stay the default: a letter body is written by an HR
administrator in a rich-text box, and the worst thing an administrator can do
to a `${...}` placeholder should be to misspell it.

But an improvement-plan letter has to print a LIST — "what we have agreed you
will work on", one line per objective — and a list is markup. Escaped, the
person receives `&lt;ul&gt;&lt;li&gt;` on the page: the letter's own source
code, rendered as prose. (The same shape as R51, reached from the other side:
there an Html field crossing JSON-RPC arrived as a plain string; here a plain
string is escaped on its way into HTML.)

SO THE HATCH IS AS NARROW AS IT CAN BE MADE:

  * one letter type — `pip`, and nothing else;
  * one placeholder name — `objectives`, and nothing else;
  * one producer — `pb.pip.case._prepare_letter`, which builds the markup
    itself with every interpolated value `escape()`d on the way in, so the
    only tags in it are tags this codebase wrote;
  * `pb.hr.letter` records are created by HR-tier code and never by a user
    typing into a field, so `context_json` is not a user-controlled surface
    to begin with.

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
RAW_LETTER_TYPE = 'pip'
RAW_KEY = 'objectives'


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
            _logger.warning('pb_pip: letter %s has unreadable extra details',
                            self.id)
            return values
        raw = extra.get(RAW_KEY)
        if isinstance(raw, str) and raw:
            values[RAW_KEY] = Markup(raw)
        return values
