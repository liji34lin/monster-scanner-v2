import time
import json
import os
import requests

BOT_TOKEN = "8790016448:AAG1BwHkqOYAw6B4yGpsW4__yem1HFZ1WaQ"

MIN_VOLUME = 5_000_000
OI_THRESHOLD = 8

CHAT_FILE = "chat_ids.json"


def telegram_api(method, data=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        r = requests.post(url, data=data, timeout=15)
        return r.json()
    except Exception as e:
        print("Telegram API error:", e)
        return None


def load_chat_ids():
    if not os.path.exists(CHAT_FILE):
        return set()

    try:
        with open(CHAT_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_chat_ids(chat_ids):
    with open(CHAT_FILE, "w") as f:
        json.dump(list(chat_ids), f)


def send_message(chat_id, text):
    telegram_api("sendMessage", {
        "chat_id": chat_id,
        "text": text
    })


def send_to_all(text):
    chat_ids = load_chat_ids()

    if not chat_ids:
        print("No chat ids yet. Send /start to the bot first.")
        return

    for chat_id in chat_ids:
        send_message(chat_id, text)


def handle_updates():
    chat_ids = load_chat_ids()

    result = telegram_api("getUpdates", {
        "timeout": 5
    })

    if not result or not result.get("ok"):
        print("getUpdates error:", result)
        return

    for update in result.get("result", []):
        message = update.get("message")

        if not message:
            continue

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = message.get("text", "")

        if chat_id:
            chat_ids.add(chat_id)

        if text == "/start":
            send_message(chat_id, "✅ 已启动，抓妖机器人正在运行。")

        elif text.lower() in ["test", "hi", "start"]:
            send_message(chat_id, "✅ 我在线，机器人正常运行。")

    save_chat_ids(chat_ids)


def get_symbols():
    r = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=20)
    data = r.json()

    if "symbols" not in data:
        print("exchangeInfo error:", data)
        return []

    symbols = []

    for s in data["symbols"]:
        if s.get("quoteAsset") == "USDT" and s.get("contractType") == "PERPETUAL":
            symbols.append(s["symbol"])

    return symbols


def get_volume():
    r = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=20)
    data = r.json()

    if not isinstance(data, list):
        print("volume error:", data)
        return {}

    vol_map = {}

    for d in data:
        try:
            vol_map[d["symbol"]] = float(d["quoteVolume"])
        except Exception:
            pass

    return vol_map


def get_funding():
    r = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex", timeout=20)
    data = r.json()

    if not isinstance(data, list):
        print("funding error:", data)
        return {}

    fr_map = {}

    for d in data:
        try:
            fr_map[d["symbol"]] = float(d["lastFundingRate"])
        except Exception:
            pass

    return fr_map


def get_oi(symbol):
    url = "https://fapi.binance.com/futures/data/openInterestHist"

    params = {
        "symbol": symbol,
        "period": "15m",
        "limit": 16
    }

    r = requests.get(url, params=params, timeout=20)
    data = r.json()

    if not isinstance(data, list):
        print(symbol, "OI error:", data)
        return 0

    if len(data) < 4:
        return 0

    try:
        first = float(data[0]["sumOpenInterest"])
        last = float(data[-1]["sumOpenInterest"])
    except Exception:
        return 0

    if first == 0:
        return 0

    return (last - first) / first * 100


def scan():
    print("Scanning...")

    symbols = get_symbols()
    volumes = get_volume()
    funding = get_funding()

    signals = []

    for sym in symbols:
        if sym not in volumes:
            continue

        if volumes[sym] < MIN_VOLUME:
            continue

        if sym not in funding:
            continue

        if funding[sym] >= 0:
            continue

        oi_change = get_oi(sym)

        if oi_change > OI_THRESHOLD:
            signals.append((sym, funding[sym], oi_change))

        time.sleep(0.05)

    if signals:
        msg = "🚀 抓妖信号:\n\n"

        for s in signals:
            msg += f"{s[0]} | FR: {s[1]:.4f} | OI: {s[2]:.2f}%\n"

        send_to_all(msg)
        print("Signal sent")
    else:
        print("No signal")


print("Bot started")

while True:
    try:
        handle_updates()
        scan()
    except Exception as e:
        print("Error:", e)

    time.sleep(300)
