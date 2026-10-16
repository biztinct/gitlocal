import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

/**
 * Business trips on My Payobook (ETP E2). Every page works without this
 * script (E-R8): the form posts, "Add a line" and a row's remove button
 * redraw the form on the server. The script only does the same in place:
 *
 *  - THE CARD WRITES ITSELF: destination, dates, the number of days, the
 *    daily allowance (the matched policy's rate × days), other costs, the
 *    estimated total and the cash advance are rewritten on every keystroke;
 *    a value that changed glows once. The arithmetic is the record's own
 *    (`_compute_duration` / `_compute_money`, mirrored by
 *    `pb.me.trip.preview`); the policies, currencies and number separators
 *    arrive from the server in `data-pbtr-facts`. This file holds NO words:
 *    it fills numbers into, and shows or hides, what the template drew.
 *  - the "Major city" switch shows only where a major-city rate exists;
 *  - cost lines are added and removed in place; Enter in a line adds the
 *    next one; a section's number turns solid once it is answered;
 *  - Ctrl/Cmd + Enter sends; Enter elsewhere never sends by accident; the
 *    send button locks once pressed;
 *  - the one-off `done` key is dropped from the address bar once shown;
 *  - arrow keys / j / k move between trip cards on the board.
 */

const DAY_MS = 24 * 60 * 60 * 1000;

function toNumber(value) {
    const n = parseFloat(String(value || "").replace(/,/g, "").trim());
    return Number.isFinite(n) && n > 0 ? n : 0;
}

function toDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) {
        return null;
    }
    const d = new Date(`${value}T00:00:00Z`);
    return Number.isNaN(d.getTime()) ? null : d;
}

export class PbTripForm extends Interaction {
    static selector = ".pbtr-form";
    dynamicContent = {
        _root: {
            "t-on-input": this.onInput,
            "t-on-change": this.onInput,
            "t-on-keydown": this.onKey,
            "t-on-submit": this.onSubmit,
        },
        "[data-pbtr-add]": { "t-on-click.prevent": this.onAdd },
        "[data-pbtr-autosize]": { "t-on-input.withTarget": this.onGrow },
    };

    setup() {
        try {
            this.facts = JSON.parse(this.el.dataset.pbtrFacts || "{}");
        } catch {
            this.facts = {};
        }
        this.facts.countries = this.facts.countries || {};
        this.facts.currencies = this.facts.currencies || {};
        this.sep = this.facts.sep || { thousands: ",", decimal: "." };
        this.companyCurrency = this.el.dataset.pbtrCurrency;
        this.next = Number(this.el.dataset.pbtrNext) || 0;
        this.lang = (document.documentElement.lang || "en-US").replace("_", "-");
        this.card = this.el.querySelector("[data-pbtr-card]");
        this.rows = this.el.querySelector("[data-pbtr-rows-in]");
        this.tpl = this.el.querySelector("[data-pbtr-tpl] .pbtr-row");
        this.typingTimer = null;
    }

    start() {
        for (const el of this.el.querySelectorAll("[data-pbtr-autosize]")) {
            this.grow(el);
        }
        const url = new URL(window.location.href);
        if (url.searchParams.has("done")) {
            url.searchParams.delete("done");
            window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
        }
        // the remove buttons of the rows drawn by the server
        for (const btn of this.el.querySelectorAll("[data-pbtr-rows-in] [data-pbtr-remove]")) {
            this.bindRemove(btn);
        }
        this.recompute(false);
    }

    // ------------------------------------------------------------ inputs
    field(name) {
        return this.el.querySelector(`[data-pbtr-in="${name}"]`);
    }

    onInput(ev) {
        if (ev.target.closest("[data-pbtr-tpl]")) {
            return;
        }
        this.recompute(true);
        if (this.card) {
            this.card.classList.add("is-typing");
            clearTimeout(this.typingTimer);
            this.typingTimer = setTimeout(() => this.card && this.card.classList.remove("is-typing"), 600);
        }
    }

    policy() {
        const country = this.field("country");
        const tier = this.field("tier");
        const entry = country ? this.facts.countries[country.value] : null;
        const toggle = this.el.querySelector("[data-pbtr-tier]");
        if (toggle) {
            toggle.hidden = !(entry && entry.tier1);
        }
        if (entry) {
            return (tier && tier.checked && entry.tier1) || entry.base;
        }
        return this.facts.fallback || { rate: 0, currency: this.companyCurrency, channel: "none" };
    }

