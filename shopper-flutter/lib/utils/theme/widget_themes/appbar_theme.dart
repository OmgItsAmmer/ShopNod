import 'package:flutter/material.dart';
import '../../constants/colors.dart';
import '../../constants/sizes.dart';

class TAppBarTheme {
  TAppBarTheme._();

  static const lightAppBarTheme = AppBarTheme(
    elevation: 0,
    centerTitle: false,
    scrolledUnderElevation: 0,
    backgroundColor: Colors.white,
    surfaceTintColor: Colors.white,
    iconTheme: IconThemeData(color: TColors.iconPrimary, size: TSizes.iconMd),
    actionsIconTheme: IconThemeData(
      color: TColors.iconPrimary,
      size: TSizes.iconMd,
    ),
    titleTextStyle: TextStyle(
      fontSize: 18.0,
      fontWeight: FontWeight.w600,
      color: TColors.black,
    ),
  );
  static const darkAppBarTheme = AppBarTheme(
    elevation: 0,
    centerTitle: false,
    scrolledUnderElevation: 0,
    backgroundColor: TColors.dark,
    surfaceTintColor: TColors.dark,
    iconTheme: IconThemeData(color: TColors.white, size: TSizes.iconMd),
    actionsIconTheme: IconThemeData(color: TColors.white, size: TSizes.iconMd),
    titleTextStyle: TextStyle(
      fontSize: 18.0,
      fontWeight: FontWeight.w600,
      color: TColors.white,
    ),
  );
}
