# Diff phone memory image of libSmurfsAndroid.so against the file.
# Reports bytes PairIP decrypted at runtime: differ from file, same in both snapshots,
# not covered by a dynamic relocation.
import struct, bisect, sys
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

SRC = 'C:/WSA/emu/libSmurfsAndroid.so'
D = 'C:/WSA/recon/phonedump2/'
f = open(SRC, 'rb').read()
e = ELFFile(open(SRC, 'rb'))
A = open(D + 'imgA.bin', 'rb').read()
B = open(D + 'imgB.bin', 'rb').read()

base = None
mapped = []
for l in open(D + 'imgA.bin.maps'):
    p = l.split()
    s, t = [int(x, 16) for x in p[0].split('-')]
    if base is None and len(p) > 5 and p[5].endswith('split_config.arm64_v8a.apk') and p[2] == '00004000':
        base = s
for l in open(D + 'imgA.bin.maps'):
    s, t = [int(x, 16) for x in l.split()[0].split('-')]
    if base <= s < base + 0x2b10000:
        mapped.append((s - base, t - base))
print('base', hex(base), 'mapped ranges', len(mapped))

reloc = set()
for s in e.iter_sections():
    if isinstance(s, RelocationSection):
        for r in s.iter_relocations():
            reloc.add(r['r_offset'])

segs = [(s['p_vaddr'], s['p_offset'], s['p_filesz']) for s in e.iter_segments() if s['p_type'] == 'PT_LOAD']
diffs = []           # (va, len)
for va, off, sz in segs:
    for ms, me in mapped:
        a, z = max(va, ms), min(va + sz, me)
        if a >= z:
            continue
        fa = f[off + a - va: off + z - va]
        pa, pb = A[a:z], B[a:z]
        i = 0
        n = z - a
        while i < n:
            if fa[i] != pa[i] and pa[i] == pb[i]:
                j = i
                while j < n and fa[j] != pa[j] and pa[j] == pb[j]:
                    j += 1
                diffs.append((a + i, j - i))
                i = j
            else:
                i += 1

# drop diffs fully inside 8-byte reloc slots
def in_reloc(v, ln):
    k = v - (v % 8) if (v % 8) else v
    for x in range(v, v + ln):
        s = x - (x % 8)
        if not any(r <= x < r + 8 for r in (s,) if r in reloc):
            return False
    return True

keep = [(v, ln) for v, ln in diffs if not in_reloc(v, ln)]
print('raw diff runs', len(diffs), 'after reloc filter', len(keep), 'bytes', sum(l for _, l in keep))

syms = sorted((s['st_value'], s['st_size'], s.name) for s in e.get_section_by_name('.dynsym').iter_symbols() if s['st_value'])
vals = [x[0] for x in syms]
def who(v):
    k = bisect.bisect_right(vals, v) - 1
    if k < 0: return '?'
    sv, sz, n = syms[k]
    return '%s+%#x' % (n[:60], v - sv) if v < sv + max(sz, 1) else '(after %s)' % n[:40]

# merge runs closer than 16 bytes
merged = []
for v, ln in keep:
    if merged and v - (merged[-1][0] + merged[-1][1]) < 16:
        merged[-1][1] = v + ln - merged[-1][0]
    else:
        merged.append([v, ln])
print('merged regions', len(merged))
for v, ln in merged[:80]:
    print('  %8x %6d  %s' % (v, ln, who(v)))
open('C:/WSA/recon/decrypted_regions.txt', 'w').write('\n'.join('%x %x' % (v, l) for v, l in keep))
