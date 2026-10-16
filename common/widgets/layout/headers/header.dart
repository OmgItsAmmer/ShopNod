import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:iconsax/iconsax.dart';

import '../../../../bindings/shell_scope.dart';
import '../../../../controllers/fullscreen/fullscreen_controller.dart';
import '../../../../controllers/media/media_controller.dart';
import 'dev_credit_bar.dart';
import 'low_credits_banner.dart';
import 'notification_bell_button.dart';
import '../../../../controllers/user/user_controller.dart';
import '../../../../utils/constants/colors.dart';
import '../../../../utils/constants/enums.dart';
import '../../../../utils/constants/sizes.dart';
import '../../../../utils/device/device_utility.dart';
import '../../../../utils/helpers/helper_functions.dart';
import '../sidebar/controller/sidebar_controller.dart';
import '../../images/t_circular_image.dart';
import '../../images/t_default_avatar.dart';
import '../../images/t_rounded_image.dart';
import '../../shimmers/shimmer.dart';

String _roleLabel(String role) {
  switch (role.toLowerCase()) {
    case 'admin':
      return 'adminOwner'.tr;
    case 'super_admin':
      return 'Super Admin';
    default:
      return 'salesman'.tr;
  }
}

class THeader extends StatelessWidget implements PreferredSizeWidget {
  const THeader({super.key, this.scaffoldKey});
  final GlobalKey<ScaffoldState>? scaffoldKey;
  @override
  Widget build(BuildContext context) {
    // All shell-scoped: registered permanently by the bindings, with
    // [shellScoped] as a first-frame fallback that registers permanently too.
    // A plain `Get.put` here would hand the header a route-scoped instance that
    // gets deleted under it on the next navigation.
    final userController = shellScoped(UserController.new);
    final mediaController = shellScoped(MediaController.new);
    final fullscreenController = shellScoped(FullscreenController.new);

    final isDark = THelperFunctions.isDarkMode(context);
    final bgColor = isDark ? TColors.dark : TColors.white;
    final borderColor = isDark ? TColors.borderSecondary : TColors.grey;
    final labelColor = isDark ? TColors.darkGrey : TColors.textSecondary;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // ── Dev credit tracker bar (debug mode only) ─────────────────────
        if (kDebugMode) const DevCreditBar(),

        // ── Low credits warning ────────────────────────────────────────────
        const LowCreditsBanner(),

        // ── Main header content ──────────────────────────────────────────
        Stack(children: [Container(
          decoration: BoxDecoration(
            color: bgColor,
            border: Border(bottom: BorderSide(color: borderColor, width: 1)),
          ),
          padding: const EdgeInsets.symmetric(
              horizontal: TSizes.md, vertical: TSizes.xs),
          child: AppBar(
            automaticallyImplyLeading: false,
            backgroundColor: Colors.transparent,
            elevation: 0,
            surfaceTintColor: Colors.transparent,
            leading: Obx(() {
              final sideBarCtrl = Get.isRegistered<SideBarController>()
                  ? SideBarController.instance
                  : Get.put(SideBarController(), permanent: true);
              final isCollapsed = sideBarCtrl.isSidebarCollapsed.value;
              final isDesktop = TDeviceUtils.isDesktopScreen(context);
              if (isDesktop && !isCollapsed) return const SizedBox.shrink();

              return IconButton(
                onPressed: () {
                  if (isDesktop) {
                    sideBarCtrl.toggleSidebarCollapse();
                  } else {
                    scaffoldKey?.currentState?.openDrawer();
                  }
                },
                icon: Icon(Iconsax.menu, color: isDark ? TColors.white : TColors.black),
                tooltip: isDesktop ? 'Expand Sidebar' : 'Open Menu',
              );
            }),
            actions: [
              // Desktop-width web and tablets are wide enough to pass the
              // breakpoint, but window_manager only exists on desktop.
              (TDeviceUtils.isDesktopScreen(context) &&
                      FullscreenController.isSupported)
                  ? Obx(() => IconButton(
                        icon: Icon(
                          fullscreenController.isFullscreen.value
                              ? Icons.fullscreen_exit
                              : Icons.fullscreen,
                          color: isDark ? TColors.white : TColors.black,
                        ),
                        onPressed: fullscreenController.toggleFullscreen,
                      ))
                  : const SizedBox.shrink(),

              const SizedBox(
                width: TSizes.spaceBtwItems / 2,
              ),
              const NotificationBellButton(),
              const SizedBox(
                width: TSizes.spaceBtwItems / 2,
              ),
              //User Data
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Obx(
                    () {
                      final image = mediaController.displayImage.value;

                      if (image != null &&
                          mediaController.displayImageOwner.value ==
                              MediaCategory.users.toString().split('.').last) {
                        return FutureBuilder<String?>(
                          future: mediaController.getImageFromBucket(
                            MediaCategory.users.toString().split('.').last,
                            image.filename ?? '',
                          ),
                          builder: (context, snapshot) {
                            if (snapshot.connectionState ==
                                ConnectionState.waiting) {
                              return const TShimmerEffect(width: 36, height: 36, radius: 100);
                            } else if (snapshot.hasError ||
                                snapshot.data == null) {
                              return const TDefaultAvatar(size: 36);
                            } else {
                              return TRoundedImage(
                                isNetworkImage: true,
                                width: 36,
                                height: 36,
                                borderRadius: 100,
                                fit: BoxFit.cover,
                                imageurl: snapshot.data!,
                              );
                            }
                          },
                        );
                      }
                      // Serve the resolved URL straight from cache. The route
                      // middleware clears `displayImage` on every navigation,
                      // which re-runs this Obx; without the cache check that
                      // rebuilt the FutureBuilder each time and flashed a
                      // shimmer, because an async future is never already
                      // complete on its first frame.
                      return Obx(() {
                        final cached = mediaController.cachedProfileImage.value;
                        if (cached != null) {
                          return TCircularImage(
                            image: cached,
                            isNetworkImage: true,
                            width: 36,
                            height: 36,
                          );
                        }

                        return FutureBuilder<String?>(
                          future: mediaController.fetchAndCacheProfileImage(
                              userController.currentUser.value.userId,
                              MediaCategory.users.toString().split('.').last),
                          builder: (context, snapshot) {
                            if (snapshot.connectionState ==
                                ConnectionState.waiting) {
                              return const TShimmerEffect(width: 36, height: 36, radius: 100);
                            } else if (snapshot.hasError) {
                              return const TDefaultAvatar(size: 36);
                            } else if (snapshot.hasData && snapshot.data != null) {
                              return TCircularImage(
                                image: snapshot.data!,
                                isNetworkImage: true,
                                width: 36,
                                height: 36,
                              );
                            } else {
                              return const TDefaultAvatar(size: 36);
                            }
                          },
                        );
                      });
                    },
                  ),
                  const SizedBox(
                    width: TSizes.sm,
                  ),
                  Obx(() {
                    if (userController.profileLoading.value) {
                      return const TShimmerEffect(width: 60, height: 20);
                    }
                    return (TDeviceUtils.isMobileScreen(context))
                        ? const SizedBox.shrink()
                        : Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(
                                userController.currentUser.value.fullName,
                                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                      fontWeight: FontWeight.w600,
                                      color: isDark ? TColors.white : TColors.black,
                                    ),
                              ),
                              Text(
                                _roleLabel(userController.currentUser.value.role),
                                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                      color: labelColor,
                                    ),
                              ),
                            ],
                          );
                  })
                ]
              )
            ],
          ),
        ),
        ]),
      ],
    );
  }

  @override
  Size get preferredSize => Size.fromHeight(
      TDeviceUtils.getAppBarHeight() + 15 + (kDebugMode ? 22 : 0) + 22);
}
