"""یک mock server محلی برای سرویس ETA شهرداری مشهد (WCF/json).

برای تست مسیر واقعیِ /api/station/<sn>/details وقتی به سرویس زنده دسترسی نیست.
پاسخ‌های wrapped واقعی‌نما (Get_LinesResult / Get_ETAResult) برمی‌گرداند.

اجرا:
    python /home/z/my-project/scripts/mock_eta_server.py [PORT]
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MOCK_LINES = {"Get_LinesResult": [
    {"Line_Number": "110", "Line_Name": "خط ۱۱۰", "Origin": "میدان شهدا", "Destination": "ترمینال وکیل‌آباد"},
    {"LineNumber": 88, "LineName": "خط ۸۸", "from": "دانشگاه فردوسی", "to": "میدان آزادی"},
    {"line": "21", "Line_Name": "خط ۲۱", "Origin": "پارک ملت", "Destination": "ترمینال قائم"},
]}
MOCK_ETA = {"Get_ETAResult": [
    {"Line_Number": "110", "Minutes": 4, "Destination": "ترمینال وکیل‌آباد"},
    {"LineNumber": "88", "Minutes": 11, "Destination": "میدان آزادی"},
    {"line": "21", "Minutes": 18, "Destination": "ترمینال قائم"},
    {"Line_Number": "110", "Minutes": 22, "Destination": "میدان شهدا"},
]}


class Handler(BaseHTTPRequestHandler):
    def _payload_for(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path.endswith("/Get_Lines"):
            return MOCK_LINES
        if path.endswith("/Get_ETA"):
            return MOCK_ETA
        return None

    def _send_json(self, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=UTF-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        payload = self._payload_for()
        if payload is None:
            self.send_response(404); self.end_headers(); return
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        sn = (q.get("Station_Number") or [""])[0]
        self._send_json(payload)
        print(f"  mock GET {self.path.split('?')[0]} Station_Number={sn}"
              f" -> {len(payload[list(payload)[0]])} items", flush=True)

    def do_POST(self):
        # سرویس واقعی POST را با 405 رد می‌کند؛ mock هم همین رفتار را شبیه‌سازی می‌کند.
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5050
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"mock ETA server on http://127.0.0.1:{port}/json  (Get_Lines, Get_ETA)", flush=True)
    srv.serve_forever()
