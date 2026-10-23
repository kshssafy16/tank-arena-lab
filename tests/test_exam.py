import sys
from pathlib import Path
import unittest

from tank_arena.engine import serialize
from tank_arena.exam import Run
from tank_arena.scenarios import load_scenarios

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'examples'))
from bot_exam_general import decide


def tiny_specs():
    return [{'stage':i,'name':f'Test {i}','skill':'synthetic test','rows':['M G G X'],
             'units':{'M':{'normal':1},'X':{'hp':30}},
             'rules':{'three_stars':1,'two_stars':2,'max_turns':3}} for i in range(1,7)]


class ExamTests(unittest.TestCase):
    def test_exact_order_min_score_and_reset(self):
        run=Run(tiny_specs())
        for i in range(12):
            self.assertEqual((run.stage,run.attempt),(i//2+1,i%2+1))
            self.assertEqual(run.state.turn,0);self.assertEqual(run.state.units['M'].normal,1)
            if i%2:run.apply('S')
            run.apply('R F' if run.state.units['M'].col==0 else 'L F')
        self.assertTrue(run.finished);self.assertFalse(run.failure)
        self.assertEqual(run.summary()['total_stars'],12)
        self.assertTrue(all(s['stars']==2 for s in run.summary()['scores']))

    def test_fail_first_and_second_terminate(self):
        for second in (False,True):
            run=Run(tiny_specs())
            if second:run.apply('R F')
            run.record_failure('client_disconnected')
            self.assertTrue(run.finished);self.assertEqual(run.stage,1)
            self.assertEqual(len(run.results),2 if second else 1)
            self.assertEqual(run.summary()['total_stars'],0)
            before=len(run.history);run.apply('R F');self.assertEqual(len(run.history),before)

    def test_partial_results_keep_previous_stages(self):
        run=Run(tiny_specs());run.apply('R F');run.apply('L F');run.record_failure('command_timeout')
        self.assertEqual(run.stage,2);self.assertEqual(run.summary()['total_stars'],3)

    def test_practice_any_stage_and_repeatability(self):
        for stage in range(1,7):
            run=Run(load_scenarios(),'practice',stage=stage,seed=42)
            initial=serialize(run.state);run.apply('S')
            retry=Run(load_scenarios(),'practice',stage=stage,seed=42)
            self.assertEqual(serialize(retry.state),initial)

    def test_no_intermediate_old_frame(self):
        run=Run(tiny_specs());run.apply('R F')
        self.assertEqual(run.attempt,2);self.assertEqual(run.state.turn,0)
        self.assertIn('X 30',serialize(run.state))

    def test_seeded_general_bot_100_runs(self):
        specs=load_scenarios()
        for seed in range(100):
            run=Run(specs,seed=seed)
            while not run.finished:
                run.apply(decide(serialize(run.state)))
            with self.subTest(seed=seed):
                self.assertEqual(len(run.results),12)
                self.assertFalse(run.failure)
                self.assertEqual(run.summary()['total_stars'],18)


if __name__=='__main__':unittest.main()
