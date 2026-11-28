import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

/**
 * ETP E3 — project time, the week on one screen.
 *
 * The page works without this file: the grid is one form ("Save week"),
 * "Copy last week" and "Fill the week with 8 h" are its submit buttons, the
 * picker is a GET form, removing an empty row is a link. This file makes it a
 * spreadsheet, and holds no words of its own (they come from the server's
 * answers and from `data-pbpt-word` in the template):
 *
 *  - every cell saves itself (Enter, Tab, an arrow key or leaving the cell),
 *    one save at a time, and answers with the row, day and week totals — the
 *    ring, the day bars and the strip move; a saved cell flashes green for
 *    300 ms; a refused one turns rose with the reason under the grid and keeps
 *    what was typed so it can be fixed;
 *  - keyboard: arrows move, Enter saves and goes down, Tab goes right, Esc
 *    puts the saved value back, N opens the cell's note;
 *  - "Add a project": type to filter, arrows, Enter — the grid comes back
 *    re-drawn by the server with the new row, and the cursor lands in it;
 *  - "Copy last week" / "Fill the week with 8 h" without a reload;
 *  - the address bar keeps `rows` (the empty rows on screen) and, on a phone,
 *    `day`, so a reload shows the same week;
 *  - phone: one day at a time — tap a day or swipe; ± half an hour.
 */
const PHONE = window.matchMedia("(max-width: 767.98px)");
const STATES = ["is-under", "is-at", "is-over", "is-none", "is-leave"];
const TOAST_MS = 4200;

function fmtHours(value) {
    // the same writing as the server's `fmt_h`: '8', '7.5', '1.25'
    const v = Math.round((Number(value) || 0) * 100) / 100;
    return Math.abs(v) < 0.005 ? "0" : String(v);
}

function looseHours(text) {
    // only for the ± buttons; the server is the judge of what was typed
    const s = String(text || "").replace(/\s+/g, "").toLowerCase();
    if (!s) {
        return 0;
    }
    let m = s.match(/^(\d{1,2})(?::|h)(\d{1,2})(?:m|min)?$/);
    if (m) {
        return Number(m[1]) + Number(m[2]) / 60;
    }
    m = s.match(/^(\d+(?:[.,]\d+)?)h?$/);
    return m ? Number(m[1].replace(",", ".")) : 0;
}

function setState(el, state) {
    if (!el) {
        return;
    }
    el.classList.remove(...STATES);
    if (state) {
        el.classList.add(`is-${state}`);
    }
}

function replay(el, cls) {
    if (!el) {
        return;
    }
    el.classList.remove(cls);
    void el.offsetWidth; // restart the animation
    el.classList.add(cls);
}

export class PbProjectTimeWeek extends Interaction {
    static selector = ".pbpt[data-pbpt][data-state='ok']";

    setup() {
        const data = this.el.dataset;
        this.week = data.week;
        this.rows = data.rows || "";
        this.day = Number(data.day) || 0;
        this.lang = document.documentElement.getAttribute("lang") || "";
        this.queue = Promise.resolve();
        this.pending = 0;
        this.errors = new Map();
        this.words = {};
        for (const w of this.el.querySelectorAll("[data-pbpt-word]")) {
            this.words[w.dataset.pbptWord] = w.textContent.trim();
        }
        this.el.classList.add("pbpt-js");
        this.touch = null;
        this.toastTimer = 0;
    }

    start() {
        const el = this.el;
        this.addListener(el, "focusin", this.onFocusIn);
        this.addListener(el, "pointerup", this.onPointerUp);
        this.addListener(el, "keydown", this.onKeyDown);
        this.addListener(el, "change", this.onChange);
        this.addListener(el, "click", this.onClick);
        this.addListener(el, "input", this.onInput);
        // <details> "toggle" does not bubble: listen in the capture phase
        this.addListener(el, "toggle", this.onToggle, { capture: true });
        this.addListener(el, "touchstart", this.onTouchStart, { passive: true });
        this.addListener(el, "touchend", this.onTouchEnd, { passive: true });
        this.addListener(document, "pointerdown", this.onOutside);
        this.addListener(window, "beforeunload", this.onBeforeUnload);
        this.registerCleanup(() => window.clearTimeout(this.toastTimer));
        this.syncUrl();
        const fresh = el.querySelector("tr.pbpt-r.is-new");
        if (fresh) {
            this.focusRow(fresh);
        }
        const toast = el.querySelector("[data-pbpt-toast]:not(.d-none)");
        if (toast) {
            this.hideToastLater(toast);
        }
    }

