"""
Файл: /App/services/wayland_screen.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Кадры и отдельный указатель ИИ для Niri; указатель не принимает
          ввод, не меняет системный курсор и не создаёт виртуальную клавиатуру.
"""
import array
import os
from pathlib import Path
import socket
import struct
import time


def uint(*values):return struct.pack('='+len(values)*'I',*values)

def string(value):
    raw=value.encode()+b'\0'
    return uint(len(raw))+raw+b'\0'*((-len(raw))%4)


def read_string(payload,offset):
    length=struct.unpack_from('=I',payload,offset)[0];offset+=4
    return payload[offset:offset+length-1].decode(),offset+(length+3)//4*4


class WaylandScreen:
    def __init__(self,output_name=None):
        self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.socket.settimeout(5);self.buffer=b'';self.next_id=2;self.globals={};self.outputs={};self.frames={};self.layers={};self.cursor=None
        display=os.environ.get('WAYLAND_DISPLAY','wayland-0')
        path=display if display.startswith('/') else str(Path(os.environ['XDG_RUNTIME_DIR'])/display)
        try:
            self.socket.connect(path);self.registry=self.allocate()
            self.send(1,1,uint(self.registry));self.roundtrip()
            outputs=[]
            for name,version in self.globals.get('wl_output',[]):
                identifier=self.allocate();self.outputs[identifier]=None
                self.send(self.registry,0,uint(name)+string('wl_output')+uint(min(4,version),identifier))
                outputs.append(identifier)
            self.roundtrip()
            if len(outputs)==1:output=outputs[0]
            else:
                matches=[identifier for identifier in outputs if self.outputs[identifier]==output_name]
                if len(matches)!=1:raise RuntimeError('Для нескольких мониторов нужен однозначный ID выбранного выхода')
                output=matches[0]
            self.output=output

        except BaseException:self.close();raise

    def allocate(self):
        result=self.next_id;self.next_id+=1;return result

    def send(self,identifier,opcode,payload=b'',fd=None):
        packet=uint(identifier,((8+len(payload))<<16)|opcode)+payload
        if fd is None:self.socket.sendall(packet)
        else:
            sent=self.socket.sendmsg([packet],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))])
            if sent<len(packet):self.socket.sendall(packet[sent:])

    def event(self):
        while len(self.buffer)<8:
            chunk=self.socket.recv(65536)
            if not chunk:raise RuntimeError('Wayland-сессия завершена')
            self.buffer+=chunk
        identifier,header=struct.unpack_from('=II',self.buffer);length=header>>16;opcode=header&65535
        if length<8 or length>65535:raise RuntimeError('Неверное сообщение Wayland')
        while len(self.buffer)<length:
            chunk=self.socket.recv(65536)
            if not chunk:raise RuntimeError('Wayland-сессия завершена')
            self.buffer+=chunk
        payload=self.buffer[8:length];self.buffer=self.buffer[length:]
        if identifier==1 and opcode==0:
            error,_=read_string(payload,8);raise RuntimeError('Wayland: '+error)
        if identifier==self.registry and opcode==0:
            name=struct.unpack_from('=I',payload)[0];interface,offset=read_string(payload,4)
            version=struct.unpack_from('=I',payload,offset)[0]
            self.globals.setdefault(interface,[]).append((name,version))
        if identifier in self.outputs and opcode==4:self.outputs[identifier]=read_string(payload,0)[0]
        if identifier in self.frames:
            frame=self.frames[identifier]
            if opcode==0:frame['buffer']=struct.unpack('=IIII',payload)
            elif opcode==1:frame['flags']=struct.unpack('=I',payload)[0]
            elif opcode==2:frame['ready']=True
            elif opcode==3:frame['failed']=True
        if identifier in self.layers and opcode==0:self.layers[identifier]['serial']=struct.unpack_from('=I',payload)[0]
        return identifier,opcode

    def roundtrip(self):
        callback=self.allocate();self.send(1,0,uint(callback))
        while self.event()!=(callback,0):pass

    def bind(self,interface,version):
        entries=self.globals.get(interface,[])
        if not entries or entries[0][1]<version:raise RuntimeError('Композитор не поддерживает '+interface)
        identifier=self.allocate();self.send(self.registry,0,uint(entries[0][0])+string(interface)+uint(version,identifier))
        return identifier

    def capture(self,path):
        from PIL import Image
        manager=self.bind('zwlr_screencopy_manager_v1',1)
        shm=self.bind('wl_shm',1)
        frame_id=self.allocate();frame={};self.frames[frame_id]=frame
        self.send(manager,0,uint(frame_id,1,self.output))
        while 'buffer' not in frame:
            self.event()
            if frame.get('failed'):raise RuntimeError('Композитор отказал в кадре')
        format_,width,height,stride=frame['buffer']
        if format_ not in {0,1} or not 0<width<=16384 or not 0<height<=16384 or not width*4<=stride<=width*4+65536:
            raise RuntimeError('Неподдерживаемый формат кадра Wayland')
        size=stride*height
        if size>256*1024*1024:raise RuntimeError('Кадр экрана слишком велик')
        fd=os.memfd_create('xopilot-screen',os.MFD_CLOEXEC);os.ftruncate(fd,size)
        pool=self.allocate();buffer=self.allocate()
        try:
            self.send(shm,0,uint(pool,size),fd)
            self.send(pool,0,uint(buffer,0,width,height,stride,format_))
            self.send(frame_id,0,uint(buffer))
            while not frame.get('ready'):
                self.event()
                if frame.get('failed'):raise RuntimeError('Кадр Wayland не получен')
            raw=os.pread(fd,size,0)
            image=Image.frombytes('RGBA',(width,height),raw,'raw','BGRA',stride,1)
            if frame.get('flags',0)&1:image=image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            image.convert('RGB').save(path)
        finally:
            self.send(buffer,0);self.send(pool,1);self.send(frame_id,1)
            self.frames.pop(frame_id,None);os.close(fd)

    def mark(self,x,y,asset):
        import gi
        gi.require_version('GdkPixbuf','2.0')
        from gi.repository import GdkPixbuf
        if self.cursor is None:
            compositor=self.bind('wl_compositor',4);shm=self.bind('wl_shm',1)
            manager=self.bind('zwlr_layer_shell_v1',1)
            surface=self.allocate();region=self.allocate();layer=self.allocate()
            self.send(compositor,0,uint(surface));self.send(compositor,1,uint(region))
            self.send(surface,5,uint(region));self.send(region,0)
            self.layers[layer]={}
            self.send(manager,0,uint(layer,surface,self.output,3)+string('xopilot-ai-cursor'))
            self.send(layer,0,uint(36,36));self.send(layer,1,uint(5))
            self.send(layer,2,struct.pack('=i',-1));self.send(layer,4,uint(0))
            self.send(surface,6)
            while 'serial' not in self.layers[layer]:self.event()
            self.send(layer,6,uint(self.layers[layer]['serial']))
            pixbuf=GdkPixbuf.Pixbuf.new_from_file_at_scale(asset,36,36,True)
            from PIL import Image
            image=Image.frombytes('RGBA',(pixbuf.get_width(),pixbuf.get_height()),pixbuf.get_pixels(),'raw','RGBA',pixbuf.get_rowstride(),1)
            rgba=image.tobytes();pixels=bytearray()
            for i in range(0,len(rgba),4):
                r,g,b,a=rgba[i:i+4];pixels.extend([b*a//255,g*a//255,r*a//255,a])
            fd=os.memfd_create('xopilot-ai-cursor',os.MFD_CLOEXEC);os.write(fd,pixels)
            pool=self.allocate();buffer=self.allocate()
            self.send(shm,0,uint(pool,len(pixels)),fd)
            self.send(pool,0,uint(buffer,0,image.width,image.height,image.width*4,0))
            self.send(surface,1,uint(buffer)+struct.pack('=ii',0,0));self.send(surface,2,struct.pack('=iiii',0,0,36,36))
            self.cursor={'surface':surface,'layer':layer,'fd':fd,'point':(x,y)}
        old_x,old_y=self.cursor['point']
        for step in range(1,9):
            fraction=step/8;fraction=fraction*fraction*(3-2*fraction)
            current_x=round(old_x+(x-old_x)*fraction);current_y=round(old_y+(y-old_y)*fraction)
            self.send(self.cursor['layer'],3,struct.pack('=iiii',current_y,0,0,current_x))
            self.send(self.cursor['surface'],6);self.roundtrip();time.sleep(.01)
        self.cursor['point']=(x,y)

    def close(self):
        self.socket.close()
        if self.cursor:os.close(self.cursor['fd']);self.cursor=None
