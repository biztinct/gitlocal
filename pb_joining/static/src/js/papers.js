/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";
import {PbJoiningBoard} from "./joining_board";

patch(PbJoiningBoard.prototype,{
    async startForm(mode) {
        if(mode!=="settings") return super.startForm(...arguments);
        await this.run(async()=>{
            const [settings,papers]=await Promise.all([this.call("settings"),this.call("papers_load")]);
            Object.assign(this.state,{mode,drawer:null,form:{...settings,papers:papers.rows},options:{countries:papers.countries},code:"",clear:{}});
        });
    },
    submitForm() {
        if(this.state.mode!=="settings")return super.submitForm(...arguments);
        this.run(async()=>{
            const f=this.state.form;
            const result=await this.call("save_settings",[f]);
            f.papers=result.rows;
            this.state.msg=_t("Saved");
        });
    },
    newPaper() {
        this.state.form.papers.push({name:"",country:"",file:"",on:true,sequence:(this.state.form.papers.length+1)*10});
    },
    async uploadPaper(row,ev) {
        const file=ev.target.files[0];
        if(!file)return;
        await this.run(async()=>{
            if(file.size>5*1024*1024)throw Error(_t("Choose a PDF up to 5 MB."));
            row.data=await new Promise((resolve,reject)=>{
                const r=new FileReader();r.onload=()=>resolve(r.result.split(",")[1]);
                r.onerror=()=>reject(Error(_t("Choose a readable PDF up to 5 MB.")));r.readAsDataURL(file);
            });
            row.file=file.name;
        });
    },
    returnSigned(s) {
        this.run(async()=>{
            this.state.drawer=await this.call("return_paper",[this.state.drawer.id,s.id,this.state.note]);
            this.state.noteKey="";this.state.note="";await this.refresh();
        });
    },
});
