/** @odoo-module **/
import { Component, useState, onWillStart } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { useSetupAction } from '@web/search/action_hook';
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';

export class ApplicationSources extends Component {
    static template = 'pb_formula_studio.ApplicationSources';
    static props = {'*': true};
    setup() {
        this.orm=useService('orm'); this.action=useService('action'); this.notification=useService('notification'); this.dialog=useService('dialog');
        this.configId=this.props.action.params.config_id;
        this.state=useState({data:null,settings:{},rows:[],tab:'calculation',query:'',filter:'all',busy:false,error:'',dirty:false,picker:0,sourceQuery:''});
        useSetupAction({beforeLeave:()=>!this.state.dirty||new Promise(resolve=>this.dialog.add(ConfirmationDialog,{body:'Your payroll source changes are not saved. Leave without saving?',confirmLabel:'Leave without saving',confirm:()=>resolve(true),cancel:()=>resolve(false)}))});
        onWillStart(()=>this.load());
    }
    async load(){this.state.busy=true;try{this.accept(await this.orm.call('hr.formula.config','application_source_workspace',[[this.configId]]));}catch(e){this.fail(e);}finally{this.state.busy=false;}}
    accept(data){this.state.data=data;this.state.settings={...data.settings};this.state.rows=data.rows.map(r=>({...r}));this.state.dirty=false;}
    fail(e){this.state.error=e?.data?.message||e.message||'Unable to load payroll sources.';}
    set(key,value){if(!this.state.data.can_edit)return;this.state.settings[key]=value;this.state.dirty=true;}
    get connected(){return this.state.rows.filter(r=>r.status==='Connected').length;}
    get needsReview(){return this.state.rows.filter(r=>r.status!=='Connected').length;}
    get visibleRows(){const q=this.state.query.toLowerCase();return this.state.rows.filter(r=>(this.state.filter!=='review'||r.status!=='Connected')&&`${r.name} ${r.owner} ${r.label}`.toLowerCase().includes(q));}
    get selected(){return this.state.rows.find(r=>r.id===this.state.picker);}
    get options(){const row=this.selected,q=this.state.sourceQuery.toLowerCase();return (this.state.data.options||[]).filter(o=>o.key!=='application.mode'&&(!o.key.startsWith('period.input.')||o.component_code===row?.code)&&!o.requires_domain_review&&o.available!==false&&`${o.label} ${o.owner}`.toLowerCase().includes(q));}
    choose(key){const row=this.selected,option=this.state.data.options.find(o=>o.key===key);Object.assign(row,option?{key,label:option.label,owner:option.owner,model:option.model,status:'Connected',pending:false}:{key:'',label:row.native_label,owner:'Saved employee or contract record',status:row.native_label==='No saved-record mapping'?'Choose a source':'Connected'});this.state.picker=0;this.state.dirty=true;}
    async save(){this.state.error='';this.state.busy=true;try{const changes=this.state.rows.filter(r=>r.key!==this.state.data.rows.find(old=>old.id===r.id).key).map(r=>({id:r.id,key:r.key}));this.accept(await this.orm.call('hr.formula.config','application_save_sources',[[this.configId],this.state.data.stamp,{...this.state.settings},changes]));this.notification.add('Payroll sources saved.',{type:'success'});}catch(e){this.fail(e);}finally{this.state.busy=false;}}
    back(){const crumbs=this.env.config?.breadcrumbs||[];return crumbs.length>1?this.action.restore(crumbs[crumbs.length-2].jsId):this.action.doAction('pb_formula_studio.action_pb_formula_studio');}
    pick(row){this.state.picker=row.id;this.state.sourceQuery='';}
}
registry.category('actions').add('pb_application_sources',ApplicationSources);
