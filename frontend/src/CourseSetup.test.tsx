// @vitest-environment jsdom
import React from "react";
import { test, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { RecordForm } from "./components";
import { words } from "./i18n";
import type { Workspace } from "./api";
afterEach(cleanup);
test("course and type changes restrict choices and clear stale assignments", () => {
  const ws:Workspace={name:"CS",term:"Fall",version:1,rules:[],events:[],records:[
    {id:"lecturer",kind:"instructors",name:"Lecturer",code:"L"},
    {id:"tutor",kind:"instructors",name:"Tutor",code:"T"},
    {id:"outsider",kind:"instructors",name:"Other teacher",code:"O"},
    {id:"g1",kind:"groups",name:"Group One",code:"G1"},
    {id:"g2",kind:"groups",name:"Group Two",code:"G2"},
  ],course_catalog:[
    {id:"c1",name:"Algorithms",code:"ALG",eligibility:{lecture:["lecturer"],tutorial:["tutor"],lab:[]},group_ids:["g1"]},
    {id:"c2",name:"Physics",code:"PHY",eligibility:{lecture:["outsider"],tutorial:[],lab:[]},group_ids:["g2"]},
  ]};
  const save=vi.fn();
  render(<RecordForm kind="courses" ws={ws} t={k=>words.en[k]} busy={false} cancel={()=>{}} submit={save}/>);
  expect(screen.queryByRole("checkbox")).toBeNull();
  fireEvent.change(screen.getByLabelText(/Course name/),{target:{value:"c1"}});
  expect(screen.getByRole("checkbox",{name:"Lecturer"})).toBeTruthy();
  expect(screen.queryByRole("checkbox",{name:"Tutor"})).toBeNull();
  expect(screen.queryByRole("checkbox",{name:"Group Two"})).toBeNull();
  fireEvent.click(screen.getByRole("checkbox",{name:"Lecturer"}));
  fireEvent.click(screen.getByRole("checkbox",{name:"Group One"}));
  fireEvent.change(screen.getByLabelText("Activity type"),{target:{value:"tutorial"}});
  expect(screen.queryByRole("checkbox",{name:"Lecturer"})).toBeNull();
  expect((screen.getByRole("checkbox",{name:"Tutor"}) as HTMLInputElement).checked).toBe(false);
  expect((screen.getByRole("checkbox",{name:"Group One"}) as HTMLInputElement).checked).toBe(true);
  fireEvent.change(screen.getByLabelText(/Course name/),{target:{value:"c2"}});
  expect(screen.queryByRole("checkbox",{name:"Group One"})).toBeNull();
  expect((screen.getByRole("checkbox",{name:"Group Two"}) as HTMLInputElement).checked).toBe(false);
  expect((screen.getByRole("button",{name:"Save changes"}) as HTMLButtonElement).disabled).toBe(true);
});
