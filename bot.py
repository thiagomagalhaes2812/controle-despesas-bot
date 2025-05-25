import logging
import re
import uuid
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import CommandHandler, MessageHandler, Filters, Dispatcher
import gspread
import json
import os
import base64
from oauth2client.service_account import ServiceAccountCredentials

from apscheduler.schedulers.background import BackgroundScheduler

# CONFIGURAÇÕES
TOKEN = "7514585491:AAE-XZmpQnQ_zslXvh1fcCtTVlOLThaEsbE"  # Substitua aqui pelo seu token do BotFather!
CHAT_ID = 1342787099      # Seu chat_id do Telegram



creds_b64 = os.getenv('CREDS_JSON_BASE64')
creds_json = base64.b64decode(creds_b64).decode('utf-8')
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)

# Configurações
TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID = 1342787099
PLANILHA = "Controle de Despesas"
ABA = "Despesas"

# GOOGLE SHEETS VIA CREDENCIAL BASE64
creds_b64 = os.getenv('CREDS_JSON_BASE64')
if not creds_b64:
    raise Exception("Variável de ambiente CREDS_JSON_BASE64 não definida")
creds_json = base64.b64decode(creds_b64).decode('utf-8')
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)
client = gspread.authorize(creds)
sheet = client.open(PLANILHA).worksheet(ABA)

# TELEGRAM & FLASK
bot = Bot(token=TOKEN)
app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()

# LOGGER
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# LEMBRETE DIÁRIO
def verificar_pagamentos():
    hoje = datetime.now().strftime("%Y-%m-%d")
    registros = sheet.get_all_records()
    mensagens = []
    for linha in registros:
        if str(linha.get("Data")) == hoje and str(linha.get("Pago?")).strip().lower() != "sim":
            mensagens.append(f"🔔 *Lembrete de pagamento*: R${linha['Valor']} - {linha['Categoria']} - {linha['Descrição']} (ID: {linha['ID']})")
    if mensagens:
        bot.send_message(chat_id=CHAT_ID, text="\n".join(mensagens), parse_mode="Markdown")

scheduler.add_job(verificar_pagamentos, trigger="cron", hour=9, minute=0)

# COMANDOS
def hoje(update, context):
    hoje = datetime.now().strftime("%Y-%m-%d")
    registros = sheet.get_all_records()
    mensagens = [
        f"💰 R${linha['Valor']} | {linha['Categoria']} | {linha['Descrição']} | ID: {linha['ID']}"
        for linha in registros if str(linha.get("Data")) == hoje
    ]
    resposta = "\n".join(mensagens) if mensagens else "Nenhum pagamento agendado para hoje."
    update.message.reply_text(resposta)

def parse_mensagem(mensagem):
    data_regex = re.search(r"(\d{2}/\d{2}/\d{4})", mensagem)
    valor_regex = re.search(r"R\$?\s?(\d+[\.,]?\d*)", mensagem)
    parcelas_regex = re.search(r"(\d+) parcelas?", mensagem, re.IGNORECASE)
    categoria = "Cartão de Crédito" if "cartão" in mensagem.lower() else "Outros"
    descricao = mensagem.strip()

    if not (data_regex and valor_regex and parcelas_regex):
        return None

    data_inicio = datetime.strptime(data_regex.group(1), "%d/%m/%Y")
    valor_total = float(valor_regex.group(1).replace(",", "."))
    parcelas = int(parcelas_regex.group(1))
    valor_parcela = round(valor_total / parcelas, 2)

    return data_inicio, valor_parcela, categoria, descricao, parcelas

def adicionar_lancamento(data, valor, categoria, descricao, parcelas):
    for i in range(parcelas):
        data_parcela = (data + timedelta(days=30 * i)).strftime("%Y-%m-%d")
        id_lancamento = str(uuid.uuid4())[:8]
        descricao_parcela = f"{descricao} ({i+1}/{parcelas})"
        sheet.append_row([data_parcela, valor, categoria, descricao_parcela, "Não", "", id_lancamento])

def receber_mensagem(update, context):
    mensagem = update.message.text
    # Confirmação de pagamento via ID
    if mensagem.lower().startswith("confirmar "):
        id_confirmar = mensagem.split(" ")[1].strip()
        registros = sheet.get_all_records()
        for idx, linha in enumerate(registros, start=2):  # 2 porque get_all_records pula header
            if str(linha.get("ID")).lower() == id_confirmar.lower():
                sheet.update_cell(idx, 5, "Sim")
                update.message.reply_text(f"✅ Pagamento do ID {id_confirmar} confirmado!")
                return
        update.message.reply_text(f"❌ ID {id_confirmar} não localizado.")
        return

    # Inclusão de nova despesa
    parsed = parse_mensagem(mensagem)
    if parsed:
        data, valor, categoria, descricao, parcelas = parsed
        adicionar_lancamento(data, valor, categoria, descricao, parcelas)
        update.message.reply_text("✅ Lançamento adicionado com sucesso.")
    else:
        update.message.reply_text("⚠️ Não consegui entender sua mensagem. Verifique o formato ou use: data, valor, parcelas.")

# WEBHOOK HANDLER
@app.route("/", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    return "ok"

# SUBSTITUTO DO before_first_request
initialized = False
@app.before_request
def initialize_once():
    global initialized
    if not initialized:
        start_bot()
        initialized = True

def start_bot():
    global dispatcher
    dispatcher = Dispatcher(bot, None, workers=1)
    dispatcher.add_handler(CommandHandler("hoje", hoje))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, receber_mensagem))

if __name__ == "__main__":
    print("Bot carregado com sucesso")
    app.run(host="0.0.0.0", port=10000)
