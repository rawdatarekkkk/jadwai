// @vitest-environment jsdom
import React from 'react';
import {test,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {ScenarioActions} from './ScenarioActions';
import type {ScheduleRun,Workspace} from './api';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const ws={version:7,records:[],rules:[],events:[],name:'Test',term:'Test'} as Workspace;
const records=[
 {id:'math',kind:'courses',name:'Math I',code:'M-1',group_ids:['g1']},{id:'math2',kind:'courses',name:'Math I',code:'M-2',group_ids:['g2']},
 {id:'g1',kind:'groups',name:'Group 1',code:'G1'},{id:'g2',kind:'groups',name:'Group 2',code:'G2'},
 {id:'r1',kind:'rooms',name:'Room 1',code:'R1'},{id:'r2',kind:'rooms',name:'Room 2',code:'R2'},
];
const run={id:'run1',name:'Plan A',created_at:'2026-11-07T10:00:00Z',input_version:7,stale:false,status:'completed',cancel_requested:false,published_at:null,
 snapshot:{name:'T',term:'T',records,rules:[],calendar:{timezone:'Africa/Cairo',days:['Sunday','Monday'],start_hour:8,end_hour:12,period_minutes:30,teaching_periods:[{start:510,end:600}],start_date:null,end_date:null}},
 result:{assignments:[{activity_id:'math',occurrence:0,instructor_id:'t',room_id:'r1',day:'Sunday',start_minute:510,end_minute:600},{activity_id:'math2',occurrence:0,instructor_id:'t',room_id:'r1',day:'Monday',start_minute:510,end_minute:600}]}} as unknown as ScheduleRun;

function setup(response:(path:string,options?:RequestInit)=>{ok:boolean;status:number;body:unknown}){
 const calls:{path:string;options?:RequestInit}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:RequestInit)=>{calls.push({path,options});const r=response(path,options);return {ok:r.ok,status:r.status,json:async()=>r.body};}));
 const reload=vi.fn(async()=>{}),select=vi.fn(),notify=vi.fn();
 render(<ScenarioActions ws={ws} run={run} runs={[run]} lang='en' reload={reload} select={select} notify={notify}/>);
 return {calls,reload,select,notify};
}

test('sessions of same-named activities are told apart by group',()=>{
 setup(()=>({ok:true,status:200,body:{}}));
 expect(screen.getByRole('option',{name:/Math I · G1 · Sunday 08:30 · Room 1/})).toBeTruthy();
 expect(screen.getByRole('option',{name:/Math I · G2 · Monday 08:30 · Room 1/})).toBeTruthy();
});

test('a valid move creates and selects a new draft; a rule-breaking one explains why',async()=>{
 const {calls,select,notify}=setup(()=>({ok:true,status:201,body:{id:'run2'}}));
 fireEvent.change(screen.getByLabelText('Session'),{target:{value:'math:0'}});
 fireEvent.change(screen.getByLabelText('Room'),{target:{value:'r2'}});
 fireEvent.click(screen.getByRole('button',{name:'Move session'}));
 await waitFor(()=>expect(select).toHaveBeenCalledWith('run2'));
 const body=JSON.parse(calls.find(c=>c.path.endsWith('/edits'))!.options!.body as string);
 expect(body.changes).toEqual([{activity_id:'math',occurrence:0,room_id:'r2'}]);
 expect(notify).toHaveBeenCalledWith('Saved as a new validated draft. The original is unchanged.');
 cleanup();
 setup(()=>({ok:false,status:422,body:{detail:{code:'edit_breaks_rules',errors:['resource_conflicts']}}}));
 fireEvent.change(screen.getByLabelText('Session'),{target:{value:'math:0'}});
 fireEvent.change(screen.getByLabelText('Start'),{target:{value:'510'}});
 fireEvent.change(screen.getByLabelText('Day'),{target:{value:'Monday'}});
 fireEvent.click(screen.getByRole('button',{name:'Move session'}));
 expect(await screen.findByText('That change breaks a rule, so it was not saved. (resource conflicts)')).toBeTruthy();
});

test('publish sends the workspace version',async()=>{
 const {calls}=setup(()=>({ok:true,status:200,body:{id:'run1',published_at:'now'}}));
 fireEvent.click(screen.getByRole('button',{name:'Publish'}));
 await screen.findByText('Published. Instructors and students now see this timetable.');
 const post=calls.find(c=>c.path.endsWith('/publish'))!;
 expect((post.options!.headers as Record<string,string>)['If-Match']).toBe('"7"');
});
