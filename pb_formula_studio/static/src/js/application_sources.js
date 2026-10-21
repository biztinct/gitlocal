/** @odoo-module **/
import { Component, useState, onWillStart, useRef, useEffect } from '@odoo/owl';
import { browser } from '@web/core/browser/browser';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { useSetupAction } from '@web/search/action_hook';
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';

/** Keep routine mapping choices relevant; advanced browsing remains explicit. */
export function sourceChoices(options, row, query = '', showAll = false) {
    const types = {
        money: ['money', 'monetary', 'float', 'decimal'],
        quantity: ['quantity', 'days', 'hours', 'number', 'integer', 'float', 'decimal'],
        integer: ['integer', 'number', 'float', 'quantity'],
        rate: ['rate', 'float', 'decimal', 'number'],
        decimal: ['decimal', 'float', 'number', 'rate', 'quantity'],
        boolean: ['boolean', 'integer'], date: ['date', 'datetime'],
        text: ['text', 'char', 'selection', 'many2one'],
        identifier: ['text', 'char', 'selection', 'many2one', 'integer'],
    };
    const q = query.toLowerCase();
    const current = o => o.key === row?.key;
    const rank = o => current(o) ? 0 : o.key === `period.input.${row?.code}` ? 1 : o.owner === row?.owner ? 2 : 3;
    return options.filter(o => o.key !== 'application.mode'
        && (!o.key.startsWith('period.input.') || o.component_code === row?.code)
        && !o.requires_domain_review && o.available !== false
        && (showAll || current(o) || (!o.key.startsWith('history.') && (types[row?.kind] || []).includes(o.unit)))
        && `${o.label} ${o.owner}`.toLowerCase().includes(q))
        .sort((a, b) => rank(a) - rank(b) || a.owner.localeCompare(b.owner) || a.label.localeCompare(b.label));
}

export class ApplicationSources extends Component {
    static template = 'pb_formula_studio.ApplicationSources';
    static props = {'*': true};
    setup() {
        this.orm=useService('orm'); this.action=useService('action'); this.notification=useService('notification'); this.dialog=useService('dialog');
        const supplied=this.props.action.params || {};
        let restored={};
        try{restored=JSON.parse(browser.sessionStorage.getItem('pb.payroll.sources.scope')||'{}');}catch{}
        this.sourceScope=supplied.config_id ? supplied : {...restored,...supplied};
        this.configId=Number(this.sourceScope.config_id)||0;
        this.traceRef=useRef('sourceTrace');
        useEffect(()=>{this.traceRef.el?.scrollIntoView({behavior:'smooth',block:'start'});},()=>[this.state.detail?.id]);
        this.state=useState({data:null,settings:{},rows:[],tab:this.sourceScope.tab || 'calculation',detail:null,detailBusy:false,employeeId:0,dateFrom:this.props.action.params.return_payrun?.date_start || '',dateTo:this.props.action.params.return_payrun?.date_end || '',query:'',filter:'all',busy:false,error:'',dirty:false,picker:0,sourceQuery:'',showAllSources:false});
        useEffect(()=>{if(this.configId)browser.sessionStorage.setItem('pb.payroll.sources.scope',JSON.stringify({config_id:this.configId,tab:this.state.tab,component_id:this.state.detail?.id||0,from_mapping:!!this.sourceScope.from_mapping}));},()=>[this.configId,this.state.tab,this.state.detail?.id]);
        useSetupAction({beforeLeave:()=>!this.state.dirty||new Promise(resolve=>this.dialog.add(ConfirmationDialog,{body:'Your payroll source changes are not saved. Leave without saving?',confirmLabel:'Leave without saving',confirm:()=>resolve(true),cancel:()=>resolve(false)}))});
        onWillStart(async()=>{await this.load();const id=Number(this.sourceScope.component_id);if(id){this.state.tab='sources';await this.inspect(id);}});
    }
    async load(){if(!this.configId){this.state.error='Open Payroll sources from a selected payroll configuration.';return;}this.state.busy=true;try{this.accept(await this.orm.call('hr.formula.config','application_source_workspace',[[this.configId]]));}catch(e){this.fail(e);}finally{this.state.busy=false;}}
    accept(data){this.state.data=data;this.state.settings={...data.settings};this.state.rows=data.rows.map(r=>({...r}));this.state.dirty=false;}
    fail(e){this.state.error=e?.data?.message||e.message||'Unable to load payroll sources.';}
    set(key,value){if(!this.state.data.can_edit)return;this.state.settings[key]=value;this.state.detail=null;this.state.dirty=true;}
    get connected(){return this.state.rows.filter(r=>r.status==='Connected').length;}
    get needsReview(){return this.state.rows.filter(r=>r.status!=='Connected').length;}
    get visibleRows(){const q=this.state.query.toLowerCase();return this.state.rows.filter(r=>(this.state.filter!=='review'||r.status!=='Connected')&&`${r.name} ${r.owner} ${r.label}`.toLowerCase().includes(q));}
    get selected(){return this.state.rows.find(r=>r.id===this.state.picker);}
    get options(){return sourceChoices(this.state.data.options||[],this.selected,this.state.sourceQuery,this.state.showAllSources);}
    choose(key){const row=this.selected,option=this.state.data.options.find(o=>o.key===key);Object.assign(row,option?{key,label:option.label,owner:option.owner,model:option.model,status:'Connected',pending:false}:{key:'',label:row.native_label,owner:'Saved employee or contract record',status:row.native_label==='No saved-record mapping'?'Choose a source':'Connected'});this.state.picker=0;this.state.detail=null;this.state.dirty=true;}
    async save(){this.state.error='';this.state.busy=true;try{const changes=this.state.rows.filter(r=>r.key!==this.state.data.rows.find(old=>old.id===r.id).key).map(r=>({id:r.id,key:r.key}));this.accept(await this.orm.call('hr.formula.config','application_save_sources',[[this.configId],this.state.data.stamp,{...this.state.settings},changes]));this.notification.add('Payroll sources saved.',{type:'success'});}catch(e){this.fail(e);}finally{this.state.busy=false;}}
    back(){if(this.props.action.params.return_payrun)return this.action.doAction('pb_payrun_wizard.action_pb_payrun_wizard',{additionalContext:{pb_payai_prefill:this.props.action.params.return_payrun}});const crumbs=this.env.config?.breadcrumbs||[];return crumbs.length>1?this.action.restore(crumbs[crumbs.length-2].jsId):this.action.doAction('pb_formula_studio.action_pb_formula_studio');}
    async inspect(id){
        if(this.state.dirty){this.notification.add('Save your source changes before tracing records.',{type:'warning'});return;}
        this.state.error='';this.state.detailBusy=true;
        try{this.state.detail=await this.orm.call('hr.formula.config','application_source_detail',[[this.configId],id]);}
        catch(e){this.fail(e);}finally{this.state.detailBusy=false;}
    }
    async openRecords(model){
        this.state.error='';
        let action;
        try{action=await this.orm.call('hr.formula.config','application_source_record_action',[[this.configId],this.state.detail.id,model,Number(this.state.employeeId)||false,this.state.dateFrom||false,this.state.dateTo||false]);}
        catch(e){this.fail(e);return;}
        // Let Odoo's error service preserve the cause of a destination-view error.
        return this.action.doAction(action);
    }
    pick(row){this.state.picker=row.id;this.state.sourceQuery='';this.state.showAllSources=false;}
}
registry.category('actions').add('pb_application_sources',ApplicationSources);
