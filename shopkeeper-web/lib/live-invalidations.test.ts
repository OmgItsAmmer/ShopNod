import { describe, expect, it } from 'vitest';
import { INVALIDATIONS } from './live';

describe('which cached data each live event refreshes', () => {
  it('covers every event the server sends', () => {
    for (const type of ['proposal.created', 'proposal.decided', 'confirmation.requested', 'redemption.recorded', 'offer.ended', 'offer.published']) {
      expect(INVALIDATIONS[type]?.length, type).toBeGreaterThan(0);
    }
  });

  it('a redemption refreshes the impact tiles and billing', () => {
    expect(INVALIDATIONS['redemption.recorded']).toEqual(expect.arrayContaining(['summary', 'billing', 'offers']));
  });

  it('a decision refreshes the learning chart', () => {
    expect(INVALIDATIONS['proposal.decided']).toContain('learning');
  });
});
