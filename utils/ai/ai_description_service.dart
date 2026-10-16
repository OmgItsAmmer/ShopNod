import 'package:flutter/foundation.dart';

import '../../services/backend/backend_api_service.dart';

/// AI product descriptions.
///
/// H-2: this used to call the model provider directly with an API key taken
/// from the bundled `.env` and pasted into the request — so the key shipped
/// inside every APK, and anyone who unzipped one could spend the owner's quota
/// (or get it rate-limited, breaking the feature for real shopkeepers).
///
/// The key now lives only in the backend's environment. The app asks the
/// backend, which calls OpenAI on its behalf — so swapping model or provider is
/// a server-side change that needs no app release.
class AiDescriptionService {
  static final _api = BackendApiService.instance;

  /// Generates a product description for a Pakistani karyana (grocery) product.
  ///
  /// [productName] - The name of the product.
  /// Returns the generated description, or throws with a message safe to show.
  static Future<String> generateProductDescription(String productName) async {
    final trimmed = productName.trim();
    if (trimmed.isEmpty) {
      throw Exception('Please enter a product name first.');
    }

    if (kDebugMode) {
      debugPrint('[AiDescriptionService] Requesting description for "$trimmed" via backend');
    }

    final result = await _api.post(
      '/api/v1/products/ai/description',
      {'productName': trimmed},
    );

    if (!result.isSuccess) {
      final message = result.errorMessage ?? 'Could not generate a description.';
      if (kDebugMode) {
        debugPrint('[AiDescriptionService] Backend returned ${result.errorCode}: $message');
      }
      throw Exception(message);
    }

    final data = result.data;
    final description =
        data is Map<String, dynamic> ? data['description'] as String? : null;

    if (description == null || description.trim().isEmpty) {
      throw Exception('The AI did not return a description. Please try again.');
    }

    return description.trim();
  }
}
