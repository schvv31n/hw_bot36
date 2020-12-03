from urllib3 import PoolManager
from datetime import datetime, timedelta
import re
import json

def get_hw(cur_date=datetime.now().strftime('%Y-%m-%d')):
    cur_date = datetime.strptime(cur_date, '%Y-%m-%d')
    
    if cur_date.weekday()==5:
        cur_date = cur_date+timedelta(days=2)
    
    with PoolManager(cert_reqs='CERT_NONE') as http:
        
        r = http.request('POST', 'https://sh-open.ris61edu.ru/auth/login',
                         fields={'login_login': '36_Курдов_Тимофей_36', 'login_password': 'faYUzEUK'})
        print(r.status)
        if r.status>=400:
            return {'valid': False, 'error': r.geturl()[28:]+'->'+str(r.status)}
        
        cookies = [i for i in re.split('[;,] ', r.getheader('Set-Cookie')) if re.match('(sessionid|NodeID)', i)]
        r2 = http.request('GET', 'https://sh-open.ris61edu.ru/personal-area/#diary',
                          headers={'Cookie':'; '.join(cookies)})
        print(r2.status)
        if r2.status>=400:
            return {'valid': False, 'error': r2.geturl()[28:]+'->'+str(r2.status)}
        
        r3 = http.request('POST', 'https://sh-open.ris61edu.ru/api/ScheduleService/GetDiary',
                    fields={'date': cur_date.strftime('%Y-%m-%d'), 'is_diary': 'true'},
                    headers={'Cookie':'; '.join(cookies),
                             'Content-Type': 'application/x-www-form-urlencoded',
                             'Content-Length': '29'},
                          encode_multipart=False)
        print(r3.status)
        if r3.status>=400:
            return {'valid': False, 'error': r3.geturl()[28:]+'->'+str(r3.status)}
    return {'valid': True, 'content': json.loads(r3.data.decode())['days']}