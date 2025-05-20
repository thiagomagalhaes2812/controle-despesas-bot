import logging
import os
import base64
import time
import threading
import re
from datetime import datetime
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials


from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def keep_alive():
    return 'Bot rodando com sucesso!'


# === CONFIGURAÇÕES ===
TOKEN = os.getenv("TOKEN")
SPREADSHEET_NAME = "Controle de Despesas"

# === RECONSTRUIR creds.json A PARTIR DO BASE64 ===
creds_base64 = os.getenv("CREDS_JSON_BASE64")
with open("creds.json", "wb") as f:
    f.write(base64.b64decode(creds_base64))

# === AUTENTICAÇÃO COM GOOGLE SHEETS ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1

# === SETUP DO TELEGRAM ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === ESCAPE PARA MarkdownV2 ===
def escape_markdown(text):
    return re.sub(r'([_\*\[\]\(\)~`>#+\-=|{}.!])', r'\\\1', text)

# === COMANDOS DO BOT ===
def start(update, context):
    update.message.reply_text("👋 Olá! Use /nova para registrar uma despesa.\nUse /meuid para ativar o lembrete.")

def nova(update, context):
    update.message.reply_text("Envie assim:\n`75.50 | Alimentação | Padaria | 20/05`", parse_mode='MarkdownV2')

def processa_despesa(update, context):
    texto = update.message.text
    partes = [p.strip() for p in texto.split('|')]

    if len(partes) < 3:
        update.message.reply_text("⚠️ Formato inválido. Use:\n`valor | categoria | descrição | data (opcional)`", parse_mode='MarkdownV2')
        return

    valor = partes[0].replace("R$", "").replace(",", ".")
    categoria = partes[1]
    descricao = partes[2]
    data = partes[3] if len(partes) > 3 else datetime.today().strftime('%d/%m/%Y')
    usuario = update.message.chat.username or update.message.chat.first_name

    sheet.append_row([data, valor, categoria, descricao, usuario])
    update.message.reply_text(f"✅ Registrado: R${valor} | {categoria} | {descricao} | {data}")

def capturar_chat_id(update, context):
    chat_id = update.message.chat_id
    update.message.reply_text(f"🆔 Seu chat_id é:\n`{chat_id}`", parse_mode='MarkdownV2')

# === LEMBRETE AUTOMÁTICO ===
def enviar_lembretes_do_dia(bot, chat_id):
    try:
        aba = client.open(SPREADSHEET_NAME).worksheet("Pagamentos")
        dados = aba.get_all_records()
        hoje = datetime.today().strftime('%Y-%m-%d')

        pagamentos_hoje = [
            f"- R${linha['Valor']} | {linha['Categoria']} | {linha['Descrição']}"
            for linha in dados if linha['Data'] == hoje and str(linha['Pago?']).strip().lower() != 'sim'
        ]

        if pagamentos_hoje:
            msg = "🔔 *Pagamentos de hoje:*\n\n" + "\n".join(pagamentos_hoje)
            bot.send_message(chat_id=chat_id, text=escape_markdown(msg), parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"[Erro no lembrete] {e}")

def agendar_lembrete_diario(bot, chat_id):
    enviado_hoje = False
    while True:
        agora = datetime.now()
        if agora.hour == 8 and not enviado_hoje:
            enviar_lembretes_do_dia(bot, chat_id)
            enviado_hoje = True
        elif agora.hour != 8:
            enviado_hoje = False
        time.sleep(60)

# === MAIN ===
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("nova", nova))
    dp.add_handler(CommandHandler("meuid", capturar_chat_id))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, processa_despesa))

    # === INSIRA AQUI SEU CHAT_ID REAL
    chat_id = 123456789  # substitua pelo seu ID real após usar /meuid

    if isinstance(chat_id, int):
        threading.Thread(target=agendar_lembrete_diario, args=(updater.bot, chat_id), daemon=True).start()

# Iniciar servidor Flask em thread paralela
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()


    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
