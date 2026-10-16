import 'package:flutter/material.dart';

import '../../../utils/device/device_utility.dart';

/// Picks the right responsive body for the current breakpoint.
///
/// This used to also build the sidebar and header via `DesktopLayout` /
/// `TabletLayout` / `MobileLayout`, which meant every screen constructed its
/// own copy of the app chrome and every navigation rebuilt it. That chrome now
/// lives once in `TAppShell`, above the navigator — this widget is only
/// responsible for choosing a layout.
class TSiteTemplate extends StatelessWidget {
  const TSiteTemplate({
    super.key,
    this.desktop,
    this.tablet,
    this.mobile,
  });

  final Widget? desktop;
  final Widget? tablet;
  final Widget? mobile;

  @override
  Widget build(BuildContext context) {
    final desktopContent = desktop ?? const SizedBox.shrink();
    final tabletContent = tablet ?? desktopContent;
    final mobileContent = mobile ?? tabletContent;

    // Breakpoints are measured against the whole window, not the space left
    // over next to the sidebar. A LayoutBuilder here would see roughly
    // `window - TSizes.sidebarWidth` and drop a 1400px desktop window to the
    // tablet body while the shell still showed the desktop sidebar.
    final Widget content;
    if (TDeviceUtils.isDesktopScreen(context)) {
      content = desktopContent;
    } else if (TDeviceUtils.isTabletScreen(context)) {
      content = tabletContent;
    } else {
      content = mobileContent;
    }

    // Kept so screens whose responsive bodies don't provide their own Scaffold
    // still get a material surface, and so in-screen snack bars / bottom sheets
    // resolve against the page rather than the shell.
    return Scaffold(body: content);
  }
}
