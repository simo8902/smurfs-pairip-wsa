#!/system/bin/sh
# Dump PairIP-decrypted the game library regions from a rooted arm64 phone.
# MUST run under busybox ash (64-bit math) as root. See the run command below.
PKG="${1:?usage: pass the package name as arg 1}"
OUT=/data/local/tmp/smdump

rm -rf "$OUT"; mkdir -p "$OUT"; cd "$OUT"

monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1

P=""; i=0
while [ -z "$P" ] && [ $i -lt 60 ]; do P=$(pidof $PKG); i=$((i+1)); sleep 0.5; done
[ -z "$P" ] && { echo "NO PID - is the game installed on the phone?"; exit 1; }
echo "pid $P"

sleep 20                       # let the native VM decrypt

cp /proc/$P/maps maps.txt

# lib sits at apk offset 0x4000; other libs in the same split map elsewhere
BASE=$(grep -E "split_config\.arm64_v8a\.apk" maps.txt \
       | awk '$3=="00004000"{split($1,a,"-"); print a[1]}' | head -1)
[ -z "$BASE" ] && BASE=$(grep "libSmurfsAndroid\.so" maps.txt \
       | awk -F- '{print $1}' | sort | head -1)
[ -z "$BASE" ] && { echo "lib mapping not found"; grep -iE "arm64" maps.txt; exit 1; }
echo "base 0x$BASE"

dumpregion() {                 # name  vaddr_hex  len_hex
  addr=$((0x$BASE + 0x$2)); pg=$((addr / 4096)); n=$(( (0x$3 + 4095) / 4096 ))
  dd if=/proc/$P/mem of=$1.bin bs=4096 skip=$pg count=$n 2>/dev/null
  echo "  $1 $(wc -c < $1.bin) bytes @ va 0x$2"
}

dumpregion text_c90000 c90000 20000
dumpregion text_ce9000 ce9000 3000
dumpregion got      1c5be60 8000
dumpregion gotplt   1c63ad8 1a000

chmod -R 777 "$OUT"
echo "DONE -> $OUT"
ls -la
