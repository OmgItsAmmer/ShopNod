# ShopNod Theme (all frontends)

One colour system for every ShopNod frontend:
- `apps/shop-web`: Next.js + Tailwind + shadcn/ui
- `apps/shopper`: Expo app, used for Android, iOS **and** the `shopper-web` build

**Rule:** no hard-coded hex values in components. Always use a token from this file.

---

## 1. Base palette

These are the original values, unchanged.

### Brand
| Token | Hex | Use |
|---|---|---|
| `primary` | `#4B68FF` | Main brand blue: main buttons, active tab, links (see §5 for text rules) |
| `secondary` | `#FFE24B` | Yellow highlight: the offer % badge, "new" markers. **Always dark text on it.** |
| `accent` | `#B0C7FF` | Soft blue: selected chips, focus rings, links in dark mode |

### Status
| Token | Hex | Use |
|---|---|---|
| `error` | `#D32F2F` | Errors, Reject, "❌ invalid QR" |
| `success` | `#388E3C` | Approved, "✅ redeemed", good margin |
| `warning` | `#F57C00` | Guardrail warnings, low margin, offer ending soon |
| `info` | `#1976D2` | Tips, "why you see this" |

### Neutrals
| Token | Hex |
|---|---|
| `black` | `#232323` |
| `pureBlack` | `#000000` |
| `darkerGrey` | `#4F4F4F` |
| `darkGrey` | `#939393` |
| `grey` | `#D9D9D9` |
| `softGrey` | `#F4F4F4` |
| `lightGrey` | `#F9F9F9` |
| `white` | `#FFFFFF` |
| `transparent` | `#00000000` |
| `iconPrimary` | `#8D8D8D` |

### Light theme
| Token | Hex |
|---|---|
| `textPrimary` | `#272727` |
| `textSecondary` | `#656565` |
| `textWhite` | `#FFFFFF` |
| `light` | `#F6F6F6` |
| `primaryBackground` | `#F5F5F5` |
| `lightContainer` | `#F6F6F6` |
| `buttonPrimary` | `#4B68FF` |
| `buttonSecondary` | `#6C757D` |
| `buttonDisabled` | `#C4C4C4` |
| `borderPrimary` | `#D9D9D9` |

### Dark theme
| Token | Value | Note |
|---|---|---|
| `dark` | `#272727` | |
| `textDarkPrimary` | `#F6F6F6` | |
| `textDarkSecondary` | `#F6F6F6` at 50% (`#F6F6F680`) | |
| `darkScaffoldBackground` | `#000000` at 10% (`#0000001A`) | **Transparent.** Can't be a page background on its own (see §2). |
| `darkContainer` | `#FFFFFF` at 10% (`#FFFFFF1A`) | Card surface, laid over the page background |
| `borderSecondary` | `#313131` | |

---

## 2. ShopNod additions

These are new values, needed for the web and for accessibility.

| Token | Value | Why |
|---|---|---|
| `darkPage` | `#121212` | `darkScaffoldBackground` is 10% black, so on its own it shows whatever is behind it. On the web that's the white browser canvas, which breaks dark mode. We use `#121212` as the solid page colour. `darkContainer` (10% white) on top of it gives cards `#2A2A2A`. |
| `primaryStrong` | `#3A56F0` | `primary` on white has a contrast of **4.45:1**, just under the 4.5:1 WCAG AA minimum for small text. Use `primaryStrong` for small blue text and links on light backgrounds (5.6:1). |
| `onSecondary` | `#272727` (= `textPrimary`) | Text on the yellow `secondary` |
| `status*Tint` | each status colour at 12% | Background for status chips (§5) |

---

## 3. Light and dark roles

Components use these **role** names, never the palette names above. Swapping themes just swaps the values.

