#!/usr/bin/env python3
"""Offline check of the init-computed word rule (level_port.py, 2026-11-08).

Needs the extracted PRX files under <root>/game/iso and the reference
LEVEL_01.PRX (fixes.py reads the camera filter omegas from it).

- LEVEL_01: the only fixes.DATA data words that are 0 in the file but nonzero
  in their original are the 20 camfilters k words.
- LEVEL_02: all 41 camfilters words port, the 20 k words marked `runtime`, and
  levels.py exposes them in the profile's `runtime` set.

Usage:
  python tools/bench/test_runtime_port.py      (or pytest)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import level_port  # noqa: E402
import levels  # noqa: E402

LEVEL02_SIZE = 0x484B00


def test_runtime_words_are_camfilters_k():
    src = level_port.Prx(level_port.BIN / 'LEVEL_01.PRX')
    data = level_port.load_fixes_data()
    runtime = sorted(n for n, (rva, orig, _) in data.items()
                     if not src.is_code(rva) and src.word(rva) == 0 and orig != 0)
    assert len(runtime) == 20, runtime
    assert all(n.startswith('camf0x') for n in runtime), runtime


def test_level02_ports_camfilters():
    out = level_port.port_level('LEVEL_02')
    camf = {n: r for n, r in out['fixes'].items() if n.startswith('camf')}
    assert len(camf) == 41 and all(r['rva'] for r in camf.values()), \
        {n: r.get('why') for n, r in camf.items() if not r['rva']}
    assert sum(1 for r in camf.values() if r.get('runtime')) == 20
    prof = levels.profile_for_size(LEVEL02_SIZE)
    assert len(prof['runtime']) == 20 and prof['runtime'] <= set(prof['fixes'])


if __name__ == '__main__':
    test_runtime_words_are_camfilters_k()
    test_level02_ports_camfilters()
    print('ok: 2/2')
