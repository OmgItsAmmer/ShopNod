/// Parses cart line quantities for API payloads (integer, positive).
int parseBillQuantity(String raw) {
  final trimmed = raw.trim();
  if (trimmed.isEmpty) return 0;
  final asDouble = double.tryParse(trimmed);
  if (asDouble == null || asDouble <= 0) return 0;
  return asDouble.round();
}
