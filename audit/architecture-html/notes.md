# Architecture HTML Audit Notes

## Audit Scope

Surface: `architecture.html`

Task: Review the showcase architecture diagram for executive readability, visual hierarchy, responsive behavior, and screenshot-visible accessibility risks.

Destination: Local folder, `audit/architecture-html/`

Capture tool: Playwright fallback. The Browser-specific capture surface was not available in this session.

## Captured Steps

1. `01-before-desktop.png` - Original desktop architecture board.
   - Health: Needs improvement.
   - Finding: The graph and vector section compressed multiple circular nodes into a narrow panel. Labels such as Components, Resources, and Incidents overlapped or were partly hidden, making the central knowledge-layer message difficult to explain.
   - Finding: The four-column architecture row made the Chat Runtime and agent tool cards too narrow for reliable scanning.
   - Accessibility risk from screenshot: Several small labels depended on condensed typography and tight spacing. This likely reduced readability for presentation screens and zoomed viewing.

2. `02-before-mobile.png` - Original mobile architecture board.
   - Health: Needs improvement.
   - Finding: The graph was scaled with CSS transform, which made the relationship labels smaller instead of adapting the layout.
   - Finding: The mobile page stacked correctly, but the graph remained a decorative cluster instead of a readable explanation.
   - Accessibility risk from screenshot: Transformed content can become hard to read and does not solve semantic reading order.

3. `03-after-desktop.png` - Revised desktop architecture board.
   - Health: Good.
   - Improvement: The top architecture board now uses a wider knowledge-layer area and moves the Chat Runtime into its own row.
   - Improvement: The graph is now represented as clear relationship rows from APP001 to Components, Resources, Incidents, Doc Chunks, and Dependencies.
   - Improvement: The runtime and LangChain tool cards are wider and easier to scan.
   - Remaining limit: Screenshot review confirms visible layout quality, but it does not prove full WCAG compliance or screen-reader behavior.

4. `04-after-mobile.png` - Revised mobile architecture board.
   - Health: Good.
   - Improvement: The graph no longer uses transform scaling. It reflows into readable stacked relationship rows.
   - Improvement: The key architecture narrative remains intact: source systems, ingestion, knowledge layer, runtime, guardrails, demo flow.
   - Remaining limit: Keyboard focus and screen-reader output were not tested from screenshots alone.

## Changes Made

- Reworked the main diagram grid from a cramped four-column row into a two-row layout.
- Expanded the Knowledge Layer so the Neo4j graph and vector index explanation has enough room.
- Replaced overlapping graph bubbles with readable relationship rows and explicit edge labels.
- Added a vector-search callout that explains how semantic retrieval and graph traversal work together.
- Expanded the Chat Runtime row so Chainlit and LangChain tools are readable side by side.
- Increased small supporting text sizes and improved muted text contrast.
- Removed fragile mobile graph scaling and allowed the knowledge graph to reflow naturally.

## Evidence Limits

This audit is screenshot-grounded. It confirms visible layout, readability, responsive reflow, and obvious overlap issues. It does not fully verify keyboard navigation, assistive technology behavior, color contrast calculations, or print/PDF export quality.
