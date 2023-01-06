import asyncio
import logging
import os
import time
import threading
from datetime import datetime
from os.path import *

from DMR.LiveAPI.danmaku import DanmakuClient

def get_length(string:str,fontsize):
    length = 0
    for s in string:
        if len(s.encode('utf-8')) == 1:
            length += 0.5*fontsize
        else:
            length += fontsize
    return int(length)

class DanmakuWriter():
    def __init__(self,url,output,segment,description,width,height,margin,dmrate,font,fontsize,overflow_op,dmduration,opacity,**kwargs) -> None:
        self.stoped = False

        self.url = url
        self.output = output + '.ass'
        self.segment = segment
        self.height = height
        self.width = width
        self.dmrate = dmrate
        self.fontsize = fontsize
        self.font = font

        self.margin = margin
        self.overflow_op = overflow_op
        self.dmduration = dmduration
        self.opacity = hex(255-int(opacity*255))[2:]
        if len(self.opacity) < 2:
            self.opacity = '0'+self.opacity
        self.kwargs = kwargs

        self.lock = threading.Lock()
        
        self.ntrack = int((height*dmrate - fontsize)/(fontsize+margin))
        self.trackinfo = [None for _ in range(self.ntrack)]

        self.meta_info = [
            '[Script Info]',
            f'Title: {description}',
            'ScriptType: v4.00+',
            'Collisions: Normal',
            f'PlayResX: {self.width}',
            f'PlayResY: {self.height}',
            'Timer: 100.0000',
            '',
            '[V4+ Styles]',
            'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
            # f'Style: Fix,Microsoft YaHei UI,25,&H66FFFFFF,&H66FFFFFF,&H66000000,&H66000000,1,0,0,0,100,100,0,0,1,2,0,2,20,20,2,0',
            f'Style: R2L,{self.font},{self.fontsize},&H{self.opacity}ffffff,,&H{self.opacity}242424,,-1,0,0,0,100,100,0,0,1,2,0,1,0,0,0,0',
            '',
            '[Events]',
            'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
        ]
        self.part = 0

    def start(self):
        self.starttime = datetime.now().timestamp()
        self.dm_file = self.output.replace(f'%03d','%03d'%self.part)
        with open(self.dm_file,'w',encoding='utf-8') as f:
            for info in self.meta_info:
                f.write(info+'\n')

        def monitor():
            while not self.stoped:
                if int(self.duration/self.segment) != self.part:
                    self.part += 1
                    self.dm_file = self.output.replace(f'%03d','%03d'%self.part)
                    with open(self.dm_file,'w',encoding='utf-8') as f:
                        for info in self.meta_info:
                            f.write(info+'\n')
                else:
                    time.sleep(5)
        
        if self.segment > 0:
            self.monitor = threading.Thread(target=monitor,daemon=True)
            self.monitor.start()
        
        self.start_dmc()
  
    @property
    def duration(self):
        return datetime.now().timestamp() - self.starttime

    def dm_available(self,dm) -> bool:
        if not (dm.get('msg_type') == 'danmaku'):
            return 
        if not dm.get('name'):
            return 
        if '\{' in dm.get('content'):
            return 
        return True
    
    def start_dmc(self):
        async def danmu_monitor():
            q = asyncio.Queue()
            dmc = DanmakuClient(self.url, q)
            task = asyncio.create_task(dmc.start())
            retry = 0

            while not self.stoped:
                try:
                    dm = q.get_nowait()
                    dm['time'] = self.duration
                    if self.dm_available(dm):
                        self.add(dm)
                    continue
                except asyncio.QueueEmpty:
                    pass
                        
                if task.done():
                    logging.error('弹幕下载线程异常退出，正在重试...')
                    retry += 1
                    await asyncio.sleep(min(5*retry,300))
                    dmc = DanmakuClient(self.url, q)
                    task = asyncio.create_task(dmc.start())
                
                await asyncio.sleep(0.1)
            await dmc.stop()
    
        monitor = threading.Thread(target=asyncio.run,args=(danmu_monitor(),),daemon=True)
        monitor.start()

    def add(self,dm):
        tid = 0
        maxbias = -1
        
        def calc_bias(dm,tic):
            if not dm:
                return self.width
            dm_length = get_length(dm['content'],self.fontsize)
            bias = (tic - dm['time'])*(dm_length+self.width)/self.dmduration - dm_length 
            return bias
        
        for i,latest_dm in enumerate(self.trackinfo):
            bias = calc_bias(latest_dm,dm['time'])
            if bias > 0.2*self.width:
                tid = i
                maxbias = bias
                break
            if bias > maxbias:
                maxbias = bias
                tid = i
        
        dm_length = get_length(dm['content'],self.fontsize)
        if maxbias<0.05*self.width and self.overflow_op == 'ignore':
            return False
        
        self.trackinfo[tid] = dm
        x0 = self.width + dm_length
        x1 = -dm_length
        y = self.fontsize + (self.fontsize+self.margin)*tid

        t0 = dm['time']-self.part*self.segment
        t1 = t0+self.dmduration

        t0 = time.strftime('%%H:%%M:%%S.%s'%str(t0).split('.')[1][:2],time.gmtime(t0))
        t1 = time.strftime('%%H:%%M:%%S.%s'%str(t1).split('.')[1][:2],time.gmtime(t1))

        dm_info = f'Dialogue: 0,{t0},{t1},R2L,,0,0,0,,'
        dm_info += '{\move(%d,%d,%d,%d)}'%(x0,y,x1,y)
        if dm['color'] != 'ffffff':
            dm_info += '{\\1c&H%s&}'%(self.opacity+dm['color'])
        dm_info += dm['content']

        with self.lock,open(self.dm_file,'a',encoding='utf-8') as f:
            f.write(dm_info+'\n')
        
        return True

    def stop(self):
        self.stoped = True
        return True
