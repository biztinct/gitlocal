/** @odoo-module **/
import { toRaw, useEffect, useRef } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { Record } from "@web/model/relational_model/record";
import { FormRenderer } from "@web/views/form/form_renderer";
import { nativeFormRoots } from "@biz_theme/js/required_fields";

patch(FormRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        const root = useRef("compiled_view_root");
        useEffect((record) => {
            nativeFormRoots.set(toRaw(record), root);
            return () => nativeFormRoots.delete(toRaw(record));
        }, () => [this.props.record, root.el]);
    },
});
function fieldWidget(record, name, fallbackRoot) {
    let root = nativeFormRoots.get(toRaw(record))?.el || fallbackRoot?.();
    const ownRoot = nativeFormRoots.get(toRaw(record))?.el;
    const row = root && [...root.querySelectorAll(".o_data_row[data-id]")]
        .find(el => el.getAttribute("data-id") === record.id);
    if (row) root = row;
    else if (!ownRoot && fallbackRoot) return null;
    if (!root) return null;
    return [...root.querySelectorAll(".o_field_widget[name], .o_field_cell[name]")].find(el => el.getAttribute("name") === name);
}
async function revealField(record, name, fallbackRoot) {
    const root = nativeFormRoots.get(toRaw(record))?.el || fallbackRoot?.();
    if (!root?.isConnected) return null;
    const visited = new Set();
    for (let i = 0; i < 20; i++) {
        const widget = fieldWidget(record, name, fallbackRoot);
        if (widget) {
            for (let node = widget.parentElement; node && node !== root; node = node.parentElement) {
                if (node.tagName === "DETAILS") node.open = true;
            }
        }
        if (widget?.getClientRects().length) {
            if (widget.matches(".o_field_cell") && !widget.querySelector("input, textarea, select")) {
                widget.click();
                await new Promise(requestAnimationFrame);
                return fieldWidget(record, name, fallbackRoot);
            }
            return widget;
        }
        // Native validation marks notebook pages containing invalid fields.
        // Those pages may not have mounted their inputs yet.
        const tab = [...root.querySelectorAll(".o_notebook .nav-link.o_page_invalid:not(.active)")]
            .find(el => !visited.has(el.getAttribute("name") || el.textContent));
        if (!tab) {
            // A notebook activates its tab before its asynchronous pane mounts.
            // Keep waiting for the field instead of returning a missing node.
            await new Promise(requestAnimationFrame);
            continue;
        }
        visited.add(tab.getAttribute("name") || tab.textContent);
        tab.click();
        await new Promise(requestAnimationFrame);
    }
    return fieldWidget(record, name, fallbackRoot);
}
export function missingRecordFields(record, prefix = "", fallbackRoot) {
    const fields = [];
    for (const name of record._unsetRequiredFields || []) {
        const metadata = record.fields[name];
        const label = prefix + (record.activeFields[name]?.string || metadata.string || name);
        if (["one2many", "many2many"].includes(metadata.type) && record.data[name]?.count) {
            for (const [i, child] of record.data[name].records.entries()) {
                fields.push(...missingRecordFields(child, `${label} (${i + 1}) / `,
                    () => nativeFormRoots.get(toRaw(record))?.el || fallbackRoot?.()));
            }
        } else {
            fields.push({ label, element: fieldWidget(record, name, fallbackRoot), target: () => revealField(record, name, fallbackRoot) });
        }
    }
    return fields;
}
patch(Record.prototype, {
    _displayInvalidFieldNotification() {
        const validation = this.model.env.services.biz_required_fields;
        const fields = missingRecordFields(this);
        if (validation && fields.length) return validation.show(fields);
        return super._displayInvalidFieldNotification(...arguments);
    },
});
