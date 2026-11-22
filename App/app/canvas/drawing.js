// Жесты остаются в WebView. По мосту передаём только готовый штрих или экспорт.
const editor = document.querySelector('.drawing-editor');
if (!editor) return;
const initial = await dioxus.recv();
if (!editor.isConnected) return;
const canvas = editor.querySelector('canvas');
const context = canvas.getContext('2d');
const undo = editor.querySelector('[data-undo]');
const redo = editor.querySelector('[data-redo]');
const exportButton = editor.querySelector('[data-export]');
const ink = editor.querySelector('[data-ink]');
const width = editor.querySelector('[data-width]');
const strokes = initial.strokes ?? [];
const size = initial.size ?? [1200, 700];
const validPoint = point => Array.isArray(point) && point.length === 2 &&
    point.every(value => Number.isFinite(value) && value >= 0 && value <= 1);
const validStroke = stroke => stroke && typeof stroke.color === 'string' &&
    CSS.supports('color', stroke.color) && Number.isFinite(stroke.width ?? 3) &&
    (stroke.width ?? 3) > 0 && Array.isArray(stroke.points) && stroke.points.every(validPoint);
if (!context || !Array.isArray(strokes) || !strokes.every(validStroke) ||
    !Array.isArray(size) || size.length !== 2 || !size.every(value => Number.isFinite(value) && value > 0)) {
    dioxus.send({kind: 'error', message: 'Не удалось открыть формат штрихов. Исходный рисунок сохранён.'});
    return;
}

// Flet хранит координаты от 0 до 1, а толщину — в исходных пикселях.
const scale = 1200 / Math.max(...size);
canvas.width = Math.max(1, Math.round(size[0] * scale));
canvas.height = Math.max(1, Math.round(size[1] * scale));
const undone = [];
const limit = 100000;
let pointCount = strokes.reduce((sum, stroke) => sum + stroke.points.length, 0);
let active = null;

function segment(stroke, start, end) {
    const [x, y] = start.map((value, axis) => value * (axis ? canvas.height : canvas.width));
    const [nextX, nextY] = end.map((value, axis) => value * (axis ? canvas.height : canvas.width));
    const thickness = Math.min(1200, Math.max(1, (stroke.width ?? 3) * scale));
    context.beginPath();
    if (x === nextX && y === nextY) {
        context.fillStyle = stroke.color;
        context.arc(x, y, thickness / 2, 0, 2 * Math.PI);
        context.fill();
    } else {
        context.strokeStyle = stroke.color;
        context.lineWidth = thickness;
        context.lineCap = 'round';
        context.moveTo(x, y);
        context.lineTo(nextX, nextY);
        context.stroke();
    }
}

function redraw() {
    context.fillStyle = '#fff';
    context.fillRect(0, 0, canvas.width, canvas.height);
    for (const stroke of strokes) {
        for (const [index, point] of stroke.points.entries()) {
            segment(stroke, stroke.points[index - 1] ?? point, point);
        }
    }
}

function buttons() {
    undo.disabled = !!active || !strokes.length;
    redo.disabled = !!active || !undone.length;
    exportButton.disabled = !!active;
}

function changed() {
    buttons();
    dioxus.send({kind: 'changed', strokes, size});
}

function coordinates(event) {
    const rect = canvas.getBoundingClientRect();
    const clamp = value => Math.min(1, Math.max(0, value));
    return [clamp((event.clientX - rect.left) / rect.width),
        clamp((event.clientY - rect.top) / rect.height)];
}

canvas.addEventListener('pointerdown', event => {
    if (active || event.button !== 0) return;
    if (pointCount >= limit) {
        dioxus.send({kind: 'error', message: 'Достигнут предел точек. Отмените штрих или начните новый рисунок.'});
        return;
    }
    if (event.isTrusted) canvas.setPointerCapture(event.pointerId);
    const point = coordinates(event);
    const stroke = {color: ink.value, width: Number(width.value), points: [point]};
    active = {id: event.pointerId, stroke};
    segment(stroke, point, point);
    buttons();
});

function extend(event) {
    if (!active || active.id !== event.pointerId) return;
    const {stroke} = active;
    if (pointCount + stroke.points.length >= limit) return;
    const point = coordinates(event);
    const previous = stroke.points.at(-1);
    if (point[0] === previous[0] && point[1] === previous[1]) return;
    stroke.points.push(point);
    segment(stroke, previous, point);
}

function finish(event) {
    if (!active || active.id !== event.pointerId) return;
    if (event.type === 'pointerup') extend(event);
    strokes.push(active.stroke);
    pointCount += active.stroke.points.length;
    active = null;
    undone.length = 0;
    changed();
}

canvas.addEventListener('pointermove', extend);
for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) {
    canvas.addEventListener(event, finish);
}
undo.addEventListener('click', () => {
    const stroke = strokes.pop();
    if (!stroke) return;
    undone.push(stroke);
    pointCount -= stroke.points.length;
    redraw();
    changed();
});
redo.addEventListener('click', () => {
    const stroke = undone.pop();
    if (!stroke) return;
    strokes.push(stroke);
    pointCount += stroke.points.length;
    redraw();
    changed();
});
exportButton.addEventListener('click', () => {
    dioxus.send({kind: 'export', png: canvas.toDataURL('image/png')});
});
redraw();
buttons();

// Пока холст открыт, канал остаётся живым для следующих изменений.
await new Promise(resolve => {
    const observer = new MutationObserver(() => {
        if (editor.isConnected) return;
        observer.disconnect();
        resolve();
    });
    observer.observe(document.body, {
        childList: true, subtree: true,
    });
});
