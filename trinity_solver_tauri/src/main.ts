import './style.css';
import {invoke} from '@tauri-apps/api/core';
import {TARGET_GUIDE_V5, TARGET_GUIDE_V45} from './target-guides';

type Kind = 'anomaly'|'relation'|'linear'|'targets';
type SolverResponse = {ok:boolean;error?:string;result?:any};
type BackendStatus = {ok:boolean;error?:string;python:string;version:string;backend_bundled:boolean};
type HistoryEntry = {time:string;kind:string;status:string;verified:boolean;duration:number};
const el=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const data:Record<Exclude<Kind,'targets'>,{name:string,title:string,accent:string,description:string,help:string,file:string,sample:()=>Record<string,unknown>}> = {
  anomaly:{name:'ANOMALIAS',title:'Detectar',accent:'anomalias.',description:'Identifique observações atípicas em séries numéricas com estimadores robustos e diagnóstico reproduzível.',help:'Informe uma série de valores. O método robusto sinaliza observações que merecem investigação.',file:'anomaly_scan.json',sample:()=>({kind:'anomaly_scan',values:Array.from({length:60},(_,i)=>i===37?17.8: Number((1.2+Math.sin(i/4)*0.25+Math.cos(i/7)*0.12).toFixed(3))),threshold:3.5})},
  relation:{name:'RELAÇÕES',title:'Pesquisar',accent:'relações.',description:'Teste relações matemáticas em dados e controle falsos positivos com permutações e separação de amostras.',help:'Forneça vetores x e y com pelo menos 30 pares. Use o p-valor exploratório somente como indicação estatística.',file:'relation_search.json',sample:()=>({kind:'relation_search',x:Array.from({length:60},(_,i)=>Number((i/4-7.5).toFixed(3))),y:Array.from({length:60},(_,i)=>Number((3+1.5*(i/4-7.5)+Math.sin(i*2.3)*0.27).toFixed(3))),permutations:99})},
  linear:{name:'SISTEMAS LINEARES',title:'Resolver',accent:'sistemas.',description:'Resolva sistemas lineares com diagnóstico de posto, erro residual e verificação numérica.',help:'Forneça uma matriz A e um vetor b. Sistemas incompatíveis recebem solução aproximada identificada.',file:'linear_system.json',sample:()=>({kind:'linear_system',A:[[3,1,0],[1,4,1],[0,2,5]],b:[9,15,19]})},
};
const HISTORY_KEY='trinity.solver.v5.history';
let current:Exclude<Kind,'targets'>='anomaly';let running=false;
const fmt=(n:number,digits=3)=>Number.isFinite(n)?n.toLocaleString('pt-BR',{maximumFractionDigits:digits}):String(n);
const bytes=(s:string)=>new TextEncoder().encode(s).length;
function createMatrix(){const mark=el('matrixMark');for(let i=0;i<121;i++){const k=document.createElement('i');if((i*7+13)%11<3 || (i%11===Math.floor(i/11)))k.className='active';mark.appendChild(k);}}
function currentProblem(){const raw=el<HTMLTextAreaElement>('problemInput').value;const result=JSON.parse(raw);if(typeof result!=='object'||result===null||Array.isArray(result))throw new Error('O problema deve ser um objeto JSON.');return result;}
function validate(){const input=el<HTMLTextAreaElement>('problemInput');const label=el('validationStatus');el('sizeCounter').textContent=`${bytes(input.value).toLocaleString('pt-BR')} bytes`;
  try{currentProblem();label.textContent='✓ JSON válido';label.className='valid';return true;}catch(e){label.textContent=`✕ ${(e as Error).message.slice(0,60)}`;label.className='invalid';return false;}}
