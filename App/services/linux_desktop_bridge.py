"""
Файл: /App/services/linux_desktop_bridge.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Изолированный системный помощник Gio/Portal: приложения Linux,
          разрешённая сессия мыши/клавиатуры и кадры PipeWire. Без shell/root.
"""
import json
import os
import sys
import subprocess
import time
import uuid
import gi
from gi.repository import Gio, GLib

BUS='org.freedesktop.portal.Desktop'
PATH='/org/freedesktop/portal/desktop'
RD='org.freedesktop.portal.RemoteDesktop'
SC='org.freedesktop.portal.ScreenCast'



class Desktop:
    def __init__(self):
        self.bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
        self.session=None;self.stream=None;self.size=None;self.fd=None;self.devices=0;self.native=None;self.accessibility=None
        self.niri='niri' in os.environ.get('XDG_CURRENT_DESKTOP','').lower()

    def call(self,interface,method,signature,values):
        return self.bus.call_sync(BUS,PATH,interface,method,GLib.Variant(signature,values),None,
                                  Gio.DBusCallFlags.NONE,15000,None)

    def request(self,interface,method,signature,values):
        token='xopilot_'+uuid.uuid4().hex
        values[-1]['handle_token']=GLib.Variant('s',token)
        expected='/org/freedesktop/portal/desktop/request/'+self.bus.get_unique_name()[1:].replace('.','_')+'/'+token
        loop=GLib.MainLoop();answer=[]
        def response(*args):answer.append(args[-2].unpack());loop.quit()
        subscription=self.bus.signal_subscribe(BUS,'org.freedesktop.portal.Request','Response',expected,None,0,response,None)
        timed=GLib.timeout_add_seconds(120,lambda:(loop.quit(),False)[1])
        try:
            self.call(interface,method,signature,tuple(values))
            if not answer:loop.run()
            if not answer:raise RuntimeError('Системное разрешение не получено за 120 секунд')
            code,result=answer[0]
            if code:raise RuntimeError(f'{interface}.{method}: пользователь или система отклонили доступ (код {code})')
            return result
        finally:
            self.bus.signal_unsubscribe(subscription)
            if GLib.MainContext.default().find_source_by_id(timed):GLib.source_remove(timed)

    def start(self):
        if self.session:return {'size':self.size,'devices':self.devices}
        interface=SC
        result=self.request(interface,'CreateSession','(a{sv})',[{'session_handle_token':GLib.Variant('s','xopilot_'+uuid.uuid4().hex)}])
        self.session=result['session_handle']
        try:
            self.request(SC,'SelectSources','(oa{sv})',[self.session,{'types':GLib.Variant('u',1),
                 'multiple':GLib.Variant('b',False),'cursor_mode':GLib.Variant('u',2)}])
            result=self.request(interface,'Start','(osa{sv})',[self.session,'',{}])
            self.devices=result.get('devices',0)
            streams=result.get('streams',[])
            if not streams:raise RuntimeError('Нужны экран, мышь и клавиатура')
            self.stream,properties=streams[0];self.serial=properties.get('pipewire-serial',self.stream);self.size=properties.get('logical_size',properties.get('size'))
            if self.niri:
                from wayland_screen import WaylandScreen
                self.native=WaylandScreen(properties.get('id'));self.devices=3
            if not self.size:raise RuntimeError('Портал не сообщил размеры экрана')
            from linux_accessibility import Accessibility
            self.accessibility=Accessibility(self.bus)
            response,fds=self.bus.call_with_unix_fd_list_sync(BUS,PATH,SC,'OpenPipeWireRemote',
                GLib.Variant('(oa{sv})',(self.session,{})),None,0,15000,None,None)
            self.fd=fds.get(response.unpack()[0])
            return {'size':self.size,'devices':self.devices}
        except Exception:self.close();raise

    def input(self,a):
        if not self.accessibility:raise RuntimeError('Сессия интерфейса не разрешена')
        target=self.accessibility.targets.get(a.get('target'))
        if not target:raise ValueError('Нужен target из последнего computer_view')
        rect=target['entry']['rect']
        if self.native and rect and rect[2]>0 and rect[3]>0:
            x,y=rect[0]+rect[2]//2,rect[1]+rect[3]//2
            if 0<=x<self.size[0] and 0<=y<self.size[1]:
                from pathlib import Path
                asset=Path(os.environ.get('XOPILOT_CURSOR_ASSET',str(Path(__file__).parent.parent/'assets/Icons/icon_cursor/icon_ai_cursor.svg')))
                self.native.mark(x,y,str(asset))
        return self.accessibility.perform(a)

    def inspect(self):
        if not self.accessibility:raise RuntimeError('Сессия не разрешена')
        return self.accessibility.inspect()

    def capture(self,path):
        if self.native:
            self.native.capture(path)
            return {'size':self.size,'captured':True}
        if self.fd is None:raise RuntimeError('Экран не разрешён')
        gi.require_version('Gst','1.0')
        from gi.repository import Gst
        Gst.init(None)
        pipeline=Gst.Pipeline.new(None)
        elements=[Gst.ElementFactory.make(n,None) for n in ['pipewiresrc','capsfilter','videoconvert','pngenc','filesink']]
        if any(e is None for e in elements):raise RuntimeError('Нужны GStreamer pipewiresrc/videoconvert/pngenc')
        source,filter_,convert,encoder,sink=elements
        filter_.set_property('caps',Gst.Caps.from_string('video/x-raw'))
        capture_fd=os.dup(self.fd)
        source.set_property('fd',capture_fd);source.set_property('target-object',str(self.serial)) if self.serial!=self.stream else source.set_property('path',str(self.stream));source.set_property('num-buffers',1)
        sink.set_property('location',path)
        for element in elements:pipeline.add(element)
        for a,b in zip(elements,elements[1:]):
            if not a.link(b):raise RuntimeError('Не удалось подключить поток экрана')
        try:
            pipeline.set_state(Gst.State.PLAYING)
            message=pipeline.get_bus().timed_pop_filtered(15*Gst.SECOND,Gst.MessageType.ERROR|Gst.MessageType.EOS)
            if message is None:raise RuntimeError('Кадр экрана не получен')
            if message.type==Gst.MessageType.ERROR:raise RuntimeError(str(message.parse_error()))
            return {'size':self.size,'captured':True}
        finally:
            pipeline.set_state(Gst.State.NULL)
            try:os.close(capture_fd)
            except OSError:pass

    def close(self):
        if self.accessibility:self.accessibility.close();self.accessibility=None
        if self.native:self.native.close();self.native=None
        if self.session:
            try:self.bus.call_sync(BUS,self.session,'org.freedesktop.portal.Session','Close',None,None,0,3000,None)
            except Exception:pass
        if self.fd is not None:os.close(self.fd)
        self.session=None;self.fd=None


