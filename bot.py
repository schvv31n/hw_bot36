import datetime as dt
import telegram as tg
import telegram.ext as tg_ext
import data
import re
from hw_request import get_hw
from pytz import timezone
import database
import os
import json
import traceback
updater = tg_ext.Updater(token=data.TOKEN1, use_context=True)

kw = ['англ', 'алг', 'био', 'геог', 'физр', 'физик', 'лит', 'хим', 'геом', 'немец', 'фр', 'ист', 'общ', 'рус', 'тех', 'обж', 'родн']

HW_SEARCH = re.compile(f"({'|'.join(kw)})", re.IGNORECASE)

def errors(update, context):
    try:
        raise context.error
    except:
        tb = traceback.format_exc()
        update.effective_chat.send_message(text='Неизвестная ошибка: \n'+tb)
updater.dispatcher.add_error_handler(errors)

def stop_bot(update, context):
    if update.message.from_user.id==420736786:
        update.message.reply_text('Бот отключен')
        updater.bot.delete_webhook()
        updater.stop()
    else:
        update.message.reply_sticker(sticker='CAACAgIAAxkBAAMcX6LrsyrpHv72CRJy6kpNife4oIgAAgYAAxLvExmDIS_rRvj5qR4E')
updater.dispatcher.add_handler(tg_ext.CommandHandler('stop', stop_bot))

def exec_script(update, context):
        if update.message.from_user.id==420736786:
            updater.dispatcher.run_async(lambda x=None: exec(update.message.text[6:]), update=update)
updater.dispatcher.add_handler(tg_ext.CommandHandler('exec', exec_script))

def update_hw(update=None, context=None):
    if update:
        if update.message.from_user.id!=420736786:
            return
    get_hw()
updater.job_queue.run_repeating(update_hw, 3600)
updater.dispatcher.add_handler(tg_ext.CommandHandler('force_update', update_hw))
    
def daily_schedule(context):
    with open(data.DB_FILENAME) as hw_reader:
        hw = json.loads(hw_reader.read())
        
    target_weekday = dt.datetime.now().weekday()    
    if target_weekday==5:
        target_weekday += 1
    target_weekday += 1
           
    if hw['valid']:
        parsed_hw = 'Расписание на завтра:\n'
        photos = []
        for i in hw['content'][target_weekday]['lessons']:
            hw_shortcut = HW_SEARCH.search(i['discipline']).groups()[0].lower()
            print(hw_shortcut)
            db_hw = database.read(hw_shortcut)
            if db_hw['photoid']:
                photos.append((db_hw['photoid'], i['discipline']))
            lesson_hw = i['homework'] if i['homework'] else db_hw['text']+(f'(фото {len(photos)})' if db_hw['photoid'] else '')
            parsed_hw+=f"{i['discipline']}({i['time_begin'][:5]} - {i['time_end'][:5]})\nД/З - {lesson_hw}\n"
            
            updater.bot.send_message(chat_id=data.TARGET_CHAT_ID, text=parsed_hw)
            if photos:
                updater.bot.send_media_group(chat_id=data.TARGET_CHAT_ID, media=[tg.InputMediaPhoto(media=i[0], caption=i[1]) for i in photos])
    else:
        update.message.reply_text('Не удалось получить расписание на завтра\nОшибка: '+hw['error'])
updater.job_queue.run_daily(daily_schedule, dt.time(hour=18, tzinfo=timezone('Europe/Moscow')), days=list(range(6)))

res_global = (None, None)
def read_hw(update, context):
    with open(data.DB_FILENAME) as hw_reader:
        res = json.loads(hw_reader.read())
        
    target_weekday = dt.datetime.now().weekday()
    if target_weekday==5:
        target_weekday += 1
    target_weekday += 1
    
    hw = None
    if res['valid']:
        for day in res['content'][target_weekday:]:
            for lesson in day['lessons']:
                groups = context.match.groups()
                if (groups[2] if groups[2] else groups[3]) in lesson['discipline'].lower():
                    hw = [lesson['discipline'], day['date'], lesson['homework']]
                    break
            if hw:
                break
        if not hw:
            db_hw = database.read((groups[2] if groups[2] else groups[3]))
            if db_hw:
                if db_hw['photoid']:
                    update.message.reply_photo(photo=db_hw['photoid'], caption='Д/З: '+db_hw['text']+'(фото выше)')
                    return
                else:
                    update.message.reply_text('Д/З: '+db_hw['text'])
                    return
            else:
                update.message.reply_text('Ошибка: '+res['error'])
                return
        elif hw[2]=='':
            hw[2] = database.read((groups[2] if groups[2] else groups[3]))
    else:
        db_hw = database.read((groups[2] if groups[2] else groups[3]))
        if db_hw.get('photoid', None)!=None:
            update.message.reply_photo(photo=db_hw['photoid'], caption='Д/З: '+db_hw['text']+'(фото выше)')
        elif db_hw.get('text', None)!=None:
                update.message.reply_text('Д/З: '+db_hw['text'])
        else:
            update.message.reply_text('Ошибка: '+res['error'])
        return
    if type(hw[2])==dict:
        if hw[2]['photoid']:
            update.message.reply_photo(photo=hw[2]['photoid'], caption=f"Д/З по предмету {hw[0]} на {hw[1]}")
        else:
            update.message.reply_text(f"Д/З по предмету {hw[0]} на {hw[1]}: {hw[2]['text']}")
    else:
        update.message.reply_text(f"Д/З по предмету {hw[0]} на {hw[1]}: {hw[2]}")
p1 = re.compile(f".*((что|че).*по.?({'|'.join(kw)})|по.?({'|'.join(kw)}).+(что|че)[- ]?(то)?.*зад.*)", re.IGNORECASE)
updater.dispatcher.add_handler(tg_ext.MessageHandler(tg_ext.Filters.regex(p1), read_hw))

def write_hw(update, context):
    if update.message.photo:
        database.write(key=HW_SEARCH.search(update.message.text).groups()[0].lower(),
                       hw_text=update.message.caption,
                       hw_photoid=update.message.photo[0].file_id)
    else:
        database.write(key=HW_SEARCH.search(update.message.text).groups()[0].lower(),
                       hw_text=context.match.groups()[1])
    update.message.reply_text('Д/З записано')
hw_write_match = re.compile(f"^({'|'.join(kw)}).*[:-] (.*)", re.IGNORECASE)
updater.dispatcher.add_handler(tg_ext.MessageHandler(tg_ext.Filters.regex(hw_write_match) | tg_ext.Filters.photo, write_hw))




updater.start_webhook(listen='0.0.0.0', port=int(os.environ.get('PORT', 5000)), url_path=data.TOKEN1)
updater.bot.set_webhook(data.WEBHOOK_URL)
updater.idle()