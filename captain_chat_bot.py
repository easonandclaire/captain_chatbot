from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, PostbackEvent, TextSendMessage, FlexSendMessage, PostbackAction, BubbleContainer, BoxComponent, TextComponent
import os
from datetime import datetime, timedelta

# 初始化 Flask
app = Flask(__name__)

# Line API 憑證
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'szs387X6h/uFwALKyXCD/f/pOjEXnlMDcM28gINyfvsaV7nO8ZXrGehEmMRLRAr17FUV6TXR/DXfTKg+b7HHtLF3epFkM3ezwM78meLgqMNvDMJ/FnrHaAP05soATrkiaZj4d5EftoAKHlDtSpE1PQdB04t89/1O/w1cDnyilFU=')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '073e81b7dc7e31ec5a127d8b935949ba')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 模擬儲存提醒日期（實際應連接資料庫）
reminder_date = datetime.strptime("2024-12-06", "%Y-%m-%d")

# 根路徑測試
@app.route("/")
def home():
    return "用藥提醒機器人運行中！"

# 接收 Webhook 回調
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# 定期提醒訊息推送
@app.route("/push_reminder", methods=['GET'])
def push_reminder():
    global reminder_date
    today = datetime.now().date()

    # 如果今天是提醒日期，發送提醒
    if today == reminder_date.date():
        flex_message = FlexSendMessage(
            alt_text="今天隊長要吃犬新寶！",
            contents=BubbleContainer(
                body=BoxComponent(
                    layout="vertical",
                    contents=[
                        TextComponent(text="今天隊長要吃犬新寶！", weight="bold", size="xl"),
                        BoxComponent(
                            layout="horizontal",
                            contents=[
                                PostbackAction(label="完成", data="action=completed"),
                                PostbackAction(label="今天忘記了，明天再提醒一次", data="action=postpone")
                            ]
                        )
                    ]
                )
            )
        )
        # 群組 ID 或用戶 ID 替換為實際目標
        line_bot_api.push_message("你的群組ID或用戶ID", flex_message)
        return "提醒已發送！"
    return "今天不是提醒日！"

# 處理 Postback
@handler.add(PostbackEvent)
def handle_postback(event):
    global reminder_date
    data = event.postback.data

    if data == "action=completed":
        reminder_date += timedelta(days=90)  # 加三個月
        reply = f"已完成用藥提醒！下次提醒時間為：{reminder_date.strftime('%Y-%m-%d')}"
    elif data == "action=postpone":
        reminder_date += timedelta(days=1)  # 加一天
        reply = f"提醒已延後，下次提醒時間為：{reminder_date.strftime('%Y-%m-%d')}"
    else:
        reply = "未知操作，請重新選擇。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

# 主程式執行
if __name__ == "__main__":
    app.run(port=5000)
