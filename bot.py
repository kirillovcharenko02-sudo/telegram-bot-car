import os
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = "8900336130:AAEKfOOyi9SQSG1P7kahUPJINz065RbdrRM"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/15CE2G6h4PpFTrJFiG2k8BIHsYUU77688SwjdVjPYCLg/edit?gid=0#gid=0"
FOLDER_ID = "1bPeN2Xs-8gj1-RpRTg3-95NdCGUdkhVK"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_google_services():
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_url(SPREADSHEET_URL)
    sheet = spreadsheet.sheet1
    drive_service = build('drive', 'v3', credentials=creds)
    return drive_service, sheet

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    username = f"@{user.username}" if user.username else f"{user.first_name} {user.last_name or ''}".strip()
    
    try:
        if update.message.document:
            file_obj = update.message.document
            file_name = file_obj.file_name
            file_id = file_obj.file_id
        elif update.message.photo:
            file_obj = update.message.photo[-1]
            file_name = f"photo_{user.id}.jpg"
            file_id = file_obj.file_id
        else:
            await update.message.reply_text("Пожалуйста, отправьте документ или фото.")
            return

        get_file_url = f"https://api.telegram.org/bot{TOKEN}/getFile?file_id={file_id}"
        response = requests.get(get_file_url, timeout=30).json()
        
        if not response.get("ok"):
            await update.message.reply_text("⚠️ Не удалось получить информацию о файле от Telegram.")
            return
            
        file_path = response["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"

        local_path = f"/tmp/{file_name}"
        file_data = requests.get(download_url, stream=True, timeout=60)
        
        with open(local_path, 'wb') as f:
            for chunk in file_data.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        drive_service, sheet = get_google_services()
        
        file_metadata = {'name': file_name, 'parents': [FOLDER_ID]}
        media = MediaFileUpload(local_path, resumable=True)
        uploaded_file = drive_service.files().create(
            body=file_metadata, media_body=media, fields='id, webViewLink'
        ).execute()
        
        file_url = uploaded_file.get('webViewLink')
        sheet.append_row([username, file_name, file_url])

        await update.message.reply_text(f"✅ Файл успешно сохранен!\nСсылка на диск: {file_url}")
        
        if os.path.exists(local_path):
            os.remove(local_path)

    except Exception as e:
        print(f"⚠️ Ошибка: {e}")
        await update.message.reply_text(f"⚠️ Ошибка при обработке: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
    print("Бот запущен...")
    app.run_polling()
