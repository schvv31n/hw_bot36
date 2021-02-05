import os
import json
import datetime as dt
import telegram as tg
import telegram.ext as tg_ext
import re
import psycopg2
from hw_request import get_hw
from pytz import timezone
import traceback
import sys
#константы
LESSONS_SHORTCUTS = ['англ', 'алг', 'био', 'геог', 'физик', 'физ', 'лит', 'хим', 'геом', 'немец', 'фр', 'ист', 'общ', 'рус', 'тех', 'обж', 'родн', 'инф']
HW_SEARCH = re.compile(f"({'|'.join(LESSONS_SHORTCUTS)})", re.IGNORECASE)   #простой match обьект для поиска названий предметов
LESSONS_STARTS = [{'hour': 8, 'minute': 10}, {'hour': 9, 'minute': 0}, {'hour': 9, 'minute': 55}, {'hour': 10, 'minute': 50}, {'hour': 11, 'minute': 45}, {'hour': 12, 'minute': 35}, {'hour': 13, 'minute': 25}]
HTML_UNWRAPPER = re.compile('<[;,. /a-zA-Z0-9=\'"]*>', re.ASCII)

#настройка бота и базы данных
with psycopg2.connect(os.environ['DATABASE_URL'], sslmode='require') as db:
    with db.cursor() as c:
        c.execute('SELECT * FROM hw')
        hw_dict = {
            os.environ['TARGET_CHAT_ID']: {
                'hw': {i[0]: {'text': i[1], 'photoid': i[2].split('<d>'), 'outdated': i[3]} for i in c.fetchall()},
                'media_groups': {}
            }
        }
print(hw_dict)
cache_loader = tg_ext.DictPersistence(chat_data_json=json.dumps(hw_dict))
updater = tg_ext.Updater(token=os.environ['TOKEN'], use_context=True, persistence=cache_loader)

def _unwrap_html(src):
    res = src
    for match in HTML_UNWRAPPER.findall(src):
        res = res.replace(match, '')
    return res

#декораторы

def handle_chat_data(f):
    def decorated(update, context):
        for key in ['hw', 'media_groups']:
            if not context.chat_data.get(key):
                context.chat_data[key] = {}
        f(update, context)
    return decorated

def groupadmin_function(f):
    def decorated(update, context):
        if update.effective_chat.type!='private':
            admins = update.effective_chat.get_administrators()
            if update.message.from_user.id in [i.user.id for i in admins]:
                f(update, context)
            else:
                update.message.reply_text('Данная функция доступна только админам группы')
        else:
            update.message.reply_text('Данная функция доступна только в группе')
    return decorated

def local_hw_cleaner(index):
    def decorated(context):
        print('initialized local_hw_cleaner')
        with open(os.environ['CACHE_FILENAME']) as hw_reader:
            hw = json.loads(hw_reader.read())
            
        today = dt.datetime.now().weekday()
        if hw['valid']:
            lessons = hw['content'][today]['lessons']
            lesson_shortcut = HW_SEARCH.search(lessons[min(len(lessons)-1, index)]['discipline']).groups()[0]
            if context.dispatcher.chat_data[os.environ['TARGET_CHAT_ID']].get(lesson_shortcut):
                context.dispatcher.chat_data[os.environ['TARGET_CHAT_ID']][lesson_shortcut]['outdated'] = True
    return decorated
                
#фоновые функции

def update_db():
    print('updating local database...')
    with psycopg2.connect(os.environ['DATABASE_URL'], sslmode='require') as db:
        with db.cursor() as c:
            c.execute('DELETE FROM hw')
            for k, v in dict(updater.dispatcher.chat_data)[int(os.environ['TARGET_CHAT_ID'])]['hw'].items():
                c.execute('INSERT INTO hw VALUES (%s, %s, %s, %s)', (k, v['text'], '<d>'.join(v['photoid']), v['outdated']))
            c.execute('SELECT * FROM hw')
            print(c.fetchall())

