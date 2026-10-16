import 'package:flutter/material.dart';

import '../../../utils/constants/colors.dart';
import '../../../utils/helpers/helper_functions.dart';
import '../containers/circular_container.dart';

/// A customized choice chip that can act like a radio button.
class TChoiceChip extends StatelessWidget {
  /// Create a chip that acts like a radio button.
  ///
  /// Parameters:
  ///   - text: The label text for the chip.
  ///   - selected: Whether the chip is currently selected.
  ///   - onSelected: Callback function when the chip is selected.
  const TChoiceChip({
    super.key,
    required this.text,
    required this.selected,
    this.onSelected,
  });

  final String text;
  final bool selected;
  final void Function(bool)? onSelected;

  @override
  Widget build(BuildContext context) {
    final avatarColor = THelperFunctions.getColor(text);
    final usePlainChip = avatarColor == null;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    // Unselected chips follow the theme: a dark surface in dark mode, the light grey in light mode.
    final plainBackground = isDark
        ? TColors.darkerGrey.withValues(alpha: 0.35)
        : TColors.lightGrey;
    final plainUnselectedText = isDark
        ? TColors.light.withValues(alpha: 0.85)
        : TColors.darkGrey;

    return Theme(
      data: Theme.of(context).copyWith(canvasColor: Colors.transparent),
      child: ChoiceChip(
        avatar: avatarColor != null
            ? TCircularContainer(
                width: 50,
                height: 50,
                backgroundColor: avatarColor,
              )
            : null,
        selected: selected,
        onSelected: onSelected,
        selectedColor: usePlainChip ? TColors.primary : avatarColor,
        backgroundColor: usePlainChip ? plainBackground : avatarColor,
        side: usePlainChip
            ? BorderSide(
                color: selected
                    ? TColors.primary
                    : TColors.grey.withValues(alpha: 0.4),
              )
            : null,
        labelStyle: TextStyle(
          color: usePlainChip
              ? (selected ? TColors.white : plainUnselectedText)
              : (selected ? TColors.white : null),
          fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
        ),
        shape: avatarColor != null ? const CircleBorder() : null,
        label: avatarColor != null ? const SizedBox() : Text(text),
        padding: avatarColor != null ? const EdgeInsets.all(0) : null,
        labelPadding: avatarColor != null ? const EdgeInsets.all(0) : null,
      ),
    );
  }
}
