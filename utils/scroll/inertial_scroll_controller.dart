import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';

/// Scroll position with per-tick inertial coast (wheel/trackpad), direction-safe.
class InertialScrollPosition extends ScrollPositionWithSingleContext {
  InertialScrollPosition({
    required super.physics,
    required super.context,
    super.initialPixels = 0.0,
    super.keepScrollOffset = true,
    super.oldPosition,
    super.debugLabel,
  });

  /// Logical px/s imparted per wheel tick (same sign as [delta]).
  static const double _wheelVelocityScale = 6.0;

  /// Maximum coast velocity from wheel input for smooth, controlled scrolling.
  static const double _maxWheelVelocity = 800.0;

  @override
  void pointerScroll(double delta) {
    if (delta == 0.0) {
      goBallistic(0.0);
      return;
    }

    final double min = minScrollExtent;
    final double max = maxScrollExtent;

    // Stop outward momentum if already at or beyond edge
    final bool isAtOrPastMin = pixels <= min;
    final bool isAtOrPastMax = pixels >= max;
    final bool scrollingOutward =
        (isAtOrPastMin && delta < 0.0) || (isAtOrPastMax && delta > 0.0);

    if (scrollingOutward) {
      final double clampedBoundary = delta < 0.0 ? min : max;
      if (pixels != clampedBoundary) {
        forcePixels(clampedBoundary);
      }
      goBallistic(0.0);
      return;
    }

    final double targetPixels = math.min(
      math.max(pixels + delta, min),
      max,
    );

    if (targetPixels == pixels) {
      goBallistic(0.0);
      return;
    }

    goIdle();
    updateUserScrollDirection(
      -delta > 0.0 ? ScrollDirection.forward : ScrollDirection.reverse,
    );
    isScrollingNotifier.value = true;
    final double oldPixels = pixels;
    forcePixels(targetPixels);
    didStartScroll();
    didUpdateScrollPositionBy(pixels - oldPixels);
    didEndScroll();

    // Do not launch outward velocity when reaching boundary
    final bool reachedBoundary =
        (targetPixels == min && delta < 0.0) || (targetPixels == max && delta > 0.0);
    if (reachedBoundary) {
      goBallistic(0.0);
    } else {
      // Coast with controlled velocity scale (no cross-direction momentum).
      final double rawVelocity = delta * _wheelVelocityScale;
      final double clampedVelocity =
          rawVelocity.clamp(-_maxWheelVelocity, _maxWheelVelocity);
      goBallistic(clampedVelocity);
    }
  }
}

/// Scroll controller used by [InertialScrollView] for wheel inertia.
class InertialScrollController extends ScrollController {
  InertialScrollController({
    super.initialScrollOffset,
    super.keepScrollOffset,
    super.debugLabel,
    super.onAttach,
    super.onDetach,
  });

  @override
  ScrollPosition createScrollPosition(
    ScrollPhysics physics,
    ScrollContext context,
    ScrollPosition? oldPosition,
  ) {
    return InertialScrollPosition(
      physics: physics,
      context: context,
      initialPixels: initialScrollOffset,
      keepScrollOffset: keepScrollOffset,
      oldPosition: oldPosition,
      debugLabel: debugLabel,
    );
  }
}
