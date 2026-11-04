# Annotation guide v2 draft — development review

Version: annotation-guide-v2-draft. Date: 1 November 2026. Status: assistant-authored, pending independent multilingual review. Predecessor: annotation-guide-v1, retained unchanged with the original release.

## Change note and context boundary

Development bundle 0.2.0-draft retains the original 96 development items and adds 48 statements in 12 four-language families for a second fictional institution, a design school. All new items are development material, not confirmatory data. Family IDs are unique across contexts. No reserved examples have been read, moved, replaced or relabelled by this release builder.

Apply guide v1's supported rule semantics and entity-resolution rules to the first synthetic context. Its Sunday–Thursday calendar and weekly-cap examples remain historical context-specific diagnostics. They do not assert current GIU policy.

For the second context, use Saturday–Thursday and the explicitly recorded 12 regular teaching hours with overtime permitted. A request to prohibit all hours above 12 is unsupported by that context's proposal boundary; do not silently change the application's overtime policy or reinterpret a prohibition as a warning. Integer-hour unavailable/preferred/permitted-window proposals remain supported. A minute-specific rule remains unsupported by the current storage precision, even if named teaching periods have minute boundaries. Do not round it.

## Annotation procedure

Read the context and full statement. Produce an envelope with decision, proposals, clarification codes and unsupported codes. Proposals remain unapproved. Do not infer a missing weekday, vague threshold, unknown instructor ID, student group membership or room suitability. Shared-target permitted windows are alternatives; different targets intersect. Mandatory closures take precedence over soft preferences without making their combination a hard contradiction.

All four translations in one intent family remain together. Reviewers must check semantic equivalence, Arabic negation, Egyptian clock expressions, time units and hard versus preferred wording. Record ambiguity rather than assuming the draft gold is authoritative.

- Ready: all fragments resolved into supported proposals.
- Clarify: missing day, undefined early, unknown instructor or similar unresolved meaning; stable codes identify the question, not exact natural-language wording.
- Unsupported: a request cannot faithfully fit the context's supported operations.
- Conflict: interpreted hard constraints cannot both hold; retain interpretations and ask for resolution.
- Mixed: supported and unresolved/unsupported fragments coexist; never drop fragments.

A label is not human-reviewed merely because a script validates its schema or a scorer matches it. Do not include oracle self-test scores in thesis model results.

## Reviewer workflow

Export a gold-free review pack through `development.py export-review`. Reviewers use pseudonymous IDs and independently add a complete output under annotation, a nonempty rationale, and their reviewer ID. Importing labels validates IDs, context semantics and completeness; it writes a separate immutable review record. It never overwrites gold or promotes a release automatically.

Two independent human reviews and a recorded adjudication are required to claim double annotation. Agreement on decision categories can be computed separately; field-level and semantic agreement require review of the complete annotations. A fresh independently managed confirmatory set and a development pilot are still needed. Automatic text-duplicate checks cannot rule out semantic paraphrase leakage.
