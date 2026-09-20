import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { applyDraftTokens } from "../services/theme_loader_service";

/**
 * VU Theme Studio — visual theme builder.
 *
 * Left rail: grouped token editor (colors, chrome, components, shape/type).
 * Main area: live playground of Odoo components driven by the DRAFT tokens.
 * Top bar: preset gallery + Preview in app / Publish / Discard.
 *
 * Draft tokens are applied as inline CSS custom properties on <html> through
 * the biz_theme_loader service — visible only in this tab until Publish.
 */

const GROUPS = [
    {
        label: "Brand",
        tokens: [
            ["vu-brand-primary", "Primary"],
            ["vu-brand-primary-dark", "Primary (hover/active)"],
            ["vu-brand-secondary", "Secondary"],
            ["vu-brand-accent", "Accent"],
            ["vu-link-color", "Links"],
        ],
    },
    {
        label: "Surfaces",
        tokens: [
            ["vu-surface-app", "App background"],
            ["vu-surface-panel", "Content background"],
            ["vu-surface-card", "Cards"],
            ["vu-surface-muted", "Muted"],
            ["vu-surface-hover", "Hover"],
        ],
    },
    {
        label: "Text",
        tokens: [
            ["vu-text-primary", "Primary text"],
            ["vu-text-secondary", "Secondary text"],
            ["vu-text-inverse", "Inverse text"],
        ],
    },
    {
        label: "Borders",
        tokens: [
            ["vu-border-soft", "Soft borders"],
            ["vu-border-strong", "Strong borders"],
        ],
    },
    {
        label: "Status colors",
        tokens: [
            ["vu-status-success", "Success"],
            ["vu-status-info", "Info"],
            ["vu-status-warning", "Warning"],
            ["vu-status-danger", "Danger"],
        ],
    },
    {
        label: "Workflow states",
        tokens: [
            ["vu-state-draft", "Draft"],
            ["vu-state-confirmed", "Confirmed"],
            ["vu-state-assigned", "Assigned"],
            ["vu-state-active", "In progress"],
            ["vu-state-completed", "Completed"],
            ["vu-state-cancelled", "Cancelled"],
            ["vu-state-closed", "Closed"],
        ],
    },
    {
        label: "Navbar & Sidebar",
        tokens: [
            ["vu-navbar-bg", "Navbar background"],
            ["vu-navbar-text", "Navbar text"],
            ["vu-sidebar-bg", "Sidebar background"],
            ["vu-sidebar-text", "Sidebar text"],
            ["vu-sidebar-hover", "Sidebar hover"],
        ],
    },
    {
        label: "Buttons",
        tokens: [
            ["vu-btn-primary-bg", "Primary button"],
            ["vu-btn-primary-text", "Primary button text"],
            ["vu-btn-primary-hover", "Primary button hover"],
            ["vu-btn-secondary-bg", "Secondary button"],
            ["vu-btn-secondary-text", "Secondary button text"],
            ["vu-btn-secondary-hover", "Secondary button hover"],
        ],
    },
    {
        label: "Status bar & Tabs",
        tokens: [
            ["vu-statusbar-btn-bg", "Status bar button"],
            ["vu-statusbar-btn-text", "Status bar button text"],
            ["vu-statusbar-btn-border", "Status bar button border"],
            ["vu-tab-active", "Active tab"],
            ["vu-focus-ring", "Focus ring"],
        ],
    },
];

const SHAPE_FIELDS = [
    ["vu-radius-sm", "Radius — small", ["2px", "4px", "6px", "8px"]],
    ["vu-radius-md", "Radius — medium", ["4px", "6px", "8px", "10px", "12px"]],
    ["vu-radius-lg", "Radius — large", ["6px", "8px", "12px", "16px"]],
    ["vu-font-size-base", "Base font size", ["0.75rem", "0.8125rem", "0.875rem", "1rem"]],
    ["vu-table-row-py", "Table density", ["2px", "3px", "4px", "6px", "8px"]],
];

