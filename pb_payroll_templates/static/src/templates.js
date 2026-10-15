/** @odoo-module **/
import { Component, useState, onWillStart, useRef } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { patch } from '@web/core/utils/patch';
import { Dialog } from '@web/core/dialog/dialog';
import { PbFormulaStudio } from '@pb_formula_studio/js/formula_studio';
import { PayrunWizard } from '@pb_payrun_wizard/js/payrun_wizard';
import { ic } from '@pb_import_kit/js/import_icons';

function saveFile(res) {
    const bytes = Uint8Array.from(atob(res.file_b64), c => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], {type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}));
    const a = document.createElement('a'); a.href=url; a.download=res.filename; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
}
const fileData = f => new Promise((resolve, reject) => {
    const r=new FileReader(); r.onload=()=>resolve(String(r.result).split(',')[1]); r.onerror=reject; r.readAsDataURL(f);
});
const month = () => { const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`; };
const message = e => e?.data?.message || e?.message || 'Please try again.';
export function moveField(layout, id, lane, before='') {
    const next=JSON.parse(JSON.stringify(layout));
    for(const key of Object.keys(next)) next[key]=next[key].filter(i=>i!==id);
    const at=before?next[lane].indexOf(before):-1;
    next[lane].splice(at<0?next[lane].length:at,0,id); return next;
}

export class WorkbookReview extends Component {
    static template='pb_payroll_templates.Review';
    static components={Dialog};
    static props={data:Object, configId:Number, onApplied:Function, close:Function};
    setup(){
        this.orm=useService('orm');
        this.state=useState({busy:false,error:'',result:null,selected:this.props.data.changes.map(c=>c.key)});
    }
    ic=ic;
    value(v){ return v===null||v===undefined||v===''?'Not entered':typeof v==='number'?v.toLocaleString(undefined,{maximumFractionDigits:4}):String(v); }
    toggle(key){const i=this.state.selected.indexOf(key);if(i<0)this.state.selected.push(key);else this.state.selected.splice(i,1);}
    async confirm(){
        if(this.state.busy)return;
        this.state.busy=true;this.state.error='';
        try{
            this.state.result=await this.orm.call('pb.payroll.templates','confirm',[this.props.configId,this.props.data.token,[...this.state.selected]]);
            await this.props.onApplied(this.state.result);
        }catch(e){this.state.error=message(e);}finally{this.state.busy=false;}
    }
    async useCurrent(){
        this.state.busy=true;this.state.error='';
        try{await this.props.onApplied({ok:true,written:0,pending:false});this.state.result={written:0,pending:false};}
        catch(e){this.state.error=message(e);}finally{this.state.busy=false;}
    }
}

export class PayrollTemplates extends Component {
    static template='pb_payroll_templates.Workspace';
    static props={'*':true};
    setup(){
        this.orm=useService('orm');this.action=useService('action');this.dialog=useService('dialog');this.notif=useService('notification');
        const ctx=this.props.action?.context||{};
        this.state=useState({busy:false,error:'',data:null,screen:'downloads',period:ctx.templates_period||month(),configId:ctx.templates_config_id||0,layout:{time:[],adjustments:[],available:[]},dirty:false,menu:'',query:'',preview:'time'});
        this.dragged='';
        this.fileRef=useRef('file');
        onWillStart(()=>this.load());
    }
    ic=ic;
    async load(){
        const sequence=this.loadSequence=(this.loadSequence||0)+1;
        this.state.busy=true;this.state.error='';
        try{
            const d=await this.orm.call('pb.payroll.templates','workspace',[Number(this.state.configId),this.state.period]);
            if(sequence!==this.loadSequence)return;
            this.state.data=d;this.state.configId=d.config_id||0;this.state.layout=JSON.parse(JSON.stringify(d.layout));this.state.dirty=false;
        }catch(e){if(sequence===this.loadSequence)this.state.error=message(e);}finally{if(sequence===this.loadSequence)this.state.busy=false;}
    }
    get config(){return this.state.data?.configs.find(c=>c.id===Number(this.state.configId))||{};}
    get fields(){return Object.fromEntries((this.state.data?.fields||[]).map(f=>[f.id,f]));}
    fieldsIn(lane){return (this.state.layout[lane]||[]).map(i=>this.fields[i]).filter(f=>f && (lane!=='available'||`${f.label} ${f.code}`.toLowerCase().includes(this.state.query.toLowerCase())));}
    get monthlyCount(){return this.state.layout.time.length+this.state.layout.adjustments.length;}
    unit(f){
        if(/hours?|\bhrs?\b|giờ/i.test(f.label))return 'Hours';
        if(/days?|ngày/i.test(f.label))return 'Days';
        return {money:this.state.data.currency,quantity:'Quantity',integer:'Whole number',decimal:'Number',rate:'%',text:'Text',identifier:'Reference',date:'Date',boolean:'Yes / No'}[f.kind]||'';
    }
    async changeConfig(ev){this.state.configId=Number(ev.target.value);await this.load();}
    async changeMonth(ev){this.state.period=ev.target.value;await this.load();}
    show(screen){this.state.screen=screen;this.state.menu='';}
    async download(mode){
        if(this.state.busy)return;this.state.busy=true;this.state.error='';
        try{saveFile(await this.orm.call('pb.payroll.templates','download',[this.state.configId,this.state.period,mode]));this.notif.add('Workbook downloaded with the latest saved data.',{type:'success'});}
        catch(e){this.state.error=message(e);}finally{this.state.busy=false;}
    }
    choose(mode){this.importMode=mode;this.fileRef.el.click();}
    async onFile(ev){const f=ev.target.files?.[0];ev.target.value='';if(f)await this.importFile(f,this.importMode);}
    async importFile(f,mode){
        if(f.size>10*1024*1024){this.state.error='Choose an Excel workbook under 10 MB.';return;}
        this.state.busy=true;this.state.error='';
        try{
            const data=await this.orm.call('pb.payroll.templates','review',[this.state.configId,this.state.period,mode,await fileData(f),f.name]);
            this.dialog.add(WorkbookReview,{data,configId:this.state.configId,onApplied:async()=>{await this.load();}});
        }catch(e){this.state.error=message(e);}finally{this.state.busy=false;}
    }
    async save(){
        this.state.busy=true;this.state.error='';
        try{await this.orm.call('pb.payroll.templates','save_layout',[this.state.configId,this.state.layout]);this.state.dirty=false;this.notif.add('Monthly layout saved for this configuration.',{type:'success'});}
        catch(e){this.state.error=message(e);}finally{this.state.busy=false;}
    }
    move(id,lane,before=''){if(!this.state.data.can_layout)return;this.state.layout=moveField(this.state.layout,id,lane,before);this.state.dirty=true;this.state.menu='';}
    earlier(id,lane){const a=this.state.layout[lane],i=a.indexOf(id);if(i>0)this.move(id,lane,a[i-1]);}
    later(id,lane){const a=this.state.layout[lane],i=a.indexOf(id);if(i<a.length-1)this.move(id,lane,a[i+2]||'');}
    startDrag(ev,id){this.dragged=id;ev.dataTransfer.setData('text/plain',id);ev.dataTransfer.effectAllowed='move';}
    allowDrop(ev){ev.preventDefault();ev.dataTransfer.dropEffect='move';}
    drop(ev,lane,before=''){ev.preventDefault();ev.stopPropagation();const id=this.dragged;this.dragged='';if(id&&this.fields[id])this.move(id,lane,before);}
    openRecords(){return this.action.doAction('pb_records.action_pb_records_desk',{additionalContext:{records_config_id:this.state.configId}});}
    openConfigurations(){return this.action.doAction('pb_formula_studio.action_pb_formula_studio');}
    openPayRun(){
        if(this.state.data.state!=='active'||!this.state.data.people){this.notif.add('Activate this configuration and assign employees before starting a pay run.',{type:'warning'});return;}
        const [y,m]=this.state.period.split('-').map(Number),last=new Date(y,m,0).getDate();
        return this.action.doAction('pb_payrun_wizard.action_pb_payrun_wizard',{additionalContext:{pb_payai_prefill:{from_templates:true,formula_config_id:this.state.configId,date_start:`${this.state.period}-01`,date_end:`${this.state.period}-${last}`}}});
    }
}
registry.category('actions').add('pb_payroll_templates',PayrollTemplates);

patch(PbFormulaStudio.prototype,{
    openPayrollTemplates(configId){
        return this.action.doAction('pb_payroll_templates.action_templates',{additionalContext:{templates_config_id:configId||this.state.config.id}});
    },
});

patch(PayrunWizard.prototype,{
    async _refreshGate(clearFile){
        if(!this.state.form.templates_monthly)return super._refreshGate(clearFile);
        try{
            this.state.sheet.gate=await this.orm.call('pb.payrun.wizard','spreadsheet_gate',[{...this.state.form}]);
            if(clearFile)this.clearSheetFile();
        }catch(e){this.notif.add(message(e),{type:'warning'});}
    },
    _applyPrefill(pre){
        if(!pre.from_templates)return super._applyPrefill(pre);
        this.state.form.templates_monthly=true;
        this.state.form.division=null;
        this.state.form.date_start=pre.date_start;this.state.form.date_end=pre.date_end;
        const card=this.schemeCards.find(c=>c.id===pre.formula_config_id);if(card)this.pickScheme(card);
    },
    openPayrollTemplates(){
        return this.action.doAction('pb_payroll_templates.action_templates',{additionalContext:{templates_config_id:this.sheetConfigId,templates_period:this.state.form.date_start?.slice(0,7)||month()}});
    },
    async downloadMonthlyTemplate(){
        try{saveFile(await this.orm.call('pb.payroll.templates','download',[this.sheetConfigId,this.state.form.date_start.slice(0,7),'monthly']));}
        catch(e){this.notif.add(message(e),{type:'danger'});}
    },
    async _takeFile(f){
        if(!f||!f.name.toLowerCase().endsWith('.xlsx'))return super._takeFile(f);
        if(f.size>10*1024*1024){this.state.sheet.error='Choose a workbook under 10 MB.';return;}
        const b64=await fileData(f);
        let isTemplate=false;
        try{isTemplate=await this.orm.call('pb.payroll.templates','is_template',[b64]);}catch(e){this.state.sheet.error=message(e);return;}
        if(!isTemplate){this.state.sheet.templateFile=false;return super._takeFile(f);}
        this.state.sheet.checking=true;this.state.sheet.error='';
        try{
            const data=await this.orm.call('pb.payroll.templates','review',[this.sheetConfigId,this.state.form.date_start.slice(0,7),'monthly',b64,f.name]);
            this.dialog.add(WorkbookReview,{data,configId:this.sheetConfigId,onApplied:async()=>{
                const result=await this.orm.call('pb.payrun.wizard','template_month_file',[this.sheetConfigId,this.state.form.date_start.slice(0,7)]);
                Object.assign(this.state.sheet,{file_b64:result.file_b64,file_name:result.filename,templateFile:true,mode:'once',skipped:false,error:'',preflight:{ok:true,columns:data.changes.length,total:0,fed:[],fed_rows:[],missing:[],employees_col:true}});
            }});
        }catch(e){this.state.sheet.error=message(e);}finally{this.state.sheet.checking=false;}
    },
});
