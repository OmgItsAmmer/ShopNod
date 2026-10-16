/* --
      LIST OF Enums
      They cannot be created inside a class.
-- */

/// Switch of Custom Brand-Text-Size Widget
enum AppRole { admin, user }

enum TransactionType { buy, sell }

enum EntityType {
  customer,
  salesman,
  vendor,
  user,
}

enum ProductType { single, variable }

enum ProductVisibility { published, hidden }

enum TextSizes { small, medium, large }

enum ImageType { asset, network, memory, file }

enum MediaCategory {
  folders,
  brands,
  categories,
  products,
  users,
  customers,
  salesman,
  guarantors,
  shop,
  vendors,
  collections,
}

extension MediaCategoryX on MediaCategory {
  String get folderName => name;
}

enum OrderStatus { pending, completed, cancelled }

enum PurchaseStatus { pending, received, cancelled }

enum PaymentMethods {
  paypal,
  googlePay,
  applePay,
  visa,
  masterCard,
  creditCard,
  paystack,
  razorPay,
  paytm
}

enum VariationType { Regular, small, medium, large }

enum StockLocation { Shop, Garage1, Garage2 } // temporary

enum SaleType { cash, installment }

/// POS bill pricing tier (retail / wholesale / installment sell prices).
enum SalePriceProfile { retail, wholesale, installment }

/// Single-control payment schedule (replaces the conflicting DurationType +
/// frequencyInMonth pair — ADR-005).
/// The canonical value is [intervalMonths]; labels are shown to the cashier.
enum PaymentSchedule {
  monthly,
  everyTwoMonths,
  quarterly,
  semiAnnual,
  yearly,
  custom;

  /// Months between installments.  [custom] returns 0; the controller
  /// reads [InstallmentController.customIntervalMonths] in that case.
  int get intervalMonths => const {
        PaymentSchedule.monthly: 1,
        PaymentSchedule.everyTwoMonths: 2,
        PaymentSchedule.quarterly: 3,
        PaymentSchedule.semiAnnual: 6,
        PaymentSchedule.yearly: 12,
        PaymentSchedule.custom: 0,
      }[this]!;

  String get label => const {
        PaymentSchedule.monthly: 'Monthly (every 1 month)',
        PaymentSchedule.everyTwoMonths: 'Every 2 months',
        PaymentSchedule.quarterly: 'Quarterly (every 3 months)',
        PaymentSchedule.semiAnnual: 'Semi-annual (every 6 months)',
        PaymentSchedule.yearly: 'Yearly (every 12 months)',
        PaymentSchedule.custom: 'Custom…',
      }[this]!;
}

// Kept for DB/report compatibility — do not use in new code.
// @deprecated Use PaymentSchedule instead.
enum DurationType { Duration, Monthly, Quarterly, Yearly }

enum UnitType {
  item, // Individual items
  dozen, // 12 items
  gross, // 144 items (12 dozen)
  kilogram, // Weight in kg
  gram, // Weight in g
  liter, // Volume in L
  milliliter, // Volume in mL
  meter, // Length in m
  centimeter, // Length in cm
  inch, // Length in inches
  foot, // Length in feet
  yard, // Length in yards
  box, // Container
  pallet, // Shipping unit
  custom // Custom unit (will be handled separately)
}

enum InstallmentStatus {
  pending,
  paid,
  overdue,
  completed,
}

enum NotificationType {
  installment,
  alertStock,
  company,
  unknown,
}

extension NotificationTypeExtension on String {
  NotificationType toNotificationType() {
    switch (this) {
      case 'installment':
        return NotificationType.installment;
      case 'alertStock':
        return NotificationType.alertStock;
      default:
        return NotificationType.unknown;
    }
  }
}
