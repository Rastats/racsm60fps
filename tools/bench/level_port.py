#!/usr/bin/env python3
"""Port LEVEL_01 RVAs (code words, data words, data addresses) to another level module.

Every level PRX carries its own copy of the engine, so a site known in LEVEL_01
sits at a different RVA in LEVEL_02 and beyond. This tool finds it offline, from
the extracted PRX files, by masked byte matching:

- code site: the 16 words before and after it (window widened up to 64 words
  until the match is unique). Masked fields: jump targets, `lui` immediates and
  the 16-bit offsets of loads, stores and `addiu`/`ori` off any base other than
  sp, since these hold relocated addresses that differ per module. Everything
  else, the site word included, must be identical.
- data word (float constants of `fixes.DATA`): the surrounding bytes, exact,
  widened until unique.
- data address (player struct, frame counter, ammo table): every `lui`/offset
  pair of LEVEL_01 that builds the address is ported as a code site, then
  decoded in the target; the result is the value all ported pairs agree on.

A site is accepted only when its match is unique and its original word is
identical. Anything else is reported as not ported, never guessed.

Init-computed data words (2026-11-08): a `fixes.DATA` data word that is 0 in
the LEVEL_01 file but nonzero in its original is written by the game at init
(the 20 camera filter k = omega x 1/30 of `camfilters`, computed by 0xCA24).
Its site is ported like any data word, the target file must also hold 0 there,
and the entry is marked `runtime`: the file cannot confirm the original, so the
only guard is the one `wordfix.py` applies to the live word in RAM.

Validated 2026-10-22 against the owner's per-level cheat files
(cheats/eu/base/LEVEL_0x_*.ini): the three C1 core words and the player
struct implied by the EU health cheats.

Usage:
  python tools/bench/level_port.py --target LEVEL_02 [--json out.json]
"""
import argparse
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = Path(os.environ.get('RACSM_ROOT', 'D:/racsm60fps'))
BIN = ROOT / 'game/iso/PSP_GAME/USRDIR/BIN'

# LEVEL_01 data addresses used by the bench (module RVAs)
ADDRESSES = {
    'frame_counter': 0x2AF28C,   # breakloop.py, clock.py
    'player': 0x337940,          # move_probe.py, damage_probe.py, fire_rate.py, entities.py
    'ammo_base': 0x2AE95C,       # fire_rate.py
    'entity_manager': 0x2CA0D0,  # entities.py
}
# C1 core (tools/runtime/pump-gate.py)
CORE = {'vblank': 0x96650, 'delta': 0x151E0, 'loop': 0x2FCFC}

SP = 29
LOADSTORE = set(range(32, 47)) | {49, 50, 53, 54, 57, 58, 61, 62}


class Prx:
    def __init__(self, path):
        self.path = Path(path)
        d = self.path.read_bytes()
        phoff, = struct.unpack_from('<I', d, 0x1C)
        phentsize, phnum = struct.unpack_from('<HH', d, 0x2A)
        size = extent = 0
        segs = []
        for i in range(phnum):
            t, off, va, _pa, fsz, msz, _fl, _al = struct.unpack_from('<8I', d, phoff + i * phentsize)
            if t == 1:
                segs.append((off, va, fsz))
                size = max(size, va + fsz)
                extent = max(extent, va + msz)
        img = bytearray(size)
        for off, va, fsz in segs:
            img[va:va + fsz] = d[off:off + fsz]
        self.img = bytes(img)
        self.extent = extent
        self.seg_bases = [va for _off, va, _fsz in segs]
        self.words = np.frombuffer(self.img[:size & ~3], dtype='<u4')
        self.text = self._text_range(d)

    @staticmethod
    def _text_range(d):
        shoff, = struct.unpack_from('<I', d, 0x20)
        shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x2E)
        if not shoff or not shnum:
            return None
        secs = [struct.unpack_from('<10I', d, shoff + i * shentsize) for i in range(shnum)]
        stroff = secs[shstrndx][4]
        for s in secs:
            name = d[stroff + s[0]:d.index(b'\0', stroff + s[0])]
            if name == b'.text':
                return (s[3], s[3] + s[5])
        return None

    def segment_of(self, rva):
        """(segment index, segment base) holding rva. HI16/LO16 relocations of a
        PRX are relative to the segment they point into, so an unrelocated
        `lui`/offset pair holds rva - base, not rva (seg 1 of LEVEL_01 starts at
        0x2DD108: the player pair at 0x30014 holds 0x5A838 for 0x337940)."""
        idx = max(i for i, b in enumerate(self.seg_bases) if b <= rva)
        return idx, self.seg_bases[idx]

    def word(self, rva):
        return int(self.words[rva >> 2])

    def is_code(self, rva):
        return self.text is not None and self.text[0] <= rva < self.text[1]


