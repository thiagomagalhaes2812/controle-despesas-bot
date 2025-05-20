import logging
import os
import base64
import time
import threading
import re
from datetime import datetime
from flask import Flask
from telegram import Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dateutil.relativedelta import relativedelta

# === CONFIGURAÇÕES ===
TOKEN = os.getenv("TOKEN")
CHAT_ID = 1342787099
SPREADSHEET_NAME = "Controle de Despesas"

# === FLASK SERVER PARA RENDER ===
app = Flask(__name__)
@app.route('/')
def keep_alive():
    return 'Bot rodando com sucesso!'

# === ESCAPE PARA MarkdownV2 ===
def escape_markdown(text):
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


# === GOOGLE SHEETS AUTENTICAÇÃO ===
creds_base64 = os.getenv("CREDS_JSON_BASE64")
with open("creds.json", "wb") as f:
    f.write(base64.b64decode(creds_base64))

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1

# === TELEGRAM SETUP ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start(update, context):
    update.message.reply_text("👋 Olá! Use /nova para registrar uma despesa.\nOu envie frases como:\n`cartão crédito c6 600,00 vencimento 04/05/2025 6 parcelas`", parse_mode='MarkdownV2')

def nova(update, context):
    update.message.reply_text("Envie a despesa assim:\n`75.50 | Alimentação | Padaria | 20/05`", parse_mode='MarkdownV2')

def capturar_chat_id(update, context):
    chat_id = update.message.chat_id
    msg = f"🆔 Seu chat_id é:\n{chat_id}"
    update.message.reply_text(escape_markdown(msg), parse_mode='MarkdownV2')

# === REGISTRO MANUAL ===
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
    update.message.reply_text(f"✅ Registrado: R${valor} | {categoria} | {descricao} | {data}", parse_mode='MarkdownV2')

# === REGISTRO INTELIGENTE COM IA ===
def interpreta_frase_inteligente(update, context):
    texto = update.message.text.strip()

    # Se for modo manual com "|", redireciona
    if "|" in texto:
        processa_despesa(update, context)
        return

    texto_lower = texto.lower()
    valores = re.findall(r'\d{2,5}[.,]\d{2}', texto_lower)
    vencimento_match = re.search(r'(\d{2}/\d{2}/\d{4})', texto_lower)
    parcelas_match = re.search(r'(\d+)\s+parcelas?', texto_lower)

    descricao = texto
    valor_total = float(valores[-1].replace(',', '.')) if valores else None
    vencimento_str = vencimento_match.group(1) if vencimento_match else None
    parcelas = int(parcelas_match.group(1)) if parcelas_match else 1

    if not valor_total or not vencimento_str:
        update.message.reply_text("❌ Não consegui entender valor ou vencimento. Verifique o formato.", parse_mode='MarkdownV2')
        return

    valor_parcela = round(valor_total / parcelas, 2)
    vencimento = datetime.strptime(vencimento_str, "%d/%m/%Y")
    aba = client.open(SPREADSHEET_NAME).worksheet("Pagamentos")

    for i in range(parcelas):
        data_parcela = vencimento + relativedelta(months=i)
        data_fmt = data_parcela.strftime('%Y-%m-%d')
        desc_parcela = f"{descricao} ({i+1}/{parcelas})"
        aba.append_row([data_fmt, valor_parcela, "Cartão de Crédito", desc_parcela, "Sim", "Não"])

    update.message.reply_text(f"✅ Parcelado: R${valor_parcela:.2f} x {parcelas}", parse_mode='MarkdownV2')

# === LEMBRETE DIÁRIO ===
def enviar_lembretes_do_dia(bot, chat_id):
    try:
        aba = client.open(SPREADSHEET_NAME).worksheet("Pagamentos")
        dados = aba.get_all_records()
        hoje = datetime.today().strftime('%Y-%m-%d')

        pagamentos = [
            f"- R${linha['Valor']} | {linha['Categoria']} | {linha['Descrição']}"
            for linha in dados if linha['Data'] == hoje and str(linha['Pago?']).strip().lower() != 'sim'
        ]

        if pagamentos:
            msg_raw = "🔔 Pagamentos de hoje:\n\n" + "\n".join(pagamentos)
            bot.send_message(chat_id=chat_id, text=escape_markdown(msg_raw), parse_mode='MarkdownV2')

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
    # Limpa qualquer webhook pendente
    Bot(TOKEN).delete_webhook()

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("nova", nova))
    dp.add_handler(CommandHandler("meuid", capturar_chat_id))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, interpreta_frase_inteligente))

    threading.Thread(target=agendar_lembrete_diario, args=(updater.bot, CHAT_ID), daemon=True).start()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
