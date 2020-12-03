import urllib.request
import urllib.parse
from datetime import datetime, timedelta
import re
import json

def get_hw(cur_date=datetime.now().strftime('%Y-%m-%d')):  #cur_date должно быть класса str в формате 'год-месяц-день'
    cur_date = datetime.strptime(cur_date, '%Y-%m-%d')  #преобразование параметра функции в дату
    
    if cur_date.weekday()==5:
        cur_date = cur_date+timedelta(days=2)   #если день недели - суббота, дата сдвигается на следующую неделю
        
    r = urllib.request.Request('https://sh-open.ris61edu.ru/auth/login',
                                data=urllib.parse.urlencode((('login_login', '36_Курдов_Тимофей_36'), ('login_password', 'faYUzEUK'))).encode(),
                                method='POST',
                                unverifiable=True)
    r = urllib.request.urlopen(r)   #залогиниться
    print(r.code)
    if r.status>=400:
        return {'valid': False, 'error': r.geturl()[28:]+'->'+str(r.code)}    #вернуть ошибку в случае неудачи
        
    cookies = [i for i in re.split('[;,] ', r.headers.get('Set-Cookie')) if re.match('(sessionid|NodeID)', i)]   #сохранить cookie-файлы
        
    r2 = urllib.request.Request('https://sh-open.ris61edu.ru/personal-area/#diary',
                                headers={'Cookie':'; '.join(cookies)},
                                method='GET',
                                unverifiable=True)
    r2 = urllib.request.urlopen(r2)   #зайти на сайт
    print(r2.code)
    if r2.code>=400:
        return {'valid': False, 'error': r2.geturl()[28:]+'->'+str(r2.code)}    #вернуть ошибку в случае неудачи
        
    r3 = urllib.request.Request('https://sh-open.ris61edu.ru/api/ScheduleService/GetDiary',
                                data=urllib.parse.urlencode((('date', cur_date.strftime('%Y-%m-%d')), ('is_diary', 'true'))).encode(),
                                headers={'Cookie':'; '.join(cookies)},
                                method='POST',
                                unverifiable=True)
    r3 = urllib.request.urlopen(r3)    #получить расписание от дневника
    print(r3.code)
    if r3.code>=400:
        return {'valid': False, 'error': r3.geturl()[28:]+'->'+str(r3.code)}   #вернуть ошибку в случае неудачи
    return {'valid': True, 'content': json.loads(r3.read().decode())['days']}