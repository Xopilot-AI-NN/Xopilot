// Описание: Новые сценарии агента, автономных аккаунтов и настоящей локальной Gemma.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
module.exports=async function({root,evaluate,wait,click,input,close,check,until,resize,requests}){
    resize(1000);await wait(350);
    if(await evaluate("return !!document.querySelector('button[title=\"Закрыть поиск\"]');"))await click('Закрыть поиск');
    await click('Поиск, закладки и экспорт');resize(390);await wait(350);
    await check('Открытое меню следует за мобильной кнопкой после изменения ширины',"const menu=document.querySelector('#chat-tools-menu').getBoundingClientRect(),anchor=document.querySelector('#chat-tools-mobile').getBoundingClientRect();return menu.left>=0&&menu.right<=innerWidth&&menu.top>=anchor.bottom;");
    await evaluate("setTimeout(()=>document.querySelector('#chat-tools-menu').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})),0);return true;");await wait(200);
    await check('Escape закрывает выпадающее меню',"return !document.querySelector('#chat-tools-menu');");
    resize(1000);await wait(350);
    const project=path.join(root,'agent-project');fs.mkdirSync(project);fs.writeFileSync(path.join(project,'example.txt'),'До действий агента');
    await click('Рабочие пространства');await click('Новое пространство');
    await input('.dialog input:not([placeholder])','Проект агента');await input('.dialog input[placeholder="/home/user/project"]',project);await click('Сохранить проект');await click('Привязать текущий чат');await close();
    await click('Режим агента');
    await check('Меню агента помещается в экран',"const r=document.querySelector('#agent-mode-menu').getBoundingClientRect();return r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight;");
    await click('Агент · подтверждать действия');await input('#chat-prompt','Измени example.txt');await click('Отправить сообщение');await click('Пауза');
    await wait(650);
    await check('Пауза удерживает следующие действия агента',"return !document.querySelector('.agent-approval')&&!![...document.querySelectorAll('button')].find(x=>x.innerText==='Продолжить');");
    assert.equal(fs.readFileSync(path.join(project,'example.txt'),'utf8'),'До действий агента');
    await click('Продолжить');await until("return !!document.querySelector('.agent-approval');",'Нет подтверждения записи');
    await check('Подтверждение показывает конкретную запись до изменения файла',"return document.querySelector('.approval-details').innerText.includes('example.txt')&&document.querySelector('.approval-details').innerText.includes('Изменено агентом');");
    assert.equal(fs.readFileSync(path.join(project,'example.txt'),'utf8'),'До действий агента');
    await click('Разрешить действие');await until("return !document.querySelector('button[title=\"Остановить ответ\"]');",'Агент не завершился');
    assert.equal(fs.readFileSync(path.join(project,'example.txt'),'utf8'),'Изменено агентом');
    await check('Результат агента появляется после выполнения инструмента',"return document.querySelector('.message.assistant').innerText.includes('Файл изменён агентом');");
    await input('#chat-prompt','Ещё одна правка');await click('Отправить сообщение');await until("return !!document.querySelector('.agent-approval');",'Нет повторного подтверждения');await click('Отклонить');
    await until("return !document.querySelector('button[title=\"Остановить ответ\"]');",'Агент не обработал отказ');
    assert.equal(fs.readFileSync(path.join(project,'example.txt'),'utf8'),'Изменено агентом');
    await check('Отказ оставляет файл нетронутым',"return document.querySelector('.message.assistant').innerText.includes('Действие отклонено');");
    await click('Режим агента');await click('Чат без инструментов');
    // Поля ищем по настоящей подписи, не обращаясь к состоянию Rust.
    async function field(label,value){await evaluate(`const label=[...document.querySelectorAll('.dialog label.field')].find(x=>x.textContent.startsWith(${JSON.stringify(label)}));const field=label?.querySelector('input,select');if(!field)throw Error('Нет поля '+${JSON.stringify(label)});field.value=${JSON.stringify(value)};setTimeout(()=>field.dispatchEvent(new Event(field.tagName==='SELECT'?'change':'input',{bubbles:true})),0);return true;`);await wait(150);}
    const finished=()=>until("return !document.querySelector('.dialog')&&!document.querySelector('.snackbar.error');",'Не завершилась смена аккаунта',20000);
    await input('#chat-prompt','Черновик гостя перед аккаунтом');
    const accountRequests=requests.length;
    await click('Аккаунт');
    await check('Профиль открывает Google и почту, локальные профили свёрнуты', "return !!document.querySelector('button[title=\"Изменить имя\"]')&&!!document.querySelector('[aria-label=\"Изменить аватар\"]')&&!![...document.querySelectorAll('button')].find(x=>x.innerText.includes('Продолжить с Google'))&&!document.querySelector('.local-account-panel');");
    await click('Регистрация');
    await check('Обычная регистрация содержит email и подтверждение пароля', "return document.querySelector('.account-auth-form input[type=email]')!==null&&document.querySelectorAll('.account-auth-form input[type=password]').length===2;");
    await click('Отмена');await click('Локальные профили');await click('Создать локальный аккаунт');
    await field('Локальный логин','ui-local-user');await field('Имя нового профиля','Локальный тест');await field('Пароль локального аккаунта','test local password 123');await field('Повторите пароль','test local password 123');await click('Зарегистрировать на устройстве');await finished();
    await check('Новый аккаунт открывает отдельную историю и настройки',"return document.querySelector('#chat-prompt').value===''&&!document.querySelector('.message')&&document.querySelector('.model-name').innerText.includes('Модель не выбрана');");
    await input('#chat-prompt','Черновик локального аккаунта');await click('Аккаунт');await click('Локальные профили');await click('Выйти в профиль устройства');await finished();
    await check('Выход восстанавливает гостевой черновик',"return document.querySelector('#chat-prompt').value==='Черновик гостя перед аккаунтом';");
    await click('Аккаунт');await click('Локальные профили');await field('Пароль локального аккаунта','wrong password 123');await click('Открыть аккаунт');
    await until("return !!document.querySelector('.snackbar.error');",'Неверный пароль не отклонён',15000);
    await check('Неверный пароль не переключает историю',"return document.querySelector('#chat-prompt').value==='Черновик гостя перед аккаунтом';");
    await evaluate("setTimeout(()=>document.querySelector('.snackbar button').click(),0);return true;");await field('Пароль локального аккаунта','test local password 123');await click('Открыть аккаунт');await finished();
    await check('Повторный вход восстанавливает локальный черновик',"return document.querySelector('#chat-prompt').value==='Черновик локального аккаунта';");
    await click('Аккаунт');await click('Локальные профили');await click('Изменить пароль');await field('Текущий пароль','test local password 123');await field('Новый пароль','test replacement password 456');await field('Повторите новый пароль','test replacement password 456');await click('Сохранить новый пароль');await finished();
    await check('Смена пароля сохраняет текущую историю и черновик',"return document.querySelector('#chat-prompt').value==='Черновик локального аккаунта';");
    await click('Аккаунт');await click('Локальные профили');await click('Удалить локальный аккаунт');await field('Пароль для удаления','test replacement password 456');await click('Подтвердить удаление аккаунта');await finished();
    await check('Удаление аккаунта сохраняет данные гостя',"return document.querySelector('#chat-prompt').value==='Черновик гостя перед аккаунтом';");
    assert.equal(JSON.parse(fs.readFileSync(path.join(root,'data/accounts/index.json'))).accounts.length,0);
    assert.equal(requests.length,accountRequests,'Аккаунты не должны выполнять HTTP-запросы');
    const model=process.env.XOPILOT_TEST_MODEL;
    if(model){
        await click('Выбор модели');await click('Установить модель из файла');await input('.dialog input[placeholder="Путь к оригинальному .litertlm"]',model);await click('Импорт Gemma4-e2b');
        await until("return !![...document.querySelectorAll('.model-card button')].find(x=>x.innerText==='Выбрать');",'Импорт модели не завершился',60000);
        // Уведомление импорта не должно мешать кнопкам каталога.
        if(await evaluate("return !!document.querySelector('.snackbar');"))await evaluate("setTimeout(()=>document.querySelector('.snackbar button').click(),0);return true;");
        await click('Выбрать');await close();await click('Новый чат');await input('#chat-prompt','What is 2 + 2? Reply with just the number.');await click('Отправить сообщение');
        await until("return !document.querySelector('button[title=\"Остановить ответ\"]')&&!!document.querySelector('.message.assistant');",'Локальная генерация не завершилась',90000);
        await check('Gemma отвечает в настоящем UI без API',"return document.querySelector('.message.assistant .message-bubble').innerText.trim()==='4'&&document.querySelector('.model-name').innerText.includes('Gemma4-e2b');");
        assert.equal(requests.length,accountRequests,'Локальная модель не должна обращаться к HTTP API');
        await click('Выбор модели');await click('Освободить память');await close();
    }
};
