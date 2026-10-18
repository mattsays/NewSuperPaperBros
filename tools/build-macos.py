#!/usr/bin/env python3
"""Build the native Apple Silicon preview from a personal USA Rev 2 or Europe Rev 1 disc dump."""
import argparse
from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WC = ROOT/'wiicompiled'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--game', type=Path)
    source.add_argument('--disc-root', type=Path)
    p.add_argument('--dotnet', default=shutil.which('dotnet'))
    p.add_argument('--nodtool', type=Path, required=True)
    p.add_argument('--symbols-root', type=Path, required=True,
                   help='SeekyCt/spm-decomp at bb6e5f6ef84e4b13808e317d687e8990f6fd7be6')
    p.add_argument('--build-dir', type=Path, default=WC/'native-build-macos-us2')
    p.add_argument('--output-dir', type=Path, default=ROOT/'dist/macos')
    p.add_argument('--jobs', type=int, default=2)
    p.add_argument('--rel-base')
    p.add_argument('--profile', choices=['us2', 'eu1'], default='us2')
    p.add_argument('--skip-translate', action='store_true')
    args = p.parse_args()
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        p.error('Run this build on an Apple Silicon Mac, outside Rosetta.')
    if args.jobs < 1: p.error('--jobs must be at least 1.')
    if not args.dotnet: p.error('A .NET 8 SDK is required; pass --dotnet /path/to/dotnet.')
    args.dotnet = str(Path(args.dotnet).resolve())
    for tool in ['cmake', 'ninja', 'clang', 'clang++', 'swiftc']:
        if not shutil.which(tool): p.error(f'Required build tool is missing: {tool}')
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT='1',
               DOTNET_CLI_HOME=str(ROOT/'toolchain/dotnet-state'),
               NUGET_PACKAGES=str(ROOT/'toolchain/nuget'))
    def run(command, cwd=ROOT):
        print('Running:', command[0], command[1] if len(command)>1 else '', flush=True)
        subprocess.run([str(x) for x in command], cwd=cwd, env=env, check=True)
    nodtool = args.nodtool.resolve()
    disc = args.disc_root.resolve() if args.disc_root else ROOT/('Disc/macOS-' + args.profile)
    args.rel_base = args.rel_base or ('0x80C464E0' if args.profile == 'eu1' else '0x80BF3F40')
    if args.game and not (disc/'sys/main.dol').exists():
        run([nodtool, 'extract', '-q', args.game.resolve(), disc])
    if not args.skip_translate:
        run([sys.executable, ROOT/f'tools/prepare-spm-{args.profile}.py', '--disc-root', disc,
             '--symbols-root', args.symbols_root.resolve(), '--runtime-map',
             ROOT/f'tools/macos/spm-{args.profile}-addresses.json', '--rel-base', args.rel_base])
        run([sys.executable, ROOT/f'tools/macos/verify-{args.profile}-sdk.py', '--disc-root', disc])
        run([args.dotnet, 'build', WC/'translator/src/Translator.Cli/Translator.Cli.csproj', '-c', 'Release'])
        cli = [args.dotnet, WC/'translator/src/Translator.Cli/bin/Release/net8.0/Translator.Cli.dll']
        project = ['--project', f'projects/spm-{args.profile}/recomp.yml']
        run(cli+['translate-recursive', '0x80006124']+project+[
            '--outdir', 'generated/functions', '--output-metadata', 'generated/base_translation_output.json',
            '--production-source-bundle', 'generated/base_translation_sources.bin', '--no-function-files',
            '--prune-stale', '--threads', str(args.jobs)], cwd=WC)
        run(cli+['emit-base-manifest']+project+['--out', 'build/base', '--functions-dir', 'generated/functions',
            '--translation-output-metadata', 'generated/base_translation_output.json', '--region', 'P' if args.profile == 'eu1' else 'E'], cwd=WC)
        run(cli+['generate-data-init']+project, cwd=WC)
        run(cli+['emit-build-shards']+project+['--base-metadata', 'generated/base_translation_output.json',
            '--base-functions-dir', 'generated/functions', '--native-source-dir', f'runtime-{args.profile}/src',
            '--out', 'generated/build_shards'], cwd=WC)
    build = args.build_dir.resolve()
    if args.profile == 'eu1' and args.build_dir == WC/'native-build-macos-us2':
        build = WC/'native-build-macos-eu1'
    run(['cmake', '-S', WC/f'runtime-{args.profile}', '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
         '-DCMAKE_C_COMPILER=clang', '-DCMAKE_CXX_COMPILER=clang++', '-DCMAKE_OSX_ARCHITECTURES=arm64',
         '-DAURORA_SDL3_PROVIDER=vendor', '-DCMAKE_DISABLE_FIND_PACKAGE_PNG=TRUE',
         '-DCMAKE_DISABLE_FIND_PACKAGE_Freetype=TRUE', '-DFT_DISABLE_BZIP2=ON',
         f'-DMKW_TRANSLATED_COMPILE_JOBS={args.jobs}'])
    run(['cmake', '--build', build, '--target', 'WiiCompiled', '--parallel', str(args.jobs)])
    run([sys.executable, ROOT/'tools/macos/package-app.py', '--build-dir', build,
         '--nodtool', nodtool, '--profile', args.profile, '--output-dir', args.output_dir.resolve()])

if __name__ == '__main__': main()
