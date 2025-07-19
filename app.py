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
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ────────────────────────────
# Flask
# ────────────────────────────
app = Flask(__name__)

# ────────────────────────────
# LINE SDK  (使用環境變數)
# ────────────────────────────
ACCESS_TOKEN   = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]

configuration = Configuration(access_token=ACCESS_TOKEN)
handler       = WebhookHandler(CHANNEL_SECRET)

# 若需管理指令，可保留；否則可刪除
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
    "[!!!]售票規則是甚麼？": "【@票速通 售票規則】 ...",
    "[!!!]高鐵票搶票": "【@票速通 高鐵訂票委託單】 ...",
    "[!!!]演唱會代操": "😍 目前可預約 2025 演唱會如下： ...",
}

# ────────────────────────────
# 狀態
# ────────────────────────────
accepted_terms_users: set[str] = set()
submitted_users: set[str]      = set()
auto_reply = False

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
# 共用：送服務條款 Bubble（僅 reply，用不到 push）
# ────────────────────────────
def _send_terms(api: MessagingApi, reply_token: str):
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {"type": "text", "text": "請先詳閱《票速通服務條款》", "weight": "bold", "size": "md"},
                {"type": "button",
                 "action": {"type": "uri", "label": "開啟 PDF", "uri": TOS_PDF_URL},
                 "style": "primary", "color": "#00A4C1"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "button",
                 "action": {"type": "message", "label": "✅ 我同意", "text": TOS_CONFIRM_TEXT},
                 "style": "primary"}
            ]
        }
    }
    msg = FlexMessage(
        alt_text="請先詳閱票速通服務條款",
        contents=FlexContainer.from_dict(bubble)
    )
    api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[msg]))

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

        # 條款同意檢查
        if uid not in accepted_terms_users:
            if text == TOS_CONFIRM_TEXT:
                accepted_terms_users.add(uid)
                _safe_reply(api, event.reply_token, "✅ 已收到您的同意，歡迎使用票速通！")
            else:
                _send_terms(api, reply_token=event.reply_token)
            return

        # 關鍵字回應
        if text in KEYWORD_REPLIES:
            _safe_reply(api, event.reply_token, KEYWORD_REPLIES[text])
            return

        # 系統管理：開/關自動回覆
        if text == "[系統]開啟自動回應" and uid in manager_user_ids:
            auto_reply = True
            _safe_reply(api, event.reply_token, "✅ 自動回應已開啟")
            return
        if text == "[系統]關閉自動回應" and uid in manager_user_ids:
            auto_reply = False
            _safe_reply(api, event.reply_token, "🛑 自動回應已關閉")
            return

        # 其它指令（預訂流程、演唱會清單…）可在此擴充

        # 不在家自動回覆
        if auto_reply:
            _safe_reply(api, event.reply_token, "[@票速通 通知您] 小編暫時不在，請留言稍候回覆。")

# ────────────────────────────
# 共用：安全回覆
# ────────────────────────────
def _safe_reply(api: MessagingApi, reply_token: str, message):
    try:
        api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=message)] if isinstance(message, str) else [message]
            )
        )
    except Exception as e:
        logging.error(f"[Reply 失敗] {e}")

# ────────────────────────────
# Run (本地測試)
# ────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run("0.0.0.0", port, debug=True)
