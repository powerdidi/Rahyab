"""داده‌های نمونه شبکه حمل‌ونقل مشهد (ایستگاه‌ها و خطوط).

NOTE (مهم): مختصات جغرافیایی ایستگاه‌ها تقریبی و نمونه‌اند — از تبدیل
شبکه‌ی انتزاعی پروتوتایپ (x,y در بازه ۰–۱۰۰) به محدوده‌ی جغرافیایی مشهد
به‌دست آمده‌اند. هدف فقط نمایش نمایشی صفحه نقشه است. در گام‌های بعد،
این داده‌ها (با مختصات واقعی) از وب‌سرویس دریافت می‌شوند؛ در آن زمان
کافی است تابع `network_json` داده را از وب‌سرویس بخواند.
"""

# محدوده‌ی جغرافیایی تقریبی مشهد (برای تبدیل شبکه‌ی نمونه به lat/lng)
MASHHAD_BBOX = {
    "lat_min": 36.20,
    "lat_max": 36.43,
    "lng_min": 59.45,
    "lng_max": 59.72,
}

# مرکز و زوم پیش‌فرض نقشه (همان سرویس پایه‌ی کاربر)
MASHHAD_CENTER = [36.329616, 59.56543]
MASHHAD_DEFAULT_ZOOM = 12


def _grid_to_ll(x, y):
    """تبدیل مختصات انتزاعی (x,y در ۰–۱۰۰) به (lat,lng) روی مشهد."""
    lng = MASHHAD_BBOX["lng_min"] + (x / 100.0) * (MASHHAD_BBOX["lng_max"] - MASHHAD_BBOX["lng_min"])
    lat = MASHHAD_BBOX["lat_max"] - (y / 100.0) * (MASHHAD_BBOX["lat_max"] - MASHHAD_BBOX["lat_min"])
    return round(lat, 5), round(lng, 5)


# ایستگاه‌های نمونه — n=نام، code=کد، x/y=موقعیت نمونه، addr=آدرس، lines=خطوط عبوری، dock=داشتن دوک دوچرخه
_RAW_STATIONS = {
    "vakilabad":    {"n": "بلوار وکیل‌آباد",          "code": 1204, "x": 14, "y": 18, "addr": "بلوار وکیل‌آباد، جنب پارک",          "lines": ["BRT1", "L12", "M1"],                "dock": False},
    "parkemellat":  {"n": "پارک ملت",                 "code": 1208, "x": 24, "y": 24, "addr": "بلوار وکیل‌آباد، جنب پارک ملت",      "lines": ["BRT1", "M1"],                       "dock": True},
    "azadi":        {"n": "میدان آزادی",              "code": 1215, "x": 36, "y": 30, "addr": "میدان آزادی، ضلع شمالی",            "lines": ["L12", "M1", "M2", "L55"],           "dock": True},
    "ariya":        {"n": "میدان آریایی",             "code": 1221, "x": 46, "y": 24, "addr": "میدان آریایی، جنب دانشگاه فردوسی",  "lines": ["M1", "L55"],                        "dock": False},
    "sajjad":       {"n": "بلوار سجاد",               "code": 1230, "x": 56, "y": 18, "addr": "بلوار سجاد، ضلع جنوبی",            "lines": ["L55"],                              "dock": False},
    "siyad":        {"n": "میدان صیاد شیرازی",        "code": 1240, "x": 70, "y": 12, "addr": "میدان صیاد شیرازی، ضلع شرقی",      "lines": ["BRT2", "L10", "M1"],                "dock": True},
    "toos":         {"n": "بزرگراه توس",              "code": 1250, "x": 84, "y": 10, "addr": "بزرگراه توس، پایانه مستوفی",        "lines": ["M1"],                               "dock": False},
    "ghasemabad":   {"n": "قاسم‌آباد، میدان مردمان",  "code": 1305, "x": 28, "y": 44, "addr": "قاسم‌آباد، میدان مردمان",          "lines": ["BRT1", "L12", "M2", "L55"],         "dock": True},
    "dad":          {"n": "میدان داد",                "code": 1310, "x": 18, "y": 58, "addr": "میدان داد، ضلع غربی",              "lines": ["L10", "M2", "L55"],                 "dock": False},
    "koohsangi":    {"n": "کوهسنگی",                  "code": 1318, "x": 24, "y": 72, "addr": "کوهسنگی، ضلع جنوبی پارک",          "lines": ["L110", "M2"],                       "dock": False},
    "shohada":      {"n": "میدان شهدا",               "code": 1325, "x": 42, "y": 58, "addr": "میدان شهدا، ضلع شمالی",            "lines": ["BRT2", "L10", "L12", "L110"],       "dock": True},
    "ferdowsi":     {"n": "میدان فردوسی",             "code": 1332, "x": 54, "y": 48, "addr": "میدان فردوسی، ضلع جنوبی",          "lines": ["BRT2", "L10", "L12"],               "dock": True},
    "ahmadabad":    {"n": "میدان احمدآباد",           "code": 1340, "x": 62, "y": 40, "addr": "میدان احمدآباد، ضلع شمالی",        "lines": ["L12", "M1"],                        "dock": False},
    "malekabad":    {"n": "میدان ملک‌آباد",           "code": 1348, "x": 72, "y": 34, "addr": "میدان ملک‌آباد، ضلع جنوبی",        "lines": ["BRT2", "L12", "M1"],                "dock": False},
    "haram":        {"n": "حرم مطهر",                 "code": 1410, "x": 54, "y": 64, "addr": "حواشی حرم مطهر، ضلع شرقی",         "lines": ["BRT1", "L110", "M2"],               "dock": False},
    "kaveh":        {"n": "میدان شهید کاوه",          "code": 1420, "x": 40, "y": 76, "addr": "بلوار شهید کاوه، ضلع جنوبی",      "lines": ["BRT2", "L110", "M2"],               "dock": True},
    "tabarsi":      {"n": "بلوار طبرسی",              "code": 1430, "x": 68, "y": 62, "addr": "بلوار طبرسی، ضلع شمالی",          "lines": ["BRT2", "M2"],                       "dock": False},
    "medinerreza":  {"n": "میدان مدینه‌الرضا",        "code": 1440, "x": 82, "y": 56, "addr": "میدان مدینه‌الرضا، ضلع جنوبی",    "lines": ["BRT2", "M2"],                       "dock": False},
    "razi":         {"n": "شهرک رازی",                "code": 1450, "x": 14, "y": 86, "addr": "شهرک رازی، ضلع شمالی",            "lines": ["L10", "L110"],                      "dock": False},
}


