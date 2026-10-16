/** Typed access to the ShopNod API. `api.d.ts` is generated: never edit it by hand. */
import type { components, paths } from './api';

export type { components, paths };
type S = components['schemas'];

export type Me = S['MeOut'];
export type Shop = S['ShopOut'];
export type ShopSummary = S['ShopSummary'];
export type Template = S['TemplateOut'];
export type Item = S['ItemOut'];
export type ItemInput = S['ItemIn'];
export type Guardrails = S['GuardrailOut'];
export type GuardrailsInput = S['GuardrailIn'];
export type Proposal = S['ProposalOut'];
export type ProposalItem = S['ProposalItem'];
export type Offer = S['OfferOut'];
export type OfferStats = S['OfferStatsOut'];
export type Confirmation = S['ConfirmationOut'];
export type Redeem = S['RedeemOut'];
export type Summary = S['SummaryOut'];
export type Billing = S['BillingOut'];
export type AuditEntry = S['AuditOut'];
export type AgentRun = S['AgentRunOut'];
export type Token = S['TokenOut'];
export type TokenCreated = S['TokenCreatedOut'];
export type AdminStatus = S['AdminStatusOut'];
export type SignalResult = S['SignalOut'];
export type ApproveResult = S['ApproveOut'];

/** The one error shape every response uses. */
export interface ApiErrorBody {
  error: { code: string; message: string; retryable: boolean; request_id: string | null; details?: Record<string, unknown> };
}

/** Live (SSE) event types on GET /v1/shop/stream. */
export type LiveEventType =
  | 'proposal.created' | 'proposal.decided' | 'confirmation.requested'
  | 'redemption.recorded' | 'offer.ended' | 'offer.published' | 'claim.created';
export interface LiveEvent { type: LiveEventType; data: Record<string, unknown> }
