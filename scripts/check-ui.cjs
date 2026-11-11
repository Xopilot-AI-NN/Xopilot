// Описание: Пользовательские сценарии в настоящем Linux WebKit, на отдельной базе.
// Node нужен только разработчику. В установленное приложение мост и стенд не входят.
// dx build --desktop -p xopilot --example interface_interaction
// node scripts/check-ui.cjs
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const http = require('node:http');
const assert = require('node:assert/strict');
const {spawn, execFileSync} = require('node:child_process');
const repository = path.resolve(__dirname, '..');
const root = fs.mkdtempSync('/tmp/xopilot-ui-check-');
// В /tmp часто tmpfs: настоящие веса держим на диске, не занимая гигабайты RAM.
const modelDirectory=process.env.XOPILOT_TEST_MODEL?path.join(repository,'target/ui-models',path.basename(root)):path.join(root,'data/models');
fs.chmodSync(root, 0o700);
const socket = path.join(root, 'ui.sock');
const binary = path.join(repository, 'target/dx/interface_interaction/debug/linux/app/interface_interaction');
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
let child, windowId;
const results = [];
const requests = [];
let agentRequests = 0;

async function evaluate(script) {
    return new Promise((resolve, reject) => {
        const connection = net.createConnection(socket);
        let buffer = '';
        connection.on('connect', () => connection.write(JSON.stringify(script) + '\n'));
        connection.on('error', reject);
        connection.on('data', chunk => {
            buffer += chunk;
            if (!buffer.includes('\n')) return;
            connection.end();
            const response = JSON.parse(buffer.split('\n')[0]);
            if (response.error || response.value?.__ui_error) reject(Error(response.error || response.value.__ui_error));
            else resolve(response.value);
        });
        connection.setTimeout(10000, () => { connection.destroy(); reject(Error('Нет ответа WebKit')); });
    });
}
async function until(script, message, timeout = 7000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
        if (await evaluate(script)) return;
        await wait(80);
    }
    throw Error(message);
}
async function click(label) {
    const script=`
        const scope = [...document.querySelectorAll('.floating-menu')].pop() || [...document.querySelectorAll('[aria-modal="true"]')].pop() || document;
        const candidates = [...scope.querySelectorAll('button')].filter(x => !x.closest('[inert]') && !x.disabled && x.getClientRects().length && getComputedStyle(x).visibility !== 'hidden');
        const label = ${JSON.stringify(label)};
        const button = candidates.find(x => x.title === label || x.getAttribute('aria-label') === label)
            || candidates.find(x => x.innerText.trim() === label) || candidates.find(x => x.innerText.includes(label));
        if (!button) throw Error('Не найдена кнопка: ' + label);
        button.scrollIntoView({block:'nearest'});
        const rect = button.getBoundingClientRect(), hit = document.elementFromPoint(rect.x + rect.width/2, rect.y + rect.height/2);
        if (!hit || !button.contains(hit)) throw Error('Кнопка перекрыта: ' + label);
        // Событие идёт отдельным оборотом, после ответа диагностического eval.
        setTimeout(() => button.click(), 0); return true;
    `;
    for(let attempt=0;;attempt++){
        try{await evaluate(script);break;}
        catch(error){if(attempt>=20||!(/Не найдена кнопка|Кнопка перекрыта/.test(error.message)))throw error;await wait(100);}
    }
    await wait(170);
}
async function input(selector, value) {
    await evaluate(`
        const field = document.querySelector(${JSON.stringify(selector)});
        if (!field) throw Error('Не найдено поле: ' + ${JSON.stringify(selector)});
        field.value = ${JSON.stringify(value)};
        setTimeout(() => field.dispatchEvent(new Event(field.tagName === 'SELECT' ? 'change' : 'input', {bubbles:true})), 0);
        return true;
    `);
    await wait(100);
}
async function check(name, script) {
    assert(await evaluate(script), name);
    results.push(name);
    console.log('✓ ' + name);
}
const close = () => click('Закрыть окно');
// Снимки снимаются только с окна запущенного стенда.
const screenshot = name => {if(windowId)execFileSync('niri',['msg','action','screenshot-window','--id',String(windowId),'--path',path.join(root,name+'.png')]);};
const menu = () => click(windowId && width < 600 ? 'Действия чата' : 'Поиск, закладки и экспорт');
let width = 1000;
function resize(next) {
    width = next;
    if (!windowId) return;
    execFileSync('niri', ['msg', 'action', 'set-window-width', '--id', String(windowId), String(next)]);
}
async function start() {
    const log = fs.openSync(path.join(root, 'app.log'), 'a');
    child = spawn(binary, [], {cwd: repository, env: {...process.env, XOPILOT_DATA_DIR:path.join(root, 'data'), XOPILOT_MODELS_DIR:modelDirectory, XOPILOT_UI_SOCKET:socket, GSETTINGS_BACKEND:'memory'}, stdio:['ignore', log, log]});
    fs.closeSync(log);
    for (let i=0;i<100 && !fs.existsSync(socket);i++) await wait(50);
    // Файл Unix socket появляется чуть раньше listen; под нагрузкой это заметная гонка.
    for(let attempt=0;;attempt++){
        try{await evaluate('return document.readyState;');break;}
        catch(error){if(attempt>=100||child.exitCode!==null||child.signalCode!==null||!['ENOENT','ECONNREFUSED'].includes(error.code))throw error;await wait(50);}
    }
    await until("return !!document.querySelector('#chat-prompt');", 'История не открылась');
    if (process.env.NIRI_SOCKET) {
        const windows = JSON.parse(execFileSync('niri', ['msg', '--json', 'windows']));
        windowId = windows.find(w => w.pid === child.pid)?.id;
        assert(windowId, 'Нет окна тестового приложения');
        execFileSync('niri', ['msg', 'action', 'move-window-to-floating', '--id', String(windowId)]);
        resize(width);
        execFileSync('niri', ['msg', 'action', 'set-window-height', '--id', String(windowId), '767']);
        await wait(350);
    }
}
async function stop() {
    if (child && child.exitCode === null && child.signalCode === null) {
        const ended = new Promise(resolve => child.once('exit', resolve));
        child.kill('SIGTERM');
        await Promise.race([ended, wait(2000)]);
        if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
    }
    if (fs.existsSync(socket)) fs.unlinkSync(socket);
}
const server = http.createServer(async (request, response) => {
    let body = '';
    for await (const chunk of request) body += chunk;
    requests.push(JSON.parse(body));
    const message=JSON.parse(body);
    if(message.messages[0]?.content?.includes('You are the Xopilot agent')){
        const turn=agentRequests++,step=turn%3,run=Math.floor(turn/3);
        const answer=step===0?{tool:'read_project_file',arguments:{path:'example.txt'}}:
            step===1?{tool:'write_project_file',arguments:{path:'example.txt',content:run===0?'Изменено агентом':'Эта правка отклонена'}}:
                {final:run===0?'Файл изменён агентом':'Действие отклонено'};
        await wait(450);
        response.writeHead(200,{'Content-Type':'application/json'});
        response.end(JSON.stringify({choices:[{message:{content:JSON.stringify(answer)}}]}));return;
    }
    response.writeHead(200, {'Content-Type':'text/event-stream'});
    response.write('data: ' + JSON.stringify({choices:[{delta:{content:'Потоковый ответ.\n\n'}}]}) + '\n\n');
    await wait(1800);
    if (!response.destroyed) response.end('data: '+JSON.stringify({choices:[{delta:{content:'**Markdown** и окончание ответа.'}}]})+'\n\ndata: [DONE]\n\n');
});

