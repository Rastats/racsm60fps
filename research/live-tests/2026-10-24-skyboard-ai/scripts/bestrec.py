"""LEVEL_22 skyboard best times (save data *(rcp1+0x220A60) + 0x880 + 0x50..0x5C, one u32 of A0 frames per
challenge; writer 0xE086C, reader 0xE0380). TEST AID --set writes one of them (state RAM only).

python bestrec.py                    # print the four records
python bestrec.py --set 0 7000       # Learner's Permit record := 7000 frames
"""
import argparse, json, sys
sys.path.insert(0, 'D:/sandboxes/racsm60fps/wt-banc/tools/bench')
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa
import levels  # noqa

NAMES = ("Learner's Permit", 'Speeding Ticket', 'Tricky Air', "Master's Challenge")


def slots(d):
    base, _ = levels.profile(d)
    save = d.u32(base + 0x220A60)
    return [save + 0x880 + 0x50 + 4 * i for i in range(4)]


def read(d):
    out = []
    for name, a in zip(NAMES, slots(d)):
        v = d.u32(a)
        out.append({'name': name, 'addr': hex(a), 'frames': v, 'shown': f'{v // 30 // 60}:{v // 30 % 60:02d}' if v else None})
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', nargs=2, type=int, metavar=('SLOT', 'FRAMES'))
    a = ap.parse_args()
    with Debugger(DEFAULT_PORT).connect() as d:
        if a.set:
            d.write_u32(slots(d)[a.set[0]], a.set[1])
        print(json.dumps(read(d), indent=1))
