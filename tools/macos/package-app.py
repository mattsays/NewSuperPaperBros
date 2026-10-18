#!/usr/bin/env python3
"""Package the local ARM64 engine and native launcher into a relocatable Mac app."""
import argparse
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

def build_icon(destination, scratch):
    """Convert the project's existing Pixl icon to the standard Retina Mac icon set."""
    iconset = scratch/'AppIcon.iconset'
    iconset.mkdir()
    for points in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            suffix = '@2x' if scale == 2 else ''
            pixels = str(points * scale)
            subprocess.run(['sips', '-s', 'format', 'png', '-z', pixels, pixels,
                            str(ROOT/'launcher/pixl.ico'), '--out',
                            str(iconset/f'icon_{points}x{points}{suffix}.png')],
                           check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(destination)], check=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--nodtool', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--launcher', type=Path)
    parser.add_argument('--profile', choices=['us2', 'eu1'], default='us2')
    args = parser.parse_args()
    pal = args.profile == 'eu1'
    app_name = 'New Super Paper Bros PAL' if pal else 'New Super Paper Bros'
    bundle_id = 'org.newsuperpaperbros.macos.pal' if pal else 'org.newsuperpaperbros.macos'
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nspb-package-', dir=args.output_dir) as scratch:
        scratch = Path(scratch)
        subprocess.run(['bash', str(ROOT/'wiicompiled/Launcher/macos/publish-app.command'),
                        '--build-dir', str(args.build_dir.resolve()), '--product', 'WiiCompiled',
                        '--output-dir', str(scratch), '--architecture', 'arm64'], check=True)
        app = scratch/(app_name + '.app'); contents = app/'Contents'
        (contents/'MacOS').mkdir(parents=True)
        (contents/'Resources').mkdir()
        build_icon(contents/'Resources/AppIcon.icns', scratch)
        helpers = contents/'Helpers'; helpers.mkdir()
        engine = helpers/'Game.app'
        shutil.move(str(scratch/'WiiCompiled.app'), engine)
        engine_contents = engine/'Contents'
        shutil.copy2(contents/'Resources/AppIcon.icns', engine_contents/'Resources/AppIcon.icns')
        (engine_contents/'MacOS/WiiCompiled').rename(engine_contents/'MacOS/nspb-engine')
        engine_info = engine_contents/'Info.plist'
        with engine_info.open('rb') as handle: values = plistlib.load(handle)
        values.update(CFBundleExecutable='nspb-engine', CFBundleIdentifier=bundle_id + '.game',
                      CFBundleName=app_name + ' Game', CFBundleDisplayName=app_name + ' Game',
                      CFBundleIconFile='AppIcon.icns', CFBundleShortVersionString='1.0.2', CFBundleVersion='10204')
        with engine_info.open('wb') as handle: plistlib.dump(values, handle)
        launcher = contents/'MacOS/NSPBLauncher'
        if args.launcher:
            shutil.copy2(args.launcher, launcher)
        else:
            subprocess.run(['swiftc', '-swift-version', '5', '-O'] + (['-D', 'PAL_BUILD'] if pal else []) + [
                            '-target', 'arm64-apple-macos12', '-module-cache-path', str(scratch/'swift-cache'),
                            str(ROOT/'tools/macos/Launcher.swift'), '-o', str(launcher)], check=True)
        shutil.copy2(args.nodtool, helpers/'nodtool')
        (helpers/'nodtool').chmod(0o755)
        info = contents/'Info.plist'
        values = dict(values)
        values.update(CFBundleExecutable='NSPBLauncher', CFBundleIdentifier=bundle_id,
                      CFBundleName=app_name, CFBundleDisplayName=app_name,
                      CFBundleShortVersionString='1.0.2', CFBundleVersion='10204', CFBundleIconFile='AppIcon.icns',
                      NSHumanReadableCopyright='Unofficial native macOS preview. Bring your own disc.',
                      NSBluetoothAlwaysUsageDescription='Connect a game controller to play.',
                      LSApplicationCategoryType='public.app-category.games')
        with info.open('wb') as handle: plistlib.dump(values, handle)
        licenses = contents/'Resources/Licenses'; licenses.mkdir(parents=True)
        for source in [ROOT/'wiicompiled/LICENSE', ROOT/'wiicompiled/THIRD-PARTY-NOTICES.md', ROOT/'tools/CREDITS.txt']:
            shutil.copy2(source, licenses/source.name)
        shutil.copy2(ROOT/'tools/macos/nod-LICENSE-MIT', licenses/'nod-LICENSE-MIT')
        # FetchContent may use sources from another checkout through CMake cache overrides.
        dependency_roots = set(args.build_dir.glob('_deps/*-src'))
        cache = args.build_dir/'CMakeCache.txt'
        if cache.exists():
            for line in cache.read_text().splitlines():
                key, separator, value = line.partition('=')
                if separator and value and ('_SOURCE_DIR:' in key or key.startswith('FETCHCONTENT_SOURCE_DIR_')):
                    dependency_roots.add(Path(value))
        for source_root in sorted(dependency_roots):
            if not source_root.is_dir() or source_root in [ROOT/'wiicompiled/runtime-us2', ROOT/'wiicompiled/runtime-eu1']: continue
            candidates = list(source_root.glob('*')) + list((source_root/'docs').glob('*'))
            for source in candidates:
                if source.is_file() and (source.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')) or source.name == 'FTL.TXT'):
                    target = licenses/source_root.name/source.name
                    target.parent.mkdir(exist_ok=True)
                    shutil.copy2(source, target)
        (contents/'Resources/Mac Preview.txt').write_text(
            ('Native Apple Silicon preview for Super Paper Mario Europe revision 1.\n' if pal else
             'Native Apple Silicon preview for Super Paper Mario USA revision 2.\n') +
            'Choose a personal RVZ/ISO/WBFS/CISO dump or an extracted game folder.\n'
            'Game data is not included in this application.\n' +
            ('Settings and saves: ~/Library/Application Support/NewSuperPaperBrosPAL\n' if pal else
             'Settings and saves: ~/Library/Application Support/NewSuperPaperBros\n') +
            'F10 opens settings; F11 switches full screen.\n'
            'This local build is ad-hoc signed, not notarized.\n')
        subprocess.run(['codesign', '--force', '--sign', '-', str(helpers/'nodtool')], check=True)
        subprocess.run(['codesign', '--force', '--sign', '-', str(engine_contents/'MacOS/nspb-engine')], check=True)
        subprocess.run(['codesign', '--force', '--sign', '-', str(engine)], check=True)
        subprocess.run(['codesign', '--force', '--sign', '-', str(launcher)], check=True)
        subprocess.run(['codesign', '--force', '--sign', '-', str(app)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
        destination = args.output_dir/(app_name + '.app')
        if destination.exists(): shutil.rmtree(destination)
        shutil.move(str(app), str(destination))
        print(destination)

if __name__ == '__main__': main()
