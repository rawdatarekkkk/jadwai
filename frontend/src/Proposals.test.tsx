// @vitest-environment jsdom
import React from 'react';
import {test,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {Proposals} from './Proposals';
import type {Workspace} from './api';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const ws={version:23,records:[],rules:[],events:[],name:'Test',term:'Test'} as Workspace;
function row(stale=false,decision='ready'){return {id:'p1',input_version:23,stale,record:{text:'No Saturday mornings',origin:'administrator_import',output:{decision,proposals:[{kind:'rule',data:{title:'Morning unavailable',type:'unavailable',instructor_id:'t',day:'Saturday',start_hour:9,end_hour:11,strength:'mandatory'}}],clarifications:decision==='ready'?[]:['which_time'],unsupported:[]},context:{calendar:{days:['Saturday'],start_hour:9,end_hour:17},records:[{id:'t',kind:'instructors',data:{name:'Test teacher'}}]}},review:null};}
function setup(saved=row()){
 const calls:{path:string;options?:RequestInit}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{calls.push({path,options});return {ok:true,status:200,json:async()=>options?.method==='POST'?{id:'review',rule_ids:['r1']}:{version:23,proposals:[saved]}};}));
 const refresh=vi.fn(async()=>{});render(<Proposals ws={ws} lang='en' refresh={refresh}/>);return {calls,refresh};
}
async function select(){fireEvent.click(await screen.findByRole('button',{name:/No Saturday mornings/}));}
test('empty inbox is honest about manual import and has no model action',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({version:23,proposals:[]})})));
 render(<Proposals ws={ws} lang='en' refresh={async()=>{}}/>);
 expect(await screen.findByText('No proposals yet. Import a candidate to begin.')).toBeTruthy();
 expect(screen.getByText('GPT-5.4 mini selected · Server configuration is required for model calls. Manual import is available.')).toBeTruthy();
});
test('structured correction creates drafts with rationale and version, never approval',async()=>{
 const {calls,refresh}=setup();await select();
 expect((screen.getByRole('button',{name:'Create draft rules'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('Rule title 1'),{target:{value:'Corrected title'}});
 fireEvent.change(screen.getByLabelText('Review rationale'),{target:{value:'Confirmed the intended period.'}});
 fireEvent.click(screen.getByRole('button',{name:'Create draft rules'}));
 await screen.findByText('Draft rules created. Review and approve them in Constraints.');
 const post=calls.find(c=>c.options?.method==='POST')!;
 const body=JSON.parse(post.options!.body as string);
 expect(body.corrected_output.proposals[0].data.title).toBe('Corrected title');
 expect(body.action).toBe('create_drafts');expect(body.request_key).toBeTruthy();
 expect((post.options!.headers as Record<string,string>)['If-Match']).toBe('"23"');
 expect(calls.some(c=>c.path.includes('/approve'))).toBe(false);expect(refresh).toHaveBeenCalled();
});
test('stale proposals can be dismissed but cannot create drafts',async()=>{
 const {calls}=setup(row(true));await select();
 fireEvent.change(screen.getByLabelText('Review rationale'),{target:{value:'Inputs changed.'}});
 expect((screen.getByRole('button',{name:'Create draft rules'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Dismiss proposal'}));
 await screen.findByText('Proposal dismissed.');
 expect(JSON.parse(calls.find(c=>c.options?.method==='POST')!.options!.body as string).action).toBe('dismiss');
});
test('clarification needs explicit resolution before conversion',async()=>{
 setup(row(false,'clarify'));await select();
 fireEvent.change(screen.getByLabelText('Review rationale'),{target:{value:'Asked the instructor and corrected the times.'}});
 const create=screen.getByRole('button',{name:'Create draft rules'}) as HTMLButtonElement;
 expect(create.disabled).toBe(true);
 fireEvent.click(screen.getByRole('checkbox'));
 expect(create.disabled).toBe(false);
});
test('failed retry retains the same request key',async()=>{
 const keys:string[]=[];
 vi.stubGlobal('fetch',vi.fn(async(_path:string,options?:RequestInit)=>{
  if(options?.method==='POST'){keys.push(JSON.parse(options.body as string).request_key);return {ok:false,status:503,json:async()=>({detail:'database_unavailable'})};}
  return {ok:true,status:200,json:async()=>({version:23,proposals:[row()]})};
 }));
 render(<Proposals ws={ws} lang='en' refresh={async()=>{}}/>);await select();
 fireEvent.change(screen.getByLabelText('Review rationale'),{target:{value:'Confirmed.'}});
 fireEvent.click(screen.getByRole('button',{name:'Create draft rules'}));await screen.findByRole('alert');
 fireEvent.click(screen.getByRole('button',{name:'Create draft rules'}));
 await waitFor(()=>expect(keys.length).toBe(2));expect(keys[0]).toBe(keys[1]);
});

test('configured model generation opens a saved interpretation for review',async()=>{
 const calls:{path:string;options?:RequestInit}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{
  calls.push({path,options});
  return {ok:true,status:200,json:async()=>path.endsWith('/configuration')?{enabled:true}:options?.method==='POST'?{status:'completed',proposal_id:'p1'}:{proposals:[row()]}};
 }));
 render(<Proposals ws={ws} lang='en' refresh={async()=>{}}/>);
 fireEvent.change(screen.getByLabelText('Requirement for JAI'),{target:{value:'No Saturday mornings'}});
 const generate=screen.getByRole('button',{name:'Generate interpretation'}) as HTMLButtonElement;
 await waitFor(()=>expect(generate.disabled).toBe(false));fireEvent.click(generate);
 await screen.findByText('Interpretation saved for review. No rules were approved.');
 expect(screen.getByLabelText('Rule title 1')).toBeTruthy();
 const post=calls.find(c=>c.options?.method==='POST')!;
 expect(post.path).toBe('/api/model-calls');
 expect(JSON.parse(post.options!.body as string).text).toBe('No Saturday mornings');
 expect(calls.some(c=>c.path.includes('/approve'))).toBe(false);
});