function displayTab(kind:Kind){
  if(kind==='targets'){
    document.querySelectorAll<HTMLButtonElement>('.nav-item').forEach(b=>b.classList.toggle('selected',b.dataset.tab==='targets'));
    el('breadcrumb').textContent='TARGET SCRIPTS';
    el('heroTitle').replaceChildren(document.createTextNode('Executar '),Object.assign(document.createElement('em'),{textContent:'Targets.'}));
    el('heroDescription').textContent='Cole scripts como na versão anterior. JavaScript com invoke() e log(), ou Python 3 no mesmo editor. Os scripts executam localmente com as permissões do seu usuário.';
    el('targetWorkspace').classList.remove('hidden');el('numericWorkspace').classList.add('hidden');
    return;
  }
  el('targetWorkspace').classList.add('hidden');el('numericWorkspace').classList.remove('hidden');
  current=kind;const d=data[kind];document.querySelectorAll<HTMLButtonElement>('.nav-item').forEach(b=>b.classList.toggle('selected',b.dataset.tab===kind));el('breadcrumb').textContent=d.name;el('heroTitle').replaceChildren(document.createTextNode(`${d.title} `),Object.assign(document.createElement('em'),{textContent:d.accent}));el('heroDescription').textContent=d.description;el('editorHelp').textContent=d.help;el('inputFilename').textContent=d.file;el<HTMLTextAreaElement>('problemInput').value=JSON.stringify(d.sample(),null,2);el('resultContent').classList.add('hidden');el('emptyState').classList.remove('hidden');el('resultTag').textContent='SEM EXECUÇÃO';el('resultTag').className='tag muted';validate();}
