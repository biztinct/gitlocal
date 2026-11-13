import json
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# ---------------------------------------------------------------------------
# Token whitelist — the only custom properties a theme may override.
# Keys are stored WITHOUT the leading "--". Token key names keep the vu-*
# prefix because every downstream stylesheet (VU Form Engine, kit modules)
# already consumes those custom properties. Three value classes drive
# validation; unknown keys are dropped silently at CSS generation time so a
# stale preset can never inject arbitrary CSS.
# ---------------------------------------------------------------------------
COLOR_KEYS = {
    "vu-brand-primary", "vu-brand-primary-dark", "vu-brand-secondary", "vu-brand-accent",
    "vu-surface-app", "vu-surface-panel", "vu-surface-card", "vu-surface-muted", "vu-surface-hover",
    "vu-text-primary", "vu-text-secondary", "vu-text-inverse",
    "vu-border-soft", "vu-border-strong",
    "vu-status-success", "vu-status-info", "vu-status-warning", "vu-status-danger",
    "vu-state-draft", "vu-state-confirmed", "vu-state-assigned", "vu-state-active",
    "vu-state-completed", "vu-state-cancelled", "vu-state-closed",
    "vu-link-color",
    "vu-navbar-bg", "vu-navbar-text",
    "vu-sidebar-bg", "vu-sidebar-text", "vu-sidebar-hover",
    # Component-level overrides — independent of the brand primary; every one
    # falls back to the semantic layer in SCSS when not set, so themes may
    # recolor a single component without touching anything else.
    "vu-btn-primary-bg", "vu-btn-primary-text", "vu-btn-primary-hover",
    "vu-btn-secondary-bg", "vu-btn-secondary-text", "vu-btn-secondary-hover",
    "vu-statusbar-btn-bg", "vu-statusbar-btn-text", "vu-statusbar-btn-border",
    "vu-tab-active",
    "vu-focus-ring",
    # Backend chrome hooks (navbar strip) introduced by biz_theme
    "biz-chrome-bg", "biz-chrome-border",
}
DIMENSION_KEYS = {
    "vu-radius-sm", "vu-radius-md", "vu-radius-lg",
    "vu-navbar-height", "vu-sidebar-width", "vu-table-row-py",
    "vu-font-size-base",
    "biz-sidebar-w", "biz-sidebar-rail-w",
}
NUMBER_KEYS = {"vu-density", "vu-radius-scale", "vu-shadow-depth", "vu-motion-scale"}
FONT_KEYS = {"vu-font-body", "vu-font-headings"}

# vu-font-* knobs also feed the pre-existing typography tokens so themes
# actually change the rendered font without touching SCSS.
ALIAS_KEYS = {
    "vu-font-body": ["vu-font-family-base"],
    "vu-font-headings": ["vu-font-family-headings"],
}

COLOR_RE = re.compile(
    r"^(#[0-9a-fA-F]{3,8}|rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(,\s*(0|1|0?\.\d+)\s*)?\))$"
)
DIMENSION_RE = re.compile(r"^\d+(\.\d+)?(px|rem|em|%)$")
NUMBER_RE = re.compile(r"^\d+(\.\d+)?$")
FONT_BAD_CHARS = re.compile(r"[;{}<>@\\]")

VERSION_PARAM = "biz_theme.theme_version"
RUNTIME_PARAM = "biz_theme.runtime_tokens"


