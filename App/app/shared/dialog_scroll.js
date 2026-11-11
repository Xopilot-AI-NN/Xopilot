// Каждая страница запоминает собственную прокрутку, даже если WebKit переиспользовал узел.
await new Promise(resolve => requestAnimationFrame(resolve));
const body = document.querySelector('.dialog-body[data-scroll-page]');
if (body && body.dataset.scrollReady !== body.dataset.scrollPage) {
    const positions = window.xopilotDialogScroll ??= new Map();
    const page = body.dataset.scrollPage;
    if (body.xopilotScrollHandler) body.removeEventListener('scroll', body.xopilotScrollHandler);
    body.dataset.scrollReady = page;
    body.scrollTop = positions.get(page) ?? 0;
    // Событие от замены содержимого может прийти раньше следующего кадра.
    // Старый слушатель не должен записать новую высоту в позицию предыдущей страницы.
    body.xopilotScrollHandler = () => {
        if (body.dataset.scrollPage === page) positions.set(page, body.scrollTop);
    };
    body.addEventListener('scroll', body.xopilotScrollHandler, { passive: true });
}
