// @vitest-environment jsdom
import React from 'react';
import {test,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {EvaluationComparison} from './EvaluationComparison';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const reviews=[{id:'a',reviewer_id:'reviewer-a',created_at:'2026-11-01T12:00:00Z'},{id:'b',reviewer_id:'reviewer-b',created_at:'2026-11-01T13:00:00Z'}];
test('comparison waits for different reviewers',()=>{
 render(<EvaluationComparison reviews={[reviews[0]]} lang='en'/>);
 expect(screen.getByText('Two completed reviews with different reviewer IDs are needed before comparison.')).toBeTruthy();
 expect((screen.getByRole('button',{name:'Compare reviews'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('First review'),{target:{value:'a'}});
 fireEvent.change(screen.getByLabelText('Second review'),{target:{value:'a'}});
 expect((screen.getByRole('button',{name:'Compare reviews'}) as HTMLButtonElement).disabled).toBe(true);
});
test('comparison shows metrics and disputed annotations without treating them as adjudicated',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({reviewer_ids:['reviewer-a','reviewer-b'],decision_agreement:{items:24,raw_agreement:23/24,cohen_kappa:.9},semantic_agreement:{items:24,equal:23,disagreement_ids:['case-a']},disagreements:[{id:'case-a',text:'Close the studio on Saturday.',language:'en',context_id:'design',first_annotation:{decision:'ready'},first_rationale:'Closure interpretation.',second_annotation:{decision:'clarify'},second_rationale:'Ask for a time.'}],contexts:[],adjudicated:false})})));
 render(<EvaluationComparison reviews={reviews} lang='en'/>);
 fireEvent.change(screen.getByLabelText('First review'),{target:{value:'a'}});
 fireEvent.change(screen.getByLabelText('Second review'),{target:{value:'b'}});
 fireEvent.click(screen.getByRole('button',{name:'Compare reviews'}));
 expect(await screen.findByText('23/24')).toBeTruthy();
 expect(screen.getByText('Close the studio on Saturday.')).toBeTruthy();
 expect(screen.getByText('Closure interpretation.')).toBeTruthy();
 expect(screen.getByText('Ask for a time.')).toBeTruthy();
 expect(screen.getByText('This comparison does not adjudicate disagreements or change draft answers.')).toBeTruthy();
 fireEvent.change(screen.getByLabelText('First review'),{target:{value:''}});
 expect(screen.queryByText('23/24')).toBeNull();
});
