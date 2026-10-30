// Trusted test harness. Scenarios are declarative; application source never runs in Node.
import {createServer} from 'node:http';
import {readFile, realpath, stat} from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
let input='';
for await (const chunk of process.stdin) {
  input += chunk;
  if (input.length > 500000) throw Error('InputTooLarge');
}
const payload=JSON.parse(input);
const started=performance.now();
let browser, server, deadline, timedOut=false;
const checks=[];
const result=(status, extra={})=>({status,checks,functional_success:null,end_to_end_pass_rate:null,e2e_pass_rate:null,build_success:null,...extra});
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.webp':'image/webp','.jpg':'image/jpeg','.woff':'font/woff','.woff2':'font/woff2'};
const csp="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; worker-src 'none'";
try {
  const {chromium}=require(path.join(payload.tool_directory,'playwright'));
  const {expect}=require(path.join(payload.tool_directory,'playwright/test.js'));
  const root=await realpath(payload.build_dir), allowed=new Set(payload.files);
  server=createServer(async(req,res)=>{
    try {
      if(!['GET','HEAD'].includes(req.method)) {res.writeHead(405);res.end();return;}
      const pathname=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);
      const relative=pathname==='/'?'index.html':pathname.slice(1);
      if(!allowed.has(relative)) {res.writeHead(404);res.end();return;}
      const filename=await realpath(path.join(root,relative));
      if(!filename.startsWith(root+path.sep) || (await stat(filename)).size>10000000) {res.writeHead(403);res.end();return;}
      const body=await readFile(filename);
      res.writeHead(200,{'Content-Type':mime[path.extname(filename)]||'application/octet-stream','Content-Security-Policy':csp,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
      res.end(req.method==='HEAD'?undefined:body);
    } catch {res.writeHead(404);res.end();}
  });
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const origin=`http://127.0.0.1:${server.address().port}`;
  deadline=setTimeout(()=>{timedOut=true;browser?.close().catch(()=>{});server?.close();},Math.max(200,(payload.max_seconds-.5)*1000));
  browser=await chromium.launch({headless:true,chromiumSandbox:true,timeout:Math.min(15000,payload.max_seconds*1000)});
  for(const scenario of payload.scenarios) {
    const row={path:scenario.source_path||'index.html',kind:'browser',scenario_id:scenario.id,requirements:scenario.requirements,status:'running',completed_steps:0};
    checks.push(row);
    const violations=[];
    const violation=kind=>{if(violations.length<32)violations.push(kind);};
    const context=await browser.newContext({viewport:scenario.viewport||{width:1280,height:800},acceptDownloads:false,serviceWorkers:'block',permissions:[]});
    try {
      await context.route('**/*',async route=>{
        const request=route.request();
        if(new URL(request.url()).origin!==origin || !['GET','HEAD'].includes(request.method())) {violation('external-network-or-write-blocked');await route.abort('blockedbyclient');}
        else await route.continue();
      });
      await context.routeWebSocket(/.*/,async ws=>{violation('websocket-blocked');await ws.close();});
      const page=await context.newPage();
      context.on('page',other=>{if(other!==page){violation('popup-blocked');other.close().catch(()=>{});}});
      page.on('download',download=>{violation('download-blocked');download.cancel().catch(()=>{});});
      page.on('dialog',dialog=>{violation('dialog-blocked');dialog.dismiss().catch(()=>{});});
      page.on('console',message=>{if(/violates.*Content Security Policy|Content Security Policy.*violat/i.test(message.text()))violation('csp-blocked-resource');});
      page.on('pageerror',()=>violation('application-runtime-error'));
      page.setDefaultTimeout(2000);
      await page.goto(origin,{waitUntil:'load',timeout:Math.min(10000,payload.max_seconds*1000)});
      for(const step of scenario.steps) {
        if(timedOut)throw Error('DeadlineExceeded');
        if(step.action==='reload')await page.reload({waitUntil:'load'});
        else {
          const target=step.target;
          const locator=target.test_id!==undefined?page.getByTestId(target.test_id):page.getByRole(target.role,target.name!==undefined?{name:target.name,exact:true}:{});
          switch(step.action){
            case 'fill':await locator.fill(step.value);break;
            case 'click':await locator.click();break;
            case 'select':await locator.selectOption(step.value);break;
            case 'press':await locator.press(step.value);break;
            case 'expect_text':await expect(locator).toContainText(step.value,{timeout:2000});break;
            case 'expect_count':await expect(locator).toHaveCount(step.count,{timeout:2000});break;
            case 'expect_visible':await expect(locator).toBeVisible({timeout:2000});break;
            case 'expect_value':await expect(locator).toHaveValue(step.value,{timeout:2000});break;
            case 'expect_checked':step.checked?await expect(locator).toBeChecked({timeout:2000}):await expect(locator).not.toBeChecked({timeout:2000});break;
            default:throw Error('UnsupportedAction');
          }
        }
        row.completed_steps++;
      }
      if(violations.length)throw Error('ProhibitedActivity');
      row.status='passed';
    } catch(error) {
      row.status=timedOut?'timeout':'failed';
      row.diagnostic=violations.length?'Application attempted prohibited activity or raised a runtime error':'Declarative acceptance action/assertion failed';
      row.error_classification=String(error.name||'Error').slice(0,80);
    } finally {
      row.blocked_activity=violations;
      await context.close();
    }
  }
  const passed=checks.filter(c=>c.status==='passed').length;
  process.stdout.write(JSON.stringify(result(passed===checks.length?'passed':'failed',{functional_success:passed===checks.length,end_to_end_pass_rate:passed/payload.scenarios.length,e2e_pass_rate:passed/payload.scenarios.length,duration_ms:Math.round(performance.now()-started),browser:'chromium',tool:'playwright@1.64.1',scenario_count:payload.scenarios.length,scope:'Only independently authored declared scenarios; no general application correctness claim',isolation:{fresh_context:true,chromium_sandbox:true,external_network:'blocked',service_workers:'blocked',downloads:'blocked'}})));
} catch(error) {
  const unavailable=/Executable doesn't exist|browserType.launch|Failed to launch|ENOENT|MODULE_NOT_FOUND/i.test(String(error));
  process.stdout.write(JSON.stringify(result(timedOut?'timeout':unavailable?'unavailable':'error',{error_classification:timedOut?'DeadlineExceeded':unavailable?'BrowserUnavailable':'HarnessError'})));
} finally {
  clearTimeout(deadline);
  await browser?.close().catch(()=>{});
  if(server){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
}