// Defaults shown when the token has no draft value (compiled biz defaults)
const BASE_DEFAULTS = {
    "vu-brand-primary": "#5A4BB0", "vu-brand-primary-dark": "#4A3D96",
    "vu-brand-secondary": "#0891B2", "vu-brand-accent": "#0891B2",
    "vu-link-color": "#5A4BB0",
    "vu-surface-app": "#FFFFFF", "vu-surface-panel": "#FAFAFA",
    "vu-surface-card": "#FFFFFF", "vu-surface-muted": "#F5F5F5",
    "vu-surface-hover": "#EDEAF8",
    "vu-text-primary": "#212121", "vu-text-secondary": "#424242",
    "vu-text-inverse": "#FFFFFF",
    "vu-border-soft": "#E0E0E0", "vu-border-strong": "#C7C7C7",
    "vu-status-success": "#0F8A63", "vu-status-info": "#0891B2",
    "vu-status-warning": "#B7791F", "vu-status-danger": "#C0332A",
    "vu-state-draft": "#64748b", "vu-state-confirmed": "#5A4BB0",
    "vu-state-assigned": "#6E72B0", "vu-state-active": "#B7791F",
    "vu-state-completed": "#0F8A63", "vu-state-cancelled": "#C0332A",
    "vu-state-closed": "#475569",
    "vu-navbar-bg": "#0E1430", "vu-navbar-text": "#FFFFFF",
    "vu-sidebar-bg": "#0E1430", "vu-sidebar-text": "#E8EDF8",
    "vu-sidebar-hover": "#1B2138",
    "vu-btn-primary-bg": "#5A4BB0", "vu-btn-primary-text": "#FFFFFF",
    "vu-btn-primary-hover": "#4A3D96",
    "vu-btn-secondary-bg": "#F5F5F5", "vu-btn-secondary-text": "#424242",
    "vu-btn-secondary-hover": "#EDEAF8",
    "vu-statusbar-btn-bg": "#FFFFFF", "vu-statusbar-btn-text": "#495057",
    "vu-statusbar-btn-border": "#E0E0E0",
    "vu-tab-active": "#5A4BB0", "vu-focus-ring": "#5A4BB0",
    "vu-radius-sm": "4px", "vu-radius-md": "8px", "vu-radius-lg": "12px",
    "vu-font-size-base": "0.8125rem", "vu-table-row-py": "4px",
};

