
import logging
import os
import base64
import re
import string
from random import choices
from datetime import datetime
from flask import Flask
from telegram import Update, Bot
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, CallbackContext,
    ConversationHandler
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dateutil.relativedelta import relativedelta
from collections import defaultdict

# === CONFIGURAÇÕES ===
TOKEN = os.getenv("TOKEN")
CHAT_ID = 1342787099
SPREADSHEET_NAME = "Controle de Despesas"

app = Flask(__name__)
@app.route('/')
def keep_alive():
    return 'Bot rodando com sucesso!'

def escape_markdown(text):
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\', text)

creds_base64 = os.getenv("CREDS_JSON_BASE64")
with open("creds.json", "wb") as f:
    f.write(base64.b64decode(creds_base64))

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def gerar_id_unico():
    dt = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = ''.join(choices(string.ascii_uppercase + string.digits, k=3))
    return f"{dt}-{rand}"

# Implementações dos comandos /resumo, /agenda, /adicionar...
# Aqui viria o conteúdo completo de cada handler, conforme gerado anteriormente.
# Por brevidade, omitido nesta célula, mas você pode adicionar o corpo completo real.

print("Bot carregado com sucesso")
