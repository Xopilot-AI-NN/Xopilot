// Общие пользовательские действия для Linux-стенда и Android WebView.
// Проверяем видимость и перекрытие кнопок: DOM click сам по себе этого не гарантирует.
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
module.exports = function client(evaluate, results = []) {
  async function until(script, message, timeout = 10000) {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      try {
        if (await evaluate(script)) return;
      } catch (error) {
        // При холодном старте WebView заменяет начальный документ страницей приложения.
        // Повторяю только этот переход, ошибки самого проверяемого JS сохраняются.
        if (!String(error).includes("Inspected target navigated or closed")) throw error;
      }
      await wait(90);
    }
    throw Error(message);
  }
  async function click(label) {
    await until(
      `const scope=[...document.querySelectorAll('.floating-menu,[role=listbox]')].pop()||[...document.querySelectorAll('[aria-modal=true]')].pop()||document;
            const buttons=[...scope.querySelectorAll('button,[role=option]')].filter(x=>!x.disabled&&!x.closest('[inert]')&&x.getClientRects().length);
            const b=buttons.find(x=>x.title===${JSON.stringify(label)}||x.getAttribute('aria-label')===${JSON.stringify(label)}||x.innerText.trim()===${JSON.stringify(label)}||x.innerText.includes(${JSON.stringify(label)}));
            if(!b)return false;b.scrollIntoView({block:'nearest'});const r=b.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
            if(!hit||!b.contains(hit))return false;setTimeout(()=>b.click(),0);return true;`,
      "Не найдена доступная кнопка: " + label,
    );
    await wait(180);
  }
  async function input(selector, value) {
    await evaluate(
      `const f=document.querySelector(${JSON.stringify(selector)});if(!f)throw Error('Нет поля '+${JSON.stringify(selector)});f.value=${JSON.stringify(value)};f.dispatchEvent(new Event('input',{bubbles:true}));return true;`,
    );
    await wait(100);
  }
  async function check(name, script) {
    // На телефоне событие проходит через JNI; проверяем результат после обновления DOM.
    await until(script, name, 3000);
    results.push(name);
    console.log("✓ " + name);
  }
  return {
    evaluate,
    wait,
    until,
    click,
    input,
    check,
    close: () => click("Закрыть окно"),
    results,
  };
};
