"""Cached gateway/L5X schema model with bounded local expansion. No PLC I/O."""
from dataclasses import dataclass, replace
import hashlib, math, re, xml.etree.ElementTree as ET
ATOMIC=frozenset('BOOL SINT INT DINT LINT USINT UINT UDINT ULINT REAL LREAL STRING'.split()); PAGE=32; MAX_BYTES=16*1024*1024; MAX_DEPTH=32
@dataclass(frozen=True)
class Node:
    name:str; path:str; dtype:str; dimensions:tuple=(); access:str='Unknown'; ancestors:tuple=(); issue:str=''; span:tuple=()
    @property
    def leaf(self): return not (self.dimensions or self.span or self.issue) and self.dtype in ATOMIC
    @property
    def selectable(self): return self.leaf and self.access!='None'
def dimensions(raw):
    if not raw or raw.strip()=='0': return ()
    raw=raw.strip()
    if not re.fullmatch(r'\d+(?:(?:\s*,\s*|\s+)\d+)*',raw): raise ValueError('Invalid array dimensions: '+raw)
    parts=re.split(r'[,\s]+',raw)
    if len(parts)>3 or any(not p.isdigit() or int(p)<1 for p in parts): raise ValueError('Invalid array dimensions: '+raw)
    dims=tuple(map(int,parts))
    if math.prod(dims)>2**31-1: raise ValueError('Array dimensions exceed supported limit')
    return dims
def effective_access(parent,child):
    if 'None' in (parent,child): return 'None'
    if 'Read Only' in (parent,child): return 'Read Only'
    return child if child!='Unknown' else parent
class Schema:
    def __init__(self,roots,types,digest): self.roots,self.types,self.digest=roots,types,digest
    @classmethod
    def from_file(cls,filename):
        with open(filename,'rb') as stream:data=stream.read(MAX_BYTES+1)
        return cls.from_bytes(data)
    @classmethod
    def from_bytes(cls,data):
        if len(data)>MAX_BYTES: raise ValueError('L5X exceeds 16 MiB import limit')
        text=data.decode('utf-8-sig')
        if '\x00' in text or re.search(r'<!\s*(DOCTYPE|ENTITY)',text,re.I): raise ValueError('DTD/entities and non-UTF-8 XML are not supported')
        root=ET.fromstring(text)
        if root.tag!='RSLogix5000Content': raise ValueError('Expected an RSLogix5000Content L5X export')
        controller=root.find('Controller')
        if controller is None: raise ValueError('Export has no Controller section')
        def make(element,path):
            name=element.get('Name','')
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name): raise ValueError('Unsupported or missing symbolic name: '+name)
            issue='Alias resolution is not supported in this version' if element.get('TagType')=='Alias' or element.get('AliasFor') else ''
            dtype=element.get('DataType',''); dtype='BOOL' if element.tag=='Member' and dtype=='BIT' else dtype
            return Node(name,path or name,dtype,dimensions(element.get('Dimensions','')),element.get('ExternalAccess','Unknown'),issue=issue)
        types={}
        for dtype in controller.findall('./DataTypes/DataType'):
            name=dtype.get('Name'); members=[]
            for member in dtype.findall('./Members/Member'):
                if member.get('Hidden','').lower()=='true': continue
                members.append(make(member,''))
            types[name]=tuple(members)
        roots=[make(t,'') for t in controller.findall('./Tags/Tag')]
        for program in controller.findall('./Programs/Program'):
            name=program.get('Name',''); roots.extend(make(t,'Program:'+name+'.'+t.get('Name','')) for t in program.findall('./Tags/Tag'))
        return cls(tuple(roots),types,hashlib.sha256(data).hexdigest())
    def checked(self,node):
        if node.issue:return node
        if len(node.ancestors)>=MAX_DEPTH or (not node.dimensions and node.dtype in node.ancestors):return replace(node,issue='Cyclic type or depth limit')
        if node.dtype not in ATOMIC and node.dtype not in self.types:return replace(node,issue='Missing/unsupported type (including AOI or built-in)')
        if node.dtype in self.types and not self.types[node.dtype]:return replace(node,issue='No exported visible members')
        return node
    def children(self,node):
        node=self.checked(node)
        if node.issue or node.access=='None' or node.leaf:return ()
        if node.dimensions:
            start,end=node.span or (0,math.prod(node.dimensions))
            if end-start>PAGE:
                size=PAGE
                while math.ceil((end-start)/size)>PAGE:size*=PAGE
                return tuple(replace(node,name='Elements %d–%d'%(i,min(i+size,end)-1),span=(i,min(i+size,end))) for i in range(start,end,size))
            result=[]
            for flat in range(start,end):
                remainder,indices=flat,[]
                for dim in reversed(node.dimensions):indices.append(remainder%dim);remainder//=dim
                suffix='['+','.join(map(str,reversed(indices)))+']';result.append(replace(node,name=suffix,path=node.path+suffix,dimensions=(),span=()))
            return tuple(result)
        return tuple(self.checked(replace(member,path=node.path+'.'+member.name,access=effective_access(node.access,member.access),ancestors=node.ancestors+(node.dtype,))) for member in self.types.get(node.dtype,()))
