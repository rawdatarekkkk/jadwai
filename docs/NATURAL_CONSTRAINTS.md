# Natural-language constraint interpretation

The Constraints page’s Interpret action uses the configured local model through the validated model-call endpoint. It produces a reviewable proposal only; creating drafts and approving rules remain separate actions. If the local model is unavailable, the page explicitly labels the built-in parser as limited. Interpret never switches to a cloud model.

The interpreter receives the actual calendar, named teaching periods, and numbered slot references. The local model distinguishes hard requirements from soft preferences. Generic teaching time requests use a small semantic frame; application code resolves numbered slots and compiles allowed-time windows, avoiding model-generated calendar arithmetic. Other rule families use the validated structured extraction path. A guard rejects an interpretation that contradicts an explicit hard/soft qualifier rather than silently strengthening or weakening it. Unclear or unrepresentable requests still require clarification.

General teaching-window rules support any combination of lectures, tutorials and labs. `teaching_allowed` is hard; `teaching_preferred` is soft. Different selectors apply together, while windows with an identical selector are weekly alternatives. Soft violations add independently checked objective penalties. Independent validation rejects hard violations. Reporting includes both rule types; repair keeps preferences soft.

Migration 0035 updates rule constraints without activating any rule. No first-slot preference has been added or approved in the live workspace.
