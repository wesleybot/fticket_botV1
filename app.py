# app.py — 票速通 LINE Bot  (2025-07-25)

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
# LINE SDK  (环境变量)
# ────────────────────────────
ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

boss_user_id = os.environ.get("BOSS_USER_ID", "")
manager_user_ids = {boss_user_id} if boss_user_id else set()

# ────────────────────────────
# 条款常数
# ────────────────────────────
TOS_VERSION = "v1"
TOS_PDF_URL = "https://fticket-botv1.onrender.com/static/tos_privacy_v1.pdf"
TOS_CONFIRM_TEXT = f"我同意，並了解自我權益關於票速通條款{TOS_VERSION}"

# ────────────────────────────
# 用户同意列表文件
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
# 状态
# ────────────────────────────
accepted_terms_users: set[str] = load_accepted_users()
submitted_users: set[str] = set()
auto_reply = False

# ────────────────────────────
# 关键字回应
# ────────────────────────────
KEYWORD_REPLIES = {
    "[!!!]售票規則是甚麼？": (
        "【@票速通 售票規則】\n"
        "🍀🍀🍀本官方成立初衷「幫追星人代買到演唱會門票」一律以「誠信」為主🍀🍀🍀 \n\n"
        
        "流程如下：\n"
        "1️⃣ 點選「演唱會代購購票」選擇您想要的演唱會節目，填寫預訂單\n記得先同意條款後，以便繼續啟用服務唷！\n"
        "2️⃣ 請耐心等候小編回覆，會進行登記。\n"
        "3️⃣ 購票當天，會提前聯繫您，確保您在購票後在，並在成功後通知您。\n"
        "4️⃣ 完成您所委託的票券後，才會進行付款動作。\n\n"
        "⚠️ 注意事項：\n"
        "➣ 一切費用，都是等到有確實「完成您所委託的票券」才進行付款。\n"
        "➣ 代購成功後，請在規定時間內付款。\n"
        "➣ 若未能「完成您所委託的票券」則不收取任何費用。\n"
        "➣ 若有任何問題，請隨時聯絡我們的客服。\n\n"
        "💬 如有疑問，請點「[!!!]票速通使用教學」了解更多。"
    ),
    "[!!!]演唱會代操": (
        "目前可預約 2025 演唱會：\n"
        "➣ 11/22 TWICE THIS IS FOR WORLD TOUR PART1 IN KAOHSIUNG\n"
        "➣ 9/27 家家 Fly to the moon\n"
        "➣ 11/1-2 G-Dragon《Übermensch》IN 大巨蛋演唱會\n"
        "➣ 11/22-23 國泰世華銀行\n伍佰 ＆ China Blue Rock Star2演唱會-高雄站\n"
        "➣ 鄧紫棋演唱會\n"
        "➣ 蔡依林演唱會\n\n"
        "✓ 一切費用，都是等到有確實「完成您所委託的票券」才進行付款。全網最低價！請點下方「演唱會代購購票」開始。"
    ),
}

# ═════════════════════════════════════════════
# Bubble 生成器
# ═════════════════════════════════════════════


def _one_row(label: str, value: str):
    return {
        "type": "box", "layout": "baseline", "contents": [
            {"type": "text", "text": label, "size": "sm",
                "color": "#aaaaaa", "flex": 1},
            {"type": "text", "text": value, "size": "sm",
                "color": "#666666", "wrap": True, "flex": 4},
        ]
    }


