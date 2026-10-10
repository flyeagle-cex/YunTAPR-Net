"""Read-only Windows handles with no write/delete sharing or link following.

Directory handles are retained to prevent parent rename/reparse replacement.
GetFileInformationByHandle binds metadata to the opened object; no resolve/stat.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import os
import msvcrt

K=ctypes.WinDLL('kernel32',use_last_error=True)
K.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
K.CreateFileW.restype=wintypes.HANDLE
K.CloseHandle.argtypes=[wintypes.HANDLE];K.CloseHandle.restype=wintypes.BOOL
K.GetFinalPathNameByHandleW.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD]
K.GetFinalPathNameByHandleW.restype=wintypes.DWORD

class Information(ctypes.Structure):
    _fields_=[('attributes',wintypes.DWORD),('created',wintypes.FILETIME),('accessed',wintypes.FILETIME),
              ('written',wintypes.FILETIME),('volume',wintypes.DWORD),('size_hi',wintypes.DWORD),
              ('size_lo',wintypes.DWORD),('links',wintypes.DWORD),('index_hi',wintypes.DWORD),('index_lo',wintypes.DWORD)]
K.GetFileInformationByHandle.argtypes=[wintypes.HANDLE,ctypes.POINTER(Information)]
K.GetFileInformationByHandle.restype=wintypes.BOOL

def info(handle):
    v=Information()
    if not K.GetFileInformationByHandle(handle,ctypes.byref(v)):raise ctypes.WinError(ctypes.get_last_error())
    return dict(attributes=int(v.attributes),volume=int(v.volume),file_index=(int(v.index_hi)<<32)|int(v.index_lo),
                size=(int(v.size_hi)<<32)|int(v.size_lo),mtime_100ns=(int(v.written.dwHighDateTime)<<32)|int(v.written.dwLowDateTime))

def final_name(handle):
    buf=ctypes.create_unicode_buffer(32768)
    n=K.GetFinalPathNameByHandleW(handle,buf,len(buf),0)
    if not n or n>=len(buf):raise ctypes.WinError(ctypes.get_last_error())
    value=buf.value
    return value[4:] if value.startswith('\\\\?\\') else value

class ReadHandle:
    def __init__(self,path,*,directory=False,payload=False):
        # The caller MUST lexically authenticate scope BEFORE invoking this API.
        flags=0x00200000 | (0x02000000 if directory else 0x08000000) # OPEN_REPARSE_POINT/BACKUP/SEQUENTIAL
        access=0x80000000 if payload else 0x80 # GENERIC_READ or FILE_READ_ATTRIBUTES
        handle=K.CreateFileW(path,access,1,None,3,flags,None) # SHARE_READ, OPEN_EXISTING
        if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        self.handle,self.reader=handle,None
        try:
            self.before=info(handle)
            if self.before['attributes']&0x400:raise PermissionError('Reparse point rejected without following target')
            if bool(self.before['attributes']&0x10)!=directory:raise ValueError('Expected directory/regular payload kind')
            self.final_path=final_name(handle)
            if payload:
                fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
                self.reader=os.fdopen(fd,'rb',buffering=0)
        except BaseException:
            self.close();raise
    def readinto(self,buffer):return self.reader.readinto(buffer)
    def snapshot(self):return info(self.handle)
    def close(self):
        if self.reader is not None:
            self.reader.close();self.reader=None;self.handle=None
        elif getattr(self,'handle',None) is not None:
            K.CloseHandle(self.handle);self.handle=None
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
