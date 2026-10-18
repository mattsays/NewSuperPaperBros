#!/usr/bin/env python3
"""Prepare the experimental Europe revision 1 profile from an extracted personal disc.

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
DOL_SHA256 = 'c853aafb4beb7504d5ab8c81445c3dc7cc244a4486c70d9eaed71639c41049cf'
REL_SHA1 = '29c78007559996dee6b615005fa3369d4cc1f5e3'
SYMBOL_HASHES = {
    'symbols.txt': '0882cccdff4200def873f883bb8118c17bac77db21d99b4d2e3beaf3c086f5a9',
    'relF/symbols.txt': '12106631726e7460bc4090d6d5680027be2d8020057f9c54dd68e48b7a8e7128',
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
    parser.add_argument('--rel-base', type=lambda x: int(x, 0), default=0x80C464E0)
    parser.add_argument('--bss-base', type=lambda x: int(x, 0))
    args = parser.parse_args()
    for name, expected in SYMBOL_HASHES.items():
        symbol_file = args.symbols_root / 'config/EU0' / name
        if hashlib.sha256(symbol_file.read_bytes()).hexdigest() != expected:
            parser.error(f'Unexpected symbol map: {name}; use the documented pinned revision')
    disc = args.disc_root.resolve()
    dol = (disc / 'sys/main.dol').read_bytes()
    if hashlib.sha256(dol).hexdigest() != DOL_SHA256:
        parser.error('main.dol is not the verified clean Europe revision 1 executable')
    compressed = (disc / 'files/rel/relF.bin').read_bytes()
    raw = lz10(compressed)
    if hashlib.sha1(raw).hexdigest() != REL_SHA1:
        parser.error('relF.bin is not the verified Europe revision 1 module')
    # Measured from the linked module's section table during a clean PAL Rev 1 boot.
    bss_base = args.bss_base if args.bss_base is not None else (args.rel_base + len(raw) + 31) & ~31
    game = ROOT / 'game/eu1'; game.mkdir(parents=True, exist_ok=True)
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
    mapping.update({0x802CC950: 0x802CF418, 0x802CE4C4: 0x802D0C50,
                    0x802DE7B4: 0x802E15A0, 0x80576720: 0x805C7740,
                    0x80557218: 0x805AA218,  # Decoded from PAL Rev 1 BTM_IsDeviceUp.
                    0x8056D0D8: 0x805AE0B8,  # now_seq, named in PAL symbols.
                    0x8056D0DC: 0x805AE0BC,  # next_seq.
                    0x8056D1C0: 0x805AE1A0,  # REL state, preserved SDA-relative slot.
                    0x8056D198: 0x805AE178,  # gp, named in PAL symbols.
                    0x8056D1B8: 0x805AE198,  # adjacent pad state, same SDA-relative slot.
                    0x80BF6840: args.rel_base,
                    0x80F12640: int(layout['bss'], 16)})
    stage = WC / 'runtime-eu1'
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
        text = text.replace('0x52385045', '0x52385050').replace('R8PE01', 'R8PP01')
        if rel.as_posix() == 'src/hle/sc.cpp':
            text += '''
// The PAL disc contains its own five translations. Select the Wii language code
// through the launcher's environment, without modifying any game assets.
extern "C" uint32_t PAL_SCGetLanguage() {
    const char* language = std::getenv("SPM_LANGUAGE");
    if (language && std::strcmp(language, "en") == 0) return 1;
    if (language && std::strcmp(language, "de") == 0) return 2;
    if (language && std::strcmp(language, "fr") == 0) return 3;
    if (language && std::strcmp(language, "es") == 0) return 4;
    return 5; // SC_LANGUAGE_IT, wii/sc.h
}
PPC_NATIVE_OVERRIDE(8029E2C8, PAL_SCGetLanguage, uint32_t, (), ());
'''

        if rel.as_posix() == 'include/runtime_config.h':
            text = text.replace('NewSuperPaperBros', 'NewSuperPaperBrosPAL')
        if rel.as_posix() == 'src/hle/input/wpad.cpp':
            # PAL Rev 1 adds an outer WPAD initializer that enters WUD/USB before
            # reaching the original initializer. Both must use the same HLE
            # state; executing WUD on a host has no Wii USB device to talk to.
            text += '\nPPC_NATIVE_OVERRIDE(802CF628, WPADInit_HLE, int32_t, (), ());\n'
        if rel.as_posix() == 'src/hle/os/os_cache.cpp':
            text = re.sub(r'^(PPC_NATIVE_OVERRIDE_VOID\(8026D830[^\n]+)$',
                          r'#if 0 // DCStoreRange is not linked in Europe revision 1.\n\1\n#endif',
                          text, flags=re.M)
        if not target.exists() or target.read_text() != text:
            target.write_text(text)
    project = WC / 'projects/spm-eu1'; project.mkdir(exist_ok=True)
    rows = []
    for module, filename in [(False, 'symbols.txt'), (True, 'relF/symbols.txt')]:
        for line in (args.symbols_root / 'config/EU0' / filename).read_text().splitlines():
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
    config = config.replace('North America (R8PE01 rev 0)', 'Europe (R8PP01 rev 1)')
    config = config.replace('spm-r8pe01', 'spm-r8pp01-rev1').replace('game_id: R8PE01', 'game_id: R8PP01').replace('region: E', 'region: P')
    config = config.replace('Super Paper Mario (USA)', 'Super Paper Mario (Europe Rev 1)')
    config = config.replace('region: E', 'region: P').replace('game_id: R8PE01', 'game_id: R8PP01')
    config = config.replace('../game/main.dol', '../game/eu1/main.dol')
    config = config.replace('../game/spm_linked.rel', '../game/eu1/spm_linked.rel')
    config = config.replace('cd3b5662f61369d5ff946098033be69de8084a20b0dfd3c3d4f4819eed6d21ac', DOL_SHA256)
    config = re.sub(r'sha256: (' + DOL_SHA256 + r').*', r'sha256: \1  # Clean Europe Rev 1; original disc audio', config)
    config = config.replace('0x80574F20', '0x805B5F00').replace('0x80576280', '0x805B7260')
    config = config.replace('0x80BF6840', f'0x{args.rel_base:08X}')
    config = config.replace('bss 0x80F12640', 'bss ' + layout['bss'])
    config = config.replace('projects/spm/MAP.txt', 'projects/spm-eu1/MAP.txt')
    config = config.replace('runtime/src', 'runtime-eu1/src')
    (project / 'recomp.yml').write_text(config)
    print(f'Prepared {len(rows)} function entries; staged runtime: {stage}')
    print('Verify the boot module log reports MATCH for both image and BSS placement.')

if __name__ == '__main__':
    main()
