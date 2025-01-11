from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os, re
from datetime import datetime, timedelta
import logging
from type import Status, UserInput, Medicine
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,  # 設置日誌級別（可選 DEBUG, INFO, WARNING, ERROR, CRITICAL）
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 初始化 Flask
app = Flask(__name__)

target_id = 'Cf1695ceb1fb06c8942f0aace132c749c'

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 儲存提醒日期
reminder_date = {
    'bravecto': None,
    'heartgard': None
}
update_reminder_type = None
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
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="感謝邀請我加入！")
    )

def query_reminder_date(event):
    global reminder_date, status
    if not reminder_date['bravecto'] and not reminder_date['heartgard']:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="目前沒有提醒時間，請輸入「修改提醒時間」進行設定。"))
    elif not reminder_date['bravecto']:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"下次餵 {Medicine['heartgard']} 的日期為：{reminder_date['heartgard']}\n目前沒有設定 {Medicine['bravecto']} 的提醒時間，請輸入「修改提醒時間"))
    elif not reminder_date['heartgard']:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"下次餵 {Medicine['bravecto']} 的日期為：{reminder_date['bravecto']}\n目前沒有設定 {Medicine['heartgard']} 的提醒時間，請輸入「修改提醒時間"))
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"下次餵{Medicine['bravecto']}的日期為：{reminder_date['bravecto']}\n下次餵{Medicine['heartgard']}的日期為：{reminder_date['heartgard']}"))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global reminder_date, status
    user_input = event.message.text.strip()

    if status == Status['normal']:
        if user_input == UserInput[Status['query_reminder']]:
            query_reminder_date(event)
        elif user_input == UserInput[Status['reset_time']]:
            buttons_template = TemplateSendMessage(
                alt_text='提醒訊息',
                template=ButtonsTemplate(
                    text="想要修改或設定的是犬新寶還是一錠除的時間呢？",
                    actions=[
                        PostbackAction(label="犬新寶", data=["update_reminder", "heartgard"]),
                        PostbackAction(label="一錠除", data=["update_reminder", "bravecto"])
                    ]
                )
            )
            line_bot_api.push_message(target_id, buttons_template)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="目前的有效指令為：\n1. 修改提醒時間\n2. 查詢提醒時間"))
        return
    elif status == Status['check_reset_time']:
        # 檢查是否為日期格式
        date_match = re.match(r'^(\d{4}/\d{2}/\d{2})$', user_input)
        if date_match:
            new_date = datetime.strptime(user_input, "%Y/%m/%d")
            if new_date < datetime.now():
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="此為過去時間，請重新輸入提醒時間。"))
                return
            if update_reminder_type == None:
                app.logger.error("update_reminder_type 為空！")
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"後端有問題，請聯繫昱豪！"))
                return
            reminder_date[update_reminder_type] = new_date
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"完成設定，下次餵 {Medicine[update_reminder_type]} 的日期為：{reminder_date[update_reminder_type].strftime('%Y/%m/%d')}。"))
            status = Status['normal']
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="時間輸入格式錯誤，，請重新輸入提醒時間。"))
        return
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"狀態錯誤，請通知昱豪！\nStatus = {status}"))

def check_reminder():
    global reminder_date
    # 檢查是否要餵一錠除
    if reminder_date['bravecto'] == datetime.now().date():
        buttons_template = TemplateSendMessage(
            alt_text='提醒訊息',
            template=ButtonsTemplate(
                text=f"今天是餵隊長{Medicine['bravecto']}的日子！請確認是否已經完成！",
                actions=[
                    PostbackAction(label="我已經完成餵藥囉", data=["done_medicine", "bravecto"]),
                    PostbackAction(label="今天忘記了，明天再提醒一次", data=["delay_medicine", "bravecto"])
                ]
            )
        )
        line_bot_api.push_message(target_id, buttons_template)
    elif reminder_date['heartgard'] == datetime.now().date():
        buttons_template = TemplateSendMessage(
            alt_text='提醒訊息',
            template=ButtonsTemplate(
                text=f"今天是餵隊長{Medicine['heartgard']}的日子！請確認是否已經完成！",
                actions=[
                    PostbackAction(label="我已經完成餵藥囉", data=["done_medicine", "heartgard"]),
                    PostbackAction(label="今天忘記了，明天再提醒一次", data=["delay_medicine", "heartgard"])
                ]
            )
        )
        line_bot_api.push_message(target_id, buttons_template)
    else:
        app.logger.error("提醒日期為空！")

# 點擊由機器人傳送的模板訊息按鈕（例如選單中的按鈕）並觸發回呼資料時觸發
@handler.add(PostbackEvent)
def handle_postback(event):
    global reminder_date, status

    action, type = event.postback.data

    if action == "done_medicine":
        if type == 'bravecto':
            reminder_date[type] += timedelta(days=90)
        elif type == 'heartgard':
            reminder_date[type] += timedelta(days=30)
        else:
            app.logger.error(f"未知的藥物類型：{type}")
            return
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"好的，下次提醒時間為 {reminder_date[type].strftime('%Y/%m/%d')}"))
        status = Status['normal']
    elif action == "delay_medicine":
        reminder_date[type] += timedelta(days=1)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"下次提醒時間設為隔日 {reminder_date[type]} 送出提醒"))
    elif action == 'update_reminder':
        update_reminder_date(type)
    else:
        app.logger.error(f"未知的動作：{action}")

def update_reminder_date(type):
    global status, update_reminder_type
    update_reminder_type = type
    status = Status['check_reset_time']
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"請輸入想要提醒的時間（YYYY/MM/DD）。"))

# 主程式執行
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