    // ------------------------------------------------------------ helpers
    get grid() {
        return this.el.querySelector("[data-pbpt-grid]");
    }

    gridRows() {
        return [...this.el.querySelectorAll("tbody tr.pbpt-r:not(.is-leave)")];
    }

    cellInput(tr, i) {
        return tr && tr.querySelector(`td.pbpt-c[data-i="${i}"] .pbpt-in`);
    }

    target(i) {
        const sum = this.el.querySelector(`.pbpt-sum[data-i="${i}"]`);
        return sum ? Number(sum.dataset.target) || 0 : 0;
    }

    focusRow(tr) {
        let input = null;
        if (PHONE.matches) {
            input = this.cellInput(tr, this.day);
        }
        for (let i = 0; !input && i < 7; i++) {
            if (this.target(i) > 0) {
                input = this.cellInput(tr, i);
            }
        }
        input = input || tr.querySelector(".pbpt-in");
        window.setTimeout(() => tr.classList.remove("is-new"), 1600);
        if (input) {
            tr.scrollIntoView({ block: "nearest", behavior: "smooth" });
            input.focus({ preventScroll: true });
        }
    }

    move(input, dr, di) {
        const rows = this.gridRows();
        let r = rows.indexOf(input.closest("tr"));
        let i = Number(input.closest("td").dataset.i);
        for (let step = 0; step < 70; step++) {
            r += dr;
            i += di;
            if (di && i > 6) {
                i = 0;
                r += 1;
            } else if (di && i < 0) {
                i = 6;
                r -= 1;
            }
            if (r < 0 || r >= rows.length) {
                return false;
            }
            const next = this.cellInput(rows[r], i);
            if (next) {
                next.focus();
                return true;
            }
        }
        return false;
    }

    syncUrl() {
        const url = new URL(window.location.href);
        for (const key of ["done", "n", "add"]) {
            url.searchParams.delete(key);
        }
        if (this.week) {
            url.searchParams.set("week", this.week);
        }
        url.searchParams.set("rows", this.rows || "");
        const tab = this.el.querySelector(`[data-pbpt-tab="${this.day}"]`);
        if (PHONE.matches && tab) {
            url.searchParams.set("day", tab.dataset.date);
        } else {
            url.searchParams.delete("day");
        }
        window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
        const field = this.el.querySelector("[data-pbpt-rows]");
        if (field) {
            field.value = this.rows || "";
        }
        const dayField = this.el.querySelector("[data-pbpt-dayfield]");
        if (dayField && tab) {
            dayField.value = tab.dataset.date;
        }
    }

    setStatus(kind) {
        const status = this.el.querySelector("[data-pbpt-status]");
        if (!status) {
            return;
        }
        status.classList.toggle("is-saving", kind === "saving");
        status.classList.toggle("is-error", kind === "error");
        const text = status.querySelector("span");
        if (text && this.words[kind === "saving" ? "saving" : "saved"]) {
            text.textContent = this.words[kind === "saving" ? "saving" : "saved"];
        }
    }

    showError(key, text) {
        if (text) {
            this.errors.set(key, text);
        } else {
            this.errors.delete(key);
        }
        const box = this.el.querySelector("[data-pbpt-msg]");
        if (!box) {
            return;
        }
        const last = [...this.errors.values()].pop();
        box.textContent = last || "";
        box.hidden = !last;
    }

    showToast(text) {
        const toast = this.el.querySelector("[data-pbpt-toast]");
        if (!toast || !text) {
            return;
        }
        toast.querySelector("[data-pbpt-toast-text]").textContent = text;
        toast.classList.remove("d-none");
        replay(toast, "pbpt-toast");
        this.hideToastLater(toast);
    }

    hideToastLater(toast) {
        window.clearTimeout(this.toastTimer);
        this.toastTimer = window.setTimeout(() => toast.classList.add("d-none"), TOAST_MS);
    }

    closePopovers(except = null) {
        for (const d of this.el.querySelectorAll("details[open]")) {
            if (d !== except && !(except && d.contains(except))) {
                d.open = false;
            }
        }
    }

