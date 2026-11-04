// @vitest-environment jsdom
import React from 'react';
import {test,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {Evaluation} from './Evaluation';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const summary={phase:5,dataset_version:'0.2.0-draft',counts:{cases:144,families:36,contexts:2},guide_version:'v2',review_pack_items:24,reviews:[]};
test('evaluation dashboard exposes gold-free downloads and prevents empty submissions',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>summary})));
 render(<Evaluation lang='en'/>);
 expect(await screen.findByText('144')).toBeTruthy();
 expect(screen.getByRole('link',{name:'Download review pack'}).getAttribute('href')).toBe('/api/evaluation/review-pack');
 expect(screen.getByRole('link',{name:'Download annotation guide'})).toBeTruthy();
 expect((screen.getByRole('button',{name:'Validate and save review'}) as HTMLButtonElement).disabled).toBe(true);
 expect(screen.getByText('No reviews have been submitted yet.')).toBeTruthy();
});
test('completed review upload is validated and saved without touching scheduling inputs',async()=>{
 const requests:string[]=[];
 vi.stubGlobal('fetch',vi.fn(async(path:string,options?:{method?:string;body?:string})=>{requests.push(path);return {ok:true,status:options?.method==='POST'?201:200,json:async()=>options?.method==='POST'?{id:'r',reviewer_id:'reviewer-a',created_at:'2026-11-01T12:00:00Z',items:24}:summary};}));
 render(<Evaluation lang='en'/>);
 await screen.findByText('144');
 fireEvent.change(screen.getByLabelText('Pseudonymous reviewer ID'),{target:{value:'reviewer-a'}});
 const file={size:500,name:'review.json',text:async()=>JSON.stringify({format:'gold-free-review-v1',items:Array.from({length:24},()=>({annotation:{}}))})};
 fireEvent.change(screen.getByLabelText('Completed review JSON'),{target:{files:[file]}});
 await screen.findByText('review.json · 24 statements ready for validation');
 fireEvent.click(screen.getByRole('button',{name:'Validate and save review'}));
 await screen.findByText('Review saved. Draft gold and scheduling inputs are unchanged.');
 expect(screen.getByRole('link',{name:'Download record'}).getAttribute('href')).toBe('/api/evaluation/reviews/r/export');
 expect(requests).toContain('/api/evaluation/reviews');
 expect(requests).not.toContain('/api/workspace');
});
test('saved adjudication history remains visible after loading the dashboard',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({...summary,adjudications:[{id:'decision-record',adjudicator_id:'declared-adjudicator',first_review_id:'review-a',second_review_id:'review-b',created_at:'2026-11-01T12:00:00Z',items:24,release_promoted:false}]})})));
 render(<Evaluation lang='en'/>);
 expect(await screen.findByText('Adjudication history')).toBeTruthy();
 expect(screen.getByText('declared-adjudicator')).toBeTruthy();
 expect(screen.getByRole('link',{name:'Download adjudication record'}).getAttribute('href')).toBe('/api/evaluation/adjudications/decision-record/export');
});

test('administrator protocol makes additional reviewer comparison optional',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({...summary,review_protocol:'single_admin_reviewer'})})));
 render(<Evaluation lang='en'/>);
 expect(await screen.findByText('Review protocol: administrator review')).toBeTruthy();
 expect(screen.getByText(/administrator is the single human reviewer/)).toBeTruthy();
 const comparison=document.querySelector('details.optional-review-comparison') as HTMLDetailsElement;
 expect(comparison.open).toBe(false);
 expect(screen.getByText('Reviewer comparison and adjudication (optional)')).toBeTruthy();
});
