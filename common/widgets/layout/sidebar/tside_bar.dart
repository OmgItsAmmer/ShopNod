import 'package:ecommerce_dashboard/repositories/authentication/authicatioon_repository.dart';
import 'package:ecommerce_dashboard/common/widgets/images/t_circular_image.dart';
import 'package:ecommerce_dashboard/common/widgets/loaders/strip_loader.dart';
import 'package:ecommerce_dashboard/common/widgets/shimmers/shimmer.dart';
import 'package:ecommerce_dashboard/routes/routes.dart';
import 'package:ecommerce_dashboard/utils/constants/colors.dart';
// ignore: unused_import
import 'package:ecommerce_dashboard/utils/constants/image_strings.dart';
import 'package:ecommerce_dashboard/utils/constants/sizes.dart';
import 'package:ecommerce_dashboard/utils/helpers/helper_functions.dart';
import 'package:flutter/material.dart';
import 'package:ecommerce_dashboard/common/widgets/scroll/inertial_scroll_view.dart';

import 'package:get/get.dart';
import 'package:iconsax/iconsax.dart';

import '../../../../bindings/shell_scope.dart';
import '../../../../controllers/media/media_controller.dart';
import '../../../../controllers/shop/shop_controller.dart';
import '../../../../controllers/user/user_controller.dart';
import '../../../../utils/constants/enums.dart';
import '../../images/t_default_avatar.dart';
import '../../images/t_rounded_image.dart';
import 'menu/menu_item.dart';
import '../../../../controllers/onboarding/guided_tour_controller.dart';
import '../../../../utils/device/device_utility.dart';
import 'controller/sidebar_controller.dart';

class TSideBar extends StatelessWidget {
  final bool assignTourKeys;
  const TSideBar({super.key, this.assignTourKeys = true});

  static const double _logoSize = TSizes.sidebarLogoSize;

