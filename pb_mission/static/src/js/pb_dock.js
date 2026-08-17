/** @odoo-module **/
/**
 * <WfDock/> — the Needs-you dock (P3b §3.2), mockup B's right column.
 *
 * The five-inbox problem dissolves here. Overtime requests, business trips,
 * attendance corrections and time off are four different models with four
 * different approval chains and, until now, four different screens to remember
 * to visit. The dock is the same queue `pb.team` has always built, mounted
 * ONCE beside every lens: whatever you came to Workforce to do, the things
 * waiting for you are on the right of it.
 *
 * Three rules this component is built around:
 *
 *   W21/W21.1 — MOUNT HOOKS READ, CLICK HANDLERS WRITE. `onWillStart` and the
 *   60-second poll call `get_team_data`, which cannot write anything. Every
 *   approve and every refuse is reachable only from a `t-on-click`. This is the
 *   rule that makes it SAFE for an always-mounted, always-polling surface to
 *   carry approve buttons at all: P1a's 591 junk corrections came from a
 *   mount-time write on a surface nobody was even clicking.
 *
 *   W12 — the dock never decides anything itself. Every act goes through
 *   `pb.team.act`, which calls the target model's OWN gated method AS THE REAL
 *   USER. A tier this user lacks is refused BY THE MODEL and the dock quotes
 *   its words. There is no sudo anywhere on this path and no `state` write.
 *
 *   W37 — no z-index. The dock is a flex sibling of the canvas, so a lens's
 *   `position: fixed` modal still resolves against the ROOT stacking context.
 *
 * The hovercard is deliberately RPC-free (§3.4): everything on it — name, job,
 * source, when — is already in the payload the dock has. A hover that fires a
 * request is a hover that fires forty of them while you read the list.
 */
