/* Readable flowchart with real insertion targets, pointer moves and a keyboard path. */
const FLOW_W=320,FLOW_H=116;
let canvasSize={w:700,h:900},flowGeometry=null,activeFlowDrag=null;
function layoutGraph(){
 const d=draft(),positions={},slots=[],labels=[],stages=[];
 const targets=flowTargets(d);
 function width(ids){return Math.max(FLOW_W+60,...ids.map(id=>{const n=byId(d,id);return n.branches?n.branches.reduce((w,b)=>w+width(b.steps),0)+40*(n.branches.length-1):n.steps?width(n.steps):FLOW_W+60;}));}
 const w=Math.max(FLOW_W+48,width(d.order)+48);
 function slot(key,stage,before,cx,y){const t=targets.find(t=>t.key===key&&t.stage===stage&&t.before===before);if(t)slots.push({...t,x:cx-FLOW_W/2,y:y-20});}
 function sequence(ids,key,stage,cx,y,next=null){
  for(const id of ids){
   slot(key,stage,id,cx,y);y+=32;positions[id]={x:cx-FLOW_W/2,y};y+=FLOW_H+30;
   const n=byId(d,id);
   if(GROUPS.includes(n.type)){
    const branches=n.branches||[{id:n.id,label:'Saved steps',steps:n.steps}],widths=branches.map(b=>width(b.steps));
    const total=widths.reduce((a,b)=>a+b,0)+40*(branches.length-1);let left=cx-total/2,bottom=y;
    branches.forEach((b,i)=>{const bx=left+widths[i]/2;labels.push({x:bx-FLOW_W/2,y,text:b.label});bottom=Math.max(bottom,sequence(b.steps,b.id,n.stage,bx,y+48));left+=widths[i]+40;});
    positions[id+'__join']={x:cx-110,y:bottom+12};y=bottom+44+46;
   }
  }
  slot(key,stage,next,cx,y);return y+28;
 }
 let y=24;
 d.stages.forEach((s,i)=>{stages.push({y,name:stageName(s),index:i});y+=42;const ids=d.order.filter(id=>byId(d,id).stage===i),next=d.order.find(id=>byId(d,id).stage>i)||null;y=sequence(ids,'main',i,w/2,y,next)+32;});
 canvasSize={w,h:y+24};flowGeometry={positions,slots,labels,stages};return positions;
}
function flowCardSummary(n){
 if(n.type==='input'&&n.form)return `${n.form.fields.filter(f=>f.type!=='section').length} fields · ${n.owner}`;
 if(n.type==='matrix')return 'Uses your saved approval route';
 if(n.type==='trigger')return 'Start';
 if(n.type==='email'&&n.enabled===false)return 'Off · approval updates are already included';
 if(HUMAN.includes(n.type))return n.owner;
 return nodeSummary(n);
}
function renderCanvas(){
 const plan=compile(draft()),pos=layoutGraph();
 $('#workarea').innerHTML=`<div class="canvas-wrap ${state.arrange?'arrange-view':''}"><div class="canvas-toolbar"><div class="canvas-tools"><button data-action="zoom-out" aria-label="Zoom out">−</button><button data-action="zoom-reset" title="Actual size">${Math.round(state.zoom*100)}%</button><button data-action="zoom-in" aria-label="Zoom in">＋</button><button data-action="fit">Fit width</button>${state.arrange?'<button data-action="layout">Tidy</button>':''}<button data-flow-action="arrange" aria-pressed="${!!state.arrange}">${state.arrange?'Done arranging':'Arrange view'}</button></div><span class="flow-feedback" role="status" aria-live="polite">${state.arrange?'Move cards without changing the order.':'Drag a step to a + to change the order.'}</span><button class="text-btn flow-help" data-flow-action="help">How to</button></div><div class="canvas-extent" style="width:${canvasSize.w*state.zoom}px;height:${canvasSize.h*state.zoom}px"><div class="canvas-surface" style="width:${canvasSize.w}px;height:${canvasSize.h}px;transform:scale(${state.zoom})"><svg class="canvas-svg" style="width:${canvasSize.w}px;height:${canvasSize.h}px" aria-label="Workflow connections"></svg>${flowGeometry.stages.map(s=>`<div class="flow-stage-label" style="top:${s.y}px"><span>${s.index+1}</span>${esc(s.name)}</div>`).join('')}${flowGeometry.labels.map(l=>`<div class="flow-path-label" style="left:${l.x}px;top:${l.y}px">${esc(l.text)}</div>`).join('')}${plan.nodes.map(n=>n.virtual?`<button class="graph-join" data-node="${n.parent}" data-join="${n.id}" style="left:${pos[n.id].x}px;top:${pos[n.id].y}px">${n.type==='join'&&byId(draft(),n.parent).type==='parallel'?(byId(draft(),n.parent).join==='all'?'All paths finish':'First path finishes'):'Continue'}</button>`:nodeCard(byId(draft(),n.id),true)).join('')}${flowGeometry.slots.map(t=>`<button class="flow-slot" data-flow-slot="${esc(t.id)}" style="left:${t.x}px;top:${t.y}px" aria-label="Add a step: ${esc(t.label)} · ${esc(t.where)}"><span class="slot-plus">+</span><span class="slot-label">${esc(t.label)}</span></button>`).join('')}</div></div></div>`;
 $$('.graph-node').forEach(el=>{const n=byId(draft(),el.dataset.node);el.querySelector('.step-detail').textContent=flowCardSummary(n);el.title=n.type==='trigger'?'The start stays first':n.title+' · Drag to move, or click to edit';});
 positionGraph();
}
function effectiveFlowPosition(id){return state.arrange&&byId(draft(),id)?.pos||flowGeometry.positions[id];}
function positionGraph(){
 nodes().forEach(n=>{const el=$(`.graph-node[data-node="${n.id}"]`),p=effectiveFlowPosition(n.id);if(el&&p){el.style.left=p.x+'px';el.style.top=p.y+'px';}});drawEdges();
}
function drawEdges(){
 const svg=$('.canvas-svg');if(!svg)return;
 svg.innerHTML=`<defs><marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L8 4 L0 8Z" fill="#a79abf"/></marker></defs>`+compile(draft()).edges.map(e=>{
  const a=byId(draft(),e.from),b=byId(draft(),e.to),pa=effectiveFlowPosition(e.from),pb=effectiveFlowPosition(e.to);if(!pa||!pb)return '';
  const x1=pa.x+(a?FLOW_W/2:110),y1=pa.y+(a?FLOW_H:44),x2=pb.x+(b?FLOW_W/2:110),y2=pb.y,mid=(y1+y2)/2;
  return `<path data-flow-from="${e.from}" data-flow-to="${e.to}" d="M${x1} ${y1} C${x1} ${mid},${x2} ${mid},${x2} ${y2}" stroke="${e.kind==='parallel'?'#79a49a':'#b6abc9'}" stroke-width="1.8" fill="none" marker-end="url(#arrow)"/>`;
 }).join('');
}
function applyFlowMove(id,target){
 const result=moveFlowStep(draft(),id,target);
 if(result.error){toast(result.error);return false;}if(result.unchanged)return false;
 change(()=>{state.draft=result.draft;state.selected=id;state.arrange=false;});
 toast('Step moved. Undo is available.');
 requestAnimationFrame(()=>$(`.graph-node[data-node="${id}"]`)?.scrollIntoView({block:'nearest',inline:'nearest'}));return true;
}
function flowSlotElement(id){return $$('.flow-slot').find(el=>el.dataset.flowSlot===id);}
function findFlowDrop(x,y){
 const wrap=$('.canvas-wrap'),bounds=wrap.getBoundingClientRect(),toolbar=$('.canvas-toolbar').getBoundingClientRect();if(x<bounds.left||x>bounds.right||y<Math.max(bounds.top,toolbar.bottom)||y>bounds.bottom)return null;
 let best=null,distance=Infinity;
 for(const t of flowGeometry.slots){const r=flowSlotElement(t.id).getBoundingClientRect(),dx=Math.abs(x-(r.x+r.width/2)),dy=Math.abs(y-(r.y+r.height/2));if(dx<=r.width/2+12&&dy<=30&&dy<distance){best=t;distance=dy;}}
 if(best)return best;
 const card=document.elementFromPoint(x,y)?.closest('.graph-node');if(!card)return null;
 const id=card.dataset.node,c=containerFor(draft(),id),n=byId(draft(),id),r=card.getBoundingClientRect(),before=y<r.y+r.height/2?id:c.ids[c.ids.indexOf(id)+1]||null;
 return flowGeometry.slots.find(t=>t.key===c.key&&t.stage===n.stage&&t.before===before)||null;
}
function showFlowDrop(t,id=null){
 $$('.flow-slot').forEach(el=>el.classList.remove('is-target','is-blocked'));
 if(!t){$('.flow-feedback').textContent='Drop on a +, or press Esc to cancel.';return;}
 const result=id?moveFlowStep(draft(),id,t):{};const el=flowSlotElement(t.id);
 el.classList.add(result.error?'is-blocked':'is-target');
 $('.flow-feedback').textContent=result.error||`${id?'Move':'Add'} · ${t.label} · ${t.where}`;
}
function clearFlowDrag(){
 if(activeFlowDrag){cancelAnimationFrame(activeFlowDrag.frame);activeFlowDrag.ghost?.remove();activeFlowDrag.clean?.();}
 activeFlowDrag=null;$('.canvas-wrap')?.classList.remove('flow-dragging');$$('.flow-lifted,.is-target,.is-blocked').forEach(el=>el.classList.remove('flow-lifted','is-target','is-blocked'));
 if($('.flow-feedback'))$('.flow-feedback').textContent=state.arrange?'Move cards without changing the order.':'Drag a step to a + to change the order.';
}
function bindFlowDrag(){
 const wrap=$('.canvas-wrap');if(!wrap)return;
 wrap.addEventListener('dragover',e=>{if(!dragData?.type)return;e.preventDefault();wrap.classList.add('flow-dragging');showFlowDrop(findFlowDrop(e.clientX,e.clientY));});
 wrap.addEventListener('drop',e=>{if(!dragData?.type)return;e.preventDefault();const target=findFlowDrop(e.clientX,e.clientY),type=dragData.type;dragData=null;clearFlowDrag();if(target)addNode(type,target.key,target.stage,target.before);else toast('Drop on a + to choose its place.');});
 $$('[data-block]').forEach(el=>el.addEventListener('dragend',clearFlowDrag));
 $$('.graph-node').forEach(el=>el.addEventListener('pointerdown',e=>{
  if(e.button!==0||activeFlowDrag)return;const id=el.dataset.node,n=byId(draft(),id);if(n.type==='trigger'&&!state.arrange)return;
  const origin={...effectiveFlowPosition(id)},sx=e.clientX,sy=e.clientY;let moving=false,target=null,last={x:sx,y:sy},nextPos=origin;
  el.setPointerCapture(e.pointerId);
  const clean=()=>{el.removeEventListener('pointermove',move);el.removeEventListener('pointerup',end);el.removeEventListener('pointercancel',cancel);el.removeEventListener('lostpointercapture',cancel);};
  const tick=()=>{if(!activeFlowDrag)return;const r=wrap.getBoundingClientRect(),top=$('.canvas-toolbar').getBoundingClientRect().bottom;if(last.x>=r.left&&last.x<=r.right&&last.y>=r.top&&last.y<=r.bottom){const dy=last.y<top+44?-12:last.y>r.bottom-60?12:0,dx=last.x<r.left+35?-10:last.x>r.right-35?10:0;wrap.scrollBy(dx,dy);if(!state.arrange){target=findFlowDrop(last.x,last.y);showFlowDrop(target,id);}}activeFlowDrag.frame=requestAnimationFrame(tick);};
  const move=ev=>{last={x:ev.clientX,y:ev.clientY};const dx=last.x-sx,dy=last.y-sy;if(!moving&&Math.abs(dx)+Math.abs(dy)<6)return;
   if(!moving){moving=true;dragged=true;activeFlowDrag={id,clean,cancel};wrap.classList.add('flow-dragging');el.classList.add('flow-lifted');if(!state.arrange){const ghost=document.createElement('div');ghost.className='flow-ghost';ghost.textContent=n.title;document.body.append(ghost);activeFlowDrag.ghost=ghost;}activeFlowDrag.frame=requestAnimationFrame(tick);}
   if(state.arrange){nextPos={x:Math.max(0,Math.min(canvasSize.w-FLOW_W,origin.x+dx/state.zoom)),y:Math.max(0,Math.min(canvasSize.h-FLOW_H,origin.y+dy/state.zoom))};el.style.left=nextPos.x+'px';el.style.top=nextPos.y+'px';}
   else{Object.assign(activeFlowDrag.ghost.style,{left:last.x+16+'px',top:last.y+12+'px'});target=findFlowDrop(last.x,last.y);showFlowDrop(target,id);}
  };
  const end=()=>{clean();if(!moving)return;clearFlowDrag();if(state.arrange){change(()=>n.pos=nextPos);}else if(target)applyFlowMove(id,target);else toast('No change. Drop on a + to move the step.');setTimeout(()=>dragged=false,0);};
  const cancel=()=>{clean();clearFlowDrag();positionGraph();setTimeout(()=>dragged=false,0);};
  el.addEventListener('pointermove',move);el.addEventListener('pointerup',end);el.addEventListener('pointercancel',cancel);el.addEventListener('lostpointercapture',cancel);
 }));
}
function openFlowMove(id){
 const available=flowTargets(draft()).filter(t=>moveFlowStep(draft(),id,t).draft);
 openModal('Move step','',`<p class="move-step-name">${esc(byId(draft(),id).title)}</p>${available.length?field('New position',`<select id="flow-destination">${available.map(t=>`<option value="${esc(t.id)}">${esc(t.where+' · '+t.label)}</option>`).join('')}</select>`):'<p class="hint">There is no other valid position yet. Add a task or path first.</p>'}<div class="modal-actions"><button class="button white" data-action="close">Cancel</button><button class="button primary" data-flow-action="confirm-move" data-flow-node="${id}" ${available.length?'':'disabled'}>Move step</button></div>`);
}
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b||(!b.dataset.flowAction&&b.dataset.flowSlot===undefined))return;e.stopImmediatePropagation();
 if(b.dataset.flowSlot!==undefined){const t=flowGeometry.slots.find(t=>t.id===b.dataset.flowSlot);if(t&&!dragged){addModal(t.key,t.stage);state.addTarget.before=t.before;}return;}
 if(b.dataset.flowAction==='arrange'){state.arrange=!state.arrange;render();return;}
 if(b.dataset.flowAction==='move'){openFlowMove(b.dataset.flowNode);return;}
 if(b.dataset.flowAction==='confirm-move'){const t=flowTargets(draft()).find(t=>t.id===$('#flow-destination').value);if(t){closeModal();applyFlowMove(b.dataset.flowNode,t);}return;}
 if(b.dataset.flowAction==='help')openModal('Build your flow','',`<div class="simple-help"><p><b>Add</b> Click a + or drag a step onto it.</p><p><b>Move</b> Drag a card to a new +. The arrows update.</p><p><b>Edit</b> Click a card to change its details.</p><p><b>Use the keyboard</b> Open a card, then choose Move…</p><p><b>Undo</b> Use ↶ or Ctrl / ⌘ Z.</p></div>`);
});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&activeFlowDrag){e.preventDefault();e.stopImmediatePropagation();activeFlowDrag.cancel();}},true);
