// @vitest-environment jsdom
import React from "react";
import {test,expect,vi,afterEach} from "vitest";
import {render,screen,fireEvent,cleanup} from "@testing-library/react";
import {ExamSchedule} from "./ExamSchedule";
import type {Workspace} from "./api";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
test('exam generation uses the source period and two-hour slots',async()=>{
 const ws={version:23,course_catalog:[{id:'c',name:'Algorithms',code:'ALG',eligibility:{lecture:[],tutorial:[],lab:[]},group_ids:[]}]} as unknown as Workspace;
 const print=vi.spyOn(window,'print').mockImplementation(()=>{});
 const title=document.title;
 const calls:unknown[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:{method?:string;body?:string})=>{
  if(options?.method==='POST'){calls.push(JSON.parse(options.body!));return {ok:true,status:201,json:async()=>({id:'run',input_version:23,snapshot:{dates:['2026-10-20'],settings:{start_date:'2026-10-20',end_date:'2026-10-31'}},result:{status:'completed',validation:{passed:true},assignments:[{course_id:'c',course_name:'Algorithms',course_code:'ALG',date:'2026-10-20',start_time:'09:00',end_time:'11:00',duration_minutes:120,programs:[{faculty_section:'INFORMATICS',program_or_cohort:'Computer Science',semester:3}]}]}})};}
  return {ok:true,status:200,json:async()=>[]};
 }));
 render(<ExamSchedule ws={ws} lang='en'/>);
 fireEvent.click(screen.getByRole('button',{name:'Generate exam schedule'}));
 await screen.findByText('Algorithms');
 expect(calls[0]).toEqual({start_date:'2026-10-20',end_date:'2026-10-31',exclude_fridays:true,max_exams_per_cohort_day:1,use_halls:true,assign_invigilators:true});
 expect(screen.getByText('Independent checks passed')).toBeTruthy();
 expect(screen.getByRole('link',{name:'Download CSV'})).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Save as PDF'}));
 expect(print).toHaveBeenCalledOnce();
 const printable=screen.getByRole('region',{name:'Printable exam schedule'});
 expect(printable.textContent).toContain('9:00-11:00');
 expect(printable.textContent).toContain('Algorithms');
 expect(printable.textContent).toContain('INFORMATICS');
 expect(printable.textContent).toContain('GIU-Cairo.Computer Science');
 expect(printable.querySelector('.exam-print-date')?.getAttribute('rowspan')).toBe('2');
 expect(printable.textContent).toContain('Rooms, invigilators');
 expect(document.title).toContain('JadwAI-Midterms-2026-10-20');
 fireEvent(window,new Event('afterprint'));
 expect(screen.queryByRole('region',{name:'Printable exam schedule'})).toBeNull();
 expect(document.title).toBe(title);
 print.mockRestore();
});

test('isolated feasibility cases show failure and verified adjustment',async()=>{
 const ws={version:23,course_catalog:[]} as unknown as Workspace;
 const requests:string[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{
  requests.push(path);
  return {ok:true,status:200,json:async()=>path.endsWith('/feasibility-tests')?[{id:'capacity',title:'Daily capacity exceeded',description:'Two exams, one available day.',before:{status:'infeasible',assignments:[]},adjustment:'Add a second eligible date.',after:{status:'completed',assignments:[]},verified:true}]:[]};
 }));
 render(<ExamSchedule ws={ws} lang='en'/>);
 fireEvent.click(screen.getByRole('button',{name:'Run feasibility test cases'}));
 await screen.findByText('Daily capacity exceeded');
 expect(screen.getByText('Before adjustment: infeasible')).toBeTruthy();
 expect(screen.getByText('Add a second eligible date.')).toBeTruthy();
 expect(screen.getByText('Verified: complete schedule; independent checks passed')).toBeTruthy();
 expect(requests).toContain('/api/exam-schedules/feasibility-tests');
 expect(requests).not.toContain('/api/workspace');
});

test('nine calendar days show seven eligible days when Fridays are excluded',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>[]})));
 render(<ExamSchedule ws={{version:23,course_catalog:[]} as unknown as Workspace} lang='en'/>);
 fireEvent.change(screen.getByLabelText('Start date'),{target:{value:'2026-10-23'}});
 const breakdown=document.querySelector('.exam-date-breakdown')!;
 expect(breakdown.textContent).toContain('9 calendar days − 2 excluded days = 7 eligible exam days');
 expect(breakdown.textContent).toContain('2026-10-23 (Friday), 2026-10-30 (Friday)');
 fireEvent.click(screen.getByRole('checkbox',{name:'Exclude Fridays'}));
 expect(breakdown.textContent).toContain('9 calendar days − 0 excluded days = 9 eligible exam days');
});
