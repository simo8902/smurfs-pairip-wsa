import struct,collections
D='C:/WSA/recon/phonedump/'
known=set()
for l in open('C:/WSA/recon/relaplt.txt'):
    p=l.split()
    if p:
        try: known.add(int(p[0],16))
        except: pass
maps=[]
for l in open(D+'maps.txt'):
    p=l.split()
    a,b=[int(x,16) for x in p[0].split('-')]
    maps.append((a,b,int(p[2],16),p[5] if len(p)>5 else ''))
base=[a for a,b,o,n in maps if n.endswith('split_config.arm64_v8a.apk') and o==0x4000][0]
g=open(D+'gotplt.bin','rb').read()
out=[];libs=collections.Counter()
for i in range(3,0x18e40//8):
    va=0x1c63ad8+8*i
    if va in known: continue
    v=struct.unpack_from('<Q',g,va-0x1c63000)[0]
    hit=[(a,o,n) for a,b,o,n in maps if a<=v<b]
    if hit:
        a,o,n=hit[0]
        if 0<=v-base<0x3000000 and n.endswith('arm64_v8a.apk'): r=('SELF',v-base)
        else:
            fb=min(x for x,y,oo,nn in maps if nn==n)  # lib load base
            r=(n,v-fb)
    else: r=('?',v)
    libs[r[0]]+=1
    out.append('%x %x %s %x'%(va,v,r[0],r[1]))
open('C:/WSA/recon/stripped.txt','w').write('\n'.join(out))
print(len(out)); print(libs)
