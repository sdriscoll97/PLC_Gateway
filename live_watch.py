"""Embedded watch tree with bounded, asynchronous reads of expanded scalar tags."""
import queue
import threading
import time
import tkinter as tk
from watch_tree import WatchBrowser

class LiveWatchBrowser(WatchBrowser):
    INTERVAL=0.5; BATCH_SIZE=32
    def __init__(self,*args,**kwargs):
        self.reader=None; self.online=False; self.read_results=queue.Queue(); self.read_epoch=0; self.read_busy=False; self.next_read=0; self.read_offset=0
        super().__init__(*args,**kwargs)
        self.read_enabled=tk.BooleanVar(master=self.top,value=False)
        self.tree.configure(columns=('value','type','access','state'))
        for key,title,width in [('value','Value',160),('type','Logix type',140),('access','Definition access',140),('state','Status',180)]:
            self.tree.heading(key,text=title); self.tree.column(key,width=width)
        self.tree.bind('<<TreeviewClose>>',self._collapse,add='+')
    def insert(self,parent,node,root=False):
        iid=super().insert(parent,node,root); values=self.tree.item(iid,'values'); self.tree.item(iid,values=('',)+tuple(values)); return iid
    def render_roots(self): self.read_epoch+=1; self.read_offset=0; super().render_roots()
    def load_online(self,refresh=False): self.online=True; super().load_online(refresh)
    def load(self,path,example=False): self.online=False; self.read_enabled.set(False); self.toggle_read(); super().load(path,example)
    def visible_leaves(self):
        result={}
        def visit(parent):
            for iid in self.tree.get_children(parent):
                node=self.nodes.get(iid)
                if node and node.selectable:result[iid]=node.path
                if self.tree.item(iid,'open'):visit(iid)
        visit(''); return result
    def clear_values(self):
        for iid,node in self.nodes.items():
            self.tree.set(iid,'value','')
            if node.selectable:self.tree.set(iid,'state','Not reading')
    def toggle_read(self):
        self.read_epoch+=1; self.next_read=0; self.clear_values()
        if self.read_enabled.get() and not self.online:self.read_enabled.set(False); self.status.set('Connect and load PLC definitions before enabling Read.')
    def _collapse(self,_event=None): self.read_epoch+=1; self.clear_values()
    def set_controller(self,name,loader,reader):
        self.generation+=1; self.read_epoch+=1; self.plc_name=name; self.online_loader,self.reader=loader,reader; self.online=False; self.read_enabled.set(False); self.schema=None; self.reset_roots(); self.status.set('Select Connect to populate tags for '+name)
    def pump(self):
        super().pump()
        if self.closed:return
        visible=self.visible_leaves()
        try:
            while True:
                generation,epoch,rows=self.read_results.get_nowait(); self.read_busy=False
                if generation!=self.generation or epoch!=self.read_epoch or not self.read_enabled.get():continue
                for iid,path,value,status in rows:
                    if visible.get(iid)==path:self.tree.set(iid,'value',value); self.tree.set(iid,'state',status)
        except queue.Empty:pass
        if not self.read_enabled.get() or not self.online or not self.reader or self.read_busy or time.monotonic()<self.next_read or not visible:return
        items=list(visible.items()); self.read_offset%=len(items); batch=items[self.read_offset:self.read_offset+self.BATCH_SIZE]; self.read_offset=(self.read_offset+len(batch))%len(items); self.next_read=time.monotonic()+self.INTERVAL; self.read_busy=True; reader,generation,epoch=self.reader,self.generation,self.read_epoch
        def worker():
            rows=[]
            try:
                responses=reader([path for _,path in batch])
                for index,(iid,path) in enumerate(batch):
                    response=responses[index] if index<len(responses) else None; status=getattr(response,'Status','No response'); value=repr(response.Value) if status=='Success' else ''; rows.append((iid,path,value,str(status)))
            except Exception as exc:rows=[(iid,path,'',str(exc)) for iid,path in batch]
            self.read_results.put((generation,epoch,rows))
        threading.Thread(target=worker,daemon=True).start()
    def close(self): self.read_enabled.set(False); self.read_epoch+=1; super().close()
