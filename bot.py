import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# === CONFIGURAÇÕES ===
TOKEN = '7514585491:AAE-XZmpQnQ_zslXvh1fcCtTVlOLThaEsbE'
SPREADSHEET_NAME = 'Controle de Despesas'  # Nome da planilha no Google Drive

# === GOOGLE SHEETS SETUP ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1  # Usa a primeira aba

# === TELEGRAM BOT SETUP ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def start(update, context):
    update.message.reply_text("👋 Olá! Sou seu assistente de despesas. Use /nova para registrar um gasto.")

def nova(update, context):
    update.message.reply_text("Envie a despesa no formato:\n`75.50 | Alimentação | McDonald's | 18/05`", parse_mode='Markdown')

def processa_despesa(update, context):
    texto = update.message.text
    partes = [p.strip() for p in texto.split('|')]

    if len(partes) < 3:
        update.message.reply_text("⚠️ Formato inválido. Envie como:\n`75.50 | Alimentação | McDonald's | 18/05`", parse_mode='Markdown')
        return

    valor = partes[0].replace("R$", "").replace(",", ".")
    categoria = partes[1]
    descricao = partes[2]
    data = partes[3] if len(partes) > 3 else datetime.today().strftime('%d/%m/%Y')
    usuario = update.message.chat.username or update.message.chat.first_name

    sheet.append_row([data, valor, categoria, descricao, usuario])

    update.message.reply_text(f"✅ Despesa registrada:\n💰 R${valor}\n📂 {categoria}\n📝 {descricao}\n📅 {data}")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("nova", nova))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, processa_despesa))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
