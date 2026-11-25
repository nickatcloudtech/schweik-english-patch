# qdEngine — build notes (original)

© KD Vision LLC (Kaliningrad)

All code, except third-party libraries, is published under the GPLv3 license. Third-party library code (where a different license is noted) is published under those libraries' licenses.

Community chat: https://t.me/kdlab_association_chat

## Structure

- `src/XLibs` — XLibs library
- `src/QD` — game source code

## Runtime status

The engine runs with assets from *The Adventures of the Good Soldier Schweik* (1C, 2007), but behavior is unstable.

## Requirements

At present the engine builds for the `Debug` configuration on Windows 10 + VS 2003 SP1.

## Step-by-step build instructions

1. In `src/XLibs`, run `build.bat` as administrator
   - Build output will be placed in `C:\XLibs`
2. Open `src\QD\Core\qdEngine.sln` in VS 2003, select the `qdEngine` project, choose `Rebuild` — this should trigger a sequential build of `qdEngineCore` and `qdEngine`
   - `Debug` build output: `src\QD\bin\dbg\qd_gameDBG.exe`

## Known issues

1. If you get "missing lib" errors, build the corresponding libraries from XLibs
2. If the build complains about a missing `stlportd_static.5.0.lib`, go to `c:\XLibs\VC7.1\` and copy `stlportd_static.5.1.lib` to `stlportd_static.5.0.lib`

## Key changes

1. Added `class MpegSound`; removed dependency on `__int64 getRDTSC()`
2. Removed use of `auto_ptr`
3. Fixed incompatibility with `XZipArchive`
4. Added missing header and `.lib` files in `XLibs/Heap`