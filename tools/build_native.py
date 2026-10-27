"""Build a standalone, libpairipcore-free native library from the original
library plus a game profile. GENERIC: contains no game-specific bytes, strings
or addresses -- those all come from the profile module.

Pipeline:
  1. splice the profile's decrypted .text/.data regions into the original lib
  2. install a DT_INIT stub that, at load:
       - dlsym-fills the 200 stripped GOT.plt slots (profile.SLOTS)
       - installs WSA GL fast-paths (local glIsProgram/glIsBuffer, cached
         glGetUniformLocation, redundant glEnable/glDisable skip, index-buffer
         virtualisation) via the slots in profile.G
  3. rename DT_NEEDED libpairipcore.so -> libc.so
  4. weaken the ExecuteProgram import

Usage: python -I build_native.py <orig_lib> <out_lib> <profile.py>
"""
import sys, struct, importlib.util
from elftools.elf.elffile import ELFFile
from keystone import Ks, KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN


def load_profile(path):
    spec = importlib.util.spec_from_file_location('game_profile', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def k32(reg, v):
    return ' movz %s, #0x%x\n movk %s, #0x%x, lsl #16\n' % (reg, v & 0xffff, reg, v >> 16)


def k64(reg, v):
    return ''.join(' %s %s, #0x%x, lsl #%d\n' % ('movz' if i == 0 else 'movk', reg, (v >> (16 * i)) & 0xffff, 16 * i)
                   for i in range(4))


def build(orig_path, out_path, P):
    lib = bytearray(open(orig_path, 'rb').read())
    e = ELFFile(open(orig_path, 'rb'))
    loads = [(s['p_vaddr'], s['p_offset'], s['p_filesz']) for s in e.iter_segments() if s['p_type'] == 'PT_LOAD']

    def vtoff(va):
        for v, o, sz in loads:
            if v <= va < v + sz:
                return o + (va - v)
        raise KeyError(hex(va))

    # 1. decrypted .text/.data (the game's PairIP-decrypted bytes, from the profile)
    nb = 0
    for va, b in P.decrypted():
        fo = vtoff(va)
        lib[fo:fo + len(b)] = b
        nb += len(b)

    # 2. slot -> libc name
    slots = list(P.SLOTS)
    assert len(slots) == 200
    A, G = P.ADDR, P.G
    STUB, TAB, MEMPTR = A['STUB'], A['TAB'], A['MEMPTR']
    DLSYM_GOT, GOT_LO, GOT_LEN = A['DLSYM_GOT'], A['GOT_LO'], A['GOT_LEN']

    # ---- stub + GL-hook layout (generic design) ----
    NENT = 2048
    B2 = 0x40 + NENT * 64
    HOFF = 0x80 + 65536 * 4
    EOFF = 0x80 + 65536 * 4 + 65536 * 16
    VOFF = EOFF + 0x40 + 65536 * 4
    MEMSZ = B2 + VOFF + 65536 * 16
    SEGSZ = 0x4000

    GETB2 = (' adr x9, start\n movz x10, #0x2a3, lsl #16\n sub x9, x9, x10\n' + k32('x10', MEMPTR)
             + ' ldr x9, [x9, x10]\n' + k32('x10', B2) + ' add x9, x9, x10\n')
    VT = '\n' + k32('x14', VOFF) + ' add x14, x9, x14\n add x14, x14, x11, lsl #4\n'

    BUFHOOKS = '''
fn_bind:
 hint #34
''' + GETB2 + '''
 mov w10, #0x8892
 cmp w0, w10
 b.ne bind_e
 str w1, [x9, #0x28]
 b bind_go
bind_e:
 mov w10, #0x8893
 cmp w0, w10
 b.ne bind_go
 str w1, [x9, #0x2c]
 lsr w12, w1, #16
 cbnz w12, bind_go
 mov w11, w1
''' + VT + '''
 ldr w12, [x14, #12]
 cbz w12, bind_go
 mov w1, #0
bind_go:
 ldr x16, [x9, #0x10]
 br x16

fn_bsub:
 hint #34
''' + GETB2 + '''
 mov w10, #0x8892
 cmp w0, w10
 b.ne bs_e
 ldr w11, [x9, #0x28]
 b bs_have
bs_e:
 mov w10, #0x8893
 cmp w0, w10
 b.ne bs_go
 ldr w11, [x9, #0x2c]
 lsr w12, w11, #16
 cbnz w12, bs_go
''' + VT + '''
 ldr w12, [x14, #12]
 cbz w12, bs_have
 add x12, x1, x2
 ldr w13, [x14, #8]
 cmp x12, x13
 b.hi bs_have
 ldr x0, [x14]
 add x0, x0, x1
 mov x1, x3
 ldr x16, [x9, #0x68]
 br x16
bs_have:
 lsr w12, w11, #16
 cbnz w12, bs_go
''' + k32('x14', HOFF) + '''
 add x14, x9, x14
 add x14, x14, x11, lsl #4
 str wzr, [x14, #8]
bs_go:
 ldr x16, [x9, #8]
 br x16

fn_drawel:
 hint #34
''' + GETB2 + '''
 ldr w11, [x9, #0x2c]
 cbz w11, de_go
 lsr w12, w11, #16
 cbnz w12, de_go
''' + VT + '''
 ldr w12, [x14, #12]
 cbz w12, de_go
 ldr x12, [x14]
 add x3, x12, x3
de_go:
 ldr x16, [x9, #0x70]
 br x16

fn_delbuf:
 hint #34
''' + GETB2 + '''
 mov w12, w0
 mov x13, x1
db_loop:
 cmp w12, #0
 b.le db_go
 ldr w11, [x13], #4
 lsr w15, w11, #16
 cbnz w15, db_skip
 add x15, x9, #0x80
 str wzr, [x15, x11, lsl #2]
''' + k32('x15', HOFF) + '''
 add x15, x9, x15
 add x15, x15, x11, lsl #4
 str wzr, [x15, #8]
''' + VT + '''
 str wzr, [x14, #12]
 ldr w15, [x9, #0x2c]
 cmp w15, w11
 b.ne db_skip
 str wzr, [x9, #0x2c]
db_skip:
 sub w12, w12, #1
 b db_loop
db_go:
 ldr x16, [x9, #0x20]
 br x16

fn_gen:
 hint #34
 stp x29, x30, [sp, #-32]!
 stp x19, x20, [sp, #16]
 mov w19, w0
 mov x20, x1
''' + GETB2 + '''
 ldr x16, [x9, #0x18]
 blr x16
''' + GETB2 + '''
gen_loop:
 cmp w19, #0
 b.le gen_done
 ldr w11, [x20], #4
 lsr w15, w11, #16
 cbnz w15, gen_skip
 add x15, x9, #0x80
 str wzr, [x15, x11, lsl #2]
''' + k32('x15', HOFF) + '''
 add x15, x9, x15
 add x15, x15, x11, lsl #4
 str wzr, [x15, #8]
''' + VT + '''
 str wzr, [x14, #12]
gen_skip:
 sub w19, w19, #1
 b gen_loop
gen_done:
 ldp x19, x20, [sp, #16]
 ldp x29, x30, [sp], #32
 ret

fn_edata:
 cbz w11, bd_pass
 lsr w12, w11, #16
 cbnz w12, bd_pass
''' + VT + '''
 ldr w12, [x14, #12]
 cbnz w12, ed_virt
 lsr x12, x1, #16
 cbnz x12, bd_pass
 mov w12, #1
 str w12, [x14, #12]
ed_virt:
 stp x29, x30, [sp, #-48]!
 stp x19, x20, [sp, #16]
 stp x21, x22, [sp, #32]
 mov x19, x14
 mov x20, x1
 mov x21, x2
 mov x22, x9
 ldr w12, [x19, #8]
 cmp x12, x20
 b.hs ed_copy
 mov x1, #256
 cmp x20, x1
 csel x1, x20, x1, hi
 str w1, [x19, #8]
 ldr x0, [x19]
 ldr x16, [x22, #0x58]
 blr x16
 str x0, [x19]
ed_copy:
 cbz x21, ed_unbind
 ldr x0, [x19]
 mov x1, x21
 mov x2, x20
 ldr x16, [x22, #0x68]
 blr x16
ed_unbind:
 mov w0, #0x8893
 mov w1, #0
 ldr x16, [x22, #0x10]
 blr x16
 ldp x21, x22, [sp, #32]
 ldp x19, x20, [sp, #16]
 ldp x29, x30, [sp], #48
 ret

fn_bdata:
 hint #34
''' + GETB2 + '''
 ldp x10, x11, [x9, #0x30]
 add x10, x10, x1
 add x11, x11, #1
 stp x10, x11, [x9, #0x30]
 mov w10, #0x8892
 cmp w0, w10
 b.ne bd_e
 ldr x11, [x9, #0x48]
 add x11, x11, #1
 str x11, [x9, #0x48]
 ldr w11, [x9, #0x28]
 b bd_have
bd_e:
 mov w10, #0x8893
 cmp w0, w10
 b.ne bd_pass
 ldr x11, [x9, #0x50]
 add x11, x11, #1
 str x11, [x9, #0x50]
 ldr w11, [x9, #0x2c]
 b fn_edata
bd_have:
 cbz w11, bd_pass
 lsr w12, w11, #16
 cbnz w12, bd_pass
 add x13, x9, #0x80
 add x13, x13, x11, lsl #2
''' + k32('x14', HOFF) + '''
 add x14, x9, x14
 add x14, x14, x11, lsl #4
 cbz x2, bd_nodedup
 lsr x12, x1, #16
 cbnz x12, bd_nodedup
''' + k64('x15', 0xcbf29ce484222325) + k64('x16', 0x100000001b3) + '''
 mov x12, #0
h_loop:
 cmp x12, x1
 b.hs h_done
 ldrb w17, [x2, x12]
 eor x15, x15, x17
 mul x15, x15, x16
 add x12, x12, #1
 b h_loop
h_done:
 ldr x12, [x14]
 ldr w17, [x14, #8]
 cmp w17, w1
 b.ne h_store
 cmp x12, x15
 b.ne h_store
 ldr x12, [x9, #0x40]
 add x12, x12, #1
 str x12, [x9, #0x40]
 ret
h_store:
 str x15, [x14]
 str w1, [x14, #8]
 b bd_upload
bd_nodedup:
 str wzr, [x14, #8]
 cbz x2, bd_setcap
bd_upload:
 ldr w12, [x13]
 cmp x12, x1
 b.lo bd_setcap
 mov x3, x2
 mov x2, x1
 mov x1, #0
 ldr x16, [x9, #8]
 br x16
bd_setcap:
 lsr x12, x1, #32
 cbnz x12, bd_pass
 str w1, [x13]
bd_pass:
 ldr x16, [x9]
 br x16
'''

    ENHOOKS = ''.join('''
fn_%s:
 hint #34
''' % nm + GETB2 + k32('x10', EOFF) + '''
 add x9, x9, x10
 lsr w10, w0, #16
 cbnz w10, %s_go
 ldr w11, [x9, #0x18]
 add x12, x9, #0x40
 ldr w13, [x12, w0, uxtw #2]
 lsl w14, w11, #2
 orr w14, w14, #%d
 cmp w13, w14
 b.eq %s_skip
 str w14, [x12, w0, uxtw #2]
%s_go:
 ldr x16, [x9, #%d]
 br x16
%s_skip:
 ret
''' % (nm, st, nm, nm, off, nm) for nm, st, off in (('enable', 2, 0), ('disable', 1, 8))) + '''
fn_clear:
 hint #34
''' + GETB2 + k32('x10', EOFF) + '''
 add x9, x9, x10
 ldr w11, [x9, #0x18]
 add w11, w11, #1
 and w11, w11, #0x3fffffff
 str w11, [x9, #0x18]
 ldr x16, [x9, #0x10]
 br x16
'''

    extra = ['mprotect', 'mmap', 'memset', 'realloc', 'memcpy']
    names = sorted(set(n for _, n in slots)) + extra

    code = '''
start:
 hint #34
 stp x29, x30, [sp, #-64]!
 stp x19, x20, [sp, #16]
 stp x21, x22, [sp, #32]
 stp x23, x24, [sp, #48]
 mov x29, sp
 adr x19, start
 movz x9, #0x2a3, lsl #16
 sub x19, x19, x9
''' + k32('x9', DLSYM_GOT) + '''
 ldr x22, [x19, x9]
 mov x0, #0
 ldr w1, n_mprotect
 add x1, x19, x1
 blr x22
 mov x21, x0
''' + k32('x9', GOT_LO) + '''
 add x0, x19, x9
''' + k32('x1', GOT_LEN) + '''
 mov x2, #3
 blr x21
''' + k32('x20', TAB) + '''
 add x20, x19, x20
 mov w23, #''' + str(len(slots)) + '''
loop:
 ldp w24, w1, [x20], #8
 mov x0, #0
 add x1, x19, x1
 blr x22
 str x0, [x19, x24]
 subs w23, w23, #1
 b.ne loop
 mov x0, #0
 ldr w1, n_mmap
 add x1, x19, x1
 blr x22
 mov x9, x0
 mov x0, #0
''' + k32('x1', MEMSZ) + '''
 mov x2, #3
 mov x3, #0x22
 mov w4, #-1
 mov x5, #0
 blr x9
 cmn x0, #1
 b.eq nohook
 cbz x0, nohook
 mov x23, x0
''' + k32('x9', MEMPTR) + '''
 str x23, [x19, x9]
 mov x0, #0
 ldr w1, n_memset
 add x1, x19, x1
 blr x22
 str x0, [x23, #0x18]
''' + k32('x9', G['getloc']) + '''
 ldr x10, [x19, x9]
 str x10, [x23]
 adr x10, fn_getloc
 str x10, [x19, x9]
''' + k32('x9', G['link']) + '''
 ldr x10, [x19, x9]
 str x10, [x23, #8]
 adr x10, fn_link
 str x10, [x19, x9]
''' + k32('x9', G['delete']) + '''
 ldr x10, [x19, x9]
 str x10, [x23, #0x10]
 adr x10, fn_delete
 str x10, [x19, x9]
 adr x10, fn_isnz
''' + k32('x9', G['isprog']) + '''
 str x10, [x19, x9]
''' + k32('x9', G['isbuf']) + '''
 str x10, [x19, x9]
''' + k32('x11', B2) + '''
 add x11, x23, x11
''' + ''.join(k32('x9', G[n]) + ' ldr x10, [x19, x9]\n str x10, [x11, #%d]\n' % o
              + (' adr x10, %s\n str x10, [x19, x9]\n' % f if f else '')
              for n, o, f in (('bdata', 0, 'fn_bdata'), ('bsub', 8, 'fn_bsub'), ('bind', 0x10, 'fn_bind'),
                              ('gen', 0x18, 'fn_gen'), ('delbuf', 0x20, 'fn_delbuf'))) + k32('x11', B2 + EOFF) + '''
 add x11, x23, x11
''' + ''.join(k32('x9', G[n]) + ' ldr x10, [x19, x9]\n str x10, [x11, #%d]\n adr x10, %s\n str x10, [x19, x9]\n' % (o, f)
              for n, o, f in (('enable', 0, 'fn_enable'), ('disable', 8, 'fn_disable'), ('clear', 0x10, 'fn_clear'))) + '''
 mov x0, #0
 ldr w1, n_realloc
 add x1, x19, x1
 blr x22
''' + k32('x11', B2) + '''
 add x11, x23, x11
 str x0, [x11, #0x58]
 mov x0, #0
 ldr w1, n_memcpy
 add x1, x19, x1
 blr x22
''' + k32('x11', B2) + '''
 add x11, x23, x11
 str x0, [x11, #0x68]
''' + k32('x9', G['drawel']) + '''
 ldr x10, [x19, x9]
 str x10, [x11, #0x70]
 adr x10, fn_drawel
 str x10, [x19, x9]
nohook:
''' + k32('x9', GOT_LO) + '''
 add x0, x19, x9
''' + k32('x1', GOT_LEN) + '''
 mov x2, #1
 blr x21
 ldp x23, x24, [sp, #48]
 ldp x21, x22, [sp, #32]
 ldp x19, x20, [sp, #16]
 ldp x29, x30, [sp], #64
 ret

''' + BUFHOOKS + ENHOOKS + '''
fn_isnz:
 hint #34
 cmp w0, #0
 cset w0, ne
 ret

getmem:
 adr x9, start
 movz x10, #0x2a3, lsl #16
 sub x9, x9, x10
''' + k32('x10', MEMPTR) + '''
 ldr x9, [x9, x10]
 ret

clear:
 stp x29, x30, [sp, #-16]!
 bl getmem
 ldr x10, [x9, #0x18]
 add x0, x9, #0x40
 mov w1, #0
''' + k32('x2', NENT * 64) + '''
 blr x10
 ldp x29, x30, [sp], #16
 ret

fn_link:
 hint #34
 stp x29, x30, [sp, #-32]!
 str x19, [sp, #16]
 mov w19, w0
 bl clear
 bl getmem
 ldr x9, [x9, #8]
 mov w0, w19
 blr x9
 ldr x19, [sp, #16]
 ldp x29, x30, [sp], #32
 ret

fn_delete:
 hint #34
 stp x29, x30, [sp, #-32]!
 str x19, [sp, #16]
 mov w19, w0
 bl clear
 bl getmem
 ldr x9, [x9, #0x10]
 mov w0, w19
 blr x9
 ldr x19, [sp, #16]
 ldp x29, x30, [sp], #32
 ret

fn_getloc:
 hint #34
 stp x29, x30, [sp, #-64]!
 stp x19, x20, [sp, #16]
 stp x21, x22, [sp, #32]
 stp x23, x24, [sp, #48]
 mov x29, sp
 mov w19, w0
 mov x20, x1
 bl getmem
 mov x21, x9
''' + k32('w9', 0x811c9dc5) + k32('w10', 0x01000193) + '''
 mov x11, x20
 mov w12, #0
hloop:
 ldrb w13, [x11], #1
 cbz w13, hdone
 eor w9, w9, w13
 mul w9, w9, w10
 add w12, w12, #1
 b hloop
hdone:
 cmp w12, #55
 b.hi passthru
''' + k32('w13', 0x9e3779b1) + '''
 mul w13, w19, w13
 eor w9, w9, w13
 and w22, w9, #%d
 mov w23, #8
probe:
 add x14, x21, #0x40
 add x14, x14, x22, lsl #6
 mov x24, x14
 ldr w15, [x14]
 cbz w15, miss
 cmp w15, w19
 b.ne next
 add x16, x14, #8
 mov x17, x20
cmploop:
 ldrb w0, [x16], #1
 ldrb w1, [x17], #1
 cmp w0, w1
 b.ne next
 cbnz w0, cmploop
 ldr w0, [x14, #4]
 b done
next:
 add w22, w22, #1
 and w22, w22, #%d
 subs w23, w23, #1
 b.ne probe
miss:
 ldr x9, [x21]
 mov w0, w19
 mov x1, x20
 blr x9
 str w0, [x24, #4]
 add x16, x24, #8
 mov x17, x20
cploop:
 ldrb w1, [x17], #1
 strb w1, [x16], #1
 cbnz w1, cploop
 str w19, [x24]
 b done
passthru:
 ldr x9, [x21]
 mov w0, w19
 mov x1, x20
 blr x9
done:
 ldp x23, x24, [sp, #48]
 ldp x21, x22, [sp, #32]
 ldp x19, x20, [sp, #16]
 ldp x29, x30, [sp], #64
 ret

n_mprotect:
 .word 0
n_mmap:
 .word 0
n_memset:
 .word 0
n_realloc:
 .word 0
n_memcpy:
 .word 0
''' % (NENT - 1, NENT - 1)

    ks = Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN)
    enc, _ = ks.asm(code, STUB)
    code_b = bytearray(enc)
    assert len(code_b) % 4 == 0 and len(code_b) <= 0x1000, hex(len(code_b))

    str_base = TAB + 8 * len(slots)
    strs = bytearray(); spos = {}
    for n in names:
        spos[n] = str_base + len(strs)
        strs += n.encode() + b'\0'
    for k, n in enumerate(extra):
        struct.pack_into('<I', code_b, len(code_b) - 4 * len(extra) + 4 * k, spos[n])
    tab = b''.join(struct.pack('<II', s, spos[n]) for s, n in slots) + bytes(strs)

    seg = {s['p_vaddr']: s for s in e.iter_segments() if s['p_type'] == 'PT_LOAD'}
    fo = seg[STUB]['p_offset']
    lib[fo:fo + 0x1000] = bytes(code_b) + b'\0' * (0x1000 - len(code_b))
    assert TAB + len(tab) <= STUB + SEGSZ
    assert not any(lib[seg[STUB]['p_offset'] + 0x1000:seg[STUB]['p_offset'] + SEGSZ])
    for i, s in enumerate(e.iter_segments()):
        if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] == STUB:
            ph = e['e_phoff'] + i * e['e_phentsize']
            struct.pack_into('<QQ', lib, ph + 32, SEGSZ, SEGSZ)
    fo = seg[STUB]['p_offset'] + TAB - STUB
    lib[fo:fo + len(tab)] = tab

    # 3. DT_NEEDED libpairipcore.so -> libc.so
    ds = e.get_section_by_name('.dynstr')
    i = ds.data().find(b'\0libpairipcore.so\0') + 1
    assert i > 0
    lib[ds['sh_offset'] + i:ds['sh_offset'] + i + 17] = b'libc.so'.ljust(17, b'\0')

    # 4. ExecuteProgram -> STB_WEAK
    sym = e.get_section_by_name('.dynsym')
    for k, s in enumerate(sym.iter_symbols()):
        if s.name == 'ExecuteProgram':
            lib[sym['sh_offset'] + k * 24 + 4] = (2 << 4) | 2
            break
    else:
        raise SystemExit('no ExecuteProgram import')

    open(out_path, 'wb').write(lib)
    print('decrypted %d bytes, stub 0x%x, table 0x%x -> %s' % (nb, len(code_b), len(tab), out_path))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit('usage: build_native.py <orig_lib> <out_lib> <profile.py>')
    build(sys.argv[1], sys.argv[2], load_profile(sys.argv[3]))
