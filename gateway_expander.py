"""Gateway-native expandable Logix browser.

The workstation talks only HTTP to PLC_Gateway. It contains no PLC addresses and
performs no direct EtherNet/IP/CIP communication.
"""
from __future__ import annotations
import argparse, queue, threading, tkinter as tk
from dataclasses import dataclass
from tkinter import ttk, messagebox
from gateway_client import GatewayClient, GatewayError

@dataclass
class Node:
    name: str
    path: str
    datatype: str = "Unknown"
    dimensions: tuple = ()
    access: str = "Unknown"
    structured: bool = False
    expandable: bool = False
    kind: str = "member"

    @property
    def selectable(self):
        return not self.expandable and not self.dimensions and self.access != "None"


def node_from(raw):
    return Node(raw.get('name',raw.get('path','')), raw.get('path',''), raw.get('datatype','Unknown'),
                tuple(raw.get('dimensions') or ()), raw.get('access','Unknown'),
                bool(raw.get('structured')), bool(raw.get('expandable')), raw.get('kind','member'))


class GatewayExpander:
    PAGE = 100
    READ_INTERVAL_MS = 750

    def __init__(self, root, client, initial_plc=None):
        self.root, self.client = root, client
        self.nodes, self.loaded = {}, set()
        self.results = queue.Queue()
        self.reading = False
        self.generation = 0
        self.root.title('PLC Gateway Expander - read-only validation')
        self.root.geometry('1180x760')
        health = client.health()
        if not health.get('read_only',False):
            raise RuntimeError('Gateway is not read-only. Validation client refuses to start.')
        plcs = health.get('configured_plcs') or []
        if not plcs: raise RuntimeError('Gateway has no configured PLCs')
        self.plc = tk.StringVar(value=initial_plc if initial_plc in plcs else plcs[0])
        self.filter = tk.StringVar(); self.status = tk.StringVar(value='Gateway connected; read-only mode confirmed.')
        self.live = tk.BooleanVar(value=False)
        bar=ttk.Frame(root,padding=6); bar.pack(fill='x')
        ttk.Label(bar,text='PLC:').pack(side='left')
        box=ttk.Combobox(bar,textvariable=self.plc,values=plcs,state='readonly',width=18); box.pack(side='left',padx=6)
        box.bind('<<ComboboxSelected>>',lambda _e:self.load_roots())
        ttk.Button(bar,text='Load tags',command=self.load_roots).pack(side='left')
        ttk.Checkbutton(bar,text='Read visible leaves',variable=self.live,command=self.toggle_live).pack(side='left',padx=12)
        ttk.Label(root,textvariable=self.status,anchor='w').pack(fill='x',padx=6)
        search=ttk.Frame(root,padding=(6,2)); search.pack(fill='x')
        ttk.Label(search,text='Root filter:').pack(side='left')
        ent=ttk.Entry(search,textvariable=self.filter); ent.pack(side='left',fill='x',expand=True,padx=6)
        ent.bind('<Return>',lambda _e:self.load_roots())
        ttk.Button(search,text='Search',command=self.load_roots).pack(side='left')
        frame=ttk.Frame(root); frame.pack(fill='both',expand=True,padx=6,pady=4)
        self.tree=ttk.Treeview(frame,columns=('value','type','access','state'),show='tree headings')
        self.tree.heading('#0',text='Tag / member'); self.tree.column('#0',width=470)
        for key,title,width in [('value','Value',170),('type','Logix type',180),('access','Access',100),('state','Status',170)]:
            self.tree.heading(key,text=title); self.tree.column(key,width=width)
        self.tree.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(frame,command=self.tree.yview); scroll.pack(side='right',fill='y'); self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<<TreeviewOpen>>',self.expand)
        actions=ttk.Frame(root,padding=6); actions.pack(fill='x')
        ttk.Button(actions,text='Read selected once',command=self.read_selected).pack(side='left')
        ttk.Button(actions,text='Copy selected path',command=self.copy_selected).pack(side='left',padx=6)
        ttk.Label(actions,text='This validation client has no write controls.').pack(side='left',padx=12)
        self.root.after(100,self.pump); self.root.after(self.READ_INTERVAL_MS,self.live_tick)
        self.load_roots()

    def _worker(self, fn, callback):
        generation=self.generation
        def run():
            try: result=fn()
            except Exception as exc: result=exc
            self.results.put((generation,callback,result))
        threading.Thread(target=run,daemon=True).start()

    def load_roots(self):
        self.generation += 1; self.live.set(False); self.nodes.clear(); self.loaded.clear()
        for iid in self.tree.get_children(): self.tree.delete(iid)
        plc,q=self.plc.get(),self.filter.get().strip(); self.status.set('Loading controller definitions through gateway...')
        self._worker(lambda:self.client.schema(plc,q=q,limit=500),self._roots_ready)

    def _roots_ready(self,payload):
        for raw in payload.get('roots',[]): self.insert('',node_from(raw),root=True)
        self.status.set(f"{len(payload.get('roots',[]))} root tags loaded through gateway; no direct PLC connection.")

    def insert(self,parent,node,root=False):
        label=node.path if root else node.name
        dtype=node.datatype + (str(node.dimensions) if node.dimensions else '')
        iid=self.tree.insert(parent,'end',text=label,values=('',dtype,node.access,'Definition; not read'))
        self.nodes[iid]=node
        if node.expandable: self.tree.insert(iid,'end',text='Expand to load...')
        return iid

    def expand(self,_event=None):
        iid=self.tree.focus()
        if iid in self.loaded or iid not in self.nodes: return
        node=self.nodes[iid]
        for child in self.tree.get_children(iid): self.tree.delete(child)
        self.tree.insert(iid,'end',text='Loading...')
        plc=self.plc.get(); self.status.set('Expanding '+node.path+' through gateway...')
        self._worker(lambda:self.client.expand(plc,node.path,limit=self.PAGE),lambda p:self._expanded(iid,node,p))

    def _expanded(self,iid,node,payload):
        for child in self.tree.get_children(iid): self.tree.delete(child)
        for raw in payload.get('children',[]): self.insert(iid,node_from(raw))
        total=int(payload.get('total',0)); shown=len(payload.get('children',[])); self.loaded.add(iid)
        suffix=f' Showing first {shown} of {total}; array paging UI follows after validation.' if total>shown else ''
        self.status.set('Expanded '+node.path+'.'+suffix)

    def selected(self):
        sel=self.tree.selection(); return (sel[0],self.nodes.get(sel[0])) if sel else (None,None)

    def read_selected(self):
        iid,node=self.selected()
        if not node or not node.selectable:
            messagebox.showinfo('Select a leaf','Choose a scalar leaf first.',parent=self.root); return
        plc=self.plc.get(); self.tree.set(iid,'state','Reading...')
        self._worker(lambda:self.client.read(plc,node.path),lambda p:self._read_ready(iid,node.path,p))

    def _read_ready(self,iid,path,payload):
        if iid not in self.nodes or self.nodes[iid].path != path: return
        self.tree.set(iid,'value',repr(payload.get('value')))
        self.tree.set(iid,'state',str(payload.get('status','Success' if payload.get('success') else 'Error')))

    def copy_selected(self):
        _iid,node=self.selected()
        if node:
            self.root.clipboard_clear(); self.root.clipboard_append(self.plc.get()+'::'+node.path)

    def toggle_live(self):
        self.status.set('Live read enabled for visible scalar leaves.' if self.live.get() else 'Live read disabled.')

    def visible_leaves(self):
        result=[]
        def visit(parent):
            for iid in self.tree.get_children(parent):
                node=self.nodes.get(iid)
                if node and node.selectable: result.append((iid,node.path))
                if self.tree.item(iid,'open'): visit(iid)
        visit(''); return result[:32]

    def live_tick(self):
        if self.live.get() and not self.reading:
            leaves=self.visible_leaves()
            if leaves:
                self.reading=True; plc=self.plc.get(); paths=[p for _,p in leaves]
                self._worker(lambda:self.client.read_batch(plc,paths),lambda p:self._batch_ready(leaves,p))
        self.root.after(self.READ_INTERVAL_MS,self.live_tick)

    def _batch_ready(self,leaves,payload):
        try:
            rows=payload.get('results',payload.get('items',[]))
            for (iid,path),row in zip(leaves,rows):
                if iid in self.nodes and self.nodes[iid].path==path:
                    self.tree.set(iid,'value',repr(row.get('value')))
                    self.tree.set(iid,'state',str(row.get('status','')))
        finally: self.reading=False

    def pump(self):
        try:
            while True:
                generation,callback,result=self.results.get_nowait()
                if generation != self.generation: continue
                if isinstance(result,Exception):
                    self.reading=False; self.status.set('Gateway error: '+str(result)); continue
                try: callback(result)
                except Exception as exc: self.reading=False; self.status.set('UI result error: '+str(exc))
        except queue.Empty: pass
        self.root.after(100,self.pump)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--gateway',default='http://127.0.0.1:8443'); parser.add_argument('--plc',default='PLC_6')
    args=parser.parse_args(); root=tk.Tk()
    try: GatewayExpander(root,GatewayClient(args.gateway),args.plc)
    except Exception as exc:
        messagebox.showerror('PLC Gateway Expander',str(exc),parent=root); root.destroy(); return
    root.mainloop()

if __name__=='__main__': main()
