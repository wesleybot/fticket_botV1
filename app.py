# app.py  -- Flask + LINE Messaging API v3
# 票速通：條款同意後才開放其他指令  (2025-07-19)

import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    PushMessageRequest,
    FlexMessage,
    FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# ─────────────────────────────────────────────
# Flask
# ─────────────────────────────────────────────
app = Flask(__name__)

# ─────────────────────────────────────────────
# LINE SDK 設定（建議改用環境變數）
# ─────────────────────────────────────────────
# LINE SDK 設定 —— 不要再塞硬字串，全部讀環境變數
ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


boss_user_id = os.environ.get(
    "BOSS_USER_ID", "U016da51eeb42b435ebe3a22442c97bb1"
)
manager_user_ids = {boss_user_id}          # 只有這些 UID 能開/關自動回覆

# ─────────────────────────────────────────────
# 條款常數
# ─────────────────────────────────────────────
TOS_VERSION = "v1"
TOS_PDF_URL = "https://fticket-botv1.onrender.com/static/%E7%A5%A8%E9%80%9F%E9%80%9A%20Ticket%20FastPass.pdf"   # ← 改成你的 PDF 連結
TOS_CONFIRM_TEXT = f"我同意票速通條款{TOS_VERSION}"

# ─────────────────────────────────────────────
# 全域狀態（記憶體快取；正式環境可換 DB）
# ─────────────────────────────────────────────
accepted_terms_users = set()   # 已按「我同意」的 UID
submitted_users = set()        # 已填過預訂單的 UID
auto_reply = False             # 是否開啟「不在家」訊息

# ─────────────────────────────────────────────
# Webhook 入口
# ─────────────────────────────────────────────


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# ─────────────────────────────────────────────
# 共用：送出「條款 PDF + 我同意」Bubble
# ─────────────────────────────────────────────


def _send_terms(line_bot_api, reply_token=None, to_user=None):
    bubble = FlexMessage(
        alt_text="請先詳閱票速通服務條款",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": "請先詳閱《票速通服務條款》",
                        "weight": "bold",
                        "size": "md",
                        "margin": "md"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "開啟 PDF",
                            "uri": TOS_PDF_URL
                        },
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
                        "action": {
                            "type": "message",
                            "label": "✅ 我同意",
                            "text": TOS_CONFIRM_TEXT
                        },
                        "style": "primary"
                    }
                ]
            }
        }
    )

    if reply_token:
        line_bot_api.reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[bubble])
        )
    elif to_user:
        line_bot_api.push_message(
            PushMessageRequest(to=to_user, messages=[bubble])
        )

# ─────────────────────────────────────────────
# FollowEvent：新好友先送條款
# ─────────────────────────────────────────────


@handler.add(FollowEvent)
def handle_follow(event: FollowEvent):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        _send_terms(line_bot_api, to_user=event.source.user_id)

