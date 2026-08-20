# UI and UX Review

## Reviewed Screens

- Extractor: `/`
- Automation: `/automation`
- History: `/history`
- Menu Map: `/menu-map`

## Confirmed Fixes

### Automation Scroll Jump

The supplier tab synchronizer called `scrollIntoView()` during page setup and
background updates. On desktop, the browser could interpret this as a request to
move the entire document, making the page jump to the top after about one
second.

The supplier tab rail now adjusts only its own horizontal scroll position. A
headless Botasaurus regression confirmed the document scroll position remains
stable.

### Resume State

The UI now treats `resuming` as an active state. It displays live timing and
continues polling, but does not offer a duplicate Resume button while the helper
process is launching.

### Destructive Actions

History deletion, run deletion, job deletion, watchlist clearing, and cleanup
retain visible confirmation and now send a server-verifiable destructive
confirmation header. Failed destructive requests remain visibly reported.

## Responsive Results

Headless Botasaurus checks at 360, 390, 768, and 1440 pixels found:

- no horizontal page overflow;
- no Resume/Delete overlap;
- stable navigation and supplier tabs;
- readable job and run metadata;
- two-column mobile action grids with full-width touch targets;
- stable automation polling without page movement.

The 360-pixel Automation view keeps the operational hierarchy compact: supplier
selection, jobs and runs, then the run inspector. Text wraps instead of being
clipped.

## Accessibility and Interaction

- Interactive controls use semantic buttons and accessible names.
- Selected supplier and run state are exposed through ARIA attributes.
- Errors and retry actions remain visible.
- Mobile action targets are at least 42 pixels high.
- Existing reduced-motion and focus styles were preserved.

## Remaining UX Notes

The application is an operational dashboard, so it intentionally favors dense,
scannable information over decorative marketing layouts. Very large histories
remain long by nature; filtering and the run inspector should be used before
reviewing individual product rows.