def errors(update, context=None):   
    try:
        raise context.error   #структура работы error handler модуля telegram
    except Exception as err:
        if type(err)==tg.error.Conflict:
            updater.bot.send_message(
                chat_id=os.environ['CREATOR_ID'],
                text='Ошибка: несколько программ подключены к одному боту'
            )
        else:
            tb = traceback.format_exc()   #преобразовать информацию об ошибке в понятный и подробный вид
            tb = tb[max(0, len(tb) - tg.constants.MAX_MESSAGE_LENGTH):]
            if type(update)==tg_ext.Updater:    #проверить, передан ли update обьект в функцию
                update.effective_chat.send_message(text='Неизвестная ошибка: \n'+tb)   #отправить текст ошибки в чат, с которого пошла ошибка
            else:
                updater.bot.send_message(chat_id=os.environ['CREATOR_ID'], text=tb)  #отправить текст ошибки создателю бота
updater.dispatcher.add_error_handler(errors)

def ny_message(context):
    print(200)
    updater.bot.send_message(text='С новым годом!❄', chat_id=os.environ['TARGET_CHAT_ID'])
updater.job_queue.run_once(
    ny_message,
    when=dt.datetime(2021, 12, 31, hour=23, minute=30, tzinfo=timezone('Europe/Moscow'))
)

def daily_schedule(context, force=False):
    with open(os.environ['CACHE_FILENAME']) as hw_reader:
        hw = json.loads(hw_reader.read())
        
    target_weekday = dt.datetime.now().weekday()    
    if target_weekday==5:
        target_weekday += 1
    target_weekday += 1
          
    if hw['valid']:
        if list(hw['content'][target_weekday].keys())[1] not in ['is_weekend', 'is_vacation']:
            parsed_hw = f"Расписание на {hw['content'][target_weekday]['date']}:\n"
            photos = []
        
            for lesson in hw['content'][target_weekday]['lessons']:
                shortcut = HW_SEARCH.search(lesson['discipline']).groups()[0].lower()
                local_hw = updater.dispatcher.chat_data[os.environ['TARGET_CHAT_ID']].get(shortcut, None)
                
                outdated = False
                if lesson['homework']:
                    for material in lesson['materials']:
                        photos.append({'media': material['url'], 'caption': lesson['discipline']})
                elif local_hw:
                    lesson['homework'] = local_hw['text']
                    outdated = local_hw['outdated']
                    for link in local_hw['photoid']:
                        photos.append({'media': link, 'caption': lesson['discipline']})
                
                parsed_hw += f"<b>{lesson['discipline']}({lesson['time_begin'][:5]} - {lesson['time_end'][:5]})</b>\n<i>Тема:</i> {lesson['theme']}\n<i>Д/З{'(возможно устарело)' if outdated else ''}:</i> {_unwrap_html(lesson['homework'])}\n\n"
            
            sent = updater.bot.send_message(chat_id=os.environ['TARGET_CHAT_ID'], text=parsed_hw, parse_mode='HTML')
            if photos:
                updater.bot.send_media_group(chat_id=os.environ['TARGET_CHAT_ID'], media=[tg.InputMediaPhoto(**i) for i in photos])
            pinned = updater.bot.get_chat(os.environ['TARGET_CHAT_ID']).pinned_message
            if pinned:
                if pinned.from_user.is_bot:
                    pinned.unpin()
            sent.pin()
        else:
            if force:
                updater.bot.send_message(chat_id=os.environ['TARGET_CHAT_ID'], text='Ошибка: завтра выходной/каникулы')
updater.job_queue.run_daily(
    daily_schedule,
    dt.time(hour=15, tzinfo=timezone('Europe/Moscow')),
    days=list(range(6))
)

for i, timestamp in enumerate(LESSONS_STARTS):
    updater.job_queue.run_daily(
        local_hw_cleaner(i),
        dt.time(**timestamp, tzinfo=timezone('Europe/Moscow')),
        days=list(range(6))
    )
    
updater.job_queue.run_repeating(lambda c: get_hw(), interval=3600)
updater.job_queue.run_repeating(lambda c: update_db(), interval=3600)

#команды создателя

def stop_bot(update, context):
    if update.message.from_user.id==int(os.environ['CREATOR_ID']):
        update.message.reply_text('Бот отключен')
        updater.bot.delete_webhook()
        updater.stop()
        sys.exit()
updater.dispatcher.add_handler(tg_ext.CommandHandler('stop', stop_bot))

