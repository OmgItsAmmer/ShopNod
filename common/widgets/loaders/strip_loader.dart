import 'package:flutter/material.dart';

import '../shimmers/shimmer.dart';

/// Small inline placeholder used where a full loader would be too large
/// (e.g. a figure still loading inside a dashboard card).
class TStripLoader extends StatelessWidget {
  const TStripLoader({super.key, this.height = 20, this.width = 100});

  final double height;
  final double width;

  @override
  Widget build(BuildContext context) {
    return TShimmerEffect(width: width, height: height, radius: height / 2);
  }
}
