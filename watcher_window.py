"""Read-only multi-PLC Watcher fed by selections from the Expander."""
from __future__ import annotations
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

class WatcherWindow:
    INTERVAL=0.5; BATCH_SIZE=32
    def __init__(self,parent,sessions,schema_loader):
        self.parent=parent;self.sessions=sessions;self.schema_loader=schema_loader;self.items={};self.nodes={};self.schemas={};self.loaded=set();self.results=queue.Queue();self.busy=set();self.epochs={};self.closed=False;self.read_enabled=tk.BooleanVar(master=parent,value=True)
        self.top=tk.Toplevel(parent);self.top.title('Watcher');self.top.geometry('1180x700');self.top.protocol('WM_DELETE_WINDOW',self.hide)
        bar=ttk.Frame(self.top,padding=6);bar.pack(fill='x');ttk.Checkbutton(bar,text='Live Read',variable=self.read_enabled,command=self._read_toggle).pack(side='left');ttk.Button(bar,text='Remove selected',command=self.remove_selected).pack(side='left',padx=6);ttk.Button(bar,text='Clear Watcher',command=self.clear).pack(side='left');self.status=tk.StringVar(value='Watcher is read-only. Add leaves or branches from Expander.');ttk.Label(bar,textvariable=self.status).pack(side='left',padx=12)
        frame=ttk.Frame(self.top);frame.pack(fill='both',expand=True,padx=6,pady=6);self.tree=ttk.Treeview(frame,columns=('plc','value','type','state'),show='tree headings');self.tree.heading('#0',text='Tag / member');self.tree.column('#0',width=520)
        for key,title,width in [('plc','PLC',110),('value','Value',180),('type','Logix type',150),('state','Status',180)]:self.tree.heading(key,text=title);self.tree.column(key,width=width)
        y=ttk.Scrollbar(frame,orient='vertical',command=self.tree.yview);x=ttk.Scrollbar(frame,orient='horizontal',command=self.tree.xview);self.tree.configure(yscrollcommand=y.set,xscrollcommand=x.set);self.tree.grid(row=0,column=0,sticky='nsew');y.grid(row=0,column=1,sticky='ns');x.grid(row=1,column=0,sticky='ew');frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1);self.tree.bind('<<TreeviewOpen>>',self.expand);self.timer=self.top.after(100,self.pump);self.next_read=0.0
    def show(self):self.top.deiconify();self.top.lift()
    def hide(self):self.top.withdraw()
    def _bump(self,plc):self.epochs[plc]=self.epochs.get(plc,0)+1
    def _read_toggle(self):
        if not self.read_enabled.get():
            for plc in list(self.epochs):self._bump(plc)
            self.busy.clear();self._mark_all('Live Read disabled',clear=True)
        self.next_read=0.0
    def add(self,plc,node):
        key=(plc,node.path)
        if key in self.items:self.tree.selection_set(self.items[key]);self.tree.see(self.items[key]);self.show();return
        iid=self._insert('',plc,node,root=True);self.items[key]=iid;self.show();self.status.set('Added %s::%s'%key)
    def _insert(self,parent,plc,node,root=False):
        label=node.path if root else node.name;dtype=node.dtype+(str(node.dimensions) if node.dimensions else '');iid=self.tree.insert(parent,'end',text=label,values=(plc,'',dtype,'Not reading' if node.selectable else 'Definition'));self.nodes[iid]=(plc,node)
        if not node.leaf and not node.issue and node.access!='None':self.tree.insert(iid,'end',text='Expand...')
        return iid
    def _schema(self,plc):
        if plc not in self.schemas:
            session=self.sessions.get(plc)
            if session is None:raise RuntimeError('PLC %s is no longer configured on gateway'%plc)
            # Expanding cached structure must never silently reconnect an explicitly disconnected session.
            if not session.connected:raise RuntimeError('PLC %s is disconnected. Connect it in Expander first.'%plc)
            schema,_=self.schema_loader(session,False);self.schemas[plc]=schema
        return self.schemas[plc]
    def expand(self,_event=None):
        iid=self.tree.focus()
        if iid in self.loaded or iid not in self.nodes:return
        plc,node=self.nodes[iid]
        try:schema=self._schema(plc)
        except Exception as exc:self.status.set('%s: %s'%(plc,exc));return
        for child in self.tree.get_children(iid):self.tree.delete(child)
        for child in schema.children(node):self._insert(iid,plc,child)
        self.loaded.add(iid)
    def remove_selected(self):
        selection=list(self.tree.selection())
        for iid in selection:self._forget_subtree(iid);self.tree.delete(iid)
        if selection:self.status.set('Removed selected Watcher item.')
    def _forget_subtree(self,iid):
        for child in self.tree.get_children(iid):self._forget_subtree(child)
        pair=self.nodes.pop(iid,None);self.loaded.discard(iid)
        if pair:
            plc,node=pair
            if self.items.get((plc,node.path))==iid:self.items.pop((plc,node.path),None)
    def clear(self):
        for iid in list(self.tree.get_children()):self._forget_subtree(iid);self.tree.delete(iid)
        self.status.set('Watcher cleared.')
    def visible_leaves(self):
        grouped={}
        def visit(parent):
            for iid in self.tree.get_children(parent):
                pair=self.nodes.get(iid)
                if pair:
                    plc,node=pair
                    if node.selectable:grouped.setdefault(plc,[]).append((iid,node.path))
                    if self.tree.item(iid,'open'):visit(iid)
        visit('');return grouped
    def _mark_plc(self,plc,state,clear=False):
        for iid,(item_plc,node) in list(self.nodes.items()):
            if item_plc==plc and node.selectable:
                if clear:self.tree.set(iid,'value','')
                self.tree.set(iid,'state',state)
    def _mark_all(self,state,clear=False):
        for plc in {p for p,_ in self.nodes.values()}:self._mark_plc(plc,state,clear)
    def _sync_disconnects(self):
        for plc in self.visible_leaves():
            session=self.sessions.get(plc)
            if session is None or not session.connected:
                if plc in self.busy:self._bump(plc);self.busy.discard(plc)
                self._mark_plc(plc,'Disconnected',clear=True)
    def _start_reads(self):
        if not self.read_enabled.get() or time.monotonic()<self.next_read:return
        self.next_read=time.monotonic()+self.INTERVAL
        for plc,leaves in self.visible_leaves().items():
            if plc in self.busy or not leaves:continue
            session=self.sessions.get(plc)
            # Explicit GUI disconnect is authoritative. Watcher never reconnects by itself.
            if session is None or not session.connected:self._mark_plc(plc,'Disconnected',clear=True);continue
            batch=leaves[:self.BATCH_SIZE];epoch=self.epochs.get(plc,0);self.busy.add(plc)
            def worker(plc=plc,batch=batch,session=session,epoch=epoch):
                rows=[]
                try:
                    responses=session.read([p for _,p in batch])
                    for index,(iid,path) in enumerate(batch):
                        r=responses[index] if index<len(responses) else None;status=getattr(r,'Status','No response');value=repr(getattr(r,'Value',None)) if status=='Success' else '';rows.append((iid,path,value,str(status)))
                except Exception as exc:rows=[(iid,path,'',str(exc)) for iid,path in batch]
                self.results.put((plc,epoch,rows))
            threading.Thread(target=worker,daemon=True).start()
    def pump(self):
        if self.closed:return
        self._sync_disconnects()
        try:
            while True:
                plc,epoch,rows=self.results.get_nowait();self.busy.discard(plc)
                session=self.sessions.get(plc)
                if epoch!=self.epochs.get(plc,0) or session is None or not session.connected:continue
                for iid,path,value,status in rows:
                    pair=self.nodes.get(iid)
                    if pair and pair[0]==plc and pair[1].path==path:self.tree.set(iid,'value',value);self.tree.set(iid,'state',status)
        except queue.Empty:pass
        self._start_reads();self.timer=self.top.after(100,self.pump)
    def close(self):
        if self.closed:return
        self.closed=True;self.read_enabled.set(False)
        for plc in list(self.epochs):self._bump(plc)
        self.busy.clear()
        try:self.top.after_cancel(self.timer)
        except Exception:pass
        self.nodes.clear();self.items.clear();self.loaded.clear();self.schemas.clear()
        try:self.top.destroy()
        except Exception:pass
