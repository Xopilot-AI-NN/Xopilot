// Фокус остаётся в открытом диалоге. Не регистрируем обработчик повторно.
const dialog = document.querySelector('[role="dialog"]');
if (dialog) dialog.focus({ preventScroll: true });
if (dialog && !dialog.dataset.focusReady) {
    dialog.dataset.focusReady = 'true';
    dialog.addEventListener('keydown', event => {
        if (event.key !== 'Tab') return;
        const controls = Array.from(dialog.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')).filter(el => el.getClientRects().length);
        if (!controls.length) { event.preventDefault(); return; }
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
            event.preventDefault(); last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog)) {
            event.preventDefault(); first.focus();
        }
    });
}
