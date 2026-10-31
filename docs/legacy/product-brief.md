# Product Brief

**Status**: accepted
**Last Updated**: 2026-10-28
**Owner**: Founder

`product-brief.md` is the canonical Discovery synthesis. It is the only minimum Discovery artifact and the primary handoff to the next phase. Keep it tight enough that a reader can grasp the product direction in a few minutes. Move material into optional leaf artifacts (`audience.md`, `positioning.md`, `landscape.md`, etc.) only when it grows beyond inline scope; when that happens, reduce the corresponding section here to a short summary that points to the leaf.

> **How this brief was made.** Discovery's research pass was skipped (founder decision, 2026-10-27): the direction was already documented in `docs/design.md` (version 1.0, 2026-10-27). This brief was written in one sitting from that document and from the founder's decisions of 2026-10-27, which are not yet in the design doc. No research leaves exist. `synthesis.md` holds only Sections 9 to 11. The design doc is **initial thinking, not the closed scope**: every item marked *proposed* below was added during drafting and is not in the doc.

## One-Line Concept

Fairband values every U.S.-listed company of a useful size by its life-cycle phase, and lets a value investor's own AI agents research, re-value and annotate the few worth a closer look, with every number computed by the engine and every judgment on record.

## Problem

A value investor needs a value for every company to find where value hides, and deep research on the few that look interesting. Mechanical screens use one method for every company, so young and declining companies get the wrong value, and the cheapest rows are usually errors. Agent research reads well but carries no defensible valuation: in the founder's TradingAgents reports, 10 of 11 price targets were chart levels, not values. The founder's own valuation notes were accurate but unreadable, and the agents' judgments had no place where the engine recomputes and the reasoning stays on record.

## Audience

Primary: the founder, a long-term value investor with a 3-year repricing horizon, who brings their own data accounts, approves and places every trade, and runs agents from the terminal (Claude Code). Secondary: other self-directed value investors who pay for the required data and bring their own agents (Claude Code, Codex, Claude Desktop). Prefer FMP alone; a GuruFocus account is needed only if data mapping identifies required gaps that it supplies. Not served: traders, technical analysts, passive investors, institutions, and investors who want a built-in AI to give them answers.

> **Source selection (founder clarification, 2026-10-28):** check FMP against every required input first. If it supplies all required data with the needed definitions, history and company coverage, use FMP alone and drop GuruFocus from the integration and account requirements. Otherwise use GuruFocus only for required gaps it can supply. The mapping outcome is not yet known. This supersedes the initial assumption that both paid accounts are required. A free data path for basic users remains deferred, not refused.

## Wedge

**One literature-based engine values every company by its life-cycle phase, and your own agents refine the value by changing inputs, never numbers: the engine recomputes, so there is one price target, and every judgment carries its reason and its evidence.**

Three qualifiers travel with the wedge. The engine follows Damodaran and the practitioner literature; it invents no methodology. Agents run outside Fairband, so Fairband enforces what they may write, not how they reason. Every result is valid until the company's next earnings report, and says so.

## Positioning Summary

The category is a local valuation workspace for a value investor and their agents. Fairband competes on the defensibility and traceability of its values, not on data breadth and not on AI of its own. Its alternatives are the vendors' own fair values (GuruFocus, Simply Wall St: one method, closed inputs, no agent writes), Damodaran's spreadsheets (phase-aware but manual, one company at a time), and agent research frameworks such as TradingAgents (readable, no valuation). It consumes FMP, supplemented by GuruFocus only for required gaps, rather than competing with data vendors. EquityEval, the founder's research-workspace concept, is unrelated to Fairband (founder, 2026-10-27; `docs/design.md`, section 2). *Partial: no landscape research ran.*

## Strategic Direction

### Hypothesis Status

No research pass ran, so no hypothesis is validated. Each one is held by founder decision.

- **Audience**: held → the founder first; paying, agent-forward value investors second (2026-10-27).
- **Problem**: held → one method for every phase misvalues; agent research has no valuation and no record.
- **Wedge**: refined → "inputs, never numbers" now also binds external agents through the MCP server (2026-10-27).
- **Desired outcome**: held → a value, a stance and a reason for every company; a readable, audited report for any company the founder picks.

### Direction-Shaping Insights