# ─────────────────────────────────────────────
# 主要訊息處理
# ─────────────────────────────────────────────


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    global auto_reply
    text = event.message.text.strip()
    user_id = event.source.user_id

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # ── ① 條款同意檢查 ───────────────────
        if user_id not in accepted_terms_users:
            if text == TOS_CONFIRM_TEXT:
                accepted_terms_users.add(user_id)
                _safe_reply(
                    line_bot_api, event.reply_token,
                    "✅ 已收到您的同意，歡迎使用票速通！"
                )
            else:
                _send_terms(line_bot_api, reply_token=event.reply_token)
            return  # 未同意者阻擋其他指令

        # ── ② 系統管理指令 ───────────────────
        if text == "[系統]開啟自動回應" and user_id in manager_user_ids:
            auto_reply = True
            _safe_reply(line_bot_api, event.reply_token, "✅ 自動回應已開啟")
            return

        if text == "[系統]關閉自動回應" and user_id in manager_user_ids:
            auto_reply = False
            _safe_reply(line_bot_api, event.reply_token, "🛑 自動回應已關閉")
            return

        # ── ③ 使用者輸入：我要預訂 ─────────────
        if text.startswith("我要預訂："):
            if user_id in submitted_users:
                reply = "⚠️ 您已填寫過訂單，如需修改請聯絡客服。"
            else:
                submitted_users.add(user_id)
                reply = (
                    "請填寫以下訂單資訊：\n"
                    "演唱會節目：\n"
                    "演唱會日期：\n"
                    "票價：\n"
                    "張數（上限為四張）："
                )
            _safe_reply(line_bot_api, event.reply_token, reply)
            return

        # ── ④ 顯示演唱會代操清單 ───────────────
        if text == "[!!!]演唱會代操":
            flex_content = {
                "type": "carousel",
                "contents": []
            }
            # 以下 create_bubble() 自行新增內容
            flex_content["contents"].append(create_bubble(
                "TWICE THIS IS FOR WORLD TOUR PART1 IN KAOHSIUNG",
                "Coming soon...", "Coming soon...", "Coming soon...",
                "Coming soon...",
                "https://img9.uploadhouse.com/fileuploads/32011/32011699f3f6ed545f4c10e2c725a17104ab2e9c.png",
                "TWICE", badge_text="HOT🔥"
            ))
            # …… 其餘 bubble 同你原本程式碼 ……

            _safe_reply(
                line_bot_api,
                event.reply_token,
                FlexMessage(
                    alt_text="演唱會節目資訊，歡迎私訊預訂！",
                    contents=FlexContainer.from_dict(flex_content)
                )
            )
            return

        # ── ⑤ 不在家自動回覆 ───────────────────
        if auto_reply:
            _safe_reply(
                line_bot_api,
                event.reply_token,
                "[@票速通 通知您] 小編 7/12–7/17 不在，若有任何事情請先留言。\n"
                "問題傳送一次即可，馬上回來回覆您！\n\n再次強調，洗頻三次將封鎖！"
            )

        # ── ⑥ 無論如何推播老闆 ────────────────
        try:
            line_bot_api.push_message(
                PushMessageRequest(
                    to=boss_user_id,
                    messages=[TextMessage(
                        text=f"📩 有人傳訊息：{text}（自動回應 {'開啟' if auto_reply else '關閉'}）"
                    )]
                )
            )
        except Exception as e:
            print(f"[推播老闆失敗] {e}")

# ─────────────────────────────────────────────
# 安全回覆封裝
# ─────────────────────────────────────────────


def _safe_reply(line_bot_api, reply_token, message):
    try:
        if isinstance(message, str):
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=message)]
                )
            )
        else:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[message]
                )
            )
    except Exception as e:
        print(f"[Reply 失敗] {e}")

# ─────────────────────────────────────────────
# 建立 Bubble 卡片（保持原本格式）
# ─────────────────────────────────────────────


def create_bubble(title, date, location, price, system,
                  image_url, artist_keyword, badge_text="NEW"):
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "image",
                                    "url": image_url,
                                    "size": "full",
                                    "aspectMode": "cover",
                                    "aspectRatio": "30:25"
                                }
                            ],
                            "flex": 1
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": badge_text,
                                    "size": "xs",
                                    "color": "#ffffff",
                                    "align": "center",
                                    "gravity": "center"
                                }
                            ],
                            "backgroundColor": "#EC3D44",
                            "paddingAll": "2px",
                            "position": "absolute",
                            "offsetStart": "18px",
                            "offsetTop": "18px",
                            "cornerRadius": "100px",
                            "width": "72px",
                            "height": "28px"
                        }
                    ]
                }
            ],
            "paddingAll": "0px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": title,
                    "wrap": True,
                    "weight": "bold",
                    "gravity": "center",
                    "size": "xl"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "日期",
                                    "color": "#aaaaaa", "size": "sm", "flex": 1},
                                {"type": "text", "text": date, "wrap": True,
                                    "color": "#666666", "size": "sm", "flex": 4}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "地點",
                                    "color": "#aaaaaa", "size": "sm", "flex": 1},
                                {"type": "text", "text": location, "wrap": True,
                                    "color": "#666666", "size": "sm", "flex": 4}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "票價",
                                    "color": "#aaaaaa", "size": "sm", "flex": 1},
                                {"type": "text", "text": price, "wrap": True,
                                    "color": "#666666", "size": "sm", "flex": 4}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "系統",
                                    "color": "#aaaaaa", "size": "sm", "flex": 1},
                                {"type": "text", "text": system, "wrap": True,
                                    "color": "#666666", "size": "sm", "flex": 4}
                            ]
                        }
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "message",
                        "label": "填寫預訂單",
                        "text": f"我要預訂：{artist_keyword}"
                    },
                    "style": "primary",
                    "color": "#00A4C1"
                }
            ]
        }
    }


# ─────────────────────────────────────────────
# 本機測試用；Render 會由 gunicorn 啟動
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
