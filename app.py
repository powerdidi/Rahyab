"""ره‌یاب مشهد — برنامه حمل‌ونقل عمومی
گام‌ها:
  ۱) صفحه منو (خانه / Bento Grid)
  ۲) صفحه نقشه شبکه (Leaflet + تایل‌های مشهد)

معماری:
- Flask به‌عنوان بک‌اند سبک برای سرو UI و وب‌سرویس.
- قالب‌ها در templates/ ، فایل‌های ایستا (css/js) در static/ .
- داده‌ها از مسیرهای Flask به قالب تزریق می‌شوند؛ در گام‌های بعد
  از وب‌سرویس واقعی دریافت می‌شوند.
"""
from flask import Flask, render_template, jsonify, request
import json
import math
import os
import requests
import sys
from dotenv import load_dotenv

import network_data

# بارگذاری فایل .env کنار app.py (یک منبع واحد برای اعتبار وب‌سرویس و سایر
# پیکربندی‌ها). مقادیر موجود در .env در os.environ قرار می‌گیرند و در ادامه
# توسط os.environ.get خوانده می‌شوند.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

app = Flask(__name__)


# داده‌های نمونه صفحه خانه (نوار اعلان‌ها).
# NOTE: فعلاً هاردکد شده‌اند؛ در گام‌های بعد از وب‌سرویس دریافت می‌شوند.
SAMPLE_NOTICES = [
    "خط ۱۱۰ از شنبه با سرفاصله ۱۵ دقیقه در ساعات اوج حرکت می‌کند.",
    "دوک دوچرخه میدان شهدا با ۳۰ دوچرخه جدید تکمیل شد.",
    "BRT خط ۲: توقف موقت در ضلع میدان فردوسی به دلیل بازسازی بزرگراه.",
]


@app.route("/")
def home():
    """صفحه منو / خانه."""
    return render_template("home.html", notices=SAMPLE_NOTICES)


@app.route("/map")
def map_page():
    """صفحه نقشه شبکه."""
    return render_template("map.html")


@app.route("/api/network")
def api_network():
    """داده شبکه (ایستگاه‌ها و خطوط) برای صفحه نقشه.

    NOTE: فعلاً از داده نمونه می‌آید؛ در گام‌های بعد این مسیر به وب‌سرویس
    واقعی وصل می‌شود.
    """
    return jsonify(network_data.network_json())


# آدرس سرویس لیست ایستگاه‌های اتوبوس شهرداری مشهد.
STATIONS_URL = "https://rtpisservice.mashhad.ir/shahreman-temp-api/stations.json"

# نشست requests سراسری با نادیده‌گرفتن تنظیمات پروکسی محیطی
# (HTTP_PROXY / HTTPS_PROXY / NO_PROXY و .netrc). در محیط‌هایی که پروکسی
# تنظیم شده اما به میزبان‌های وب‌سرویس نمی‌رسد، اتصال مستقیم برقرار می‌شود.
_session = requests.Session()
_session.trust_env = False

# مسیر کش محلی ایستگاه‌ها. داده‌ی ایستگاه‌ها ثابت است و در چند صفحه استفاده
# می‌شود؛ بنابراین یک‌بار از سایت خوانده و در این فایل ذخیره می‌شود و سپس همه‌ی
# درخواست‌ها از همین فایلِ محلی (سریع) سرو می‌شوند. برای به‌روزرسانی:
#   GET /api/stations?refresh=1
STATIONS_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stations.json")
# نسخه‌ی اسکیما‌ی کش. داده‌ی خام ایستگاه‌ها (با station_code) ذخیره می‌شود و
# نرمال‌سازی هنگام خواندن اعمال می‌شود تا هر تغییر در _normalize_stations
# (مثل اصلاح id→station_code) روی کشِ موجود هم اثر کند. اگر نسخه‌ی فایل کش
# با این مقدار هم‌خوان نبود (مثل نسخه‌ی ۱ که نگاشت قدیمی id داشت)، کش نادیده
# گرفته شده و از سایت بازخوانی می‌شود.
STATIONS_CACHE_VERSION = 2

# شعاع کره‌ی وب‌مرکاتور (EPSG:3857) برای تبدیل متر ↔ درجه.
_MERC_R = 6378137.0
# محدوده‌ی تقریبی مشهد (برای تشخیص مختصات معتبر و جابجایی lat/lng).
_MASH_LAT = (35.5, 37.0)
_MASH_LNG = (59.0, 60.2)


