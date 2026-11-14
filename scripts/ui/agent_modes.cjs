// Проверяю новые режимы через настоящий чат и локальный совместимый API стенда.
module.exports=async({evaluate,wait,click,input,check,until,screenshot})=>{
 await click('Размышление');await click('Лёгкий');
 for(const mode of ['Точный агент','Мульти Агенты','Мульти Агенты с подкреплением']){
  await click('Режим агента');await click(mode);
  await input('#chat-prompt','Задача нового режима: проверь документы');await click('Отправить сообщение');
  await until("return !document.querySelector('button[title=\"Остановить ответ\"]')&&!!document.querySelector('.reasoning-trace');",'Новый режим не завершился',30000);
  await check('Выполнен режим: '+mode,"return document.querySelector('.message.assistant .message-bubble').innerText.includes('Ответ расширенного режима');");
  await check('План отображается в чате: '+mode,"return [...document.querySelectorAll('.reasoning-trace')].some(x=>x.dataset.state==='completed'&&x.querySelector('p').textContent.trim());");
  if(screenshot) screenshot('agent-mode-'+['Точный агент','Мульти Агенты','Мульти Агенты с подкреплением'].indexOf(mode));
 }
 await click('Режим агента');await click('Чат без инструментов');
 await click('Размышление');await click('Выключить размышление');
 await evaluate("setTimeout(()=>document.querySelector('#reasoning-menu').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})),0);return true;");await wait(100);
 await input('#chat-prompt','Исходный запрос для уточнения');await click('Отправить сообщение');
 await until("return document.querySelector('button[title=\"Остановить ответ\"]')&&document.querySelector('.message.assistant').innerText.includes('Потоковый ответ');",'Нет потокового ответа');
 await input('#chat-prompt','Уточнение пользователя');await click('Уточнить текущую задачу');
 await until("return !document.querySelector('button[title=\"Остановить ответ\"]');",'Уточнение не завершилось',15000);
 await check('Уточнение текущей задачи сохранено',"return [...document.querySelectorAll('.message.user')].some(x=>x.innerText.includes('Уточнение пользователя'));");
 await check('ИИ учёл уточнение до окончательного ответа',"return document.querySelector('.message.assistant .message-bubble').innerText.includes('Уточнение учтено');");
 await check('В ответе доступна кнопка озвучивания',"return !!document.querySelector('button[title=\"Озвучить ответ\"]');");
};
