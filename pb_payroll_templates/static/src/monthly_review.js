/** @odoo-module **/
import { Component, useState, useRef } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';
import { Dialog } from '@web/core/dialog/dialog';
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';

const text = v => String(v ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/gi,'d').toLowerCase().trim();
const numeric = k => ['money','decimal','integer','quantity','rate'].includes(k);
export function columnLetter(index) {
    let result='';for(let n=index+1;n;n=Math.floor((n-1)/26))result=String.fromCharCode(65+(n-1)%26)+result;return result;
}
export function reviewValue(raw, kind) {
    if(raw===null||raw===undefined||raw==='')return {value:null,error:''};
    if(String(raw).trim().startsWith('=')||String(raw).trim().startsWith('@'))return {value:raw,error:'Enter a value, not a formula.'};
    if(numeric(kind)){
        const n=Number(raw);return Number.isFinite(n)&&(kind!=='integer'||Number.isInteger(n))?{value:n,error:''}:{value:raw,error:kind==='integer'?'Enter a whole number.':'Enter a valid number.'};
    }
    if(kind==='boolean'){
        const v=String(raw).toLowerCase().trim();
        if(['true','yes','1'].includes(v))return {value:true,error:''};
        if(['false','no','0'].includes(v))return {value:false,error:''};
        return {value:raw,error:'Enter Yes or No.'};
    }
    if(kind==='date'&&!/^\d{4}-\d{2}-\d{2}$/.test(String(raw)))return {value:raw,error:'Use YYYY-MM-DD.'};
    return {value:String(raw),error:''};
}