function history():HistoryEntry[]{try{return JSON.parse(localStorage.getItem(HISTORY_KEY)||'[]') as HistoryEntry[];}catch{return []}}
function drawHistory(){const rows=history();el('statRuns').textContent=String(rows.length);const host=el('historyList');host.replaceChildren();if(!rows.length){host.textContent='Nenhuma execução registrada.';host.className='history-list history-empty';return;}host.className='history-list';for(const row of rows.slice(0,6)){const div=document.createElement('div');div.className='history-row';const a=document.createElement('b');a.textContent=row.kind;const b=document.createElement('span');b.textContent=row.time;const c=document.createElement('span');c.className=row.verified?'good':'bad';c.textContent=row.status;const d=document.createElement('span');d.textContent=`${fmt(row.duration,1)} ms`;div.append(a,b,c,d);host.append(div)}}
function addHistory(res:any){const kind=String(res.kind);const entry:HistoryEntry={kind,time:new Date().toLocaleString('pt-BR'),status:String(res.status),verified:!!res.verified,duration:Number(res.elapsed_ms||0)};try{localStorage.setItem(HISTORY_KEY,JSON.stringify([entry,...history()].slice(0,80)));}catch{}drawHistory()}
function metric(name:string,value:string){const div=document.createElement('div');div.className='metric';const k=document.createElement('span');k.textContent=name;const v=document.createElement('strong');v.textContent=value;div.append(k,v);return div;}
function chart(scores:(number|null)[],indices:number[]){const host=el('visualization');host.replaceChildren();if(!scores.length||scores.length>3000)return;const clean=scores.map(v=>typeof v==='number'&&Number.isFinite(v)?v:0);const max=Math.max(...clean,1);const w=560,h=120,left=22,right=15,top=11,bottom=17;const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.setAttribute('aria-label','Pontuações de anomalia por amostra');const path=document.createElementNS(svg.namespaceURI,'path');const pts=clean.map((v,i)=>`${i?'L':'M'}${(left+i*(w-left-right)/Math.max(1,clean.length-1)).toFixed(2)},${(h-bottom-v/max*(h-top-bottom)).toFixed(2)}`).join(' ');path.setAttribute('d',pts);path.setAttribute('stroke','#4bdfbf');path.setAttribute('stroke-width','2');path.setAttribute('fill','none');svg.appendChild(path);for(const i of indices.slice(0,60)){const circle=document.createElementNS(svg.namespaceURI,'circle');circle.setAttribute('cx',String(left+i*(w-left-right)/Math.max(1,clean.length-1)));circle.setAttribute('cy',String(h-bottom-clean[i]/max*(h-top-bottom)));circle.setAttribute('r','4');circle.setAttribute('fill','#efbf69');svg.appendChild(circle);}host.appendChild(svg);}
function showResult(res:any){const ok=!!res.verified;el('resultContent').classList.remove('hidden');el('emptyState').classList.add('hidden');el('resultTag').textContent=ok?'VERIFICADO':'NÃO VERIFICADO';el('resultTag').className=ok?'tag':'tag muted';el('resultIcon').textContent=ok?'✓':'!';const labels:Record<string,string>={solved:'Solução encontrada',approximate:'Solução aproximada',candidate:'Candidato identificado',no_candidate:'Nenhuma anomalia detectada',inconclusive:'Evidência inconclusiva',failed:'Verificação falhou'};el('resultStatus').textContent=labels[res.status]||String(res.status);el('resultSubstatus').textContent=`${res.method} · ${fmt(Number(res.elapsed_ms),1)} ms`;
  const diag=res.diagnostics||{};const metrics=el('metrics');metrics.replaceChildren();
  if(res.kind==='anomaly_scan'){metrics.append(metric('CANDIDATOS',String(res.output?.candidate_indices?.length??0)),metric('AMOSTRAS',String(diag.n_samples??0)),metric('MEDIANA',fmt(diag.median)),metric('LIMIAR',fmt(diag.threshold)));chart(res.output?.scores||[],res.output?.candidate_indices||[])}
  else {el('visualization').replaceChildren();if(res.kind==='relation_search')metrics.append(metric('MODELO',String(res.output?.model||'indefinido')),metric('P-VALOR',fmt(diag.selection_adjusted_permutation_p,4)),metric('GANHO NO HOLDOUT',`${fmt((diag.candidate_lift||0)*100,1)}%`),metric('AMOSTRAS',String(diag.n_samples??0)));else metrics.append(metric('POSTO',String(diag.rank??'?')),metric('RESÍDUO',fmt(diag.residual_norm,8)),metric('EQUAÇÕES',String(diag.equations??0)),metric('VARIÁVEIS',String(diag.unknowns??0)));}
  el('resultJson').textContent=JSON.stringify({output:res.output,diagnostics:res.diagnostics,status:res.status},null,2);
  el('caveat').textContent=res.caveat||'Resultados devem ser verificados independentemente.';
}
async function checkStatus(){try{const st=await invoke<BackendStatus>('solver_status');const live=st.ok;el('connectionLight').className=`pulse ${live?'online':'offline'}`;el('connectionStatus').textContent=live?'Motor conectado':'Motor indisponível';el('statEngine').textContent=live?'Operacional':'Indisponível';el('statEngine').setAttribute('title',live?st.python:(st.error||''));}catch(e){el('connectionStatus').textContent='Bridge Tauri indisponível';el('connectionLight').className='pulse offline';el('statEngine').textContent='Offline';console.error(e);}}
async function execute(){if(running)return;if(!validate())return;const button=el<HTMLButtonElement>('runBtn');try{const problem=currentProblem();const seed=Number(el<HTMLInputElement>('seedInput').value);if(!Number.isSafeInteger(seed))throw new Error('Semente inválida.');running=true;button.disabled=true;button.textContent='Processando...';const answer=await invoke<SolverResponse>('solver_run',{problem,seed});if(!answer.ok)throw new Error(answer.error||'Falha do motor');showResult(answer.result);addHistory(answer.result);}
catch(e){el('emptyState').classList.remove('hidden');el('resultContent').classList.add('hidden');el('emptyState').replaceChildren();const h=document.createElement('h3');h.textContent='Não foi possível executar.';const p=document.createElement('p');p.textContent=String(e);el('emptyState').append(h,p);el('resultTag').textContent='ERRO';el('resultTag').className='tag muted';}
finally{running=false;button.disabled=false;button.innerHTML='<span class="play-icon">▶</span> Executar análise <span>↗</span>';}}
createMatrix();displayTab('targets');drawHistory();checkStatus();
document.querySelectorAll<HTMLButtonElement>('.nav-item').forEach(btn=>btn.addEventListener('click',()=>displayTab(btn.dataset.tab as Kind)));
el('sampleBtn').addEventListener('click',()=>{el<HTMLTextAreaElement>('problemInput').value=JSON.stringify(data[current].sample(),null,2);validate();});
el('problemInput').addEventListener('input',validate);el('runBtn').addEventListener('click',execute);
el('clearHistory').addEventListener('click',()=>{localStorage.removeItem(HISTORY_KEY);drawHistory();});


