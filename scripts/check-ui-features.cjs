// Описание: Новые сценарии агента, автоматического профиля и настоящей локальной Gemma.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
module.exports=async function({root,evaluate,wait,click,input,close,check,until,resize,requests,modelDirectory,screenshot}){
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
    screenshot('desktop-agent-actions');
    await click('Режим агента');await click('Чат без инструментов');
    await input('#chat-prompt','Черновик автоматического профиля');
    const accountRequests=requests.length;
    await click('Аккаунт');
    await check('Профиль создан без локальной регистрации', "return document.querySelector('.profile-identity').innerText.includes('автоматически')&&!document.querySelector('.account-local-trigger')&&!document.querySelector('.local-account-panel');");
    await click('Регистрация');
    await check('Регистрация по почте остаётся серверной', "return document.querySelector('.account-auth-form input[type=email]')!==null&&document.querySelectorAll('.account-auth-form input[type=password]').length===2;");
    await click('Отмена');await close();
    assert.equal(requests.length,accountRequests,'Профиль не должен обращаться к серверу без нажатия входа');
    await check('Карточки действий находятся в ленте и показывают результаты', "return !!document.querySelector('.messages .agent-actions')&&!!document.querySelector('.agent-action[data-state=completed]')&&!!document.querySelector('.agent-action[data-state=failed]')&&!document.querySelector('.composer-area .agent-trace');");
    await check('Готовность задачи находится над вводом', "const dock=document.querySelector('.activity-dock').getBoundingClientRect(),composer=document.querySelector('.composer').getBoundingClientRect();return dock.bottom<=composer.top&&!!document.querySelector('.task-completion');");
    const model=process.env.XOPILOT_TEST_MODEL;
    if(model){
        // Отдельный Rust-стенд проверяет тот же поток импорта; UI проверяет одиночный chooser.
        require('node:child_process').execFileSync('cargo',['run','-p','xopilot','--no-default-features','--example','model_import_smoke','--',model],{cwd:path.resolve(__dirname,'..'),env:{...process.env,CARGO_BUILD_JOBS:'2',XOPILOT_MODELS_DIR:modelDirectory},stdio:'pipe',timeout:120000});
        await click('Выбор модели');
        await check('Импорт — один выбор файла без ручного пути и выбора Gemma', "return document.querySelectorAll('#model-file-picker').length===1&&document.querySelector('#model-file-picker').accept==='.litertlm'&&!document.querySelector('.model-import-panel');");
        await until("return !![...document.querySelectorAll('.model-card button')].find(x=>x.innerText==='Выбрать');",'Импорт модели не завершился',60000);
        await click('Выбрать');await close();await click('Новый чат');await input('#chat-prompt','What is 2 + 2? Reply with just the number.');await click('Отправить сообщение');
        await until("return !document.querySelector('button[title=\"Остановить ответ\"]')&&!!document.querySelector('.message.assistant');",'Локальная генерация не завершилась',90000);
        await check('Gemma отвечает в настоящем UI без API',"return document.querySelector('.message.assistant .message-bubble').innerText.trim()==='4'&&document.querySelector('.model-name').innerText.includes('Gemma4-e2b');");
        assert.equal(requests.length,accountRequests,'Локальная модель не должна обращаться к HTTP API');
        await click('Выбор модели');await click('Освободить память');await close();
    }
};
