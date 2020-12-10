import datetime as dt
import telegram as tg
import telegram.ext as tg_ext
import data
import re
from hw_request import get_hw
from pytz import timezone
import database
import os
updater = tg_ext.Updater(token=data.token1, use_context=True)

homework = {}
kw = ['англ', 'алг', 'био', 'геог', 'физр', 'физик', 'лит', 'хим', 'геом', 'нем', 'фр', 'ист', 'общ', 'рус', 'тех', 'обж', 'родн']
tables = {'Англ.яз': 'english', 'Алгебра': 'algebra', 'Биология': 'biology', 'География': 'geography', 'Физра': 'PE', 'Физика': 'physics', 'Литра': 'literature', 'Химия': 'chemistry', 'Геометрия': 'geometry', 'Нем.': 'german','Франц.яз':'french', 'История': 'history', 'Обществознание': 'sociology', 'Рус.яз': 'russian', 'Технология': 'technology', 'ОБЖ': 'obzh'}
schedule = ['8:10 - 8:50', '9:00 - 9:40', '9:55 - 10:35', '10:50 - 11:30', '11:45 - 12:25', '12:35 - 13:15', '13:25 - 14:05']

HW_SEARCH = re.compile(f"({'|'.join(kw)})", re.IGNORECASE)

def stop_bot(update, context):
    if update.message.from_user.id==420736786:
        update.message.reply_text('Бот отключен')
        updater.bot.delete_webhook()
        updater.stop()
    else:
        update.message.reply_sticker(sticker='CAACAgIAAxkBAAMcX6LrsyrpHv72CRJy6kpNife4oIgAAgYAAxLvExmDIS_rRvj5qR4E')
updater.dispatcher.add_handler(tg_ext.CommandHandler('stop', stop_bot))

def daily_schedule(context):
    if dt.datetime.now().weekday()==5:
        hw = get_hw((dt.datetime.now()+dt.timedelta(days=3)).strftime('%Y-%m-%d'))
        target_weekday = 0
    else:
        hw = get_hw()
        target_weekday = dt.datetime.now().weekday()+1
        
    if hw['valid']:
        parsed_hw = 'Расписание на завтра:\n'
        photos = []
        for i in hw['content'][target_weekday]['lessons']:
            hw_shortcut = HW_SEARCH.search(i['discipline']).groups()[0].lower()
            
            db_hw = database.read(hw_shortcut)
            if db_hw['hw_photoid']:
                photos.append((db_hw['photoid'], i['discipline']))
            lesson_hw = i['homework'] if i['homework'] else db_hw['text']+(f'(фото {len(photos)})' if db_hw['photoid'] else '')
            parsed_hw+=f"{i['discipline']}({i['time_begin'][:5]} - {i['time_end'][:5]})\nД/З - {lesson_hw}\n"
            
            updater.bot.send_message(chat_id='-1001265019760', text=parsed_hw)
            if photos:
                updater.bot.send_media_group(chat_id='-1001265019760', media=[tg.InputMediaPhoto(media=i[0], caption=i[1]) for i in photos])
    else:
        updater.job_queue.run_once(daily_schedule, 600)
updater.job_queue.run_daily(daily_schedule, dt.time(hour=18, tzinfo=timezone('Europe/Moscow')), days=list(range(6)))

res_global = (None, None)
def read_hw(update, context):
    global res_global
    if res_global[0]:
        if dt.datetime.now()-res_global[1]>dt.timedelta(minutes=3):
            res_global = (get_hw(), dt.datetime.now())
    else:
        res_global = (get_hw(), dt.datetime.now())
    if not res_global[0]['valid']:
        update.message.reply_text('Ошибка: '+res_global[0]['error'])
        return
    res = res_global[0]
    hw = None
    if res['valid']:
        for day in res['content'][dt.datetime.now().weekday()+1:-1]:
            for lesson in day['lessons']:
                groups = context.match.groups()
                if (groups[2] if groups[2] else groups[3]) in lesson['discipline'].lower():
                    hw = [lesson['discipline'], day['date'], lesson['homework']]
                    break
            if hw:
                break
        if not hw:
            res = get_hw((dt.datetime.now()+dt.timedelta(days=7)).strftime('%Y-%m-%d'))
            if res['valid']:
                for day in res['content'][:dt.datetime.now().weekday()+1]:
                    for lesson in day['lessons']:
                        groups = context.match.groups() 
                        if (groups[2] if groups[2] else groups[3]) in lesson['discipline'].lower():
                            hw = [lesson['discipline'], day['date'], lesson['homework']]
                            break
                    if hw:
                        break
                if not hw:
                    update.message.reply_text('Ошибка: предмет не найден')
                    return
            else:
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
        if hw[2]=='':
            hw[2] = database.read((groups[2] if groups[2] else groups[3]))
    else:
        db_hw = database.read((groups[2] if groups[2] else groups[3]))
        if db_hw:
            if db_hw['photoid']:
                update.message.reply_photo(photo=db_hw['photoid'], caption='Д/З: '+db_hw['text']+'(фото выше)')
            else:
                update.message.reply_text('Д/З: '+db_hw['text'])
        else:
            update.message.reply_text('Ошибка: '+res['error'])
        return
    if type(hw[2])==dict:
        if hw[2]['photoid']:
            update.message.reply_photo(photo=db_hw['photoid'], caption=db_hw['text'])
        else:
            update.message.reply_text(db_hw['text'])
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



updater.start_webhook(listen='0.0.0.0', port=int(os.environ.get('PORT', 5000)), url_path=data.token1)
updater.bot.set_webhook(data.webhook_url)
updater.idle()