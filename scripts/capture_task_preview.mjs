// Capture the verified Task Management reference build in an isolated browser.
import assert from 'node:assert/strict';
import {readFile, realpath} from 'node:fs/promises';
import {createRequire} from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);
const {chromium} = require('../tooling/browser/node_modules/playwright');
const [reportPath, output] = process.argv.slice(2);
const report = JSON.parse(await readFile(reportPath, 'utf8'));
assert.equal(report.status, 'passed');
assert.equal(report.verification.functional_success, true);
const root = await realpath(report.verification.dist_path);
const origin = 'http://localhost';
const types = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css'};
const blocked = [];
const browser = await chromium.launch({headless:true, chromiumSandbox:true});
try {
  const page = await browser.newPage({viewport:{width:1000,height:760}, serviceWorkers:'block'});
  await page.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const relative = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
    const type = types[path.extname(relative)];
    if (url.origin !== origin || request.method() !== 'GET' || !type || !/^[a-zA-Z0-9_./-]+$/.test(relative)) {
      blocked.push(url.pathname);
      return route.abort();
    }
    const target = await realpath(path.join(root, relative)).catch(() => null);
    if (!target || !target.startsWith(root + path.sep)) {
      blocked.push(url.pathname);
      return route.abort();
    }
    return route.fulfill({contentType:type, body:await readFile(target), headers:{
      'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    }});
  });
  await page.goto(origin);
  for (const title of ['Review the specification', 'Check the dependency graph', 'Export the validation report']) {
    await page.getByRole('textbox', {name:'Task title'}).fill(title);
    await page.getByRole('button', {name:'Add task'}).click();
  }
  await page.getByRole('checkbox', {name:'Complete Review the specification'}).check();
  assert.match(await page.locator('#task-count').textContent(), /3 of 3/);
  assert.deepEqual(blocked, []);
  await page.screenshot({path:output, fullPage:true, animations:'disabled'});
} finally {
  await browser.close();
}
