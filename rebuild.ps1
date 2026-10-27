<#
Rebuild the PairIP-free, GL-accelerated Smurfs' Village splits from scratch.

Inputs you supply (none are in this repo):
  -Orig      folder holding the 5 ORIGINAL splits you own:
             base.apk config.arm64_v8a.apk config.en.apk config.xhdpi.apk game_assets.apk
  -Keystore  a keystore to sign with (any; all splits get the same cert)
  -StorePass / -KeyPass / -Alias   its credentials
  -Out       output folder for the signed splits (default .\out)

Tooling (override if not on PATH / default location):
  -ApktoolJar   path to apktool.jar
  -BuildTools   Android build-tools dir containing zipalign.exe + apksigner.bat
  -Python       python with pyelftools + keystone-engine + capstone

All game-specific data comes from game\profile_3_02_0.py. Everything else is generic.
#>
param(
  [Parameter(Mandatory=$true)][string]$Orig,
  [Parameter(Mandatory=$true)][string]$Keystore,
  [string]$StorePass = "smurfs123",
  [string]$KeyPass   = "smurfs123",
  [string]$Alias     = "smurfs",
  [string]$Out       = "$PSScriptRoot\out",
  [string]$ApktoolJar = "C:\Windows\apktool.jar",
  [string]$BuildTools = "",
  [string]$Python     = "python"
)
$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$profile = Join-Path $repo "game\profile_3_02_0.py"
$tools = Join-Path $repo "tools"
$work = Join-Path $repo "_build"
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
New-Item -ItemType Directory -Force $work, $Out | Out-Null

function P($expr) { & $Python -I -c "import importlib.util as u;s=u.spec_from_file_location('p',r'$profile');m=u.module_from_spec(s);s.loader.exec_module(m);print($expr)" }
$arm64 = P "m.ARM64_SPLIT"
$libpath = P "m.LIB_PATH"
$splits = (P "' '.join(m.SPLITS)").Split(" ")
$wrapCls = (P "' '.join(m.WRAP_CLASSES)").Split(" ")

Write-Host "== 1. decompile base.apk ==" -ForegroundColor Cyan
$base = Join-Path $work "base"
& java -jar $ApktoolJar d -f -o $base (Join-Path $Orig "base.apk")

Write-Host "== 2. normalise smali/manifest to LF ==" -ForegroundColor Cyan
Get-ChildItem -Recurse $base -Include *.smali,AndroidManifest.xml | ForEach-Object {
  $t = [IO.File]::ReadAllText($_.FullName).Replace("`r`n","`n")
  [IO.File]::WriteAllText($_.FullName, $t)
}

Write-Host "== 3. generic transforms ==" -ForegroundColor Cyan
& $Python -I (Join-Path $tools "patch_strings.py") $base
& $Python -I (Join-Path $tools "wrap_fromnative.py") $base
foreach ($c in $wrapCls) { & $Python -I (Join-Path $tools "wrap_fromnative.py") $base $c }

Write-Host "== 4. apply game-specific smali/manifest edits ==" -ForegroundColor Cyan
& $Python -I (Join-Path $tools "apply_patch.py") $base $profile

Write-Host "== 5. build + native lib ==" -ForegroundColor Cyan
$baseRebuilt = Join-Path $work "base_rebuilt.apk"
& java -jar $ApktoolJar b $base -o $baseRebuilt
$origLib = Join-Path $work "orig_libSmurfsAndroid.so"
& $Python -I -c "import zipfile,sys;open(r'$origLib','wb').write(zipfile.ZipFile(r'$(Join-Path $Orig $arm64)').read('$libpath'))"
$newLib = Join-Path $work "libSmurfsAndroid.so"
& $Python -I (Join-Path $tools "build_native.py") $origLib $newLib $profile
$arm64Unsigned = Join-Path $work "arm64_unsigned.apk"
& $Python -I (Join-Path $tools "repack.py") (Join-Path $Orig $arm64) $newLib $arm64Unsigned $libpath

Write-Host "== 6. align + sign all splits ==" -ForegroundColor Cyan
if (-not $BuildTools) { throw "pass -BuildTools <android build-tools dir with zipalign.exe + apksigner.bat>" }
$zipalign = Join-Path $BuildTools "zipalign.exe"
$apksigner = Join-Path $BuildTools "apksigner.bat"
function SignTo($inApk, $outName) {
  $aligned = Join-Path $work ("al_" + $outName)
  & $zipalign -f -p 4 $inApk $aligned
  $final = Join-Path $Out $outName
  Copy-Item $aligned $final -Force
  & $apksigner sign --ks $Keystore --ks-pass "pass:$StorePass" --key-pass "pass:$KeyPass" --ks-key-alias $Alias `
      --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled false $final
  Remove-Item ($final + ".idsig") -ErrorAction SilentlyContinue
}
SignTo $baseRebuilt "base.apk"
SignTo $arm64Unsigned $arm64
foreach ($s in $splits) {
  if ($s -eq "base.apk" -or $s -eq $arm64) { continue }
  SignTo (Join-Path $Orig $s) $s     # re-sign the untouched splits with the same cert
}

Write-Host "`nDONE. Signed splits in $Out" -ForegroundColor Green
Write-Host "Install on WSA:  adb install-multiple -r $Out\*.apk"
