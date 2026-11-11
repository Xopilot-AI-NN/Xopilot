// В WebView добавляем единственную запись истории: Android Back не должен уничтожать Activity.
for (let frame = 0; frame < 60 && !document.querySelector('.app'); frame++) {
    await new Promise(requestAnimationFrame);
}
const scrolls = () => ({
    scrolls: Object.fromEntries(window.xopilotDialogScroll || []),
    chat_scroll: document.querySelector('.messages')?.scrollTop || 0,
});
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') dioxus.send({kind: 'background', ...scrolls()});
});
if (document.querySelector('.app')?.dataset.platform === 'android') {
    history.pushState({xopilot: true}, '', location.href);
    window.addEventListener('popstate', () => {
        history.pushState({xopilot: true}, '', location.href);
        dioxus.send({kind: 'back', ...scrolls()});
    });
}
// Снимок прокрутки применяется после первого пакета DOM с загруженной перепиской.
const restore = () => {
    const messages = document.querySelector('.messages');
    if (messages && typeof window.xopilotChatScroll === 'number') {
        messages.scrollTop = window.xopilotChatScroll;
        delete window.xopilotChatScroll;
    }
};
new MutationObserver(restore).observe(document.getElementById('main') || document.body, {childList: true, subtree: true});
restore();
await new Promise(() => {});
