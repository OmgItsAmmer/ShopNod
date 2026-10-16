import 'package:ecommerce_dashboard/common/widgets/containers/rounded_container.dart';
import 'package:ecommerce_dashboard/common/widgets/icons/t_circular_icon.dart';
import 'package:ecommerce_dashboard/common/widgets/images/t_rounded_image.dart';
import 'package:ecommerce_dashboard/common/widgets/shimmers/shimmer.dart';
import 'package:ecommerce_dashboard/controllers/media/media_controller.dart';
import 'package:ecommerce_dashboard/utils/constants/colors.dart';
import 'package:ecommerce_dashboard/utils/constants/enums.dart';
import 'package:ecommerce_dashboard/utils/constants/sizes.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:iconsax/iconsax.dart';

enum ThumbnailPickStyle { button, cameraOverlay }

/// Displays an entity thumbnail with local preview until save uploads it.
class EntityThumbnailPreview extends StatelessWidget {
  const EntityThumbnailPreview({
    super.key,
    required this.category,
    required this.entityId,
    this.width = 150,
    this.height = 150,
    this.networkWidth,
    this.networkHeight,
    this.pickStyle = ThumbnailPickStyle.button,
    this.buttonLabel = 'Add Thumbnail',
  });

  final MediaCategory category;
  final int entityId;
  final double width;
  final double height;
  final double? networkWidth;
  final double? networkHeight;
  final ThumbnailPickStyle pickStyle;
  final String buttonLabel;

  @override
  Widget build(BuildContext context) {
    final mediaController = Get.find<MediaController>();
    final bucketName = category.folderName;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        pickStyle == ThumbnailPickStyle.cameraOverlay
            ? Stack(
                alignment: Alignment.bottomRight,
                children: [
                  _ThumbnailImage(
                    mediaController: mediaController,
                    bucketName: bucketName,
                    entityId: entityId,
                    width: width,
                    height: height,
                    networkWidth: networkWidth ?? width,
                    networkHeight: networkHeight ?? height,
                  ),
                  _PickControl(
                    mediaController: mediaController,
                    category: category,
                    pickStyle: pickStyle,
                  ),
                ],
              )
            : _ThumbnailImage(
                mediaController: mediaController,
                bucketName: bucketName,
                entityId: entityId,
                width: width,
                height: height,
                networkWidth: networkWidth ?? width,
                networkHeight: networkHeight ?? height,
              ),
        if (pickStyle == ThumbnailPickStyle.button) ...[
          const SizedBox(height: TSizes.spaceBtwItems),
          _PickControl(
            mediaController: mediaController,
            category: category,
            pickStyle: pickStyle,
            buttonLabel: buttonLabel,
          ),
        ],
      ],
    );
  }
}

class _ThumbnailImage extends StatelessWidget {
  const _ThumbnailImage({
    required this.mediaController,
    required this.bucketName,
    required this.entityId,
    required this.width,
    required this.height,
    required this.networkWidth,
    required this.networkHeight,
  });

  final MediaController mediaController;
  final String bucketName;
  final int entityId;
  final double width;
  final double height;
  final double networkWidth;
  final double networkHeight;

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final image = mediaController.displayImage.value;

      if (image?.file != null &&
          mediaController.displayImageOwner.value == bucketName) {
        return TRoundedImage(
          isFileImage: true,
          width: width,
          height: height,
          imageurl: image!.file!.path,
        );
      }

      if (image != null &&
          image.imageId > 0 &&
          image.filename != null &&
          image.filename!.isNotEmpty &&
          mediaController.displayImageOwner.value == bucketName) {
        return FutureBuilder<String?>(
          future: mediaController.getImageFromBucket(
            bucketName,
            image.filename!,
            shopId: image.shopId,
          ),
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return TShimmerEffect(width: width, height: height);
            }
            if (snapshot.hasError || snapshot.data == null) {
              return const Icon(Icons.error);
            }
            return TRoundedImage(
              isNetworkImage: true,
              width: width,
              height: height,
              imageurl: snapshot.data!,
            );
          },
        );
      }

      return FutureBuilder<String?>(
        future: mediaController.fetchMainImage(entityId, bucketName),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return TShimmerEffect(width: networkWidth, height: networkHeight);
          }
          if (snapshot.hasError) {
            return const Text('Error loading image');
          }
          if (snapshot.hasData && snapshot.data != null) {
            return TRoundedImage(
              isNetworkImage: true,
              width: networkWidth,
              height: networkHeight,
              imageurl: snapshot.data!,
            );
          }
          return TCircularIcon(
            icon: Iconsax.image,
            width: width,
            height: height,
            backgroundColor: TColors.primaryBackground,
          );
        },
      );
    });
  }
}

class _PickControl extends StatelessWidget {
  const _PickControl({
    required this.mediaController,
    required this.category,
    required this.pickStyle,
    this.buttonLabel = 'Add Thumbnail',
  });

  final MediaController mediaController;
  final MediaCategory category;
  final ThumbnailPickStyle pickStyle;
  final String buttonLabel;

  @override
  Widget build(BuildContext context) {
    if (pickStyle == ThumbnailPickStyle.cameraOverlay) {
      return TRoundedContainer(
        onTap: () => mediaController.pickThumbnailPreview(category: category),
        borderColor: TColors.white,
        backgroundColor: TColors.primary,
        padding: const EdgeInsets.all(6),
        child: const Icon(
          Iconsax.camera,
          size: 25,
          color: TColors.white,
        ),
      );
    }

    return OutlinedButton(
      onPressed: () => mediaController.pickThumbnailPreview(category: category),
      child: Text(
        buttonLabel,
        style: Theme.of(context).textTheme.titleMedium,
      ),
    );
  }
}
