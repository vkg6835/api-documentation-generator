const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const fixture=JSON.parse(execFileSync('py',['-3.13','-c',`import json
from pathlib import Path
from app.server import demo
from app.engine import analyze
from app.quality import load_quality_report
sample=demo('bookstore')
record=analyze(sample['files'],sample['name'])
record.update({'id':'DOC-0001','created_at':'2026-10-29T12:00:00+05:30'})
print(json.dumps({'sample':sample,'record':record,'evaluation':{**json.loads(Path('artifacts/evaluation.json').read_text()),'llm_quality':load_quality_report()}}))`],{cwd:root,encoding:'utf8',maxBuffer:2000000}));
const elements=new Map();
const modelButtons=[{disabled:false,title:''},{disabled:false,title:''}];
function element(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',className:'',value:'',classList:{remove(){},toggle(){}}});return elements.get(id);}
const sandbox=vm.createContext({document:{getElementById:element,querySelectorAll:selector=>selector==='[data-model-action]'?modelButtons:[],addEventListener(){}},window:{addEventListener(){}},location:{hash:'#workspace'},setTimeout:()=>0,clearTimeout(){},console,URLSearchParams,fixture,
fetch:async url=>{const routes={'/api/health':{llm:{available:true,model:'fixture'}},'/api/demo?name=bookstore':fixture.sample,'/api/projects':{items:[fixture.record]},'/api/projects/DOC-0001':fixture.record,'/api/evaluation':fixture.evaluation};assert.ok(Object.hasOwn(routes,url),'Unexpected request: '+url);return {ok:true,json:async()=>structuredClone(routes[url])};}});
async function main(){for(const file of ['schema.js','model-status.js','quality.js'])vm.runInContext(fs.readFileSync(path.join(root,'static',file),'utf8'),sandbox);const source=fs.readFileSync(path.join(root,'static/app.js'),'utf8').replace(/\ninitialize\(\);\s*$/,'\nglobalThis.ready=initialize();');vm.runInContext(source,sandbox);await sandbox.ready;assert.match(element('content').innerHTML,/Let your code explain itself/);for(const [route,label] of [['history','Your API references'],['evaluation','A demo you can defend'],['guide','Code first. Claims second.'],['project/DOC-0001','Bookstore API']]){sandbox.location.hash='#'+route;await vm.runInContext('route()',sandbox);assert.ok(element('content').innerHTML.includes(label),route);assert.ok(!element('content').innerHTML.includes('undefined'),route);}for(const tab of ['reference','evidence','examples']){vm.runInContext(`state.tab='${tab}';state.endpointIndex=2;globalThis.rendered=projectPage(state.project)`,sandbox);assert.ok(sandbox.rendered.length>1000);assert.ok(!sandbox.rendered.includes('undefined'));}assert.equal(vm.runInContext("h('<script>bad()</script>')",sandbox),'&lt;script&gt;bad()&lt;/script&gt;');assert.equal(vm.runInContext("h('x\"y')",sandbox),'x&quot;y');await additionalChecks();console.log('Frontend smoke passed: pages, tabs, schema fields/arrays, model readiness and HTML escaping. No visual browser check.');}
async function additionalChecks(){
  vm.runInContext('globalThis.rendered=evaluationPage(fixture.evaluation)',sandbox);
  for(const expected of ['8 endpoints · 16 drafts','Codex (assistant)','View full recorded output','View source and usage context','1.50 / 2'])assert.ok(sandbox.rendered.includes(expected),expected);
  const untrusted=structuredClone(fixture.evaluation.llm_quality);untrusted.cases[0].drafts[0].output.behavior='<img src=x onerror=bad()> owner';sandbox.unsafeQuality=untrusted;
  vm.runInContext('globalThis.rendered=qualityPanel(unsafeQuality)',sandbox);assert.ok(!sandbox.rendered.includes('<img'));assert.ok(sandbox.rendered.includes('&lt;img'));
  vm.runInContext("globalThis.rendered=schemaDetails(state.project.endpoints.find(e=>e.method==='POST'),state.project.schemas)",sandbox);
  for(const expected of ['BookCreate','title','author','price','published','Min length: 1','Max length: 120','Minimum: 0','false','Response 201'])assert.ok(sandbox.rendered.includes(expected),expected);
  vm.runInContext("globalThis.rendered=schemaDetails(state.project.endpoints.find(e=>e.name==='list_books'),state.project.schemas)",sandbox);
  assert.match(sandbox.rendered,/Fields of each array item/);
  assert.match(sandbox.rendered,/array of Book/);
  vm.runInContext("globalThis.rendered=schemaCard('Unsafe <img>',{type:'object',properties:{'<script>':{type:'string',description:'<img src=x>',pattern:'<test>'}},required:[]},{})",sandbox);
  assert.ok(!sandbox.rendered.includes('<img'));
  assert.match(sandbox.rendered,/&lt;script&gt;/);
  assert.equal(vm.runInContext("resolvedSchema({\u0024ref:'#/components/schemas/Loop'},{Loop:{\u0024ref:'#/components/schemas/Loop'}}).\u0024ref",sandbox),'#/components/schemas/Loop');
  for(const [status,label] of [[{available:false,state:'unavailable',message:'Ollama unavailable.',action:'Start Ollama.'},'Ollama unavailable'],[{available:false,state:'missing_model',message:'Model missing.',action:'Run ollama pull gemma:2b.'},'Model missing'],[{available:true,busy:true,model:'gemma:2b',message:'Drafting.',action:'Wait.'},'Drafting descriptions']]){
    sandbox.testStatus=status;vm.runInContext('state.health={llm:testStatus};updateModelStatus()',sandbox);
    assert.ok(element('model-status').textContent.includes(label));assert.ok(!element('model-notice').hidden);assert.ok(modelButtons.every(button=>button.disabled));
  }
  vm.runInContext("state.health={llm:{available:true,busy:false,model:'gemma:2b'}};updateModelStatus()",sandbox);
  assert.ok(element('model-notice').hidden);assert.ok(modelButtons.every(button=>!button.disabled));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
