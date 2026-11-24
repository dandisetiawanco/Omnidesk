# Omni Glass Design System

Product: OmniDesk
Tagline: Your computer. Powered by intelligence.
Dial: ENERGY 2 / RHYTHM 2 / MOTION 2

## Design Read and Rationale (R-31)

- Color: Neutral graphite (`#0E1116` dark, `#F3F5F8` light) and crisp silver surfaces give OmniDesk the calm clarity of an operating-system utility rather than a marketing SaaS dashboard. One restrained ice-blue accent (`#0B66C3` light, `#6CB6FF` dark text / `#1563B8` dark solid) marks active navigation, focused inputs, and primary execution actions. Semantic green, amber, and red carry real execution and risk states paired with explicit icons and labels, never color alone.
- Material and Glass (Owner-Directed 4-Tier Hierarchy): Omni Glass uses four calibrated depths rather than uniform blur. Tier 0 exposes native OS window vibrancy (macOS `NSVisualEffectView::UnderWindowBackground`, Windows 11 Mica / Windows 10 Acrylic, Linux compositor or solid fallback). Tier 1 covers translucent navigation chrome (sidebar, draggable native titlebar, Teach Mode recording banner). Tier 2 applies high-opacity frosted surfaces (`82%` to `84%`) with hairline specular top edges to primary workspace panels (Command Composer, Operator Timeline, Workflow Inspector, Settings) so text retains `> 12:1` contrast. Tier 3 elevates transient floating surfaces (Command Palette, Approval Dialogs, Floating Assistant, Toasts) with deeper blur and controlled shadow. Performance Mode collapses all blur filters to crisp solid surfaces.
- Typography (R-06 compliance): System-native UI typography (`-apple-system, BlinkMacSystemFont, "Segoe UI Variable", "Segoe UI", "Ubuntu", sans-serif`) matches each host OS natively and eliminates web-font layout shift. Tabular numerals (`font-variant-numeric: tabular-nums`) keep timestamps, durations, file sizes, and step counts vertically aligned. Monospace (`ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`) is used strictly for file paths, SHA-256 digests, selectors, and JSON workflow schemas, never for decorative headlines.
- Layout and Rhythm (R-05, RHYTHM 2): Each screen is composed around the primary decision made there. Home centers on the natural-language command composer with live system readiness beside it. Operator uses a split execution layout (plan and timeline on the left, live context and approval rail on the right). Workflow Studio uses a full-bleed interactive node canvas with a docked inspector. Teach Mode uses a focused three-stage capture, review, and parameterize pipeline. Activity uses a scannable audit table with an inline detail drawer.
- Spacing and Radii (R-11): Radii follow structural hierarchy: `6px` for inline badges and keyboard caps, `8px` for inputs and buttons, `12px` for workspace panels, and `16px` only for top-layer modal dialogs. No pill-shaped defaults across all controls.
- Elevation and Glow (R-12, R-13): Workspace panels sit flat on the canvas with hairline borders. Elevation shadows appear only on floating overlays (Command Palette, Permission Dialog, contextual popovers) and the pinned Emergency Stop bar when a run is active. No decorative ambient glow on cards, icons, or backgrounds.
- Motion (R-19, MOTION 2): Motion communicates physical state transitions: top-layer dialog entry/exit via `@starting-style` and `transition-behavior: allow-discrete`, sidebar width transition, and execution progress bars. All non-essential motion pauses under `prefers-reduced-motion: reduce` and when OmniDesk Performance Mode is enabled for lower-powered hardware.
- Icons (R-04): Lucide icons (requested in product specification) are chosen strictly for literal functional meaning (folders, play/pause/stop, shield, terminal, globe, sliders). Sparkles, stars, magic wands, robots, and glowing orbs are banned.
- Identity Motif: The OmniDesk mark combines a precision octagonal frame with an offset directional aperture representing desktop control and bounded permission, rendered as an adaptive monochrome/ice-blue geometric SVG across light mode, dark mode, and system tray states.

## Verified WCAG AA Palette (contrast-check.py)

| Token | Light Mode | Dark Mode | Verified Contrast |
| --- | --- | --- | --- |
| Canvas | `#F3F5F8` | `#0E1116` | Base ground |
| Surface | `#FFFFFF` | `#161B22` | Elevated solid pane |
| Rail / Subtle | `#EAEFF5` | `#12161D` | Adaptive navigation shell |
| Text Primary | `#11161F` | `#F0F4F8` | 16.60:1 (light), 15.65:1 (dark) |
| Text Secondary | `#455061` | `#9BA7B8` | 7.47:1 (light), 7.10:1 (dark) |
| Accent Solid + White | `#0B66C3` | `#1563B8` | 5.67:1 (light), 5.99:1 (dark) |
| Accent Text on Surface | `#0B66C3` | `#6CB6FF` | 5.67:1 (light), 8.05:1 (dark) |
| Success Text on Surface | `#146C43` | `#4CD98D` | 6.45:1 (light), 9.57:1 (dark) |
| Warning Text on Surface | `#8A5300` | `#F5B942` | 6.33:1 (light), 9.80:1 (dark) |
| Danger Button + White | `#B42318` | `#C92A2A` | 6.57:1 (light), 5.46:1 (dark) |
| Control Border (non-text) | `#6E7B8F` | `#68768A` | 4.29:1 (light), 3.75:1 (dark) |