import {
    Component, useState, onWillStart, onWillUnmount,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.team";
const DOCK_KEY = "pbwf.dock.v1";
const POLL_MS = 60000;
/** Below this the canvas cannot spare 268px, so the dock starts as a strip. */
const NARROW = 1280;

/**
 * Source → identity. The tones are P0's semantic map, promoted from the pbim
 * palette and used nowhere else in the shell: amber overtime (the Overtime
 * Desk's own promoted identity), indigo trips (the brand primary), blue
 * corrections, green leave (the canonical promoted-green scale). No hex here —
 * `tone` only ever becomes a class name (W1).
 */
const SOURCES = [
    { key: "ot", icon: "zap", tone: "ot", label: _t("Overtime") },
    { key: "trip", icon: "plane", tone: "trip", label: _t("Trips") },
    { key: "correction", icon: "fileText", tone: "correction", label: _t("Attendance") },
    { key: "leave", icon: "umbrella", tone: "leave", label: _t("Time off") },
];
const SOURCE_BY_KEY = Object.fromEntries(SOURCES.map((s) => [s.key, s]));

export class WfDock extends Component {
    static template = "pb_mission.WfDock";
    static props = {
        // a card's employee is a door (W5) — the shell decides what opens
        onOpenPerson: { type: Function },
        // "+N more" and "Open full queue →" — the shell raises the Approvals lens
        onOpenQueue: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");

        this.state = useState({
            loading: true,
            data: null,
            failed: false,
            // "team" | "org" — only offered when the SERVER says can_org
            scope: "team",
            collapsed: this._restoreCollapsed(),
            busy: {},          // "model:id" → true while an act is in flight
            removed: {},       // optimistic removal after a successful act
            refuseFor: null,   // "model:id" whose required-note box is open
            refuseNote: "",
            hover: null,       // "model:id" whose hovercard is showing
            hoverAt: { top: 0, right: 0 },
        });

        // READ ONLY (W21). `get_team_data` has no write path in it at all, which
        // is exactly why an always-mounted surface may call it on mount.
        onWillStart(() => this.load());

        // Ambient means ambient: the queue ages while you work in a lens. The
        // poll is the same pure read, skipped when the tab is hidden so a
        // forgotten background tab is not a standing query every minute.
        this._poll = window.setInterval(() => {
            if (!document.hidden && !this.state.loading) { this.load(true); }
        }, POLL_MS);
        onWillUnmount(() => window.clearInterval(this._poll));
    }

    ic(n, s = 14) { return ic(n, s); }

    // ------------------------------------------------------------------ data
    /**
     * @param {boolean} quiet - a poll must not flash the loader over a list the
     *   officer is reading, and must not clear the note box they are typing in.
     */
    async load(quiet = false) {
        if (!quiet) { this.state.loading = true; }
        try {
            const data = await this.orm.call(MODEL, "get_team_data", [], {
                recursive: true,
                scope: this.state.scope,
                // the dock renders a queue, never a roster — see pb.team's
                // docstring for why org scope would otherwise walk 4 500 people
                // four times a minute
                queues_only: true,
            });
            this.state.data = data;
            this.state.failed = false;
            if (!quiet) { this.state.removed = {}; }
        } catch (e) {
            // W40: a catch may narrow a feature only for the reason it was
            // written for. This one records the failure and SAYS so on the
            // surface; it never silently retires the dock.
            this.state.failed = true;
            console.warn("pb_mission: the dock could not load its queue", e);
        } finally {
            this.state.loading = false;
        }
    }

    key(it) { return `${it.model}:${it.res_id}`; }

    get items() {
        const items = (this.state.data && this.state.data.queues
                       && this.state.data.queues.items) || [];
        return items.filter((it) => !this.state.removed[this.key(it)]);
    }

    get counts() {
        return (this.state.data && this.state.data.queues
                && this.state.data.queues.counts) || {};
    }

    get hasMore() {
        return (this.state.data && this.state.data.queues
                && this.state.data.queues.has_more) || {};
    }

    /**
     * The header number is the SERVER's true total (a search_count), minus what
     * this session has just cleared. The list is capped at 20 per source, so
     * counting the rows on screen would report a shrinking backlog as the real
     * one grew past the cap.
     */
    get total() {
        const server = (this.state.data && this.state.data.queues
                        && this.state.data.queues.total) || 0;
        return Math.max(0, server - Object.keys(this.state.removed).length);
    }

    get canOrg() { return !!(this.state.data && this.state.data.can_org); }

    get hasTeam() { return !!(this.state.data && this.state.data.has_team); }

    /** Cards grouped by source, in the semantic order, with the cut marker. */
    get groups() {
        const by = {};
        for (const it of this.items) {
            (by[it.source] = by[it.source] || []).push(it);
        }
        const out = [];
        for (const s of SOURCES) {
            const rows = by[s.key];
            if (!rows || !rows.length) { continue; }
            const total = this.counts[s.key] || rows.length;
            out.push({
                key: s.key,
                label: s.label,
                rows,
                // "+N more" counts what is NOT on screen, from the true total
                more: this.hasMore[s.key] ? Math.max(0, total - rows.length) : 0,
            });
        }
        return out;
    }

    sourceIcon(source) {
        const s = SOURCE_BY_KEY[source];
        return ic(s ? s.icon : "inbox", 11);
    }

    sourceTone(source) {
        const s = SOURCE_BY_KEY[source];
        return s ? s.tone : "slate";
    }

    sourceLabel(source) {
        const s = SOURCE_BY_KEY[source];
        return s ? s.label : source;
    }

    /** "today" · "2d" · "11d" — the age is why a queue is a problem. */
    ageLabel(it) {
        const n = it.age || 0;
        return n <= 0 ? _t("today") : _t("%sd", n);
    }

    /** Three days is the point at which a pending request is a complaint. */
    ageTone(it) { return (it.age || 0) >= 3 ? "old" : ""; }

    // ---------------------------------------------------------------- scope
    async setScope(scope) {
        if (this.state.scope === scope) { return; }
        // Belt and braces on top of the server gate: never SEND a scope the
        // payload says this user does not have.
        if (scope === "org" && !this.canOrg) { return; }
        this.state.scope = scope;
        this.state.removed = {};
        this.state.refuseFor = null;
        await this.load();
    }

    // ------------------------------------------------------------- collapse
    _restoreCollapsed() {
        try {
            const raw = window.localStorage.getItem(DOCK_KEY);
            if (raw) {
                const v = JSON.parse(raw);
                if (typeof v.collapsed === "boolean") { return v.collapsed; }
            }
        } catch { /* private mode, or somebody's hand-edited JSON */ }
        // No stored preference: on a laptop the canvas cannot spare 268px, so
        // the dock arrives as a badge strip and expands on one click.
        return window.innerWidth < NARROW;
    }

    toggleCollapsed() {
        this.state.collapsed = !this.state.collapsed;
        this.state.refuseFor = null;
        this.state.hover = null;
        try {
            window.localStorage.setItem(
                DOCK_KEY, JSON.stringify({ collapsed: this.state.collapsed }));
        } catch { /* private mode */ }
    }

    /** The strip's per-source dots — same order, same tones, just the numbers. */
    get stripCounts() {
        return SOURCES
            .map((s) => ({ key: s.key, tone: s.tone, label: s.label,
                           n: this.counts[s.key] || 0 }))
            .filter((s) => s.n > 0);
    }

    // ------------------------------------------------------------ hovercard
    /**
     * Pure presentation off data already in hand (§3.4) — no RPC, no endpoint.
     *
     * `position: fixed` with a measured origin, not an absolute child of the
     * card: the dock body is a `overflow-y: auto` scroller, and per CSS Overflow
     * that also makes it a horizontal clipper — an absolutely-positioned
     * hovercard would be sliced off at the dock's left edge and look like a
     * rendering bug (the same geometry lesson as W34). Fixed positioning escapes
     * every ancestor's overflow, and the shell creates no transform/filter
     * context that would break it.
     *
     * The card is `pointer-events: none`: the pointer must never be able to
     * land ON it, because the 8px gap between it and the row would then make it
     * flicker. The DOOR is the card's own identity row, which is a real button;
     * the hovercard's last line just names what that click does.
     */
    onCardEnter(it, ev) {
        const el = ev && ev.currentTarget;
        if (el && el.getBoundingClientRect) {
            const r = el.getBoundingClientRect();
            this.state.hoverAt = {
                // clamp so a card near the bottom of a long queue still shows
                top: Math.max(8, Math.min(window.innerHeight - 150, r.top - 4)),
                right: Math.max(8, window.innerWidth - r.left + 10),
            };
        }
        this.state.hover = this.key(it);
    }

    onCardLeave(it) {
        if (this.state.hover === this.key(it)) { this.state.hover = null; }
    }

    hoverItem() {
        return this.items.find((it) => this.key(it) === this.state.hover) || null;
    }

    // ------------------------------------------------------------- the acts
    // Everything below is reachable ONLY from a click handler (W21.1).
    async approve(it) {
        const k = this.key(it);
        if (this.state.busy[k]) { return; }
        this.state.busy[k] = true;
        try {
            const res = await this.orm.call(MODEL, "act", [
                it.model, it.res_id, "approve",
            ]);
            this._afterAct(it, res, _t("Approved"));
        } catch (e) {
            this._error(e);
        } finally {
            delete this.state.busy[k];
        }
    }

    openRefuse(it) {
        this.state.refuseFor = this.key(it);
        this.state.refuseNote = "";
        this.state.hover = null;
    }

    cancelRefuse() {
        this.state.refuseFor = null;
        this.state.refuseNote = "";
    }

    onRefuseNote(ev) { this.state.refuseNote = ev.target.value; }

    /**
     * The note is REQUIRED here, unlike the Team cockpit's optional one.
     * A refusal that arrives with no reason is a support ticket: the employee
     * has to ask a human what happened, and two of the four models (trips,
     * corrections) carry the note into their own refusal chain where it is the
     * only record of why.
     */
    get canConfirmRefuse() { return !!this.state.refuseNote.trim(); }

    async confirmRefuse(it) {
        const k = this.key(it);
        if (this.state.busy[k] || !this.canConfirmRefuse) { return; }
        this.state.busy[k] = true;
        try {
            const res = await this.orm.call(MODEL, "act", [
                it.model, it.res_id, "refuse", this.state.refuseNote.trim(),
            ]);
            this.state.refuseFor = null;
            this.state.refuseNote = "";
            this._afterAct(it, res, _t("Refused"));
        } catch (e) {
            this._error(e);
        } finally {
            delete this.state.busy[k];
        }
    }

    /**
     * `act` answers three different ways and they must not be conflated
     * (the Team cockpit's precedent, kept identical):
     *   ok + the record's own state changed  → cleared, success toast;
     *   ok but the MODEL refused the record (a young-worker guard on apply)
     *                                        → cleared, WARNING toast — never
     *                                          reported as approved;
     *   not ok                               → the model's own words, row kept.
     */
    _afterAct(it, res, okLabel) {
        if (res && res.ok && res.state === "refused" && okLabel !== _t("Refused")) {
            this.state.removed[this.key(it)] = true;
            this.notif.add(_t("Refused by a server guard · %s", it.employee.name),
                           { type: "warning", title: _t("Not applied") });
        } else if (res && res.ok) {
            this.state.removed[this.key(it)] = true;
            this.notif.add(`${okLabel} · ${it.employee.name}`, { type: "success" });
        } else {
            this.notif.add((res && res.error)
                || _t("The request could not be processed."),
                { type: "warning", title: _t("Not allowed") });
            return;     // the row stays; nothing changed, so nothing to refetch
        }
        // Re-read after every act: the queue is shared, and an optimistic
        // removal is a guess about ONE row, not about the other twenty.
        this.load(true);
    }

    _error(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message)
            || _t("Something went wrong.");
        this.notif.add(msg, { type: "danger" });
    }

    // ----------------------------------------------------------- the doors
    openPerson(it) {
        this.state.hover = null;
        this.props.onOpenPerson(it.employee.id);
    }

    openQueue() { this.props.onOpenQueue(); }
}
