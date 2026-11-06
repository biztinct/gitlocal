/** @odoo-module **/
import { useState, useEffect, onWillUnmount } from '@odoo/owl';
import { patch } from '@web/core/utils/patch';
import { _t } from '@web/core/l10n/translation';
import { PbFormulaStudio } from './formula_studio';
import { formatComponentValue, componentInputType } from './value_format';

const commandLanesGetter = Object.getOwnPropertyDescriptor(PbFormulaStudio.prototype, 'commandLanes').get;
const paletteCommandsGetter = Object.getOwnPropertyDescriptor(PbFormulaStudio.prototype, 'paletteCommands').get;

patch(PbFormulaStudio.prototype, {
    setup() {
        super.setup(...arguments);
        // OWL renders templates with t-set through a context inheriting from the
        // component. Timers, cancellation tokens and graph caches must belong to
        // the real instance, not a short-lived render context.
        this._experienceHost = this;
        for (const [name, descriptor] of Object.entries(Object.getOwnPropertyDescriptors(PbFormulaStudio.prototype))) {
            if (name !== 'constructor' && name !== 'setup' && typeof descriptor.value === 'function') {
                this[name] = this[name].bind(this);
            }
        }
        this.experience = useState({query: '', filter: 'all', inspector: 'formula', group: '',
            draft: null, draftBusy: false, draftError: '', sampleBusy: false,
            typeReview: null, typeBusy: false, whatifRuns: [], whatifRun: '',
            outcome: '', whatifProgress: 0, whatifError: '', depQuery: ''});
        useEffect(() => {
            if (this.state.loaded && this.state.config.id) {
                try { sessionStorage.setItem('pbfs-workspace:' + this.state.config.id,
                    JSON.stringify({selected: this.state.selectedId})); } catch (_) {}
            }
        }, () => [this.state.loaded, this.state.config.id, this.state.selectedId]);
        useEffect(() => {
            if (!this.experience.draft && this.experience.typeReview === null) return;
            const opener = document.activeElement;
            const dialog = document.querySelector('.experience-dialog');
            const controls = () => [...(dialog?.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])') || [])];
            (dialog?.querySelector('[autofocus], input, select') || controls()[0])?.focus();
            const handle = ev => {
                if (ev.key === 'Escape') {
                    ev.preventDefault(); ev.stopImmediatePropagation();
                    this.closeComponentDraft(); this.closeTypeReview();
                } else if (ev.key === 'Tab') {
                    const nodes=controls(), first=nodes[0], last=nodes[nodes.length-1];
                    if (ev.shiftKey && document.activeElement===first) { ev.preventDefault(); last?.focus(); }
                    else if (!ev.shiftKey && document.activeElement===last) { ev.preventDefault(); first?.focus(); }
                }
            };
            window.addEventListener('keydown',handle,true);
            return () => { window.removeEventListener('keydown',handle,true); if (opener?.isConnected) opener.focus(); };
        },()=>[!!this.experience.draft,this.experience.typeReview !== null]);
        onWillUnmount(() => { clearTimeout(this._testTimer); clearTimeout(this._whatifTimer); this._whatifToken = (this._whatifToken || 0) + 1; });
    },
    async load(id) {
        const previous = this.state.config.id;
        await super.load(...arguments);
        if (this.state.empty) return;
        if (previous !== this.state.config.id) {
            this.experience.query = ''; this.experience.filter = 'all';
            this.experience.outcome = this.state.config.net_code || '';
            this.experience.whatifRun = '';
            let saved;
            try { saved = JSON.parse(sessionStorage.getItem('pbfs-workspace:' + this.state.config.id)); } catch (_) {}
            // Every newly opened scheme starts on Cards, including sessions
            // with an older saved Table/Grid preference. In-place reloads keep
            // the current view so saving a component does not move the reader.
            this.state.view = 'cards';
            if (saved && this.state.components.some(c => c.id === saved.selected)) this.state.selectedId = saved.selected;
        }
    },
    async chooseConfig(id) {
        await super.chooseConfig(...arguments);
        if (this.state.config.id === id) this.state.view = 'cards';
    },
    componentName(code) { return this.state.components.find(c=>c.code===code)?.name || code; },
    get commandLanes() { return commandLanesGetter.call(this._experienceHost || this); },
    get paletteCommands() { return paletteCommandsGetter.call(this._experienceHost || this); },
    get buildView() { return ['table', 'grid', 'cards'].includes(this.state.view); },
    get experienceRows() {
        const q = this.experience.query.trim().toLocaleLowerCase();
        const issueIds = new Set((this.state.probData?.problems || []).map(p=>p.rule_id));
        const rows = this.state.components.filter(c => (!q || `${c.name} ${c.code} ${c.col}`.toLocaleLowerCase().includes(q)) &&
            (this.experience.filter === 'all' || (this.experience.filter === 'issues' ? (!c.is_valid || issueIds.has(c.id)) : c.type === this.experience.filter)));
        return [...rows].sort((a,b) => (this.experience.group ? this.experienceGroup(a).localeCompare(this.experienceGroup(b)) : 0) || (a.sequence - b.sequence));
    },
    experienceGroup(c) { return this.experience.group === 'type' ? this.experienceType(c) : c.display_group || _t('Ungrouped'); },
    experienceType(c) { return {input: _t('Input'), formula: _t('Formula'), constant: _t('Constant')}[c.type] || c.type; },
    get valueKinds() { return [
        ['money', _t('Money')], ['quantity', _t('Quantity (days, hours)')], ['rate', _t('Percentage')],
        ['integer', _t('Whole number')], ['decimal', _t('Decimal number')], ['identifier', _t('ID or code')],
        ['text', _t('Text')], ['date', _t('Date')], ['boolean', _t('Yes / No')]]; },
    kindLabel(kind) { return (this.valueKinds.find(k => k[0] === kind) || ['', kind])[1]; },
    get issueSummary() {
        const c = (this.state.probData || {}).counts || {};
        if (c.error) return c.error === 1 ? _t('1 error to resolve') : _t('%s errors to resolve', c.error);
        if (this.testChip?.kind === 'fail') return this.testChip.failed === 1 ? _t('1 sample check failing') : _t('%s sample checks failing', this.testChip.failed);
        if (c.warning) return c.warning === 1 ? _t('1 warning to review') : _t('%s warnings to review', c.warning);
        return _t('No blocking issues');
    },
    openReviewQueue() {
        if (this.state.probData?.counts?.error) this.openProblems();
        else if (this.testChip?.kind === 'fail') this.openTest();
        else this.openProblems();
    },
    async openActualPreview() { this.state.previewDrawer = true; await this.openPersonPicker(); },
    fmtTyped(c, value) { return formatComponentValue(c, value, this.state.config.currency || '', {yes:_t('Yes'), no:_t('No')}); },
    tcell(value, row) { return this.fmtTyped(row, value); },
    testInputType(row) { return componentInputType(row); },
    replayFmt(item) { return this.fmtTyped(this.byCol(item.col) || this.state.components.find(c => c.code === item.code) || item, item.value); },
    whatifFmtVal(v) { return this.fmtTyped(this.state.components.find(c => c.code === this.state.whatifTarget) || this.whatifComp, v); },
    async loadSampleDetail(id) {
        const d = await this.orm.call('pb.formula.studio','get_sample_detail',[id]);
        if (this.state.testSampleId === id) this.state.testDetail = d && d.ok ? d : null;
    },
    closeWhatif() { this.cancelWhatif(); this.state.whatifOpen = false; },
    openDepMap() {
        super.openDepMap(...arguments);
        if (this.selected) requestAnimationFrame(()=>this.focusDependency({target:{value:this.selected.col}}));
    },
    async changePreviewSample(ev) {
        const id = Number(ev.target.value);
        if (!id) return;
        this.experience.sampleBusy = true;
        try {
            const preview = await this.orm.call('pb.formula.studio','compute_preview',[this.state.config.id,id]);
            this.state.personPayslipId = false; this.state.preview = preview;
        } finally { this.experience.sampleBusy = false; }
    },
    inspectComponent(id) { this.selectComponent(id); this.experience.inspector = 'formula'; },
    reviewUsage(id) { this.setView('table'); this.inspectComponent(id); this.experience.inspector = 'impact'; },
    editInspected() { this.setView('cards'); },
    addComponentQuick() {
        if (!this.state.canEdit) return;
        this.experience.draftError = '';
        this.experience.draft = {name:'', column_type:'input', value_kind:'', excel_formula:'', constant_value:0};
    },
    closeComponentDraft() { if (!this.experience.draftBusy) this.experience.draft = null; },
    async createComponentDraft() {
        const d = this.experience.draft;
        if (!d || this.experience.draftBusy) return;
        this.experience.draftError = '';
        if (!d.name.trim()) { this.experience.draftError = _t('Enter a component name.'); return; }
        if (!d.value_kind) { this.experience.draftError = _t('Choose a value type.'); return; }
        if (d.column_type === 'formula' && !d.excel_formula.trim()) { this.experience.draftError = _t('Enter a formula.'); return; }
        this.experience.draftBusy = true;
        try {
            if (d.column_type === 'formula') {
                const check = await this.orm.call('pb.formula.studio','validate_formula_live',[this.state.config.id,d.excel_formula]);
                if (check && check.valid === false) { this.experience.draftError = check.message || _t('Check the formula.'); return; }
            }
            const r = await this.orm.call('pb.formula.studio','add_component',[this.state.config.id,{...d,constant_value:Number(d.constant_value)||0}]);
            if (!r.ok) throw new Error(r.msg || _t('Could not add component.'));
            this.experience.draft = null;
            await this.load(this.state.config.id); this.state.selectedId = r.rule_id;
            this.notif.add(_t('Component added'),{type:'success'});
        } catch(e) { this.experience.draftError = e.message || _t('Could not add component.'); }
        finally { this.experience.draftBusy = false; }
    },
    async changeComponentKind(ev) {
        if (!this.selected || !this.state.canEdit) return;
        const kind = ev.target.value, code = this.selected.code;
        await this.orm.call('hr.formula.config','set_component_setup',[[this.state.config.id],{[code]:{kind}}]);
        await this.load(this.state.config.id);
        this.notif.add(_t('Value type saved. Recompute a pay run to change its stored results.'),{type:'success'});
    },
    async reviewValueTypes() {
        this.experience.typeBusy = true;
        try {
            const r = await this.orm.call('pb.formula.studio','experience_review_types',[this.state.config.id]);
            this.experience.typeReview = (r.rows || []).map(row => ({...row,selected:false}));
        } finally { this.experience.typeBusy = false; }
    },
    closeTypeReview() { if (!this.experience.typeBusy) this.experience.typeReview = null; },
    async applyValueTypes() {
        const updates = Object.fromEntries((this.experience.typeReview || []).filter(r=>r.selected).map(r=>[r.code,{kind:r.proposed}]));
        this.experience.typeBusy = true;
        try {
            if (Object.keys(updates).length) await this.orm.call('hr.formula.config','set_component_setup',[[this.state.config.id],updates]);
            this.experience.typeReview = null; await this.load(this.state.config.id);
            this.notif.add(_t('Selected value types saved'),{type:'success'});
        } finally { this.experience.typeBusy = false; }
    },
    onTestInput(code, ev) {
        // Keep all pending fields, capture the sample, and serialize requests.
        const sampleId = this.state.testSampleId, value = ev.target.value;
        const key = sampleId + ':' + code;
        this._pendingTestInputs ||= new Map();
        this._pendingTestInputs.set(key,{sampleId,code,value});
        clearTimeout(this._testTimer);
        this._testTimer = setTimeout(() => this.flushTestInputs(),320);
    },
    async flushTestInputs() {
        const entries = [...(this._pendingTestInputs || new Map()).values()];
        this._pendingTestInputs = new Map();
        const groups = new Map();
        for (const e of entries) groups.set(e.sampleId,{...(groups.get(e.sampleId)||{}),[e.code]:e.value});
        this._testSaveChain = (this._testSaveChain || Promise.resolve()).catch(()=>{}).then(async()=>{
            for (const [id,inputs] of groups) {
                try {
                    const r = await this.orm.call('pb.formula.studio','save_sample_inputs',[id,inputs]);
                    if (r && r.ok) { if (this.state.testSampleId === id) this.state.testDetail = r; this._syncSampleVerdict(r); }
                } catch(e) { this.notif.add(_t('Sample input could not be saved. Check the value and try again.'),{type:'danger'}); }
            }
        });
        await this._testSaveChain;
    },
    async selectSample(id) { await this.flushTestInputs(); await super.selectSample(...arguments); },
    async openWhatif() {
        this.state.whatifOpen = true; this.state.whatifResult = null;
        this.experience.whatifError = ''; this.experience.whatifProgress = 0;
        const [data,runs] = await Promise.all([
            this.orm.call('pb.formula.studio','whatif_components',[this.state.config.id]),
            this.orm.call('pb.formula.studio','compare_runs',[this.state.config.id])]);
        this.state.whatifData = data;
        this.experience.whatifRuns = runs.runs || [];
        this.experience.whatifRun = this.experience.whatifRuns[0]?.id || '';
        this.experience.outcome = this.state.config.net_code || '';
        const first = (data.components || []).find(c=>c.value) || (data.components || [])[0];
        if (first) this.whatifSelectTarget(first.code);
    },
    whatifSelectTarget(code) {
        const c = (this.state.whatifData?.components || []).find(x=>x.code===code);
        if (!c) return;
        this.cancelWhatif(); this.state.whatifTarget = code; this.state.whatifBase = c.value || 0;
        this.state.whatifMult = 1; this.state.whatifResult = null;
    },
    onWhatifSlide(ev) { this.cancelWhatif(); this.state.whatifMult = Number(ev.target.value)/100; this.state.whatifResult = null; },
    cancelWhatif() { this._whatifToken = (this._whatifToken || 0)+1; this.state.whatifBusy = false; },
    invalidateWhatif() { this.cancelWhatif(); this.state.whatifResult = null; },
    async _runWhatif(limit) {
        if (!this.state.whatifTarget || !this.experience.whatifRun || !this.experience.outcome) {
            this.experience.whatifError = _t('Choose a pay run and an outcome first.'); return;
        }
        const token = this._whatifToken = (this._whatifToken || 0)+1;
        this.state.whatifBusy = true; this.state.whatifResult = null;
        this.experience.whatifProgress = 0; this.experience.whatifError = '';
        let simId;
        try {
            const prep = await this.orm.call('pb.formula.studio','whatif_prepare',
                [this.state.config.id,this.state.whatifTarget,this.whatifCandidate,limit||false,Number(this.experience.whatifRun),this.experience.outcome]);
            simId = prep.sim_id;
            if (token !== this._whatifToken) return;
            if (!prep.ok || !simId) { this.experience.whatifError = prep.msg || _t('No stored inputs in this pay run.'); return; }
            this.state.whatifHeadlineName = prep.headline_name;
            const ids = prep.payslip_ids || [];
            if (!ids.length) { this.experience.whatifError = _t('No stored inputs in this pay run.'); return; }
            for (let i=0;i<ids.length;i+=100) {
                if (token !== this._whatifToken) return;
                await this.orm.call('pb.formula.studio','whatif_batch',[{sim_id:simId,payslip_ids:ids.slice(i,i+100)}]);
                this.experience.whatifProgress = Math.round(100*Math.min(i+100,ids.length)/ids.length);
            }
            if (token !== this._whatifToken) return;
            const r = await this.orm.call('pb.formula.studio','whatif_result',[simId]);
            if (token === this._whatifToken) this.state.whatifResult = r.result;
        } catch(e) { if (token === this._whatifToken) this.experience.whatifError = _t('Calculation failed. Check the inputs and try again.'); }
        finally {
            if (simId) this.orm.call('pb.formula.studio','whatif_drop',[simId]).catch(()=>{});
            if (token === this._whatifToken) this.state.whatifBusy = false;
        }
    },
    get experienceOutcomes() {
        const list = this.state.config.outcomes || [];
        return list.filter(c=>c.code === this.state.config.net_code);
    },
    get psNet() {
        const net = (this.state.psData?.rich_components || []).find(c=>c.code === this.state.config.net_code);
        return net && net.value !== undefined ? net.value : null;
    },
    get payslipLayoutReady() {
        return !!this.state.psData?.document || !!this.state.psData?.layout_html || !!this.state.psData?.sections?.some(s=>(s.components||[]).length || (s.embedded_components||[]).length);
    },
    focusDependency(ev) {
        const col = ev.target.value, node = this.state.depNodes.find(n=>n.col===col);
        if (!node) { this.clearDepFocus(); return; }
        this.setDepFocus(node);
        const box = this.depCanvasRef?.el?.getBoundingClientRect();
        this.state.depZoom = 1;
        this.state.depPan = {x:(box?.width || 1000)/2-node.x-node.w/2, y:(box?.height || 650)/2-node.y-node.h/2};
    },
});