    money(amount, currencyId) {
        const cur = this.facts.currencies[currencyId] ||
            this.facts.currencies[this.companyCurrency] || { symbol: "", position: "after", dp: 2 };
        const fixed = Math.abs(amount).toFixed(cur.dp);
        const [whole, dec] = fixed.split(".");
        const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, this.sep.thousands);
        const num = (amount < 0 ? "-" : "") + (dec ? `${grouped}${this.sep.decimal}${dec}` : grouped);
        if (!cur.symbol) {
            return num;
        }
        return cur.position === "after" ? `${num} ${cur.symbol}` : `${cur.symbol} ${num}`;
    }

    datesLabel(from, to) {
        // the server's own shape (babel "d MMM", `pb.me.trip.dates_label`):
        // "12–14 Nov", "30 Nov – 2 Dec", "28 Dec 2026 – 3 Jan 2027"
        let fmt;
        try {
            fmt = new Intl.DateTimeFormat(this.lang, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
        } catch {
            fmt = new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
        }
        const part = (date, withYear) => {
            const bits = Object.fromEntries(fmt.formatToParts(date).map((p) => [p.type, p.value]));
            return withYear ? `${bits.day} ${bits.month} ${bits.year}` : `${bits.day} ${bits.month}`;
        };
        if (from.getTime() === to.getTime()) {
            return part(to, false);
        }
        if (from.getUTCFullYear() !== to.getUTCFullYear()) {
            return `${part(from, true)} – ${part(to, true)}`;
        }
        if (from.getUTCMonth() === to.getUTCMonth()) {
            return `${from.getUTCDate()}–${part(to, false)}`;
        }
        return `${part(from, false)} – ${part(to, false)}`;
    }

    // ------------------------------------------------------------- card
    out(key, text, flash) {
        for (const el of this.el.querySelectorAll(`[data-pbtr-out="${key}"]`)) {
            if (el.textContent !== text) {
                el.textContent = text;
                if (flash) {
                    el.classList.remove("is-flash");
                    void el.offsetWidth; // restart the glow
                    el.classList.add("is-flash");
                }
            }
        }
    }

    show(key, on) {
        for (const el of this.el.querySelectorAll(`[data-pbtr-show="${key}"]`)) {
            el.hidden = !on;
        }
    }

    placeholder(key, on) {
        for (const el of this.el.querySelectorAll(`[data-pbtr-ph="${key}"]`)) {
            el.hidden = !on;
        }
    }

    recompute(flash) {
        const policy = this.policy();
        const country = this.field("country");
        const city = (this.field("city")?.value || "").trim();
        const countryName = country && country.selectedIndex >= 0
            ? country.options[country.selectedIndex].text.trim() : "";
        const where = [city, countryName].filter(Boolean).join(", ");
        this.out("where", where, flash);
        this.placeholder("where", !where);

        const from = toDate(this.field("from")?.value);
        const to = toDate(this.field("to")?.value);
        const valid = Boolean(from && to && to >= from);
        const days = valid ? Math.round((to - from) / DAY_MS) + 1 : 0;
        this.out("dates", valid ? this.datesLabel(from, to) : "", flash);
        this.placeholder("dates", !valid);
        this.out("days", String(days), flash);
        this.show("days", days > 0);
        this.placeholder("days", days === 0);
        for (const el of this.el.querySelectorAll('[data-pbtr-one="days"]')) {
            el.hidden = days !== 1;
        }
        for (const el of this.el.querySelectorAll('[data-pbtr-many="days"]')) {
            el.hidden = days === 1;
        }

        const rate = Number(policy.rate) || 0;
        const currency = policy.currency || this.companyCurrency;
        const allowance = rate * days;
        let lines = 0;
        for (const input of this.el.querySelectorAll('[data-pbtr-rows-in] [data-pbtr-in="line"]')) {
            lines += toNumber(input.value);
        }
        const advance = toNumber(this.field("advance")?.value);
        this.out("rate", this.money(rate, currency), flash);
        this.out("allowance", this.money(allowance, currency), flash);
        this.out("lines", this.money(lines, currency), flash);
        this.out("estimated", this.money(allowance + lines, currency), flash);
        this.out("advance", this.money(advance, currency), flash);
        this.show("calc", rate > 0 && days > 0);
        this.show("lines", lines > 0);
        this.show("advance", advance > 0);
        const channel = rate > 0 ? policy.channel : "none";
        for (const el of this.el.querySelectorAll("[data-pbtr-channel]")) {
            el.hidden = el.dataset.pbtrChannel !== channel;
        }
        this.markAnswered(where, valid);
    }

    markAnswered(where, datesOk) {
        const secs = this.el.querySelectorAll(".pbtr-sec");
        const purpose = (this.el.querySelector('[name="purpose"]')?.value || "").trim();
        const linesOk = [...this.el.querySelectorAll('[data-pbtr-rows-in] [data-pbtr-in="line"]')]
            .some((i) => toNumber(i.value) > 0);
        const advanceOk = toNumber(this.field("advance")?.value) > 0;
        const answered = [Boolean(where && (this.field("city")?.value || "").trim()), datesOk,
            Boolean(purpose), linesOk, advanceOk];
        secs.forEach((sec, i) => sec.classList.toggle("is-answered", Boolean(answered[i])));
    }

    // ------------------------------------------------------------- rows
    onAdd() {
        this.addRow(true);
    }

    addRow(focus) {
        if (!this.tpl || !this.rows) {
            return null;
        }
        const n = this.next++;
        const row = this.tpl.cloneNode(true);
        row.dataset.pbtrRow = String(n);
        for (const el of row.querySelectorAll("[name], [value]")) {
            for (const attr of ["name", "value"]) {
                const v = el.getAttribute(attr);
                if (v && v.includes("__n__")) {
                    el.setAttribute(attr, v.replaceAll("__n__", String(n)));
                }
            }
            el.disabled = false;
        }
        for (const el of row.querySelectorAll("[disabled]")) {
            el.disabled = false;
        }
        this.rows.append(row);
        this.bindRemove(row.querySelector("[data-pbtr-remove]"));
        if (focus) {
            row.querySelector('[data-pbtr-in="line"]')?.focus();
        }
        return row;
    }

    bindRemove(btn) {
        if (!btn) {
            return;
        }
        this.addListener(btn, "click", (ev) => {
            ev.preventDefault();
            this.removeRow(btn.closest(".pbtr-row"));
        });
    }

    removeRow(row) {
        if (!row) {
            return;
        }
        const rows = [...this.rows.querySelectorAll(".pbtr-row")];
        const index = rows.indexOf(row);
        const done = () => {
            row.remove();
            if (!this.rows.querySelector(".pbtr-row")) {
                this.addRow(false);
            }
            this.recompute(true);
            const left = [...this.rows.querySelectorAll(".pbtr-row")];
            const target = left[Math.min(index, left.length - 1)];
            target?.querySelector('[data-pbtr-in="line"]')?.focus();
        };
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            done();
            return;
        }
        row.classList.add("is-leaving");
        this.waitForTimeout(done, 180);
    }

    // ----------------------------------------------------------- keyboard
    onKey(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        if (ev.ctrlKey || ev.metaKey) {
            ev.preventDefault();
            this.send();
            return;
        }
        const target = ev.target;
        if (target.tagName === "TEXTAREA" || target.tagName === "BUTTON" || target.tagName === "A"
            || target.tagName === "SUMMARY") {
            return;
        }
        // Enter in a cost line adds the next line; anywhere else it never
        // sends the form by accident
        ev.preventDefault();
        const row = target.closest("[data-pbtr-rows-in] .pbtr-row");
        if (row) {
            this.addRow(true);
        }
    }

    send() {
        const button = this.el.querySelector("[data-pbtr-send]");
        if (!button || button.classList.contains("is-sending")) {
            return;
        }
        if (this.el.reportValidity()) {
            this.el.requestSubmit(button);
        }
    }

    onSubmit(ev) {
        const submitter = ev.submitter;
        if (!submitter || !submitter.matches("[data-pbtr-send], [data-pbtr-save]")) {
            return;
        }
        if (submitter.classList.contains("is-sending")) {
            ev.preventDefault();
            return;
        }
        submitter.classList.add("is-sending");
        submitter.setAttribute("aria-busy", "true");
    }

    // ------------------------------------------------------------- text
    grow(el) {
        el.style.height = "auto";
        el.style.height = `${Math.min(el.scrollHeight + 2, 360)}px`;
    }

    onGrow(ev, el) {
        this.grow(el);
    }
}

