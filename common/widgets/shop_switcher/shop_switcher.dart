import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:iconsax/iconsax.dart';

import '../../../Models/team/shop_membership_model.dart';
import '../../../common/widgets/loaders/tloaders.dart';
import '../../../repositories/authentication/authicatioon_repository.dart';
import '../../../utils/constants/colors.dart';
import '../../../utils/constants/sizes.dart';

/// Dashboard header dropdown that lets a user with multiple shop memberships
/// switch the currently-active shop. Renders nothing when the user only
/// belongs to one shop — there's no decision to make in that case.
class ShopSwitcher extends StatelessWidget {
  const ShopSwitcher({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = AuthenticationRepository.instance;

    return Obx(() {
      // Re-read off `currentUser` reactively.
      final user = auth.currentUser.value;
      if (user == null) return const SizedBox.shrink();

      final memberships = auth.memberships
          .map((m) => ShopMembership.fromJson(m))
          .where((m) => m.isActive)
          .toList();
      if (memberships.length <= 1) return const SizedBox.shrink();

      final activeShopId = auth.activeShopId;
      final active = memberships.firstWhereOrNull((m) => m.shopId == activeShopId);
      final label = active?.shopName ?? 'Select shop';

      return PopupMenuButton<int>(
        position: PopupMenuPosition.under,
        tooltip: 'Switch shop',
        onSelected: (shopId) async {
          if (shopId == activeShopId) return;
          try {
            await auth.switchShop(shopId);
            TLoaders.successSnackBar(
              title: 'Switched shop',
              message: memberships.firstWhere((m) => m.shopId == shopId).shopName,
            );
          } catch (e) {
            TLoaders.errorSnackBar(
              title: 'Could not switch shop',
              message: e.toString().replaceFirst('Exception: ', ''),
            );
          }
        },
        itemBuilder: (context) => memberships
            .map(
              (m) => PopupMenuItem<int>(
                value: m.shopId,
                child: _ShopRow(membership: m, isActive: m.shopId == activeShopId),
              ),
            )
            .toList(),
        child: _SwitcherChip(label: label),
      );
    });
  }
}

class _SwitcherChip extends StatelessWidget {
  final String label;
  const _SwitcherChip({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: TColors.lightGrey,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: TColors.borderPrimary),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Iconsax.shop, size: 16, color: TColors.primary),
          const SizedBox(width: 6),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 200),
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 13,
              ),
            ),
          ),
          const SizedBox(width: 4),
          const Icon(Iconsax.arrow_down_1, size: 14, color: TColors.grey),
        ],
      ),
    );
  }
}

class _ShopRow extends StatelessWidget {
  final ShopMembership membership;
  final bool isActive;
  const _ShopRow({required this.membership, required this.isActive});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(
          isActive ? Iconsax.tick_circle : Iconsax.shop,
          size: 16,
          color: isActive ? TColors.primary : TColors.grey,
        ),
        const SizedBox(width: TSizes.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                membership.shopName,
                style: TextStyle(
                  fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
                ),
              ),
              Text(
                membership.role,
                style: const TextStyle(fontSize: 11, color: TColors.grey),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
