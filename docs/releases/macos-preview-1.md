# macOS Apple Silicon Preview 1

This release provides **New Super Paper Bros.app**, compiled natively for Apple Silicon with Metal rendering. It uses the **Europe revision 1 (R8PP01)** profile.

## Download and play

1. Download `NewSuperPaperBros-macOS-AppleSilicon-preview.zip` and extract it.
2. Open `New Super Paper Bros.app`. You can move it to Applications first.
3. Choose your own clean **Super Paper Mario Europe Rev 1** disc dump, or its extracted `sys` and `files` folders. The launcher verifies executable hashes before enabling Play.
4. Choose resolution, aspect ratio and language, then press Play.

Fresh profiles default to 1080p, 16:10 and Italian. English, French, German and Spanish are also available from the original PAL disc assets. F10 opens settings and controls; F11 toggles full screen. Some Mac keyboards require Fn.

The app imports the original disc assets locally; no disc image, imported Disc folder, personal settings or saves are bundled. The native engine contains translated game code and embedded executable initialization sections. The original matching disc is still required for its files.

## Included changes

- Native AppKit launcher and Pixl icon for the launcher and game.
- Internal resolution options through 4K, plus matching the display.
- A 16:10 Mac display mode with a top-anchored HUD: health and the flip meter on the left, score in the center, and coins on the right. Icons and digits move together; dialog boxes stay centered.
- PAL-specific function and SDK mappings, measured REL placement and original five-language localization.
- Persistent HD texture controls. Razius's partial 4× pack is optional and downloaded separately using `tools/macos/install-hd-textures.py` from the source archive. It is not included in this release.

The displayed app name no longer has a PAL suffix. Its internal PAL identifier and `~/Library/Application Support/NewSuperPaperBrosPAL` data directory are retained, so existing PAL saves, settings and installed textures continue to work. USA saves are separate.

## Requirements and limitations

Apple Silicon is required; no Intel executable is included. The build targets macOS 12 and later, but testing was performed on an M1 with macOS 26.6.2. The app is ad-hoc signed and is not Developer ID notarized.

This is an experimental preview. Verified: native build, 28/28 PAL SDK checks, translation without unsupported instructions or invalid SSA, targeted projection/configuration tests, original Italian menus, HD texture loading, first-level movement/jump/3D flip, 16:10 HUD alignment in 2D and 3D, launcher startup and return after quitting. The level tests use a developer warp and temporary saves. Full story progression, every chapter/effect, physical controllers and older macOS releases remain unverified.

## Source and checksums

`NewSuperPaperBros-macOS-source.zip` contains the port source and build scripts for this release. Building requires the matching personal disc input. Dependency licenses and notices are included in the app. `SHA256SUMS.txt` provides hashes for both archives.

See the [English macOS guide](https://github.com/mattsays/NewSuperPaperBros/blob/codex/native-macos-pal/tools/macos/README.md), [PAL adaptation notes](https://github.com/mattsays/NewSuperPaperBros/blob/codex/native-macos-pal/docs/macOS-PAL.md) and [PR #1](https://github.com/mattsays/NewSuperPaperBros/pull/1).
