#!/usr/bin/env python3
"""Autonomous PPSSPP test bench: launch an instance, look at the screen, drive
the controller and read/write emulated memory through the debugger WebSocket.

This is the control layer for unattended A/B/C measurements. It complements
the read-only observers in tools/runtime/ (which deliberately refuse input and
writes): here input, screenshots and guarded memory writes are allowed, because
the bench owns a dedicated portable instance (tools/env/setup_ppsspp_portable.py)
and never the owner's interactive PPSSPP.

Time base: PPSSPP's `cpu.status.ticks` (CoreTiming cycles) is emulated time,
independent of host speed, focus or throttling. Convert with the CPU clock in
effect (see `measure_clock` in tools/bench/clock.py). Wall-clock time is only
used for timeouts.

Dependency-free (standard library only). Python 3.10+.

CLI examples (instance and ISO paths default to the D:/racsm60fps layout):
  python tools/bench/ppsspp_bench.py launch
  python tools/bench/ppsspp_bench.py status
  python tools/bench/ppsspp_bench.py shot --out D:/racsm60fps/work/shots/a.png
  python tools/bench/ppsspp_bench.py press cross --frames 2
  python tools/bench/ppsspp_bench.py hold --buttons right --frames 30
  python tools/bench/ppsspp_bench.py stick --x 0 --y -1 --frames 60
  python tools/bench/ppsspp_bench.py modules
  python tools/bench/ppsspp_bench.py read --addr 0x08800000 --count 4
  python tools/bench/ppsspp_bench.py quit
"""
import argparse
import base64
import json
import os
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_ROOT = Path(os.environ.get('RACSM_ROOT', 'D:/racsm60fps'))
# RACSM_INSTANCE / RACSM_PORT let parallel benches each own one instance
# (emu/ppsspp-N, debugger port 60906+N); scripts that import the defaults follow.
DEFAULT_INSTANCE = Path(os.environ.get('RACSM_INSTANCE', DEFAULT_ROOT / 'emu/ppsspp-1'))
DEFAULT_ISO = DEFAULT_ROOT / 'game/UCES00420.iso'
DEFAULT_PORT = int(os.environ.get('RACSM_PORT', '60907'))
TIMEOUT_S = 20.0


class BenchError(RuntimeError):
    pass


