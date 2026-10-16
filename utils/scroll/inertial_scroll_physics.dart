import 'package:flutter/material.dart';

/// Strong inertial glide after drag release or wheel input (all platforms).
class InertialScrollPhysics extends BouncingScrollPhysics {
  const InertialScrollPhysics({super.parent})
      : super(decelerationRate: ScrollDecelerationRate.fast);

  @override
  InertialScrollPhysics applyTo(ScrollPhysics? ancestor) {
    return InertialScrollPhysics(parent: buildParent(ancestor));
  }

  @override
  double get minFlingVelocity => 25.0;

  @override
  double get dragStartDistanceMotionThreshold => 2.0;

  @override
  Simulation? createBallisticSimulation(
    ScrollMetrics position,
    double velocity,
  ) {
    final Tolerance tolerance = toleranceFor(position);

    // Stop overscroll bounce when velocity is pushing outward at or past boundary
    if (position.pixels <= position.minScrollExtent && velocity <= 0.0) {
      return null;
    }
    if (position.pixels >= position.maxScrollExtent && velocity >= 0.0) {
      return null;
    }

    if (velocity.abs() < tolerance.velocity && !position.outOfRange) {
      return null;
    }

    return BouncingScrollSimulation(
      spring: SpringDescription.withDampingRatio(
        mass: 0.35,
        stiffness: 75.0,
        ratio: 1.15,
      ),
      position: position.pixels,
      velocity: velocity,
      leadingExtent: position.minScrollExtent,
      trailingExtent: position.maxScrollExtent,
      tolerance: tolerance,
      constantDeceleration: 1800,
    );
  }
}

ScrollPhysics get inertialScrollPhysics => const InertialScrollPhysics(
      parent: AlwaysScrollableScrollPhysics(),
    );
