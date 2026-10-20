"""
Файл: /App/services/billing.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Условия тарифов Zephyr и подтверждённые сервером заказы DonationAlerts.
"""
from decimal import Decimal, ROUND_HALF_UP
import json
import locale
import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from .db import get_db

CURRENCIES={'auto':'Авто по региону устройства','RUB':'Российский рубль · RUB','BYN':'Белорусский рубль · BYN','USD':'Доллар США · USD','EUR':'Евро · EUR'}
PLANS=[
    dict(id='micro',name='Zephyr Micro',rub=0,period='month',quota_bytes=128*1024*1024,available=True,
         features=['Локальные модели и собственный API без ограничений Xopilot',
                   'Canvas: текст, код, рисунки и предпросмотр сайтов',
                   'Пространства, библиотека, документы и память обо мне',
                   'Защищённые и временные чаты, сквозная синхронизация 128 МБ',
                   'Zephyr Micro + 3 сообщения Elite в неделю — после запуска облачных моделей'],remote_jobs=0,top_up=False),
    dict(id='elite',name='Zephyr Elite',rub=1000,period='month',quota_bytes=2*1024*1024*1024,available=False,
         features=['Все возможности Micro',
                   'Облачное хранилище 2 ГиБ · сквозное шифрование',
                   'История завершённых заданий за 1 дн. на участвовавших устройствах',
                   'Удалённые задания с телефона на связанном ПК: 1 активное задание',
                   'Доступ к модели Zephyr Elite после запуска облачных моделей',
                   'Дополнительные токены — после подключения пакетов',
                   'Учреждениям −40% (600 RUB), программистам −20% (800 RUB) после проверки документов'],remote_jobs=1,top_up=True),
    dict(id='ultra',name='Zephyr Ultra',rub=4000,period='month',quota_bytes=10*1024*1024*1024,available=False,
         features=['Все возможности Elite',
                   'Облачное хранилище 10 ГиБ · сквозное шифрование',
                   'История завершённых заданий за 7 дн. на участвовавших устройствах',
                   'До 3 одновременных удалённых заданий на связанных ПК',
                   'Micro, Elite и Ultra — после запуска облачных моделей',
                   'Дополнительные токены — после подключения пакетов'],remote_jobs=3,top_up=True),
    dict(id='led',name='Zephyr Led',rub=7000,period='month',quota_bytes=50*1024*1024*1024,available=False,
         features=['Все возможности Ultra',
                   'Облачное хранилище 50 ГиБ · сквозное шифрование',
                   'История завершённых заданий за 30 дн. на участвовавших устройствах',
                   'Удалённые задания на всех связанных ПК',
                   'Полный доступ к Micro, Elite и Ultra — после запуска облачных моделей',
                   'Без лимита облачных сообщений и токенов; докупка не нужна',
                   'До 30 активных удалённых заданий — техническая защита очереди'],remote_jobs=30,top_up=False),
]
DISCOUNTS={'institution':40,'programmer':20}

def elite_price(category=None,*,verified=False):
    if category not in (None,*DISCOUNTS):raise ValueError('Неизвестная категория скидки')
    return 1000*(100-DISCOUNTS.get(category,0))//100 if verified else 1000


def currency():
    setting=get_db().get_setting('display_currency') or 'auto'
    if setting!='auto':return setting if setting in CURRENCIES else 'RUB'
    region=(locale.getlocale()[0] or os.environ.get('LANG','')).upper()
    try:
        from .platforms import is_android
        if is_android():
            country=json.loads(get_db().get_setting('device_info_v1') or '{}').get('region')
            if isinstance(country,str) and len(country)==2:region='_'+country.upper()
    except (ValueError,TypeError):pass
    if '_BY' in region or 'BELARUS' in region:return 'BYN'
    if '_US' in region or 'UNITEDSTATES' in region:return 'USD'
    if any('_'+country in region for country in ('DE','FR','IT','ES','NL','AT','FI','IE','PT')):return 'EUR'
    return 'RUB'


def set_currency(value):
    if value not in CURRENCIES:raise ValueError('Неизвестная валюта')
    get_db().set_setting('display_currency',value)


