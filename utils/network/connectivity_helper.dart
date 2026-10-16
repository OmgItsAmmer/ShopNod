/// Conditional export: platform-correct internet connectivity check.
///
/// - Web (`dart.library.html`): HTTP probe via [ConnectivityHelperWeb]
/// - Native (`dart.library.io`): DNS lookup via [ConnectivityHelperIo]
///
/// Both exports expose a single top-level function:
/// ```dart
/// Future<bool> hasActualInternet([String? backendUrl]);
/// ```
export 'connectivity_helper_web.dart'
    if (dart.library.io) 'connectivity_helper_io.dart';
