import type { Proposal } from '@shopnod/shared-types';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../messages/en.json';
import { ProposalCard } from './proposal-card';

const ctx = { shopName: "Ali's Bakery", currency: 'PKR', timezone: 'Asia/Karachi' };

function proposal(over: Partial<Proposal> = {}): Proposal {
  return {
    id: 'p1',
    shop_id: 's1',
    status: 'pending',
    source: 'rules',
    items: [{ item_id: 'i1', name: 'Croissant', category: 'pastry', was_minor: 18000, new_price_minor: 15300, cost_minor: 9000, pct: 15 }],
    proposed_pct: 15,
    original_pct: 15,
    final_pct: null,
    window_start: '2026-03-10T10:30:00Z',
    window_end: '2026-03-10T12:00:00Z',
    cap: 30,
    reason: 'Quiet for 40 min, 38% below a normal Tuesday. 12 croissants expire tonight.',
    guardrail_saves: [],
    created_at: '2026-03-10T10:00:00Z',
    ...over,
  };
}

function renderCard(p: Proposal) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="en" messages={en} timeZone="UTC">
      <QueryClientProvider client={qc}>
        <ProposalCard proposal={p} ctx={ctx} />
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ currency: 'PKR', timezone: 'Asia/Karachi' }), { status: 200 })));
});
afterEach(() => vi.unstubAllGlobals());

describe('proposal card', () => {
  it('shows the % in large type, old price to new price, the reason as a quote and the window in shop time', () => {
    renderCard(proposal());
    expect(screen.getByRole('article', { name: 'Offer proposal, 15 percent off' })).toBeInTheDocument();
    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getByText('Croissant')).toBeInTheDocument();
    expect(screen.getByLabelText('Regular price')).toHaveClass('line-through');
    expect(screen.getByLabelText('Offer price')).toHaveTextContent(/153/);
    expect(screen.getByTestId('proposal-reason')).toHaveTextContent(/12 croissants expire tonight/);
    expect(screen.getByText(/15:30–17:00/)).toBeInTheDocument(); // 10:30Z is 15:30 in Karachi (UTC+5), not UTC time
  });

  it('labels the source honestly: "Rule-based" or "AI"', () => {
    const { unmount } = renderCard(proposal({ source: 'rules' }));
    expect(screen.getByText('Rule-based')).toBeInTheDocument();
    unmount();
    renderCard(proposal({ source: 'ai' }));
    expect(screen.getByText('AI')).toBeInTheDocument();
  });

  it('shows a margin chip with words, only when the cost is known', () => {
    const { unmount } = renderCard(proposal());
    expect(screen.getByTestId('margin-chip')).toHaveTextContent('41% margin');
    unmount();
    renderCard(proposal({ items: [{ item_id: 'i1', name: 'Croissant', was_minor: 18000, new_price_minor: 15300 }] }));
    expect(screen.queryByTestId('margin-chip')).toBeNull();
  });

  it('flags low margin and below-cost with words, not colour alone', () => {
    const { unmount } = renderCard(proposal({ items: [{ item_id: 'i', name: 'Cake', was_minor: 18000, new_price_minor: 10000, cost_minor: 9000 }] }));
    expect(screen.getByTestId('margin-chip')).toHaveTextContent('Low margin: 10%');
    unmount();
    renderCard(proposal({ items: [{ item_id: 'i', name: 'Cake', was_minor: 18000, new_price_minor: 8000, cost_minor: 9000 }] }));
    expect(screen.getByTestId('margin-chip')).toHaveTextContent('Below cost');
  });

  it('shows "Guardrail saved you: 25% → 15%" when the validator lowered the AI', () => {
    renderCard(proposal({ original_pct: 25, guardrail_saves: [{ rule: 'max_discount_pct', message: 'Guardrail saved you: 25% → 15%', before: 25, after: 15 }] }));
    expect(screen.getByText('Guardrail saved you: 25% → 15%')).toBeInTheDocument();
  });

  it('has Approve, Edit and Reject, all reachable with the keyboard', () => {
    renderCard(proposal());
    for (const name of ['Approve', 'Edit', 'Reject']) {
      const b = screen.getByRole('button', { name });
      expect(b).toBeEnabled();
      expect(b.tabIndex).toBeGreaterThanOrEqual(0);
    }
    expect(screen.getByRole('article')).toHaveAttribute('tabindex', '0');
  });

  it('hides the action buttons while waiting for the dashboard confirmation of an AI assistant request', () => {
    renderCard(proposal({ status: 'awaiting_confirmation' }));
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
    const card = screen.getByRole('article');
    expect(within(card).getByText('Waiting for your confirmation')).toBeInTheDocument();
  });
});
