# app.py — 票速通 LINE Bot  (2025-07-19)

import os, logging
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage,
    FlexMessage, FlexContainer
)
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
ACCESS_TOKEN   = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]

configuration = Configuration(access_token=ACCESS_TOKEN)
handler       = WebhookHandler(CHANNEL_SECRET)

boss_user_id     = os.environ.get("BOSS_USER_ID", "U016da51eeb42b435ebe3a22442c97bb1")
manager_user_ids = {boss_user_id}

# ────────────────────────────
# 條款常數
# ────────────────────────────
TOS_VERSION      = "v1"
TOS_PDF_URL      = "https://fticket-botv1.onrender.com/static/tos_privacy_v1.pdf"
TOS_CONFIRM_TEXT = f"我同意票速通條款{TOS_VERSION}"

# ────────────────────────────
# 關鍵字回應
# ────────────────────────────
KEYWORD_REPLIES = {
    "[!!!]售票規則是甚麼？": "【@票速通 售票規則】 ... (此處省略，內容同原檔)",
    "[!!!]高鐵票搶票":      "【@票速通 高鐵訂票委託單】 ... (同原檔)",
    "[!!!]演唱會代操":      "😍 目前可預約 2025 演唱會如下： ... (同原檔)",
}

# ────────────────────────────
# 狀態
# ────────────────────────────
accepted_terms_users: set[str] = set()
submitted_users: set[str]      = set()
auto_reply = False

# ═════════════════════════════════════════════
# 🆕  演唱會 Bubble 產生器
# ═════════════════════════════════════════════
def _one_row(label: str, value: str):
    return {
        "type": "box",
        "layout": "baseline",
        "contents": [
            {"type": "text", "text": label, "size": "sm",
             "color": "#aaaaaa", "flex": 1},
            {"type": "text", "text": value, "size": "sm",
             "color": "#666666", "wrap": True, "flex": 4}
        ]
    }

def create_bubble(title, date, location, price, system,
                  image_url, artist_keyword, badge_text="NEW"):
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [{
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {"type": "image", "url": image_url,
                     "size": "full", "aspectMode": "cover",
                     "aspectRatio": "30:25", "flex": 1},
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "position": "absolute",
                        "offsetStart": "18px",
                        "offsetTop": "18px",
                        "width": "72px",
                        "height": "28px",
                        "backgroundColor": "#EC3D44",
                        "cornerRadius": "100px",
                        "paddingAll": "2px",
                        "contents": [{
                            "type": "text", "text": badge_text,
                            "size": "xs", "color": "#ffffff",
                            "align": "center", "gravity": "center"
                        }]
                    }]
            }],
            "paddingAll": "0px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {"type": "text", "text": title, "wrap": True,
                 "weight": "bold", "gravity": "center", "size": "xl"},
                {"type": "box", "layout": "vertical", "spacing": "sm",
                 "contents": [
                     _one_row("日期", date),
                     _one_row("地點", location),
                     _one_row("票價", price),
                     _one_row("系統", system)
                 ]}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [{
                "type": "button",
                "action": {"type": "message",
                           "label": "填寫預訂單",
                           "text": f"我要預訂：{artist_keyword}"},
                "style": "primary",
                "color": "#00A4C1"
            }]
        }
    }

# 會用到的 Bubble 清單（可自行增刪）
CONCERT_BUBBLES = [
    create_bubble("TWICE THIS IS FOR WORLD TOUR PART1 IN KAOHSIUNG",
                  "Coming soon...", "Coming soon...", "Coming soon...",
                  "Coming soon...",
                  "https://img9.uploadhouse.com/fileuploads/32011/32011699f3f6ed545f4c10e2c725a17104ab2e9c.png",
                  "TWICE", "HOT🔥"),
    create_bubble("台新銀行周興哲 Odyssey 旅程巡迴演唱會 臺北返場",
                  "2025/9/26–28 19:30", "臺北小巨蛋",
                  "4,280 / 3,880 / 3,480 / 2,880 / 1,880 / 1,280 / 800",
                  "KKTIX",
                  "https://img7.uploadhouse.com/fileuploads/32041/320416079d76281470f509aafbfc8409d9141f90.png",
                  "周興哲", "HOT🔥"),
    create_bubble("家家 月部落 Fly to the moon 你給我的月不落現場",
                  "9/27 19:00", "Legacy Taipei",
                  "NT 1800（全區座席）/ NT 900（身障席）",
                  "拓元售票",
                  "https://img4.uploadhouse.com/fileuploads/32041/32041604c5fee787f6b7ec43d0d3fe8991ae995d.png",
                  "家家", "HOT🔥"),
    # …其餘 Bubble 可自行加入
]