  @override
  Widget build(BuildContext context) {
    // Shell-scoped — see [shellScoped]. A plain `Get.put` here handed the
    // sidebar a route-scoped instance that the next navigation deleted.
    final shopController = shellScoped(ShopController.new);
    final mediaController = shellScoped(MediaController.new);
    final isDark = THelperFunctions.isDarkMode(context);
    final bgColor = isDark ? TColors.dark : TColors.white;
    final borderColor = isDark ? TColors.borderSecondary : TColors.grey;
    final sectionStyle = Theme.of(context).textTheme.labelSmall?.copyWith(
          letterSpacing: 1.0,
          color: isDark ? TColors.darkGrey : TColors.textSecondary,
          fontSize: 10,
        );

    return Drawer(
      width: TSizes.sidebarWidth,
      shape: const BeveledRectangleBorder(),
      backgroundColor: bgColor,
      child: Container(
        decoration: BoxDecoration(
          color: bgColor,
          border: Border(right: BorderSide(color: borderColor, width: 1)),
        ),
        child: InertialScrollView(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.only(top: TSizes.xs, right: TSizes.xs),
                child: Align(
                  alignment: Alignment.topRight,
                  child: IconButton(
                    icon: Icon(
                      Iconsax.arrow_left_2,
                      size: 18,
                      color: isDark ? TColors.lightGrey : TColors.darkGrey,
                    ),
                    tooltip: 'Close Sidebar',
                    onPressed: () {
                      if (Get.isRegistered<SideBarController>()) {
                        final ctrl = SideBarController.instance;
                        if (TDeviceUtils.isDesktopScreen(context)) {
                          ctrl.toggleSidebarCollapse();
                        } else {
                          ctrl.closeDrawerIfOpen();
                        }
                      }
                    },
                  ),
                ),
              ),
              Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Obx(() {
                    final image = mediaController.displayImage.value;

                    if (image != null &&
                        mediaController.displayImageOwner.value ==
                            MediaCategory.shop.toString().split('.').last) {
                      return FutureBuilder<String?>(
                        future: mediaController.getImageFromBucket(
                          MediaCategory.shop.toString().split('.').last,
                          image.filename ?? '',
                        ),
                        builder: (context, snapshot) {
                          if (snapshot.connectionState ==
                              ConnectionState.waiting) {
                            return const TShimmerEffect(
                              width: _logoSize,
                              height: _logoSize,
                            );
                          } else if (snapshot.hasError ||
                              snapshot.data == null) {
                            return const TDefaultAvatar(size: _logoSize);
                          } else {
                            return TRoundedImage(
                              isNetworkImage: true,
                              width: _logoSize,
                              height: _logoSize,
                              imageurl: snapshot.data!,
                            );
                          }
                        },
                      );
                    }

                    return Obx(() {
                      if (mediaController.cachedSidebarImage.value != null) {
                        return TRoundedImage(
                          isNetworkImage: true,
                          width: _logoSize,
                          height: _logoSize,
                          imageurl: mediaController.cachedSidebarImage.value!,
                        );
                      }

                      return FutureBuilder<String?>(
                        future: mediaController.fetchAndCacheSidebarImage(
                          shopController.selectedShop.value.shopId,
                          MediaCategory.shop.toString().split('.').last,
                        ),
                        builder: (context, snapshot) {
                          if (snapshot.connectionState ==
                              ConnectionState.waiting) {
                            return const TShimmerEffect(
                              width: _logoSize,
                              height: _logoSize,
                            );
                          } else if (snapshot.hasError ||
                              snapshot.data == null) {
                            return const TDefaultAvatar(size: _logoSize);
                          } else {
                            return TCircularImage(
                              isNetworkImage: true,
                              width: _logoSize,
                              height: _logoSize,
                              image: snapshot.data!,
                            );
                          }
                        },
                      );
                    });
                  }),
                  const SizedBox(height: TSizes.xs),
                  Obx(() {
                    if (shopController.isLoading.value) {
                      return const TStripLoader(width: _logoSize, height: 24);
                    }

                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: TSizes.sm),
                      child: Text(
                        shopController.selectedShop.value.shopname,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                        textAlign: TextAlign.center,
                        overflow: TextOverflow.ellipsis,
                        maxLines: 2,
                      ),
                    );
                  }),
                ],
              ),
              const SizedBox(height: TSizes.sm),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: TSizes.xs,
                  vertical: TSizes.xs,
                ),
                child: Builder(
                  builder: (context) {
                    final tourCtrl = assignTourKeys && Get.isRegistered<GuidedTourController>()
                        ? GuidedTourController.instance
                        : null;
                    final sellKey = tourCtrl?.sidebarSellKey;
                    final buyKey = tourCtrl?.sidebarBuyKey;
                    final productsKey = tourCtrl?.sidebarProductsKey;
                    final reportsKey = tourCtrl?.sidebarReportsKey;

                    return Obx(() {
                      final auth = AuthenticationRepository.instance;
                      final menuItems = <Widget>[];

                      // MENU Section
                      menuItems.add(_SectionLabel(label: 'MENU', style: sectionStyle));
                      menuItems.add(const TMenuItem(
                        icon: Iconsax.status_up,
                        itemName: 'DashBoard',
                        route: TRoutes.dashboard,
                      ));

                      // BUY/SELL Section
                      final buySellItems = <Widget>[];
                      if (auth.hasPermission('pos_sale')) {
                        buySellItems.add(TMenuItem(
                          targetKey: sellKey,
                          icon: Iconsax.money_send,
                          itemName: 'Sell (Create Invoice)',
                          route: TRoutes.sales,
                        ));
                      }
                      if (auth.hasPermission('manage_purchases')) {
                        buySellItems.add(TMenuItem(
                          targetKey: buyKey,
                          icon: Iconsax.receive_square,
                          itemName: 'Buy (Restock)',
                          route: TRoutes.purchaseSales,
                        ));
                      }
                      if (buySellItems.isNotEmpty) {
                        menuItems.add(_SectionLabel(label: 'BUY/SELL', style: sectionStyle));
                        menuItems.addAll(buySellItems);
                      }

                      // LOGS Section
                      final logsItems = <Widget>[];
                      if (auth.hasPermission('manage_orders')) {
                        logsItems.add(const TMenuItem(
                          icon: Iconsax.box_time,
                          itemName: 'Orders',
                          route: TRoutes.orders,
                        ));
                      }
                      if (auth.hasPermission('manage_purchases')) {
                        logsItems.add(const TMenuItem(
                          icon: Iconsax.buy_crypto,
                          itemName: 'Purchases',
                          route: TRoutes.purchases,
                        ));
                      }
                      if (auth.hasPermission('manage_account_book')) {
                        logsItems.add(const TMenuItem(
                          icon: Iconsax.receipt_1,
                          itemName: 'Account Book',
                          route: TRoutes.accountBook,
                        ));
                      }
                      if (auth.hasPermission('manage_expenses')) {
                        logsItems.add(const TMenuItem(
                          icon: Iconsax.ticket_star,
                          itemName: 'Expenses',
                          route: TRoutes.expenseScreen,
                        ));
                      }
                      if (logsItems.isNotEmpty) {
                        menuItems.add(_SectionLabel(label: 'LOGS', style: sectionStyle));
                        menuItems.addAll(logsItems);
                      }

                      // PEOPLE Section
                      final peopleItems = <Widget>[];
                      if (auth.hasPermission('manage_customers')) {
                        peopleItems.add(const TMenuItem(
                          icon: Iconsax.user_tag,
                          itemName: 'Customers',
                          route: TRoutes.customer,
                        ));
                      }
                      if (auth.hasPermission('manage_vendors')) {
                        peopleItems.add(const TMenuItem(
                          icon: Iconsax.profile_add,
                          itemName: 'Vendors',
                          route: TRoutes.vendor,
                        ));
                      }
                      if (auth.isAdmin) {
                        peopleItems.add(const TMenuItem(
                          icon: Iconsax.user_octagon,
                          itemName: 'Salesman',
                          route: TRoutes.salesman,
                        ));
                        peopleItems.add(const TMenuItem(
                          icon: Iconsax.user_add,
                          itemName: 'Staff Management',
                          route: TRoutes.staffManagement,
                        ));
                      }
                      if (peopleItems.isNotEmpty) {
                        menuItems.add(_SectionLabel(label: 'PEOPLE', style: sectionStyle));
                        menuItems.addAll(peopleItems);
                      }

                      // INVENTORY Section
                      final inventoryItems = <Widget>[];
                      if (auth.hasPermission('manage_products')) {
                        inventoryItems.add(TMenuItem(
                          targetKey: productsKey,
                          icon: Iconsax.box_search,
                          itemName: 'Products',
                          route: TRoutes.products,
                        ));
                        inventoryItems.add(const TMenuItem(
                          icon: Iconsax.bookmark_2,
                          itemName: 'Brands',
                          route: TRoutes.brand,
                        ));
                        inventoryItems.add(const TMenuItem(
                          icon: Iconsax.category,
                          itemName: 'Categories',
                          route: TRoutes.category,
                        ));
                      
                      }
                      if (inventoryItems.isNotEmpty) {
                        menuItems.add(_SectionLabel(label: 'INVENTORY', style: sectionStyle));
                        menuItems.addAll(inventoryItems);
                      }

                      // OTHER Section
                      final otherItems = <Widget>[];
                      if (auth.hasPermission('manage_products')) {
                        otherItems.add(const TMenuItem(
                          icon: Iconsax.image,
                          itemName: 'Media',
                          route: TRoutes.mediaScreen,
                        ));
                      }
                      if (auth.hasPermission('view_reports')) {
                        otherItems.add(TMenuItem(
                          targetKey: reportsKey,
                          icon: Iconsax.chart_1,
                          itemName: 'Reports',
                          route: TRoutes.reportScreen,
                        ));
                      }
                  otherItems.add(const TMenuItem(
                    icon: Iconsax.profile_circle,
                    itemName: 'Profile',
                    route: TRoutes.profileScreen,
                  ));
                  if (auth.isAdmin) {
                    otherItems.add(const TMenuItem(
                      icon: Iconsax.shop,
                      itemName: 'Store',
                      route: TRoutes.storeScreen,
                    ));
                  }
                  if (otherItems.isNotEmpty) {
                    menuItems.add(_SectionLabel(label: 'OTHER', style: sectionStyle));
                    menuItems.addAll(otherItems);
                  }


                  menuItems.add(const SizedBox(height: TSizes.sm));
                  menuItems.add(const _LogoutMenuItem());

                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: menuItems,
                  );
                });
              }),
            ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LogoutMenuItem extends StatefulWidget {
  const _LogoutMenuItem();

  @override
  State<_LogoutMenuItem> createState() => _LogoutMenuItemState();
}

