# JadwAI and JAI

Chosen by the project owner on 15 October 2026.

## Product

Name: **JadwAI**. Preserve this exact capitalization in prose, UI, metadata, documentation, and presentations. The name joins jadwal (جدول, timetable) with AI. Highlight the AI suffix in the wordmark; use `jadwai` for package names and technical identifiers.

Tagline: **Your semester, intelligently arranged.**

Arabic tagline: **فصلك الدراسي، بترتيب أذكى.** Keep the JadwAI wordmark in Latin script in both interface languages so the identity stays recognizable; display the wordmark left-to-right inside the RTL layout.

The existing warm ivory, forest-green, and botanical palette remains the visual direction. The favicon combines a calendar and J. Branding assets are implemented as SVG/CSS source, so they stay crisp and editable.

## Assistant

Name: **JAI**, pronounced **jay**. Use uppercase JAI consistently rather than alternating with jAi, Jai, or a generic “AI bot.” JAI is JadwAI's timetabling companion, not the scheduling solver or an approving authority.

Opening line: **Hi, I’m JAI. Let’s plan a clearer week.**

Personality: calm, clear, friendly, and precise. Explain ambiguity, ask for missing details, and make the administrator's control explicit. Never claim to approve rules, generate a timetable, or validate results unless that exact capability actually ran and its evidence is available.

Avatar: a forest-green speech tile containing a light J and a small sage sparkle. Use the same avatar on the launcher and introduction panel. UI strings are translated through the existing catalog; JAI keeps its name in both languages.

Current behavior: a guided-help panel with working navigation to academic data, structured manual rules, and timetable status. The panel clearly labels AI extraction as coming soon. There is no conversational model, inferred response, provider call, or automatic approval behind it yet. Phase 6 adds real extraction, clarification, and review under the same identity.

## Rename and compatibility

The application folder is now `jadwai/`. Package name, browser metadata, session cookie, request header, language preference key, administrator environment variables, synthetic account email, API title, scripts, and documentation use the new name. The local seed account is `admin@jadwai.local`; its password is preserved in the ignored `.env` file. Alembic migration 0003 changes only the original synthetic administrator email and avoids overwriting another existing account.

The existing Compose project, PostgreSQL database/user, and data-volume identifiers retain their original internal `mizan` names to reuse the already initialized volume and preserve saved records. These are storage compatibility identifiers, not product branding. The old account spelling appears only in the reversible migration. Do not do a blanket replacement of database URLs or volume names on an existing installation; that can disconnect the application from its saved data.
