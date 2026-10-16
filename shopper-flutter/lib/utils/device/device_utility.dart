import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../constants/sizes.dart';

/// Device helpers. No `dart:io`, so everything here also works in the web build.
class TDeviceUtils {
  static void hideKeyboard(BuildContext context) =>
      FocusScope.of(context).unfocus();

  static Future<void> setStatusBarColor(Color color) async {
    SystemChrome.setSystemUIOverlayStyle(
      SystemUiOverlayStyle(statusBarColor: color),
    );
  }

  static bool isLandscapeOrientation(BuildContext context) =>
      MediaQuery.orientationOf(context) == Orientation.landscape;

  static bool isPortraitOrientation(BuildContext context) =>
      MediaQuery.orientationOf(context) == Orientation.portrait;

  static void setFullScreen(bool enable) {
    SystemChrome.setEnabledSystemUIMode(
      enable ? SystemUiMode.immersiveSticky : SystemUiMode.edgeToEdge,
    );
  }

  static double getScreenHeight(BuildContext context) =>
      MediaQuery.sizeOf(context).height;

  static double getScreenWidth(BuildContext context) =>
      MediaQuery.sizeOf(context).width;

  static double getPixelRatio(BuildContext context) =>
      MediaQuery.devicePixelRatioOf(context);

  static double getStatusBarHeight(BuildContext context) =>
      MediaQuery.paddingOf(context).top;

  static double getBottomNavigationBarHeight() => kBottomNavigationBarHeight;

  static double getAppBarHeight() => kToolbarHeight;

  static double getKeyboardHeight(BuildContext context) =>
      MediaQuery.viewInsetsOf(context).bottom;

  static bool isKeyboardVisible(BuildContext context) =>
      MediaQuery.viewInsetsOf(context).bottom > 0;

  static bool isPhysicalDevice() =>
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.android ||
          defaultTargetPlatform == TargetPlatform.iOS);

  static void vibrate(Duration duration) {
    HapticFeedback.vibrate();
    Future.delayed(duration, HapticFeedback.vibrate);
  }

  static Future<void> setPreferredOrientations(
    List<DeviceOrientation> orientations,
  ) => SystemChrome.setPreferredOrientations(orientations);

  static void hideStatusBar() =>
      SystemChrome.setEnabledSystemUIMode(SystemUiMode.manual, overlays: []);

  static void showStatusBar() => SystemChrome.setEnabledSystemUIMode(
    SystemUiMode.manual,
    overlays: SystemUiOverlay.values,
  );

  static bool isIOS() => !kIsWeb && defaultTargetPlatform == TargetPlatform.iOS;

  static bool isAndroid() =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  static bool isDesktopScreen(BuildContext context) =>
      getScreenWidth(context) >= TSizes.desktopScreenSize;

  static bool isTabletScreen(BuildContext context) {
    final width = getScreenWidth(context);
    return width >= TSizes.tabletScreenSize && width < TSizes.desktopScreenSize;
  }

  static bool isMobileScreen(BuildContext context) =>
      getScreenWidth(context) < TSizes.tabletScreenSize;
}
