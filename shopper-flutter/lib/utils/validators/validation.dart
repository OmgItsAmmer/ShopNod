/// VALIDATION CLASS
class TValidator {
  /// Empty Text Validation
  static String? validateEmptyText(String? fieldName, String? value) {
    if (value == null || value.isEmpty) {
      return '$fieldName is required.';
    }

    return null;
  }

  /// Username Validation
  static String? validateUsername(String? username) {
    if (username == null || username.isEmpty) {
      return 'Username is required.';
    }

    // Define a regular expression pattern for the username.
    const pattern = r"^[a-zA-Z0-9_-]{3,20}$";

    // Create a RegExp instance from the pattern.
    final regex = RegExp(pattern);

    // Use the hasMatch method to check if the username matches the pattern.
    bool isValid = regex.hasMatch(username);

    // Check if the username doesn't start or end with an underscore or hyphen.
    if (isValid) {
      isValid =
          !username.startsWith('_') &&
          !username.startsWith('-') &&
          !username.endsWith('_') &&
          !username.endsWith('-');
    }

    if (!isValid) {
      return 'Username is not valid.';
    }

    return null;
  }

  /// Email Validation
  static String? validateEmail(String? value) {
    final trimmed = value?.trim();
    if (trimmed == null || trimmed.isEmpty) {
      return 'Email is required.';
    }

    // Standard RFC-compliant email validation regex
    final emailRegExp = RegExp(
      r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    );

    if (!emailRegExp.hasMatch(trimmed)) {
      return 'Invalid email address.';
    }

    return null;
  }

  /// Password Validation
  static String? validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Password is required.';
    }

    // Check for minimum password length
    if (value.length < 6) {
      return 'Password must be at least 6 characters long.';
    }

    // Check for uppercase letters
    if (!value.contains(RegExp(r'[A-Z]'))) {
      return 'Password must contain at least one uppercase letter.';
    }

    // Check for numbers
    if (!value.contains(RegExp(r'[0-9]'))) {
      return 'Password must contain at least one number.';
    }

    // Check for special characters
    if (!value.contains(RegExp(r'[!@#$%^&*(),.?":{}|<>]'))) {
      return 'Password must contain at least one special character.';
    }

    return null;
  }

  /// Normalizes user input to Pakistani mobile format (03XXXXXXXXX) or empty.
  static String normalizePhoneNumber(String value) {
    final digits = value.replaceAll(RegExp(r'\D'), '');
    if (digits.isEmpty) return '';
    if (digits.length == 10 && digits.startsWith('3')) {
      return '0$digits';
    }
    return digits;
  }

  /// Phone Number Validation (Pakistani mobile: 03XXXXXXXXX)
  static String? validatePhoneNumber(String? value) {
    return _validatePkPhone(value, required: true);
  }

  /// Optional phone — empty is allowed; non-empty must be valid PK mobile.
  static String? validateOptionalPhoneNumber(String? value) {
    return _validatePkPhone(value, required: false);
  }

  static String? _validatePkPhone(String? value, {required bool required}) {
    if (value == null || value.trim().isEmpty) {
      return required ? 'Phone number is required.' : null;
    }

    final normalized = normalizePhoneNumber(value);
    final phoneRegExp = RegExp(r'^03[0-9]{9}$');

    if (!phoneRegExp.hasMatch(normalized)) {
      return 'Enter a valid Pakistani mobile number (03XXXXXXXXX).';
    }

    return null;
  }

  // Add more custom validators as needed for your specific requirements.
}
