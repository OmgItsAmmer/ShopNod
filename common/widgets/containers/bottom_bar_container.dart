import 'package:ecommerce_dashboard/common/widgets/containers/rounded_container.dart';
import 'package:ecommerce_dashboard/controllers/media/media_controller.dart';
import 'package:ecommerce_dashboard/utils/constants/colors.dart';
import 'package:ecommerce_dashboard/utils/constants/sizes.dart';
import 'package:ecommerce_dashboard/utils/device/device_utility.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

/// Shared save / discard bottom bar for entity add-edit forms.
class FormBottomBar extends StatelessWidget {
  const FormBottomBar({
    super.key,
    required this.isLoading,
    required this.isNewRecord,
    required this.onDiscard,
    required this.onSave,
    this.saveLabel = 'Save',
    this.updateLabel = 'Update',
    this.discardLabel = 'Discard',
    this.showIcons = false,
    this.discardUsesErrorStyle = false,
    this.popOnComplete = true,
    this.clearPendingThumbnail = true,
    this.saveButtonKey,
  });

  final bool isLoading;
  final bool isNewRecord;
  final VoidCallback onDiscard;
  final Future<void> Function() onSave;
  final String saveLabel;
  final String updateLabel;
  final String discardLabel;
  final bool showIcons;
  final bool discardUsesErrorStyle;
  final bool popOnComplete;
  final bool clearPendingThumbnail;
  final Key? saveButtonKey;

  @override
  Widget build(BuildContext context) {
    final primaryLabel = isNewRecord ? saveLabel : updateLabel;

    return TRoundedContainer(
      padding: const EdgeInsets.all(TSizes.defaultSpace),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          Expanded(
            flex: TDeviceUtils.isDesktopScreen(context) ? 4 : 0,
            child: const SizedBox(),
          ),
          Expanded(
            child: SizedBox(
              width: double.infinity,
              child: showIcons
                  ? OutlinedButton.icon(
                      icon: Icon(
                        Icons.cancel,
                        size: 18,
                        color: discardUsesErrorStyle
                            ? TColors.error
                            : TColors.white,
                      ),
                      label: Text(discardLabel),
                      onPressed: isLoading ? null : () => _handleDiscard(context),
                      style: discardUsesErrorStyle
                          ? OutlinedButton.styleFrom(
                              side: const BorderSide(color: TColors.error),
                              foregroundColor: TColors.error,
                            )
                          : null,
                    )
                  : OutlinedButton(
                      onPressed: isLoading ? null : () => _handleDiscard(context),
                      style: discardUsesErrorStyle
                          ? OutlinedButton.styleFrom(
                              side: const BorderSide(color: TColors.error),
                              foregroundColor: TColors.error,
                            )
                          : null,
                      child: Text(discardLabel),
                    ),
            ),
          ),
          const SizedBox(width: TSizes.spaceBtwItems),
          Expanded(
            child: SizedBox(
              width: double.infinity,
              child: showIcons
                  ? ElevatedButton.icon(
                      key: saveButtonKey,
                      icon: isLoading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: TColors.white,
                              ),
                            )
                          : const Icon(
                              Icons.done_all,
                              size: 18,
                              color: TColors.white,
                            ),
                      label: Text(primaryLabel),
                      onPressed: isLoading ? null : () => _handleSave(context),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: TColors.primary,
                        foregroundColor: TColors.white,
                      ),
                    )
                  : ElevatedButton(
                      key: saveButtonKey,
                      onPressed: isLoading ? null : () => _handleSave(context),
                      child: isLoading
                          ? const CircularProgressIndicator(color: TColors.white)
                          : Text(primaryLabel),
                    ),
            ),
          ),
        ],
      ),
    );
  }

  void _handleDiscard(BuildContext context) {
    if (clearPendingThumbnail && Get.isRegistered<MediaController>()) {
      Get.find<MediaController>().clearPendingThumbnail();
    }
    onDiscard();
  }

  Future<void> _handleSave(BuildContext context) async {
    await onSave();
    if (popOnComplete && context.mounted) {
      Navigator.of(context).pop();
    }
  }
}

/// Obx-friendly wrapper when loading state lives on a GetX controller.
class FormBottomBarObx extends StatelessWidget {
  const FormBottomBarObx({
    super.key,
    required this.isLoading,
    required this.isNewRecord,
    required this.onDiscard,
    required this.onSave,
    this.saveLabel = 'Save',
    this.updateLabel = 'Update',
    this.discardLabel = 'Discard',
    this.showIcons = false,
    this.discardUsesErrorStyle = false,
    this.popOnComplete = true,
    this.clearPendingThumbnail = true,
    this.saveButtonKey,
  });

  final RxBool isLoading;
  final bool isNewRecord;
  final VoidCallback onDiscard;
  final Future<void> Function() onSave;
  final String saveLabel;
  final String updateLabel;
  final String discardLabel;
  final bool showIcons;
  final bool discardUsesErrorStyle;
  final bool popOnComplete;
  final bool clearPendingThumbnail;
  final Key? saveButtonKey;

  @override
  Widget build(BuildContext context) {
    return Obx(
      () => FormBottomBar(
        isLoading: isLoading.value,
        isNewRecord: isNewRecord,
        onDiscard: onDiscard,
        onSave: onSave,
        saveLabel: saveLabel,
        updateLabel: updateLabel,
        discardLabel: discardLabel,
        showIcons: showIcons,
        discardUsesErrorStyle: discardUsesErrorStyle,
        popOnComplete: popOnComplete,
        clearPendingThumbnail: clearPendingThumbnail,
        saveButtonKey: saveButtonKey,
      ),
    );
  }
}
