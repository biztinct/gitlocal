/** @odoo-module **/
import { Component, useState, onWillStart, onWillUnmount, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ConnectionLostError } from "@web/core/network/rpc";
import { ic as kitIc } from "@pb_import_kit/js/import_icons";
import { TIC, tic } from "@pb_tenants/js/pbtn_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
// THE PREVIEW IS THE BAR. Not a drawing of it, not a lookalike styled to
// match — the same component the customer's web client mounts, with the same
// stylesheet and the same time-phrase renderer. A preview that is a separate
// implementation is a preview that goes quietly out of date the first time
// somebody changes a padding, and the owner then approves a sentence nobody
// will ever see.
import { PbTenancyBar } from "@pb_tenancy/js/tenancy_banner";
import { _t } from "@web/core/l10n/translation";

const COUNTRIES = [
    ["", _t("— pick later —")], ["VN", _t("Vietnam")], ["ID", _t("Indonesia")], ["IN", _t("India")],
    ["SG", _t("Singapore")], ["TH", _t("Thailand")], ["KH", _t("Cambodia")], ["MY", _t("Malaysia")],
];
const STATE_BADGE = {
    live: ["ok", _t("Live")], provisioning: ["info", _t("Provisioning")], draft: ["muted", _t("Draft")],
    error: ["err", _t("Error")], decommissioned: ["muted", _t("Decommissioned")],
};

