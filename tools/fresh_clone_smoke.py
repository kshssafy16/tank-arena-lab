"""Local clone -> setup -> CLI server -> one bot -> 12 results; no source inputs."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'dist'/('smoke-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    clone=folder/'checkout'
    subprocess.run(['git','clone','--quiet','--no-hardlinks',str(ROOT),str(clone)],check=True)
    assert not (clone/'.private_reference').exists()
    setup=['cmd','/c',r'scripts\setup.bat'] if os.name=='nt' else ['sh','scripts/setup.sh']
    subprocess.run(setup,cwd=clone,check=True,timeout=90)
    python=clone/('.venv/Scripts/python.exe' if os.name=='nt' else '.venv/bin/python')
    server=subprocess.Popen([str(python),'run.py','--mode','exam','--tcp-port','0','--http-port','0','--turn-delay','0','--no-browser'],
                            cwd=clone,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:
        first=server.stdout.readline()
        match=re.search(r'UI (http://127\.0\.0\.1:\d+) \| TCP 127\.0\.0\.1:(\d+)',first)
        if not match:raise RuntimeError('Server did not start: '+first)
        url,port=match.groups()
        bot=subprocess.run([str(python),'examples/bot_exam_general.py','--port',port],cwd=clone,
                           capture_output=True,text=True,timeout=30,check=True)
        with urllib.request.urlopen(url+'/api/state') as response:view=json.load(response)
        summary=view['run']
        assert summary['finished'] and not summary['failure'],summary
        assert summary['connections']==1 and summary['completed_attempts']==12,summary
        assert bot.stdout.count('CONNECTIONS=1')==1
        with urllib.request.urlopen(url+'/api/replay') as response:replay=json.load(response)
        assert len(replay['results'])==12
        report={'fresh_clone':True,'setup':'PASS','original_material_required':False,
                'single_process':True,'connections':summary['connections'],'attempts':summary['completed_attempts'],
                'total_stars':summary['total_stars'],'platform':sys.platform,'python':sys.version.split()[0]}
        (folder/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:
        server.terminate()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.wait()


if __name__=='__main__':main()
