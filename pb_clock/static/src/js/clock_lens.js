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
 * CLOCK-3 HERO MOMENT — THE ATTENTION STRIP. Right under the live sentence,
 * a note that reads like a colleague's: grey and calm at zero ("Nothing needs
 * attention."), otherwise one plain sentence per problem ("Factory 2 has not
 * called in since 14:02.") with the door that fixes it and, for a manager,
 * Mute for a week. ↑/↓ to move, Enter opens the door. The 15-minute watcher
 * (pb.clock.alert) writes the rows; the lens only reads them.
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
import { setPlaceSub } from "@pb_hub/js/hub_place";

const MODEL = "pb.clock.lens";
const POLL_MS = 30000;
const TYPEAHEAD_MS = 180;

const KIND_LABEL = {
    in: _t("In"), out: _t("Out"), break: _t("Break tap"), double: _t("Double tap"),
    unknown: _t("Unknown"), held: _t("On hold"), ignored: _t("Ignored"),
    waiting: _t("Waiting"), before: _t("Before start"),
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
        this.rootRef = useRef("root");
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
            allow: null,                // the Allow sheet {id, name, location, tz, history_from}
            menu: false,                // machine card whose menu is open
            resend: null,               // {id, since}
            showBlocked: false,
            arrived: {},                // pending ids that just appeared (hero moment)
            attnSel: 0,                 // keyboard row in the Attention strip
            showMuted: false,
            flash: "",                  // the block / machine a door just opened
        });
        this._seenPending = null;
        this._seen = null;
        this._timer = null;

        const off = this.ctxSvc.onChange(() => this.load());
        onWillUnmount(off);
        onWillStart(() => this.load());
        onMounted(() => {
            // CLOCK-3: tell Learn's helper this is Time › Time clocks (the
            // inner tab of the Time lens of Mission Control)
            if (this.props.embedded) { setPlaceSub("pb_workforce", "time", "clocks"); }
            this._poll = setInterval(() => {
                this.state.tick += 1;
                if (!document.hidden) { this.load({ silent: true }); }
            }, POLL_MS);
        });
        onWillUnmount(() => {
            if (this.props.embedded) { setPlaceSub("pb_workforce", "time", ""); }
            clearInterval(this._poll);
            clearTimeout(this._timer);
            clearTimeout(this._fade);
            clearTimeout(this._arrFade);
            clearTimeout(this._flashT);
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
            this._markNew(data, silent);
            this._markArrived(data);
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
    _markNew(data, silent) {
        const ids = (data.recent && data.recent.rows || []).map((r) => r.id);
        const fresh = {};
        // only the 30-second refresh brings punches that "just arrived"; a
        // week / filter change is a new list, not new punches
        if (silent && this._seen) {
            for (const id of ids) { if (!this._seen.has(id)) { fresh[id] = true; } }
        }
        this._seen = new Set([...(silent && this._seen ? this._seen : []), ...ids]);
        this.state.newIds = fresh;
        if (Object.keys(fresh).length) {
            clearTimeout(this._fade);
            this._fade = setTimeout(() => { this.state.newIds = {}; }, 4000);
        }
    }

    /** A machine that starts asking to connect while the lens is open
     *  arrives with a ripple (setup day: HR turns round, it is there). */
    _markArrived(data) {
        const ids = (data.pending || []).map((p) => p.id);
        const fresh = {};
        if (this._seenPending) {
            for (const id of ids) { if (!this._seenPending.has(id)) { fresh[id] = true; } }
        }
        this._seenPending = new Set(ids);
        if (Object.keys(fresh).length) {
            this.state.arrived = fresh;
            clearTimeout(this._arrFade);
            this._arrFade = setTimeout(() => { this.state.arrived = {}; }, 6000);
        }
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
            const n = this.pending.length;
            if (n) {
                return { tone: "ask", text: n === 1
                    ? _t("A machine is asking to connect. Press Allow to let it in.")
                    : _t("%s machines are asking to connect. Press Allow to let them in.", n) };
            }
            const on = this.listening;
            if (on.length) {
                return { tone: "wait", text: on.length === 1
                    ? _t("%s is connected. Waiting for the first punch.", on[0].name)
                    : _t("%s machines are connected. Waiting for the first punch.", on.length) };
            }
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

    // ------------------------------------------------------------ attention (CLOCK-3)
    get attention() {
        return (this.state.data && this.state.data.attention) || { items: [], muted: [], count: 0 };
    }
    get attnItems() { return this.attention.items || []; }
    /** the strip shows once something is connected or something needs a person */
    get showAttention() { return !this.showStart || this.attnItems.length; }
    get attnTitle() {
        const n = this.attnItems.length;
        return n === 1 ? _t("1 thing needs attention") : _t("%s things need attention", n);
    }
    get attnChecked() {
        const at = this.attention.checked_at;
        return at ? _t("Checked %s", this.ago(at)) : "";
    }
    get mutedLabel() {
        const n = (this.attention.muted || []).length;
        return n === 1 ? _t("1 muted for a week") : _t("%s muted for a week", n);
    }
    /** when the watcher first noticed it: "noticed 14:02" / "noticed yesterday 14:02" */
    sinceLabel(it) {
        void this.state.tick;
        const d = fromUtc(it.since);
        if (!d) { return ""; }
        const today = new Date();
        const yest = new Date(); yest.setDate(today.getDate() - 1);
        if (d.toDateString() === today.toDateString()) { return _t("noticed %s", hhmm(d)); }
        if (d.toDateString() === yest.toDateString()) { return _t("noticed yesterday %s", hhmm(d)); }
        return _t("noticed %s", d.toLocaleDateString([], { weekday: "short", day: "2-digit", month: "short" }));
    }
    doorLabel(it) {
        const b = it.door && it.door.block;
        if (b === "machine") { return _t("Show the machine"); }
        if (b === "pending") { return _t("Show it"); }
        if (b === "held") { return _t("Show punches on hold"); }
        if (b === "missing") { return _t("Show the days"); }
        if (b === "settings") { return _t("Show the re-check"); }
        return _t("Show the machines");
    }
    tipMute() { return _t("Mute for a week"); }
    selectAttn(i) { this.state.attnSel = i; }
    attnDelay(i) { return `animation-delay: ${Math.min(i, 6) * 40}ms`; }
    onAttnKey(ev) {
        const n = this.attnItems.length;
        if (!n) { return; }
        if (ev.key === "ArrowDown") { this.state.attnSel = Math.min(n - 1, this.state.attnSel + 1); ev.preventDefault(); }
        else if (ev.key === "ArrowUp") { this.state.attnSel = Math.max(0, this.state.attnSel - 1); ev.preventDefault(); }
        else if (ev.key === "Enter") { const it = this.attnItems[this.state.attnSel]; if (it) { this.openDoor(it); } ev.preventDefault(); }
    }
    /** Scroll to the block the alert is about and light it for a moment. */
    openDoor(it) {
        const door = it.door || {};
        const root = this.rootRef.el;
        if (!root) { return; }
        let sel = `[data-block="${door.block}"]`;
        let flash = door.block;
        if (door.block === "machine" && door.device_id) {
            sel = `[data-device="${door.device_id}"]`;
            flash = "dev-" + door.device_id;
        }
        const el = root.querySelector(sel) || root.querySelector('[data-block="machines"]');
        if (!el) { return; }
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        this.state.flash = flash;
        clearTimeout(this._flashT);
        this._flashT = setTimeout(() => { this.state.flash = ""; }, 2200);
    }
    isFlash(key) { return this.state.flash === key; }
    async muteItem(it) { await this._write("mute_alerts", [it.ids]); }
    async unmute(m) { await this._write("unmute_alerts", [[m.id]]); }
    toggleMuted() { this.state.showMuted = !this.state.showMuted; }

    // ------------------------------------------------------------ machines
    get devices() { return (this.state.data && this.state.data.devices) || []; }
    deviceName(d) { return d.kind === "upload" ? _t("Files you upload") : d.name; }
    hasMachines() {
        return this.devices.length || this.pending.length || this.blocked.length;
    }
    deviceLast(d) { return d.last_punch_at ? this.ago(d.last_punch_at) : _t("no punch yet"); }
    toggleDevice(d) {
        this.state.filters.device_id = this.state.filters.device_id === d.id ? false : d.id;
        this.load();
    }
    get terminals() { return this.devices.filter((d) => d.kind === "terminal"); }
    get listening() { return this.devices.filter((d) => d.listening); }
    /** the "bring in the first punches" card: nothing in, no machine let in */
    get showStart() { return this.hero.tone === "empty"; }
    get heroActions() { return ["live", "quiet"].includes(this.hero.tone); }

    // ------------------------------------------------------------ machines asking to connect
    get pending() { return (this.state.data && this.state.data.pending) || []; }
    get blocked() { return (this.state.data && this.state.data.blocked) || []; }
    get address() { return (this.state.data && this.state.data.address) || {}; }
    get pendingTitle() {
        const n = this.pending.length;
        if (!n) { return _t("No machine is asking to connect"); }
        return n === 1 ? _t("1 machine is asking to connect")
                       : _t("%s machines are asking to connect", n);
    }
    get addressLine() {
        const a = this.address;
        if (!a.host) { return ""; }
        return _t("Address to type into the machine: %(host)s · port %(port)s · secure (HTTPS) on",
            { host: a.host, port: a.port || 443 });
    }
    get blockedLabel() {
        const n = this.blocked.length;
        return n === 1 ? _t("1 ignored machine") : _t("%s ignored machines", n);
    }
    pendingSeen(p) { return _t("first heard %s", this.ago(p.first_seen_at)); }
    openAllow(p) {
        if (!this.state.data.can_manage) { return; }
        this.state.allow = {
            id: p.id, serial: p.serial, name: p.name || "", location: p.location || "",
            tz: p.tz || "UTC", history_from: p.history_from || "",
        };
        setTimeout(() => {
            const el = document.querySelector(".pbck-allow input[name='name']");
            if (el) { el.focus(); }
        }, 40);
    }
    closeAllow() { this.state.allow = null; }
    onAllowField(key, ev) { if (this.state.allow) { this.state.allow[key] = ev.target.value; } }
    onAllowKey(ev) {
        if (ev.key === "Escape") { ev.preventDefault(); this.closeAllow(); }
        if (ev.key === "Enter" && ev.target.tagName !== "SELECT") { ev.preventDefault(); this.submitAllow(); }
    }
    get allowSentence() {
        const a = this.state.allow;
        if (!a || !a.history_from) { return ""; }
        return _t("The machine sends everything it still holds. Punches from before %s are kept on record but never become work days.",
            this.fmtDate(a.history_from));
    }
    async submitAllow() {
        const a = this.state.allow;
        if (!a) { return; }
        const res = await this._write("allow_device", [a.id, {
            name: a.name, location: a.location, tz: a.tz, history_from: a.history_from,
        }]);
        if (res) { this.state.allow = null; }
    }
    async ignorePending(p) { await this._write("ignore_device", [p.id]); }
    async unblock(b) { await this._write("unblock_device", [b.id]); }
    toggleBlocked() { this.state.showBlocked = !this.state.showBlocked; }
    get zones() { return (this.state.data && this.state.data.zones) || []; }

    // ------------------------------------------------------------ machine card
    toggleMenu(dv) {
        this.state.menu = this.state.menu === dv.id ? false : dv.id;
        this.state.resend = null;
    }
    closeMenu() { this.state.menu = false; this.state.resend = null; }
    startResend(dv) {
        const d = new Date(); d.setDate(1);
        const iso = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-01";
        this.state.resend = { id: dv.id, since: dv.history_from && dv.history_from > iso ? dv.history_from : iso };
    }
    onResendDate(ev) { if (this.state.resend) { this.state.resend.since = ev.target.value; } }
    async sendResend() {
        const r = this.state.resend;
        if (!r) { return; }
        const res = await this._write("resend_since", [r.id, r.since]);
        if (res) { this.closeMenu(); }
    }
    async ignoreDevice(dv) {
        const res = await this._write("ignore_device", [dv.id]);
        if (res) { this.closeMenu(); }
    }
    /** "Connected · heard 20 s ago" / "Silent since 14:02". */
    linkLine(dv) {
        void this.state.tick;
        const d = fromUtc(dv.last_seen_at);
        if (!d) { return { tone: "grey", text: _t("Waiting for the first call") }; }
        const secs = Math.round((Date.now() - d.getTime()) / 1000);
        if (secs < 180) { return { tone: "on", text: _t("Connected · heard %s", this.ago(dv.last_seen_at)) }; }
        return { tone: "grey", text: _t("Silent since %s", this.ago(dv.last_seen_at)) };
    }
    clockLine(dv) {
        const mins = (s) => Math.max(1, Math.round(Math.abs(s) / 60));
        const corrected = fromUtc(dv.corrected_at);
        if (corrected && Date.now() - corrected.getTime() < 86400000) {
            const by = dv.corrected_by_s || 0;
            const was = by > 0 ? _t("was %s min fast", mins(by)) : _t("was %s min slow", mins(by));
            return { tone: "ok", text: _t("Clock corrected %(ago)s, %(was)s", { ago: this.ago(dv.corrected_at), was }) };
        }
        if (dv.skew_n >= 3 && Math.abs(dv.skew_s) > 60) {
            return { tone: "warn", text: dv.skew_s > 0
                ? _t("Clock %s min fast · correcting", mins(dv.skew_s))
                : _t("Clock %s min slow · correcting", mins(dv.skew_s)) };
        }
        if (dv.skew_n) { return { tone: "ok", text: _t("Clock on time") }; }
        return null;
    }
    historyLine(dv) {
        if (!dv.history_from) { return ""; }
        if (!dv.before_start) { return _t("Pairing from %s", this.fmtDate(dv.history_from)); }
        return dv.before_start === 1
            ? _t("Pairing from %s · 1 older punch kept, not paired", this.fmtDate(dv.history_from))
            : _t("Pairing from %(day)s · %(n)s older punches kept, not paired",
                 { day: this.fmtDate(dv.history_from), n: this.fmtN(dv.before_start) });
    }
    commandLine(dv) {
        const c = dv.command;
        if (!c) { return null; }
        const since = c.since ? this.fmtDate(c.since) : "";
        if (c.kind === "resend") {
            if (c.state === "queued") { return { tone: "busy", text: _t("Resend since %s · waiting for the machine", since) }; }
            if (c.state === "sent") { return { tone: "busy", text: _t("Resend since %s · the machine is sending", since) }; }
            if (c.state === "done") { return { tone: "ok", text: _t("Resend since %(day)s done %(ago)s", { day: since, ago: this.ago(c.done_at) }) }; }
            return { tone: "warn", text: _t("Resend since %(day)s did not work: %(why)s", { day: since, why: c.note }) };
        }
        if (c.kind === "check") {
            if (c.state === "done") { return { tone: "ok", text: _t("Sending everything again · asked %s", this.ago(c.done_at)) }; }
            if (c.state === "failed") { return { tone: "warn", text: _t("The machine did not answer. Restart it and it will send its punches.") }; }
            return { tone: "busy", text: _t("Asking the machine to send everything again…") };
        }
        return null;
    }
    tipMenu() { return _t("More for this machine"); }
    /** a machine let in whose punches come by file (no live connection) */
    fileLine(dv) {
        if (dv.kind !== "terminal" || dv.listening) { return ""; }
        const n = dv.users_count || 0;
        if (!n) { return _t("Its punches arrive by file"); }
        return n === 1 ? _t("Its punches arrive by file · 1 person on the machine")
                       : _t("Its punches arrive by file · %s people on the machine", this.fmtN(n));
    }
    /** CLOCK-3 §6: "Receiving history: 42,300 punches so far · 18,900 waiting
     *  to pair · about 25 minutes left". */
    backfillLine(dv) {
        const b = dv.backfill;
        if (!b) { return ""; }
        const left = b.minutes_left === null || b.minutes_left === undefined ? ""
            : (b.minutes_left <= 1 ? _t("about a minute left")
               : b.minutes_left < 90 ? _t("about %s minutes left", b.minutes_left)
               : _t("about %s hours left", Math.round(b.minutes_left / 60)));
        const head = _t("Receiving history: %(got)s punches so far · %(wait)s waiting to pair",
            { got: this.fmtN(b.received), wait: this.fmtN(b.waiting) });
        return left ? head + " · " + left : head;
    }
    backfillStyle(pct) { return `width: ${Math.max(3, Math.min(100, pct || 0))}%`; }
    backfillSay(b) { return _t("%(name)s is sending its history — %(pct)s", { name: b.name, pct: b.pct + "%" }); }

    // ------------------------------------------------------------ days missing a check-out
    get missing() { return (this.state.data && this.state.data.missing_checkout) || { rows: [], total: 0 }; }

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
        s[key] = (key === "trust_direction" || key === "allow_plain" || key === "alert_mail") ? ev.target.checked : ev.target.value;
    }
    get settingsDirty() {
        const a = this.state.settings, b = this.state.data && this.state.data.settings;
        if (!a || !b) { return false; }
        return Number(a.max_span_h) !== Number(b.max_span_h)
            || Number(a.double_tap_min) !== Number(b.double_tap_min)
            || !!a.trust_direction !== !!b.trust_direction
            || !!a.allow_plain !== !!b.allow_plain
            || !!a.alert_mail !== !!b.alert_mail;
    }
    async saveSettings() {
        const s = this.state.settings;
        const b = (this.state.data && this.state.data.settings) || {};
        // only the three pairing settings change how punches become days
        const pairing = Number(s.max_span_h) !== Number(b.max_span_h)
            || Number(s.double_tap_min) !== Number(b.double_tap_min)
            || !!s.trust_direction !== !!b.trust_direction;
        const res = await this._write("save_settings",
            [s.max_span_h, s.double_tap_min, s.trust_direction, !!s.allow_plain, !!s.alert_mail], { quiet: true });
        if (res) {
            this.state.settings = { ...res.settings };
            if (pairing) {
                this.notif.add(res.message, {
                    type: "success",
                    buttons: [{ name: _t("Re-pair this week"), primary: true, onClick: () => this.repairWeek() }],
                });
            } else if (!!s.allow_plain !== !!b.allow_plain) {
                this.notif.add(s.allow_plain
                    ? _t("Saved. Older machines may now send over a plain connection.")
                    : _t("Saved. Machines must use a secure connection."), { type: "success" });
            } else {
                this.notif.add(s.alert_mail
                    ? _t("Saved. Attendance managers get the 08:00 summary and a note when a machine stops.")
                    : _t("Saved. No time-clock emails are sent; the alerts stay on this screen."), { type: "success" });
            }
        }
    }
    async repairWeek() { await this._write("repair_week", [this.wf.weekStart]); }

    /** "Last full re-check: today 02:31 · 0 days changed" (CLOCK-3 §5). */
    get recheckLine() {
        const r = (this.state.data && this.state.data.recheck) || {};
        if (!r.at) { return _t("The first full re-check runs tonight at 02:30."); }
        const d = fromUtc(r.at);
        const today = new Date();
        const yest = new Date(); yest.setDate(today.getDate() - 1);
        let when = d.toLocaleDateString([], { day: "2-digit", month: "short" }) + " " + hhmm(d);
        if (d.toDateString() === today.toDateString()) { when = _t("today %s", hhmm(d)); }
        else if (d.toDateString() === yest.toDateString()) { when = _t("yesterday %s", hhmm(d)); }
        const changed = r.fixed === 1 ? _t("1 day changed") : _t("%s days changed", r.fixed || 0);
        return _t("Last full re-check: %(when)s · %(changed)s", { when, changed });
    }
    get recheckTone() {
        const r = (this.state.data && this.state.data.recheck) || {};
        return r.fixed ? "warn" : "grey";
    }

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
    fmtDate(iso) {
        if (!iso) { return ""; }
        const d = new Date(iso + "T00:00:00");
        return isNaN(d.getTime()) ? iso : d.toLocaleDateString([], { day: "2-digit", month: "short", year: "numeric" });
    }
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
