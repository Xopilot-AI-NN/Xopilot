// Общие пользовательские действия для Linux-стенда и Android WebView.
// Проверяем видимость и перекрытие кнопок: DOM click сам по себе этого не гарантирует.
const assert = require("node:assert/strict");
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
module.exports = function client(evaluate, results = []) {
  async function until(script, message, timeout = 10000) {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      if (await evaluate(script)) return;
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
    assert(await evaluate(script), name);
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
