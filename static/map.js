/* ================= صفحه نقشه شبکه =================
   لایه پایه: Leaflet + تایل‌های TMS شهرداری مشهد (سرویس پایه‌ی کاربر).
   لایه‌های روی آن: مسیرهای خطوط (polyline) و ایستگاه‌ها (circleMarker).
   - اتوبوس: ایستگاه‌های واقعی از /api/stations (وب‌سرویس stations.json).
   - مترو/BRT/دوچرخه: داده نمونه از /api/network (در گام‌های بعد واقعی می‌شود).
*/
(function () {
  if (!window.RA_DATA || window.RA_DATA.page !== "map") return;

  const FA = "۰۱۲۳۴۵۶۷۸۹";
  const fa = (v) => String(v).replace(/\d/g, (d) => FA[d]);
  const icons = () => { if (window.lucide) lucide.createIcons(); };

  const MODE_LABEL = { bus: "اتوبوس", brt: "BRT", metro: "مترو", bike: "دوچرخه" };
  const MODE_COLOR = { bus: "#4f9159", metro: "#b08b25", brt: "#c14f4b", bike: "#8a63a8" };

  const CENTER = [36.329616, 59.56543];
  const DEFAULT_ZOOM = 12;
  // محدوده‌ی تقریبی مشهد — فقط برای محافظت از fitBounds در برابر مختصات نامعتبر.
  const MASHHAD_BBOX = { latMin: 35.5, latMax: 37.0, lngMin: 59.0, lngMax: 60.2 };
  const TILE_URL =
    "https://basemap.mashhad.ir/geoserver/gwc/service/tms/1.0.0/MashhadBaseMap1401@EPSG:900913@png/{z}/{x}/{y}.png";

  let map = null;
  let stationLayer = null;
  let routeLayer = null;
  let busLayer = null; // لایه‌ی کلاستر ایستگاه‌های اتوبوس (MarkerCluster)
  let network = null; // {stations, lines} — داده نمونه مترو/BRT/دوچرخه
  let busStations = null; // کش ایستگاه‌های واقعی اتوبوس از /api/stations
  let renderToken = 0; // جلوگیری از تداخل رندرهای ناهمگام
  const state = { mode: null, lines: [] };

  /* ---------- راه‌اندازی نقشه ---------- */
  function initMap() {
    // zoomControl: false → دکمه‌های زوم را خودمان در پایین صفحه قرار می‌دهیم.
    map = L.map("mapCanvas", { zoomControl: false, attributionControl: true }).setView(CENTER, DEFAULT_ZOOM);
    L.tileLayer(TILE_URL, {
      minZoom: 7,
      maxZoom: 20,
      tms: true,
      attribution: "Mashhad Map",
    }).addTo(map);
    L.control.zoom({ position: "bottomright" }).addTo(map);
    stationLayer = L.layerGroup().addTo(map);
    routeLayer = L.layerGroup().addTo(map);
    // لایه‌ی کلاستر برای ایستگاه‌های اتوبوس: در زوم‌های پایین تجمیع می‌شود و
    // با زوم داخل، ایستگاه‌های بیشتری نمایان می‌شوند.
    busLayer = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 55,
      disableClusteringAtZoom: 16,
      iconCreateFunction: busClusterIcon,
    }).addTo(map);
    // اطمینان از اندازه‌گیری درست اندازه بوم پس از چیدمان
    setTimeout(() => map.invalidateSize(), 120);
  }

  /* ---------- دریافت داده شبکه نمونه ---------- */
  async function loadNetwork() {
    try {
      const r = await fetch("/api/network");
      if (!r.ok) throw new Error("network http " + r.status);
      network = await r.json();
    } catch (e) {
      toast("دریافت داده شبکه ناموفق بود", "alert-triangle");
      return;
    }
    renderAll();
  }

  /* ---------- ایستگاه‌های اتوبوس (وب‌سرویس واقعی) ---------- */
  async function loadBusStations() {
    try {
      const r = await fetch("/api/stations");
      if (!r.ok) throw new Error("stations http " + r.status);
      const data = await r.json();
      const list = Array.isArray(data) ? data : (data.stations || []);
      return list.filter(
        (s) =>
          typeof s.lat === "number" && typeof s.lng === "number" &&
          Number.isFinite(s.lat) && Number.isFinite(s.lng) &&
          s.lat >= -90 && s.lat <= 90 && s.lng >= -180 && s.lng <= 180
      );
    } catch (e) {
      toast("دریافت ایستگاه‌های اتوبوس ناموفق بود", "alert-triangle");
      return [];
    }
  }

  function busClusterIcon(cluster) {
    const n = cluster.getChildCount();
    const size = n < 10 ? "sm" : n < 100 ? "md" : "lg";
    const dim = n < 10 ? 30 : n < 100 ? 38 : 46;
    return L.divIcon({
      html: `<span>${fa(n)}</span>`,
      className: `bus-cluster bus-cluster-${size}`,
      iconSize: [dim, dim],
      iconAnchor: [dim / 2, dim / 2],
    });
  }

  // آیکن تک‌ایستگاه اتوبوس: نقطه‌ی سبز با حلقه‌ی سفید (با divIcon) —
  // باید L.marker باشد تا توسط MarkerCluster تجمیع شود (circleMarker کلاستر نمی‌شود).
  function busStationIcon() {
    return L.divIcon({
      className: "bus-station-icon",
      html: "",
      iconSize: [14, 14],
      iconAnchor: [7, 7],
      popupAnchor: [0, -8],
    });
  }

  // فرار از کاراکترهای HTML برای تزریق امن مقادیر سرور به innerHTML.
  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/"/g, "&quot;")
    .replace(/</g, "&lt;").replace(/>/g, "&gt;");

  /* ---------- Bottom Sheet اطلاعات ایستگاه ----------
     با کلیک روی هر ایستگاه اتوبوس، یک Sheet از پایین صفحه باز می‌شود و
     اطلاعات ایستگاه (نام + شماره/کد)، خطوط عبوری و زمان تقریبی رسیدن اتوبوس را
     از /api/station/<id>/details می‌گیرد و نمایش می‌دهد.
     - در حالت بارگذاری: spinner + پیام.
     - در حالت خطا: پیام + دکمه‌ی تلاش دوباره.
     - داده‌ها فقط از وب‌سرویس واقعی می‌آیند (بدون داده‌ی نمایشی).
  */
  let sheetToken = 0; // جلوگیری از تداخل درخواست‌های ناهمگام هنگام کلیک سریع روی ایستگاه‌های مختلف

  function openStationSheet(st) {
    const sn = st.id;
    const name = st.name || "ایستگاه اتوبوس";
    const codeTxt = sn != null && sn !== "" ? fa(sn) : "";

    sheetToken++;
    const myToken = sheetToken;

    openSheet(`
      <div class="sh-h"></div>
      <div class="st-head">
        <h3>${esc(name)}</h3>
        ${codeTxt ? `<p>کد ${codeTxt}</p>` : ""}
      </div>
      <div id="stationSheetBody">
        <div class="spin"></div>
        <div class="load-tx">دریافت خطوط عبوری و زمان‌بندی…</div>
      </div>
      <div style="height:12px"></div>
    `);
    icons();

    const url = `/api/station/${encodeURIComponent(sn)}/details`;
    fetchStationDetails(url, myToken, st);
  }

  function fetchStationDetails(url, myToken, st) {
    fetch(url)
      .then((r) => r.json().then((d) => ({ ok: r.ok, data: d })))
      .then(({ ok, data }) => {
        if (myToken !== sheetToken) return; // Sheet جدیدتری باز شده — نتیجه‌ی قدیمی را دور بریز
        if (ok) { renderStationSheetBody(data); return; }
        const err = (data && data.error) || "http";
        const detail = (data && data.detail) || "";
        if (err === "no_credentials") {
          renderSheetError(st, myToken, { msg: "اعتبار وب‌سرویس در فایل .env تنظیم نشده است." });
        } else if (err === "upstream_unreachable") {
          renderSheetError(st, myToken, {
            msg: "سرویس ETA در دسترس نیست یا داده‌ای برنگرداند.",
            detail,
          });
        } else {
          renderSheetError(st, myToken, { msg: "دریافت اطلاعات ایستگاه ناموفق بود.", detail });
        }
      })
      .catch(() => renderSheetError(st, myToken, { msg: "دریافت اطلاعات ایستگاه ناموفق بود." }));
  }

  // نمایش خطا در Sheet. info = {msg, detail?}. detail (کوتاه) کم‌رنگ نشان داده
  // می‌شود تا علت واقعی (کد HTTP / نوع خطا / wrapper) دیده شود.
  function renderSheetError(st, myToken, info) {
    if (myToken !== sheetToken) return;
    const body = document.getElementById("stationSheetBody");
    if (!body) return;
    const msg = (info && info.msg) || "دریافت اطلاعات ایستگاه ناموفق بود.";
    const detail = (info && info.detail) ? String(info.detail).slice(0, 160) : "";
    const detailHtml = detail
      ? `<div class="load-tx" style="margin-top:6px;color:var(--ink-soft);font-size:11px;word-break:break-word">${esc(detail)}</div>`
      : "";
    body.innerHTML = `
      <div class="load-tx" style="color:#c14f4b">${msg}</div>
      ${detailHtml}
      <div style="height:14px"></div>
      <button class="ghost" id="sheetRetry"><i data-lucide="refresh-cw"></i> تلاش دوباره</button>`;
    icons();
    const rb = document.getElementById("sheetRetry");
    if (rb) rb.onclick = () => openStationSheet(st);
  }

  function renderStationSheetBody(data) {
    const body = document.getElementById("stationSheetBody");
    if (!body) return;
    const lines = Array.isArray(data.lines) ? data.lines : [];
    const eta = Array.isArray(data.eta) ? data.eta : [];

    // خطوط عبوری — چیپ‌های شماره‌ی خط (با عنوان در tooltip)
    const linesHtml = lines.length
      ? `<div class="chips">${lines.map((ln) => {
          const sub = ln.from && ln.to ? `${ln.from} ← ${ln.to}` : (ln.to || ln.from || "");
          return `<span class="lchip" style="--c:#4f9159"${sub ? ` title="${esc(sub)}"` : ""}>${fa(ln.num || "—")}</span>`;
        }).join("")}</div>`
      : `<div class="load-tx">خط عبوری ثبت نشده است.</div>`;

    // بُرد زمان رسیدن اتوبوس — هر ردیف: واحدِ زمان (چیپِ دقیقه + واژه‌ی «دقیقه») | خط | مقصد.
    // عددِ دقیقه داخل .lchip است و واژه‌ی «دقیقه» کنارش (بیرون چیپ). وقتی ETA نبود
    // (ETA_Time="-") چیپ «—» نشان می‌دهد و واژه‌ی «دقیقه» نمایش داده نمی‌شود.
    const etaHtml = eta.length
      ? `<div class="board">${eta.map((e) => {
          const dest = e.dest ? `به ${esc(e.dest)}` : "زمان رسیدن اتوبوس";
          const minTxt = e.minutes != null
            ? (e.minutes <= 0 ? "الان" : fa(e.minutes))
            : (e.time && e.time !== "-" ? fa(e.time) : "—");
          const minLbl = (e.minutes != null && e.minutes > 0) ? `<span class="min-lbl">دقیقه</span>` : "";
          return `<div class="dep">
            <div class="dep-time"><span class="lchip" style="--c:#4f9159">${minTxt}</span>${minLbl}</div>
            <div class="dep-mid"><b>خط ${e.num ? fa(e.num) : ""}</b><span>${dest}</span></div>
          </div>`;
        }).join("")}</div>`
      : `<div class="load-tx">زمان‌بندی فعالی موجود نیست.</div>`;

    body.innerHTML = `
      <div class="sh-sec">خطوط عبوری</div>
      ${linesHtml}
      <div class="sh-sec">زمان رسیدن اتوبوس</div>
      ${etaHtml}`;
    icons();
  }

  async function renderBusStations(tok) {
    if (!busStations) busStations = await loadBusStations();
    if (tok !== renderToken) return; // یک رندر جدیدتر شروع شده — از قدم زدن جلوگیری کن
    if (!busStations.length) {
      map.setView(CENTER, DEFAULT_ZOOM);
      return;
    }
    const ll = [];
    const inMashhad = [];
    busStations.forEach((st) => {
      // L.marker (با divIcon) تا توسط MarkerCluster تجمیع شود؛
      // circleMarker توسط این پلاگین کلاستر نمی‌شود.
      L.marker([st.lat, st.lng], { icon: busStationIcon() })
        .addTo(busLayer)
        .on("click", () => openStationSheet(st));
      ll.push([st.lat, st.lng]);
      if (
        st.lat >= MASHHAD_BBOX.latMin && st.lat <= MASHHAD_BBOX.latMax &&
        st.lng >= MASHHAD_BBOX.lngMin && st.lng <= MASHHAD_BBOX.lngMax
      ) {
        inMashhad.push([st.lat, st.lng]);
      }
    });
    // در ورود به حالت اتوبوس، دید نقشه را به همه‌ی ایستگاه‌ها fit نکن (جلوگیری از
    // زوم‌اوت و شلوغی). اگر هیچ ایستگاه معتبری در مشهد نبود، به مرکز مشهد برگرد؛
    // وگرنه روی نمای فعلی بمان تا کاربر با زوم داخل، ایستگاه‌های هر منطقه را ببیند
    // و کلاسترها تراکم را مدیریت کنند.
    if (!inMashhad.length) {
      toast("مختصات ایستگاه‌ها خارج از محدوده‌ی مشهد است", "alert-triangle");
      map.setView(CENTER, DEFAULT_ZOOM);
      return;
    }
    const c = map.getCenter();
    const inside =
      c.lat >= MASHHAD_BBOX.latMin && c.lat <= MASHHAD_BBOX.latMax &&
      c.lng >= MASHHAD_BBOX.lngMin && c.lng <= MASHHAD_BBOX.lngMax;
    if (!inside) map.setView(CENTER, DEFAULT_ZOOM);
  }

  /* ---------- تعیین خطوط قابل نمایش (نمونه) ---------- */
  function linesToShow() {
    if (!network) return [];
    if (state.lines.length) return state.lines.slice();
    if (state.mode) {
      return Object.keys(network.lines).filter((lid) => network.lines[lid].type === state.mode);
    }
    return [];
  }

  /* ---------- پاپ‌آپ ایستگاه نمونه ---------- */
  function popupHTML(sid) {
    const st = network.stations[sid];
    const chips = st.lines
      .map((lid) => {
        const ln = network.lines[lid];
        return `<span class="lchip" style="--c:${ln.color}">${fa(ln.num)}</span>`;
      })
      .join("");
    return `<div style="min-width:190px">
      <strong style="font-size:15px;display:block;margin-bottom:2px">${st.n}</strong>
      <span style="font-size:11px;color:#7b8aa3;font-weight:600;display:block;margin-bottom:8px">کد ${fa(st.code)}${st.dock ? " · دوک دوچرخه" : ""}</span>
      ${st.addr ? `<div style="font-size:11px;color:#7b8aa3;line-height:1.7;margin-bottom:8px">${st.addr}</div>` : ""}
      <div style="font-size:11px;font-weight:800;color:#7b8aa3;margin-bottom:6px">خطوط عبوری</div>
      <div class="chips" style="gap:6px">${chips}</div>
    </div>`;
  }

  /* ---------- رندر کامل لایه‌ها ---------- */
  function renderAll() {
    if (!map) return;
    const tok = ++renderToken;
    stationLayer.clearLayers();
    routeLayer.clearLayers();
    busLayer.clearLayers();
    renderLineChips();
    syncToolbar();

    // حالت اتوبوس: ایستگاه‌های واقعی از وب‌سرویس (بدون مسیر خط)
    if (state.mode === "bus") {
      renderBusStations(tok);
      return;
    }

    if (!network) {
      map.setView(CENTER, DEFAULT_ZOOM);
      return;
    }

    const lids = linesToShow();
    const shown = new Set();

    // مسیرهای خطوط
    lids.forEach((lid) => {
      const ln = network.lines[lid];
      const pts = ln.stops.map((sid) => [network.stations[sid].lat, network.stations[sid].lng]);
      if (pts.length > 1) {
        L.polyline(pts, { color: ln.color, weight: 4, opacity: 0.85 }).addTo(routeLayer);
      }
      ln.stops.forEach((s) => shown.add(s));
    });

    // حالت دوچرخه بدون خط انتخابی → فقط ایستگاه‌های دارای دوک
    if (state.mode === "bike" && !state.lines.length) {
      Object.keys(network.stations).forEach((sid) => {
        if (network.stations[sid].dock) shown.add(sid);
      });
    }

    const color = state.mode ? MODE_COLOR[state.mode] : "#7b8aa3";

    // ایستگاه‌ها
    shown.forEach((sid) => {
      const st = network.stations[sid];
      L.circleMarker([st.lat, st.lng], {
        radius: 6,
        color: color,
        weight: 2,
        fillColor: "#fff",
        fillOpacity: 1,
      })
        .addTo(stationLayer)
        .bindPopup(popupHTML(sid), { maxWidth: 260 });
    });

    // تنظیم دید نقشه روی ایستگاه‌های نمایش‌داده‌شده
    if (shown.size) {
      const ll = [...shown].map((sid) => [network.stations[sid].lat, network.stations[sid].lng]);
      map.fitBounds(L.latLngBounds(ll).pad(0.25));
    } else {
      map.setView(CENTER, DEFAULT_ZOOM);
    }
  }

  /* ---------- نوار خطوط انتخاب‌شده ---------- */
  function renderLineChips() {
    const bar = document.getElementById("mapSelectedLines");
    if (!bar) return;
    if (!network || !state.lines.length) {
      bar.innerHTML = "";
      return;
    }
    bar.innerHTML = state.lines
      .map((lid) => {
        const ln = network.lines[lid];
        if (!ln) return "";
        return `<div class="map-line-chip" data-lid="${lid}"><span>${ln.title}</span><i data-lucide="x"></i></div>`;
      })
      .join("");
    icons();
    bar.querySelectorAll(".map-line-chip").forEach((chip) => {
      chip.onclick = () => {
        state.lines = state.lines.filter((id) => id !== chip.dataset.lid);
        renderAll();
      };
    });
  }

  function syncToolbar() {
    document.querySelectorAll(".map-mode").forEach((btn) => {
      btn.classList.toggle("on", btn.dataset.mode === state.mode);
    });
  }

  /* ---------- نوارابزار و sheet انتخاب خط ---------- */
  function bindToolbar() {
    document.querySelectorAll(".map-mode").forEach((btn) => {
      btn.onclick = () => {
        const mode = btn.dataset.mode;
        state.mode = state.mode === mode ? null : mode;
        state.lines = [];
        renderAll();
      };
    });

    const addBtn = document.getElementById("mapAddLine");
    if (addBtn) {
      addBtn.onclick = () => {
        if (!state.mode) {
          document.querySelectorAll(".map-mode").forEach((el) => {
            el.classList.add("shake");
            setTimeout(() => el.classList.remove("shake"), 500);
          });
          toast("ابتدا نوع حمل‌ونقل را انتخاب کنید", "alert-triangle");
          return;
        }
        openLineSheet();
      };
    }

    const back = document.getElementById("mapBackBtn");
    if (back) back.onclick = () => go("home");
  }

  function openLineSheet() {
    // اتوبوس: فعلاً فقط ایستگاه‌ها نمایش داده می‌شوند؛ داده‌ی خطوط واقعی هنوز نیست
    if (state.mode === "bus") {
      toast("انتخاب خط اتوبوس در گام‌های بعد فعال می‌شود", "info");
      return;
    }
    if (!network) return;
    const available = Object.keys(network.lines).filter((lid) => network.lines[lid].type === state.mode);
    const listHtml = available
      .map((lid) => {
        const ln = network.lines[lid];
        const on = state.lines.includes(lid);
        return `<div class="sheet-toggle-row" data-lid="${lid}">
          <div><b>${ln.title}</b><span>از ${ln.from} به ${ln.to}</span></div>
          <div class="sheet-toggle ${on ? "on" : ""}"></div>
        </div>`;
      })
      .join("");

    openSheet(
      `<div class="sh-h"></div>
       <h3 class="sh-t">انتخاب خطوط ${MODE_LABEL[state.mode]}</h3>
       <div id="lineToggleList">${listHtml}</div>
       <div style="height:20px"></div>
       <button class="ghost" id="closeLineSheet"><i data-lucide="check"></i> تایید و بستن</button>`
    );
    icons();

    document.querySelectorAll("#lineToggleList .sheet-toggle-row").forEach((row) => {
      row.onclick = () => {
        const lid = row.dataset.lid;
        row.querySelector(".sheet-toggle").classList.toggle("on");
        if (state.lines.includes(lid)) state.lines = state.lines.filter((id) => id !== lid);
        else state.lines.push(lid);
        renderAll();
      };
    });

    const closeBtn = document.getElementById("closeLineSheet");
    if (closeBtn) closeBtn.onclick = closeSheet;
  }

  /* ---------- شروع ---------- */
  initMap();
  bindToolbar();
  loadNetwork();
  icons();
})();