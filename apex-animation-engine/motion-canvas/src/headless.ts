import {editorBootstrap, Renderer, RendererResult} from '@motion-canvas/core/lib/app';
import {MetaFile} from '@motion-canvas/core/lib/meta';
import {Vector2} from '@motion-canvas/core';
import settings from './project';
import raw from './native.json';
import {parseNativeExport} from './interchange';

const data = parseNativeExport(raw);
const run = async () => {
  const project = await editorBootstrap('apex-rescue',
    {core:'3.17.2',two:'3.17.2',ui:null,vitePlugin:'3.17.2'},
    [],settings,new MetaFile('headless-project',false),new MetaFile('headless-settings',false));
  const renderer = new Renderer(project);
  const result = new Promise<RendererResult>(resolve => renderer.onFinished.subscribe(resolve));
  await renderer.render({
    name:'apex-rescue',size:new Vector2(data.width,data.height),resolutionScale:2/3,
    fps:data.fps,range:[0,data.duration],colorSpace:'srgb',background:'#16202f',
    exporter:{name:'@motion-canvas/core/image-sequence',options:{fileType:'image/png',quality:100,groupByScene:false}}
  });
  if(await result!==RendererResult.Success)throw new Error('Motion Canvas renderer failed');
  return {fps:data.fps,duration:data.duration};
};
Object.assign(window,{apexRender:run});
