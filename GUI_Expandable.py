"""Full Expander UI using BMX13 gateway transport and cached Logix definitions."""
import os
import tkinter as tk
from tkinter import ttk
from GUI_ControlLogix_MultiPLC import PLCApp, main as launch_application
from watch_tree import WatchBrowser
from live_watch import LiveWatchBrowser
from gateway_schema import load_gateway_schema
from watcher_window import WatcherWindow

class ExpandablePLCApp(PLCApp):
    def __init__(self,root):
        self._closing=False; self.watcher=None
        super().__init__(root)
    def _build_ui(self):
        main_root=self.root;self.tools_window=tk.Toplevel(main_root);self.tools_window.title('PLC tools - reads, writes, object search and diagnostics');self.tools_window.geometry('1240x860');self.tools_window.protocol('WM_DELETE_WINDOW',self.tools_window.withdraw);self.tools_window.withdraw();self.root=self.tools_window
        try:super()._build_ui()
        finally:self.root=main_root
        self.root.title('PLC Gateway Expander');self.root.geometry('1240x760');self.var_browser_plc=tk.StringVar(value=self.var_taglist_plc.get())
        bar=ttk.Frame(self.root,padding=6);bar.pack(fill='x');ttk.Label(bar,text='PLC:').pack(side='left');self.plc_dropdown=ttk.Combobox(bar,textvariable=self.var_browser_plc,values=self.sessions.names(),state='readonly',width=20);self.plc_dropdown.pack(side='left',padx=6);self.plc_dropdown.bind('<<ComboboxSelected>>',self._browser_plc_changed)
        ttk.Button(bar,text='Connect',command=self.connect_browser).pack(side='left');ttk.Button(bar,text='Disconnect',command=self.disconnect_browser).pack(side='left')
        ttk.Button(bar,text='Open Watcher',command=self.open_watcher).pack(side='left',padx=8)
        self.browser=LiveWatchBrowser(self.root,self.var_browser_plc.get(),self.add_browser_leaf,online_loader=lambda force:None,embedded=True,add_watch=self.add_to_watcher)
        ttk.Checkbutton(bar,text='Read',variable=self.browser.read_enabled,command=self.browser.toggle_read).pack(side='left',padx=12);ttk.Button(bar,text='PLC tools / Object Search...',command=self.show_tools).pack(side='left');ttk.Button(bar,text='Write selected...',command=self.write_browser_leaf).pack(side='left');ttk.Button(bar,text='Diagnostics...',command=self.show_diagnostics).pack(side='left');ttk.Label(self.root,textvariable=self.var_status,anchor='w').pack(fill='x');self._browser_plc_changed()
    def show_tools(self):self.tools_window.deiconify();self.tools_window.lift()
    def open_watcher(self):
        if self.watcher is None or self.watcher.closed:self.watcher=WatcherWindow(self.root,self.sessions,self.discover_session)
        self.watcher.show()
    def add_to_watcher(self,plc_name,node):
        self.open_watcher();self.watcher.add(plc_name,node)
    def _browser_plc_changed(self,_event=None):
        name=self.var_browser_plc.get();session=self.sessions.get(name);self.var_taglist_plc.set(name);self.var_default_plc.set(name);self.var_obj_plc.set(name);self.var_write_plc.set(name);self._populate_taglist_combo();self.browser.set_controller(name,lambda force:self.discover_session(session,force),session.read if session else None)
        if session and session.connected:self.browser.load_online()
    def connect_browser(self):
        session=self.sessions.get(self.var_browser_plc.get())
        if session is None or session.connecting:return
        if session.connected:self.browser.load_online();return
        def connect_and_load(force):
            with session.lock:
                if self._closing:raise RuntimeError('Application is closing')
                ok,message=session.connect(status_cb=self._status)
                if not ok:raise RuntimeError(message)
                return self.discover_session(session,force)
        self.browser.online_loader=connect_and_load;self.browser.load_online();self.browser.online_loader=lambda force:self.discover_session(session,force)
    def disconnect_browser(self):self._disconnect_one(self.var_browser_plc.get());self._refresh_conn_table()
    def _disconnect_one(self,name):
        if name==self.var_browser_plc.get():
            session=self.sessions.get(name);self.browser.set_controller(name,lambda force:self.discover_session(session,force),session.read if session else None)
        super()._disconnect_one(name)
    def write_browser_leaf(self):
        node=self.browser.selected()
        if not node or not node.selectable or node.access=='Read Only':self.browser.status.set('Select a writable scalar member first.');return
        self.var_write_plc.set(self.browser.plc_name);self.var_write_tag.set(node.path);self.show_tools()
    def on_close(self):
        self._closing=True;self.browser.close()
        if self.watcher is not None and not self.watcher.closed:self.watcher.close()
        super().on_close()
    def open_tag_browser(self):
        name=self.var_taglist_plc.get();session=self.sessions.get(name);browser=WatchBrowser(self.root,name,self.add_browser_leaf,online_loader=lambda force:self.discover_session(session,force),add_watch=self.add_to_watcher)
        if session and session.connected:browser.load_online()
    def discover_session(self,session,refresh=False):
        if session is None:raise RuntimeError('Select a configured PLC first')
        with session.lock:
            if not session.connected:raise RuntimeError('Connect this PLC through BMX13 first')
            schema,source=load_gateway_schema(session.client,session.name,refresh=refresh);entries=[]
            for node in schema.roots:
                scope=node.path.split('.',1)[0] if node.path.startswith('Program:') else 'Controller';label='%s    [%s]    (%s)'%(node.path,node.dtype,scope);entries.append((label,node.path))
            session.all_tags=[label for label,_ in entries];session.raw_tag_names=[path for _,path in entries];session.tag_display_map=dict(entries);self.ui_queue.put(('taglist',session.name));return schema,source
    def _do_connect(self,session):
        session.clear_tag_list();ok,message=session.connect(status_cb=self._status);self.ui_queue.put(('conn',None))
        if not ok:self._error('[%s] connection failed: %s'%(session.name,message));return
        try:_,source=self.discover_session(session);self._status('[%s] %s'%(session.name,source))
        except Exception as exc:self._status('[%s] connected; definitions unavailable: %s'%(session.name,exc))
        self.ui_queue.put(('conn',None))
    def _do_load_tags(self,session):
        try:_,source=self.discover_session(session,refresh=True);self._status('[%s] %s'%(session.name,source))
        except Exception as exc:self._error(str(exc))
    def add_browser_leaf(self,plc_name,path):
        line='%s::%s'%(plc_name,path);current=self.txt_tags.get('1.0',tk.END).strip()
        if line not in [x.strip() for x in current.splitlines()]:self.txt_tags.insert(tk.END,('\n' if current else '')+line)
        self.show_tools();self._status_direct('Added %s from cached definitions. Use Read Once to validate.'%line)
def main():launch_application(ExpandablePLCApp)
if __name__=='__main__':main()
