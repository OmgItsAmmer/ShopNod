import 'package:ecommerce_dashboard/utils/constants/colors.dart';
import 'package:ecommerce_dashboard/utils/constants/sizes.dart';
import 'package:flutter/material.dart';
import 'package:iconsax/iconsax.dart';

/// Collapsible section for optional entity fields (POS: keep main form compact).
class OptionalFieldsExpansion extends StatefulWidget {
  const OptionalFieldsExpansion({
    super.key,
    required this.children,
    this.initiallyExpanded = false,
  });

  final List<Widget> children;
  final bool initiallyExpanded;

  @override
  State<OptionalFieldsExpansion> createState() =>
      _OptionalFieldsExpansionState();
}

class _OptionalFieldsExpansionState extends State<OptionalFieldsExpansion> {
  late bool _expanded;

  @override
  void initState() {
    super.initState();
    _expanded = widget.initiallyExpanded;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          height: 36,
          child: OutlinedButton.icon(
            onPressed: () => setState(() => _expanded = !_expanded),
            icon: Icon(
              _expanded ? Iconsax.arrow_up_2 : Iconsax.arrow_down_1,
              size: 16,
            ),
            label: Text(
              _expanded
                  ? 'Hide Additional Fields / اضافی فیلڈز چھپائیں'
                  : 'Additional Fields (Optional) / اضافی فیلڈز',
              style: Theme.of(context).textTheme.labelMedium,
            ),
            style: OutlinedButton.styleFrom(
              foregroundColor: TColors.primary,
              side: const BorderSide(color: TColors.borderPrimary),
              padding: const EdgeInsets.symmetric(horizontal: TSizes.sm),
            ),
          ),
        ),
        if (_expanded) ...[
          const SizedBox(height: TSizes.sm),
          ...widget.children,
        ],
      ],
    );
  }
}
