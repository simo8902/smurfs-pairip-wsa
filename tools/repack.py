"""Replace a native library inside a split APK, dropping the old signature.
Generic: all paths come from argv.

Usage: python -I repack.py <src_split.apk> <new_lib.so> <out_unsigned.apk> <in_apk_lib_path>
"""
import sys, zipfile

src, lib_path, dst = sys.argv[1], sys.argv[2], sys.argv[3]
entry = sys.argv[4]  # in-apk path of the .so to replace
lib = open(lib_path, 'rb').read()
zi = zipfile.ZipFile(src)
zo = zipfile.ZipFile(dst, 'w')
for i in zi.infolist():
    if i.filename.startswith('META-INF/') and i.filename.rsplit('.', 1)[-1] in ('SF', 'RSA', 'EC', 'DSA', 'MF'):
        continue
    data = lib if i.filename == entry else zi.read(i)
    n = zipfile.ZipInfo(i.filename, i.date_time)
    n.compress_type = i.compress_type
    n.external_attr = i.external_attr
    zo.writestr(n, data)
zo.close()
print('repacked ->', dst)
