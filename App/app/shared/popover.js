await new Promise(resolve => requestAnimationFrame(resolve));
const menu = document.getElementById(menuId);
const findAnchor = () => {
    let anchor = document.getElementById(anchorId);
    // При изменении ширины заголовок переключает кнопки без перемонтирования меню.
    if (anchorId === 'chat-tools-desktop' && !anchor?.getClientRects().length) anchor = document.getElementById('chat-tools-mobile');
    return anchor;
};
if (menu && findAnchor()) {
    window.__xopilotPopovers ??= {};
    window.__xopilotPopovers[menuId]?.abort();
    const controller = new AbortController();
    window.__xopilotPopovers[menuId] = controller;
    const position = () => {
        const anchor=findAnchor(); if (!anchor) return;
        const viewport = window.visualViewport;
        const width = viewport?.width ?? innerWidth, height = viewport?.height ?? innerHeight;
        const top = viewport?.offsetTop ?? 0, left = viewport?.offsetLeft ?? 0;
        const rect = anchor.getBoundingClientRect(), margin = 8;
        menu.style.maxWidth = Math.max(0,width-2*margin)+'px';
        const below = top+height-rect.bottom-margin, above = rect.top-top-margin;
        const upward = below < 180 && above > below;
        menu.style.maxHeight = Math.max(48,(upward?above:below)-margin)+'px';
        const size = menu.getBoundingClientRect();
        menu.style.left = Math.max(left+margin, Math.min(rect.left,left+width-size.width-margin))+'px';
        menu.style.top = (upward?Math.max(top+margin,rect.top-size.height-margin):Math.max(top+margin,rect.bottom+margin))+'px';
        menu.style.visibility = 'visible';
    };
    position();
    addEventListener('resize',position,{signal:controller.signal});
    addEventListener('scroll',position,{capture:true,signal:controller.signal});
    window.visualViewport?.addEventListener('resize',position,{signal:controller.signal});
    menu.querySelector('button:not(:disabled)')?.focus({preventScroll:true});
    menu.addEventListener('keydown',event=>{
        const controls=[...menu.querySelectorAll('button:not(:disabled)')];
        let index=controls.indexOf(document.activeElement);
        if(event.key==='ArrowDown'||event.key==='ArrowUp'){
            event.preventDefault();index=(index+(event.key==='ArrowDown'?1:-1)+controls.length)%controls.length;controls[index]?.focus();
        }
    },{signal:controller.signal});
}
