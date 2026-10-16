import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:iconsax/iconsax.dart';

import '../../../../controllers/shop/shop_controller.dart';
import '../../../../utils/constants/colors.dart';
import '../../../../utils/constants/sizes.dart';
import '../../../../utils/device/device_utility.dart';
import '../../../../utils/helpers/helper_functions.dart';

/// Full-width header bar shown when the shop credit balance is below threshold.
class LowCreditsBanner extends StatelessWidget {
  const LowCreditsBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final shopController = ShopController.instance;
    final isDark = THelperFunctions.isDarkMode(context);
    final isMobile = TDeviceUtils.isMobileScreen(context);

    return Obx(() {
      if (!shopController.isCreditsLow) {
        return const SizedBox(height: 22);
      }

      final bgColor = TColors.error.withValues(alpha: isDark ? 0.18 : 0.08);
      final borderColor = TColors.error.withValues(alpha: isDark ? 0.45 : 0.3);

      return Container(
        height: 22,
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: TSizes.md),
        decoration: BoxDecoration(
          color: bgColor,
          border: Border(
            bottom: BorderSide(color: borderColor, width: 1),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Iconsax.warning_2, color: TColors.error, size: 14),
            const SizedBox(width: TSizes.xs),
            Text(
              isMobile ? 'Credits are low' : 'Credits are low · کریڈٹ کم ہیں',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: TColors.error,
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ],
        ),
      );
    });
  }
}
