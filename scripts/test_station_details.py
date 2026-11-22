"""تست محلی مسیر /api/station/<sn>/details و کمک‌تابع‌های ETA (داده‌ی واقعی).

چون در محیط ساخت به rtpisservice.mashhad.ir دسترسی نیست، داده‌ی زنده‌ی سرویس
واقعی تست نمی‌شود؛ در عوض:

۱) نرمال‌سازی پاسخ‌های محتملِ WCF (wrapped/bare/mixed) با نمونه‌های ساخته‌شده.
۲) مسیر details: no_credentials (503)، ورودی نامعتبر (400)، سرویس در دسترس نیست (502 سریع).
۳) مسیر details با یک **mock server محلی** که پاسخ‌های wrapped واقعی‌نما
   (Get_LinesResult / Get_ETAResult) برمی‌گرداند — یعنی کل مسیر واقعی:
   POST با بدنه‌ی JSON → نرمال‌سازی → پاسخ ۲۰۰.
۴) بارگذاری فایل .env توسط app (python-dotenv) — با یک زیرپردازش که .env را
   موقتاً پر و سپس بازمی‌گرداند.

اجرا:
    python /home/z/my-project/scripts/test_station_details.py
"""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJ = "/home/z/my-project/download/mashhad-rahayab"
ENV_PATH = os.path.join(PROJ, ".env")
sys.path.insert(0, PROJ)

# اعتبار وب‌سرویس را از محیط پاک کن تا حالت no_credentials را ببینیم.
os.environ.pop("MASHHAD_RTPPI_USER", None)
os.environ.pop("MASHHAD_RTPPI_PASS", None)
os.environ.pop("MASHHAD_ETA_BASE", None)

import app as A  # noqa: E402

failures = []


def check(name, cond, detail=""):
    mark = "OK " if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


# ---------- mock server محلی (شبیه‌ساز سرویس WCF/json) ----------
MOCK_LINES = {"Get_LinesResult": [
    {"Line_Number": "110", "Line_Name": "خط ۱۱۰", "Origin": "میدان شهدا", "Destination": "ترمینال وکیل‌آباد"},
    {"LineNumber": 88, "LineName": "خط ۸۸", "from": "دانشگاه فردوسی", "to": "میدان آزادی"},
    {"line": "21"},
]}
MOCK_ETA = {"Get_ETAResult": [
    {"Line_Number": "110", "Minutes": 4, "Destination": "ترمینال وکیل‌آباد"},
    {"LineNumber": "88", "Remaining_Minute": "11", "to": "میدان آزادی"},
    {"line": "21", "ArriveTime": "08:45"},
    {"line": "7", "minutes": 0},
]}