// Target Scripts: compatibilidade com scripts da versão antiga.
const TARGET_STORAGE='trinity.solver.targets.v501';
const TARGET_MODE='trinity.solver.targets.mode.v501';
const TARGET_JS=`// Target Script JavaScript · API compatível com o app antigo
// Use invoke(command, args), log(text) e runPython(code).
const result = await invoke('solver_run', {
  problem: {kind:'linear_system', A:[[3,1],[1,2]], b:[9,8]}, seed:5711
});
log('Resultado: ' + JSON.stringify(result, null, 2));

// Exemplo para código Python:
// const output = await invoke('run_python_script', {
//   script: "print('Trinity 11x11 pronto')"
// });
// log(output);
`;
const TARGET_PY=`# Target Python · roda no workspace Trinity 11x11
import numpy as np
from core.primary_core import solve_problem
print('TRINITY TARGET PYTHON')
r = solve_problem({'kind':'linear_system', 'A':[[3,1],[1,2]], 'b':[9,8]})
print(r['output'])
`;
const targetEditor=el<HTMLTextAreaElement>('scriptInput');
const targetMode=el<HTMLSelectElement>('targetMode');
let runningTarget=false;
function logTarget(message:unknown){
  const consoleEl=el<HTMLPreElement>('targetLog');
  const raw=typeof message==='string'?message:JSON.stringify(message,null,2);
  consoleEl.textContent+=(consoleEl.textContent?'\n':'')+raw;
  consoleEl.scrollTop=consoleEl.scrollHeight;
}
function targetStats(){el('targetSize').textContent=`${bytes(targetEditor.value).toLocaleString('pt-BR')} bytes · salvo localmente`;}
function saveTarget(){try{localStorage.setItem(TARGET_STORAGE,targetEditor.value);localStorage.setItem(TARGET_MODE,targetMode.value);}catch{}targetStats();}
function newSample(){targetEditor.value=targetMode.value==='python'?TARGET_PY:TARGET_JS;saveTarget();}
async function executeTarget(){
  if(runningTarget)return;
  const script=targetEditor.value;
  if(!script.trim()){el('targetStatus').textContent='Cole um script antes de executar.';return;}
  if(bytes(script)>192_000){el('targetStatus').textContent='Target excede 192 KB.';return;}
  const started=performance.now();let calls=0;
  let active='inicializando';
  const button=el<HTMLButtonElement>('runTargetBtn');
  runningTarget=true;button.disabled=true;button.textContent='Executando...';
  el('targetLog').textContent='';el('targetStatus').textContent='▶ Executando Target';
  const interval=window.setInterval(()=>{
    const seconds=(performance.now()-started)/1000;
    el('targetElapsed').textContent=`${seconds.toFixed(1)} s`;
    el('targetStatus').textContent=`▶ ${active} · ${calls} chamada(s) · ${seconds.toFixed(1)}s`;
  },250);
  const safeInvoke=async (cmd:string,args?:Record<string,unknown>):Promise<any>=>{
    if(!['solver_status','solver_run','run_python_script'].includes(cmd)){
      throw new Error(`Comando '${cmd}' não disponível na v5.0.1. O app anterior tinha módulos 9Q/128Q que ainda não foram portados.`);
    }
    calls++;active=cmd;logTarget(`[CALL #${calls}] ${cmd}`);
    const start=performance.now();
    try{const result=await invoke(cmd,args);logTarget(`[DONE #${calls}] ${cmd} ${((performance.now()-start)/1000).toFixed(2)}s`);return result;}
    catch(e){logTarget(`[FAIL #${calls}] ${cmd}: ${String(e)}`);throw e;}
  };
  try{
    if(targetMode.value==='python'){
      const output=await safeInvoke('run_python_script',{script});
      logTarget(output);
    }else{
      // Preserve the former Target API and top-level await support.
      const transformed=script.replace(/^(\s*)\(async\s/m,'$1await (async ');
      const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
      const fn=new AsyncFunction('invoke','log','runPython',transformed);
      const output=await fn(safeInvoke,logTarget,(code:string)=>safeInvoke('run_python_script',{script:code}));
      if(output!==undefined)logTarget(output);
    }
    active='concluído';
    el('targetStatus').textContent=`✓ Target concluído em ${((performance.now()-started)/1000).toFixed(2)}s`;
  }catch(e){active='erro';logTarget(`[ERRO] ${String(e)}`);el('targetStatus').textContent='✕ Target falhou';}
  finally{
    window.clearInterval(interval);el('targetElapsed').textContent=`${((performance.now()-started)/1000).toFixed(1)} s`;
    runningTarget=false;button.disabled=false;button.innerHTML='<span class="play-icon">▶</span> Run Target <span>↗</span>';
  }
}
function targetGuide():string {return TARGET_GUIDE_V5;}
function targetGuideLegacy():string {return TARGET_GUIDE_V45;}

async function copyTargetGuideText(content:string):Promise<void> {
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard API indisponível');
    await navigator.clipboard.writeText(content);
    return;
  } catch {
    const field=document.createElement('textarea');
    field.value=content;
    field.setAttribute('readonly','');
    field.setAttribute('aria-hidden','true');
    field.style.cssText='position:fixed;top:0;left:-10000px;opacity:0;';
    const previous=document.activeElement as HTMLElement | null;
    document.body.appendChild(field);
    field.focus();field.select();
    let ok=false;
    try { ok=document.execCommand('copy'); }
    finally { field.remove();previous?.focus(); }
    if (!ok) throw new Error('Cópia automática indisponível');
  }
}
function showManualTargetGuide(content:string):void {
  let preview=document.getElementById('targetGuideManual') as HTMLTextAreaElement | null;
  if (!preview) {
    preview=document.createElement('textarea');
    preview.id='targetGuideManual';
    preview.className='target-guide-manual';
    preview.readOnly=true;
    preview.setAttribute('aria-label','Guia de Target Scripts para copiar com Command C');
    const pane=el('targetWorkspace').querySelector('.target-editor-pane');
    if (!pane) throw new Error('Editor de Target não encontrado');
    pane.appendChild(preview);
  }
  preview.value=content;
  preview.focus();preview.select();
}

