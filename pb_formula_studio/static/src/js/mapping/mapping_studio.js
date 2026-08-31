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
 *
 * ---------------------------------------------------------------------------
 * JOURNEY J1 — this is now the ONLY shell.
 *
 * Until J1 the same `MappingCanvas` was mounted by two hosts: this one, and a
 * scrim inside the Formula Studio called "Mapping canvas". They shared ~85% of
 * their surface and NEITHER was a superset — the overlay owned the whole
 * Employee/Contract toolkit (lane chips, the two field pickers, the payroll
 * reveal, the reconciliation dialog, template SAVE and DELETE), this one owned
 * the sentence header, the pickers, the suggestion story and the deep-link
 * protocol. A user who found one of them met half a product, and which half
 * depended on which door they came through.
 *
 * So the overlay's payload moved HERE and the overlay was retired. Two rules
 * governed the move and are worth keeping:
 *
 *   * the behaviours themselves were already in `MappingCanvas` — remove-right,
 *     the `⋮` verbs, the group filter. The overlay's advantage was that it
 *     PASSED those props. Most of J1 is therefore wiring, not logic;
 *   * anything the overlay implemented in its own markup (the reconciliation
 *     dialog, the template save panel) MOVED — it was not copied. `grep` finds
 *     one implementation of each, and it is in this file.
 */
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { MappingCanvas } from "./mapping_canvas";
import { TransformFlowBoard } from "./transform_flow_board";
import { JourneyBoard } from "./journey_board";
import { ComponentTreatmentBoard } from "@pb_formula_studio/js/component_treatment";
import { placeInLane } from "./mapping_geometry";
import { ROLE_LANE_ORDER, roleIcon, roleLabel } from "./mapping_roles";
// JOURNEY J4 — the Rule Composer is IMPORTED, never re-implemented. J4's brief
// was to give transformations an address, not a second editor: a board that
// could author a rule would be a fourth place the same object is described, and
// the three that already exist are the problem this phase was opened to fix.
// `pb_integrations` is now a hard dependency of this module (declared in the
// manifest) — an undeclared cross-module import is a dead import waiting for the
// first database that installs one module and not the other, and it takes the
// whole backend bundle with it (the manifest's own `pb_import_kit` note).
import { RuleComposer } from "@pb_integrations/js/rule_composer";

const MODEL = "pb.formula.studio";

/**
 * How long a cut wire can be put back — JOURNEY J6 D3.
 *
 * The toast IS the undo window, so this number is the whole policy. The house
 * default is 4000ms, which is enough time to READ "Wire removed" and not enough
 * to decide you did not mean it and move a mouse there; 10s is the pause a
 * person actually takes before "…wait, no". Deliberately not `sticky`: a safety
 * net that never expires is an undo system, and this is not one.
 */
const UNDO_MS = 10000;

/**
 * The five adapters, in plain language.
 *
 * The tab labels they replace were the adapter names — "API fields", "Cycle
 * carryover" — which describe the CODE. These describe the sentence: what goes
 * in, what comes out. The `id` is unchanged, because it is the RPC prefix and
 * the overlay's `state.mapMode`; only the words a person reads are new.
 */
export const MODES = [
    // JOURNEY J5 — FIRST, and the cold-start default. It is first because it is
    // the only tab that answers the question the other six are pieces of, and
    // it is the default because the two doors that arrive without naming a mode
    // (the Settings card and the global palette) are exactly the arrivals of
    // somebody who does not yet know which piece they want. Every deep link
    // that NAMES a `pb_mode` is unchanged — that is the regression this phase
    // is most at risk of and case 1 checks each documented door individually.
    { id: "journey", icon: "compass", label: _t("Journey"),
      hint: _t("The whole picture: which systems, feeds and files reach this "
               + "scheme, what each one changes on the way, and what the last "
               + "pay run actually used.") },
    { id: "api", icon: "plug", label: _t("System fields → Scheme"),
      hint: _t("Wire the fields an HR system's API delivers onto a scheme's inputs.") },
    // JOURNEY J4 — between the API tab and the Spreadsheet tab, because that is
    // where it belongs in the story: a transformation reads what the system
    // sent (the tab to its left) and feeds a component (the tab to its right).
    // MJ19: every string here is ONE literal or is joined with an explicit `+`.
    // A two-line string with no operator is idiomatic Python and a SyntaxError
    // in JavaScript, it survives `node --check` run through a pipe, and it takes
    // the whole backend bundle down with a blank page and no server error.
    { id: "transform", icon: "sigma", label: _t("Transformations"),
      hint: _t("See what each transformation rule reads, what it computes, "
               + "and which components take its answer.") },
    { id: "import", icon: "table", label: _t("Spreadsheet columns → Scheme"),
      hint: _t("Wire the columns of an uploaded file onto a scheme's inputs.") },
    // JOURNEY J3 S1 / J-D4 — the ⇆ is the point. These rows have ALWAYS run both
    // ways (import writes the record, the resolver reads it back when the file or
    // feed is empty) and the tab has always described only the first half.
    { id: "employee", icon: "users", label: _t("Employee & contract ⇆"),
      hint: _t("Copy what a scheme computes onto employee and contract records — "
               + "and read them back when a pay run finds nothing in the file or feed.") },
    { id: "scheme", icon: "layers", label: _t("Scheme assignment"),
      hint: _t("Say which payroll scheme pays each part of the workforce.") },
    { id: "cycle", icon: "refresh", label: _t("Mid ↔ End cycle"),
      hint: _t("Carry a mid-cycle advance's components into the end-cycle run.") },
    // VALUEKIND P5 — LAST, because it is where the sentence ends: every tab
    // above says where a value comes from, and this one says what the scheme
    // then does with it. It arrived here from inside the Source Atlas, which is
    // reached from a pay run — the wrong home for a setting that changes every
    // run, past and future. The Atlas now shows the same board read-only and
    // links here.
    { id: "treatment", icon: "settings", label: _t("Component treatment"),
      hint: _t("What the scheme does with each component: which group it shows "
               + "in, what net pay does with it, whether it is already inside "
               + "another total, and whether its value is money, hours or text.") },
];

/** Which adapters take a transform on the wire, and which take templates. */
const TEMPLATABLE = ["api", "cycle"];

export class MappingStudio extends Component {
    static template = "pb_formula_studio.MappingStudio";
    static components = { MappingCanvas, TransformFlowBoard, JourneyBoard,
                          ComponentTreatmentBoard,
                          RuleComposer, HubBackChip };
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
        // a deep link that NAMES a connector has chosen one
        const linkedConnector = !!this.arrival.connector_id;

