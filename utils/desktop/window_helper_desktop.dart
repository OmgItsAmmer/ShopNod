import 'package:window_manager/window_manager.dart';

class WindowHelper {
  static Future<void> ensureInitialized() async {
    await windowManager.ensureInitialized();
  }

  static Future<bool> isFullScreen() async {
    return await windowManager.isFullScreen();
  }

  static Future<void> setFullScreen(bool value) async {
    await windowManager.setFullScreen(value);
  }
}
