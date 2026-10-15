"""
Файл: /App/app/task_messages.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Действия ИИ, команды и текущий вывод процессов в сообщениях чата.
"""
import asyncio
import json
import re
import shlex
import flet as ft
from .palette import color, apply_palette
from .task_summaries import PREFIX,describe,summarize,context
try:
    from ..services import task_processes
except ImportError:
    from services import task_processes


def action_arguments(arguments):
    if arguments.get('argv'):
        return shlex.join(arguments['argv'])
    short={key:(f'[{len(value)} символов]' if key in {'content','html'} and isinstance(value,str) else value)
           for key,value in arguments.items()}
    return json.dumps(short,ensure_ascii=False,indent=2)


def code_block(value):
    runs=re.findall(r'`+',value)
    fence='`'*max(3,1+max(map(len,runs),default=0))
    return fence+'\n'+value+'\n'+fence


class TaskMessages:
    def __init__(self,page,chat_id,workspace_id,*,current_chat,chat_list,save,update,on_record=None,on_comment=None):
        self.page,self.chat_id,self.workspace_id=page,chat_id,workspace_id
        self.current_chat,self._chat_list=current_chat,chat_list
        self.save,self.update=save,update
        self.on_record,self.on_comment=on_record,on_comment
        self.items={}

    @property
    def chat_list(self):
        return self._chat_list if hasattr(self._chat_list,"controls") else self._chat_list()

    def dispatch(self,event):
        try:self.page.run_task(self.receive,event)
        except RuntimeError:pass  # The page has disconnected; no new UI task can be scheduled.

    def comment(self,text):
        if self.on_comment:self.on_comment(text)

    async def open_link(self,url):
        try:
            from ..services.external_browser import open_external
            await open_external(url)
        except Exception as exc:self.page.show_dialog(ft.SnackBar(ft.Text(str(exc))))

    def mounted(self,item):
        return self.current_chat()==self.chat_id and item['card'] in self.chat_list.controls

    def refresh(self,item):
        event=item['event'];result=event.get('result')
        process=result if isinstance(result,dict) and 'pid' in result else None
        if event.get('error'):state='Ошибка · '+event['error']
        elif process:
            state=f"PID {process['pid']} · "+('Выполняется' if process['running'] else f"Завершено · код {process['exit_code']}")
        else:state='Готово' if event['phase']=='result' else 'Выполняется…'
        item['state'].value=state
        if process:
            detail='Папка: '+process['cwd']+'\n\n'+(process['output'][-24000:] or 'Вывод ещё не поступил')
        elif result is not None:
            detail=json.dumps(result,ensure_ascii=False,indent=2)[:24000]
        else:detail=event.get('error','Вывод появится после выполнения действия')
        summary,links=summarize(event['tool'],result) if result is not None else ('',[])
        stored=event.get('stored')
        if stored and not process:
            state=stored['state'];summary=stored['summary'];links=stored.get('links',[]);detail=stored['detail']
        item['summary']=summary
        failed=state.startswith('Ошибка')
        running=event['phase']=='start' and not stored
        item['state'].value=('Не удалось выполнить · раскройте подробности' if failed else state+(' · '+summary if summary else ''))
        tone=color('#c94b4b') if failed else color('#087f8c') if running else color('#47747a')
        item['state'].color=tone
        item['indicator'].icon=ft.Icons.ERROR_OUTLINE if failed else ft.Icons.MORE_HORIZ if running else ft.Icons.CHECK_CIRCLE_OUTLINE
        item['indicator'].color=tone
        item['card'].border=ft.Border(left=ft.BorderSide(2,tone))
        if event['tool']=='computer_input' and isinstance(result,dict) and result.get('target_name'):
            item['label'].value='Действие в окне · '+result['target_name']
        item['links'].controls=[ft.TextButton(content=ft.Text(url,size=11,max_lines=1,overflow=ft.TextOverflow.ELLIPSIS),
            width=240,height=28,on_click=lambda _,url=url:self.page.run_task(self.open_link,url)) for url in links]
        item['links'].visible=bool(links)
        item['link_values']=links
        item['detail'].value=detail
        item['stop'].visible=bool(process and process['running'])
        return state,detail

    def persist(self,item):
        state,detail=self.refresh(item)
        event=item['event'];result=event.get('result')
        record=dict(tool=event['tool'],label=event['label'],title=item['title'],state=state,
            summary=item['summary'],links=item.get('link_values',[]),arguments_text=item['arguments'],detail=detail,
            process={key:value for key,value in result.items() if key!='output'} if isinstance(result,dict) and 'pid' in result else None)
        text=PREFIX+json.dumps(record,ensure_ascii=False)
        try:
            if item['message_id'] is None:
                item['message_id']=self.save(self.chat_id,text)
                item['card'].data=item['message_id']
            else:self.update(item['message_id'],text)
            if self.on_record:self.on_record(item['message_id'],context(text))
        except Exception as exc:
            self.page.show_dialog(ft.SnackBar(ft.Text('Действие выполнено, но журнал не сохранён: '+str(exc))))

    async def stop(self,item):
        result=item['event'].get('result') or {}
        try:
            process=task_processes.get(result.get('id'),'chat:'+str(self.chat_id),self.workspace_id)
            snapshot=await asyncio.to_thread(process.stop)
            item['event'].update(phase='result',result=snapshot)
            self.persist(item)
            if self.mounted(item):item['card'].update()
        except Exception as exc:self.page.show_dialog(ft.SnackBar(ft.Text(str(exc))))

    async def watch(self,item,identifier):
        previous=None
        while True:
            try:result=task_processes.get(identifier,'chat:'+str(self.chat_id),self.workspace_id).snapshot()
            except ValueError:return
            if result!=previous:
                item['event'].update(result=result)
                self.refresh(item)
                if self.mounted(item):item['card'].update()
                previous=result
            if not result['running']:
                if item['message_id'] is not None:self.persist(item)
                return
            await asyncio.sleep(1)

    def make_item(self,event):
        title=describe(event['tool'],event['arguments'])
        stored=event.get('stored')
        if stored:title=stored['title']
        label=ft.Text(event['label']+(' · '+title if title else ''),weight=ft.FontWeight.W_500,size=12,max_lines=2,overflow=ft.TextOverflow.ELLIPSIS)
        state=ft.Text('',size=11,color=color('#47747a'))
        detail=ft.Text('',size=12,font_family='monospace',selectable=True)
        arguments=action_arguments(event['arguments'])
        if stored:arguments=stored['arguments_text']
        stop=ft.TextButton(content='Остановить процесс',visible=False)
        state.max_lines=2;state.overflow=ft.TextOverflow.ELLIPSIS
        links=ft.Row(wrap=True,spacing=0,visible=False)
        indicator=ft.Icon(ft.Icons.MORE_HORIZ,size=16,color=color('#087f8c'))
        tile=ft.ExpansionTile(title=label,subtitle=state,leading=indicator,dense=True,
            min_tile_height=30,tile_padding=0,controls_padding=8,expanded=False,
            expanded_cross_axis_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[ft.Text(arguments,size=11,font_family='monospace',selectable=True),detail])
        card=ft.Container(padding=ft.Padding.symmetric(horizontal=10,vertical=0),border_radius=8,
            bgcolor=None,content=ft.Column(spacing=0,controls=[tile,links,stop]))
        item=dict(card=card,indicator=indicator,label=label,state=state,detail=detail,stop=stop,arguments=arguments,event=event,title=title,links=links,
                  message_id=None,watching=False)
        stop.on_click=lambda _:self.page.run_task(self.stop,item)
        apply_palette(card)
        return item

    def restore_saved(self,record,message_id):
        event=dict(id='message:'+str(message_id),tool=record['tool'],label=record['label'],arguments={},phase='result',stored=record)
        process=record.get('process')
        if isinstance(process,dict):
            try:event['result']=task_processes.get(process.get('id'),'chat:'+str(self.chat_id),self.workspace_id).snapshot()
            except ValueError:
                if process.get('running'):record={**record,'state':'Журнал команды · процесс сейчас не отслеживается'};event['stored']=record
        item=self.make_item(event);item['message_id']=message_id;item['card'].data=message_id;self.refresh(item)
        if event.get('result',{}).get('running'):self.page.run_task(self.watch,item,event['result']['id'])
        return item['card']

    def restore(self,event,message_id):
        item=self.make_item(event);item["message_id"]=message_id;item["card"].data=message_id
        self.refresh(item)
        if event["result"]["running"]:self.page.run_task(self.watch,item,event["result"]["id"])
        return item["card"]

    async def receive(self,event):
        item=self.items.get(event["id"])
        if item is None:
            item=self.make_item(event)
            self.items[event["id"]]=item
            if self.current_chat()==self.chat_id:self.chat_list.controls.insert(0,item["card"])
        item['event']=event
        self.refresh(item)
        result=event.get('result')
        if isinstance(result,dict) and result.get('running') and not item['watching']:
            item['watching']=True;self.page.run_task(self.watch,item,result['id'])
        if event['phase'] in {'result','error'}:self.persist(item)
        if self.mounted(item):self.chat_list.update()
