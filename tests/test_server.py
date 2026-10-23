from contextlib import contextmanager
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from tank_arena.protocol import CommandReader
from tank_arena.server import Arena, create_servers
from test_exam import tiny_specs

ROOT=Path(__file__).resolve().parents[1]


@contextmanager
def server(specs=None,timeout=None,mode='exam'):
    with tempfile.TemporaryDirectory() as tmp:
        arena=Arena(specs=specs,output=tmp,timeout=timeout,delay=0)
        arena.configure(mode)
        tcp,http=create_servers(arena,0,0)
        try:yield arena,tcp.server_address[1],http.server_port
        finally:
            with arena.lock:
                arena.generation+=1
                if arena.client:
                    try:arena.client.shutdown(socket.SHUT_RDWR)
                    except OSError:pass
                arena.lock.notify_all()
            tcp.shutdown();http.shutdown();tcp.server_close();http.server_close()


def await_result(arena):
    end=time.monotonic()+3
    while time.monotonic()<end:
        with arena.lock:
            if arena.run.finished and arena.saved and arena.client is None:return
        time.sleep(.01)
    raise AssertionError('Run did not finish/save/close')


class NetworkTests(unittest.TestCase):
    def test_actual_single_python_process_single_tcp_12_attempts(self):
        with server() as (arena,port,http):
            result=subprocess.run([sys.executable,str(ROOT/'examples/bot_exam_general.py'),'--port',str(port)],
                                  cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            await_result(arena)
            summary=arena.run.summary()
            self.assertEqual(summary['connections'],1)
            self.assertEqual(summary['completed_attempts'],12)
            self.assertEqual(summary['total_stars'],18)
            self.assertEqual(result.stdout.count('CONNECTIONS=1'),1)
            replay=json.loads(Path(arena.replay_path).read_text(encoding='utf-8'))
            self.assertEqual(len(replay['results']),12)
            self.assertEqual([(x['stage'],x['attempt']) for x in replay['results']],[(s,a) for s in range(1,7) for a in (1,2)])

    def test_legacy_trailing_space_client_12_attempts(self):
        with server(tiny_specs()) as (arena,port,_):
            with socket.create_connection(('127.0.0.1',port)) as conn:
                conn.settimeout(3);conn.sendall('INIT 한글닉네임 '.encode())
                for _ in range(12):
                    raw=conn.recv(8192);self.assertTrue(raw.startswith(b'1 4 1 1 0'))
                    conn.sendall(b'R F ' if b'M G G X' in raw else b'L F ')
                self.assertEqual(conn.recv(8192),b'0 0 0 0 0\n')
            await_result(arena);self.assertEqual(arena.run.connections,1)
            self.assertEqual(arena.run.summary()['total_stars'],18)

    def test_timeout_disconnect_runtime_indistinguishable(self):
        with server(tiny_specs(),timeout=.08) as (arena,port,_):
            with socket.create_connection(('127.0.0.1',port)) as conn:
                conn.sendall(b'INIT Slow\n');conn.recv(8192);time.sleep(.15)
            await_result(arena);self.assertEqual(arena.run.failure,'command_timeout')
        with server(tiny_specs()) as (arena,port,_):
            with socket.create_connection(('127.0.0.1',port)) as conn:
                conn.sendall(b'INIT Exit\n');conn.recv(8192)
            await_result(arena);self.assertEqual(arena.run.failure,'client_disconnected')

    def test_fragmented_utf8_init_and_command(self):
        with server(tiny_specs(),mode='practice') as (arena,port,_):
            with socket.create_connection(('127.0.0.1',port)) as conn:
                for byte in 'INIT 실험\n'.encode():conn.sendall(bytes([byte]));time.sleep(.001)
                conn.recv(8192)
                for block in (b'R',b' ',b'F',b'\n'):conn.sendall(block);time.sleep(.005)
                self.assertEqual(conn.recv(8192),b'0 0 0 0 0\n')
            await_result(arena);self.assertEqual(arena.run.nickname,'실험')

    def test_coalesced_stale_commands_rejected(self):
        with server(tiny_specs()) as (arena,port,_):
            with socket.create_connection(('127.0.0.1',port)) as conn:
                conn.sendall(b'INIT Pipeline\n');conn.recv(8192);conn.sendall(b'R F\nR F\n');conn.recv(8192)
            await_result(arena);self.assertEqual(arena.run.failure,'protocol_error')

    def test_newline_mode_does_not_guess_fragment_boundary(self):
        with server(tiny_specs(),mode='practice') as (arena,port,_):
            with socket.create_connection(('127.0.0.1',port)) as conn:
                conn.sendall(b'INIT Framed\n');conn.recv(8192)
                conn.sendall(b'R ');time.sleep(.12);conn.sendall(b'F\n')
                self.assertEqual(conn.recv(8192),b'0 0 0 0 0\n')
            await_result(arena)
            self.assertFalse(arena.run.failure)
            self.assertEqual(arena.run.results[0]['turns'],1)

    def test_disconnect_during_pause_is_not_left_pending(self):
        with server(tiny_specs(),mode='practice') as (arena,port,_):
            arena.control({'action':'pause'})
            with socket.create_connection(('127.0.0.1',port)) as conn:
                conn.sendall(b'INIT Leaving\n');conn.recv(8192);conn.sendall(b'S\n');time.sleep(.03)
            await_result(arena)
            self.assertEqual(arena.run.failure,'client_disconnected')

    def test_second_client_does_not_replace_active_client(self):
        with server(tiny_specs()) as (arena,port,_):
            with socket.create_connection(('127.0.0.1',port)) as first:
                first.sendall(b'INIT Owner\n');first.recv(8192)
                with socket.create_connection(('127.0.0.1',port)) as second:
                    second.settimeout(2);self.assertEqual(second.recv(8192),b'')
                self.assertEqual(arena.run.connections,1);self.assertEqual(arena.run.nickname,'Owner')

    def test_http_assets_controls_origin_and_export(self):
        with server(tiny_specs(),mode='practice') as (arena,_,port):
            base=f'http://127.0.0.1:{port}'
            for path in ('/','/app.js','/style.css','/api/state','/api/replay'):
                with urllib.request.urlopen(base+path) as r:self.assertEqual(r.status,200)
            def post(body,origin=None):
                headers={'Content-Type':'application/json'}
                if origin:headers['Origin']=origin
                return urllib.request.urlopen(urllib.request.Request(base+'/api/control',data=json.dumps(body).encode(),headers=headers))
            with post({'action':'command','command':'R F'}) as r:self.assertEqual(r.status,200)
            self.assertTrue(arena.run.finished)
            with self.assertRaises(urllib.error.HTTPError) as e:post({'action':'reset'},'https://example.invalid')
            self.assertEqual(e.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError) as e:post([])
            self.assertEqual(e.exception.code,400)
            with post({'action':'start','mode':'exam'}):pass
            with self.assertRaises(urllib.error.HTTPError):post({'action':'command','command':'R F'})

    def test_reset_generation_cannot_fail_new_run(self):
        with server(tiny_specs(),mode='practice') as (arena,port,_):
            with socket.create_connection(('127.0.0.1',port)) as conn:
                conn.sendall(b'INIT Old\n');conn.recv(8192)
                arena.configure('practice',stage=2)
                time.sleep(.05)
                self.assertFalse(arena.run.finished);self.assertEqual(arena.run.stage,2)
                self.assertEqual(arena.run.connections,0)

    def test_pause_step_preserves_one_pending_action(self):
        with server(tiny_specs(),mode='practice') as (arena,port,_):
            arena.control({'action':'pause'})
            with socket.create_connection(('127.0.0.1',port)) as conn:
                conn.sendall(b'INIT Stepper\n');conn.recv(8192);conn.sendall(b'S\n');time.sleep(.05)
                self.assertEqual(arena.run.state.turn,0)
                arena.control({'action':'step'});conn.recv(8192)
                self.assertEqual(arena.run.state.turn,1)
                conn.sendall(b'R F\n');time.sleep(.03);self.assertFalse(arena.run.finished)
                arena.control({'action':'step'});self.assertEqual(conn.recv(8192),b'0 0 0 0 0\n')
            await_result(arena);self.assertEqual(arena.run.results[0]['turns'],2)


if __name__=='__main__':unittest.main()
