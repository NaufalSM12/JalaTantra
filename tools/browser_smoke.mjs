import { spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

const credentials = JSON.parse(await new Promise((resolve) => {
  let input = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => input += chunk);
  process.stdin.on('end', () => resolve(input));
}));
const profile = await fs.mkdtemp(path.join(os.tmpdir(), 'k8-edge-test-'));
const output = path.join(os.tmpdir(), 'k8-browser-results');
await fs.mkdir(output, { recursive: true });
const browser = spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', [
  '--headless=new', '--remote-debugging-port=0', '--no-first-run', '--no-default-browser-check',
  `--user-data-dir=${profile}`, '--window-size=1440,1000', 'about:blank',
], { stdio: 'ignore' });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let websocket;
const pending = new Map();
const errors = [];
let sequence = 0;
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
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text + ': ' + result.exceptionDetails.exception?.description);
  return result.result.value;
}
async function waitFor(expression, label, timeout = 45000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (await evaluate(expression)) return;
    await pause(300);
  }
  await capture('failure');
  console.log(await evaluate('Array.from(document.querySelectorAll("[role=combobox],[role=option]")).map(e=>({tag:e.tagName,role:e.getAttribute("role"),value:e.value,text:e.textContent})).slice(0,12)'));
  throw new Error(`Browser timeout: ${label}`);
}
async function capture(name) {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await fs.writeFile(path.join(output, `${name}.png`), Buffer.from(png.data, 'base64'));
  const text = await evaluate('document.body.innerText');
  await fs.writeFile(path.join(output, `${name}.txt`), text);
  console.log(`Screenshot: ${path.join(output, `${name}.png`)}`);
  return text;
}
async function open(url) {
  await send('Page.navigate', { url });
  await waitFor('document.readyState === "complete"', 'page ready');
}
try {
  let port;
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      port = (await fs.readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0];
      break;
    } catch { await pause(100); }
  }
  if (!port) throw new Error('Edge debugging endpoint unavailable');
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page = pages.find(item => item.type === 'page');
  websocket = new WebSocket(page.webSocketDebuggerUrl);
  await once(websocket, 'open');
  websocket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const request = pending.get(message.id);
      pending.delete(message.id);
      clearTimeout(request.timer);
      if (message.error) request.reject(new Error(JSON.stringify(message.error)));
      else request.resolve(message.result);
    }
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    if (message.method === 'Network.responseReceived' && message.params.response.status >= 400) {
      errors.push(`${message.params.response.status} ${message.params.response.url}`);
    }
  });
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Network.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await open('http://127.0.0.1:3000/login');
  await waitFor('!!document.querySelector("input[name=user]")', 'login form');
  await evaluate('document.querySelector("input[name=user]").focus()');
  await send('Input.insertText', { text: credentials.username });
  await evaluate('document.querySelector("input[name=password]").focus()');
  await send('Input.insertText', { text: credentials.password });
  await evaluate('document.querySelector("button[type=submit]").click()');
  await waitFor('document.body.innerText.includes("Total node") && !location.pathname.includes("login")', 'demo home');
  await waitFor('document.body.innerText.includes("CPU / tren per perangkat") && document.querySelectorAll("canvas").length > 0', 'rendered demo charts');
  await pause(2000);
  const initial = await capture('demo-desktop');
  if (!initial.includes('SIMULASI')) throw new Error('Simulation warning absent');
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 1250, y: 700, deltaY: 780, deltaX: 0 });
  await pause(1800);
  await capture('demo-inventory');
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 1250, y: 700, deltaY: 720, deltaX: 0 });
  await pause(1800);
  await capture('demo-database');
  await evaluate('Array.from(document.querySelectorAll("a")).find(a=>a.textContent.trim()==="Operasional").click()');
  await waitFor('document.body.innerText.includes("Node UP") && document.title.includes("REAL")', 'real navigation');
  await pause(1800);
  await capture('real-desktop');
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 1250, y: 700, deltaY: 1470, deltaX: 0 });
  await pause(1800);
  await capture('real-database');
  await open('http://127.0.0.1:3000/d/kelompok8-demo?var-device=app01');
  await waitFor('!!document.querySelector("[role=combobox]")', 'device dropdown');
  await evaluate('document.querySelector("[role=combobox]").focus()');
  await send('Input.insertText', { text: 'db01' });
  await waitFor('Array.from(document.querySelectorAll("[role=option]")).some(e=>e.textContent.includes("db01"))', 'filtered dropdown option');
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: 1100, y: 190, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: 1100, y: 190, button: 'left', clickCount: 1 });
  await waitFor('location.search.includes("db01")', 'device selection via dropdown');
  await pause(1800);
  await capture('demo-dropdown');
  await open('http://127.0.0.1:3000/d/kelompok8-demo?var-device=lab-offline01&from=now-15m&to=now');
  await waitFor('document.body.innerText.includes("Total node")', 'offline selection');
  await pause(1800);
  const offline = await capture('demo-offline');
  if (!offline.includes('lab-offline01') || !offline.includes('Tidak ada data')) throw new Error('Offline selection not rendered correctly');
  await open('http://127.0.0.1:3000/d/kelompok8-demo?var-device=nonexistent-device&from=now-15m&to=now');
  await waitFor('document.body.innerText.includes("Total node")', 'empty selection');
  await pause(1800);
  const empty = await capture('demo-empty');
  if (!empty.includes('Tidak ada data')) throw new Error('Empty selection has no explicit unknown state');
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await open('http://127.0.0.1:3000/d/kelompok8-demo?from=now-15m&to=now');
  await waitFor('document.body.innerText.includes("Total node")', 'mobile dashboard');
  await pause(1800);
  await capture('demo-mobile');
  await fs.writeFile(path.join(output, 'browser-errors.json'), JSON.stringify(errors, null, 2));
  console.log(JSON.stringify({ tests: ['login', 'home', 'demo charts', 'real navigation', 'offline filter', 'empty filter', 'mobile layout'], errors }));
  if (errors.length) throw new Error('Browser reported errors; inspect browser-errors.json');
} finally {
  if (websocket?.readyState === WebSocket.OPEN) {
    try { await send('Browser.close'); } catch {}
    websocket.close();
  }
  if (browser.exitCode === null) await Promise.race([once(browser, 'exit'), pause(5000)]);
  try { await fs.rm(profile, { recursive: true, force: true }); } catch {}
}
