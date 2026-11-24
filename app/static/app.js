'use strict';

(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const paths = {
    overview: ['M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z'],
    server: ['M4 3h16v7H4zM4 14h16v7H4zM7 6.5h.01M7 17.5h.01M15 6.5h2M15 17.5h2'],
    topology: ['M9 3h6v6H9zM2 16h6v6H2zM16 16h6v6h-6zM12 9v4M5 16v-3h14v3'],
    incident: ['M12 3 2 21h20L12 3ZM12 9v5M12 17h.01'],
    automation: ['m13 2-9 12h7l-1 8 10-12h-7l1-8Z'],
    activity: ['M3 12h4l3-8 4 16 3-8h4'],
    shield: ['M12 3 3 6v6c0 5 9 9 9 9s9-4 9-9V6l-9-3ZM8 12l3 3 5-6'],
    menu: ['M4 6h16M4 12h16M4 18h16'],
    close: ['m6 6 12 12M6 18 18 6'],
    chevron: ['m7 10 5 5 5-5'],
    arrow: ['M4 12h16m-6-6 6 6-6 6'],
    refresh: ['M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 13 3M18 18A8 8 0 0 1 5 15'],
    plus: ['M12 5v14M5 12h14'],
    search: ['M20 20l-5-5', 'M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z'],
    check: ['m5 12 4 4L19 6'],
    clock: ['M12 8v5l3 2', 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z'],
    key: ['m14 10-9 9H2v-3l9-9', 'M22 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z'],
    logout: ['M9 4H3v16h6M9 12h12m-5-5 5 5-5 5'],
    edit: ['m14 5 5 5M3 21l5-1L21 7l-5-5L3 15v6Z'],
    trash: ['M3 6h18M8 6V3h8v3M5 6l1 15h12l1-15M10 10v7M14 10v7'],
    cpu: ['M6 6h12v12H6zM9 9h6v6H9zM9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4'],
    network: ['M12 3v18M5 7l7-4 7 4M5 17l7 4 7-4M3 12h18'],
    info: ['M12 11v6M12 7h.01', 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z'],
    pin: ['M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z', 'M14 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z'],
    terminal: ['m5 7 5 5-5 5M13 17h6'],
    stethoscope: ['M4 4v6a6 6 0 0 0 12 0V4', 'M10 16v1a4 4 0 0 0 8 0v-2', 'M18 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z'],
    bolt: ['M13 3 4 14h6l-1 7 9-11h-6l1-7Z'],
    filter: ['M3 5h18l-7 8v6l-4 2v-8L3 5Z'],
    book: ['M4 3h16v18H4zM8 7h8M8 11h8M8 15h5'],
    storage: ['M3 5h18v14H3zM7 15h.01M11 15h.01M3 11h18'],
    router: ['M3 14h18v7H3zM7 14V8M17 14V8M5 5a10 10 0 0 1 14 0M8 8a6 6 0 0 1 8 0M7 18h.01M11 18h.01'],
    switch: ['M2 7h20v11H2zM6 11v3M10 11v3M14 11v3M18 11v3'],
    pause: ['M8 5v14M16 5v14']
  };
  const labels = {
    up: 'Sehat', down: 'Gangguan', warning: 'Perhatian', unknown: 'Belum diperiksa',
    open: 'Terbuka', acknowledged: 'Ditangani', resolved: 'Selesai',
    info: 'Informasi', critical: 'Kritis', awaiting_approval: 'Menunggu persetujuan',
    queued: 'Antrean', running: 'Berjalan', succeeded: 'Berhasil', failed: 'Gagal', cancelled: 'Dibatalkan',
    admin: 'Administrator', operator: 'Operator', viewer: 'Viewer',
    audit: 'Audit layanan', collect_evidence: 'Kumpulkan bukti sistem', diagnose: 'Diagnosis layanan', ensure_service: 'Pastikan layanan aktif', restart_service: 'Restart layanan', reload_service: 'Muat ulang layanan',
    check: 'Pemeriksaan layanan', server: 'Server', router: 'Router', switch: 'Switch', storage: 'Storage'
  };
  const pageMeta = {
    overview: ['PUSAT KENDALI', 'Ringkasan operasi', 'Satu pandangan untuk kesehatan dan aktivitas infrastruktur Anda.'],
    devices: ['INVENTARIS', 'Perangkat', 'Kenali aset Anda. Periksa layanan dan kelola koneksi.'],
    topology: ['PETA INFRASTRUKTUR', 'Topologi jaringan', 'Hubungan antarperangkat berdasarkan koneksi dalam inventaris.'],
    incidents: ['RESPONS OPERASIONAL', 'Insiden', 'Prioritaskan gangguan, koordinasikan penanganan, catat penyelesaiannya.'],
    automation: ['CONTROLLED AUTOMATION', 'Otomasi', 'Rencana yang jelas. Persetujuan eksplisit. Eksekusi yang tercatat.'],    activity: ['JEJAK OPERASI', 'Aktivitas', 'Riwayat tindakan dan perubahan dalam satu alur yang dapat ditelusuri.']
  };
  const terminal = new Set(['succeeded', 'failed', 'cancelled']);
  const preference = (key, fallback) => { try { return localStorage.getItem(`jalatantra.${key}`) || fallback; } catch { return fallback; } };
  const savePreference = (key, value) => { try { localStorage.setItem(`jalatantra.${key}`, value); } catch { /* Storage is optional. */ } };
  const savedPage = preference('page', 'overview');
  const state = {
    environment: preference('environment', 'demo') === 'real' ? 'real' : 'demo',
    page: pageMeta[location.hash.slice(1)] ? location.hash.slice(1) : (pageMeta[savedPage] ? savedPage : 'overview'),
    user: null, csrf: null, catalog: null, data: {}, loading: false, request: 0, sessionVersion: 0,
    filters: { search: '', deviceStatus: '', kind: '', incidentStatus: '', severity: '', jobStatus: '', activitySearch: '' },
    topologySelected: null, showRoutes: true, modal: null, modalVersion: 0, detailTimer: null,
    watchedJobs: new Map(), lastUpdated: null
  };

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => {
      if (value === null || value === undefined || value === false) return;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
      else if (key === 'checked' || key === 'disabled' || key === 'hidden' || key === 'selected') node[key] = Boolean(value);
      else node.setAttribute(key, value === true ? '' : String(value));
    });
    children.flat(Infinity).forEach(child => { if (child !== null && child !== undefined && child !== false) node.append(child instanceof Node ? child : document.createTextNode(String(child))); });
    return node;
  }
  function svg(tag, attrs = {}, ...children) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
    children.flat().forEach(child => node.append(child instanceof Node ? child : document.createTextNode(String(child))));
    return node;
  }
  function icon(name, className = '') {
    return svg('svg', { viewBox: '0 0 24 24', class: `icon ${className}`, fill: 'none', stroke: 'currentColor', 'stroke-width': '1.65', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' }, (paths[name] || paths.server).map(d => svg('path', { d })));
  }
  function button(text, name, callback, variant = 'secondary', attrs = {}) {
    return el('button', { type: 'button', class: `btn ${variant}`, onclick: callback, ...attrs }, name ? icon(name) : null, text);
  }
  const text = (selector, value) => { $(selector).textContent = value; };
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const number = value => finite(value) ? new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 }).format(value) : '—';
  const percent = value => finite(value) ? `${number(value)}%` : '—';
  const date = (value, full = false) => {
    if (!value || Number.isNaN(new Date(value).getTime())) return 'Belum tersedia';
    return new Intl.DateTimeFormat('id-ID', { day: '2-digit', month: 'short', ...(full ? { year: 'numeric' } : {}), hour: '2-digit', minute: '2-digit' }).format(new Date(value));
  };
  function age(value) {
    if (!value || Number.isNaN(new Date(value).getTime())) return 'Belum diperiksa';
    const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000));
    if (minutes < 1) return 'Baru saja';
    if (minutes < 60) return `${minutes} menit lalu`;
    if (minutes < 1440) return `${Math.floor(minutes / 60)} jam lalu`;
    return `${Math.floor(minutes / 1440)} hari lalu`;
  }
  function traffic(value) {
    if (!finite(value)) return '—';
    if (Math.abs(value) >= 1e9) return `${number(value / 1e9)} GB/s`;
    if (Math.abs(value) >= 1e6) return `${number(value / 1e6)} MB/s`;
    if (Math.abs(value) >= 1e3) return `${number(value / 1e3)} kB/s`;
    return `${number(value)} B/s`;
  }
  function badge(status, custom) { return el('span', { class: `badge status-${Object.hasOwn(labels, status) ? status : 'unknown'}` }, el('span', { class: 'status-dot' }), custom || labels[status] || status || 'Tidak diketahui'); }
  function scopeBadge(environment = state.environment) { return el('span', { class: `scope-badge ${environment === 'real' ? 'real' : 'demo'}` }, environment === 'real' ? 'REAL · AKTUAL' : 'DEMO · SINTETIS'); }
  const canWrite = () => state.user && ['admin', 'operator'].includes(state.user.role);
  const canApprove = () => state.user?.role === 'admin';
  const items = data => Array.isArray(data?.items) ? data.items : [];
  const query = values => new URLSearchParams(Object.entries(values).filter(([, value]) => value !== '' && value !== null && value !== undefined)).toString();
  const apiId = value => encodeURIComponent(value);
  const serviceLabel = key => state.catalog?.services?.find(service => service.id === key)?.label || key;
  const actionLabel = key => state.catalog?.actions?.find(action => action.id === key)?.label || labels[key] || key;

  class ApiError extends Error { constructor(message, status) { super(message); this.status = status; } }
  async function api(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    const version = state.sessionVersion;
    try {
      const headers = { Accept: 'application/json' };
      if (options.method && options.method !== 'GET') {
        headers['Content-Type'] = 'application/json';
        if (path !== '/api/login') headers['X-CSRF-Token'] = state.csrf || '';
      }
      const response = await fetch(path, { method: options.method || 'GET', credentials: 'same-origin', cache: 'no-store', headers, signal: controller.signal, ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}) });
      const raw = await response.text();
      let data;
      try { data = raw ? JSON.parse(raw) : {}; } catch { throw new ApiError('Respons layanan tidak dapat dibaca. Coba lagi.', response.status); }
      if (!response.ok) {
        const messages = { 401: 'Sesi berakhir. Silakan masuk kembali.', 403: 'Akses ditolak. Periksa peran akun dan izin tindakan.', 409: 'Data berubah atau tindakan tidak lagi tersedia. Muat ulang sebelum mencoba lagi.', 422: 'Data belum valid. Periksa isian dan cakupan perangkat.' };
        if (response.status === 401 && path !== '/api/login' && version === state.sessionVersion) showLogin();
        const prefix = messages[response.status] || 'Permintaan tidak berhasil.';
        throw new ApiError(data.error ? `${prefix} ${data.error}` : prefix, response.status);
      }
      if (version !== state.sessionVersion) throw new ApiError('Sesi telah berubah. Silakan coba kembali.', 401);
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new ApiError('Waktu tunggu habis. Periksa koneksi lalu coba lagi.', 0);
      if (error instanceof ApiError) throw error;
      throw new ApiError('Tidak dapat terhubung ke layanan. Data tidak diganti dengan data sintetis.', 0);
    } finally { clearTimeout(timeout); }
  }
  function toast(message, tone = 'success') {
    const node = el('div', { class: `toast ${tone}` }, icon(tone === 'success' ? 'check' : 'info'), el('span', {}, message));
    node.append(button('', 'close', () => node.remove(), 'ghost', { 'aria-label': 'Tutup notifikasi' }));
    $('#toasts').append(node);
    while ($('#toasts').children.length > 4) $('#toasts').firstElementChild.remove();
    setTimeout(() => node.remove(), tone === 'error' ? 14000 : 8000);
  }
  function errorBox(error) { return el('div', { class: 'inline-error', role: 'alert' }, icon('incident'), error.message || String(error)); }
  function empty(title, description, action) { return el('div', { class: 'empty-state' }, el('span', { class: 'empty-icon' }, icon('network')), el('h3', {}, title), el('p', {}, description), action || null); }
  function panel(title, subtitle, content, action, className = '') {
    return el('section', { class: `card ${className}` }, el('div', { class: 'card-heading' }, el('div', {}, el('h2', {}, title), subtitle ? el('p', {}, subtitle) : null), action || null), content);
  }
  function loading() { return el('div', { class: 'loading-state', role: 'status' }, el('span', { class: 'spinner' }), 'Memuat data operasi…'); }
  function field(labelText, control, hint, className = '') {
    const id = control.id || `field-${++field.counter}`;
    control.id = id;
    const node = el('div', { class: `form-field ${className}` }, el('label', { for: id }, labelText), control);
    if (hint) { const helper = el('small', { id: `${id}-hint`, class: 'field-hint' }, hint); control.setAttribute('aria-describedby', helper.id); node.append(helper); }
    return node;
  }
  field.counter = 0;
  function selectControl(values, value, attrs = {}) {
    const node = el('select', attrs, values.map(([key, label]) => el('option', { value: key }, label)));
    node.value = value ?? '';
    return node;
  }
  function showLogin() {
    state.sessionVersion++;
    state.request++;
    state.user = null;
    state.csrf = null;
    state.catalog = null;
    state.data = {};
    state.watchedJobs.forEach(timer => clearTimeout(timer));
    state.watchedJobs.clear();
    closeModal();
    if ($('#confirm-dialog').open) $('#confirm-dialog').close();
    closeSidebar();
    $('#app-shell').hidden = true;
    $('#boot-screen').hidden = true;
    $('#login-screen').hidden = false;
    $('#password').value = '';
    $('#profile-menu').hidden = true;
    $('#username').focus();
  }
  async function startSession(session) {
    if (!session.user || !session.csrf_token) throw new ApiError('Sesi tidak lengkap. Silakan masuk kembali.', 401);
    state.user = session.user;
    state.csrf = session.csrf_token;
    $('#login-screen').hidden = true;
    $('#boot-screen').hidden = true;
    $('#app-shell').hidden = false;
    $('#password').value = '';
    text('#profile-name', state.user.username);
    text('#profile-role', labels[state.user.role] || state.user.role);
    text('#profile-avatar', state.user.username.slice(0, 2).toUpperCase());
    text('#profile-summary', `Masuk sebagai ${state.user.username}`);
    $('#ai-settings').hidden = !canApprove();
    $('#assistant-toggle').hidden = !canWrite();
    try { state.catalog = await api('/api/catalog'); } catch (error) { if (state.user) toast(error.message, 'error'); }
    if (state.user) navigate(state.page, false);
  }
  function navigate(page, focus = true) {
    if (!state.user || !pageMeta[page]) return;
    state.page = page;
    state.data = {};
    state.topologySelected = null;
    state.request++;
    savePreference('page', page);
    if (location.hash !== `#${page}`) history.replaceState(null, '', `#${page}`);
    closeSidebar();
    closeModal();
    $$('#main-nav a').forEach(link => { link.classList.toggle('active', link.dataset.page === page); if (link.dataset.page === page) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current'); });
    const [eyebrow, title, description] = pageMeta[page];
    text('#page-eyebrow', eyebrow); text('#page-title', title); text('#page-description', description);
    text('#breadcrumb-page', $('#main-nav .active').textContent.trim());
    document.title = `${title} · JalaTantra`;
    updateEnvironment();
    renderActions();
    renderToolbar();
    $('#page-content').replaceChildren(loading());
    $('#page-error').hidden = true;
    if (focus) $('#main-content').focus({ preventScroll: true });
    loadPage();
  }
  function updateEnvironment() {
    $$('[data-env]').forEach(node => node.setAttribute('aria-pressed', String(node.dataset.env === state.environment)));
    $('#environment-banner').classList.toggle('is-real', state.environment === 'real');
    $('#environment-banner').replaceChildren(scopeBadge(), el('span', {}, state.environment === 'demo' ? 'Lingkungan simulasi · Data dan hasil pemeriksaan bersifat sintetis.' : 'Lingkungan aktual · Pemeriksaan dan otomasi dapat mengakses layanan nyata.'), el('span', { class: 'environment-right' }, icon('shield'), 'Perubahan tercatat'));
  }
  function renderActions() {
    const actions = [button('Segarkan', 'refresh', () => loadPage(), 'secondary', { id: 'refresh-button' })];
    if (canWrite()) {
      if (state.page === 'devices') actions.push(button('Tambah perangkat', 'plus', () => editDevice(), 'primary'));
      if (state.page === 'incidents') actions.push(button('Buat insiden', 'plus', () => createIncident(), 'primary'));
      if (state.page === 'automation') actions.push(button('Rencanakan otomasi', 'plus', () => planAutomation(), 'primary'));
    }
    $('#page-actions').replaceChildren(...actions);
  }
  function renderToolbar() {
    const bar = $('#page-toolbar');
    bar.replaceChildren();
    const filter = (key, options, label) => selectControl(options, state.filters[key], { 'aria-label': label, onchange: event => { state.filters[key] = event.target.value; if (key === 'incidentStatus') loadPage(); else renderPage(); } });
    if (state.page === 'devices') {
      let timer;
      const search = el('input', { type: 'search', placeholder: 'Cari nama atau alamat perangkat…', 'aria-label': 'Cari perangkat', value: state.filters.search, oninput: event => { state.filters.search = event.target.value; clearTimeout(timer); timer = setTimeout(() => { if (state.page === 'devices') loadPage(); }, 320); } });
      bar.append(el('div', { class: 'filter-bar' }, el('div', { class: 'search-field' }, icon('search'), search), filter('deviceStatus', [['', 'Semua status'], ...['up', 'warning', 'down', 'unknown'].map(key => [key, labels[key]])], 'Filter status perangkat'), filter('kind', [['', 'Semua jenis'], ...['server', 'router', 'switch', 'storage'].map(key => [key, labels[key]])], 'Filter jenis perangkat'), el('span', { class: 'filter-count', id: 'filter-count' })));
    } else if (state.page === 'incidents') {
      bar.append(el('div', { class: 'filter-bar' }, el('div', { class: 'filter-label' }, icon('filter'), 'Filter insiden'), filter('incidentStatus', [['', 'Semua status'], ...['open', 'acknowledged', 'resolved'].map(key => [key, labels[key]])], 'Filter status insiden'), filter('severity', [['', 'Semua prioritas'], ...['critical', 'warning', 'info'].map(key => [key, labels[key]])], 'Filter prioritas'), el('span', { class: 'filter-count', id: 'filter-count' })));
    } else if (state.page === 'automation') {
      bar.append(el('div', { class: 'filter-bar' }, el('div', { class: 'filter-label' }, icon('filter'), 'Riwayat eksekusi'), filter('jobStatus', [['', 'Semua status'], ...['awaiting_approval', 'queued', 'running', 'succeeded', 'failed', 'cancelled'].map(key => [key, labels[key]])], 'Filter status otomasi'), el('span', { class: 'filter-count', id: 'filter-count' })));
    } else if (state.page === 'activity') {
      bar.append(el('div', { class: 'filter-bar' }, el('div', { class: 'search-field' }, icon('search'), el('input', { type: 'search', placeholder: 'Cari aktor, tindakan, atau detail…', 'aria-label': 'Cari aktivitas', value: state.filters.activitySearch, oninput: event => { state.filters.activitySearch = event.target.value; renderPage(); } })), el('span', { class: 'filter-count', id: 'filter-count' })));
    }
  }
  async function loadPage(automatic = false) {
    if (!state.user || (automatic && (document.hidden || state.loading))) return;
    const request = ++state.request;
    const page = state.page;
    const environment = state.environment;
    state.loading = true;
    const refresh = $('#refresh-button');
    if (refresh) { refresh.disabled = true; refresh.classList.add('refreshing'); }
    text('#refresh-status', automatic ? 'Memperbarui data…' : 'Mengambil data…');
    try {
      const q = query({ environment });
      let data;
      if (page === 'overview') {
        const [overview, metrics] = await Promise.all([api(`/api/overview?${q}`), api(`/api/metrics?${q}`).catch(error => ({ available: false, error: error.message, source: environment }))]);
        data = { overview, metrics };
      } else if (page === 'devices' || page === 'topology') {
        data = { devices: items(await api(`/api/devices?${query({ environment, search: page === 'devices' ? state.filters.search : '' })}`)) };
      } else if (page === 'incidents') {
        data = { incidents: items(await api(`/api/incidents?${query({ environment, status: state.filters.incidentStatus })}`)) };
      } else if (page === 'automation') {
        data = { jobs: items(await api(`/api/jobs?${q}`)) };
        if (!state.catalog) state.catalog = await api('/api/catalog');
      } else { data = { activity: items(await api(`/api/audit?${q}`)) }; }
      if (request !== state.request || !state.user) return;
      state.data = data;
      state.lastUpdated = new Date();
      $('#page-error').hidden = true;
      renderPage();
      text('#refresh-status', `Diperbarui ${new Intl.DateTimeFormat('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(state.lastUpdated)} · refresh 12 dtk`);
    } catch (error) {
      if (request !== state.request || !state.user) return;
      $('#page-error').hidden = false;
      $('#page-error').replaceChildren(icon('incident'), el('div', {}, el('strong', {}, 'Data belum dapat diperbarui'), el('p', {}, error.message)), button('Coba lagi', 'refresh', () => loadPage()));
      if (!Object.keys(state.data).length) $('#page-content').replaceChildren(empty('Koneksi data belum tersedia', 'Tidak ada data pengganti. Hubungkan kembali untuk melihat kondisi lingkungan ini.'));
      text('#refresh-status', state.lastUpdated ? `Data terakhir ${date(state.lastUpdated)} · koneksi terputus` : 'Belum tersinkronisasi');
    } finally {
      if (request === state.request) { state.loading = false; if (refresh) { refresh.disabled = false; refresh.classList.remove('refreshing'); } }
    }
  }
  function renderPage() {
    const content = $('#page-content');
    const active = document.activeElement;
    const focusKey = content.contains(active) ? active.dataset.focusKey : null;
    if (state.page === 'overview' && state.data.overview) content.replaceChildren(renderOverview());
    else if (state.page === 'devices' && state.data.devices) content.replaceChildren(renderDevices());
    else if (state.page === 'topology' && state.data.devices) content.replaceChildren(renderTopology());
    else if (state.page === 'incidents' && state.data.incidents) content.replaceChildren(renderIncidents());
    else if (state.page === 'automation' && state.data.jobs) content.replaceChildren(renderAutomation());
    else if (state.page === 'activity' && state.data.activity) content.replaceChildren(renderActivity());
    if (focusKey) $$('[data-focus-key]', content).find(node => node.dataset.focusKey === focusKey)?.focus({ preventScroll: true });
  }
  function statCard(label, value, detail, iconName, tone = 'teal') {
    return el('div', { class: 'stat-card' }, el('div', { class: 'stat-top' }, el('span', {}, label), el('span', { class: `stat-icon ${tone}` }, icon(iconName))), el('div', { class: 'stat-value' }, number(value)), el('div', { class: 'stat-detail' }, detail));
  }
  function renderOverview() {
    const { overview: data, metrics } = state.data;
    const count = data.counts || {};
    const root = el('div', { class: 'page-stack' });
    const attention = (count.down || 0) + (count.warning || 0);
    root.append(el('section', { class: 'overview-hero' }, el('div', {}, el('div', { class: 'hero-date' }, icon('clock'), new Intl.DateTimeFormat('id-ID', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date())), el('h2', {}, 'Setiap koneksi, dalam kendali.'), el('p', {}, attention ? `${number(attention)} perangkat memerlukan perhatian. Tinjau kondisi layanan sebelum mengambil tindakan.` : count.devices ? 'Pantau kesehatan layanan dan tindak lanjuti perubahan dari satu tempat.' : 'Mulai dengan menambahkan perangkat untuk membangun visibilitas infrastruktur.')), el('div', { class: 'hero-state' }, el('span', { class: `hero-state-icon ${attention ? 'attention' : ''}` }, icon(attention ? 'incident' : 'shield')), el('div', {}, el('strong', {}, attention ? 'Perlu perhatian' : count.devices ? 'Operasi terpantau' : 'Siap untuk terhubung'), el('small', {}, state.environment === 'real' ? 'Lingkungan aktual' : 'Simulasi terisolasi')))));
    if (!data.worker?.healthy) root.append(el('div', { class: 'page-error' }, icon('incident'), el('div', {}, el('strong', {}, 'Worker otomasi belum memberi heartbeat'), el('p', {}, data.worker?.heartbeat_at ? `Terakhir terlihat ${age(data.worker.heartbeat_at)}. Pemeriksaan dan antrean mungkin tertunda; periksa layanan jalatantra-worker.` : 'Belum ada heartbeat worker. Pemeriksaan dan antrean mungkin belum berjalan.'))));
    root.append(el('div', { class: 'stats-grid' }, statCard('Total perangkat', count.devices, `${number(count.unknown)} belum diperiksa`, 'server'), statCard('Perangkat sehat', count.up, `${number(count.warning)} perhatian · ${number(count.down)} gangguan`, 'activity'), statCard('Insiden aktif', count.open_incidents, 'Terbuka & sedang ditangani', 'incident', 'amber'), statCard('Pekerjaan tertunda', count.pending_jobs, 'Persetujuan & antrean eksekusi', 'automation', 'blue')));
    const summary = metrics?.summary || {};
    const chart1 = panel('Utilisasi sumber daya', 'CPU & memori · riwayat pemantauan', el('div', {}, el('div', { class: 'chart-summary' }, metricReadout('CPU', summary.cpu, 'teal'), metricReadout('Memori', summary.memory, 'blue')), lineChart(metrics, [{ key: 'cpu', label: 'CPU', color: '#119d89' }, { key: 'memory', label: 'Memori', color: '#6988cb' }], 'percent')), el('span', { class: 'chart-source' }, metrics?.source === 'demo' ? 'SINTETIS' : 'PROMETHEUS'));
    const chart2 = panel('Lalu lintas jaringan', 'Throughput · byte per detik', el('div', {}, el('div', { class: 'chart-summary' }, metricReadout('RX · masuk', summary.rx, 'teal', true), metricReadout('TX · keluar', summary.tx, 'blue', true)), lineChart(metrics, [{ key: 'rx', label: 'RX', color: '#119d89' }, { key: 'tx', label: 'TX', color: '#6988cb' }], 'traffic')), el('span', { class: 'chart-source' }, metrics?.updated_at ? age(metrics.updated_at) : 'MENUNGGU DATA'));
    root.append(el('div', { class: 'charts-grid' }, chart1, chart2));
    root.append(el('div', { class: 'overview-middle' }, panel('Kesehatan perangkat', 'Berdasarkan pemeriksaan terakhir', healthDonut(count)), panel('Perangkat terpantau', 'Snapshot inventaris', deviceTable((data.devices || []).slice(0, 5), true), button('Lihat semua', 'arrow', () => navigate('devices'), 'text'))));
    root.append(el('div', { class: 'overview-bottom' }, panel('Insiden terbaru', 'Prioritas yang belum terselesaikan', incidentList(data.incidents || [], true), button('Semua insiden', 'arrow', () => navigate('incidents'), 'text')), panel('Langkah berikutnya', 'Tindakan terarah untuk operasi Anda', el('div', { class: 'next-actions' }, nextAction('server', 'Tinjau inventaris', 'Periksa perangkat dan layanan yang dipantau.', () => navigate('devices')), nextAction('automation', 'Kelola antrean otomasi', `${number(count.pending_jobs)} pekerjaan menunggu tindak lanjut.`, () => navigate('automation')), nextAction('book', 'Telusuri aktivitas', 'Lihat jejak perubahan dan pelaku tindakan.', () => navigate('activity'))))));
    root.append(el('div', { class: 'overview-bottom' }, panel('Eksekusi terakhir', 'Status yang dilaporkan oleh worker', compactJobs(data.jobs || [])), panel('Aktivitas terkini', 'Jejak tindakan terakhir', activityList((data.activity || []).slice(0, 5), true))));
    text('#nav-incident-count', number(count.open_incidents));
    $('#nav-incident-count').hidden = !count.open_incidents;
    return root;
  }
  function metricReadout(label, value, color, network = false) { return el('div', { class: 'metric-readout' }, el('span', {}, el('i', { class: `legend-dot ${color}` }), label), el('strong', {}, network ? traffic(value) : percent(value))); }
  function nextAction(name, title, description, callback) { return el('button', { type: 'button', class: 'next-action', onclick: callback }, el('span', { class: 'action-icon' }, icon(name)), el('span', {}, el('strong', {}, title), el('small', {}, description)), icon('arrow')); }
  function lineChart(metrics, series, type) {
    if (!metrics?.available) return el('div', { class: 'chart-empty' }, icon('activity'), el('strong', {}, 'Metrik belum tersedia'), el('span', {}, metrics?.error || 'Menunggu sampel pemantauan dari lingkungan ini.'));
    const history = (metrics.history || []).filter(point => !Number.isNaN(new Date(point.time).getTime())).slice(-60).sort((a, b) => new Date(a.time) - new Date(b.time));
    const values = history.flatMap(point => series.map(item => point[item.key])).filter(finite);
    if (!history.length || !values.length) return el('div', { class: 'chart-empty' }, icon('activity'), el('strong', {}, 'Belum ada sampel historis'), el('span', {}, 'Sampel yang tidak tersedia tetap ditampilkan sebagai celah.'));
    const width = 620, height = 210, left = 62, right = 18, top = 15, bottom = 34;
    const max = type === 'percent' ? Math.max(100, ...values) : Math.max(1, ...values) * 1.15;
    const minTime = new Date(history[0].time).getTime(), maxTime = new Date(history[history.length - 1].time).getTime();
    const x = point => left + (maxTime === minTime ? 0.5 : (new Date(point.time).getTime() - minTime) / (maxTime - minTime)) * (width - left - right);
    const y = value => top + (1 - Math.max(0, value) / max) * (height - top - bottom);
    const format = type === 'percent' ? percent : traffic;
    const chart = svg('svg', { viewBox: `0 0 ${width} ${height}`, class: 'line-chart', role: 'group', 'aria-label': `${series.map(item => item.label).join(' dan ')}. ${type === 'percent' ? 'Satuan persen.' : 'Satuan byte per detik.'} Celah berarti sampel tidak tersedia.` });
    chart.append(svg('title', {}, 'Riwayat metrik dari API pemantauan'));
    for (let i = 0; i <= 4; i++) {
      const value = max * i / 4;
      chart.append(svg('line', { x1: left, x2: width - right, y1: y(value), y2: y(value), class: 'chart-grid-line' }), svg('text', { x: left - 10, y: y(value) + 4, 'text-anchor': 'end', class: 'chart-axis' }, format(value)));
    }
    [...new Set([0, Math.floor((history.length - 1) / 3), Math.floor(2 * (history.length - 1) / 3), history.length - 1])].forEach(index => chart.append(svg('text', { x: x(history[index]), y: height - 8, 'text-anchor': 'middle', class: 'chart-axis' }, new Intl.DateTimeFormat('id-ID', { hour: '2-digit', minute: '2-digit' }).format(new Date(history[index].time)))));
    const wrap = el('div', { class: 'chart-wrap' });
    const tooltip = el('div', { class: 'chart-tooltip', role: 'status', hidden: true });
    series.forEach(item => {
      let current = [];
      const flush = () => { if (current.length) { chart.append(svg('polyline', { points: current.join(' '), fill: 'none', stroke: item.color, 'stroke-width': 2.4, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' })); current = []; } };
      history.forEach(point => { if (finite(point[item.key])) current.push(`${x(point)},${y(point[item.key])}`); else flush(); });
      flush();
      history.forEach(point => {
        if (!finite(point[item.key])) return;
        const label = `${date(point.time)} · ${item.label} ${format(point[item.key])}`;
        const dot = svg('circle', { cx: x(point), cy: y(point[item.key]), r: history.length === 1 ? 4 : 3.2, fill: item.color, class: 'chart-point', tabindex: 0, 'aria-label': label });
        dot.append(svg('title', {}, label));
        const show = () => { tooltip.textContent = label; tooltip.hidden = false; tooltip.style.left = `${Math.min(68, Math.max(2, x(point) / width * 100))}%`; tooltip.style.top = `${Math.max(0, y(point) / height * 100 - 20)}%`; };
        dot.addEventListener('mouseenter', show); dot.addEventListener('focus', show);
        dot.addEventListener('mouseleave', () => { tooltip.hidden = true; }); dot.addEventListener('blur', () => { tooltip.hidden = true; });
        chart.append(dot);
      });
    });
    wrap.append(chart, tooltip, el('div', { class: 'chart-legend' }, series.map(item => el('span', {}, el('i', { class: `legend-dot ${item.key === 'cpu' || item.key === 'rx' ? 'teal' : 'blue'}` }), item.label)), el('small', {}, 'Celah = data tidak tersedia')));
    return wrap;
  }
  function healthDonut(count) {
    const statuses = [['up', '#119d89'], ['warning', '#e5aa49'], ['down', '#d76565'], ['unknown', '#dce4e7']];
    const total = statuses.reduce((sum, [key]) => sum + (finite(count[key]) ? count[key] : 0), 0);
    const chart = svg('svg', { viewBox: '0 0 180 180', class: 'health-donut', role: 'img', 'aria-label': statuses.map(([key]) => `${labels[key]}: ${number(count[key])}`).join(', ') });
    chart.append(svg('circle', { cx: 90, cy: 90, r: 68, fill: 'none', stroke: '#edf1f1', 'stroke-width': 17 }));
    let offset = 0;
    const circumference = 2 * Math.PI * 68;
    statuses.forEach(([key, color]) => {
      const length = total ? (count[key] || 0) / total * circumference : 0;
      if (length) chart.append(svg('circle', { cx: 90, cy: 90, r: 68, fill: 'none', stroke: color, 'stroke-width': 17, 'stroke-dasharray': `${Math.max(0, length - 3)} ${circumference}`, 'stroke-dashoffset': -offset, transform: 'rotate(-90 90 90)' }));
      offset += length;
    });
    chart.append(svg('text', { x: 90, y: 88, class: 'donut-value', 'text-anchor': 'middle' }, total ? percent((count.up || 0) / total * 100) : '—'), svg('text', { x: 90, y: 108, class: 'donut-label', 'text-anchor': 'middle' }, total ? 'perangkat sehat' : 'belum ada data'));
    return el('div', { class: 'health-content' }, chart, el('div', { class: 'health-legend' }, statuses.map(([key]) => el('div', {}, badge(key), el('strong', {}, number(count[key]))))));
  }
  function deviceName(device, small = false) {
    return el('div', { class: 'device-identity' }, el('span', { class: `device-glyph ${small ? 'small' : ''}` }, icon(device.kind || 'server')), el('div', {}, el('button', { type: 'button', class: 'name-link', 'data-focus-key': `device-${device.id}`, onclick: () => openDevice(device.id) }, device.name), el('small', { class: 'mono' }, device.address)));
  }
  function table(headers, rows, className = '') { return el('div', { class: `table-wrap ${className}` }, el('table', {}, el('thead', {}, el('tr', {}, headers.map(header => el('th', { scope: 'col' }, header)))), el('tbody', {}, rows))); }
  function deviceTable(devices, compact = false) {
    if (!devices.length) return empty('Belum ada perangkat', 'Tambahkan perangkat untuk mulai memantau layanan.', canWrite() ? button('Tambah perangkat', 'plus', () => editDevice(), 'secondary') : null);
    const headers = compact ? ['Perangkat', 'Status', 'Pemeriksaan'] : ['Perangkat', 'Jenis / lokasi', 'Layanan', 'Status', 'Pemeriksaan terakhir', ''];
    return table(headers, devices.map(device => el('tr', {}, el('td', {}, deviceName(device, compact)), ...(!compact ? [el('td', {}, el('span', {}, labels[device.kind] || device.kind), el('small', { class: 'cell-sub' }, device.site || 'Tanpa lokasi')), el('td', {}, el('div', { class: 'service-tags' }, (device.services || []).slice(0, 3).map(key => el('span', { class: 'service-tag' }, serviceLabel(key))), (device.services || []).length > 3 ? el('span', { class: 'service-tag' }, `+${device.services.length - 3}`) : null))] : []), el('td', {}, badge(device.status)), el('td', {}, el('span', { title: date(device.last_checked_at, true) }, age(device.last_checked_at)), !compact ? el('small', { class: 'cell-sub' }, finite(device.latency_ms) ? `${number(device.latency_ms)} ms` : 'Latensi belum tersedia') : null), ...(!compact ? [el('td', {}, button('', 'arrow', () => openDevice(device.id), 'ghost', { 'aria-label': `Detail ${device.name}`, 'data-focus-key': `detail-${device.id}` }))] : []))));
  }
  function renderDevices() {
    const devices = state.data.devices.filter(device => (!state.filters.deviceStatus || device.status === state.filters.deviceStatus) && (!state.filters.kind || device.kind === state.filters.kind));
    text('#filter-count', `${devices.length} perangkat`);
    return el('div', { class: 'page-stack' }, el('div', { class: 'inventory-summary' }, el('span', {}, icon('server'), `${state.data.devices.length} perangkat dalam hasil inventaris`), el('span', {}, icon('shield'), canWrite() ? 'Pemeriksaan sesuai cakupan alamat yang diizinkan' : 'Akses baca saja')), el('section', { class: 'card' }, devices.length ? deviceTable(devices) : empty('Tidak ada perangkat yang cocok', 'Ubah filter pencarian atau tambahkan perangkat ke lingkungan ini.', canWrite() ? button('Tambah perangkat', 'plus', () => editDevice(), 'primary') : null)));
  }
  function incidentList(incidents, compact = false) {
    if (!incidents.length) return empty('Tidak ada insiden', compact ? 'Tidak ada insiden terbuka pada respons terbaru.' : 'Insiden akan muncul di sini sesuai filter yang dipilih.');
    return el('div', { class: 'incident-list' }, incidents.map(incident => el('button', { type: 'button', class: 'incident-item', 'data-focus-key': `incident-${incident.id}`, onclick: () => openIncident(incident.id, incident) }, el('span', { class: `incident-indicator severity-${incident.severity}` }, icon('incident')), el('span', { class: 'incident-copy' }, el('strong', {}, incident.title), el('small', {}, `${incident.device_name || 'Perangkat tidak tersedia'} · ${age(incident.created_at)}`)), el('span', { class: 'incident-right' }, incident.category === 'metric' ? el('span', { class: 'service-tag' }, 'Anomali metrik') : null, badge(incident.severity), !compact ? badge(incident.status) : null), icon('chevron'))));
  }
  function renderIncidents() {
    const incidents = state.data.incidents.filter(incident => !state.filters.severity || incident.severity === state.filters.severity);
    text('#filter-count', `${incidents.length} insiden`);
    const counts = state.data.incidents;
    return el('div', { class: 'page-stack' }, el('div', { class: 'mini-stats' }, ...['open', 'acknowledged', 'resolved'].map(status => el('div', {}, badge(status), el('strong', {}, counts.filter(incident => incident.status === status).length))), el('small', {}, 'Ringkasan hasil filter status')), panel('Daftar insiden', 'Pilih insiden untuk melihat detail dan tindak lanjut', incidentList(incidents)));
  }
  function compactJobs(jobs) {
    if (!jobs.length) return empty('Belum ada eksekusi', 'Rencanakan audit atau perubahan layanan melalui katalog otomasi.');
    return el('div', { class: 'compact-list' }, jobs.map(job => el('button', { type: 'button', class: 'compact-item', onclick: () => openJob(job.id), 'data-focus-key': `job-${job.id}` }, el('span', { class: 'action-icon' }, icon('terminal')), el('span', { class: 'compact-copy' }, el('strong', {}, actionLabel(job.action)), el('small', {}, `${job.device_name || 'Perangkat'} · ${age(job.created_at)}`)), badge(job.status))));
  }
  function renderAutomation() {
    const jobs = state.data.jobs.filter(job => !state.filters.jobStatus || job.status === state.filters.jobStatus);
    text('#filter-count', `${jobs.length} pekerjaan`);
    const actions = state.catalog?.actions || [];
    const catalog = el('div', { class: 'automation-catalog' }, actions.map(action => el('section', { class: 'card automation-card' }, el('span', { class: 'catalog-icon' }, icon(action.id === 'audit' ? 'search' : action.id === 'diagnose' ? 'stethoscope' : action.id === 'collect_evidence' ? 'book' : ['restart_service', 'reload_service'].includes(action.id) ? 'refresh' : 'shield')), el('span', { class: 'catalog-label' }, action.requires_approval ? 'PERSETUJUAN ADMIN' : 'PEMERIKSAAN'), el('h2', {}, action.label), el('p', {}, action.description), el('div', { class: 'catalog-footer' }, el('span', {}, icon(action.requires_approval ? 'shield' : 'book'), action.requires_approval ? 'Perubahan layanan' : 'Audit terkontrol'), button('Buat rencana', 'arrow', () => planAutomation(action.id), 'text', { disabled: !canWrite(), title: !canWrite() ? 'Akses baca saja' : action.label })))));
    const content = jobs.length ? table(['Pekerjaan / aksi', 'Perangkat', 'Status', 'Diajukan oleh', 'Dibuat', ''], jobs.map(job => el('tr', {}, el('td', {}, el('button', { class: 'name-link', type: 'button', onclick: () => openJob(job.id), 'data-focus-key': `job-${job.id}` }, actionLabel(job.action)), el('small', { class: 'cell-sub mono' }, `#${job.id}${job.service ? ` · ${serviceLabel(job.service)}` : ''}`)), el('td', {}, job.device_name || 'Perangkat tidak tersedia', el('small', { class: 'cell-sub' }, job.environment === 'demo' ? 'Demo · simulasi' : 'Real · aktual')), el('td', {}, badge(job.status)), el('td', {}, job.requester || actorName(job.requested_by)), el('td', {}, date(job.created_at)), el('td', {}, button('', 'arrow', () => openJob(job.id), 'ghost', { 'aria-label': `Detail pekerjaan ${job.id}` }))))) : empty('Belum ada pekerjaan yang cocok', 'Gunakan katalog untuk membuat rencana, atau pilih status lain.');
    return el('div', { class: 'page-stack' }, catalog, el('div', { class: 'workflow-strip' }, ...[['01', 'Rencanakan', 'Pilih perangkat & aksi'], ['02', 'Tinjau & setujui', 'Perubahan oleh admin'], ['03', 'Eksekusi', 'Diproses worker'], ['04', 'Telusuri', 'Log & hasil aktual']].map(([step, title, subtitle]) => el('div', {}, el('span', { class: 'step-number' }, step), el('div', {}, el('strong', {}, title), el('small', {}, subtitle))))), panel('Riwayat pekerjaan', 'Tidak ada eksekusi tanpa permintaan yang tercatat', content));
  }
  function actorName(value) { return typeof value === 'object' && value ? value.username || value.name || String(value.id || '—') : String(value ?? '—'); }
  function detailText(value) { return typeof value === 'object' && value !== null ? JSON.stringify(value, null, 2) : String(value ?? ''); }
  function activityList(activity, compact = false) {
    if (!activity.length) return empty('Belum ada aktivitas', 'Tindakan pengguna dan eksekusi akan tercatat di sini.');
    return el('div', { class: `activity-list ${compact ? 'compact' : ''}` }, activity.map(entry => el('div', { class: 'activity-entry' }, el('span', { class: 'timeline-dot' }, icon('activity')), el('div', { class: 'activity-copy' }, el('div', { class: 'activity-title' }, el('strong', {}, entry.action), el('span', {}, actorName(entry.actor))), el('p', {}, detailText(entry.detail)), el('small', {}, date(entry.created_at, !compact))), !compact ? scopeBadge(entry.environment) : null)));
  }
  function renderActivity() {
    const needle = state.filters.activitySearch.toLocaleLowerCase('id');
    const activity = state.data.activity.filter(entry => `${actorName(entry.actor)} ${entry.action} ${detailText(entry.detail)}`.toLocaleLowerCase('id').includes(needle));
    text('#filter-count', `${activity.length} aktivitas`);
    return panel('Audit trail', 'Riwayat dari layanan · urutan sesuai respons terbaru', activityList(activity));
  }
  function routeFor(device, devices) {
    const chain = [], seen = new Set();
    let cursor = device;
    while (cursor && !seen.has(String(cursor.id))) { chain.push(cursor); seen.add(String(cursor.id)); cursor = devices.find(item => String(item.id) === String(cursor.parent_id)); }
    return chain;
  }
  function renderTopology() {
    const devices = state.data.devices;
    if (!devices.length) return panel('Peta koneksi', 'Berdasarkan inventaris', empty('Belum ada koneksi untuk dipetakan', 'Tambahkan perangkat dan tentukan perangkat induk untuk membentuk topologi.', canWrite() ? button('Tambah perangkat', 'plus', () => editDevice(), 'primary') : null));
    const selected = devices.find(device => String(device.id) === String(state.topologySelected));
    const sites = [...new Set(devices.map(device => device.site || 'Tanpa lokasi'))];
    const width = Math.max(860, sites.length * 260);
    const maxRows = Math.max(...sites.map(site => devices.filter(device => (device.site || 'Tanpa lokasi') === site).length));
    const height = Math.max(420, maxRows * 104 + 98);
    const chart = svg('svg', { viewBox: `0 0 ${width} ${height}`, width, height, class: 'topology-svg', role: 'group', 'aria-label': 'Topologi berdasarkan perangkat induk di inventaris. Pilih simpul untuk detail.' });
    const positions = new Map();
    sites.forEach((site, siteIndex) => {
      const center = (siteIndex + 0.5) * width / sites.length;
      chart.append(svg('text', { x: center, y: 36, 'text-anchor': 'middle', class: 'topology-site' }, site));
      devices.filter(device => (device.site || 'Tanpa lokasi') === site).forEach((device, index) => positions.set(String(device.id), { x: center - 100, y: 70 + index * 104 }));
    });
    const route = selected ? routeFor(selected, devices) : [];
    const routeIds = new Set(route.map(device => String(device.id)));
    let links = 0, missing = 0;
    devices.forEach(device => {
      if (device.parent_id === null || device.parent_id === undefined) return;
      const source = positions.get(String(device.parent_id)), target = positions.get(String(device.id));
      if (!source) { missing++; return; }
      links++;
      if (!state.showRoutes) return;
      const sameColumn = source.x === target.x;
      const sx = source.x + (sameColumn ? 200 : 100), sy = source.y + (sameColumn ? 32 : 64), tx = target.x + (sameColumn ? 200 : 100), ty = target.y + (sameColumn ? 32 : 0);
      const d = sameColumn ? `M${sx} ${sy} C${sx + 45} ${sy},${tx + 45} ${ty},${tx} ${ty}` : `M${sx} ${sy} C${sx} ${(sy + ty) / 2},${tx} ${(sy + ty) / 2},${tx} ${ty}`;
      chart.append(svg('path', { d, class: `topology-link ${routeIds.has(String(device.id)) && routeIds.has(String(device.parent_id)) ? 'selected' : ''}` }, svg('title', {}, `${devices.find(item => String(item.id) === String(device.parent_id))?.name || ''} → ${device.name}`)));
    });
    devices.forEach(device => {
      const position = positions.get(String(device.id));
      const group = svg('g', { transform: `translate(${position.x} ${position.y})`, class: `topology-node ${String(device.id) === String(state.topologySelected) ? 'selected' : ''}`, tabindex: 0, role: 'button', 'aria-label': `${device.name}, ${device.address}, ${labels[device.status] || device.status}`, 'aria-pressed': String(String(device.id) === String(state.topologySelected)), 'data-focus-key': `node-${device.id}` });
      group.append(svg('rect', { width: 200, height: 64, rx: 12, class: 'node-background' }), svg('rect', { x: 12, y: 15, width: 31, height: 32, rx: 7, class: 'node-symbol-bg' }), svg('path', { d: 'M19 24h17v6H19zM19 34h17v6H19z', class: 'node-symbol' }), svg('text', { x: 54, y: 28, class: 'node-name' }, device.name.length > 19 ? `${device.name.slice(0, 18)}…` : device.name), svg('text', { x: 54, y: 46, class: 'node-address' }, device.address), svg('circle', { cx: 185, cy: 16, r: 4, class: `node-status status-${['up', 'down', 'warning'].includes(device.status) ? device.status : 'unknown'}` }));
      const choose = () => { state.topologySelected = device.id; renderPage(); };
      group.addEventListener('click', choose); group.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(); } });
      chart.append(group);
    });
    const selector = selectControl([['', 'Pilih perangkat…'], ...devices.map(device => [device.id, device.name])], state.topologySelected || '', { 'aria-label': 'Pilih simpul topologi', 'data-focus-key': 'topology-select', onchange: event => { state.topologySelected = event.target.value; renderPage(); } });
    const toggle = el('label', { class: 'checkbox-label' }, el('input', { type: 'checkbox', checked: state.showRoutes, 'data-focus-key': 'route-toggle', onchange: event => { state.showRoutes = event.target.checked; renderPage(); } }), 'Tampilkan koneksi');
    const aside = selected ? el('div', { class: 'topology-detail' }, el('span', { class: 'eyebrow' }, 'SIMPUL TERPILIH'), el('span', { class: 'large-device-glyph' }, icon(selected.kind)), el('h2', {}, selected.name), el('p', { class: 'mono muted' }, selected.address), badge(selected.status), el('dl', { class: 'detail-list' }, el('dt', {}, 'Lokasi'), el('dd', {}, selected.site || 'Tanpa lokasi'), el('dt', {}, 'Jenis'), el('dd', {}, labels[selected.kind] || selected.kind), el('dt', {}, 'Cakupan'), el('dd', {}, selected.managed ? 'Dikelola' : 'Inventaris saja')), el('h3', {}, 'Rute inventaris'), el('ol', { class: 'route-list' }, [...route].reverse().map(device => el('li', {}, device.name))), el('p', { class: 'field-hint' }, 'Rute mengikuti perangkat induk, bukan hasil penemuan jaringan.'), button('Detail perangkat', 'arrow', () => openDevice(selected.id), 'primary')) : empty('Pilih sebuah simpul', 'Lihat alamat, kondisi, dan rute perangkat dari koneksi inventaris.');
    return el('div', { class: 'page-stack' }, el('section', { class: 'card' }, el('div', { class: 'topology-toolbar' }, el('div', {}, el('strong', {}, `${devices.length} simpul`), el('span', { class: 'muted' }, ` · ${links} koneksi · ${sites.length} lokasi`)), selector, toggle), el('div', { class: 'topology-layout' }, el('div', { class: 'topology-canvas' }, chart), el('aside', { class: 'topology-aside' }, aside)), el('div', { class: 'topology-footer' }, el('div', { class: 'chart-legend' }, badge('up'), badge('warning'), badge('down'), badge('unknown')), el('span', {}, missing ? `${missing} referensi induk tidak tersedia dalam inventaris aktif.` : 'Koneksi berasal dari relasi inventaris.'))));
  }

  function openModal(title, eyebrow, drawer = false, type = 'form') {
    closeModal();
    state.modal = { type };
    $('#detail-dialog').classList.toggle('drawer', drawer);
    text('#dialog-title', title); text('#dialog-eyebrow', eyebrow);
    $('#dialog-body').replaceChildren();
    $('#detail-dialog').showModal();
    return state.modalVersion;
  }
  function closeModal() {
    clearTimeout(state.detailTimer);
    state.modalVersion++;
    state.modal = null;
    if ($('#detail-dialog').open) $('#detail-dialog').close();
  }
  function modalCurrent(version) { return Boolean(state.user && $('#detail-dialog').open && version === state.modalVersion); }
  function modalError(error, version, retry) {
    if (!modalCurrent(version)) return;
    $('#dialog-body').replaceChildren(errorBox(error), ...(retry ? [button('Coba lagi', 'refresh', retry)] : []));
  }
  function scopeNotice(environment, action = 'Perubahan') {
    return el('div', { class: `scope-notice ${environment === 'real' ? 'real' : ''}` }, scopeBadge(environment), el('p', {}, environment === 'real' ? `${action} ditujukan ke lingkungan aktual. Tinjau perangkat dan dampaknya sebelum melanjutkan.` : `${action} berada di lingkungan simulasi. Hasil sintetis tidak menyatakan perubahan pada infrastruktur aktual.`));
  }
  function confirmAction({ title, description, environment = state.environment, caution, exact, note, label = 'Konfirmasi', danger = false, submit }) {
    const dialog = $('#confirm-dialog');
    if (dialog.open) return;
    let busy = false;
    text('#confirm-title', title);
    const body = $('#confirm-body');
    const confirm = $('#confirm-submit');
    const cancel = $('#confirm-cancel');
    const close = $('#confirm-close');
    const error = $('#confirm-error');
    error.hidden = true;
    confirm.disabled = false; cancel.disabled = false; close.disabled = false;
    confirm.className = `btn ${danger ? 'danger' : 'primary'}`;
    confirm.textContent = label;
    body.replaceChildren(scopeNotice(environment, 'Tindakan ini'), el('p', { class: 'confirm-description' }, description));
    if (caution) body.append(el('div', { class: 'caution-box' }, icon('incident'), el('span', {}, caution)));
    let exactInput = null, noteInput = null;
    if (exact !== undefined) {
      exactInput = el('input', { type: 'text', autocomplete: 'off', required: true, placeholder: exact });
      body.append(field(`Ketik nama perangkat: ${exact}`, exactInput, 'Nama harus sama persis untuk memberikan persetujuan.'));
    }
    if (note) {
      noteInput = el('textarea', { rows: 4, required: true, maxlength: 4000, placeholder: 'Tuliskan tindak lanjut dan hasil penanganan…' });
      body.append(field(note, noteInput));
    }
    $('#confirm-form').onsubmit = async event => {
      event.preventDefault();
      if (busy) return;
      if (exactInput && exactInput.value !== exact) { error.textContent = 'Nama perangkat belum sama persis.'; error.hidden = false; exactInput.focus(); return; }
      if (noteInput && !noteInput.value.trim()) { error.textContent = 'Catatan tidak boleh kosong.'; error.hidden = false; noteInput.focus(); return; }
      busy = true; confirm.disabled = true; cancel.disabled = true; close.disabled = true; error.hidden = true;
      confirm.textContent = 'Memproses…';
      try {
        await submit({ confirmation: exactInput?.value, note: noteInput?.value.trim() });
        if (dialog.open) dialog.close();
      } catch (err) { error.textContent = err.message; error.hidden = false; }
      finally { busy = false; confirm.disabled = false; cancel.disabled = false; close.disabled = false; confirm.textContent = label; }
    };
    dialog.oncancel = event => { if (busy) event.preventDefault(); };
    close.onclick = cancel.onclick = () => { if (!busy) dialog.close(); };
    dialog.showModal();
    (exactInput || noteInput || cancel).focus();
  }
  function detailPair(label, value) { return [el('dt', {}, label), el('dd', {}, value ?? '—')]; }
  function scopeReason(device) {
    if (device.environment === 'demo') return 'Pemeriksaan menggunakan simulasi sintetis; tidak menghubungi perangkat aktual.';
    if (!device.checks_allowed) return 'Alamat berada di luar cakupan pemeriksaan yang diizinkan. Perangkat tetap dapat dicatat, tetapi pemeriksaan tidak dijalankan.';
    if (!device.managed) return 'Pemeriksaan tersedia sesuai kebijakan alamat. Perangkat ini belum menjadi target otomasi terkelola.';
    return 'Target terkelola. Pemeriksaan mengakses layanan aktual dan otomasi mengikuti persetujuan.';
  }
  async function openDevice(id) {
    const version = openModal('Detail perangkat', 'INVENTARIS PERANGKAT', true, 'device');
    state.modal.id = id;
    $('#dialog-body').append(loading());
    try {
      const device = await api(`/api/devices/${apiId(id)}`);
      if (!modalCurrent(version)) return;
      state.modal.device = device;
      text('#dialog-title', device.name);
      const controls = el('div', { class: 'detail-actions' }, button('Periksa layanan', 'activity', () => requestCheck(device), 'primary', { disabled: !canWrite() || !device.checks_allowed, title: !canWrite() ? 'Akses baca saja' : !device.checks_allowed ? 'Pemeriksaan tidak diizinkan untuk alamat ini' : 'Jalankan pemeriksaan' }));
      if (canWrite()) controls.append(button('Edit', 'edit', () => editDevice(device)), button('', 'trash', () => archiveDevice(device), 'danger-ghost', { 'aria-label': `Arsipkan ${device.name}` }));
      const autoApproveNote = canApprove() ? el('button', { type: 'button', class: 'auto-approve-toggle' + (device.auto_approve ? ' active' : ''), onclick: () => toggleAutoApprove(device) }, el('span', { class: 'auto-approve-state' }, icon(device.auto_approve ? 'check' : 'close')), el('span', {}, el('strong', {}, 'Auto-approve layanan'), el('small', {}, device.auto_approve ? 'Aktif — ensure/restart langsung dieksekusi tanpa persetujuan terpisah, tetap tercatat audit.' : 'Nonaktif — persetujuan administrator tetap diwajibkan.'))) : null;
      const status = el('div', { id: 'device-live-status', class: 'detail-status' }, badge(device.status), scopeBadge(device.environment));
      const checks = el('div', { id: 'device-checks' }, loading());
      const metrics = el('div', { id: 'device-metrics' }, loading());
      const parentLabel = el('span', {}, device.parent_id === null || device.parent_id === undefined ? 'Tanpa perangkat induk' : `Perangkat #${device.parent_id}`);
      $('#dialog-body').replaceChildren(el('div', { class: 'device-detail-intro' }, el('span', { class: 'large-device-glyph' }, icon(device.kind)), el('div', {}, el('strong', { class: 'detail-address mono' }, device.address), el('small', { class: 'muted' }, `${labels[device.kind] || device.kind} · ${device.site || 'Tanpa lokasi'}`))), status, controls, ...(autoApproveNote ? [autoApproveNote] : []), el('div', { class: 'scope-explanation' }, icon('shield'), el('div', {}, el('strong', {}, device.managed ? 'Target terkelola' : 'Tercatat dalam inventaris'), el('p', {}, scopeReason(device)))), el('dl', { class: 'detail-list' }, ...detailPair('Lokasi', device.site || 'Tanpa lokasi'), ...detailPair('Perangkat induk', parentLabel), ...detailPair('Port exporter', device.exporter_port || 'Tidak ditetapkan'), ...detailPair('Diperbarui', date(device.updated_at, true))), el('div', { class: 'detail-section' }, el('h3', {}, 'Layanan yang dipantau'), el('div', { class: 'service-tags' }, (device.services || []).length ? device.services.map(key => el('span', { class: 'service-tag' }, serviceLabel(key))) : el('span', { class: 'muted' }, 'Belum ada layanan'))), ...(device.notes ? [el('div', { class: 'detail-section' }, el('h3', {}, 'Catatan perangkat'), el('p', { class: 'preserve-lines' }, device.notes))] : []), el('div', { class: 'detail-section' }, el('h3', {}, 'Metrik perangkat'), metrics), el('div', { class: 'detail-section' }, el('div', { class: 'section-heading' }, el('h3', {}, 'Riwayat pemeriksaan'), button('Muat ulang', 'refresh', () => loadDeviceChecks(device, version), 'text')), checks), ...(canWrite() ? [button('Buat insiden perangkat', 'incident', () => createIncident(device.id), 'secondary')] : []));
      if (device.parent_id !== null && device.parent_id !== undefined) api(`/api/devices/${apiId(device.parent_id)}`).then(parent => { if (modalCurrent(version)) parentLabel.replaceChildren(el('button', { class: 'name-link', type: 'button', onclick: () => openDevice(parent.id) }, parent.name)); }).catch(() => { if (modalCurrent(version)) parentLabel.textContent += ' · tidak tersedia'; });
      loadDeviceChecks(device, version);
      loadDeviceMetrics(device, version);
    } catch (error) { modalError(error, version, () => openDevice(id)); }
  }
  async function loadDeviceMetrics(device, version) {
    try {
      const metrics = await api(`/api/metrics?${query({ environment: device.environment, device_id: device.id })}`);
      if (!modalCurrent(version)) return;
      const summary = metrics.summary || {};
      $('#device-metrics').replaceChildren(metrics.available ? el('div', {}, el('div', { class: 'device-metric-grid' }, ...[['CPU', summary.cpu], ['Memori', summary.memory], ['Disk', summary.disk]].map(([label, value]) => el('div', {}, el('small', {}, label), el('strong', {}, percent(value))))), el('small', { class: 'field-hint' }, `${metrics.source === 'demo' ? 'Sintetis' : 'Prometheus'} · ${metrics.updated_at ? date(metrics.updated_at) : 'Menunggu sampel'}`)) : el('div', { class: 'subtle-empty' }, metrics.error || 'Belum tersedia. Perangkat baru mungkin belum memiliki riwayat metrik.'));
    } catch (error) { if (modalCurrent(version)) $('#device-metrics')?.replaceChildren(errorBox(error)); }
  }
  async function loadDeviceChecks(device, version) {
    try {
      const checks = items(await api(`/api/checks?${query({ environment: device.environment, device_id: device.id })}`));
      if (!modalCurrent(version)) return;
      $('#device-checks').replaceChildren(checks.length ? el('div', { class: 'check-history' }, checks.slice(0, 12).map((check, index) => {
        const details = el('details', { class: 'check-run', open: index === 0 });
        details.append(el('summary', {}, el('span', {}, el('strong', {}, `Pemeriksaan #${check.id}`), el('small', {}, `${date(check.created_at)} · ${finite(check.duration_ms) ? `${number(check.duration_ms)} ms` : 'Durasi belum tersedia'}`)), badge(check.status)), el('div', { class: 'check-results' }, (check.results || []).length ? check.results.map(result => el('div', { class: 'check-result' }, el('div', {}, el('strong', {}, result.label || serviceLabel(result.service)), el('small', { class: 'preserve-lines' }, result.detail || 'Tidak ada detail tambahan')), el('div', { class: 'check-result-state' }, badge(result.status), el('small', {}, finite(result.latency_ms) ? `${number(result.latency_ms)} ms` : '—')))) : el('p', { class: 'muted' }, 'Hasil layanan belum tersedia.')));
        return details;
      })) : el('div', { class: 'subtle-empty' }, 'Belum ada pemeriksaan. Jalankan pemeriksaan untuk mendapatkan kondisi layanan.'));
    } catch (error) { if (modalCurrent(version)) $('#device-checks')?.replaceChildren(errorBox(error)); }
  }
  function requestCheck(device) {
    if (!canWrite() || !device.checks_allowed) return;
    confirmAction({ title: 'Jalankan pemeriksaan layanan?', environment: device.environment, description: `${device.name} · ${device.address}. Layanan: ${(device.services || []).map(serviceLabel).join(', ') || 'sesuai konfigurasi perangkat'}.`, caution: device.environment === 'real' ? 'Pemeriksaan membuka koneksi ke port layanan dalam cakupan yang diizinkan. Tidak mengubah konfigurasi layanan.' : 'Worker akan menghasilkan hasil pemeriksaan sintetis untuk perangkat Demo.', label: 'Jalankan pemeriksaan', submit: async () => {
      const response = await api(`/api/devices/${apiId(device.id)}/check`, { method: 'POST', body: {} });
      if (!response.job) throw new ApiError('Respons pekerjaan tidak lengkap. Segarkan riwayat sebelum mengulangi.', 0);
      toast(`Pemeriksaan #${response.job.id}: ${labels[response.job.status] || response.job.status}.`);
      watchCheckJob(response.job, device);
      if (state.environment === device.environment) loadPage();
    } });
  }
  function watchCheckJob(job, device) {
    const key = String(job.id);
    clearTimeout(state.watchedJobs.get(key));
    const version = state.sessionVersion;
    let attempts = 0;
    const poll = async () => {
      if (!state.user || version !== state.sessionVersion) { state.watchedJobs.delete(key); return; }
      if (document.hidden) { state.watchedJobs.set(key, setTimeout(poll, 4000)); return; }
      try {
        const current = await api(`/api/jobs/${apiId(job.id)}`);
        if (version !== state.sessionVersion) return;
        if (terminal.has(current.status)) {
          state.watchedJobs.delete(key);
          toast(`Pemeriksaan ${device.name}: ${labels[current.status] || current.status}.`, current.status === 'succeeded' ? 'success' : 'error');
          if (state.modal?.type === 'device' && String(state.modal.id) === String(device.id)) {
            loadDeviceChecks(device, state.modalVersion);
            const modalVersion = state.modalVersion;
            api(`/api/devices/${apiId(device.id)}`).then(updated => { if (modalCurrent(modalVersion)) $('#device-live-status').replaceChildren(badge(updated.status), scopeBadge(updated.environment)); }).catch(error => toast(error.message, 'error'));
          }
          if (state.environment === device.environment) loadPage();
          return;
        }
      } catch (error) { if (error.status === 401 || error.status === 403 || error.status === 404) { state.watchedJobs.delete(key); if (state.user) toast(error.message, 'error'); return; } }
      if (++attempts >= 150) { state.watchedJobs.delete(key); toast(`Pemantauan pemeriksaan #${job.id} dijeda. Lihat status terbaru dalam riwayat otomasi.`, 'info'); return; }
      state.watchedJobs.set(key, setTimeout(poll, 2400));
    };
    poll();
  }
  async function editDevice(device = null) {
    if (!canWrite()) return;
    const environment = device?.environment || state.environment;
    const version = openModal(device ? 'Edit perangkat' : 'Tambah perangkat', 'INVENTARIS', true);
    $('#dialog-body').append(loading());
    try {
      const [devices, catalog] = await Promise.all([api(`/api/devices?${query({ environment })}`).then(items), state.catalog ? Promise.resolve(state.catalog) : api('/api/catalog')]);
      if (!modalCurrent(version)) return;
      state.catalog = catalog;
      const nameInput = el('input', { name: 'name', value: device?.name || '', required: true, maxlength: 80, placeholder: 'Contoh: Core Server' });
      const addressInput = el('input', { name: 'address', value: device?.address || (environment === 'real' ? '127.0.0.1' : ''), required: true, maxlength: 45, placeholder: 'Alamat IP perangkat', spellcheck: 'false' });
      const kind = selectControl(['server', 'router', 'switch', 'storage'].map(key => [key, labels[key]]), device?.kind || 'server');
      const site = el('input', { value: device?.site || '', maxlength: 100, placeholder: 'Contoh: Jakarta · DC 01' });
      const parents = devices.filter(item => String(item.id) !== String(device?.id));
      const parent = selectControl([['', 'Tanpa perangkat induk'], ...parents.map(item => [item.id, item.name])], device?.parent_id || '');
      const exporter = el('input', { type: 'number', min: 1, max: 65535, step: 1, value: device?.exporter_port ?? 9100, required: true });
      const notes = el('textarea', { rows: 3, maxlength: 4000, placeholder: 'Fungsi perangkat atau catatan operasional…' }, device?.notes || '');
      const services = el('fieldset', { class: 'service-fieldset' }, el('legend', {}, 'Layanan yang dipantau'), el('div', { class: 'service-options' }, (catalog.services || []).map(service => el('label', { class: 'service-option' }, el('input', { type: 'checkbox', name: 'service', value: service.id, checked: device?.services?.includes(service.id) || false }), el('span', {}, el('strong', {}, service.label), el('small', {}, `${service.protocol || 'TCP'} · ${service.port ?? '—'}`))))));
      const formError = el('div', { role: 'alert', hidden: true });
      const submit = button(device ? 'Simpan perubahan' : 'Tambahkan perangkat', 'check', null, 'primary', { type: 'submit' });
      const form = el('form', { class: 'device-form' }, scopeNotice(environment, 'Pencatatan inventaris'), el('div', { class: 'form-grid' }, field('Nama perangkat', nameInput, null, 'span-2'), field('Alamat IP / host', addressInput, 'Alamat di luar cakupan tetap dapat dicatat; pemeriksaan dan otomasi dibatasi.', 'span-2'), field('Jenis perangkat', kind), field('Lokasi', site), field('Perangkat induk', parent), field('Port node exporter', exporter)), services, field('Catatan', notes), el('div', { class: 'scope-explanation' }, icon('info'), el('div', {}, el('strong', {}, 'Inventaris tidak mendaftarkan akses remote'), el('p', {}, `Jaringan yang diizinkan: ${(catalog.allowed_networks || []).join(', ') || 'ditentukan oleh kebijakan layanan'}. Menyimpan perangkat tidak menjalankan Ansible.`))), formError, el('div', { class: 'form-footer' }, button('Batal', null, () => device ? openDevice(device.id) : closeModal()), submit));
      form.addEventListener('submit', event => {
        event.preventDefault();
        if (!nameInput.value.trim() || !addressInput.value.trim()) { formError.replaceChildren(errorBox(new Error('Nama dan alamat tidak boleh kosong.'))); formError.hidden = false; return; }
        const payload = { name: nameInput.value.trim(), address: addressInput.value.trim(), kind: kind.value, site: site.value.trim(), services: $$('input[name="service"]:checked', services).map(input => input.value), notes: notes.value.trim(), parent_id: parent.value ? parents.find(item => String(item.id) === parent.value)?.id ?? parent.value : null, exporter_port: Number(exporter.value), ...(!device ? { environment } : {}) };
        confirmAction({ title: device ? 'Simpan perubahan inventaris?' : 'Tambahkan perangkat ini?', environment, description: `${payload.name} · ${payload.address}. Hanya inventaris yang diperbarui; tidak ada konfigurasi layanan yang diubah.`, label: device ? 'Simpan perubahan' : 'Tambahkan perangkat', submit: async () => {
          submit.disabled = true;
          try {
            const response = await api(device ? `/api/devices/${apiId(device.id)}` : '/api/devices', { method: device ? 'PATCH' : 'POST', body: payload });
            toast(device ? 'Inventaris perangkat diperbarui.' : 'Perangkat ditambahkan ke inventaris.');
            const saved = response.device || response;
            if (modalCurrent(version)) { if (saved.id || device?.id) openDevice(saved.id || device.id); else closeModal(); }
            if (state.environment === environment) loadPage();
          } finally { submit.disabled = false; }
        } });
      });
      $('#dialog-body').replaceChildren(form);
      nameInput.focus();
    } catch (error) { modalError(error, version, () => editDevice(device)); }
  }
  function toggleAutoApprove(device) {
    if (!canApprove()) return;
    const enable = !device.auto_approve;
    confirmAction({ title: enable ? 'Aktifkan auto-approve?' : 'Nonaktifkan auto-approve?', environment: device.environment, description: `${device.name} (${device.address}).`, caution: enable ? 'Perubahan layanan (Pastikan aktif / Restart) pada perangkat ini akan langsung dieksekusi tanpa persetujuan terpisah. Tetap terbatas pada katalog aksi tetap, dan setiap eksekusi tercatat audit dengan penanda auto-approve.' : 'Persetujuan administrator kembali diwajibkan untuk setiap perubahan layanan.', label: enable ? 'Aktifkan auto-approve' : 'Nonaktifkan', danger: enable, submit: async () => {
      const updated = await api(`/api/devices/${apiId(device.id)}/auto-approve`, { method: 'PATCH', body: { enabled: enable } });
      toast(enable ? 'Auto-approve diaktifkan untuk perangkat ini.' : 'Auto-approve dinonaktifkan.');
      if (modalCurrent(state.modalVersion)) openDevice(updated.id || device.id);
      if (state.environment === device.environment) loadPage();
    } });
  }
  function archiveDevice(device) {
    if (!canWrite()) return;
    confirmAction({ title: 'Arsipkan perangkat?', environment: device.environment, description: `${device.name} (${device.address}) akan dikeluarkan dari inventaris aktif.`, caution: 'Riwayat pemeriksaan, insiden, dan otomasi tetap tersimpan. Pengarsipan tidak mematikan perangkat atau layanannya. Tinjau koneksi induk dan pekerjaan yang masih aktif.', danger: true, label: 'Arsipkan perangkat', submit: async () => {
      await api(`/api/devices/${apiId(device.id)}`, { method: 'DELETE', body: {} });
      toast('Perangkat diarsipkan. Riwayat tetap tersimpan.');
      closeModal(); loadPage();
    } });
  }
  async function createIncident(deviceId = null) {
    if (!canWrite()) return;
    const environment = state.environment;
    const version = openModal('Buat insiden', 'RESPONS OPERASIONAL');
    $('#dialog-body').append(loading());
    try {
      const devices = items(await api(`/api/devices?${query({ environment })}`));
      if (!modalCurrent(version)) return;
      if (!devices.length) { $('#dialog-body').replaceChildren(empty('Perangkat belum tersedia', 'Tambahkan perangkat sebelum mencatat insiden.', button('Tambah perangkat', 'plus', () => editDevice(), 'primary'))); return; }
      const device = selectControl([['', 'Pilih perangkat'], ...devices.map(item => [item.id, `${item.name} · ${item.address}`])], deviceId || '', { required: true });
      const title = el('input', { required: true, maxlength: 200, placeholder: 'Ringkasan singkat gangguan' });
      const severity = selectControl(['info', 'warning', 'critical'].map(key => [key, labels[key]]), 'warning');
      const details = el('textarea', { rows: 5, maxlength: 8000, placeholder: 'Gejala, dampak, dan konteks yang perlu diketahui…' });
      const form = el('form', {}, scopeNotice(environment, 'Pencatatan insiden'), field('Perangkat', device), field('Judul insiden', title), field('Prioritas', severity), field('Detail insiden', details), el('div', { class: 'form-footer' }, button('Batal', null, closeModal), button('Tinjau insiden', 'arrow', null, 'primary', { type: 'submit' })));
      form.addEventListener('submit', event => {
        event.preventDefault();
        if (!title.value.trim()) { title.setCustomValidity('Judul tidak boleh kosong.'); title.reportValidity(); return; }
        const chosen = devices.find(item => String(item.id) === device.value);
        if (!chosen) return;
        confirmAction({ title: 'Catat insiden baru?', environment, description: `${title.value.trim()} · ${chosen.name} · ${labels[severity.value]}.`, label: 'Buat insiden', submit: async () => {
          const response = await api('/api/incidents', { method: 'POST', body: { device_id: chosen.id, title: title.value.trim(), severity: severity.value, details: details.value.trim() } });
          toast('Insiden berhasil dicatat.');
          const incident = response.incident || response;
          if (incident.id) openIncident(incident.id, { ...incident, device_name: incident.device_name || chosen.name }); else closeModal();
          loadPage();
        } });
      });
      title.addEventListener('input', () => title.setCustomValidity(''));
      $('#dialog-body').replaceChildren(form);
    } catch (error) { modalError(error, version, () => createIncident(deviceId)); }
  }
  async function openIncident(id, incident) {
    if (!incident) return;
    const version = openModal(incident.title, `INSIDEN #${id}`, true, 'incident');
    state.modal.id = id;
    const environment = state.environment;
    const actions = el('div', { class: 'detail-actions' });
    if (canWrite() && incident.status !== 'resolved') {
      if (incident.status === 'open') actions.append(button('Mulai penanganan', 'check', () => updateIncident(incident, 'acknowledged', environment), 'primary'));
      actions.append(button('Selesaikan insiden', 'shield', () => updateIncident(incident, 'resolved', environment)));
    }
    const aiBox = el('div', { id: 'incident-ai', class: 'detail-section' }, loading());
    $('#dialog-body').replaceChildren(el('div', { class: 'detail-status' }, badge(incident.severity), badge(incident.status), scopeBadge(environment)), actions, el('dl', { class: 'detail-list' }, ...detailPair('Perangkat', incident.device_id ? el('button', { type: 'button', class: 'name-link', onclick: () => openDevice(incident.device_id) }, incident.device_name || `#${incident.device_id}`) : 'Tidak tersedia'), ...detailPair('Ditugaskan ke', incident.assignee || actorName(incident.assigned_to)), ...detailPair('Dibuat', date(incident.created_at, true)), ...detailPair('Diperbarui', date(incident.updated_at, true)), ...detailPair('Diselesaikan', incident.resolved_at ? date(incident.resolved_at, true) : 'Belum selesai')), el('section', { class: 'detail-section' }, el('h3', {}, 'Detail insiden'), el('p', { class: 'preserve-lines' }, incident.details || 'Tidak ada detail tambahan.')), el('section', { class: 'detail-section' }, el('h3', {}, 'Catatan penanganan'), el('p', { class: 'preserve-lines' }, incident.resolution_note || 'Belum ada catatan.')), aiBox);
    const timeline = el('section', { class: 'detail-section' }, el('h3', {}, 'Riwayat penanganan'), el('p', { class: 'muted' }, 'Memuat riwayat…'));
    $('#dialog-body').insertBefore(timeline, aiBox);
    api(`/api/incidents/${apiId(id)}?${query({ environment })}`).then(detail => {
      if (!modalCurrent(version)) return;
      const history = detail.history || [];
      timeline.replaceChildren(el('h3', {}, 'Riwayat penanganan'), history.length ? el('div', { class: 'check-history' }, history.map(entry => el('div', { class: 'activity-entry' }, el('span', { class: 'timeline-dot' }, icon('activity')), el('div', { class: 'activity-copy' }, el('div', { class: 'activity-title' }, el('strong', {}, entry.action), el('span', {}, entry.actor)), entry.note ? el('p', { class: 'preserve-lines' }, entry.note) : null, el('small', {}, date(entry.created_at, true)))))) : el('p', { class: 'muted' }, 'Belum ada riwayat tambahan.'));
    }).catch(error => { if (modalCurrent(version)) timeline.replaceChildren(el('h3', {}, 'Riwayat penanganan'), errorBox(error)); });
    loadIncidentAnalysis(incident, aiBox);
  }
  async function loadIncidentAnalysis(incident, container) {
    const version = state.modalVersion;
    try {
      const status = await api('/api/ai/status').catch(() => ({ available: false }));
      if (version !== state.modalVersion) return;
      if (!status.available || !canWrite()) {
        container.replaceChildren(el('h3', {}, 'Analisis asisten (opsional)'), el('p', { class: 'muted' }, 'Asisten AI tidak aktif pada layanan ini. Aplikasi tetap berfungsi penuh tanpa fitur ini.'));
        return;
      }
      const analyse = button('Buat analisis', 'bolt', async () => {
        analyse.disabled = true;
        container.replaceChildren(el('h3', {}, 'Analisis asisten'), loading());
        try {
          const analysis = await api(`/api/incidents/${apiId(incident.id)}/explain?${query({ environment: incident.environment || state.environment })}`, { method: 'POST', body: {} });
          if (version !== state.modalVersion) return;
          const followup = button('Saran tindak lanjut', 'bolt', async () => {
            followup.disabled = true;
            try {
              const result = await api(`/api/incidents/${apiId(incident.id)}/followup?${query({ environment: incident.environment || state.environment })}`, { method: 'POST', body: {} });
              container.append(el('div', { class: 'detail-section' }, el('div', { class: 'section-heading' }, el('h3', {}, 'Saran tindak lanjut'), el('span', { class: 'ai-source' }, icon('bolt'), `${result.precedent_count || 0} preseden · baca saja`)), el('div', { class: 'ai-summary preserve-lines' }, result.suggestions)));
            } catch (error) { container.append(errorBox(error)); } finally { followup.disabled = false; }
          }, 'secondary');
          container.replaceChildren(el('div', { class: 'section-heading' }, el('h3', {}, 'Analisis asisten'), el('span', { class: 'ai-source' }, icon('bolt'), 'AI · ' + (analysis.model || 'asisten') + ' · baca saja')), el('div', { class: 'ai-summary preserve-lines' }, analysis.summary), el('div', { class: 'form-footer' }, followup));
        } catch (error) {
          if (version === state.modalVersion) container.replaceChildren(el('h3', {}, 'Analisis asisten'), errorBox(error), el('div', { class: 'form-footer' }, analyse));
        } finally { analyse.disabled = false; }
      }, 'primary');
      container.replaceChildren(el('h3', {}, 'Analisis asisten (opsional)'), el('p', { class: 'muted' }, 'Minta ringkasan berdasarkan data insiden yang tersimpan. Tidak ada tindakan yang akan dijalankan.'), el('div', { class: 'form-footer' }, analyse));
    } catch (error) {
      if (version === state.modalVersion) container.replaceChildren(el('h3', {}, 'Analisis asisten (opsional)'), errorBox(error));
    }
  }
  function updateIncident(incident, status, environment) {
    if (!canWrite()) return;
    confirmAction({ title: status === 'resolved' ? 'Selesaikan insiden?' : 'Mulai menangani insiden?', environment, description: `${incident.title} · ${incident.device_name || 'Perangkat'}. Status akan berubah menjadi ${labels[status].toLowerCase()}.`, note: status === 'resolved' ? 'Catatan penyelesaian' : 'Catatan penanganan', label: status === 'resolved' ? 'Selesaikan insiden' : 'Mulai penanganan', submit: async ({ note }) => {
      const response = await api(`/api/incidents/${apiId(incident.id)}`, { method: 'PATCH', body: { status, note } });
      toast(`Insiden: ${labels[status]}.`);
      const updated = response.incident || response;
      if (updated.id && updated.status) openIncident(updated.id, { ...incident, ...updated });
      else {
        const fresh = items(await api(`/api/incidents?${query({ environment })}`)).find(item => String(item.id) === String(incident.id));
        if (fresh) openIncident(fresh.id, fresh); else closeModal();
      }
      loadPage();
    } });
  }
  async function planAutomation(actionId = 'audit', deviceId = null) {
    if (!canWrite()) return;
    const environment = state.environment;
    const version = openModal('Rencana otomasi', 'ANSIBLE · CONTROLLED AUTOMATION');
    $('#dialog-body').append(loading());
    try {
      const [devices, catalog] = await Promise.all([api(`/api/devices?${query({ environment })}`).then(items), state.catalog ? Promise.resolve(state.catalog) : api('/api/catalog')]);
      if (!modalCurrent(version)) return;
      state.catalog = catalog;
      if (!devices.length || !catalog.actions?.length) { $('#dialog-body').replaceChildren(empty('Target otomasi belum tersedia', 'Tambahkan perangkat terkelola sebelum membuat rencana otomasi.')); return; }
      const device = selectControl([['', 'Pilih target perangkat'], ...devices.map(item => [item.id, `${item.name} · ${item.address}${environment === 'real' && !item.managed ? ' · inventaris saja' : ''}`])], deviceId || '', { required: true });
      const action = selectControl(catalog.actions.map(item => [item.id, item.label]), catalog.actions.some(item => item.id === actionId) ? actionId : catalog.actions[0].id, { required: true });
      const service = selectControl([], '');
      const serviceField = field('Layanan target', service);
      const plan = el('div', { class: 'plan-preview' });
      const submit = button('Tinjau & ajukan', 'arrow', null, 'primary', { type: 'submit' });
      function updatePlan() {
        const chosen = devices.find(item => String(item.id) === device.value);
        const selectedAction = catalog.actions.find(item => item.id === action.value);
        const oldValue = service.value;
        const available = (catalog.services || []).filter(item => chosen?.services?.includes(item.id));
        service.replaceChildren(el('option', { value: '' }, 'Pilih layanan'), ...available.map(item => el('option', { value: item.id }, item.label)));
        if (available.some(item => item.id === oldValue)) service.value = oldValue;
        serviceField.hidden = !selectedAction?.requires_service;
        service.required = Boolean(selectedAction?.requires_service);
        const allowed = chosen && (environment === 'demo' || chosen.managed);
        submit.disabled = !allowed;
        plan.replaceChildren(el('div', { class: 'section-heading' }, el('h3', {}, 'Pratinjau rencana'), icon('shield')), el('p', {}, selectedAction?.description || 'Pilih aksi untuk meninjau rencana.'), el('dl', { class: 'detail-list' }, ...detailPair('Target', chosen ? `${chosen.name} · ${chosen.address}` : 'Belum dipilih'), ...detailPair('Eksekusi', environment === 'demo' ? 'Simulasi sintetis oleh worker' : 'Ansible pada target aktual'), ...detailPair('Persetujuan', selectedAction?.requires_approval ? (chosen?.auto_approve ? 'Auto-approve aktif — langsung dieksekusi, tetap tercatat audit' : 'Wajib disetujui administrator') : 'Masuk antrean setelah konfirmasi')), ...(chosen && !allowed ? [el('div', { class: 'inline-error' }, 'Perangkat ini hanya tercatat dalam inventaris dan tidak termasuk target otomasi terkelola.')] : []), el('small', { class: 'field-hint' }, selectedAction?.requires_approval ? (chosen?.auto_approve ? 'Perangkat ini ditandai auto-approve oleh admin. Pekerjaan akan langsung masuk antrean eksekusi tanpa langkah persetujuan terpisah.' : 'Mengajukan rencana tidak menyetujui perubahan. Administrator harus mengonfirmasi nama target secara terpisah.') : (selectedAction?.id === 'diagnose' ? 'Diagnosis hanya membaca status unit, log terakhir, disk, dan memori. Hasil dilampirkan ke insiden terbuka perangkat ini.' : 'Audit akan mengumpulkan kondisi layanan tanpa meminta perubahan konfigurasi.')));
      }
      device.addEventListener('change', updatePlan); action.addEventListener('change', updatePlan);
      const form = el('form', {}, scopeNotice(environment, 'Otomasi'), field('Perangkat target', device), field('Aksi', action), serviceField, plan, el('div', { class: 'form-footer' }, button('Batal', null, closeModal), submit));
      form.addEventListener('submit', event => {
        event.preventDefault();
        const chosen = devices.find(item => String(item.id) === device.value);
        const selectedAction = catalog.actions.find(item => item.id === action.value);
        if (!chosen || !selectedAction || (environment === 'real' && !chosen.managed)) return;
        const payload = { device_id: chosen.id, action: action.value, ...(selectedAction.requires_service ? { service: service.value } : {}) };        confirmAction({ title: 'Ajukan rencana otomasi?', environment, description: `${selectedAction.label} · ${chosen.name} (${chosen.address})${payload.service ? ` · ${serviceLabel(payload.service)}` : ''}.`, caution: selectedAction.requires_approval ? 'Pekerjaan menunggu persetujuan admin. Ensure atau restart dapat memengaruhi ketersediaan layanan setelah disetujui.' : 'Audit akan masuk antrean eksekusi worker. Tinjau target sebelum melanjutkan.', label: 'Ajukan rencana', submit: async () => {
          const response = await api('/api/jobs', { method: 'POST', body: payload });
          if (!response.job) throw new ApiError('Respons pekerjaan tidak lengkap. Periksa riwayat sebelum mengulangi.', 0);
          toast(`Pekerjaan #${response.job.id}: ${labels[response.job.status] || response.job.status}.`);
          openJob(response.job.id);
          loadPage();
        } });
      });
      $('#dialog-body').replaceChildren(form);
      updatePlan();
    } catch (error) { modalError(error, version, () => planAutomation(actionId, deviceId)); }
  }
  async function openJob(id) {
    const version = openModal(`Pekerjaan #${id}`, 'RIWAYAT OTOMASI', true, 'job');
    state.modal.id = id;
    $('#dialog-body').replaceChildren(loading());
    try {
      const job = await api(`/api/jobs/${apiId(id)}`);
      if (!modalCurrent(version)) return;
      const status = el('div', { id: 'job-live-status', class: 'detail-status' });
      const actions = el('div', { id: 'job-live-actions', class: 'detail-actions' });
      const detail = el('div', { id: 'job-live-detail' });
      const logs = el('pre', { id: 'job-live-logs', class: 'job-logs', tabindex: 0, 'aria-label': 'Log eksekusi pekerjaan' });
      const result = el('div', { id: 'job-live-result' });
      const polling = el('small', { id: 'job-polling', class: 'field-hint', role: 'status' });
      $('#dialog-body').replaceChildren(status, scopeNotice(job.environment, 'Eksekusi ini'), el('div', { class: 'job-action-title' }, el('span', { class: 'catalog-icon' }, icon('terminal')), el('div', {}, el('h3', {}, actionLabel(job.action)), el('p', {}, `${job.device_name || 'Perangkat'}${job.service ? ` · ${serviceLabel(job.service)}` : ''}`))), actions, detail, el('div', { class: 'detail-section' }, el('div', { class: 'section-heading' }, el('h3', {}, 'Log eksekusi'), button('Perbarui', 'refresh', () => refreshJob(id, version), 'text')), logs, polling), el('div', { class: 'detail-section' }, el('h3', {}, 'Hasil pekerjaan'), result));
      renderJobDetail(job);
      if (!terminal.has(job.status)) state.detailTimer = setTimeout(() => refreshJob(id, version), 2500);
    } catch (error) { modalError(error, version, () => openJob(id)); }
  }
  function renderJobDetail(job) {
    state.modal.job = job;
    $('#job-live-status').replaceChildren(badge(job.status), scopeBadge(job.environment));
    const actionNode = $('#job-live-actions');
    const activeKey = actionNode.contains(document.activeElement) ? document.activeElement.dataset.focusKey : null;
    const actions = [];
    if (job.status === 'awaiting_approval') {
      if (canApprove()) actions.push(button('Tinjau persetujuan', 'shield', () => approveJob(job), 'primary', { 'data-focus-key': 'approve-job' }));
      else actions.push(el('p', { class: 'field-hint' }, 'Menunggu persetujuan administrator.'));
    }
    if (canWrite() && ['awaiting_approval', 'queued'].includes(job.status)) actions.push(button('Batalkan pekerjaan', 'close', () => cancelJob(job), 'danger-ghost', { 'data-focus-key': 'cancel-job' }));
    actionNode.replaceChildren(...actions);
    if (activeKey) $$('[data-focus-key]', actionNode).find(node => node.dataset.focusKey === activeKey)?.focus({ preventScroll: true });
    $('#job-live-detail').replaceChildren(el('dl', { class: 'detail-list' }, ...detailPair('ID pekerjaan', `#${job.id}`), ...detailPair('Diajukan oleh', job.requester || actorName(job.requested_by)), ...detailPair('Disetujui oleh', job.approver || actorName(job.approved_by)), ...detailPair('Dibuat', date(job.created_at, true)), ...detailPair('Mulai', job.started_at ? date(job.started_at, true) : 'Belum dimulai'), ...detailPair('Selesai', job.finished_at ? date(job.finished_at, true) : 'Belum selesai')));
    const log = $('#job-live-logs');
    const nearEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 35;
    const logText = job.logs || (job.status === 'awaiting_approval' ? 'Belum dieksekusi. Menunggu persetujuan administrator.' : job.status === 'queued' ? 'Menunggu worker. Log akan muncul setelah eksekusi dimulai.' : 'Belum ada log yang dilaporkan oleh worker.');
    if (log.textContent !== logText) { log.textContent = logText; if (nearEnd) log.scrollTop = log.scrollHeight; }
    $('#job-live-result').replaceChildren(job.result !== null && job.result !== undefined ? el('pre', { class: 'job-result', tabindex: 0 }, detailText(job.result)) : el('p', { class: 'muted' }, 'Belum ada hasil yang dilaporkan.'));
    text('#job-polling', terminal.has(job.status) ? 'Status akhir diterima dari layanan.' : 'Status & log diperbarui otomatis selama panel terbuka.');
  }
  async function refreshJob(id, version) {
    clearTimeout(state.detailTimer);
    if (!modalCurrent(version)) return;
    if (document.hidden) { state.detailTimer = setTimeout(() => refreshJob(id, version), 4000); return; }
    try {
      const job = await api(`/api/jobs/${apiId(id)}`);
      if (!modalCurrent(version)) return;
      renderJobDetail(job);
      if (!terminal.has(job.status)) state.detailTimer = setTimeout(() => refreshJob(id, version), 2500);
    } catch (error) {
      if (!modalCurrent(version)) return;
      text('#job-polling', `Pembaruan terhenti. ${error.message}`);
      if (![401, 403, 404].includes(error.status)) state.detailTimer = setTimeout(() => refreshJob(id, version), 10000);
    }
  }
  async function approveJob(job) {
    if (!canApprove() || job.status !== 'awaiting_approval') return;
    try {
      const device = await api(`/api/devices/${apiId(job.device_id)}`);
      confirmAction({ title: 'Setujui perubahan layanan?', environment: job.environment, description: `${actionLabel(job.action)} · ${serviceLabel(job.service)} · ${device.name} (${device.address}).`, caution: 'Restart dapat memutus koneksi aktif. Memastikan layanan aktif dapat memulai proses yang sedang berhenti. Persetujuan akan memasukkan pekerjaan ke antrean eksekusi; tindakan yang berjalan tidak dapat dibatalkan di sini.', exact: device.name, label: 'Setujui & antrekan', submit: async ({ confirmation }) => {
        await api(`/api/jobs/${apiId(job.id)}/approve`, { method: 'POST', body: { confirmation } });
        toast('Persetujuan dicatat. Periksa status eksekusi dari worker.');
        if (state.modal?.type === 'job' && String(state.modal.id) === String(job.id)) refreshJob(job.id, state.modalVersion);
        loadPage();
      } });
    } catch (error) { toast(error.message, 'error'); }
  }
  function cancelJob(job) {
    if (!canWrite() || !['awaiting_approval', 'queued'].includes(job.status)) return;
    confirmAction({ title: 'Batalkan pekerjaan?', environment: job.environment, description: `Pekerjaan #${job.id} · ${actionLabel(job.action)} · ${job.device_name || 'Perangkat'}.`, caution: 'Hanya pekerjaan yang masih menunggu persetujuan atau antrean yang dapat dibatalkan. Status akan diperiksa kembali oleh layanan.', label: 'Batalkan pekerjaan', danger: true, submit: async () => {
      await api(`/api/jobs/${apiId(job.id)}/cancel`, { method: 'POST', body: {} });
      toast('Permintaan pembatalan dicatat.');
      if (state.modal?.type === 'job' && String(state.modal.id) === String(job.id)) refreshJob(job.id, state.modalVersion);
      loadPage();
    } });
  }
  async function aiSettings() {
    if (!canApprove()) return;
    closeProfile();
    const version = openModal('Pengaturan asisten AI', 'AI · OPSIONAL · BACA SAJA');
    $('#dialog-body').append(loading());
    let current;
    try {
      current = await api('/api/ai/settings');
    } catch (error) { modalError(error, version, aiSettings); return; }
    if (!modalCurrent(version)) return;
    const enabled = el('input', { type: 'checkbox', role: 'switch', checked: current.enabled });
    const providerInfo = el('div', { class: 'ai-provider-note' }, icon('info'),
      el('span', {}, 'Penyedia yang kompatibel: OpenAI, DeepSeek, Qwen, GLM, OpenRouter, vLLM/Ollama lokal, dan layanan lain dengan endpoint Chat Completions. Contoh OpenRouter: Base URL https://openrouter.ai/api/v1, Model ID berakhiran :free untuk model gratis.'));
    const baseUrl = el('input', { value: current.base_url, maxlength: 300, placeholder: 'https://api.example.com/v1', spellcheck: 'false', autocomplete: 'off' });
    const apiKey = el('input', { type: 'password', value: '', placeholder: current.has_key ? `Tersimpan ····${current.key_hint} (kosongkan untuk tetap memakai)` : 'Masukkan kunci API', autocomplete: 'new-password' });
    const keyEye = button('', current.has_key ? 'check' : 'key', () => { apiKey.type = apiKey.type === 'password' ? 'text' : 'password'; }, 'ghost', { 'aria-label': 'Tampilkan atau sembunyikan kunci' });
    const apiKeyWrap = el('div', { class: 'key-input-wrap' }, apiKey, keyEye);
    const modelId = el('input', { value: current.model, maxlength: 120, placeholder: 'Contoh: qwen3.8-max', spellcheck: 'false', autocomplete: 'off', list: 'ai-model-list' });
    const modelList = el('datalist', { id: 'ai-model-list' });
    const modelsButton = button('Ambil daftar model', 'refresh', async () => {
      modelsButton.disabled = true;
      try {
        const result = await api('/api/ai/settings/models', { method: 'POST', body: { base_url: baseUrl.value.trim(), api_key: apiKey.value, timeout: Number(timeout.value) || 20, max_tokens: Number(maxTokens.value) || 600 } });
        modelList.replaceChildren(...(result.models || []).map(value => el('option', { value })));
        toast((result.models || []).length ? `${result.models.length} model tersedia untuk dipilih.` : 'Penyedia tidak mengembalikan daftar model.', (result.models || []).length ? 'success' : 'info');
      } catch (error) { toast(error.message, 'error'); } finally { modelsButton.disabled = false; }
    }, 'secondary');
    const timeout = el('input', { type: 'number', min: 2, max: 60, step: 1, value: 20 });
    const maxTokens = el('input', { type: 'number', min: 64, max: 2000, step: 1, value: 600 });
    const verifyOut = el('div', { class: 'ai-verify-result', role: 'status', hidden: true });
    const formError = el('div', { role: 'alert', hidden: true });
    const verifyBtn = button('Uji koneksi', 'bolt', async () => {
      verifyBtn.disabled = true;
      verifyOut.hidden = false;
      verifyOut.className = 'ai-verify-result';
      verifyOut.replaceChildren(el('span', { class: 'spinner' }), 'Menguji koneksi ke penyedia…');
      try {
        const result = await api('/api/ai/settings/verify', { method: 'POST', body: { base_url: baseUrl.value.trim(), model: modelId.value.trim(), api_key: apiKey.value, timeout: Number(timeout.value) || 20, max_tokens: Number(maxTokens.value) || 600 } });
        verifyOut.className = 'ai-verify-result ok';
        verifyOut.replaceChildren(icon('check'), el('span', {}, `Terhubung. Model ${result.model} merespons: "${result.preview}"`));
      } catch (error) {
        verifyOut.className = 'ai-verify-result fail';
        verifyOut.replaceChildren(icon('incident'), el('span', {}, error.message));
      } finally { verifyBtn.disabled = false; }
    });
    const submit = button('Simpan pengaturan', 'check', null, 'primary', { type: 'submit' });
    const form = el('form', { class: 'ai-settings-form' },
      el('div', { class: 'scope-explanation' }, icon('shield'), el('div', {}, el('strong', {}, 'Fitur tambahan — aplikasi berjalan penuh tanpa ini'), el('p', {}, 'Asisten hanya membaca data operasional dan menulis ringkasan. Tidak pernah mengeksekusi otomasi atau mengubah status insiden.'))),
      el('label', { class: 'checkbox-label ai-enabled-row' }, enabled, el('span', {}, el('strong', {}, 'Aktifkan asisten AI'), el('small', {}, 'Hanya operator dan admin yang dapat meminta analisis insiden.'))),
      providerInfo,
      field('Base URL', baseUrl, 'Harus http(s), tanpa kredensial di URL. Contoh: https://api.example.com/v1'),
      field('Kunci API', apiKeyWrap),
      el('div', { class: 'form-grid' }, field('Model ID', modelId, 'Nama model sesuai penyedia, misal qwen3.8-max atau deepseek-chat.'), el('div', { class: 'form-field' }, el('label', {}, 'Model dari penyedia'), modelsButton)), modelList,
      el('div', { class: 'form-grid' }, field('Batas waktu (detik)', timeout), field('Batas token keluaran', maxTokens)),
      el('div', { class: 'form-footer split' }, el('div', {}, verifyBtn), el('div', { class: 'form-footer-right' }, button('Batal', null, closeModal), submit)),
      verifyOut, formError);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (submit.disabled) return;
      submit.disabled = true; formError.hidden = true;
      try {
        const saved = await api('/api/ai/settings', { method: 'POST', body: { enabled: enabled.checked, base_url: baseUrl.value.trim(), model: modelId.value.trim(), api_key: apiKey.value, timeout: Number(timeout.value) || 20, max_tokens: Number(maxTokens.value) || 600 } });
        toast(saved.enabled ? `Asisten AI aktif (${saved.model}).` : 'Asisten AI dinonaktifkan.');
        closeModal();
      } catch (error) { formError.replaceChildren(errorBox(error)); formError.hidden = false; }
      finally { submit.disabled = false; }
    });
    $('#dialog-body').replaceChildren(form);
    if (!current.has_key) apiKey.focus();
  }
  async function askAssistant() {
    if (!canWrite()) return;
    const version = openModal('Tanya asisten', 'AI · BACA SAJA', true, 'assistant');
    const output = el('div', { class: 'ai-summary preserve-lines' }, 'Tanyakan kondisi perangkat, insiden aktif, atau riwayat otomasi pada lingkungan yang sedang dipilih.');
    const question = el('textarea', { rows: 4, maxlength: 1000, placeholder: 'Contoh: Perangkat mana yang perlu saya periksa terlebih dahulu?' });
    const submit = button('Tanyakan', 'bolt', null, 'primary', { type: 'submit' });
    const insight = (label, route, key) => button(label, 'bolt', async () => {
      output.textContent = 'Asisten sedang membaca data operasional…';
      try {
        const result = await api(`${route}?${query({ environment: state.environment })}`, { method: 'POST', body: {} });
        if (modalCurrent(version)) output.replaceChildren(el('div', { class: 'section-heading' }, el('strong', {}, label), el('span', { class: 'ai-source' }, icon('bolt'), result.model || 'AI')), el('div', { class: 'preserve-lines' }, result[key]));
      } catch (error) { if (modalCurrent(version)) output.replaceChildren(errorBox(error)); }
    }, 'secondary');
    const form = el('form', {}, el('div', { class: 'ai-provider-note' }, icon('shield'), el('span', {}, `Lingkungan aktif: ${state.environment === 'real' ? 'REAL · data aktual' : 'DEMO · data sintetis'}. Jawaban hanya memakai data lingkungan ini dan tidak menjalankan tindakan apa pun.`)), output, el('div', { class: 'form-footer' }, insight('Prioritaskan insiden', '/api/ai/triage', 'triage'), insight('Buat handover', '/api/ai/handover', 'handover')), field('Pertanyaan', question), el('div', { class: 'form-footer' }, button('Tutup', null, closeModal), submit));
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (!question.value.trim() || submit.disabled) return;
      submit.disabled = true; output.textContent = 'Asisten sedang membaca data operasional…';
      try {
        const result = await api(`/api/ai/ask?${query({ environment: state.environment })}`, { method: 'POST', body: { question: question.value.trim() } });
        if (modalCurrent(version)) output.replaceChildren(el('div', { class: 'section-heading' }, el('strong', {}, 'Jawaban asisten'), el('span', { class: 'ai-source' }, icon('bolt'), result.model || 'AI')), el('div', { class: 'preserve-lines' }, result.answer));
      } catch (error) { if (modalCurrent(version)) output.replaceChildren(errorBox(error)); }
      finally { submit.disabled = false; }
    });
    $('#dialog-body').replaceChildren(form); question.focus();
  }

  function changePassword() {
    closeProfile();
    openModal('Ubah kata sandi', 'KEAMANAN AKUN');    const current = el('input', { type: 'password', autocomplete: 'current-password', required: true });
    const password = el('input', { type: 'password', autocomplete: 'new-password', required: true, minlength: 12 });
    const repeat = el('input', { type: 'password', autocomplete: 'new-password', required: true, minlength: 12 });
    const error = el('div', { hidden: true, role: 'alert' });
    const submit = button('Simpan kata sandi', 'key', null, 'primary', { type: 'submit' });
    const form = el('form', {}, el('p', { class: 'muted' }, 'Gunakan kata sandi unik untuk melindungi ruang operasi Anda.'), field('Kata sandi saat ini', current), field('Kata sandi baru', password, 'Gunakan setidaknya 12 karakter.'), field('Ulangi kata sandi baru', repeat), error, el('div', { class: 'form-footer' }, button('Batal', null, closeModal), submit));
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (submit.disabled) return;
      if (password.value !== repeat.value) { error.replaceChildren(errorBox(new Error('Kata sandi baru belum sama.'))); error.hidden = false; repeat.focus(); return; }
      submit.disabled = true; error.hidden = true;
      try {
        const response = await api('/api/password', { method: 'POST', body: { current_password: current.value, new_password: password.value } });
        if (response.csrf_token) state.csrf = response.csrf_token;
        current.value = ''; password.value = ''; repeat.value = '';
        closeModal(); toast('Kata sandi berhasil diperbarui.');
      } catch (err) { error.replaceChildren(errorBox(err)); error.hidden = false; }
      finally { submit.disabled = false; }
    });
    $('#dialog-body').replaceChildren(form);
    current.focus();
  }
  function closeProfile() { $('#profile-menu').hidden = true; $('#profile-toggle').setAttribute('aria-expanded', 'false'); }
  function closeSidebar() {
    $('#sidebar').classList.remove('open');
    $('#sidebar-backdrop').hidden = true;
    $('#open-sidebar').setAttribute('aria-expanded', 'false');
    document.body.classList.remove('drawer-open');
    $('#sidebar').removeAttribute('aria-modal');
    $('#sidebar').removeAttribute('role');
  }
  function openSidebar() {
    $('#sidebar').classList.add('open');
    $('#sidebar-backdrop').hidden = false;
    $('#open-sidebar').setAttribute('aria-expanded', 'true');
    $('#sidebar').setAttribute('role', 'dialog');
    $('#sidebar').setAttribute('aria-modal', 'true');
    document.body.classList.add('drawer-open');
    $('#close-sidebar').focus();
  }
  function bindEvents() {
    $$('[data-icon]').forEach(node => node.replaceChildren(icon(node.dataset.icon)));
    $$('#main-nav a').forEach(link => link.addEventListener('click', event => { event.preventDefault(); navigate(link.dataset.page); }));
    $('.sidebar .brand').addEventListener('click', event => { event.preventDefault(); navigate('overview'); });
    window.addEventListener('hashchange', () => { if (pageMeta[location.hash.slice(1)]) navigate(location.hash.slice(1)); });
    $$('[data-env]').forEach(node => node.addEventListener('click', () => {
      if (state.environment === node.dataset.env) return;
      state.environment = node.dataset.env;
      state.lastUpdated = null;
      state.filters.search = '';
      savePreference('environment', state.environment);
      $('#nav-incident-count').hidden = true;
      navigate(state.page);
    }));
    $('#open-sidebar').addEventListener('click', openSidebar);
    $('#close-sidebar').addEventListener('click', closeSidebar);
    $('#sidebar-backdrop').addEventListener('click', closeSidebar);
    $('#dialog-close').addEventListener('click', closeModal);
    $('#detail-dialog').addEventListener('cancel', event => { event.preventDefault(); closeModal(); });
    $('#profile-toggle').addEventListener('click', () => { const open = $('#profile-menu').hidden; $('#profile-menu').hidden = !open; $('#profile-toggle').setAttribute('aria-expanded', String(open)); if (open) $('#change-password').focus(); });
    $('#change-password').addEventListener('click', changePassword);
    $('#ai-settings').addEventListener('click', aiSettings);
    $('#assistant-toggle').addEventListener('click', askAssistant);
    document.addEventListener('click', event => { if (!event.target.closest('.profile-wrap')) closeProfile(); });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        if (!$('#profile-menu').hidden) { closeProfile(); $('#profile-toggle').focus(); }
        if ($('#sidebar').classList.contains('open')) { closeSidebar(); $('#open-sidebar').focus(); }
      }
      if (event.key === 'Tab' && $('#sidebar').classList.contains('open')) {
        const focusable = $$('a, button', $('#sidebar')).filter(node => node.getClientRects().length);
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (event.shiftKey && (document.activeElement === first || !$('#sidebar').contains(document.activeElement))) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    });
    window.matchMedia('(min-width: 1025px)').addEventListener('change', event => { if (event.matches) closeSidebar(); });
    $('#logout').addEventListener('click', () => {
      closeProfile();
      confirmAction({ title: 'Keluar dari ruang operasi?', description: 'Sesi akun pada browser ini akan diakhiri. Pekerjaan yang sudah masuk antrean tetap diproses oleh worker.', label: 'Keluar', submit: async () => { await api('/api/logout', { method: 'POST', body: {} }); showLogin(); } });
    });
    $('#login-form').addEventListener('submit', async event => {
      event.preventDefault();
      const submit = $('#login-submit');
      if (submit.disabled) return;
      submit.disabled = true; submit.textContent = 'Menghubungkan…'; $('#login-error').hidden = true;
      try {
        const session = await api('/api/login', { method: 'POST', body: { username: $('#username').value.trim(), password: $('#password').value } });
        await startSession(session);
      } catch (error) { $('#login-error').textContent = error.message; $('#login-error').hidden = false; }
      finally { submit.disabled = false; submit.textContent = 'Masuk ke JalaTantra →'; }
    });
    document.addEventListener('visibilitychange', () => { if (!document.hidden && state.user) loadPage(true); });
    setInterval(() => loadPage(true), 12000);
  }
  async function init() {
    bindEvents();
    try { await startSession(await api('/api/session')); }
    catch (error) { showLogin(); if (error.status !== 401) { $('#login-error').textContent = error.message; $('#login-error').hidden = false; } }
  }
  init();
})();
