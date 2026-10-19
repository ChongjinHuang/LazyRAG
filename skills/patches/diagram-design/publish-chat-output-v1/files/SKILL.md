---
name: diagram-design
description: Create branded architecture, IT current-state, flowchart, sequence, state machine, ER/data model, timeline, swimlane, quadrant, radar/spider, polar chart (polar/radial lollipop), loop/flywheel, nested, tree, org chart, layer stack, Venn, pyramid/funnel, treemap, bar, line, Gantt and scatter charts, high-level, process, medallion, data flow, DP integration, DP security matrix, Sankey, fishbone, Wardley map, kanban, user journey, deployment, dependency graph, UML class, story map, or database schema diagrams as standalone HTML/SVG/PNG. Redraw .drawio/.drawio.png/.drawio.svg or Mermaid .mmd sources at a chosen size/detail; onboard brand tokens from a website; add semantic patterns, callouts, accessible motion, or sketchy/hand-drawn styling.
license: MIT
metadata:
  version: "2.6"
---

# Diagram Design

Create a clear, accessible diagram and deliver it as a self-contained HTML file with inline SVG and CSS. Read `references/core-rules.md` for the shared diagram rules and the reference for the selected diagram type. Do not read the entire skill package before drawing.

## Decide what to draw

- Use a flowchart for decisions and approval paths (`references/type-flowchart.md`); a sequence diagram for messages ordered in time (`references/type-sequence.md`); an architecture diagram for components and connections (`references/type-architecture.md`); a swimlane when handoffs between roles are the point (`references/type-swimlane.md`). For other types, find the matching `references/type-*.md` and read that one reference.
- Use the facts the user supplied. Ask only for missing information that changes the essential nodes, order, or branches. When a reasonable assumption is enough, mark it beside the diagram instead of blocking delivery. Do not add an unrequested process rule as fact.
- Before every diagram, inspect the project root for `.diagram-design` and resolve the effective style guide by `references/profiles.md` (marker first, then the working copy). A valid marker loads its named profile directly, including `profile: default`; a missing named profile must be reported and resolved with the user, never silently replaced. For an invalid marker, report it and follow the markerless fallback. Read the selected guide before drawing. If the markerless guide is still the shipped default, proceed unless the user asks for branding; use `references/onboarding.md` only for requested customization.

## Draw and check

1. Choose a diagram type and read `references/core-rules.md` plus its type reference. If the diagram has a behavior pattern that needs specialized semantics, read `references/semantic-patterns.md`. Use `assets/template.html` as a starting point when file tools are available.
2. Build one complete `.html` document with embedded CSS and an inline `<svg>`. Make the viewBox contain every node and connector. Keep labels legible, distinguish approval and rejection paths, and give every decision an explicit next step or end. Avoid external images and scripts; motion is optional only when requested.
3. Give the SVG `role="img"`, a unique `aria-labelledby`, and matching first-child `<title>` and `<desc>`. Check that connectors attach to nodes without crossing labels or clipping the viewBox. If a file was written and the installed script is available, run `python3 scripts/self_check.py <html-file>`; fix any failures before publishing.

`python3 scripts/mermaid_extract.py <existing-file>` and `python3 scripts/drawio_extract.py <existing-file>` parse existing Mermaid and draw.io sources for **redrawing**. They are not generators and do not accept diagram nodes, edges, titles, or output-format arguments. For a diagram described in prose, write the HTML directly. Read `references/import-mermaid.md` or `references/import-drawio.md` only for an import. Export PNG or SVG only when requested, following `references/export.md`; never label HTML bytes as an image.

## Deliver in LazyMind chat

A workspace file alone is not a chat deliverable. Once the HTML is complete, call `save_chat_artifact` with an `.html` filename. Pass the complete HTML as `content` with `content_type="text"`, or pass the path of an existing workspace file with `content_type="file"`. Do this before optional refinements. If the user requested multiple files, save each actual file once. In the final reply, copy each returned `file_markdown` link verbatim, briefly state what the diagram covers, and finish the turn. Do not spend another model round on presentation after the files are saved.
