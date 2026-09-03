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
    // FLEET P5. Three standings a customer can be in that are not "paying and
    // running", each with the colour that says how worried to be: a trial is
    // information, a paused customer is a problem, and a customer with a
    // deletion date on them is neither — it is a decision already taken.
    trial: ["info", _t("On trial")],
    suspended: ["err", _t("Paused")],
    pending_deletion: ["muted", _t("Deleting")],
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
            // The checks card once everything is green: hidden, but one click
            // away — "Send a test email" is wanted on a good day too.
            checksOpen: false,
            wiz: this._freshWiz(),
            det: { id: null, tab: "overview", d: null, busy: "", confirm: "", newDomain: "", restoreMsg: null, syncOpen: false },
            // "In step with master": read-only until somebody presses the button.
            sync: this._freshSync(),
            // The waves a release goes out in. Read-only until Start.
            roll: this._freshRoll(),
            // One customer's wave, window and history of updates.
            upd: { d: null, busy: "", openTask: null },
            // The notice composer. Closed until somebody opens it.
            notice: this._freshNotice(),
            // FLEET P3. What is wrong right now, and the settings behind it.
            alerts: this._freshAlerts(),
            // FLEET P4. Which parts of the product each customer gets.
            feat: this._freshFeat(),
            // FLEET P5. What every customer pays, and what they have used.
            bill: this._freshBill(),
            // FLEET P5. One customer's plan, standing and invoice history.
            plan: this._freshPlanTab(),
            settings: { open: false, busy: false, d: null, error: "" },
            mailTest: null,
        });
        this._tick = null;
        this._rollPoll = null;
        // DOCUMENT, IN THE CAPTURE PHASE, AND BOTH HALVES ARE LOAD-BEARING.
        // Something in the shared web client already listens for keydown on
        // <body> and stops the event there, so a listener on `window` — the
        // obvious place, and where this started — never heard a single key.
        // Capturing on the document runs before anything can swallow it.
        // The cost is that this now sees keys meant for other people, so the
        // handler bows out for text fields and for any open dialog.
        useExternalListener(document, "keydown", this.onKeydown.bind(this), { capture: true });
        onWillUnmount(() => {
            if (this._tick) { clearInterval(this._tick); }
            if (this._rollPoll) { clearInterval(this._rollPoll); }
        });
        onWillStart(async () => { await this.loadFleet(); });
    }

    ic(n, s = 16) { return TIC[n] ? tic(n, s) : kitIc(n, s); }

    _freshWiz() {
        return {
            step: 1, running: false, finished: false, error: null,
            // FLEET P5. A customer is created ON a plan, because a customer
            // with no plan is a customer nobody can invoice — and the moment
            // to notice that is now, not at the end of the month.
            form: { name: "", slug: "", admin_name: "", admin_email: "",
                    country_code: "", plan_id: false, trial: false },
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
        return !!(w.form.name.trim() && w.slug.st === "ok"
                  && /\S+@\S+\.\S+/.test(w.form.admin_email) && w.form.plan_id);
    }

    /** The plans offered in the wizard: the ones still on sale. */
    get wizPlans() {
        return (this.state.data.plans || []).filter((p) => p.active);
    }

    get wizPlan() {
        return this.wizPlans.find((p) => p.id === this.state.wiz.form.plan_id) || null;
    }

    pickWizPlan(planId) {
        const w = this.state.wiz;
        w.form.plan_id = planId;
        // A plan's own trial length is what a trial on it lasts, so the toggle
        // is only offered once a plan has been chosen.
        if (!planId) { w.form.trial = false; }
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
        this.state.roll = this._freshRoll();
        await this.loadSync();
        this.loadRollout();
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
                    // The rings belong to a release, so a new release means the
                    // panel above them is talking about the wrong one until it
                    // is asked again.
                    this.loadRollout();
                } catch (e) {
                    this.notif.add(this.errText(e, _t("The release could not be cut.")), { type: "danger" });
                } finally {
                    s.busy = "";
                }
            },
            cancel: () => {},
        });
    }

    // ---------------------------------------------------------- rollouts
    //
    // THE HERO OF THIS SCREEN IS THE ROW OF RINGS. A release does not land on
    // the fleet; it walks across it, one wave at a time — a practice run on a
    // copy nobody sees, the blank database new customers are made from, one
    // customer on their own, the customers who volunteered to be early, then
    // everybody. Each wave is a card, each customer a chip with a dot, and the
    // dot is the whole status: waiting, updating, done, failed, left behind.
    //
    // NOTHING ON THIS SCREEN STARTS ANYTHING. The plan dialog says so in those
    // words, and the button that starts it is the only one that does.

    _freshRoll() {
        return {
            loaded: false, d: null, busy: "",
            plan: null, planOpen: false, watch: 24, early: 48,
            abortText: "", skipFor: null, skipText: "",
            logOpen: false, ringIdx: 0,
        };
    }

    async loadRollout(quiet = true) {
        const r = this.state.roll;
        try {
            r.d = await this.orm.silent.call("pb.tenants", "rollout_state", []);
            r.loaded = true;
            this._syncPoll();
        } catch (e) {
            if (!quiet) {
                this.notif.add(this.errText(e, _t("The rollout could not be read.")),
                               { type: "danger" });
            }
        }
    }

    /**
     * Watch a rollout that is actually moving, and only then.
     *
     * A rollout spends most of its life waiting for somebody's night, and
     * polling through that would be a request every eight seconds for a day to
     * be told nothing has changed. The poll runs while a task is in flight and
     * stops the moment it is not.
     */
    _syncPoll() {
        const cur = this.state.roll.d && this.state.roll.d.current;
        const live = !!cur && cur.state === "running";
        if (live && !this._rollPoll) {
            this._rollPoll = setInterval(() => {
                if (this.state.view !== "sync") { return; }
                this.loadRollout();
            }, 8000);
        } else if (!live && this._rollPoll) {
            clearInterval(this._rollPoll);
            this._rollPoll = null;
        }
    }

    get rollout() { return (this.state.roll.d && this.state.roll.d.current) || null; }

    /** The heading over the rings. Past tense once it is over. */
    get rolloutTitle() {
        const r = this.rollout;
        if (!r) { return ""; }
        if (r.state === "done") { return _t("Release %(name)s went out", { name: r.release }); }
        if (r.state === "aborted") { return _t("Release %(name)s was called off", { name: r.release }); }
        return _t("Release %(name)s is going out", { name: r.release });
    }

    /** The one sentence at the top of the rings: where this release has got to. */
    get rolloutHeadline() {
        const r = this.rollout;
        if (!r) { return ""; }
        switch (r.state) {
            case "done":
                return _t(
                    "Release %(name)s is on %(done)s of %(total)s customers. Took %(mins)s minutes.",
                    { name: r.release, done: r.customer_done, total: r.customer_total, mins: r.minutes });
            case "paused":
                return _t("Stopped at the %(ring)s.", { ring: r.current_ring_label.toLowerCase() });
            case "waiting":
                return r.watch_left_h
                    ? _t("Watching the %(ring)s — %(hours)s h left.",
                         { ring: r.current_ring_label.toLowerCase(), hours: r.watch_left_h })
                    : _t("Waiting for the next customer's window to open.");
            case "aborted":
                return _t("Called off. %(done)s of %(total)s customers got it.",
                          { done: r.customer_done, total: r.customer_total });
            default:
                return _t("%(ring)s — %(done)s of %(total)s steps done.",
                          { ring: r.current_ring_label, done: r.done_count, total: r.task_count });
        }
    }

    taskDot(t) {
        return { queued: "q", running: "r", done: "d", failed: "f", skipped: "s" }[t.state] || "q";
    }

    /** What a chip says when you rest on it — never a bare state word. */
    taskTitle(t) {
        switch (t.state) {
            case "queued":
                return t.run_now
                    ? _t("%(who)s — next in line, not waiting for their window.", { who: t.label })
                    : _t("%(who)s — waiting for their window%(when)s.",
                         { who: t.label, when: t.scheduled_for ? " (" + t.scheduled_for + ")" : "" });
            case "running": return _t("%(who)s — being updated now.", { who: t.label });
            case "done": return _t("%(who)s — done in %(secs)s seconds.", { who: t.label, secs: t.duration_s });
            case "failed": return _t("%(who)s — %(why)s", { who: t.label, why: t.error });
            case "skipped": return _t("%(who)s — left behind on the old release.", { who: t.label });
            default: return t.label;
        }
    }

    async openRolloutPlan() {
        const r = this.state.roll;
        r.busy = "plan";
        try {
            r.plan = await this.orm.call("pb.tenants", "rollout_plan", []);
            r.watch = r.plan.watch_canary;
            r.early = r.plan.watch_early;
            r.planOpen = true;
        } catch (e) {
            this.notif.add(this.errText(e, _t("The plan could not be worked out.")),
                           { type: "danger" });
        } finally {
            r.busy = "";
        }
    }

    closeRolloutPlan() {
        if (this.state.roll.busy) { return; }
        this.state.roll.planOpen = false;
        this.state.roll.plan = null;
    }

    async startRollout() {
        const r = this.state.roll;
        if (r.plan && r.plan.blockers.length) { return; }
        r.busy = "start";
        try {
            r.d = await this.orm.call("pb.tenants", "rollout_start",
                                      [null, parseInt(r.watch, 10) || 0, parseInt(r.early, 10) || 0]);
            r.planOpen = false;
            r.plan = null;
            this._syncPoll();
            this.notif.add(_t("The rollout has started — the practice run goes first."),
                           { type: "success" });
            this.loadSync();
        } catch (e) {
            this.notif.add(this.errText(e, _t("It could not be started.")), { type: "danger" });
        } finally {
            r.busy = "";
        }
    }

    async _rollCall(method, args, busy, okMsg) {
        const r = this.state.roll;
        r.busy = busy;
        try {
            r.d = await this.orm.call("pb.tenants", method, args);
            this._syncPoll();
            if (okMsg) { this.notif.add(okMsg, { type: "success" }); }
            this.loadSync();
            return true;
        } catch (e) {
            this.notif.add(this.errText(e, _t("That did not work.")), { type: "danger" });
            return false;
        } finally {
            r.busy = "";
        }
    }

    rolloutPause() { this._rollCall("rollout_pause", [this.rollout.id, ""], "pause", _t("Paused.")); }
    rolloutResume() { this._rollCall("rollout_resume", [this.rollout.id], "resume"); }
    rolloutTick() { this._rollCall("rollout_tick", [this.rollout.id], "tick"); }

    continueNow() {
        const r = this.rollout;
        this.dialog.add(ConfirmationDialog, {
            title: _t("Continue now"),
            body: _t(
                "The watch period on the %(ring)s ends here and the next wave starts. " +
                "The point of waiting is that a problem shows up on one customer before it " +
                "reaches the rest — so only do this if you have looked.",
                { ring: r.current_ring_label.toLowerCase() }),
            confirmLabel: _t("Continue now"),
            confirm: () => this._rollCall("rollout_continue_now", [r.id], "continue"),
            cancel: () => {},
        });
    }

    taskRetry(t) { this._rollCall("task_retry", [t.id], "task" + t.id, _t("Back in the queue.")); }
    taskRunNow(t) { this._rollCall("task_run_now", [t.id], "task" + t.id); }

    askSkip(t) {
        this.state.roll.skipFor = t;
        this.state.roll.skipText = "";
    }

    confirmSkip() {
        const r = this.state.roll;
        const t = r.skipFor;
        this._rollCall("task_skip", [t.id, r.skipText], "task" + t.id).then((ok) => {
            if (ok) { r.skipFor = null; r.skipText = ""; }
        });
    }

    abortRollout() {
        const r = this.state.roll;
        if (r.abortText !== this.rollout.release) { return; }
        this._rollCall("rollout_abort", [this.rollout.id, r.abortText], "abort",
                       _t("Called off.")).then(() => { r.abortText = ""; });
    }

    /**
     * Arrow keys walk the row of waves.
     *
     * Bound from the component's one keydown handler (F10: `document`, capture
     * phase) rather than on the row, so it works whether or not a card happens
     * to hold focus — the row is the thing being read, not a form field.
     */
    _ringKey(dir) {
        const r = this.rollout;
        if (!r || !r.rings.length) { return; }
        const next = Math.max(0, Math.min(r.rings.length - 1, this.state.roll.ringIdx + dir));
        this.state.roll.ringIdx = next;
        const el = document.querySelectorAll(".tnx-ring")[next];
        if (el) { el.focus(); }
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
            // FLEET P3. Off unless somebody ticks it: most messages are about
            // one customer's own database and have no business on a page the
            // whole world can read.
            public: false,
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
            ], { public: !!n.public });
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

    // ------------------------------------------------------------- alerts
    //
    // WHAT IS WRONG RIGHT NOW, AND WHAT TO DO ABOUT IT. Measured against a
    // triage list rather than against a log: three groups in the order a person
    // works through them, every row carrying its own next step, and two buttons
    // that mean two different things — "I know about this" and "this is over".
    //
    // Nothing here polls. The sweep behind it runs every fifteen minutes and
    // emails; a screen that re-asks every eight seconds would be pretending to
    // be faster than the thing it is watching.

    _freshAlerts() {
        return { loaded: false, busy: "", d: null, tab: "open", idx: 0, resolveFor: null, resolveText: "" };
    }

    async openAlerts() {
        this.state.view = "alerts";
        this.state.alerts = this._freshAlerts();
        await this.loadAlerts();
    }

    async loadAlerts(quiet = true) {
        const a = this.state.alerts;
        try {
            a.d = await this.orm.silent.call("pb.tenants", "alerts_data", []);
            a.loaded = true;
            if (!quiet) { this.notif.add(_t("Looked again."), { type: "info" }); }
        } catch (e) {
            this.notif.add(this.errText(e, _t("The alerts could not be read.")), { type: "danger" });
            this.state.view = "fleet";
        }
    }

    /** Every open row in the order they are drawn — what the arrow keys walk. */
    get alertRows() {
        const d = this.state.alerts.d;
        if (!d) { return []; }
        return [...d.critical, ...d.warning, ...d.acknowledged];
    }

    get alertEmpty() {
        const d = this.state.alerts.d;
        return !!d && !this.alertRows.length;
    }

    severityWord(sev) {
        return { critical: _t("Needs attention now"), warning: _t("Worth a look"), info: _t("For information") }[sev] || _t("Worth a look");
    }

    async _alertCall(method, args, busy, okMsg) {
        const a = this.state.alerts;
        a.busy = busy;
        try {
            a.d = await this.orm.call("pb.tenants", method, args);
            if (okMsg) { this.notif.add(okMsg, { type: "success" }); }
            this.loadFleet();
            return true;
        } catch (e) {
            this.notif.add(this.errText(e, _t("That did not work.")), { type: "danger" });
            return false;
        } finally {
            a.busy = "";
        }
    }

    ackAlert(row) {
        this._alertCall("alert_ack", [row.id], "a" + row.id,
                        _t("Acknowledged — you will not be reminded about it again."));
    }

    askResolve(row) {
        this.state.alerts.resolveFor = row;
        this.state.alerts.resolveText = "";
    }

    confirmResolve() {
        const a = this.state.alerts;
        const row = a.resolveFor;
        this._alertCall("alert_resolve", [row.id, a.resolveText], "a" + row.id,
                        _t("Closed.")).then((ok) => {
            if (ok) { a.resolveFor = null; a.resolveText = ""; }
        });
    }

    checkNow() {
        this._alertCall("alert_check_now", [], "check", _t("Checked everything."));
    }

    openAlertTenant(row) {
        if (row.tenant_id) { this.openDetail(row.tenant_id); }
    }

    // ------------------------------------------------------- alert settings
    async openSettings() {
        const s = this.state.settings;
        s.open = true; s.error = ""; s.busy = true;
        try {
            s.d = await this.orm.silent.call("pb.tenants", "alert_settings", []);
        } catch (e) {
            s.error = this.errText(e, _t("The settings could not be read."));
        } finally {
            s.busy = false;
        }
    }

    closeSettings() {
        if (this.state.settings.busy) { return; }
        this.state.settings = { open: false, busy: false, d: null, error: "" };
    }

    async saveSettings() {
        const s = this.state.settings;
        s.busy = true; s.error = "";
        try {
            // The dialog edits the same dict the server sent back, so what is
            // saved is what is on screen — no second shape to keep in step.
            s.d = await this.orm.call("pb.tenants", "alert_settings_save", [{
                emails: s.d.emails,
                from: s.d.from,
                interval_critical: s.d.interval_critical,
                interval_warning: s.d.interval_warning,
                digest_hour: s.d.digest_hour,
                tenant_cost_mb: s.d.tenant_cost_mb,
                reserve_mb: s.d.reserve_mb,
                thresholds: { ...s.d.thresholds },
            }]);
            this.notif.add(_t("Saved."), { type: "success" });
            this.loadFleet();
            if (this.state.view === "alerts") { this.loadAlerts(); }
        } catch (e) {
            s.error = this.errText(e, _t("That could not be saved."));
        } finally {
            s.busy = false;
        }
    }

    /** Prove the channel. There is no other way to know it works. */
    async sendTestEmail() {
        this.state.det.busy = "mailtest";
        this.state.mailTest = null;
        try {
            const r = await this.orm.call("pb.tenants", "mail_test", []);
            this.state.mailTest = r;
            this.notif.add(r.message || (r.ok ? _t("Sent.") : _t("It did not go.")),
                           { type: r.ok ? "success" : "danger" });
            await this.loadFleet();
        } catch (e) {
            const msg = this.errText(e, _t("The test message could not be sent."));
            this.state.mailTest = { ok: false, message: msg };
            this.notif.add(msg, { type: "danger" });
        } finally {
            this.state.det.busy = "";
        }
    }

    /** How many platform checks are still unfinished. Drives the checklist. */
    get platformIssues() {
        const checks = (this.state.data.platform && this.state.data.platform.checks) || [];
        return checks.filter((c) => !c.ok).length;
    }

    /** The capacity bar: how many more customers this machine can hold. */
    get capacity() {
        return this.state.data.capacity || { level: "ok", headroom: 0, reason: "" };
    }

    get capacityBar() {
        const c = this.capacity;
        const used = Math.max(0, (c.mem_total_mb || 0) - (c.mem_available_mb || 0));
        const pct = c.mem_total_mb ? Math.min(100, Math.round((used * 100) / c.mem_total_mb)) : 0;
        return { pct, cls: c.level };
    }

    // ============================================ WHAT EACH CUSTOMER GETS
    //
    // FLEET P4. Deploy is not release. Every part of the product is installed
    // on every customer (that is what "in step" means), and THIS screen decides
    // which of them each customer can actually see. One click, and within
    // seconds their rail entry, their tiles and their search rows change.
    //
    // THE ONE SENTENCE THAT HAS TO BE ON THE SCREEN, and is: a switch takes
    // doors off a screen. It is not a security control. What somebody may read
    // on their own database is still decided by the roles they hold there.
    //
    // The hero is the preview beside the matrix: the customer's own left menu,
    // built from their own switches, with the entry fading out as the switch is
    // flipped. Nobody should have to log in as a customer to find out what they
    // will see.

    _freshFeat() {
        return {
            loaded: false, busy: "", d: null,
            tab: "matrix",
            // Which customer the preview is showing, and which cell the
            // keyboard is on. Indices into `featRows` / `featCols`.
            sel: { r: 0, c: 0 },
            // The open cell menu: `{tid, key}` or null.
            menu: null, reason: "",
            // A shift-click range down one column, ready for a bulk switch.
            range: null,
            // A bulk about to happen, waiting for one confirmation.
            confirm: null,
            // The catalogue line being edited, as a working copy.
            edit: null,
        };
    }

    async openFeatures() {
        this.state.view = "features";
        this.state.feat = this._freshFeat();
        await this.loadFeatures();
    }

    async loadFeatures(quiet = true) {
        const f = this.state.feat;
        try {
            f.d = await this.orm.silent.call("pb.tenants", "features_data", []);
            f.loaded = true;
            if (!quiet) { this.notif.add(_t("Looked again."), { type: "info" }); }
        } catch (e) {
            this.notif.add(this.errText(e, _t("The feature switches could not be read.")),
                           { type: "danger" });
            this.state.view = "fleet";
        }
    }

    /** The customers the matrix has rows for, in the order they are drawn. */
    get featRows() {
        const d = this.state.feat.d;
        return d ? (d.tenants || []) : [];
    }

    /** The features the matrix has columns for. */
    get featCols() {
        const d = this.state.feat.d;
        return d ? (d.catalogue || []) : [];
    }

    /** The customer the preview is showing. Never undefined while there are rows. */
    get featTenant() {
        const rows = this.featRows;
        if (!rows.length) { return null; }
        return rows[Math.min(this.state.feat.sel.r, rows.length - 1)] || null;
    }

    /**
     * The customer's own left menu, as their administrator will see it.
     *
     * Built from THEIR switches and OUR rail records — the same nine entries
     * this platform draws, because every customer runs the same product. An
     * entry belonging to a part they have not got is dropped when the platform
     * said hide, and kept with a padlock when it said locked. That is exactly
     * what their database will decide; this is not a drawing of it.
     */
    get featPreview() {
        const d = this.state.feat.d;
        const row = this.featTenant;
        if (!d || !row) { return []; }
        const modes = {};
        for (const c of d.catalogue || []) { modes[c.key] = c.mode; }
        const out = [];
        for (const item of d.rail || []) {
            const key = item.feature;
            const on = !key || row.on[key] !== false;
            if (!on && modes[key] !== "lock") { continue; }
            out.push({ ...item, locked: !on });
        }
        return out;
    }

    /**
     * The rail stores Lucide's own hyphenated names (`book-open`); the kit's
     * registry is keyed camelCase (`bookOpen`). Converted here rather than
     * changing either side: the rail's names are DATA on nine databases, and
     * the kit's keys are read by forty files.
     *
     * `refresh-cw` is the one that does not fall out of the rule — the kit
     * calls it `refresh` — so it is named, not guessed.
     */
    railIcon(name) {
        const alias = { "refresh-cw": "refresh" };
        const raw = name || "circle";
        if (alias[raw]) { return alias[raw]; }
        return raw.replace(/-([a-z])/g, (_m, ch) => ch.toUpperCase());
    }

    /** "9 of 10 switched on · 2 decided by hand" for one row. */
    featRowNote(row) {
        const total = this.featCols.length;
        const on = this.featCols.filter((c) => row.on[c.key] !== false).length;
        const bits = [_t("%(on)s of %(total)s on", { on, total })];
        if (row.custom) { bits.push(_t("%s decided by hand", row.custom)); }
        return bits.join(" · ");
    }

    /** Where a cell's answer came from: the catalogue, or somebody. */
    featSource(row, col) {
        return (row.source && row.source[col.key]) || "default";
    }

    featCellClass(row, col, r, c) {
        const on = row.on[col.key] !== false;
        const sel = this.state.feat.sel;
        const inRange = this._inRange(r, c);
        return [
            on ? "on" : "off",
            this.featSource(row, col) === "default" ? "std" : "own",
            (sel.r === r && sel.c === c) ? "cur" : "",
            inRange ? "rng" : "",
        ].filter(Boolean).join(" ");
    }

    /**
     * How many customers the painted range covers.
     *
     * A GETTER AND NOT `Math.abs(...)` IN THE TEMPLATE. JavaScript built-ins
     * are not in scope inside an OWL template — `Math.abs(x)` compiles to
     * `ctx.Math.abs(x)` and throws the moment that branch first renders, which
     * here would be the first shift-click somebody ever made (ledger F16).
     */
    get featRangeCount() {
        const rg = this.state.feat.range;
        return rg ? Math.abs(rg.to - rg.from) + 1 : 0;
    }

    _inRange(r, c) {
        const rg = this.state.feat.range;
        if (!rg || rg.col !== c) { return false; }
        return r >= Math.min(rg.from, rg.to) && r <= Math.max(rg.from, rg.to);
    }

    /**
     * A click on one cell.
     *
     * Plain click flips it. Shift-click paints a range down the column instead
     * of flipping anything — the reader is choosing WHO before deciding WHAT,
     * which is the order a spreadsheet trained everybody to expect.
     */
    onFeatCell(ev, r, c) {
        const f = this.state.feat;
        f.sel = { r, c };
        f.menu = null;
        if (ev && ev.shiftKey) {
            const from = (f.range && f.range.col === c) ? f.range.from : r;
            f.range = { col: c, from, to: r };
            return;
        }
        f.range = null;
        this.featToggle(r, c);
    }

    async featToggle(r, c) {
        const row = this.featRows[r];
        const col = this.featCols[c];
        if (!row || !col || this.state.feat.busy) { return; }
        const on = row.on[col.key] === false;
        await this._featCall(
            "features_set", [row.id, col.key, on, ""], `${row.id}:${col.key}`,
            on ? _t("%(f)s is on for %(who)s.", { f: col.name, who: row.name })
               : _t("%(f)s is off for %(who)s.", { f: col.name, who: row.name }));
    }

    async _featCall(method, args, busy, okMsg) {
        const f = this.state.feat;
        f.busy = busy;
        try {
            const res = await this.orm.call("pb.tenants", method, args);
            // Every one of these methods hands back the WHOLE screen, so the
            // matrix, the preview, the counts and the "last pushed" line move
            // together. A partial update is how two numbers on one screen start
            // disagreeing.
            f.d = res.data || res;
            const push = res.push;
            if (push && push.ok === false) {
                this.notif.add(push.reason || _t("That customer could not be reached."),
                               { type: "warning" });
            } else if (okMsg) {
                this.notif.add(okMsg, { type: "success" });
            }
            this.loadFleet();
            return true;
        } catch (e) {
            this.notif.add(this.errText(e, _t("That did not work.")), { type: "danger" });
            return false;
        } finally {
            f.busy = "";
        }
    }

    // ------------------------------------------------------- the cell menu
    openFeatMenu(r, c) {
        const f = this.state.feat;
        const row = this.featRows[r];
        const col = this.featCols[c];
        if (!row || !col) { return; }
        f.sel = { r, c };
        f.menu = { tid: row.id, key: col.key, r, c };
        f.reason = (row.reason && row.reason[col.key]) || "";
    }

    closeFeatMenu() { this.state.feat.menu = null; }

    get featMenuRow() {
        const m = this.state.feat.menu;
        return m ? this.featRows.find((t) => t.id === m.tid) || null : null;
    }

    get featMenuCol() {
        const m = this.state.feat.menu;
        return m ? this.featCols.find((c) => c.key === m.key) || null : null;
    }

    /** Save the one line that says why this customer's answer is what it is. */
    async saveFeatReason() {
        const row = this.featMenuRow;
        const col = this.featMenuCol;
        if (!row || !col) { return; }
        const on = row.on[col.key] !== false;
        const ok = await this._featCall(
            "features_set", [row.id, col.key, on, this.state.feat.reason],
            "reason", _t("Noted."));
        if (ok) { this.state.feat.menu = null; }
    }

    async resetFeat() {
        const row = this.featMenuRow;
        const col = this.featMenuCol;
        if (!row || !col) { return; }
        const ok = await this._featCall(
            "features_reset", [row.id, col.key], "reset",
            _t("%s is back to the standard setting.", col.name));
        if (ok) { this.state.feat.menu = null; }
    }

    async pushFeatures(tenantId) {
        await this._featCall("features_push", [tenantId], "push" + tenantId,
                             _t("Sent."));
    }

    // ----------------------------------------------------- a whole column
    /**
     * One feature, every customer (or the range somebody painted), one
     * confirmation that names the count and the names.
     */
    askFeatBulk(c, on) {
        const col = this.featCols[c];
        if (!col) { return; }
        const rg = this.state.feat.range;
        let rows = this.featRows;
        if (rg && rg.col === c) {
            const lo = Math.min(rg.from, rg.to), hi = Math.max(rg.from, rg.to);
            rows = rows.slice(lo, hi + 1);
        }
        if (!rows.length) { return; }
        this.state.feat.confirm = {
            key: col.key, name: col.name, on,
            ids: rows.map((t) => t.id),
            names: rows.map((t) => t.name),
        };
    }

    closeFeatBulk() { this.state.feat.confirm = null; }

    get featBulkSentence() {
        const cf = this.state.feat.confirm;
        if (!cf) { return ""; }
        const word = cf.on ? _t("switched on") : _t("switched off");
        return _t("%(name)s will be %(word)s for %(n)s customer(s): %(who)s.",
                  { name: cf.name, word, n: cf.ids.length,
                    who: cf.names.join(", ") });
    }

    async confirmFeatBulk() {
        const cf = this.state.feat.confirm;
        if (!cf) { return; }
        const f = this.state.feat;
        f.busy = "bulk";
        try {
            const res = await this.orm.call(
                "pb.tenants", "features_bulk", [cf.key, cf.on, cf.ids, ""]);
            f.d = res.data || f.d;
            f.confirm = null;
            f.range = null;
            this.notif.add(res.message || _t("Done."),
                           { type: (res.failed || []).length ? "warning" : "success" });
            this.loadFleet();
        } catch (e) {
            this.notif.add(this.errText(e, _t("That did not work.")), { type: "danger" });
        } finally {
            f.busy = "";
        }
    }

    // ---------------------------------------------------------- catalogue
    openFeatCatalogue() {
        this.state.feat.tab = "catalogue";
        this.state.feat.menu = null;
    }

    openFeatMatrix() {
        this.state.feat.tab = "matrix";
        this.state.feat.edit = null;
    }

    editFeature(col) {
        // A WORKING COPY, never the row itself: a form bound straight to the
        // list would rewrite the screen while somebody was still typing, and
        // Cancel would have nothing to go back to.
        this.state.feat.edit = {
            id: col.id, key: col.key, name: col.name, blurb: col.blurb || "",
            area: col.area, default_on: col.default_on, mode: col.mode,
            lock_text: col.lock_text || "", sequence: col.sequence,
        };
    }

    cancelFeatEdit() { this.state.feat.edit = null; }

    async saveFeature() {
        const e = this.state.feat.edit;
        if (!e) { return; }
        const f = this.state.feat;
        f.busy = "cat";
        try {
            f.d = await this.orm.call("pb.tenants", "feature_save", [e.id, {
                name: e.name, blurb: e.blurb, area: e.area,
                default_on: !!e.default_on, mode: e.mode,
                lock_text: e.lock_text, sequence: parseInt(e.sequence, 10) || 10,
            }]);
            f.edit = null;
            this.notif.add(_t("Saved, and every live customer has been told."),
                           { type: "success" });
            this.loadFleet();
        } catch (err) {
            this.notif.add(this.errText(err, _t("That could not be saved.")),
                           { type: "danger" });
        } finally {
            f.busy = "";
        }
    }

    /** The two words a mode is called on screen. Never "hide"/"lock" raw. */
    modeWord(mode) {
        return mode === "lock" ? _t("Shown locked") : _t("Hidden");
    }

    // --------------------------------------------------------- keyboard
    /** Move the cursor around the matrix. Returns true when it handled the key. */
    _featKey(ev) {
        const f = this.state.feat;
        if (f.tab !== "matrix" || f.confirm || f.edit) { return false; }
        const rows = this.featRows.length, cols = this.featCols.length;
        if (!rows || !cols) { return false; }
        const step = { ArrowDown: [1, 0], ArrowUp: [-1, 0],
                       ArrowRight: [0, 1], ArrowLeft: [0, -1] }[ev.key];
        if (step) {
            ev.preventDefault();
            f.menu = null;
            f.sel = {
                r: Math.max(0, Math.min(rows - 1, f.sel.r + step[0])),
                c: Math.max(0, Math.min(cols - 1, f.sel.c + step[1])),
            };
            const el = document.querySelector(
                `.tnx-fcell[data-r="${f.sel.r}"][data-c="${f.sel.c}"]`);
            if (el) { el.focus(); }
            return true;
        }
        if (ev.key === " " || ev.key === "Spacebar") {
            ev.preventDefault();
            this.featToggle(f.sel.r, f.sel.c);
            return true;
        }
        return false;
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
            if (this.state.settings.open) { this.closeSettings(); return; }
            if (this.state.bill.settingsOpen) { this.closeBillSettings(); return; }
            if (this.state.bill.preview) { this.closePreview(); return; }
            if (this.state.bill.planEdit) { this.cancelPlanEdit(); return; }
            if (this.state.bill.paidFor) { this.state.bill.paidFor = null; return; }
            if (this.state.bill.voidFor) { this.state.bill.voidFor = null; return; }
            if (this.state.feat.confirm) { this.closeFeatBulk(); return; }
            if (this.state.feat.edit) { this.cancelFeatEdit(); return; }
            if (this.state.feat.menu) { this.closeFeatMenu(); return; }
            if (this.state.alerts.resolveFor) { this.state.alerts.resolveFor = null; return; }
            if (this.state.notice.open) { this.closeNotice(); return; }
            if (this.state.roll.planOpen) { this.closeRolloutPlan(); return; }
            if (this.state.roll.skipFor) { this.state.roll.skipFor = null; return; }
            if (this.state.view === "sync") {
                if (this.state.sync.result || this.state.sync.dry || this.state.sync.run) {
                    this.dismissResult();
                } else if (Object.values(this.state.sync.open).some(Boolean)) {
                    this.state.sync.open = {};
                } else if (!this.state.sync.busy) {
                    this.backToFleet();
                }
            } else if (this.state.view === "features") {
                if (this.state.feat.range) { this.state.feat.range = null; }
                else if (!this.state.feat.busy) { this.backToFleet(); }
            } else if (this.state.view === "billing") {
                if (this.state.bill.raised) { this.state.bill.raised = null; }
                else if (!this.state.bill.busy) { this.backToFleet(); }
            } else if (this.state.view === "detail" || this.state.view === "alerts") {
                this.backToFleet();
            }
            return;
        }
        // The matrix is a grid, so it is walked and worked with the keys a grid
        // has always been walked with.
        if (this.state.view === "features" && this._featKey(ev)) { return; }
        // The alerts list is a list, so it is walked and worked with keys.
        if (this.state.view === "alerts" && !this.state.settings.open
            && !this.state.alerts.resolveFor) {
            const rows = this.alertRows;
            if ((ev.key === "ArrowDown" || ev.key === "ArrowUp") && rows.length) {
                ev.preventDefault();
                const next = this.state.alerts.idx + (ev.key === "ArrowDown" ? 1 : -1);
                this.state.alerts.idx = Math.max(0, Math.min(rows.length - 1, next));
                const el = document.querySelectorAll(".tnx-alert")[this.state.alerts.idx];
                if (el) { el.focus(); }
                return;
            }
            if ((ev.key === "a" || ev.key === "A") && rows.length) {
                const row = rows[Math.min(this.state.alerts.idx, rows.length - 1)];
                if (row && row.state === "open") {
                    ev.preventDefault();
                    this.ackAlert(row);
                }
                return;
            }
        }
        // The row of waves reads left to right, so the arrow keys walk it.
        if (this.state.view === "sync" && !this.state.roll.planOpen
            && (ev.key === "ArrowRight" || ev.key === "ArrowLeft")) {
            if (!this.rollout) { return; }
            ev.preventDefault();
            this._ringKey(ev.key === "ArrowRight" ? 1 : -1);
            return;
        }
        if (ev.key === "r" || ev.key === "R") {
            if (this.state.notice.open || this.state.roll.planOpen
                || this.state.settings.open) { return; }
            if (this.state.view === "alerts" && !this.state.alerts.busy) {
                ev.preventDefault();
                this.loadAlerts(false);
            } else if (this.state.view === "features" && !this.state.feat.busy) {
                ev.preventDefault();
                this.loadFeatures(false);
            } else if (this.state.view === "billing" && !this.state.bill.busy) {
                ev.preventDefault();
                this.loadBilling(false);
            } else if (this.state.view === "sync" && !this.state.sync.busy) {
                ev.preventDefault();
                this.loadSync(false);
                this.loadRollout(false);
            } else if (this.state.view === "fleet") {
                ev.preventDefault();
                this.refreshFleetHealth();
            }
        }
    }

    // ================================================ WHAT A CUSTOMER PAYS
    //
    // FLEET P5. The month strip across the top, the customer table under it,
    // and the one button that matters: "Raise September" — which shows every
    // invoice and every line BEFORE a single one exists. Nothing on this screen
    // creates, sends or pauses anything without somebody reading a preview
    // first, and the two crons behind it read customers and write only here.

    _freshBill() {
        return {
            loaded: false, busy: "", tab: "customers", d: null, period: null,
            preview: null, previewBusy: false, raised: null,
            planEdit: null, settingsOpen: false, settings: null, error: "",
            paidFor: null, paidNote: "", voidFor: null, voidReason: "",
        };
    }

    async openBilling() {
        this.state.bill = this._freshBill();
        this.state.view = "billing";
        await this.loadBilling(false);
    }

    async loadBilling(quiet = true) {
        const b = this.state.bill;
        b.busy = "load";
        try {
            const call = quiet ? this.orm.silent : this.orm;
            b.d = await call.call("pb.tenants", "billing_data", [b.period]);
            b.period = b.d.period;
            b.settings = { ...b.d.settings };
            b.error = "";
        } catch (e) {
            b.error = this.errText(e, _t("The billing screen could not be read."));
        } finally {
            b.busy = "";
            b.loaded = true;
        }
    }

    openBillTab(tab) { this.state.bill.tab = tab; }

    async setBillPeriod(period) {
        this.state.bill.period = period;
        this.state.bill.preview = null;
        this.state.bill.raised = null;
        await this.loadBilling();
    }

    get bill() { return this.state.bill.d || {}; }

    get billRows() { return this.bill.rows || []; }

    /** The twelve months across the top, tallest bar = most invoices. */
    get billMonths() {
        const months = this.bill.months || [];
        const top = Math.max(1, ...months.map((m) => m.invoices || 0));
        return months.map((m) => ({ ...m,
            pct: Math.round(((m.invoices || 0) * 100) / top) }));
    }

    /**
     * A customer's twelve readings as an SVG polyline. PURE-ish.
     *
     * Built here rather than in the template: JavaScript built-ins are not in
     * scope inside an OWL template (ledger F16), and a sparkline that is
     * arithmetic in markup is a sparkline nobody can read or test.
     */
    sparkline(history, key = "employees") {
        const rows = history || [];
        if (rows.length < 2) { return ""; }
        const values = rows.map((r) => r[key] || 0);
        const top = Math.max(1, ...values);
        const step = 100 / (rows.length - 1);
        return values
            .map((v, i) => `${(i * step).toFixed(1)},${(20 - (v * 18) / top).toFixed(1)}`)
            .join(" ");
    }

    seatTone(seat) {
        return { full: "bad", near: "warn" }[(seat || {}).verdict] || "ok";
    }

    invoiceTone(inv) {
        if (!inv) { return "muted"; }
        return { paid: "ok", overdue: "err", sent: "info",
                 draft: "muted", void: "muted" }[inv.state] || "muted";
    }

    // ------------------------------------------------------- the meter
    async meterNow() {
        const b = this.state.bill;
        b.busy = "meter";
        try {
            const r = await this.orm.call("pb.tenants", "meter_run", []);
            b.d = r.data;
            b.settings = { ...b.d.settings };
            this.notif.add(
                r.failed && r.failed.length
                    ? _t("Read %(n)s customer(s). Could not reach: %(who)s.",
                         { n: r.measured, who: r.failed.join(", ") })
                    : _t("Read %(n)s customer(s).", { n: r.measured }),
                { type: r.failed && r.failed.length ? "warning" : "success" });
        } catch (e) {
            this.notif.add(this.errText(e, _t("The reading could not be taken.")),
                           { type: "danger" });
        } finally {
            b.busy = "";
        }
    }

    // -------------------------------------- THE HERO: preview before create
    async openPreview() {
        const b = this.state.bill;
        b.previewBusy = true;
        b.raised = null;
        try {
            b.preview = await this.orm.call("pb.tenants", "billing_preview",
                                            [b.period]);
        } catch (e) {
            this.notif.add(this.errText(e, _t("The preview could not be built.")),
                           { type: "danger" });
        } finally {
            b.previewBusy = false;
        }
    }

    closePreview() {
        if (this.state.bill.previewBusy) { return; }
        this.state.bill.preview = null;
    }

    get previewTotals() {
        const p = this.state.bill.preview;
        if (!p) { return []; }
        return (p.totals || []).map((t) => ({
            ...t, amount_h: this._money(t.amount, t.currency) }));
    }

    /** Thousands separators, and the currency's own decimals. */
    _money(amount, currency) {
        const cur = (this.bill.currencies || []).find((c) => c.name === currency);
        const places = currency === "VND" ? 0 : 2;
        const text = Number(amount || 0).toLocaleString(undefined, {
            minimumFractionDigits: places, maximumFractionDigits: places });
        return cur && cur.symbol ? `${text} ${cur.symbol}` : text;
    }

    async confirmRaise() {
        const b = this.state.bill;
        const p = b.preview;
        if (!p || !p.billable) { return; }
        b.previewBusy = true;
        try {
            const r = await this.orm.call("pb.tenants", "billing_raise",
                                          [b.period, !p.closed]);
            b.d = r.data;
            b.settings = { ...b.d.settings };
            b.preview = null;
            b.raised = r;
            this.notif.add(_t("%(n)s invoice(s) raised for %(month)s.",
                              { n: r.created.length, month: r.period_label }),
                           { type: "success" });
            this.loadFleet();
        } catch (e) {
            this.notif.add(this.errText(e, _t("The invoices could not be raised.")),
                           { type: "danger" });
        } finally {
            b.previewBusy = false;
        }
    }

    // ------------------------------------------------- one invoice at a time
    async _invCall(method, args, busy, okMsg) {
        const b = this.state.bill;
        b.busy = busy;
        try {
            const r = await this.orm.call("pb.tenants", method, args);
            if (r && r.data) {
                b.d = r.data;
                b.settings = { ...b.d.settings };
            }
            if (okMsg) { this.notif.add(okMsg, { type: "success" }); }
            this.loadFleet();
            return r;
        } catch (e) {
            this.notif.add(this.errText(e, _t("That did not work.")),
                           { type: "danger" });
            return null;
        } finally {
            b.busy = "";
        }
    }

    sendInvoice(inv) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Email invoice %(n)s", { n: inv.number }),
            body: _t(
                "The invoice and its PDF go to %(to)s, and a copy appears on the " +
                "customer's own Plan & usage page. Nothing is charged — this is a " +
                "request for a bank transfer.", { to: inv.sent_to || this._billTo(inv) }),
            confirmLabel: _t("Send it"),
            confirm: () => this._invCall("invoice_send", [inv.id], "inv" + inv.id,
                                         _t("Sent.")),
            cancel: () => {},
        });
    }

    _billTo(inv) {
        const row = this.billRows.find((r) => r.id === inv.tenant_id);
        return (row && row.billing_email) || _t("their billing address");
    }

    askPaid(inv) {
        this.state.bill.paidFor = inv;
        this.state.bill.paidNote = "";
    }

    async confirmPaid() {
        const b = this.state.bill;
        const inv = b.paidFor;
        if (!inv) { return; }
        const ok = await this._invCall("invoice_mark_paid",
                                       [inv.id, b.paidNote], "inv" + inv.id,
                                       _t("Marked as paid."));
        if (ok) { b.paidFor = null; b.paidNote = ""; }
    }

    askVoid(inv) {
        this.state.bill.voidFor = inv;
        this.state.bill.voidReason = "";
    }

    async confirmVoid() {
        const b = this.state.bill;
        const inv = b.voidFor;
        if (!inv || !b.voidReason.trim()) { return; }
        const ok = await this._invCall("invoice_void",
                                       [inv.id, b.voidReason], "inv" + inv.id,
                                       _t("Cancelled."));
        if (ok) { b.voidFor = null; b.voidReason = ""; }
    }

    /**
     * The PDF, in the browser, without a round trip through a download route.
     *
     * The bytes are already on the record; a blob URL hands them straight to
     * whatever the reader opens PDFs with, and is revoked a moment later so the
     * page does not hold a copy of every invoice it has ever shown.
     */
    async downloadPdf(inv) {
        this.state.bill.busy = "pdf" + inv.id;
        try {
            const r = await this.orm.call("pb.tenants", "invoice_pdf", [inv.id]);
            const bytes = Uint8Array.from(atob(r.data), (c) => c.charCodeAt(0));
            const url = URL.createObjectURL(
                new Blob([bytes], { type: "application/pdf" }));
            const a = document.createElement("a");
            a.href = url;
            a.download = r.name;
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 4000);
        } catch (e) {
            this.notif.add(this.errText(e, _t("The PDF could not be made.")),
                           { type: "danger" });
        } finally {
            this.state.bill.busy = "";
        }
    }

    // ------------------------------------------------------------ the plans
    get plans() { return this.bill.plans || []; }

    newPlan() {
        this.state.bill.planEdit = {
            id: null, name: "", code: "", blurb: "", pricing: "per_employee",
            price: 0, tiers: [], currency_id: (this.bill.currencies || [])
                .map((c) => c.id)[0] || false,
            employee_limit: 0, vat_pct: 0, trial_days: 14, feature_keys: [],
            features: [], sequence: 50, active: true,
        };
    }

    editPlan(plan) {
        this.state.bill.planEdit = JSON.parse(JSON.stringify(plan));
    }

    cancelPlanEdit() { this.state.bill.planEdit = null; }

    setPlanPricing(pricing) {
        const p = this.state.bill.planEdit;
        p.pricing = pricing;
        if (pricing === "flat_tier" && !p.tiers.length) { this.addTier(); }
    }

    addTier() {
        const p = this.state.bill.planEdit;
        const last = p.tiers[p.tiers.length - 1];
        p.tiers.push({ up_to: last ? (last.up_to || 0) * 2 || 100 : 100,
                       price: last ? last.price : 0 });
    }

    removeTier(index) { this.state.bill.planEdit.tiers.splice(index, 1); }

    togglePlanFeature(key) {
        const p = this.state.bill.planEdit;
        const at = p.feature_keys.indexOf(key);
        if (at >= 0) { p.feature_keys.splice(at, 1); } else { p.feature_keys.push(key); }
    }

    get planEditValid() {
        const p = this.state.bill.planEdit;
        if (!p || !p.name.trim()) { return false; }
        return p.pricing !== "flat_tier" || p.tiers.length > 0;
    }

    async savePlan() {
        const b = this.state.bill;
        const p = b.planEdit;
        if (!this.planEditValid) { return; }
        b.busy = "plan";
        const ids = (this.bill.features || [])
            .filter((f) => p.feature_keys.includes(f.key)).map((f) => f.id);
        try {
            await this.orm.call("pb.tenants", "plan_save", [p.id || false, {
                name: p.name, code: p.code || undefined, blurb: p.blurb,
                pricing: p.pricing, price: Number(p.price) || 0,
                currency_id: p.currency_id,
                employee_limit: parseInt(p.employee_limit, 10) || 0,
                vat_pct: Number(p.vat_pct) || 0,
                trial_days: parseInt(p.trial_days, 10) || 14,
                sequence: parseInt(p.sequence, 10) || 50,
                active: p.active,
                tiers: p.tiers.map((t) => ({ up_to: parseInt(t.up_to, 10) || 0,
                                             price: Number(t.price) || 0 })),
                feature_ids: ids,
            }]);
            b.planEdit = null;
            this.notif.add(_t("Saved."), { type: "success" });
            await this.loadBilling();
        } catch (e) {
            this.notif.add(this.errText(e, _t("The plan could not be saved.")),
                           { type: "danger" });
        } finally {
            b.busy = "";
        }
    }

    archivePlan(plan) {
        this.dialog.add(ConfirmationDialog, {
            title: plan.active ? _t("Retire the %(name)s plan", { name: plan.name })
                               : _t("Bring the %(name)s plan back", { name: plan.name }),
            body: plan.active
                ? _t("It stops being offered to new customers. Nothing changes " +
                     "for anybody already on it, and you can bring it back.")
                : _t("It can be chosen for new customers again."),
            confirmLabel: plan.active ? _t("Retire it") : _t("Bring it back"),
            confirm: async () => {
                try {
                    await this.orm.call("pb.tenants", "plan_archive",
                                        [plan.id, !!plan.active]);
                    await this.loadBilling();
                } catch (e) {
                    this.notif.add(this.errText(e, _t("That did not work.")),
                                   { type: "danger" });
                }
            },
            cancel: () => {},
        });
    }

    // --------------------------------------------------------- the settings
    openBillSettings() {
        this.state.bill.settingsOpen = true;
        this.state.bill.settings = { ...(this.bill.settings || {}) };
    }

    closeBillSettings() {
        if (this.state.bill.busy === "settings") { return; }
        this.state.bill.settingsOpen = false;
    }

    get autoSuspendOn() {
        const raw = String((this.state.bill.settings || {}).auto_suspend || "0")
            .trim().toLowerCase();
        return !["", "0", "off", "false", "no", "none"].includes(raw);
    }

    toggleAutoSuspend() {
        const s = this.state.bill.settings;
        s.auto_suspend = this.autoSuspendOn ? "0" : "1";
    }

    async saveBillSettings() {
        const b = this.state.bill;
        b.busy = "settings";
        try {
            const r = await this.orm.call("pb.tenants", "billing_settings_save",
                                          [{ ...b.settings }]);
            b.settings = { ...r.settings };
            if (b.d) { b.d.settings = { ...r.settings }; b.d.auto_suspend = r.auto_suspend; }
            b.settingsOpen = false;
            this.notif.add(_t("Saved."), { type: "success" });
        } catch (e) {
            this.notif.add(this.errText(e, _t("That could not be saved.")),
                           { type: "danger" });
        } finally {
            b.busy = "";
        }
    }

    // ==================================================== one customer's plan
    _freshPlanTab() {
        return { d: null, busy: "", confirm: "", reason: "", days: 30,
                 email: "", trial: "" };
    }

    async loadPlanTab() {
        const p = this.state.plan;
        p.busy = "load";
        try {
            p.d = await this.orm.silent.call("pb.tenants", "tenant_billing",
                                             [this.state.det.id]);
            p.email = p.d.billing_email_set || "";
            p.trial = p.d.trial_ends || "";
        } catch (e) {
            this.notif.add(this.errText(e, _t("This customer's plan could not be read.")),
                           { type: "danger" });
        } finally {
            p.busy = "";
        }
    }

    async _planCall(method, args, busy, okMsg) {
        const p = this.state.plan;
        p.busy = busy;
        try {
            const r = await this.orm.call("pb.tenants", method, args);
            if (r && r.data) { p.d = r.data; }
            if (okMsg) { this.notif.add(okMsg, { type: "success" }); }
            p.confirm = "";
            p.reason = "";
            await this.openDetail(this.state.det.id);
            this.state.det.tab = "plan";
            this.loadFleet();
            return r;
        } catch (e) {
            this.notif.add(this.errText(e, _t("That did not work.")),
                           { type: "danger" });
            return null;
        } finally {
            p.busy = "";
        }
    }

    setTenantPlan(planId, trial = false) {
        this._planCall("tenant_set_plan",
                       [this.state.det.id, parseInt(planId, 10), trial],
                       "plan", _t("Plan set, and their database has been told."));
    }

    convertTrial() {
        this._planCall("tenant_convert", [this.state.det.id], "convert",
                       _t("They are a paying customer now."));
    }

    resumeTenant() {
        this._planCall("tenant_resume", [this.state.det.id], "resume",
                       _t("Their people can get back in."));
    }

    cancelDeletion() {
        this._planCall("tenant_cancel_deletion", [this.state.det.id], "undelete",
                       _t("Deletion called off."));
    }

    suspendTenant() {
        const p = this.state.plan;
        this._planCall("tenant_suspend",
                       [this.state.det.id, p.reason, p.confirm], "suspend",
                       _t("Their access is paused. Their data is untouched."));
    }

    scheduleDeletion() {
        const p = this.state.plan;
        this._planCall("tenant_schedule_deletion",
                       [this.state.det.id, parseInt(p.days, 10) || 30,
                        p.reason, p.confirm], "delete",
                       _t("A date is set, and a final backup was taken."));
    }

    askPlanAction(which) {
        const p = this.state.plan;
        p.confirm = "";
        p.reason = "";
        p.ask = which;
    }

    async savePlanTabDetails() {
        const p = this.state.plan;
        p.busy = "save";
        try {
            p.d = await this.orm.call("pb.tenants", "tenant_billing_save",
                                      [this.state.det.id,
                                       { billing_email: p.email,
                                         trial_ends: p.trial || false }]);
            this.notif.add(_t("Saved."), { type: "success" });
        } catch (e) {
            this.notif.add(this.errText(e, _t("That could not be saved.")),
                           { type: "danger" });
        } finally {
            p.busy = "";
        }
    }

    // ------------------------------------------------------------- detail
    async openDetail(id) {
        this.state.det = { id, tab: "overview", d: null, busy: "", confirm: "", newDomain: "", restoreMsg: null, syncOpen: false };
        this.state.upd = { d: null, busy: "", openTask: null };
        this.state.plan = this._freshPlanTab();
        this.state.view = "detail";
        this.state.det.d = await this.orm.silent.call("pb.tenants", "get_tenant", [id]);
    }

    // -------------------------------------------------------- Updates tab
    //
    // One customer's answer to three questions: which wave am I in, when is my
    // night, and what has actually been done to me. The last one is a timeline
    // rather than a log, because the reader is asking "when did this customer
    // last change", not "what did line 400 say".

    async openTab(tab) {
        this.state.det.tab = tab;
        if (tab === "updates" && !this.state.upd.d) { await this.loadUpdates(); }
        if (tab === "plan" && !this.state.plan.d) { await this.loadPlanTab(); }
    }

    async loadUpdates() {
        const u = this.state.upd;
        u.busy = "load";
        try {
            u.d = await this.orm.silent.call("pb.tenants", "tenant_updates",
                                             [this.state.det.id]);
        } catch (e) {
            this.notif.add(this.errText(e, _t("This customer's updates could not be read.")),
                           { type: "danger" });
        } finally {
            u.busy = "";
        }
    }

    async setWindow(vals) {
        const u = this.state.upd;
        u.busy = "save";
        try {
            u.d = await this.orm.call("pb.tenants", "tenant_set_window",
                                      [this.state.det.id, vals.ring ?? null,
                                       vals.start ?? null, vals.hours ?? null]);
            this.notif.add(_t("Saved — %(window)s.", { window: u.d.next_window }),
                           { type: "success" });
        } catch (e) {
            this.notif.add(this.errText(e, _t("That could not be saved.")), { type: "danger" });
            await this.loadUpdates();
        } finally {
            u.busy = "";
        }
    }

    setRing(ring) { this.setWindow({ ring }); }
    onWindowInput(which, ev) {
        const v = parseInt(ev.target.value, 10);
        if (isNaN(v)) { return; }
        this.setWindow(which === "start" ? { start: v } : { hours: v });
    }

    /** Update this one customer now, outside any rollout. Same unit, same guards. */
    updateNow() {
        const u = this.state.upd;
        this.dialog.add(ConfirmationDialog, {
            title: _t("Update %(name)s now", { name: u.d.name }),
            body: _t(
                "This runs the same update a rollout would run, on this customer alone, " +
                "right now rather than inside their window. Their users are not warned first. " +
                "For a release going to everybody, use the rollout — it practises on a copy " +
                "before it touches anybody."),
            confirmLabel: _t("Update them now"),
            confirm: async () => {
                u.busy = "run";
                try {
                    const r = await this.orm.call("pb.tenants", "tenant_update_now",
                                                  [this.state.det.id, false]);
                    this.notif.add(r.message || _t("Done."),
                                   { type: r.skipped_count > 0 ? "warning" : "success" });
                    await this.loadUpdates();
                    this.state.det.d = await this.orm.silent.call(
                        "pb.tenants", "get_tenant", [this.state.det.id]);
                } catch (e) {
                    this.notif.add(this.errText(e, _t("It did not finish.")), { type: "danger" });
                } finally {
                    u.busy = "";
                }
            },
            cancel: () => {},
        });
    }

    toggleTask(id) {
        this.state.upd.openTask = this.state.upd.openTask === id ? null : id;
    }

    /** Seconds as something a person says out loud. */
    secs(n) {
        n = n || 0;
        if (n < 90) { return _t("%(n)ss", { n }); }
        return _t("%(n)s min", { n: Math.round(n / 60) });
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