    // ------------------------------------------------------------ numbers
    applyNumbers(tr, i, res) {
        const bump = (el, text) => {
            if (el && el.textContent !== text) {
                el.textContent = text;
                el.classList.toggle("is-zero", text === "0");
                replay(el, "is-bump");
            }
        };
        if (tr) {
            bump(tr.querySelector("[data-pbpt-row-total]"), fmtHours(res.row_total));
            const phone = tr.querySelector("[data-pbpt-row-total-phone]");
            if (phone) {
                phone.textContent = fmtHours(res.row_total);
            }
        }
        const sum = this.el.querySelector(`.pbpt-sum[data-i="${i}"]`);
        if (sum) {
            bump(sum.querySelector("[data-pbpt-day-total]"), fmtHours(res.day_total));
            const bar = sum.querySelector(".pbpt-meter i");
            if (bar) {
                bar.style.setProperty("--pbpt-fill", `${res.day_pct}%`);
            }
            setState(sum, res.day_state);
        }
        const tab = this.el.querySelector(`[data-pbpt-tab="${i}"]`);
        if (tab) {
            const total = tab.querySelector("[data-pbpt-strip-total]");
            if (total) {
                total.textContent = fmtHours(res.day_total);
            }
            const bar = tab.querySelector(".pbpt-strip-bar i");
            if (bar) {
                bar.style.setProperty("--pbpt-fill", `${res.day_pct}%`);
            }
            setState(tab, res.day_state);
        }
        bump(this.el.querySelector("[data-pbpt-week-total]"), fmtHours(res.week_total));
        this.applyRing(res);
    }

    applyRing(res) {
        const ring = this.el.querySelector("[data-pbpt-ring]");
        if (!ring || res.week_pct === undefined) {
            return;
        }
        ring.style.setProperty("--pbpt-pct", String(res.week_pct));
        setState(ring, res.week_state);
        ring.classList.toggle("is-zero", !res.week_pct);
        const logged = ring.querySelector("[data-pbpt-ring-logged]");
        const text = fmtHours(res.week_logged);
        if (logged && logged.textContent !== text) {
            logged.textContent = text;
            replay(ring, "is-bump");
        }
    }

    // --------------------------------------------------------------- save
    commit(input, note = null) {
        const td = input.closest("td");
        const tr = input.closest("tr");
        const value = input.value.trim();
        const saved = input.dataset.saved || "";
        if (note === null && (value === saved || value === input.dataset.pending)) {
            return;
        }
        input.dataset.pending = value;
        td.classList.add("is-saving");
        this.setStatus("saving");
        this.pending += 1;
        const params = {
            project_id: Number(tr.dataset.project),
            task_id: Number(tr.dataset.task),
            date: td.dataset.date,
            hours: note === null ? value : saved,
            lang: this.lang,
        };
        if (note !== null) {
            params.note = note;
        }
        this.queue = this.queue
            .then(() => this.send(input, td, tr, params, value, note))
            .catch(() => {});
    }

    async send(input, td, tr, params, value, note) {
        let res;
        try {
            res = await this.waitFor(rpc("/my/project-time/cell", params));
        } catch {
            res = { ok: false, error: this.words.offline };
        } finally {
            this.pending -= 1;
            delete input.dataset.pending;
            td.classList.remove("is-saving");
        }
        const key = input.name;
        if (!res || !res.ok) {
            td.classList.add("is-error");
            const label = input.getAttribute("aria-label") || "";
            this.showError(key, `${label}: ${(res && res.error) || this.words.offline}`);
            this.setStatus("error");
            return;
        }
        td.classList.remove("is-error");
        this.showError(key, null);
        if (note === null) {
            // normalise what was typed ("1:30" → "1.5") unless the person
            // already typed something else into it
            if (input.value.trim() === value) {
                input.value = res.hours_text;
            }
            input.dataset.saved = res.hours_text;
        } else {
            const noteInput = td.querySelector(".pbpt-note-in");
            if (noteInput) {
                noteInput.dataset.saved = res.note || "";
                noteInput.value = res.note || "";
            }
        }
        td.classList.toggle("has-note", Boolean(res.note));
        replay(td, "is-saved");
        window.setTimeout(() => td.classList.remove("is-saved"), 320);
        this.applyNumbers(tr, td.dataset.i, res);
        tr.dataset.hasLines = res.row_total > 0 || this.rowHasNote(tr) ? "1" : "0";
        this.setStatus(this.errors.size ? "error" : "saved");
    }

    rowHasNote(tr) {
        return [...tr.querySelectorAll(".pbpt-note-in")].some((n) => (n.dataset.saved || "").trim());
    }