def exec_script(update, context):
        if update.message.from_user.id==int(os.environ['CREATOR_ID']):
            updater.dispatcher.run_async(lambda u=None, c=None: exec(update.message.text[6:]), u=update, c=context)
updater.dispatcher.add_handler(tg_ext.CommandHandler('exec', exec_script))

#команды админов

@groupadmin_function
def update_hw(update, context):
    sent = update.effective_chat.send_message('Обновляю...')
    resp = get_hw()
    if resp['valid']:
        sent.edit_text('Д/З обновлено')
    else:
        sent.edit_text('Ошибка: '+resp['error'])
updater.dispatcher.add_handler(tg_ext.CommandHandler('force_update', update_hw))

@groupadmin_function    
def force_schedule(update, context):
    daily_schedule(context, force=True)
updater.dispatcher.add_handler(tg_ext.CommandHandler('schedule', force_schedule))

def info(update, context):
    update.effective_chat.send_message(f"Версия бота: {os.environ['BOT_VERSION']}\nСоздатель: @schvv31n")
updater.dispatcher.add_handler(tg_ext.CommandHandler('info', info))

@handle_chat_data
def read_hw(update, context):
    with open(os.environ['CACHE_FILENAME']) as hw_reader:
        res = json.loads(hw_reader.read())
        
    target_weekday = dt.datetime.now().weekday()
    end_weekday = None
    groups = context.match.groups()
    keyword = HW_SEARCH.search(groups[2] if groups[2] else groups[3]).groups()[0]
    if 'на сегодня' not in update.message.text.lower():
        if target_weekday==5:
            target_weekday += 1
        target_weekday += 1
    else:
        end_weekday = target_weekday + 1
    
    #парсинг json-данных с сайта
    hw = None
    if res['valid']:
        for day in res['content'][target_weekday:end_weekday]:
            if list(day.keys())[1] in ['is_weekend', 'is_vacation']:
                continue
                
            for lesson in day['lessons']:
                groups = context.match.groups()
                if keyword in lesson['discipline'].lower():
                    hw = [lesson['discipline'], day['date'], _unwrap_html(lesson['homework']), [i['url'] for i in lesson['materials']]]
                    break
            if hw:
                break
                
        if not hw:
            if 'на сегодня' not in update.message.text.lower():
                db_hw = context.chat_data['hw'].get(keyword, '')
                if db_hw:
                    if db_hw['photoid']:
                        photos = [tg.InputMediaPhoto(media=db_hw['photoid'][0], caption=f"Д/З: {db_hw['text']}{'(устарело!)' if db_hw['outdated'] else ''}")]
                        for link in db_hw['photoid'][1:]:
                            photos.append(tg.InputMediaPhoto(media=link))
                        update.message.reply_media_group(media=photos)
                    else:
                        update.message.reply_text('Д/З: '+db_hw['text'])
                else:
                    update.message.reply_text('Ошибка: предмет не найден')
            else:
                update.message.reply_text('Ошибка: предмет не найден')
                print(keyword)
            return
        elif hw[2]=='':
            hw[2] = context.chat_data['hw'].get(keyword, '')
            
    else:
        db_hw = context.chat_data['hw'].get(keyword, {})
        if db_hw.get('photoid', None):
            photos = [tg.InputMediaPhoto(
                media=db_hw['photoid'][0],
                caption=f"Д/З: {db_hw['text']}{'(устарело!)' if db_hw['outdated'] else ''}"
            )]
            for link in db_hw['photoid'][1:]:
                photos.append(tg.InputMediaPhoto(media=link))
            update.message.reply_media_group(media=photos)
        elif db_hw.get('text', None):
            update.message.reply_text('Д/З: '+db_hw['text']+('(устарело!)' if db_hw['outdated'] else ''))
        else:
            update.message.reply_text('Ошибка: '+res['error'])
        return
    #отправка сообщения с данными
    if type(hw[2])==dict:
        if hw[2]['photoid']!=[""]:
            photos = [tg.InputMediaPhoto(media=hw[2]['photoid'][0], caption=f"Д/З по предмету {hw[0]} на {hw[1]}: {hw[2]['text']}{'(устарело!)' if hw[2]['outdated'] else ''}")]
            for link in hw[2]['photoid'][1:]:
                photos.append(tg.InputMediaPhoto(media=link))
            update.message.reply_media_group(media=photos)
        else:
            update.message.reply_text(f"Д/З по предмету {hw[0]} на {hw[1]}: {hw[2]['text']}")
    else:
        if hw[3]:
            photos = [tg.InputMediaPhoto(
                media=hw[3][0],
                caption=f"Д/З по предмету {hw[0]} на {hw[1]}: {_unwrap_html(hw[2])}"
            )]
            for link in hw[3]:
                photos.append(tg.InputMediaPhoto(media=link))
            update.message.reply_media_group(media=photos)
        else:
            update.message.reply_text(f"Д/З по предмету {hw[0]} на {hw[1]}: {_unwrap_html(hw[2])}")
        
