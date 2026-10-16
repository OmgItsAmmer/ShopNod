import 'package:ecommerce_dashboard/common/widgets/layout/sidebar/controller/sidebar_controller.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../../../../bindings/shell_scope.dart';
import '../../../../../controllers/onboarding/guided_tour_controller.dart';
import '../../../../../utils/constants/colors.dart';
import '../../../../../utils/constants/sizes.dart';
import '../../../../../utils/helpers/helper_functions.dart';

class TMenuItem extends StatelessWidget {
  const TMenuItem({
    Key? key,
    this.route = '',
    required this.itemName,
    required this.icon,
    this.targetKey,
  }) : super(key: key ?? targetKey);

  final String route;
  final String itemName;
  final IconData icon;
  final Key? targetKey;

  String _getTranslationKey(String name) {
    switch (name.replaceAll(' ', '').toLowerCase()) {
      case 'dashboard':
        return 'dashboard';
      case 'sale':
        return 'sale';
      case 'purchase':
        return 'purchase';
      case 'orders':
        return 'orders';
      case 'purchases':
        return 'purchases';
      case 'accountbook':
        return 'accountBook';
      case 'expenses':
        return 'expenses';
      case 'customers':
        return 'customers';
      case 'vendors':
        return 'vendors';
      case 'salesman':
        return 'salesman';
      case 'products':
        return 'products';
      case 'brands':
        return 'brands';
      case 'categories':
        return 'categories';
      case 'collections':
        return 'collections';
      case 'media':
        return 'media';
      case 'reports':
        return 'reports';
      case 'profile':
        return 'profile';
      case 'store':
        return 'store';
      default:
        return name;
    }
  }

  @override
  Widget build(BuildContext context) {
    // Shell-scoped: a plain Get.put fallback would register a route-scoped
    // instance that the next navigation deletes (see [shellScoped]).
    final menuController = shellScoped(SideBarController.new);
    final tourCtrl = shellScoped(GuidedTourController.new);
    final isDark = THelperFunctions.isDarkMode(context);
    final inactiveColor = isDark ? TColors.darkGrey : TColors.darkerGrey;

    return Obx(
      () {
        final isEnabled = tourCtrl.isSidebarItemEnabled(route);
        final isHighlighted = (menuController.isHovering(route) || menuController.isActive(route)) && isEnabled;
        final iconColor = isHighlighted ? TColors.white : inactiveColor;
        final textColor = isHighlighted ? TColors.white : inactiveColor;

        return IgnorePointer(
          ignoring: !isEnabled,
          child: Opacity(
            opacity: isEnabled ? 1.0 : 0.4,
            child: InkWell(
              onTap: isEnabled ? () => menuController.menuOnTap(route) : null,
              onHover: isEnabled
                  ? (hovering) => hovering
                      ? menuController.changeHoverItem(route)
                      : menuController.changeHoverItem('')
                  : null,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 1),
                child: Container(
                  height: TSizes.sidebarItemHeight,
                  decoration: BoxDecoration(
                    color: isHighlighted ? TColors.primary : TColors.transparent,
                    borderRadius: BorderRadius.circular(TSizes.borderRadiusSm),
                  ),
                  child: Row(
                    children: [
                      Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: TSizes.sm,
                        ),
                        child: Icon(
                          icon,
                          size: TSizes.iconSm,
                          color: iconColor,
                        ),
                      ),
                      Expanded(
                        child: Text(
                          _getTranslationKey(itemName).tr,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: textColor,
                                fontSize: TSizes.fontSizeSm,
                              ),
                          overflow: TextOverflow.ellipsis,
                          maxLines: 1,
                        ),
                      ),
                      const SizedBox(width: TSizes.xs),
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
