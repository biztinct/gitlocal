/** @odoo-module **/
import { Component, useState, onWillStart, useRef, onWillUnmount, onMounted } from '@odoo/owl';
import { Dialog } from '@web/core/dialog/dialog';
import { useService } from '@web/core/utils/hooks';
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';
import { _t } from '@web/core/l10n/translation';
import { ic } from '@pb_import_kit/js/import_icons';

// PDR S3 — previews are worked out after the grid renders, 20 people a call.
const PREVIEW_BATCH = 20;
// PDR P2 W1b — only the rows in view (plus a margin) are drawn.
const ROW_HEIGHT = 60;      // fallback until a drawn row is measured
const OVERSCAN = 8;
// The worksheet asks for the light payload: per-column facts travel once.
const COMPACT = {context: {pr_compact: true}};

export class PayrollReviewDialog extends Component {
    static template = 'pb_payrun_wizard.PayrollReviewDialog';
    static components = { Dialog };
    static props = { payload: Object, onReviewed: Function, close: Function };
    setup() {
        this.orm = useService('orm'); this.action = useService('action'); this.dialog = useService('dialog');
        this.grid = useRef('grid'); this.alive = true;
        this.state = useState({data:null, loading:true, saving:false, error:'', query:'', componentQuery:'', filter:'all', group:'all',
            selected:null, detail:null, value:'', reason:'', scope:'run', review:false, history:false, maximized:false,
            channels:{leave:false,overtime:false,adjustments:false,timesheets:false,settlements:false}, note:'', pending:false,
            previews:{done:0,total:0}, scrollTop:0, viewHeight:600});
        // Built once: a new markup() per render re-inserts the SVG every redraw.
        this.icons = {remind: ic('calendarClock', 13), remindLarge: ic('calendarClock', 16), working: ic('loader', 12)};
        this.previewCache = new Map(); this.previewToken = 0;
        this.rowHeight = ROW_HEIGHT; this.byCode = {}; this.scrollFrame = 0;
        this.onResize = () => this.measure();
        onWillStart(()=>this.load());
        onMounted(()=>{ window.addEventListener('resize', this.onResize); this.measure(); });
        onWillUnmount(()=>{this.alive=false;this.previewToken++;window.removeEventListener('resize', this.onResize);
            if(this.scrollFrame)cancelAnimationFrame(this.scrollFrame);});
    }
    async load() {
        this.state.loading=true;
        try { this.previewCache.clear(); this.accept(await this.orm.call('pb.payrun.wizard','open_payroll_review',[this.props.payload],COMPACT)); }
        catch(e) { this.state.error=e.data?.message||e.message; }
        finally {this.state.loading=false; requestAnimationFrame(()=>this.measure());}
    }
    accept(data, changedIds=[]) {
        for(const id of changedIds) this.previewCache.delete(id);
        this.byCode = Object.fromEntries((data.columns||[]).map(c=>[c.code,c]));
        this.applyCachedPreviews(data);
        this.state.data=data;
        if(data.review?.certification) this.state.channels={...this.state.channels,...data.review.certification.channels};
        if(data.review?.settlement_no_activity) this.state.channels.settlements=true;
        this.state.note=data.review?.reason||this.state.note;
        if(this.state.selected) {
            const p=data.people.find(p=>p.employee_id===this.state.selected.employee_id);
            const col=this.byCode[this.state.selected.code];
            if(p&&col&&p.cells[col.code]) {
                this.state.selected=this.selection(p,col);
                // A paste or another save can change the selected cell: show the server's value.
                if(!this.state.pending) this.state.value=this.display(p.cells[col.code],col);
            }
        }
        this.fetchPreviews();
    }
    // A cell carries only what the grid draws; the column carries the rest.
    selection(person, col) {
        return {...person.cells[col.code], code:col.code, label:col.name, source_owner:col.source_owner,
                rule_id:col.id, employee_id:person.employee_id, person:person.name};
    }
    // ---- PDR P2 W1b: windowed rows ----
    measure() {
        const el=this.grid.el; if(!el)return;
        const row=el.querySelector('tbody tr.pr-row');
        if(row){const h=row.getBoundingClientRect().height; if(h>20)this.rowHeight=h;}
        this.state.viewHeight=el.clientHeight||600;
    }
    onGridScroll() {
        if(this.scrollFrame)return;
        this.scrollFrame=requestAnimationFrame(()=>{
            this.scrollFrame=0; const el=this.grid.el; if(!el)return;
            this.state.scrollTop=el.scrollTop;
            if(Math.abs(this.state.viewHeight-el.clientHeight)>4)this.measure();
        });
    }
    get rowWindow() {
        const total=this.people.length, h=this.rowHeight;
        const visible=Math.ceil((this.state.viewHeight||600)/h)+1;
        let start=Math.max(0,Math.floor(this.state.scrollTop/h)-OVERSCAN);
        start=Math.min(start,Math.max(0,total-visible-OVERSCAN));
        const end=Math.min(total,start+visible+2*OVERSCAN);
        return {start,end,top:start*h,bottom:(total-end)*h};
    }
    get windowPeople() {const w=this.rowWindow;return this.people.slice(w.start,w.end);}
    // Bring a row into the drawn window, then focus one of its cells.
    revealCell(person, col) {
        const index=this.people.indexOf(person), el=this.grid.el;
        if(index<0||!el)return;
        const top=index*this.rowHeight, bottom=top+this.rowHeight, head=el.querySelector('thead')?.offsetHeight||70;
        if(top<el.scrollTop||bottom>el.scrollTop+el.clientHeight-head)
            el.scrollTop=Math.max(0,top-Math.round(el.clientHeight/3));
        this.state.scrollTop=el.scrollTop;
        const focus=(tries)=>requestAnimationFrame(()=>{
            const cell=this.grid.el?.querySelector(`[data-cell="${person.employee_id}:${col.id}"]`);
            if(!cell){if(tries)focus(tries-1);return;}
            cell.scrollIntoView({block:'nearest',inline:'center'});cell.querySelector('input,button')?.focus();
        });
        focus(3);
    }
    // ---- PDR S3: calculation previews stream in after the grid ----
    resultColumns(data=this.state.data) {return (data?.columns||[]).filter(c=>c.group==='results');}
    isBlocked(person) {return Object.values(person.cells).some(c=>c.preview==='blocked');}
    fillPreview(person, preview, columns) {
        for(const col of columns) {
            const cell=person.cells[col.code]; if(!cell||cell.preview!=='pending')continue;
            cell.value=preview.values?.[col.code] ?? null; cell.preview='done';
        }
        const sel=this.state.selected;
        if(sel?.employee_id===person.employee_id && person.cells[sel.code]?.preview==='done' && this.byCode[sel.code])
            this.state.selected=this.selection(person,this.byCode[sel.code]);
    }
    applyCachedPreviews(data) {
        const columns=this.resultColumns(data);
        for(const person of data.people||[]) {
            const cached=this.previewCache.get(person.employee_id);
            if(!cached)continue;
            if(this.isBlocked(person)||cached.blocked){this.previewCache.delete(person.employee_id);continue;}
            this.fillPreview(person,cached,columns);
        }
    }
    async fetchPreviews() {
        const token=++this.previewToken, data=this.state.data;
        if(!data)return;
        const {id,revision}=data, columns=this.resultColumns(data);
        const wanted=data.people.filter(p=>Object.values(p.cells).some(c=>c.preview==='pending')).map(p=>p.employee_id);
        this.state.previews={done:0,total:wanted.length};
        for(let i=0;i<wanted.length;i+=PREVIEW_BATCH) {
            const batch=wanted.slice(i,i+PREVIEW_BATCH);
            let answer;
            try { answer=await this.orm.silent.call('hr.payroll.preparation','preview_rows',[[id],revision,batch]); }
            catch { answer=null; }   // a changed worksheet answers with its own refresh
            if(!this.alive||token!==this.previewToken||this.state.data?.revision!==revision)return;
            if(!answer)break;
            for(const [key,preview] of Object.entries(answer)) {
                const employeeId=Number(key);
                this.previewCache.set(employeeId,preview);
                const person=this.state.data.people.find(p=>p.employee_id===employeeId);
                if(person&&!preview.blocked)this.fillPreview(person,preview,columns);
            }
            this.state.previews.done=Math.min(wanted.length,i+batch.length);
        }
        if(token===this.previewToken)this.state.previews={done:0,total:0};
    }
    get previewText() {const p=this.state.previews;return p.total?_t('Working out previews · %(done)s of %(total)s',{done:p.done,total:p.total}):'';}
    get finalMonthPeople() {return (this.state.data?.people||[]).filter(p=>p.reminders?.length).length;}
    get reminderText() {
        const n=this.finalMonthPeople, names=(this.state.data?.reminder_columns||[]).join(', ')||_t('the final tax period');
        return n===1
            ? _t('1 person is in their final tax month — check %(names)s and the year-to-date figures.',{names})
            : _t('%(count)s people are in their final tax month — check %(names)s and the year-to-date figures.',{count:n,names});
    }
    showFinalMonth() {if(this.state.pending)return;this.state.query='';this.state.filter='final';}
    searchText(value) {return String(value||'').normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/đ/gi,'d').toLocaleLowerCase();}
    get groupedColumns() {return (this.state.data?.columns||[]).filter(c=>this.state.group==='all'||c.group===this.state.group);}
    get columns() {
        const words=this.searchText(this.state.componentQuery).trim().split(/\s+/).filter(Boolean);
        return this.groupedColumns.filter(c=>words.every(word=>this.searchText(`${c.name} ${c.code}`).includes(word)));
    }
    componentSearch(ev) {this.state.componentQuery=ev.target.value;this.columnsChanged();}
    clearComponentSearch() {this.state.componentQuery='';this.columnsChanged();}
    columnsChanged() {
        if(this.selected && !this.columns.some(c=>c.code===this.selected.code)) {
            this.state.selected=null;this.state.detail=null;
        }
        requestAnimationFrame(()=>{if(this.grid.el)this.grid.el.scrollLeft=0;});
    }
    get people() {
        const q=this.searchText(this.state.query);
        return (this.state.data?.people||[]).filter(p=>(!q||this.searchText(p.name).includes(q))&&
            (this.state.filter==='all'||(this.state.filter==='final'?p.reminders?.length:
             Object.values(p.cells).some(c=>this.state.filter==='issues'?c.issue:c.edit))));
    }
    get selected() {return this.state.selected;}
    get selectedColumn() {return this.selected?this.byCode[this.selected.code]:null;}
    get pendingFuture() { return (this.state.data?.people||[]).flatMap(p=>Object.values(p.cells)).filter(c=>c.edit?.scope==='future'&&!c.edit?.proposal_id).length; }
    get canReview() {return this.state.data&&!this.state.data.issues&&!this.state.data.global_issues.length&&!this.pendingFuture&&!this.state.saving&&!this.state.pending;}
    // ---- PDR P2 W1: words for a value (the stored number never changes) ----
    word(col, value) {
        if(value===null||value===undefined||value==='')return '';
        const n=Number(value);
        const hit=col?.labels?.length&&Number.isFinite(n)?col.labels.find(o=>Math.abs(o.value-n)<1e-9):null;
        return hit?hit.label:String(value);   // an unmatched number shows as itself
    }
    display(cell, col=this.byCode[cell?.code]) {
        return cell?.optional?'':cell?.value===null||cell?.value===undefined?'':this.word(col,cell.value);
    }
    cellText(person, col) {return this.display(person.cells[col.code],col);}
    // Text typed or pasted into a worded cell → the number to save, or an error sentence.
    toNumber(col, text) {
        const raw=String(text??'').trim();
        if(!col?.labels?.length||!raw)return {value:text};
        const t=raw.toLocaleLowerCase(), hit=col.labels.find(o=>o.label.trim().toLocaleLowerCase()===t);
        if(hit)return {value:String(hit.value)};
        if(/^-?\d+(\.\d+)?$/.test(raw))return {value:raw};
        if(col.control==='toggle') {
            if(['y','yes','true'].includes(t))return {value:'1'};
            if(['n','no','false'].includes(t))return {value:'0'};
        }
        const yesNo=col.labels.length===2&&col.labels.every(o=>['yes','no'].includes(o.label.trim().toLocaleLowerCase()));
        return {error: yesNo
            ? _t('%(name)s needs Y or N.',{name:col.name})
            : _t('%(name)s needs one of: %(words)s.',{name:col.name,words:col.labels.map(o=>o.label).join(', ')})};
    }
    pick(option) {
        if(!this.selected?.editable||this.state.saving)return;
        this.state.value=option.label; this.state.pending=true;
    }
    isPicked(option) {return String(this.state.value).trim().toLocaleLowerCase()===option.label.trim().toLocaleLowerCase();}
    pickFromSelect(ev) {const col=this.selectedColumn;const o=col?.labels.find(o=>o.label===ev.target.value);if(o)this.pick(o);}
    get selectedUnmatched() {
        const col=this.selectedColumn, v=String(this.state.value??'').trim();
        return v&&col?.labels?.length&&!col.labels.some(o=>o.label.trim().toLocaleLowerCase()===v.toLocaleLowerCase())?v:'';
    }
    status(cell) {return cell?.status==='preview'?(cell.preview==='pending'?_t('Working out…'):_t('Calculation preview')):cell?.issue?(cell.tone==='red'?_t('! Needs a value'):_t('! Review source')):cell?.remind?_t('Final tax month'):cell?.edit?_t('Edited for this run'):cell?.not_applicable?_t('Not used for this employee'):cell?.optional?_t('Optional · left blank'):cell?.usual_answer?_t('Usual answer · no contract line'):cell?.editable?_t('From records'):_t('Read only');}
    async select(person,col) {
        const cell=person.cells[col.code]; if(!cell)return;
        if(this.selected?.employee_id===person.employee_id && this.selected?.code===col.code)return;
        if(this.state.pending) { this.state.error=_t('Save or restore the current correction before selecting another cell.'); return; }
        this.state.selected=this.selection(person,col);
        this.state.value=this.display(cell,col); this.state.reason=cell.edit?.reason||''; this.state.scope=cell.edit?.scope||'run';
        this.state.detail=null;
        if(col.group==='results'){this.state.detail={explanation:_t('Calculation preview. Final payroll is computed after review.'),formula:col.formula,actions:[],consumers:[]};return;}
        try {
            const detail=await this.orm.call('hr.formula.config','application_source_detail',[[this.props.payload.formula_config_id],col.id]);
            if(this.selected?.code===col.code&&this.selected?.employee_id===person.employee_id) this.state.detail=detail;
        } catch(e){this.state.error=e.data?.message||e.message;}
    }
    async editCell(person,col,ev) {
        const value=ev.target.value, cell=person.cells[col.code];
        if(value===this.display(cell,col)){this.state.pending=false;return;}
        if(!cell.editable)return;
        if(this.selected?.employee_id!==person.employee_id||this.selected?.code!==col.code) await this.select(person,col);
        this.state.value=value; this.state.pending=true;
        await this.saveSelected();
    }
    inputCell(person,col,ev) {
        this.state.value=ev.target.value; this.state.pending=true;
    }
    cellValue(person,col) {
        return this.selected?.employee_id===person.employee_id && this.selected?.code===col.code
            ? this.state.value : this.display(person.cells[col.code],col);
    }
    historyChanges(event) {
        return (event.data?.changes||[]).map(change=>{
            const col=this.byCode[change.code];
            const before=change.before?.value ?? change.after?.original, after=change.after?.value;
            return {
                person:this.state.data.people.find(p=>p.employee_id===change.employee_id)?.name||_t('Employee'),
                item:col?.name||change.code,
                before:before===undefined||before===null?_t('No amount'):this.word(col,before),
                after:after===undefined||after===null?_t('Restored source'):this.word(col,after), reason:change.after?.reason||'',
            };
        });
    }
    changed() {this.state.pending=true;}
    async transact(method,args=[],changedIds=[]) {
        this.state.saving=true; this.state.error='';
        try {
            const data=await this.orm.call('hr.payroll.preparation',method,[[this.state.data.id],this.state.data.revision,...args],COMPACT);
            if(this.alive)this.accept(data,changedIds);
            return data;
        } catch(e){if(this.alive)this.state.error=e.data?.message||e.message;return null;}
        finally{if(this.alive)this.state.saving=false;}
    }
    blankIgnored(col, cell, value) {
        return (col?.optional || cell?.not_applicable) && col?.kind!=='text' && !String(value ?? '').trim();
    }
    async saveSelected() {
        if(this.state.saving)return;
        const cell=this.selected, col=this.selectedColumn;
        if(this.blankIgnored(col,cell,this.state.value)){this.state.pending=false;this.state.value=this.display(cell,col);this.state.error='';return;}
        const wire=this.toNumber(col,this.state.value);
        if(wire.error){this.state.error=wire.error;return;}
        const data=await this.transact('save_cells',[crypto.randomUUID(),[{employee_id:cell.employee_id,code:cell.code,
            value:wire.value,reason:this.state.reason,scope:this.state.scope}]],[cell.employee_id]);
        if(data){this.state.pending=false;this.state.value=this.display(this.selected,this.selectedColumn);}
    }
    async restore() {
        if(this.state.pending) {this.state.pending=false;this.state.value=this.display(this.selected,this.selectedColumn);this.state.error='';return;}
        const c=this.selected;
        await this.transact('save_cells',[crypto.randomUUID(),[{employee_id:c.employee_id,code:c.code,restore:true}]],[c.employee_id]);
        this.state.value=this.display(this.selected,this.selectedColumn);
    }
    async paste(person,col,ev) {
        const text=ev.clipboardData.getData('text/plain');
        if(!text.includes('\t')&&!text.includes('\n'))return;
        ev.preventDefault();
        if(this.state.pending||this.state.saving){this.state.error=_t('Save the current correction before pasting a range.');return;}
        if(!this.state.reason.trim()) {this.state.error=_t('Add a reason in the source panel before pasting a range.');return;}
        const people=this.people, columns=this.columns;
        const ri=people.indexOf(person), ci=columns.indexOf(col), changes=[];
        for(const [dy,line] of text.replace(/\r/g,'').replace(/\n$/,'').split('\n').entries()) {
            for(const [dx,value] of line.split('\t').entries()) {
                const p=people[ri+dy],c=columns[ci+dx],cell=p?.cells[c?.code];
                if(cell?.editable && this.blankIgnored(c,cell,value))continue;
                if(!cell?.editable||!value.trim()) {this.state.error=_t('Paste includes a blank, protected cell or a cell outside this view. Nothing was saved.');return;}
                const wire=this.toNumber(c,value);
                if(wire.error){this.state.error=_t('%(person)s · %(error)s Nothing was saved.',{person:p.name,error:wire.error});return;}
                changes.push({employee_id:p.employee_id,code:c.code,value:wire.value,scope:'run',reason:this.state.reason});
            }
        }
        if(changes.length)await this.transact('save_cells',[crypto.randomUUID(),changes],[...new Set(changes.map(c=>c.employee_id))]);
    }
    nextIssue() {
        if(this.state.pending){this.state.error=_t('Save or restore the current correction first.');return;}
        const issues=this.state.data.people.flatMap(p=>this.state.data.columns.filter(c=>p.cells[c.code]?.issue).map(c=>({p,c})));
        if(!issues.length)return;
        const i=issues.findIndex(v=>v.p.employee_id===this.selected?.employee_id&&v.c.code===this.selected?.code);
        const {p,c}=issues[(i+1)%issues.length];this.state.query='';this.state.componentQuery='';this.state.filter='issues';this.state.group='all';
        this.select(p,c);
        requestAnimationFrame(()=>this.revealCell(p,c));
    }
    async openSource(model) {
        if(this.state.pending){this.state.error=_t('Save or restore your correction before opening a source record.');return;}
        const c=this.selected;
        try {
            const action=await this.orm.call('hr.formula.config','application_source_record_action',[[this.props.payload.formula_config_id],c.rule_id,model,c.employee_id,...this.state.data.period]);
            await this.action.doAction({...action,target:'new'},{onClose:()=>this.load()});
        }catch(e){this.state.error=e.data?.message||e.message;}
    }
    async openRecordProposal() {
        const id=this.selected?.edit?.proposal_id;
        if(!id)return;
        try {
            await this.action.doAction({type:'ir.actions.act_window',name:_t('Saved-record change'),
                res_model:'pb.records.apply',res_id:id,views:[[false,'form']],target:'new'},
                {onClose:()=>this.load()});
        }catch(e){this.state.error=e.data?.message||e.message;}
    }
    submitFuture() {
        this.dialog.add(ConfirmationDialog,{title:_t('Update saved records on approval?'),
            body:_t('Submit %(count)s saved-record changes through Records Desk approval. These will affect future payrolls once approved. Current records remain unchanged until approval.',{count:this.pendingFuture}),
            confirm:()=>this.transact('submit_record_changes'),confirmLabel:_t('Submit record changes')});
    }
    async finish() {
        const data=await this.transact('review',[this.state.channels,this.state.note]);
        if(data?.ready){this.props.onReviewed(data);this.props.close();}
    }
    closeSaved() {
        if(this.state.pending||this.state.saving){this.state.error=_t('Save or restore your current correction before closing.');return;}
        if(this.state.data?.ready)this.props.onReviewed(this.state.data);
        this.props.close();
    }
    keydown(ev) {
        if(ev.key==='Enter'&&ev.target.tagName==='INPUT') {ev.preventDefault();ev.target.blur();}
    }
}
