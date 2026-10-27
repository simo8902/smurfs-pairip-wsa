P=$(pidof "$PKG")
PKG="${1:?usage: pass the package name as arg 1}"
for t in /proc/$P/task/*; do
  set -- $(cat $t/stat)
  echo "${t##*/} $(cat $t/comm) utime=${14} stime=${15}"
done