import 'package:http/http.dart' as http;

/// Web implementation of the internet reachability check.
///
/// DNS lookup is not available on the web (no `dart:io`), so we fall back to
/// an HTTP probe against the app backend. A non-5xx response indicates the
/// network is reachable even if the status is 404 / 401 / 405.
///
/// [backendUrl] should be the base URL of the backend, e.g.
/// `https://api.example.com`. If `null` the function returns `true`
/// optimistically (browser's own network stack handles offline detection).
Future<bool> hasActualInternet([String? backendUrl]) async {
  if (backendUrl == null) return true;
  try {
    final response = await http
        .get(Uri.parse('$backendUrl/api/v1/health'))
        .timeout(const Duration(seconds: 3));
    return response.statusCode < 500;
  } catch (_) {
    return false;
  }
}
