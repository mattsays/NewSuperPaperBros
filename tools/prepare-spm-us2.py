#!/usr/bin/env python3
"""Prepare the experimental USA revision 2 profile from an extracted personal disc.

The runtime address manifest is derived from public revision-specific symbol maps.
Game binaries remain untracked; the original extraction is never modified.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WC = ROOT / 'wiicompiled'
DOL_SHA256 = '316fe3a88654cf55f164a493fdc7d872fb7362298613e335a2240b4921bfe7a0'
REL_SHA1 = 'd53d181f6da865e3d442d77076d16291e8341168'
SYMBOL_HASHES = {
    'symbols.txt': 'af5c157a247bd903357e8b5d9fe169034e93feb6d825b9fd2c223c560c39cd12',
    'relF/symbols.txt': '8eef0d30f2d21757da18b406f3d971f6c38fc011e4956d8c469f25013ff9f3cb',
}

def lz10(data):
    if data[0] != 0x10:
        raise ValueError('Expected an LZ10-compressed relF.bin')
    size = int.from_bytes(data[1:4], 'little')
    out = bytearray(); at = 4
    while len(out) < size:
        flags = data[at]; at += 1
        for bit in range(8):
            if len(out) >= size: break
            if flags & (0x80 >> bit):
                token = int.from_bytes(data[at:at+2], 'big'); at += 2
                for _ in range((token >> 12) + 3):
                    out.append(out[-((token & 4095) + 1)])
            else:
                out.append(data[at]); at += 1
    return bytes(out)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc-root', type=Path, required=True)
    parser.add_argument('--symbols-root', type=Path, required=True,
                        help='Pinned SeekyCt/spm-decomp checkout')
    parser.add_argument('--runtime-map', type=Path, required=True)
    parser.add_argument('--rel-base', type=lambda x: int(x, 0), default=0x80BF3F40)
    parser.add_argument('--bss-base', type=lambda x: int(x, 0))
    args = parser.parse_args()
    for name, expected in SYMBOL_HASHES.items():
        symbol_file = args.symbols_root / 'config/US2' / name
        if hashlib.sha256(symbol_file.read_bytes()).hexdigest() != expected:
            parser.error(f'Unexpected symbol map: {name}; use the documented pinned revision')
    disc = args.disc_root.resolve()
    dol = (disc / 'sys/main.dol').read_bytes()
    if hashlib.sha256(dol).hexdigest() != DOL_SHA256:
        parser.error('main.dol is not the verified clean USA revision 2 executable')
    compressed = (disc / 'files/rel/relF.bin').read_bytes()
    raw = lz10(compressed)
    if hashlib.sha1(raw).hexdigest() != REL_SHA1:
        parser.error('relF.bin is not the verified USA revision 2 module')
    # Measured from the linked module's section table during a clean Rev 2 boot.
    bss_base = args.bss_base if args.bss_base is not None else (args.rel_base + len(raw) + 31) & ~31
    game = ROOT / 'game/us2'; game.mkdir(parents=True, exist_ok=True)
    (game / 'main.dol').write_bytes(dol)
    (game / 'relF.bin').write_bytes(compressed)
    subprocess.run([sys.executable, str(WC / 'projects/spm/tools/prelink_spm_rel.py'),
                    str(game / 'relF.bin'), str(game / 'spm_linked.rel'),
                    str(game / 'spm_rel_layout.json'), hex(args.rel_base), hex(bss_base)], check=True)
    layout = json.loads((game / 'spm_rel_layout.json').read_text())
    manifest = json.loads(args.runtime_map.read_text())
    mapping = {int(k, 16): int(v['to'], 16) for k, v in manifest['mapped'].items()}
    # The new SDK splits/replaces these entry points; the public size sequence
    # alone cannot match their changed bodies. These are explicit entry points.
    mapping.update({0x802CC950: 0x802CD368, 0x802CE4C4: 0x802CEB4C,
                    0x802DE7B4: 0x802DF4F0, 0x80576720: 0x80576100,
                    0x80557218: 0x80558C18,  # Decoded from Rev 2 BTM_IsDeviceUp.
                    0x80BF6840: args.rel_base,
                    0x80F12640: int(layout['bss'], 16)})
    stage = WC / 'runtime-us2'
    stage.mkdir(exist_ok=True)
    token = re.compile(r'(?<![0-9a-fA-F])(?:0x)?(80[0-9a-fA-F]{6})(?![0-9a-fA-F])')
    for source in (WC / 'runtime').rglob('*'):
        rel = source.relative_to(WC / 'runtime'); target = stage / rel
        if source.is_dir():
            target.mkdir(exist_ok=True); continue
        if rel.parts[0] in ('third_party', 'assets') or source.suffix not in ('.h', '.hpp', '.cpp', '.inc'):
            shutil.copy2(source, target); continue
        text = source.read_text()
        def replace(match):
            old = int(match[1], 16)
            if old not in mapping: return match[0]
            digits = f'{mapping[old]:08X}'
            if match[1].islower(): digits = digits.lower()
            return ('0x' if match[0].startswith('0x') else '') + digits
        text = token.sub(replace, text)
        if rel.as_posix() == 'src/hle/input/wpad.cpp':
            # Rev 2 adds an outer WPAD initializer that enters WUD/USB before
            # reaching the original initializer. Both must use the same HLE
            # state; executing WUD on a host has no Wii USB device to talk to.
            text += '\nPPC_NATIVE_OVERRIDE(802CD578, WPADInit_HLE, int32_t, (), ());\n'
        if rel.as_posix() == 'src/hle/os/os_cache.cpp':
            text = re.sub(r'^(PPC_NATIVE_OVERRIDE_VOID\(8026D830[^\n]+)$',
                          r'#if 0 // DCStoreRange is not linked in USA revision 2.\n\1\n#endif',
                          text, flags=re.M)
        if not target.exists() or target.read_text() != text:
            target.write_text(text)
    project = WC / 'projects/spm-us2'; project.mkdir(exist_ok=True)
    rows = []
    for module, filename in [(False, 'symbols.txt'), (True, 'relF/symbols.txt')]:
        for line in (args.symbols_root / 'config/US2' / filename).read_text().splitlines():
            match = re.match(r'(\S+) = (\S+):0x([0-9A-Fa-f]+);.*type:function', line)
            if match:
                addr = int(match[3], 16)
                if module:
                    # .text offsets in the decomp symbol map start at zero;
                    # the module's section table records its actual file offset.
                    section_table = struct.unpack_from('>I', raw, 0x10)[0]
                    text_offset = struct.unpack_from('>I', raw, section_table + 8)[0] & ~1
                    addr += args.rel_base + text_offset
                rows.append((addr, match[1]))
    (project / 'MAP.txt').write_text(''.join(f'{a:08X} {n}\n' for a,n in sorted(set(rows))))
    config = (WC / 'projects/spm/recomp.yml').read_text()
    config = config.replace('R8PE01 rev 0', 'R8PE01 rev 2')
    config = config.replace('spm-r8pe01', 'spm-r8pe01-rev2')
    config = config.replace('Super Paper Mario (USA)', 'Super Paper Mario (USA Rev 2)')
    config = config.replace('../game/main.dol', '../game/us2/main.dol')
    config = config.replace('../game/spm_linked.rel', '../game/us2/spm_linked.rel')
    config = config.replace('cd3b5662f61369d5ff946098033be69de8084a20b0dfd3c3d4f4819eed6d21ac', DOL_SHA256)
    config = re.sub(r'sha256: (' + DOL_SHA256 + r').*', r'sha256: \1  # Clean USA Rev 2; original disc audio', config)
    config = config.replace('0x80574F20', '0x80574900').replace('0x80576280', '0x80575C60')
    config = config.replace('0x80BF6840', f'0x{args.rel_base:08X}')
    config = config.replace('bss 0x80F12640', 'bss ' + layout['bss'])
    config = config.replace('projects/spm/MAP.txt', 'projects/spm-us2/MAP.txt')
    config = config.replace('runtime/src', 'runtime-us2/src')
    (project / 'recomp.yml').write_text(config)
    print(f'Prepared {len(rows)} function entries; staged runtime: {stage}')
    print('Verify the boot module log reports MATCH for both image and BSS placement.')

if __name__ == '__main__':
    main()