| Role | Light | Dark |
|---|---|---|
| `background` (page) | `primaryBackground` `#F5F5F5` | `darkPage` `#121212` |
| `surface` (cards, sheets) | `white` `#FFFFFF` | `darkContainer` over page → `#2A2A2A` |
| `surfaceMuted` (inputs, table stripes) | `lightContainer` `#F6F6F6` | `#FFFFFF0D` (5% white) |
| `text` | `textPrimary` `#272727` | `textDarkPrimary` `#F6F6F6` |
| `textMuted` | `textSecondary` `#656565` | `textDarkSecondary` `#F6F6F680` |
| `textOnPrimary` | `textWhite` | `textWhite` |
| `border` | `borderPrimary` `#D9D9D9` | `borderSecondary` `#313131` |
| `icon` | `iconPrimary` `#8D8D8D` | `darkGrey` `#939393` |
| `primary` (fills) | `buttonPrimary` `#4B68FF` | `primary` `#4B68FF` |
| `link` (small blue text) | `primaryStrong` `#3A56F0` | `accent` `#B0C7FF` |
| `buttonSecondary` | `#6C757D` | `#6C757D` |
| `buttonDisabled` | `#C4C4C4` (text `#656565`) | `#FFFFFF1F` (text `#F6F6F680`) |
| `highlight` | `secondary` `#FFE24B` | `secondary` `#FFE24B` |
| `focusRing` | `accent` `#B0C7FF` | `accent` `#B0C7FF` |
| `error` / `success` / `warning` / `info` | palette values | same values |

---

## 4. Code

### 4.1 One source of truth: `packages/theme`

```
packages/theme/
├── tokens.ts      # palette + light/dark roles (imported by the Expo app)
├── theme.css      # the same values as CSS variables (imported by shop-web)
└── tokens.test.ts # fails if theme.css and tokens.ts disagree
```

### 4.2 `packages/theme/tokens.ts`

```ts
export const palette = {
  primary: '#4B68FF', primaryStrong: '#3A56F0', secondary: '#FFE24B', accent: '#B0C7FF',
  iconPrimary: '#8D8D8D',
  error: '#D32F2F', success: '#388E3C', warning: '#F57C00', info: '#1976D2',
  black: '#232323', pureBlack: '#000000', darkerGrey: '#4F4F4F', darkGrey: '#939393',
  grey: '#D9D9D9', softGrey: '#F4F4F4', lightGrey: '#F9F9F9', white: '#FFFFFF', transparent: '#00000000',
  textPrimary: '#272727', textSecondary: '#656565', textWhite: '#FFFFFF',
  light: '#F6F6F6', primaryBackground: '#F5F5F5', lightContainer: '#F6F6F6',
  buttonPrimary: '#4B68FF', buttonSecondary: '#6C757D', buttonDisabled: '#C4C4C4', borderPrimary: '#D9D9D9',
  dark: '#272727', textDarkPrimary: '#F6F6F6', textDarkSecondary: '#F6F6F680',
  darkScaffoldBackground: '#0000001A', darkContainer: '#FFFFFF1A', borderSecondary: '#313131',
  darkPage: '#121212',
} as const;

const status = {
  error: palette.error, success: palette.success, warning: palette.warning, info: palette.info,
  errorTint: '#D32F2F1F', successTint: '#388E3C1F', warningTint: '#F57C001F', infoTint: '#1976D21F',
};

export const light = {
  background: palette.primaryBackground, surface: palette.white, surfaceMuted: palette.lightContainer,
  text: palette.textPrimary, textMuted: palette.textSecondary, textOnPrimary: palette.textWhite,
  border: palette.borderPrimary, icon: palette.iconPrimary,
  primary: palette.buttonPrimary, link: palette.primaryStrong,
  buttonSecondary: palette.buttonSecondary, buttonDisabled: palette.buttonDisabled, buttonDisabledText: palette.textSecondary,
  highlight: palette.secondary, onHighlight: palette.textPrimary, focusRing: palette.accent,
  ...status,
};

export const dark: typeof light = {
  background: palette.darkPage, surface: '#2A2A2A', surfaceMuted: '#FFFFFF0D',
  text: palette.textDarkPrimary, textMuted: palette.textDarkSecondary, textOnPrimary: palette.textWhite,
  border: palette.borderSecondary, icon: palette.darkGrey,
  primary: palette.primary, link: palette.accent,
  buttonSecondary: palette.buttonSecondary, buttonDisabled: '#FFFFFF1F', buttonDisabledText: palette.textDarkSecondary,
  highlight: palette.secondary, onHighlight: palette.textPrimary, focusRing: palette.accent,
  ...status,
};

export type Theme = typeof light;
```

