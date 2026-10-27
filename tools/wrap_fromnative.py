# Wrap every static fromNative_* JNI callback in try/catch(Throwable) -> default return.
# A Java exception thrown back into native code otherwise stays pending and poisons later JNI calls.
import os, re, sys

ROOT = sys.argv[1]
PARAM_SIZE = {'J': 2, 'D': 2}


def param_regs(desc, static):
    args = desc[desc.index('(') + 1:desc.index(')')]
    n = 0 if static else 1
    i = 0
    while i < len(args):
        c = args[i]
        if c == '[':
            while args[i] == '[':
                i += 1
            if args[i] == 'L':
                i = args.index(';', i)
            n += 1
        elif c == 'L':
            i = args.index(';', i)
            n += 1
        else:
            n += PARAM_SIZE.get(c, 1)
        i += 1
    return n


def handler(ret):
    out = ['    move-exception v0', '    invoke-virtual {v0}, Ljava/lang/Throwable;->printStackTrace()V']
    if ret == 'V':
        out.append('    return-void')
    elif ret in 'JD':
        out += ['    const-wide/16 v0, 0x0', '    return-wide v0']
    elif ret[0] in 'L[':
        out += ['    const/4 v0, 0x0', '    return-object v0']
    else:
        out += ['    const/4 v0, 0x0', '    return v0']
    return out


def wrap(lines, start, end, uid):
    head = lines[start]
    m = re.match(r'\.method (.*?)(\S+)\((.*?)\)(\S+)$', head.strip())
    mods, name, ret = m.group(1), m.group(2), m.group(4)
    desc = '(' + m.group(3) + ')' + ret
    static = ' static ' in ' ' + mods
    body = lines[start + 1:end]
    li = next(k for k, l in enumerate(body) if l.strip().startswith('.locals'))
    loc = int(body[li].split()[1])
    newloc = max(loc, 2)
    if newloc + param_regs(desc, static) > 16 and newloc != loc:
        return None, name + ' (register limit, skipped)'
    body[li] = '    .locals %d' % newloc
    # first code line: skip directives/annotations
    k = li + 1
    while k < len(body):
        s = body[k].strip()
        if s and not s.startswith(('.param', '.end param', '.annotation', '.end annotation')) \
                and not body[k].startswith('        '):
            break
        k += 1
    body.insert(k, '    :try_start_wfn%d' % uid)
    body += ['    :try_end_wfn%d' % uid,
             '    .catch Ljava/lang/Throwable; {:try_start_wfn%d .. :try_end_wfn%d} :catch_wfn%d' % (uid, uid, uid),
             '', '    :catch_wfn%d' % uid] + handler(ret)
    return [head] + body, name


# argv[1]: base dir. optional argv[2]: wrap every method (except ctors) of the
# smali file whose path ends with it (used for whole ad/SDK classes).
ONLY = sys.argv[2] if len(sys.argv) > 2 else None


def wanted(l):
    if not l.startswith('.method') or ' native ' in l + ' ' or ' abstract ' in l:
        return False
    if ONLY:
        return '<init>' not in l and '<clinit>' not in l
    return 'fromNative_' in l


def main():
    uid = 0 if not ONLY else 1000
    done = []
    for dp, _, fs in os.walk(ROOT):
        for f in fs:
            if not f.endswith('.smali'):
                continue
            p = os.path.join(dp, f)
            if ONLY and not p.replace('\\', '/').endswith(ONLY):
                continue
            lines = open(p, encoding='utf-8').read().split('\n')
            if not any(wanted(l) for l in lines):
                continue
            out, i, changed = [], 0, False
            while i < len(lines):
                l = lines[i]
                if wanted(l):
                    j = lines.index('.end method', i)
                    if any('try_start_wfn' in x for x in lines[i:j]):
                        out += lines[i:j]; i = j; continue
                    uid += 1
                    new, name = wrap(lines, i, j, uid)
                    if new is None:
                        print('SKIP', f, name); out += lines[i:j]
                    else:
                        out += new; changed = True; done.append(f + ':' + name)
                    i = j
                    continue
                out.append(l)
                i += 1
            if changed:
                open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
    print('wrapped', len(done))


main()
