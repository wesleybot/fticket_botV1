# app.py — 票速通 LINE Bot  (2025-07-19)

import os
import logging
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
# 關鍵字回應
# ────────────────────────────
KEYWORD_REPLIES = {
    "[!!!]售票規則是甚麼？": (
        "【@票速通 售票規則】\n"
        "🍀🍀🍀本官方成立初心「幫追星人買到演唱會門票」一律以「誠信」為主🍀🍀🍀\n\n"
        "若您想詢問演唱會場次，請按選單【演唱會代操搶票登記】。\n"
        "若有其他問題，歡迎洽詢客服。\n\n"
        "〖常見Q&A〗"
        "Q：代操費用怎麼算？\n"
        "A：所有代操費用以「一筆委託」計算，詢問客服想要的演唱會，將報價給您，且並費用而非計入票價加價當中。\n"
        "Q：票款與代操費如何支付？\n"
        "A：售票系統虛擬帳號 / iPassMoney 一卡通轉帳 / 街口支付轉帳 / 支付寶轉帳\n"
        "Q：如何證明真的搶到票？\n"
        "A：購票完成後，將與訂單拍照，並手寫當前時間，讓您安心。\n"
        "Q：取票方式？\n"
        "A：依照售票系統規定時間，也可選擇帳號給您保管，直到您取票為止。詳細請參《票速通服務條款》\n"
    ),
    "[!!!]高鐵票搶票": (
        "【@票速通 高鐵訂票委託單】\n"
        "出發站：\n"
        "抵達站：\n"
        "出發日期：\n"
        "出發時間：\n"
        "張數（全票為主）：\n"
        "車次需求（可留空）：\n\n"
        "請依上列格式填寫，小助手將盡速回覆，謝謝！"
    ),
    "[!!!]演唱會代操": (
        "😍 目前可預約 2025 演唱會如下：😍\n\n"
        "➣ 11/22 TWICE THIS IS FOR WORLD TOUR PART1 IN KAOHSIUNG\n"
        "➣ 9/26-28 台新銀行周興哲 Odyssey 旅程巡迴演唱會 臺北返場\n"
        "➣ 9/27 家家 月部落 Fly to the moon 你給我的月不落現場\n"
        "➣ 11/22-23 伍佰 Wu Bai & China Blue Rock Star 2 in 高雄\n\n"
        "✓ 搶票成功後才收代操費（全網最低價！）\n"
        "請點選選單「演唱會代操」並填寫委託單，小助手將回覆。"
    ),
}

# ────────────────────────────
# 狀態
# ────────────────────────────
accepted_terms_users: set[str] = set()
submitted_users: set[str] = set()
auto_reply = False

# ═════════════════════════════════════════════
# Bubble 產生器
# ═════════════════════════════════════════════


def _one_row(label: str, value: str):
    return {"type": "box", "layout": "baseline", "contents": [
            {"type": "text", "text": label, "size": "sm",
             "color": "#aaaaaa", "flex": 1},
            {"type": "text", "text": value, "size": "sm",
             "color": "#666666", "wrap": True, "flex": 4}]}


def create_bubble(title, date, location, price, system,
                  image_url, artist_keyword, badge_text="NEW"):
    return {
        "type": "bubble",
        "header": {
            "type": "box", "layout": "vertical", "contents": [{
                "type": "box", "layout": "horizontal", "contents": [
                    {"type": "image", "url": image_url,
                     "size": "full", "aspectMode": "cover",
                     "aspectRatio": "30:25", "flex": 1},
                    {"type": "box", "layout": "horizontal", "position": "absolute",
                     "offsetStart": "18px", "offsetTop": "18px",
                     "width": "72px", "height": "28px",
                     "backgroundColor": "#EC3D44", "cornerRadius": "100px",
                     "paddingAll": "2px",
                     "contents": [{"type": "text", "text": badge_text,
                                   "size": "xs", "color": "#ffffff",
                                   "align": "center", "gravity": "center"}]}]}],
            "paddingAll": "0px"},
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": title, "wrap": True,
                 "weight": "bold", "gravity": "center", "size": "xl"},
                {"type": "box", "layout": "vertical", "spacing": "sm",
                 "contents": [
                     _one_row("日期", date),
                     _one_row("地點", location),
                     _one_row("票價", price),
                     _one_row("系統", system)]}]},
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [{
                "type": "button",
                "action": {"type": "message", "label": "填寫預訂單",
                           "text": f"我要預訂：{artist_keyword}"},
                "style": "primary", "color": "#00A4C1"}]}
    }


CONCERT_BUBBLES = [
    create_bubble("TWICE THIS IS FOR WORLD TOUR PART1 IN KAOHSIUNG",
                  "Coming soon…", "Coming soon…", "Coming soon…", "Coming soon…",
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
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "請先詳閱《票速通服務條款》同意後即可開始使用",
                 "weight": "bold", "size": "md"},
                {"type": "button",
                 "action": {"type": "uri", "label": "點我查閱服務條款PDF", "uri": TOS_PDF_URL},
                 "style": "primary", "color": "#00A4C1"}]},
        "footer": {
            "type": "box", "layout": "vertical",
            "contents": [{
                "type": "button",
                "action": {"type": "message", "label": "✅ 我同意，並了解自我權益",
                           "text": TOS_CONFIRM_TEXT},
                "style": "primary"}]}}
    api.reply_message(ReplyMessageRequest(
        reply_token=reply_token,
        messages=[FlexMessage(
            alt_text="請先詳閱票速通服務條款，即可開始使用功能",
            contents=FlexContainer.from_dict(bubble))]))

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

        # ① 條款
        if uid not in accepted_terms_users:
            if text == TOS_CONFIRM_TEXT:
                accepted_terms_users.add(uid)
                _safe_reply(api, event.reply_token,
                            "✅ 已收到您的同意條款，並了解自我權益，歡迎使用票速通！")
            else:
                _send_terms(api, event.reply_token)
            return

        # ② 指令：演唱會代操（文字 + Carousel）
        if text == "[!!!]演唱會代操":
            carousel = FlexContainer.from_dict({
                "type": "carousel", "contents": CONCERT_BUBBLES})
            messages = [
                TextMessage(text=KEYWORD_REPLIES[text]),
                FlexMessage(
                    alt_text="演唱會節目資訊，歡迎私訊預訂！",
                    contents=carousel)
            ]
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token, messages=messages))
            return

        # ③ 其他關鍵字
        if text in KEYWORD_REPLIES:
            _safe_reply(api, event.reply_token, KEYWORD_REPLIES[text])
            return

        # ④ 預訂
        if text.startswith("我要預訂："):
            if uid in submitted_users:
                _safe_reply(api, event.reply_token, "⚠️ 您已填寫過訂單，如需修改請聯絡客服。")
            else:
                submitted_users.add(uid)
                _safe_reply(api, event.reply_token,
                            "請填寫以下訂單資訊：\n演唱會節目：\n演唱會日期：\n票價：\n張數（上限四張）：")
            return

        # ⑤ 自動回覆切換
        if text == "[系統]開啟自動回應" and uid in manager_user_ids:
            auto_reply = True
            _safe_reply(api, event.reply_token, "✅ 自動回應已開啟")
            return
        if text == "[系統]關閉自動回應" and uid in manager_user_ids:
            auto_reply = False
            _safe_reply(api, event.reply_token, "🛑 自動回應已關閉")
            return

        # ⑥ 自動回覆
        if auto_reply:
            _safe_reply(api, event.reply_token, "[@票速通 通知您] 小編暫時不在，請留言稍候回覆。")

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
