// @vitest-environment jsdom
import React from "react";
import {test,expect,vi,afterEach} from "vitest";
import {render,screen,fireEvent,cleanup} from "@testing-library/react";
import {SourceTimetables} from "./SourceTimetables";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
test('imported source rows can be browsed and filtered without creating activities',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>[{id:'s',source_document:'schedule.xlsx',summary:{explicit_room_identifiers:1},instructor_mentions:[],entries:[{day:'Saturday',start_time:'08:30',end_time:'10:00',raw_text:'Algorithms T1',section_as_printed:'3rd Informatics',cohort_as_printed:'CS I',track_as_printed:'',room_codes:['A.100'],source_sheet:'Saturday',source_cell:'E4',review_flags:[],activity_type_candidate:'tutorial'}]}]})));
 render(<SourceTimetables lang="en"/>);
 fireEvent.click(await screen.findByRole('button',{name:'Browse imported data'}));
 expect(screen.getByText('Algorithms T1')).toBeTruthy();
 expect(screen.getByText(/Course needs confirmation/)).toBeTruthy();
 fireEvent.change(screen.getByLabelText('Search imported timetable'),{target:{value:'no match'}});
 expect(screen.queryByText('Algorithms T1')).toBeNull();
});
