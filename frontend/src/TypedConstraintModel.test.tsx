// @vitest-environment jsdom
import React from 'react';
import {test,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {TypedConstraint} from './TypedConstraint';
import {words} from './i18n';
import type {Workspace} from './api';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const ws={version:23,records:[],rules:[],events:[],name:'Test',term:'Test'} as Workspace;
const proposal={id:'p1',review:null,record:{text:'Prefer later lectures',origin:'provider_response',output:{decision:'ready',proposals:[{kind:'rule',data:{type:'teaching_preferred',title:'Later lectures',day:null,start_hour:10,end_hour:18,strength:'preferred',params:{activity_types:['lecture']}}}],clarifications:[],unsupported:[]}}};
test('Interpret uses the local model and previews a soft proposal without creating rules',async()=>{
 const calls:{path:string;body?:unknown}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{calls.push({path,body:options?.body?JSON.parse(String(options.body)):undefined});return {ok:true,status:200,json:async()=>path.includes('/configuration')?{enabled:true,provider:'local'}:path==='/api/model-calls'?{status:'completed',proposal_id:'p1'}:{proposals:[proposal]}};}));
 const refresh=vi.fn(async()=>{});
 render(<TypedConstraint ws={ws} lang="en" t={k=>words.en[k]} refresh={refresh}/>);
 fireEvent.change(screen.getByRole('textbox'),{target:{value:'Prefer later lectures'}});
 await waitFor(()=>expect((screen.getByRole('button',{name:'Interpret'}) as HTMLButtonElement).disabled).toBe(false));
 fireEvent.click(screen.getByRole('button',{name:'Interpret'}));
 await screen.findByText(/Preferred teaching time window/);
 expect(calls.some(c=>c.path==='/api/model-calls'&&!!c.body)).toBe(true);
 expect(calls.some(c=>c.path.includes('/proposals/interpret')||c.path.includes('/review')||c.path.includes('/approve')||c.path==='/api/rules')).toBe(false);
 expect(refresh).not.toHaveBeenCalled();
 expect(screen.getByRole('button',{name:'Create draft rules'})).toBeTruthy();
});
