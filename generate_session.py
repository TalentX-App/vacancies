from telethon.sessions import StringSession
from telethon.sync import TelegramClient

# Заполните свои данные
api_id = '29034483'
api_hash = 'bab2bcf8c88794099570f8257946f490'

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nВот ваш session string:\n")
    print(client.session.save())
