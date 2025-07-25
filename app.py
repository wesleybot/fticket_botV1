# app.py — 票速通 LINE Bot  (2025-07-19)

import os
import json
import logging
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage,
    FlexMessage, FlexContainer
)
# 正確的 QuickReply 類別路徑
from linebot.v3.messaging.models import QuickReply, QuickReplyButton, MessageAction
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ────────────────────────────
# Logging
# ────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# ────────────────────────────
# Flask
# ────────────────────────────
app = Flask(__name__)

# ────────────────────────────
# LINE SDK  (環境變數)
# ────────────────────────────
ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

boss_user_id = os.environ.get("BOSS_USER_ID", "")
manager_user_ids = {boss_user_id} if boss_user_id else set()

# ────────────────────────────
# 條款常數
# ────────────────────────────
TOS_VERSION = "v1"
TOS_PDF_URL = "https://fticket-botv1.onrender.com/static/tos_privacy_v1.pdf"
TOS_CONFIRM_TEXT = f"我同意，並了解自我權益關於票速通條款{TOS_VERSION}"

# ────────────────────────────
# 使用者同意列表檔案
# ────────────────────────────
ACCEPTED_USERS_FILE = "accepted_users.json"

def load_accepted_users():
    if os.path.exists(ACCEPTED_USERS_FILE):
        with open(ACCEPTED_USERS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_accepted_users():
    with open(ACCEPTED_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(accepted_terms_users), f, ensure_ascii=False, indent=2)

# ────────────────────────────
# 狀態
# ────────────────────────────
accepted_terms_users: set[str] = load_accepted_users()
submitted_users: set[str] = set()
auto_reply = False

# ────────────────────────────
# 關鍵字回應
# ────────────────────────────
KEYWORD_REPLIES = {
    "[!!!]售票規則是甚麼？": (
        "【@票速通 售票規則】\n"
        "🍀 本官方以「誠信」為本，詳情請見以下說明：\n\n"
        "Q：代操費用？\nA：一筆委託計算，不額外加價。\n\n"
        "Q：支付方式？\nA：LINE Pay、街口、一卡通、支付寶等。\n\n"
        "Q：如何證明？\nA：提供訂單截圖與手寫時間。\n"
    ),
    "[!!!]演唱會代操": (
        "😍 可預約 2025 演唱會：\n"
        "➣ 11/22 TWICE 世界巡迴 PART1 in 高雄\n"
        "➣ 9/26-28 周興哲 Odyssey 臺北返場\n"
        "➣ 9/27 家家 Fly to the moon\n"
        "➣ 11/22-23 伍佰 Rock Star 2 in 高雄\n\n"
        "✓ 搶票成功才收費，全網最低價！點「填寫預訂單」開始。"
    ),
}

# ═════════════════════════════════════════════
# Bubble 產生器
# ═════════════════════════════════════════════
def _one_row(label: str, value: str):
    return {"type": "box", "layout": "baseline", "contents": [
        {"type": "text", "text": label, "size": "sm", "color": "#aaaaaa", "flex": 1},
        {"type": "text", "text": value, "size": "sm", "color": "#666666", "wrap": True, "flex": 4},
    ]}

def create_bubble(title, date, location, price, system,
                  image_url, artist_keyword, badge_text="NEW"):
    return {
        "type": "bubble",
        "header": {"type":"box","layout":"vertical","contents":[
            {"type":"box","layout":"horizontal","contents":[
                {"type":"image","url":image_url,"size":"full","aspectMode":"cover","aspectRatio":"30:25","flex":1},
                {"type":"box","layout":"horizontal","position":"absolute",
                 "offsetStart":"18px","offsetTop":"18px","width":"72px","height":"28px",
                 "backgroundColor":"#EC3D44","cornerRadius":"100px","paddingAll":"2px",
                 "contents":[{"type":"text","text":badge_text,"size":"xs","color":"#ffffff","align":"center","gravity":"center"}]}
            ]}
        ],"paddingAll":"0px"},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":title,"wrap":True,"weight":"bold","gravity":"center","size":"xl"},
            {"type":"box","layout":"vertical","spacing":"sm","contents":[
                _one_row("日期", date),
                _one_row("地點", location),
                _one_row("票價", price),
                _one_row("系統", system),
            ]}
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","action":{"type":"message","label":"填寫預訂單","text":f"我要預訂：{artist_keyword}"},
             "style":"primary","color":"#00A4C1"}
        ]}
    }

CONCERT_BUBBLES = [
    create_bubble("TWICE THIS IS FOR WORLD TOUR PART1 IN KAOHSIUNG",
                  "Coming soon…","—","—","—",
                  "https://img9.uploadhouse.com/...TWICE.png","TWICE"),
    create_bubble("周興哲 Odyssey 臺北返場",
                  "2025/9/26–28","臺北小巨蛋","—","KKTIX",
                  "https://img7.uploadhouse.com/...Zhou.png","周興哲"),
    create_bubble("家家 Fly to the moon",
                  "9/27","Legacy Taipei","—","拓元售票",
                  "https://img4.uploadhouse.com/...JiaJia.png","家家"),
]

