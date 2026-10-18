For the Europe revision 1 profile, Italian localization, 16:10 and HD pack setup, see [macOS/PAL documentation](../../docs/macOS-PAL.md).

# Native macOS preview: USA revision 2

This branch extends NewSuperPaperBros v1.0.2 (`abcaf268713c6e709f4773e90f1987b5369fc3cd`) with a native Apple Silicon build, an AppKit launcher, personal-disc import and a separate USA revision 2 recompilation profile. It uses the existing Metal renderer and native runtime. No external emulator is required.

The preview was tested on an Apple M1 with 16 GB RAM and macOS 26.6.2. The deployment target is macOS 12, but older macOS releases have not been tested. Intel builds are not included.

## Playing

Open `New Super Paper Bros.app`. Choose a personal Super Paper Mario **USA revision 2** RVZ/ISO/WBFS/CISO image, or an extracted folder containing `sys` and `files`. The launcher checks executable hashes before enabling Play. Other revisions and patched game executables are rejected.

The app stores settings, saves and imported disc files in `~/Library/Application Support/NewSuperPaperBros`. An extracted folder selected directly remains in its original location. The original disc image is never modified. Importing another image replaces only the launcher's own `Disc` extraction and preserves saves. The launcher has buttons for saves, mods and logs.

Default controls:

| Action | Keyboard |
| --- | --- |
| Move | Arrow keys |
| Jump / confirm (Wii 2) | Space or X |
| Wii 1 | Z or Left Shift |
| Flip (Wii A) | A |
| Shake | C or Left Control |
| Tilt | Q / E |
| Pause (+) | Return or Escape |
| Minus | Minus or Tab |
| Settings / change bindings | F10 |
| Full screen | F11 |

Some Mac keyboards require Fn with function keys. Physical controllers are supported by the upstream runtime but were not tested in this preview.

The native launcher has a Resolution menu for 480p, 720p, 1080p, 1440p, 4K (2160p), or Match screen (Retina backing pixels). It saves the choice immediately and applies it on the next game launch; F10 → Resolution changes it during play. The launcher reloads changes made in game when the game closes, and preserves advanced values chosen there. Fresh profiles default to 1080p; existing profiles keep their resolution. Higher internal resolution sharpens rendered geometry; it does not replace the original textures.

Both the launcher and nested game app use a native Mac icon converted from the project’s existing `launcher/pixl.ico` artwork. `package-app.py` generates all standard and Retina sizes with Apple’s tools and sets both bundle icon entries before signing.

Fresh profiles use Metal, windowed display, 16:10 and no frame interpolation. The aspect menu also offers 16:9, original 4:3, Fill and Cinematic, preserving existing choices. The clean disc's audio is used. Razius HD textures can be installed separately with `install-hd-textures.py`; the launcher then offers a persistent toggle. Neither the pack nor the Windows setup script's HQ audio modifications are bundled. This local app is ad-hoc signed, without Developer ID notarization.

In 16:10 the HUD retains its original top inset: health and the flip meter stay on the left, score in the center, and coins on the right. Icons and digits move together without resizing. The adjustment is scoped to the game's HUD draw calls, including nested helpers, and accounts for their perspective depth. Centered dialogs, menus, world geometry and other aspect modes are unaffected.

## Building

Requirements: Apple Silicon Mac, Apple command line developer tools including Swift, Python 3, CMake, Ninja, .NET 8 SDK, and the official `encounter/nod` nodtool v2.0.0-alpha.10 for macOS ARM64. These are development dependencies; the packaged game does not need .NET, Python, CMake, Ninja or Homebrew installed.

Obtain the public symbol maps from `SeekyCt/spm-decomp`, pinned to commit `bb6e5f6ef84e4b13808e317d687e8990f6fd7be6`. The preparation script verifies the hashes of `config/US2/symbols.txt` and `config/US2/relF/symbols.txt`; an arbitrary newer checkout is not a substitute.

From the repository root:

```sh
python3 tools/build-macos.py \
  --game "/absolute/path/Super Paper Mario (USA) (Rev 2).rvz" \
  --dotnet /absolute/path/to/dotnet \
  --nodtool /absolute/path/to/nodtool \
  --symbols-root /absolute/path/to/spm-decomp \
  --jobs 2
```

The output is `dist/macos/New Super Paper Bros.app`. Use absolute tool paths. The first translated-code build took about 28 minutes on the test M1; allow several GB of working space. The script downloads native dependencies through the upstream build system. PNG and Freetype are built from source to avoid dependencies on a host's Homebrew installation. The app bundles its required PNG library and nodtool.

`--disc-root` can replace `--game` for an already extracted image. `--build-dir` and `--output-dir` select other destinations. `--skip-translate` is for rebuilding an already prepared checkout; it requires existing `runtime-us2`, game inputs and generated sources.

Generated files, private disc inputs and translated game sources are ignored by Git. The source archive contains the port's source changes and public symbol names, without the disc extraction or generated game code. Building requires the user's own matching game.

## Revision adaptation

The accepted main DOL SHA-256 is `316fe3a88654cf55f164a493fdc7d872fb7362298613e335a2240b4921bfe7a0`. Compressed `files/rel/relF.bin` must match `24920508fb790854d3191c0caa6f6434efcf948b0656f15bb8236cd81cb060f6`. The decompressed REL SHA-1 is `d53d181f6da865e3d442d77076d16291e8341168`. The partition's boot header reports revision 0 even for this revision 2 dump, so that byte is not used to identify executable compatibility.

`prepare-spm-us2.py` stages a separate runtime from the upstream revision 0 runtime and applies `spm-us2-addresses.json`. The map was derived from matching public US0/US2 symbol names and monotonic same-type/same-size sequences. Not every inferred internal address is independently proven; this remains an experimental revision profile. `verify-us2-sdk.py` independently checks 28 essential SDK addresses against instructions in the actual DOL.

Runtime observations established the actual loaded REL image at `0x80BF3F40` and BSS at `0x80F0FE20`. Earlier layout guesses booted menus but failed at the game's map prolog. These exact bases now match the runtime loader, including prolog `0x80C3205C`. Small-data bases are r13=`0x80574900` and r2=`0x80575C60`.

Revision 2's outer WPAD initializer at `0x802CD578` must enter the existing native WPAD implementation; otherwise boot enters unsupported Wii USB initialization. The preparation script adds that binding only to the staged revision 2 runtime. It also adapts direct native function bindings and disables an override for a function absent from revision 2. The upstream revision 0 project remains separate.

## Verification and limits

Verified: clean extraction and hashes; 28/28 SDK instruction checks; translation with no reported unsupported instructions or invalid SSA; native ARM64 compilation; matching REL placement; title screen; a temporary save write and subsequent reload; Flipside and chapter 1 map loading; movement, jump and the 3D flip; rendered screenshots; native audio initialization with nonzero samples; launcher Play, keyboard start, F10 settings and normal quit through the actual Mac UI; ad-hoc signature verification and dependency packaging.

Short normal-render tests reached about 60 guest frames per second. That is not a full-game performance guarantee. A separate Metal validation run produced no reported validation error but stalled its presented-frame counter in a town event; the normal-render chapter test continued through movement and flipping. Full-game progression, lengthy cutscenes, all items and chapters, physical controllers, older macOS releases, Intel and optional mod packs remain unverified. The temporary test save is not installed into the player's profile.

For developer verification, the engine supports `SPM_CAPTURE_PATH=/absolute/frame.bmp` and `SPM_CAPTURE_FRAME=1200` to capture its own rendered output. The launcher supports `--install-game PATH` for local setup. These are test hooks, not required for normal use.
