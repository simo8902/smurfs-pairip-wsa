from elftools.elf.elffile import ELFFile
e=ELFFile(open('C:/WSA/recon/phonedump/libc.so','rb'))
syms={}
for s in e.get_section_by_name('.dynsym').iter_symbols():
    if s['st_value'] and s['st_info']['type'] in ('STT_FUNC','STT_GNU_IFUNC','STT_OBJECT'):
        syms.setdefault(s['st_value'],[]).append((s.name,s['st_info']['type']))
# p_vaddr of first load
lo=min(s['p_vaddr'] for s in e.iter_segments() if s['p_type']=='PT_LOAD')
res=[];miss=0;ifn=0
for l in open('C:/WSA/recon/stripped.txt'):
    va,v,lib,off=l.split()
    o=int(off,16)+lo
    n=syms.get(o)
    if not n: miss+=1; res.append('%s ? %x'%(va,o)); continue
    nm=sorted(n,key=lambda x:(x[0].startswith('_'),len(x[0])))[0][0]
    res.append('%s %s'%(va,nm))
open('C:/WSA/recon/stripped_named.txt','w').write('\n'.join(res))
print('miss',miss); print('\n'.join(res[:12]))
