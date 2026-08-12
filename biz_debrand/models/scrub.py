# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""One-off scrub of vendor references already written into the database.

The runtime seams (``_()`` patch, QWeb tree walker, JS ``_t()`` patch, Apps-list
``read()``) cover everything rendered *from source*. They cannot touch content
that was materialised into rows before the brand existed — chatter messages the
bot posted, activity notes, chat names, digest tips, seeded social links.

Runs from ``_biz_debrand_apply_brand``, i.e. on install, on every upgrade of
this module, and on every save of the Branding settings. Idempotent by
construction: the rewrite is a no-op once applied, and rows are only touched
when they still match.

Deliberately NOT scrubbed:
  * ``ir_module_module`` metadata — re-imported from every ``__manifest__.py``
    on each ``-u``; handled at ``read()`` instead (see ir_module_module.py).
  * ``ir_model_fields*`` — already debranded at runtime by web_debranding's
    ``get_field_string`` / ``get_field_help`` / ``get_field_selection``.
  * email *addresses* — only the display name of an address is rewritten;
    rewriting the addr-spec would silently change routing.
"""
import logging
import re

from psycopg2.extras import Json

from odoo import models

from .brand import HAS_ODOO_RE, brand_for_env, debrand_text

_logger = logging.getLogger(__name__)

# (table, [plain text/varchar columns]) — scrubbed row by row in Python so the
# rewrite rules are identical to every other seam (PostgreSQL regexes have no
# lookahead, so an equivalent SQL expression is not possible).
TEXT_TARGETS = [
    ("mail_message", ["body", "subject"]),
    ("mail_activity", ["note"]),
    ("discuss_channel", ["name", "description"]),
    ("ir_ui_view", ["name"]),
    ("ir_asset", ["name"]),
    ("hr_job", ["requirements"]),
]

# (table, [jsonb translated columns])
JSONB_TARGETS = [
    ("ir_actions", ["name", "help"]),
    ("ir_act_window", ["help"]),
    ("ir_act_report_xml", ["name"]),
    ("res_groups", ["name", "comment"]),
    ("digest_tip", ["name", "tip_description"]),
    ("mail_template", ["name", "subject", "body_html"]),
    ("hr_skill", ["name"]),
    ("hr_resume_line", ["name"]),
    ("hr_job", ["description"]),
    # pb_learn deliberately described the legacy salary structures by the
    # vendor's name. Ruled out by the brand owner: no vendor mention anywhere,
    # legacy or not. The module's source XML is fixed too, so a reinstall does
    # not bring it back — this only catches already-loaded rows.
    ("learn_station", ["outline_what"]),
    ("learn_column", ["body"]),
    ("learn_screen", ["blurb"]),
]

# Vendor-owned social accounts seeded into every website record.
SOCIAL_COLUMNS = [
    "social_facebook",
    "social_twitter",
    "social_linkedin",
    "social_github",
    "social_instagram",
    "social_tiktok",
    "social_youtube",
]

# Any host under the vendor's domain — including subdomains such as
# apps.odoo.com, which debrand_url deliberately leaves alone.
VENDOR_URL_RE = re.compile(r"https?://(?:[\w-]+\.)*odoo\.(?:com|sh)\b", re.IGNORECASE)

BATCH = 2000


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _biz_columns(self, table, columns):
        """Return the subset of ``columns`` that actually exists on ``table``."""
        self.env.cr.execute(
            """
            SELECT column_name FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = %s AND column_name = ANY(%s)
            """,
            (table, list(columns)),
        )
        return [row[0] for row in self.env.cr.fetchall()]

    def _biz_scrub_text(self, table, columns, brand, website):
        columns = self._biz_columns(table, columns)
        if not columns:
            return 0
        cols = ", ".join('"%s"' % c for c in columns)
        where = " OR ".join("""%s ~* '\\modoo'""" % ('"%s"' % c) for c in columns)
        self.env.cr.execute('SELECT id, %s FROM "%s" WHERE %s' % (cols, table, where))
        rows = self.env.cr.fetchall()
        updates = []
        for row in rows:
            record_id, values = row[0], row[1:]
            new_values = [debrand_text(v, brand, website) if isinstance(v, str) else v for v in values]
            if any(new is not old for new, old in zip(new_values, values)):
                updates.append(tuple(new_values) + (record_id,))
        if not updates:
            return 0
        assignment = ", ".join('"%s" = %%s' % c for c in columns)
        sql = 'UPDATE "%s" SET %s WHERE id = %%s' % (table, assignment)
        for start in range(0, len(updates), BATCH):
            self.env.cr.executemany(sql, updates[start:start + BATCH])
        return len(updates)

    def _biz_scrub_jsonb(self, table, columns, brand, website):
        columns = self._biz_columns(table, columns)
        if not columns:
            return 0
        touched = 0
        for column in columns:
            self.env.cr.execute(
                """SELECT id, "%s" FROM "%s" WHERE "%s"::text ~* '\\modoo'"""
                % (column, table, column)
            )
            updates = []
            for record_id, value in self.env.cr.fetchall():
                if not isinstance(value, dict):
                    continue
                new_value = {
                    lang: debrand_text(text, brand, website) if isinstance(text, str) else text
                    for lang, text in value.items()
                }
                if new_value != value:
                    updates.append((new_value, record_id))
            if not updates:
                continue
            sql = 'UPDATE "%s" SET "%s" = %%s WHERE id = %%s' % (table, column)
            payload = [(Json(value), record_id) for value, record_id in updates]
            for start in range(0, len(payload), BATCH):
                self.env.cr.executemany(sql, payload[start:start + BATCH])
            touched += len(payload)
        return touched

    def _biz_scrub_email_display_names(self, brand, website):
        """Rewrite only the display-name part of stored ``"Name" <addr>`` values.

        8,490 historical ``mail_message`` rows carry ``"OdooBot"
        <odoobot@example.com>``. The address is routing data and is left
        untouched; only the quoted name a human reads is rebranded.
        """
        touched = 0
        for table, columns in (("mail_message", ["email_from", "reply_to"]),):
            for column in self._biz_columns(table, columns):
                self.env.cr.execute(
                    """SELECT DISTINCT "%s" FROM "%s" WHERE "%s" ~* '\\modoo'"""
                    % (column, table, column)
                )
                for (value,) in self.env.cr.fetchall():
                    if not value or "<" not in value:
                        continue  # bare address: no display name to rebrand
                    display, _, rest = value.partition("<")
                    new_display = debrand_text(display, brand, website)
                    if new_display is display:
                        continue
                    self.env.cr.execute(
                        'UPDATE "%s" SET "%s" = %%s WHERE "%s" = %%s' % (table, column, column),
                        (new_display + "<" + rest, value),
                    )
                    touched += self.env.cr.rowcount
        return touched

    def _biz_scrub_socials(self):
        """Clear the vendor's own social accounts seeded into website records."""
        columns = self._biz_columns("website", SOCIAL_COLUMNS)
        if not columns:
            return 0
        clauses = " OR ".join("""%s ~* '\\modoo'""" % ('"%s"' % c) for c in columns)
        assignment = ", ".join(
            """"{c}" = CASE WHEN "{c}" ~* '\\modoo' THEN NULL ELSE "{c}" END""".format(c=c)
            for c in columns
        )
        self.env.cr.execute("UPDATE website SET %s WHERE %s" % (assignment, clauses))
        return self.env.cr.rowcount

    def _biz_scrub_demo_emails(self, brand, website):
        """Vendor addresses seeded into contact records.

        Two distinct shapes, both non-routable:
          * ``…@odoo.com`` on demo contacts -> the reserved ``example.com``;
          * ``odoobot@example.com``, the bot's placeholder local-part, which is
            what still reads "odoobot" in Technical -> Emails once the display
            name has been rebranded.
        Real customer addresses are never matched: only these two patterns are.
        """
        local = re.sub(r"[^a-z0-9]+", "", brand.lower()) or "bot"
        touched = 0
        for table, column in (
            ("res_partner", "email"),
            ("res_partner", "email_normalized"),
            ("hr_employee", "work_email"),
            ("hr_employee", "private_email"),
            ("mail_message", "email_from"),
            ("mail_message", "reply_to"),
        ):
            if not self._biz_columns(table, [column]):
                continue
            self.env.cr.execute(
                """UPDATE "{t}" SET "{c}" = regexp_replace("{c}", '@(www\\.)?odoo\\.com\\M', '@example.com', 'gi')
                    WHERE "{c}" ~* '@(www\\.)?odoo\\.com\\M'""".format(t=table, c=column)
            )
            touched += self.env.cr.rowcount
            self.env.cr.execute(
                """UPDATE "{t}" SET "{c}" = regexp_replace("{c}", '\\modoo[_-]?bot@', %s, 'gi')
                    WHERE "{c}" ~* '\\modoo[_-]?bot@'""".format(t=table, c=column),
                (local + "@",),
            )
            touched += self.env.cr.rowcount
        return touched

    def _biz_scrub_backend_links(self):
        """Retarget stored ``/odoo/...`` deep links at the rebranded prefix.

        Chatter bodies and mail templates embed absolute backend links. The
        text rewrite deliberately leaves paths alone (they are routing, not
        prose), so this is handled here — and only when a router rebrand such
        as biz_deroute is actually installed to receive them.
        """
        prefix = self._biz_debrand_webclient_prefix()
        if not prefix:
            return 0
        touched = 0
        for table, column in (
            ("mail_message", "body"),
            ("mail_template", "body_html"),
        ):
            if not self._biz_columns(table, [column]):
                continue
            self.env.cr.execute(
                """UPDATE "{t}" SET "{c}" = replace("{c}"::text, '"/odoo/', %s)::{cast}
                    WHERE "{c}"::text LIKE %s""".format(
                    t=table,
                    c=column,
                    cast="jsonb" if self._biz_is_jsonb(table, column) else "text",
                ),
                ('"%s/' % prefix, '%"/odoo/%'),
            )
            touched += self.env.cr.rowcount
        return touched

    def _biz_scrub_vendor_menus(self):
        """Archive menu items whose only purpose is to leave for the vendor.

        "Third-Party Apps" and "Theme Store" are ungrouped, active menus bound
        to ``ir.actions.act_url`` targets on ``apps.odoo.com``. Their *labels*
        are already brand-neutral, so no text rule catches them, but clicking
        one lands the user on the vendor's storefront. The subdomain is left
        out of the URL rewrite on purpose (see debrand_url), so retiring the
        entry is the honest fix.

        Scoped by destination host, not by label: only menus that actually
        navigate to a vendor domain are touched.
        """
        menus = self.env["ir.ui.menu"].sudo().search([("active", "=", True)])
        targets = menus.filtered(
            lambda m: isinstance(m.action, models.BaseModel)
            and m.action._name == "ir.actions.act_url"
            and VENDOR_URL_RE.search(m.action.url or "")
        )
        if not targets:
            return 0
        _logger.info("biz_debrand: archiving vendor menus %s", targets.mapped("name"))
        targets.write({"active": False})
        return len(targets)

    def _biz_is_jsonb(self, table, column):
        self.env.cr.execute(
            """SELECT data_type FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s AND column_name=%s""",
            (table, column),
        )
        row = self.env.cr.fetchone()
        return bool(row) and row[0] == "jsonb"

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------
    def _biz_debrand_scrub_data(self):
        brand, website = brand_for_env(self.env)
        if not brand or HAS_ODOO_RE.search(brand):
            _logger.warning("biz_debrand: refusing to scrub with brand %r", brand)
            return False

        total = 0
        for table, columns in TEXT_TARGETS:
            try:
                total += self._biz_scrub_text(table, columns, brand, website)
            except Exception:
                _logger.warning("biz_debrand: scrub of %s failed", table, exc_info=True)
        for table, columns in JSONB_TARGETS:
            try:
                total += self._biz_scrub_jsonb(table, columns, brand, website)
            except Exception:
                _logger.warning("biz_debrand: jsonb scrub of %s failed", table, exc_info=True)
        for step in (
            lambda: self._biz_scrub_email_display_names(brand, website),
            self._biz_scrub_socials,
            lambda: self._biz_scrub_demo_emails(brand, website),
            self._biz_scrub_backend_links,
            self._biz_scrub_vendor_menus,
        ):
            try:
                total += step()
            except Exception:
                _logger.warning("biz_debrand: scrub step failed", exc_info=True)

        # Rewritten rows are cached: translated fields in the ORM cache, and
        # QWeb trees in the 'templates' cache keyed by view id, not by brand.
        self.env.invalidate_all()
        self.env.registry.clear_cache("default", "templates")
        _logger.info("biz_debrand: scrubbed %s stored rows as %r", total, brand)
        return total
