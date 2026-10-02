import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

/**
 * VU Form Engine — render-time activation + hero data getters.
 *
 * All getters are O(1) reads of record data ALREADY loaded by the view; the
 * engine never triggers extra fetches. Every getter fails closed (stock look).
 */

const heroRegistry = registry.category("vu_form_hero");

// Models that must always render stock, regardless of arch
const VU_EXCLUDED_MODELS = new Set([
    "res.config.settings",
    "base.module.update",
    "base.language.install",
    "ir.module.module",
]);

const TITLE_FIELD_CANDIDATES = ["display_name", "name", "complete_name", "title"];
const STATUS_FIELD_CANDIDATES = ["state", "stage_id", "status"];

function relParts(value) {
    // many2one record values: [id, label] tuple or {id, display_name} object
    if (!value) {
        return null;
    }
    if (Array.isArray(value)) {
        return { id: value[0], label: value[1] || "" };
    }
    if (typeof value === "object") {
        return { id: value.id, label: value.display_name || "" };
    }
    return null;
}

patch(FormRenderer.prototype, {
    get vuFormEnabled() {
        try {
            if (this.env.inDialog) {
                return false;
            }
            const record = this.props.record;
            if (!record || !record.resModel || VU_EXCLUDED_MODELS.has(record.resModel)) {
                return false;
            }
            if (this.vuHeroConfig.disabled) {
                return false;
            }
            // server kill-switch: ir.config_parameter pb_theme.vu_form_engine
            if ((session.vu_form_engine || "on") === "off") {
                return false;
            }
            // emergency client-side kill-switch (no deploy needed)
            try {
                if (window.localStorage.getItem("vu_form_engine") === "off") {
                    return false;
                }
            } catch {
                // storage unavailable — ignore
            }
            return true;
        } catch {
            return false; // fail closed to stock rendering
        }
    },

    get vuHeroConfig() {
        try {
            return heroRegistry.get(this.props.record.resModel, null) || {};
        } catch {
            return {};
        }
    },

    get vuTitleValue() {
        try {
            const record = this.props.record;
            const candidates = [this.vuHeroConfig.titleField, ...TITLE_FIELD_CANDIDATES].filter(
                Boolean
            );
            for (const fieldName of candidates) {
                if (!(fieldName in record.data)) {
                    continue;
                }
                const value = record.data[fieldName];
                if (!value) {
                    continue;
                }
                if (typeof value === "string") {
                    return value;
                }
                const rel = relParts(value);
                if (rel && rel.label) {
                    return rel.label;
                }
            }
            return "";
        } catch {
            return "";
        }
    },

    get vuInitials() {
        const title = (this.vuTitleValue || "").trim();
        if (!title) {
            return "";
        }
        // strip punctuation so "(Tự Động) Cấy…" → "TC", not "(T"
        const words = title
            .split(/\s+/)
            .map((w) => w.replace(/[^\p{L}\p{N}]/gu, ""))
            .filter(Boolean);
        if (!words.length) {
            return "";
        }
        const first = words[0][0] || "";
        const last = words.length > 1 ? words[words.length - 1][0] : words[0][1] || "";
        return (first + last).toUpperCase();
    },

    get vuStatus() {
        try {
            const record = this.props.record;
            const candidates = [this.vuHeroConfig.statusField, ...STATUS_FIELD_CANDIDATES].filter(
                Boolean
            );
            for (const fieldName of candidates) {
                const fieldDef = record.fields[fieldName];
                if (!fieldDef || !(fieldName in record.data)) {
                    continue;
                }
                const value = record.data[fieldName];
                if (value === false || value === null || value === undefined || value === "") {
                    continue;
                }
                if (fieldDef.type === "selection") {
                    const option = (fieldDef.selection || []).find(([key]) => key === value);
                    return { value: String(value), label: option ? option[1] : String(value) };
                }
                if (fieldDef.type === "many2one") {
                    const rel = relParts(value);
                    if (rel && rel.label) {
                        return { value: String(rel.id ?? ""), label: rel.label };
                    }
                }
            }
            return null;
        } catch {
            return null;
        }
    },
});
