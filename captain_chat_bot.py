from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import JoinEvent, MessageEvent, PostbackEvent, TextSendMessage, FlexSendMessage, PostbackAction, BubbleContainer, BoxComponent, TextComponent
import os
from datetime import datetime, timedelta
import logging
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(
    level=logging.INFO,  # 設置日誌級別（可選 DEBUG, INFO, WARNING, ERROR, CRITICAL）
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 初始化 Flask
app = Flask(__name__)

target_id = 'Cf1695ceb1fb06c8942f0aace132c749c'

# 初始化 APScheduler
scheduler = BackgroundScheduler()
scheduler.start()

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

@handler.add(JoinEvent)
def handle_join(event):
    app.logger.info("JoinEvent received - starting to process")
    if event.source.type == "group":
        group_id = event.source.group_id
        app.logger.info(f"加入群組，群組 ID: {group_id}")
    elif event.source.type == "room":
        room_id = event.source.room_id
        app.logger.info(f"加入聊天室，聊天室 ID: {room_id}")
    else:
        app.logger.info(f'type: {event.source.type}')
        app.logger.info(f'event: {event}')
    # 回覆訊息
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="感謝邀請我加入！")
    )

@handler.add(MessageEvent)
def handle_message(event):
    # 獲取事件的來源
    source = event.source
    target_id = None

    # 判斷來源類型
    if source.type == "user":
        target_id = source.user_id
        app.logger.info(f"獲取到用戶 ID: {target_id}")
    elif source.type == "group":
        target_id = source.group_id
        app.logger.info(f"獲取到群組 ID: {target_id}")
    elif source.type == "room":
        target_id = source.room_id
        app.logger.info(f"獲取到聊天室 ID: {target_id}")

    # 可以回覆用戶的訊息，確認收到
    reply = TextSendMessage(text="感謝你的訊息！我們已記錄你的 ID。")
    line_bot_api.reply_message(event.reply_token, reply)

# 定期提醒訊息推送
@app.route("/push_reminder", methods=['GET'])
def push_reminder():
    global reminder_date
    today = datetime.now().date()

    # 如果今天是提醒日期，發送提醒
    if today == reminder_date.date():
        flex_message = FlexSendMessage(
            alt_text="今天隊長要吃犬新寶！",
            contents={
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "今天隊長要吃犬新寶！",
                            "weight": "bold",
                            "size": "xl"
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "完成",
                                        "data": "action=completed"
                                    },
                                    "style": "primary"
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "今天忘記了，明天再提醒一次",
                                        "data": "action=postpone"
                                    },
                                    "style": "secondary"
                                }
                            ]
                        }
                    ]
                }
            }
        )
        # 推送訊息給所有群組或聊天室
        try:
            line_bot_api.push_message(target_id, flex_message)
            app.logger.info(f"訊息已成功推送到目標 ID: {target_id}")
        except Exception as e:
            app.logger.info(f"推送到目標 ID {target_id} 失敗，原因: {e}")
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
        # 安排下一次提醒任務（3個月後）
        run_date = datetime.now() + timedelta(days=90)
        scheduler.add_job(push_reminder, 'date', run_date=run_date)
        app.logger.info(f"已安排 3 個月後的提醒，時間：{run_date}")
    elif data == "action=postpone":
        reminder_date += timedelta(seconds=5)  # 加一天
        reply = f"提醒已延後，下次提醒時間為：{reminder_date.strftime('%Y-%m-%d')}"
        # 使用 APScheduler 在 5 秒後安排推送提醒任務
        run_date = datetime.now() + timedelta(seconds=5)
        scheduler.add_job(push_reminder, 'date', run_date=run_date)
        app.logger.info(f"已安排延後的提醒，時間：{run_date}")
    else:
        reply = "未知操作，請重新選擇。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

# 主程式執行
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