// При остановке стенда закрываем только запущенное им окно, не оставляя тестовый процесс.
process.once('SIGTERM',()=>{void stop().finally(()=>{server.close();process.exit(143);});});
process.once('SIGINT',()=>{void stop().finally(()=>{server.close();process.exit(130);});});

(async () => {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    await start();
    await input('#chat-prompt', 'Черновик первого чата');
    await click('Открыть меню');
    await check('Выдвижное меню принимает клики и получает фокус', "return !document.querySelector('.drawer-layer').inert && document.activeElement.classList.contains('drawer');");
    await click('Настройки');
    for (const section of ['Профиль и аккаунт', 'Персонализация', 'Модели', 'История', 'Обновления', 'О программе']) {
        await click(section);
        await check('Все окна настроек сохраняют общий размер: '+section, "const r=document.querySelector('.dialog').getBoundingClientRect();window.__settingsSize??={width:r.width,height:r.height};return Math.abs(r.width-window.__settingsSize.width)<1&&Math.abs(r.height-window.__settingsSize.height)<1;");
        await check('Открывается раздел: ' + section, `return document.querySelector('#dialog-title').textContent === ${JSON.stringify(section)};`);
        if (section === 'Профиль и аккаунт') {
            await click('Изменить имя');
            await input('.profile-name-editor input', 'Имя UI-проверки');
            await click('Назад к настройкам');
            await check('Несохранённый профиль защищён при возврате', "return document.querySelector('[role=alertdialog]')?.contains(document.activeElement);");
            await click('Остаться');
            await click('Сохранить имя');
        }
        if (section === 'Модели') {
            await check('Скачивание расположено справа внутри карточки модели', "return [...document.querySelectorAll('.model-card')].every(card=>{const row=card.getBoundingClientRect(),button=card.querySelector('button').getBoundingClientRect();return button.right<=row.right&&button.left>row.left+row.width/2&&button.top>=row.top&&button.bottom<=row.bottom;});");
        }
        if (section === 'Персонализация') {
            await click('Тема оформления');
            await check('Тематический список помещается в окно и отмечает выбранную тему', "const menu=document.querySelector('[role=listbox]'),r=menu.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight&&!!menu.querySelector('[aria-selected=true]')&&!document.querySelector('select[aria-label=\"Тема оформления\"]');");
            await click('Аква · тёмная');
            await click('Тема оформления');
            if(windowId)execFileSync('niri',['msg','action','screenshot-window','--id',String(windowId),'--path',path.join(root,'desktop-themed-select.png')]);
            await click('Аква · тёмная');
            await check('Тема применяется в открытом окне', "return document.querySelector('.app').dataset.theme === 'dark';");
            await click('Тема оформления'); await click('Аква · светлая');
            await click('Память обо мне');
            await input('.dialog textarea', 'Инструкции UI-проверки');
            await click('Сохранить профиль'); await close();
            await check('Память возвращает в персонализацию', "return document.querySelector('#dialog-title').textContent === 'Персонализация';");
        }
        if(windowId)execFileSync('niri',['msg','action','screenshot-window','--id',String(windowId),'--path',path.join(root,'desktop-section-'+['Профиль и аккаунт','Персонализация','Модели','История','Обновления','О программе'].indexOf(section)+'.png')]);
        await click('Назад к настройкам');
    }
    await close();
    await check('Настройки сохраняют черновик чата', "return document.querySelector('#chat-prompt').value === 'Черновик первого чата';");
    const project = path.join(root, 'project');
    fs.mkdirSync(project);
    fs.writeFileSync(path.join(project, 'example.txt'), 'Первоначальный текст');
    await click('Рабочие пространства'); await click('Новое пространство');
    await input('.dialog input:not([placeholder])', 'Проект UI-проверки');
    await input('.dialog textarea', 'Инструкции тестового проекта');
    await input('.dialog input[placeholder="/home/user/project"]', project);
    await close(); await click('Остаться'); await click('Сохранить проект');
    await click('Привязать текущий чат');
    await check('Привязка проекта обновляет заголовок чата', "return document.querySelector('.header-title').innerText.includes('Проект UI-проверки');");
    await click('Открыть файлы'); await click('Список файлов');
    await check('Список показывает файлы выбранного проекта', "return document.querySelector('.dialog pre').innerText.includes('example.txt');");
    await input('.dialog input[placeholder="src/main.rs"]', 'example.txt'); await click('Открыть файл');
    await input('textarea[aria-label="Редактор файла"]', 'Правка через интерфейс'); await click('Сохранить файл');
    assert.equal(fs.readFileSync(path.join(project, 'example.txt'), 'utf8'), 'Правка через интерфейс');
    await input('textarea[aria-label="Редактор файла"]', 'Правка с конфликтом');
    fs.writeFileSync(path.join(project, 'example.txt'), 'Внешняя правка');
    await click('Сохранить файл');
    await check('Конфликт файла показан пользователю', "return !!document.querySelector('.snackbar.error');");
    assert.equal(fs.readFileSync(path.join(project, 'example.txt'), 'utf8'), 'Внешняя правка');
    await evaluate("setTimeout(()=>document.querySelector('.snackbar button').click(),0);return true;");
    await click('Закрыть редактор'); await click('Отбросить');
    await click('Удалить пространство'); await click('Подтвердить удаление пространства');
    await check('Удаление пространства сохраняет чат и снимает привязку', "return document.querySelector('.header-title').innerText.includes('Все чаты') && !document.querySelector('.dialog').innerText.includes('Удалить пространство');");
    assert(fs.existsSync(path.join(project, 'example.txt')));
    await close();
    await click('Canvas');
    await input('.dialog input', 'Canvas UI-проверки');
    await input('.dialog textarea', '# Сохранённый Canvas');
    await click('Сохранить');
    await click('Документ'); await click('Новый документ');
    await check('Пункт «Новый документ» действительно открывает пустой Canvas', "return document.querySelector('.dialog input').value === '' && document.querySelector('.dialog textarea').value === '';");
    await click('Документ'); await click('Canvas UI-проверки');
    await check('Сохранённый Canvas открывается по выбору из списка', "return document.querySelector('.dialog textarea').value === '# Сохранённый Canvas';");
    await input('.dialog textarea', 'Несохранённая правка'); await close();
    await click('Остаться'); await click('Сохранить');
    await click('Удалить Canvas'); await click('Подтвердить удаление Canvas');
    await click('Документ');
    await check('Canvas удаляется только после подтверждения', "return document.querySelectorAll('[role=listbox] [role=option]').length === 1 && document.querySelector('.dialog textarea').value === '';");
    await click('Новый документ');
    await close();
    await menu(); await click('Шаблоны запросов'); await click('Создать');
    await input('.dialog .section input', 'Шаблон UI-проверки'); await input('.dialog textarea', 'Первый текст шаблона');
    await click('Добавить шаблон'); await click('Изменить шаблон'); await input('.dialog textarea', 'Исправленный шаблон'); await click('Сохранить шаблон');
    await check('Шаблон редактируется без создания дубликата', "return document.querySelectorAll('.dialog .list .section').length === 1 && document.querySelector('.dialog .list').innerText.includes('Исправленный шаблон');");
    await click('Вставить в сообщение');
    await check('Шаблон дополняет черновик без отправки', `return document.querySelector('#chat-prompt').value === ${JSON.stringify('Черновик первого чата\n\nИсправленный шаблон')};`);
    await click('Выбор модели'); await click('Подключить API');
    await input('.dialog input[type=password]', 'test-key-only'); await click('OpenRouter');
    await check('Смена провайдера очищает прежний ключ', "return document.querySelector('.dialog input[type=password]').value === '';");
    await close(); await click('Остаться');
    await input('.dialog input[placeholder="https://example.com/v1"]', `http://127.0.0.1:${server.address().port}/v1`);
    await input('.dialog input[placeholder="Идентификатор из каталога провайдера"]', 'interface-test');
    await click('Сохранить модель'); await close(); await close();
    await input('#chat-prompt', 'Вопрос UI-проверки'); await click('Отправить сообщение');
    await until("return document.querySelector('.message.assistant')?.innerText.includes('Потоковый ответ');", 'Первый SSE-фрагмент не появился');
    await check('Ответ отображается по мере получения SSE', "return !!document.querySelector('button[title="+JSON.stringify('Остановить ответ')+"]') && document.querySelector('.message.assistant').innerText.includes('Потоковый ответ');");
    await until("return !document.querySelector('button[title="+JSON.stringify('Остановить ответ')+"]');", 'Ответ не завершился');
    await click('Действия сообщения'); await click('Изменить');
    await input('textarea[aria-label="Текст сообщения"]', 'Правка, которую отменили'); await click('Отмена');
    await click('Действия сообщения'); await click('Изменить');
    await check('Отмена редактирования восстанавливает сохранённое сообщение', "return document.querySelector('textarea[aria-label="+JSON.stringify('Текст сообщения')+"]').value.includes('окончание ответа');");
    await click('Отмена'); await click('Действия сообщения'); await click('В закладки');
    await menu(); await click('Закладки');
    await check('Закладки показывают только отмеченные сообщения', "return document.querySelectorAll('.message').length === 1 && document.querySelector('.message').classList.contains('assistant');");
    await input('input[aria-label="Поиск по сообщениям"]', 'ничегонесовпадает');
    await check('Поиск без совпадений объясняет пустую ленту', "return document.querySelector('.search-empty')?.innerText.includes('Ничего не найдено');");
    await click('Закрыть поиск');
    await menu(); await click('Экспортировать чат');
    assert(fs.readdirSync(path.join(root, 'data', 'exports')).some(name => name.endsWith('.md')));
    await until("return !document.querySelector('.snackbar');", 'Уведомление не исчезло', 6500);
    await check('Уведомление закрывается автоматически', "return !document.querySelector('.snackbar');");
    await input('#chat-prompt', 'Ответ для отмены'); await click('Отправить сообщение'); await click('Остановить ответ');
    await until("return !document.querySelector('button[title="+JSON.stringify('Остановить ответ')+"]');", 'Отмена не завершилась');
    await check('После остановки ввод снова доступен', "return !document.querySelector('#chat-prompt').disabled;");
    await click('Открыть меню'); await click('Новый чат'); await input('#chat-prompt', 'Черновик после перезапуска');
    await wait(700); await stop(); await start();
    await check('Черновик переживает перезапуск приложения', "return document.querySelector('#chat-prompt').value === 'Черновик после перезапуска';");
    if (windowId) {
        resize(390); await wait(350);
        await click('Открыть меню'); await click('Настройки');
        for (const section of ['Профиль и аккаунт','Персонализация','Модели','История','Обновления','О программе']) {
            await click(section);
            await check('Узкий экран: ' + section, "return document.documentElement.scrollWidth <= innerWidth && document.querySelector('.dialog').getBoundingClientRect().right <= innerWidth;");
            await click('Назад к настройкам');
        }
        await close();
        for (const section of ['Рабочие пространства','Чаты','Материалы','Защищённые чаты']) {
            await click('Открыть меню'); await click(section);
            await check('Узкий экран: ' + section, "return document.documentElement.scrollWidth <= innerWidth && !!document.querySelector('.dialog');");
            await close();
        }
        await click('Открыть меню');
        await wait(300);
        execFileSync('niri', ['msg', 'action', 'screenshot-window', '--id', String(windowId), '--path', path.join(root, 'mobile-drawer.png')]);
        await click('Настройки'); await click('Профиль и аккаунт');
        await click('Изменить имя'); await input('.profile-name-editor input', 'Несохранённое имя'); await close();
        execFileSync('niri', ['msg', 'action', 'screenshot-window', '--id', String(windowId), '--path', path.join(root, 'mobile-unsaved.png')]);
        await click('Остаться'); await click('Сохранить имя'); await close();
        resize(1000); await wait(350);
        await click('Поиск, закладки и экспорт'); await click('Закладки');
        execFileSync('niri', ['msg', 'action', 'screenshot-window', '--id', String(windowId), '--path', path.join(root, 'desktop-empty-bookmarks.png')]);
    }
    await require('./check-ui-features.cjs')({root,evaluate,wait,click,input,close,check,until,resize,requests,modelDirectory,screenshot});
    fs.writeFileSync(path.join(root, 'result.json'), JSON.stringify({checks:results, httpRequests:requests.length, viewportWidths:windowId?[1000,390]:[1060], platform:'Linux WebKitGTK; Android device not tested'}, null, 2));
    console.log(`${results.length} проверок пройдено. Артефакты: ${root}`);
})().catch(async error => {
    console.error(error);
    try {
        const state = await evaluate("return {focus:document.activeElement?.outerHTML.slice(0,500),error:document.querySelector('.snackbar')?.innerText,drawer:document.querySelector('.drawer-layer')?.outerHTML.slice(0,500),dialog:document.querySelector('.dialog')?.innerText,confirmation:document.querySelector('[role=alertdialog]')?.innerText};");
        fs.writeFileSync(path.join(root, 'failure.json'), JSON.stringify(state, null, 2));
    } catch (_) {}
    console.error('Артефакты: ' + root);
    process.exitCode=1;
}).finally(async () => {await stop(); server.close();});