def _mercator_to_wgs(x, y):
    """تبدیل مختصات وب‌مرکاتور (EPSG:3857، متر: x=easting، y=northing) به WGS84 (درجه)."""
    lng = (x / _MERC_R) * 180.0 / math.pi
    lat = (2.0 * math.atan(math.exp(y / _MERC_R)) - math.pi / 2.0) * 180.0 / math.pi
    return lat, lng


def _to_wgs84(lat, lng):
    """نرمال‌سازی مختصات یک ایستگاه به WGS84 درجه.

    حالت‌های پوشش‌داده‌شده:
    - درجه‌ی معتبر (مثل ۳۶.۳، ۵۹.۵): بدون تغییر.
    - متر وب‌مرکاتور (مثل lat≈۴۲۹۰۰۰۰، long≈۶۶۳۰۰۰۰): تبدیل به درجه.
      در این حالت فیلد long=easting و lat=northing است.
    - جابجایی lat/lng (در مشهد lat<50 و lng>50؛ اگر برعکس باشد، جابجا می‌شود).
    """
    # ۱) اگر خارج از بازه‌ی درجه است → احتمالاً متر وب‌مرکاتور.
    if abs(lat) > 90 or abs(lng) > 180:
        lat, lng = _mercator_to_wgs(lng, lat)  # x=long, y=lat
    # ۲) تشخیص جابجایی (Mashhad: lat≈36، lng≈59).
    if 50.0 < lat < 90.0 and 0.0 < lng < 50.0:
        lat, lng = lng, lat
    if not (math.isfinite(lat) and math.isfinite(lng)):
        return None
    return lat, lng


def _normalize_stations(raw):
    """تبدیل پاسخ خام stations.json به لیست یکدست {id, code, name, lat, lng}.

    سرویس ممکن است لیست باشد یا دیکشنری با کلید data/features/stations/... ؛
    هر آیتم نیز ممکن است مختصات را با نام‌های lat/long یا lng/lon برگرداند.
    این تابع همه‌ی این حالت‌ها را پوشش می‌دهد تا وابسته به جزئیات اسکیما نباشیم.
    """
    items = raw
    if isinstance(raw, dict):
        for k in ("data", "stations", "features", "items", "result", "list"):
            v = raw.get(k)
            if isinstance(v, list):
                items = v
                break
        else:
            # حالت دیکشنریِ {id: {...}} → مقادیر
            vals = list(raw.values())
            if vals and all(isinstance(x, dict) for x in vals):
                items = vals
    if not isinstance(items, list):
        return []

    out = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        lat = item.get("lat") or item.get("latitude") or item.get("Lat")
        lng = item.get("long") or item.get("Long") or item.get("lng") or item.get("lon") or item.get("longitude")
        if lat is None or lng is None:
            continue
        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            continue
        norm = _to_wgs84(lat, lng)
        if norm is None:
            continue
        lat, lng = norm
        name = (
            item.get("name") or item.get("Name") or item.get("title")
            or item.get("stationName") or item.get("StationName")
            or item.get("label") or item.get("address") or item.get("نام") or ""
        )
        # شماره‌ی ایستگاه برای وب‌سرویس ETA: اولویت با station_code است.
        # توجه: «id» در سرویس، شناسه‌ی داخلی است (مثل 8723) و شماره‌ی واقعی
        # ایستگاه نیست؛ «station_code» شماره‌ی واقعی است (مثل 1885) که
        # Get_Lines/Get_ETA انتظارش دارند. id و codeی خروجی = همان station_code.
        sc = (
            item.get("station_code") or item.get("Station_Code") or item.get("stationCode")
            or item.get("code") or item.get("Code")
            or item.get("id") or item.get("ID") or (i + 1)
        )
        out.append({"id": sc, "code": sc, "name": str(name) if name else "", "lat": lat, "lng": lng})
    return out


def _fetch_live_stations():
    """دریافت زنده‌ی stations.json از وب‌سرویس (داده‌ی خام، بدون نرمال‌سازی).

    نرمال‌سازی (انتخاب station_code به‌عنوان شماره‌ی ایستگاه و تبدیل مختصات به
    WGS84) در زمان خواندن/سروکردن اعمال می‌شود تا همیشه با کد فعلی سازگار باشد.
    """
    resp = _session.get(STATIONS_URL, timeout=15, headers={"User-Agent": "rahayab/1.0"})
    resp.raise_for_status()
    return resp.json()


