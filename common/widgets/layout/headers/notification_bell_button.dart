import 'package:ecommerce_dashboard/controllers/notification/notification_controller.dart';
import 'package:ecommerce_dashboard/utils/constants/colors.dart';
import 'package:ecommerce_dashboard/utils/constants/sizes.dart';
import 'package:ecommerce_dashboard/utils/device/device_utility.dart';
import 'package:ecommerce_dashboard/utils/helpers/helper_functions.dart';
import 'package:ecommerce_dashboard/views/notifications/notification_dropdown_panel.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:iconsax/iconsax.dart';

/// Header notification bell: dropdown on desktop/tablet, full screen on mobile.
class NotificationBellButton extends StatefulWidget {
  const NotificationBellButton({super.key});

  @override
  State<NotificationBellButton> createState() => _NotificationBellButtonState();
}

class _NotificationBellButtonState extends State<NotificationBellButton> {
  final LayerLink _layerLink = LayerLink();
  OverlayEntry? _overlayEntry;

  @override
  void dispose() {
    _removeOverlay();
    super.dispose();
  }

  void _onBellPressed() {
    final notifController = Get.find<NotificationController>();
    // Lazy-fetch: first bell tap triggers the network call.
    notifController.fetchNotificationsIfNeeded();

    if (TDeviceUtils.isMobileScreen(context)) {
      notifController.showNotifications();
      return;
    }
    if (_overlayEntry != null) {
      _removeOverlay();
    } else {
      _showOverlay();
    }
  }

  void _showOverlay() {
    // The header lives in the shell, above the root navigator, so there is no
    // Overlay ancestor here. `Get.overlayContext` is the navigator's own
    // overlay, which is also what keeps the dropdown above page content.
    final overlayContext = Get.overlayContext;
    if (overlayContext == null) return;
    final overlay = Overlay.of(overlayContext);
    _overlayEntry = OverlayEntry(
      builder: (overlayContext) => Stack(
        children: [
          Positioned.fill(
            child: GestureDetector(
              onTap: _removeOverlay,
              behavior: HitTestBehavior.opaque,
              child: Container(color: Colors.transparent),
            ),
          ),
          CompositedTransformFollower(
            link: _layerLink,
            targetAnchor: Alignment.bottomRight,
            followerAnchor: Alignment.topRight,
            offset: const Offset(-4, TSizes.sm),
            // The panel lives in an Overlay, outside the page's Scaffold, so its tappable rows had no
            // Material ancestor to paint ink on ("No Material widget found"). Give it its own.
            child: Material(
              type: MaterialType.transparency,
              child: NotificationDropdownPanel(onClose: _removeOverlay),
            ),
          ),
        ],
      ),
    );
    overlay.insert(_overlayEntry!);
  }

  void _removeOverlay() {
    _overlayEntry?.remove();
    _overlayEntry = null;
  }

  @override
  Widget build(BuildContext context) {
    final notificationController = Get.find<NotificationController>();

    return CompositedTransformTarget(
      link: _layerLink,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          IconButton(
            onPressed: _onBellPressed,
            icon: const Icon(Iconsax.notification),
          ),
          Positioned(
            top: 0,
            right: 0,
            child: Obx(() {
              final unreadCount = notificationController.unreadCount;
              if (unreadCount <= 0) return const SizedBox.shrink();
              return TweenAnimationBuilder<double>(
                tween: Tween<double>(begin: 0.0, end: 1.0),
                duration: const Duration(milliseconds: 400),
                builder: (context, value, child) {
                  return Transform.scale(
                    scale: value,
                    child: Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: TColors.error,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: THelperFunctions.isDarkMode(context) ? TColors.dark : TColors.white,
                          width: 1.5,
                        ),
                      ),
                      constraints: const BoxConstraints(
                        minWidth: 16,
                        minHeight: 16,
                      ),
                      child: Center(
                        child: Text(
                          unreadCount > 9 ? '9+' : '$unreadCount',
                          style: const TextStyle(
                            color: TColors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                  );
                },
              );
            }),
          ),
        ],
      ),
    );
  }
}
