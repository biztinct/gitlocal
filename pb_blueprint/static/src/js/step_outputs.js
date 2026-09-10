/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onWillUpdateProps,
         onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

import { STEP_META } from "./blueprint_steps";
import {
    FILTER_KEYS, filterLabel, filterHint, badgeLabel, groupLabel, flowNodes,
    fmtValue, formulaText, isLongFormula, filterRows, windowOf,
} from "./outputs_text";
import { OutputInspector } from "./output_inspector";

/** One table row, in pixels. Fixed, because the window maths depends on it. */
const ROW_H = 46;

/** Above this many rows the table paints only what is on screen. */
const VIRTUAL_FROM = 150;

/**
 * Step 4 — Outputs & formulas: see what your rules create.
 *
 * The hero is the money-flow strip: four nodes joined by arrows that say, in
 * one line, that this configuration turns N given numbers into N components
 * through N calculations, and that the answer is somebody's take-home pay and
 * what they cost. The counts run up on arrival, and hovering a node lights the
 * filter that shows you exactly those rows — the picture and the table are the
 * same thing at two zoom levels.
 *
 * Underneath, every component with its calculation IN CODES rather than in the
 * column letters the engine stores, what it pays the sample employee, and where
 * the calculation came from. The inspector answers the two questions a table
 * cannot: what feeds this number, and what does it feed.
 */