class Debugger:
    """Minimal WebSocket client for the PPSSPP debugger API (text frames only)."""

    def __init__(self, port=DEFAULT_PORT, host='127.0.0.1'):
        self.host, self.port = host, port
        self.sock = None
        self.buffer = b''
        self.seq = 0
        self.events = []          # broadcasts received while waiting for replies

    # -- transport ---------------------------------------------------------
    def connect(self, timeout=TIMEOUT_S):
        self.sock = socket.create_connection((self.host, self.port), timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f'GET /debugger HTTP/1.1\r\nHost: {self.host}:{self.port}\r\n'
               'Upgrade: websocket\r\nConnection: Upgrade\r\n'
               f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n'
               'Sec-WebSocket-Protocol: debugger.ppsspp.org\r\n\r\n')
        self.sock.sendall(req.encode())
        head = b''
        while b'\r\n\r\n' not in head:
            chunk = self.sock.recv(1)
            if not chunk:
                raise BenchError('connection closed during handshake')
            head += chunk
        self.buffer = head.split(b'\r\n\r\n', 1)[1]
        if b' 101 ' not in head.split(b'\r\n', 1)[0]:
            raise BenchError('handshake refused: ' + head.split(b'\r\n', 1)[0].decode(errors='replace'))
        return self

    def close(self):
        try:
            if self.sock:
                self._send(b'', 0x8)
                self.sock.close()
        except OSError:
            pass
        self.sock = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _recv_exact(self, n):
        while len(self.buffer) < n:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise BenchError('connection closed')
            self.buffer += chunk
        data, self.buffer = self.buffer[:n], self.buffer[n:]
        return data

    def _send(self, payload, opcode=0x1):
        mask = os.urandom(4)
        n = len(payload)
        if n < 126:
            head = bytes([0x80 | opcode, 0x80 | n])
        elif n < 65536:
            head = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack('>H', n)
        else:
            head = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack('>Q', n)
        masked = bytes(b ^ mask[i & 3] for i, b in enumerate(payload))
        self.sock.sendall(head + mask + masked)

    def _recv(self):
        payload = b''
        while True:
            b0, b1 = self._recv_exact(2)
            opcode, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack('>H', self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._recv_exact(8))[0]
            mask = self._recv_exact(4) if b1 & 0x80 else None
            chunk = self._recv_exact(n) if n else b''
            if mask:
                chunk = bytes(b ^ mask[i & 3] for i, b in enumerate(chunk))
            if opcode == 0x8:
                raise BenchError('server closed the connection')
            if opcode == 0x9:
                self._send(chunk, 0xA)
                continue
            if opcode == 0xA:
                continue
            payload += chunk
            if b0 & 0x80:
                return json.loads(payload.decode('utf-8', errors='replace'))

    # -- requests ----------------------------------------------------------
    def call(self, event, timeout=TIMEOUT_S, **fields):
        """Send one request and return its reply (matched by ticket)."""
        self.seq += 1
        ticket = f'bench-{self.seq}'
        self._send(json.dumps({'event': event, 'ticket': ticket, **fields}).encode())
        deadline = time.monotonic() + timeout
        while True:
            msg = self._recv()
            if msg.get('ticket') == ticket:
                if msg.get('event') == 'error':
                    raise BenchError(f'{event}: {msg.get("message")}')
                return msg
            # cpu.stepping / cpu.resume are acknowledged by an untagged broadcast
            # of the same name (SteppingBroadcaster), not by a ticketed reply.
            if msg.get('ticket') is None and msg.get('event') == event and event in ('cpu.stepping', 'cpu.resume'):
                return msg
            if msg.get('event') == 'error' and msg.get('ticket') is None:
                raise BenchError(f'{event}: {msg.get("message")}')
            self.events.append(msg)
            if time.monotonic() > deadline:
                raise BenchError(f'timeout waiting for {event}')

    # -- convenience -------------------------------------------------------
    def game(self):
        return self.call('game.status')

    def cpu(self):
        return self.call('cpu.status')

    def ticks(self):
        return int(self.cpu()['ticks'])

    def modules(self, active_only=True):
        mods = self.call('hle.module.list')['modules']
        return [m for m in mods if m.get('isActive') or not active_only]

    def module(self, name='rcp1'):
        found = [m for m in self.modules() if m['name'] == name]
        if len(found) != 1:
            raise BenchError(f'module {name!r}: {len(found)} resident')
        return found[0]

    def read(self, address, size):
        r = self.call('memory.read', address=address, size=size, replacements=False)
        data = base64.b64decode(r['base64'])
        if len(data) != size:
            raise BenchError('short read')
        return data

    def u32(self, address, count=1):
        vals = struct.unpack(f'<{count}I', self.read(address, 4 * count))
        return vals[0] if count == 1 else list(vals)

    def f32(self, address, count=1):
        vals = struct.unpack(f'<{count}f', self.read(address, 4 * count))
        return vals[0] if count == 1 else list(vals)

    def write_u32(self, address, value, expect=None):
        """Guarded word write: optional expected old value, verified read-back."""
        if expect is not None:
            old = self.u32(address)
            if old != expect:
                raise BenchError(f'guard failed at 0x{address:08X}: 0x{old:08X} != 0x{expect:08X}')
        self.call('memory.write_u32', address=address, value=value)
        if self.u32(address) != value:
            raise BenchError(f'read-back mismatch at 0x{address:08X}')

    def pause(self):
        return self.call('cpu.stepping')

    def resume(self):
        return self.call('cpu.resume')

    def screenshot(self, out_path):
        """Save the displayed frame as PNG. PPSSPP only serves screenshots while
        the CPU (or GPU) is stepping, so the CPU is paused around the capture;
        emulated time does not advance while paused."""
        was_stepping = self.cpu().get('stepping')
        if not was_stepping:
            self.pause()
        try:
            r = self.call('gpu.buffer.screenshot', type='uri', timeout=30)
        finally:
            if not was_stepping:
                self.resume()
        uri = r.get('uri', '')
        if not uri.startswith('data:image/png;base64,'):
            raise BenchError('unexpected screenshot payload')
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(base64.b64decode(uri.split(',', 1)[1]))
        return out, r.get('width'), r.get('height')

    def buttons(self, **state):
        """Set button states, e.g. buttons(cross=True, right=False)."""
        return self.call('input.buttons.send', buttons=state)

    def release_all(self):
        """Release every button and centre both sticks. Call at the start of a run:
        a script killed while holding a button leaves it pressed (seen 2026-10-19)."""
        self.buttons(**{b: False for b in ('cross', 'circle', 'triangle', 'square', 'up', 'down', 'left',
                                           'right', 'start', 'select', 'ltrigger', 'rtrigger')})
        self.stick(0, 0, 'left')
        self.stick(0, 0, 'right')

    def press(self, button, frames=1):
        """Press and release one button for `frames` emulated frames."""
        return self.call('input.buttons.press', button=button, duration=frames)

    def stick(self, x, y, stick='left'):
        return self.call('input.analog.send', stick=stick, x=float(x), y=float(y))

    # -- event-driven sampling ---------------------------------------------
    # Tight polling starves the emulator (observed 2026-10-19: CoreTiming
    # ticks froze while a loop issued back-to-back requests). Exact, cheap
    # timestamps come from breakpoints instead: the CPU stops at the event,
    # the `cpu.stepping` broadcast carries the emulated tick count, the bench
    # reads what it needs and resumes. Emulated time does not advance while
    # stepping, so the samples are exact whatever the host speed.
    def wait_event(self, event, timeout=TIMEOUT_S):
        """Return the next untagged broadcast named `event` (earlier ones queued in self.events first)."""
        for i, msg in enumerate(self.events):
            if msg.get('event') == event and msg.get('ticket') is None:
                return self.events.pop(i)
        self.sock.settimeout(timeout)
        try:
            while True:
                msg = self._recv()
                if msg.get('event') == event and msg.get('ticket') is None:
                    return msg
                if msg.get('event') != 'cpu.resume':      # resume acks are noise here
                    self.events.append(msg)
        except (socket.timeout, TimeoutError):
            return None
        finally:
            self.sock.settimeout(TIMEOUT_S)

    def add_mem_breakpoint(self, address, size=4, write=True, read=False, change=True, log=False, enabled=True):
        return self.call('memory.breakpoint.add', address=address, size=size, write=write, read=read,
                         change=change, log=log, enabled=enabled)

    def remove_mem_breakpoint(self, address, size=4):
        return self.call('memory.breakpoint.remove', address=address, size=size)

    def add_cpu_breakpoint(self, address, enabled=True, log=False, condition=None):
        fields = {'address': address, 'enabled': enabled, 'log': log}
        if condition:
            fields['condition'] = condition
        return self.call('cpu.breakpoint.add', **fields)

    def remove_cpu_breakpoint(self, address):
        return self.call('cpu.breakpoint.remove', address=address)

    def resume_quiet(self):
        """Resume without waiting for the acknowledgement broadcast (used in break loops)."""
        self.seq += 1
        self._send(json.dumps({'event': 'cpu.resume', 'ticket': f'bench-{self.seq}'}).encode())


