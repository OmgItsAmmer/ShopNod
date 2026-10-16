import 'package:ecommerce_dashboard/utils/scroll/inertial_scroll_physics.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

/// Global scroll: inertial physics on every platform (web, desktop, mobile).
class AppScrollBehavior extends MaterialScrollBehavior {
  const AppScrollBehavior();

  /// Deliberately excludes [PointerDeviceKind.mouse] (ISSUES.md).
  ///
  /// This is a desktop-first, mouse-driven app. With mouse included here, a
  /// click-and-drag anywhere over scrollable content — which is nearly
  /// everywhere, since most screens sit inside a scroll view — started a pan
  /// gesture with the bouncy inertial physics below and always won the
  /// gesture arena over text selection, so click-drag could never select
  /// text; it just shoved the page around. Mouse users still scroll fine via
  /// the scroll wheel, trackpad, or scrollbar thumb, none of which go through
  /// `dragDevices`. Touch and stylus keep drag-to-scroll since there is no
  /// competing selection gesture to lose to on those devices.
  @override
  Set<PointerDeviceKind> get dragDevices => {
        PointerDeviceKind.touch,
        PointerDeviceKind.stylus,
        PointerDeviceKind.trackpad,
      };

  @override
  ScrollPhysics getScrollPhysics(BuildContext context) => inertialScrollPhysics;

  @override
  GestureVelocityTrackerBuilder velocityTrackerBuilder(BuildContext context) {
    switch (Theme.of(context).platform) {
      case TargetPlatform.iOS:
        return (PointerEvent event) =>
            IOSScrollViewFlingVelocityTracker(event.kind);
      case TargetPlatform.macOS:
        return (PointerEvent event) =>
            MacOSScrollViewFlingVelocityTracker(event.kind);
      case TargetPlatform.android:
      case TargetPlatform.fuchsia:
      case TargetPlatform.linux:
      case TargetPlatform.windows:
        return (PointerEvent event) =>
            IOSScrollViewFlingVelocityTracker(event.kind);
    }
  }
}
