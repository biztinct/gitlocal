'use strict';
/* WF2 P6b — the workbench's one translation word, `_t` (no framework).
   _t('English phrase') returns the phrase in the signed-in person's language,
   or the English itself when there is no translation; named holes are
   filled from `values`: _t('%(n)s steps', {n: 3}). With no dictionary (an
   English login, or the words could not be loaded) every call returns
   exactly the English it was given, so English screens do not change.
   _t.n(count, one, many, values) picks the singular or the plural phrase
   (English grammar) and fills %(n)s with the count.
   _t.on is true when a translated dictionary is in use; the few English
   grammar helpers (a / an, ’s, 1st 2nd 3rd) only apply when it is false.
   The dictionary comes from /pb_lifecycle/workflow/words.js, the next
   script in index.html, before any screen is drawn. */
const _t=(()=>{
 let words=Object.create(null);
 const fill=(text,values)=>values?String(text).replace(/%\((\w+)\)s/g,(all,k)=>Object.prototype.hasOwnProperty.call(values,k)?String(values[k]):all):text;
 const t=(text,values)=>fill(words[text]||text,values);
 t.on=false;t.lang='en_US';
 t.n=(count,one,many,values)=>t(count===1?one:many,Object.assign({n:count},values||{}));
 /* _t.later('phrase') marks a phrase that is translated where it is used
    (a table of words handed to _t / _t.n later); it returns it unchanged. */
 t.later=text=>text;
 t.load=data=>{
  const w=data&&data.words;if(!w||typeof w!=='object')return;
  words=Object.assign(Object.create(null),w);
  t.lang=String(data.lang||'en_US');t.on=Object.keys(words).length>0&&!/^en/.test(t.lang);
  if(t.on)document.documentElement.lang=t.lang.split('_')[0];
 };
 /* The one English line in index.html ("Opening your workflows…") is
    swapped as the parser inserts it, before the first paint. */
 const swap=()=>{const el=document.querySelector('#app > main.loading');if(!el)return false;if(t.on){const was=el.textContent;el.textContent=t(was);}return true;};
 const watch=new MutationObserver(()=>{if(swap())watch.disconnect();});
 watch.observe(document.documentElement,{childList:true,subtree:true});
 document.addEventListener('DOMContentLoaded',()=>watch.disconnect(),{once:true});
 return t;
})();
