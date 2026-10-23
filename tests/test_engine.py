import copy
import unittest

from tank_arena.engine import initial_state, serialize, stars, step, supplies
from tank_arena.protocol import parse_command, parse_row, parse_state, StateStream
from tank_arena.scenarios import load_scenarios


def scene(rows=("MGGX",), normal=5, mega=2, hp=100, target_hp=100, rules=None, extra=None):
    return initial_state({"rows":list(rows), "units":{"M":{"normal":normal,"mega":mega,"hp":hp},
                          "X":{"hp":target_hp}, **(extra or {})}, "rules":rules or {}}, variant=False)


class ProtocolTests(unittest.TestCase):
    def test_rows_compact_spaced_multichar(self):
        self.assertEqual(parse_row("MGGE1X",5),["M","G","G","E1","X"])
        self.assertEqual(parse_row("G R T T R G R G E1 G",10)[8],"E1")
        self.assertEqual(parse_row("GRRGTGGRGX",10)[-1],"X")
        for row in ("", "G G", "G Z X", "GG?GX"):
            with self.subTest(row=row),self.assertRaises(ValueError):parse_row(row,5)

    def test_roundtrip_all_stage_dimensions(self):
        dimensions=[]
        for spec in load_scenarios():
            s=initial_state(spec)
            p=parse_state(serialize(s))
            self.assertEqual(p.grid,s.grid())
            self.assertEqual(p.allies['M'][0],str(s.units['M'].hp))
            dimensions.append((len(p.grid),len(p.grid[0])))
        self.assertIn((8,8),dimensions);self.assertIn((10,10),dimensions);self.assertIn((16,16),dimensions)
        self.assertIn((8,12),dimensions)

    def test_state_stream_every_byte_and_multiple(self):
        raw=serialize(scene());stream=StateStream()
        for b in raw.encode()[:-1]:
            stream.feed(bytes([b]));self.assertIsNone(stream.pop())
        stream.feed(raw.encode()[-1:]+raw.encode())
        self.assertEqual(stream.pop(),raw);self.assertEqual(stream.pop(),raw);self.assertIsNone(stream.pop())

    def test_empty_code_line_not_stripped(self):
        raw="1 4 1 1 1\nM G G X\nM 100 R 1 0\nX 30\n\n"
        stream=StateStream();stream.feed(raw.encode())
        self.assertEqual(parse_state(stream.pop()).codes,[""])

    def test_bad_states(self):
        for raw in ('', '1 4 1 1 0\nM G G X\n', '999999 1 1 1 0\n',serialize(scene())+serialize(scene())):
            with self.subTest(raw=raw[:20]),self.assertRaises(ValueError):parse_state(raw)

    def test_command_grammar(self):
        for action in ('A','F','F M','S','G VECTOR'):
            for prefix in ('','U ','D ','L ','R '):
                self.assertIsNotNone(parse_command(prefix+action))
        for command in ('','U','R A R A','F N','F M M','G','G lower','INIT Bot','A M','S F'):
            with self.subTest(command=command),self.assertRaises(ValueError):parse_command(command)