function relLuminance(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
    if (!m) return null;
    const [r, g, b] = [0, 2, 4].map((i) => {
        let c = parseInt(m[1].slice(i, i + 2), 16) / 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(fg, bg) {
    const l1 = relLuminance(fg);
    const l2 = relLuminance(bg);
    if (l1 === null || l2 === null) return null;
    const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
    return (hi + 0.05) / (lo + 0.05);
}

// Pairs that must stay readable (label, fg token, bg token, minimum ratio)
const CONTRAST_PAIRS = [
    ["Body text on cards", "vu-text-primary", "vu-surface-card", 4.5],
    ["Secondary text on cards", "vu-text-secondary", "vu-surface-card", 4.5],
    ["Primary button label", "vu-btn-primary-text", "vu-btn-primary-bg", 4.5],
    ["Navbar text", "vu-navbar-text", "vu-navbar-bg", 4.5],
    ["Sidebar text", "vu-sidebar-text", "vu-sidebar-bg", 4.5],
    ["Links on content", "vu-link-color", "vu-surface-panel", 4.5],
];

export class ThemeStudioAction extends Component {
    static template = "biz_theme.ThemeStudio";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.loader = useService("biz_theme_loader");
        this.groups = GROUPS;
        this.shapeFields = SHAPE_FIELDS;
        this.state = useState({
            presets: [],
            tokens: {},          // draft overrides only (sparse)
            presetKey: null,
            themeName: "Custom theme",
            previewing: false,
            dirty: false,
            undoStack: [],
            redoStack: [],
            activeGroup: "Brand",
        });

        onWillStart(async () => {
            this.state.presets = await this.orm.searchRead(
                "biz.theme.preset", [],
                ["key", "name", "description", "token_values", "preview_colors"],
                { order: "sequence" }
            );
            const published = await this.orm.searchRead(
                "biz.theme", [["state", "=", "published"]],
                ["name", "preset_key", "token_values"], { limit: 1 }
            );
            if (published.length) {
                this.state.tokens = { ...(published[0].token_values || {}) };
                this.state.presetKey = published[0].preset_key;
                this.state.themeName = published[0].name;
            }
            // An unfinished draft (this tab) outranks the published theme —
            // re-entering the Studio must never silently drop edits.
            const draft = this.loader.getDraft();
            if (draft && Object.keys(draft).length) {
                this.state.tokens = { ...draft };
                this.state.dirty = true;
            }
            this.state.previewing = this.loader.isPreviewing();
            this._applyLocal();
        });
    }

    // ------------------------------------------------------------------
    // Token access
    // ------------------------------------------------------------------
    value(key) {
        return this.state.tokens[key] || BASE_DEFAULTS[key] || "";
    }

    isOverridden(key) {
        return key in this.state.tokens;
    }

    _snapshot() {
        this.state.undoStack.push(JSON.stringify(this.state.tokens));
        if (this.state.undoStack.length > 100) this.state.undoStack.shift();
        this.state.redoStack = [];
    }

    setToken(key, value) {
        this._snapshot();
        if (!value || value === BASE_DEFAULTS[key]) {
            delete this.state.tokens[key];
        } else {
            this.state.tokens[key] = value;
        }
        this.state.dirty = true;
        this._applyLocal();
    }

    resetToken(key) {
        this._snapshot();
        delete this.state.tokens[key];
        this.state.dirty = true;
        this._applyLocal();
    }

    onColorInput(key, ev) {
        this.setToken(key, ev.target.value.toUpperCase());
    }

    onTextInput(key, ev) {
        const v = ev.target.value.trim();
        if (/^#[0-9a-fA-F]{6}$/.test(v) || v === "") {
            this.setToken(key, v.toUpperCase());
        }
    }

    onShapeChange(key, ev) {
        this.setToken(key, ev.target.value);
    }

    undo() {
        if (!this.state.undoStack.length) return;
        this.state.redoStack.push(JSON.stringify(this.state.tokens));
        this.state.tokens = JSON.parse(this.state.undoStack.pop());
        this.state.dirty = true;
        this._applyLocal();
    }

    redo() {
        if (!this.state.redoStack.length) return;
        this.state.undoStack.push(JSON.stringify(this.state.tokens));
        this.state.tokens = JSON.parse(this.state.redoStack.pop());
        this._applyLocal();
    }

    resetAll() {
        this._snapshot();
        this.state.tokens = {};
        this.state.presetKey = "default";
        this.state.dirty = true;
        this._applyLocal();
    }

    // ------------------------------------------------------------------
    // Presets / import / export
    // ------------------------------------------------------------------
    applyPreset(preset) {
        this._snapshot();
        this.state.tokens = { ...(preset.token_values || {}) };
        this.state.presetKey = preset.key;
        this.state.themeName = preset.name;
        this.state.dirty = true;
        this._applyLocal();
    }

    exportJson() {
        const blob = new Blob([JSON.stringify(this.state.tokens, null, 2)], {
            type: "application/json",
        });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `${(this.state.themeName || "theme").replace(/\s+/g, "_")}.json`;
        a.click();
        URL.revokeObjectURL(a.href);
    }

    async importJson(ev) {
        const file = ev.target.files[0];
        if (!file) return;
        try {
            const tokens = JSON.parse(await file.text());
            if (typeof tokens !== "object" || Array.isArray(tokens)) throw new Error();
            this._snapshot();
            this.state.tokens = tokens;
            this.state.dirty = true;
            this._applyLocal();
            this.notification.add("Theme imported.", { type: "success" });
        } catch {
            this.notification.add("Invalid theme file.", { type: "danger" });
        }
        ev.target.value = "";
    }

    // ------------------------------------------------------------------
    // Contrast (WCAG AA)
    // ------------------------------------------------------------------
    get contrastIssues() {
        const issues = [];
        for (const [label, fg, bg, min] of CONTRAST_PAIRS) {
            const ratio = contrastRatio(this.value(fg), this.value(bg));
            if (ratio !== null && ratio < min) {
                issues.push({ label, ratio: ratio.toFixed(2), min });
            }
        }
        return issues;
    }

    // ------------------------------------------------------------------
    // Preview / publish / discard
    // ------------------------------------------------------------------
    _applyLocal() {
        if (this.state.dirty) {
            // Real edits: persist so the preview follows across app pages
            this.loader.preview(this.state.tokens);
            this.state.previewing = true;
        } else {
            // Pristine state (== published theme): reflect locally only,
            // never write an empty draft into sessionStorage
            applyDraftTokens(this.state.tokens);
        }
    }

    stopPreview() {
        this.loader.stopPreview();
        this.state.previewing = false;
    }

    async publish() {
        const issues = this.contrastIssues;
        const body = issues.length
            ? `Warning: ${issues.length} contrast pair(s) fall below WCAG AA ` +
              `(${issues.map((i) => i.label).join(", ")}). Publish for ALL users anyway?`
            : "Publish this theme for ALL users?";
        this.dialog.add(ConfirmationDialog, {
            title: "Publish theme",
            body,
            confirmLabel: "Publish",
            confirm: async () => {
                const id = await this.orm.create("biz.theme", [{
                    name: this.state.themeName || "Custom theme",
                    preset_key: this.state.presetKey,
                    token_values: this.state.tokens,
                }]);
                await this.orm.call("biz.theme", "action_publish", [id]);
                this.loader.stopPreview();
                window.location.reload();
            },
            cancel: () => {},
        });
    }

    discard() {
        this.loader.stopPreview();
        this.state.tokens = {};
        this.state.dirty = false;
        this.state.undoStack = [];
        this.state.redoStack = [];
        // Reload published state
        window.location.reload();
    }
}

registry.category("actions").add("biz_theme.theme_studio", ThemeStudioAction);
