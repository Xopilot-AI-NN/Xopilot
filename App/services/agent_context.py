"""
Файл: /App/services/agent_context.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Различаю переписки Xopilot и действия внутри внешнего приложения по контексту задачи.
"""
import re

_APPS=re.compile(r'телеграм\w*|telegram|дискорд\w*|discord|whatsapp|ватсап\w*|signal|сигнал\w*|viber|вайбер\w*',re.I)
_INTERNAL=re.compile(r'(?:чат|переписк|истори).{0,40}xopilot|xopilot.{0,40}(?:чат|переписк|истори)|(?:предыдущ|позапрошл|прошл).{0,25}(?:чат|разговор)|(?:previous|earlier).{0,25}chat',re.I)
_ACTION=re.compile(r'открой|найди|нажми|введи|напиши|отправь|покажи|open|find|click|type|send',re.I)


def external_app(prompt,history=()):
    """Уточнение «в Telegram» сохраняет исходную цель, но новая явная тема имеет приоритет."""
    if _INTERNAL.search(prompt) and ('xopilot' in prompt.casefold() or not re.search(r'\bв\s+(?:'+_APPS.pattern+r')',prompt,re.I)):return None
    explicit=_APPS.search(prompt)
    if explicit:return explicit.group(0)
    if not (_ACTION.search(prompt) or re.match(r'^\s*(?:да|нет|в|на|там|ему|ей)\b',prompt,re.I)):
        return None
    if not re.search(r'чат|контакт|сообщен|окн|кнопк|там|ему|ей|chat|contact|message|window',prompt,re.I):return None
    users=[str(item.get('content','')) for item in history if item.get('role')=='user']
    for text in reversed(users[-3:]):
        if _INTERNAL.search(text):return None
        match=_APPS.search(text)
        if match:return match.group(0)
    return None


def is_followup_action(prompt,history=()):
    if re.match(r'^\s*(?:как|почему|зачем|how|why)\b',prompt,re.I):return False
    app=external_app(prompt,history)
    return bool(app and (_ACTION.search(prompt) or re.match(r'^\s*(?:да|нет|в|на|там|ему|ей)\b',prompt,re.I)))


def instruction(app):
    if not app:return ''
    return ('\nТекущая задача относится к внешнему приложению '+app+'. '
            '«Чат», контакт и поиск здесь относятся к интерфейсу этого приложения. '
            'search_chats/read_chat/list_recent_chats ищут только историю Xopilot и не управляют мессенджером. '
            'Для внешнего окна выбери computer_start/computer_view/computer_input, используй свежие наблюдения. '
            'Если управление недоступно или нужная кнопка не наблюдается, честно объясни это, не ищи контакт в Xopilot. '
            'Короткое уточнение пользователя продолжает предыдущую задачу; не подменяй его новой задачей. '
            'Итог простого действия: не более двух коротких предложений, без списков, внутреннего кода и повторного приветствия. '
            'При недоступности Telegram не предлагай вместо него искать контакт в истории Xopilot. '
            'Не придумывай переключатель полного доступа или другие настройки, которых инструменты не показывали.')
