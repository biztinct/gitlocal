import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

/**
 * Expenses on My Payobook (ETP E1). Every page works without this script —
 * the forms are plain multipart POSTs (E-R8). It adds what makes a receipt
 * feel instant:
 *
 *  - the chosen file appears in the drop area at once (an image fills it with
 *    a soft fade, a PDF shows a document glyph and its name) and the fields
 *    settle in under it; dragging a file over the area lights it up;
 *  - the amount gets thousands separators as it is typed, the way the
 *    reader's language writes them (the server says how, in data-*);
 *  - "Add another receipt" adds the next receipt in place (a copy of the
 *    hidden blank the server drew, so this file holds no words) and a running
 *    total appears under the stack;
 *  - the send button explains why it cannot be pressed yet (no file, no
 *    amount, no category — the three reasons are drawn hidden in the page);
 *  - Cmd/Ctrl + Enter sends; Esc in the note folds it away; a double press
 *    never sends twice; the one-off `done` / `fresh` keys leave the address
 *    bar once shown; arrow keys / j / k move between claims on the list.
 */
const MAX_BYTES = 10 * 1024 * 1024;
const TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"];

function escapeRe(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export class PbExpenseForm extends Interaction {
    static selector = ".pbex";
    dynamicContent = {
        _root: {
            "t-on-change.noUpdate": this.onChange,
            "t-on-input.noUpdate": this.onInput,
            "t-on-click.noUpdate": this.onClick,
            "t-on-keydown.noUpdate": this.onKeydown,
            "t-on-submit.noUpdate": this.onSubmit,
            "t-on-dragenter.noUpdate": this.onDrag,
            "t-on-dragover.noUpdate": this.onDrag,
            "t-on-dragleave.noUpdate": this.onDragLeave,
            "t-on-drop.noUpdate": this.onDragLeave,
        },
    };

    setup() {
        this.urls = new Map();
    }

    start() {
        for (const form of this.el.querySelectorAll("form[data-pbex-form]")) {
            for (const input of form.querySelectorAll("[data-pbex-amount]")) {
                if (input.value) {
                    input.value = this.format(form, input.value);
                }
            }
            this.refresh(form);
        }
        const url = new URL(window.location.href);
        if (url.searchParams.has("done") || url.searchParams.has("fresh")) {
            url.searchParams.delete("done");
            url.searchParams.delete("fresh");
            window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
        }
    }

    destroy() {
        for (const objectUrl of this.urls.values()) {
            URL.revokeObjectURL(objectUrl);
        }
    }

    // ------------------------------------------------------------ money
    opts(form) {
        const d = form.dataset;
        return {
            decimals: Number(d.pbexDecimals || 0),
            thousands: d.pbexThousands === undefined ? "," : d.pbexThousands,
            point: d.pbexPoint || ".",
            symbol: d.pbexSymbol || "",
            position: d.pbexPosition || "after",
        };
    }

    /** "1200000" → "1,200,000" in the reader's separators. */
    format(form, raw) {
        const o = this.opts(form);
        const point = o.decimals > 0 ? o.point : null;
        let text = String(raw);
        let intPart = text;
        let fracPart = null;
        if (point && text.includes(point)) {
            const at = text.lastIndexOf(point);
            intPart = text.slice(0, at);
            fracPart = text.slice(at + 1).replace(/\D/g, "").slice(0, o.decimals);
        }
        intPart = intPart.replace(/\D/g, "").replace(/^0+(?=\d)/, "");
        const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, o.thousands);
        return fracPart === null ? grouped : `${grouped || "0"}${point}${fracPart}`;
    }

    parse(form, raw) {
        const o = this.opts(form);
        let text = String(raw || "");
        if (o.thousands) {
            text = text.replace(new RegExp(escapeRe(o.thousands), "g"), "");
        }
        if (o.decimals > 0 && o.point !== ".") {
            text = text.replace(new RegExp(escapeRe(o.point), "g"), ".");
        }
        if (o.decimals === 0) {
            text = text.replace(/[.,]/g, "");
        }
        const value = parseFloat(text.replace(/[^\d.]/g, ""));
        return Number.isFinite(value) ? value : 0;
    }

    money(form, value) {
        const o = this.opts(form);
        const fixed = value.toFixed(o.decimals);
        const [intPart, fracPart] = fixed.split(".");
        const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, o.thousands);
        const number = fracPart ? `${grouped}${o.point}${fracPart}` : grouped;
        return o.position === "before" ? `${o.symbol}${number}` : `${number} ${o.symbol}`;
    }

    onInput(ev) {
        const input = ev.target;
        if (input.matches("[data-pbex-amount]")) {
            const form = input.closest("form");
            const before = input.value;
            const caret = input.selectionStart ?? before.length;
            const digitsBefore = before.slice(0, caret).replace(/\D/g, "").length;
            const after = this.format(form, before);
            input.value = after;
            // keep the caret after the same number of digits
            let seen = 0;
            let pos = after.length;
            for (let i = 0; i < after.length; i++) {
                if (seen === digitsBefore) {
                    pos = i;
                    break;
                }
                if (/\d/.test(after[i])) {
                    seen++;
                }
            }
            if (digitsBefore === 0) {
                pos = 0;
            }
            try {
                input.setSelectionRange(pos, pos);
            } catch {
                // some input types refuse a selection; the value is still right
            }
            this.refresh(form);
        }
    }

    // ------------------------------------------------------------ files
    onChange(ev) {
        const input = ev.target;
        const form = input.closest("form[data-pbex-form]");
        if (!form) {
            return;
        }
        if (input.matches("[data-pbex-file]")) {
            this.onFile(input);
        }
        this.refresh(form);
    }

    onFile(input) {
        const block = input.closest("[data-pbex-block]");
        const file = input.files && input.files[0];
        // the camera button and the picker are two doors to ONE receipt
        for (const other of block.querySelectorAll("[data-pbex-file]")) {
            if (other !== input && file) {
                other.value = "";
            }
        }
        const zone = block.querySelector(".pbex-drop-zone");
        const preview = block.querySelector("[data-pbex-preview]");
        const img = block.querySelector("[data-pbex-img]");
        const doc = block.querySelector("[data-pbex-doc]");
        const problems = {
            size: Boolean(file && file.size > MAX_BYTES),
            type: Boolean(file && file.type && !TYPES.includes(file.type)),
        };
        for (const warn of block.querySelectorAll("[data-pbex-warn]")) {
            warn.classList.toggle("d-none", !problems[warn.dataset.pbexWarn]);
        }
        input.setCustomValidity(problems.size || problems.type ? " " : "");
        const old = this.urls.get(block);
        if (old) {
            URL.revokeObjectURL(old);
            this.urls.delete(block);
        }
        if (!file) {
            zone.classList.remove("has-file");
            preview.classList.add("d-none");
            return;
        }
        zone.classList.add("has-file");
        preview.classList.remove("d-none");
        if (file.type.startsWith("image/") && !problems.type) {
            const objectUrl = URL.createObjectURL(file);
            this.urls.set(block, objectUrl);
            img.src = objectUrl;
            img.classList.remove("d-none");
            // replay the fade for a second photo
            img.style.animation = "none";
            void img.offsetWidth;
            img.style.animation = "";
            doc.classList.add("d-none");
        } else {
            img.classList.add("d-none");
            img.removeAttribute("src");
            doc.classList.remove("d-none");
            doc.querySelector("[data-pbex-docname]").textContent = file.name;
        }
        const fields = block.querySelector("[data-pbex-fields]");
        fields.classList.remove("is-revealed");
        void fields.offsetWidth;
        fields.classList.add("is-revealed");
        const amount = block.querySelector("[data-pbex-amount]");
        if (amount && !amount.value && window.matchMedia("(hover: hover)").matches) {
            amount.focus({ preventScroll: true });
        }
    }

    onDrag(ev) {
        const zone = ev.target.closest && ev.target.closest(".pbex-drop-zone");
        if (zone) {
            zone.classList.add("is-over");
        }
    }

    onDragLeave(ev) {
        const zone = ev.target.closest && ev.target.closest(".pbex-drop-zone");
        if (zone) {
            zone.classList.remove("is-over");
        }
    }

    // ------------------------------------------------- more receipts
    onClick(ev) {
        const more = ev.target.closest("[data-pbex-more]");
        if (more && this.addBlock(more.closest("form"))) {
            ev.preventDefault();
            return;
        }
        const drop = ev.target.closest("[data-pbex-unblock]");
        if (drop) {
            ev.preventDefault();
            const form = drop.closest("form");
            const block = drop.closest("[data-pbex-block]");
            const old = this.urls.get(block);
            if (old) {
                URL.revokeObjectURL(old);
                this.urls.delete(block);
            }
            block.remove();
            this.renumber(form);
            this.refresh(form);
        }
    }

    /** Copy the hidden blank into the stack. False when there is no blank
     * (the claim page) or no room: the button then posts as it is. */
    addBlock(form) {
        const blank = form && form.querySelector("[data-pbex-blank]");
        const stack = form && form.querySelector("[data-pbex-stack]");
        if (!blank || !stack) {
            return false;
        }
        const blocks = stack.querySelectorAll("[data-pbex-block]");
        const max = Number(form.dataset.pbexMax) || 20;
        if (blocks.length >= max) {
            return false;
        }
        const used = [...blocks].map((b) => Number(b.dataset.pbexBlock) || 0);
        const index = Math.max(0, ...used) + 1;
        const html = blank.innerHTML
            .replaceAll("__SFX__", `_${index}`)
            .replaceAll("__IDX__", String(index))
            .replaceAll("__N__", String(blocks.length + 1));
        const holder = document.createElement("div");
        holder.innerHTML = html;
        const block = holder.firstElementChild;
        block.disabled = false;
        block.removeAttribute("disabled");
        stack.appendChild(block);
        this.renumber(form);
        this.refresh(form);
        const zone = block.querySelector(".pbex-drop-zone");
        block.scrollIntoView({ behavior: "smooth", block: "center" });
        zone?.querySelector("input")?.focus({ preventScroll: true });
        return true;
    }

    renumber(form) {
        let n = 0;
        for (const block of form.querySelectorAll("[data-pbex-stack] [data-pbex-block]")) {
            n++;
            const label = block.querySelector("[data-pbex-n]");
            if (label) {
                label.textContent = String(n);
            }
        }
    }

    // ------------------------------------------------------ send state
    blocks(form) {
        return [...form.querySelectorAll("[data-pbex-stack] [data-pbex-block]")];
    }

    blockState(form, block) {
        const hasFile = [...block.querySelectorAll("[data-pbex-file]")].some(
            (i) => i.files && i.files.length
        );
        const amountInput = block.querySelector("[data-pbex-amount]");
        const amount = amountInput ? this.parse(form, amountInput.value) : 0;
        const hasCat = Boolean(block.querySelector("[data-pbex-cat]:checked"));
        return { hasFile, amount, hasCat, empty: !hasFile && !amount };
    }

    refresh(form) {
        if (!form || !form.matches("form[data-pbex-form]")) {
            return;
        }
        const blocks = this.blocks(form);
        const have = Number(form.dataset.pbexHave || 0);
        let reason = "ok";
        let total = 0;
        for (const block of blocks) {
            const s = this.blockState(form, block);
            total += s.amount;
            // on a draft that already holds receipts, an untouched form
            // simply sends what is there
            if (have > 0 && s.empty && !s.hasCat) {
                continue;
            }
            if (reason === "ok") {
                if (!s.hasFile) {
                    reason = "file";
                } else if (!s.amount) {
                    reason = "amount";
                } else if (!s.hasCat) {
                    reason = "cat";
                }
            }
        }
        if (!blocks.length && !have) {
            reason = "file";
        }
        const send = form.querySelector("[data-pbex-send]");
        if (send) {
            send.disabled = reason !== "ok";
            for (const say of send.querySelectorAll("[data-pbex-say]")) {
                say.classList.toggle("d-none", say.dataset.pbexSay !== reason);
            }
        }
        const row = form.querySelector("[data-pbex-total-row]");
        if (row) {
            row.classList.toggle("d-none", blocks.length < 2);
            row.querySelector("[data-pbex-total]").textContent = this.money(form, total);
        }
    }

    // ------------------------------------------------------ keyboard
    onKeydown(ev) {
        const target = ev.target;
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            const form = target.closest && target.closest("form[data-pbex-form]");
            const send = form && form.querySelector("[data-pbex-send]");
            if (send && !send.disabled) {
                ev.preventDefault();
                if (form.reportValidity()) {
                    form.requestSubmit(send);
                }
            }
            return;
        }
        if (ev.key === "Escape" && target.matches && target.matches("[data-pbex-note]")) {
            const details = target.closest("details");
            if (details) {
                ev.preventDefault();
                details.open = false;
                details.querySelector("summary")?.focus();
            }
            return;
        }
        if (target.closest && target.closest("[data-pbex-rows]") && !ev.altKey && !ev.ctrlKey && !ev.metaKey) {
            const rows = [...this.el.querySelectorAll("[data-pbex-rows] a.pbex-cc")];
            const at = rows.indexOf(document.activeElement);
            let next = null;
            if (ev.key === "ArrowDown" || ev.key === "j") {
                next = rows[Math.min(rows.length - 1, at + 1)];
            } else if (ev.key === "ArrowUp" || ev.key === "k") {
                next = rows[Math.max(0, at - 1)];
            }
            if (next) {
                ev.preventDefault();
                next.focus();
            }
        }
    }

    onSubmit(ev) {
        const form = ev.target;
        if (!form.matches || !form.matches("form[data-pbex-form]")) {
            return;
        }
        if (form.classList.contains("is-sending")) {
            ev.preventDefault();
            return;
        }
        form.classList.add("is-sending");
        const button = ev.submitter;
        if (button) {
            button.classList.add("is-sending");
            button.setAttribute("aria-busy", "true");
        }
    }
}

registry.category("public.interactions").add("pb_me_expense.expense_form", PbExpenseForm);
