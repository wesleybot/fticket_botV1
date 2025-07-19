# app.py  — 票速通 LINE Bot  (2025-07-19)

import os, logging, re
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage,
    PushMessageRequest, FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ─────────────────────────────────────────────
# Flask
# ─────────────────────────────────────────────
app = Flask(__name__)

# ─────────────────────────────────────────────
# LINE SDK 設定（用環境變數）
# ─────────────────────────────────────────────
ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

boss_user_id = os.environ.get("BOSS_USER_ID", "U016da51eeb42b435ebe3a22442c97bb1")
manager_user_ids = {boss_user_id}

# ─────────────────────────────────────────────
# 條款常數
# ─────────────────────────────────────────────
TOS_VERSION = "v1"
TOS_PDF_URL = "https://fticket-botv1.onrender.com/static/tos_privacy_v1.pdf"
TOS_CONFIRM_TEXT = f"我同意票速通條款{TOS_VERSION}"

# ===== 🆕 歡迎訊息 & 關鍵字回應 =========================
WELCOME_TEMPLATE = (
    "【歡迎您{Nickname} 加入{AccountName}】\n"
    "我是小助手將會為您提供服務\n\n"
    "目前服務項目：\n"
    "✅ 高鐵代操作購買乘車票\n"
    "✅ 各大演唱會代操作搶票\n\n"
    "請點選「聊天選單」即可開始操作。\n\n"
    "😍 目前可預約 2025 演唱會如下：😍\n"
    "➣ TWICE THIS IS FOR WORLD TOUR PART1 IN KAOHSIUNG\n"
    "➣ 台新銀行周興哲 Odyssey 旅程巡迴演唱會 臺北返場\n"
    "➣ 家家 月部落 Fly to the moon 你給我的月不落現場\n"
    "➣ 伍佰 Wu Bai & China Blue Rock Star 2 世界巡迴演唱會 in 高雄\n"
    "➣ 鄧紫棋 演唱會\n"
    "➣ 蔡依林 演唱會（預計年底）\n\n"
    "✓ 演唱會搶票成功後，才會收取代操費（全網最低價！！！）\n"
    "倘若想預定門票請點選選單「演唱會代操」填寫正確格式，等待小助手回覆。\n"
    "（不一定百分百開，但有消息會開演唱會。）"
)

KEYWORD_REPLIES = {
    "[!!!]售票規則是甚麼？": (
        "【@票速通 售票規則】\n"
        "🍀🍀🍀本官方成立初心「幫追星人買到演唱會門票」一律以「誠信」為主🍀🍀🍀\n\n"
        "若您想詢問相關國內、外演唱會場次，"
        "直接按下選單【演唱會代操搶票登記】進行預定。\n\n"
        "若有其他相關演唱會...等問題，歡迎洽詢本官方賴 @票速通\n"
        "😳！請自行評估，建議確認誠信再來！🎉\n\n"
        "哈囉我是小助手，現在我來為你講解價格、後續取票問題！\n"
        "Q：代操費用到底怎麼計算？\n"
        "A：所有代操費用報價都是以「一筆」計算，而非一張算一次代操費。\n"
        "Q：委託搶到票，該怎麼支付？\n"
        "A：若搶票系統可 ATM 匯款，我們會給官方售票帳號，可信度較高。\n"
        "Q：誰知道你們搶票是不是真的？\n"
        "A：主頁/IG/Threads 都有搶票紀錄貼文，請誠心相信我們！\n"
        "Q：該怎麼取票？\n"
        "A：依各演唱會公告領票，KKTIX 多可直接領；拓元約開場前五天。\n"
        "！！！一律以誠信為主，我們信任您，您也應該信任我們！！！\n\n"
        "Q：遇到取消或退票？\n"
        "A：如非官方退票或演出取消，概不退換。\n\n"
        "😘任何問題我們都在，隨時為您處理，請不要擔心🎉"
    ),
    "[!!!]高鐵票搶票": (
        "【@票速通 高鐵訂票委託單】\n"
        "出發站：\n"
        "抵達站：\n"
        "出發日期：\n"
        "出發時間：\n"
        "張數（全票為主）：\n"
        "車次需求（可留空）：\n\n"
        "請依照委託單內容填寫，我們將盡速回覆，謝謝！😍"
    ),
    "[!!!]演唱會代操": (
        "😍 目前可預約 2025 演唱會如下：😍\n"
        "➣ TWICE THIS IS FOR WORLD TOUR PART1 IN KAOHSIUNG\n"
        "➣ 台新銀行周興哲 Odyssey 旅程巡迴演唱會 臺北返場\n"
        "➣ 家家 月部落 Fly to the moon 你給我的月不落現場\n"
        "➣ 伍佰 Wu Bai & China Blue Rock Star 2 世界巡迴演唱會 in 高雄\n"
        "➣ 鄧紫棋 演唱會\n"
        "➣ 蔡依林 演唱會（預計年底）\n\n"
        "✓ 演唱會搶票成功後，才會收取代操費（全網最低價！！！）\n"
        "倘若想預定門票請點選選單「演唱會代操」填寫正確格式，等待小助手回覆。\n"
        "（不一定百分百開，但有消息會開演唱會。）\n\n"
        "哈囉我是小助手，我又來跟你說話了～\n"
        "👉 請先點選「售票規則」了解詳細資訊，再耐心等老闆回覆唷！"
    ),
}

