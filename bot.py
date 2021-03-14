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
import time
#константы
SPECIAL_NAMES = {'Физическая культура': 'Физра'}
LESSONS_SHORTCUTS = ['англ', 'алг', 'био', 'геог', 'физик', 'физр', 'лит', 'хим', 'геом', 'немец', 'фр', 'ист', 'общ', 'рус', 'тех', 'обж', 'инф']
HW_SEARCH = re.compile(f"({'|'.join(LESSONS_SHORTCUTS)})", re.IGNORECASE)   #простой match обьект для поиска названий предметов
LESSONS_STARTS = [{'hour': 8, 'minute': 10}, {'hour': 9, 'minute': 0}, {'hour': 9, 'minute': 55}, {'hour': 10, 'minute': 50}, {'hour': 11, 'minute': 45}, {'hour': 12, 'minute': 35}, {'hour': 13, 'minute': 25}]
HTML_UNWRAPPER = re.compile(f"<[{ ''.join([bytes([i]).decode() for i in range(128) if i not in [60, 62]]) }]*>")
NO_LESSONS = ['is_weekend', 'is_vacation', 'is_holiday']
EMPTY_CHATDATA = {'hw': {},
                  'media_groups': {},
                  'temp': {
                      'media_id': '',
                      'photoids': [],
                      'hw': {}
                  }
                 }

#настройка бота и базы данных
with psycopg2.connect(os.environ['DATABASE_URL'], sslmode='require') as db:
    with db.cursor() as c:
        c.execute('SELECT * FROM hw')
        hw_dict = {
            os.environ['TARGET_CHAT_ID']: {
                'hw': {i[0]: {'text': i[1],
                              'photoid': i[2].split('<d>') if i[2] else [],
                              'outdated': i[3]
                             } for i in c.fetchall()
                      },
                'media_groups': {},
                'temp': {
                    'media_id': '',
                    'photoids': [],
                    'hw': {}
                }
            }
        }
print(hw_dict)
cache_loader = tg_ext.DictPersistence(chat_data_json=json.dumps(hw_dict))
defaults = tg_ext.Defaults(quote=True, tzinfo=timezone('Europe/Moscow'))
updater = tg_ext.Updater(token=os.environ['TOKEN'], use_context=True, persistence=cache_loader, defaults=defaults)

def _unwrap_html(src):
    res = src
    for match in HTML_UNWRAPPER.findall(src):
        res = res.replace(match, '')
    return res

#декораторы

def handle_chat_data(f):
    def decorated(update, context):
        if not context.chat_data:
            context.chat_data.update(EMPTY_CHATDATA)
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
        with open(os.environ['CACHE_FILENAME']) as hw_reader:
            hw = json.loads(hw_reader.read())
            
        today = dt.datetime.now().weekday()
        if hw['valid']:
            if hw['content'][today].keys()[1] not in NO_LESSONS:
                lessons = hw['content'][today]['lessons']
                lesson_shortcut = HW_SEARCH.search(lessons[min(len(lessons)-1, index)]['discipline']).groups()[0].lower()
                if context.dispatcher.chat_data[int(os.environ['TARGET_CHAT_ID'])]['hw'].get(lesson_shortcut):
                    context.dispatcher.chat_data[int(os.environ['TARGET_CHAT_ID'])]['hw'][lesson_shortcut]['outdated'] = True
    return decorated
                
#фоновые функции

def update_db():
    with psycopg2.connect(os.environ['DATABASE_URL'], sslmode='require') as db:
        with db.cursor() as c:
            c.execute('DELETE FROM hw')
            for k, v in dict(updater.dispatcher.chat_data)[int(os.environ['TARGET_CHAT_ID'])]['hw'].items():
                c.execute('INSERT INTO hw VALUES (%s, %s, %s, %s)', (k, v['text'], '<d>'.join(v['photoid']), v['outdated']))
            c.execute('SELECT * FROM hw')
            
def delete_keyboard(context):
    try:
        context.job.context.edit_reply_markup()
    except:
        pass
    else:
        del context.chat_data['temp']['hw'][context.job.context.message_id]

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
        if list(hw['content'][target_weekday].keys())[1] not in NO_LESSONS:
            parsed_hw = f"Расписание на {hw['content'][target_weekday]['date']}:\n"
            photos = []
        
            for lesson in hw['content'][target_weekday]['lessons']:
                full_name = SPECIAL_NAMES.get(lesson['discipline'], lesson['discipline'])
                shortcut = HW_SEARCH.search(full_name.lower()).groups()[0]
                local_hw = updater.dispatcher.chat_data[int(os.environ['TARGET_CHAT_ID'])]['hw'].get(shortcut, None)
                
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
    dt.time(hour=15),
    days=list(range(6))
)