def apps():
    return sorted([{'package':a.get_id(),'name':a.get_display_name()} for a in Gio.AppInfo.get_all()
                   if a.should_show() and a.get_id()],key=lambda a:a['name'].casefold())


def main():
    desktop=Desktop()
    try:
        for line in sys.stdin:
            try:
                request=json.loads(line);action=request['method'];a=request.get('arguments',{})
                if action=='apps':result=apps()
                elif action=='launch':
                    entry=next((app for app in Gio.AppInfo.get_all() if app.should_show() and app.get_id()==a['package']),None)
                    if not entry:raise ValueError('Выберите установленное приложение из list_apps')
                    os.environ.pop('NO_AT_BRIDGE',None)
                    result={'launched':bool(entry.launch([],None)),'package':entry.get_id()}
                elif action=='start':result=desktop.start()
                elif action=='capture':result=desktop.capture(a['path'])
                elif action=='input':result=desktop.input(a)
                elif action=='inspect':result=desktop.inspect()
                elif action=='close':desktop.close();result={'closed':True}
                else:raise ValueError('Неизвестный метод')
                print(json.dumps({'result':result},ensure_ascii=False),flush=True)
            except Exception as exc:print(json.dumps({'error':str(exc)},ensure_ascii=False),flush=True)
    finally:desktop.close()

if __name__=='__main__':main()
