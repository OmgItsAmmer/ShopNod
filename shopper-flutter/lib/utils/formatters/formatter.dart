import 'package:intl/intl.dart';

class TFormatter {
  static String formatDate(DateTime? date) {
    date ??= DateTime.now();
    final onlyDate = DateFormat('dd/MM/yyyy').format(date);
    final onlyTime = DateFormat('hh:mm').format(date);
    return '$onlyDate at $onlyTime';
  }

  /// Money from minor units (paisa/cents), e.g. 84000 → "Rs 840".
  static String formatMinor(int amountMinor, {String symbol = 'Rs '}) =>
      formatCurrency(amountMinor / 100, symbol: symbol);

  static String formatCurrency(double amount, {String symbol = 'Rs '}) =>
      NumberFormat.currency(
        locale: 'en_US',
        symbol: symbol,
        decimalDigits: amount == amount.roundToDouble() ? 0 : 2,
      ).format(amount);

  /// Pakistani mobile numbers: 03001234567 → (0300) 123 4567.
  static String formatPhoneNumber(String phoneNumber) {
    if (phoneNumber.length == 10) {
      return '(${phoneNumber.substring(0, 3)}) ${phoneNumber.substring(3, 6)} ${phoneNumber.substring(6)}';
    } else if (phoneNumber.length == 11) {
      return '(${phoneNumber.substring(0, 4)}) ${phoneNumber.substring(4, 7)} ${phoneNumber.substring(7)}';
    }
    return phoneNumber;
  }
}