- One engine, one route per phase: the inputs change by phase, the arithmetic does not.
- Scripts compute, agents judge. With the agents outside Fairband, the rule moves into the service layer: the MCP tools are its contract.
- The top of every mechanical screen collects errors, so the screen ranks by "cheap and clean" and every row explains itself, including a refusal.
- Readability is a hard requirement: a reader part, an audit appendix, and a number check that rejects what it cannot trace.
- Paid data limits reach for now: anyone can read the method; running it requires FMP and, only where the input mapping requires it, GuruFocus. If FMP covers all required inputs, GuruFocus is dropped. A free data path is the later lever for basic users.

### Strategic Tensions

- Open source with paid-only data — accepted for the first phase; the audience is investors who already pay. A free path is deferred, not refused.
- Agents outside Fairband cannot be held to reasoning quality, only to their writes — accepted; the log of mechanical versus reviewed values shows over time whether the agents help.
- A value for every company versus honest refusals — accepted; a refusal with a reason is a row, and a missing row is the failure.
- Fairband and EquityEval: closed (founder, 2026-10-27). The two products are unrelated, as `docs/design.md`, section 2 already recorded. There is no tension; the brief re-opened the question in error.

> Full synthesis reasoning: see `synthesis.md`, Section 10.

## Capability Handoff

All candidates: Discovery proposes, Product commits (`synthesis.md`, Section 11).

