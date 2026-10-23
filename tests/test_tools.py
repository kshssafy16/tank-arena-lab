from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from tank_arena.engine import initial_state,serialize,step
from tank_arena.exam import Run
from tank_arena.scenarios import load_scenarios
from test_engine import scene
from test_exam import tiny_specs

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from reference_import import specification
from parity_check import compare
from release_check import scan
from verify_replay import verify


class ToolTests(unittest.TestCase):
    def test_capture_import_private_profile_and_fail_on_missing_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'stages').mkdir()
            spec=specification(serialize(scene()),4)
            (root/'stages/stage4.json').write_text(json.dumps(spec),encoding='utf-8')
            specs=load_scenarios('private',root)
            self.assertFalse(specs[0]['available'])
            self.assertEqual(Run(specs,'practice',stage=4,profile='private').stage,4)
            with self.assertRaises(ValueError):Run(specs,profile='private')

    def test_private_variant_selection_no_immediate_repeat(self):
        specs=tiny_specs()
        for spec in specs:
            spec['variants']=[{'rows':['M G G X']},{'rows':['X G G M']}]
        run=Run(specs,profile='private')
        while not run.finished:
            run.apply('R F' if run.state.units['M'].col==0 else 'L F')
        self.assertEqual(len(run.results),12)
        variants=[x['variant'] for x in run.results]
        self.assertTrue(all(a!=b for a,b in zip(variants,variants[1:])))

    def test_differential_trace_detects_real_difference(self):
        s=scene(target_hp=100);after=step(s,'R A')
        trace={'initial':serialize(s),'turns':[{'command':'R A','expected':serialize(after)}]}
        self.assertTrue(compare(trace)['matches'])
        trace['turns'][0]['expected']=serialize(s)
        self.assertFalse(compare(trace)['matches'])

    def test_replay_reexecutes_and_detects_tampering(self):
        run=Run(tiny_specs())
        while not run.finished:run.apply('R F' if run.state.units['M'].col==0 else 'L F')
        data=run.replay();self.assertEqual(verify(data)['attempts'],12)
        data['history'][1]['state']['units']['M']['hp']=3
        with self.assertRaises(ValueError):verify(data)

    def test_release_guard_tracks_private_binary_brand_credentials_and_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);private=root/'.private_reference';(private/'stages').mkdir(parents=True)
            (root/'safe.py').write_text('print(1)',encoding='utf-8')
            self.assertEqual(scan(root,['safe.py'],private),[])
            (private/'stages/stage1.json').write_text(json.dumps({'rows':['M G X']}),encoding='utf-8')
            (root/'map.json').write_text(json.dumps({'rows':['M G X']}),encoding='utf-8')
            (root/'bad.bin').write_bytes(b'MZpayload')
            (root/'brand.txt').write_text(bytes.fromhex('7373616679').decode(),encoding='utf-8')
            (root/'secret.txt').write_text('ABCD'+'-'+'EFGH'+'-'+'IJKL'+'-'+'MNOP',encoding='utf-8')
            for name in ('map.json','bad.bin','brand.txt','secret.txt','.private_reference/stages/stage1.json'):
                with self.subTest(name=name):self.assertTrue(scan(root,[name],private))

    def test_supply_cap_and_terminal_packet(self):
        s=scene(('FMGX',),mega=10)
        from tank_arena.engine import supplies
        from tank_arena.protocol import parse_state,StateStream
        self.assertEqual(step(s,'G '+supplies(s)[0][1]).units['M'].mega,10)
        stream=StateStream();stream.feed(b'0 0 0 0 0\n')
        self.assertEqual(parse_state(stream.pop()).grid,[])

    def test_dynamic_terrain_replanning_and_npc_determinism(self):
        spec={'rows':['M G G X','G G G G','E1 G G G'],
              'units':{'M':{'normal':1},'X':{'hp':30}},
              'terrain_schedule':[{'turn':1,'changes':[{'row':0,'col':1,'tile':'W'}]}],
              'npc_schedule':[{'turn':1,'unit':'E1','directions':['R']}]}
        s=initial_state(spec,variant=False);t=step(s,'S')
        self.assertEqual(t.terrain[0][1],'W');self.assertEqual(t.units['E1'].col,1)
        self.assertEqual(t.snapshot(),step(s,'S').snapshot())
        mirrored=initial_state(spec,seed=1);m=step(mirrored,'S')
        self.assertEqual(m.terrain[0][2],'W')


if __name__=='__main__':unittest.main()
