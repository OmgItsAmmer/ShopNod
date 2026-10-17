'use client';

import type { Redeem } from '@shopnod/shared-types';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Camera, CameraOff, Check, X } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Field, Input } from '@/components/ui/input';
import { StatusChip } from '@/components/ui/chips';
import { api, ApiError, errorMessage, newKey } from '@/lib/api';
import { formatMoney } from '@/lib/money';
import { useMe } from '@/lib/queries';
import { RecentSet, type ScanResultKind, isShopNodPayload, normalizeShortCode, vibrationFor } from '@/lib/scan';
import { playSound, vibrate } from '@/lib/sound';
import { cn } from '@/lib/utils';

type Source = { payload: string } | { short_code: string };
interface HistoryRow {
  at: number;
  label: string;
  result: ScanResultKind;
}

type CameraState = 'idle' | 'starting' | 'running' | 'denied' | 'unsupported';

interface BarcodeDetectorLike {
  detect(source: CanvasImageSource): Promise<{ rawValue: string }[]>;
}
declare global {
  interface Window {
    BarcodeDetector?: new (opts?: { formats?: string[] }) => BarcodeDetectorLike;
  }
}

/** Camera scanning: the native BarcodeDetector where it exists, `html5-qrcode` everywhere else. */
function useQrCamera(onDetect: (text: string) => void, paused: boolean) {
  const [state, setState] = useState<CameraState>('idle');
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const stopRef = useRef<() => void>(() => undefined);
  const onDetectRef = useRef(onDetect);
  onDetectRef.current = onDetect;
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  const stop = useCallback(() => {
    stopRef.current();
    stopRef.current = () => undefined;
    setState((s) => (s === 'running' || s === 'starting' ? 'idle' : s));
  }, []);

  const start = useCallback(async () => {
    setState('starting');
    if (!navigator.mediaDevices?.getUserMedia) {
      setState('unsupported');
      return;
    }
    try {
      if (window.BarcodeDetector) {
        const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
        const video = videoRef.current;
        if (!video) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        video.srcObject = stream;
        await video.play();
        let alive = true;
        const loop = async () => {
          while (alive) {
            if (!pausedRef.current && video.readyState >= 2) {
              try {
                const codes = await detector.detect(video);
                if (codes[0]?.rawValue) onDetectRef.current(codes[0].rawValue);
              } catch {
                /* a frame failed to decode: try the next one */
              }
            }
            await new Promise((r) => setTimeout(r, 180));
          }
        };
        void loop();
        stopRef.current = () => {
          alive = false;
          stream.getTracks().forEach((t) => t.stop());
          video.srcObject = null;
        };
        setState('running');
      } else {
        const { Html5Qrcode } = await import('html5-qrcode');
        const scanner = new Html5Qrcode('qr-fallback', { verbose: false });
        await scanner.start(
          { facingMode: 'environment' },
          { fps: 8, qrbox: { width: 240, height: 240 } },
          (text) => {
            if (!pausedRef.current) onDetectRef.current(text);
          },
          () => undefined,
        );
        stopRef.current = () => {
          void scanner.stop().then(() => scanner.clear()).catch(() => undefined);
        };
        setState('running');
      }
    } catch (e) {
      const name = (e as { name?: string })?.name;
      setState(name === 'NotAllowedError' || name === 'SecurityError' ? 'denied' : 'unsupported');
    }
  }, []);

  useEffect(() => () => stopRef.current(), []);
  return { state, start, stop, videoRef, native: typeof window !== 'undefined' && !!window.BarcodeDetector };
}

