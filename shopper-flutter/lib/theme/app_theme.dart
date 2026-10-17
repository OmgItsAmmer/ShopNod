import 'package:flutter/material.dart';

import '../utils/constants/colors.dart';
import '../utils/constants/sizes.dart';
import '../utils/theme/theme.dart';

@immutable
class ShopNodTheme extends ThemeExtension<ShopNodTheme> {
  const ShopNodTheme({
    required this.background,
    required this.surface,
    required this.surfaceMuted,
    required this.text,
    required this.textMuted,
    required this.border,
    required this.icon,
    required this.primary,
    required this.link,
    required this.highlight,
    required this.focusRing,
    required this.info,
    required this.success,
    required this.warning,
    required this.error,
  });

  final Color background,
      surface,
      surfaceMuted,
      text,
      textMuted,
      border,
      icon,
      primary,
      link,
      highlight,
      focusRing,
      info,
      success,
      warning,
      error;

  static const light = ShopNodTheme(
    background: TColors.primaryBackground,
    surface: TColors.white,
    surfaceMuted: TColors.lightContainer,
    text: TColors.textPrimary,
    textMuted: TColors.textSecondary,
    border: TColors.borderPrimary,
    icon: TColors.iconPrimary,
    primary: TColors.primary,
    link: Color(0xFF3A56F0),
    highlight: TColors.secondary,
    focusRing: TColors.accent,
    info: TColors.info,
    success: TColors.success,
    warning: TColors.warning,
    error: TColors.error,
  );
  static const dark = ShopNodTheme(
    background: Color(0xFF121212),
    surface: Color(0xFF2A2A2A),
    surfaceMuted: Color(0x0DFFFFFF),
    text: TColors.textDarkPrimary,
    textMuted: TColors.textDarkSecondary,
    border: TColors.borderSecondary,
    icon: TColors.darkGrey,
    primary: TColors.primary,
    link: TColors.accent,
    highlight: TColors.secondary,
    focusRing: TColors.accent,
    info: TColors.info,
    success: TColors.success,
    warning: TColors.warning,
    error: TColors.error,
  );

  @override
  ShopNodTheme copyWith() => this;
  @override
  ShopNodTheme lerp(covariant ShopNodTheme? other, double t) => this;
}

/// The app theme: the shared design system (`utils/theme`) plus ShopNod's own pieces
/// (colour scheme, cards, navigation bar, snackbars and the [ShopNodTheme] tokens).
ThemeData buildShopNodTheme(Brightness brightness) {
  final dark = brightness == Brightness.dark;
  final t = dark ? ShopNodTheme.dark : ShopNodTheme.light;
  final base = dark ? TAppTheme.darkTheme : TAppTheme.lightTheme;
  final scheme =
      ColorScheme.fromSeed(
        seedColor: t.primary,
        brightness: brightness,
      ).copyWith(
        primary: t.primary,
        onPrimary: TColors.white,
        secondary: t.highlight,
        onSecondary: TColors.textPrimary,
        surface: t.surface,
        onSurface: t.text,
        error: t.error,
        outline: t.border,
      );
  return base.copyWith(
    colorScheme: scheme,
    scaffoldBackgroundColor: t.background,
    extensions: [t],
    appBarTheme: base.appBarTheme.copyWith(
      backgroundColor: t.background,
      surfaceTintColor: t.background,
    ),
    cardTheme: CardThemeData(
      color: t.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(TSizes.cardRadiusLg),
        side: BorderSide(color: t.border),
      ),
    ),
    inputDecorationTheme: base.inputDecorationTheme.copyWith(
      filled: true,
      fillColor: t.surface,
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(TSizes.inputFieldRadius),
        borderSide: BorderSide(color: t.primary, width: 2),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: t.surface,
      indicatorColor: t.primary.withValues(alpha: .15),
      height: 72,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: t.text,
      contentTextStyle: TextStyle(color: t.background),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(TSizes.borderRadiusLg),
      ),
    ),
  );
}

extension ThemeAccess on BuildContext {
  ShopNodTheme get tokens => Theme.of(this).extension<ShopNodTheme>()!;
}