def create_bubble(title, date, location, price, system,
                image_url, artist_keyword, badge_text="NEW"):
    return {
        "type": "bubble",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "image", "url": image_url, "size": "full",
                    "aspectMode": "cover", "aspectRatio": "30:25", "flex": 1},
                {"type": "box", "layout": "horizontal", "position": "absolute",
                "offsetStart": "18px", "offsetTop": "18px", "width": "72px", "height": "28px",
                "backgroundColor": "#EC3D44", "cornerRadius": "100px", "paddingAll": "2px",
                "contents": [{"type": "text", "text": badge_text, "size": "xs", "color": "#ffffff", "align": "center", "gravity": "center"}]}
            ]}
        ], "paddingAll": "0px"},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "text", "text": title, "wrap": True,
                "weight": "bold", "gravity": "center", "size": "xl"},
            {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                _one_row("日期", date),
                _one_row("地點", location),
                _one_row("票價", price),
                _one_row("系統", system),
            ]}
        ]},
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "button", "action": {"type": "message", "label": "填寫預訂單", "text": f"我要預訂：{artist_keyword}"},
            "style": "primary", "color": "#00A4C1"}
        ]}
    }


CONCERT_BUBBLES = [
    create_bubble(
                "TWICE THIS IS FOR WORLD TOUR PART1 IN KAOHSIUNG",
                "2025/11/22（六）", 
                "Comimg soon...",
                "Comimg soon...",
                "Comimg soon...",
                "https://img9.uploadhouse.com/fileuploads/32011/32011699f3f6ed545f4c10e2c725a17104ab2e9c.png",
                "TWICE",
                badge_text="HOT🔥"
            ),
    create_bubble(
                "家家 月部落 Fly to the moon 你給我的月不落現場",
                "9.27 Sat. 19:00", 
                "Legacy Taipei 音樂展演空間",
                "NT. 1800（全區座席）/ NT. 900（身障席）",
                "拓元售票系統",
                "https://img4.uploadhouse.com/fileuploads/32041/32041604c5fee787f6b7ec43d0d3fe8991ae995d.png",
                "家家",
                badge_text="HOT🔥"
            ),
    create_bubble(
                "國泰世華銀行\n伍佰 ＆ China Blue Rock Star2演唱會-高雄站",
                "11.22 (六) 19:30\n11.23 (日) 19:00", 
                "高雄巨蛋",
                "800/1800/2800/3200/3800/4200(實名制抽選/全座席)",
                "拓元售票系統",
                "https://img5.uploadhouse.com/fileuploads/31934/319346856d24e3358b522bc1d8aa65825c41d420.png",
                "伍佰",
                badge_text="HOT🔥"
            ),
    create_bubble(
                "G-Dragon《Übermensch》IN 大巨蛋演唱會",
                "2025/11/1、2025/11/2 （暫定）", 
                "台北大巨蛋（暫定）",
                "Comimg soon...",
                "Comimg soon...",
                "https://img4.uploadhouse.com/fileuploads/32056/320564443116af1e32d4e7f88b5945bff73aa8ca.png",
                "GD",
                badge_text="即將來🔥"
            ),
    create_bubble(
                "鄧紫棋演唱會",
                "Comimg soon...", 
                "Comimg soon...",
                "Comimg soon...",
                "Comimg soon...",
                "https://img1.uploadhouse.com/fileuploads/31980/31980371b9850a14e08ec5f39c646f7b5068e008.png",
                "鄧紫棋",
                badge_text="即將來🔥"
            ),
    create_bubble(
                "蔡依林演唱會", 
                "Comimg soon...", 
                "Comimg soon...", 
                "Coming soon...", 
                "Comimg soon...", 
                "https://img7.uploadhouse.com/fileuploads/31934/319347074ebade93a4a6310dec72f08996dc2af1.png", 
                "蔡依林",
                badge_text="即將來🔥"
            )
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
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "text", "text": "請先詳閱《票速通服務條款》，同意後才能繼續使用服務。",
                "weight": "bold", "size": "md"},
            {"type": "button", "action": {"type": "uri", "label": "點我查閱服務條款PDF", "uri": TOS_PDF_URL},
             "style": "primary", "color": "#00A4C1"}
        ]},
        "footer": {"type": "box", "layout": "vertical", "contents": [
            {"type": "button", "action": {"type": "message", "label": "✅ 我同意，並了解自我權益",
                                          "text": TOS_CONFIRM_TEXT}, "style": "primary"}
        ]}
    }
    api.reply_message(ReplyMessageRequest(
        reply_token=reply_token,
        messages=[FlexMessage(
            alt_text="請先詳閱並同意《票速通服務條款》繼續服務。", contents=FlexContainer.from_dict(bubble))]
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

        # ① 同意條款
        if text == TOS_CONFIRM_TEXT:
            accepted_terms_users.add(uid)
            save_accepted_users()
            _safe_reply(api, event.reply_token,
                        "✅ 已收到您的同意條款！並了解自我權益。請重新點「填寫預訂單」開始預約。")
            return

        # ② 演唱會代操
        if text == "[!!!]演唱會代操":
            carousel = FlexContainer.from_dict(
                {"type": "carousel", "contents": CONCERT_BUBBLES})
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=KEYWORD_REPLIES[text]),
                    FlexMessage(alt_text="演唱會列表", contents=carousel)
                ]
            ))
            return

        # ③ 互動教學（FlexMessage 四按鈕）
        if text == "[!!!]票速通使用教學":
            teach = {
                "type": "bubble",
                "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                    {"type": "text", "text": "📘 您想要進一步了解什麼？",
                        "weight": "bold", "size": "md"}
                ]},
                "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                    {"type": "button", "action": {"type": "message",
                                                  "label": "常見Q&A", "text": "常見問題Q&A"}, "style": "primary"},
                    {"type": "button", "action": {"type": "message",
                                                  "label": "預約演唱會教學", "text": "怎麼預約演唱會？"}, "style": "primary"},
                    {"type": "button", "action": {"type": "message",
                                                  "label": "集點卡是什麼？", "text": "集點卡可以幹嘛？"}, "style": "primary"},
                    {"type": "button", "action": {"type": "message",
                                                  "label": "我都學會了", "text": "我都會了！"}, "style": "primary"},
                ]}
            }
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(
                    alt_text="互動教學", contents=FlexContainer.from_dict(teach))]
            ))
            return

        # 教學選項
        if text == "常見問題Q&A":
            _safe_reply(api, event.reply_token,
                        "🧾 常見Q&A：\nQ：代操費用？\nA：只收服務費，不加價。")
            return
        if text == "怎麼預約演唱會？":
            _safe_reply(api, event.reply_token,
                        "🎟️ 請在「演唱會代操」點「填寫預訂單」，如「我要預訂：TWICE」")
            return
        if text == "集點卡可以幹嘛？":
            _safe_reply(api, event.reply_token, "💳 集點卡：累 1 點，3 點兌 50 元。")
            return
        if text == "我都會了！":
            _safe_reply(api, event.reply_token, "🎉 已完成教學，有問題再聯絡客服！")
            return

        # ④ 其他關鍵字
        if text in KEYWORD_REPLIES:
            _safe_reply(api, event.reply_token, KEYWORD_REPLIES[text])
            return

        # ⑤ 填寫預訂單（此時檢查條款）
        if text.startswith("我要預訂："):
            if uid not in accepted_terms_users:
                _send_terms(api, event.reply_token)
                return
            if uid in submitted_users:
                _safe_reply(api, event.reply_token, "⚠️ 您已填寫過訂單，如需修改請聯絡客服。")
            else:
                submitted_users.add(uid)
                _safe_reply(api, event.reply_token,
                            "請填寫：\n演唱會：\n日期：\n票價：\n張數（上限4張）：")
            return

        # ⑥ 系統自動回覆切換
        if text == "[系統]開啟自動回應" and uid in manager_user_ids:
            auto_reply = True
            _safe_reply(api, event.reply_token, "✅ 自動回應已開啟")
            return
        if text == "[系統]關閉自動回應" and uid in manager_user_ids:
            auto_reply = False
            _safe_reply(api, event.reply_token, "🛑 自動回應已關閉")
            return

        # ⑦ 自動回覆
        if auto_reply:
            _safe_reply(api, event.reply_token, "[@票速通] 小編暫時不在，請留言稍候。")

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
