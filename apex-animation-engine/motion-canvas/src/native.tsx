import {Circle, Line, Rect, Txt, Node, makeScene2D} from '@motion-canvas/2d';
import {createSignal, tween} from '@motion-canvas/core';
import raw from './native.json';
import {parseNativeExport, type Point} from './interchange';
const data = parseNativeExport(raw);
const chains = [
  ['pelvis','spine_mid','neck_base','neck_top'],
  ...['f','n'].flatMap(s => [
    ['shoulder_'+s,'elbow_'+s,'wrist_'+s,'hand_'+s],
    ['pelvis','hip_'+s,'knee_'+s,'ankle_'+s,'toe_'+s],
  ]),
];
export default makeScene2D(function* (view) {
  const index=createSignal(0);
  const frame=()=>data.frames[Math.min(data.frames.length-1,Math.floor(index()+1e-7))];
  const cam=()=>frame().camera;
  // Same native perspective projection at each depth plane, before screen roll.
  const scale=(z:number)=>data.height*1.1/Math.max(20,cam().view_h*1.1+z);
  const point=(p:Point,z=0):Point=>[(p[0]-cam().cx)*scale(z),-(p[1]-cam().cy)*scale(z)];
  const room=data.room, theme=data.theme, hw=room.width/2, rh=room.height, back=room.depth_back;
  view.add(<Rect width={'100%'} height={'100%'} fill={theme.background}/>);
  const world=new Node({rotation:()=>cam().roll,position:()=>[cam().shx*data.height/1080,cam().shy*data.height/1080]});
  view.add(world);
  const polygon=(pts:[number,number,number][],color:string)=>world.add(<Line zIndex={-100000} closed points={()=>pts.map(([x,y,z])=>point([x,y],z))} fill={color}/>);
  polygon([[-hw,0,back],[hw,0,back],[hw,rh,back],[-hw,rh,back]],theme.back);
  polygon([[-hw,0,-100],[hw,0,-100],[hw,0,back],[-hw,0,back]],theme.floor);
  polygon([[-hw,0,-100],[-hw,0,back],[-hw,rh,back],[-hw,rh,-100]],theme.side);
  polygon([[hw,0,-100],[hw,0,back],[hw,rh,back],[hw,rh,-100]],theme.side);
  const step=Math.max(room.grid_spacing,20);
  for(let x=-hw;x<=hw;x+=step)world.add(<Line zIndex={-99999} points={()=>[point([x,0],back),point([x,rh],back)]} stroke={theme.accent} opacity={0.12} lineWidth={1}/>);
  for(let y=0;y<=rh;y+=step)world.add(<Line zIndex={-99999} points={()=>[point([-hw,y],back),point([hw,y],back)]} stroke={theme.accent} opacity={0.12} lineWidth={1}/>);
  const actorIds=[...new Set(data.frames.flatMap(f=>Object.keys(f.actors)))];
  const props=new Map(data.frames.flatMap(f=>f.props.map(p=>[p.id,p] as const)));
  for(const id of actorIds){
    const style=data.styles[id];
    const actor=()=>frame().actors[id];
    const z=()=>actor()?.depth??0;
    const joint=(name:string):Point=>point(actor()?.joints[name]??[0,0],z());
    world.add(<Node opacity={()=>actor()?1:0} zIndex={()=>-z()}>
      {chains.map((chain,i)=><Line points={()=>chain.map(joint)} stroke={i===1||i===2?style.far_color:style.body_color}
        lineWidth={()=>Math.max(1,style.limb_width*scale(z()))} lineCap={'round'} lineJoin={'round'}/>)}
      <Circle position={()=>joint('head_center')} size={()=>{const a=joint('head_center'),b=joint('head_top');return Math.max(8,2*Math.hypot(a[0]-b[0],a[1]-b[1]));}}
        stroke={style.body_color} fill={theme.background} lineWidth={()=>Math.max(1,style.limb_width*scale(z())*.8)}/>
    </Node>);
  }
  for(const [id,initial] of props){
    const current=()=>frame().props.find(p=>p.id===id);
    const z=()=>current()?.z??initial.z;
    const size=():Point=>{const p=current()??initial;return [p.size[0]*scale(z()),p.size[1]*scale(z())];};
    world.add(<Node opacity={()=>current()?1:0} zIndex={()=>-z()} position={()=>point(current()?.pos??initial.pos,z())}
      rotation={()=>-(current()?.angle??0)*180/Math.PI}>
      {initial.kind==='glyph'?<Txt text={()=>current()?.glyph??''} fill={theme.accent} fontSize={()=>size()[1]}/>:
        <Rect size={size} fill={'#536579'} stroke={'#a7b7c8'} lineWidth={2}/>}
    </Node>);
  }
  view.add(<Rect width={'100%'} height={'100%'} fill={'#000000'} opacity={()=>frame().fade} zIndex={10000}/>);
  yield* tween(data.duration,value=>index(value*(data.frames.length-1)));
});
