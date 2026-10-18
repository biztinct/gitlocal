/** @odoo-module **/
import { Component, useState, useExternalListener, onWillUnmount } from '@odoo/owl';
import { documentField, documentIssues } from './payslip_document_tools';

export class PayslipDocumentDesigner extends Component {
    static template = 'pb_formula_studio.PayslipDocumentDesigner';
    static props = ['document', 'components', 'meta', 'onSave', 'onClose'];
    setup() {
        this.state = useState({ document: JSON.parse(JSON.stringify(this.props.document)),
            page: 0, selected: null, zoom: 1, preview: false, busy: false, dirty: false,
            error: '', query: '', historyIndex: 0, historyCount: 1 });
        this.history = [this.snapshot()];
        useExternalListener(window, 'pointermove', this.pointerMove.bind(this));
        useExternalListener(window, 'pointerup', this.pointerUp.bind(this));
        onWillUnmount(() => { this.drag = null; });
    }
    get page() { return this.state.document.pages[this.state.page]; }
    get selected() { return this.page.fields.find(field => field.id === this.state.selected); }
    get issues() { return documentIssues(this.state.document); }
    get metaFields() { return Object.keys(this.props.meta || {}).map(key => ({ key, name: key.replaceAll('_', ' ') })); }
    get components() {
        const q = this.state.query.toLowerCase();
        return this.props.components.filter(component => !q || `${component.name} ${component.code} ${component.col}`.toLowerCase().includes(q));
    }
    snapshot() { return JSON.stringify(this.state.document.pages.map(page => page.fields)); }
    remember() {
        const snapshot = this.snapshot();
        if (snapshot === this.history[this.state.historyIndex]) return;
        this.history = this.history.slice(0, this.state.historyIndex + 1);
        this.history.push(snapshot);
        if (this.history.length > 40) this.history.shift();
        this.state.historyIndex = this.history.length - 1;
        this.state.historyCount = this.history.length;
        this.state.dirty = true;
    }
    undo(delta) {
        const next = this.state.historyIndex + delta;
        if (next < 0 || next >= this.history.length) return;
        const fields = JSON.parse(this.history[next]);
        fields.forEach((rows, index) => { this.state.document.pages[index].fields = rows; });
        this.state.historyIndex = next;
        this.state.dirty = true;
    }
    setPage(ev) { this.state.page = Number(ev.target.value); this.state.selected = null; }
    fieldStyle(field) {
        const font = { serif: "'PB Payslip Serif','Times New Roman',serif", sans: "'PB Payslip Sans',Arial,sans-serif", mono: "'PB Payslip Mono',monospace" }[field.font];
        const size = this.fit(field).size;
        return `left:${field.x / this.page.width * 100}%;top:${field.y / this.page.height * 100}%;width:${field.w / this.page.width * 100}%;height:${field.h / this.page.height * 100}%;font-size:${size * this.state.zoom}px;font-family:${font};font-weight:${field.bold ? 700 : 400};font-style:${field.italic ? 'italic' : 'normal'};text-align:${field.align};color:${field.color};background:${field.cover ? field.background : 'transparent'};padding:${this.state.zoom}px ${2*this.state.zoom}px;`;
    }
    fit(field) {
        const ctx = (this.measureCanvas ||= document.createElement('canvas')).getContext('2d');
        const font = { serif: 'PB Payslip Serif', sans: 'PB Payslip Sans', mono: 'PB Payslip Mono' }[field.font];
        let size = field.font_size;
        const text = String(this.value(field));
        while (true) {
            ctx.font = `${field.italic ? 'italic ' : ''}${field.bold ? 'bold ' : ''}${size}px "${font}"`;
            const lines = [];
            for (const paragraph of text.split('\n')) {
                let line = '';
                for (const word of paragraph.split(' ')) {
                    const candidate = `${line} ${word}`.trim();
                    if (line && ctx.measureText(candidate).width > field.w - 4) { lines.push(line); line = word; }
                    else line = candidate;
                }
                lines.push(line);
            }
            if (size <= 4 || (lines.length * size * 1.15 <= field.h - 2 && lines.every(line => ctx.measureText(line).width <= field.w - 4))) return { size, value: lines.join('\n') };
            size = Math.max(4, size - .25);
        }
    }
    value(field) {
        if (field.binding === 'text') return field.text.replace(/\{\{pb_meta:([a-z_]+)\}\}/g,
            (_match, key) => this.props.meta[key] || field.empty);
        if (field.binding === 'meta') return this.props.meta[field.meta_key] || field.empty;
        if (field.binding !== 'component') return field.empty;
        const component = this.props.components.find(item => item.id === field.rule_id);
        let value = component?.value;
        if (value === undefined || value === null || value === '') return field.empty;
        if (field.rate_rule_id) {
            const rate = Number(this.props.components.find(item => item.id === field.rate_rule_id)?.value);
            if (!Number.isFinite(rate) || rate <= 0 || !Number.isFinite(Number(value))) return field.empty;
            value = field.rate_operation === 'multiply' ? Number(value) * rate : Number(value) / rate;
        }
        if (field.format === 'auto' && !field.rate_rule_id) return component.formatted_value ?? String(value);
        if (field.format === 'text' || !Number.isFinite(Number(value))) return String(value);
        const decimals = field.format === 'integer' ? 0 : Number(field.decimals || 0);
        const number = Number(value) * (field.format === 'percentage' ? 100 : 1);
        return (field.format === 'currency' ? field.currency : '') + number.toLocaleString('en-US',
            { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + (field.format === 'percentage' ? '%' : '');
    }
    source(field) { return field.binding === 'meta' ? `meta:${field.meta_key}` : field.binding === 'component' ? `component:${field.rule_id}` : field.binding; }
    setSource(ev) {
        const value = ev.target.value, field = this.selected;
        this.state.query = '';
        field.rule_id = false; field.meta_key = '';
        if (value.startsWith('component:')) {
            field.binding = 'component'; field.rule_id = Number(value.split(':')[1]);
            const component = this.props.components.find(item => item.id === field.rule_id);
            if (component && component.value_kind !== 'money') field.format = 'auto';
        }
        else if (value.startsWith('meta:')) { field.binding = 'meta'; field.meta_key = value.split(':')[1]; field.align = 'left'; }
        else field.binding = value;
        this.remember();
    }
    change(key, ev, numeric = false) {
        if (!this.selected) return;
        const field = this.selected;
        field[key] = ev.target.type === 'checkbox' ? ev.target.checked : numeric ? Number(ev.target.value) : ev.target.value;
        if (['x', 'y', 'w', 'h'].includes(key)) this.clamp(field);
        this.remember();
    }
    clamp(field) {
        field.w = Math.max(3, Math.min(this.page.width, field.w));
        field.h = Math.max(3, Math.min(this.page.height, field.h));
        field.x = Math.max(0, Math.min(this.page.width - field.w, field.x));
        field.y = Math.max(0, Math.min(this.page.height - field.h, field.y));
    }
    add(kind) {
        const field = documentField(`field-${Date.now()}-${this.page.fields.length}`, kind === 'blank' ? 'New live field' : kind === 'cover' ? 'Cover area' : 'Text',
            40, 70, 150, 24);
        if (kind !== 'blank') Object.assign(field, { binding: 'text', text: kind === 'cover' ? '' : 'Your text', empty: '', align: 'left' });
        this.clamp(field);
        this.page.fields.push(field); this.state.selected = field.id;
        this.state.preview = false; this.remember();
    }
    duplicate() {
        if (!this.selected) return;
        const field = { ...this.selected, id: `field-${Date.now()}-${this.page.fields.length}`, x: this.selected.x + 8, y: this.selected.y + 8 };
        this.clamp(field); this.page.fields.push(field); this.state.selected = field.id; this.remember();
    }
    remove() { this.page.fields = this.page.fields.filter(field => field.id !== this.state.selected); this.state.selected = null; this.remember(); }
    pointerDown(field, ev, resize = false) {
        if (this.state.preview || ev.button !== 0) return;
        ev.preventDefault(); ev.stopPropagation();
        ev.currentTarget.closest('.ps-document-sheet')?.focus();
        this.state.selected = field.id;
        this.drag = { id: field.id, x: ev.clientX, y: ev.clientY, start: { ...field }, resize };
    }
    pointerMove(ev) {
        if (!this.drag) return;
        const field = this.page.fields.find(item => item.id === this.drag.id);
        if (!field) return;
        const dx = (ev.clientX - this.drag.x) / this.state.zoom, dy = (ev.clientY - this.drag.y) / this.state.zoom;
        if (this.drag.resize) { field.w = this.drag.start.w + dx; field.h = this.drag.start.h + dy; }
        else { field.x = this.drag.start.x + dx; field.y = this.drag.start.y + dy; }
        this.clamp(field);
    }
    pointerUp() { if (this.drag) { this.drag = null; this.remember(); } }
    keyDown(ev) {
        if (/INPUT|TEXTAREA|SELECT/.test(ev.target.tagName)) return;
        if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'z') { ev.preventDefault(); this.undo(ev.shiftKey ? 1 : -1); return; }
        if (!this.selected || this.state.preview) return;
        if (ev.key === 'Delete' || ev.key === 'Backspace') { ev.preventDefault(); this.remove(); return; }
        const delta = ev.shiftKey ? 10 : 1;
        const move = { ArrowLeft: [-delta, 0], ArrowRight: [delta, 0], ArrowUp: [0, -delta], ArrowDown: [0, delta] }[ev.key];
        if (move) { ev.preventDefault(); this.selected.x += move[0]; this.selected.y += move[1]; this.clamp(this.selected); this.remember(); }
    }
    async save() {
        if (this.state.busy) return;
        this.remember(); this.state.busy = true; this.state.error = '';
        try {
            const result = await this.props.onSave(JSON.parse(JSON.stringify(this.state.document)));
            if (result?.ok) { this.state.dirty = false; this.props.onClose(); }
            else this.state.error = result?.msg || 'The design could not be saved.';
        } catch { this.state.error = 'The design could not be saved. Check your connection and retry.'; }
        finally { this.state.busy = false; }
    }
}
