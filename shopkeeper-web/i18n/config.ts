export const LOCALES = ['en', 'ur', 'ar', 'es'] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = 'en';
/** Right-to-left languages: the root element gets `dir="rtl"`. */
export const RTL_LOCALES: ReadonlySet<string> = new Set(['ur', 'ar']);
export const LOCALE_COOKIE = 'NEXT_LOCALE';

export const LOCALE_NAMES: Record<Locale, string> = {
  en: 'English',
  ur: 'اردو',
  ar: 'العربية',
  es: 'Español',
};

export function isLocale(v: string | undefined | null): v is Locale {
  return !!v && (LOCALES as readonly string[]).includes(v);
}

export function directionOf(locale: string): 'rtl' | 'ltr' {
  return RTL_LOCALES.has(locale) ? 'rtl' : 'ltr';
}

type Tree = { [k: string]: string | Tree };

/** Missing keys in a translation fall back to English instead of showing a raw key. */
export function mergeMessages(base: Tree, override: Tree): Tree {
  const out: Tree = { ...base };
  for (const [k, v] of Object.entries(override)) {
    const b = out[k];
    out[k] = typeof v === 'object' && v !== null && typeof b === 'object' && b !== null ? mergeMessages(b as Tree, v) : v;
  }
  return out;
}
