/** @odoo-module **/
/**
 * The Mapping Studio — a front door where FROM and TO read as a sentence.
 *
 * The complaint this surface exists to answer, in the owner's words: "the user
 * gets confused on what he is mapping to what — source and destination". The
 * mapping canvas has been right for two cycles; what was wrong was everything
 * around it. It lived as a scrim INSIDE the Formula Studio, so its target was
 * whichever configuration the Studio happened to be loaded on and was named
 * nowhere; its source was a bare `<select>` of connector names; and its five
 * adapters were tabs called "Cycle carryover", "API fields", "Import columns".
 * Nothing on the screen said which way the arrow pointed.
 *
 * So this is a full-screen cockpit whose permanent header is one sentence:
 *
 *     FROM  <connector> · <feed>      ══ N mapped ══▶      TO  <scheme>
 *
 * Both ends are PICKERS. Changing the scheme you are mapping onto — the
 * question the owner asked out loud, "how do I change the payroll template in
 * this screenshot" — is one click on the right-hand side of that sentence.
 *
 * Three things it deliberately does NOT do:
 *
 *   * it does not fork `MappingCanvas`. The board, the bezier wires, the
 *     transform popover and its 260ms debounce are the same component the
 *     overlay mounts (W6, kit-first). Two additive, opt-in lines were added to
 *     it this cycle — a sample value and a group header, both rendered only for
 *     items that carry the key — so every existing adapter is unchanged;
 *   * it does not fork the five server adapters. The same `${prefix}_mapping_*`
 *     RPC contracts the overlay calls, with ONE additive argument
 *     (`api_mapping_data`/`api_mapping_create` accept an endpoint);
 *   * it does not offer python transforms. The whitelist lives on the server
 *     and `api_transform_save` refuses everything outside it (W12) — there is
 *     no client path to a code-authoring surface, and there must not be.
 */
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { MappingCanvas } from "./mapping_canvas";

const MODEL = "pb.formula.studio";

/**
 * The five adapters, in plain language.
 *
 * The tab labels they replace were the adapter names — "API fields", "Cycle
 * carryover" — which describe the CODE. These describe the sentence: what goes
 * in, what comes out. The `id` is unchanged, because it is the RPC prefix and
 * the overlay's `state.mapMode`; only the words a person reads are new.
 */
export const MODES = [
    { id: "api", icon: "plug", label: _t("System fields → Scheme"),
      hint: _t("Wire the fields an HR system's API delivers onto a scheme's inputs.") },
    { id: "import", icon: "table", label: _t("Spreadsheet columns → Scheme"),
      hint: _t("Wire the columns of an uploaded file onto a scheme's inputs.") },
    { id: "employee", icon: "users", label: _t("Employee & contract fields"),
      hint: _t("Copy what a scheme computes back onto employee and contract records.") },
    { id: "scheme", icon: "layers", label: _t("Scheme assignment"),
      hint: _t("Say which payroll scheme pays each part of the workforce.") },
    { id: "cycle", icon: "refresh", label: _t("Mid ↔ End cycle"),
      hint: _t("Carry a mid-cycle advance's components into the end-cycle run.") },
];

/** Which adapters take a transform on the wire, and which take templates. */
const TEMPLATABLE = ["api", "cycle"];

