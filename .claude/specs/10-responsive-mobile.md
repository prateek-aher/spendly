# Spec: Responsive Design for Mobile Devices

## Overview
Spendly's layout is desktop-first: `static/css/style.css` already has a few narrow-viewport media queries (hiding the hero mockup under 900px, stacking the profile header under 640px, etc.), but they were added ad hoc per page and leave real gaps. The biggest one: on screens under 600px, `.nav-links a:not(.nav-cta)` are hidden outright with no replacement, so a logged-in user on a phone loses access to "Profile", "Analytics", "Sign out", and their greeting — there is no way back to the app once you land on a page other than the one you're on. This step makes the whole app usable on a phone: a real mobile navigation menu, a transaction table that doesn't require horizontal scrolling to read, and touch-sized interactive elements, without changing any route or database behavior.

## Depends on
- Step 1 — Database Setup
- Step 3 — Login and Logout (nav greeting/session-aware links this step must keep reachable on mobile)
- Step 5 — Backend Routes for Profile Page (`profile.html`'s stats/filter/transaction-table/category-breakdown layout this step reflows)
- Step 7/8/9 — Add/Edit/Delete Expense (`expenses_add.html` form and the profile table's Edit/Delete actions this step resizes for touch)

## Routes
No new routes. No changes to any route handler in `app.py`.

## Database changes
No database changes.

## Templates
- **Create:** none
- **Modify:**
  - `templates/base.html` — add a hamburger toggle button inside `.nav-inner` (visible only under the mobile breakpoint) that shows/hides `.nav-links` as a slide-down panel, so every link that's reachable on desktop stays reachable on mobile.
  - `templates/profile.html` — add a `data-label` attribute to each `<td>` in the transaction table (e.g. `data-label="Date"`, `data-label="Amount"`) so the existing table can restyle itself into a stacked card list on narrow screens via CSS `::before { content: attr(data-label) }`, instead of relying on `.profile-table-wrap`'s horizontal scroll.

## Files to change
- `templates/base.html` — add a `<button class="nav-toggle" id="nav-toggle" aria-expanded="false" aria-controls="nav-links" aria-label="Menu">` (a simple hamburger icon, e.g. three `<span>` bars) between `.nav-brand` and `.nav-links`; give `.nav-links` an `id="nav-links"` so the button can reference it via `aria-controls`.
- `templates/profile.html` — add `data-label` attributes to the five `<td>` cells in the transaction row loop (Date, Description, Category, Amount, Actions).
- `static/css/style.css` — replace the current `@media (max-width: 600px) { .nav-links a:not(.nav-cta) { display: none; } }` rule with a proper mobile-nav pattern: hide `.nav-toggle` above the breakpoint, show it below the breakpoint, and turn `.nav-links` into an absolutely-positioned dropdown panel (full-width, below the navbar) that's hidden by default and shown via a `.nav-links.is-open` class under the breakpoint only — above the breakpoint `.nav-links` stays exactly as it renders today. Also: convert `.profile-table` to a stacked-card layout under ~640px using the new `data-label` attributes (`display: block` on `tr`/`td`, `td::before` showing the label), raise minimum tap-target sizing (padding/min-height) on `.filter-pill`, `.category-pill`, `.date-quick-pick`, `.btn-ghost`, and `.pagination-btn` under the same breakpoint, and make `.hero-actions` / `.cta-section` buttons stack full-width under ~480px.
- `static/js/main.js` — add a `DOMContentLoaded`-scoped handler that toggles `.is-open` on `#nav-links` (and flips `#nav-toggle`'s `aria-expanded`) on click, closes the menu when a nav link inside it is clicked (so navigating doesn't leave the menu stuck open on the next page), and closes it on `Escape` or on an outside click.

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No new breakpoints beyond what's needed — reuse/extend the existing `900px` / `600px` / `640px` / `480px` media query boundaries already in `style.css` rather than inventing new arbitrary ones.
- The hamburger toggle must be pure CSS-visibility + a small vanilla-JS class toggle — no new JS dependencies, no build step.
- `.nav-links` must render identically to how it does today above the breakpoint; the dropdown/`is-open` behavior only applies inside the mobile media query.
- Keep the transaction table's underlying `<table>` markup (don't switch to `<div>`-based cards) — the mobile look comes from CSS restyling the same table via `data-label`, so the desktop layout and any future JS/tests that query `.profile-table td` keep working unmodified.
- Every interactive element (nav links inside the mobile menu, filter pills, category pills, date quick-picks, edit/delete buttons, pagination buttons) must have at least a ~44px touch target on mobile per baseline accessibility guidance.

## Definition of done
- [ ] At a 375px-wide viewport while logged in, the hamburger toggle is visible in the navbar and `.nav-links` (greeting, Profile, Analytics, Sign out) is hidden until it's tapped
- [ ] Tapping the hamburger toggle reveals all nav links in a full-width dropdown below the navbar; tapping it again (or tapping a link, or pressing Escape, or tapping outside the menu) closes it
- [ ] At viewports ≥ 900px (or whatever the existing desktop breakpoint is), the navbar renders exactly as it does today — no hamburger visible, links inline
- [ ] On the profile page at 375px wide, the recent-transactions table reads as stacked rows with visible field labels (Date/Description/Category/Amount/Actions) and requires no horizontal scrolling to read any value
- [ ] On the profile page at ≥ 900px, the transaction table still renders as a normal table, unchanged from before this step
- [ ] Edit/Delete buttons, filter-period pills, category pills, and date quick-pick buttons are comfortably tappable (no visually-overlapping or sub-44px targets) at 375px wide
- [ ] The landing page's hero buttons and CTA button stack to full width and remain fully visible with no horizontal overflow at 375px wide
- [ ] The add/edit expense form is fully usable (no clipped or overflowing inputs) at 375px wide
- [ ] No horizontal page-level scrollbar appears on any existing page (landing, login, register, profile, analytics, add/edit expense) at 375px wide
</content>
