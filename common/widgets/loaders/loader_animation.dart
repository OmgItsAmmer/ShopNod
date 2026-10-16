import 'package:flutter/material.dart';

import 'dukaandar_loader.dart';

/// A circular loader widget with customizable foreground and background colors.
class TLoaderAnimation extends StatelessWidget {
  const TLoaderAnimation({
    super.key,
  });

  @override
  Widget build(BuildContext context) {
    return const Center(child: TDukaandarLoader(size: 200));
  }
}
