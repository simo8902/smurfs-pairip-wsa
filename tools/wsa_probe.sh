#!/system/bin/sh
# Run under busybox ash as root on WSA. Polls libSmurfsAndroid state until the game dies.
PKG="${1:?usage: pass the package name as arg 1}"
BB=/data/adb/magisk/busybox
am force-stop $PKG
monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
P=""; i=0
while [ -z "$P" ] && [ $i -lt 100 ]; do P=$(pidof $PKG); i=$((i+1)); $BB usleep 50000; done
echo "pid $P"
rd() {  # rd addr_dec -> 8-byte little-endian hex
  $BB dd if=/proc/$P/mem bs=8 skip=$(($1/8)) count=1 2>/dev/null | $BB od -An -tx8 | tr -d ' '
}
BASE=""
n=0
P=${P%% *}
ls -d /proc/$P/maps
while [ -e /proc/$P/maps ] && [ $n -lt 200 ]; do
  if [ -z "$BASE" ]; then
    BASE=$(grep split_config.arm64_v8a.apk /proc/$P/maps | awk '($3=="00004000"||$3=="00001000") && $1 ~ /^4000/{split($1,a,"-"); print a[1]}' | head -1)
    [ -n "$BASE" ] && echo "base 0x$BASE"
    cp /proc/$P/maps /data/local/tmp/wmaps.txt 2>/dev/null
  fi
  if [ -n "$BASE" ]; then
    B=$((0x$BASE))
    FLAG=$(rd $((B + 0x29af780)))
    SG=$(rd $((B + 0x1c5dd38)))
    if [ -n "$SG" ] && [ "$SG" != "0000000000000000" ]; then
      S=$((0x$SG))
      echo "t=$n flag=$FLAG sgame=$SG +28=$(rd $((S + 0x28))) +60=$(rd $((S + 0x60)))"
    else
      echo "t=$n flag=$FLAG sgame=$SG"
    fi
  fi
  n=$((n+1)); $BB usleep 100000
done
echo "process gone"
