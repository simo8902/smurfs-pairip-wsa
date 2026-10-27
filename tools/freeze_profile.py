# One-time: extract the game-specific native profile from the known-good rebuilt lib.
# Output: game/profile_3_02_0.py  (the ONE quarantined file with game-derived content).
# Decrypted bytes = diff(good, original) MINUS the parts build_native regenerates
# (the DT_INIT stub segment, the libpairipcore->libc rename, the ExecuteProgram bind,
#  and the program-header size bump).
import base64, struct, textwrap
from elftools.elf.elffile import ELFFile

import sys
ORIG, GOOD, OUT = sys.argv[1], sys.argv[2], sys.argv[3]  # original lib, known-good rebuilt lib, output profile

o = bytearray(open(ORIG, 'rb').read())
g = bytearray(open(GOOD, 'rb').read())
assert len(o) == len(g), (len(o), len(g))
e = ELFFile(open(ORIG, 'rb'))

segs = [(s['p_vaddr'], s['p_offset'], s['p_filesz']) for s in e.iter_segments() if s['p_type'] == 'PT_LOAD']
def off2va(fo):
    for va, off, sz in segs:
        if off <= fo < off + sz:
            return va + (fo - off)
    return None

STUB = 0x2a30000
stub_off = {s['p_vaddr']: s['p_offset'] for s in e.iter_segments() if s['p_type'] == 'PT_LOAD'}[STUB]
excluded = set()
excluded |= set(range(stub_off, stub_off + 0x4000))                       # regenerated stub segment
ds = e.get_section_by_name('.dynstr')
i = ds.data().find(b'\0libpairipcore.so\0') + 1
excluded |= set(range(ds['sh_offset'] + i, ds['sh_offset'] + i + 17))     # DT_NEEDED rename
sym = e.get_section_by_name('.dynsym')
for k, s in enumerate(sym.iter_symbols()):
    if s.name == 'ExecuteProgram':
        excluded.add(sym['sh_offset'] + k * 24 + 4)                        # st_info byte
for idx, s in enumerate(e.iter_segments()):
    if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] == STUB:
        ph = e['e_phoff'] + idx * e['e_phentsize']
        excluded |= set(range(ph + 32, ph + 48))                           # p_filesz,p_memsz

# contiguous runs where good != orig and offset not regenerated
runs = []
i = 0
n = len(o)
while i < n:
    if g[i] != o[i] and i not in excluded:
        j = i
        while j < n and g[j] != o[j] and j not in excluded:
            j += 1
        va = off2va(i)
        assert va is not None and off2va(j - 1) == va + (j - 1 - i), hex(i)
        runs.append((va, bytes(g[i:j])))
        i = j
    else:
        i += 1

dec_bytes = sum(len(b) for _, b in runs)

IFUNC = {'8fd40': 'memmove', '90200': 'memset', '90140': 'memrchr'}
slots = []
for l in open(sys.argv[4]):  # stripped_named.txt
    p = l.split()
    slots.append((int(p[0], 16), IFUNC[p[2]] if p[1] == '?' else p[1]))
assert len(slots) == 200

ADDR = dict(STUB=0x2a30000, TAB=0x2a31000, MEMPTR=0x2a28008, DLSYM_GOT=0x1c6ef40,
            GOT_LO=0x1c63000, GOT_LEN=0x1a000)
G = dict(isprog=0x1c65538, isbuf=0x1c64db8, getloc=0x1c654f8, link=0x1c653e8, delete=0x1c65420,
         bind=0x1c64278, gen=0x1c64dc0, bdata=0x1c64dc8, bsub=0x1c7bac8, delbuf=0x1c7bad8,
         enable=0x1c64258, disable=0x1c641f0, clear=0x1c65468, drawel=0x1c641e8)

b64 = base64.b64encode(b''.join(struct.pack('<II', va, len(b)) + b for va, b in runs)).decode()
wrapped = '\n'.join(textwrap.wrap(b64, 100))

with open(OUT, 'w', newline='\n') as f:
    f.write('''"""Game-specific profile for Smurfs' Village 3.02.0 (778), arm64.

THIS IS THE ONE FILE HOLDING COPYRIGHT-DERIVED CONTENT: the bytes PairIP
decrypts at runtime (recovered from a memory dump of a device the owner
controls) plus the virtual addresses specific to this build. Every other file
in the repo is generic tooling with no game content. Regenerate with
tools/ re-analysis if the game version changes.

DECRYPTED packs records of {u32 vaddr, u32 len, len bytes}: the decrypted
.text/.data to splice into the original library. ADDR/G are this build's
addresses. SLOTS maps the 200 stripped GOT.plt slots to libc symbols.
"""
import base64, struct

VERSION = "3.02.0 (778)"

ADDR = {%s}

# GL functions hooked for WSA (name -> GOT.plt slot vaddr)
G = {%s}

SLOTS = [
%s]

_DEC = (
%s)


def decrypted():
    """Yield (vaddr, bytes) decrypted regions."""
    raw = base64.b64decode(_DEC)
    i = 0
    while i < len(raw):
        va, n = struct.unpack_from('<II', raw, i); i += 8
        yield va, raw[i:i + n]; i += n
''' % (', '.join("'%s': 0x%x" % (k, v) for k, v in ADDR.items()),
       ', '.join("'%s': 0x%x" % (k, v) for k, v in G.items()),
       '\n'.join('    (0x%x, %r),' % (v, nm) for v, nm in slots),
       '\n'.join('    %r' % (ln + ('' if k == len(wrapped.split(chr(10))) - 1 else '')) for k, ln in enumerate(wrapped.split('\n')))))

print('runs', len(runs), 'decrypted bytes', dec_bytes, 'slots', len(slots), '->', OUT)
