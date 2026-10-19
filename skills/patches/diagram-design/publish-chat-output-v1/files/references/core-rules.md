# Core diagram rules

Read this for every diagram. Type references own layout grammar and may explicitly exempt a type from a shared rule. Use the effective style returned by `scripts/resolve_style.py`; literal colors in examples do not override a profile.

## 1. Philosophy

Every node represents a distinct idea and every edge carries information. Merge concepts that always travel together; remove redundant labels/edges. Aim for density 4/10 and 1–2 focal elements. Split over-budget diagrams into overview and detail.

## 2. Use boundaries

Draw only when a visual teaches more than prose or a table. Use bullets/tables for lists or simple before/after, a sentence for a one-shape diagram, and wiretext for quick Unicode sketches. Do not force a diagram. Full selection and behavioral routing: [type-index.md](type-index.md).

## 4. Universal anti-patterns

No gratuitous dark cyan/purple glow, shadows, identical treatment for every node, default equal-width summary-card grids, oversized rounded boxes (maximum 6–10px), vertical arrow text, floating legends inside the figure, unmasked edge labels, or accents on every important node. Do not reproduce an imported renderer's layout. Mono is for technical values, never blanket styling; never JetBrains Mono. Use the type-specific anti-patterns too.

## 5. Design system

Use named roles from the effective guide: `paper`/`paper-2` backgrounds, `ink` primary text/strokes, `muted`/`soft` secondary labels and arrows, `rule`/`rule-solid` hairlines, `accent`/`accent-tint` for at most two focal elements, `link` for HTTP/API/external edges. Node treatments and exact font roles come from the resolver. Preserve brand families/weights, disclose fallback fonts; otherwise names use Geist sans, technical values Geist Mono, title Instrument Serif, callouts italic serif. For CJK use the matching Noto/local fallback, 12px minimum; wide/full-width characters cost 1em, other characters their Latin advance, combining marks zero. CJK arrow/legend/tag prose uses 12px sans, weight 500, without tracking/uppercase; expand masks. Detailed language/series/terminal rules remain in [style-guide.md](style-guide.md), loaded only for those features. Series colors are only for charts that need them; terminal is a separate fixed opt-in skin.

## 6. Core SVG primitives and connector rules

1. Off-axis connectors use rounded orthogonal elbows (`r=8`, minimum 6). Straight lines are only horizontal/vertical. Type-specific arcs/ribbons/diagonals need an explicit exemption in the type reference. Elbow and bridge formulas: [type-architecture.md](type-architecture.md); code examples: [svg-primitives.md](svg-primitives.md).
2. Every arrow label has an opaque paper mask and a visible 6–10px gap from the stroke. Center it on a clear segment (beside vertical edges), not on the arrow. Keep Latin labels ≤14 characters; never vertical writing.
3. No connectors share a stroke or run on top of each other. Offset routes ≥12px; use bridge/hop for unavoidable point crossings. Redesign or split if arrows cannot be traced independently.
4. Multiple connectors on one node edge need distinct attach points ≥12px apart (8px only for tiny boxes). For N on edge length L use offset `L*k/(N+1)`, k=1..N. Do not merge strokes near the node; parallel arrows remain separated along their whole length.
5. Reroute around non-endpoint boxes. Only a geometrically unavoidable intervening cross-cutting box may be crossed: use a dashed transit stroke, label the visible end, and put the arrowhead at the true destination, never the intervening box.
6. A label mask must not overlap a node painted after it; the node would clip the text. Put masks on open canvas beyond node bounds. A badge fully inside its own node or a mask over an earlier zone container is allowed. Use the repository geometry verifier when available; installed self-check alone does not validate all geometry.

Draw arrows before node masks/boxes. Use opaque paper masks under translucent node fills, node `rx=6`, rectangular type tags `rx=2`. Define default/accent/link arrow markers. Keep the default background clean paper and borderless; dotted paper and framed containers are opt-in. Put the legend in a horizontal strip below the drawing, separated by a hairline, and add about 60px to the viewBox. Code and optional primitives stay in [svg-primitives.md](svg-primitives.md).

## 7. Layout and complexity

Use the 4px grid for coordinates, dimensions, padding and gaps (20/24/32/40/48px gaps, 8/12/16px padding); prescribed typography, 6px radii, stroke widths, opacity and 22px dot patterns retain their explicit exceptions. Default: at most 9 nodes, 12 arrows and 2 focal elements. Specialized budgets are in the selected type reference and [type-budgets.md](type-budgets.md), read only for the selected type when applicable. Imports have conditional `faithful` exceptions in [output-spec.md](output-spec.md); connector rules never relax. Header → borderless diagram → optional varied-width summary cards → hairline footer. Card/template details: [presentation.md](presentation.md).

## 9. Pre-output gate

Confirm type/pattern/size and assumptions; load its type reference. Check node/edge meaning, labeled decision exits, all paths ending or looping explicitly, selected complexity budget, ≤2 focal elements and a complete minimal legend. Remove redundant content. Check all six connector rules, legibility, viewBox containment, no clipped labels and grid alignment. Confirm font roles, brand/fallbacks, no shadows/oversized radii/equal generic cards. For imports report merged/collapsed/dropped content; never invent or silently omit source components. Run the installed self-check on the completed file before publication. Detailed upstream checklist: [design-details.md](design-details.md), only when a check needs elaboration.

## 12. Output and accessible SVG

Produce self-contained HTML with embedded CSS and inline SVG; The only allowed remote stylesheet is `https://fonts.googleapis.com/css2?...`, with local font fallbacks; omit remote preconnect links (including fonts.gstatic.com), external images and other remote resources. Static by default. Load [animation.md](animation.md) only for requested motion or when ordered change materially benefits from it; motion must preserve the full static/no-JS meaning and honor reduced-motion/print/static-query states. Use the supplied motion controller, never improvise it.

The diagram SVG has `role="img"` and `aria-labelledby` pointing to both title and description. `<title>` is the first child before defs; `<desc>` follows. Use unique file/variant-prefixed IDs, never bare `title`/`desc`. Title names the subject (about ≤60 characters); description is one content-focused sentence, not shape narration. Decorative SVG uses `aria-hidden="true"`. Export only requested formats through [export.md](export.md); do not mislabel HTML as image bytes. Publish through the chat artifact tool and return its exact link.
