#!/system/bin/sh
# Full-image dump of PairIP-decrypted the game library (all mapped pages), taken twice.
# Two snapshots let the PC side tell runtime-mutated .data from VM-decrypted bytes.
# MUST run under busybox ash (64-bit math) as root.
PKG="${1:?usage: pass the package name as arg 1}"
OUT=/data/local/tmp/smdump2
SPAN=0x2b10000                 # lib image size (last segment ends 0x2b0c250)

rm -rf "$OUT"; mkdir -p "$OUT"; cd "$OUT"
am force-stop $PKG
monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1

P=""; i=0
while [ -z "$P" ] && [ $i -lt 60 ]; do P=$(pidof $PKG); i=$((i+1)); sleep 0.5; done
[ -z "$P" ] && { echo "NO PID - is the game installed on the phone?"; exit 1; }
P=${P%% *}
echo "pid $P"

BASE=""; i=0
while [ -z "$BASE" ] && [ $i -lt 60 ]; do
  BASE=$(grep -E "split_config\.arm64_v8a\.apk" /proc/$P/maps \
         | awk '$3=="00004000"{split($1,a,"-"); print a[1]}' | head -1)
  i=$((i+1)); sleep 0.5
done
[ -z "$BASE" ] && { echo "lib mapping not found"; exit 1; }
echo "base 0x$BASE"

snap() {                       # snap <file>
  B=$((0x$BASE)); E=$((B + SPAN))
  : > $1
  grep -v '^ *$' /proc/$P/maps | while read range rest; do
    s=$((0x${range%-*})); e=$((0x${range#*-}))
    [ $s -ge $B ] && [ $s -lt $E ] || continue
    dd if=/proc/$P/mem of=$1 bs=4096 skip=$((s/4096)) seek=$(((s-B)/4096)) \
       count=$(((e-s)/4096)) conv=notrunc 2>/dev/null
  done
  cp /proc/$P/maps $1.maps
  echo "  $1 $(wc -c < $1) bytes"
}

sleep 8
snap imgA.bin
sleep 12
snap imgB.bin

chmod -R 777 "$OUT"
echo "DONE -> $OUT"
ls -la