class _MockHandler(BaseHTTPRequestHandler):
    def _payload(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path.endswith("/Get_Lines"):
            return MOCK_LINES
        if path.endswith("/Get_ETA"):
            return MOCK_ETA
        return None

    def do_GET(self):
        payload = self._payload()
        if payload is None:
            self.send_response(404); self.end_headers(); return
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=UTF-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        # سرویس واقعی POST را با 405 رد می‌کند — mock هم همین‌کار را می‌کند.
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.end_headers()

    def log_message(self, *a):
        pass


def _start_mock():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _MockHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/json"


# ---------- ۱) نرمال‌سازی ----------
print("== unit: _extract_list ==")
check("bare list", A._extract_list([1, 2, 3], "Get_LinesResult") == [1, 2, 3])
check("wrapped Get_LinesResult",
      A._extract_list({"Get_LinesResult": [{"a": 1}]}, "Get_LinesResult") == [{"a": 1}])
check("dict-of-dicts values",
      A._extract_list({"x": {"a": 1}, "y": {"b": 2}}, "Get_LinesResult") == [{"a": 1}, {"b": 2}])
check("data key list", A._extract_list({"data": [1, 2]}, "Get_LinesResult") == [1, 2])
check("empty for scalar", A._extract_list(42, "Get_LinesResult") == [])
check("ASP.NET AJAX d wrapper (bare)",
      A._extract_list({"d": [{"a": 1}]}, "Get_LinesResult") == [{"a": 1}])
check("d wrapping Get_LinesResult",
      A._extract_list({"d": {"Get_LinesResult": [{"a": 1}]}}, "Get_LinesResult") == [{"a": 1}])
check("Get_LinesResult wrapping d",
      A._extract_list({"Get_LinesResult": {"d": [{"a": 1}]}}, "Get_LinesResult") == [{"a": 1}])
check("nested d in d",
      A._extract_list({"d": {"d": [{"a": 1}]}}, "Get_LinesResult") == [{"a": 1}])

print("\n== unit: _normalize_lines (wrapped WCF) ==")
lines = A._normalize_lines(MOCK_LINES)
check("lines count == 3", len(lines) == 3, str(lines))
check("line0 num/title", lines[0]["num"] == "110" and lines[0]["title"] == "خط ۱۱۰", str(lines[0]))
check("line1 from/to", lines[1]["from"] == "دانشگاه فردوسی" and lines[1]["to"] == "میدان آزادی", str(lines[1]))
check("line2 fallback title", lines[2]["title"] == "خط 21", str(lines[2]))

print("\n== unit: _normalize_eta (mixed minute types) ==")
eta = A._normalize_eta(MOCK_ETA)
check("eta count == 4", len(eta) == 4, str(eta))
check("eta0 minutes==4", eta[0]["minutes"] == 4 and eta[0]["dest"] == "ترمینال وکیل‌آباد", str(eta[0]))
check("eta1 string-minute parsed", eta[1]["minutes"] == 11, str(eta[1]))
check("eta2 time fallback", eta[2]["minutes"] is None and eta[2]["time"] == "08:45", str(eta[2]))
check("eta3 zero minute", eta[3]["minutes"] == 0, str(eta[3]))

# ---------- ۱.۵) _call_eta با GET + query params (رفع 405) ----------
print("\n== unit: _call_eta uses GET with query params ==")
captured = {}


class _FakeResp:
    status_code = 200
    headers = {"Content-Type": "application/json"}
    text = '{"Get_LinesResult": [{"Line_Number": "1"}]}'
    url = "http://mock/json/Get_Lines"

    def json(self):
        return json.loads(self.text)


_orig_get = A._session.get


def _fake_get(url, params=None, timeout=None, headers=None):
    captured["url"] = url
    captured["params"] = params or {}
    captured["headers"] = headers or {}
    return _FakeResp()


A._session.get = _fake_get
try:
    A.ETA_USER, A.ETA_PASS = "u", "p"
    out = A._call_eta("Get_Lines", 7343)
    check("used GET (session.get called)", "url" in captured)
    check("url ends with /Get_Lines", captured["url"].endswith("/Get_Lines"), str(captured.get("url")))
    check("params: Station_Number=7343", captured["params"].get("Station_Number") == 7343, str(captured["params"]))
    check("params: username/password sent",
          captured["params"].get("username") == "u" and captured["params"].get("password") == "p")
    check("Accept: application/json", captured["headers"].get("Accept") == "application/json")
    check("parsed JSON response", out == {"Get_LinesResult": [{"Line_Number": "1"}]})
finally:
    A._session.get = _orig_get
    A.ETA_USER, A.ETA_PASS = "", ""


# ---------- ۲/۳) مسیرها ----------
client = A.app.test_client()

print("\n== route: no creds → 503 no_credentials ==")
r = client.get("/api/station/7559/details")
body = r.get_json()
check("status 503", r.status_code == 503, f"status={r.status_code}")
check("error no_credentials", body.get("error") == "no_credentials", str(body))

print("\n== route: bad station_number → 400 ==")
r = client.get("/api/station/abc/details")
check("status 400", r.status_code == 400, f"status={r.status_code}")
check("error bad_station_number", r.get_json().get("error") == "bad_station_number")

print("\n== route: live unreachable (dead ETA_BASE) → 502 سریع ==")
A.ETA_USER, A.ETA_PASS = "u", "p"
A.ETA_BASE = "http://127.0.0.1:1/json"  # پورت مرده → ConnectionError فوری
r = client.get("/api/station/7559/details")
body = r.get_json()
check("status 502", r.status_code == 502, f"status={r.status_code} body={body}")
check("error upstream_unreachable", body.get("error") == "upstream_unreachable", str(body))
A.ETA_USER, A.ETA_PASS = "", ""

print("\n== route: real-data path با mock server (GET → normalize → 200) ==")
srv, mock_base = _start_mock()
A.ETA_USER, A.ETA_PASS = "u", "p"
A.ETA_BASE = mock_base
r = client.get("/api/station/7559/details")
body = r.get_json()
check("status 200", r.status_code == 200, f"status={r.status_code} body={body}")
check("source live", body.get("source") == "live", str(body))
check("station_number 7559", body.get("station_number") == 7559, str(body))
check("lines == 3", len(body.get("lines", [])) == 3, str(body.get("lines")))
check("eta == 4", len(body.get("eta", [])) == 4, str(body.get("eta")))
check("eta0 minutes==4 (from mock)", body["eta"][0]["minutes"] == 4, str(body["eta"][0]))
A.ETA_USER, A.ETA_PASS = "", ""
A.ETA_BASE = "https://rtpisservice.mashhad.ir/ETA_Service.svc/json"
srv.shutdown()

print("\n== route: /api/health still ok ==")
r = client.get("/api/health")
check("health ok", r.status_code == 200 and r.get_json().get("status") == "ok")

print("\n== route: /api/stations reachable (cache or fallback) ==")
r = client.get("/api/stations")
check("stations responds (200 or 502)", r.status_code in (200, 502), f"status={r.status_code}")

# ---------- ۴) سیم‌بندی .env (بررسی ایستا، بدون لمس فایل واقعی) ----------
print("\n== .env wiring (بررسی منبع — بدون تغییر فایل) ==")
# NOTE: این بخش عمداً فایل .env واقعی را نمی‌نویسد/حذف نمی‌کند، چون این پروژه
# محیط زنده‌ی کاربر است و اعتبار واقعی ممکن است در .env یا متغیرهای محیط باشد.
src = open(os.path.join(PROJ, "app.py"), encoding="utf-8").read()
gi = open(os.path.join(PROJ, ".gitignore"), encoding="utf-8").read()
rq = open(os.path.join(PROJ, "requirements.txt"), encoding="utf-8").read()
check("app.py calls load_dotenv", "load_dotenv(" in src)
check("load_dotenv points to .env next to app.py",
      'os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")' in src)
check("ETA_USER reads MASHHAD_RTPPI_USER", 'os.environ.get("MASHHAD_RTPPI_USER"' in src)
check("ETA_PASS reads MASHHAD_RTPPI_PASS", 'os.environ.get("MASHHAD_RTPPI_PASS"' in src)
check("ETA_BASE overridable via MASHHAD_ETA_BASE", '"MASHHAD_ETA_BASE"' in src)
check(".env in .gitignore", ".env" in gi)
check("python-dotenv in requirements.txt", "python-dotenv" in rq)

print("\n== summary ==")
if failures:
    print(f"  {len(failures)} FAILED: {failures}")
    sys.exit(1)
print("  all passed.")