# Quick3DPrint reference design audit

Audit date: 17 October 2026  
Reference: <https://www.quick3dp.com/>  
Method: rendered Chromium inspection with Playwright, computed-style sampling, hover inspection, and full-page screenshots at 1440×900, 1920×1080, 768×1024, and 390×844.

## Source-of-truth screenshots

- `artifacts/reference/desktop-1440x900.png`
- `artifacts/reference/large-1920x1080.png`
- `artifacts/reference/tablet-768x1024.png`
- `artifacts/reference/mobile-390x844.png`
- `artifacts/reference/desktop-hover.png`

The reference measured 5,841 px tall at 1440 px wide and 7,367 px tall at 390 px wide. The mobile page is not a scaled desktop composition: the showcase, process, location content, and footer all stack vertically.

## Visual system measured from the rendered site

### Colour and surfaces

- Page and card surface: `rgb(255, 255, 255)`.
- Near-black section and hero frame: visually `rgb(14, 14, 14)` / near-black ink.
- Primary reference accent: `rgb(232, 56, 61)`.
- Secondary location surface: `rgb(250, 250, 250)`.
- Primary text renders near `rgb(10, 10, 10)`; muted copy is a mid zinc/grey.
- White is used for text on the red and near-black sections.
- The design avoids gradients and decorative glass. Most hierarchy comes from flat colour blocks, strong type, borders, and whitespace.

ShopNod adaptation: layout, geometry, contrast rhythm, and interaction treatment follow the reference, while the accent is mapped to the mandated ShopNod `primary`, yellow tags to `secondary`, dark sections to the existing black neutral, and all component colours to semantic theme roles from `docs/theme.md`.

### Typography

- Font: Geist variable, weights 100–900, with the rendered fallback stack `Geist, "Geist Fallback", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`.
- Body: 16 px / 24 px, weight 400.
- Desktop hero at 1440 px: 120 px, weight 700, line-height 114 px (`.95`), letter-spacing `-6.6px` (`-.055em`), measured width 1,004 px.
- Desktop section display headings: 60 px, weight 700, 61.2 px line-height, `-2.7px` tracking.
- Process item headings: 24 px / 32 px, weight 600, `-.6px` tracking.
- Small section labels: 14 px / 20 px. Location column labels use weight 600, `0.7px` spacing, uppercase.
- Mobile hero: approximately 43 px with the same compressed line-height and tight tracking. Mobile display headings step down while retaining the same weight and density.

### Layout and spacing

- Hero is inset 12 px on desktop and 8 px on mobile, with a heavy near-black rounded frame.
- Desktop header: x 12/y 12, 1,416×92 px, padding 24×32 px. Mobile header is 374×84 px with 20 px padding.
- Desktop hero headline starts near y 257 and is centered. The hero fills the first 900 px viewport.
- Primary desktop content container: 1,200 px (x 120–1320 at 1440 px), giving 120 px outer gutters.
- Main vertical sections use roughly 112–128 px spacing on desktop and 96–112 px on mobile.
- Primary buttons are pills. Header CTAs measure 40 px high with 8×20 px padding; the main CTA is 64 px high with 16×32 px padding.
- Reference CTA border: 2 px dark; effectively fully rounded.
- Product showcase: text selector on the left, media panel on the right. Rows are separated with fine rules rather than individual cards. Mobile turns each category into a stacked text/image sequence.
- Process: near-black full-width section, large heading followed by four separated rows. Desktop rows are number / title / description; mobile rows stack description under the title.
- Footer: white, columnar desktop layout and a long single-column mobile layout, separated from preceding content by a subtle rule.

### Motion and interaction

- Initial eyebrow, hero heading, and hero artwork use an 800 ms upward reveal with `cubic-bezier(.16,1,.3,1)` and staggered delays.
- Hero objects float on a 6 s `ease-in-out` loop with 0.7 s staggered delays.
- A decorative ring spins over 70 s linear.
- Marquee is a seamless 24 s linear infinite loop.
- CTA hover uses a 150 ms standard ease transition and does not translate or scale.
- Product-selector hover changes active presentation without geometric movement.
- ShopNod implementation preserves the reveal/floating/marquee character, uses short colour transitions for controls, and disables continuous motion under `prefers-reduced-motion`.

## Responsive observations

- 1920 px retains a centered capped content width rather than stretching text indefinitely.
- 768 px reduces gutters, preserves the framed hero, and begins stacking dense two-column sections.
- 390 px keeps the hero full-viewport, compresses the brand/navigation, stacks all sections, changes the process to two columns (number + content), and makes footer columns vertical.
- Reference mobile sections measured: proof begins around y 1,072; showcase y 1,455; process y 3,122; CTA y 4,084; red social block y 4,572; footer starts around y 6,502.

## ShopNod content and functionality mapping

- Quick Order → existing demo-login action and sign-in route.
- Product categories → ShopNod’s actual offer lifecycle: quiet signal, guardrail-checked draft, human approval, and QR redemption.
- Numeric claims and awards → replaced with truthful product guarantees; no invented customers, awards, or performance statistics.
- Social feed → replaced with a real trust/audit preview because the project contains no verified ShopNod social feed or social links.
- Reference photography → replaced with a styled preview of the real ShopNod offer interface because the repository contains no suitable licensed product photography.
- All API-backed dashboard, onboarding, scan, settings, billing, trace, audit, and offer flows remain connected to their original routes and logic.

## Implementation screenshots

- `artifacts/local/desktop-1440x900.png`
- `artifacts/local/large-1920x1080.png`
- `artifacts/local/tablet-768x1024.png`
- `artifacts/local/mobile-390x844.png`

At all four measured viewport sizes the implementation had `scrollWidth === clientWidth`, no page overflow, and no browser console or runtime errors during capture.
