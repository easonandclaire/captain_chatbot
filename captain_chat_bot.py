from flask import Flask, request, abort
from linebot.v3.messaging import MessagingApi, Configuration
from linebot.v3.webhooks import WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.v3.messaging.models import *
import os, re
from datetime import datetime, timedelta
import logging
from type import Status, UserInput
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,  # 設置日誌級別（可選 DEBUG, INFO, WARNING, ERROR, CRITICAL）
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 初始化 Flask
app = Flask(__name__)
user_set = set()

target_id = 'Cf1695ceb1fb06c8942f0aace132c749c'

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
messaging_api = MessagingApi(configuration=config)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 儲存提醒日期
reminder_date = None
status = Status['normal']

# 根路徑測試
@app.route("/")
def home():
    return "用藥提醒機器人運行中！"

@app.route("/callback", methods=['POST'])
def callback():
    # 獲取請求的簽名
    signature = request.headers['X-Line-Signature']
    # 獲取請求的body
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@app.route("/trigger_reminder", methods=["GET"])
def trigger_reminder():
    check_reminder()  # 手動調用定時檢查函數
    return "Reminder triggered!", 200

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
    reply_request = ReplyMessageRequest(
        reply_token=event.reply_token,  # 回覆 Token
            messages=[
                TextMessage(text="感謝邀請我加入！")  # 消息內容
            ]
    )
    messaging_api.reply_message(reply_request)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global reminder_date, status, user_set
    user_id = event.source.user_id
    if user_id not in user_set:
        app.logger.info(f"add user: {user_id}")
        user_set.add(user_id)
    user_input = event.message.text.strip()

    if status in [Status['normal'], Status['no_reminder_time']]:
        # 檢查是否為"重設提醒時間"
        if user_input == UserInput[Status['reset_time']]:
            reply_request = ReplyMessageRequest(
                reply_token=event.reply_token,  # 回覆 Token
                    messages=[
                        TextMessage(text="好的，請問想修改成什麼日子？輸入格式為 \"YYYY/MM/DD\"")  # 消息內容
                    ]
            )
            status = Status['check_reset_time']
        elif not reminder_date:
            status = Status['no_reminder_time']
            reply_request = ReplyMessageRequest(
                reply_token=event.reply_token,  # 回覆 Token
                    messages=[
                        TextMessage(text="目前沒有設定提醒日期，請輸入`重設提醒時間`設定提醒日期。")  # 消息內容
                    ]
            )
        elif user_input == UserInput[Status['query_reminder']]:
            reply_request = ReplyMessageRequest(
                reply_token=event.reply_token,  # 回覆 Token
                    messages=[
                        TextMessage(text=f"目前提醒時間為 {reminder_date.strftime('%Y/%m/%d')} 早上 8 點")  # 消息內容
                    ]
            )
        else:
            reply_request = ReplyMessageRequest(
                reply_token=event.reply_token,  # 回覆 Token
                    messages=[
                        TextMessage(text=f"目前的有效指令為：\n1. 重設提醒時間\n2. 查詢提醒時間")  # 消息內容
                    ]
            )
    elif status == Status['check_reset_time']:
        # 檢查是否為日期格式
        date_match = re.match(r'^(\d{4}/\d{2}/\d{2})$', user_input)
        if date_match:
            new_date = datetime.strptime(user_input, "%Y/%m/%d")
            reminder_date = new_date
            reply_request = ReplyMessageRequest(
                reply_token=event.reply_token,  # 回覆 Token
                    messages=[
                        TextMessage(text=f"提醒日期已設定為 {reminder_date.strftime('%Y/%m/%d')}")  # 消息內容
                    ]
            )
            status = Status['normal']
        else:
            reply_request = ReplyMessageRequest(
                reply_token=event.reply_token,  # 回覆 Token
                    messages=[
                        TextMessage(text="日期格式不正確，請重新輸入 (格式為 YYYY/MM/DD)")  # 消息內容
                    ]
            )
    elif status == Status['set_delay_time']:
        # 延後時間的回覆處理
        if re.match(r'^\d+$', user_input):
            days_to_delay = int(user_input)
            reminder_date += timedelta(days=days_to_delay)
            reply_request = ReplyMessageRequest(
                reply_token=event.reply_token,  # 回覆 Token
                    messages=[
                        TextMessage(text=f"已延後提醒時間，新的提醒時間為 {reminder_date.strftime('%Y/%m/%d')}")  # 消息內容
                    ]
            )
            status = Status['normal']
        else:
            reply_request = ReplyMessageRequest(
                reply_token=event.reply_token,  # 回覆 Token
                    messages=[
                        TextMessage(text="請輸入有效的數字，表示要延後的天數。")  # 消息內容
                    ]
            )
    else:
        reply_request = ReplyMessageRequest(
            reply_token=event.reply_token,  # 回覆 Token
                messages=[
                    TextMessage(text=f"狀態錯誤，請通知昱豪！\nStatus = {status}")  # 消息內容
                ]
        )
    messaging_api.reply_message(reply_request)

def check_reminder():
    global reminder_date
    if reminder_date and reminder_date.date() == datetime.now().date():
        for target_id in user_set:
            buttons_template = TemplateSendMessage(
                alt_text='提醒訊息',
                template=ButtonsTemplate(
                    text="今天是提醒日期，請確認是否已經完成！",
                    actions=[
                        PostbackAction(label="我已經餵藥了", data="done_medicine"),
                        PostbackAction(label="我想要延後時間", data="delay_medicine")
                    ]
                )
            )
            # 封裝 PushMessageRequest
            push_request = PushMessageRequest(
                to=target_id,  # 發送的目標 ID
                messages=[buttons_template]  # 消息內容
            )
            # 發送消息
            messaging_api.push_message(push_request)

# 點擊由機器人傳送的模板訊息按鈕（例如選單中的按鈕）並觸發回呼資料時觸發
@handler.add(PostbackEvent)
def handle_postback(event):
    global reminder_date, status

    data = event.postback.data

    if data == "done_medicine":
        reminder_date += timedelta(days=30)
        reply_request = ReplyMessageRequest(
            reply_token=event.reply_token,  # 回覆 Token
                messages=[
                    TextMessage(text=f"下次提醒時間為 {reminder_date.strftime('%Y/%m/%d')}")  # 消息內容
                ]
        )
        status = Status['normal']
    elif data == "delay_medicine":
        reply_request = ReplyMessageRequest(
            reply_token=event.reply_token,  # 回覆 Token
                messages=[
                    TextMessage(text="想要延後幾天呢？請輸入數字")  # 消息內容
                ]
        )
        status = Status['set_delay_time']
    messaging_api.push_message(push_request)
        

# 主程式執行
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