export class PbTenants extends Component {
    static template = "pb_tenants.PbTenants";
    static components = { HubBackChip, PbTenancyBar };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.dialog = useService("dialog");
        // The return door a caller passed (Settings, a hub, another cockpit).
        // Read ONCE, from props, never written back — the arrival protocol's
        // rule since Cycle 1. Null when nobody sent us, and the chip is then
        // ABSENT rather than inert (W5/W29).
        this.back = hubBack(this.props);
        this.countries = COUNTRIES;
        this.stateBadge = STATE_BADGE;
        this._slugTimer = null;
        this.state = useState({
            loaded: false,
            view: "fleet",
            data: { platform: { checks: [], registrar_records: [] }, kpis: {}, tenants: [], steps: [] },
            checklistOpen: true,
            wiz: this._freshWiz(),
            det: { id: null, tab: "overview", d: null, busy: "", confirm: "", newDomain: "", restoreMsg: null, syncOpen: false },
            // "In step with master": read-only until somebody presses the button.
            sync: this._freshSync(),
            // The notice composer. Closed until somebody opens it.
            notice: this._freshNotice(),
        });
        this._tick = null;
        // DOCUMENT, IN THE CAPTURE PHASE, AND BOTH HALVES ARE LOAD-BEARING.
        // Something in the shared web client already listens for keydown on
        // <body> and stops the event there, so a listener on `window` — the
        // obvious place, and where this started — never heard a single key.
        // Capturing on the document runs before anything can swallow it.
        // The cost is that this now sees keys meant for other people, so the
        // handler bows out for text fields and for any open dialog.
        useExternalListener(document, "keydown", this.onKeydown.bind(this), { capture: true });
        onWillUnmount(() => { if (this._tick) { clearInterval(this._tick); } });
        onWillStart(async () => { await this.loadFleet(); });
    }

    ic(n, s = 16) { return TIC[n] ? tic(n, s) : kitIc(n, s); }

    _freshWiz() {
        return {
            step: 1, running: false, finished: false, error: null,
            form: { name: "", slug: "", admin_name: "", admin_email: "", country_code: "" },
            slugTouched: false,
            slug: { st: "idle", msg: "", url: "" },
            steps: [], console: [], tenantId: null, creds: null, doneUrl: null,
        };
    }

    // ------------------------------------------------------------- fleet
    async loadFleet(silent = true) {
        const call = silent ? this.orm.silent : this.orm;
        const d = await call.call("pb.tenants", "get_fleet_data", []);
        this.state.data = d;
        this.state.loaded = true;
    }

    async recheckPlatform() {
        this.state.det.busy = "platform";
        try { await this.loadFleet(); } finally { this.state.det.busy = ""; }
        this.notif.add(_t("Platform status refreshed."), { type: "info" });
    }

    async refreshFleetHealth() {
        this.state.det.busy = "platform";
        try {
            const d = await this.orm.silent.call("pb.tenants", "refresh_health", []);
            this.state.data = d;
        } finally { this.state.det.busy = ""; }
    }

    openUrl(url) { window.open(url, "_blank"); }

    async copy(text, label = _t("Copied")) {
        try {
            await navigator.clipboard.writeText(text);
            this.notif.add(label + " — " + text, { type: "success" });
        } catch {
            this.notif.add(_t("Copy failed — select and copy manually."), { type: "warning" });
        }
    }

    // ------------------------------------------------------------- wizard
    openWizard() {
        this.state.wiz = this._freshWiz();
        this.state.view = "wizard";
    }

    closeWizard() {
        if (this.state.wiz.running) { return; }
        this.state.view = "fleet";
        this.loadFleet();
    }

    slugify(name) {
        return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").replace(/^[0-9-]+/, "").slice(0, 30);
    }

    onNameInput() {
        const w = this.state.wiz;
        if (!w.slugTouched) {
            w.form.slug = this.slugify(w.form.name);
            this.queueSlugCheck();
        }
    }

    onSlugInput() {
        const w = this.state.wiz;
        w.slugTouched = true;
        w.form.slug = this.slugify(w.form.slug) || w.form.slug.toLowerCase();
        this.queueSlugCheck();
    }

    queueSlugCheck() {
        const w = this.state.wiz;
        clearTimeout(this._slugTimer);
        if (!w.form.slug) { w.slug = { st: "idle", msg: "", url: "" }; return; }
        w.slug = { st: "checking", msg: _t("Checking availability…"), url: "" };
        this._slugTimer = setTimeout(async () => {
            const slug = w.form.slug;
            try {
                const r = await this.orm.silent.call("pb.tenants", "check_slug", [slug]);
                if (this.state.wiz.form.slug !== slug) { return; }
                w.slug = r.ok
                    ? { st: "ok", msg: _t("Available"), url: r.url }
                    : { st: "bad", msg: r.reason || _t("Not available"), url: "" };
            } catch (e) {
                if (this.state.wiz.form.slug !== slug) { return; }
                w.slug = { st: "bad", msg: this.errText(e, _t("Could not check — retry.")), url: "" };
            }
        }, 350);
    }

    /**
     * Readable one-liner for a failed RPC.
     *
     * This used to be a bare `catch {}` painting "Could not check — retry." over
     * everything, which made a dropped connection and a real server refusal look
     * identical — and cost an afternoon of diagnosis once. Always keep the cause
     * visible: on screen if we can name it, in the console regardless.
     */
    errText(e, fallback) {
        console.error("pb_tenants RPC failed:", e);
        if (!e) { return fallback; }
        if (e instanceof ConnectionLostError || e.name === "ConnectionLostError") {
            return _t("Lost connection to the server — check your network and retry.");
        }
        const raw = e.data?.message || e.message || e.data?.arguments?.[0] || "";
        const msg = String(raw).trim().split("\n")[0];
        return msg ? (msg.length > 160 ? msg.slice(0, 157) + "…" : msg) : fallback;
    }

    get wizValid() {
        const w = this.state.wiz;
        return !!(w.form.name.trim() && w.slug.st === "ok" && /\S+@\S+\.\S+/.test(w.form.admin_email));
    }

    toReview() { if (this.wizValid) { this.state.wiz.step = 2; } }
    backToIdentity() { this.state.wiz.step = 1; }

    async launchProvision() {
        const w = this.state.wiz;
        w.step = 3;
        w.steps = this.state.data.steps.map((s) => ({ ...s, state: "pending", ms: 0 }));
        await this.runProvision();
    }

    async runProvision() {
        const w = this.state.wiz;
        w.running = true; w.error = null;
        try {
            if (!w.tenantId) {
                const res = await this.orm.silent.call("pb.tenants", "provision_start", [{ ...w.form }]);
                w.tenantId = res.tenant_id;
                w.console.push({ line: _t("Provisioning %(host)s …", { host: w.form.slug + "." + this.state.data.base_domain }), level: "info" });
            }
            for (const st of w.steps) {
                if (st.state === "done") { continue; }
                st.state = "run";
                const r = await this.orm.silent.call("pb.tenants", "provision_run", [w.tenantId, st.key]);
                (r.log || []).forEach((l) => w.console.push(l));
                st.ms = r.ms || 0;
                if (!r.ok) {
                    st.state = "fail";
                    w.error = r.error || _t("Step failed.");
                    return;
                }
                st.state = "done";
                if (r.credentials) { w.creds = r.credentials; }
                if (r.url) { w.doneUrl = r.url; }
            }
            w.finished = true;
            this.loadFleet();
        } catch (e) {
            const cur = w.steps.find((s) => s.state === "run");
            if (cur) { cur.state = "fail"; }
            w.error = (e && e.data && e.data.message) || (e && e.message) || "Provisioning failed.";
            w.console.push({ line: w.error, level: "error" });
        } finally {
            w.running = false;
        }
    }

    retryProvision() {
        const w = this.state.wiz;
        w.steps.forEach((s) => { if (s.state === "fail") { s.state = "pending"; } });
        this.runProvision();
    }

    // -------------------------------------------------- in step with master
    //
    // The whole view is READ-ONLY until somebody presses the one button, and
    // the copy says so in those words. Nothing on this screen runs on a timer,
    // on an upgrade or on a deploy: a customer's database does not gain a part
    // of the product because something else was upgraded. The nightly check
    // that keeps these numbers fresh only ever LOOKS.

    _freshSync() {
        return {
            loaded: false, busy: "", d: null, open: {}, result: null,
            notes: "", run: null, dry: null,
        };
    }

    async openSync() {
        this.state.view = "sync";
        this.state.sync = this._freshSync();
        await this.loadSync();
    }

    async loadSync(quiet = true) {
        const s = this.state.sync;
        try {
            s.d = await this.orm.silent.call("pb.tenants", "sync_report", []);
            s.loaded = true;
            if (!quiet) { this.notif.add(_t("Re-checked."), { type: "info" }); }
        } catch (e) {
            this.notif.add(this.errText(e, _t("The report could not be read.")), { type: "danger" });
            this.state.view = "fleet";
        }
    }

    toggleSyncRow(key) {
        this.state.sync.open[key] = !this.state.sync.open[key];
    }

    /** The one-word standing of a database, and the colour that goes with it. */
    releaseChip(row) {
        const rel = this.state.sync.d && this.state.sync.d.release;
        const name = rel ? rel.name : "";
        if (row.state === "decommissioned") { return { cls: "muted", label: _t("closed down") }; }
        // With no release cut there is nothing to be "on", and repeating the
        // status word in two neighbouring columns tells the reader nothing.
        if (!name) { return { cls: "muted", label: _t("no release yet") }; }
        switch (row.release_state) {
            case "on":     return { cls: "ok",    label: name || _t("in step") };
            case "behind": return { cls: "warn",  label: name ? _t("behind %(release)s", { release: name }) : _t("behind") };
            case "none":   return { cls: "muted", label: _t("no release yet") };
            default:       return { cls: "muted", label: _t("not checked") };
        }
    }

    /** How full the ring on the release banner is drawn. */
    get releaseRing() {
        const r = this.state.sync.d && this.state.sync.d.release;
        const total = (this.state.sync.d && this.state.sync.d.measured) || 0;
        const on = (this.state.sync.d && this.state.sync.d.on_release) || 0;
        const pct = r && total ? Math.round((on / total) * 100) : 0;
        // r=26 circle: circumference 163.4
        return { pct, dash: `${(163.4 * pct) / 100} 163.4`, on, total };
    }

    get syncBlocked() {
        const d = this.state.sync.d;
        return !!(d && d.master_behind_files && d.master_behind_files.length);
    }

    /** Plain-English names for what the one call is doing, ticked on a timer. */
    get syncStepLabels() {
        return [
            _t("Refreshing its list of parts"),
            _t("Adding what is missing"),
            _t("Bringing versions up to the master"),
            _t("Re-reading who can do what"),
            _t("Checking nothing was skipped"),
            _t("Recording where it now stands"),
        ];
    }

    async syncDryRun(row) {
        const s = this.state.sync;
        s.busy = row.key;
        s.dry = null;
        s.result = null;
        try {
            s.dry = await this.orm.call("pb.tenants", "sync_bring_in_step", [row.key, true]);
        } catch (e) {
            this.notif.add(this.errText(e, _t("The preview could not be made.")), { type: "danger" });
        } finally {
            s.busy = "";
        }
    }

    syncBringInStep(row) {
        const s = this.state.sync;
        const add = row.to_install.length;
        const up = row.to_update.length;
        const bits = [];
        if (add) { bits.push(_t("%(n)s to add", { n: add })); }
        if (up) { bits.push(_t("%(n)s to move to the master's version (and anything that depends on them)", { n: up })); }
        let body = _t(
            "%(what)s, then a check that nothing was skipped. Their own data is not touched and nothing is taken away. " +
            "This takes a minute or two.",
            { what: bits.join(_t(" and ")) }
        );
        if (row.is_template) {
            body += " " + _t("Afterwards the template's scheduled jobs are switched back off, the way a template should sit.");
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Bring %(name)s in step", { name: row.name }),
            body,
            confirmLabel: _t("Bring it in step"),
            confirm: () => this._runBringInStep(row),
            cancel: () => {},
        });
    }

    /**
     * One RPC, six named steps.
     *
     * The server does the whole unit in a single call — it has to, because the
     * database it is working on rebuilds itself halfway through and cannot be
     * asked questions in the meantime. So the stepper below is honest about
     * what it is: the step names in the order they happen, ticked on a patient
     * cadence, snapping to the real answer the moment it arrives. The copy says
     * "a minute or two" rather than showing a percentage nobody measured.
     */
    async _runBringInStep(row) {
        const s = this.state.sync;
        s.busy = row.key;
        s.result = null;
        s.dry = null;
        s.run = {
            key: row.key, name: row.name,
            steps: this.syncStepLabels.map((label) => ({ label, state: "pending" })),
            idx: 0,
        };
        s.run.steps[0].state = "run";
        this._tick = setInterval(() => {
            const run = this.state.sync.run;
            if (!run || run.idx >= run.steps.length - 1) { return; }
            run.steps[run.idx].state = "done";
            run.idx += 1;
            run.steps[run.idx].state = "run";
        }, 7000);
        try {
            const r = await this.orm.call("pb.tenants", "sync_bring_in_step", [row.key, false]);
            s.result = r;
            this.notif.add(r.message || _t("Done."), { type: r.skipped_count > 0 ? "warning" : "success" });
        } catch (e) {
            const msg = this.errText(e, _t("It did not finish."));
            if (s.run) {
                s.run.steps[s.run.idx].state = "fail";
                s.run.error = msg;
            }
            this.notif.add(msg, { type: "danger" });
        } finally {
            clearInterval(this._tick);
            this._tick = null;
            if (s.run && !s.run.error) { s.run = null; }
            s.busy = "";
            await this.loadSync();
            this.loadFleet();
        }
    }

    dismissResult() {
        this.state.sync.result = null;
        this.state.sync.dry = null;
        this.state.sync.run = null;
    }

    cutRelease() {
        const s = this.state.sync;
        this.dialog.add(ConfirmationDialog, {
            title: _t("Cut a release"),
            body: _t(
                "This writes down exactly what the master runs right now and names it after today. " +
                "From then on every customer is measured against that list instead of against a moving target."
            ),
            confirmLabel: _t("Cut it"),
            confirm: async () => {
                s.busy = "release";
                try {
                    s.d = await this.orm.call("pb.tenants", "release_cut", [s.notes || ""]);
                    s.notes = "";
                    this.notif.add(
                        _t("Release %(name)s cut.", { name: s.d.release ? s.d.release.name : "" }),
                        { type: "success" });
                    this.loadFleet();
                } catch (e) {
                    this.notif.add(this.errText(e, _t("The release could not be cut.")), { type: "danger" });
                } finally {
                    s.busy = "";
                }
            },
            cancel: () => {},
        });
    }

    // ------------------------------------------------- telling a customer
    //
    // THE ONE PLACE THE PLATFORM SPEAKS TO PEOPLE WHO ARE NOT ITS OWNER. Every
    // word typed here lands at the top of every page of a payroll office that
    // is trying to get paid this week, so the composer is built around one
    // idea: nothing is sent that the sender has not already seen exactly as it
    // will look. The preview below the form IS the bar.

    _freshNotice() {
        return {
            open: false, busy: false, target: "all",
            kind: "maintenance", title: "", text: "",
            starts_at: "", ends_at: "",
            live: [], result: null, error: "",
        };
    }

    /**
     * Open the composer, pointed at everybody or at one customer.
     *
     * `target` is "all" or a customer id as a string — the same two shapes the
     * server takes, so nothing is translated between here and there.
     */
    async openNotice(target = "all") {
        // A tenant id arrives as a number from the detail screen and as the
        // string "all" from the fleet head; the server takes either, and the
        // `<select>` only ever hands back strings — so everything is a string
        // from here on, coerced HERE rather than in the template (F16).
        target = String(target);
        const fresh = this._freshNotice();
        fresh.open = true;
        fresh.target = String(target);
        this.state.notice = fresh;
        // EVERYTHING AFTER THIS POINT WRITES THROUGH `this.state.notice`, NOT
        // through `fresh`. The two are the same data, but only the one read
        // back off the state is the reactive proxy: mutating the raw object
        // changes the value and tells nobody, so the two date boxes stayed
        // visibly empty while holding the defaults the server had just sent.
        try {
            const d = await this.orm.silent.call("pb.tenants", "notice_compose_defaults", []);
            const n = this.state.notice;
            if (!n.open || n.target !== String(target)) { return; }  // closed meanwhile
            n.starts_at = this._forInput(d.starts_at);
            n.ends_at = this._forInput(d.ends_at);
            n.live = d.live || [];
        } catch (e) {
            this.state.notice.error = this.errText(
                e, _t("The composer could not be set up."));
        }
    }

    closeNotice() {
        if (this.state.notice.busy) { return; }
        this.state.notice = this._freshNotice();
    }

    /**
     * A stamp the server sent, as the WALL CLOCK IN FRONT OF THE PERSON TYPING.
     *
     * THE TIME ZONE IS THE WHOLE POINT OF THESE TWO METHODS. The server keeps
     * every moment in UTC, and `<input type="datetime-local">` shows and
     * returns the reader's own local time with no zone attached at all. Pass
     * one straight into the other and the window silently moves by the
     * offset — seven hours, here — and nobody sees it until a customer's bar
     * announces maintenance in the middle of their morning (F17).
     */
    _forInput(stamp) {
        if (!stamp) { return ""; }
        const d = new Date(String(stamp).replace(" ", "T") + "Z");
        if (isNaN(d.getTime())) { return ""; }
        const p = (n) => String(n).padStart(2, "0");
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
             + `T${p(d.getHours())}:${p(d.getMinutes())}`;
    }

    /** The reverse: what the person typed, as the UTC stamp the server stores. */
    _toUtc(local) {
        if (!local) { return ""; }
        const d = new Date(local);          // no zone suffix -> read as LOCAL
        if (isNaN(d.getTime())) { return ""; }
        return d.toISOString().slice(0, 19).replace("T", " ");
    }

    /**
     * The notice as the customer will receive it, rebuilt on every keystroke.
     *
     * A getter and NOT stored state: it is derived from three inputs and OWL
     * recomputes it when they change. Its `id` is a constant, because the
     * preview is never dismissed and the real id is minted by the server at the
     * moment of sending.
     */
    get previewNotice() {
        const n = this.state.notice;
        return {
            id: "preview",
            kind: n.kind,
            title: n.title.trim() || _t("Your message goes here"),
            text: n.text.trim(),
            // Converted to UTC exactly as the send will convert them, so the
            // phrase under the form is the phrase the customer will read.
            starts_at: this._toUtc(n.starts_at),
            ends_at: this._toUtc(n.ends_at),
        };
    }

    /** Who this send reaches, in a sentence — checked before the button, not after. */
    get noticeAudience() {
        const n = this.state.notice;
        if (n.target === "all") {
            const linked = n.live.filter((t) => t.linked);
            const cold = n.live.filter((t) => !t.linked);
            return {
                count: linked.length,
                names: linked.map((t) => t.name),
                cold: cold.map((t) => t.name),
            };
        }
        const one = n.live.find((t) => String(t.id) === n.target);
        return {
            count: one && one.linked ? 1 : 0,
            names: one ? [one.name] : [],
            cold: one && !one.linked ? [one.name] : [],
        };
    }

    get noticeValid() {
        const n = this.state.notice;
        if (!n.title.trim() || n.busy) { return false; }
        if (n.starts_at && n.ends_at && n.ends_at <= n.starts_at) { return false; }
        return this.noticeAudience.count > 0;
    }

    /** Why the send button is off — never a disabled control with no reason. */
    get noticeBlocker() {
        const n = this.state.notice;
        if (!n.title.trim()) { return _t("Give the message a title."); }
        if (n.starts_at && n.ends_at && n.ends_at <= n.starts_at) {
            return _t("The message has to finish after it starts.");
        }
        if (this.noticeAudience.count === 0) {
            return this.noticeAudience.cold.length
                ? _t("Nobody here can receive it yet — bring them in step first.")
                : _t("There are no live customers to send it to.");
        }
        return "";
    }

    async sendNotice() {
        const n = this.state.notice;
        if (!this.noticeValid) { return; }
        n.busy = true;
        n.error = "";
        try {
            n.result = await this.orm.call("pb.tenants", "notice_send", [
                n.target === "all" ? "all" : parseInt(n.target, 10),
                n.kind, n.title, n.text,
                this._toUtc(n.starts_at), this._toUtc(n.ends_at),
            ]);
            this.notif.add(n.result.message, { type: "success" });
            await this.loadFleet();
            if (this.state.view === "detail" && this.state.det.id) {
                await this._detCall("get_tenant", [this.state.det.id], "notice");
            }
        } catch (e) {
            n.error = this.errText(e, _t("The message was not sent."));
        } finally {
            n.busy = false;
        }
    }

    clearNotice(target) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Take the message down"),
            body: _t("The bar disappears from their pages within a minute. " +
                     "Nothing else changes."),
            confirmLabel: _t("Take it down"),
            confirm: async () => {
                try {
                    const r = await this.orm.call("pb.tenants", "notice_clear",
                        [target === "all" ? "all" : parseInt(target, 10)]);
                    this.notif.add(r.message, { type: "success" });
                    await this.loadFleet();
                    if (this.state.view === "detail" && this.state.det.id) {
                        await this._detCall("get_tenant", [this.state.det.id], "notice");
                    }
                } catch (e) {
                    this.notif.add(this.errText(e, _t("It could not be taken down.")),
                                   { type: "danger" });
                }
            },
            cancel: () => {},
        });
    }

    // -------------------------------------------------------- keyboard
    //
    // Two keys, and they are the two a person presses forty times an hour on
    // this screen: look again, and get out of whatever is open.
    onKeydown(ev) {
        const el = ev.target;
        const typing = el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
        if (typing || ev.ctrlKey || ev.metaKey || ev.altKey) { return; }
        // A dialog owns the keyboard while it is open — Escape belongs to it.
        if (document.querySelector(".o_dialog, .modal.show")) { return; }
        if (ev.key === "Escape") {
            // The composer is a scrim over whatever view opened it, so it owns
            // Escape before that view does.
            if (this.state.notice.open) { this.closeNotice(); return; }
            if (this.state.view === "sync") {
                if (this.state.sync.result || this.state.sync.dry || this.state.sync.run) {
                    this.dismissResult();
                } else if (Object.values(this.state.sync.open).some(Boolean)) {
                    this.state.sync.open = {};
                } else if (!this.state.sync.busy) {
                    this.backToFleet();
                }
            } else if (this.state.view === "detail") {
                this.backToFleet();
            }
            return;
        }
        if (ev.key === "r" || ev.key === "R") {
            if (this.state.notice.open) { return; }
            if (this.state.view === "sync" && !this.state.sync.busy) {
                ev.preventDefault();
                this.loadSync(false);
            } else if (this.state.view === "fleet") {
                ev.preventDefault();
                this.refreshFleetHealth();
            }
        }
    }

    // ------------------------------------------------------------- detail
    async openDetail(id) {
        this.state.det = { id, tab: "overview", d: null, busy: "", confirm: "", newDomain: "", restoreMsg: null, syncOpen: false };
        this.state.view = "detail";
        this.state.det.d = await this.orm.silent.call("pb.tenants", "get_tenant", [id]);
    }

    /**
     * The last "bring in step" on this customer, unpacked for reading.
     *
     * Stored as one blob at the moment it happened, so the question "what did
     * that button actually do" has an answer weeks later — which it did not
     * before, when the only trace was a line in a log nobody opens.
     */
    get lastSync() {
        const raw = this.state.det.d && this.state.det.d.last_sync_result;
        if (!raw) { return null; }
        try {
            return JSON.parse(raw);
        } catch {
            return null;
        }
    }

    backToFleet() {
        this.state.view = "fleet";
        this.loadFleet();
    }

    async _detCall(method, args, busy, okMsg) {
        const det = this.state.det;
        det.busy = busy;
        try {
            const d = await this.orm.silent.call("pb.tenants", method, args);
            if (d && d.id) { det.d = d; }
            if (okMsg) { this.notif.add(okMsg, { type: "success" }); }
            return d;
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("Action failed."), { type: "danger" });
        } finally {
            det.busy = "";
        }
    }

    async refreshTenantHealth() {
        await this._detCall("refresh_health", [this.state.det.id], "health", "Health refreshed.");
    }

    async backupNow() {
        await this._detCall("backup_now", [this.state.det.id, "manual"], "backup", "Backup completed.");
    }

    restoreStaging(backupId) {
        const det = this.state.det;
        this.dialog.add(ConfirmationDialog, {
            title: _t("Restore to staging"),
            body: _t("This restores a copy of the backup into '%(database)s'. The live tenant is untouched. Any existing staging copy is replaced. Continue?", { database: det.d.staging_db }),
            confirmLabel: _t("Restore copy"),
            confirm: () => {
                this._detCall("restore_staging", [det.id, backupId || null], "restore").then((r) => {
                    if (r && r.staging_url) {
                        det.restoreMsg = r;
                        this._detCall("get_tenant", [det.id], "restore");
                    }
                });
            },
            cancel: () => {},
        });
    }

    dropStaging() {
        const det = this.state.det;
        this.dialog.add(ConfirmationDialog, {
            title: _t("Remove staging copy"),
            body: _t("Drop the staging database '%(database)s'? The live tenant is untouched.", { database: det.d.staging_db }),
            confirmLabel: _t("Drop staging"),
            confirm: () => { det.restoreMsg = null; this._detCall("drop_staging", [det.id], "restore", "Staging removed."); },
            cancel: () => {},
        });
    }

    async addDomain() {
        const det = this.state.det;
        const host = (det.newDomain || "").trim();
        if (!host) { return; }
        const d = await this._detCall("domain_add", [det.id, host], "domain", "Domain added — configure DNS next.");
        if (d) { det.newDomain = ""; }
    }

    async checkDomain(id) { await this._detCall("domain_check", [id], "domain"); }
    async activateDomain(id) { await this._detCall("domain_activate", [id], "domain", "Domain is live with TLS."); }

    removeDomain(id, hostname) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Remove domain"),
            body: _t("Detach %(hostname)s from this tenant? Its certificate and routing are removed.", { hostname }),
            confirmLabel: _t("Remove"),
            confirm: () => { this._detCall("domain_remove", [id], "domain", "Domain removed."); },
            cancel: () => {},
        });
    }

    async offboard() {
        const det = this.state.det;
        if (det.confirm !== det.d.slug) { return; }
        det.busy = "offboard";
        try {
            const r = await this.orm.call("pb.tenants", "offboard", [det.id, det.confirm]);
            this.notif.add(_t("Tenant decommissioned. Final backup: %(backup)s", { backup: r.final_backup || _t("n/a") }), { type: "success" });
            this.backToFleet();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("Offboarding failed."), { type: "danger" });
        } finally {
            det.busy = "";
        }
    }

    /** "Assets, Employees, Contracts" — a list of parts, for a sentence. */
    labelList(rows) {
        return (rows || []).map((r) => r.label || r.module).join(", ");
    }

    /** The release chip on a fleet card and on the detail screen. */
    fleetReleaseChip(t) {
        const rel = this.state.data.release;
        switch (t.release_state) {
            case "on":     return { cls: "ok",    label: t.release || (rel ? rel.name : _t("in step")) };
            case "behind": return { cls: "warn",  label: rel ? _t("behind %(release)s", { release: rel.name }) : _t("behind") };
            case "none":   return { cls: "muted", label: _t("no release") };
            default:       return { cls: "muted", label: _t("not checked") };
        }
    }

    healthDot(t) {
        return { ok: "hd-ok", warn: "hd-warn", down: "hd-down" }[t.health] || "hd-unknown";
    }
}

registry.category("actions").add("pb_tenants", PbTenants);