function ResultOverlay({ result, onClose, currency }: { result: Redeem; onClose: () => void; currency: string }) {
  const t = useTranslations('scan');
  const locale = useLocale();
  const ok = result.result === 'ok';
  const btn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    btn.current?.focus();
    const id = setTimeout(onClose, ok ? 7000 : 12000);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      clearTimeout(id);
      window.removeEventListener('keydown', onKey);
    };
  }, [onClose, ok]);

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="scan-title"
      data-testid="scan-result"
      data-result={result.result}
      className={cn('fixed inset-0 z-[60] grid place-items-center p-6 text-center text-white', ok ? 'bg-success' : 'bg-destructive')}
    >
      <div className="grid max-w-xl justify-items-center gap-5">
        <span className="animate-pop grid size-32 place-items-center rounded-full bg-white/20">
          {ok ? <Check className="size-20" strokeWidth={3} aria-hidden /> : <X className="size-20" strokeWidth={3} aria-hidden />}
        </span>
        <h2 id="scan-title" className="text-5xl font-extrabold leading-tight sm:text-6xl">
          {ok ? t('applyPct', { pct: result.discount_pct ?? 0 }) : t(`result.${result.result}`)}
        </h2>
        {ok && (
          <ul className="grid gap-1 text-2xl">
            {result.items.map((i) => (
              <li key={i.name}>
                {i.name}: <span className="line-through opacity-80">{formatMoney(i.was_minor, currency, locale)}</span> → <strong>{formatMoney(i.new_price_minor, currency, locale)}</strong>
              </li>
            ))}
          </ul>
        )}
        {!ok && <p className="text-2xl">{t(`hint.${result.result}`)}</p>}
        <Button ref={btn} size="lg" variant="outline" className="mt-2 min-w-48 border-white bg-transparent text-white hover:bg-white/15" onClick={onClose} data-testid="scan-next">
          {t('scanNext')}
        </Button>
      </div>
    </div>
  );
}

