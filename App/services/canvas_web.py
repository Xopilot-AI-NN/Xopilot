"""
Файл: /App/services/canvas_web.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Изолированный просмотр HTML/CSS/JS в Canvas, чтение DOM и
          взаимодействие с сайтом. Браузер запускается только по запросу.
          Нет доступа к файлам ПК, shell, загрузкам, внешней сети или вкладкам пользователя.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import shutil
import tempfile
import threading
from pathlib import Path
from . import canvases
from .platforms import is_android

_lock = threading.RLock()
_sessions = {}
POLICY = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'"
DOM = """() => ({title:document.title, text:document.body?.innerText.slice(0,24000)||'',
 elements:Array.from(document.querySelectorAll('button,a,input,textarea,select,[role=button]')).slice(0,150).map((e,index)=>{
 const r=e.getBoundingClientRect();return {index,tag:e.tagName,id:e.id, name:e.getAttribute('name'),
 text:e.innerText?.slice(0,200)||e.getAttribute('aria-label')||'', type:e.type,
 value:e.type==='password'?'[password]':e.value, x:r.x,y:r.y,width:r.width,height:r.height}})})"""


class WebSession:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='CanvasWeb')
        self.browser = self.driver = self.page = None
        self.cdp = None
        self.digest = None
        self.folder = Path(tempfile.mkdtemp(prefix='xopilot-canvas-preview-'))
        self.timer = None
        self.closed = False
        self.mutex = threading.RLock()

    def call(self, content, action=None):
        with self.mutex:
            if self.closed: raise ValueError('Просмотр закрыт; откройте его заново')
            if self.timer: self.timer.cancel()
            self.timer = threading.Timer(90, self.close); self.timer.daemon = True; self.timer.start()
            return self.executor.submit(self._call, content, action or {}).result(timeout=25)

    def _call(self, content, action):
        if self.page is None:
            from playwright.sync_api import sync_playwright
            self.driver = sync_playwright().start()
            if not Path(self.driver.chromium.executable_path).is_file():
                self.driver.stop();self.driver=None
                raise RuntimeError('Установите компонент просмотра сайтов кнопкой в Canvas. Он скачивается один раз и запускается только при просмотре.')
            try:
                self.browser = self.driver.chromium.launch(headless=True, chromium_sandbox=True)
                context = self.browser.new_context(viewport={'width': 960, 'height': 600},
                    accept_downloads=False, service_workers='block', permissions=[])
                context.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8',
                    headers={'Content-Security-Policy': POLICY}, body=content)
                    if route.request.url == 'http://canvas.xopilot.invalid/' else route.abort())
                self.page = context.new_page(); self.page.set_default_timeout(3500)
                self.cdp = context.new_cdp_session(self.page)
                self.page.on('popup', lambda popup: popup.close())
            except Exception:
                if self.browser: self.browser.close(); self.browser=None
                self.driver.stop(); self.driver=None
                raise
        digest = hashlib.sha256(content.encode()).hexdigest()
        if self.digest != digest:
            # Replace the one synthetic route with the current edited document.
            self.page.context.unroute('**/*')
            self.page.context.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8',
                headers={'Content-Security-Policy': POLICY}, body=content)
                if route.request.url == 'http://canvas.xopilot.invalid/' else route.abort())
            self.page.goto('http://canvas.xopilot.invalid/', wait_until='domcontentloaded')
            self.digest = digest
        operation = action.get('action')
        if operation in {'click', 'fill'}:
            selector = str(action.get('selector', ''))
            if not selector: raise ValueError('Передайте CSS selector из DOM')
            target = self.page.locator(selector)
            if target.count() != 1: raise ValueError('CSS selector должен указывать ровно на один элемент')
            if operation == 'click': target.click()
            else: target.fill(str(action.get('text', '')))
        elif operation == 'viewport':
            self.page.set_viewport_size({'width':max(240,min(1920,int(action['width']))),
                                         'height':max(160,min(1600,int(action['height'])))})
        elif operation in {'back','forward'}:
            history=self.cdp.send('Page.getNavigationHistory')
            index=history['currentIndex']+(-1 if operation=='back' else 1)
            if 0 <= index < len(history['entries']) and history['entries'][index]['url'].startswith('http://canvas.xopilot.invalid/'):
                self.cdp.send('Page.navigateToHistoryEntry',{'entryId':history['entries'][index]['id']})
                self.page.wait_for_load_state('domcontentloaded')
        elif operation == 'point':
            x, y = float(action['x']), float(action['y'])
            viewport=self.page.viewport_size
            if not 0 <= x < viewport['width'] or not 0 <= y < viewport['height']: raise ValueError('Координаты вне области Canvas')
            self.page.mouse.click(x, y)
        elif operation == 'type': self.page.keyboard.insert_text(str(action.get('text', '')))
        elif operation == 'scroll': self.page.mouse.wheel(0, max(-600, min(600, float(action.get('dy', 300)))))
        elif operation == 'reload': self.page.reload(wait_until='domcontentloaded')
        elif operation: raise ValueError('Действия Canvas: click/fill/point/type/scroll/reload')
        snapshot = self.page.evaluate(DOM)
        history=self.cdp.send('Page.getNavigationHistory')
        index=history['currentIndex'];entries=history['entries']
        navigation={name:0 <= i < len(entries) and entries[i]['url'].startswith('http://canvas.xopilot.invalid/')
                    for name,i in [('can_go_back',index-1),('can_go_forward',index+1)]}
        fragment='#'+self.page.url.split('#',1)[1] if '#' in self.page.url else ''
        path = self.folder / 'viewport.png'
        try:self.page.screenshot(path=str(path), animations='disabled')
        except Exception as exc:
            if 'Unable to capture screenshot' not in str(exc):raise
            self.page.wait_for_timeout(100)
            self.page.screenshot(path=str(path),animations='disabled')
        return {**snapshot, **navigation, 'fragment':fragment, 'screenshot': str(path), **self.page.viewport_size,
                'network': 'blocked', 'scripts': 'isolated'}

    def close(self):
        with self.mutex:
            if self.closed: return
            self.closed=True
            if self.timer: self.timer.cancel()
        def dispose():
            if self.browser: self.browser.close()
            if self.driver: self.driver.stop()
            shutil.rmtree(self.folder, ignore_errors=True)
        try: self.executor.submit(dispose).result(timeout=15)
        finally: self.executor.shutdown(wait=False, cancel_futures=True)


def document(chat_id, workspace_id, identifier):
    if chat_id < 0: raise ValueError('Просмотр сайта недоступен в защищённом/временном чате')
    value = canvases.resolve_document(chat_id, workspace_id, identifier)
    if value['kind'] != 'web' and Path(value['title']).suffix.lower() not in {'.html', '.htm'}:
        raise ValueError('Для просмотра сайта выберите тип Canvas «Сайт» или HTML-файл')
    return value


def inspect(chat_id, workspace_id, identifier, action=None, *, presentation=None):
    value = document(chat_id, workspace_id, identifier)
    identifier = value['id']
    if is_android():
        from . import mobile_runtime
        import base64
        result = mobile_runtime.call('canvasWeb', {'id': identifier, 'html': value['content'],
            'presentation':presentation or {}, **(action or {})})
        result = json.loads(result) if isinstance(result, str) else result
        if result.get('image'):
            from .paths import app_data_dir
            root = app_data_dir() / 'runtime/canvas-preview'; root.mkdir(parents=True, exist_ok=True)
            path = root / (identifier+'.png'); path.write_bytes(base64.b64decode(result.pop('image'), validate=True))
            result['screenshot'] = str(path)
        return result
    key = (chat_id, identifier)
    with _lock:
        session = _sessions.get(key)
        if session is None or session.closed:
            # Opening another document releases the old browser on this chat.
            for old_key in list(_sessions):
                if old_key[0] == chat_id:
                    _sessions.pop(old_key).close()
            session = _sessions[key] = WebSession()
    return session.call(value['content'], action)


def close(chat_id, identifier):
    if is_android():
        from .mobile_runtime import call
        from .paths import app_data_dir
        try: return call('canvasWebClose')
        finally: (app_data_dir() / 'runtime/canvas-preview' / (identifier+'.png')).unlink(missing_ok=True)
    with _lock: session = _sessions.pop((chat_id, identifier), None)
    if session: session.close()


def install_browser():
    if is_android():raise ValueError('Android использует встроенный просмотр сайтов')
    import subprocess
    from playwright._impl._driver import compute_driver_executable
    executable,cli=compute_driver_executable()
    subprocess.run([str(executable),str(cli),'install','chromium'],check=True,timeout=600,stdout=subprocess.DEVNULL)
    return True
