#!/usr/bin/env python3
"""Check Rev 2 SDK globals against instructions in the user's own main.dol."""
from pathlib import Path
import argparse
import importlib.util
import json
import struct
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('spm_address_audit', ROOT/'tools/audit-spm-runtime.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
Dol, signed16, active_lines, ADDRESS = audit.Dol, audit.signed16, audit.active_lines, audit.ADDRESS

def sdk_evidence(dol, wc):
    def word(pc):
        return struct.unpack('>I', dol.read(pc, 4))[0]

    def lis_addi(pc, low=None):
        hi, lo = word(pc), word(low if low is not None else pc + 4)
        assert hi >> 26 == 15 and lo >> 26 == 14
        assert (hi >> 21) & 31 == (lo >> 16) & 31
        return ((hi & 0xFFFF) << 16) + signed16(lo & 0xFFFF)

    ptr_load = word(0x80291DDC)
    assert ptr_load >> 26 == 32 and (ptr_load >> 16) & 31 == 2
    gxptr = 0x80575C60 + signed16(ptr_load & 0xFFFF)
    gxdata = word(gxptr)
    fifo = lis_addi(0x80291DE0)
    # These offsets come from the exact GXBeginDisplayList load/store instructions.
    offsets = {pc: signed16(word(pc) & 0xFFFF) for pc in
               (0x80291E14, 0x80291E34, 0x80291E38, 0x80291E3C, 0x80291E40, 0x80291E44, 0x80291E48)}
    expected = {
        'src/hle/gx/gx_internal.h': {gxptr, fifo, fifo + offsets[0x80291E44], fifo + offsets[0x80291E40]},
        'src/hle/gx/gx_init.cpp': {gxdata, fifo + offsets[0x80291E14], fifo + offsets[0x80291E34],
                                   fifo + offsets[0x80291E38], fifo + offsets[0x80291E3C],
                                   fifo + offsets[0x80291E40], fifo + offsets[0x80291E44], fifo + offsets[0x80291E48]},
    }
    horver = lis_addi(0x80281D3C, 0x80281D44)
    expected['src/hle/vi.cpp'] = {horver + signed16(word(pc) & 0xFFFF) for pc in
                                 (0x80281D64, 0x802814D0, 0x80281D68, 0x80281D78, 0x802827BC)}
    expected['src/hle/os/os_thread.cpp'] = {
        lis_addi(0x80275710) + signed16(word(0x80275718) & 0xFFFF)}
    queue_init = word(0x80280B48)  # VIInit: OSInitThreadQueue(&retraceQueue).
    assert queue_init >> 26 == 14 and (queue_init >> 16) & 31 == 13
    retrace_queue = 0x80574900 + signed16(queue_init & 0xFFFF)
    expected['src/fiber_manager.cpp'] = {retrace_queue, retrace_queue + 4}
    expected['src/hle/audio/ax_internal.h'] = {
        0x80574900 + signed16(word(pc) & 0xFFFF) for pc in (0x80289A60, 0x80289A5C, 0x80289B84)}
    expected['src/hle/audio/ax_internal.h'].add(lis_addi(0x80287124, 0x80287144))
    expected['src/hle/audio/ax_effects.cpp'] = {0x80575C60 + signed16(word(0x80288CDC) & 0xFFFF)}
    expected['src/hle/storage/dvd.cpp'] = {
        0x80574900 + signed16(word(pc) & 0xFFFF) for pc in (0x8027A36C, 0x8027A73C, 0x8027A730)}
    checks = []
    for file, addresses in expected.items():
        source = '\n'.join(line for _, line in active_lines((wc / 'runtime-us2' / file).read_text()))
        actual = {int(m.group(1), 16) for m in ADDRESS.finditer(source)}
        for addr in sorted(addresses):
            checks.append(dict(file=file, address=f'{addr:08X}', passed=addr in actual,
                               evidence='Decoded SPM SDK instruction anchors; see sdk_evidence() for PCs'))
    return checks

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc-root', type=Path, required=True)
    args = parser.parse_args()
    results = sdk_evidence(Dol(args.disc_root/'sys/main.dol'), ROOT/'wiicompiled')
    failed = [row for row in results if not row['passed']]
    print(f"SDK instruction checks: {len(results)-len(failed)}/{len(results)} passed")
    if failed:
        print(json.dumps(failed, indent=2))
        raise SystemExit(1)

if __name__ == '__main__': main()
