from urllib3 import PoolManager, disable_warnings, Timeout
from datetime import datetime, timedelta
import re
import json
import os

def get_hw():
    disable_warnings()   #отключение предупреждений о незащищенном соединении
    this_week = datetime.now()   #получение нынешнего времени
    next_week = this_week+timedelta(days=7)        #определение даты для получения информации на следующею неделю
    
    with PoolManager(cert_reqs='CERT_NONE', timeout=Timeout(connect=5.0)) as http:
        
        error = None
        
        try:
            r = http.request('POST', 'https://sh-open.ris61edu.ru/auth/login',
                             fields={'login_login': '36_Курдов_Тимофей_36', 'login_password': 'faYUzEUK'}) #регистрация на сайте
        except:
            error = 'Локальная ошибка: не удалось установить соединение'
        print(r.status)
        if r.status>=400 and not error:
            error = f'Ошибка сервера: не удалось авторизоваться(код ошибки: {r.status})'
            
        cookies = [i for i in re.split('[;,] ', r.getheader('Set-Cookie')) if re.match('(sessionid|NodeID)', i)]
        r2 = http.request('GET', 'https://sh-open.ris61edu.ru/personal-area/#diary',
                          headers={'Cookie':'; '.join(cookies)})   #вход на главную страницу сайта
                                                                   #(без этого действия сайт не даст информацию)
        print(r2.status)
        if r2.status>=400 and not error:
            error = f'Ошибка сервера: не удалось войти в главное меню сайта(код ошибки: {r.status})'
        
        r3 = http.request('POST', 'https://sh-open.ris61edu.ru/api/ScheduleService/GetDiary',
                    fields={'date': this_week.strftime('%Y-%m-%d'), 'is_diary': 'true'},
                    headers={'Cookie':'; '.join(cookies),
                             'Content-Type': 'application/x-www-form-urlencoded',
                             'Content-Length': '29'},
                          encode_multipart=False)#получение информации на нынешнюю(если сегодня суббота - следующую) неделю
        print(r3.status)
        if r3.status>=400 and not error:
            error = 'Ошибка сервера: не удалось кешировать данные'
        
        r4 = http.request('POST', 'https://sh-open.ris61edu.ru/api/ScheduleService/GetDiary',
                    fields={'date': next_week.strftime('%Y-%m-%d'), 'is_diary': 'true'},
                    headers={'Cookie':'; '.join(cookies),
                             'Content-Type': 'application/x-www-form-urlencoded',
                             'Content-Length': '29'},
                          encode_multipart=False)   #получение информации на неделю, идущую после this_week
        print(r4.status)
        if r4.status>=400 and not error:
            error = 'Ошибка сервера: не удалось кешировать данные'
    if error:
        res = {'read_at': datetime.now().isoformat(),
               'valid': False,
               'error': error
              }
    else:
        res = {'read_at': datetime.now().isoformat(),
               'valid': True,
               'content': json.loads(r3.data.decode())['days']+json.loads(r4.data.decode())['days']
              }
    with open(os.environ['CACHE_FILENAME'], 'w') as hw_writer:
        hw_writer.write(json.dumps(res))
    return res