def rates():
    try:
        cached=json.loads(get_db().get_setting('cbr_display_rates_v1') or '{}')
        if not isinstance(cached,dict) or not isinstance(cached.get('values'),dict):cached={}
        if cached and (not isinstance(cached.get('fetched_at'),(int,float)) or
                       any(not Decimal(str(v)).is_finite() or Decimal(str(v))<=0 for v in cached['values'].values())):cached={}
    except (ValueError,TypeError,ArithmeticError):cached={}
    if cached and time.time()-cached.get('fetched_at',0)<86400:return cached
    request=urllib.request.Request('https://www.cbr.ru/scripts/XML_daily.asp',headers={'User-Agent':'Xopilot/2.0'})
    try:
        with urllib.request.urlopen(request,timeout=10) as response:
            raw=response.read(512*1024+1)
        if len(raw)>512*1024:raise ValueError('Too large')
        document=ET.fromstring(raw);values={'RUB':'1'}
        for element in document.findall('Valute'):
            code=element.findtext('CharCode')
            if code in ('BYN','USD','EUR'):
                rate=Decimal(element.findtext('Value').replace(',','.'))/Decimal(element.findtext('Nominal'))
                if not rate.is_finite() or rate<=0:raise ValueError('Invalid rate')
                values[code]=str(rate)
        result={'date':document.attrib['Date'],'values':values,'fetched_at':time.time()}
        get_db().set_setting('cbr_display_rates_v1',json.dumps(result));return result
    except Exception:
        # Cached dates remain visible. Unavailable rates never become made-up prices.
        return cached


def prices(approved_discount=None):
    selected=currency();quotes=rates() if selected!='RUB' else {}
    result=[]
    for plan in PLANS:
        row=dict(plan);row['label']='Бесплатно' if plan['rub']==0 else f"{plan['rub']:,} RUB".replace(',',' ')
        if plan['id']=='elite' and approved_discount in DISCOUNTS:
            row['rub']=elite_price(approved_discount,verified=True)
            row['label']=f"{row['rub']} RUB"
        value=quotes.get('values',{}).get(selected)
        if row['rub'] and selected!='RUB' and value:
            amount=(Decimal(row['rub'])/Decimal(value)).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
            row['label']=f'≈ {amount} {selected}';row['base_label']=f"{row['rub']} RUB"
        result.append(row)
    return {'currency':selected,'rate_date':quotes.get('date'),'plans':result}


def account_status():
    from . import cloud_account
    if not cloud_account.state():
        return {'enabled':False,'plan':'micro','expires_at':None,'signed_in':False}
    result = cloud_account.request('/billing')
    result['signed_in'] = True
    return result


def create_order(plan):
    from .cloud_account import request
    if plan not in ('elite','ultra','led'):
        raise ValueError('Выберите платный тариф')
    result = request('/billing/orders',method='POST',body={'plan':plan})
    from urllib.parse import urlsplit
    import uuid
    try:
        order = str(uuid.UUID(result['id']))
        url = urlsplit(result['payment_url'])
        amount = result['amount_kopecks']
        recipient = url.path.removeprefix('/r/')
        allowed_amounts = {'elite':(60000,80000,100000),'ultra':(400000,),'led':(700000,)}
        if (url.scheme != 'https' or url.netloc != 'www.donationalerts.com' or not url.path.startswith('/r/')
                or not recipient or '/' in recipient or not all(c.isascii() and (c.isalnum() or c in '_-') for c in recipient)
                or url.query or url.fragment or result['currency'] != 'RUB' or type(amount) is not int
                or amount not in allowed_amounts[plan] or result.get('plan') != plan
                or result.get('status','pending') != 'pending'
                or result['payment_message'] != 'XOPILOT-'+uuid.UUID(order).hex):
            raise ValueError()
    except (KeyError,ValueError,TypeError):
        raise ValueError('Сервер вернул неверный заказ') from None
    return result


def check_order(identifier):
    import uuid
    from .cloud_account import request
    key=str(uuid.UUID(identifier))
    result=request('/billing/orders/'+key+'/check',method='POST',body={})
    if (not isinstance(result,dict) or result.get('id')!=key or result.get('status') not in
            ('pending','paid','expired','cancelled') or result.get('plan') not in ('elite','ultra','led')):
        raise ValueError('Сервер вернул неверный статус заказа')
    return result


def cancel_order(identifier):
    import uuid
    from .cloud_account import request
    return request('/billing/orders/'+str(uuid.UUID(identifier)),method='DELETE')
