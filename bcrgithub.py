import os
import time
import threading
import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote
from flask import Flask, jsonify

# ======================
# Cấu hình & Bảo mật
# ======================
BASE = "https://aibcr.me"
LOGIN_URL = f"{BASE}/login"
LOBBY_URL = f"{BASE}/ae/lobby"
GETNEWRESULT_URL = f"{BASE}/baccarat/getnewresult"

# Sử dụng biến môi trường để tránh lộ pass trên GitHub
# Nếu không có biến môi trường, code sẽ dùng giá trị mặc định bạn cung cấp
USERNAME = os.environ.get("BOT_USER", "tuanhkdepzai")
PASSWORD = os.environ.get("BOT_PASS", "3245257860")

# ======================
# Biến toàn cục
# ======================
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
})

last_results = {}      
filtered_data = []     
auto_running = True

# ======================
# Hàm xử lý Logic
# ======================
def get_csrf_token(html):
    soup = BeautifulSoup(html, "html.parser")
    t = soup.find("input", {"name": "_token"})
    if t and t.get("value"):
        return t["value"]
    meta = soup.find("meta", {"name": "csrf-token"})
    if meta and meta.get("content"):
        return meta["content"]
    return None

def login():
    try:
        r = session.get(LOGIN_URL, timeout=15)
        token = get_csrf_token(r.text)
        payload = {"username": USERNAME, "password": PASSWORD, "action": "Login"}
        if token:
            payload["_token"] = token
        
        headers = {
            "Referer": LOGIN_URL, 
            "Origin": BASE, 
            "Content-Type": "application/x-www-form-urlencoded"
        }
        resp = session.post(LOGIN_URL, data=payload, headers=headers, timeout=15)
        print(f"✅ Đăng nhập: {resp.status_code}")
        return True
    except Exception as e:
        print(f"❌ Lỗi đăng nhập: {e}")
        return False

def call_getnewresult():
    global filtered_data
    xsrf_token = unquote(session.cookies.get("XSRF-TOKEN", ""))
    headers = {
        "Referer": LOBBY_URL,
        "Origin": BASE,
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": xsrf_token,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    try:
        resp = session.post(GETNEWRESULT_URL, headers=headers, data={"gameCode": "ae"}, timeout=15)
        if resp.status_code == 419: # Token hết hạn
            print("🔄 CSRF Token hết hạn, đang đăng nhập lại...")
            login()
            return

        if not resp.ok: return

        data = resp.json().get("data", [])
        new_filtered = []

        for t in data:
            tb_name = t.get("table_name", "")
            curr = t.get("result", "")
            prev = last_results.get(tb_name, "")

            if curr and curr != prev:
                last_results[tb_name] = curr
                new_filtered.append({
                    "table_name": tb_name,
                    "result": curr,
                    "goodRoad": t.get("goodRoad", ""),
                    "round": t.get("round", ""),
                    "time": time.strftime("%H:%M:%S")
                })

        if new_filtered:
            fd_dict = {item["table_name"]: item for item in filtered_data}
            for f in new_filtered:
                fd_dict[f["table_name"]] = f
            filtered_data = list(fd_dict.values())

    except Exception as e:
        print(f"⚠️ Lỗi fetch data: {e}")

def auto_loop():
    print("🔄 Bắt đầu vòng lặp lấy dữ liệu ngầm...")
    while auto_running:
        call_getnewresult()
        time.sleep(2) # Tăng lên 2s để tránh bị block IP trên server cloud

# ======================
# Flask API
# ======================
app = Flask(__name__)

@app.route("/")
def home():
    return {"status": "running", "message": "Baccarat API is active"}

@app.route("/data")
def get_data():
    sorted_data = sorted(filtered_data, key=lambda x: x["table_name"])
    return jsonify({
        "total_tables": len(sorted_data),
        "last_update": time.strftime("%H:%M:%S"),
        "data": sorted_data
    })

# ======================
# Khởi động hệ thống
# ======================
if __name__ == "__main__":
    # 1. Thực hiện đăng nhập trước
    if login():
        session.get(LOBBY_URL, timeout=15)
        
        # 2. Chạy luồng cập nhật dữ liệu ngầm
        update_thread = threading.Thread(target=auto_loop, daemon=True)
        update_thread.start()
        
        # 3. Chạy Flask Server với Port động từ môi trường
        # Render/Heroku sẽ tự cấp PORT, nếu không có thì dùng 5000
        port = int(os.environ.get("PORT", 5000))
        print(f"🚀 Server sẵn sàng tại port {port}")
        app.run(host="0.0.0.0", port=port)