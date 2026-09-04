/** @odoo-module **/
import { Component, useState, useRef, onMounted } from "@odoo/owl";

// W14 — Find & replace (WP-A / D-A3, D-A7).
// Client-side search over the shared index (all formulas/names/codes are already
// in memory); server-side commit through the extended bulk_save_formulas
// (reason='bulk'). Replace mutates FORMULA TEXT ONLY — a code/name hit offers a
// jump to the existing rename flow instead of string-replacing an identity (C5).
export class FindReplace extends Component {
    static template = "pb_formula_studio.FindReplace";
    static props = {
        index: Array,                 // [{id,col,code,name,category,formula,type,is_valid,_*}]
        canEdit: { type: Boolean, optional: true },
        onClose: Function,
        onValidate: Function,         // (formula) => Promise<{valid, message}>
        onCommit: Function,           // (items, note) => Promise<{ok, saved}>
        onRename: Function,           // (ruleId) => void
        onJump: Function,             // (ruleId) => void
    };

    setup() {
        this.state = useState({
            query: "", replace: "",
            opts: { matchCase: false, wholeToken: true, scopeFormulas: true, scopeNames: true, scopeCodes: true },
            checked: {},              // {ruleId: bool} — which formula hits to commit
            validity: {},             // {ruleId: {valid, message}} after dry-run
            busy: false, dryRunning: false,
        });
        this.queryRef = useRef("query");
        this._vseq = 0;               // dry-run supersede token (C8)
        this._dryTimer = null;
        onMounted(() => { if (this.queryRef.el) this.queryRef.el.focus(); });
    }

    // ---- matching primitives ----
    _escape(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
    _regex() {
        const q = this.state.query;
        if (!q) return null;
        let pat = this._escape(q);
        if (this.state.opts.wholeToken) pat = "(?<![\\w.])" + pat + "(?![\\w.])";   // token boundary, digits/dots incl.
        try { return new RegExp(pat, this.state.opts.matchCase ? "g" : "gi"); } catch (e) { return null; }
    }
    _has(re, text) { if (!re || !text) return false; re.lastIndex = 0; const r = re.test(text); re.lastIndex = 0; return r; }
    count(text) { const re = this._regex(); if (!re || !text) return 0; re.lastIndex = 0; return (text.match(re) || []).length; }
    replaced(text) { const re = this._regex(); if (!re) return text; re.lastIndex = 0; return text.replace(re, this.state.replace); }
    // segment a string into {t, m} runs so matches render as <mark> without raw HTML.
    segs(text) {
        const re = this._regex();
        if (!re || !text) return [{ t: text || "", m: false }];
        const out = []; let last = 0, mm; re.lastIndex = 0;
        while ((mm = re.exec(text)) !== null) {
            if (mm.index > last) out.push({ t: text.slice(last, mm.index), m: false });
            out.push({ t: mm[0], m: true });
            last = mm.index + mm[0].length;
            if (mm.index === re.lastIndex) re.lastIndex++;   // zero-width guard
        }
        if (last < text.length) out.push({ t: text.slice(last), m: false });
        return out;
    }

    // ---- hit list (grouped by component) ----
    get hits() {
        const q = this.state.query.trim();
        const re = this._regex();
        if (!q || !re) return [];
        const o = this.state.opts;
        const out = [];
        for (const c of this.props.index) {
            const fHit = !!o.scopeFormulas && c.type === "formula" && this._has(re, c.formula);
            const nHit = !!o.scopeNames && this._has(re, c.name);
            const cHit = !!o.scopeCodes && (this._has(re, c.code) || this._has(re, c.col));
            if (!fHit && !nHit && !cHit) continue;
            out.push({ comp: c, fHit, nHit, cHit, count: fHit ? this.count(c.formula) : 0,
                       proposed: fHit ? this.replaced(c.formula) : null });
        }
        return out;
    }
    get formulaHits() { return this.hits.filter(h => h.fHit); }
    get totalOccurrences() { return this.formulaHits.reduce((a, h) => a + h.count, 0); }
    isChecked(id) { return this.state.checked[id] !== false; }   // default ON
    validityOf(id) { return this.state.validity[id] || null; }

    // ---- events ----
    _reset() { this.state.checked = {}; this.state.validity = {}; this._scheduleDryRun(); }
    // IME guard (C3): the inputs are uncontrolled (t-ref, no value binding), so
    // while an IME composition is active we skip the search/dry-run entirely and
    // run once on compositionend — Vietnamese/CJK input no longer searches over
    // half-composed strings (W14 review finding).
    onCompositionStart() { this._composing = true; }
    onCompositionEnd(ev) { this._composing = false; this.state.query = this.queryRef.el ? this.queryRef.el.value : ev.target.value; this._reset(); }
    onQuery(ev) { if (this._composing) return; this.state.query = ev.target.value; this._reset(); }
    onReplace(ev) { if (this._composing) return; this.state.replace = ev.target.value; this._reset(); }
    toggleOpt(k) { this.state.opts[k] = !this.state.opts[k]; this._reset(); }
    toggleHit(id) { this.state.checked[id] = this.isChecked(id) === false ? true : false; }
    onQueryKeydown(ev) { if (ev.key === "Enter") { ev.preventDefault(); this.queryRef.el && this.queryRef.el.blur(); } }

    // Dry-run each proposed formula through validate (batched, superseded — C8).
    _scheduleDryRun() {
        clearTimeout(this._dryTimer);
        if (!this.props.canEdit || this.state.replace === "") return;
        this._dryTimer = setTimeout(async () => {
            const seq = ++this._vseq;
            this.state.dryRunning = true;
            const targets = this.formulaHits;
            const results = {};
            for (const h of targets) {
                const res = await this.props.onValidate(h.proposed);
                if (seq !== this._vseq) return;                 // superseded → drop
                results[h.comp.id] = res || { valid: true, message: "" };
            }
            if (seq === this._vseq) { this.state.validity = results; this.state.dryRunning = false; }
        }, 300);
    }

    get commitItems() {
        return this.formulaHits
            .filter(h => this.isChecked(h.comp.id))
            .filter(h => { const v = this.validityOf(h.comp.id); return !v || v.valid !== false; })   // exclude known-invalid
            .map(h => ({ rule_id: h.comp.id, formula: h.proposed }));
    }
    get excludedCount() {
        return this.formulaHits.filter(h => this.isChecked(h.comp.id))
            .filter(h => { const v = this.validityOf(h.comp.id); return v && v.valid === false; }).length;
    }
    get canCommit() { return this.props.canEdit && this.state.replace !== "" && this.commitItems.length > 0 && !this.state.busy; }

    async commit() {
        if (!this.canCommit) return;
        const items = this.commitItems;
        const note = `find/replace: ${this.state.query} → ${this.state.replace}`;
        this.state.busy = true;
        try {
            await this.props.onCommit(items, note);
        } finally { this.state.busy = false; }
        // the parent reloads components → index changes; clear per-hit state
        this.state.validity = {}; this.state.checked = {};
    }

    rename(id) { this.props.onRename(id); }
    jump(id) { this.props.onJump(id); }
    close() { this.props.onClose(); }
}
