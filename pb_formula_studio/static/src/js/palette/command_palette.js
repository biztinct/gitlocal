/** @odoo-module **/
import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// W99 — Command palette (WP-A / D-A5). Registry-driven: the parent hands a static
// array of descriptors {id, section, label, keywords, run, sublabel} plus dynamic
// Components/Configs sections. Every run() calls an existing studio method — no RPC
// on open (opens in < 50 ms). ⌘K/Ctrl+K is wired in the studio root via useHotkey.
export class CommandPalette extends Component {
    static template = "pb_formula_studio.CommandPalette";
    static props = {
        commands: Array,
        onClose: Function,
    };
    static SECTION_ORDER = ["Views", "Actions", "Components", "Configs"];

    setup() {
        this.state = useState({ q: "", active: 0 });
        this.searchRef = useRef("search");
        this.listRef = useRef("list");
        this.notif = useService("notification");
        onMounted(() => { if (this.searchRef.el) this.searchRef.el.focus(); });
    }

    // Fuzzy subsequence scorer with word-boundary + consecutive bonuses (~30 lines,
    // no lib). Returns -Infinity when the query is not a subsequence of the haystack.
    _score(query, label, keywords) {
        const hay = (label + " " + (keywords || "")).toLowerCase();
        const q = query.toLowerCase();
        if (!q) return 0;
        let qi = 0, score = 0, prev = -2;
        for (let i = 0; i < hay.length && qi < q.length; i++) {
            if (hay[i] === q[qi]) {
                const boundary = i === 0 || /[\s·.\-_/]/.test(hay[i - 1]);
                score += 1 + (boundary ? 3 : 0) + (i === prev + 1 ? 2 : 0);
                prev = i; qi++;
            }
        }
        if (qi < q.length) return -Infinity;
        return score - hay.length * 0.01;   // tie-break toward shorter labels
    }

    get results() {
        const q = this.state.q.trim();
        const scored = [];
        for (const c of this.props.commands) {
            const s = q ? this._score(q, c.label, c.keywords) : 0;
            if (s === -Infinity) continue;
            scored.push({ cmd: c, score: s });
        }
        // Order by SECTION first, then score within a section. `results` is the
        // single source of truth for both the flat index (state.active / run())
        // AND the grouped render, so this ordering makes ArrowUp/Down walk the
        // list exactly as it appears on screen. Sorting only by score let the
        // flat index and the section-grouped rendering disagree, so the
        // highlight jumped between sections instead of moving down (W99 fix).
        const rank = s => {
            const i = CommandPalette.SECTION_ORDER.indexOf(s);
            return i === -1 ? CommandPalette.SECTION_ORDER.length : i;
        };
        scored.sort((a, b) =>
            rank(a.cmd.section) - rank(b.cmd.section) || (q ? b.score - a.score : 0));
        return scored.slice(0, 60);   // keep the list snappy at 250-component scale
    }
    get groups() {
        const rows = this.results;
        const map = {};
        rows.forEach((r, idx) => { (map[r.cmd.section] = map[r.cmd.section] || []).push({ cmd: r.cmd, idx }); });
        return CommandPalette.SECTION_ORDER.filter(s => map[s]).map(s => ({ name: s, rows: map[s] }));
    }
    get count() { return this.results.length; }

    hoverId(cmd) {
        return (cmd.id && cmd.id.startsWith("cmp.")) ? parseInt(cmd.id.slice(4), 10) : false;
    }

    onInput(ev) { this.state.q = ev.target.value; this.state.active = 0; }
    setActive(i) { this.state.active = i; }
    _clamp() { this.state.active = Math.max(0, Math.min(this.count - 1, this.state.active)); }
    onKeydown(ev) {
        if (ev.key === "ArrowDown") { ev.preventDefault(); this.state.active = Math.min(this.count - 1, this.state.active + 1); this._scroll(); }
        else if (ev.key === "ArrowUp") { ev.preventDefault(); this.state.active = Math.max(0, this.state.active - 1); this._scroll(); }
        else if (ev.key === "Enter") { ev.preventDefault(); this.run(this.state.active); }
        else if (ev.key === "Escape") { ev.preventDefault(); this.props.onClose(); }
    }
    _scroll() {
        requestAnimationFrame(() => {
            const el = this.listRef.el && this.listRef.el.querySelector(".cp-row.active");
            if (el) el.scrollIntoView({ block: "nearest" });
        });
    }
    run(idx) {
        const r = this.results[idx];
        if (!r) return;
        this.props.onClose();
        // Never let a bad command wedge the palette — but don't fail SILENTLY
        // either (W99 review finding): tell the user the command errored.
        try {
            r.cmd.run();
        } catch (e) {
            console.error("Command palette action failed:", r.cmd.id, e);
            this.notif.add(
                "That action couldn't be completed. Please try again.",
                { type: "danger" });
        }
    }
    close() { this.props.onClose(); }
}
