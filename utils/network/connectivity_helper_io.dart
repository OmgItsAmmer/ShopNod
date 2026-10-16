import 'dart:async';
import 'dart:io';
import 'package:http/http.dart' as http;

/// Native (dart:io) implementation of the internet / backend reachability check.
///
/// If [backendUrl] is provided, probes the backend health endpoint.
/// Otherwise, performs a real DNS lookup for `google.com`.
Future<bool> hasActualInternet([String? backendUrl]) async {
  if (backendUrl != null && backendUrl.isNotEmpty) {
    try {
      final uri = Uri.parse('$backendUrl/api/v1/health');
      final response = await http.get(uri).timeout(const Duration(seconds: 2));
      return response.statusCode < 500;
    } catch (_) {
      return false;
    }
  }

  try {
    final result = await InternetAddress.lookup('google.com');
    return result.isNotEmpty && result[0].rawAddress.isNotEmpty;
  } catch (_) {
    return false;
  }
}

