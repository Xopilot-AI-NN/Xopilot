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
  await input("#chat-prompt", "Черновик общего UI-теста");
  await click("Открыть меню");
  await click("Настройки");
  for (const section of [
    "Профиль и аккаунт",
    "Персонализация",
    "Модели",
    "История",
    "Обновления",
    "О программе",
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
      await input(".profile-name-editor input", "UI Test");
      await click("Сохранить имя");
      await check(
        "Имя сохранено через Rust",
        "return document.querySelector('.profile-name').textContent.includes('UI Test');",
      );
    }
    if (section === "Модели")
      await check(
        "Кнопки моделей внутри карточек",
        "return [...document.querySelectorAll('.model-card')].every(c=>{const b=c.querySelector('button').getBoundingClientRect(),r=c.getBoundingClientRect();return b.right<=r.right+1&&b.bottom<=r.bottom+1;});",
      );
    if (section === "О программе") {
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
