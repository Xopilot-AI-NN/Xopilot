// Один и тот же набор событий выполняется в настоящих WebKitGTK и Android WebView.
// Не подменяет хранилище: имя, Canvas и черновик проходят через Rust и SQLCipher.
module.exports = async function offline({
  evaluate,
  click,
  input,
  check,
  close,
  until,
}) {
  await until(
    "return document.querySelector('.app')?.dataset.ready==='true';",
    "История не открылась",
    20000,
  );
  await click("Режим агента");
  // Android сначала измеряет и размещает меню: скрытый первый кадр не содержит innerText.
  await until("const menu=document.querySelector('#agent-mode-menu');return !!menu && getComputedStyle(menu).visibility==='visible';", "Меню агентностей не появилось");
  await check("В меню есть новые агентности", "const text=document.querySelector('#agent-mode-menu').innerText;return ['Точный агент','Мульти Агенты','Мульти Агенты с подкреплением'].every(s=>text.includes(s));");
  await click("Точный агент");
  await check("Точный агент выбран", "return document.querySelector('#agent-mode-trigger').textContent.includes('Точный агент');");
  await click("Размышление");
  await click("Высокий");
  await check("Глубина размышления изменена", "return document.querySelector('#reasoning-trigger').textContent.includes('Высокий');");
  await click("Режим агента");await click("Чат без инструментов");
  await click("Размышление");await click("Выключить размышление");
  // Закрываю список повторным нажатием, не затрагивая режим отправки сообщения.
  await evaluate("setTimeout(()=>document.querySelector('#reasoning-menu').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})),0);return true;");
  await until("return !document.querySelector('#reasoning-menu');", "Список размышления не закрылся");
  await input("#chat-prompt", "Черновик общего UI-теста");
  await click("Открыть меню");
  await click("Настройки");
  for (const section of [
    "Профиль и аккаунт",
    "Персонализация",
    "Модели",
    "История",
    "Обновления",
    "О приложении",
  ]) {
    await click(section);
    await check(
      "Открывается " + section,
      `return document.querySelector('#dialog-title')?.textContent===${JSON.stringify(section)};`,
    );
    await check(
      "Окно помещается в видимую область: " + section,
      "const r=document.querySelector('.dialog').getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1&&r.top>=-1&&r.bottom<=innerHeight+1;",
    );
    if (section === "Профиль и аккаунт") {
      await click("Изменить имя");
      await input("input.profile-name-input", "UI Test");
      await click("Сохранить имя");
      await check(
        "Имя сохранено через Rust",
        "return document.querySelector('.profile-name').textContent.includes('UI Test');",
      );
    }
    if (section === "Персонализация") {
      await click("Память обо мне");
      await input('input[aria-label="Запись памяти"]', "Предпочитаю короткие ответы");
      await click("Сохранить запись");
      await check("Запись появилась в редакторе памяти", "return document.querySelector('.dialog').innerText.includes('Предпочитаю короткие ответы');");
      await click("Изменить запись");
      await input('input[aria-label="Запись памяти"]', "Предпочитаю подробные ответы");
      await click("Сохранить запись");
      await check("Правка памяти сохранена", "return document.querySelector('.dialog').innerText.includes('Предпочитаю подробные ответы');");
      await close();
    }
    if (section === "Модели")
      await check(
        "Кнопки моделей внутри карточек",
        "return [...document.querySelectorAll('.model-card')].every(c=>{const b=c.querySelector('button').getBoundingClientRect(),r=c.getBoundingClientRect();return b.right<=r.right+1&&b.bottom<=r.bottom+1;});",
      );
    if (section === "О приложении") {
      await click("Сохранить диагностику");
      await until(
        "return document.querySelector('.snackbar')?.innerText.includes('Диагностика сохранена');",
        "Диагностика не создана",
      );
      await check(
        "Диагностический архив создан",
        "return document.querySelector('.snackbar').innerText.includes('.zip');",
      );
    }
    await click("Назад к настройкам");
  }
  await close();
  await check(
    "Разделы не теряют черновик",
    "return document.querySelector('#chat-prompt').value==='Черновик общего UI-теста';",
  );
  if (
    await evaluate(
      "const b=document.querySelector('button[title=\"Действия чата\"]');return !!b&&b.getClientRects().length>0;",
    )
  ) {
    await click("Действия чата");
  }
  await click("Canvas");
  await input(".dialog input", "Общий UI Canvas");
  await input(".dialog textarea", "Текст, сохранённый общим UI-тестом");
  await click("Сохранить");
  for (const format of ["docx", "xlsx"]) {
    await click("Экспорт " + format);
    await until(
      `return document.querySelector('.dialog [role=status]')?.innerText.includes('.${format}');`,
      "Экспорт не завершился",
    );
    await check(
      "Canvas экспортирован в " + format,
      `return document.querySelector('.dialog [role=status]').innerText.includes('.${format}');`,
    );
  }
  await click("Документ");
  await click("Новый документ");
  await click("Документ");
  await click("Общий UI Canvas");
  await check(
    "Canvas сохранён и открыт повторно",
    "return document.querySelector('.dialog textarea').value==='Текст, сохранённый общим UI-тестом';",
  );
  await close();
};
