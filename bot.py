import datetime as dt
import telegram as tg
import telegram.ext as tg_ext
import data
import re
from hw_request import get_hw
from pytz import timezone
import os
updater = tg_ext.Updater(token=data.token1, use_context=True)

homework = {}
kw = {'англ': 'Англ.яз', 'алг': "Алгебра", "био": "Биология", "гео": "География", "физр": "Физра", "физик": "Физика", "лит": "Литра", "хим": "Химия", "геометр": "Геометрия", "нем": "Нем./Франц.яз", "фр": "Нем./Франц.яз", "ист": "История", "общ": "Обществознание", "рус": "Рус.яз", "тех": "Технология", "обж": "ОБЖ", "родн": "Родн.яз"}
tables = {'Англ.яз': 'english', 'Алгебра': 'algebra', 'Биология': 'biology', 'География': 'geography', 'Физра': 'PE', 'Физика': 'physics', 'Литра': 'literature', 'Химия': 'chemistry', 'Геометрия': 'geometry', 'Нем.': 'german','Франц.яз':'french', 'История': 'history', 'Обществознание': 'sociology', 'Рус.яз': 'russian', 'Технология': 'technology', 'ОБЖ': 'obzh'}
schedule = ['8:10 - 8:50', '9:00 - 9:40', '9:55 - 10:35', '10:50 - 11:30', '11:45 - 12:25', '12:35 - 13:15', '13:25 - 14:05']

def stop_bot(update, context):
    if update.message.from_user.id==420736786:
        update.message.reply_text('Бот отключен')
        updater.bot.delete_webhook()
        updater.stop()
    else:
        update.message.reply_sticker(sticker='CAACAgIAAxkBAAMcX6LrsyrpHv72CRJy6kpNife4oIgAAgYAAxLvExmDIS_rRvj5qR4E')
updater.dispatcher.add_handler(tg_ext.CommandHandler('stop', stop_bot))

def daily_schedule(context):
    hw = get_hw()
    if hw['valid']:
        res_str = 'Расписание на завтра:\n'
        for i in hw['content'][dt.datetime.now().weekday()]['lessons']:
            res_str += f"{i['discipline']}({i['time_begin'][:-3]} - {i['time_end'][:-3]}):\nД/З - {i['homework']}\n"
        context.bot.send_message(chat_id='-1001265019760', text=res_str)
updater.job_queue.run_daily(daily_schedule, time=dt.time(hour=18, tzinfo=timezone('Europe/Moscow')), days=list(range(6)))

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
                    hw = (lesson['discipline'], day['date'], lesson['homework'])
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
                            hw = (lesson['discipline'], day['date'], lesson['homework'])
                            break
                    if hw:
                        break
                if not hw:
                    update.message.reply_text('Ошибка: предмет не найден')
                    return
            else:
                update.message.reply_text('Ошибка: '+res['error'])
                return
    else:
        update.message.reply_text('Ошибка: '+res['error'])
        return
    update.message.reply_text(f'Д/З по предмету {hw[0]} на {hw[1]}: {hw[2]}')
p1 = re.compile(f".*((что|че).*по.?({'|'.join(kw)})|по.?({'|'.join(kw)}).+(что|че)[- ]?(то)?.*зад.*)", re.IGNORECASE)
updater.dispatcher.add_handler(tg_ext.MessageHandler(tg_ext.Filters.regex(p1), read_hw))



updater.start_webhook(listen='0.0.0.0', port=int(os.environ.get('PORT', 5000)), url_path=data.token1)
updater.bot.set_webhook(data.webhook_url)
updater.idle()