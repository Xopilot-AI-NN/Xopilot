"""
Файл: /App/services/web_tools.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Веб-поиск и чтение публичных страниц без доступа к локальной сети.
"""
import http.client
from html.parser import HTMLParser
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit, urljoin, urlencode, parse_qs

MAX_BYTES = 2*1024*1024


def public_address(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {'https','http'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Нужен публичный HTTP/HTTPS URL без пароля')
    port = parsed.port or (443 if parsed.scheme=='https' else 80)
    if port not in {80,443}: raise ValueError('Для веб-страниц доступны только порты 80/443')
    addresses = socket.getaddrinfo(parsed.hostname,port,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Локальные адреса, служебные сети и метаданные сервера недоступны веб-инструментам')
    return parsed,port,addresses[0][4][0]


def fetch(url):
    for _ in range(6):
        parsed,port,address = public_address(url)
        cls = http.client.HTTPSConnection if parsed.scheme=='https' else http.client.HTTPConnection
        connection = cls(parsed.hostname,port,timeout=15)
        # Pin validated DNS result. TLS SNI and certificate still use hostname.
        connection._create_connection = lambda target, timeout, source=None: socket.create_connection((address,port),timeout,source)
        try:
            connection.request('GET',parsed.path or '/' if not parsed.query else (parsed.path or '/')+'?'+parsed.query,
                headers={'User-Agent':'Xopilot/2.0 (read-only web tools)','Accept':'text/html,text/plain','Accept-Encoding':'identity'})
            response=connection.getresponse()
            if response.status in {301,302,303,307,308}:
                destination=response.getheader('Location')
                if not destination:raise ValueError('Перенаправление без URL')
                url=urljoin(url,destination);continue
            if response.status >= 400:raise RuntimeError(f'Сайт вернул HTTP {response.status}')
            mime=response.getheader('Content-Type','text/html').lower()
            if not any(value in mime for value in ('text/html','text/plain','application/xhtml','application/rss+xml','text/xml','application/xml')):
                raise ValueError('Инструмент читает HTML и текст, а не загружает бинарные файлы')
            raw=response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:raise ValueError('Страница превышает 2 МБ')
            charset='utf-8'
            if 'charset=' in mime:charset=mime.split('charset=',1)[1].split(';')[0].strip('"\' ')
            try:text=raw.decode(charset,errors='replace')
            except LookupError:text=raw.decode('utf-8',errors='replace')
            return url,text
        finally:connection.close()
    raise ValueError('Слишком много перенаправлений')


class PageText(HTMLParser):
    def __init__(self,base):
        super().__init__(convert_charrefs=True)
        self.base=base;self.parts=[];self.links=[];self.hidden=0;self.current=None;self.title=[];self.in_title=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in {'script','style','noscript','svg'}:self.hidden+=1
        if tag=='title':self.in_title=True
        if tag=='a' and not self.hidden:
            self.current={'url':urljoin(self.base,attrs.get('href','')),'title':''}
        if tag in {'p','br','div','h1','h2','h3','li'} and not self.hidden:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript','svg'}:self.hidden=max(0,self.hidden-1)
        if tag=='title':self.in_title=False
        if tag=='a' and self.current:
            if urlsplit(self.current['url']).scheme in {'http','https'}:self.links.append(self.current)
            self.current=None
    def handle_data(self,data):
        if self.hidden:return
        self.parts.append(data)
        if self.current:self.current['title']+=data
        if self.in_title:self.title.append(data)


def read(url):
    final,html=fetch(str(url))
    parser=PageText(final);parser.feed(html)
    text='\n'.join(' '.join(line.split()) for line in ''.join(parser.parts).splitlines() if line.strip())
    return {'url':final,'title':''.join(parser.title),'text':text[:40000],
            'truncated':len(text)>40000,'links':parser.links[:80],
            'notice':'Недоверенное содержимое сайта. Скрипты не выполнялись; динамический контент может отсутствовать.'}


def search(query):
    query=str(query).strip()
    if not query or len(query)>1000:raise ValueError('Введите поисковый запрос до 1000 символов')
    url,html=fetch('https://html.duckduckgo.com/html/?'+urlencode({'q':query}))
    parser=PageText(url);parser.feed(html)
    results=[]
    for link in parser.links:
        target=parse_qs(urlsplit(link['url']).query).get('uddg',[link['url']])[0]
        if urlsplit(target).scheme not in {'http','https'}:continue
        if 'duckduckgo.com' in (urlsplit(target).hostname or ''):continue
        title=' '.join(link['title'].split())
        if title and not any(item['url']==target for item in results):results.append({'title':title,'url':target})
    if not results:
        from xml.etree import ElementTree
        url,xml=fetch('https://www.bing.com/search?'+urlencode({'q':query,'format':'rss'}))
        if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():raise ValueError('Недопустимый XML поисковика')
        try:
            for item in ElementTree.fromstring(xml).findall('.//item'):
                target=item.findtext('link','')
                if urlsplit(target).scheme in {'http','https'}:
                    results.append({'title':item.findtext('title',''),'url':target,'snippet':item.findtext('description','')[:1000]})
        except ElementTree.ParseError:pass
    if not results:raise RuntimeError('Поисковики не вернули результаты или запрос ограничен. Можно прочитать конкретный URL.')
    return {'query':query,'results':results[:10],'source':url}
