import 'package:flutter/material.dart';
import 'package:iconsax/iconsax.dart';

import '../../../utils/constants/colors.dart';
import '../../../utils/helpers/helper_functions.dart';

/// Reusable, theme-adaptive default avatar displaying a circle head with semi-circle body icon.
class TDefaultAvatar extends StatelessWidget {
  const TDefaultAvatar({
    super.key,
    this.size = 56.0,
    this.iconSize,
    this.backgroundColor,
    this.iconColor,
  });

  final double size;
  final double? iconSize;
  final Color? backgroundColor;
  final Color? iconColor;

  @override
  Widget build(BuildContext context) {
    final isDark = THelperFunctions.isDarkMode(context);
    final effectiveBgColor = backgroundColor ??
        (isDark ? TColors.darkContainer : TColors.grey.withValues(alpha: 0.35));
    final effectiveIconColor = iconColor ??
        (isDark ? TColors.white : TColors.darkerGrey);
    final effectiveIconSize = iconSize ?? (size * 0.55);

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: effectiveBgColor,
        shape: BoxShape.circle,
        border: Border.all(
          color: isDark ? TColors.borderSecondary : TColors.borderPrimary,
          width: 1,
        ),
      ),
      child: Center(
        child: Icon(
          Iconsax.user, // Circle head with semi-circle body
          size: effectiveIconSize,
          color: effectiveIconColor,
        ),
      ),
    );
  }
}