export class MonthlyInputReview extends Component {
    static template='pb_payroll_templates.MonthlyReview';
    static components={Dialog};
    static props={data:Object, configId:Number, onApplied:Function, close:Function};
    setup(){
        this.gridRef=useRef('grid');this.orm=useService('orm');this.dialog=useService('dialog');this.notification=useService('notification');
        this.original=JSON.parse(JSON.stringify(this.props.data));
        this.state=useState({data:JSON.parse(JSON.stringify(this.props.data)),busy:false,error:'',expanded:false,query:'',fieldQuery:'',tab:'all',filter:'all',page:0,active:null,edits:{},updateRecords:false});
    }
    get data(){return this.state.data;}
    get columns(){
        const q=text(this.state.fieldQuery);
        return this.data.grid.columns.filter(c=>(this.state.tab==='all'||c.tab===this.state.tab)&&(!q||text(c.label+' '+c.code).includes(q)));
    }
    cellMatches(cell){return this.state.filter==='all'||(this.state.filter==='changed'&&cell.changed)||(this.state.filter==='issues'&&(cell.issue||cell.missing))||(this.state.filter==='edited'&&cell.source==='edited');}
    get filteredRows(){
        const q=text(this.state.query),cols=this.columns;
        return this.data.grid.rows.filter(r=>(!q||text(r.name+' '+r.code).includes(q))&&cols.some(c=>this.cellMatches(r.cells[c.id])));
    }
    get rows(){return this.filteredRows.slice(this.state.page*40,(this.state.page+1)*40);}
    get pages(){return Math.max(1,Math.ceil(this.filteredRows.length/40));}
    get stats(){
        const s={changed:0,people:0,excel:0,system:0,edited:0,issues:0,missing:0,compared:0};
        for(const r of this.data.grid.rows){let moved=false;for(const c of this.data.grid.columns){const v=r.cells[c.id];s.changed+=Number(v.changed);moved=moved||v.changed;s[v.source==='excel'?'excel':v.source==='edited'?'edited':'system']++;s.issues+=Number(!!v.issue);s.missing+=Number(!!v.missing);s.compared+=Number(v.has_prior);}s.people+=Number(moved);}return s;
    }
    get editCount(){return Object.keys(this.state.edits).length;}
    get canConfirm(){return !this.state.busy&&!this.stats.issues&&!this.stats.missing&&!this.data.structural_issues.length;}
    get active(){if(!this.state.active)return null;const {eid,fid}=this.state.active;return {row:this.data.grid.rows.find(r=>r.emp_id===eid),column:this.data.grid.columns.find(c=>c.id===fid)};}
    get activeCell(){const a=this.active;return a?.row.cells[a.column.id];}
    format(v){return v===null||v===undefined||v===''?'Not available':typeof v==='number'?v.toLocaleString(undefined,{maximumFractionDigits:4}):typeof v==='boolean'?(v?'Yes':'No'):String(v);}
    inputValue(v){return v===null||v===undefined?'':typeof v==='boolean'?(v?'Yes':'No'):String(v);}
    period(v){const [y,m]=v.split('-');return new Date(Number(y),Number(m)-1,1).toLocaleDateString(undefined,{month:'long',year:'numeric'});}
    sourceLabel(cell){return {excel:'Excel',system:'System',edited:'Edited',default:'Default'}[cell.source]||'System';}
    baselineLabel(cell){return {finalized_payroll:'Finalized payroll',computed_payroll:'Computed payroll · not finalized',saved_inputs:'Saved monthly inputs',reviewed_inputs:'Reviewed monthly inputs'}[cell.baseline_kind]||'No previous-month value';}
    letter(i){return columnLetter(i+2);}
    unit(c){return {money:this.data.currency||'Amount',quantity:'Quantity',integer:'Whole number',decimal:'Number',rate:'%',date:'YYYY-MM-DD',boolean:'Yes / No',text:'Text',identifier:'Reference'}[c.kind]||'';}
    cellClass(cell){return `pt-grid-cell source-${cell.source}${cell.changed?' is-changed':''}${cell.issue||cell.missing?' has-issue':''}${!this.cellMatches(cell)?' is-muted':''}`;}
    cellTitle(c,cell){return `${c.label}\n${this.sourceLabel(cell)} · ${cell.detail}\n${cell.has_prior?this.period(this.data.previous_period)+': '+this.format(cell.prior):'No previous-month value'}${cell.issue?'\n'+cell.issue:''}`;}
    focus(row,c){this.state.active={eid:row.emp_id,fid:c.id};}
    edit(row,c,raw){
        const cell=row.cells[c.id],parsed=reviewValue(raw,c.kind);
        Object.assign(cell,{value:parsed.value,source:'edited',detail:'Edited in review · this month only',issue:parsed.error,missing:c.required&&parsed.value===null});
        if(c.positive&&parsed.value!==null&&Number(parsed.value)<=0)cell.issue='Enter a number greater than zero.';
        cell.changed=cell.has_prior&&cell.value!==cell.prior;
        this.state.edits[`${row.emp_id}:${c.id}`]={emp_id:row.emp_id,field_id:c.id,value:parsed.value};
    }
    paste(ri,ci,ev){
        const raw=ev.clipboardData.getData('text/plain');
        if(!/[\t\n]/.test(raw))return;
        ev.preventDefault();
        const rows=[...this.rows],columns=[...this.columns];
        const lines=raw.replace(/\r/g,'').replace(/\n$/,'').split('\n');
        for(let y=0;y<lines.length;y++){const row=rows[ri+y];if(!row)break;const values=lines[y].split('\t');for(let x=0;x<values.length;x++){const col=columns[ci+x];if(col)this.edit(row,col,values[x]);}}
    }
    keydown(ri,ci,ev){
        if(ev.key!=='Enter')return;ev.preventDefault();
        this.gridRef.el.querySelector(`input[data-row="${ri+(ev.shiftKey?-1:1)}"][data-col="${ci}"]`)?.focus();
    }
    finishEdit(row,c){const cell=row.cells[c.id];if(cell.value===null&&cell.current!==null&&cell.current!==undefined)this.edit(row,c,cell.current);}
    onInput(row,c,ev){this.edit(row,c,ev.target.value);}
    restoreActive(){const a=this.active;if(!a)return;const initial=this.original.grid.rows.find(r=>r.emp_id===a.row.emp_id).cells[a.column.id];Object.assign(this.activeCell,JSON.parse(JSON.stringify(initial)));delete this.state.edits[`${a.row.emp_id}:${a.column.id}`];}
    reset(){for(const r of this.data.grid.rows){const original=this.original.grid.rows.find(o=>o.emp_id===r.emp_id);r.cells=JSON.parse(JSON.stringify(original.cells));}this.state.edits={};this.state.error='';}
    setFilter(value){this.state.filter=value;this.state.page=0;}
    setTab(value){this.state.tab=value;this.state.page=0;}
    search(key,ev){this.state[key]=ev.target.value;this.state.page=0;}
    close(){
        if(!this.editCount)return this.props.close();
        this.dialog.add(ConfirmationDialog,{title:'Discard review edits?',body:'Edits in this review have not been applied. Close and discard them?',confirmLabel:'Discard edits',confirm:()=>this.props.close()});
    }
    async confirm(){
        if(!this.canConfirm)return;
        this.state.busy=true;this.state.error='';
        try{
            const result=await this.orm.call('pb.payroll.templates','confirm_monthly_review',[this.props.configId,this.data.token,Object.values(this.state.edits),this.state.updateRecords]);
            // Once saved, retries must refresh from the applied receipt rather
            // than attempting to consume the single-use review token again.
            this.state.edits={};
            if(result.record_update){const r=result.record_update;this.notification.add(r.pending?'Master-record changes submitted for approval'+(r.reference?' · '+r.reference:''):'Mapped master records updated',{type:r.pending?'info':'success'});}
            await this.props.onApplied(result);this.props.close();
        }catch(e){this.state.error=e?.data?.message||e.message||'Please try again.';}finally{this.state.busy=false;}
    }
}
