import 'package:ecommerce_dashboard/routes/routes.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

/// Owns navigation state for the persistent app shell.
///
/// [currentRoute] is the single source of truth for both the sidebar highlight
/// and whether the shell chrome is visible. It is fed by `TRouteObserver`, so
/// it stays correct no matter how a route was reached (sidebar tap, deep link,
/// back button, or a `Get.toNamed` from inside a screen).
class SideBarController extends GetxController {
  final currentRoute = TRoutes.splashScreen.obs;
  final hoverItem = ''.obs;
  final isSidebarCollapsed = false.obs;

  /// Derived from [currentRoute], but kept as its own observable so the shell
  /// only rebuilds when chrome actually appears or disappears — not on every
  /// navigation between two chrome-bearing screens.
  final showsChrome = TRoutes.showsShell(TRoutes.splashScreen).obs;

  void toggleSidebarCollapse() {
    isSidebarCollapsed.value = !isSidebarCollapsed.value;
  }

  void changeHoverItem(String route) {
    if (!isActive(route)) {
      hoverItem.value = route;
    }
  }

  bool isActive(String route) => currentRoute.value == route;
  bool isHovering(String route) => hoverItem.value == route;

  /// Called by the route observer once the navigator has settled.
  void syncCurrentRoute(String? route) {
    if (route == null || route == currentRoute.value) return;
    currentRoute.value = route;
    showsChrome.value = TRoutes.showsShell(route);
    // A route change always ends the hover that triggered it; otherwise the
    // old item stays highlighted until the pointer moves again.
    hoverItem.value = '';
  }

  static SideBarController get instance => Get.find();

  /// Scaffold that owns the shell, so the drawer can be closed without the
  /// navigator. The drawer now sits above the root navigator, where
  /// `ModalRoute.of` is null — a `Get.back()` here would pop the current page
  /// instead of closing the drawer.
  final shellScaffoldKey = GlobalKey<ScaffoldState>();

  void closeDrawerIfOpen() {
    final scaffold = shellScaffoldKey.currentState;
    if (scaffold != null && scaffold.isDrawerOpen) {
      scaffold.closeDrawer();
    }
  }

  void openDrawerIfClosed() {
    final scaffold = shellScaffoldKey.currentState;
    if (scaffold != null && !scaffold.isDrawerOpen) {
      scaffold.openDrawer();
    }
  }

  void menuOnTap(String route) {
    closeDrawerIfOpen();

    if (isActive(route)) return;

    // Sidebar destinations are top level: replace the stack instead of growing
    // it. `Get.toNamed` here meant every visited screen stayed alive in memory
    // for the whole session.
    Get.offAllNamed(route);
  }
}
