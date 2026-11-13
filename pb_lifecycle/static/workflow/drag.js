/* One drag for mouse, pen and touch (WF2 P3a), replacing the HTML5 drag.
   Kept from before: drops land only on "+" slots, the slot under the pointer
   lights up, Escape cancels, an invalid move explains and changes nothing,
   one Undo per move, the "Move step" dialog stays the keyboard path.
   Added: a ghost card under the pointer, auto-scroll near the edges, touch
   starts from the grip (so the page still scrolls), a mouse starts anywhere
   on the card after 6 px. The Stages sheet reorders rows the same way. */
const DRAG={on:null};
const DRAG_THRESHOLD={mouse:6,pen:6,touch:4};

function dragSlotSelector(d){return d.section!==undefined?'[data-section-slot]':'[data-slot]';}
function dragSlotAt(d,x,y){
 // A little vertical tolerance: the "+" slots are slim targets.
 for(const dy of [0,-10,10,-18,18]){
  const el=document.elementFromPoint(x,y+dy)?.closest(dragSlotSelector(d));
  if(el&&!el.closest('.drag-ghost'))return el;
 }
 return null;
}
function dragScrollers(d){
 if(d.section!==undefined)return [$('#sheet .sheet-body')].filter(Boolean);
 return [$('.builder .workarea'),$('.builder .workarea .canvas')].filter(Boolean);
}
function startDrag(x,y){
 const d=DRAG.on;d.started=true;clearTimeout(d.timer);
 const r=d.src.getBoundingClientRect(),ghost=document.createElement('div');
 ghost.className='drag-ghost'+(d.section!==undefined?' row-ghost':'');ghost.setAttribute('aria-hidden','true');
 const copy=(d.section!==undefined?d.src.closest('.stage-row'):d.src).cloneNode(true);
 copy.querySelectorAll('[data-act],[id]').forEach(e=>{e.removeAttribute('data-act');e.removeAttribute('id');});
 copy.removeAttribute('data-act');ghost.appendChild(copy);
 const box=(d.section!==undefined?d.src.closest('.stage-row'):d.src).getBoundingClientRect();
 ghost.style.width=Math.max(box.width,200)+'px';
 d.dx=x-box.left;d.dy=y-box.top;d.ghost=ghost;
 (d.src.closest('dialog')||document.body).appendChild(ghost);
 (d.section!==undefined?d.src.closest('.stage-row'):d.src).classList.add('drag-source');
 document.body.classList.add('dragging');
 moveDrag(x,y);d.raf=requestAnimationFrame(autoScroll);
}
function moveDrag(x,y){
 const d=DRAG.on;if(!d?.ghost)return;d.px=x;d.py=y;
 d.ghost.style.transform=`translate(${x-d.dx}px,${y-d.dy}px)`;
 const slot=dragSlotAt(d,x,y);
 if(slot!==d.slot){d.slot?.classList.remove('over');slot?.classList.add('over');d.slot=slot;}
}
function autoScroll(){
 const d=DRAG.on;if(!d?.started)return;
 const edge=64;
 for(const el of dragScrollers(d)){
  const r=el.getBoundingClientRect();let dx=0,dy=0;
  if(d.py<r.top+edge&&d.py>r.top-40)dy=-Math.ceil((r.top+edge-d.py)/edge*16);
  else if(d.py>r.bottom-edge&&d.py<r.bottom+40)dy=Math.ceil((d.py-(r.bottom-edge))/edge*16);
  if(d.px<r.left+edge&&d.px>r.left-40)dx=-Math.ceil((r.left+edge-d.px)/edge*16);
  else if(d.px>r.right-edge&&d.px<r.right+40)dx=Math.ceil((d.px-(r.right-edge))/edge*16);
  if(dx||dy){el.scrollBy(dx,dy);moveDrag(d.px,d.py);}
 }
 d.raf=requestAnimationFrame(autoScroll);
}
function endDrag(){
 const d=DRAG.on;if(!d)return;
 clearTimeout(d.timer);cancelAnimationFrame(d.raf);
 d.ghost?.remove();d.slot?.classList.remove('over');
 $$('.drag-source').forEach(e=>e.classList.remove('drag-source'));$$('.drop.over,[data-section-slot].over').forEach(e=>e.classList.remove('over'));
 document.body.classList.remove('dragging');
 if(d.started)S.dragClickBlock=Date.now();
 DRAG.on=null;
}
async function finishDrag(){
 const d=DRAG.on,slot=d.slot;endDrag();
 if(!slot)return;
 try{
  if(d.section!==undefined){
   const at=Number(slot.dataset.sectionSlot),to=at>d.section?at-1:at;
   S.sheetMoveAct='section-up';await moveSection(d.section,to);return;
  }
  const t=targets(S.w.definition).find(t=>t.id===slot.dataset.slot);
  if(!t)throw Error('Choose an available position.');
  if(d.type){await addNode(d.type,t);return;}
  const moved=moveStep(S.w.definition,d.id,t);
  if(moved===S.w.definition)return;
  mutate(()=>{S.w.definition=moved;S.selected=d.id;});
  notify('Step moved. Undo is available.');
 }catch(err){notify(err.message,true);}
}
document.addEventListener('pointerdown',e=>{
 S.dragClickBlock=0; // a new press is a new intention; only the click that ends a drag is swallowed
 if(e.button!==0||DRAG.on||S.page!=='editor'||!S.w)return;
 const grip=e.target.closest('[data-section-drag]');
 const src=grip||e.target.closest('.node[data-drag-id],.palette-item[data-drag-type]');
 if(!src)return;
 const touch=e.pointerType==='touch';
 if(touch&&src.classList.contains('node')&&!e.target.closest('.grip'))return;
 DRAG.on={src,id:src.dataset.dragId,type:src.dataset.dragType,section:grip?Number(grip.dataset.sectionDrag):undefined,
  x:e.clientX,y:e.clientY,px:e.clientX,py:e.clientY,pointer:e.pointerId,kind:e.pointerType||'mouse',started:false};
 // Touch on a step in the left list: press and hold to pick it up (a tap still adds it).
 if(touch&&src.dataset.dragType)DRAG.on.timer=setTimeout(()=>{if(DRAG.on&&!DRAG.on.started){startDrag(DRAG.on.px,DRAG.on.py);navigator.vibrate?.(8);}},350);
});
document.addEventListener('pointermove',e=>{
 const d=DRAG.on;if(!d||e.pointerId!==d.pointer)return;
 d.px=e.clientX;d.py=e.clientY;
 if(!d.started){
  const dist=Math.hypot(e.clientX-d.x,e.clientY-d.y);
  if(d.kind==='touch'&&d.type){if(dist>8){clearTimeout(d.timer);DRAG.on=null;}return;}
  if(dist<(DRAG_THRESHOLD[d.kind]||6))return;
  startDrag(e.clientX,e.clientY);
 }
 e.preventDefault();moveDrag(e.clientX,e.clientY);
},{passive:false});
document.addEventListener('pointerup',e=>{const d=DRAG.on;if(!d||e.pointerId!==d.pointer)return;if(d.started)finishDrag();else endDrag();});
document.addEventListener('pointercancel',e=>{if(DRAG.on&&e.pointerId===DRAG.on.pointer)endDrag();});
// Once a drag has started the page must not scroll under the finger.
document.addEventListener('touchmove',e=>{if(DRAG.on?.started)e.preventDefault();},{passive:false});
document.addEventListener('contextmenu',e=>{if(DRAG.on)e.preventDefault();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&DRAG.on){e.preventDefault();e.stopPropagation();endDrag();}},true);
// The click that ends a drag must not also open, add or select.
document.addEventListener('click',e=>{if(S.dragClickBlock&&Date.now()-S.dragClickBlock<450){S.dragClickBlock=0;e.preventDefault();e.stopImmediatePropagation();}},true);
document.addEventListener('dragstart',e=>{if(e.target.closest?.('.node,.palette-item,.row-grip'))e.preventDefault();});
