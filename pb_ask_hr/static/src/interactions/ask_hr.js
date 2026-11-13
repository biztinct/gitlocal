import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

/**
 * Ask HR on My Payobook (TIERS T3a). Every page works without this script;
 * it only adds the conveniences of a good chat:
 *
 *  - the chosen files appear as chips (name + size) under the picker, and the
 *    picker's own warnings (drawn hidden in the template — this file holds no
 *    words) show before sending when there are too many, a wrong type, or a
 *    file over 10 MB; the server checks the same things again;
 *  - Ctrl/Cmd + Enter sends the form; the send button is locked once pressed
 *    so a double click never sends twice;
 *  - text boxes grow with what is typed;
 *  - the one-off `done` / `error` keys are dropped from the address bar once
 *    shown, so a reload does not toast again;
 *  - arrow keys move between rows on the list.
 */
const MAX_BYTES = 10 * 1024 * 1024;
const TYPES = ["application/pdf", "image/png", "image/jpeg"];

function fmtSize(bytes) {
    if (bytes >= 1024 * 1024) {
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export class PbAskHr extends Interaction {
    static selector = ".pbah";
    dynamicContent = {
        "[data-pbah-files]": { "t-on-change.withTarget": this.onFiles },
        "[data-pbah-autosize]": { "t-on-input.withTarget": this.onGrow },
        "form[data-pbah-form]": {
            "t-on-keydown.withTarget": this.onFormKey,
            "t-on-submit.withTarget": this.onSubmit,
        },
        "[data-pbah-rows]": { "t-on-keydown": this.onRowsKey },
    };

    start() {
        for (const el of this.el.querySelectorAll("[data-pbah-autosize]")) {
            this.grow(el);
        }
        const url = new URL(window.location.href);
        if (url.searchParams.has("done") || url.searchParams.has("error")) {
            url.searchParams.delete("done");
            url.searchParams.delete("error");
            window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
        }
    }

    // ------------------------------------------------------------ files
    onFiles(ev, input) {
        const picker = input.closest(".pbah-picker");
        const list = picker.querySelector("[data-pbah-chosen]");
        const max = Number(input.dataset.pbahMax) || 3;
        const files = [...(input.files || [])];
        list.replaceChildren(
            ...files.map((file) => {
                const li = document.createElement("li");
                const name = document.createElement("span");
                name.textContent = file.name;
                const size = document.createElement("small");
                size.textContent = fmtSize(file.size);
                li.append(name, size);
                return li;
            })
        );
        const problems = {
            count: files.length > max,
            type: files.some((f) => f.type && !TYPES.includes(f.type)),
            size: files.some((f) => f.size > MAX_BYTES),
        };
        for (const warn of picker.querySelectorAll("[data-pbah-warn]")) {
            warn.classList.toggle("d-none", !problems[warn.dataset.pbahWarn]);
        }
        input.setCustomValidity(Object.values(problems).some(Boolean) ? " " : "");
    }

    // ------------------------------------------------------------- text
    grow(el) {
        el.style.height = "auto";
        el.style.height = `${Math.min(el.scrollHeight + 2, 420)}px`;
    }

    onGrow(ev, el) {
        this.grow(el);
    }

    // ------------------------------------------------------------- form
    onFormKey(ev, form) {
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            ev.preventDefault();
            if (form.reportValidity()) {
                form.requestSubmit();
            }
        }
    }

    onSubmit(ev, form) {
        const button = form.querySelector("[data-pbah-submit]");
        if (!button) {
            return;
        }
        if (button.classList.contains("is-sending")) {
            ev.preventDefault();
            return;
        }
        button.classList.add("is-sending");
        button.setAttribute("aria-busy", "true");
    }

    // ------------------------------------------------------------- rows
    onRowsKey(ev) {
        if (ev.altKey || ev.ctrlKey || ev.metaKey) {
            return;
        }
        const rows = [...this.el.querySelectorAll("[data-pbah-rows] a.pbah-row")];
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

registry.category("public.interactions").add("pb_ask_hr.ask_hr", PbAskHr);
