// Validate the Python interchange at the renderer boundary, without coercing or
// silently dropping invalid geometry. Coordinates are native world-space pairs.
export type Point = [number, number];
export type Actor = {joints: Record<string, Point>; depth: number};
export type Prop = {id:string; kind:string; pos:Point; size:Point; angle:number; glyph:string|null; z:number};
export type Frame = {t:number; actors:Record<string,Actor>; props:Prop[]};
export type NativeExport = {version:number; fps:number; width:number; height:number; duration:number; frames:Frame[]};

function fail(path:string): never {throw new Error('Invalid APEX interchange: '+path);}
function obj(v:unknown,p:string):Record<string,unknown> {
  if (v === null || typeof v !== 'object' || Array.isArray(v)) return fail(p);
  return v as Record<string,unknown>;
}
function number(v:unknown,p:string):number {
  if (typeof v !== 'number' || !Number.isFinite(v)) return fail(p);
  return v;
}
function positive(v:unknown,p:string):number {const n=number(v,p); if(n<=0)return fail(p);return n;}
function str(v:unknown,p:string):string {if(typeof v !== 'string')return fail(p);return v;}
function arr(v:unknown,p:string):unknown[] {if(!Array.isArray(v))return fail(p);return v;}
function pair(v:unknown,p:string):Point {
  const a=arr(v,p); if(a.length!==2)return fail(p);
  return [number(a[0],p+'[0]'),number(a[1],p+'[1]')];
}
const jointsRequired=['pelvis','spine_mid','neck_base','neck_top','head_center','head_top',
  ...['f','n'].flatMap(s=>['shoulder','elbow','wrist','hand','hip','knee','ankle','toe'].map(j=>j+'_'+s))];
export function parseNativeExport(input:unknown):NativeExport {
  const d=obj(input,'root');
  if(d.version!==1)return fail('version');
  const fps=positive(d.fps,'fps'),width=positive(d.width,'width'),height=positive(d.height,'height');
  const duration=positive(d.duration,'duration');
  const frames=arr(d.frames,'frames').map((value,i):Frame=>{
    const p='frames['+i+']',f=obj(value,p);
    const t=number(f.t,p+'.t');
    if(Math.abs(t-i/fps)>1e-6 || t>duration+1e-6)return fail(p+'.t');
    const actors:Record<string,Actor>=Object.create(null);
    for(const [id,value] of Object.entries(obj(f.actors,p+'.actors'))){
      const a=obj(value,p+'.actors.'+id);
      const joints:Record<string,Point>=Object.create(null);
      for(const [key,v] of Object.entries(obj(a.joints,p+'.joints')))joints[key]=pair(v,p+'.joints.'+key);
      for(const key of jointsRequired)if(!joints[key])return fail(p+'.joints.'+key);
      actors[id]={joints,depth:number(a.depth,p+'.depth')};
    }
    const seen=new Set<string>();
    const props=arr(f.props,p+'.props').map((value,j):Prop=>{
      const q=p+'.props['+j+']',o=obj(value,q),id=str(o.id,q+'.id');
      if(seen.has(id))return fail(q+'.id'); seen.add(id);
      const size=pair(o.size,q+'.size'); if(size.some(n=>n<=0))return fail(q+'.size');
      return {id,kind:str(o.kind,q+'.kind'),pos:pair(o.pos,q+'.pos'),size,
        angle:number(o.angle,q+'.angle'),glyph:o.glyph===null?null:str(o.glyph,q+'.glyph'),z:number(o.z,q+'.z')};
    });
    return {t,actors,props};
  });
  if(frames.length!==Math.floor(duration*fps)+1)return fail('frame count');
  return {version:1,fps,width,height,duration,frames};
}
