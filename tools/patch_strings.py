import os, re, sys
base = sys.argv[1]
dry = len(sys.argv) > 2 and sys.argv[2] == 'dry'
count = 0
files = 0
pat = re.compile(
    r'(\.field\s+(?=[^\r\n]*\bstatic\b)'
    r'[^\r\n]*?:Ljava/lang/String;)'
    r'(?=[ \t]*[\r\n])'
)
def sub(m):
    global count
    count += 1
    return m.group(0) + ' = ""'
for root, dirs, fl in os.walk(base):
    for fn in fl:
        if not fn.endswith('.smali'):
            continue
        p = os.path.join(root, fn)
        with open(p, 'r', encoding='utf-8', newline='') as f:
            c = f.read()
        n = pat.sub(sub, c)
        if n != c:
            if not dry:
                with open(p, 'w', encoding='utf-8', newline='') as f:
                    f.write(n)
            files += 1
print("Patched", count, "fields in", files, "files", "(dry)" if dry else "")
