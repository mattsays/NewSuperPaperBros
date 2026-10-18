#!/usr/bin/env python3
"""Install the pinned Razius 4x texture pack into a local Mac preview profile."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

URL = 'https://files.emulationking.com/wii/texturepacks/superpapermario/razius/Super-Paper-Mario-HD-Texture-Pack-Razius-4x-DDS.7z'
SHA256 = '0d6487afa9d15ef9600d3f7dcaa4e760b0412833a4764f5e2a4e6a5de7e6d2c8'
AUTHOR = 'https://www.emutalk.net/threads/super-paper-mario.55330/'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True, help='Path to New Super Paper Bros.app')
    parser.add_argument('--archive', type=Path, help='Use an already downloaded copy of the pinned archive')
    args = parser.parse_args()
    launcher = args.app.resolve()/'Contents/MacOS/NSPBLauncher'
    if not launcher.is_file(): parser.error('The app launcher was not found.')
    tar = shutil.which('bsdtar') or shutil.which('tar')
    if not tar: parser.error('Apple tar/libarchive is required.')
    with tempfile.TemporaryDirectory(prefix='spm-hd-') as temporary:
        temporary = Path(temporary)
        archive = args.archive or temporary/'SPM-HD-Razius-4x.7z'
        if args.archive is None:
            print('Downloading Razius 4x DDS textures (about 24 MiB)...', flush=True)
            urllib.request.urlretrieve(URL, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
            parser.error('The archive does not match the verified texture pack.')
        listing = subprocess.check_output([tar, '-tf', str(archive)], text=True).splitlines()
        if any(Path(name).is_absolute() or '..' in Path(name).parts for name in listing):
            parser.error('Unsafe archive path.')
        extracted = temporary/'textures'; extracted.mkdir()
        subprocess.run([tar, '-xf', str(archive), '-C', str(extracted)], check=True)
        subprocess.run([str(launcher), '--install-textures', str(extracted)], check=True)
    print('Installed and enabled. Restart the game to load the textures.')
    print('Artist: Razius. Original project:', AUTHOR)
    print('This is a partial pack; localized PAL artwork without a matching replacement stays original.')

if __name__ == '__main__': main()
