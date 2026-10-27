"""Apply a unified diff (the game's smali/manifest edits, from the profile) to a
decompiled tree. Pure Python, LF-normalised, modifications only (-p1).

Usage: python -I apply_patch.py <base_dir> <profile.py>
"""
import sys, os, re, importlib.util


def load_profile(path):
    spec = importlib.util.spec_from_file_location('game_profile', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def split_files(diff):
    # yield (path, [hunks]) where path is the b/ side with the leading component stripped
    cur, hunks, path = None, None, None
    out = []
    lines = diff.split('\n')
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.startswith('--- '):
            i += 1
            plus = lines[i]
            assert plus.startswith('+++ '), plus
            path = plus[4:].split('\t')[0]
            path = path.split('/', 1)[1] if '/' in path else path   # strip b/
            hunks = []
            out.append((path, hunks))
        elif l.startswith('@@'):
            m = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', l)
            os_, oc = int(m.group(1)), int(m.group(2) or 1)
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('--- '):
                body.append(lines[i]); i += 1
            hunks.append((os_, oc, body)); continue
        i += 1
    return out


def apply_hunk(dst, start, body):
    # returns new dst (list) ; raises on context mismatch
    old = []
    new = []
    for b in body:
        if b.startswith('-'):
            old.append(b[1:])
        elif b.startswith('+'):
            new.append(b[1:])
        elif b.startswith(' '):
            old.append(b[1:]); new.append(b[1:])
        # ignore '' (trailing split sentinel) and '\ No newline at end of file'
    # locate: expected at start-1, but search a small window for robustness
    n = len(old)
    for delta in [0] + [d for k in range(1, 200) for d in (k, -k)]:
        p = start - 1 + delta
        if 0 <= p <= len(dst) - n and dst[p:p + n] == old:
            return dst[:p] + new + dst[p + n:]
    raise RuntimeError('hunk context not found near line %d' % start)


def main(base, profile_py):
    diff = load_profile(profile_py).patch_text()
    files = split_files(diff)
    for path, hunks in files:
        fp = os.path.join(base, path.replace('/', os.sep))
        with open(fp, 'r', encoding='utf-8', newline='') as f:
            dst = f.read().replace('\r\n', '\n').split('\n')
        # apply bottom-up so earlier line numbers stay valid
        for start, _, body in sorted(hunks, key=lambda h: h[0], reverse=True):
            dst = apply_hunk(dst, start, body)
        with open(fp, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(dst))
    print('applied edits to %d files' % len(files))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: apply_patch.py <base_dir> <profile.py>')
    main(sys.argv[1], sys.argv[2])
