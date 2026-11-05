/** @odoo-module **/
import { Component, useState, onWillStart, useRef, onWillUnmount } from '@odoo/owl';
import { Dialog } from '@web/core/dialog/dialog';
import { useService } from '@web/core/utils/hooks';
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';
import { ic } from '@pb_import_kit/js/import_icons';

// PDR S3 — previews are worked out after the grid renders, 20 people a call.
const PREVIEW_BATCH = 20;

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
            previews:{done:0,total:0}});
        // Built once: a new markup() per render re-inserts the SVG every redraw.
        this.icons = {remind: ic('calendarClock', 13), remindLarge: ic('calendarClock', 16), working: ic('loader', 12)};
        this.previewCache = new Map(); this.previewToken = 0;
        onWillStart(()=>this.load());
        onWillUnmount(()=>{this.alive=false;this.previewToken++;});
    }
    async load() {
        this.state.loading=true;
        try { this.previewCache.clear(); this.accept(await this.orm.call('pb.payrun.wizard','open_payroll_review',[this.props.payload])); }
        catch(e) { this.state.error=e.data?.message||e.message; }
        finally {this.state.loading=false;}
    }
    accept(data, changedIds=[]) {
        for(const id of changedIds) this.previewCache.delete(id);
        this.applyCachedPreviews(data);
        this.state.data=data;
        if(data.review?.certification) this.state.channels={...this.state.channels,...data.review.certification.channels};
        if(data.review?.settlement_no_activity) this.state.channels.settlements=true;
        this.state.note=data.review?.reason||this.state.note;
        if(this.state.selected) {
            const p=data.people.find(p=>p.employee_id===this.state.selected.employee_id);
            const cell=p?.cells[this.state.selected.code];
            if(cell) this.state.selected={...cell,employee_id:p.employee_id,person:p.name};
        }
        this.fetchPreviews();
    }
    // ---- PDR S3: calculation previews stream in after the grid ----
    resultColumns(data=this.state.data) {return (data?.columns||[]).filter(c=>c.group==='results');}
    isBlocked(person) {return Object.values(person.cells).some(c=>c.preview==='blocked');}
    fillPreview(person, preview, columns) {
        for(const col of columns) {
            const cell=person.cells[col.code]; if(!cell||cell.preview!=='pending')continue;
            cell.value=preview.values?.[col.code] ?? null; cell.preview='done';
        }
        if(this.state.selected?.employee_id===person.employee_id && person.cells[this.state.selected.code]?.preview==='done')
            this.state.selected={...person.cells[this.state.selected.code],employee_id:person.employee_id,person:person.name};
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
    get previewText() {const p=this.state.previews;return p.total?`Working out previews · ${p.done} of ${p.total}`:'';}
    get finalMonthPeople() {return (this.state.data?.people||[]).filter(p=>p.reminders?.length).length;}
    get reminderText() {
        const n=this.finalMonthPeople, names=(this.state.data?.reminder_columns||[]).join(', ')||'the final tax period';
        return `${n} ${n===1?'person is':'people are'} in their final tax month — check ${names} and the year-to-date figures.`;
    }
    showFinalMonth() {if(this.state.pending)return;this.state.query='';this.state.filter='final';}
    searchText(value) {return String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/gi,'d').toLocaleLowerCase();}
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
    get pendingFuture() { return (this.state.data?.people||[]).flatMap(p=>Object.values(p.cells)).filter(c=>c.edit?.scope==='future'&&!c.edit?.proposal_id).length; }
    get canReview() {return this.state.data&&!this.state.data.issues&&!this.state.data.global_issues.length&&!this.pendingFuture&&!this.state.saving&&!this.state.pending;}
    display(cell) { return cell?.optional?'':cell?.value===null||cell?.value===undefined?'':String(cell.value); }
    status(cell) {return cell?.status==='preview'?(cell.preview==='pending'?'Working out…':'Calculation preview'):cell?.issue?(cell.tone==='red'?'! Needs a value':'! Review source'):cell?.remind?'Final tax month':cell?.edit?'Edited for this run':cell?.not_applicable?'Not used for this employee':cell?.optional?'Optional · left blank':cell?.usual_answer?'Usual answer · no contract line':cell?.editable?'From records':'Read only';}
    async select(person,col) {
        const cell=person.cells[col.code]; if(!cell)return;
        if(this.selected?.employee_id===person.employee_id && this.selected?.code===col.code)return;
        if(this.state.pending) { this.state.error='Save or restore the current correction before selecting another cell.'; return; }
        this.state.selected={...cell,employee_id:person.employee_id,person:person.name};
        this.state.value=this.display(cell); this.state.reason=cell.edit?.reason||''; this.state.scope=cell.edit?.scope||'run';
        this.state.detail=null;
        if(col.group==='results'){this.state.detail={explanation:'Calculation preview. Final payroll is computed after review.',formula:col.formula,actions:[],consumers:[]};return;}
        try {
            const detail=await this.orm.call('hr.formula.config','application_source_detail',[[this.props.payload.formula_config_id],col.id]);
            if(this.selected?.code===col.code&&this.selected?.employee_id===person.employee_id) this.state.detail=detail;
        } catch(e){this.state.error=e.data?.message||e.message;}
    }
    async editCell(person,col,ev) {
        const value=ev.target.value, cell=person.cells[col.code];
        if(value===this.display(cell)){this.state.pending=false;return;}
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
            ? this.state.value : this.display(person.cells[col.code]);
    }
    historyChanges(event) {
        return (event.data?.changes||[]).map(change=>({
            person:this.state.data.people.find(p=>p.employee_id===change.employee_id)?.name||'Employee',
            item:this.state.data.columns.find(c=>c.code===change.code)?.name||change.code,
            before:change.before?.value ?? change.after?.original ?? 'No amount',
            after:change.after?.value ?? 'Restored source', reason:change.after?.reason||'',
        }));
    }
    changed() {this.state.pending=true;}
    async transact(method,args=[],changedIds=[]) {
        this.state.saving=true; this.state.error='';
        try {
            const data=await this.orm.call('hr.payroll.preparation',method,[[this.state.data.id],this.state.data.revision,...args]);
            if(this.alive)this.accept(data,changedIds);
            return data;
        } catch(e){if(this.alive)this.state.error=e.data?.message||e.message;return null;}
        finally{if(this.alive)this.state.saving=false;}
    }
    blankIgnored(cell, value) {
        const col=this.state.data.columns.find(c=>c.code===cell.code);
        return (col?.optional || cell.not_applicable) && col?.kind!=='text' && !String(value ?? '').trim();
    }
    async saveSelected() {
        if(this.state.saving)return;
        const cell=this.selected;
        if(this.blankIgnored(cell,this.state.value)){this.state.pending=false;this.state.value=this.display(cell);this.state.error='';return;}
        const data=await this.transact('save_cells',[crypto.randomUUID(),[{employee_id:cell.employee_id,code:cell.code,
            value:this.state.value,reason:this.state.reason,scope:this.state.scope}]],[cell.employee_id]);
        if(data){this.state.pending=false;this.state.value=this.display(this.selected);}
    }
    async restore() {
        if(this.state.pending) {this.state.pending=false;this.state.value=this.display(this.selected);this.state.error='';return;}
        const c=this.selected;
        await this.transact('save_cells',[crypto.randomUUID(),[{employee_id:c.employee_id,code:c.code,restore:true}]],[c.employee_id]);
        this.state.value=this.display(this.selected);
    }
    async paste(person,col,ev) {
        const text=ev.clipboardData.getData('text/plain');
        if(!text.includes('\t')&&!text.includes('\n'))return;
        ev.preventDefault();
        if(this.state.pending||this.state.saving){this.state.error='Save the current correction before pasting a range.';return;}
        if(!this.state.reason.trim()) {this.state.error='Add a reason in the source panel before pasting a range.';return;}
        const ri=this.people.indexOf(person), ci=this.columns.indexOf(col), changes=[];
        for(const [dy,line] of text.replace(/\r/g,'').replace(/\n$/,'').split('\n').entries()) {
            for(const [dx,value] of line.split('\t').entries()) {
                const p=this.people[ri+dy],c=this.columns[ci+dx],cell=p?.cells[c?.code];
                if(cell?.editable && this.blankIgnored(cell,value))continue;
                if(!cell?.editable||!value.trim()) {this.state.error='Paste includes a blank, protected cell or a cell outside this view. Nothing was saved.';return;}
                changes.push({employee_id:p.employee_id,code:c.code,value,scope:'run',reason:this.state.reason});
            }
        }
        if(changes.length)await this.transact('save_cells',[crypto.randomUUID(),changes],[...new Set(changes.map(c=>c.employee_id))]);
    }
    nextIssue() {
        if(this.state.pending){this.state.error='Save or restore the current correction first.';return;}
        const issues=this.state.data.people.flatMap(p=>this.state.data.columns.filter(c=>p.cells[c.code]?.issue).map(c=>({p,c})));
        if(!issues.length)return;
        const i=issues.findIndex(v=>v.p.employee_id===this.selected?.employee_id&&v.c.code===this.selected?.code);
        const {p,c}=issues[(i+1)%issues.length];this.state.query='';this.state.componentQuery='';this.state.filter='issues';this.state.group='all';
        this.select(p,c);
        requestAnimationFrame(()=>{const el=this.grid.el?.querySelector(`[data-cell="${p.employee_id}:${c.id}"]`);el?.scrollIntoView({block:'nearest',inline:'center'});el?.querySelector('input,button')?.focus();});
    }
    async openSource(model) {
        if(this.state.pending){this.state.error='Save or restore your correction before opening a source record.';return;}
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
            await this.action.doAction({type:'ir.actions.act_window',name:'Saved-record change',
                res_model:'pb.records.apply',res_id:id,views:[[false,'form']],target:'new'},
                {onClose:()=>this.load()});
        }catch(e){this.state.error=e.data?.message||e.message;}
    }
    submitFuture() {
        this.dialog.add(ConfirmationDialog,{title:'Update saved records on approval?',
            body:`Submit ${this.pendingFuture} saved-record changes through Records Desk approval. These will affect future payrolls once approved. Current records remain unchanged until approval.`,
            confirm:()=>this.transact('submit_record_changes'),confirmLabel:'Submit record changes'});
    }
    async finish() {
        const data=await this.transact('review',[this.state.channels,this.state.note]);
        if(data?.ready){this.props.onReviewed(data);this.props.close();}
    }
    closeSaved() {
        if(this.state.pending||this.state.saving){this.state.error='Save or restore your current correction before closing.';return;}
        if(this.state.data?.ready)this.props.onReviewed(this.state.data);
        this.props.close();
    }
    keydown(ev) {
        if(ev.key==='Enter'&&ev.target.tagName==='INPUT') {ev.preventDefault();ev.target.blur();}
    }
}
