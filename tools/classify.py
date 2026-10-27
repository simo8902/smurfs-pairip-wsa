import struct
exec(open('C:/WSA/recon/diffimg.py').read().split("# merge runs")[0].replace("print(","(lambda *a,**k:None)("))
merged=[]
for v, ln in keep:
    if merged and v - (merged[-1][0] + merged[-1][1]) < 16: merged[-1][1] = v + ln - merged[-1][0]
    else: merged.append([v, ln])
def foff(va):
    for sv,so,sz in segs:
        if sv<=va<sv+sz: return so+va-sv
import collections
cls=collections.Counter()
out=[]
for v,ln in merged:
    if v<0x1c80918: continue
    fb=f[foff(v):foff(v)+ln]; pb=A[v:v+ln]
    z=fb.count(0)/ln
    ptr=0
    a0=v-(v%8)
    for q in range(a0,v+ln,8):
        x=struct.unpack_from('<Q',A,q)[0]
        if (x>>40) in (0x7b,0x7a,0x7c,0x7f,0x7e,0x7d) or (x>>56)==0xb4: ptr+=1
    kind='RUNTIME' if (z>0.6 or ptr) else 'DECRYPT'
    cls[kind]+=1
    out.append('%x %d %s zero=%.2f ptr=%d %s'%(v,ln,kind,z,ptr,who(v)[:40]))
print(cls)
print('\n'.join(l for l in out if 'DECRYPT' in l))
print('--- runtime sample'); print('\n'.join([l for l in out if 'RUNTIME' in l][:6]))
