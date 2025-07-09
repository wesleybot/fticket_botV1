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
auto_reply = False  # 預設開啟自動回應

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
            flex_content["contents"].append(create_bubble(
                "TWICE THIS IS FOR WORLD TOUR PART1 IN KAOHSIUNG",
                "Comimg soon...", 
                "Comimg soon...",
                "Comimg soon...",
                "Comimg soon...",
                "https://img9.uploadhouse.com/fileuploads/32011/32011699f3f6ed545f4c10e2c725a17104ab2e9c.png",
                "TWICE",
                badge_text="HOT🔥"
            ))
            flex_content["contents"].append(create_bubble(
                "台新銀行周興哲Odyssey旅程巡迴演唱會 臺北返場",
                "2025/9/26(五)-2025/9/28(日)，19:30正式開唱", 
                "臺北小巨蛋",
                "4,280元、3,880元、3,480元、2,880元、1,880元、1,280元、800元",
                "KKTIX",
                "https://img0.uploadhouse.com/fileuploads/32024/320248008a66f80d992df87a252663b9077bdb8c.png",
                "周興哲",
                badge_text="HOT🔥"
            ))
            flex_content["contents"].append(create_bubble(
                "家家 月部落 Fly to the moon 你給我的月不落現場",
                "9.27 Sat. 19:00", 
                "Legacy Taipei 音樂展演空間",
                "NT. 1800（全區座席）/ NT. 900（身障席）",
                "拓元售票系統",
                "https://img4.uploadhouse.com/fileuploads/32041/32041604c5fee787f6b7ec43d0d3fe8991ae995d.png",
                "家家",
                badge_text="HOT🔥"
            ))
            flex_content["contents"].append(create_bubble(
                "國泰世華銀行\n伍佰 ＆ China Blue Rock Star2演唱會-高雄站",
                "11.22 (六) 19:30\n11.23 (日) 19:00", 
                "Comimg soon...",
                "Comimg soon...",
                "拓元售票系統",
                "https://img5.uploadhouse.com/fileuploads/31934/319346856d24e3358b522bc1d8aa65825c41d420.png",
                "伍佰",
                badge_text="HOT🔥"
            ))
            flex_content["contents"].append(create_bubble(
                "《Blackpink World Tour【Deadline】In Kaohsiung》",
                "10/18（六）、10/19（日）", 
                "高雄世運",
                "Comimg soon...",
                "拓元售票系統",
                "https://img6.uploadhouse.com/fileuploads/31980/3198036627832f485ac579d704e3f590f8bd4bda.png",
                "BP",
                badge_text="HOT🔥"
            ))
            flex_content["contents"].append(create_bubble(
                "鄧紫棋演唱會",
                "Comimg soon...", 
                "Comimg soon...",
                "Comimg soon...",
                "Comimg soon...",
                "https://img1.uploadhouse.com/fileuploads/31980/31980371b9850a14e08ec5f39c646f7b5068e008.png",
                "鄧紫棋",
                badge_text="即將來🔥"
            ))
            flex_content["contents"].append(create_bubble(
                "蔡依林演唱會", 
                "Comimg soon...", 
                "Comimg soon...", 
                "Coming soon...", 
                "Comimg soon...", 
                "https://img7.uploadhouse.com/fileuploads/31934/319347074ebade93a4a6310dec72f08996dc2af1.png", 
                "蔡依林",
                badge_text="即將來🔥"
            ))

            _safe_reply(line_bot_api, event.reply_token,
                FlexMessage(
                    alt_text="演唱會節目資訊，歡迎私訊預訂！",
                    contents=FlexContainer.from_dict(flex_content)
                )
            )
            return

        # 如果 auto_reply 開啟，發送預設訊息
        if auto_reply:
            _safe_reply(line_bot_api, event.reply_token, "[@票速通 通知您] 小編7/12-7/17不在，若有任何事情，請先留言即可。\n The editor was away from home from 7/12 to 7/17. If you have any questions, please leave a message first.\n 問題傳送一次即可，馬上回來回覆您！\n\n再次強調，洗頻三次將封鎖！")
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
