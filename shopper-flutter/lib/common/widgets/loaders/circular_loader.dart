import 'package:flutter/material.dart';

import '../../../utils/constants/colors.dart';
import '../../../utils/constants/sizes.dart';

/// A spinner on a round coloured background.
class TCircularLoader extends StatelessWidget {
  const TCircularLoader({
    super.key,
    this.foregroundColor = TColors.white,
    this.backgroundColor = TColors.primary,
  });

  final Color foregroundColor;
  final Color backgroundColor;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(TSizes.lg),
    decoration: BoxDecoration(color: backgroundColor, shape: BoxShape.circle),
    child: CircularProgressIndicator(color: foregroundColor),
  );
}
