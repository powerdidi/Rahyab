
import requests

URL = "https://rtpisservice.mashhad.ir/shahreman-temp-api/stations.json"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

# تست اول: با تنظیمات پیش‌فرض شبکه و پروکسی
print("\n--- Test 1: Default connection ---")

try:
    response = requests.get(URL, headers=headers, timeout=20)
    print("Status:", response.status_code)
    print("Response:", response.text[:500])
except Exception as e:
    print("Error:", repr(e))


# تست دوم: اتصال مستقیم بدون پروکسی محیطی
print("\n--- Test 2: Direct connection ---")

session = requests.Session()
session.trust_env = False

try:
    response = session.get(URL, headers=headers, timeout=20)
    print("Status:", response.status_code)
    print("Response:", response.text[:500])
except Exception as e:
    print("Error:", repr(e))
