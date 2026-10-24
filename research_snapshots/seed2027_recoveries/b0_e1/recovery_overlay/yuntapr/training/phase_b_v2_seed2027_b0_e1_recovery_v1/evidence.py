"""Bounded JSONL/SHA audit. No complete event log or parsed-row list in memory."""
import hashlib,json
CHUNK=1024**2
MAX_LINE=2*1024**2

def scan(reader, *, event_log=False, keep=False):
    h=hashlib.sha256();buf=bytearray(CHUNK);tail=bytearray();parts=[];size=lines=total=0;pending=None
    def consume(raw):
        nonlocal lines,total,pending
        if not raw:raise ValueError('EMPTY_AUDIT_LINE')
        row=json.loads(raw);lines+=1;e=row['event']
        if e=='READ_RESERVED':
            if pending is not None:raise ValueError('OVERLAPPING_READS')
            pending=[row['file_key'],row['opened_utc']]
        elif e=='READ_FINISHED':
            if pending!=[row['file_key'],row['opened_utc']]:raise ValueError('UNMATCHED_READ_FINISH')
            pending=None
        if e in ('READ_FINISHED','PUBLIC_METADATA_READ'):
            n=row['bytes']
            if type(n) is not int or n<0:raise ValueError('INVALID_READ_BYTES')
            total+=n
    while n:=reader.readinto(buf):
        size+=n;h.update(memoryview(buf)[:n])
        if keep:
            if size>16*1024**2:raise ValueError('SMALL_METADATA_BOUND')
            parts.append(bytes(memoryview(buf)[:n]))
        if event_log:
            tail.extend(memoryview(buf)[:n]);start=0
            while True:
                end=tail.find(b'\n',start)
                if end<0:break
                if end-start>MAX_LINE:raise ValueError('AUDIT_LINE_BOUND')
                consume(tail[start:end]);start=end+1
            if start:del tail[:start]
            if len(tail)>MAX_LINE:raise ValueError('AUDIT_LINE_BOUND')
    if event_log and tail:raise ValueError('INCOMPLETE_AUDIT_LINE_NO_GUESSING')
    return dict(sha256=h.hexdigest(),bytes=size,lines=lines,content_bytes=total,
                trailing_read_reservation=pending),b''.join(parts) if keep else None
