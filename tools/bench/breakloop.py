#!/usr/bin/env python3
"""Break loop: exact event times and frame-locked input, in emulated time.

PPSSPP write memchecks stop the CPU *before* the store executes (OBSERVED
2026-10-19, Pokitaru: PC on `sw a0,0x40(v0)`, memory still holding the old
value). Reading memory at the break therefore gives the previous value. This
loop decodes the store at PC and reads its source register (`cpu.getReg`), so
every event gets its own tick and its own new value.

One extra watch on the game frame counter (module RVA 0x2AF28C, +1 per main
loop frame) gives a callback once per frame while the CPU is stopped. Input
sent from that callback is applied at a frame boundary, never at a wall-clock
moment, so an input script means the same thing in A0 (30 Hz) and C1 (60 Hz).

Usage (library):
    loop = BreakLoop(d, base)
    loop.watch(addr, on_change)          # on_change(tick, old, new)
    loop.every_frame(on_frame)           # on_frame(tick, frame_value)
    loop.run(seconds)                    # emulated seconds
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ppsspp_bench import BenchError  # noqa: E402

CPU_HZ = 222_000_000
FRAME_COUNTER_RVA = 0x2AF28C
STORES = {0x28: 1, 0x29: 2, 0x2B: 4, 0x39: 4}     # sb, sh, sw, swc1 -> size


def _sext16(v):
    return v - 0x10000 if v & 0x8000 else v


def is_branch(word):
    """True for MIPS/Allegrex branches and jumps (instructions with a delay slot)."""
    op = word >> 26
    if op in (2, 3):                       # j, jal
        return True
    if op == 0 and (word & 0x3F) in (8, 9):  # jr, jalr
        return True
    if op in (4, 5, 6, 7, 20, 21, 22, 23):   # beq, bne, blez, bgtz (+ likely)
        return True
    if op == 1 and ((word >> 16) & 0x1F) in (0, 1, 2, 3, 16, 17, 18, 19):  # regimm branches
        return True
    if op == 17 and ((word >> 21) & 0x1F) == 8:  # bc1x
        return True
    return False


def pending_store(d, pc):
    """(address, size, new value) of the store at `pc`, before it executes.

    A store in a delay slot stops the CPU on its branch (OBSERVED 2026-10-19:
    the frame counter `sw a0,-0x7074(s3)` sits in the slot of a `jal`), so the
    slot is decoded instead. Registers are read before the branch executes,
    which is exact unless the store uses `ra` written by its own jal.
    """
    word = d.u32(pc)
    if is_branch(word):
        pc += 4
        word = d.u32(pc)
    op = word >> 26
    if op not in STORES:
        raise BenchError(f'break at 0x{pc:08X} is not a store (0x{word:08X})')
    rs, rt = (word >> 21) & 31, (word >> 16) & 31
    ea = (d.call('cpu.getReg', category=0, register=rs)['uintValue'] + _sext16(word & 0xFFFF)) & 0xFFFFFFFF
    size = STORES[op]
    value = d.call('cpu.getReg', category=1 if op == 0x39 else 0, register=rt)['uintValue']
    return ea, size, value & ((1 << (8 * size)) - 1)


class BreakLoop:
    def __init__(self, d, base, frame_counter_rva=None):
        self.d, self.base = d, base
        if frame_counter_rva is None:          # per level (levels.py); LEVEL_01: FRAME_COUNTER_RVA
            import levels
            frame_counter_rva = levels.profile(d)[1]['frame_counter']
        self.frame_counter_rva = frame_counter_rva
        self.watches = {}          # address -> callback(tick, old, new)
        self.frame_cb = None
        self.end_cb = None
        self.breaks = self.frames = self.other = 0
        self.pending_at_end = None  # (address, new value) of a watched store left for after the run

    def watch(self, address, callback):
        self.watches[address] = callback

    def every_frame(self, callback):
        self.frame_cb = callback

    def at_end(self, callback):
        """callback() runs once at the end while the CPU is still stopped (release inputs here)."""
        self.end_cb = callback

    def run(self, seconds, wall_limit=None):
        """Run until `seconds` of emulated time have passed; return (start tick, end tick)."""
        d = self.d
        fc = self.base + self.frame_counter_rva
        addrs = list(self.watches) + ([fc] if self.frame_cb else [])
        span = int(seconds * CPU_HZ)
        wall_limit = wall_limit or max(60.0, seconds * 40)
        d.pause()                              # stop first, so no event fires before t_start
        stepping = True
        try:
            for a in addrs:
                d.add_mem_breakpoint(a, 4, write=True, change=True)
            t_start = t = int(d.cpu()['ticks'])
            if self.frame_cb:                  # inputs for the first frame, set while stopped
                self.frame_cb(t, None)
            d.resume_quiet()
            stepping = False
            deadline = time.monotonic() + wall_limit
            while True:
                if time.monotonic() > deadline:
                    raise BenchError(f'wall-clock limit {wall_limit:.0f} s reached before {seconds} emulated s')
                ev = d.wait_event('cpu.stepping', timeout=1.0)
                if ev is None:                 # no event for a while: check the clock
                    if int(d.cpu()['ticks']) - t_start >= span:
                        d.pause()
                        stepping = True
                        t = int(d.cpu()['ticks'])
                        break
                    continue
                stepping = True
                self.breaks += 1
                t = int(ev['ticks'])
                ea, size, new = pending_store(d, int(ev['pc']))
                if t - t_start >= span:
                    if ea in self.watches:
                        self.pending_at_end = (ea, new)
                    break
                if ea == fc and self.frame_cb:
                    self.frames += 1
                    self.frame_cb(t, new)
                elif ea in self.watches:
                    self.watches[ea](t, d.u32(ea), new)
                else:
                    self.other += 1
                d.resume_quiet()
                stepping = False
        finally:
            try:
                if self.end_cb:
                    self.end_cb()
            finally:
                for a in addrs:
                    d.remove_mem_breakpoint(a, 4)
                if stepping or d.cpu().get('stepping'):
                    d.resume()
        return t_start, t
