import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { dark, light, palette } from './tokens';

const css = readFileSync(new URL('./theme.css', import.meta.url), 'utf8');

/** Pull `--name: value` pairs out of one CSS block. */
function vars(selector: string): Record<string, string> {
  const start = css.indexOf(selector + ' {');
  const body = css.slice(start, css.indexOf('}', start));
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/--([\w-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim().toUpperCase();
  return out;
}

const root = vars(':root');
const darkVars = vars('.dark');
const u = (s: string) => s.toUpperCase();

describe('theme.css and tokens.ts agree', () => {
  it('light roles match :root', () => {
    expect(root['background']).toBe(u(light.background));
    expect(root['foreground']).toBe(u(light.text));
    expect(root['card']).toBe(u(light.surface));
    expect(root['primary']).toBe(u(light.primary));
    expect(root['primary-strong']).toBe(u(light.link));
    expect(root['secondary']).toBe(u(light.highlight));
    expect(root['secondary-foreground']).toBe(u(light.onHighlight));
    expect(root['muted']).toBe(u(light.surfaceMuted));
    expect(root['muted-foreground']).toBe(u(light.textMuted));
    expect(root['accent']).toBe(u(palette.accent));
    expect(root['destructive']).toBe(u(light.error));
    expect(root['success']).toBe(u(light.success));
    expect(root['warning']).toBe(u(light.warning));
    expect(root['info']).toBe(u(light.info));
    expect(root['border']).toBe(u(light.border));
    expect(root['ring']).toBe(u(light.focusRing));
    expect(root['icon']).toBe(u(light.icon));
    expect(root['button-secondary']).toBe(u(light.buttonSecondary));
    expect(root['button-disabled']).toBe(u(light.buttonDisabled));
    expect(root['link']).toBe(u(light.link));
    expect(root['success-tint']).toBe(u(light.successTint));
    expect(root['warning-tint']).toBe(u(light.warningTint));
    expect(root['error-tint']).toBe(u(light.errorTint));
    expect(root['info-tint']).toBe(u(light.infoTint));
  });

  it('dark roles match .dark', () => {
    expect(darkVars['background']).toBe(u(dark.background));
    expect(darkVars['foreground']).toBe(u(dark.text));
    expect(darkVars['card']).toBe(u(dark.surface));
    expect(darkVars['border']).toBe(u(dark.border));
    expect(darkVars['icon']).toBe(u(dark.icon));
    expect(darkVars['link']).toBe(u(dark.link));
    expect(darkVars['primary']).toBe(u(dark.primary));
  });

  it('dark secondary text is 60% (not 50%): 50% on the muted surface was below WCAG AA 4.5:1', () => {
    expect(palette.textDarkSecondary).toBe('#F6F6F699');
    expect(darkVars['muted-foreground']).toBe('RGBA(246,246,246,.6)');
  });

  it('error text has a lighter dark-mode value so it stays readable (4.5:1) on dark cards', () => {
    expect(root['destructive-text']).toBe(u(light.errorText));
    expect(darkVars['destructive-text']).toBe(u(dark.errorText));
    expect(dark.errorText).not.toBe(dark.error);
  });

  it('dark page is a solid colour, never the see-through overlays', () => {
    expect(dark.background).toBe(palette.darkPage);
    expect(dark.background).not.toBe(palette.darkScaffoldBackground);
    expect(dark.surface).not.toBe(palette.darkContainer);
  });

  it('every themed colour is defined for both modes', () => {
    expect(Object.keys(dark).sort()).toEqual(Object.keys(light).sort());
  });
});