# ────────────────────────────
# Webhook 入口
# ────────────────────────────
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ────────────────────────────
# 共用：條款 Bubble（reply 版）
# ────────────────────────────
def _send_terms(api: MessagingApi, reply_token: str):
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "請先詳閱《票速通服務條款》",
                 "weight": "bold", "size": "md"},
                {"type": "button",
                 "action": {"type": "uri", "label": "開啟 PDF", "uri": TOS_PDF_URL},
                 "style": "primary", "color": "#00A4C1"}
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical",
            "contents": [{
                "type": "button",
                "action": {"type": "message",
                           "label": "✅ 我同意", "text": TOS_CONFIRM_TEXT},
                "style": "primary"}]
        }
    }
    api.reply_message(ReplyMessageRequest(
        reply_token=reply_token,
        messages=[FlexMessage("請先詳閱服務條款",
                              FlexContainer.from_dict(bubble))]))

# ────────────────────────────
# MessageEvent
# ────────────────────────────
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    global auto_reply
    text = event.message.text.strip()
    uid  = event.source.user_id

    with ApiClient(configuration) as cli:
        api = MessagingApi(cli)

        # 1) 條款同意檢查
        if uid not in accepted_terms_users:
            if text == TOS_CONFIRM_TEXT:
                accepted_terms_users.add(uid)
                _safe_reply(api, event.reply_token, "✅ 已收到您的同意，歡迎使用票速通！")
            else:
                _send_terms(api, reply_token=event.reply_token)
            return

        # 2) 關鍵字回應
        if text in KEYWORD_REPLIES:
            _safe_reply(api, event.reply_token, KEYWORD_REPLIES[text])
            return

        # 3) 「我要預訂：」流程
        if text.startswith("我要預訂："):
            if uid in submitted_users:
                _safe_reply(api, event.reply_token,
                            "⚠️ 您已填寫過訂單，如需修改請聯絡客服。")
            else:
                submitted_users.add(uid)
                _safe_reply(api, event.reply_token,
                            "請填寫以下訂單資訊：\n"
                            "演唱會節目：\n"
                            "演唱會日期：\n"
                            "票價：\n"
                            "張數（上限四張）：")
            return

        # 4) 演唱會 Bubble Carousel
        if text == "[!!!]演唱會代操":
            carousel = {"type": "carousel", "contents": CONCERT_BUBBLES}
            _safe_reply(api, event.reply_token,
                        FlexMessage("演唱會節目資訊，歡迎私訊預訂！",
                                    FlexContainer.from_dict(carousel)))
            return

        # 5) 系統管理：開/關自動回覆
        if text == "[系統]開啟自動回應" and uid in manager_user_ids:
            auto_reply = True
            _safe_reply(api, event.reply_token, "✅ 自動回應已開啟")
            return
        if text == "[系統]關閉自動回應" and uid in manager_user_ids:
            auto_reply = False
            _safe_reply(api, event.reply_token, "🛑 自動回應已關閉")
            return

        # 6) 不在家自動回覆
        if auto_reply:
            _safe_reply(api, event.reply_token,
                        "[@票速通 通知您] 小編暫時不在，請留言稍候回覆。")

# ────────────────────────────
# 共用：安全回覆
# ────────────────────────────
def _safe_reply(api: MessagingApi, reply_token: str, message):
    try:
        if isinstance(message, str):
            api.reply_message(ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=message)]))
        else:
            api.reply_message(ReplyMessageRequest(
                reply_token=reply_token, messages=[message]))
    except Exception as e:
        logging.error(f"[Reply 失敗] {e}")

# ────────────────────────────
# Run (本地測試)
# ────────────────────────────
if __name__ == "__main__":
    app.run("0.0.0.0", int(os.environ.get("PORT", 5001)), debug=True)
