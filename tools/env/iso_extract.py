#!/usr/bin/env python3
"""List or extract files from a PSP UMD ISO image (plain ISO 9660, 2048-byte sectors).

No third-party dependencies. The output directory must be outside the Git
repository: extracted game files are game-derived content and must never be
committed (docs/PUBLICATION_POLICY.md).

Usage:
  python tools/env/iso_extract.py ISO --list
  python tools/env/iso_extract.py ISO --out DIR [--only PSP_GAME/USRDIR]
"""
import argparse
import struct
from pathlib import Path

SECTOR = 2048


def read_sector(f, lba, count=1):
    f.seek(lba * SECTOR)
    return f.read(count * SECTOR)


def parse_dir(f, lba, size, prefix=''):
    """Yield (path, lba, size, is_dir) for every entry below a directory extent."""
    data = read_sector(f, lba, (size + SECTOR - 1) // SECTOR)
    pos = 0
    while pos < len(data):
        rec_len = data[pos]
        if rec_len == 0:
            # Records never cross a sector boundary; skip to the next sector.
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        rec = data[pos:pos + rec_len]
        ext_lba = struct.unpack_from('<I', rec, 2)[0]
        ext_size = struct.unpack_from('<I', rec, 10)[0]
        flags = rec[25]
        name_len = rec[32]
        name = rec[33:33 + name_len]
        pos += rec_len
        if name in (b'\x00', b'\x01'):
            continue
        name = name.decode('ascii', 'replace').split(';')[0]
        path = prefix + name
        is_dir = bool(flags & 2)
        yield path, ext_lba, ext_size, is_dir
        if is_dir:
            yield from parse_dir(f, ext_lba, ext_size, path + '/')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('iso')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--out')
    ap.add_argument('--only', default='', help='extract only paths starting with this prefix')
    a = ap.parse_args()
    with open(a.iso, 'rb') as f:
        pvd = read_sector(f, 16)
        if pvd[1:6] != b'CD001':
            raise SystemExit('not an ISO 9660 image')
        root = pvd[156:156 + 34]
        root_lba = struct.unpack_from('<I', root, 2)[0]
        root_size = struct.unpack_from('<I', root, 10)[0]
        entries = list(parse_dir(f, root_lba, root_size))
        if a.list or not a.out:
            for path, lba, size, is_dir in entries:
                print(f"{'D' if is_dir else 'F'} {lba:8d} {size:11d} {path}")
            return
        out = Path(a.out).resolve()
        for path, lba, size, is_dir in entries:
            if not path.startswith(a.only):
                continue
            target = out / path
            if is_dir:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            f.seek(lba * SECTOR)
            remaining = size
            with open(target, 'wb') as w:
                while remaining:
                    chunk = f.read(min(remaining, 1 << 20))
                    if not chunk:
                        raise SystemExit(f'truncated extent: {path}')
                    w.write(chunk)
                    remaining -= len(chunk)
        print(f'extracted {sum(1 for e in entries if not e[3] and e[0].startswith(a.only))} files to {out}')


if __name__ == '__main__':
    main()
