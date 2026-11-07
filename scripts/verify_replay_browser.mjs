// Exercise the replay UI with an inert adversarial import. Nothing is uploaded.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';

const require=createRequire(import.meta.url);
const {chromium}=require('../tooling/browser/node_modules/playwright');
const base=new URL(process.argv[2]).origin;
const marker='/__recursa_replay_probe__';
const browser=await chromium.launch({headless:true,chromiumSandbox:true});
try{
  const page=await browser.newPage({viewport:{width:390,height:844}});
  const requests=[];
  page.on('request',request=>requests.push(request.url()));
  await page.goto(base+'/#execution');
  const content='<script>globalThis.recursaProbe=true</script><img src="'+marker+'" onerror="globalThis.recursaProbe=true">';
  const imported={id:'local-replay-security-probe',events:[],artifacts:[{path:'probe.html',content}]};
  await page.locator('#import-run').setInputFiles({
    name:'probe.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(imported))
  });
  await page.waitForFunction(()=>document.querySelector('#run-select').value==='local-replay-security-probe');
  await page.getByRole('button',{name:'Generated artifacts'}).click();
  await page.waitForFunction(text=>document.querySelector('#source-code')?.textContent===text,content);
  assert.equal(await page.locator('#source-code img,#source-code script').count(),0);
  assert.equal(await page.evaluate(()=>globalThis.recursaProbe),undefined);
  const violation=await page.evaluate(()=>new Promise((resolve,reject)=>{
    const timeout=setTimeout(()=>reject(Error('No inline script CSP violation observed')),3000);
    document.addEventListener('securitypolicyviolation',event=>{
      clearTimeout(timeout);
      resolve({directive:event.effectiveDirective,blocked:event.blockedURI});
    },{once:true});
    const script=document.createElement('script');
    script.textContent='globalThis.recursaProbe=true';
    document.head.append(script);
  }));
  assert.match(violation.directive,/^script-src/);
  assert.equal(violation.blocked,'inline');
  assert.equal(await page.evaluate(()=>globalThis.recursaProbe),undefined);
  assert.equal(requests.some(url=>url.includes(marker)),false);
  assert.ok(requests.every(url=>new URL(url).origin===base));
  const response=await page.request.get(base+'/api/runs/local-replay-security-probe');
  assert.equal(response.status(),404);
  console.log('Replay import remained local and inert; browser blocked an unauthorized inline script');
}finally{
  await browser.close();
}