class _LogoutMenuItemState extends State<_LogoutMenuItem> {
  bool _isHovered = false;

  Future<void> _confirmLogout() async {
    // The sidebar lives in the shell, above the root navigator, so there is no
    // Navigator ancestor here for `showDialog`. `Get.dialog` routes through the
    // app's global navigator key instead.
    final confirmed = await Get.dialog<bool>(
      AlertDialog(
        title: Text('logout'.tr),
        content: Text('areYouSureLogout'.tr),
        actions: [
          TextButton(
            onPressed: () => Get.back(result: false),
            child: Text('cancel'.tr),
          ),
          TextButton(
            onPressed: () => Get.back(result: true),
            style: TextButton.styleFrom(foregroundColor: TColors.error),
            child: Text('logout'.tr),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      await Get.find<UserController>().logOut();
    }
  }

  @override
  Widget build(BuildContext context) {
    final iconColor = _isHovered ? TColors.white : TColors.error;
    final textColor = _isHovered ? TColors.white : TColors.error;

    return InkWell(
      onTap: _confirmLogout,
      onHover: (hovering) => setState(() => _isHovered = hovering),
      child: Container(
        height: TSizes.sidebarItemHeight,
        decoration: BoxDecoration(
          color: _isHovered ? TColors.error : TColors.transparent,
          borderRadius: BorderRadius.circular(TSizes.borderRadiusSm),
        ),
        child: Row(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: TSizes.sm),
              child: Icon(
                Iconsax.logout,
                size: TSizes.iconSm,
                color: iconColor,
              ),
            ),
            Expanded(
              child: Text(
                'logout'.tr,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: textColor,
                      fontSize: TSizes.fontSizeSm,
                      fontWeight: FontWeight.w600,
                    ),
                overflow: TextOverflow.ellipsis,
                maxLines: 1,
              ),
            ),
            const SizedBox(width: TSizes.xs),
          ],
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.label, this.style});

  final String label;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(
        left: TSizes.sm,
        top: TSizes.xs,
        bottom: 1,
      ),
      child: Text(label, style: style),
    );
  }
}
