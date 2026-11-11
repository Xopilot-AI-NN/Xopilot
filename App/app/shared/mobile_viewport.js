// WebView оставляет layout viewport высоким при открытии IME: используем видимую область.
if (!window.xopilotSetInsets) {
    let edges = { top: 0, right: 0, bottom: 0, left: 0 };
    let frame = 0;
    const update = () => {
        frame = 0;
        const viewport = window.visualViewport;
        const height = Math.min(innerHeight, viewport?.height ?? innerHeight);
        const keyboard = innerHeight - height > 100;
        const scale = devicePixelRatio || 1;
        const style = document.documentElement.style;
        style.setProperty('--app-viewport-height', `${height}px`);
        for (const side of ['top', 'right', 'bottom', 'left']) {
            // IME уже уменьшила видимую область; отступ навигации второй раз не прибавляем.
            const value = side === 'bottom' && keyboard ? 0 : edges[side] / scale;
            style.setProperty(`--safe-${side}`, `${Math.max(0, value)}px`);
        }
        // Android иногда прокручивает layout viewport к прежней позиции поля после показа IME.
        if (window.scrollY) window.scrollTo(0, 0);
    };
    const schedule = () => {
        if (!frame) frame = requestAnimationFrame(update);
    };
    window.xopilotSetInsets = value => { edges = value; schedule(); };
    visualViewport?.addEventListener('resize', schedule);
    visualViewport?.addEventListener('scroll', schedule);
    window.addEventListener('resize', schedule);
    schedule();
}