# ─────────────────────────────────────────────
# 全域狀態
# ─────────────────────────────────────────────
accepted_terms_users: set[str] = set()
submitted_users: set[str] = set()
auto_reply = False

# ─────────────────────────────────────────────
# Webhook 入口
# ─────────────────────────────────────────────
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ─────────────────────────────────────────────
# 共用：服務條款 Bubble
# ─────────────────────────────────────────────
def _send_terms(api: MessagingApi, reply_token: str | None = None, to_user: str | None = None):
    bubble_dict = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {"type": "text", "text": "請先詳閱《票速通服務條款》", "weight": "bold", "size": "md"},
                {
                    "type": "button",
                    "action": {"type": "uri", "label": "開啟 PDF", "uri": TOS_PDF_URL},
                    "style": "primary",
                    "color": "#00A4C1"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "✅ 我同意", "text": TOS_CONFIRM_TEXT},
                    "style": "primary"
                }
            ]
        }
    }
    msg = FlexMessage(alt_text="請先詳閱票速通服務條款", contents=FlexContainer.from_dict(bubble_dict))

    if reply_token:
        api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[msg]))
    elif to_user:
        api.push_message(PushMessageRequest(to=to_user, messages=[msg]))

# ─────────────────────────────────────────────
# FollowEvent：送條款＋歡迎訊息
# ─────────────────────────────────────────────
@handler.add(FollowEvent)
def handle_follow(event: FollowEvent):
    uid = event.source.user_id
    with ApiClient(configuration) as client:
        api = MessagingApi(client)

        # 1) 條款 Bubble
        _send_terms(api, to_user=uid)

        # 2) 歡迎訊息（取暱稱／帳號名）
        try:
            prof = api.get_profile(uid)
            nickname = prof.display_name
        except Exception:
            nickname = "朋友"

        # Replace template placeholder
        welcome_text = WELCOME_TEMPLATE.format(Nickname=nickname, AccountName="票速通")

        api.push_message(
            PushMessageRequest(to=uid, messages=[TextMessage(text=welcome_text)])
        )
        logging.info(f"Push welcome message to {uid}")

# ─────────────────────────────────────────────
# MessageEvent
# ─────────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    global auto_reply
    text = event.message.text.strip()
    uid = event.source.user_id

    with ApiClient(configuration) as client:
        api = MessagingApi(client)

        # ① 條款同意檢查
        if uid not in accepted_terms_users:
            if text == TOS_CONFIRM_TEXT:
                accepted_terms_users.add(uid)
                _safe_reply(api, event.reply_token, "✅ 已收到您的同意，歡迎使用票速通！")
            else:
                _send_terms(api, reply_token=event.reply_token)
            return

        # ② 關鍵字自動回應  ===== 🆕
        if text in KEYWORD_REPLIES:
            _safe_reply(api, event.reply_token, KEYWORD_REPLIES[text])
            return

        # ③ 系統管理指令
        if text == "[系統]開啟自動回應" and uid in manager_user_ids:
            auto_reply = True
            _safe_reply(api, event.reply_token, "✅ 自動回應已開啟")
            return
        if text == "[系統]關閉自動回應" and uid in manager_user_ids:
            auto_reply = False
            _safe_reply(api, event.reply_token, "🛑 自動回應已關閉")
            return

        # ④ 其他 ...（原本邏輯保留）
        # 你先前的預訂、演唱會 Bubble 內容在此略
        # ...

        # ⑤ 不在家自動回覆
        if auto_reply:
            _safe_reply(api, event.reply_token, "[@票速通 通知您] 小編暫時不在，請留言稍候回覆。")

# ─────────────────────────────────────────────
# 共用：安全回覆
# ─────────────────────────────────────────────
def _safe_reply(api: MessagingApi, reply_token: str, message):
    try:
        if isinstance(message, str):
            api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=message)]))
        else:
            api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[message]))
    except Exception as e:
        logging.error(f"[Reply 失敗] {e}")

# ─────────────────────────────────────────────
# Flask run (本地測試)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run("0.0.0.0", port, debug=True)
