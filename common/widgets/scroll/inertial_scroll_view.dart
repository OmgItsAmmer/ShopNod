import 'package:ecommerce_dashboard/utils/scroll/inertial_scroll_controller.dart';
import 'package:ecommerce_dashboard/utils/scroll/inertial_scroll_physics.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

/// Drop-in replacement for [SingleChildScrollView] with real inertial scrolling.
class InertialScrollView extends StatefulWidget {
  const InertialScrollView({
    super.key,
    required this.child,
    this.scrollDirection = Axis.vertical,
    this.padding,
    this.controller,
    this.primary,
    this.clipBehavior = Clip.hardEdge,
    this.reverse = false,
    this.restorationId,
    this.keyboardDismissBehavior = ScrollViewKeyboardDismissBehavior.manual,
    this.dragStartBehavior = DragStartBehavior.start,
  });

  final Widget child;
  final Axis scrollDirection;
  final EdgeInsetsGeometry? padding;
  final ScrollController? controller;
  final bool? primary;
  final Clip clipBehavior;
  final bool reverse;
  final String? restorationId;
  final ScrollViewKeyboardDismissBehavior keyboardDismissBehavior;
  final DragStartBehavior dragStartBehavior;

  @override
  State<InertialScrollView> createState() => _InertialScrollViewState();
}

class _InertialScrollViewState extends State<InertialScrollView> {
  ScrollController? _ownedController;

  ScrollController get _controller => widget.controller ?? _ownedController!;

  @override
  void initState() {
    super.initState();
    if (widget.controller == null) {
      _ownedController = InertialScrollController();
    }
  }

  @override
  void dispose() {
    _ownedController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      controller: _controller,
      scrollDirection: widget.scrollDirection,
      primary: widget.primary,
      padding: widget.padding,
      clipBehavior: widget.clipBehavior,
      reverse: widget.reverse,
      restorationId: widget.restorationId,
      keyboardDismissBehavior: widget.keyboardDismissBehavior,
      dragStartBehavior: widget.dragStartBehavior,
      physics: inertialScrollPhysics,
      child: widget.child,
    );
  }
}
