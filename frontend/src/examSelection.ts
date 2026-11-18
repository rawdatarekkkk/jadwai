export const examOnScreen: {run_id?: string; query?: string} = {};
export let requestedExamRun: string | undefined;
export function selectExamRun(id: string) {
  requestedExamRun = id;
  window.dispatchEvent(new CustomEvent("jadwai:exam-selection", {detail: id}));
}
export function rememberExamRun(id: string | undefined) { requestedExamRun = id; }
