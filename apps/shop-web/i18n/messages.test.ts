import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import ar from '../messages/ar.json';
import en from '../messages/en.json';
import es from '../messages/es.json';
import ur from '../messages/ur.json';
import { LOCALES, directionOf, isLocale, mergeMessages } from './config';

type Tree = { [k: string]: string | Tree };
const root = path.resolve(__dirname, '..');

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name === '.next') continue;
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name)) out.push(p);
  }
  return out;
}

/** Same idea as scripts/extract_keys.py: `t('key')` resolves to the nearest preceding `useTranslations('ns')`. */
function usedKeys(): string[] {
  const keys = new Set<string>();
  const decl = /(?:const|let)\s+(\w+)\s*=\s*(?:await\s+)?(?:useTranslations|getTranslations)\(\s*'([\w.]+)'\s*\)/g;
  const call = /(?<![\w.])(\w+)\(\s*(?:'([\w.]+)'|`([^`]+)`)/g;
  for (const dir of ['app', 'components', 'lib']) {
    for (const file of walk(path.join(root, dir))) {
      const src = readFileSync(file, 'utf8');
      const decls = [...src.matchAll(decl)].map((m) => ({ pos: m.index ?? 0, v: m[1], ns: m[2] }));
      if (decls.length === 0) continue;
      const names = new Set(decls.map((d) => d.v));
      for (const m of src.matchAll(call)) {
        if (!names.has(m[1])) continue;
        const prior = decls.filter((d) => d.v === m[1] && d.pos < (m.index ?? 0)).at(-1);
        if (!prior) continue;
        keys.add(m[2] ? `${prior.ns}.${m[2]}` : `${prior.ns}.${m[3].split('${')[0]}*`);
      }
    }
  }
  return [...keys].sort();
}

function lookup(tree: Tree, dotted: string): string | Tree | undefined {
  return dotted.split('.').reduce<string | Tree | undefined>((node, part) => (typeof node === 'object' && node ? node[part] : undefined), tree);
}

function flatten(tree: Tree, prefix = ''): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(tree)) {
    if (typeof v === 'string') out[prefix + k] = v;
    else Object.assign(out, flatten(v, `${prefix}${k}.`));
  }
  return out;
}

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)/g)].map((m) => m[1]).sort();

/** Keys picked at runtime (t(variable)) that the scanner cannot see. */
const DYNAMIC: Record<string, string[]> = {
  nav: ['dashboard', 'offers', 'scan', 'items', 'guardrails', 'insights', 'agentTrace', 'audit', 'billing', 'settings', 'admin'],
  'onboarding.steps': ['shop', 'location', 'review'],
  'inbox.skipped': ['proposal_already_pending', 'active_offer_overlaps', 'budget_used_up', 'max_offers_reached', 'default'],
  'proposal.reasons': ['wrong_items', 'wrong_time', 'too_generous', 'other'],
  'proposal.violations': ['max_discount_pct', 'min_price', 'never_discount', 'banned_category', 'window_in_past', 'allowed_hours', 'max_offers_per_day', 'max_redemptions_per_offer', 'budget', 'invalid_pct', 'invalid_cap', 'window_invalid', 'unknown_item', 'no_items_left'],
  'offers.status': ['active', 'ended', 'sold_out'],
  'offers.tabs': ['active', 'ended', 'all'],
  'scan.result': ['invalid', 'expired', 'wrong_shop', 'already_redeemed', 'offer_ended'],
  'scan.hint': ['invalid', 'expired', 'wrong_shop', 'already_redeemed', 'offer_ended'],
  'insights.channels': ['dashboard', 'mcp_confirmed', 'mcp'],
  'audit.actors': ['user', 'agent', 'system', 'mcp'],
  'audit.channels': ['dashboard', 'mcp_confirmed', 'mcp'],
  'audit.filters': ['proposal', 'guardrails', 'approval', 'offer', 'redemption', 'token', 'billing'],
  'trace.agents': ['all', 'shop_agent', 'copy'],
  'trace.reasons': ['ai_outage_flag', 'circuit_open', 'no_ai_configured', 'timeout', 'error', 'invalid_output'],
  'admin.outboxStatus': ['pending', 'sent', 'dead'],
  'admin.breakerState': ['closed', 'open', 'half_open'],
  'settings.days': ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'],
  'settings.grid': ['busy', 'normal', 'quiet'],
};

describe('English messages cover every key the code uses', () => {
  const keys = usedKeys();

  it('finds a realistic number of keys', () => {
    expect(keys.length).toBeGreaterThan(300);
  });

  it('has every static key', () => {
    const missing = keys.filter((k) => !k.endsWith('*') && lookup(en as Tree, k) === undefined);
    expect(missing).toEqual([]);
  });

  it('has the group behind every dynamic key', () => {
    const missing = keys.filter((k) => k.endsWith('*')).map((k) => k.replace(/\.?\*$/, '')).filter((g) => typeof lookup(en as Tree, g) !== 'object');
    expect(missing).toEqual([]);
  });

  it('has every runtime-chosen key', () => {
    const missing: string[] = [];
    for (const [group, names] of Object.entries(DYNAMIC)) for (const n of names) if (lookup(en as Tree, `${group}.${n}`) === undefined) missing.push(`${group}.${n}`);
    expect(missing).toEqual([]);
  });

  it('has no empty strings', () => {
    expect(Object.entries(flatten(en as Tree)).filter(([, v]) => v.trim() === '')).toEqual([]);
  });
});

describe.each([
  ['ur', ur],
  ['ar', ar],
  ['es', es],
])('%s translation', (_name, tr) => {
  const enFlat = flatten(en as Tree);
  const trFlat = flatten(tr as Tree);

  it('has no keys that English does not have (typos)', () => {
    expect(Object.keys(trFlat).filter((k) => !(k in enFlat))).toEqual([]);
  });

  it('keeps the same {placeholders} as English', () => {
    const bad = Object.keys(trFlat).filter((k) => k in enFlat && placeholders(trFlat[k]).join() !== placeholders(enFlat[k]).join());
    expect(bad).toEqual([]);
  });

  it('translates the core screens: navigation, inbox, proposal actions and scan', () => {
    for (const k of ['nav.dashboard', 'nav.scan', 'dashboard.imQuiet', 'inbox.title', 'proposal.approve', 'proposal.edit', 'proposal.reject', 'proposal.aiWrittenLabel', 'scan.title', 'scan.applyPct', 'landing.tryAsJudge']) {
      expect(trFlat[k], k).toBeTruthy();
      expect(trFlat[k], `${k} should differ from English`).not.toBe(enFlat[k]);
    }
  });
});

describe('locales and right-to-left', () => {
  it('Urdu and Arabic are right-to-left, English and Spanish are not', () => {
    expect(directionOf('ur')).toBe('rtl');
    expect(directionOf('ar')).toBe('rtl');
    expect(directionOf('en')).toBe('ltr');
    expect(directionOf('es')).toBe('ltr');
    expect(LOCALES).toEqual(['en', 'ur', 'ar', 'es']);
  });

  it('only accepts known locales', () => {
    expect(isLocale('ur')).toBe(true);
    expect(isLocale('fr')).toBe(false);
    expect(isLocale(undefined)).toBe(false);
  });

  it('missing translations fall back to English instead of showing a raw key', () => {
    const merged = mergeMessages(en as Tree, ur as Tree) as Tree;
    expect(lookup(merged, 'proposal.approve')).toBe((ur as Tree & { proposal: Tree }).proposal.approve);
    expect(lookup(merged, 'admin.title')).toBe((en as Tree & { admin: Tree }).admin.title); // not translated in Urdu
    expect(lookup(merged, 'proposal.violations.max_discount_pct')).toBeTruthy();
  });
});
