'use client';

import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';

export interface ChartColors {
  series: [string, string, string, string];
  grid: string;
  axis: string;
  surface: string;
}

const FALLBACK: ChartColors = { series: ['#4B68FF', '#FFE24B', '#B0C7FF', '#4F4F4F'], grid: '#D9D9D9', axis: '#656565', surface: '#FFFFFF' };

/**
 * Recharts colours from the theme tokens (theme.md §5): series in order primary, secondary, accent, darkerGrey;
 * grid lines `border`, axis labels `textMuted`. No hex values live in components.
 */
export function useChartColors(): ChartColors {
  const { resolvedTheme } = useTheme();
  const [colors, setColors] = useState<ChartColors>(FALLBACK);
  useEffect(() => {
    const cs = getComputedStyle(document.documentElement);
    const v = (name: string, fb: string) => cs.getPropertyValue(name).trim() || fb;
    setColors({
      series: [v('--primary', FALLBACK.series[0]), v('--secondary', FALLBACK.series[1]), v('--accent', FALLBACK.series[2]), resolvedTheme === 'dark' ? '#939393' : '#4F4F4F'],
      grid: v('--border', FALLBACK.grid),
      axis: v('--muted-foreground', FALLBACK.axis),
      surface: v('--card', FALLBACK.surface),
    });
  }, [resolvedTheme]);
  return colors;
}
