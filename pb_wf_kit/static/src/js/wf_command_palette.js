/** @odoo-module **/
/**
 * <WfCommandPalette/> — ⌘K for the Workforce workspace (P3b §3.5).
 *
 * Three groups, one input:
 *   Lenses  — the seven rooms, filtered instantly, no request;
 *   People  — the SAME debounced `hr.employee.name_search` the shared context
 *             bar runs, with the same 220 ms and the same limit, so there is
 *             one person-search behaviour in Workforce and not two;
 *   Actions — a static registry the HOST supplies. The kit knows nothing about
 *             schedules or punches; it renders labels and calls back (W6).
 *
 * The host mounts it through the Odoo OVERLAY SERVICE, which puts it in
 * `.o-overlay-container` — outside the workspace's DOM entirely. That is what
 * keeps W37 intact: the palette needs to paint above a lens's `position: fixed`
 * modals, and the only way to do that without stacking the shell's own chrome
 * is to not be inside the shell at all.
 *
 * W40 lives here too. This database has NO `unaccent` extension: "Bui Anh"
 * matches nothing while "Bùi Anh" matches. Rather than pre-filter or fold
 * client-side (both of which would lie about what the server can find), the
 * empty state SAYS so — and the catch narrows nothing, it warns.
 */
import {
    Component, useState, useRef, onMounted, onWillUnmount,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const PERSON_LIMIT = 8;
const TYPEAHEAD_MS = 220;
const RECENTS_KEY = "pbwf.palette.v1";
const RECENTS_MAX = 5;

export class WfCommandPalette extends Component {
    static template = "pb_wf_kit.WfCommandPalette";
    static props = {
        // [{ key, label, icon }] — the rooms this persona may open
        lenses: { type: Array },
        // [{ id, label, sublabel, icon }] — whatever the host wants to offer
        actions: { type: Array },
        onPickLens: { type: Function },
        onPickPerson: { type: Function },
        onRunAction: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            q: "",
            people: [],
            searching: false,
            searched: false,   // a query ran and came back (drives the hint)
            denied: false,     // this persona cannot read hr.employee
            active: 0,
            recents: this._loadRecents(),
        });
        this.inputRef = useRef("input");
        this._timer = null;

        onMounted(() => { if (this.inputRef.el) { this.inputRef.el.focus(); } });
        onWillUnmount(() => { if (this._timer) { clearTimeout(this._timer); } });
    }

    ic(n, s = 14) { return ic(n, s); }

    // ------------------------------------------------------------- the rows
    /**
     * ONE flat, ordered list is the single source of truth for both the
     * keyboard index and the grouped render. Sorting the render separately from
     * the index is how a highlight starts jumping between sections (the Formula
     * Studio palette's own W99 fix).
     */
    get rows() {
        const q = this.state.q.trim().toLowerCase();
        const out = [];
        // What is already on screen as a recent must not appear twice — a
        // duplicated row makes the arrow keys look broken.
        const seen = new Set();

        if (!q) {
            for (const r of this.state.recents) {
                out.push({ ...r, group: _t("Recent") });
                seen.add(`${r.kind}:${r.id}`);
            }
        }

        for (const l of this.props.lenses) {
            if (q && !l.label.toLowerCase().includes(q)) { continue; }
            if (seen.has(`lens:${l.key}`)) { continue; }
            out.push({
                kind: "lens", id: l.key, label: l.label, icon: l.icon,
                group: _t("Lenses"),
            });
        }

        for (const p of this.state.people) {
            out.push({
                kind: "person", id: p.id, label: p.name, icon: "user",
                group: _t("People"),
            });
        }

        for (const a of this.props.actions) {
            if (q && !(`${a.label} ${a.sublabel || ""}`).toLowerCase().includes(q)) {
                continue;
            }
            if (seen.has(`action:${a.id}`)) { continue; }
            out.push({
                kind: "action", id: a.id, label: a.label,
                sublabel: a.sublabel, icon: a.icon, group: _t("Actions"),
            });
        }
        return out;
    }

    /** The same rows, grouped for rendering, carrying their FLAT index. */
    get groups() {
        const map = new Map();
        this.rows.forEach((row, idx) => {
            if (!map.has(row.group)) { map.set(row.group, []); }
            map.get(row.group).push({ row, idx });
        });
        return [...map.entries()].map(([name, items]) => ({ name, items }));
    }

    get count() { return this.rows.length; }

    /**
     * The diacritics hint (§2a). It only appears once a search has actually
     * come back empty — telling someone about accent folding before they have
     * typed anything is noise, and after they have found their person it is
     * wrong.
     */
    get showAccentHint() {
        return this.state.searched
            && !this.state.searching
            && !this.state.people.length
            && this.state.q.trim().length >= 2;
    }

    // ------------------------------------------------------------ searching
    onInput(ev) {
        this.state.q = ev.target.value;
        this.state.active = 0;
        if (this._timer) { clearTimeout(this._timer); }
        const q = this.state.q.trim();
        if (q.length < 2 || this.state.denied) {
            this.state.people = [];
            this.state.searched = false;
            return;
        }
        this.state.searching = true;
        this._timer = setTimeout(() => this._search(q), TYPEAHEAD_MS);
    }

    async _search(q) {
        try {
            const res = await this.orm.call("hr.employee", "name_search", [], {
                // Odoo 19: `BaseModel.name_search(name, domain, operator, limit)`.
                // The pre-19 kwarg was `args`, and passing it raises TypeError on
                // EVERY keystroke — the bug that silently deleted the context
                // bar's person search for three phases (W40).
                name: q, domain: [], operator: "ilike", limit: PERSON_LIMIT,
            });
            if (this.state.q.trim() !== q) { return; }   // a late reply
            this.state.people = (res || []).map(([id, name]) => ({ id, name }));
            this.state.searched = true;
        } catch (e) {
            this.state.people = [];
            this.state.searched = true;
            // W40: only an ACCESS failure means "this persona has no person
            // search". Anything else is a bug, and retiring the control for the
            // session hides the very error that needs fixing.
            const name = (e && e.data && e.data.name) || "";
            if (/AccessError|AccessDenied/.test(name)) {
                this.state.denied = true;
            } else {
                console.warn("wf_palette: person search failed", e);
            }
        } finally {
            this.state.searching = false;
        }
    }

    // ------------------------------------------------------------- keyboard
    onKeydown(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.props.onClose();
            return;
        }
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            this.state.active = this.count ? (this.state.active + 1) % this.count : 0;
            return;
        }
        if (ev.key === "ArrowUp") {
            ev.preventDefault();
            this.state.active = this.count
                ? (this.state.active - 1 + this.count) % this.count : 0;
            return;
        }
        if (ev.key === "Enter") {
            ev.preventDefault();
            const row = this.rows[this.state.active];
            if (row) { this.run(row); }
        }
    }

    setActive(idx) { this.state.active = idx; }

    // ------------------------------------------------------------ execution
    /**
     * Every outcome closes the palette, and every outcome is a CLICK (or an
     * Enter, which is the same event chain). Nothing here runs from a mount
     * hook (W21) — the palette's only lifecycle work is focusing its input.
     */
    run(row) {
        this._remember(row);
        if (row.kind === "lens") {
            this.props.onPickLens(row.id);
        } else if (row.kind === "person") {
            this.props.onPickPerson(row.id);
        } else if (row.kind === "action") {
            this.props.onRunAction(row.id);
        }
        this.props.onClose();
    }

    // -------------------------------------------------------------- recents
    _loadRecents() {
        try {
            const raw = window.localStorage.getItem(RECENTS_KEY);
            const v = raw ? JSON.parse(raw) : null;
            return Array.isArray(v) ? v.slice(0, RECENTS_MAX) : [];
        } catch { return []; }
    }

    _remember(row) {
        const entry = { kind: row.kind, id: row.id, label: row.label,
                        icon: row.icon };
        const next = [entry, ...this.state.recents.filter(
            (r) => !(r.kind === entry.kind && r.id === entry.id))]
            .slice(0, RECENTS_MAX);
        this.state.recents = next;
        try {
            window.localStorage.setItem(RECENTS_KEY, JSON.stringify(next));
        } catch { /* private mode */ }
    }
}