class EngineTests(unittest.TestCase):
    def test_pure_step_and_rotation_move(self):
        s=scene(('GGGX','GMGG','GGGG'));before=copy.deepcopy(s.snapshot())
        for direction,pos in [('U',(0,1)),('D',(2,1)),('L',(1,0)),('R',(1,2))]:
            t=step(s,direction+' A');u=t.units['M']
            self.assertEqual((u.row,u.col),pos);self.assertEqual(u.direction,direction);self.assertEqual(t.turn,1)
        self.assertEqual(s.snapshot(),before)

    def test_collision_every_obstacle_and_unit(self):
        for tile in ('W','R','T','F','M2','E1','X','H'):
            row=f'M {tile} G '+('G' if tile=='X' else 'X')
            s=scene((row,))
            t=step(s,'R A')
            self.assertEqual(t.units['M'].col,0,tile);self.assertEqual(t.turn,1)
            self.assertEqual(t.events[0]['kind'],'blocked_move')
        self.assertEqual(step(scene(),'L A').units['M'].direction,'L')

    def test_sand_entry_and_repeated_damage(self):
        s=scene(('MSGX',),hp=20)
        s=step(s,'R A');self.assertEqual(s.units['M'].hp,10)
        s=step(s,'L A');s=step(s,'R A')
        self.assertEqual(s.outcome,'fail');self.assertEqual(s.reason,'player_destroyed')
        self.assertEqual(step(s,'S').turn,s.turn)

    def test_range_water_sand(self):
        for row in ('MWGX','MSGX'):
            s=step(scene((row,),target_hp=30),'R F')
            self.assertEqual(s.outcome,'success')
        s=step(scene(('MGGGX',),target_hp=30),'R F')
        self.assertEqual(s.units['X'].hp,30)

    def test_damage_independent_ammunition(self):
        s=scene();s=step(s,'F');self.assertEqual(s.units['X'].hp,70)
        s=step(s,'F M');self.assertEqual(s.units['X'].hp,0);self.assertEqual(s.outcome,'success')
        self.assertEqual((s.units['M'].normal,s.units['M'].mega),(4,1))

    def test_tree_stops_shot_then_clears(self):
        s=scene(('MTGX',),target_hp=30)
        s=step(s,'R F');self.assertEqual(s.terrain[0][1],'G');self.assertEqual(s.units['X'].hp,30)
        s=step(s,'R F');self.assertEqual(s.outcome,'success')

    def test_rock_facility_and_friendly_block_shot(self):
        for tile in ('R','F','H'):
            s=step(scene((f'M {tile} G X',)),'F M')
            self.assertEqual(s.units['X'].hp,100)
            if tile == 'H':self.assertEqual(s.units[tile].hp,30)

    def test_friendly_policy_and_death(self):
        s=scene(('M M2 G X',),extra={'M2':{'hp':30}},rules={'friendly_fire':False})
        self.assertEqual(step(s,'F').units['M2'].hp,30)
        self.assertEqual(step(s,'F').units['X'].hp,70)
        s.rules.friendly_fire=True
        self.assertEqual(step(s,'F').units['M2'].hp,0)
        s=scene(('M H G X',),extra={'H':{'hp':30}})
        self.assertEqual(step(s,'F').reason,'friendly_turret_destroyed')

    def test_empty_ammo_turn_cost_no_fallback(self):
        s=step(scene(mega=0),'F M')
        self.assertEqual(s.units['M'].normal,5);self.assertEqual(s.turn,1)
        self.assertEqual(s.units['X'].hp,100);self.assertEqual(s.events[0]['kind'],'empty_ammo')

    def test_supply_adjacent_wrong_correct_repeated(self):
        s=scene(('FMGX',),mega=0)
        s.units['M'].direction='R'
        _,plain,code=supplies(s)[0]
        self.assertNotEqual(plain,code)
        wrong=step(s,'G WRONG');self.assertEqual(wrong.units['M'].mega,0)
        s=step(s,'G '+plain);self.assertEqual(s.units['M'].mega,1)
        s=step(s,'G '+supplies(s)[0][1]);self.assertEqual(s.units['M'].mega,2)
        self.assertEqual(s.turn,2);self.assertEqual(s.terrain[0][0],'F')
        far=scene(('MGFX',),mega=0)
        self.assertEqual(supplies(far),[])
        self.assertEqual(step(far,'G VECTOR').units['M'].mega,0)

    def test_code_changes_and_deterministic(self):
        s=scene(('FMGX',));self.assertEqual(serialize(s),serialize(copy.deepcopy(s)))
        self.assertEqual(supplies(s),supplies(copy.deepcopy(s)))
        self.assertGreater(len({supplies(step(s,'S'))[0][2],supplies(s)[0][2],supplies(step(step(s,'S'),'S'))[0][2]}),1)

    def test_invalid_consumes_or_fails(self):
        s=scene();self.assertEqual(step(s,'R A R A').turn,1)
        s.rules.invalid_command='fail';self.assertEqual(step(s,'NOPE').reason,'invalid_command')

    def test_turn_limit_and_winning_boundary(self):
        s=scene(rules={'max_turns':1,'three_stars':1,'two_stars':1},target_hp=30)
        self.assertEqual(step(s,'S').reason,'turn_limit')
        self.assertEqual(step(s,'F').outcome,'success')

    def test_star_boundaries(self):
        s=scene();s.outcome='success'
        for turn,expected in ((30,3),(31,2),(60,2),(61,1)):
            s.turn=turn;self.assertEqual(stars(s),expected)
        s.outcome='fail';self.assertEqual(stars(s),0)

    def test_spec_validation(self):
        for rows in (('MMGX',),('MGG',),('MX','GGGG')):
            with self.assertRaises(ValueError):scene(rows)
        with self.assertRaises(ValueError):scene(rules={'three_stars':90,'two_stars':60})


if __name__=='__main__':unittest.main()