def mask_of(w):
    op = w >> 26
    if op in (2, 3):                       # j / jal
        return 0xFC000000
    if op == 15:                           # lui
        return 0xFFFF0000
    rs = (w >> 21) & 31
    if (op in LOADSTORE or op in (9, 13)) and rs != SP:
        return 0xFFFF0000
    return 0xFFFFFFFF


def match_words(dst, pattern, masks):
    """Word indexes i of dst where dst[i+k] & masks[k] == pattern[k] for all k."""
    n = len(dst) - len(pattern) + 1
    ok = np.ones(n, dtype=bool)
    for k, (p, m) in enumerate(zip(pattern, masks)):
        ok &= (dst[k:k + n] & np.uint32(m)) == np.uint32(p & m)
        if not ok.any():
            break
    return np.nonzero(ok)[0]


def port_code(src, dst, rva, widths=(8, 16, 32, 64)):
    i = rva >> 2
    for w in widths:
        lo, hi = max(0, i - w), min(len(src.words), i + w + 1)
        pat = [int(x) for x in src.words[lo:hi]]
        masks = [mask_of(x) for x in pat]
        hits = match_words(dst.words, pat, masks)
        if len(hits) == 1:
            return {'rva': int(hits[0] + (i - lo)) * 4, 'window_words': hi - lo}
        if len(hits) == 0:
            return {'rva': None, 'why': f'no match at window {hi - lo} words'}
    return {'rva': None, 'why': f'{len(hits)} matches at window {hi - lo} words'}


def port_data(src, dst, rva, widths=(4, 8, 16, 32)):
    i = rva >> 2
    for w in widths:
        lo, hi = max(0, i - w), min(len(src.words), i + w + 1)
        pat = [int(x) for x in src.words[lo:hi]]
        hits = match_words(dst.words, pat, [0xFFFFFFFF] * len(pat))
        if len(hits) == 1:
            return {'rva': int(hits[0] + (i - lo)) * 4, 'window_words': hi - lo}
        if len(hits) == 0:
            return {'rva': None, 'why': f'no exact match at window {hi - lo} words'}
    return {'rva': None, 'why': f'{len(hits)} matches at window {hi - lo} words'}


def _sext(v):
    return v - 0x10000 if v & 0x8000 else v


def address_pairs(prx, target, span=12):
    """(lui index, user index) pairs in .text building `target` as lui hi + signed lo."""
    w = prx.words
    lo_t, hi_t = prx.text if prx.text else (0, len(w) * 4)
    want_hi = ((target + 0x8000) >> 16) & 0xFFFF
    luis = np.nonzero(((w >> 26) == 15) & ((w & 0xFFFF) == want_hi))[0]
    out = []
    for li in luis:
        if not lo_t <= li * 4 < hi_t:
            continue
        rt = (int(w[li]) >> 16) & 31
        for k in range(li + 1, min(li + span, len(w))):
            u = int(w[k])
            op, rs, rtt = u >> 26, (u >> 21) & 31, (u >> 16) & 31
            if rs == rt and (op in LOADSTORE or op in (9, 13)):
                val = ((want_hi << 16) + (_sext(u & 0xFFFF) if op != 13 else (u & 0xFFFF))) & 0xFFFFFFFF
                if val == target:
                    out.append((int(li), k))
                break
            if op == 15 and rtt == rt:
                break
    return out


