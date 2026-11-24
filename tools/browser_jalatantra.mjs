import { spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

const credentials = JSON.parse(await new Promise(resolve => {
  let input = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => input += chunk);
  process.stdin.on('end', () => resolve(input));
}));
const profile = await fs.mkdtemp(path.join(os.tmpdir(), 'jalatantra-edge-'));
const output = path.join(os.tmpdir(), 'jalatantra-browser-results');
await fs.mkdir(output, { recursive: true });
const browser = spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', [
  '--headless=new', '--remote-debugging-port=0', '--no-first-run', '--no-default-browser-check',
  '--no-proxy-server', `--user-data-dir=${profile}`, '--window-size=1440,1000', 'about:blank',
], { stdio: 'ignore' });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const errors = [];
const tests = [];
const pending = new Map();
let websocket;
let sequence = 0;
let createdDeviceId;
let createdDeviceArchived = false;
function send(method, params = {}) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 20000);
    pending.set(id, { resolve, reject, timer });
    websocket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
}
async function capture(name) {
  const screenshot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await fs.writeFile(path.join(output, name + '.png'), Buffer.from(screenshot.data, 'base64'));
  await fs.writeFile(path.join(output, name + '.txt'), await evaluate('document.body.innerText'));
  console.log('Screenshot: ' + path.join(output, name + '.png'));
}
async function wait(expression, label, timeout = 45000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (await evaluate(expression)) return;
    await pause(250);
  }
  await capture('failure');
  throw new Error('Browser timeout: ' + label);
}
async function click(label, root = 'document') {
  await wait(`Array.from(${root}.querySelectorAll('button,a')).some(e => e.textContent.trim() === ${JSON.stringify(label)} && !e.disabled && e.getClientRects().length)`, 'button ' + label, 12000);
  await evaluate(`(() => { const button = Array.from(${root}.querySelectorAll('button,a')).find(e => e.textContent.trim() === ${JSON.stringify(label)} && !e.disabled && e.getClientRects().length); if (!button) throw new Error('Button not found: ' + ${JSON.stringify(label)}); button.click(); })()`);
}
async function input(selector, value) {
  await evaluate(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); e.focus(); e.select(); })()`);
  await send('Input.insertText', { text: value });
}
async function field(label, value) {
  await evaluate(`(() => { const label = Array.from(document.querySelectorAll('#dialog-body label')).find(e => e.textContent === ${JSON.stringify(label)}); if (!label) throw new Error('Field not found'); const e = document.getElementById(label.htmlFor); e.value = ${JSON.stringify(value)}; e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true})); })()`);
}
async function navigate(page, title) {
  await evaluate(`document.querySelector('#main-nav [data-page=${page}]').click()`);
  await wait(`document.querySelector('#page-title').textContent === ${JSON.stringify(title)} && !document.querySelector('#page-content .loading-state') && document.querySelector('#page-content').children.length > 0`, title);
}
async function confirm() {
  await wait('document.querySelector("#confirm-dialog").open', 'confirmation');
  await evaluate('document.querySelector("#confirm-submit").click()');
  await wait('!document.querySelector("#confirm-dialog").open', 'confirmation completed');
}
async function close() {
  await evaluate('document.querySelector("#dialog-close").click()');
}
try {
  let port;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { port = (await fs.readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; break; }
    catch { await pause(100); }
  }
  if (!port) throw new Error('Edge debugging endpoint unavailable');
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  websocket = new WebSocket(pages.find(page => page.type === 'page').webSocketDebuggerUrl);
  await once(websocket, 'open');
  websocket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const entry = pending.get(message.id);
      pending.delete(message.id);
      clearTimeout(entry.timer);
      if (message.error) entry.reject(new Error(JSON.stringify(message.error))); else entry.resolve(message.result);
    }
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
    if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error') {
      const text = message.params.entry.text;
      if (!text.includes('401')) errors.push(text);
    }
    if (message.method === 'Network.responseReceived') {
      const response = message.params.response;
      if (response.status >= 400 && !(response.status === 401 && response.url.endsWith('/api/session'))) errors.push(`${response.status} ${response.url}`);
    }
  });
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable'); await send('Log.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: (credentials.base_url || 'http://127.0.0.1:3080') + '/' });
  await wait('!document.querySelector("#login-screen")?.hidden', 'login form');
  await capture('login-desktop');
  await input('#username', credentials.username); await input('#password', credentials.password);
  await evaluate('document.querySelector("#login-submit").click()');
  await wait('!document.querySelector("#app-shell").hidden && !!document.querySelector("#page-content .card")', 'authenticated overview');
  await capture('overview-desktop');
  if (await evaluate('/kelompok|dosen|kuliah|praktikum|batasan software/i.test(document.body.innerText)')) throw new Error('Non-product wording found');
  await evaluate('document.querySelector("#assistant-toggle").click()');
  await wait('document.querySelector("#dialog-title").textContent === "Tanya asisten" && document.querySelector("#dialog-body").textContent.includes("Prioritaskan insiden") && document.querySelector("#dialog-body").textContent.includes("Buat handover")', 'assistant dialog');
  await close();
  tests.push('login, product wording, overview and assistant dialog');
  await navigate('topology', 'Topologi jaringan');
  await capture('topology-desktop');
  tests.push('inventory topology');
  await navigate('devices', 'Perangkat');
  await capture('devices-desktop');
  const name = 'browser-' + Date.now();
  await click('Tambah perangkat');
  await wait('!!document.querySelector(".device-form")', 'device form');
  await input('input[name=name]', name);
  await input('input[name=address]', '192.0.2.210');
  await evaluate('document.querySelector("input[name=service][value=ssh]").click()');
  await field('Lokasi', 'Verifikasi browser');
  await click('Tambahkan perangkat', 'document.querySelector("#dialog-body")');
  await confirm();
  await wait(`document.querySelector('#dialog-title').textContent === ${JSON.stringify(name)} && !!document.querySelector('#device-checks')`, 'saved device detail');
  createdDeviceId = await evaluate(`fetch('/api/devices?environment=demo', {credentials:'same-origin'}).then(r => r.json()).then(data => data.items.find(item => item.name === ${JSON.stringify(name)}).id)`);
  await click('Periksa layanan', 'document.querySelector("#dialog-body")');
  await confirm();
  await wait('!!document.querySelector("#device-checks .check-run")', 'persisted check');
  await capture('device-detail');
  await fs.writeFile(path.join(output, 'device-detail.html'), await evaluate('document.querySelector("#dialog-body").innerHTML'));
  if (!await evaluate('document.body.innerText.includes("Auto-approve layanan")')) throw new Error('Auto-approve control missing for admin');
  await click('Auto-approve layanan', 'document.querySelector("#dialog-body")').catch(async () => {
    await evaluate('document.querySelector("#dialog-body .auto-approve-toggle").click()');
  });
  await confirm();
  await wait('document.querySelector("#dialog-body .auto-approve-toggle.active") !== null', 'auto-approve enabled');
  await click('Auto-approve layanan', 'document.querySelector("#dialog-body")').catch(async () => {
    await evaluate('document.querySelector("#dialog-body .auto-approve-toggle").click()');
  });
  await confirm();
  await wait('document.querySelector("#dialog-body .auto-approve-toggle.active") === null', 'auto-approve disabled again');
  tests.push('admin auto-approve toggle');
  await click('Edit', 'document.querySelector("#dialog-body")');
  await wait('!!document.querySelector(".device-form")', 'edit form');
  await field('Lokasi', 'Verifikasi browser diperbarui');
  await click('Simpan perubahan', 'document.querySelector("#dialog-body")');
  await confirm();
  await wait('document.querySelector("#dialog-body").textContent.includes("Verifikasi browser diperbarui") && !!document.querySelector("#device-checks")', 'saved device changes');
  await close();
  tests.push('device create, check, edit');
  await navigate('automation', 'Otomasi');
  await wait('document.body.innerText.includes("Diagnosis layanan")', 'diagnose card visible');
  tests.push('diagnose action catalog card');
  await evaluate('document.querySelector("#profile-toggle").click()');
  await wait('!document.querySelector("#profile-menu").hidden', 'profile menu');
  await click('Pengaturan AI');
  await wait('document.querySelector("#dialog-title").textContent === "Pengaturan asisten AI" && !!document.querySelector(".ai-settings-form")', 'ai settings form');
  const aiText = await evaluate('document.querySelector(".ai-settings-form").innerText');
  for (const needle of ['Base URL', 'Kunci API', 'Model ID', 'Uji koneksi', 'Ambil daftar model']) {
    if (!aiText.includes(needle)) throw new Error('Missing AI settings field: ' + needle);
  }
  await capture('ai-settings');
  await fs.writeFile(path.join(output, 'ai-settings.html'), await evaluate('document.querySelector("#dialog-body").innerHTML'));
  await close();
  tests.push('admin AI settings dialog with provider/base URL/key/model fields');
  await click('Rencanakan otomasi');
  await wait('document.querySelector("#dialog-title").textContent === "Rencana otomasi" && document.querySelectorAll("#dialog-body select").length === 3', 'automation form');
  const deviceId = await evaluate(`Array.from(document.querySelector('#dialog-body select').options).find(e => e.textContent.startsWith(${JSON.stringify(name)} + ' ·')).value`);
  await field('Perangkat target', deviceId);
  await field('Aksi', 'ensure_service');
  await field('Layanan target', 'ssh');
  await click('Tinjau & ajukan', 'document.querySelector("#dialog-body")');
  await confirm();
  await wait('document.querySelector("#job-live-status")?.textContent.includes("Menunggu persetujuan")', 'pending approval');
  await capture('automation-approval');
  await click('Tinjau persetujuan', 'document.querySelector("#dialog-body")');
  await wait('!!document.querySelector("#confirm-body input")', 'explicit target confirmation');
  await input('#confirm-body input', 'wrong-name');
  await evaluate('document.querySelector("#confirm-submit").click()');
  await wait('!document.querySelector("#confirm-error").hidden', 'wrong target rejected');
  await input('#confirm-body input', name);
  await confirm();
  await wait('document.querySelector("#job-live-status")?.textContent.includes("Berhasil")', 'verified simulated execution', 150000);
  await capture('automation-result');
  if (!await evaluate('document.querySelector("#job-live-logs").textContent.includes("Ansible tidak dijalankan")')) throw new Error('Simulation execution not identified');
  await close();
  tests.push('plan, reject wrong confirmation, approve, worker execution and logs');
  await navigate('incidents', 'Insiden');
  await click('Buat insiden');
  await wait('document.querySelector("#dialog-body").textContent.includes("Judul insiden")', 'incident form');
  await field('Perangkat', deviceId);
  await field('Judul insiden', 'Verifikasi UI ' + name);
  await field('Detail insiden', 'Pengujian pencatatan dan penyelesaian insiden melalui browser.');
  await click('Tinjau insiden', 'document.querySelector("#dialog-body")');
  await confirm();
  await wait('document.querySelector("#dialog-body").textContent.includes("Mulai penanganan")', 'incident detail');
  await click('Mulai penanganan', 'document.querySelector("#dialog-body")');
  await wait('!!document.querySelector("#confirm-body textarea")', 'acknowledgment note');
  await input('#confirm-body textarea', 'Insiden sedang diperiksa melalui browser.');
  await confirm();
  await wait('document.querySelector("#dialog-body").textContent.includes("Ditangani")', 'incident acknowledged');
  await click('Selesaikan insiden', 'document.querySelector("#dialog-body")');
  await wait('!!document.querySelector("#confirm-body textarea")', 'resolution note');
  await input('#confirm-body textarea', 'Pengujian siklus insiden selesai dan hasil diverifikasi.');
  await confirm();
  await wait('document.querySelector("#dialog-body").textContent.includes("Pengujian siklus insiden selesai")', 'incident resolved');
  await wait('document.querySelector("#dialog-body").textContent.includes("Riwayat penanganan")', 'incident timeline');
  await capture('incident-resolved');
  await close();
  tests.push('incident creation, acknowledgment and resolution');
  await navigate('devices', 'Perangkat');
  await click(name);
  await wait(`!!document.querySelector('[aria-label="Arsipkan ${name}"]')`, 'archive control');
  await evaluate(`document.querySelector('[aria-label="Arsipkan ${name}"]').click()`);
  await confirm();
  await wait('!document.querySelector("#detail-dialog").open', 'device archived');
  createdDeviceArchived = true;
  await navigate('activity', 'Aktivitas');
  await capture('activity-desktop');
  tests.push('device archival and audit trail');
  await evaluate('document.querySelector("#env-real").click()');
  await navigate('overview', 'Ringkasan operasi');
  await wait('document.querySelector("#environment-banner").textContent.includes("Real") || document.querySelector("#environment-banner").textContent.includes("REAL")', 'real environment');
  await capture('real-overview');
  await navigate('devices', 'Perangkat');
  await click('localhost');
  await wait('document.querySelector("#device-checks")?.textContent.includes("SSH")', 'real service checks');
  await capture('real-service-checks');
  await close();
  await evaluate('document.querySelector("#env-demo").click()');
  await navigate('overview', 'Ringkasan operasi');
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await capture('overview-mobile');
  if (await evaluate('document.documentElement.scrollWidth > innerWidth + 1')) throw new Error('Mobile horizontal overflow');
  await evaluate('document.querySelector("#open-sidebar").click()');
  await capture('navigation-mobile');
  await navigate('devices', 'Perangkat');
  await capture('devices-mobile');
  await evaluate('document.querySelector("#profile-toggle").click(); document.querySelector("#logout").click()');
  await confirm();
  await wait('!document.querySelector("#login-screen").hidden', 'logout');
  await capture('login-mobile');
  tests.push('real/demo separation, mobile navigation and logout');
  await fs.writeFile(path.join(output, 'results.json'), JSON.stringify({ tests, errors }, null, 2));
  console.log(JSON.stringify({ tests, errors }));
  if (errors.length) throw new Error('Browser errors recorded');
} finally {
  if (createdDeviceId && !createdDeviceArchived && websocket?.readyState === WebSocket.OPEN) {
    try {
      await evaluate(`(async () => {
        const session = await fetch('/api/session', {credentials:'same-origin'}).then(response => response.json());
        const jobs = await fetch('/api/jobs?environment=demo', {credentials:'same-origin'}).then(response => response.json());
        for (const job of jobs.items.filter(item => String(item.device_id) === String(${JSON.stringify('__DEVICE_ID__')})).filter(item => ['awaiting_approval','queued'].includes(item.status))) {
          await fetch('/api/jobs/' + job.id + '/cancel', {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf_token}, body:'{}'});
        }
        await fetch('/api/devices/' + ${JSON.stringify('__DEVICE_ID__')}, {method:'DELETE', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf_token}, body:'{}'});
      })()`.replaceAll('__DEVICE_ID__', String(createdDeviceId)));
    } catch {}
  }
  if (websocket?.readyState === WebSocket.OPEN) {
    try { await send('Browser.close'); } catch {}
    websocket.close();
  }
  if (browser.exitCode === null) await Promise.race([once(browser, 'exit'), pause(5000)]);
  await fs.rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 400 });
}
