"""Path resolution for source and frozen workstation application."""
import os
import sys
APP_NAME='ControlLogixTool'
_data_dir_cache=None
def is_frozen(): return getattr(sys,'frozen',False)
def app_dir():
    if is_frozen(): return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))
def resource_dir():
    meipass=getattr(sys,'_MEIPASS',None); return meipass if meipass else app_dir()
def resource_path(*parts): return os.path.join(resource_dir(),*parts)
def _writable(folder):
    probe=os.path.join(folder,'.write_probe')
    try:
        os.makedirs(folder,exist_ok=True)
        with open(probe,'w') as f:f.write('x')
        os.remove(probe); return True
    except Exception:return False
def data_dir():
    global _data_dir_cache
    if _data_dir_cache:return _data_dir_cache
    candidates=[app_dir()]; local=os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA')
    if local:candidates.append(os.path.join(local,APP_NAME))
    home=os.path.expanduser('~')
    if home and home!='~':candidates.append(os.path.join(home,'.'+APP_NAME))
    tmp=os.environ.get('TEMP') or os.environ.get('TMP') or '/tmp'; candidates.append(os.path.join(tmp,APP_NAME))
    for folder in candidates:
        if _writable(folder):_data_dir_cache=folder; return folder
    _data_dir_cache=os.getcwd(); return _data_dir_cache
def data_path(filename): return os.path.join(data_dir(),filename)
def describe(): return 'frozen=%s | exe dir=%s | resources=%s | data=%s'%(is_frozen(),app_dir(),resource_dir(),data_dir())
if __name__=='__main__':print(describe())