def _validate_token(key, value):
    """Return a safe value for the token, or None if invalid/unknown."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if key in COLOR_KEYS:
        return value if COLOR_RE.match(value) else None
    if key in DIMENSION_KEYS:
        return value if DIMENSION_RE.match(value) else None
    if key in NUMBER_KEYS:
        return value if NUMBER_RE.match(value) else None
    if key in FONT_KEYS:
        return None if FONT_BAD_CHARS.search(value) else value
    return None


class BizTheme(models.Model):
    _name = "biz.theme"
    _description = "Biz Theme"
    _order = "state desc, write_date desc"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", string="Company")
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published"), ("archived", "Archived")],
        default="draft", required=True,
    )
    preset_key = fields.Char(help="Preset this theme started from (provenance).")
    token_values = fields.Json(default=lambda self: {})
    token_values_text = fields.Text(
        string="Tokens (JSON)",
        compute="_compute_token_values_text",
        inverse="_inverse_token_values_text",
        help="Editable JSON view of the token values.",
    )
    version = fields.Integer(default=1, readonly=True)

    @api.depends("token_values")
    def _compute_token_values_text(self):
        for theme in self:
            theme.token_values_text = json.dumps(
                theme.token_values or {}, indent=2, sort_keys=True
            )

    def _inverse_token_values_text(self):
        for theme in self:
            try:
                values = json.loads(theme.token_values_text or "{}")
            except ValueError:
                raise ValidationError("Tokens must be valid JSON.")
            if not isinstance(values, dict):
                raise ValidationError("Tokens must be a JSON object.")
            theme.token_values = values

    # ------------------------------------------------------------------
    # CSS generation
    # ------------------------------------------------------------------
    def _safe_tokens(self):
        """Whitelisted, validated token dict (aliases expanded)."""
        self.ensure_one()
        safe = {}
        for key, value in (self.token_values or {}).items():
            clean = _validate_token(key, value)
            if clean is None:
                continue
            safe[key] = clean
            for alias in ALIAS_KEYS.get(key, []):
                safe[alias] = clean
        return safe

    def _to_css(self):
        self.ensure_one()
        tokens = self._safe_tokens()
        if not tokens:
            return "/* biz_theme: no overrides */\n:root {}\n"
        lines = [f"    --{key}: {value};" for key, value in sorted(tokens.items())]
        return ":root {\n%s\n}\n" % "\n".join(lines)

    @api.model
    def _runtime_enabled(self):
        """Brand lock: a brand overlay (e.g. pb_theme) sets
        ``biz_theme.runtime_tokens = off`` to freeze its compiled branding —
        the tokens endpoint then serves empty CSS and Theme Studio is locked."""
        icp = self.env["ir.config_parameter"].sudo()
        return icp.get_param(RUNTIME_PARAM, "on") != "off"

    @api.model
    def _published_css(self):
        """CSS block for the currently published theme (empty rules if none)."""
        if not self._runtime_enabled():
            return "/* biz_theme: runtime tokens locked by brand module */\n:root {}\n"
        theme = self.sudo().search([("state", "=", "published")], limit=1)
        return theme._to_css() if theme else "/* biz_theme: default */\n:root {}\n"

    @api.model
    def _current_version(self):
        return self.env["ir.config_parameter"].sudo().get_param(VERSION_PARAM, "0")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def action_publish(self):
        self.ensure_one()
        published = self.search([("state", "=", "published"), ("id", "!=", self.id)])
        published.write({"state": "archived"})
        self.write({"state": "published", "version": self.version + 1})
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(VERSION_PARAM, str(int(icp.get_param(VERSION_PARAM, "0")) + 1))
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_discard(self):
        """Delete a draft (drafts only — published history is kept)."""
        self.filtered(lambda t: t.state == "draft").unlink()
        return {"type": "ir.actions.act_window_close"}

    def action_duplicate(self):
        self.ensure_one()
        copy = self.copy({"name": f"{self.name} (copy)", "state": "draft", "version": 1})
        return {
            "type": "ir.actions.act_window",
            "res_model": "biz.theme",
            "res_id": copy.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def create_from_preset(self, preset_key, name=None):
        preset = self.env["biz.theme.preset"].search([("key", "=", preset_key)], limit=1)
        if not preset:
            raise ValidationError(f"Unknown preset: {preset_key}")
        return self.create({
            "name": name or preset.name,
            "preset_key": preset_key,
            "token_values": preset.token_values or {},
        })


class BizThemePreset(models.Model):
    _name = "biz.theme.preset"
    _description = "Biz Theme Preset"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    key = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    description = fields.Char()
    token_values = fields.Json(default=lambda self: {})
    preview_colors = fields.Json(
        default=lambda self: [], help="Swatch strip for the preset gallery (list of hex strings)."
    )

    _sql_constraints = [("key_uniq", "unique(key)", "Preset key must be unique.")]