try{const saved=localStorage.getItem(TARGET_MODE);if(saved==='python'||saved==='javascript')targetMode.value=saved;}catch{}
try{targetEditor.value=localStorage.getItem(TARGET_STORAGE)||'';}catch{}
if(!targetEditor.value)newSample();targetStats();
targetEditor.addEventListener('input',saveTarget);
targetMode.addEventListener('change',()=>{newSample();});
el('runTargetBtn').addEventListener('click',executeTarget);
el('targetExampleBtn').addEventListener('click',newSample);
el('targetClearBtn').addEventListener('click',()=>{targetEditor.value='';saveTarget();targetEditor.focus();});
async function handleGuideCopy(content:string,which:string):Promise<void> {
  try {
    await copyTargetGuideText(content);
    el('targetGuideFeedback').textContent='✓ '+which+' copiado';
    el('targetStatus').textContent='Guia '+which+' copiado para a área de transferência.';
  } catch {
    el('targetGuideFeedback').textContent='Use ⌘C no texto selecionado';
    el('targetStatus').textContent='Cópia automática bloqueada. Pressione ⌘C no texto selecionado.';
    showManualTargetGuide(content);
  }
}
el('targetGuideBtn').addEventListener('click',()=>handleGuideCopy(targetGuide(),'5.0'));
el('targetLegacyGuideBtn').addEventListener('click',()=>handleGuideCopy(targetGuideLegacy(),'4.5'));
el('copyTargetOutputBtn').addEventListener('click',async()=>{await navigator.clipboard.writeText(el('targetLog').textContent||'');el('targetStatus').textContent='Output copiado.';});
