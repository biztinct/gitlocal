/* The shared mail.template, presented as a focused message composer. */
function templateMarkup(raw){
 const dom=document.createElement('template');dom.innerHTML=raw||'<p>Write your message here.</p>';S.templateTokens={};
 for(const e of dom.content.querySelectorAll('script,iframe,object,embed,link,meta,style,svg,math,form,input,button'))e.remove();
 for(const e of dom.content.querySelectorAll('*'))for(const a of [...e.attributes])if(/^on/i.test(a.name)||a.name==='srcdoc'||(['href','src','xlink:href'].includes(a.name)&&!(/^(https?:|mailto:|tel:|\/|#)/i.test(a.value))))e.removeAttribute(a.name);
 for(const e of [...dom.content.querySelectorAll('*')]){
  if(!dom.content.contains(e))continue;
  if([...e.attributes].some(a=>a.name.startsWith('t-'))||e.tagName==='T'){
   const key=uid('token'),raw=e.outerHTML,label=e.getAttribute('t-out')||e.getAttribute('t-field')||'Dynamic section';S.templateTokens[key]=raw;
   const chip=document.createElement('span');chip.className='message-token';chip.contentEditable='false';chip.dataset.templateToken=key;chip.textContent=label.replace(/^object\./,'');e.replaceWith(chip);
  }
 }
 return dom.innerHTML;
}
function captureTemplate(){
 if(!S.templateDraft||S.page!=='template')return;
 for(const e of $$('[data-template-field]'))S.templateDraft.values[e.dataset.templateField]=e.value;
 if($('#message-body')&&S.templateBodyChanged){const dom=document.createElement('template');dom.innerHTML=$('#message-body').innerHTML;for(const chip of dom.content.querySelectorAll('[data-template-token]')){const frag=document.createElement('template');frag.innerHTML=S.templateTokens[chip.dataset.templateToken]||'';chip.replaceWith(frag.content);}S.templateDraft.values.body_html=dom.innerHTML;}
}
function templatePage(){
 const t=S.templateDraft,v=t.values;
 const control=(key,label,placeholder='')=>`<label for="message-${key}">${label}</label><input id="message-${key}" data-template-field="${key}" value="${esc(v[key]||'')}" placeholder="${esc(placeholder)}">`;
 return `<main class="message-page"><div class="message-heading"><div>${btn('template-back','Back to '+esc(S.w.definition.name),'back','plain')}<div class="eyebrow">Saved messages · ${esc(t.model_label)}</div><h1>${t.id?'Make every message feel right':'A good message moves work forward'}</h1><p class="muted">Write once. Use it wherever this message belongs.</p></div>${btn('template-save',t.id?'Save shared template':'Save & use template','check','primary')}</div>
 ${t.shared?'<div class="banner">This is a shared template. Saving updates every place that uses it.</div>':''}
 <div class="message-grid"><section class="card message-compose">${control('name','Template name','For example, Expense details received')}${control('subject','Email subject','A clear, friendly subject')}
 <div class="row between message-label"><label id="message-body-label">Message</label>${btn('template-variable','Insert a detail','plus','small plain')}</div>
 <div class="message-toolbar" role="toolbar" aria-label="Message formatting">${[['bold','Bold'],['italic','Italic'],['insertUnorderedList','Bullets'],['removeFormat','Clear style']].map(([cmd,label])=>btn('template-format',label,'','small plain',`data-command="${cmd}"`)).join('')}</div>
 <div id="message-body" class="message-body" contenteditable="true" role="textbox" aria-multiline="true" aria-labelledby="message-body-label">${templateMarkup(v.body_html)}</div>
 <details class="message-delivery" open><summary>Delivery</summary><div class="message-addresses">${control('email_to','To','Email address, or insert a record detail')}${control('email_from','From (optional)','Use the configured sender')}${control('email_cc','Cc (optional)')}${control('reply_to','Reply to (optional)')}</div><small>Sender, recipients and delivery use your existing mail service.</small></details>
 <details class="message-delivery"><summary>Language & advanced content</summary>${control('lang','Language (optional)','For example, en_US')}<small>Existing dynamic sections are kept intact. For complex templates, edit their original content here.</small>${btn('template-source','Edit HTML content','','small plain')}</details></section>
 <aside class="card message-preview"><div class="row between"><h2>A quick look</h2>${pill('Nothing is sent')}</div><p class="muted">Preview with a record to check the personal details.</p><div class="row"><input id="message-sample-search" placeholder="Find an example record" aria-label="Find an example record">${btn('template-samples','Find','search','small')}</div><select id="message-sample" aria-label="Example record">${opts(S.templateSamples||[],S.templateSample,'Choose a record')}</select>${btn('template-preview','Preview message','play','')}
 <div id="message-preview-result">${S.templatePreview?`<div class="email-envelope"><small>To: ${esc(S.templatePreview.email_to||'From native recipient settings')}</small><h3>${esc(S.templatePreview.subject)}</h3></div><iframe title="Email preview" sandbox="" srcdoc="${esc(previewDocument(S.templatePreview.body_html))}"></iframe>`:'<div class="message-preview-empty">'+svgIcon('email')+'<h3>Your message, with a personal touch</h3><p>Choose a record and preview. You can save a template before any records exist.</p></div>'}</div></aside></div></main>`;
}
function previewDocument(body){return '<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:"><style>body{font:15px/1.6 system-ui;color:#302e42;padding:12px;overflow-wrap:anywhere}img{max-width:100%}</style></head><body>'+body+'</body></html>';}
async function templateAction(name,el){
 if(name==='template'||name==='new-template'){
  await save();S.templateOrigin={selected:S.selected,view:S.view,tab:S.tab,scroll:$('.workarea')?.scrollTop||0};S.templateDraft=await rpc('template_detail',[S.w.id,name==='template'?Number(el.dataset.id):null]);S.templateOriginal=JSON.stringify(S.templateDraft.values);S.templateBodyChanged=false;S.templatePreview=null;S.templateSamples=[];S.templateSample=null;S.page='template';close();render();return true;
 }
 if(!name.startsWith('template-'))return false;
 captureTemplate();
 if(name==='template-back'){
  if(JSON.stringify(S.templateDraft.values)!==S.templateOriginal){modal('Leave this message?', '<p>Your unsaved message changes will be discarded.</p>',btn('close','Keep editing')+btn('template-discard','Discard changes','','danger'));return true;}
  return templateAction('template-discard',el);
 }
 if(name==='template-discard'){S.page='editor';Object.assign(S,S.templateOrigin);close();render();if($('.workarea'))$('.workarea').scrollTop=S.templateOrigin.scroll;return true;}
 if(name==='template-save'){
  const t=S.templateDraft,result=await rpc('save_template',[S.w.id,t.values,t.id,t.revision]);S.w.metadata=await rpc('metadata',[S.w.source_model,S.w.id]);
  const n=byId(S.w.definition,S.templateOrigin.selected);if(n?.type==='email'&&n.template_id!==result.id)mutate(()=>n.template_id=result.id,false);await save();S.templateOriginal=JSON.stringify(t.values);await templateAction('template-discard',el);notify('Template saved. You’re back at the same step.');return true;
 }
 if(name==='template-samples'){S.templateSamples=await rpc('template_samples',[S.w.id,$('#message-sample-search').value]);$('#message-sample').innerHTML=opts(S.templateSamples,'',S.templateSamples.length?'Choose a record':'No accessible records yet');return true;}
 if(name==='template-preview'){S.templateSample=Number($('#message-sample').value);if(!S.templateSample)throw Error('Choose an example record first.');S.templatePreview=await rpc('template_preview',[S.w.id,S.templateDraft.values,S.templateSample]);render();return true;}
 if(name==='template-format'){document.execCommand(el.dataset.command,false);S.templateBodyChanged=true;return true;}
 if(name==='template-variable'){
  modal('Add a personal detail',field('Place it in','<select id="variable-target">'+opts([['body_html','Message'],['subject','Subject'],['email_to','To'],['email_from','From'],['reply_to','Reply to']],'body_html',null)+'</select>')+field('Record detail','<select id="variable-field">'+opts(S.templateDraft.fields.filter(f=>f.type!=='many2one'),'')+'</select>'),btn('close','Cancel')+btn('template-insert','Insert detail','plus','primary'));return true;
 }
 if(name==='template-insert'){
  const key=$('#variable-field').value,target=$('#variable-target').value;if(!key)throw Error('Choose a record detail.');const token='{{ object.'+key+' }}';
  if(target==='body_html'){S.templateDraft.values.body_html+=(S.templateDraft.values.body_html?' ':'')+'<t t-out="object.'+key+'"/>';}else S.templateDraft.values[target]=(S.templateDraft.values[target]||'')+token;
  close();render();return true;
 }
 if(name==='template-source'){modal('Message HTML', '<p class="muted">Dynamic sections use the existing template language.</p><textarea id="template-source" class="code-input" aria-label="Message HTML">'+esc(S.templateDraft.values.body_html)+'</textarea>',btn('close','Cancel')+btn('template-source-save','Use this content','check','primary'));return true;}
 if(name==='template-source-save'){
  // Native sanitization runs before HTML is shown in the visual editor.
  const body=$('#template-source').value;S.templateDraft.values.body_html=body;close();
  // Keep source edits as text until the server sanitizes on save/preview.
  S.templateBodyChanged=false;$('#message-body').textContent='HTML content updated. Save or preview to apply it.';return true;
 }
 return false;
}
document.addEventListener('input',e=>{if(e.target.closest('#message-body'))S.templateBodyChanged=true;if(e.target.dataset.templateField&&S.templateDraft)S.templateDraft.values[e.target.dataset.templateField]=e.target.value;});
document.addEventListener('mousedown',e=>{if(e.target.closest('[data-act="template-format"]'))e.preventDefault();});
