/* ================= ابزارها ================= */
const $ = s => document.querySelector(s);
const FA = '۰۱۲۳۴۵۶۷۸۹';
const fa = v => String(v).replace(/\d/g, d => FA[d]);
const faMoney = n => fa(Math.round(n).toLocaleString('en-US')).replace(/,/g, '٬');
const faTime = m => {
  m = Math.round(((m % 1440) + 1440) % 1440);
  return fa(String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'));
};
const icons = () => { if (window.lucide) lucide.createIcons(); };

/* داده‌های تزریق‌شده از سمت سرور (در گام‌های بعد از وب‌سرویس) */
const DATA = window.RA_DATA || {};
const NOTICES = DATA.notices || [];

/* ================= toast ================= */
let toastT = null;
function toast(msg, icon = 'check') {
  const h = $('#toastHost');
  if (!h) return;
  h.innerHTML = `<div class="toast"><i data-lucide="${icon}"></i><span>${msg}</span></div>`;
  icons();
  clearTimeout(toastT);
  toastT = setTimeout(() => { h.innerHTML = ''; }, 2600);
}

/* ================= sheet (پایین‌صفحه‌ای) ================= */
function openSheet(html) {
  const host = $('#sheetHost');
  if (!host) return;
  host.innerHTML = `<div class="sh-back"></div><div class="sheet">${html}</div>`;
  host.classList.add('on');
  requestAnimationFrame(() => host.classList.add('in'));
  icons();
  const back = host.querySelector('.sh-back');
  if (back) back.onclick = closeSheet;
}
function closeSheet() {
  const host = $('#sheetHost');
  if (!host || !host.classList.contains('on')) return;
  host.classList.remove('in');
  setTimeout(() => { host.classList.remove('on'); host.innerHTML = ''; }, 280);
}

/* ================= نوار اعلان‌ها (ticker) ================= */
let tkI = null, tkIdx = 0;
function startTicker() {
  stopTicker();
  if (NOTICES.length < 2) return;
  tkI = setInterval(() => {
    tkIdx = (tkIdx + 1) % NOTICES.length;
    const el = $('#tick');
    if (!el) return;
    el.classList.remove('tk-anim');
    void el.offsetWidth;
    el.textContent = NOTICES[tkIdx];
    el.classList.add('tk-anim');
  }, 4200);
}
function stopTicker() {
  clearInterval(tkI);
  tkI = null;
}

/* ================= dock ================= */
function setDock(p) {
  document.querySelectorAll('#dock button').forEach(b => {
    b.classList.toggle('on', b.dataset.dock === p);
  });
}

/* ================= ناوبری =================
   صفحات ساخته‌شده به مسیر واقعی Flask هدایت می‌شوند؛
   بقیه فعلاً پیام «در گام‌های بعد» می‌دهند. */
const ROUTES = {
  home: '/',
  map: '/map',
};
const COMING_SOON = {
  bus: 'مسیریاب اتوبوس',
  combo: 'مسیریاب ترکیبی',
  qr: 'اسکن ایستگاه',
};
function go(page) {
  if (ROUTES[page]) { window.location.href = ROUTES[page]; return; }
  const label = COMING_SOON[page];
  if (label) toast('این بخش در گام‌های بعد ساخته می‌شود', 'info');
}

/* رویدادهای سراسری */
document.addEventListener('click', e => {
  const g = e.target.closest('[data-go]');
  if (g) { go(g.dataset.go); return; }
});
document.querySelectorAll('#dock button').forEach(b => {
  b.onclick = () => go(b.dataset.dock);
});

/* ================= ساعت و تاریخ ================= */
function clockTick() {
  const d = new Date();
  const cEl = $('#clock');
  if (cEl) cEl.textContent = fa(String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'));
  const dEl = $('#date');
  if (dEl) {
    try {
      dEl.textContent = new Intl.DateTimeFormat('fa-IR', { day: 'numeric', month: 'long' }).format(d);
    } catch (e) {
      dEl.textContent = '';
    }
  }
}

/* ================= شروع — فقط در صفحه خانه ================= */
icons();
if (DATA.page === 'home') {
  setDock('home');
  clockTick();
  setInterval(clockTick, 1000);
  startTicker();
}
