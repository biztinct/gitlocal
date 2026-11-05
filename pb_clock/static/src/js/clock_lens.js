/** @odoo-module **/
/**
 * Time clocks — a lens of the Time hub (CLOCK-1, ledger D8).
 *
 * HERO MOMENT: one live sentence at the top — "Last punch 3 min ago, Factory 2
 * · 612 people punched today" — with a pulse dot that breathes indigo while
 * punches arrive and goes grey when a working day has been quiet for two
 * hours. Below it, only what needs a person: numbers that match nobody (with a
 * suggested match and a keyboard-first assign), punches on hold (with the
 * reason and a door to a correction), then the machines and the recent
 * punches. Settings sit last, for managers.
 *
 * Registered in the hub's "pb_time_hub.lenses" registry; mounted embedded
 * with the hub's doors (onPerson, onChanged, onOpenLens) and a `seed`
 * ({codes}) when the Import lens's "Assign now" opened it.
 *
 * Facade: pb.clock.lens (officer-gated, company-scoped; get_lens is a READ,
 * every write answers {error} in plain words). Polls every 30 s while open —
 * no bus — and new punches slide in at the top of the list.
 */
import { Component, useState, useRef, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.clock.lens";
const POLL_MS = 30000;
const TYPEAHEAD_MS = 180;

const KIND_LABEL = {
    in: _t("In"), out: _t("Out"), break: _t("Break tap"), double: _t("Double tap"),
    unknown: _t("Unknown"), held: _t("On hold"), ignored: _t("Ignored"),
    waiting: _t("Waiting"),
};

/** naive-UTC "YYYY-MM-DD HH:MM:SS" → Date */
function fromUtc(s) {
    if (!s) { return null; }
    const d = new Date(s.replace(" ", "T") + "Z");
    return isNaN(d.getTime()) ? null : d;
}
function hhmm(d) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

export class ClockLens extends Component {
    static template = "pb_clock.ClockLens";
    static props = {
        embedded: { type: Boolean, optional: true },
        seed: { type: Object, optional: true },
        onPerson: { type: Function, optional: true },
        onChanged: { type: Function, optional: true },
        onOpenLens: { type: Function, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ctxSvc = useService("wf_context");
        this.wf = useState(this.ctxSvc.state);
        this.ic = ic;
        this.KIND_LABEL = KIND_LABEL;
        this.unknownRef = useRef("unknown");
        this.state = useState({
            loading: true,
            failed: false,
            data: null,
            busy: "",
            filters: { period: "week", device_id: false, state: "all", code: "" },
            sel: 0,                     // keyboard row in the unknown table
            assign: null,               // {code, query, matches, ix}
            settings: null,             // the manager's draft
            newIds: {},                 // punch ids that just arrived (slide-in)
            tick: 0,                    // re-renders the "3 min ago" phrases
            moreLoading: false,
        });
        this._seen = null;
        this._timer = null;

        const off = this.ctxSvc.onChange(() => this.load());
        onWillUnmount(off);
        onWillStart(() => this.load());
        onMounted(() => {
            this._poll = setInterval(() => {
                this.state.tick += 1;
                if (!document.hidden) { this.load({ silent: true }); }
            }, POLL_MS);
        });
        onWillUnmount(() => {
            clearInterval(this._poll);
            clearTimeout(this._timer);
        });
    }

    // ------------------------------------------------------------ data
    get seedCodes() {
        return (this.props.seed && this.props.seed.codes) || [];
    }

    async load({ silent = false } = {}) {
        if (!silent) { this.state.loading = !this.state.data; }
        try {
            const data = await this.orm.call(MODEL, "get_lens", [], {
                week_start: this.wf.weekStart,
                department_id: this.wf.departmentId || false,
                person_id: this.wf.personId || false,
                codes: this.seedCodes,
                filters: this.state.filters,
            });
            this._markNew(data);
            this.state.data = data;
            if (!this.state.settings && data.settings) {
                this.state.settings = { ...data.settings };
            }
            this.state.failed = false;
            const n = data.unknown.rows.length;
            if (this.state.sel >= n) { this.state.sel = Math.max(0, n - 1); }
        } catch (e) {
            if (!silent || !this.state.data) { this.state.failed = true; }
            console.warn("Time clocks: lens unavailable", e);
        } finally {
            this.state.loading = false;
        }
    }

    /** Punches that were not on screen before this refresh slide in. */
    _markNew(data) {
        const ids = (data.recent && data.recent.rows || []).map((r) => r.id);
        const fresh = {};
        if (this._seen) {
            for (const id of ids) { if (!this._seen.has(id)) { fresh[id] = true; } }
        }
        this._seen = new Set([...(this._seen || []), ...ids]);
        this.state.newIds = fresh;
    }

    async loadMore() {
        const d = this.state.data;
        if (!d || !d.recent.more || this.state.moreLoading) { return; }
        this.state.moreLoading = true;
        try {
            const next = await this.orm.call(MODEL, "get_lens", [], {
                week_start: this.wf.weekStart,
                department_id: this.wf.departmentId || false,
                person_id: this.wf.personId || false,
                filters: { ...this.state.filters, offset: d.recent.rows.length },
            });
            d.recent.rows = [...d.recent.rows, ...next.recent.rows];
            d.recent.more = next.recent.more;
            for (const r of next.recent.rows) { this._seen.add(r.id); }
        } finally {
            this.state.moreLoading = false;
        }
    }

    // ------------------------------------------------------------ hero
    ago(utc) {
        void this.state.tick;   // re-evaluate on every poll tick
        const d = fromUtc(utc);
        if (!d) { return ""; }
        const mins = Math.round((Date.now() - d.getTime()) / 60000);
        if (mins < 1) { return _t("just now"); }
        if (mins < 60) { return _t("%s min ago", mins); }
        const today = new Date();
        const yest = new Date(); yest.setDate(today.getDate() - 1);
        if (d.toDateString() === today.toDateString()) { return _t("today %s", hhmm(d)); }
        if (d.toDateString() === yest.toDateString()) { return _t("yesterday %s", hhmm(d)); }
        return d.toLocaleDateString([], { weekday: "short", day: "2-digit", month: "short" })
            + " " + hhmm(d);
    }

    get hero() {
        const h = (this.state.data && this.state.data.hero) || { state: "empty" };
        if (h.state === "empty") {
            return { tone: "empty", text: _t("No machine connected. Upload a punch file to start.") };
        }
        const people = h.people_today === 1
            ? _t("1 person punched today")
            : _t("%s people punched today", (h.people_today || 0).toLocaleString());
        if (h.state === "quiet") {
            return { tone: "quiet", text: _t("Nothing since %(ago)s, %(device)s · %(people)s",
                { ago: this.ago(h.last_punch_at), device: h.device, people }) };
        }
        return { tone: "live", text: _t("Last punch %(ago)s, %(device)s · %(people)s",
            { ago: this.ago(h.last_punch_at), device: h.device, people }) };
    }

    get waitingText() {
        const n = (this.state.data && this.state.data.waiting) || 0;
        if (!n) { return ""; }
        return n === 1 ? _t("1 punch is being paired…") : _t("%s punches are being paired…", n.toLocaleString());
    }

    openUpload() {
        if (this.props.onOpenLens) { this.props.onOpenLens("import", { import_mode: "punches" }); }
    }

    // ------------------------------------------------------------ machines
    get devices() { return (this.state.data && this.state.data.devices) || []; }
    deviceName(d) { return d.kind === "upload" ? _t("Files you upload") : d.name; }
    deviceLast(d) { return d.last_punch_at ? this.ago(d.last_punch_at) : _t("no punch yet"); }
    toggleDevice(d) {
        this.state.filters.device_id = this.state.filters.device_id === d.id ? false : d.id;
        this.load();
    }
    async toggleAllowed(d, ev) {
        ev.stopPropagation();
        await this._write("set_device", [d.id, { allowed: !d.allowed }]);
    }

    // ------------------------------------------------------------ unknown
    get unknown() { return (this.state.data && this.state.data.unknown) || { rows: [], total: 0 }; }
    get suggestedCount() { return this.unknown.rows.filter((r) => r.suggestion).length; }

    onUnknownKey(ev) {
        const rows = this.unknown.rows;
        if (this.state.assign) { return; }
        if (ev.key === "ArrowDown") {
            this.state.sel = Math.min(rows.length - 1, this.state.sel + 1);
            ev.preventDefault();
        } else if (ev.key === "ArrowUp") {
            this.state.sel = Math.max(0, this.state.sel - 1);
            ev.preventDefault();
        } else if (ev.key === "Enter" && rows[this.state.sel]) {
            this.openAssign(rows[this.state.sel]);
            ev.preventDefault();
        }
    }

    selectRow(i) { this.state.sel = i; }
    noop() {}
    onDeviceKey(ev, dv) {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); this.toggleDevice(dv); }
    }

    openAssign(row) {
        this.state.sel = this.unknown.rows.indexOf(row);
        this.state.assign = { code: row.code, query: "", matches: [], ix: 0, searching: false };
        setTimeout(() => {
            const root = this.unknownRef.el;
            const input = root && root.querySelector(".pbck-ta__in");
            if (input) { input.focus(); }
        }, 30);
    }
    closeAssign() {
        this.state.assign = null;
        const el = this.unknownRef.el;
        if (el) { el.focus(); }
    }
    onAssignInput(ev) {
        const a = this.state.assign;
        a.query = ev.target.value;
        clearTimeout(this._timer);
        if (a.query.trim().length < 1) { a.matches = []; return; }
        this._timer = setTimeout(() => this._searchPeople(a.query), TYPEAHEAD_MS);
    }
    async _searchPeople(q) {
        const a = this.state.assign;
        if (!a) { return; }
        a.searching = true;
        try {
            const res = await this.orm.call(MODEL, "search_people", [q]);
            if (this.state.assign !== a || a.query !== q) { return; }
            a.matches = res;
            a.ix = 0;
        } finally {
            a.searching = false;
        }
    }
    onAssignKey(ev) {
        const a = this.state.assign;
        if (!a) { return; }
        if (ev.key === "Escape") { this.closeAssign(); ev.preventDefault(); return; }
        if (ev.key === "ArrowDown") { a.ix = Math.min(a.matches.length - 1, a.ix + 1); ev.preventDefault(); }
        if (ev.key === "ArrowUp") { a.ix = Math.max(0, a.ix - 1); ev.preventDefault(); }
        if (ev.key === "Enter" && a.matches[a.ix]) { this.assign(a.code, a.matches[a.ix].id); ev.preventDefault(); }
    }
    async assign(code, employeeId) {
        const ok = await this._write("assign_code", [code, employeeId]);
        if (ok) { this.state.assign = null; this._focusUnknownSoon(); }
    }
    async assignSuggested(row) {
        if (row.suggestion) { await this.assign(row.code, row.suggestion.id); }
    }
    async assignAllSuggested() {
        const rows = this.unknown.rows.filter((r) => r.suggestion);
        if (!rows.length || this.state.busy) { return; }
        this.state.busy = "bulk";
        let done = 0, failed = 0;
        try {
            for (const r of rows) {
                const res = await this.orm.call(MODEL, "assign_code", [r.code, r.suggestion.id]);
                if (res && res.error) { failed += 1; } else { done += 1; }
            }
        } finally {
            this.state.busy = "";
        }
        this.notif.add(
            failed ? _t("%(done)s matched · %(failed)s could not be matched", { done, failed })
                   : (done === 1 ? _t("1 number matched") : _t("%s numbers matched", done)),
            { type: failed ? "warning" : "success" });
        await this._after();
    }
    async autoMatch() { await this._write("auto_match", []); }
    _focusUnknownSoon() {
        setTimeout(() => { const el = this.unknownRef.el; if (el) { el.focus(); } }, 50);
    }
    showCode(code) {
        this.state.filters.code = this.state.filters.code === code ? "" : code;
        this.load();
    }

    // ------------------------------------------------------------ held
    get held() { return (this.state.data && this.state.data.held) || { rows: [], total: 0 }; }

    async fixDay(row) {
        if (this.state.busy) { return; }
        this.state.busy = "fix";
        try {
            // the WRITE lives in the click handler, never in a mount (W21)
            const corr = await this.orm.call("pb.attendance.flow", "create_correction", [{
                employee_id: row.employee_id,
                date: row.day,
                correction_type: "adjust",
                reason: _t("Time clock punches on hold for %(day)s: %(why)s",
                           { day: row.day_label, why: row.note }),
                reuse_draft: true,
            }]);
            if (this.props.onOpenLens) {
                this.props.onOpenLens("exceptions", { correction_id: corr.id });
            }
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("The correction could not be opened."),
                { type: "danger" });
        } finally {
            this.state.busy = "";
        }
    }

    // ------------------------------------------------------------ recent
    get recent() { return (this.state.data && this.state.data.recent) || { rows: [], total: 0 }; }
    get periodChips() {
        return [{ key: "today", label: _t("Today") }, { key: "week", label: _t("This week") }];
    }
    get stateChips() {
        return [
            { key: "all", label: _t("All") },
            { key: "counted", label: _t("Counted") },
            { key: "unknown", label: _t("Unknown number") },
            { key: "held", label: _t("On hold") },
            { key: "ignored", label: _t("Ignored") },
        ];
    }
    setPeriod(k) { this.state.filters.period = k; this.load(); }
    setStateFilter(k) { this.state.filters.state = k; this.load(); }
    clearFilters() {
        Object.assign(this.state.filters, { period: "week", device_id: false, state: "all", code: "" });
        this.load();
    }
    get filtered() {
        const f = this.state.filters;
        return f.period !== "week" || f.device_id || f.state !== "all" || f.code;
    }
    get deviceFilterName() {
        const d = this.devices.find((x) => x.id === this.state.filters.device_id);
        return d ? this.deviceName(d) : "";
    }
    openPerson(id) { if (id && this.props.onPerson) { this.props.onPerson(id); } }

    // ------------------------------------------------------------ settings
    onSetting(key, ev) {
        const s = this.state.settings;
        s[key] = key === "trust_direction" ? ev.target.checked : ev.target.value;
    }
    get settingsDirty() {
        const a = this.state.settings, b = this.state.data && this.state.data.settings;
        if (!a || !b) { return false; }
        return Number(a.max_span_h) !== Number(b.max_span_h)
            || Number(a.double_tap_min) !== Number(b.double_tap_min)
            || !!a.trust_direction !== !!b.trust_direction;
    }
    async saveSettings() {
        const s = this.state.settings;
        const res = await this._write("save_settings",
            [s.max_span_h, s.double_tap_min, s.trust_direction], { quiet: true });
        if (res) {
            this.state.settings = { ...res.settings };
            this.notif.add(res.message, {
                type: "success",
                buttons: [{ name: _t("Re-pair this week"), primary: true, onClick: () => this.repairWeek() }],
            });
        }
    }
    async repairWeek() { await this._write("repair_week", [this.wf.weekStart]); }

    // ------------------------------------------------------------ helpers
    /** One write RPC → toast in plain words → refresh. {error} never throws. */
    async _write(method, args, { quiet = false } = {}) {
        if (this.state.busy) { return null; }
        this.state.busy = method;
        try {
            const res = await this.orm.call(MODEL, method, args);
            if (res && res.error) {
                this.notif.add(res.error, { type: "warning" });
                return null;
            }
            if (!quiet && res && res.message) {
                this.notif.add(res.message, { type: "success" });
            }
            await this._after();
            return res || {};
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work. Try again in a moment."),
                { type: "danger" });
            return null;
        } finally {
            this.state.busy = "";
        }
    }
    async _after() {
        await this.load({ silent: true });
        if (this.props.onChanged) { this.props.onChanged(); }
    }
    fmtN(n) { return (Number(n) || 0).toLocaleString(); }
    // words in a template expression are never translated: they live here
    tipShowCode(code) { return _t("Show the punches of %s", code); }
    tipGive(r) { return _t("Give %(code)s to %(name)s", { code: r.code, name: r.suggestion.name }); }
    tipDevice(dv) {
        return this.state.filters.device_id === dv.id ? _t("Show every machine") : _t("Show only this machine");
    }
    get moreLabel() {
        const r = this.recent;
        return _t("Show %s more", this.fmtN(Math.min(200, r.total - r.rows.length)));
    }
    get assignAllLabel() { return _t("Assign all suggested (%s)", this.suggestedCount); }
    seenLabel(utc) {
        const d = fromUtc(utc);
        return d ? d.toLocaleDateString([], { day: "2-digit", month: "short" }) + " " + hhmm(d) : "";
    }
}

registry.category("pb_time_hub.lenses").add("clocks", {
    key: "clocks",
    label: _t("Time clocks"),
    icon: "scan",
    Component: ClockLens,
    sequence: 50,
});
