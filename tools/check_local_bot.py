"""Execute a user's existing Python script unchanged against local practice.

Only use your own trusted scripts. No subprocess sandbox is implied.
The original source is not copied; results and stdout stay private.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tank_arena.server import Arena,create_servers


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('bot',type=Path)
    p.add_argument('--mode',choices=['practice','exam'],default='practice')
    p.add_argument('--stage',type=int,choices=range(1,7),default=1)
    p.add_argument('--timeout',type=float,default=30)
    p.add_argument('--profile',choices=['public','private'],default='public')
    args=p.parse_args();bot=args.bot.resolve()
    before=hashlib.sha256(bot.read_bytes()).hexdigest()
    output=ROOT/'.private_reference/local_bot';output.mkdir(parents=True,exist_ok=True)
    arena=Arena(output=output,delay=0,profile=args.profile)
    arena.configure(args.mode,args.stage)
    tcp,http=create_servers(arena,8747,0)
    try:
        proc=subprocess.run([sys.executable,'-B',str(bot)],cwd=ROOT,capture_output=True,timeout=args.timeout)
        end=time.monotonic()+2
        while arena.client is not None and time.monotonic()<end:time.sleep(.01)
        after=hashlib.sha256(bot.read_bytes()).hexdigest()
        report={'source_unchanged':before==after,'source_sha256':before,'returncode':proc.returncode,
                'summary':arena.run.summary(),'note':'Local simulator test; not a live original-game differential test'}
        (output/'stdout.txt').write_bytes(proc.stdout)
        (output/'stderr.txt').write_bytes(proc.stderr)
        (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:
        with arena.lock:
            arena.generation+=1
            if arena.client:
                try:arena.client.shutdown(2)
                except OSError:pass
            arena.lock.notify_all()
        tcp.shutdown();http.shutdown();tcp.server_close();http.server_close()


if __name__=='__main__':main()
