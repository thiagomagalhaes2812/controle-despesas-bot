
import os
import logging
import base64
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler

import gspread
from oauth2client.service_account import ServiceAccountCredentials

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SPREADSHEET_NAME = "Controle de Despesas"

creds_base64 = os.getenv("CREDS_JSON_BASE64")
with open("creds.json", "wb") as f:
    f.write(base64.b64decode(creds_base64))

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1

bot = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=0)

def start(update, context):
    update.message.reply_text("🤖 Bot de controle de despesas ativo com Webhook!")

dispatcher.add_handler(CommandHandler("start", start))

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

@app.before_first_request
def init_webhook():
    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

@app.route('/')
def index():
    return "Bot ativo com Webhook!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Rodando Flask na porta: {port}")
    app.run(host='0.0.0.0', port=port)