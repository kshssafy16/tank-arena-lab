"""Verify all saved state transitions by deterministically replaying commands."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tank_arena.exam import Run


def verify(data):
    if data.get('format')!='tank-arena-replay-v1':raise ValueError('Unknown replay format')
    summary=data['summary']
    initial_stage=data['history'][0]['stage']
    run=Run(data['scenarios'],summary['mode'],initial_stage,summary['seed'],summary['profile'])
    for index,record in enumerate(data['history']):
        if record['type']=='turn':
            if (run.stage,run.attempt)!=(record['stage'],record['attempt']):raise ValueError(f'Attempt mismatch at entry {index}')
            run.apply(record['command'])
            actual=next(x for x in reversed(run.history) if x['type']=='turn')
            if actual['state']!=record['state']:raise ValueError(f'State mismatch at entry {index}')
        elif record['type']=='start':
            actual=next(x for x in reversed(run.history) if x['type']=='start')
            if actual['state']!=record['state']:raise ValueError(f'Initial state mismatch at entry {index}')
        else:raise ValueError('Unknown replay record')
    if not run.finished and summary['finished']:
        run.record_failure(summary['failure'])
    if run.results!=data['results']:raise ValueError('Result mismatch')
    if run.summary()['total_stars']!=summary['total_stars']:raise ValueError('Score mismatch')
    return {'verified_turns':sum(x['type']=='turn' for x in data['history']),
            'attempts':len(run.results),'total_stars':run.summary()['total_stars']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('replay',type=Path)
    args=parser.parse_args()
    print(json.dumps(verify(json.loads(args.replay.read_text(encoding='utf-8')))))
