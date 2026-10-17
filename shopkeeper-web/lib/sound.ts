/** A short "new proposal" chime, made with WebAudio so there is no audio file to ship. */

const KEY = 'shopnod.sound';

export function soundEnabled(): boolean {
  try {
    return localStorage.getItem(KEY) !== 'off';
  } catch {
    return true;
  }
}

export function setSoundEnabled(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? 'on' : 'off');
  } catch {
    /* private mode: ignore */
  }
}

let ctx: AudioContext | null = null;

function tone(freq: number, start: number, dur: number, gain = 0.08) {
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const g = ctx.createGain();
  osc.type = 'sine';
  osc.frequency.value = freq;
  g.gain.setValueAtTime(0, ctx.currentTime + start);
  g.gain.linearRampToValueAtTime(gain, ctx.currentTime + start + 0.02);
  g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + start + dur);
  osc.connect(g).connect(ctx.destination);
  osc.start(ctx.currentTime + start);
  osc.stop(ctx.currentTime + start + dur + 0.05);
}

export type SoundKind = 'proposal' | 'success' | 'error';

export function playSound(kind: SoundKind, force = false): void {
  if (typeof window === 'undefined' || (!force && !soundEnabled())) return;
  try {
    const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    ctx = ctx ?? new AC();
    if (ctx.state === 'suspended') void ctx.resume();
    if (kind === 'proposal') {
      tone(784, 0, 0.18);
      tone(1047, 0.16, 0.28);
    } else if (kind === 'success') {
      tone(660, 0, 0.12);
      tone(880, 0.1, 0.12);
      tone(1320, 0.2, 0.25);
    } else {
      tone(220, 0, 0.25, 0.12);
      tone(165, 0.22, 0.35, 0.12);
    }
  } catch {
    /* audio blocked until a user gesture: ignore */
  }
}

export function vibrate(pattern: number | number[]): void {
  try {
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) navigator.vibrate(pattern);
  } catch {
    /* unsupported */
  }
}
