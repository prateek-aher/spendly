---
name: frontend-design
description: Generates and redesigns UI pages/components for Spendly, a Flask + Jinja2 personal expense tracker (github.com/prateek-aher/spendly), matching its existing warm/editorial design system (paper/ink palette, forest-green accent, DM Serif Display + DM Sans, Lucide icons). Use this skill whenever the user asks to design, build, create, redesign, improve, or restyle any Spendly page or UI component — e.g. "design the dashboard page", "create UI for expense list", "build a component for budget alerts", "redesign the profile page" — even if they don't mention Spendly by name but the context is clearly this project (Flask templates, expense tracker, references to files like base.html/style.css). Also use when asked to add icons, forms, cards, charts, or navigation elements consistent with Spendly's look.
---

# Spendly UI Designer

Generates production-ready UI for Spendly — a Flask + Jinja2 personal expense
tracker with hand-written CSS (no framework). The goal is UI that looks like
it was built by the same person who built the rest of the app, not a generic
AI-generated SaaS template.

**Before writing any code, read `references/design-tokens.md`.** It contains
the actual CSS variables, typography rules, and component patterns pulled
from the live repo. This is the single source of truth for colors, spacing,
fonts, and existing component classes — don't guess or default to generic
"modern SaaS" styling (blue palettes, Inter/system sans headings, heavy
shadows, pill buttons everywhere). Spendly's look is warm, editorial, and
restrained: paper background, near-black ink, forest green + mustard
accents, a serif display font for headings only.

## Workflow

1. **Clarify scope, briefly.** You need: (a) what page/component, (b) what
   data/fields it displays or collects, (c) any constraints (existing route
   name, specific fields from the Flask backend, reference screenshot). If
   the user's request already contains enough of this, don't ask — proceed.
   Only ask a clarifying question when the request is genuinely ambiguous
   (e.g. "design the dashboard" with no hint of what data it shows).

2. **Check for reference material.** If the user attaches a screenshot or
   points to an existing template, look at it before designing — consistency
   with what already exists beats consistency with these notes. If they
   mention a page that isn't in `templates/` yet (dashboard, expense list,
   budget, categories, etc.), design it fresh using the tokens/patterns in
   `references/design-tokens.md`, extending them sensibly (e.g. new stat
   tile variants, new category colors following the existing desaturated
   palette).

3. **Design, then build.** Output has two parts every time:

   **A. UI structure (brief, 5-10 lines max)** — layout and key sections,
   and the 1-2 UX decisions worth calling out (e.g. "empty state for no
   transactions yet", "sticky filter bar on scroll"). Don't over-explain;
   this is a quick orientation, not a design doc.

   **B. Code** — by default (unless the user asks for something else):
   - A Jinja2 template file (`{% extends "base.html" %}` pattern, matching
     the block structure of existing templates — `title`, `content`, and
     `scripts`/`head` blocks as needed)
   - CSS additions written as a block ready to append to
     `static/css/style.css`, using only the existing `:root` variables
     (add new ones only if genuinely missing, following the existing naming
     convention)
   - Inline SVG icons (Lucide-style, see design-tokens.md) embedded directly
     in the template — don't make the user chase down a separate icon file

4. **Flag anything you had to assume.** If you invented a new color variant,
   a new component pattern, or guessed at backend field names/routes, say so
   in one line so the user can correct it easily.

## Design Rules (non-negotiable)

- Card-based layout, `var(--radius-md)` (12px) for cards, `var(--radius-sm)`
  (6px) for buttons/inputs, `var(--radius-lg)` (20px) only for large framing
  panels.
- Spacing on the ~8px grid already in use (see design-tokens.md).
- Borders (`1px solid var(--border)`) are the primary way to separate cards
  from background — reserve shadows for one or two elevated elements per
  page, using the existing subtle shadow value, not a generic drop shadow.
- Headings in `--font-display` (DM Serif Display), everything else in
  `--font-body` (DM Sans).
- Icons from Lucide only, sized and colored to match surrounding text
  (`currentColor`/`stroke` inheriting `--ink`/`--ink-muted`/`--accent`).
- Responsive by default: grid layouts collapse to 1 column under ~640px;
  don't ship a desktop-only layout unless explicitly asked.
- No clutter: every element on the page should justify its presence. Prefer
  whitespace over decoration.

## Consistency Check

Before finalizing, sanity-check the output against
`references/design-tokens.md`:
- Every color is a `var(--...)` reference, not a hardcoded hex.
- No Tailwind/Bootstrap classes or utility-class soup.
- Headings use the display font; nothing else does.
- Icons are Lucide-style, not emoji or a mismatched icon set.

If the user's request implies a visual direction that conflicts with the
existing system (e.g. "make it feel more like Stripe" — blue, sans-only,
glassy), point out the conflict and ask whether they want to evolve the
brand or stay consistent with what's shipped, rather than silently picking
one.

## Avoid

- Generic AI-template tells: hero sections with gradient blobs, glassmorphic
  cards, purple-to-blue gradients, oversized rounded pill buttons everywhere,
  Inter/system-font-only headings.
- Unstructured code dumps — always pair code with the brief structure
  summary from step 3A.
- Introducing a component library, CSS framework, or build step (Tailwind,
  Bootstrap, PostCSS pipeline) — this is plain HTML/CSS/Jinja2.
- Reproducing exact class names from design-tokens.md for a *new* kind of
  component if it doesn't fit — extend the pattern, don't force unrelated
  UI into an ill-fitting existing class.