def _load_cached_stations():
    """خواندن ایستگاه‌ها از کش و نرمال‌سازی در زمان خواندن.

    کش داده‌ی خام را با نسخه‌ی اسکیما ذخیره می‌کند. اگر فایل نبود/خراب بود یا
    نسخه‌اش قدیمی بود، None برمی‌گرداند تا /api/stations از سایت بازخوانی کند.
    در غیر این‌صورت داده‌ی خام را با _normalize_stations فعلی نرمال می‌کند.
    """
    try:
        with open(STATIONS_CACHE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("version") != STATIONS_CACHE_VERSION:
        return None  # کش قدیمی یا نامعتبر → بازخوانی
    raw = data.get("stations")
    if not isinstance(raw, (list, dict)):
        return None
    return _normalize_stations(raw)


def _save_cached_stations(raw):
    """ذخیره‌ی داده‌ی خام ایستگاه‌ها + نسخه‌ی اسکیما در فایل کش محلی (JSON، UTF-8).

    داده‌ی خام (با station_code) ذخیره می‌شود، نه نرمال‌شده، تا نرمال‌سازی همیشه
    با کد فعلی در زمان خواندن اعمال شود.
    """
    os.makedirs(os.path.dirname(STATIONS_CACHE), exist_ok=True)
    import datetime as _dt
    payload = {
        "version": STATIONS_CACHE_VERSION,
        "stations": raw,
        "count": len(raw) if isinstance(raw, list) else 0,
        "updated": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    with open(STATIONS_CACHE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


@app.route("/api/stations")
def api_stations():
    """لیست ایستگاه‌های اتوبوس (با کش محلی).

    جریان: داده‌ی ایستگاه‌ها ثابت است، پس یک‌بار از وب‌سرویس شهرداری خوانده و
    در data/stations.json ذخیره می‌شود؛ سپس همه‌ی درخواست‌ها از این فایل محلی
    (سریع و بدون وابستگی به شبکه) سرو می‌شوند.

    - GET /api/stations            → از کش (در صورت نبود، از سایت و سپس کش).
    - GET /api/stations?refresh=1  → بازخوانی اجباری از سایت و به‌روزرسانی کش.
    - اگر سایت در دسترس نبود ولی کش موجود بود، به‌عنوان fallback از کش سرو می‌شود.
    """
    force_refresh = request.args.get("refresh") == "1"

    if not force_refresh:
        cached = _load_cached_stations()
        if cached is not None:
            return jsonify({"stations": cached, "count": len(cached), "source": "cache"})

    # کش موجود نیست (یا refresh درخواست شده) → از سایت بخوان.
    try:
        raw = _fetch_live_stations()
    except requests.RequestException as e:
        # سایت در دسترس نیست؛ اگر کش موجود بود، از آن استفاده کن.
        cached = _load_cached_stations()
        if cached is not None:
            return jsonify({"stations": cached, "count": len(cached), "source": "cache-fallback"})
        return jsonify({"error": "upstream_unreachable", "detail": str(e)}), 502
    except ValueError as e:
        cached = _load_cached_stations()
        if cached is not None:
            return jsonify({"stations": cached, "count": len(cached), "source": "cache-fallback"})
        return jsonify({"error": "upstream_bad_json", "detail": str(e)}), 502

    # داده‌ی خام را در کش ذخیره کن و نسخه‌ی نرمال‌شده (با station_code) را سرو کن.
    _save_cached_stations(raw)
    stations = _normalize_stations(raw)
    return jsonify({"stations": stations, "count": len(stations), "source": "live"})


# ---------- وب‌سرویس ETA (خطوط عبوری و زمان رسیدن اتوبوس) ----------
# سرویس ETA شهرداری مشهد (WCF با رفتار json/ASP.NET-AJAX):
#   POST /ETA_Service.svc/json/Get_Lines   ← لیست خطوط عبوری از ایستگاه
#   POST /ETA_Service.svc/json/Get_ETA     ← زمان تقریبی رسیدن اتوبوس به ایستگاه
# پارامترها (بدنه‌ی JSON): Station_Number, username, password
# اعتبار وب‌سرویس از فایل .env (و در نتیجه os.environ) خوانده می‌شود تا در کد
# هاردکد نشود: MASHHAD_RTPPI_USER, MASHHAD_RTPPI_PASS
# اگر تنظیم نشده باشند، مسیر details خطای no_credentials برمی‌گرداند.
# آدرس پایه نیز قابل بازنویسی است (برای تغییر URL یا تست با سرویس محلی):
#   MASHHAD_ETA_BASE
ETA_BASE = os.environ.get(
    "MASHHAD_ETA_BASE",
    "https://rtpisservice.mashhad.ir/ETA_Service.svc/json",
)
ETA_USER = os.environ.get("MASHHAD_RTPPI_USER", "")
ETA_PASS = os.environ.get("MASHHAD_RTPPI_PASS", "")


def _call_eta(method, station_number):
    """فراخوانی یک متد از سرویس ETA.

    ابتدا POST با بدنه‌ی JSON (Station_Number/username/password) می‌زند. اگر
    سرویس 405 (Method Not Allowed) داد — یعنی عملیات WebGet است و فقط GET
    می‌پذیرد — خودکار با GET و همان پارامترها به‌صورت query string تلاش می‌کند.
    بدین‌ترتیب چه سرویس POST بخواهد چه GET، کار می‌کند.
    پاسخ ممکن است wrapped باشد (کلید <method>Result یا wrapper «d») که در
    _extract_list باز می‌شود. در صورت خطا، کد HTTP، هدر Allow و بخشی از بدنه
    به stderr لاگ می‌شود تا علت واقعی قابل تشخیص باشد.
    """
    url = f"{ETA_BASE.rstrip('/')}/{method}"
    payload = {
        "Station_Number": station_number,
        "username": ETA_USER,
        "password": ETA_PASS,
    }
    headers = {"User-Agent": "rahayab/1.0", "Accept": "application/json"}
    resp = _session.post(url, json=payload, timeout=15, headers=headers)
    if resp.status_code == 405:
        # POST مجاز نیست (WebGet) → با GET و query string تلاش کن.
        resp = _session.get(url, params=payload, timeout=15, headers=headers)
    body_snip = (resp.text or "")[:300]
    if resp.status_code >= 400:
        allow = resp.headers.get("Allow")
        print(f"[ETA] {method} → HTTP {resp.status_code}  url={resp.url}"
              + (f"  Allow={allow}" if allow else "")
              + f"\n        body={body_snip!r}", file=sys.stderr, flush=True)
        raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
    try:
        return resp.json()
    except ValueError:
        print(f"[ETA] {method} → پاسخ JSON نیست (HTTP {resp.status_code})\n"
              f"        body={body_snip!r}", file=sys.stderr, flush=True)
        raise


def _extract_list(raw, result_key):
    """استخراج لیست از پاسخ وب‌سرویس با پوشش اسکیما‌های رایج.

    حالت‌ها:
    - لیست مستقیم → همان.
    - wrapper ASP.NET AJAX: کلید «d» (تک‌سطحی یا تودرتو) باز می‌شود.
    - کلید <result_key> (مثل Get_LinesResult) یا data/features/items/result/list.
    - دیکشنری {id: {...}} → مقادیر.
    تا ۴ سطح پایین می‌رود تا wrapperهای تودرتو (مثل {"d":{"Get_LinesResult":[...]}})
    باز شوند. در صورت نبود، لیست خالی برمی‌گردد.
    """
    seen = 0
    while isinstance(raw, dict) and seen < 4:
        seen += 1
        # ۱) wrapperهای رایج که خودشان لیست دارند.
        for k in (result_key, "d", "Data", "data", "features", "items", "result", "list"):
            v = raw.get(k)
            if isinstance(v, list):
                return v
        # ۲) wrapper «d» یا result_key که خودشان dict هستند → یک سطح پایین‌تر برو.
        descended = False
        for k in (result_key, "d", "Data"):
            v = raw.get(k)
            if isinstance(v, dict):
                raw = v
                descended = True
                break
        if descended:
            continue
        # ۳) دیکشنری {id: {...}} → مقادیر.
        vals = list(raw.values())
        if vals and all(isinstance(x, dict) for x in vals):
            return vals
        return []
    if isinstance(raw, list):
        return raw
    return []


def _first_str(item, keys):
    """اولین مقدار غیرخالی از میان کلیدهای احتمالی (برای اسکیما نامشخص)."""
    for k in keys:
        v = item.get(k)
        if v not in (None, "", []):
            return str(v)
    return ""


def _normalize_lines(raw):
    """تبدیل پاسخ Get_Lines به لیست یکدست {num, title, from, to}."""
    out = []
    for item in _extract_list(raw, "Get_LinesResult"):
        if not isinstance(item, dict):
            continue
        num = _first_str(item, [
            "Line_Number", "LineNumber", "LineNo", "line", "num",
            "number", "Line", "LNo", "Code", "code", "Line_Id", "LineId",
        ])
        title = _first_str(item, [
            "Line_Name", "LineName", "name", "title", "Title", "LineTitle",
            "Line_Title", "Line_Name_FA", "Fa_Name", "FaName",
        ])
        origin = _first_str(item, [
            "Origin", "from", "From", "Start", "src", "source",
            "First_Station", "FirstStation", "Start_Station",
        ])
        dest = _first_str(item, [
            "Destination", "Dest", "dest", "to", "To", "End",
            "Last_Station", "LastStation", "End_Station",
        ])
        out.append({
            "num": num,
            "title": title or (f"خط {num}" if num else "خط"),
            "from": origin,
            "to": dest,
        })
    return out


def _normalize_eta(raw):
    """تبدیل پاسخ Get_ETA به لیست یکدست {num, minutes, time, dest}.

    minutes اولویت با فیلدهای عددی (دقیقه) دارد؛ اگر نبود، رشته‌ی زمان در time می‌رود.
    """
    out = []
    for item in _extract_list(raw, "Get_ETAResult"):
        if not isinstance(item, dict):
            continue
        num = _first_str(item, [
            "Line_Number", "LineNumber", "LineNo", "line", "num", "number", "Line",
        ])
        dest = _first_str(item, [
            "Destination", "Dest", "dest", "to", "To", "End",
        ])
        minutes = None
        for k in [
            "Minutes", "minutes", "ETA", "eta", "Remaining_Minute",
            "RemainingMinute", "remaining", "Arrive_Minute", "Arrival_Minute",
            "ETA_Time",
        ]:
            v = item.get(k)
            if isinstance(v, (int, float)) and v >= 0:
                minutes = int(v)
                break
            if isinstance(v, str) and v.strip().isdigit():
                minutes = int(v.strip())
                break
        time_str = ""
        if minutes is None:
            time_str = _first_str(item, [
                "ArriveTime", "ArrivalTime", "arrive", "Time", "time", "ETA_Time",
            ])
        out.append({"num": num, "minutes": minutes, "time": time_str, "dest": dest})
    return out


@app.route("/api/station/<station_number>/details")
def api_station_details(station_number):
    """جزئیات ایستگاه برای Bottom Sheet: خطوط عبوری + زمان رسیدن اتوبوس.

    - GET /api/station/<station_number>/details
        → {station_number, lines:[...], eta:[...], source:"live", warnings?}

    داده‌ها فقط از وب‌سرویس واقعی ETA شهرداری مشهد خوانده می‌شوند (بدون داده‌ی
    نمایشی). خطوط و ETA به‌صورت همروندا (دو فراخوانی موازی) گرفته می‌شوند تا
    تأخیر کم شود. اگر یکی از آن‌ها خطا داد ولی دیگری موفق بود، پاسخ با warnings
    برمی‌گردد تا Sheet حداقل بخش موفق را نشان دهد. هر دو خطا دادند → 502.
    اعتبار وب‌سرویس از فایل .env خوانده می‌شود (MASHHAD_RTPPI_USER/PASS)؛
    اگر نباشد → 503 no_credentials.
    """
    try:
        sn = int(station_number)
    except ValueError:
        return jsonify({"error": "bad_station_number"}), 400

    if not ETA_USER or not ETA_PASS:
        return jsonify({
            "error": "no_credentials",
            "detail": ("اعتبار وب‌سرویس در فایل .env تنظیم نشده است. "
                       "MASHHAD_RTPPI_USER و MASHHAD_RTPPI_PASS را در .env وارد کنید."),
        }), 503

    from concurrent.futures import ThreadPoolExecutor

    lines, eta, errors = [], [], []
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_lines = ex.submit(_safe_call_eta, "Get_Lines", sn)
        f_eta = ex.submit(_safe_call_eta, "Get_ETA", sn)
        lines_raw, lines_err = f_lines.result()
        eta_raw, eta_err = f_eta.result()

    if lines_err:
        errors.append(f"lines:{lines_err}")
    else:
        lines = _normalize_lines(lines_raw)
    if eta_err:
        errors.append(f"eta:{eta_err}")
    else:
        eta = _normalize_eta(eta_raw)

    # لاگِ تشخیصیِ ETA: برای هر خط، مقدار خامِ ETA_Time و bus_id را چاپ می‌کند تا
    # مشخص شود سرویس برای این ایستگاه عددِ دقیقه می‌دهد یا "-" (اتوبوسی در راه
    # نیست). این نشان می‌دهد «—» در چیپ به‌خاطر داده‌ی سرویس است یا باگِ پردازش.
    # نمونه: [ETA] Get_ETA station=1885 → 2 خط: 1031=ETA:'-'/bus:0, 1098=ETA:'-'/bus:0
    if eta and not eta_err:
        try:
            _items = _extract_list(eta_raw, "Get_ETAResult")
            _summary = ", ".join(
                f"{it.get('Line_Number') or it.get('Line_Id') or '?'}="
                f"ETA:{it.get('ETA_Time')!r}"
                f"/bus:{(it.get('bus_info') or {}).get('bus_id')}"
                for it in _items if isinstance(it, dict)
            )
            print(f"[ETA] Get_ETA station={sn} → {len(eta)} خط: {_summary}",
                  file=sys.stderr, flush=True)
        except Exception:
            pass

    # هر کدام از lines/eta که خالی شد، raw آن را لاگ کن تا ساختار واقعی پاسخ
    # (wrapper ناشناخته / پیام خطای داخل JSON / null / شماره‌ی اشتباه ایستگاه)
    # دیده شود — حتی اگر یکی پر و دیگری خالی باشد.
    if not lines and not lines_err:
        print(f"[ETA] Get_Lines station={sn} → خالی. raw={str(lines_raw)[:300]!r}",
              file=sys.stderr, flush=True)
    if not eta and not eta_err:
        print(f"[ETA] Get_ETA station={sn} → خالی. raw={str(eta_raw)[:300]!r}",
              file=sys.stderr, flush=True)

    # اگر Get_Lines داده‌ای برنگرداند (یا خطا داد) ولی ETA خطوط را داشت، خطوط
    # عبوری را از ETA استخراج کن — خودِ ETA شامل Line_Number و Destinationِ
    # خطوط عبوری ایستگاه است (با ETA_Time="-" اگر اتوبوسی در راه نیست). بدین‌ترتیب
    # خطوط عبوری همیشه نمایش داده می‌شوند حتی اگر Get_Lines خالی یا با ساختار
    # ناشناخته برگردد.
    if not lines and eta:
        lines = [{
            "num": e.get("num") or "",
            "title": (f"خط {e['num']}" if e.get("num") else "خط"),
            "from": "",
            "to": e.get("dest") or "",
        } for e in eta if e.get("num")]

    if not lines and not eta:
        # هر دو خالی → ۵۰۲. جزئیات خام (کوتاه) در detail می‌رود تا در Bottom Sheet
        # هم دیده شود و شماره‌ی ارسالی + ساختار پاسخ برای تشخیص قابل‌مشاهده باشد.
        raw_hint = (f"station={sn} lines_raw={str(lines_raw)[:100]!r}"
                    f" eta_raw={str(eta_raw)[:100]!r}")
        detail = ("; ".join(errors) + " | " if errors else "") + raw_hint
        return jsonify({"error": "upstream_unreachable", "detail": detail}), 502

    payload = {
        "station_number": sn,
        "lines": lines,
        "eta": eta,
        "source": "live",
    }
    if errors:
        payload["warnings"] = errors
    return jsonify(payload)


def _safe_call_eta(method, station_number):
    """فراخوانی ETA با مدیریت استثنا؛ برمی‌گرداند (data, error_str).

    جزئیات خطا (کد HTTP / بدنه / نوع استثنا) در _call_eta به stderr لاگ می‌شود.
    error_str کوتاه است تا در پاسخ ۵۰۲ (و Bottom Sheet) نمایش داده شود.
    """
    try:
        return _call_eta(method, station_number), None
    except requests.HTTPError as e:
        return None, f"http:{e}"
    except requests.RequestException as e:
        print(f"[ETA] {method} → {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        return None, f"net:{type(e).__name__}"
    except ValueError:
        return None, "bad_json"


@app.route("/api/health")
def health():
    """بررسی زنده بودن سرویس."""
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)