export class MappingStudio extends Component {
    static template = "pb_formula_studio.MappingStudio";
    static components = { MappingCanvas, HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        // Read ONCE, from props, never written back — the arrival protocol's
        // rule since the IA shell. Everything here is optional and everything
        // here is CHECKED on the server (`mapping_pickers` reports what it
        // could not honour rather than landing quietly on something else).
        this.back = hubBack(this.props);
        const ctx = (this.props.action && this.props.action.context) || {};
        this.arrival = {
            connector_id: Number(ctx.pb_connector) || 0,
            endpoint_id: Number(ctx.pb_endpoint) || 0,
            config_id: Number(ctx.pb_config) || 0,
        };
        const askedMode = MODES.some((m) => m.id === ctx.pb_mode) ? ctx.pb_mode : "";

        this.state = useState({
            loaded: false, busy: false,
            mode: askedMode || "api",
            connectors: [], configs: [], batches: [],
            connectorId: 0, endpointId: 0, configId: 0, batchId: 0,
            data: null,
            dismissed: [],
            // which rich dropdown is open, and its search box
            picker: "", pquery: "",
            // what the arrival context asked for and could not have
            fellBack: [],
            // template panel
            tmplOpen: false, tmplBusy: false, tmplList: [], tmplResult: null,
            // C5 — one-shot orders for the board. The TOKEN is the point: a
            // second click on "15 mapped" has to flash the wires a second time,
            // and a boolean cannot say "again".
            cmd: { token: 0, kind: "" },
        });

        // A click anywhere else closes an open dropdown. An event handler, not
        // a lifecycle hook — it only writes this component's own state.
        useExternalListener(window, "click", () => { this.state.picker = ""; });

        onWillStart(async () => {
            await this.loadPickers();
            await this.load();
            this.state.loaded = true;
        });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ================================================================ pickers
    async loadPickers() {
        let d;
        try {
            d = await this.orm.call(MODEL, "mapping_pickers", [this.arrival]);
        } catch (e) {
            console.warn("pb_formula_studio: mapping_pickers failed", e);
            this.notif.add(_t("The connectors and schemes could not be read."),
                           { type: "danger" });
            return;
        }
        const def = d.defaults || {};
        Object.assign(this.state, {
            connectors: d.connectors || [],
            configs: d.configs || [],
            batches: d.batches || [],
            connectorId: def.connector_id || 0,
            endpointId: def.endpoint_id || 0,
            configId: def.config_id || 0,
            fellBack: def.fell_back || [],
        });
        // A deep link that lands on a DIFFERENT scheme than it named is the
        // worst bug class in this codebase, so it is said out loud rather than
        // absorbed (W76.3/W117).
        if (this.state.fellBack.length) {
            this.notif.add(this.fellBackLabel, { type: "warning" });
        }
    }

    get fellBackLabel() {
        const what = this.state.fellBack;
        if (what.includes("config")) {
            return _t("The scheme this link named is not available to you — "
                      + "showing %s instead.", this.configName);
        }
        if (what.includes("connector")) {
            return _t("The connector this link named is not available to you — "
                      + "showing %s instead.", this.connectorName);
        }
        return _t("The feed this link named is no longer on this connector — "
                  + "showing all of them.");
    }

    // ---------------------------------------------------------- the sentence
    get connector() {
        return this.state.connectors.find((c) => c.id === this.state.connectorId) || null;
    }
    get connectorName() { return (this.connector && this.connector.name) || _t("No connector"); }

    get endpoints() { return (this.connector && this.connector.endpoints) || []; }

    get endpoint() {
        return this.endpoints.find((e) => e.id === this.state.endpointId) || null;
    }
    get endpointName() {
        return (this.endpoint && this.endpoint.name) || _t("All feeds");
    }

    get config() {
        return this.state.configs.find((c) => c.id === this.state.configId) || null;
    }
    get configName() { return (this.config && this.config.name) || _t("No scheme"); }

    get batch() {
        return this.state.batches.find((b) => b.id === this.state.batchId) || null;
    }

    /** The FROM column's provenance summary, or null on a non-API board. */
    get srcSummary() {
        const d = this.state.data;
        return (d && d.ok && d.source_summary) || null;
    }

    /**
     * What the FROM half of the header is entitled to say about its own list.
     *
     * Cycle 5 printed `206 fields · never synced`. Both halves were true and
     * the sentence was a lie: those 206 were `hr.employee`'s columns, and the
     * heading above them said ZOHO PEOPLE (ABM). The rule now is that the count
     * and its ORIGIN have to agree, so the origin comes from the server beside
     * the list it describes rather than being guessed at from a number here.
     *
     *   31 expected fields · Zoho People catalogue · not yet synced
     *   40 fields · synced 3d ago
     *   28 fields · 3 not sent last sync
     *   206 Odoo employee fields · this source has not told us its own
     */
    get fromSub() {
        const d = this.state.data;
        const n = (d && d.ok && d.left) ? d.left.length : 0;
        if (this.state.mode !== "api") { return _t("%s fields", n); }
        const s = this.srcSummary;
        if (!s) {
            // An older server, or a board built before C6. Say the count and
            // nothing about where it came from — an unqualified number is a
            // smaller claim than a wrong qualification.
            const ep = this.endpoint;
            const when = ep ? this.since(ep.last_sync) : "";
            return when ? _t("%(fields)s · %(when)s", { fields: _t("%s fields", n), when })
                        : _t("%s fields", n);
        }
        if (s.odoo && !s.live && !s.catalog) {
            return _t("%s Odoo employee fields · this source has not told us its own",
                      s.odoo);
        }
        if (!s.live && s.catalog) {
            return _t("%(n)s expected fields · %(vendor)s catalogue · not yet synced",
                      { n: s.catalog, vendor: s.vendor });
        }
        const ep = this.endpoint;
        const when = ep ? this.since(ep.last_sync) : "";
        const bits = [_t("%s fields", n)];
        if (when) { bits.push(when); }
        if (s.drift) { bits.push(_t("%s not sent last sync", s.drift)); }
        return bits.join(" · ");
    }

    /**
     * The first-run hint: this board has never seen a byte from this system.
     *
     * Shown only when there is something to map and nothing has arrived — the
     * exact moment a new connector is at its most mappable and looks its most
     * empty. It is a sentence, not a warning: nothing is wrong.
     */
    get firstRunHint() {
        if (this.state.mode !== "api") { return null; }
        const s = this.srcSummary;
        if (!s || s.ever_synced || !s.catalog || s.live) { return null; }
        return _t(
            "These are the fields %(vendor)s is expected to deliver. Map them now — the first sync will confirm them.",
            { vendor: s.vendor });
    }

    /** The honest half of the hint: can this connector even be asked? */
    get firstRunNote() {
        const s = this.srcSummary;
        return (s && !s.fetch_ready && s.fetch_reason) ? s.fetch_reason : "";
    }

    /** "250 input columns · VN · active". */
    get toSub() {
        const c = this.config;
        if (!c) { return ""; }
        const bits = [_t("%s input columns", c.input_count)];
        if (c.country) { bits.push(c.country); }
        if (c.state) { bits.push(c.state); }
        return bits.join(" · ");
    }

    /** "3 hours ago", from the ISO string. Never "NaN days" (W46). */
    since(iso) {
        if (!iso) { return _t("never synced"); }
        const t = new Date(iso.endsWith("Z") ? iso : iso.replace(" ", "T") + "Z").getTime();
        if (isNaN(t)) { return _t("never synced"); }
        const h = (Date.now() - t) / 3600000;
        if (h < 1) { return _t("synced <1h ago"); }
        if (h < 24) { return _t("synced %sh ago", Math.round(h)); }
        return _t("synced %sd ago", Math.round(h / 24));
    }

    /**
     * What the FROM half of the sentence is, this mode.
     *
     * `kind` is what the slot RENDERS: a picker the user can change, or a
     * fixed label the adapter decided. The grammar never changes — there is
     * always a FROM on the left and a TO on the right — which is the whole
     * point: five different boards, one sentence.
     */
    get fromSlot() {
        const d = this.state.data || {};
        switch (this.state.mode) {
            case "api":
                return { kind: "connector", title: this.connectorName,
                         sub: this.fromSub, icon: "plug" };
            case "import":
                return { kind: "batch",
                         title: (this.batch && this.batch.name) || d.left_title
                                || _t("No import batch"),
                         sub: this.fromSub, icon: "table" };
            case "employee":
                return { kind: "config", title: this.configName,
                         sub: this.toSub, icon: "calculator" };
            case "scheme":
                return { kind: "static", title: _t("Employee segments"),
                         sub: _t("Departments with employees"), icon: "users" };
            default:      // cycle
                return { kind: "static",
                         title: (d.mid && d.mid.name) || _t("Mid-cycle scheme"),
                         sub: _t("Mid-cycle configuration"), icon: "refresh" };
        }
    }

    get toSlot() {
        const d = this.state.data || {};
        switch (this.state.mode) {
            case "api":
            case "import":
                return { kind: "config", title: this.configName,
                         sub: this.toSub, icon: "calculator" };
            case "employee":
                return { kind: "static", title: _t("Employee & contract fields"),
                         sub: _t("Written back on each payslip"), icon: "users" };
            case "scheme":
                return { kind: "static", title: _t("Payroll schemes"),
                         sub: _t("The scheme that pays each segment"), icon: "layers" };
            default:      // cycle
                return { kind: "static",
                         title: (d.end && d.end.name) || _t("End-cycle scheme"),
                         sub: _t("End-cycle configuration"), icon: "layers" };
        }
    }

    /**
     * The scheme picker is ALWAYS reachable in one click.
     *
     * In three modes it IS one half of the sentence; in the other two the
     * sentence is about departments or about a cycle pair, and the scheme is
     * still what the board is anchored to. Rather than hide it there — which
     * is exactly the "where do I change the template" question the cycle
     * exists to kill — it becomes a chip beside the modes.
     */
    get schemeChipVisible() { return this.state.mode === "cycle"; }

    get mappedCount() { return this.wires.filter((w) => w.state === "accepted").length; }
    get suggestedCount() { return this.wires.filter((w) => w.state === "suggested").length; }

    /** "15 mapped" → flash every wire on the board for a second. */
    flashWires() {
        if (!this.mappedCount) { return; }
        this.state.cmd = { token: this.state.cmd.token + 1, kind: "pulse" };
    }
    /** "2 suggested" → filter both columns down to what the suggestions touch. */
    focusSuggested() {
        this.state.cmd = { token: this.state.cmd.token + 1, kind: "suggested" };
    }

    get modes() { return MODES; }
    get mode() { return MODES.find((m) => m.id === this.state.mode) || MODES[0]; }

    // ================================================================== board
    /** The adapter prefix; `null` means the bespoke cycle adapter. */
    get prefix() {
        return { api: "api", import: "import", scheme: "scheme",
                 employee: "employee" }[this.state.mode] || null;
    }

    get canEdit() { return !!(this.state.data && this.state.data.can_edit); }

    get leftItems() { return (this.state.data && this.state.data.left) || []; }
    get rightItems() { return (this.state.data && this.state.data.right) || []; }

    get wires() {
        const w = (this.state.data && this.state.data.wires) || [];
        const d = this.state.dismissed;
        return d.length ? w.filter((x) => !d.includes(x.id)) : w;
    }

    async load() {
        this.state.busy = true;
        this.state.dismissed = [];
        const cfg = this.state.configId || false;
        try {
            let r;
            switch (this.state.mode) {
                case "api":
                    r = await this.orm.call(MODEL, "api_mapping_data",
                                            [cfg, this.state.connectorId || false,
                                             this.state.endpointId || false]);
                    break;
                case "import":
                    r = await this.orm.call(MODEL, "import_mapping_data",
                                            [cfg, this.state.batchId || false]);
                    break;
                case "employee":
                    r = await this.orm.call(MODEL, "employee_mapping_data", [cfg, false]);
                    break;
                case "scheme":
                    r = await this.orm.call(MODEL, "scheme_mapping_data", [cfg, false]);
                    break;
                default:
                    r = await this.orm.call(MODEL, "mapping_canvas_data", [cfg]);
            }
            this.state.data = r;
            // the import adapter picks a batch for you when you did not
            if (this.state.mode === "import" && r && r.context_id) {
                this.state.batchId = r.context_id;
            }
            if (this.state.mode === "api" && r && r.context_id && !this.state.connectorId) {
                this.state.connectorId = r.context_id;
            }
        } catch (e) {
            console.warn("pb_formula_studio: mapping data failed", e);
            this.state.data = { ok: false, reason: "error" };
        } finally {
            this.state.busy = false;
        }
    }

    // =================================================================== acts
    async setMode(id) {
        if (this.state.mode === id) { return; }
        this.state.mode = id;
        this.state.data = null;
        this.state.tmplOpen = false;
        await this.load();
    }

    togglePicker(which, ev) {
        if (ev) { ev.stopPropagation(); }
        this.state.picker = this.state.picker === which ? "" : which;
        this.state.pquery = "";
    }
    closePicker() { this.state.picker = ""; this.state.pquery = ""; }
    onPickerQuery(ev) { this.state.pquery = ev.target.value || ""; }

    /** The options of the open dropdown, filtered by its search box. */
    get pickerOptions() {
        const q = (this.state.pquery || "").trim().toLowerCase();
        const hit = (s) => !q || (s || "").toLowerCase().includes(q);
        switch (this.state.picker) {
            case "connector":
                return this.state.connectors
                    .filter((c) => hit(c.name) || hit(c.type))
                    .map((c) => ({
                        id: c.id, label: c.name, on: c.id === this.state.connectorId,
                        sub: _t("%(feeds)s feeds · %(maps)s mappings · %(when)s", {
                            feeds: (c.endpoints || []).length, maps: c.mapping_count,
                            when: this.since(c.last_sync) }),
                        tone: c.status === "error" ? "err"
                            : (c.status === "connected" ? "ok" : "muted"),
                    }));
            case "endpoint":
                return [{ id: 0, label: _t("All feeds"), on: !this.state.endpointId,
                          sub: _t("Every field this connector has ever delivered"),
                          tone: "muted" }].concat(
                    this.endpoints.filter((e) => hit(e.name) || hit(e.code))
                        .map((e) => ({
                            id: e.id, label: e.name, on: e.id === this.state.endpointId,
                            sub: this.feedSub(e),
                            tone: e.status === "failed" ? "err"
                                : (e.status === "success" ? "ok" : "muted"),
                        })));
            case "config":
                return this.state.configs
                    .filter((c) => hit(c.name) || hit(c.code))
                    .map((c) => ({
                        id: c.id, label: c.name, on: c.id === this.state.configId,
                        sub: _t("%(cols)s columns · %(inputs)s inputs%(country)s", {
                            cols: c.column_count, inputs: c.input_count,
                            country: c.country ? " · " + c.country : "" }),
                        tone: c.state === "active" ? "ok" : "muted",
                    }));
            case "batch":
                return this.state.batches
                    .filter((b) => hit(b.name))
                    .map((b) => ({ id: b.id, label: b.name,
                                   on: b.id === this.state.batchId,
                                   sub: "", tone: "muted" }));
            default:
                return [];
        }
    }

    /**
     * A feed option's second line — WITHOUT repeating the line above it.
     *
     * A feed derived from the data store is named after its data type, so the
     * obvious "type · N mapped · when" printed "Dependents / Family" directly
     * under "Dependents / Family". The connector cockpit hit this in Cycle 1
     * and settled it there (`subLabel`): a label that repeats the line above
     * it is not a label, and the reader learns to stop reading both. Same rule,
     * because two surfaces that disagree about it is worse than either.
     * One msgid per shape, never a sentence assembled from fragments (W80).
     */
    feedSub(e) {
        const type = (e.data_type_label || e.data_type || "").trim();
        const same = type.toLowerCase() === (e.name || "").trim().toLowerCase();
        return same
            ? _t("%(maps)s mapped · %(when)s",
                 { maps: e.mapping_count, when: this.since(e.last_sync) })
            : _t("%(type)s · %(maps)s mapped · %(when)s",
                 { type, maps: e.mapping_count, when: this.since(e.last_sync) });
    }

    get pickerTitle() {
        return {
            connector: _t("Pick the system you are mapping FROM"),
            endpoint: _t("Pick the feed"),
            config: _t("Pick the payroll scheme you are mapping TO"),
            batch: _t("Pick the uploaded file"),
        }[this.state.picker] || "";
    }

    async pick(id) {
        const which = this.state.picker;
        this.state.picker = "";
        this.state.pquery = "";
        switch (which) {
            case "connector":
                if (this.state.connectorId === id) { return; }
                this.state.connectorId = id;
                this.state.endpointId = 0;    // a feed belongs to ONE connector
                break;
            case "endpoint":
                if (this.state.endpointId === id) { return; }
                this.state.endpointId = id;
                break;
            case "config":
                if (this.state.configId === id) { return; }
                this.state.configId = id;
                break;
            case "batch":
                if (this.state.batchId === id) { return; }
                this.state.batchId = id;
                break;
            default:
                return;
        }
        await this.load();
    }

    // ============================================================ wire intent
    async accept(wire) {
        const p = this.prefix;
        if (p) {
            await this.orm.call(MODEL, `${p}_mapping_create`,
                                this._createArgs(wire.source || wire.leftId, wire.rightId));
        } else {
            await this.orm.call(MODEL, "mapping_accept", [wire.ref]);
        }
        await this.load();
    }

    async reject(wire) {
        if (this.prefix) {
            // api/import suggestions are computed live, never persisted — the
            // only thing "reject" can mean is "not on my screen".
            this.state.dismissed = [...this.state.dismissed, wire.id];
            return;
        }
        await this.orm.call(MODEL, "mapping_reject", [wire.ref]);
        await this.load();
    }

    async remove(wire) {
        const p = this.prefix;
        await this.orm.call(MODEL, p ? `${p}_mapping_delete` : "mapping_delete",
                            [wire.ref]);
        await this.load();
    }

    /** The create signature differs per adapter; this is the one place it does. */
    _createArgs(leftId, rightId) {
        const cfg = this.state.configId || false;
        switch (this.state.mode) {
            case "api":
                return [cfg, this.state.connectorId, leftId, rightId,
                        this.state.endpointId || false];
            case "import":
                return [cfg, this.state.batchId || false, leftId, rightId];
            default:
                return [cfg, false, leftId, rightId];
        }
    }

    async draw(leftId, rightId) {
        const p = this.prefix;
        const r = p
            ? await this.orm.call(MODEL, `${p}_mapping_create`,
                                  this._createArgs(leftId, rightId))
            : await this.orm.call(MODEL, "mapping_create", [this.state.configId, leftId, rightId]);
        if (r && r.ok === false) {
            this.notif.add(r.msg || _t("Could not connect those two."), { type: "warning" });
            return;
        }
        await this.load();
    }

    /**
     * Which boards can be suggested at all.
     *
     * `api` and `import` compute name matches live on every read; `cycle` has
     * a wizard that persists proposals. `scheme` (departments → schemes) and
     * `employee` (components → employee fields) have no matching notion —
     * offering the button there would be a control whose only honest answer is
     * "nothing", and a button everybody learns to ignore is worse than no
     * button (W64).
     */
    get canSuggest() { return ["api", "import", "cycle"].includes(this.state.mode); }

    /**
     * "Suggest mappings".
     *
     * Two different engines behind one button, which is correct rather than
     * lazy: the cycle adapter PERSISTS proposals (a wizard writes suggestion
     * records), while api and import compute them live on every read. So for
     * cycle this generates; for the others it re-reads and says how many are
     * on the board. A button that did nothing visible on three of five modes
     * would be worse than no button.
     */
    async suggest() {
        this.state.busy = true;
        try {
            if (this.state.data && this.state.data.supports_suggest) {
                const r = await this.orm.call(MODEL, "mapping_suggest", [this.state.configId]);
                if (r && r.ok) { this.state.data = r; }
            } else {
                await this.load();
            }
            const n = this.suggestedCount;
            this.notif.add(n ? _t("%s suggestion(s) on the board — accept the ones that look right.", n)
                             : _t("No suggestions could be found for this pair."),
                           { type: n ? "success" : "warning" });
        } catch (e) {
            console.warn("pb_formula_studio: suggest failed", e);
            this.notif.add(_t("Suggestions could not be computed."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async acceptAll() {
        const sugs = this.wires.filter((w) => w.state === "suggested" && w.confidence >= 0.9);
        if (!sugs.length) { return; }
        this.state.busy = true;
        try {
            for (const w of sugs) {
                const p = this.prefix;
                if (p) {
                    await this.orm.call(MODEL, `${p}_mapping_create`,
                                        this._createArgs(w.source || w.leftId, w.rightId));
                } else {
                    await this.orm.call(MODEL, "mapping_accept", [w.ref]);
                }
            }
        } finally {
            this.state.busy = false;
        }
        await this.load();
        this.notif.add(_t("Accepted %s high-confidence mapping(s).", sugs.length),
                       { type: "success" });
    }

    // W62 — transforms on the wire. Preview never writes; save is manager-gated
    // AND field-whitelisted server-side (`python` is refused there, W12).
    async transformPreview(ref, draft) {
        try { return await this.orm.call(MODEL, "api_transform_preview", [ref, draft]); }
        catch (e) { return { ok: false, error: _t("Preview failed") }; }
    }
    async transformSave(ref, vals) {
        const r = await this.orm.call(MODEL, "api_transform_save", [ref, vals]);
        if (r && r.ok) { await this.load(); }
        else if (r && r.msg) { this.notif.add(r.msg, { type: "warning" }); }
        return r;
    }

    // =============================================================== templates
    get templatable() { return TEMPLATABLE.includes(this.state.mode); }

    async openTemplates() {
        this.state.tmplOpen = true;
        this.state.tmplResult = null;
        this.state.tmplBusy = true;
        try {
            const r = await this.orm.call(MODEL, "mapping_template_list", [this.state.mode]);
            this.state.tmplList = (r && r.templates) || [];
        } catch (e) {
            this.state.tmplList = [];
        } finally {
            this.state.tmplBusy = false;
        }
    }
    closeTemplates() { this.state.tmplOpen = false; this.state.tmplResult = null; }

    async applyTemplate(id) {
        this.state.tmplBusy = true;
        try {
            const r = await this.orm.call(MODEL, "mapping_template_apply",
                                          [id, this.state.configId,
                                           this.state.connectorId || false]);
            if (r && r.ok) {
                this.state.tmplResult = r;
                await this.load();
            } else {
                this.notif.add((r && r.msg) || _t("That template could not be applied."),
                               { type: "warning" });
            }
        } finally {
            this.state.tmplBusy = false;
        }
    }

    // ================================================================== empty
    /** The three-step strip only appears when there is nothing wired yet. */
    get firstRun() {
        return !!(this.state.data && this.state.data.ok && !this.mappedCount);
    }

    get emptyReason() {
        const d = this.state.data;
        if (!d || d.ok) { return ""; }
        return {
            no_config: _t("There is no payroll scheme on this database yet."),
            no_connector: _t("No HR system is connected yet — connect one in Integrations."),
            no_batch: _t("No file has been uploaded yet. Import one, then map its columns here."),
            no_pair: _t("This scheme has no mid-cycle/end-cycle twin to carry values into."),
        }[d.reason] || _t("There is nothing to map on this board.");
    }
}

registry.category("actions").add("pb_mapping_studio", MappingStudio);
