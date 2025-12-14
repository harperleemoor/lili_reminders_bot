from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dateutil.parser import parse
from datetime import datetime
import re

BOT_TOKEN = 7961853275:AAFM6_wVMxtB26YUFrJZ4lVMX1w1xA7_j9Q

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler()

active_reminders = {}

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer(
        "Привет! Я бот-напоминалка 🤖\n\n"
        "Напиши мне напоминание, например:\n"
        "• Купить молоко в 18:00\n"
        "• Позвонить маме через 30 минут\n"
        "• Сходить в спортзал завтра в 20:00\n\n"
        "Я напомню и буду повторять каждые 5 минут, пока ты не ответишь:\n"
        "ок / понял / сделал / done"
    )

@dp.message_handler()
async def handle_reminder(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    time_found = None
    reminder_text = text

    try:
        parsed = parse(text, fuzzy=True, dayfirst=True)
        if parsed > datetime.now() - timedelta(minutes=1):  # чтобы не напоминал о прошлом
            time_found = parsed
            # Пытаемся убрать время из текста напоминания
            reminder_text = re.sub(r'(в\s*\d{1,2}:\d{2}|через\s*\d+\s*(час|часа|часов|минут|минуты)|завтра|сегодня|\d{1,2}:\d{2})', '', text, flags=re.IGNORECASE).strip()
            if not reminder_text:
                reminder_text = text
    except:
        pass

    if not time_found:
        await message.answer("Не смог понять время 😔\n"
                             "Примеры правильных сообщений:\n"
                             "• Купить хлеб в 15:30\n"
                             "• Позвонить другу через 2 часа\n"
                             "• Выпить воду через 30 минут\n"
                             "• Завтра в 10:00 сходить к врачу")
        return

    confirmation = await message.answer(
        f"✅ Хорошо, напомню:\n\"{reminder_text}\"\n"
        f"📅 {time_found.strftime('%d.%m.%Y в %H:%M')}"
    )

    job_id = f"reminder_{user_id}_{confirmation.message_id}"

    scheduler.add_job(
        first_remind,
        'date',
        run_date=time_found,
        args=[user_id, reminder_text, job_id],
        id=job_id
    )

    active_reminders[user_id] = {
        "text": reminder_text,
        "job_id": job_id,
        "confirmed_message_id": confirmation.message_id
    }

async def first_remind(user_id, text, job_id):
    msg = await bot.send_message(user_id, f"🔔 НАПОМИНАНИЕ!\n\n{text}\n\nОтветь 'ок', 'понял', 'сделал' или 'done', чтобы я перестал спамить!")
    
    repeat_job_id = job_id + "_repeat"
    scheduler.add_job(
        repeat_remind,
        'interval',
        minutes=5,
        args=[user_id, text],
        id=repeat_job_id
    )
    
    if user_id in active_reminders:
        active_reminders[user_id]["repeat_job_id"] = repeat_job_id
        active_reminders[user_id]["last_remind_message_id"] = msg.message_id

async def repeat_remind(user_id, text):
    if user_id not in active_reminders:
        return
    await bot.send_message(user_id, f"🔔 ЕЩЁ РАЗ!\n\n{text}\n\nСкорее ответь 'ок' или 'понял'!")

@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ок', 'понял', 'сделал', 'done', 'ok', 'готово', 'yes'])
async def acknowledge(message: types.Message):
    user_id = message.from_user.id
    if user_id in active_reminders:
        repeat_id = active_reminders[user_id].get("repeat_job_id")
        if repeat_id and scheduler.get_job(repeat_id):
            scheduler.remove_job(repeat_id)
        
        await message.answer("Отлично! Напоминание снято 😇")
        del active_reminders[user_id]

if __name__ == '__main__':
    scheduler.start()
    executor.start_polling(dp, skip_updates=True)
