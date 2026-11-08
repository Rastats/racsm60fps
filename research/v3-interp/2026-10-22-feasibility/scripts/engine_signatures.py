#!/usr/bin/env python3
"""Look for the LEVEL_01 update/render boundary pieces in every level module.

Signatures are runs of position-independent instruction words taken from
LEVEL_01 (no jal/lui targets, which relocation changes):
  drawq    draw-queue walker loop of 0x6BB14: lw a0,8(s2); bne a0,s0; nop; lw a1,4(s2); jalr a1; lw a0,0(s2)
  drawmoby moby draw 0x6F514 prologue: world matrix and bone buffer from the moby record
  pumpcb   pump-1 per-entity dispatch 0x6B9B0: lw a1,0x1C(s0); mov.s f12,f20; jalr a1; move a0,s6
Prints the RVA of each hit per module (game modules are not read beyond the
extracted ISO folder given on the command line).

Usage: python engine_signatures.py <extracted PSP_GAME/USRDIR/BIN folder>
"""
import struct
import sys
from pathlib import Path

SIGS = {
    'drawq': [0x8E440008, 0x14900004, 0x00000000, 0x8E450004, 0x00A0F809, 0x8E440000],
    'drawmoby': [0x8E240048, 0x14800005, 0x00000000, 0x10000046, 0x00000000],
    'pumpcb': [0x8E05001C, 0x4600A306, 0x00A0F809, 0x02C02025],
}


def text_words(path):
    d = path.read_bytes()
    shoff, = struct.unpack_from('<I', d, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x2E)
    secs = [struct.unpack_from('<10I', d, shoff + i * shentsize) for i in range(shnum)]
    stro = secs[shstrndx][4]
    for s in secs:
        if d[stro + s[0]:d.index(b'\0', stro + s[0])] == b'.text':
            return s[3], struct.unpack_from('<%dI' % (s[5] // 4), d, s[4])
    raise ValueError('no .text in %s' % path)


def find(words, sig):
    n = len(sig)
    first = sig[0]
    return [i for i, w in enumerate(words) if w == first and list(words[i:i + n]) == sig]


def main():
    folder = Path(sys.argv[1])
    for prx in sorted(folder.glob('*.PRX')):
        try:
            va, words = text_words(prx)
        except (ValueError, struct.error) as e:
            print(prx.name, 'skipped:', e)
            continue
        hits = {k: ['0x%X' % (va + 4 * i) for i in find(words, s)] for k, s in SIGS.items()}
        print('%-14s %s' % (prx.name, '  '.join('%s=%s' % (k, ','.join(v) or '-') for k, v in hits.items())))


if __name__ == '__main__':
    main()