- **Candidate Areas**: Universe & Data; Life-cycle Classification; Valuation Engine; Screen & Value Pockets; Company Research Record; Agent Access; Portfolio; Platform. Eight; Product re-cuts. Insider trades and 13F holdings are evidence inside the Record and the Screen, not an Area (founder, 2026-10-27).
- **Concern candidates**: every feature must (A) tag every input and record every write with its provenance; (B) change inputs only, never a value; (C) keep vendor keys in private local credential configuration and vendor data locally; send neither to a Fairband-operated service; send a vendor key only from its adapter to that vendor over HTTPS, and scrub secrets from outputs and records; (D) keep human-facing output readable, codes in the appendix; (E) run only on request and date every result; (F) cite a source or a versioned policy value for every rule; (G) check every agent write on the server.
- **Platform candidates**: one service layer; the local web server with background jobs; the database with history and snapshots; the vendor clients with a store and a URL scrub; a versioned policy registry; a provenance ledger; the MCP server scaffolding; point-in-time data access; export.
- **Feature candidates**: 51 live (FC-01 to FC-52 and FC-37a; FC-38 and FC-48 withdrawn) in eight themes, listed in `synthesis.md`, Section 11. Thirteen carry a *proposed* mark: ten whole features (FC-26, FC-33, FC-35, FC-40, FC-41, FC-45, FC-49, FC-50, FC-51, FC-52) and three partial additions (FC-05, FC-34, FC-42); FC-51 and FC-52 are marked *later*. Four more (FC-36, FC-37, FC-37a, FC-39) come from the founder's decisions of 2026-10-27 and are not in the design doc either.
- **Journey seeds**: J1 Find a pocket → pick a company → deep analysis → stance → trade (spine candidate); J2 Refresh and see what moved; J3 Validity window expires → work item → re-value; J4 Calibrate the classifier; J5 Portfolio review on request; J6 Onboarding (*proposed*).
- **Surface set**: S1 local web app (human, first release); S2 MCP server (agents, first release); S3 the builder's test surface (by rule). Rejected (2026-10-27): a CLI; a local HTTP API for scripting (no user identified); a Markdown export and the agent playbook plugin as surfaces (they are features, FC-35 and FC-41); a hosted service; a desktop app (deferred); chat-app views (need a remote MCP server; later).
- **Product roles**: Owner (the user); Agent (an external principal over MCP; one role, every write under the server's rules; the work roles such as News Analyst live in the playbook, and each write records which agent and which playbook role made it); System (the engine as author of mechanical values). Multi-user roles and agent permission presets waived (founder, 2026-10-27): single-user, local.
- **Segments**: the founder; paying value investors with terminal or desktop agents; later, investors whose agents live in chat apps. Lens only.
- **Shared capabilities**: run the engine on an input set; resolve a frozen snapshot; write a tagged change; universe statistics (deciles); policy lookup; price facts and multiples.
- **Value anchors**: Value (a defensible value for every company, by phase); Pockets (see where value hides, by group); Depth (deep research on the few, by my own agents); Trust (every number reproducible, every judgment on record); Readable (a report I can read in five pages); Mine (my data, my keys, my machine, my trades); One target (one price target, no borrowed moods).

> Contract coverage (supplied / partial / waived): see `synthesis.md` Section 9 and Section 11.

## Goals

- The user, or an agent over MCP, can request a mechanical valuation for any scope: one ticker, a list, a cap band, or the whole universe. Every company in the scope gets a value, a stance and a reason, or a refusal that says why.
- The phase classifier follows Damodaran's words, shows its evidence, and has a flag count the founder can calibrate.
- The Mature Growth route carries the reinvestment charge and net-income growth, tested against the numbers in the design doc.
- The founder's agents can read every record and write overrides, notes and reports over MCP, under rules the server enforces.
- Any value investor can read a company report in five pages, and every number in it traces to an appendix row.
- A user installs Fairband in one command, enters their own keys once, and keeps all data on their machine.

## Non-Goals

- No technical analysis and no technical price target. The horizons do not match, and two prices would conflict.
- No brokerage connection. The user places every trade.
- No LLM inside Fairband: no API key, no agent graph, no hosted AI. The intelligence is the user's own agents.
- No hosted service. Banks, insurers, REITs and OTC listings are out for now.
- No scheduled refresh. Nothing runs unless the user asks.
- No screener builder and no idea tracking. Insider trades and 13F holdings are shown as evidence with the value beside them. They never change a value or a stance.
- No CLI surface and no public HTTP API. One command starts the server. The web page and the MCP server are the only entry points.

Deferred to a later phase, not refused (founder, 2026-10-27): a free data path for basic users (FC-51); portfolio management as a playbook skill, where the agent writes notes and recommendations on the portfolio against the user's strategy over MCP (FC-52). Fairband itself still computes no strategy.

## Uncertainties

- assumption — The decile translation of Damodaran's growth words gives a sane flag rate. Check after the classifier runs on the universe.
- question — Whether the selected FMP plan supplies the required annual depth, fields and company coverage. Verify account entitlement and actual data before assigning sources.
- question — Which required inputs, if any, are missing from FMP and available from GuruFocus? Resolve through data mapping before implementing the affected adapters. No gaps means FMP alone; remaining gaps mean GuruFocus only for those inputs.
- risk — External agents may not follow the playbook. Fairband can enforce writes, not reasoning. The mechanical-versus-reviewed log is the measure.
- closed (founder, 2026-10-27) — Fairband and EquityEval are unrelated (`docs/design.md`, section 2). The question was listed here in error.
- risk — The growth-belief rule from the stocks repo needs the Base Rate Book, which cannot ship. A source an open-source user can get is needed.
- question — Sources for sales-to-capital, failure probability and distress probability, which the early and Decline routes need.
- risk — The MCP specification moves quickly; the agent surface may need rework between releases.

## Evidence Notes

- `docs/design.md` (2026-10-25 to 2026-10-27) — the founder's decisions and reasons, with the decision log.
- `../openalice/reports/Valuation methods by life cycle phase.md` — the literature behind every route; supports the one-engine wedge.
- `../stocks` — the method v1.7, the mechanical screen, 171 notes with phase labels for calibration, and the readability complaint.
- `../TradingAgents/reports/` — readable reports; 10 of 11 price targets were chart levels. Supports "no technical analysis".
- `../equityeval/discovery/` (2026-10-24) — 10 of 18 research platforms run an MCP server, none with per-agent authority. Supports the MCP surface.
- Founder decisions of 2026-10-27: local web app, MCP server, no LLM inside, no CLI, paid data only. Source-selection clarification, 2026-10-28: prefer FMP alone; retain GuruFocus only for required gaps established by data mapping.

## Open Questions

- Product (map): whether the work inbox is a first-release capability. (The EquityEval relationship was closed on 2026-10-27: unrelated.)
- Architecture: the database technology (SQLite or DuckDB were named); the front-end stack; the MCP transport on localhost; the jobs model; the point-in-time design; the source assignment after mapping required inputs against FMP and checking GuruFocus only for gaps.
- Release and roadmap: which routes ship in the first release; the twelve open design items in `docs/design.md`, section 15, each at the release that builds its route.
- Validation: establish whether FMP alone covers all required inputs during data mapping. Later: whether other investors adopt it.