p1 = re.compile(f"\\b((что|че)\\b.*по.?({'|'.join(LESSONS_SHORTCUTS)})|по.?({'|'.join(LESSONS_SHORTCUTS)}).+(что|че)[- ]?(то)?.*зад.*)", re.IGNORECASE)
updater.dispatcher.add_handler(tg_ext.MessageHandler(tg_ext.Filters.regex(p1), read_hw))

p2 = re.compile(f"^({'|'.join(LESSONS_SHORTCUTS)}).*[:-] (.*)", re.IGNORECASE+re.MULTILINE)

@handle_chat_data
def write_hw(update, context):
    if update.message.photo:
        if update.message.media_group_id in list(context.chat_data['media_groups'].keys()):  #проверка на id альбома в памяти
            context.chat_data['hw'][context.chat_data['media_groups'][update.message.media_group_id]]['photoid'].append(
                update.message.photo[0].file_id
            )   #добавление фото из сообщения к дз с одинаковым id альбома, что и у нового фото
            
        else:
            hw_match = HW_SEARCH.search(update.message.caption)
            if hw_match:
                actual_hw_text = ''
                hw_full_match = p2.search(update.message.caption)
                
                if hw_full_match:
                    actual_hw_text = hw_full_match.groups()[1]
                    
                context.chat_data['hw'][hw_match.groups()[0].lower()] = {
                    'text': _unwrap_html(actual_hw_text),
                    'photoid': [update.message.photo[0].file_id],
                    'outdated': False
                }
                
                reverse = {b: a for a, b in context.chat_data['media_groups'].items()}
                if context.chat_data['media_groups'].get(reverse.get(hw_match.groups()[0].lower(), None), None):
                    del context.chat_data['media_groups'][reverse[hw_match.groups()[0].lower()]]
                context.chat_data['media_groups'][update.message.media_group_id] = hw_match.groups()[0].lower()
                
                update.message.reply_text('Д/З записано')
    else:
        context.chat_data['hw'][HW_SEARCH.search(update.message.text).groups()[0].lower()] = {
            'text': _unwrap_html(context.match.groups()[1]),
            'photoid': [],
            'outdated': False
        }
        
        print(context.chat_data['media_groups'])
        reverse = {b: a for a, b in context.chat_data['media_groups'].items()}
        if context.chat_data['media_groups'].get(reverse.get(context.match.groups()[0].lower(), None), None):
            del context.chat_data['media_groups'][reverse[context.match.groups()[0].lower()]]
        
        update.message.reply_text('Д/З записано')
updater.dispatcher.add_handler(tg_ext.MessageHandler(tg_ext.Filters.regex(p2) | tg_ext.Filters.photo, write_hw))

if os.path.exists(os.environ['CACHE_FILENAME']):
    with open(os.environ['CACHE_FILENAME']) as cache:
        cache_dict = json.loads(cache.read())
        if dt.datetime.now() - dt.datetime.fromisoformat(cache_dict['read_at']) > dt.timedelta(hours=1):
            get_hw()
else:
    get_hw()

updater.bot.send_message(chat_id=os.environ['CREATOR_ID'], text='Бот включен\nВерсия бота: '+os.environ['BOT_VERSION'])
updater.start_webhook(listen='0.0.0.0', port=int(os.environ.get('PORT', 5000)), url_path=os.environ['TOKEN'])
updater.bot.set_webhook(os.environ['HOST_URL']+os.environ['TOKEN'])
updater.idle()

update_db()
updater.bot.send_message(chat_id=os.environ['CREATOR_ID'], text='Бот отключен')