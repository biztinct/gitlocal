import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

/**
 * WDGAP QF3 — the "Request time off" form on My Leave.
 *
 * The form works without this file: it is a plain multipart POST and the
 * server checks everything again (the part of the day, the times, the
 * documents, the dates). This file holds no words — every sentence is in the
 * QWeb template or comes back from the server — and adds:
 *
 *  - only the controls the chosen kind of leave uses: "Full day / Morning /
 *    Afternoon" for a kind counted in half days, from/to times for a kind
 *    counted in hours, nothing extra for whole days;
 *  - the document block says "needed" for a kind that asks for one;
 *  - the live preview: how much this request counts and what is left after
 *    it, asked from `/my/work/leave/preview` (read-only) as the fields change;
 *  - the chosen files are named under the buttons; one over 10 MB or of
 *    another kind is flagged before sending (the server still decides).
 */
const MAX_BYTES = 10 * 1024 * 1024;
const TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
const DEBOUNCE_MS = 250;

function toggle(el, show) {
    if (el) {
        el.classList.toggle("d-none", !show);
    }
}

export class PbEwLeaveForm extends Interaction {
    static selector = "form[data-pbew-leave-form]";
    dynamicContent = {
        _root: {
            "t-on-change.noUpdate": this.onChange,
            "t-on-input.noUpdate": this.onInput,
            "t-on-submit.noUpdate": this.onSubmit,
        },
    };

    setup() {
        this.timer = null;
        this.seq = 0;
        this.sending = false;
    }

    start() {
        toggle(this.q("[data-pbew-docstatic]"), false);
        this.refresh();
    }

    destroy() {
        clearTimeout(this.timer);
    }

    q(sel) {
        return this.el.querySelector(sel);
    }

    value(name) {
        const el = this.el.querySelector(`[name="${name}"]`);
        return el ? el.value : "";
    }

    selectedType() {
        const select = this.q("[data-pbew-type]");
        const opt = select && select.selectedOptions && select.selectedOptions[0];
        return {
            unit: (opt && opt.dataset.unit) || "day",
            doc: opt && opt.dataset.doc === "1",
        };
    }

    onChange(ev) {
        if (ev.target.matches("[data-pbew-file]")) {
            this.showFiles();
            return;
        }
        this.refresh();
    }

    onInput(ev) {
        if (ev.target.matches("input[type=date], input[type=time]")) {
            this.refresh();
        }
    }

    onSubmit(ev) {
        if (this.sending) {
            ev.preventDefault();
            return;
        }
        this.sending = true;
        const button = this.el.querySelector("button[type=submit]");
        if (button) {
            button.setAttribute("aria-busy", "true");
        }
    }

    refresh() {
        const { unit, doc } = this.selectedType();
        const from = this.value("date_from");
        const to = this.value("date_to");
        const oneDay = !from || !to || from === to;
        // the part-of-day controls the chosen kind uses, and only those
        toggle(this.q('[data-pbew-part="half_day"]'), unit === "half_day");
        toggle(this.q('[data-pbew-part="hour"]'), unit === "hour");
        for (const el of this.el.querySelectorAll("[data-pbew-many]")) {
            toggle(el, !oneDay);
        }
        toggle(this.q("[data-pbew-one]"), oneDay);
        const pfrom = this.q("[data-pbew-pfrom]");
        if (pfrom) {
            const morning = pfrom.querySelector("[data-pbew-oneonly]");
            if (morning) {
                morning.hidden = !oneDay;
                morning.disabled = !oneDay;
                if (!oneDay && pfrom.value === "am") {
                    pfrom.value = "full";
                }
            }
        }
        // the kind's own fields only: a hidden control must not be sent
        for (const el of this.el.querySelectorAll('[data-pbew-part="half_day"] select')) {
            el.disabled = unit !== "half_day";
        }
        for (const el of this.el.querySelectorAll('[data-pbew-part="hour"] input')) {
            el.disabled = unit !== "hour";
        }
        // documents: prominent when the kind asks for one
        const docs = this.q("[data-pbew-docs]");
        if (docs) {
            docs.classList.toggle("is-needed", doc);
        }
        toggle(this.q("[data-pbew-docneed]"), doc);
        toggle(this.q("[data-pbew-docopt]"), !doc);
        this.schedulePreview();
    }

    schedulePreview() {
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.preview(), DEBOUNCE_MS);
    }

    async preview() {
        const box = this.q("[data-pbew-preview]");
        if (!box) {
            return;
        }
        const from = this.value("date_from");
        const to = this.value("date_to");
        if (!from || !to) {
            toggle(box, false);
            return;
        }
        const { unit } = this.selectedType();
        const seq = ++this.seq;
        let res;
        try {
            res = await this.waitFor(
                rpc("/my/work/leave/preview", {
                    type_id: this.value("type_id"),
                    date_from: from,
                    date_to: to,
                    period_from: unit === "half_day" ? this.value("period_from") : "",
                    period_to: unit === "half_day" && from !== to ? this.value("period_to") : "",
                    hour_from: unit === "hour" ? this.value("hour_from") : "",
                    hour_to: unit === "hour" ? this.value("hour_to") : "",
                })
            );
        } catch {
            return;            // the preview is a help, never a blocker
        }
        if (seq !== this.seq || !res) {
            return;
        }
        const amount = this.q("[data-pbew-amount]");
        const after = this.q("[data-pbew-after]");
        const warn = this.q("[data-pbew-warn]");
        const err = this.q("[data-pbew-err]");
        if (!res.ok) {
            amount.textContent = "";
            after.textContent = "";
            toggle(warn, false);
            err.textContent = res.error || "";
            toggle(err, Boolean(res.error));
            toggle(box, Boolean(res.error));
            return;
        }
        amount.textContent = res.amount_label || "";
        after.textContent = res.after_label || "";
        toggle(after, Boolean(res.after_label));
        warn.textContent = res.warning || "";
        toggle(warn, Boolean(res.warning));
        err.textContent = res.error || "";
        toggle(err, Boolean(res.error));
        box.classList.toggle("is-over", Boolean(res.over));
        toggle(box, true);
    }

    showFiles() {
        const names = [];
        let tooBig = false;
        let wrongKind = false;
        for (const input of this.el.querySelectorAll("[data-pbew-file]")) {
            for (const file of input.files || []) {
                names.push(file.name);
                tooBig = tooBig || file.size > MAX_BYTES;
                wrongKind = wrongKind || (file.type && !TYPES.includes(file.type));
            }
        }
        const label = this.q("[data-pbew-docnames]");
        if (label) {
            label.textContent = names.join(", ");
            toggle(label, names.length > 0);
        }
        toggle(this.q('[data-pbew-docwarn="size"]'), tooBig);
        toggle(this.q('[data-pbew-docwarn="type"]'), wrongKind);
    }
}

/** The "Add a document" form on a row: names the chosen files. */
export class PbEwLeaveDocForm extends Interaction {
    static selector = "form[data-pbew-docform]";
    dynamicContent = {
        _root: { "t-on-change.noUpdate": this.onChange },
    };

    onChange() {
        PbEwLeaveForm.prototype.showFiles.call(this);
    }

    q(sel) {
        return this.el.querySelector(sel);
    }
}

registry.category("public.interactions").add("pb_ess_workforce.leave_form", PbEwLeaveForm);
registry.category("public.interactions").add("pb_ess_workforce.leave_doc_form", PbEwLeaveDocForm);
