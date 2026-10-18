"""
Файл: /App/services/linux_accessibility.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Действия с основными окнами через AT-SPI без системной мыши,
          эмуляции клавиатуры, смены фокуса и чтения паролей.
"""
import uuid
import time
import os
from pathlib import Path
from gi.repository import Gio,GLib

PREFIX='org.a11y.atspi.'


class Accessibility:
    def __init__(self,session_bus):
        address=session_bus.call_sync('org.a11y.Bus','/org/a11y/bus','org.a11y.Bus','GetAddress',None,None,0,3000,None).unpack()[0]
        self.bus=Gio.DBusConnection.new_for_address_sync(address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT|Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,None,None)
        self.targets={}
        self._inspect_deadline=None

    def timeout(self):
        if self._inspect_deadline is None:return 1500
        remaining=int((self._inspect_deadline-time.monotonic())*1000)
        if remaining<=0:raise TimeoutError('Завершено время чтения элементов экрана')
        return min(250,remaining)

    def call(self,reference,interface,method,signature=None,arguments=()):
        return self.bus.call_sync(reference[0],reference[1],PREFIX+interface,method,
            GLib.Variant(signature,arguments) if signature else None,None,0,self.timeout(),None).unpack()

    def prop(self,reference,name):
        return self.bus.call_sync(reference[0],reference[1],'org.freedesktop.DBus.Properties','Get',
            GLib.Variant('(ss)',(PREFIX+'Accessible',name)),None,0,self.timeout(),None).unpack()[0]

    def inspect(self):
        # One deadline covers all RPCs, including a slow registry/root node.
        # Never multiply the old 1.5 s timeout by every property of every node.
        self._inspect_deadline=time.monotonic()+3
        try:return self._inspect()
        finally:self._inspect_deadline=None

    def is_controller(self, reference):
        """Never interrogate/control our own GTK/Flutter accessibility thread."""
        controller=int(os.environ.get('XOPILOT_CONTROLLER_PID', '0'))
        parent=int(os.environ.get('XOPILOT_CONTROLLER_PARENT_PID', '0'))
        if not controller:return False
        try:
            pid=self.bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'GetConnectionUnixProcessID',
                GLib.Variant('(s)', (reference[0],)), None, 0, self.timeout(), None).unpack()[0]
            if pid==controller:return True
            process=Path('/proc')/str(pid)
            ppid=int((process/'stat').read_text().rpartition(')')[2].split()[1])
            executable=(process/'exe').resolve().name.casefold()
            return ppid in {controller, parent} and executable in {'flet', 'xopilot'}
        except (OSError, ValueError, IndexError, GLib.Error):
            return False

    def _inspect(self):
        self.targets={};rows=[]
        roots=self.call(('org.a11y.atspi.Registry','/org/a11y/atspi/accessible/root'),'Accessible','GetChildren')[0]
        pending=[(tuple(r),'',0) for r in roots if not self.is_controller(r)];visited=set()
        while pending and len(visited)<220 and time.monotonic()<self._inspect_deadline:
            reference,parent,depth=pending.pop(0)
            if reference in visited or depth>12 or reference[1].endswith('/null'):continue
            visited.add(reference)
            try:
                name=self.prop(reference,'Name') or ''
                role=self.call(reference,'Accessible','GetRoleName')[0]
                interfaces=self.call(reference,'Accessible','GetInterfaces')[0]
                identifier=uuid.uuid4().hex
                actions=self.call(reference,'Action','GetActions')[0] if PREFIX+'Action' in interfaces else []
                rect=None
                if PREFIX+'Component' in interfaces:
                    rect=list(self.call(reference,'Component','GetExtents','(u)',(0,))[0])
                protected=self.call(reference,'Accessible','GetRole')[0]==40 or 'password' in role.casefold() or 'парол' in role.casefold()
                value='[скрыто]' if protected else None
                if not protected and PREFIX+'Text' in interfaces:
                    value=self.call(reference,'Text','GetText','(ii)',(0,400))[0]
                entry={'id':identifier,'parent_id':parent,'name':name[:300],'role':role,'rect':rect,
                       'actions':[a[0] for a in actions], 'editable':PREFIX+'EditableText' in interfaces and not protected}
                if value is not None:entry['text']=value
                rows.append(entry)
                self.targets[identifier]={'reference':reference,'entry':entry,'actions':actions,'protected':protected}
                children=self.call(reference,'Accessible','GetChildren')[0]
                pending.extend(((r[0] or reference[0],r[1]),identifier,depth+1) for r in children)
            except Exception:continue  # A disappearing or inaccessible node never authorizes raw input.
        return rows

    def perform(self,arguments):
        target=self.targets.get(arguments.get('target'))
        if not target:raise ValueError('Выберите target из последнего computer_view; старые ID недействительны')
        entry=target['entry'];action=arguments.get('action')
        if action=='set_text':
            if not entry['editable'] or target['protected']:raise ValueError('Это поле не поддерживает независимое редактирование')
            result=self.call(target['reference'],'EditableText','SetTextContents','(s)',(arguments['text'],))[0]
        elif action=='click':
            names=entry['actions'];requested=arguments.get('name')
            if requested is None:
                if len(names)!=1:raise ValueError('Укажи name из списка actions выбранного элемента')
                index=0
            else:
                if requested not in names:raise ValueError('Нет такого доступного действия')
                index=names.index(requested)
            result=self.call(target['reference'],'Action','DoAction','(i)',(index,))[0]
        else:raise ValueError('Независимый ввод поддерживает click и set_text по ID элемента')
        if not result:raise RuntimeError('Приложение отклонило действие доступности')
        return {'performed':True,'action':action,'target_name':entry['name'],'rect':entry['rect']}

    def close(self):
        self.targets={};self.bus.close_sync(None)