# ────────────────────────────
# Webhook 入口
# ────────────────────────────
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ────────────────────────────
# 條款 Bubble
# ────────────────────────────
def _send_terms(api: MessagingApi, reply_token: str):
    bubble = {
        "type": "bubble",
        "body": {
            "type":"box","layout":"vertical","spacing":"sm",
            "contents":[
                {"type":"text","text":"請先詳閱《票速通服務條款》，同意後才能繼續","weight":"bold","size":"md"},
                {"type":"button","action":{"type":"uri","label":"查看條款PDF","uri":TOS_PDF_URL},
                 "style":"primary","color":"#00A4C1"}
            ]
        },
        "footer":{
            "type":"box","layout":"vertical","contents":[
                {"type":"button","action":{"type":"message","label":"✅ 我同意","text":TOS_CONFIRM_TEXT},"style":"primary"}
            ]
        }
    }
    api.reply_message(ReplyMessageRequest(
        reply_token=reply_token,
        messages=[FlexMessage(alt_text="請先同意條款", contents=FlexContainer.from_dict(bubble))]
    ))

# ────────────────────────────
# MessageEvent
# ────────────────────────────
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    global auto_reply
    text = event.message.text.strip()
    uid = event.source.user_id

    with ApiClient(configuration) as cli:
        api = MessagingApi(cli)

        # 同意條款回覆
        if text == TOS_CONFIRM_TEXT:
            accepted_terms_users.add(uid)
            save_accepted_users()
            _safe_reply(api, event.reply_token,
                        "✅ 感謝同意！請重新點「填寫預訂單」開始預約。")
            return

        # 演唱會代操
        if text == "[!!!]演唱會代操":
            carousel = FlexContainer.from_dict({"type":"carousel","contents":CONCERT_BUBBLES})
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=KEYWORD_REPLIES[text]),
                    FlexMessage(alt_text="演唱會列表", contents=carousel)
                ]
            ))
            return

        # 互動教學
        if text == "[!!!]票速通使用教學":
            msg = TextMessage(
                text="📘 您想要進一步了解什麼？",
                quick_reply=QuickReply(items=[
                    QuickReplyButton(action=MessageAction(label="常見Q&A", text="教學：常見Q&A")),
                    QuickReplyButton(action=MessageAction(label="預約演唱會教學", text="教學：預約演唱會")),
                    QuickReplyButton(action=MessageAction(label="集點卡是什麼？", text="教學：集點卡")),
                    QuickReplyButton(action=MessageAction(label="我都學會了", text="教學：完成")),
                ])
            )
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[msg]))
            return

        # 教學選項
        if text == "教學：常見Q&A":
            _safe_reply(api, event.reply_token,
                        "🧾 常見Q&A：\nQ：代操費用？\nA：只收服務費，不加價。\nQ：付款方式？\nA：LINE Pay／街口等。\nQ：如何證明？\nA：訂單截圖+手寫時間。")
            return
        if text == "教學：預約演唱會":
            _safe_reply(api, event.reply_token,
                        "🎟️ 請於「演唱會代操」點「填寫預訂單」，範例：「我要預訂：TWICE」")
            return
        if text == "教學：集點卡":
            _safe_reply(api, event.reply_token,
                        "💳 集點卡：每筆代操累一點，3 點兌 50 元。")
            return
        if text == "教學：完成":
            _safe_reply(api, event.reply_token,
                        "🎉 已完成教學！隨時詢客服。")
            return

        # 其他關鍵字
        if text in KEYWORD_REPLIES:
            _safe_reply(api, event.reply_token, KEYWORD_REPLIES[text])
            return

        # 填寫預訂單（僅此時檢查條款）
        if text.startswith("我要預訂："):
            if uid not in accepted_terms_users:
                _send_terms(api, event.reply_token)
                return
            if uid in submitted_users:
                _safe_reply(api, event.reply_token,
                            "⚠️ 您已填寫過訂單，如需修改請聯絡客服。")
            else:
                submitted_users.add(uid)
                _safe_reply(api, event.reply_token,
                            "請填寫：\n演唱會：\n日期：\n票價：\n張數（上限4張）：")
            return

        # 系統自動回覆切換
        if text == "[系統]開啟自動回應" and uid in manager_user_ids:
            auto_reply = True
            _safe_reply(api, event.reply_token, "✅ 自動回應已開啟")
            return
        if text == "[系統]關閉自動回應" and uid in manager_user_ids:
            auto_reply = False
            _safe_reply(api, event.reply_token, "🛑 自動回應已關閉")
            return

        # 自動回覆
        if auto_reply:
            _safe_reply(api, event.reply_token,
                        "[@票速通] 小編暫時不在，請留言稍候。")

# ────────────────────────────
# 安全回覆
# ────────────────────────────
def _safe_reply(api: MessagingApi, reply_token: str, message):
    try:
        if isinstance(message, str):
            api.reply_message(ReplyMessageRequest(
                reply_token=reply_token, messages=[TextMessage(text=message)]))
        else:
            api.reply_message(ReplyMessageRequest(
                reply_token=reply_token, messages=[message]))
    except Exception as e:
        logging.error(f"[Reply 失敗] {e}")

if __name__ == "__main__":
    app.run("0.0.0.0", int(os.environ.get("PORT", 5001)), debug=True)
