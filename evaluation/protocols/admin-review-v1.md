# Administrator annotation review protocol v1

Recorded 1 November 2026 from the user's instruction: “the admin will review”.

The administrator is the single human reviewer of the current assistant-authored draft annotations. The website records the authenticated submitting account and a declared pseudonymous reviewer ID. No real review, reviewer identity or judgment is manufactured by the implementation.

## Current workflow

1. The administrator opens the gold-free review pack in the browser or downloads it with the guide.
2. For each statement, the administrator reads the supplied context, chooses supported interpretations or clarification/unsupported labels, and explains the decision without seeing the expected draft answer in the form.
3. The completed review is validated and saved as a separate immutable record. It does not automatically approve constraints, overwrite gold, promote a release, or establish a research result.
4. A corrected dataset release can later retain the review reference, exact guide hash, corrections and a clear single-annotator limitation. The present pilot pack contains 24 statements; reviewing it does not certify all 144 development examples.
5. Additional-review comparison and adjudication are optional if a second review is actually obtained. They are not required steps in the administrator-only workflow and do not justify inventing extra reviewer identities.

## Reporting boundary

Describe the labels as administrator-reviewed only after actual review records exist. State the single-annotator limitation; do not report inter-annotator agreement without two genuine human reviewers. Repeated submissions by one person do not establish independent annotation. The existing reserved set remains author-exposed and cannot become blind by relabelling it.

The future sealing pipeline supports an explicit single-annotator declaration, but sealing fresh protected material is a separate technical operation. Freshness, consent, authorship and independence declarations require external evidence; the software does not certify them. A frozen configuration, integrity hashes and access logs do not substitute for that evidence.
