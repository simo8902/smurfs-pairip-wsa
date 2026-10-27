# smurfs-wsa-fix

Rebuild a PairIP-free, GL-accelerated build of Smurfs' Village **3.02.0 (778)**
(arm64) for Windows Subsystem for Android, **from scratch on a clean checkout**.

Private backup. Runs ~60–70 fps in the village (stock PairIP build fails to
launch on any PC Android layer; once patched it was GPU-round-trip bound at
~16 fps until the GL hooks).

## Design: one game file, everything else generic

All copyright-derived content lives in a single file:

> **`game/profile_3_02_0.py`** — the bytes PairIP decrypts at runtime (recovered
> from a memory dump of a device the owner controls), this build's virtual
> addresses, the GOT slot→libc map, and the smali/AndroidManifest edits (as a
> unified diff). Nothing else in the repo contains game code, strings or assets.

Every file under `tools/` and `rebuild.ps1` is generic: it operates on inputs
*you* supply (your own copy of the game) plus that one profile. You bring:

- the 5 original splits you own: `base.apk`, `config.arm64_v8a.apk`,
  `config.en.apk`, `config.xhdpi.apk`, `game_assets.apk`
- a keystore to sign with
- `apktool`, Android build-tools (`zipalign`, `apksigner`), a JRE, and
  `python` with `pyelftools keystone-engine capstone`

## Rebuild

```powershell
./rebuild.ps1 -Orig C:\path\to\original\splits `
              -Keystore C:\path\to\my.keystore -Alias myalias `
              -StorePass ****  -KeyPass **** `
              -BuildTools C:\path\to\android\build-tools\android-14 `
              -ApktoolJar C:\path\to\apktool.jar
# -> signed splits in .\out ; install with:
adb install-multiple -r .\out\*.apk
```

What it does (all generic, driven by the profile):
1. `apktool d` the base, normalise smali/manifest to LF.
2. Generic transforms: `patch_strings.py` (default every PairIP-stripped
   `String` field to `""`) and `wrap_fromnative.py` (wrap JNI callbacks, and the
   ad/SDK classes in `profile.WRAP_CLASSES`, in try/catch).
3. `apply_patch.py` applies the profile's smali + manifest diff (the PairIP
   neuters, restored string values, AppLovin disable, manifest removals).
4. `apktool b`; `build_native.py` rebuilds the native lib from the original +
   profile (splice decrypted bytes, DT_INIT dlsym stub + WSA GL fast-paths, drop
   `libpairipcore`); `repack.py` puts it in the arm64 split.
5. Align + sign all five splits with your key.

## Reproducibility (verified)

- `build_native.py` + profile reproduce the known-good native library
  **byte-for-byte**.
- The generic transforms + `apply_patch.py` reproduce the working smali/manifest
  tree **exactly** (16 files, 0 diffs).

## Files

```
game/profile_3_02_0.py   the ONE game-specific file (decrypted bytes, addresses, smali/manifest diff)
rebuild.ps1              end-to-end driver
tools/
  build_native.py        generic: original lib + profile -> standalone lib
  apply_patch.py         generic: apply the profile's unified diff (pure python)
  patch_strings.py       generic: default stripped String fields to ""
  wrap_fromnative.py     generic: wrap JNI callbacks / named classes in try/catch
  repack.py              generic: swap a .so into a split, drop old signature
  freeze_profile.py      how the profile's native half was derived (provenance)
  phone_dump*.sh         re-dump decrypted memory from a rooted device (new versions)
  diffimg.py classify.py slots.py names.py   analysis to re-derive a profile (new versions)
  wsa_probe.sh bufstat.sh threads.sh         runtime diagnostics
install.bat              install the five signed splits on WSA
```

The device/analysis scripts take the package name as an argument; the core
rebuild path needs no edits.

## Works / doesn't

- Works: game, village, Google Play Games cloud save.
- Broken by design/limitation: in-app purchases (Play Billing rejects the
  re-signed app), ads (AppLovin disabled), Facebook login.

## Scope

Specific to **3.02.0 (778)** arm64. A new game version needs a fresh rooted-phone
dump (`tools/phone_dump2.sh`) and a re-derived profile (the analysis scripts).
For personal use with a game you own. See [LICENSE](LICENSE) — covers the scripts
only, grants no rights to the game.
