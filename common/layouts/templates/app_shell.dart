import 'package:ecommerce_dashboard/common/widgets/layout/headers/header.dart';
import 'package:ecommerce_dashboard/common/widgets/layout/sidebar/controller/sidebar_controller.dart';
import 'package:ecommerce_dashboard/common/widgets/layout/sidebar/tside_bar.dart';
import 'package:ecommerce_dashboard/utils/constants/sizes.dart';
import 'package:ecommerce_dashboard/utils/device/device_utility.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

/// Hosts the sidebar and header **above** the root navigator.
///
/// Previously every screen wrapped itself in `TSiteTemplate`, which built its
/// own `TSideBar` and `THeader`. Each navigation therefore threw away the whole
/// chrome and rebuilt it — refetching the shop logo and profile image, and
/// animating the sidebar along with the page. Mounting the chrome once here
/// means a route change only swaps [child], which is the navigator.
///
/// The tree shape is deliberately constant: sidebar and header collapse to
/// zero-size widgets on chromeless routes rather than being removed, so
/// [child] never changes depth and the navigator is never re-parented.
class TAppShell extends StatefulWidget {
  const TAppShell({super.key, required this.child});

  /// The root navigator supplied by `GetMaterialApp.builder`.
  final Widget child;

  @override
  State<TAppShell> createState() => _TAppShellState();
}

class _TAppShellState extends State<TAppShell> {
  // The shell builds inside GetMaterialApp.builder, which can run before the
  // initial binding on the very first frame.
  final SideBarController _controller = Get.isRegistered<SideBarController>()
      ? Get.find<SideBarController>()
      : Get.put(SideBarController(), permanent: true);

  // One header instance for the app's lifetime. Handing Flutter the same widget
  // object on every rebuild lets it short-circuit the subtree, so toggling the
  // sidebar or crossing a chromeless route does not rebuild the header.
  late final Widget _header = THeader(scaffoldKey: _controller.shellScaffoldKey);

  @override
  Widget build(BuildContext context) {
    return Overlay(
      initialEntries: [
        OverlayEntry(
          builder: (context) {
            final controller = _controller;
            final isDesktop = TDeviceUtils.isDesktopScreen(context);

            return Obx(() {
              final showChrome = controller.showsChrome.value;
              final showInlineSidebar = showChrome && isDesktop && !controller.isSidebarCollapsed.value;

              return Scaffold(
                key: controller.shellScaffoldKey,
                drawer: showChrome && !isDesktop ? const TSideBar() : null,
                body: SafeArea(
                  child: Row(
                    children: [
                      // Collapsed rather than removed to keep `child` at a fixed depth.
                      // ClipRect + OverflowBox ensures TSideBar is always laid out with its full
                      // 250px width, preventing 0-width layout assertions and mouse tracker crashes.
                      if (isDesktop)
                         AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          curve: Curves.easeInOut,
                          width: showInlineSidebar ? TSizes.sidebarWidth : 0,
                          child: ClipRect(
                            child: OverflowBox(
                              minWidth: TSizes.sidebarWidth,
                              maxWidth: TSizes.sidebarWidth,
                              alignment: Alignment.topLeft,
                              child: SizedBox(
                                width: TSizes.sidebarWidth,
                                child: IgnorePointer(
                                  ignoring: !showInlineSidebar,
                                  child: const TSideBar(),
                                ),
                              ),
                            ),
                          ),
                        ),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (showChrome)
                              _header
                            else
                              const SizedBox.shrink(),
                            Expanded(child: widget.child),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              );
            });
          },
        ),
      ],
    );
  }
}