def port_address(src, dst, target):
    seg, src_base = src.segment_of(target)
    dst_base = dst.seg_bases[seg]
    pairs = address_pairs(src, target - src_base)
    votes = {}
    for li, ui in pairs:
        r = port_code(src, dst, ui * 4)
        if r['rva'] is None:
            continue
        dui = r['rva'] >> 2
        dli = dui - (ui - li)
        lw, uw = int(dst.words[dli]), int(dst.words[dui])
        if lw >> 26 != 15:
            continue
        op = uw >> 26
        val = (((lw & 0xFFFF) << 16) + (_sext(uw & 0xFFFF) if op != 13 else uw & 0xFFFF) + dst_base) & 0xFFFFFFFF
        votes[val] = votes.get(val, 0) + 1
    if not votes:
        return {'rva': None, 'pairs': len(pairs), 'why': 'no ported pair'}
    best = max(votes, key=votes.get)
    return {'rva': best if len(votes) == 1 else None, 'pairs': len(pairs),
            'votes': {hex(k): v for k, v in votes.items()},
            **({} if len(votes) == 1 else {'why': 'pairs disagree'})}


def load_fixes_data():
    import importlib.util
    spec = importlib.util.spec_from_file_location('fixes', HERE.parents[1] / 'tools/runtime/fixes.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DATA


def port_level(target, src_name='LEVEL_01'):
    src, dst = Prx(BIN / f'{src_name}.PRX'), Prx(BIN / f'{target}.PRX')
    out = {'source': src_name, 'target': target, 'size': hex((dst.extent + 0xFF) & ~0xFF),
           'core': {}, 'addresses': {}, 'fixes': {}}
    for name, rva in CORE.items():
        r = port_code(src, dst, rva)
        if r['rva'] is not None:
            r['word'] = hex(dst.word(r['rva']))
        out['core'][name] = {k: (hex(v) if k == 'rva' and v is not None else v) for k, v in r.items()}
    for name, rva in ADDRESSES.items():
        r = port_address(src, dst, rva)
        out['addresses'][name] = {k: (hex(v) if k == 'rva' and v is not None else v) for k, v in r.items()}
    for name, (rva, orig, new) in sorted(load_fixes_data().items()):
        runtime = not src.is_code(rva) and src.word(rva) == 0 and orig != 0
        if src.word(rva) != orig and not runtime:
            out['fixes'][name] = {'rva': None, 'why': 'LEVEL_01 word differs from fixes.DATA original'}
            continue
        r = port_code(src, dst, rva) if src.is_code(rva) else port_data(src, dst, rva)
        if r['rva'] is not None and dst.word(r['rva']) != src.word(rva):
            r = {'rva': None, 'why': 'matched site holds another word'}
        elif r['rva'] is not None and runtime:
            r['runtime'] = True       # init-computed: original checked in RAM by wordfix only
        out['fixes'][name] = {k: (hex(v) if k == 'rva' and v is not None else v) for k, v in r.items()}
        out['fixes'][name]['kind'] = 'code' if src.is_code(rva) else 'data'
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--target', required=True, help='module stem, e.g. LEVEL_02')
    ap.add_argument('--json', help='write the full table here')
    a = ap.parse_args()
    out = port_level(a.target)
    ported = sum(1 for v in out['fixes'].values() if v['rva'])
    summary = {'target': a.target, 'size': out['size'], 'core': out['core'], 'addresses': out['addresses'],
               'fixes_ported': f'{ported}/{len(out["fixes"])}'}
    print(json.dumps(summary, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
