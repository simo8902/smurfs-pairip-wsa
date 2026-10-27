BB=/data/adb/magisk/busybox
PKG="${1:?usage: pass the package name as arg 1}"
P=$(pidof "$PKG")
rd() { $BB dd if=/proc/$P/mem bs=8 skip=$(($1/8)) count=1 2>/dev/null | $BB od -An -tu8 | tr -d ' '; }
B=$((0x400020a00000))
M=$(rd $((B + 0x2a28008)))
C=$((M + 0x20040 + 0x30))
r() { echo "$(rd $C) $(rd $((C+8))) $(rd $((C+16))) $(rd $((C+24))) $(rd $((C+32)))"; }
set -- $(r); b1=$1 n1=$2 s1=$3 a1=$4 e1=$5
sleep 5
set -- $(r)
echo "bytes/5s=$(($1-b1)) calls/5s=$(($2-n1)) skipped/5s=$(($3-s1)) array/5s=$(($4-a1)) element/5s=$(($5-e1))"