def wait_port(port, timeout=60.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), 1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def launch(instance=DEFAULT_INSTANCE, iso=DEFAULT_ISO, port=DEFAULT_PORT, wait=True):
    exe = Path(instance) / 'PPSSPPWindows64.exe'
    if not exe.is_file():
        raise BenchError(f'missing instance: {exe} (run tools/env/setup_ppsspp_portable.py)')
    if (Path(instance) / 'installed.txt').exists():
        raise BenchError('instance is not portable (installed.txt present)')
    flags = 0x00000008 if sys.platform == 'win32' else 0   # DETACHED_PROCESS
    proc = subprocess.Popen([str(exe), str(iso)], cwd=str(instance), creationflags=flags,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (Path(instance) / 'bench.pid').write_text(str(proc.pid), encoding='ascii')
    if wait and not wait_port(port):
        raise BenchError(f'debugger port {port} did not open (pid {proc.pid})')
    return proc.pid


def quit_instance(instance=DEFAULT_INSTANCE):
    """Stop only the PPSSPP process started by `launch` for this instance.

    Never kills by image name: the owner may be playing in another PPSSPP.
    The PID is checked against the instance's executable path before stopping.
    """
    pid_file = Path(instance) / 'bench.pid'
    if not pid_file.exists():
        return 'no bench.pid: nothing to stop'
    pid = int(pid_file.read_text(encoding='ascii').strip())
    exe = str((Path(instance) / 'PPSSPPWindows64.exe').resolve()).lower()
    probe = subprocess.run(['powershell', '-NoProfile', '-Command',
                            f'(Get-Process -Id {pid} -ErrorAction SilentlyContinue).Path'],
                           capture_output=True, text=True)
    path = probe.stdout.strip().lower()
    if not path:
        pid_file.unlink()
        return f'pid {pid} not running'
    if path != exe:
        raise BenchError(f'pid {pid} is {path}, not this instance: refusing to stop it')
    subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, text=True)
    pid_file.unlink()
    return f'stopped pid {pid}'