### 4.3 Expo (`apps/shopper`)

```ts
// apps/shopper/src/theme.ts
import { useColorScheme } from 'react-native';
import { light, dark } from '@shopnod/theme';
export const useTheme = () => (useColorScheme() === 'dark' ? dark : light);
```

- Use it in components as `const t = useTheme(); <View style={{ backgroundColor: t.surface }} />`.
- Set `"userInterfaceStyle": "automatic"` in `app.json`, so the app follows the phone setting.
- In the web build, also set `<meta name="theme-color">` to `light.primary`.

### 4.4 Next.js + Tailwind v4 + shadcn (`apps/shop-web`)

`packages/theme/theme.css` (imported once in `app/globals.css`):

```css
:root {
  --background: #F5F5F5;  --foreground: #272727;
  --card: #FFFFFF;        --card-foreground: #272727;
  --popover: #FFFFFF;     --popover-foreground: #272727;
  --primary: #4B68FF;     --primary-foreground: #FFFFFF;
  --primary-strong: #3A56F0;
  --secondary: #FFE24B;   --secondary-foreground: #272727;
  --muted: #F6F6F6;       --muted-foreground: #656565;
  --accent: #B0C7FF;      --accent-foreground: #272727;
  --destructive: #D32F2F; --destructive-foreground: #FFFFFF;
  --success: #388E3C;  --warning: #F57C00;  --info: #1976D2;
  --border: #D9D9D9;  --input: #D9D9D9;  --ring: #B0C7FF;
  --icon: #8D8D8D;
  --button-secondary: #6C757D;  --button-disabled: #C4C4C4;
  --link: #3A56F0;
}

.dark {
  --background: #121212;  --foreground: #F6F6F6;
  --card: #2A2A2A;        --card-foreground: #F6F6F6;
  --popover: #2A2A2A;     --popover-foreground: #F6F6F6;
  --primary: #4B68FF;     --primary-foreground: #FFFFFF;
  --secondary: #FFE24B;   --secondary-foreground: #272727;
  --muted: rgba(255,255,255,.05); --muted-foreground: rgba(246,246,246,.5);
  --accent: #B0C7FF;      --accent-foreground: #272727;
  --destructive: #D32F2F; --destructive-foreground: #FFFFFF;
  --border: #313131;  --input: #313131;  --ring: #B0C7FF;
  --icon: #939393;
  --button-disabled: rgba(255,255,255,.12);
  --link: #B0C7FF;
}

@theme inline {
  --color-background: var(--background);   --color-foreground: var(--foreground);
  --color-card: var(--card);                --color-card-foreground: var(--card-foreground);
  --color-popover: var(--popover);          --color-popover-foreground: var(--popover-foreground);
  --color-primary: var(--primary);          --color-primary-foreground: var(--primary-foreground);
  --color-primary-strong: var(--primary-strong);
  --color-secondary: var(--secondary);      --color-secondary-foreground: var(--secondary-foreground);
  --color-muted: var(--muted);              --color-muted-foreground: var(--muted-foreground);
  --color-accent: var(--accent);            --color-accent-foreground: var(--accent-foreground);
  --color-destructive: var(--destructive);  --color-destructive-foreground: var(--destructive-foreground);
  --color-success: var(--success);  --color-warning: var(--warning);  --color-info: var(--info);
  --color-border: var(--border);  --color-input: var(--input);  --color-ring: var(--ring);
  --color-icon: var(--icon);  --color-link: var(--link);
  --color-button-secondary: var(--button-secondary);  --color-button-disabled: var(--button-disabled);
}

body { background: var(--background); color: var(--foreground); }
```

