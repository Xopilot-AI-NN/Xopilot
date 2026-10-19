"""Файл: /App/services/api_tools.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Нативные вызовы функций API с исходными ID и результатами инструментов.
"""
import json
from .task_control import EmptyModelReplyError


class ToolReply(str):
    def __new__(cls, text, message):
        value = super().__new__(cls, text)
        value.message = message
        return value


def decode(message, tools):
    calls = message.get('tool_calls')
    if not calls:
        content = message.get('content')
        if isinstance(content, list):
            content = '\n'.join(p.get('text', '') for p in content if isinstance(p, dict))
        if not isinstance(content, str) or not content.strip():
            raise EmptyModelReplyError('API вернул пустой ответ вместо текста или вызова инструмента')
        # Already-valid legacy envelopes remain supported during provider fallback.
        try:
            legacy = json.loads(content)
            if isinstance(legacy, dict) and any(k in legacy for k in ('final', 'tool', 'actions')):
                return content.strip()
        except ValueError:
            pass
        return json.dumps({'final': content.strip()}, ensure_ascii=False)
    if not isinstance(calls, list):raise ValueError('Некорректные вызовы инструментов API')
    allowed = {t['function']['name'] for t in tools}
    actions, identifiers = [], set()
    for call in calls:
        function = call.get('function', {})
        identifier = call.get('id')
        if call.get('type') != 'function' or function.get('name') not in allowed:
            raise ValueError('API вызвал недоступный инструмент')
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError('Нужны уникальные ID вызовов инструментов API')
        args = json.loads(function['arguments'])
        if not isinstance(args, dict):raise ValueError('Аргументы функции должны быть объектом')
        identifiers.add(identifier)
        actions.append({'tool': function['name'], 'arguments': args})
    envelope = {'actions': actions}
    if isinstance(message.get('content'), str) and message['content'].strip():
        envelope['message'] = message['content'].strip()
    return ToolReply(json.dumps(envelope, ensure_ascii=False),
        {'role': 'assistant', 'content': message.get('content'), 'tool_calls': calls,
         **({key:message[key] for key in ('reasoning_details','reasoning_content') if key in message})})


def messages(history, current, results=None):
    output = []
    for item in [*(history or []), {'role': 'user', 'content': current, '_tool_results': results}]:
        content = item.get('content', '')
        if isinstance(content, ToolReply):
            output.append(content.message)
        elif item.get('_tool_results'):
            output.extend(item['_tool_results'])
            marker = '\n\nУточнения пользователя к текущей задаче:\n'
            if isinstance(content, str) and marker in content:
                output.append({'role': 'user', 'content': content.split(marker, 1)[1]})
        else:
            output.append({'role': 'assistant' if item['role'] in {'ai', 'assistant', 'model'} else 'user',
                           'content': content})
    return output


def results(reply, executed):
    if not isinstance(reply, ToolReply):return None
    calls = reply.message['tool_calls']
    if len(calls) != len(executed):return None
    return [{'role': 'tool', 'tool_call_id': call['id'],
             'content': json.dumps(result, ensure_ascii=False)} for call, result in zip(calls, executed)]
