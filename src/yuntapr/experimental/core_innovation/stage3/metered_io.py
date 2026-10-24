"""Serial manifest-bound logical source-byte meter; originals are read-only."""
from pathlib import Path
import builtins,hashlib,io,json,os,sqlite3,sys


def path_key(path):return os.path.normcase(os.path.abspath(os.fsdecode(path)))


class IdentityConflict(RuntimeError):pass


class MeasuredReader:
    def __init__(self,owner,path,handle):
        self.owner=owner;self.path=path;self.handle=handle;self.n=0;self.hash=hashlib.sha256()
    def __enter__(self):return self
    def __exit__(self,exc_type,exc,tb):
        close_error=receipt_error=None
        try:self.handle.close()
        except OSError as error:close_error=error
        try:self.owner.finish(self.path,self.n,self.hash.hexdigest())
        except IdentityConflict as error:receipt_error=error
        # A partial digest cannot establish changed source contents. Preserve
        # the original I/O error while still recording the uncertain read.
        if exc is not None:
            for error in (close_error,receipt_error):
                if error is not None:exc.add_note('Read finalization: '+str(error))
            return False
        if close_error is not None:raise close_error
        if receipt_error is not None:raise receipt_error
    def read(self,size=-1):
        expected=self.owner.files[self.path]['bytes'];remaining=expected-self.n
        if remaining<=0:return b''
        raw=self.handle.read(remaining if size<0 else min(size,remaining));self.n+=len(raw);self.hash.update(raw)
        self.owner.record(self.path,self.n)
        return raw


class SourceMeter:
    """Every source open must pass the meter and have a precommitted job intent.

    Counters describe bytes delivered to Python readers, not OS disk-sector I/O.
    A crash between delivery and counter commit remains covered by reservations.
    """
    def __init__(self,db,files,*,max_files,max_bytes):
        self.db=db;self.files={path_key(k):v for k,v in files.items()};self.max_files=max_files;self.max_bytes=max_bytes
        self.active=set();self.opening=False;self.original_open=io.open;self.installed=False
        self.db.execute('CREATE TABLE IF NOT EXISTS file_io (path TEXT PRIMARY KEY,state TEXT,expected_bytes INTEGER,actual_bytes INTEGER,sha256 TEXT,prior_sha_available INTEGER)');self.db.commit()
    def install(self):
        def audit(event,args):
            if not self.installed:return
            if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
                p=path_key(args[0]);text=p.lower()
                if p in self.files or text.endswith(('.nc','.hgt','.hgt.zip','.hdf5','.h5')):
                    if not self.opening or p not in self.active:raise PermissionError('Raw source open outside active manifest-bound meter')
        sys.addaudithook(audit);io.open=self.open;self.installed=True
    def uninstall(self):
        io.open=self.original_open;self.installed=False
    def open(self,file,mode='r',*args,**kwargs):
        if not isinstance(file,(str,bytes,os.PathLike)):return self.original_open(file,mode,*args,**kwargs)
        p=path_key(file)
        if p not in self.files:return self.original_open(file,mode,*args,**kwargs)
        if mode!='rb' or p not in self.active:raise PermissionError('Only active read-only source jobs allowed')
        job=self.db.execute('SELECT state FROM jobs WHERE id=?',(self.files[p]['job_id'],)).fetchone()
        if not job or job[0]!='PENDING':raise PermissionError('Job intent must be committed before source open')
        if self.db.execute('SELECT 1 FROM file_io WHERE path=?',(p,)).fetchone():raise RuntimeError('Completed or uncertain source cannot be opened again')
        used=self.db.execute('SELECT COUNT(*),COALESCE(SUM(expected_bytes),0) FROM file_io').fetchone()
        f=self.files[p]
        if used[0]+1>self.max_files or used[1]+f['bytes']>self.max_bytes:raise PermissionError('Cumulative file/byte cap exhausted')
        if os.stat(file).st_size!=f['bytes']:raise IdentityConflict('Source size differs from approved inventory')
        with self.db:self.db.execute('INSERT INTO file_io VALUES (?,?,?,?,?,?)',(p,'INTENT',f['bytes'],0,None,int(f.get('sha') is not None)))
        self.opening=True
        try:handle=self.original_open(file,mode,*args,**kwargs)
        finally:self.opening=False
        return MeasuredReader(self,p,handle)
    def record(self,path,count):
        with self.db:self.db.execute('UPDATE file_io SET actual_bytes=? WHERE path=?',(count,path))
    def finish(self,path,count,sha):
        expected=self.files[path];state='READ_COMPLETE' if count==expected['bytes'] else 'PARTIAL_UNCERTAIN'
        if state=='READ_COMPLETE' and expected.get('sha') is not None and sha!=expected['sha']:state='SHA_CONFLICT'
        with self.db:self.db.execute('UPDATE file_io SET state=?,sha256=? WHERE path=?',(state,sha,path))
        if state!='READ_COMPLETE':raise IdentityConflict(state)
    def receipt(self,path):
        p=path_key(path);row=self.db.execute('SELECT state,actual_bytes,sha256,prior_sha_available FROM file_io WHERE path=?',(p,)).fetchone()
        if not row or row[0]!='READ_COMPLETE':raise IdentityConflict('Source not completely measured')
        return dict(state=row[0],bytes=row[1],sha256=row[2],prior_sha_available=bool(row[3]))
    def totals(self):
        row=self.db.execute('SELECT COUNT(*),COALESCE(SUM(actual_bytes),0),COALESCE(SUM(expected_bytes),0) FROM file_io').fetchone()
        return dict(opened_files=row[0],delivered_bytes=row[1],reserved_bytes=row[2],states=dict(self.db.execute('SELECT state,COUNT(*) FROM file_io GROUP BY state')))