/**
 * The board and the trip page: drop the one-off `done` key from the address
 * bar (a reload must not toast again), lock a pressed action button, and
 * move between trip cards with the arrow keys.
 */
export class PbTripPages extends Interaction {
    static selector = ".pbtr:not(.pbtr-ask)";
    dynamicContent = {
        "[data-pbtr-rows]": { "t-on-keydown": this.onRowsKey },
        "form[data-pbtr-lock]": { "t-on-submit.withTarget": this.onLock },
    };

    start() {
        const url = new URL(window.location.href);
        if (url.searchParams.has("done")) {
            url.searchParams.delete("done");
            window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
        }
    }

    onLock(ev, form) {
        if (form.dataset.pbtrSent) {
            ev.preventDefault();
            return;
        }
        form.dataset.pbtrSent = "1";
        form.querySelector("button[type=submit]")?.setAttribute("aria-busy", "true");
    }

    onRowsKey(ev) {
        if (ev.altKey || ev.ctrlKey || ev.metaKey) {
            return;
        }
        const cards = [...this.el.querySelectorAll("[data-pbtr-rows] a.pbtr-tc")];
        const at = cards.indexOf(document.activeElement);
        let next = null;
        if (ev.key === "ArrowDown" || ev.key === "ArrowRight" || ev.key === "j") {
            next = cards[Math.min(cards.length - 1, at + 1)];
        } else if (ev.key === "ArrowUp" || ev.key === "ArrowLeft" || ev.key === "k") {
            next = cards[Math.max(0, at - 1)];
        }
        if (next) {
            ev.preventDefault();
            next.focus();
        }
    }
}

registry.category("public.interactions").add("pb_me_trip.trip_form", PbTripForm);
registry.category("public.interactions").add("pb_me_trip.trip_pages", PbTripPages);