def wait_for_game(dbg, game_id='UCES00420', timeout=60.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        g = dbg.game().get('game') or {}
        if g.get('id') == game_id:
            return g
        time.sleep(0.5)
    raise BenchError(f'game {game_id} not running')


def _main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('launch'); p.add_argument('--instance', default=str(DEFAULT_INSTANCE)); p.add_argument('--iso', default=str(DEFAULT_ISO))
    sub.add_parser('status')
    sub.add_parser('modules')
    p = sub.add_parser('shot'); p.add_argument('--out', required=True)
    p.add_argument('--method', choices=('window', 'debugger'), default='window',
                   help='window = PrintWindow capture (default; works on 1.20.4), debugger = gpu.buffer.screenshot')
    p.add_argument('--instance', default=str(DEFAULT_INSTANCE))
    p = sub.add_parser('press'); p.add_argument('button'); p.add_argument('--frames', type=int, default=2)
    p = sub.add_parser('hold'); p.add_argument('--buttons', required=True); p.add_argument('--frames', type=int, default=30)
    p = sub.add_parser('stick'); p.add_argument('--x', type=float, default=0); p.add_argument('--y', type=float, default=0)
    p.add_argument('--frames', type=int, default=30); p.add_argument('--right', action='store_true')
    p = sub.add_parser('read'); p.add_argument('--addr', required=True); p.add_argument('--count', type=int, default=1)
    p.add_argument('--float', action='store_true')
    sub.add_parser('pause'); sub.add_parser('resume')
    p = sub.add_parser('quit'); p.add_argument('--instance', default=str(DEFAULT_INSTANCE))
    a = ap.parse_args()

    if a.cmd == 'launch':
        pid = launch(a.instance, a.iso, a.port)
        with Debugger(a.port).connect() as d:
            print(json.dumps({'pid': pid, 'game': wait_for_game(d)}))
        return
    if a.cmd == 'quit':
        print(quit_instance(a.instance))
        return
    with Debugger(a.port).connect() as d:
        if a.cmd == 'status':
            print(json.dumps({'game': d.game().get('game'), 'cpu': d.cpu()}))
        elif a.cmd == 'modules':
            for m in d.modules():
                print(f"{m['name']:24s} 0x{m['address']:08X} size 0x{m['size']:X}")
        elif a.cmd == 'shot':
            if a.method == 'debugger':
                out, w, h = d.screenshot(a.out)
            else:
                sys.path.insert(0, str(Path(__file__).resolve().parent))   # also under python -I
                import wincap
                pid = int((Path(a.instance) / 'bench.pid').read_text(encoding='ascii'))
                out, w, h = wincap.capture(pid, a.out)
            print(json.dumps({'file': str(out), 'width': w, 'height': h, 'ticks': d.ticks()}))
        elif a.cmd == 'press':
            d.press(a.button, a.frames)
            print('ok')
        elif a.cmd == 'hold':
            names = [b.strip() for b in a.buttons.split(',') if b.strip()]
            d.buttons(**{n: True for n in names})
            t0 = d.ticks()
            time.sleep(a.frames / 60.0)
            d.buttons(**{n: False for n in names})
            print(json.dumps({'held': names, 'ticks': d.ticks() - t0}))
        elif a.cmd == 'stick':
            which = 'right' if a.right else 'left'
            d.stick(a.x, a.y, which)
            time.sleep(a.frames / 60.0)
            d.stick(0, 0, which)
            print('ok')
        elif a.cmd == 'read':
            addr = int(a.addr, 0)
            vals = d.f32(addr, a.count) if a.float else d.u32(addr, a.count)
            vals = vals if isinstance(vals, list) else [vals]
            print(' '.join(f'{v:.6g}' if a.float else f'0x{v:08X}' for v in vals))
        elif a.cmd == 'pause':
            print(json.dumps(d.pause()))
        elif a.cmd == 'resume':
            print(json.dumps(d.resume()))


if __name__ == '__main__':
    _main()
