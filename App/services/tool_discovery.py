"""
Файл: /App/services/tool_discovery.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Компактный каталог и загрузка схем инструментов по запросу модели.
"""
import re

GROUPS={
    'memory':('памят запомн пользователь предпочт память memory remember preference',{'search_memory','save_memory'}),
    'chats':('чат переписк разговор chat history conversation',{'search_chats','read_chat','list_recent_chats'}),
    'library':('библиотек материал заметк library material note document',{'list_library','search_library','read_material','create_note','create_document'}),
    'canvas':('канвас рисун сайт предпросмотр canvas drawing preview',{'list_canvases','read_canvas','create_canvas','update_canvas','inspect_canvas','interact_canvas'}),
    'web':('интернет браузер сайт поисков search web website browser url',{'search_web','read_website'}),
    'project':('проект код файл папк команд компиляц процесс project code file folder command process compile',{'list_project_files','read_project_file','write_project_file','run_project_command','start_project_process','read_project_process','stop_project_process'}),
    'computer':('пк компьютер экран курсор мыш кнопк desktop computer screen cursor click',{'computer_start','computer_view','computer_input'}),
    'device':('приложен музык трек телефон app launch media music android',{'list_apps','launch_app','control_media'}),
}
CATALOG='memory — память; chats — только история Xopilot (не мессенджеры); library — материалы/заметки/документы; canvas — Canvas; web — интернет; project — файлы/команды проекта; computer — экран/окна ПК; device — приложения/музыка.'
_STOP={'для','как','что','мне','надо','нужны','нужен','нужно','инструмент','инструменты','tool','tools','the','for','and'}


def discover(query, available):
    words={w.casefold() for w in re.findall(r'[\w-]{3,}',str(query)) if w.casefold() not in _STOP}
    scores={}
    exact={name for name in available if name!='discover_tools' and name.casefold() in str(query).casefold()}
    if exact:return {name:available[name] for name in available if name in exact}
    for name in available:
        if name=='discover_tools':continue
        score=0
        for group,(hints,names) in GROUPS.items():
            if name not in names:continue
            tokens=hints.split()+[group]
            score+=sum(1 for word in words if any(word.startswith(t) or t.startswith(word) for t in tokens))
        if score:scores[name]=score
    names=sorted(scores,key=lambda name:(-scores[name],list(available).index(name)))[:5]
    return {name:available[name] for name in names}
