/// Canonical installment math — single source of truth for ADR-004.
///
/// All financial surfaces (plan generation, display totals, refund helpers)
/// MUST use this class so they stay consistent.
///
/// Formula:
///   financedBase     = billAmount − downPayment
///   marginAmount     = financedBase × (marginPercent / 100)
///   totalToSplit     = financedBase + documentCharges + otherCharges + marginAmount
///   totalCollectible = downPayment + totalToSplit
///
/// Installment rows (N rows, seq 1..N):
///   regular  = round(totalToSplit / N, 2)
///   last row = totalToSplit − (regular × (N−1))   // absorbs rounding drift
class InstallmentTotals {
  final double financedBase;
  final double marginAmount;
  final double totalToSplit;
  final double totalCollectible;

  const InstallmentTotals({
    required this.financedBase,
    required this.marginAmount,
    required this.totalToSplit,
    required this.totalCollectible,
  });
}

class InstallmentCalculator {
  InstallmentCalculator._();

  /// Compute all canonical totals from raw field values.
  static InstallmentTotals calculate({
    required double billAmount,
    required double downPayment,
    required double documentCharges,
    required double otherCharges,
    required double marginPercent,
  }) {
    final financedBase = billAmount - downPayment;
    final marginAmount =
        marginPercent > 0 ? financedBase * (marginPercent / 100) : 0.0;
    final totalToSplit =
        financedBase + documentCharges + otherCharges + marginAmount;
    final totalCollectible = downPayment + totalToSplit;

    return InstallmentTotals(
      financedBase: financedBase,
      marginAmount: marginAmount,
      totalToSplit: totalToSplit < 0 ? 0 : totalToSplit,
      totalCollectible: totalCollectible,
    );
  }

  /// Split [totalToSplit] into [n] installment amounts.
  /// Returns a list of length [n]; the last element absorbs rounding drift.
  static List<double> splitIntoInstallments(double totalToSplit, int n) {
    assert(n > 0);
    if (n == 1) return [totalToSplit];

    final regular =
        double.parse((totalToSplit / n).toStringAsFixed(2));
    final last =
        double.parse((totalToSplit - regular * (n - 1)).toStringAsFixed(2));

    return [
      ...List.filled(n - 1, regular),
      last,
    ];
  }
}