for i, timestamp in enumerate(LESSONS_STARTS):
    updater.job_queue.run_daily(
        local_hw_cleaner(i),
        dt.time(**timestamp),
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
    update_db()
    resp = get_hw()
    if resp['valid']:
        sent.edit_text('Д/З обновлено')
    else:
        sent.edit_text(resp['error'])
updater.dispatcher.add_handler(tg_ext.CommandHandler('force_update', update_hw))

@groupadmin_function    
def force_schedule(update, context):
    daily_schedule(context, force=True)
updater.dispatcher.add_handler(tg_ext.CommandHandler('schedule', force_schedule))

#общие команды

def info(update, context):
    update.effective_chat.send_message(f"Версия бота: {os.environ['BOT_VERSION']}\nСоздатель: @schvv31n")
updater.dispatcher.add_handler(tg_ext.CommandHandler('info', info))

@handle_chat_data
def read_hw(update, context):
    keyword = HW_SEARCH.search(update.message.text).groups()[0]
    buttons = tg.InlineKeyboardMarkup([
        [tg.InlineKeyboardButton(text='Из электронного дневника', callback_data=f"READ_HW#EXT#{keyword}#{'1' if 'сегодня' in update.message.text else ''}")],
        [tg.InlineKeyboardButton(text='Из этого чата', callback_data=f"READ_HW#LOCAL#{keyword}")],
        [tg.InlineKeyboardButton(text='Отмена', callback_data="READ_HW#CANCEL")]
    ])
    
    update.message.reply_text(text='Откуда получить Д/З?', reply_markup=buttons)
        
p1 = re.compile(f"\\b((что|че|чё|чо|шо|що)\\b.*по.?({'|'.join(LESSONS_SHORTCUTS)})|по.?({'|'.join(LESSONS_SHORTCUTS)}).+(что|че)[- ]?(то)?.*зад.*)", re.IGNORECASE)
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
            hw_match = HW_SEARCH.search(update.message.caption if update.message.caption else '')
            if hw_match:
                keyword = hw_match.groups()[0].lower()
                #HW_SEARCH.search(update.message.text).groups()[0].lower()
                prev_hw = context.chat_data['hw'].get(keyword, {})
                actual_hw_text = ''
                hw_full_match = p2.search(update.message.caption)
                
                if hw_full_match:
                    actual_hw_text = hw_full_match.groups()[1]
                    
                if context.chat_data['temp']['media_id'] == update.message.media_group_id:
                    temp_photos = context.chat_data['temp']['photoids']
                else:
                    temp_photos = []
                    
                context.chat_data['hw'][keyword] = {
                    'text': _unwrap_html(actual_hw_text),
                    'photoid': [update.message.photo[0].file_id]+temp_photos,
                    'outdated': False
                }
                context.chat_data['temp']['hw'].update({update.message.message_id: prev_hw})
                
                reverse = {b: a for a, b in context.chat_data['media_groups'].items()}
                if context.chat_data['media_groups'].get(reverse.get(keyword, None), None):
                    del context.chat_data['media_groups'][reverse[keyword]]
                context.chat_data['media_groups'][update.message.media_group_id] = keyword
                
                button = tg.InlineKeyboardMarkup([[
                    tg.InlineKeyboardButton(text='Отмена', callback_data=f"WRITE_HW#CANCEL#{keyword}")
                ]])
        
                answer = update.message.reply_text('Д/З записано', reply_markup=button)
                updater.job_queue.run_once(delete_keyboard, when=10, context=answer)
                
            else:
                print('entry')
                if context.chat_data['temp']['media_id'] == update.message.media_group_id:
                    print('entry1')
                    context.chat_data['temp']['photoids'].append(update.message.photo[0].file_id)
                else:
                    print('entry2')
                    if context.chat_data['temp']['media_id']:
                        print('entry21')
                        context.chat_data['temp']['photoids'] = [update.message.photo[0].file_id]
                    else:
                        context.chat_data['temp']['photoids'].append(update.message.photo[0].file_id)
                    context.chat_data['temp']['media_id'] = update.message.media_group_id
    else:
        keyword = context.match.groups()[0].lower()
        #HW_SEARCH.search(update.message.text).groups()[0].lower()
        prev_hw = context.chat_data['hw'].get(keyword, {})
        
        context.chat_data['hw'][keyword] = {
            'text': _unwrap_html(context.match.groups()[1]),
            'photoid': [],
            'outdated': False
        }
        context.chat_data['temp']['hw'].update({update.message.message_id: prev_hw})
        
        reverse = {b: a for a, b in context.chat_data['media_groups'].items()}
        if context.chat_data['media_groups'].get(reverse.get(keyword)):
            del context.chat_data['media_groups'][reverse[keyword]]
        
        button = tg.InlineKeyboardMarkup([[
            tg.InlineKeyboardButton(text='Отмена', callback_data=f"WRITE_HW#CANCEL#{keyword}")
        ]])
        
        answer = update.message.reply_text('Д/З записано', reply_markup=button)
        updater.job_queue.run_once(delete_keyboard, when=10, context=answer)
        
updater.dispatcher.add_handler(tg_ext.MessageHandler(tg_ext.Filters.regex(p2) | tg_ext.Filters.photo, write_hw))

@handle_chat_data
def delete_hw(update, context):
    subject_index = update.message.text.find('#')
    if subject_index == -1:
        update.message.reply_text('Ошибка: нет названия предмета\nСинтаксис команды: <code>/delete #предмет</code>',
                                  parse_mode='HTML')
        return
    subject = update.message.text[subject_index+1:]
    shortcut = HW_SEARCH.search(subject.lower())
    if not shortcut:
        update.message.reply_text('Ошибка: предмет не найден')
        return
    else:
        shortcut = shortcut.groups()[0]
    prev_hw = context.chat_data['hw'].get(shortcut)
    if not prev_hw:
        update.message.reply_text('Ошибка: Д/З по указанному предмету не найдено')
        return
    
    del context.chat_data['hw'][shortcut]
    context.chat_data['temp']['hw'][update.message.message_id] = prev_hw
    
    button = tg.InlineKeyboardMarkup([[
        tg.InlineKeyboardButton(text='Отмена', callback_data=f"DEL_HW#CANCEL#{shortcut}")
    ]])
    answer = update.message.reply_text(text='Д/З удалено', reply_markup=button)
    updater.job_queue.run_once(delete_keyboard, when=10, context=answer)
updater.dispatcher.add_handler(tg_ext.CommandHandler('delete', delete_hw))

def get_external_hw(subject, for_today=False):
    with open('hw.json') as reader:
        hw = json.loads(reader.read())
        
    target_weekday = dt.datetime.now().weekday()
    end_weekday = None
    if not for_today:
        if target_weekday==5:
            target_weekday += 1
        target_weekday += 1
    else:
        end_weekday = target_weekday + 1    
    date = ''
    full_name = ''
    text = ''
    photos = []
        
    if hw['valid']:
        for day in hw['content'][target_weekday:end_weekday]:
            if list(day.keys())[1] in NO_LESSONS:
                continue
                
            for lesson in day['lessons']:
                if subject in lesson['discipline'].lower():
                    date = lesson['date']
                    full_name = lesson['discipline']
                    text = _unwrap_html(lesson['homework'])
                    photos = [i['url'] for i in lesson['materials']]
                    
            if subject in full_name.lower():
                break
                
        if date:
            return (f'Д/З по предмету {full_name} на {date}: {text}', photos)
        else:
            return ('Предмет не найден', [])
    
    else:
        return (hw['error'], [])
    
def get_local_hw(subject, chat_data):
    res = chat_data['hw'].get(subject, {'text': '', 'photoid': []})
    return ('Д/З: '+res['text'], res['photoid'])

def button_callback(update, context):
    print(update.callback_query.data)
    if update.callback_query.message.reply_to_message.from_user == update.callback_query.from_user:
        args = update.callback_query.data.split('#')
        
        if args[0] == 'READ_HW':
            if args[1] == 'CANCEL':
                update.callback_query.message.delete()
            else:
                if args[1] == 'EXT':
                    res = get_external_hw(args[2], for_today=bool(args[3]))
                elif args[1] == 'LOCAL':
                    res = get_local_hw(args[2], context.chat_data)
                    
                if res[1]:
                    req_msg = update.callback_query.message.reply_to_message
                    update.callback_query.message.delete()
                    
                    photo_objs = [tg.InputMediaPhoto(media=res[1][0], caption=res[0])]
                    photo_objs += [tg.InputMediaPhoto(media=i) for i in res[1][1:]]
                    
                    req_msg.reply_media_group(media=photo_objs)
                else:
                    update.callback_query.message.edit_text(text=res[0])
                    
        elif args[0] == 'WRITE_HW':
            if args[1] == 'CANCEL':
                request_msgid = update.callback_query.message.reply_to_message.message_id
                prev_hw = context.chat_data['temp']['hw'][request_msgid]
                if prev_hw:
                    context.chat_data['hw'][args[2]] = prev_hw
                else:
                    del context.chat_data['hw'][args[2]]
                del context.chat_data['temp']['hw'][request_msgid]
        elif args[0] == 'DEL_HW':
            if args[1] == 'CANCEL':
                request_msgid = update.callback_query.message.reply_to_message.message_id
                prev_hw = context.chat_data['temp']['hw'][request_msgid]
                print(prev_hw)
                context.chat_data['hw'][args[2]] = prev_hw
                del context.chat_data['temp']['hw'][request_msgid]    
                update.callback_query.message.delete()
updater.dispatcher.add_handler(tg_ext.CallbackQueryHandler(button_callback))
        

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