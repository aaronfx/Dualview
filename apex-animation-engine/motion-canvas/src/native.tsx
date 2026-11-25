import {Circle, Line, Rect, Txt, Node, makeScene2D} from '@motion-canvas/2d';
import {createSignal, tween} from '@motion-canvas/core';
import raw from './native.json';

type Point = [number, number];
type Actor = {joints: Record<string, Point>; depth: number};
type Prop = {id:string; kind:string; pos:Point; size:Point; angle:number; glyph:string|null; z:number};
type Frame = {t:number; actors:Record<string,Actor>; props:Prop[]};
type Export = {version:number; fps:number; width:number; height:number; duration:number; frames:Frame[]};
const data = raw as Export;
const chains = [
  ['pelvis','spine_mid','neck_base','neck_top'],
  ...['f','n'].flatMap(s => [
    ['shoulder_'+s,'elbow_'+s,'wrist_'+s,'hand_'+s],
    ['pelvis','hip_'+s,'knee_'+s,'ankle_'+s,'toe_'+s],
  ]),
];
const colors = ['#efac38','#4c9aff','#57c78b','#de708a'];
if (data.version !== 1 || !data.frames.length || data.fps <= 0) throw new Error('Invalid APEX interchange');

export default makeScene2D(function* (view) {
  const index = createSignal(0);
  const frame = () => data.frames[Math.min(data.frames.length - 1, Math.floor(index()))];
  const actorIds = [...new Set(data.frames.flatMap(f => Object.keys(f.actors)))];
  const props = new Map(data.frames.flatMap(f => f.props.map(p => [p.id,p] as const)));
  // Fixed world overview, not the native cinematic camera. A common uniform scale preserves geometry.
  const scale = 0.7;
  const point = (p: Point): Point => [p[0]*scale, -p[1]*scale+220];
  view.add(<Rect width={'100%'} height={'100%'} fill={'#16202f'}/>);
  view.add(<Line points={[[-1000,220],[1000,220]]} stroke={'#63778b'} lineWidth={3}/>);
  for (const id of actorIds) {
    const color = colors[actorIds.indexOf(id)%colors.length];
    const joints = () => frame().actors[id]?.joints;
    const joint = (name:string):Point => point(joints()?.[name] ?? [0,0]);
    view.add(<Node opacity={() => joints()?1:0}>
      {chains.map(chain => <Line points={() => chain.map(joint)} stroke={color}
        lineWidth={7} lineCap={'round'} lineJoin={'round'}/>)}
      <Circle position={() => joint('head_center')}
        size={() => {const a=joint('head_center'), b=joint('head_top'); return Math.max(8,2*Math.hypot(a[0]-b[0],a[1]-b[1]));}}
        stroke={color} fill={'#16202f'} lineWidth={6}/>
    </Node>);
  }
  for (const [id, initial] of props) {
    const current = () => frame().props.find(p => p.id === id);
    view.add(<Node opacity={() => current()?1:0} position={() => point(current()?.pos ?? initial.pos)}
      rotation={() => -(current()?.angle ?? 0)*180/Math.PI}>
      {initial.kind === 'glyph' ? <Txt text={() => current()?.glyph ?? ''} fill={'#f1f5f9'} fontSize={initial.size[1]*scale}/> :
        <Rect size={[initial.size[0]*scale,initial.size[1]*scale]} fill={'#536579'} stroke={'#a7b7c8'} lineWidth={2}/>}
    </Node>);
  }
  yield* tween(data.duration, value => index(value*(data.frames.length-1)));
});