        this.state = useState({
            loaded: false, busy: false,
            // J5 — cold start lands on the Journey. `askedMode` is still king:
            // a link that names a mode gets that mode, which is what keeps every
            // pre-existing door (the Integrations cockpit's `api`, the connector
            // cockpit's `api`, Formula Studio's `employee`) landing exactly where
            // it always did.
            mode: askedMode || "journey",
            connectors: [], configs: [], batches: [],
            connectorId: 0, endpointId: 0, configId: 0, batchId: 0,
            // JOURNEY J4 — was the connector CHOSEN, or merely defaulted to?
            // The five boards ask different questions of the same list and
            // their heuristics honestly disagree (abm: the API board's answer
            // is connector 1, where this scheme's wires point; every
            // transformation rule on the database is on connector 3). A choice
            // must survive a tab switch; a guess must not, or the reader lands
            // on an empty Transformations board over a database with eight
            // rules in it and concludes the feature is broken.
            connectorPicked: linkedConnector,
            // VALUEKIND P5 — reported by the treatment board once it has read.
            treatmentCount: 0,
            data: null,
            fetchOffer: null, fetchBusy: false,
            dismissed: [],
            // SOURCING S6 — columns named by hand on the spreadsheet board
            extraCols: [],
            // which rich dropdown is open, and its search box
            picker: "", pquery: "",
            // what the arrival context asked for and could not have
            fellBack: [],
            // ---- J1: the employee-board toolkit, ported off the retired overlay
            // Both filters live in the HOST, not in the canvas: the canvas is
            // payroll-agnostic and must not learn what a "payroll component" is.
            empPayroll: false,      // include the pay columns in the LEFT column
            empLane: null,          // a role lane LABEL, or null for every lane
            empQuery: "", empResults: [],       // "Add a field to map…"
            empExtras: [], empHidden: [],       // session-scoped right-column edits
            empMenu: null, empMenuFilter: "", empMenuAll: {},   // Employee ▾ / Contract ▾
            // ---- J2: the Excel on-ramp (the `import` board only)
            rampBusy: "",       // "read" | "template" | "handoff" while one runs
            rampOver: false,    // a file is being dragged over the dropzone
            // ---- J1: reconciliation (MAPFIX B3), moved here whole
            rcnOpen: false, rcnBusy: false, rcnRows: null,
            // template panel. `tmplMode` replaced the old `tmplOpen` boolean when
            // SAVE arrived from the overlay: the panel now has two faces.
            tmplMode: "", tmplBusy: false, tmplList: [], tmplResult: null,
            tmplName: "",
            // C5 — one-shot orders for the board. The TOKEN is the point: a
            // second click on "15 mapped" has to flash the wires a second time,
            // and a boolean cannot say "again". J1 adds `leftId`, which the
            // "Send to a field instead…" verb uses to arm a card.
            cmd: { token: 0, kind: "" },
            // ---- J3 S2: the source-conflict choice (owner decision J-D3).
            // `null` while there is no question to answer. Holds the SERVER's
            // sentences plus the draw it is about to make, so answering it is a
            // single call with one extra argument and cancelling is not a call
            // at all.
            conflict: null, conflictBusy: false,
            // ---- J4: the Rule Composer, opened IN PLACE.
            // `null` while it is closed; `{ruleId, connectorId}` while it is
            // open, with `ruleId: 0` meaning "a new rule". Exactly the shape the
            // Integrations cockpit uses, because it is the same component and a
            // second convention for opening it would be a second thing to keep
            // in step.
            composer: null,
            // ---- J5: the arrival's pre-filter, and the way back.
            //
            // `focus` is read ONCE off `pb_focus` here and thereafter written
            // only by a Journey door. It is the host's, not any board's: wiring
            // it through the arrival reader once was the handover's explicit
            // instruction, and the alternative — every tab learning to read a
            // context key — is six places to keep in step for one feature.
            focus: (ctx.pb_focus || "").toString(),
            // Set when a Journey node opened this tab, so the tab can offer the
            // way BACK to the picture. `HubBackChip` leaves the whole cockpit;
            // this is a move within it, and conflating the two would make the
            // Journey a place you can only leave.
            fromJourney: false,
        });