export class StepOutputs extends Component {
    static template = "pb_blueprint.StepOutputs";
    static components = { OutputInspector };
    static props = {
        configId: { type: [Number, Boolean] },
        revision: { type: Number, optional: true },
        sampleId: { type: [Number, Boolean], optional: true },
        sampleName: { type: String, optional: true },
        currency: { type: String, optional: true },
        reloadKey: { type: Number, optional: true },
        // The Test step's coverage line names a component nobody has checked;
        // pressing it lands here with that component already open.
        inspectRule: { type: Number, optional: true },
        onChanged: { type: Function },
        onRevision: { type: Function },
        onGrid: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.searchRef = useRef("search");
        this.listRef = useRef("list");

        this.state = useState({
            loading: true,
            error: "",
            data: null,
            filter: "final",
            query: "",
            focus: 0,
            expanded: 0,          // the row whose whole calculation is showing
            inspect: 0,           // the row the side sheet is open on
            hover: "",            // the money-flow node under the pointer
            exporting: false,
            busy: false,
            scrollTop: 0,
            viewport: 620,
            shown: { inputs: 0, components: 0, rules: 0 },
        });

        this._raf = null;
        this._searchTimer = null;

        useHotkey("control+f", () => this.focusSearch(),
                  { bypassEditableProtection: true });

        onWillStart(async () => {
            if (this.props.inspectRule) {
                // Arriving from the coverage line: the component being asked
                // about may well be one the default filter hides, so widen
                // first rather than opening a sheet over an empty table.
                this.state.filter = "all";
            }
            await this.load();
            this.state.loading = false;
            if (this.props.inspectRule) { this.openInspector(this.props.inspectRule); }
        });

        // The value beside every row is what it pays THIS sample employee, so
        // it has to follow the sample — a number that is quietly wrong is worse
        // than no number (BP23).
        onWillUpdateProps(async (next) => {
            if (next.reloadKey !== this.props.reloadKey
                    || next.sampleId !== this.props.sampleId) {
                await this.load(next.sampleId);
            }
        });

        onWillUnmount(() => {
            if (this._raf) { cancelAnimationFrame(this._raf); }
            if (this._searchTimer) { clearTimeout(this._searchTimer); }
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    get meta() { return STEP_META.outputs; }

    async rpc(method, args) {
        try {
            return await this.orm.call("pb.blueprint.studio", method, args || []);
        } catch (e) {
            const reason = (e && e.data && e.data.message) || (e && e.message) || "";
            this.notif.add(reason || _t("The server could not be reached."),
                           { type: "danger" });
            return { ok: false, reason };
        }
    }

    async load(sampleId) {
        const res = await this.rpc("bp_outputs", [
            this.props.configId,
            sampleId === undefined ? (this.props.sampleId || false) : (sampleId || false),
            this.state.filter,
            this.state.query,
        ]);
        if (!res || !res.ok) {
            this.state.error = (res && res.reason)
                || _t("The outputs could not be read. Reload the page to try again.");
            return;
        }
        this.state.error = "";
        this.state.data = res;
        this.state.focus = 0;
        if (res.revision !== undefined) { this.props.onRevision(res.revision); }
        this._countUp(res.strip || {});
    }

    // ==================================================================
    // The money-flow strip
    // ==================================================================
    /**
     * The three counts run up to their new value over 520ms.
     *
     * Motion with a purpose and nothing else: it is what makes the strip read
     * as a flow rather than as three unrelated numbers, and it repeats whenever
     * the configuration actually changes underneath it.
     */
    _countUp(strip) {
        const to = {
            inputs: Number(strip.inputs || 0),
            components: Number(strip.components || 0),
            rules: Number(strip.rules || 0),
        };
        const from = { ...this.state.shown };
        if (from.inputs === to.inputs && from.components === to.components
                && from.rules === to.rules) {
            return;
        }
        if (this._raf) { cancelAnimationFrame(this._raf); }
        const start = performance.now();
        const span = 520;
        const tick = (now) => {
            const t = Math.min(1, (now - start) / span);
            const eased = 1 - Math.pow(1 - t, 3);
            for (const key of ["inputs", "components", "rules"]) {
                this.state.shown[key] = Math.round(
                    from[key] + (to[key] - from[key]) * eased);
            }
            this._raf = t < 1 ? requestAnimationFrame(tick) : null;
        };
        this._raf = requestAnimationFrame(tick);
    }

    get nodes() {
        const data = this.data;
        const nodes = flowNodes(data.strip || {}, data.totals || {});
        nodes[0].shown = this.state.shown.inputs;
        nodes[1].shown = this.state.shown.components;
        nodes[2].shown = this.state.shown.rules;
        return nodes;
    }

    onNodeEnter(node) { this.state.hover = node.key; }
    onNodeLeave() { this.state.hover = ""; }

    async onNodeClick(node) {
        const key = (node.filters || [])[0];
        if (key) { await this.setFilter(key); }
    }

    /** A chip lights up when the node under the pointer is about those rows. */
    lit(key) {
        if (!this.state.hover) { return false; }
        const node = this.nodes.find((n) => n.key === this.state.hover);
        return !!node && (node.filters || []).includes(key);
    }

    money(value) { return fmtValue(value); }

    // ==================================================================
    // Filters and search
    // ==================================================================
    get FILTERS() { return FILTER_KEYS; }

    filterLabel(key) { return filterLabel(key); }

    get filterHint() { return filterHint(this.state.filter); }

    countOf(key) { return ((this.data.counts || {})[key]) || 0; }

    async setFilter(key) {
        if (this.state.filter === key) { return; }
        this.state.filter = key;
        this.state.expanded = 0;
        this.state.scrollTop = 0;
        if (this.listRef.el) { this.listRef.el.scrollTop = 0; }
        await this.load();
    }

    onSearch(ev) {
        this.state.query = ev.target.value;
        this.state.focus = 0;
        // Local first, so typing feels instant; the server follows a beat later
        // and reaches past the rows this answer happened to carry.
        if (this._searchTimer) { clearTimeout(this._searchTimer); }
        this._searchTimer = setTimeout(() => this.load(), 260);
    }

    clearSearch() {
        this.state.query = "";
        if (this._searchTimer) { clearTimeout(this._searchTimer); }
        this.focusSearch();
        this.load();
    }

    focusSearch() {
        if (this.searchRef.el) { this.searchRef.el.focus(); }
    }

    get searching() { return !!(this.state.query || "").trim(); }

    // ==================================================================
    // The table
    // ==================================================================
    get data() { return this.state.data || {}; }

    get rows() { return filterRows(this.data.rows || [], this.state.query); }

    get virtual() {
        // Windowing is switched off while a row is expanded: an expanded row is
        // taller than the others, and a window built on one fixed height would
        // then scroll to the wrong place. The cap on rows the server sends
        // makes painting them all for that moment cheap.
        return this.rows.length > VIRTUAL_FROM && !this.state.expanded;
    }

    get pane() {
        if (!this.virtual) {
            return { first: 0, last: this.rows.length, top: 0, bottom: 0 };
        }
        return windowOf(this.rows.length, this.state.scrollTop,
                        this.state.viewport, ROW_H);
    }

    get painted() {
        const w = this.pane;
        return this.rows.slice(w.first, w.last);
    }

    get rowHeight() { return ROW_H; }

    onScroll(ev) {
        if (!this.virtual) { return; }
        this.state.scrollTop = ev.target.scrollTop;
        this.state.viewport = ev.target.clientHeight || 620;
    }

    badgeLabel(badge) { return badgeLabel(badge); }
    groupLabel(group) { return groupLabel(group); }
    formulaText(row) { return formulaText(row); }
    isLong(row) { return isLongFormula(row); }
    valueOf(row) { return fmtValue(row.value); }

    isExpanded(row) { return this.state.expanded === row.id; }

    toggleExpand(row) {
        this.state.expanded = this.isExpanded(row) ? 0 : row.id;
    }

    /** The whole table's own keys, and they stop here (BP20). */
    onListKeydown(ev) {
        const rows = this.rows;
        const mine = ["ArrowDown", "ArrowUp", "Enter", "Escape"];
        if (mine.includes(ev.key)) { ev.stopPropagation(); }
        if (!rows.length) { return; }
        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const step = ev.key === "ArrowDown" ? 1 : -1;
            this.state.focus = Math.max(0, Math.min(rows.length - 1,
                                                    this.state.focus + step));
            this.focusRow(this.state.focus);
            return;
        }
        if (ev.key === "Enter") {
            ev.preventDefault();
            const row = rows[this.state.focus];
            if (row) { this.openInspector(row.id); }
            return;
        }
        if (ev.key === "Escape" && this.state.inspect) {
            ev.preventDefault();
            this.closeInspector();
        }
    }

    focusRow(index) {
        const el = this.listRef.el
            && this.listRef.el.querySelectorAll(".pbbp-out-row")[
                index - this.pane.first];
        if (el) { el.focus(); }
    }

    get emptyLine() {
        // A configuration with nothing in it is not a filter that matched
        // nothing: saying "nothing matches Final outputs" to somebody who has
        // not added a component yet answers a question they did not ask.
        if (!this.searching && !this.countOf("all")) {
            return _t("This configuration has no components yet. Add them on the Pay rules step, or import a workbook.");
        }
        if (this.searching) {
            return _t("Nothing matches “%s”. Try a component's name, its code, or part of its calculation.",
                      this.state.query.trim());
        }
        if (this.state.filter !== "all") {
            // The chip's own words, in quotes: every other phrasing reads
            // wrongly for at least one of the nine ("is a edited by hand yet").
            return _t("Nothing here matches “%s”. Press “All” to see every component.",
                      filterLabel(this.state.filter));
        }
        return _t("This configuration has no components yet. Add them on the Pay rules step, or import a workbook.");
    }

    get cappedLine() {
        const n = Number(this.data.capped || 0);
        if (!n) { return ""; }
        return _t("Showing the first %(shown)s of %(total)s. Search to narrow it down.",
                  { shown: this.data.shown, total: this.data.matching });
    }

    // ==================================================================
    // The inspector
    // ==================================================================
    openInspector(ruleId) { this.state.inspect = ruleId; }

    closeInspector() { this.state.inspect = 0; }

    /** A chip inside the inspector: jump to the component it names. */
    async onJump(ruleId) {
        const known = (this.data.rows || []).some((r) => r.id === ruleId);
        if (!known) {
            // It is filtered out of the current view — widen rather than fail.
            await this.setFilter("all");
        }
        this.state.inspect = ruleId;
        const index = this.rows.findIndex((r) => r.id === ruleId);
        if (index >= 0) {
            this.state.focus = index;
            if (this.virtual) {
                this.state.scrollTop = Math.max(0, index * ROW_H - 120);
                if (this.listRef.el) {
                    this.listRef.el.scrollTop = this.state.scrollTop;
                }
            }
        }
    }

    /** The inspector changed something — the hero and the table both follow. */
    async onInspectorChanged(res) {
        if (res && res.revision !== undefined) { this.props.onRevision(res.revision); }
        await this.load();
        this.props.onChanged(res || {});
    }

    // ==================================================================
    // The catalogue
    // ==================================================================
    async onExport() {
        if (this.state.exporting) { return; }
        this.state.exporting = true;
        const res = await this.rpc("bp_export_catalog",
                                   [this.props.configId, this.props.sampleId || false]);
        this.state.exporting = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason)
                || _t("The catalogue could not be built."), { type: "warning" });
            return;
        }
        this.download(res);
        this.notif.add(
            res.components === 1
                ? _t("Downloaded — 1 component in the file.")
                : _t("Downloaded — %s components in the file.", res.components),
            { type: "success" });
    }

    /** Text to a saved file, without ever leaving the page. */
    download(res) {
        const blob = new Blob([res.content], { type: res.mimetype });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = res.filename;
        link.click();
        URL.revokeObjectURL(url);
    }
}
