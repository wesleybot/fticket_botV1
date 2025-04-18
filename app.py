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

app = Flask(__name__)

# === 你的設定 ===
configuration = Configuration(
    access_token='8zFnGQiVtGuRdmZSV4xTjVgOFfZGww/WfO1V0LqYo5cQD4EKN9dMOPBwkU2OzIxwvkvOUD5k4gKbCLv0z2OKM5HDVlztWwujDtGLtRZ8DTDkr9+71clA3pqYtzYLulJNS/qLREqQZIpd1ij81dTOXAdB04t89/1O/w1cDnyilFU='
)
handler = WebhookHandler('39127f50f8d05186e6e6a7cc033b2ead')

boss_user_id = 'U016da51eeb42b435ebe3a22442c97bb1'
manager_user_ids = {boss_user_id}  # 只有這個人能開關自動回應

# === 全域變數 ===
submitted_users = set()
auto_reply = True  # 預設開啟自動回應

# === Webhook 入口 ===
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# === 建立 Bubble 卡片 ===
def create_bubble(title, date, location, price, system, image_url, artist_keyword, badge_text="NEW"):
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
                            "width": "48px",
                            "height": "25px"
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
                                {"type": "text", "text": "日期", "color": "#aaaaaa", "size": "sm", "flex": 1},
                                {"type": "text", "text": date, "wrap": True, "color": "#666666", "size": "sm", "flex": 4}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "地點", "color": "#aaaaaa", "size": "sm", "flex": 1},
                                {"type": "text", "text": location, "wrap": True, "color": "#666666", "size": "sm", "flex": 4}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "票價", "color": "#aaaaaa", "size": "sm", "flex": 1},
                                {"type": "text", "text": price, "wrap": True, "color": "#666666", "size": "sm", "flex": 4}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": "系統", "color": "#aaaaaa", "size": "sm", "flex": 1},
                                {"type": "text", "text": system, "wrap": True, "color": "#666666", "size": "sm", "flex": 4}
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

# === 訊息處理 ===
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    global auto_reply
    text = event.message.text.strip()
    user_id = event.source.user_id

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        if text == "[系統]開啟自動回應" and user_id in manager_user_ids:
            auto_reply = True
            _safe_reply(line_bot_api, event.reply_token, "✅ 自動回應已開啟")
            return

        if text == "[系統]關閉自動回應" and user_id in manager_user_ids:
            auto_reply = False
            _safe_reply(line_bot_api, event.reply_token, "🛑 自動回應已關閉")
            return

        if text.startswith("我要預訂："):
            if user_id in submitted_users:
                reply = "⚠️ 您已填寫過訂單，如需修改請聯絡客服。"
            else:
                submitted_users.add(user_id)
                reply = "請填寫以下訂單資訊：\n演唱會節目：\n演唱會日期：\n票價：\n張數（上限為四張）："
            _safe_reply(line_bot_api, event.reply_token, reply)
            return

        if text == "[!!!]演唱會代操":
            flex_content = {
                "type": "carousel",
                "contents": []
            }
            flex_content["contents"].append(create_bubble("國泰世華銀行\n伍佰 ＆ China Blue Rock Star2演唱會-高雄站", "2025.11.22 (六) 19:30\n2025.11.23 (日) 19:00", "Comimg soon...", "Comimg soon...", "拓元售票系統", "https://img5.uploadhouse.com/fileuploads/31934/319346856d24e3358b522bc1d8aa65825c41d420.png", "伍佰", badge_text="HOT🔥"))
            flex_content["contents"].append(create_bubble("玉山銀行\n五月天25週年巡迴歌迷過生日-台北站", "2025.07.12(六)18:00", "臺北流行音樂中心表演廳", "Comimg soon...", "拓元售票系統", "https://img4.uploadhouse.com/fileuploads/31934/319347049577ac603847741dbf746d7eedf3c057.png", "五月天", badge_text="HOT🔥"))
            flex_content["contents"].append(create_bubble("2025 KAI SOLO CONCERT TOUR <KAION> IN TAIPEI", "2025.07.12(六)18:00", "臺北流行音樂中心表演廳", "Comimg soon...", "拓元售票系統", "https://img8.uploadhouse.com/fileuploads/31934/31934708f74031421c828781caaa86f02cbc7495.png", "KAI", badge_text="HOT🔥"))
            flex_content["contents"].append(create_bubble("2025 HA HYUN SANG FAN CONCERT ＜FINE DAY WITH HYUN SANG＞ IN TAIPEI", "2025.05.17(六)19:00", "Legacy MAX", "TWD 4,600 / 4,200 / 3,800 / 2,800", "拓元售票系統", "https://img5.uploadhouse.com/fileuploads/31934/319347154ae5bf4508c3e55e0b830e5ad9368eb3.png", "HA HYUN SANG", badge_text="HOT🔥"))
            flex_content["contents"].append(create_bubble("蔡依林演唱會", "Comimg soon...", "Comimg soon...", "Coming soon...", "Comimg soon...", "https://img7.uploadhouse.com/fileuploads/31934/319347074ebade93a4a6310dec72f08996dc2af1.png", "蔡依林"))

            _safe_reply(line_bot_api, event.reply_token,
                FlexMessage(
                    alt_text="演唱會節目資訊，歡迎私訊預訂！",
                    contents=FlexContainer.from_dict(flex_content)
                )
            )
            return

        # 如果 auto_reply 開啟，發送預設訊息
        if auto_reply:
            _safe_reply(line_bot_api, event.reply_token, "[@票速通 通知您]\n請點選下方選單服務，若有其他疑問請私訊一次就好！\n請稍等會馬上回覆您！！！")

        # 無論如何推播給老闆
        try:
            line_bot_api.push_message(
                PushMessageRequest(
                    to=boss_user_id,
                    messages=[TextMessage(text=f"📩 有人傳訊息：{text}（自動回應 {'開啟' if auto_reply else '關閉'}）")]
                )
            )
        except Exception as e:
            print(f"推播老闆失敗：{e}")

# === 安全回覆封裝 ===
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
        print(f"回覆失敗：{e}")

if __name__ == "__main__":
    app.run(debug=True, port=5001)
