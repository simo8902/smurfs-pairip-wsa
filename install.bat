@echo off
rem Install PairIP-free Smurfs' Village 3.02.0 (778) on WSA.
rem WSA must be running with Developer mode on.
setlocal
set ADB=adb
where adb >nul 2>nul || set ADB=C:\sysinternals\adb.exe
set DEV=127.0.0.1:58526

%ADB% connect %DEV%
cd /d "%~dp0apk"
%ADB% -s %DEV% install-multiple -r base.apk config.arm64_v8a.apk config.en.apk config.xhdpi.apk game_assets.apk
if errorlevel 1 (
  echo.
  echo Install failed. If it says signatures do not match: uninstall Smurfs in WSA first,
  echo then run this again. Your progress comes back from the cloud save.
)
pause
