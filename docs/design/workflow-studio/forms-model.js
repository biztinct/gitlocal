/* Typed, versioned forms. All records and attachments here are fictional/local. */
const FORM_TYPES={text:'Short text',textarea:'Long text',select:'Dropdown',multiselect:'Multiple choice',boolean:'Yes / No',number:'Number',date:'Date',email:'Email',lookup:'Record lookup',file:'Attachment',rows:'Repeating rows',section:'Section heading'};
const FORM_RECORD_FIELDS={department:{label:'Department',type:'text',fact:'department'},employee:{label:'Employee name',type:'text',fact:'employee'},amount:{label:'Request amount',type:'number',fact:'amount'},email:{label:'Employee email',type:'email',fact:'email'}};
function newFormField(type='text') {return {id:uid('field'),type,label:FORM_TYPES[type],required:false,help:'',options:['Option 1','Option 2'],visibility:null,access:'edit',source:'',section:''};}
function expenseForm(){return {id:'expense-details',version:1,title:'A few details about your expense',description:'Help your reviewer understand the request. We have filled in what we already know.',fields:[
 {id:'context',type:'section',label:'Your request'},
 {id:'department',type:'text',label:'Department',source:'department',access:'readonly',required:false},
 {id:'purpose',type:'textarea',label:'What was the expense for?',required:true,help:'A short explanation gives your reviewer the context they need.'},
 {id:'category',type:'select',label:'Expense category',required:true,options:['Travel','Meals','Equipment','Other']},
 {id:'expense_date',type:'date',label:'Expense date',required:true},
 {id:'billing',type:'section',label:'Customer billing'},
 {id:'billable',type:'boolean',label:'Bill this to a customer?',required:true},
 {id:'customer',type:'lookup',label:'Which customer?',required:true,options:['Acme · Australia','Northstar · Australia','Rize · Indonesia'],visibility:{field:'billable',value:'true'},help:'Choose the customer associated with this expense.'},
 {id:'receipt',type:'file',label:'Receipt or supporting document',required:false,help:'Attach a receipt or another document that explains your expense.'}
 ]};}
function formVisible(f,values,form){if(!f.visibility)return true;const parent=form.fields.find(p=>p.id===f.visibility.field);return !!parent&&formVisible(parent,values,{fields:form.fields.filter(p=>p.id!==f.id)})&&String(values[parent.id]??'')===f.visibility.value;}
function initialFormValues(form,facts={}){const out={};for(const f of form.fields){if(f.source&&FORM_RECORD_FIELDS[f.source])out[f.id]=facts[FORM_RECORD_FIELDS[f.source].fact]??'';else if(f.default!==undefined)out[f.id]=f.default;}return out;}
function formDefinitionErrors(form){const errors=[],ids=new Set();if(!form.title?.trim())errors.push('Give the form a title.');if(!form.fields.some(f=>f.type!=='section'))errors.push('Add at least one question.');
 form.fields.forEach((f,i)=>{if(ids.has(f.id))errors.push('Every field needs its own identifier.');if(!FORM_TYPES[f.type])errors.push('Choose a supported field type.');if(!f.label?.trim())errors.push('Give every field a label.');
 if(['select','multiselect','lookup'].includes(f.type)&&(!f.options?.length||f.options.some(x=>!x.trim())||new Set(f.options).size!==f.options.length))errors.push(`${f.label}: use distinct, non-empty choices.`);
 if(f.source&&(!FORM_RECORD_FIELDS[f.source]||FORM_RECORD_FIELDS[f.source].type!==f.type||f.access!=='readonly'))errors.push(`${f.label}: existing record fields must keep their type and read-only access in this preview.`);
 if(f.access==='readonly'&&!f.source&&f.type!=='section')errors.push(`${f.label}: choose an existing record field for read-only information.`);
 if(f.visibility){const parent=form.fields.slice(0,i).find(p=>p.id===f.visibility.field);if(!parent||!['boolean','select'].includes(parent.type))errors.push(`${f.label}: visibility must use an earlier Yes/No or dropdown question.`);else if(!(parent.type==='boolean'?['true','false']:parent.options).includes(f.visibility.value))errors.push(`${f.label}: choose a valid visibility answer.`);}
 ids.add(f.id);});return errors;}
function validateForm(form,raw,facts={}){const values={...raw,...initialFormValues({fields:form.fields.filter(f=>f.source)},facts)},answers={},errors={};
 for(const f of form.fields){if(f.type==='section'||!formVisible(f,values,form))continue;let v=values[f.id];const empty=v===undefined||v===null||v===''||Array.isArray(v)&&!v.length;
 if(empty){if(f.required)errors[f.id]=`Enter ${f.label.toLowerCase()} to continue.`;continue;}
 if(['text','textarea','email','date','select','lookup'].includes(f.type)){if(typeof v!=='string'||!v.trim()){errors[f.id]='Enter a value.';continue;}v=v.trim();}
 if(f.type==='email'&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v))errors[f.id]='Enter a valid email address.';
 if(f.type==='number'){if(!['number','string'].includes(typeof v)||!String(v).trim()||!Number.isFinite(Number(v)))errors[f.id]='Enter a valid number.';else {v=Number(v);if(f.min!==undefined&&v<Number(f.min))errors[f.id]=`Use ${f.min} or more.`;}}
 if(f.type==='boolean'){if(![true,false,'true','false'].includes(v))errors[f.id]='Choose Yes or No.';else v=v===true||v==='true';}
 if(['select','lookup'].includes(f.type)&&!f.options.includes(v))errors[f.id]='Choose one of the available options.';
 if(f.type==='multiselect'&&(!Array.isArray(v)||v.some(x=>!f.options.includes(x))))errors[f.id]='Choose from the available options.';
 if(f.type==='date'&&(!/^\d{4}-\d{2}-\d{2}$/.test(v)||!Number.isFinite(Date.parse(v))||new Date(v).toISOString().slice(0,10)!==v))errors[f.id]='Enter a valid date.';
 if(f.type==='file'&&(!Array.isArray(v)||v.some(x=>!x.name||!Number.isFinite(x.size)||x.size<0||x.size>10*1024*1024)))errors[f.id]='Choose files smaller than 10 MB each.';
 if(f.type==='rows'&&(!Array.isArray(v)||v.some(x=>!x.description?.trim()||x.amount===''||!Number.isFinite(Number(x.amount))||Number(x.amount)<0)))errors[f.id]='Complete each row with a description and a nonnegative amount.';
 answers[f.id]=v;
 }return {answers,errors};}
function sampleFormAnswers(form,facts){const a=initialFormValues(form,facts);for(const f of form.fields){if(f.type==='section'||f.source)continue;a[f.id]=f.type==='boolean'?false:['select','lookup'].includes(f.type)?f.options[0]:f.type==='multiselect'?[f.options[0]]:f.type==='number'?100:f.type==='date'?'2026-11-08':f.type==='email'?'sample@example.invalid':f.type==='file'?[{name:'sample-receipt.pdf',size:1200}]:f.type==='rows'?[{description:'Travel',amount:100}]:'Example information supplied';}return a;}
function displayAnswer(v){return Array.isArray(v)?v.map(x=>typeof x==='object'?x.name||`${x.description}: ${x.amount}`:x).join(', '):typeof v==='boolean'?v?'Yes':'No':String(v??'');}
