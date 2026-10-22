/** @odoo-module **/
import { Component, useState, onWillStart, useRef, onWillUnmount } from '@odoo/owl';
import { Dialog } from '@web/core/dialog/dialog';
import { useService } from '@web/core/utils/hooks';
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';

export class PayrollReviewDialog extends Component {
    static template = 'pb_payrun_wizard.PayrollReviewDialog';
    static components = { Dialog };
    static props = { payload: Object, onReviewed: Function, close: Function };
    setup() {
        this.orm = useService('orm'); this.action = useService('action'); this.dialog = useService('dialog');
        this.grid = useRef('grid'); this.alive = true;
        this.state = useState({data:null, loading:true, saving:false, error:'', query:'', filter:'all', group:'all',
            selected:null, detail:null, value:'', reason:'', scope:'run', review:false, history:false, maximized:false,
            channels:{leave:false,overtime:false,adjustments:false,timesheets:false}, note:'', pending:false});
        onWillStart(()=>this.load());
        onWillUnmount(()=>{this.alive=false;});
    }
    async load() {
        this.state.loading=true;
        try { this.accept(await this.orm.call('pb.payrun.wizard','open_payroll_review',[this.props.payload])); }
        catch(e) { this.state.error=e.data?.message||e.message; }
        finally {this.state.loading=false;}
    }
    accept(data) {
        this.state.data=data;
        if(data.review?.certification) this.state.channels={...this.state.channels,...data.review.certification.channels};
        this.state.note=data.review?.reason||this.state.note;
        if(this.state.selected) {
            const p=data.people.find(p=>p.employee_id===this.state.selected.employee_id);
            const cell=p?.cells[this.state.selected.code];
            if(cell) this.state.selected={...cell,employee_id:p.employee_id,person:p.name};
        }
    }
    get columns() { return (this.state.data?.columns||[]).filter(c=>this.state.group==='all'?c.group!=='results':c.group===this.state.group); }
    get people() {
        const q=this.state.query.toLocaleLowerCase();
        return (this.state.data?.people||[]).filter(p=>(!q||p.name.toLocaleLowerCase().includes(q))&&
            (this.state.filter==='all'||Object.values(p.cells).some(c=>this.state.filter==='issues'?c.issue:c.edit)));
    }
    get selected() {return this.state.selected;}
    get pendingFuture() { return (this.state.data?.people||[]).flatMap(p=>Object.values(p.cells)).filter(c=>c.edit?.scope==='future'&&!c.edit?.proposal_id).length; }
    get canReview() {return this.state.data&&!this.state.data.issues&&!this.state.data.global_issues.length&&!this.pendingFuture&&!this.state.saving&&!this.state.pending;}
    display(cell) { return cell?.optional?'—':cell?.value===null||cell?.value===undefined?'':String(cell.value); }
    status(cell) {return cell?.status==='preview'?'Calculation preview':cell?.issue?(cell.tone==='red'?'! Needs a value':'! Review source'):cell?.edit?'Edited for this run':cell?.optional?'No amount · uses zero':cell?.editable?'From records':'Read only';}
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
    async transact(method,args=[]) {
        this.state.saving=true; this.state.error='';
        try {
            const data=await this.orm.call('hr.payroll.preparation',method,[[this.state.data.id],this.state.data.revision,...args]);
            if(this.alive)this.accept(data);
            return data;
        } catch(e){if(this.alive)this.state.error=e.data?.message||e.message;return null;}
        finally{if(this.alive)this.state.saving=false;}
    }
    async saveSelected() {
        if(this.state.saving)return;
        const cell=this.selected;
        const data=await this.transact('save_cells',[crypto.randomUUID(),[{employee_id:cell.employee_id,code:cell.code,
            value:this.state.value,reason:this.state.reason,scope:this.state.scope}]]);
        if(data){this.state.pending=false;this.state.value=this.display(this.selected);}
    }
    async restore() {
        if(this.state.pending) {this.state.pending=false;this.state.value=this.display(this.selected);this.state.error='';return;}
        const c=this.selected;
        await this.transact('save_cells',[crypto.randomUUID(),[{employee_id:c.employee_id,code:c.code,restore:true}]]);
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
                if(!cell?.editable||!value.trim()) {this.state.error='Paste includes a blank, protected cell or a cell outside this view. Nothing was saved.';return;}
                changes.push({employee_id:p.employee_id,code:c.code,value,scope:'run',reason:this.state.reason});
            }
        }
        await this.transact('save_cells',[crypto.randomUUID(),changes]);
    }
    nextIssue() {
        if(this.state.pending){this.state.error='Save or restore the current correction first.';return;}
        const issues=this.state.data.people.flatMap(p=>this.state.data.columns.filter(c=>p.cells[c.code]?.issue).map(c=>({p,c})));
        if(!issues.length)return;
        const i=issues.findIndex(v=>v.p.employee_id===this.selected?.employee_id&&v.c.code===this.selected?.code);
        const {p,c}=issues[(i+1)%issues.length];this.state.query='';this.state.filter='issues';this.state.group='all';
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
