import { patch } from "@web/core/utils/patch";
import { FormCompiler } from "@web/views/form/form_compiler";
import { SettingsFormCompiler } from "@web/webclient/settings_form_view/settings_form_compiler";
import { append, createElement } from "@web/core/utils/xml";
import { vuIconForSection } from "./vu_form_hero_registry";

/**
 * VU Form Engine — compile-time enhancement of every native form view.
 *
 * Contract (mirrors mail's chatter relocation patch):
 *  - The restructured markup is baked into the cached template, but stays
 *    INERT until the renderer adds `.vu-form` at render time
 *    (see vu_form_renderer.js — dialogs/kill-switch/excluded models stay stock).
 *  - Structural anchors (.o_form_sheet_bg, .o_form_sheet, chatter hooks) are
 *    never renamed or removed, so mail/muk_web_chatter patches keep working.
 *  - The native .oe_title node is MOVED (not cloned) into the hero — the Field
 *    component inside stays the same editable instance.
 */

// Bespoke form views that keep their hand-built UI.
// (admin_model_navigator_view was removed — it's a LIST js_class, never a
//  form, so it never matched here; the admin record forms it links to are
//  native and already get the engine skin.)
const VU_EXCLUDED_JS_CLASS = new Set([
    "synconics_bi_dashboard_form_view",
]);

// Views that bring their OWN identity header (js_class chrome) — they keep the
// full engine skin (cards, tabs, chatter) but the auto-hero is suppressed so
// the record name/status isn't shown twice. Also honoured: class="vu-no-hero"
// on the <form> arch.
const VU_NO_HERO_JS_CLASS = new Set([
    "fin_invoice_form_view",
    // Phase 3 migration: booking cockpit keeps its controller (side sheets)
    // and its own sticky header; layout + skin now come from the engine
    "ops_booking_form",
    // Phase 3 migration: client profile keeps its OWL chrome (hero with
    // avatar + stat strip + right action sidebar); engine skins the form
    "ops_client_profile_form",
    // Phase 3 migration: CRM contact form keeps its OWL header (contact
    // name + status + action buttons); engine skins the vu-card sections
    "crm_contact_form_view",
]);

function buildHero(res) {
    const sheet = res.querySelector(".o_form_sheet");
    if (!sheet || sheet.querySelector(".vu-hero")) {
        return; // nosheet forms get the CSS skin only — fail closed
    }
    const hero = createElement("div", { class: "vu-hero" });

    // Native avatar/image block (res.partner, hr.employee, product…) joins the
    // hero. NOT inside a t-if container — it must keep rendering in inert mode.
    // [class*=…] also matches compiled <Field> components, whose class attr is
    // a quoted JS expression ('oe_avatar') that plain .oe_avatar misses.
    const avatar = sheet.querySelector(
        '.oe_avatar, .o_employee_avatar, [class*="oe_avatar"], [class*="o_employee_avatar"]'
    );
    if (avatar) {
        if (avatar.tagName === "Field") {
            // component node: class is an expression → append as literal
            const prev = avatar.getAttribute("class");
            avatar.setAttribute("class", prev ? `${prev} + ' vu-hero-pic'` : "'vu-hero-pic'");
        } else {
            avatar.classList.add("vu-hero-pic");
        }
        append(hero, avatar);
    }

    const glance = createElement("div", {
        class: "vu-hero-glance",
        "t-if": "__comp__.vuFormEnabled",
    });
    append(
        glance,
        createElement("div", {
            class: "vu-hero-avatar",
            "t-if": "__comp__.vuInitials",
            "t-esc": "__comp__.vuInitials",
        })
    );
    append(hero, glance);

    const main = createElement("div", { class: "vu-hero-main" });
    const title = sheet.querySelector(".oe_title");
    if (title) {
        append(main, title); // moves the compiled node — same Field, still editable
    } else {
        append(
            main,
            createElement("span", {
                class: "vu-hero-name",
                "t-if": "__comp__.vuFormEnabled",
                "t-esc": "__comp__.vuTitleValue",
            })
        );
    }
    append(hero, main);

    const meta = createElement("div", {
        class: "vu-hero-meta",
        "t-if": "__comp__.vuFormEnabled",
    });
    const statusChip = createElement("span", {
        class: "vu-hero-status",
        "t-if": "__comp__.vuStatus",
        "t-esc": "__comp__.vuStatus.label",
        "t-att-data-vu-state": "__comp__.vuStatus.value",
    });
    append(meta, statusChip);
    append(hero, meta);

    sheet.prepend(hero);
}

patch(FormCompiler.prototype, {
    compile(key, params = {}) {
        const res = super.compile(...arguments);
        try {
            if (params.isSubView) {
                return res; // x2many subviews stay stock (rendered in dialogs/inline)
            }
            if (this instanceof SettingsFormCompiler) {
                return res; // res.config.settings has its own dedicated UI
            }
            const arch = this.templates[key];
            if (!arch || arch.tagName !== "form") {
                return res;
            }
            const jsClass = arch.getAttribute("js_class");
            if (jsClass && VU_EXCLUDED_JS_CLASS.has(jsClass)) {
                return res;
            }
            const archClasses = (arch.getAttribute("class") || "").split(/\s+/);
            if (archClasses.includes("vu-form-native")) {
                return res; // per-view opt-out
            }
            const root = res.querySelector(".o_form_renderer");
            if (!root) {
                return res;
            }
            // Runtime activation: one cached template serves stock AND vu modes
            const prevClass = root.getAttribute("t-attf-class") || "";
            root.setAttribute(
                "t-attf-class",
                `${prevClass} {{ __comp__.vuFormEnabled ? 'vu-form' : '' }}`
            );
            const noHero =
                (jsClass && VU_NO_HERO_JS_CLASS.has(jsClass)) ||
                archClasses.includes("vu-no-hero");
            if (noHero) {
                // marker for CSS (e.g. hide the duplicate .oe_title — the
                // view's own header already displays name/status)
                root.classList.add("vu-no-hero");
            } else {
                buildHero(res);
            }
        } catch (error) {
            // Fail closed to a fully stock form — never break rendering
            console.warn("vu_form_engine: enhancement skipped", error);
        }
        return res;
    },

    compileGroup(el, params) {
        const res = super.compileGroup(...arguments);
        try {
            // InnerGroups become section cards; icon derives from the title.
            // NOTE: `class` on component nodes is a JS EXPRESSION (see
            // copyAttributes in view_compiler.js) — it must be a quoted
            // string literal, or OWL compiles `vu-sec` as `ctx['vu']-...`.
            if (res && res.tagName === "InnerGroup") {
                const classes = ["vu-sec"];
                if (el.hasAttribute("string")) {
                    classes.push(`vu-ico-${vuIconForSection(el.getAttribute("string"))}`);
                }
                const prev = res.getAttribute("class");
                res.setAttribute(
                    "class",
                    prev ? `${prev} + ' ${classes.join(" ")}'` : `'${classes.join(" ")}'`
                );
            }
        } catch {
            // ignore — group renders stock
        }
        return res;
    },
});