    rowIsEmpty(tr) {
        const inputs = [...tr.querySelectorAll(".pbpt-in")];
        return inputs.every((i) => !(i.dataset.saved || "").trim() && !i.value.trim()) && !this.rowHasNote(tr);
    }

    // ------------------------------------------------------------- events
    onFocusIn(ev) {
        const input = ev.target;
        if (input.classList && input.classList.contains("pbpt-in")) {
            // a selected cell, like a spreadsheet: typing replaces it
            this.justFocused = input;
            input.select();
        }
    }

    onPointerUp(ev) {
        if (this.justFocused && ev.target === this.justFocused) {
            ev.preventDefault();
        }
        this.justFocused = null;
    }

    onKeyDown(ev) {
        const t = ev.target;
        if (!t.classList) {
            return;
        }
        if (t.classList.contains("pbpt-in")) {
            this.onCellKey(ev, t);
        } else if (t.classList.contains("pbpt-note-in")) {
            this.onNoteKey(ev, t);
        } else if (t.matches("[data-pbpt-q]")) {
            this.onPickKey(ev, t);
        } else if (ev.key === "Escape") {
            const open = t.closest("details[open]");
            if (open) {
                open.open = false;
                const summary = open.querySelector("summary");
                if (summary) {
                    summary.focus();
                }
            }
        }
    }

    onCellKey(ev, input) {
        if (ev.ctrlKey || ev.metaKey || ev.altKey) {
            return;
        }
        const len = input.value.length;
        const whole = input.selectionStart === 0 && input.selectionEnd === len;
        switch (ev.key) {
            case "Enter":
                ev.preventDefault();
                this.commit(input);
                if (!this.move(input, ev.shiftKey ? -1 : 1, 0)) {
                    input.select();
                }
                break;
            case "Tab":
                this.commit(input);
                if (this.move(input, 0, ev.shiftKey ? -1 : 1)) {
                    ev.preventDefault();
                }
                break;
            case "Escape":
                ev.preventDefault();
                input.value = input.dataset.saved || "";
                input.closest("td").classList.remove("is-error");
                this.showError(input.name, null);
                input.select();
                break;
            case "ArrowUp":
            case "ArrowDown":
                ev.preventDefault();
                this.commit(input);
                this.move(input, ev.key === "ArrowUp" ? -1 : 1, 0);
                break;
            case "ArrowLeft":
                if (whole || (input.selectionStart === 0 && input.selectionEnd === 0)) {
                    ev.preventDefault();
                    this.commit(input);
                    this.move(input, 0, -1);
                }
                break;
            case "ArrowRight":
                if (whole || (input.selectionStart === len && input.selectionEnd === len)) {
                    ev.preventDefault();
                    this.commit(input);
                    this.move(input, 0, 1);
                }
                break;
            case "n":
            case "N":
                ev.preventDefault();
                this.openNote(input.closest("td"));
                break;
        }
    }

    openNote(td) {
        const details = td && td.querySelector("details.pbpt-note");
        if (!details) {
            return;
        }
        this.closePopovers(details);
        details.open = true;
        const noteInput = details.querySelector(".pbpt-note-in");
        if (noteInput) {
            noteInput.focus();
            noteInput.select();
        }
    }

    closeNote(noteInput) {
        const details = noteInput.closest("details");
        details.open = false;
        const cell = details.closest("td").querySelector(".pbpt-in");
        if (cell) {
            cell.focus();
        }
    }