/** The counter scan page: full-width camera, an always-visible short-code box, and a big ✅ / ❌. */
export function ScanView() {
  const t = useTranslations('scan');
  const qc = useQueryClient();
  const { data: me } = useMe();
  const currency = me?.shop?.currency ?? 'USD';
  const [result, setResult] = useState<Redeem | null>(null);
  const [code, setCode] = useState('');
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const recent = useRef(new RecentSet(4000));
  const attemptKey = useRef<{ sig: string; key: string } | null>(null);

  const redeem = useMutation({
    mutationFn: (src: Source) => {
      const sig = JSON.stringify(src);
      // A fresh key per scan; reused only if the very same attempt is retried after a network error.
      if (!attemptKey.current || attemptKey.current.sig !== sig) attemptKey.current = { sig, key: newKey() };
      return api<Redeem>('/v1/shop/redemptions', { method: 'POST', body: src, idempotencyKey: attemptKey.current.key });
    },
    onSuccess: (r, src) => {
      attemptKey.current = null;
      setResult(r);
      vibrate(vibrationFor(r.result));
      playSound(r.result === 'ok' ? 'success' : 'error', true);
      setHistory((h) => [{ at: Date.now(), label: 'short_code' in src ? src.short_code : t('qrScanned'), result: r.result }, ...h].slice(0, 8));
      if (r.result === 'ok') {
        for (const k of ['summary', 'offers', 'offer', 'offer-stats', 'billing']) void qc.invalidateQueries({ queryKey: [k] });
        setCode('');
      }
    },
    onError: (e) => {
      const msg = e instanceof ApiError && e.retryable ? t('networkRetry') : errorMessage(e);
      setResult({ result: 'invalid', discount_pct: null, items: [], offer: null, message: msg });
      vibrate([400]);
      playSound('error', true);
    },
  });

  const handleDetect = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (recent.current.has(trimmed) || redeem.isPending) return;
      if (!isShopNodPayload(trimmed)) {
        // Not one of ours (a random QR): say so once, instead of calling the server
        setResult({ result: 'invalid', discount_pct: null, items: [], offer: null, message: t('result.invalid') });
        vibrate([400]);
        return;
      }
      redeem.mutate({ payload: trimmed });
    },
    [redeem, t],
  );

  const closeResult = useCallback(() => {
    setResult(null);
    recent.current.clear();
  }, []);

  const camera = useQrCamera(handleDetect, !!result || redeem.isPending);
  const codeValid = code.length === 6;

  return (
    <div className="grid gap-5">
      <div className="grid gap-1">
        <h1 className="text-3xl font-extrabold">{t('title')}</h1>
        <p className="text-lg text-muted-foreground">{t('subtitle')}</p>
      </div>

      <Card className="overflow-hidden">
        <div className="relative grid aspect-[4/3] max-h-[60vh] w-full place-items-center bg-editorial sm:aspect-video" data-testid="camera-area">
          {camera.native ? (
            <video ref={camera.videoRef} playsInline muted className={cn('size-full object-cover', camera.state !== 'running' && 'hidden')} aria-label={t('cameraLabel')} />
          ) : (
            <div id="qr-fallback" className={cn('size-full', camera.state !== 'running' && 'hidden')} />
          )}
          {camera.state === 'running' && (
            <div aria-hidden className="pointer-events-none absolute inset-[18%] rounded-3xl border-4 border-white/90 shadow-[0_0_0_9999px_rgba(0,0,0,0.35)]" />
          )}
          {camera.state !== 'running' && (
            <div className="grid justify-items-center gap-3 p-6 text-center text-white">
              {camera.state === 'denied' || camera.state === 'unsupported' ? <CameraOff className="size-12" aria-hidden /> : <Camera className="size-12" aria-hidden />}
              <p className="max-w-sm text-lg">
                {camera.state === 'denied' ? t('cameraDenied') : camera.state === 'unsupported' ? t('cameraUnsupported') : t('cameraIdle')}
              </p>
              {camera.state !== 'unsupported' && (
                <Button size="lg" variant="secondary" onClick={() => void camera.start()} loading={camera.state === 'starting'} data-testid="start-camera">
                  {t('startCamera')}
                </Button>
              )}
            </div>
          )}
        </div>
        {camera.state === 'running' && (
          <div className="flex justify-end p-3">
            <Button variant="outline" onClick={camera.stop}>
              {t('stopCamera')}
            </Button>
          </div>
        )}
      </Card>

      <Card className="p-5">
        <form
          className="grid gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (codeValid) redeem.mutate({ short_code: code });
          }}
        >
          <label htmlFor="short-code" className="text-base font-semibold">
            {t('shortCode')}
          </label>
          <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center">
            <Input
              id="short-code"
              value={code}
              onChange={(e) => setCode(normalizeShortCode(e.target.value))}
              inputMode="text"
              autoCapitalize="characters"
              autoComplete="off"
              spellCheck={false}
              maxLength={6}
              placeholder="K7M4PX"
              aria-describedby="short-code-hint"
              className="text-center text-3xl font-bold tracking-[0.3em] uppercase"
              data-testid="short-code-input"
            />
            <Button
              type="submit"
              size="lg"
              disabled={!codeValid}
              loading={redeem.isPending}
              data-testid="redeem-code"
              className="min-h-12"
            >
              {t('check')}
            </Button>
          </div>
          <p id="short-code-hint" className="text-sm text-muted-foreground">
            {t('shortCodeHint')}
          </p>
        </form>
      </Card>

      {history.length > 0 && (
        <section aria-labelledby="recent-scans" className="grid gap-2">
          <h2 id="recent-scans" className="text-xl font-bold">
            {t('recent')}
          </h2>
          <ul className="grid gap-2">
            {history.map((h) => (
              <li key={h.at} className="flex items-center justify-between gap-3 rounded-xl bg-muted px-4 py-2">
                <span className="font-medium">{h.label}</span>
                <StatusChip tone={h.result === 'ok' ? 'success' : 'error'}>{h.result === 'ok' ? t('ok') : t(`result.${h.result}`)}</StatusChip>
              </li>
            ))}
          </ul>
        </section>
      )}

      {result && <ResultOverlay result={result} onClose={closeResult} currency={currency} />}
    </div>
  );
}
