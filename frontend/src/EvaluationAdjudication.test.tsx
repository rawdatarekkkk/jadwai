// @vitest-environment jsdom
import React from 'react';
import {test,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {EvaluationAdjudication} from './EvaluationAdjudication';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const props={first:'a',second:'b',reviewerIds:['reviewer-a','reviewer-b'],disputes:[{id:'case-a',text:'A requirement.',first_annotation:{decision:'ready'},second_annotation:{decision:'clarify'}}],records:[],lang:'en' as const,onSaved:vi.fn()};
test('decision record requires a third declared ID and a rationale for each dispute',()=>{
 render(<EvaluationAdjudication {...props}/>);
 const submit=screen.getByRole('button',{name:'Save adjudication record'}) as HTMLButtonElement;
 expect(submit.disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('Pseudonymous adjudicator ID'),{target:{value:'REVIEWER-A'}});
 fireEvent.change(screen.getByLabelText('Chosen interpretation case-a'),{target:{value:'first'}});
 fireEvent.change(screen.getByLabelText('Decision rationale case-a'),{target:{value:'Rationale.'}});
 expect(submit.disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('Pseudonymous adjudicator ID'),{target:{value:'third-reviewer'}});
 expect(submit.disabled).toBe(false);
});
test('selected decision is saved separately and a retry cannot create another record',async()=>{
 const submitted:unknown[]=[];const onSaved=vi.fn();
 vi.stubGlobal('fetch',vi.fn(async(_path:string,options:{body:string})=>{submitted.push(JSON.parse(options.body));return {ok:true,status:201,json:async()=>({id:'record',adjudicator_id:'third-reviewer',first_review_id:'a',second_review_id:'b',items:24,created_at:'2026-11-01T12:00:00Z',release_promoted:false})};}));
 render(<EvaluationAdjudication {...props} onSaved={onSaved}/>);
 fireEvent.change(screen.getByLabelText('Pseudonymous adjudicator ID'),{target:{value:'third-reviewer'}});
 fireEvent.change(screen.getByLabelText('Chosen interpretation case-a'),{target:{value:'second'}});
 fireEvent.change(screen.getByLabelText('Decision rationale case-a'),{target:{value:'Needs clarification.'}});
 fireEvent.click(screen.getByRole('button',{name:'Save adjudication record'}));
 await screen.findByText('Adjudication record saved. Draft answers and scheduling inputs are unchanged.');
 expect(onSaved).toHaveBeenCalledOnce();
 expect((submitted[0] as {resolutions:unknown[]}).resolutions).toEqual([{id:'case-a',annotation:{decision:'clarify'},rationale:'Needs clarification.'}]);
 expect((screen.getByRole('button',{name:'Save adjudication record'}) as HTMLButtonElement).disabled).toBe(true);
});
test('invalid custom JSON is rejected before submission',()=>{
 const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
 render(<EvaluationAdjudication {...props}/>);
 fireEvent.change(screen.getByLabelText('Pseudonymous adjudicator ID'),{target:{value:'third-reviewer'}});
 fireEvent.change(screen.getByLabelText('Chosen interpretation case-a'),{target:{value:'custom'}});
 fireEvent.change(screen.getByLabelText('Annotation case-a'),{target:{value:'not json'}});
 fireEvent.change(screen.getByLabelText('Decision rationale case-a'),{target:{value:'Rationale.'}});
 fireEvent.click(screen.getByRole('button',{name:'Save adjudication record'}));
 expect(screen.getByRole('alert').textContent).toContain('valid JSON');
 expect(fetch).not.toHaveBeenCalled();
});
