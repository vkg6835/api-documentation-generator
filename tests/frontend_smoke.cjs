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
sample=demo('bookstore')
record=analyze(sample['files'],sample['name'])
record.update({'id':'DOC-0001','created_at':'2026-10-29T12:00:00+05:30'})
print(json.dumps({'sample':sample,'record':record,'evaluation':json.loads(Path('artifacts/evaluation.json').read_text())}))`],{cwd:root,encoding:'utf8',maxBuffer:2000000}));
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',className:'',value:'',classList:{remove(){},toggle(){}}});return elements.get(id);}
const sandbox=vm.createContext({document:{getElementById:element,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},location:{hash:'#workspace'},setTimeout:()=>0,clearTimeout(){},console,URLSearchParams,fixture,
fetch:async url=>{const routes={'/api/health':{llm:{available:true,model:'fixture'}},'/api/demo?name=bookstore':fixture.sample,'/api/projects':{items:[fixture.record]},'/api/projects/DOC-0001':fixture.record,'/api/evaluation':fixture.evaluation};assert.ok(Object.hasOwn(routes,url),'Unexpected request: '+url);return {ok:true,json:async()=>structuredClone(routes[url])};}});
async function main(){const source=fs.readFileSync(path.join(root,'static/app.js'),'utf8').replace(/\ninitialize\(\);\s*$/,'\nglobalThis.ready=initialize();');vm.runInContext(source,sandbox);await sandbox.ready;assert.match(element('content').innerHTML,/Let your code explain itself/);for(const [route,label] of [['history','Your API references'],['evaluation','A demo you can defend'],['guide','Code first. Claims second.'],['project/DOC-0001','Bookstore API']]){sandbox.location.hash='#'+route;await vm.runInContext('route()',sandbox);assert.ok(element('content').innerHTML.includes(label),route);assert.ok(!element('content').innerHTML.includes('undefined'),route);}for(const tab of ['reference','evidence','examples']){vm.runInContext(`state.tab='${tab}';state.endpointIndex=2;globalThis.rendered=projectPage(state.project)`,sandbox);assert.ok(sandbox.rendered.length>1000);assert.ok(!sandbox.rendered.includes('undefined'));}assert.equal(vm.runInContext("h('<script>bad()</script>')",sandbox),'&lt;script&gt;bad()&lt;/script&gt;');assert.equal(vm.runInContext("h('x\"y')",sandbox),'x&quot;y');console.log('Frontend smoke passed: 5 pages, 3 endpoint tabs, HTML escaping. No visual browser check.');}
main().catch(error=>{console.error(error);process.exitCode=1;});