        // J3 S2 — when the conflict dialog appears, focus goes INTO it. Without
        // this the shell keeps focus, Escape reaches nothing and a keyboard user
        // is looking at a modal they cannot answer or dismiss (MJ10's family: an
        // affordance that is not a native dialog has to re-earn every native
        // dialog behaviour, one at a time).
        useAutofocus({ refName: "cflFocus" });

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
        // SC-4 — a deep link (or a remembered mode) that names a tab this
        // scheme's lane config hides lands on the Journey instead of on a
        // board whose tab does not exist.
        if (!this.modes.some((m) => m.id === this.state.mode)) {
            this.state.mode = (this.modes[0] || {}).id || "journey";
        }
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
     *   206 Payobook employee fields · this source has not told us its own
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
            return _t("%s Payobook employee fields · this source has not told us its own",
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
            case "journey":
                // The FROM half of the Journey is every source at once, which is
                // the one honest thing to put there — naming a single connector
                // over a picture of two would be W76.3's bug class, a header
                // that looks right and describes the wrong thing.
                return { kind: "static", title: _t("Every source"),
                         sub: _t("Systems, files and records"), icon: "gitMerge" };
            case "api":
                return { kind: "connector", title: this.connectorName,
                         sub: this.fromSub, icon: "plug" };
            case "transform":
                return { kind: "connector", title: this.connectorName,
                         sub: this.transformSub, icon: "plug" };
            case "import":
                // J2 — a file dropped on the ramp NAMES the FROM half. Before
                // it, this said "No import batch": a technical noun for a thing
                // the reader had not done and had no way to do from here.
                return { kind: "batch",
                         title: (this.batch && this.batch.name)
                                || (this.sample && this.sample.filename)
                                || d.left_title || _t("No file yet"),
                         sub: this.fromSub, icon: "table" };
            case "employee":
                return { kind: "config", title: this.configName,
                         sub: this.toSub, icon: "calculator" };
            case "scheme":
                return { kind: "static", title: _t("Employee segments"),
                         sub: _t("Departments with employees"), icon: "users" };
            case "treatment":
                return { kind: "static", title: _t("Every component"),
                         sub: _t("However its value reaches the scheme"),
                         icon: "layers" };
            default:      // cycle
                return { kind: "static",
                         title: (d.mid && d.mid.name) || _t("Mid-cycle scheme"),
                         sub: _t("Mid-cycle configuration"), icon: "refresh" };
        }
    }

    get toSlot() {
        const d = this.state.data || {};
        switch (this.state.mode) {
            // J5 — the scheme picker is HALF THE SENTENCE here, which is how
            // scope 1's "scheme picker as on other tabs" is met without adding a
            // seventh control: the Journey is a picture OF a scheme, so the
            // scheme belongs in the header, not in a chip beside the tabs.
            case "journey":
            case "api":
            case "transform":
            case "import":
            case "treatment":
                return { kind: "config", title: this.configName,
                         sub: this.toSub, icon: "calculator" };
            case "employee":
                // J3 S1 — "written back" was half the story; these rows are read
                // back too, which is the whole of J-D4.
                return { kind: "static", title: _t("Employee & contract fields"),
                         sub: _t("Written on import · read back on a pay run"),
                         icon: "users" };
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

    get modes() {
        // SC-4 — a lane the scheme switched off takes its tab with it. The
        // server refuses the writes either way; this removes the door.
        const cfg = (this.state.configs || []).find(
            (c) => c.id === this.state.configId);
        const lanes = cfg && cfg.lanes;
        if (!lanes) { return MODES; }
        return MODES.filter((m) => {
            if (m.id === "api" && !lanes.api) { return false; }
            if (m.id === "import" && !lanes.excel) { return false; }
            return true;
        });
    }
    get mode() {
        return this.modes.find((m) => m.id === this.state.mode)
            || this.modes[0] || MODES[0];
    }

    // ================================================================== board
    /** The adapter prefix; `null` means the bespoke cycle adapter. */
    get prefix() {
        // J4 — `transform` maps to `api` ON PURPOSE and this is the whole of the
        // phase's write path. A rule's output key is already a legal
        // `source_field`, so a rule → component edge IS an `api` wire; routing it
        // through the same prefix means `draw`, `remove` and the J3 conflict
        // probe all reach the existing adapters with no branch of their own, and
        // the dialog fires here because it fires for `api`, not because a second
        // implementation remembered to.
        return { api: "api", transform: "api", import: "import", scheme: "scheme",
                 employee: "employee" }[this.state.mode] || null;
    }

    get isTransform() { return this.state.mode === "transform"; }

    get isJourney() { return this.state.mode === "journey"; }

    get isTreatment() { return this.state.mode === "treatment"; }

    /** How many components the treatment board is showing. */
    get treatmentCount() { return this.state.treatmentCount || 0; }

    /** "42 wired" — the Journey's own middle-of-the-sentence count. */
    get journeyWired() {
        const d = this.state.data;
        return (d && d.ok && d.header && d.header.wired) || 0;
    }

    /** "8 rules · 1 output unread" — the health counts, in the FROM sub-line. */
    get transformSub() {
        const d = this.state.data;
        if (!d || !d.ok) {
            // an empty board still owes the header a sentence: a blank sub-line
            // under a connector name reads as "still loading"
            return d && d.reason === 'no_rules'
                ? _t("No transformation rules yet") : "";
        }
        const c = d.counts || {};
        // One msgid per SHAPE, never a sentence assembled from fragments, and
        // never "8 rule(s)" — the parenthesised plural is a translator's
        // problem pushed onto the reader (W80, and the rail beside this says
        // "8 rules" cleanly, so the two would not even have matched).
        const bits = [c.rules === 1 ? _t("1 rule") : _t("%s rules", c.rules || 0)];
        if (c.unread) {
            bits.push(c.unread === 1 ? _t("1 output unread")
                                     : _t("%s outputs unread", c.unread));
        }
        if (c.drift) {
            bits.push(c.drift === 1 ? _t("1 reads a field not seen")
                                    : _t("%s read a field not seen", c.drift));
        }
        if (c.severed) {
            bits.push(c.severed === 1 ? _t("1 lost its target")
                                      : _t("%s lost their target", c.severed));
        }
        return bits.join(" · ");
    }

    get canEdit() { return !!(this.state.data && this.state.data.can_edit); }

    /**
     * JOURNEY J3 S1 — read off the PAYLOAD, never off the mode id.
     *
     * `this.state.mode === "employee"` would have been one character shorter and
     * a lie waiting to happen: the fact that these rows are two-way lives in the
     * server, beside the resolver that reads them back. An adapter that stopped
     * being bidirectional would have to remember to edit a client conditional it
     * has no reason to know about.
     */
    get isBidirectional() {
        return !!(this.state.data && this.state.data.bidirectional);
    }

    get leftItems() {
        const server = (this.state.data && this.state.data.left) || [];
        // SOURCING S6 — columns typed in this session, kept in front of the
        // server's list until a wire makes them permanent. They are dropped on
        // every reload EXCEPT that a bound one comes back from the server in the
        // "Already used by this scheme" lane, which is what makes the affordance
        // honest: a card you never wired does not survive, and one you did does.
        const extra = this.state.extraCols
            .filter((c) => !server.some((x) => String(x.id) === "c:" + c))
            .map((c) => ({ id: "c:" + c, label: c, sublabel: "",
                           group: _t("Added here"), meta: {} }));
        return extra.length ? extra.concat(server) : server;
    }
    /**
     * The right column — plus, on the employee board, this session's edits.
     *
     * MAPFIX F2/MF40: an extra is spliced INTO ITS LANE, never appended after the
     * whole catalogue. The canvas emits a group header whenever `group` changes
     * between consecutive rows, so a pinned Identity field tacked on below "Other
     * contract fields" grows a second "Identity" heading at the bottom of the
     * board and the lane headers stop telling the truth for as long as the
     * session lasts. `placeInLane` (the pure kernel in `mapping_geometry.js`) is
     * the client twin of the server's `_ec_place_in_lane` — one rule, expressed
     * once per side of the wire.
     *
     * MF40 also says this path is LATENT on a full catalogue: since Phase E the
     * server sends all 236 cards and both pickers are strict subsets of them, so
     * every field a user can pin is already on the board and nothing is ever
     * appended. It becomes live the moment anything narrows the served catalogue.
     * Keep it correct anyway — the pickers are the reason it exists.
     */
    get rightItems() {
        const base = (this.state.data && this.state.data.right) || [];
        if (this.state.mode !== "employee") { return base; }
        const hidden = new Set(this.state.empHidden);
        const seen = new Set(base.map((i) => i.id));
        const out = base.filter((i) => !hidden.has(i.id));
        for (const extra of this.state.empExtras) {
            if (seen.has(extra.id) || hidden.has(extra.id)) { continue; }
            placeInLane(out, extra);
        }
        return out;
    }

    /** Only the spreadsheet board takes a column as typed. */
    get canAddLeft() {
        return !!(this.state.data && this.state.data.ok && this.state.data.can_add
                  && this.canEdit);
    }
    get addLeftLabel() {
        return (this.state.data && this.state.data.add_label)
            || _t("Use “%s” as a spreadsheet column");
    }
    addLeftColumn(text) {
        const t = (text || "").trim();
        if (!t || this.state.extraCols.includes(t)) { return; }
        this.state.extraCols = [...this.state.extraCols, t];
    }

    /**
     * A sealed card answers on the board, not only on the server.
     *
     * S5 put the refusal in `clickRight` and in both create RPCs, and then
     * neither host passed `onRightBlocked` — so clicking a calculated component
     * cleared the armed card and said nothing at all, which reads as the board
     * being broken rather than as the component being produced.
     */
    rightBlocked(item) {
        const hint = (item && item.meta && item.meta.badgeHint)
            || _t("This component is produced by the scheme, not imported into it.");
        this.notif.add(hint, { type: "info" });
    }

    /** "Open rule" from the lineage popover — into the rule composer. */
    openRule(ruleId) {
        if (!ruleId) { return; }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.api.transformation.rule",
            res_id: ruleId,
            views: [[false, "form"]],
            target: "current",
        });
    }

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
                case "journey":
                    // ONE read for five lanes. It composes the helpers the other
                    // tabs already call; it defines nothing and it writes nothing.
                    r = await this.orm.call(MODEL, "journey_data", [cfg]);
                    break;
                case "api":
                    r = await this.orm.call(MODEL, "api_mapping_data",
                                            [cfg, this.state.connectorId || false,
                                             this.state.endpointId || false]);
                    break;
                case "transform":
                    // an UNCHOSEN connector is re-derived by the adapter, which
                    // knows which systems actually carry rules
                    r = await this.orm.call(MODEL, "transform_flow_data",
                                            [cfg, this.state.connectorPicked
                                                  ? (this.state.connectorId || false)
                                                  : false]);
                    break;
                case "import":
                    r = await this.orm.call(MODEL, "import_mapping_data",
                                            [cfg, this.state.batchId || false]);
                    break;
                case "employee":
                    // J1 — the third argument is `include_payroll`. The Studio
                    // used to hard-code `false`, so the payroll lane was
                    // unreachable here and the reveal chip had nothing to reveal.
                    r = await this.orm.call(MODEL, "employee_mapping_data",
                                            [cfg, false, !!this.state.empPayroll]);
                    break;
                case "scheme":
                    r = await this.orm.call(MODEL, "scheme_mapping_data", [cfg, false]);
                    break;
                case "treatment":
                    // The board owns its own read (`value_kind_board`), because
                    // it is the same component the Source Atlas renders and it
                    // cannot depend on this shell's payload to exist. Nothing
                    // here to fetch — but the shell still needs an `ok` payload
                    // or it renders its "could not load" state over a board that
                    // loaded perfectly well.
                    r = { ok: true };
                    break;
                default:
                    r = await this.orm.call(MODEL, "mapping_canvas_data", [cfg]);
            }
            this.state.data = r;
            // the import adapter picks a batch for you when you did not
            if (this.state.mode === "import" && r && r.context_id) {
                this.state.batchId = r.context_id;
            }
            if (this.state.mode === "api" && r && r.context_id
                && !this.state.connectorId) {
                this.state.connectorId = r.context_id;
            }
            // J4 — ALWAYS, on this board. The adapter may have re-derived the
            // connector (see `connectorPicked`), and a header that names one
            // system while the lanes show another is this codebase's worst bug
            // class (W76.3/W117): it looks right and it is describing the wrong
            // thing. Adopting it also means the picker opens on the truth.
            if (this.state.mode === "transform" && r && r.context_id
                && r.context_id !== this.state.connectorId) {
                this.state.connectorId = r.context_id;
                this.state.endpointId = 0;
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
        this.state.extraCols = [];
        this.state.tmplMode = "";
        // A tab chosen from the strip is not an arrival from the Journey, so it
        // carries neither the pre-filter nor the way back. Leaving them set
        // would leave a "Journey" chip on a tab nobody reached from there and a
        // search box narrowed by a word the user never typed.
        this.state.focus = "";
        this.state.fromJourney = false;
        this._resetEmpToolkit();
        await this.load();
    }

    // ======================= J5 — the doors, and the way back ================
    /**
     * A Journey node was clicked. Land on its tab, already scoped.
     *
     * This is the whole of scope 4 and it is deliberately ONE method: the
     * alternative — a handler per node kind — is six places that have to agree
     * about what "pre-scoped" means, which is the duplication this programme
     * has spent five phases removing. A door is `{mode, connector, endpoint,
     * focus}` and every field is optional.
     *
     * Nothing here writes. It changes which tab is on screen and what that tab
     * is pointed at; the RPC it ends in is the destination tab's own read.
     */
    async openDoor(door) {
        if (!door || !MODES.some((m) => m.id === door.mode)) { return; }
        if (door.connector) {
            this.state.connectorId = Number(door.connector) || 0;
            // MJ22 — a door that NAMES a connector has chosen one, and a choice
            // must survive the tab it lands on re-deriving its own default.
            this.state.connectorPicked = true;
            this.state.endpointId = 0;
        }
        if (door.endpoint) { this.state.endpointId = Number(door.endpoint) || 0; }
        this.state.mode = door.mode;
        this.state.data = null;
        this.state.extraCols = [];
        this.state.tmplMode = "";
        this.state.focus = (door.focus || "").toString();
        this.state.fromJourney = true;
        this._resetEmpToolkit();
        // BEFORE the load, not after: `state.data = null` unmounts the board,
        // and a board that is about to be created reads the order at mount
        // (see `MappingCanvas.setup`). Bumping the token afterwards would race
        // the render and lose the filter about half the time — the flakiest
        // possible shape for a feature whose whole promise is "one click".
        this._applyFocus();
        await this.load();
    }

    /** "← Journey" — a move WITHIN the cockpit, never `HubBackChip`'s exit. */
    async backToJourney() {
        this.state.fromJourney = false;
        this.state.focus = "";
        await this.setMode("journey");
    }

    /**
     * Hand the pre-filter to whichever board is now on screen.
     *
     * The canvas takes it through `command` — the one-shot order channel that
     * already exists for exactly this, already carries three kinds and is
     * already guarded by a token, so a fourth costs no new prop and cannot fire
     * on a board that does not send it. The transformation board takes it as an
     * optional prop because it has no command channel.
     *
     * A board with neither simply ignores it, which is the right failure: an
     * unhonoured pre-filter is a tab that opened one click further from the
     * answer, not a tab that opened on the wrong thing.
     */
    _applyFocus() {
        const text = (this.state.focus || "").trim();
        if (this.isJourney || this.isTransform) { return; }
        // ALWAYS write the command, even with nothing to focus — and this is the
        // whole of a defect the live pass caught.
        //
        // `command` is replayed at mount (that is what makes a door land
        // pre-filtered at all). So a door with NO focus, returning early, left
        // the PREVIOUS door's order sitting in the prop: opening "Payobook
        // records" after opening a feed called Employees mounted the people
        // board filtered to "Employees", which looks exactly like a board that
        // has lost most of its cards. An empty order is still an order — it
        // says "filter by nothing" — and issuing it is what makes each door
        // independent of the one before it.
        this.state.cmd = { token: this.state.cmd.token + 1,
                           kind: "search", text };
    }

    /**
     * Everything the employee board remembers is per-BOARD, not per-session.
     *
     * A pinned field, a lane filter and the payroll reveal all describe one
     * scheme's people mapping; carrying them onto the API board would filter a
     * column list by a lane that board does not have. Called on every mode
     * switch and on every scheme change.
     */
    _resetEmpToolkit() {
        Object.assign(this.state, {
            empQuery: "", empResults: [], empExtras: [], empHidden: [],
            empMenu: null, empMenuFilter: "", empMenuAll: {},
            empPayroll: false, empLane: null,
        });
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
                this.state.connectorPicked = true;
                this.state.endpointId = 0;    // a feed belongs to ONE connector
                break;
            case "endpoint":
                if (this.state.endpointId === id) { return; }
                this.state.endpointId = id;
                break;
            case "config":
                if (this.state.configId === id) { return; }
                this.state.configId = id;
                // a lane filter and a pinned field belong to the scheme they
                // were chosen on — see `_resetEmpToolkit`
                this._resetEmpToolkit();
                break;
            case "batch":
                if (this.state.batchId === id) { return; }
                this.state.batchId = id;
                this.state.extraCols = [];
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
        // JOURNEY J6 D3 — the API board and the Transformations board cut the
        // SAME model (`prefix` maps both to `api`), so they get the same undo,
        // from the same method. The Excel and Employee boards cut different
        // models and are out of this round's scope; they keep today's path
        // rather than being handed a half-built safety net.
        if (p === "api") {
            return this._removeWireUndoable("api_mapping_cut", "api_mapping_restore",
                                            [wire.ref]);
        }
        // ------------------------------------------------------------------
        // JOURNEY J8 — a CONTRACT COMPONENT wire has no mapping row behind it.
        //
        // The boolean on the rule is the fact, so "remove" here means DETACH,
        // and the id in `wire.ref` is deliberately false: handing a rule id to
        // `employee_mapping_delete` would browse `hr.payslip.import.mapping` and
        // unlink whatever row happened to carry that number. The `kind` is what
        // decides, never the shape of the id.
        //
        // The detach can be REFUSED — contracts may already carry values under
        // this code — and the refusal names the door that is open. It is shown,
        // not swallowed, and there is no force path.
        // ------------------------------------------------------------------
        if (wire.kind === "component") {
            return this._removeWireUndoable("employee_mapping_detach_component",
                                            "employee_component_restore",
                                            [wire.componentId]);
        }
        await this.orm.call(MODEL, p ? `${p}_mapping_delete` : "mapping_delete",
                            [wire.ref]);
        await this.load();
    }

    /**
     * Cut a wire, and give the reader one chance to put it back.
     *
     * JOURNEY J6 D3, and the reason it exists is D0: the owner double-clicked a
     * live wire, the board deleted `OTHRS300` → "OT 3 Hours", and there was no
     * way back from the screen it happened on. D3 removes the accident (a
     * double-click is not destructive any more, and the Remove verb is off the
     * wire's click path); this is the second line of defence, for the delete
     * that was deliberate and wrong.
     *
     * **The undo window IS the toast.** No queue, no history stack, no
     * "restore last deleted" hiding in a menu — those are an undo SYSTEM, which
     * would need to answer what happens when the row is re-drawn, re-cut and
     * re-drawn while three tabs are open. This is a safety net: it catches the
     * mistake you have just made, while you are still looking at it, and then it
     * is gone. `api_mapping_restore` is idempotent, so a double-pressed Undo puts
     * back one wire.
     *
     * ONE implementation, deliberately: two copies would drift, and the copy
     * that drifted would be the one on the board nobody was testing that week.
     *
     * JOURNEY J8 — and that is why the two adapters are ARGUMENTS rather than a
     * second copy. A contract component is cut by clearing two booleans on a
     * rule, not by unlinking a row, and its restore has to put the column ROLE
     * back as well; the shape ("cut returns a snapshot, undo replays it into an
     * inverse RPC, the toast IS the window") is identical, so the shape is what
     * is shared. A refusal from the cut — the detach the contracts block — is
     * shown here and stops the toast, because there is nothing to undo.
     */
    async _removeWireUndoable(cutMethod, restoreMethod, args) {
        if (!args || args[0] === undefined || args[0] === null
            || args[0] === false) { return; }
        const res = await this.orm.call(MODEL, cutMethod, args);
        if (res && res.ok === false) {
            this.notif.add(res.msg || _t("That wire could not be removed."),
                           { type: "warning" });
            return;
        }
        await this.load();
        if (!res || !res.ok || !res.snapshot) { return; }
        const snapshot = res.snapshot;
        this.notif.add(_t("Wire removed"), {
            type: "warning",
            autocloseDelay: UNDO_MS,
            buttons: [{
                name: _t("Undo"),
                primary: true,
                onClick: async () => {
                    await this.orm.call(MODEL, restoreMethod, [snapshot]);
                    await this.load();
                },
            }],
        });
    }

    /** The create signature differs per adapter; this is the one place it does. */
    _createArgs(leftId, rightId) {
        const cfg = this.state.configId || false;
        switch (this.state.mode) {
            case "api":
                return [cfg, this.state.connectorId, leftId, rightId,
                        this.state.endpointId || false];
            case "transform":
                // no endpoint: a transformation rule belongs to the CONNECTOR,
                // not to one of its feeds, and passing whichever feed the API
                // tab was last left on would stamp a wire with a provenance
                // nothing on this board ever chose.
                return [cfg, this.state.connectorId, leftId, rightId, false];
            case "import":
                return [cfg, this.state.batchId || false, leftId, rightId];
            default:
                return [cfg, false, leftId, rightId];
        }
    }

    /**
     * JOURNEY J3 S2 / owner decision J-D3 — ask BEFORE writing, never after.
     *
     * The either-API-or-Excel rule used to be settled by whichever row the
     * resolver happened to read first, in silence. Now: probe (a read-only RPC),
     * and if a second live source would exist, put the three-way choice on
     * screen. **Cancel makes no writing call whatsoever** — the draw simply never
     * happens — which is why the probe is a separate adapter rather than a flag
     * on the create. A same-source redraw probes clean and keeps the old silent
     * swap plus its toast, so nothing that was one gesture became two.
     */
    async draw(leftId, rightId) {
        const p = this.prefix;
        if (p === "api" || p === "import") {
            let probe = null;
            try {
                probe = await this.orm.call(MODEL, "source_conflict_probe",
                                            [this.state.configId, p, rightId, leftId,
                                             this.state.connectorId || false]);
            } catch (e) {
                // A probe that cannot run must not block a draw that would have
                // worked before this phase existed. It degrades to today's
                // behaviour, which is the swap toast.
                console.warn("pb_formula_studio: conflict probe failed", e);
            }
            if (probe && probe.conflict) {
                this.state.conflict = { ...probe.conflict, leftId, rightId };
                return;
            }
        }
        await this._commitDraw(leftId, rightId, null);
    }

    /**
     * Go and fetch real data, so the FROM column shows what the system
     * actually sends instead of what its documentation claims.
     */
    async runFetchFields() {
        const offer = this.state.fetchOffer;
        if (!offer || this.state.fetchBusy) { return; }
        this.state.fetchBusy = true;
        try {
            const r = await this.orm.call(MODEL, "fetch_live_fields",
                                          [offer.connectorId]);
            this.notif.add((r && r.msg) || _t("Fetched."),
                           { type: r && r.ok ? "success" : "warning" });
            this.state.fetchOffer = null;
            await this.load();
        } catch (e) {
            console.warn("pb_formula_studio: fetch_live_fields failed", e);
            this.notif.add(_t("Could not fetch from that system."),
                           { type: "danger" });
        } finally {
            this.state.fetchBusy = false;
        }
    }

    dismissFetchOffer() {
        if (!this.state.fetchBusy) { this.state.fetchOffer = null; }
    }

    /** Answer the dialog. `resolve` is "replace" | "keep"; cancel never gets here. */
    async resolveConflict(resolve) {
        const c = this.state.conflict;
        if (!c || this.state.conflictBusy) { return; }
        this.state.conflictBusy = true;
        try {
            await this._commitDraw(c.leftId, c.rightId, resolve);
        } finally {
            this.state.conflictBusy = false;
            this.state.conflict = null;
        }
    }

    /**
     * Cancel. Deliberately not an RPC and deliberately not a state rollback:
     * there is nothing to undo, because nothing was sent.
     */
    cancelConflict() {
        if (this.state.conflictBusy) { return; }
        this.state.conflict = null;
    }

    async _commitDraw(leftId, rightId, resolve) {
        const p = this.prefix;
        // ------------------------------------------------------------------
        // JOURNEY J8 — the card must not vanish under the hand that wired it.
        //
        // `employee_mapping_make_component('amount')` sets `column_role =
        // 'payroll'` (CR-A2), and the employee board hides payroll-role cards
        // until the payroll chip is on. Wire a column to the amount card with
        // that chip off and the card disappears the instant the wire succeeds —
        // which reads as "the board ate my column", not as "this now feeds the
        // calculation". MF15 already reveals the lane for the MENU verb; a wire
        // is the same act by a different gesture and gets the same reveal, from
        // the same state flag rather than from a second mechanism.
        // ------------------------------------------------------------------
        const revealPayroll = p === "employee" && rightId === "c:amount"
                              && !this.state.empPayroll;
        if (revealPayroll) { this.state.empPayroll = true; }
        const args = this._createArgs(leftId, rightId);
        if (resolve && (p === "api" || p === "import")) {
            // `api` takes (cfg, connector, src, rule, endpoint); `import` takes
            // (cfg, batch, col, rule). `resolve` is the trailing optional in both.
            args.push(resolve);
        }
        const r = p
            ? await this.orm.call(MODEL, `${p}_mapping_create`, args)
            : await this.orm.call(MODEL, "mapping_create", [this.state.configId, leftId, rightId]);
        // Nothing has ever been fetched from this system, so there is no way
        // to know which fields it really sends. Offer to go and find out
        // rather than refusing and leaving the reader stuck.
        if (r && r.ok === false && r.needs_fetch) {
            this.state.fetchOffer = { connectorId: r.connector_id, msg: r.msg };
            return;
        }
        if (r && r.ok === false) {
            // the reveal was speculative; a refusal must not leave the board in
            // a state the user did not ask for
            if (revealPayroll) { this.state.empPayroll = false; }
            this.notif.add(r.msg || _t("Could not connect those two."), { type: "warning" });
            return;
        }
        if (r && r.ok && r.msg && p === "employee"
            && String(rightId || "").startsWith("c:")) {
            this.notif.add(
                revealPayroll
                    ? r.msg + " " + _t("Pay columns are shown so you can see it.")
                    : r.msg,
                { type: "success" });
        }
        // SOURCING S6 — switching a component from one source to the other is one
        // deliberate act, and an act that changes what a component reads has to say
        // so. Silence here would make the two boards look independent when they are
        // two doors onto one decision.
        if (r && r.replaced && r.replaced.msg) {
            this.notif.add(r.replaced.msg, { type: "info" });
        }
        await this.load();
    }

    /**
     * COLROLES P3 — a card the adapter sealed answers here too.
     *
     * MAPFIX B2 emptied this of its original occupant: the employee board no longer
     * seals its contract components, because colour coding is a suggestion and a
     * person is allowed to re-route one. The handler stays because sealing is a
     * generic capability of the canvas — any adapter may still use it, and a click
     * that is a silent no-op on the full-screen studio while the overlay explains
     * itself is the same board telling two different stories.
     */
    leftBlocked(item) {
        const hint = (item && item.meta && item.meta.badgeHint)
            || _t("This column already has a destination.");
        this.notif.add(hint, { type: "info" });
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
                // CR3, second copy. `mapping_suggest` is the CYCLE adapter's method,
                // and this branch used to call it for whichever mode happened to
                // report `supports_suggest`. Cycle was the only one that did, so the
                // bug was dormant — until the employee board started saying yes too.
                const p = this.prefix;
                const r = p
                    ? await this.orm.call(MODEL, `${p}_mapping_suggest`, [this.state.configId])
                    : await this.orm.call(MODEL, "mapping_suggest", [this.state.configId]);
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

    // ============================ J1 — the employee & contract toolkit =========
    //
    // Everything between here and the template panel arrived from the retired
    // overlay. The BEHAVIOURS all live in `MappingCanvas` already; what the
    // overlay had and this host did not was the toolbar around them and the
    // props that switch them on. Read the section as "what the employee board
    // needs that the other four do not".

    get isEmp() { return this.state.mode === "employee"; }

    /**
     * The lane chips: one per role this structure actually has.
     *
     * Sorted into the same lane order the LEFT column uses, so the row reads as a
     * table of contents for what is underneath it rather than as an unordered set
     * of badges. A role with no columns gets no chip — an empty "Bank 0" teaches
     * the reader to stop reading the row.
     */
    get empChips() {
        const counts = (this.state.data && this.state.data.counts) || {};
        return ROLE_LANE_ORDER
            .filter((role) => counts[role] && counts[role].total)
            .map((role) => ({
                role,
                label: counts[role].label || roleLabel(role),
                icon: roleIcon(role),
                total: counts[role].total,
                unmapped: counts[role].unmapped || 0,
            }));
    }

    /** The lane filter is by GROUP LABEL, because that is what the canvas groups on. */
    toggleEmpLane(chip) {
        if (chip.role === "payroll" && !this.state.empPayroll) {
            // Asking to see the payroll lane is asking for the columns in it; a
            // chip that filtered to a lane the server has not sent would empty
            // the board.
            this.toggleEmpPayroll();
            return;
        }
        this.state.empLane = this.state.empLane === chip.label ? null : chip.label;
    }

    async toggleEmpPayroll() {
        this.state.empPayroll = !this.state.empPayroll;
        if (!this.state.empPayroll && this.state.empLane === roleLabel("payroll")) {
            this.state.empLane = null;
        }
        await this.load();
    }

    clearEmpLane() { this.state.empLane = null; }

    get empLaneFilter() { return this.isEmp ? (this.state.empLane || "") : ""; }

    // ---- "Add a field to map…" ------------------------------------------------
    // The right column is the whole catalogue, which is 236 cards on abm; this is
    // how you reach one by name instead of by scrolling. A field pinned here is
    // session-scoped until a wire makes it permanent — the server then returns it
    // in `right` on the next load, which is what makes the affordance honest.
    onEmpSearch(ev) {
        const q = ev.target.value || "";
        this.state.empQuery = q;
        clearTimeout(this._empTimer);
        if (q.trim().length < 2) { this.state.empResults = []; return; }
        this._empTimer = setTimeout(async () => {
            try {
                const r = await this.orm.call(MODEL, "ec_search_fields",
                                              [q, this.state.configId || false]);
                this.state.empResults = (r && r.fields) || [];
            } catch (e) {
                this.state.empResults = [];
            }
        }, 220);
    }

    addEmpField(item) {
        const base = (this.state.data && this.state.data.right) || [];
        if (!this.state.empExtras.some((x) => x.id === item.id)
            && !base.some((x) => x.id === item.id)) {
            this.state.empExtras = [...this.state.empExtras, item];
        }
        // if it had been session-hidden, un-hide it so the add takes effect
        this.state.empHidden = this.state.empHidden.filter((x) => x !== item.id);
        this.state.empQuery = "";
        this.state.empResults = [];
    }

    /**
     * Remove an UNWIRED field from the right column — session-scoped.
     *
     * A pinned extra is dropped; a catalogue field is hidden until the board
     * reloads. Nothing is written: a MAPPED field never reaches here, because the
     * canvas gates its ✕ on the card having no wire.
     */
    removeRightField(id) {
        if (this.state.empExtras.some((x) => x.id === id)) {
            this.state.empExtras = this.state.empExtras.filter((x) => x.id !== id);
        } else if (!this.state.empHidden.includes(id)) {
            this.state.empHidden = [...this.state.empHidden, id];
        }
    }

    // ---- Employee ▾ / Contract ▾ ----------------------------------------------
    // The other way in: browse one model's whole catalogue rather than search it.
    // Lazy-loaded once per model, then filtered in the client.
    async toggleEmpMenu(model) {
        if (this.state.empMenu === model) { this.closeEmpMenu(); return; }
        this.state.empMenu = model;
        this.state.empMenuFilter = "";
        if (!this.state.empMenuAll[model]) {
            let fields = [];
            try {
                const r = await this.orm.call(MODEL, "ec_model_fields", [model]);
                fields = (r && r.fields) || [];
            } catch (e) {
                fields = [];
            }
            this.state.empMenuAll = { ...this.state.empMenuAll, [model]: fields };
        }
    }
    closeEmpMenu() { this.state.empMenu = null; this.state.empMenuFilter = ""; }
    onEmpMenuFilter(ev) { this.state.empMenuFilter = ev.target.value || ""; }

    get empMenuFields() {
        const model = this.state.empMenu;
        if (!model) { return []; }
        const all = this.state.empMenuAll[model] || [];
        const q = (this.state.empMenuFilter || "").trim().toLowerCase();
        if (!q) { return all; }
        return all.filter((f) =>
            (f.label || "").toLowerCase().includes(q)
            || ((f.meta && f.meta.field) || "").toLowerCase().includes(q));
    }
    get empMenuLabel() {
        return this.state.empMenu === "hr.contract" ? _t("Contract") : _t("Employee");
    }

    isFieldAdded(id) { return this.rightItems.some((i) => i.id === id); }
    isFieldMapped(id) {
        return this.wires.some((w) => w.rightId === id && w.state === "accepted");
    }
    /** Row click in a browse dropdown: toggle add/remove for unmapped fields. */
    pickEmpMenuField(f) {
        if (this.isFieldMapped(f.id)) { return; }      // locked — unwire first
        if (this.isFieldAdded(f.id)) { this.removeRightField(f.id); }
        else { this.addEmpField(f); }
    }

    // ---- the card verbs (MAPFIX B2) -------------------------------------------
    /**
     * A verb pressed on a left card.
     *
     * Four verbs, three of which are a write and one of which is not: "Send to a
     * field instead…" ARMS the card and hands the board back to the user, because
     * choosing the destination is the whole decision and doing it for them would
     * make the verb a guess.
     *
     * The overlay reloaded the Formula Studio's configuration afterwards, because
     * its role lens and problems rail read these flags. There is no grid on this
     * surface, so the board reload is the whole of it here — the Formula Studio
     * re-reads the configuration when the user navigates back to it.
     */
    async empAction(item, action) {
        action = action || (item && item.meta && item.meta.action);
        if (!action) { return; }
        if (action.key === "to_field") {
            this.state.cmd = { token: this.state.cmd.token + 1,
                               kind: "armLeft", leftId: item.id };
            this.notif.add(
                _t("Pick the field on the right. What the contract already holds is kept as history."),
                { type: "info" });
            return;
        }
        let method = "employee_mapping_detach_component";
        let args = [item.id];
        if (action.key === "make_text" || action.key === "make_amount") {
            method = "employee_mapping_make_component";
            args = [item.id, action.key === "make_text" ? "text" : "amount"];
            // MF15 — CR-A2 puts an AMOUNT component in the payroll lane, and this
            // board hides that lane until asked. Without this the card the user
            // just acted on vanishes from under the pointer (W40's exact failure),
            // and the success message alone does not undo it.
            if (action.key === "make_amount") { this.state.empPayroll = true; }
        }
        this.state.busy = true;
        let r;
        try {
            r = await this.orm.call(MODEL, method, args);
        } catch (e) {
            r = { ok: false, msg: _t("That change could not be saved.") };
        } finally {
            this.state.busy = false;
        }
        if (r && r.ok === false) {
            this.notif.add(r.msg || _t("That change could not be saved."),
                           { type: "warning" });
            return;
        }
        if (r && r.msg) { this.notif.add(r.msg, { type: "success" }); }
        await this.load();
    }

    // ======================== J2 — the Excel on-ramp ==========================
    //
    // The Spreadsheet board's whole problem was that it could not answer "what
    // are my file's columns?". You could type a heading from memory and wire it
    // to a component, and find out next month whether you had spelled it right.
    //
    // Four verbs fix that, and they are deliberately the SAME four a person
    // does with a spreadsheet: show me my columns · give me the file to fill
    // in · use this one · forget it. Everything below is thin — the parsing,
    // the storage and the load all happen on the server, in code that already
    // existed, because a second parser in the browser would be a second
    // opinion about what a column is called.

    get isImport() { return this.state.mode === "import"; }

    /** `{filename, read_on, columns, shown, line}` — or null before any drop. */
    get sample() {
        const d = this.state.data;
        return (d && d.ok && d.sample) || null;
    }

    get rampBusy() { return !!this.state.rampBusy; }

    /** "38 of 54 components are fed by a column." Said once, where it matters. */
    get coverage() {
        const d = this.state.data;
        if (!d || !d.ok || !d.inputs) { return ""; }
        return _t("%(wired)s of %(total)s components are fed by a column.",
                  { wired: d.wired || 0, total: d.inputs });
    }

    // ---- the dropzone ---------------------------------------------------------
    onRampOver(ev) { ev.preventDefault(); this.state.rampOver = true; }
    onRampLeave(ev) { ev.preventDefault(); this.state.rampOver = false; }
    onRampDrop(ev) {
        ev.preventDefault();
        this.state.rampOver = false;
        const f = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
        if (f) { this.readFile(f); }
    }
    onRampPick(ev) {
        const f = ev.target.files && ev.target.files[0];
        // Clear the input so choosing the SAME file twice fires a change event
        // the second time — otherwise "re-read it, I fixed a heading" silently
        // does nothing, which reads as the feature being broken.
        ev.target.value = "";
        if (f) { this.readFile(f); }
    }

    /** Base64 the file in the browser; everything else happens server-side. */
    _b64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
            reader.onerror = () => reject(new Error("read failed"));
            reader.readAsDataURL(file);
        });
    }

    /**
     * "Read the headings" — and say so, in those words, before and after.
     *
     * The copy is load-bearing: a person about to drop a payroll file on a
     * screen they have not used before needs to know the numbers in it are not
     * going anywhere. Nothing here creates a batch, a line or a payslip.
     */
    async readFile(file, { thenHandoff = false } = {}) {
        if (!this.state.configId) {
            this.notif.add(_t("Pick the payroll scheme this file belongs to first."),
                           { type: "warning" });
            return null;
        }
        let b64;
        this.state.rampBusy = thenHandoff ? "handoff" : "read";
        try {
            b64 = await this._b64(file);
        } catch (e) {
            this.state.rampBusy = "";
            this.notif.add(_t("That file could not be opened."), { type: "danger" });
            return null;
        }
        try {
            if (thenHandoff) { return await this._handoff(b64, file.name); }
            const r = await this.orm.call(MODEL, "import_mapping_read_headers",
                                          [this.state.configId, b64, file.name]);
            if (!r || r.ok === false) {
                this.notif.add((r && r.msg) || _t("Those headings could not be read."),
                               { type: "warning" });
                return null;
            }
            this.state.data = r;
            this.state.extraCols = [];
            const read = r.read || {};
            this.notif.add(
                _t("Read %(n)s column heading(s) from %(file)s. No data was imported.",
                   { n: read.shown || read.columns || 0, file: file.name }),
                { type: "success" });
            if (read.truncated) {
                this.notif.add(_t("That workbook is very wide — only the first "
                                  + "columns were kept."), { type: "info" });
            }
            return r;
        } catch (e) {
            console.warn("pb_formula_studio: header read failed", e);
            this.notif.add(_t("Those headings could not be read."), { type: "danger" });
            return null;
        } finally {
            this.state.rampBusy = "";
        }
    }

    async forgetFile() {
        if (!this.state.configId) { return; }
        this.state.rampBusy = "read";
        try {
            const r = await this.orm.call(MODEL, "import_mapping_forget_headers",
                                          [this.state.configId]);
            if (r && r.ok === false) {
                this.notif.add(r.msg || _t("That file could not be forgotten."),
                               { type: "warning" });
                return;
            }
            this.state.data = r;
            this.notif.add(_t("The file was forgotten. Every wire you drew is still here."),
                           { type: "info" });
        } finally {
            this.state.rampBusy = "";
        }
    }

    // ---- the template ---------------------------------------------------------
    /**
     * "Download a template built from this scheme".
     *
     * The blob-download path is `formula_studio.js`' (`exportTestTemplate`),
     * which is the one this codebase already uses for every generated
     * workbook; the interesting half is server-side, where the headings are
     * derived from what the resolver matches rather than from a label.
     */
    async downloadTemplate() {
        if (!this.state.configId) {
            this.notif.add(_t("Pick a payroll scheme first."), { type: "warning" });
            return;
        }
        this.state.rampBusy = "template";
        try {
            const r = await this.orm.call(MODEL, "import_mapping_template",
                                          [this.state.configId]);
            if (!r || r.ok === false) {
                this.notif.add((r && r.msg) || _t("That template could not be built."),
                               { type: "warning" });
                return;
            }
            const bin = atob(r.file_b64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) { bytes[i] = bin.charCodeAt(i); }
            const url = URL.createObjectURL(new Blob([bytes], { type: r.mimetype }));
            const a = document.createElement("a");
            a.href = url;
            a.download = r.filename;
            a.click();
            URL.revokeObjectURL(url);
            this.notif.add(
                _t("Template downloaded — one column per input component, "
                   + "headed exactly as this scheme reads them."),
                { type: "success" });
        } catch (e) {
            console.warn("pb_formula_studio: template failed", e);
            this.notif.add(_t("That template could not be built."), { type: "danger" });
        } finally {
            this.state.rampBusy = "";
        }
    }

    // ---- the handoff ----------------------------------------------------------
    /**
     * "Load this file as a pay run…" — the one door, from here.
     *
     * Calls the guided flow's own `create_and_load`, which creates the batch,
     * loads the rows and matches employees, and then STOPS. Validate and
     * commit stay on the batch, in front of a person. This board can start a
     * run; it can never finish one.
     */
    loadAsPayRun() {
        if (!this.sample) { return; }
        return this._handoff(null, null);
    }

    onRampHandoffPick(ev) {
        const f = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (f) { this.readFile(f, { thenHandoff: true }); }
    }

    async _handoff(b64, filename) {
        this.state.rampBusy = "handoff";
        let r;
        try {
            r = await this.orm.call(MODEL, "import_mapping_handoff",
                                    [this.state.configId, b64 || false,
                                     filename || false]);
        } catch (e) {
            console.warn("pb_formula_studio: handoff failed", e);
            r = { ok: false };
        } finally {
            this.state.rampBusy = "";
        }
        if (!r || r.ok === false) {
            this.notif.add((r && r.msg) || _t("That file could not be loaded as a pay run."),
                           { type: "warning" });
            return null;
        }
        this.notif.add(
            _t("%(rows)s row(s) loaded, %(matched)s matched. Nothing is committed yet.",
               { rows: r.total_lines || 0, matched: r.matched || 0 }),
            { type: "success" });
        this.action.doAction({
            type: "ir.actions.client",
            tag: "pb_import_batch_cockpit",
            name: _t("Pay data load"),
            params: { batch_id: r.batch_id },
        });
        return r;
    }

    // ---- reconciliation (MAPFIX B3) -------------------------------------------
    /**
     * "Resolve remaining N columns".
     *
     * The board can leave a column with no wire and no badge indefinitely, and
     * that state reads as "not finished yet" for a day and as "fine" thereafter.
     * This is the surface that refuses to let it: every column with no destination
     * is listed, pre-ticked to become a contract component, and the person may
     * untick any of them to say "imported, deliberately used nowhere" (role
     * `reference`). Nothing is silently unresolved after it closes.
     */
    get unresolvedCount() {
        const d = this.state.data;
        return (d && d.ok && this.isEmp && d.unresolved) || 0;
    }
    get rcnRows() { return this.state.rcnRows || []; }
    get rcnTicked() { return this.rcnRows.filter((r) => r.tick); }

    async openReconcile() {
        if (!this.state.configId) { return; }
        this.state.rcnOpen = true;
        this.state.rcnRows = null;
        this.state.rcnBusy = true;
        try {
            const r = await this.orm.call(MODEL, "employee_mapping_unresolved",
                                          [this.state.configId]);
            this.state.rcnRows = ((r && r.rows) || []).map((x) => ({ ...x, tick: true }));
        } catch (e) {
            this.state.rcnRows = [];
            this.notif.add(_t("Those columns could not be read."), { type: "warning" });
        } finally {
            this.state.rcnBusy = false;
        }
    }
    closeReconcile() { this.state.rcnOpen = false; }
    toggleRcnRow(row) { row.tick = !row.tick; }
    setRcnAll(v) { for (const r of this.rcnRows) { r.tick = v; } }
    setRcnType(row, t) { row.value_type = t; }

    async applyReconcile() {
        if (!this.state.configId || !this.rcnRows.length) { return; }
        const decisions = this.rcnRows.map((r) => ({
            id: r.id, component: !!r.tick, value_type: r.value_type || "amount",
        }));
        // MF15 again: an amount component lands in the payroll lane, which this
        // board hides by default — reveal it, or the columns just resolved read as
        // having disappeared rather than as having been dealt with.
        if (decisions.some((d) => d.component && d.value_type === "amount")) {
            this.state.empPayroll = true;
        }
        this.state.rcnBusy = true;
        let r;
        try {
            r = await this.orm.call(MODEL, "employee_mapping_resolve_remaining",
                                    [this.state.configId, decisions,
                                     !!this.state.empPayroll]);
        } catch (e) {
            r = { ok: false, msg: _t("Those columns could not be saved.") };
        } finally {
            this.state.rcnBusy = false;
        }
        if (!r || r.ok === false) {
            this.notif.add((r && r.msg) || _t("Those columns could not be saved."),
                           { type: "warning" });
            return;
        }
        // The RPC hands back the refreshed board, so the footer count and the lane
        // chips move in the same frame the dialog closes in.
        this.state.data = r;
        this.state.rcnOpen = false;
        const a = r.applied || {};
        this.notif.add(_t("%s kept on the contract, %s left as reference.",
                          a.components || 0, a.reference || 0),
                       { type: "success" });
    }

    // =============================================================== templates
    get templatable() { return TEMPLATABLE.includes(this.state.mode); }

    /**
     * J1 — the panel has two faces now.
     *
     * The Studio was apply-only: you could spend a template but never mint one,
     * which made the feature look broken to anybody who reached it from here
     * rather than from the overlay. Save and delete moved across, and the panel
     * became a `tmplMode` ("save" | "apply") rather than a boolean, so the two
     * share one shell, one scrim and one Escape.
     */
    async openTemplates() {
        this.state.tmplMode = "apply";
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
    openTemplateSave() {
        this.state.tmplMode = "save";
        this.state.tmplName = "";
        this.state.tmplResult = null;
    }
    closeTemplates() { this.state.tmplMode = ""; this.state.tmplResult = null; }

    onTmplName(ev) { this.state.tmplName = ev.target.value || ""; }
    /**
     * Enter saves — and only from THIS input.
     *
     * MF33's lesson one input device over: a key handler that acts on more than
     * the element it is bound to acts on things nobody pressed it for. This is
     * bound to the name box, so there is nothing else it can reach.
     */
    onTmplKey(ev) { if (ev.key === "Enter") { this.saveTemplate(); } }

    async saveTemplate() {
        const name = (this.state.tmplName || "").trim();
        if (!name) {
            this.notif.add(_t("Give the template a name."), { type: "warning" });
            return;
        }
        this.state.tmplBusy = true;
        try {
            const r = await this.orm.call(MODEL, "mapping_template_save",
                                          [this.state.configId, this.state.mode, name]);
            if (r && r.ok) {
                this.notif.add(
                    _t("Saved “%(name)s” — %(n)s wire(s).", { name, n: r.line_count }),
                    { type: "success" });
                this.closeTemplates();
            } else {
                this.notif.add((r && r.msg) || _t("That template could not be saved."),
                               { type: "warning" });
            }
        } finally {
            this.state.tmplBusy = false;
        }
    }

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

    async deleteTemplate(id) {
        const r = await this.orm.call(MODEL, "mapping_template_delete", [id]);
        if (r && r.ok === false) {
            this.notif.add(r.msg || _t("That template could not be deleted."),
                           { type: "warning" });
            return;
        }
        await this.openTemplates();      // refresh the list in place
    }

    // ================================================================== empty
    /** The three-step strip only appears when there is nothing wired yet. */
    get firstRun() {
        // J4 — never on the Transformations board. The three-step strip says
        // "pick a source, pick a scheme, draw a wire or let us suggest them",
        // and on this board two of those three are wrong: there are no
        // suggestions, and the first thing to do with a rule-less connector is
        // write a rule. The board renders its own empty states instead.
        // J5 — never on the Journey either, and for a sharper version of the
        // same reason: the three-step strip tells you to pick a source and draw
        // a wire, and the Journey is the tab you are on precisely because you do
        // not yet know which source. Its ghosts carry the invitation instead,
        // one per lane, each pointing at the tab that can actually do it.
        // VALUEKIND P5 — never on Component treatment, for the plainest
        // reason of the three: that board has no wires at all, so "draw a wire"
        // is an instruction for a different screen.
        if (this.isTransform || this.isJourney || this.isTreatment) { return false; }
        return !!(this.state.data && this.state.data.ok && !this.mappedCount);
    }

    /** "8 rules" — the rail's own count on the Transformations board. */
    get ruleCount() {
        const d = this.state.data;
        return (d && d.ok && d.counts && d.counts.rules) || 0;
    }

    get emptyReason() {
        const d = this.state.data;
        if (!d || d.ok) { return ""; }
        return {
            no_config: _t("There is no payroll scheme on this database yet."),
            no_connector: _t("No HR system is connected yet — connect one in Integrations."),
            no_batch: _t("No file has been uploaded yet. Import one, then map its columns here."),
            no_pair: _t("This scheme has no mid-cycle/end-cycle twin to carry values into."),
            // J4 — a connector with no rules is not an error and must not read
            // as one. It is the normal state of a system nobody has had to
            // compute anything from yet, and the only useful verb is offered
            // beside the sentence rather than described in it.
            no_rules: _t("This system has no transformation rules yet. A rule turns "
                         + "what the system sends — a list of overtime rows, a table "
                         + "of dependants — into one number a pay component can read."),
        }[d.reason] || _t("There is nothing to map on this board.");
    }

    // ==================== J4 — the Rule Composer, opened in place ============
    //
    // The component is `pb_integrations`', mounted here unchanged. It owns all
    // of its own state, talks to its own four `pb.integrations` RPCs and
    // communicates with a host through exactly two callbacks, which is why it
    // could move without a wrapper: there was nothing cockpit-shaped in it to
    // unpick. Its scrim is `position: fixed` at `--pbim-z-modal`, so it is
    // mounted at the shell root — a sibling of the board, never inside it,
    // because an ancestor with a `transform` would trap a fixed scrim inside the
    // board it is supposed to cover.

    /**
     * The connector list the composer needs — MEMOISED ON ARRAY IDENTITY.
     *
     * A getter that builds a fresh array every call hands the child new props on
     * every single render of this host, and the composer re-renders (losing an
     * open picker, a half-typed name) for reasons that have nothing to do with
     * it. The Integrations cockpit learned this and caches the same way.
     */
    get composerConnectors() {
        const src = this.state.connectors;
        if (this._ccSrc !== src) {
            this._ccSrc = src;
            this._ccOut = src.map((c) => ({ id: c.id, name: c.name, icon: c.icon || "plug" }));
        }
        return this._ccOut;
    }

    /** `id` 0 opens it empty — "New transformation rule…". */
    openComposer(ruleId) {
        this.state.composer = {
            ruleId: ruleId || 0,
            connectorId: this.state.connectorId || 0,
        };
    }
    closeComposer() { this.state.composer = null; }

    /**
     * A saved rule changes every lane at once — its reads, its summary, its
     * health — so the board is RE-READ rather than patched. Patching would mean
     * this host holding a second opinion about what a rule is, which is the
     * duplication J4 exists to remove.
     */
    async onRuleSaved() {
        this.state.composer = null;
        await this.load();
    }

    /**
     * A rule → component edge, cut. `ref` is the mapping id; bindings never get
     * here. J6 D3 — the same helper the API board uses, not a second copy of it.
     */
    async removeTransformWire(ref) {
        return this._removeWireUndoable("api_mapping_cut", "api_mapping_restore",
                                        [ref]);
    }
}

registry.category("actions").add("pb_mapping_studio", MappingStudio);