# خطوط نمونه — type, num, title, color, from, to, stops
LINES = {
    "BRT1": {"type": "brt",   "num": "1",   "title": "BRT خط ۱",      "color": "#c14f4b", "from": "بلوار وکیل‌آباد",     "to": "حرم مطهر",           "stops": ["vakilabad", "parkemellat", "ghasemabad", "haram"]},
    "BRT2": {"type": "brt",   "num": "2",   "title": "BRT خط ۲",      "color": "#2e8ba0", "from": "میدان صیاد شیرازی",   "to": "میدان مدینه‌الرضا",  "stops": ["siyad", "malekabad", "ferdowsi", "shohada", "kaveh", "tabarsi", "medinerreza"]},
    "L10":  {"type": "bus",   "num": "10",  "title": "اتوبوس خط ۱۰",  "color": "#4f9159", "from": "میدان صیاد شیرازی",   "to": "شهرک رازی",          "stops": ["siyad", "ferdowsi", "shohada", "dad", "razi"]},
    "L12":  {"type": "bus",   "num": "12",  "title": "اتوبوس خط ۱۲",  "color": "#c98a35", "from": "بلوار وکیل‌آباد",     "to": "میدان ملک‌آباد",     "stops": ["vakilabad", "azadi", "ghasemabad", "shohada", "ferdowsi", "ahmadabad", "malekabad"]},
    "L110": {"type": "bus",   "num": "110", "title": "اتوبوس خط ۱۱۰", "color": "#8a63a8", "from": "حرم مطهر",            "to": "شهرک رازی",          "stops": ["haram", "shohada", "kaveh", "koohsangi", "razi"]},
    "L55":  {"type": "bus",   "num": "55",  "title": "اتوبوس خط ۵۵",  "color": "#c05a78", "from": "بلوار سجاد",          "to": "میدان داد",          "stops": ["sajjad", "ariya", "azadi", "ghasemabad", "dad"]},
    "M1":   {"type": "metro", "num": "1",   "title": "مترو خط ۱",     "color": "#b08b25", "from": "بلوار وکیل‌آباد",     "to": "بزرگراه توس",        "stops": ["vakilabad", "parkemellat", "azadi", "ariya", "ahmadabad", "malekabad", "siyad", "toos"]},
    "M2":   {"type": "metro", "num": "2",   "title": "مترو خط ۲",     "color": "#4b6b9e", "from": "میدان مدینه‌الرضا",   "to": "میدان آزادی",        "stops": ["medinerreza", "tabarsi", "haram", "kaveh", "koohsangi", "dad", "ghasemabad", "azadi"]},
}


def build_stations():
    """ساخت دیکشنری ایستگاه‌ها با مختصات lat/lng محاسبه‌شده."""
    out = {}
    for sid, s in _RAW_STATIONS.items():
        lat, lng = _grid_to_ll(s["x"], s["y"])
        out[sid] = {
            "n": s["n"],
            "code": s["code"],
            "lat": lat,
            "lng": lng,
            "addr": s["addr"],
            "lines": s["lines"],
            "dock": s["dock"],
        }
    return out


STATIONS = build_stations()


def network_json():
    """خروجی JSON شبکه برای ارسال به کلاینت."""
    return {"stations": STATIONS, "lines": LINES}
