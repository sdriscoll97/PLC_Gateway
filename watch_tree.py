"""L5X-backed expandable browser. Import/expansion never performs PLC I/O."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tag_schema import Schema
import app_paths


class WatchBrowser:
    def __init__(self, parent, plc_name, add_leaf, online_loader=None, embedded=False):
        self.plc_name, self.add_leaf = plc_name, add_leaf
        self.online_loader = online_loader
        self.schema = None
        self.nodes, self.loaded = {}, set()
        self.results = queue.Queue()
        self.generation = 0
        self.closed = False
        self.offset = 0
        self.top = ttk.Frame(parent) if embedded else tk.Toplevel(parent)
        if embedded:
            self.top.pack(fill='both', expand=True)
        else:
            self.top.title('Expandable browser - ' + plc_name)
            self.top.geometry('950x600')
            self.top.protocol('WM_DELETE_WINDOW', self.close)
        toolbar = ttk.Frame(self.top); toolbar.pack(fill='x')
        ttk.Button(toolbar, text='Load L5X...', command=self.choose_file).pack(side='left')
        ttk.Button(toolbar, text='Load offline example', command=self.load_example).pack(side='left')
        if online_loader:
            ttk.Button(toolbar, text='Use PLC definitions', command=self.load_online).pack(side='left')
            ttk.Button(toolbar, text='Refresh Definitions', command=lambda: self.load_online(True)).pack(side='left')
        self.status = tk.StringVar(value='Load an approved L5X export. No live schema validation.')
        ttk.Label(self.top, textvariable=self.status, wraplength=900).pack(fill='x')
        filters = ttk.Frame(self.top); filters.pack(fill='x')
        ttk.Label(filters, text='Root tag filter:').pack(side='left')
        self.filter = tk.StringVar(); search_entry = ttk.Entry(filters, textvariable=self.filter)
        search_entry.pack(side='left', fill='x', expand=True)
        search_entry.bind('<Return>', lambda event: self.reset_roots())
        ttk.Button(filters, text='Search', command=self.reset_roots).pack(side='left')
        ttk.Button(filters, text='Previous roots', command=lambda: self.page(-32)).pack(side='left')
        ttk.Button(filters, text='Next roots', command=lambda: self.page(32)).pack(side='left')
        frame = ttk.Frame(self.top); frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(frame, columns=('type','access','state'), show='tree headings')
        self.tree.heading('#0', text='Tag / member'); self.tree.column('#0', width=420)
        for key,title in [('type','Logix type'),('access','Definition access'),('state','Status')]:
            self.tree.heading(key,text=title); self.tree.column(key,width=140)
        self.tree.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(frame,command=self.tree.yview); scroll.pack(side='right',fill='y'); self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<<TreeviewOpen>>',self.expand); self.tree.bind('<Double-1>',self.double_click)
        actions=ttk.Frame(self.top); actions.pack(fill='x')
        ttk.Button(actions,text='Add selected leaf to read list',command=self.add_selected).pack(side='left')
        ttk.Button(actions,text='Copy selected path',command=self.copy_path).pack(side='left')
        ttk.Label(actions,text='Select an accessible scalar member.').pack(side='left')
        self.timer=self.top.after(100,self.pump)
    def choose_file(self):
        path=filedialog.askopenfilename(parent=self.top,filetypes=[('Logix XML export','*.L5X *.l5x')])
        if path:self.load(path)
    def load_online(self,refresh=False):
        if not self.online_loader:return
        self.generation+=1; generation=self.generation; loader=self.online_loader; self.schema=None; self.reset_roots(); self.status.set('Checking controller identity and loading definitions...')
        def worker():
            try: result=loader(refresh)
            except Exception as exc: result=str(exc)
            self.results.put((generation,'',False,result))
        threading.Thread(target=worker,daemon=True).start()
    def load_example(self): self.load(app_paths.resource_path('examples','watch-demo.L5X'),example=True)
    def load(self,path,example=False):
        self.generation+=1; generation=self.generation; self.schema=None; self.reset_roots(); self.status.set('Loading schema...')
        def worker():
            try: result=Schema.from_file(path)
            except Exception as exc: result=str(exc)
            self.results.put((generation,str(path),example,result))
        threading.Thread(target=worker,daemon=True).start()
    def pump(self):
        if self.closed:return
        try:
            while True:
                generation,path,example,result=self.results.get_nowait()
                if generation!=self.generation:continue
                if isinstance(result,tuple):
                    self.schema,source=result; self.status.set(source+' | Identity checked; program edits require Refresh Definitions.'); self.reset_roots(); continue
                if isinstance(result,Schema):
                    self.schema=result; self.status.set(('SYNTHETIC EXAMPLE - ' if example else 'EXPORT ONLY - ')+Path(path).name+' | SHA256 '+result.digest[:12]+' | Not validated against a live controller; values may differ.'); self.reset_roots()
                else:self.status.set('Import failed: '+result)
        except queue.Empty:pass
        self.timer=self.top.after(100,self.pump)
    def reset_roots(self): self.offset=0; self.render_roots()
    def page(self,delta):
        if not self.schema:return
        total=len(self.filtered_roots()); self.offset=max(0,min(self.offset+delta,max(0,((total-1)//32)*32))); self.render_roots()
    def filtered_roots(self):
        needle=self.filter.get().casefold(); return [n for n in self.schema.roots if needle in n.path.casefold()]
    def render_roots(self):
        for iid in self.tree.get_children():self.tree.delete(iid)
        self.nodes.clear(); self.loaded.clear()
        if self.schema:
            for node in self.filtered_roots()[self.offset:self.offset+32]:self.insert('',self.schema.checked(node),root=True)
    def insert(self,parent,node,root=False):
        status=node.issue or ('External access denied' if node.access=='None' else 'Definition; not read'); label=node.path if root else node.name; dtype=node.dtype+(str(node.dimensions) if node.dimensions else '')
        iid=self.tree.insert(parent,'end',text=label,values=(dtype,node.access,status)); self.nodes[iid]=node
        if not node.leaf and not node.issue and node.access!='None':self.tree.insert(iid,'end',text='Loading...')
        return iid
    def expand(self,_event=None):
        iid=self.tree.focus()
        if iid in self.loaded or iid not in self.nodes or not self.schema:return
        for child in self.tree.get_children(iid):self.tree.delete(child)
        for child in self.schema.children(self.nodes[iid]):self.insert(iid,child)
        self.loaded.add(iid)
    def selected(self):
        selection=self.tree.selection(); return self.nodes.get(selection[0]) if selection else None
    def add_selected(self):
        node=self.selected()
        if node and node.selectable:self.add_leaf(self.plc_name,node.path)
        else:messagebox.showinfo('Select a leaf','Choose a scalar member with no known access restriction.',parent=self.top)
    def double_click(self,event):
        if 'indicator' in self.tree.identify_element(event.x,event.y):return
        iid=self.tree.identify_row(event.y); node=self.nodes.get(iid)
        if node and node.selectable:self.tree.selection_set(iid); self.add_selected(); return 'break'
    def copy_path(self):
        node=self.selected()
        if node and not node.span:self.top.clipboard_clear(); self.top.clipboard_append(self.plc_name+'::'+node.path)
    def close(self):
        self.closed=True; self.generation+=1; self.top.after_cancel(self.timer); self.top.destroy()

if __name__=='__main__':
    root=tk.Tk(); root.withdraw(); browser=WatchBrowser(root,'OFFLINE',lambda plc,path:print(plc+'::'+path)); browser.top.protocol('WM_DELETE_WINDOW',lambda:(browser.close(),root.destroy())); root.mainloop()
