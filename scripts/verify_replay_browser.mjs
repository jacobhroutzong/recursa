// Exercise Studio navigation and an inert adversarial import. Nothing is uploaded.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';

const require=createRequire(import.meta.url);
const {chromium}=require('../tooling/browser/node_modules/playwright');
const base=new URL(process.argv[2]).origin;
const marker='/__recursa_replay_probe__';
const harnessLab='https://jacobroutzong.dev/projects/harness2-lab/';
const browser=await chromium.launch({headless:true,chromiumSandbox:true});

async function verifyNavigation(studio,width){
  const page=await browser.newPage({viewport:{width,height:844}});
  try{
    await page.goto(new URL('#overview',studio).href);
    const areas=page.locator('.research-areas');
    const agentLink=page.getByRole('navigation',{name:'Studio sections'})
      .getByRole('link',{name:'Agent Optimization',exact:true});
    assert.ok(await page.getByRole('heading',{name:'Recursa Studio',exact:true}).isVisible());
    assert.ok(await areas.getByRole('heading',{name:'Application Synthesis',exact:true}).isVisible());
    assert.ok(await areas.getByRole('heading',{name:'Agent Optimization',exact:true}).isVisible());
    assert.equal(await areas.getByRole('link',{name:'Agent Optimization',exact:true}).getAttribute('href'),harnessLab);
    assert.ok(await areas.getByText(/replays recorded evidence/).isVisible());
    assert.ok(await areas.getByText(/scripted, stochastic scores/).isVisible());
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth===window.innerWidth));
    await page.getByRole('button',{name:/Browse benchmark traces/}).waitFor();

    await page.getByRole('link',{name:'Recursa Studio overview'}).focus();
    await page.keyboard.press('Tab');
    assert.ok(await page.getByRole('button',{name:'Overview'}).evaluate(button=>button===document.activeElement));
    await page.keyboard.press('Tab');
    assert.ok(await agentLink.evaluate(link=>link===document.activeElement && link.matches(':focus-visible')));

    await areas.getByRole('link',{name:'Browse specifications'}).press('Enter');
    await page.waitForFunction(()=>location.hash==='#playground' && !document.querySelector('#view-playground').hidden);
    await page.locator('#preset-list button').first().waitFor();
    assert.ok(await areas.isHidden());
    for(const [name,view] of [
      ['Execution explorer','execution'],['Generated artifacts','artifacts'],['Benchmarks','benchmarks'],
      ['Research & architecture','research'],['Build progress','progress'],['Security checks','security'],
      ['Overview','overview'],
    ]){
      await page.getByRole('button',{name}).press('Enter');
      assert.equal(new URL(page.url()).hash,'#'+view);
      assert.ok(await page.locator('#view-'+view).isVisible());
      if(view==='benchmarks')await page.locator('#series-results').waitFor();
    }
    assert.ok(await areas.isVisible());

    await page.route(harnessLab,route=>route.fulfill({
      contentType:'text/plain; charset=utf-8',body:'Harness² Lab navigation test',
    }));
    await agentLink.press('Enter');
    await page.waitForURL(harnessLab);
    assert.equal(await page.locator('body').innerText(),'Harness² Lab navigation test');
  }finally{
    await page.close();
  }
}

try{
  for(const studio of [base+'/',...process.argv.slice(3,4)]){
    for(const width of [390,1440])await verifyNavigation(studio,width);
    console.log(`Research areas, existing views, and keyboard navigation passed at 390px and 1440px on ${studio}`);
  }
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
