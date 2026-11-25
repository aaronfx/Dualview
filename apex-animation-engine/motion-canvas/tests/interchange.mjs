import assert from 'node:assert/strict';
import {parseNativeExport} from '../src/interchange.ts';
import {readFileSync} from 'node:fs';
const source=JSON.parse(readFileSync(new URL('../src/native.json',import.meta.url),'utf8'));
const valid=parseNativeExport(source);
assert.equal(valid.frames.length,source.frames.length);
assert.deepEqual(valid.frames[0].actors[Object.keys(source.frames[0].actors)[0]].joints.pelvis,
 source.frames[0].actors[Object.keys(source.frames[0].actors)[0]].joints.pelvis);
const bad=structuredClone(source);
const actor=Object.values(bad.frames[0].actors)[0];
actor.joints.pelvis=[1,2,3];
assert.throws(()=>parseNativeExport(bad),/pelvis/);
const missing=structuredClone(source);
delete Object.values(missing.frames[0].actors)[0].joints.head_center;
assert.throws(()=>parseNativeExport(missing),/head_center/);
const timing=structuredClone(source);
timing.frames[1].t+=1;
assert.throws(()=>parseNativeExport(timing),/\.t/);
console.log('APEX interchange: real native scene accepted; malformed geometry and timing rejected');
