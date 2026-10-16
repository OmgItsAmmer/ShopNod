'use client';
/** TanStack Query hooks. Live (SSE) events invalidate the matching keys, see lib/live.tsx. */
import type {
  AdminStatus, AgentRun, AuditEntry, Billing, Confirmation, Guardrails, Item, Me, Offer, OfferStats, Proposal, Shop,
  Summary, Template, Token,
} from '@shopnod/shared-types';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { api } from './api';

export const keys = {
  me: ['me'] as const,
  shop: ['shop'] as const,
  templates: ['templates'] as const,
  items: ['items'] as const,
  guardrails: ['guardrails'] as const,
  proposals: (status?: string) => ['proposals', status ?? 'open'] as const,
  confirmations: ['confirmations'] as const,
  offers: (status?: string) => ['offers', status ?? 'all'] as const,
  offer: (id: string) => ['offer', id] as const,
  offerStats: (id: string) => ['offer-stats', id] as const,
  summary: ['summary'] as const,
  learning: ['learning'] as const,
  billing: ['billing'] as const,
  audit: (action?: string) => ['audit', action ?? 'all'] as const,
  agentRuns: (agent?: string) => ['agent-runs', agent ?? 'all'] as const,
  agentRun: (id: string) => ['agent-run', id] as const,
  tokens: ['tokens'] as const,
  admin: ['admin-status'] as const,
};

export const useMe = () => useQuery({ queryKey: keys.me, queryFn: () => api<Me>('/v1/auth/me'), retry: false, staleTime: 0, refetchOnMount: 'always' });
export const useShop = () => useQuery({ queryKey: keys.shop, queryFn: () => api<Shop>('/v1/shop/shop') });
export const useTemplates = () => useQuery({ queryKey: keys.templates, queryFn: () => api<Template[]>('/v1/shop/templates'), staleTime: Infinity });
export const useItems = () => useQuery({ queryKey: keys.items, queryFn: () => api<Item[]>('/v1/shop/items') });
export const useGuardrails = () => useQuery({ queryKey: keys.guardrails, queryFn: () => api<Guardrails>('/v1/shop/guardrails') });

export const useProposals = (status?: string) =>
  useQuery({
    queryKey: keys.proposals(status),
    queryFn: () => api<Proposal[]>(`/v1/shop/proposals${status ? `?status=${encodeURIComponent(status)}` : ''}`),
    placeholderData: keepPreviousData,
  });

export const useConfirmations = () => useQuery({ queryKey: keys.confirmations, queryFn: () => api<Confirmation[]>('/v1/shop/confirmations') });

export const useOffers = (status?: string) =>
  useQuery({
    queryKey: keys.offers(status),
    queryFn: () => api<Offer[]>(`/v1/shop/offers${status ? `?status=${encodeURIComponent(status)}` : ''}`),
    placeholderData: keepPreviousData,
  });
export const useOffer = (id: string) => useQuery({ queryKey: keys.offer(id), queryFn: () => api<Offer>(`/v1/shop/offers/${id}`) });
export const useOfferStats = (id: string) =>
  useQuery({ queryKey: keys.offerStats(id), queryFn: () => api<OfferStats>(`/v1/shop/offers/${id}/stats`) });

export const useSummary = () => useQuery({ queryKey: keys.summary, queryFn: () => api<Summary>('/v1/shop/insights/summary') });

export interface LearningCurve {
  weeks: { week: string; proposals: number; approved: number; approval_rate: number; edit_rate: number; avg_edit: number }[];
  totals: {
    proposals: number; decided: number; approval_rate: number | null; edit_rate: number | null; avg_edit: number | null;
    expired: number; median_time_to_decision_s: number | null;
  };
  reject_reasons: Record<string, number>;
  approval_channels: Record<string, number>;
  guardrail_saves: { clamped: number; blocked: number };
  learned_pct_by_category: Record<string, number>;
  next_proposal_pct: number;
}
export const useLearning = () => useQuery({ queryKey: keys.learning, queryFn: () => api<LearningCurve>('/v1/shop/insights/learning-curve') });

export const useBilling = () => useQuery({ queryKey: keys.billing, queryFn: () => api<Billing>('/v1/shop/billing') });
export const useAudit = (action?: string) =>
  useQuery({ queryKey: keys.audit(action), queryFn: () => api<AuditEntry[]>(`/v1/shop/audit?limit=200${action ? `&action=${encodeURIComponent(action)}` : ''}`) });
export const useAgentRuns = (agent?: string) =>
  useQuery({ queryKey: keys.agentRuns(agent), queryFn: () => api<AgentRun[]>(`/v1/shop/agent-runs?limit=100${agent ? `&agent=${agent}` : ''}`) });
export const useAgentRun = (id: string) => useQuery({ queryKey: keys.agentRun(id), queryFn: () => api<AgentRun>(`/v1/shop/agent-runs/${id}`) });
export const useTokens = () => useQuery({ queryKey: keys.tokens, queryFn: () => api<Token[]>('/v1/shop/tokens') });
export const useAdminStatus = (enabled = true) =>
  useQuery({ queryKey: keys.admin, queryFn: () => api<AdminStatus>('/v1/admin/status'), enabled, refetchInterval: 5000 });