    onNoteKey(ev, noteInput) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.saveNote(noteInput);
            this.closeNote(noteInput);
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            noteInput.value = noteInput.dataset.saved || "";
            this.closeNote(noteInput);
        }
    }

    saveNote(noteInput) {
        const value = noteInput.value.trim();
        if (value === (noteInput.dataset.saved || "")) {
            return;
        }
        const input = noteInput.closest("td").querySelector(".pbpt-in");
        if (input) {
            this.commit(input, value);
        }
    }

    onChange(ev) {
        const t = ev.target;
        if (t.classList && t.classList.contains("pbpt-in")) {
            this.commit(t);
        } else if (t.classList && t.classList.contains("pbpt-note-in")) {
            this.saveNote(t);
        }
    }

    onToggle(ev) {
        const details = ev.target;
        if (!(details instanceof HTMLDetailsElement) || !details.open) {
            return;
        }
        this.closePopovers(details);
        if (details.matches("[data-pbpt-pick]")) {
            const q = details.querySelector("[data-pbpt-q]");
            if (q) {
                q.value = "";
                this.filterPicker("");
                q.focus();
            }
        } else if (details.classList.contains("pbpt-note")) {
            const noteInput = details.querySelector(".pbpt-note-in");
            if (noteInput && document.activeElement !== noteInput) {
                noteInput.focus();
            }
        }
    }

    onOutside(ev) {
        for (const d of this.el.querySelectorAll("details[open]")) {
            if (!d.contains(ev.target)) {
                if (d.classList.contains("pbpt-note")) {
                    const noteInput = d.querySelector(".pbpt-note-in");
                    if (noteInput) {
                        this.saveNote(noteInput);
                    }
                }
                d.open = false;
            }
        }
    }

    onBeforeUnload(ev) {
        if (this.pending > 0) {
            ev.preventDefault();
            ev.returnValue = "";
        }
    }

    onInput(ev) {
        if (ev.target.matches && ev.target.matches("[data-pbpt-q]")) {
            this.filterPicker(ev.target.value);
        }
    }

    onClick(ev) {
        const t = ev.target.closest
            ? ev.target.closest("[data-pbpt-step], [data-pbpt-tab], [data-pbpt-copy], [data-pbpt-fill], [data-pbpt-remove], [data-pbpt-open-pick], .pbpt-pick-o")
            : null;
        if (!t) {
            return;
        }
        if (t.matches("[data-pbpt-step]")) {
            const input = t.closest("td").querySelector(".pbpt-in");
            const next = Math.min(24, Math.max(0, looseHours(input.value) + Number(t.dataset.pbptStep)));
            input.value = next ? fmtHours(next) : "";
            this.commit(input);
        } else if (t.matches("[data-pbpt-tab]")) {
            ev.preventDefault();
            this.setDay(Number(t.dataset.pbptTab));
        } else if (t.matches("[data-pbpt-copy]")) {
            ev.preventDefault();
            this.structural(t, "/my/project-time/copy-last-week", {});
        } else if (t.matches("[data-pbpt-fill]")) {
            ev.preventDefault();
            const tr = t.closest("tr");
            t.closest("details").open = false;
            this.structural(t, "/my/project-time/row/fill", {
                project_id: Number(tr.dataset.project),
                task_id: Number(tr.dataset.task),
            });
        } else if (t.matches("[data-pbpt-remove]")) {
            ev.preventDefault();
            this.removeRow(t.closest("tr"));
        } else if (t.matches("[data-pbpt-open-pick]")) {
            ev.preventDefault();
            const pick = this.el.querySelector("[data-pbpt-pick]");
            if (pick) {
                pick.open = true;
                pick.scrollIntoView({ block: "nearest", behavior: "smooth" });
            }
        } else if (t.matches(".pbpt-pick-o")) {
            this.choose(t);
        }
    }

    // ---------------------------------------------------------- phone day
    setDay(index) {
        const i = Math.max(0, Math.min(6, index));
        this.day = i;
        const table = this.el.querySelector(".pbpt-t");
        if (table) {
            table.dataset.day = String(i);
        }
        for (const tab of this.el.querySelectorAll("[data-pbpt-tab]")) {
            if (Number(tab.dataset.pbptTab) === i) {
                tab.setAttribute("aria-current", "true");
            } else {
                tab.removeAttribute("aria-current");
            }
        }
        this.syncUrl();
    }

    onTouchStart(ev) {
        if (!PHONE.matches || !ev.target.closest(".pbpt-t") || ev.touches.length !== 1) {
            this.touch = null;
            return;
        }
        this.touch = { x: ev.touches[0].clientX, y: ev.touches[0].clientY };
    }

    onTouchEnd(ev) {
        if (!this.touch || !ev.changedTouches.length) {
            return;
        }
        const dx = ev.changedTouches[0].clientX - this.touch.x;
        const dy = ev.changedTouches[0].clientY - this.touch.y;
        this.touch = null;
        if (Math.abs(dx) > 56 && Math.abs(dx) > Math.abs(dy) * 1.6) {
            this.setDay(this.day + (dx < 0 ? 1 : -1));
        }
    }

    // ------------------------------------------------------------- picker
    pickOptions() {
        return [...this.el.querySelectorAll(".pbpt-pick-o")];
    }

    filterPicker(query) {
        const words = String(query || "").toLowerCase().split(/\s+/).filter(Boolean);
        let any = false;
        let firstVisible = null;
        for (const o of this.pickOptions()) {
            const hay = o.dataset.search || "";
            const show = words.every((w) => hay.includes(w));
            o.hidden = !show;
            o.classList.remove("is-active");
            o.setAttribute("aria-selected", "false");
            if (show) {
                any = true;
                firstVisible = firstVisible || o;
            }
        }
        // a company heading shows only when something under it does
        for (const g of this.el.querySelectorAll(".pbpt-pick-g")) {
            let next = g.nextElementSibling;
            let visible = false;
            while (next && !next.classList.contains("pbpt-pick-g")) {
                visible = visible || !next.hidden;
                next = next.nextElementSibling;
            }
            g.hidden = !visible;
        }
        const none = this.el.querySelector("[data-pbpt-pick-none]");
        if (none) {
            none.hidden = any;
        }
        if (firstVisible && words.length) {
            this.activate(firstVisible);
        }
    }

    activate(option) {
        for (const o of this.pickOptions()) {
            const on = o === option;
            o.classList.toggle("is-active", on);
            o.setAttribute("aria-selected", on ? "true" : "false");
        }
        if (option) {
            option.scrollIntoView({ block: "nearest" });
        }
    }

    onPickKey(ev, q) {
        const visible = this.pickOptions().filter((o) => !o.hidden);
        const current = visible.findIndex((o) => o.classList.contains("is-active"));
        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const step = ev.key === "ArrowDown" ? 1 : -1;
            const next = visible[(current + step + visible.length) % visible.length];
            this.activate(next || null);
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            const pick = visible[current] || (visible.length === 1 ? visible[0] : null);
            if (pick) {
                this.choose(pick);
            }
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            const details = q.closest("details");
            details.open = false;
            details.querySelector("summary").focus();
        }
    }

    async choose(option) {
        const details = option.closest("details");
        const key = option.dataset.key;
        const existing = this.el.querySelector(`tr.pbpt-r[data-key="${key}"]`);
        details.open = false;
        if (existing) {
            this.focusRow(existing);
            replay(existing, "is-new");
            return;
        }
        await this.structural(details.querySelector("summary"), "/my/project-time/row/add", {
            project_id: Number(option.dataset.project),
            task_id: Number(option.dataset.task),
        });
    }

    // --------------------------------------------------- re-drawn grid
    async structural(button, route, params) {
        if (button) {
            button.classList.add("is-busy");
        }
        let res;
        try {
            await this.queue;
            res = await this.waitFor(rpc(route, {
                ...params,
                week: this.week,
                rows: this.rows,
                day: (this.el.querySelector(`[data-pbpt-tab="${this.day}"]`) || {}).dataset?.date,
                lang: this.lang,
            }));
        } catch {
            res = { ok: false, error: this.words.offline };
        } finally {
            if (button) {
                button.classList.remove("is-busy");
            }
        }
        if (!res || !res.ok) {
            this.showError("structural", (res && res.error) || this.words.offline);
            return;
        }
        this.showError("structural", null);
        this.grid.innerHTML = res.html;
        this.rows = res.rows || "";
        this.applyRing(res);
        const copy = this.el.querySelector("[data-pbpt-copy]");
        if (copy) {
            copy.classList.toggle("d-none", !res.can_copy);
        }
        this.markPicker();
        this.syncUrl();
        if (res.message) {
            this.showToast(res.message);
        }
        if (res.focus) {
            const tr = this.el.querySelector(`tr.pbpt-r[data-key="${res.focus}"]`);
            if (tr) {
                this.focusRow(tr);
            }
        }
    }

    markPicker() {
        const inWeek = new Set([...this.el.querySelectorAll("tr.pbpt-r[data-key]")].map((tr) => tr.dataset.key));
        for (const o of this.pickOptions()) {
            const on = inWeek.has(o.dataset.key);
            o.classList.toggle("is-in", on);
        }
    }

    removeRow(tr) {
        if (!tr) {
            return;
        }
        const details = tr.querySelector("details[open]");
        if (details) {
            details.open = false;
        }
        if (!this.rowIsEmpty(tr)) {
            return;
        }
        const key = tr.dataset.key;
        this.rows = this.rows.split(",").filter((k) => k && k !== key).join(",");
        tr.remove();
        this.markPicker();
        this.syncUrl();
        this.showToast(this.words.removed);
    }
}

registry.category("public.interactions").add("pb_me_project_time.week", PbProjectTimeWeek);