- Dark mode uses `next-themes` with `attribute="class"` and `defaultTheme="system"`.
- shadcn components pick these values up with no extra setup.
- In Tailwind classes, write `bg-primary`, `text-muted-foreground`, `border-border` and `text-link`, never `bg-[#4b68ff]`.

---

## 5. Rules for using colour

### Text contrast (WCAG 2.2 AA, required by [compliance.md §6](compliance.md))

| Pair | Contrast | Allowed for |
|---|---|---|
| `textPrimary` on `primaryBackground` / white | 14:1 | Everything |
| `textSecondary` on `primaryBackground` | 5.4:1 | Everything |
| White on `primary` `#4B68FF` | 4.45:1 | **Large text only:** 18.7 px bold or 24 px+. ShopNod buttons are big anyway, so button labels are **18 px+ semibold/bold**. |
| `primaryStrong` on white | 5.6:1 | Small blue text, links |
| `textPrimary` on `secondary` yellow | 11.5:1 | Everything. White on yellow is **never** used. |
| `darkGrey` / `iconPrimary` on white | 3.1–3.3:1 | Icons and disabled states only, **never body text** |
| `success` / `warning` as text on white | 4.1 / 2.9:1 | **Not allowed as text.** Use the status chip pattern below. |
| `error`, `info` as text on white | 5.0 / 4.6:1 | Fine for short messages |
| `primary` on `darkPage` | 4.2:1 | Fills only. Dark-mode links use `accent`. |

### Status chips (one pattern everywhere)
A chip has:
- a background of the status tint (12%)
- a coloured icon (the status colour)
- a label in `text` (not in the status colour)

Examples: `✓ Approved`, `⚠ Guardrail saved you: 25% → 15%`, `✕ Rejected`.

### ShopNod components

| Component | Colours |
|---|---|
| Offer % badge | Background `secondary`, text `onHighlight`, bold |
| "Was / now" price | Was: `textMuted` with strike-through. Now: `text`, bold. |
| "AI-written, approved by the shop" label | `info` icon + `textMuted` text, small but always visible |
| "Same price for everyone" note | `textMuted` |
| "Rule-based" label | Neutral chip: `surfaceMuted` background + `textMuted` text |
| Proposal card: Approve / Edit / Reject | Approve = `primary` fill. Edit = outline with `border` and `text`. Reject = text button in `error`. |
| Margin chip | `success` (healthy), `warning` (low), `error` (below cost), using the status chip pattern |
| Guardrail saved you | `warning` status chip |
| Scan result | ✅ = full-screen `success` with a white icon and **large** white text. ❌ = the same with `error`. |
| QR screen | **The QR code is always black on white, even in dark mode** (cameras need contrast). The short code below it uses `text`. |
| "Redeemed!" state | `success` chip + confetti in `primary`, `secondary` and `accent` |
| Charts (Recharts) | Series in order: `primary`, `secondary`, `accent`, `darkerGrey`. Grid lines `border`, axis labels `textMuted`. |
| Focus outline | 2 px `focusRing` plus a 2 px offset, on every interactive element |
| Disabled button | `buttonDisabled` background + `buttonDisabledText` text |

### Don'ts
- Don't use `darkScaffoldBackground` or `darkContainer` as a solid colour. They are see-through overlays.
- Don't put white text on `secondary`, `success` (small text) or `warning`.
- Don't use colour as the only signal. Every status also has an icon or a word.
- Don't change these values inside an app. Change them in `packages/theme`, and both apps update.
