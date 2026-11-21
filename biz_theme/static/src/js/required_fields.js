/** @odoo-module **/
import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

const controls = "input:not([type=hidden]), textarea, select, [contenteditable=true]";
export const validationScopes = "[data-biz-validation-scope], form, .pbim-modal, .pplw-card, [role=dialog]";
export const nativeFormRoots = new WeakMap();

export function isEditable(element) {
    return !element.disabled && !element.readOnly && !element.closest("[inert], .o_readonly_modifier, .o_invisible_modifier");
}
function associatedLabel(element) {
    return element.labels?.[0] || element.closest("label") ||
        (element.previousElementSibling?.matches("label") && element.previousElementSibling);
}
function labelText(label) {
    // Required badges, input contents and select options are not the field name.
    const copy = label?.cloneNode(true);
    for (const child of copy?.querySelectorAll(`${controls}, .pbva-field-required`) || []) child.remove();
    return copy?.textContent || "";
}
export function fieldLabel(element) {
    const explicit = element.getAttribute("data-biz-required-label") || element.getAttribute("data-biz-required") || element.getAttribute("aria-label");
    if (explicit) return explicit;
    return (labelText(associatedLabel(element)) || element.getAttribute("placeholder") || _t("Required field"))
        .replace(/\s*\*\s*$/, "").replace(/\s+Required\s*$/, "").trim();
}
function declaredRequired(element) {
    if (element.required || element.getAttribute("aria-required") === "true" || element.hasAttribute("data-biz-required")) return true;
    const label = associatedLabel(element);
    return !!label && (/\*\s*$/.test(labelText(label)) || !!label.querySelector(".pbva-field-required"));
}
export function isMissing(element) {
    if (element.hasAttribute("data-biz-missing")) return element.getAttribute("data-biz-missing") === "true";
    if (element.type === "checkbox") return !element.checked;
    if (element.type === "radio") {
        return ![...(element.form || element.closest(validationScopes) || element.ownerDocument).querySelectorAll("input[type=radio]")]
            .some(radio => radio.name === element.name && radio.checked);
    }
    if (element.type === "file") return !element.files?.length;
    if (element.tagName === "SELECT" && element.multiple) return !element.selectedOptions.length;
    if (element.isContentEditable) return !element.textContent.trim();
    return !String(element.value ?? "").trim();
}
export function collectRequired(scope) {
    const fields = [];
    const radios = new Set();
    for (const element of scope.querySelectorAll(`${controls}, [data-biz-required]`)) {
        if (!isEditable(element) || !element.getClientRects().length || getComputedStyle(element).visibility === "hidden" || !declaredRequired(element) || !isMissing(element)) continue;
        if (element.type === "radio") {
            if (radios.has(element.name)) continue;
            radios.add(element.name);
        }
        fields.push({ label: fieldLabel(element), element, target: () => element });
    }
    return fields;
}
export function highlightField(element) {
    if (!element?.isConnected) return;
    element.classList.add("biz-required-invalid");
    element.setAttribute("aria-invalid", "true");
}
export function clearField(element) {
    element.classList.remove("biz-required-invalid");
    // Native field widgets own their own invalid state.
    if (!element.matches(".o_field_widget")) element.removeAttribute("aria-invalid");
}
export async function focusField(field) {
    const element = await field.target();
    if (!element?.isConnected) return;
    highlightField(element);
    element.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" });
    const input = element.matches(controls) ? element : [...element.querySelectorAll(`${controls}, [tabindex], button`)].find(el => isEditable(el) && el.getClientRects().length && el.getAttribute("aria-disabled") !== "true");
    if (input && isEditable(input)) input.focus({ preventScroll: true });
    else { element.setAttribute("tabindex", "-1"); element.focus({ preventScroll: true }); }
}

export class RequiredFieldsDialog extends Component {
    static template = "biz_theme.RequiredFieldsDialog";
    static components = { Dialog };
    static props = { fields: Array, close: Function };
    get title() { return _t("Complete the required fields"); }
}

/** One validator per web client; explicit destroy also supports isolated tests. */
export function createRequiredValidation(dialog, eventRoot = document, keyboardRoot = window) {
    let closePopup = null;
    const listeners = [];
    const listen = (root, name, handler) => {
        root.addEventListener(name, handler, true);
        listeners.push(() => root.removeEventListener(name, handler, true));
    };
    function show(fields) {
        if (!fields.length || closePopup) return () => {};
        for (const field of fields) highlightField(field.element);
        closePopup = dialog.add(RequiredFieldsDialog, { fields }, {
            onClose: () => {
                closePopup = null;
                // Let the overlay unmount and restore its focus first.
                requestAnimationFrame(() => requestAnimationFrame(() => focusField(fields[0])));
            },
        });
        return closePopup;
    }
    function validate(scope) {
        const fields = collectRequired(scope);
        if (!fields.length) return true;
        show(fields);
        return false;
    }
    listen(eventRoot, "click", ev => {
        const action = ev.target.closest?.("[data-biz-validate], button[type=submit], input[type=submit]");
        if (!action || action.disabled || action.closest(".biz-required-dialog")) return;
        const scope = action.closest(validationScopes);
        if (!scope || scope.closest(".o_form_view")) return;
        if (!validate(scope)) { ev.preventDefault(); ev.stopImmediatePropagation(); }
    });
    listen(eventRoot, "submit", ev => {
        if (!ev.target.matches("form") || ev.target.closest(".o_form_view")) return;
        if (!validate(ev.target)) { ev.preventDefault(); ev.stopImmediatePropagation(); }
    });
    // Browser validation can stop submission before a submit event exists.
    listen(eventRoot, "invalid", ev => {
        const scope = ev.target.closest?.("form");
        if (scope && declaredRequired(ev.target) && isMissing(ev.target)) {
            ev.preventDefault(); show(collectRequired(scope));
        }
    });
    // Custom panels have their own Escape handlers. Close only this popup.
    listen(keyboardRoot, "keydown", ev => {
        if (ev.key === "Escape" && closePopup) {
            ev.preventDefault(); ev.stopImmediatePropagation(); closePopup();
        }
    });
    const clear = ev => {
        const element = ev.target;
        if (element.matches?.(controls) && !isMissing(element)) {
            clearField(element);
            const widget = element.closest(".biz-required-invalid.o_field_widget, .biz-required-invalid.o_field_cell");
            if (widget) clearField(widget);
        }
        // Reactive choice groups update their missing flag after their handler.
        requestAnimationFrame(() => {
            const scope = element.closest?.(validationScopes);
            for (const group of scope?.querySelectorAll("[data-biz-required].biz-required-invalid") || []) {
                if (!isMissing(group)) clearField(group);
            }
        });
    };
    listen(eventRoot, "input", clear);
    listen(eventRoot, "change", clear);
    listen(eventRoot, "click", clear);
    return { show, validate, destroy() { closePopup?.(); listeners.forEach(remove => remove()); } };
}
registry.category("services").add("biz_required_fields", {
    dependencies: ["dialog"],
    start(env, { dialog }) { return createRequiredValidation(dialog); },
});
