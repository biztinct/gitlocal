/* Move the definition, not just its drawing. Targets use stable step IDs. */
function flowTargets(d){
 const targets=[];
 for(const c of containers(d)){
  const stages=c.key==='main'?d.stages.map((_,i)=>i):[c.parent.stage];
  for(const stage of stages){
   const ids=c.key==='main'?c.ids.filter(id=>byId(d,id).stage===stage):c.ids;
   const next=c.key==='main'?c.ids.find(id=>byId(d,id).stage>stage)||null:null;
   for(const before of [...ids,next]){
    if(before==='trigger')continue;
    const where=c.branch?.label||c.parent?.title||stageName(d.stages[stage]);
    targets.push({id:`${c.key}:${stage}:${before||'end'}`,key:c.key,stage,before,
     label:before&&ids.includes(before)?`Before ${byId(d,before).title}`:`End of ${where}`,where});
   }
  }
 }
 return targets;
}
function flowProblem(message){
 if(message.includes('Collect this information'))return 'Keep the form before approval.';
 if(message.includes('Keep one Approval Matrix'))return 'Keep approval on the main path.';
 if(message.includes('Unknown or unavailable token'))return 'Another step needs this answer first.';
 if(message.includes('Add work to every parallel'))return 'Keep at least one step in each parallel path.';
 return message;
}
function placeFlowStep(d,id,target){
 const n=byId(d,id),c=containers(d).find(c=>c.key===target.key);
 if(!n||!c)return 'This position is no longer available.';
 if(!Number.isInteger(target.stage)||!d.stages[target.stage])return 'Choose a stage.';
 if(target.before&&!c.ids.includes(target.before))return 'This position is no longer available.';
 let at=target.before?c.ids.indexOf(target.before):c.ids.length;
 if(c.key==='main'&&at===0)return 'Keep the start first.';
 c.ids.splice(at,0,id);
 descendants(d,id).forEach(id=>{byId(d,id).stage=c.parent?.stage??target.stage;});
 if(c.key==='main'&&c.ids.some((id,i)=>i&&byId(d,id).stage<byId(d,c.ids[i-1]).stage))return 'Choose a position inside this stage.';
 d.nodes.forEach(n=>delete n.pos);
 return null;
}
function moveFlowStep(d,id,target){
 const n=byId(d,id),from=containerFor(d,id),to=containers(d).find(c=>c.key===target.key);
 if(!n||!from||!to)return {error:'This step or path is no longer available.'};
 if(n.type==='trigger')return {error:'Keep the start first.'};
 if(target.before===id&&from.key===to.key){
  if(target.stage===n.stage)return {unchanged:true};
  target={...target,before:from.ids[from.ids.indexOf(id)+1]||null};
 }
 if(to.parent&&descendants(d,id).includes(to.parent.id))return {error:'A group cannot go inside itself.'};
 const copy=clone(d),source=containerFor(copy,id);source.ids.splice(source.ids.indexOf(id),1);
 const error=placeFlowStep(copy,id,target);if(error)return {error};
 if(JSON.stringify(copy.order)===JSON.stringify(d.order)&&copy.nodes.every(n=>n.stage===byId(d,n.id).stage&&JSON.stringify(n.branches||n.steps)===JSON.stringify(byId(d,n.id).branches||byId(d,n.id).steps)))return {unchanged:true};
 const previous=new Set(issues(d).filter(i=>i.severity==='error').map(i=>i.id+'|'+i.text));
 const added=issues(copy).find(i=>i.severity==='error'&&!previous.has(i.id+'|'+i.text));
 if(added)return {error:flowProblem(added.text)};
 return {draft:copy};
}
function insertFlowStep(d,type,target){
 const copy=clone(d),n=makeNode(type,target.stage);
 if(type==='module_move')n.targetStage='phone';
 if(type==='matrix')n.matrixProcess=d.template;
 if(type==='email'&&d.integration){n.optional=true;n.enabled=false;}
 copy.nodes.push(n);const error=placeFlowStep(copy,n.id,target);
 return error?{error}:{draft:copy,id:n.id};
}
