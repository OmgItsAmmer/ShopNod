import 'package:flutter/material.dart';

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
    background: Color(0xFFF5F5F5),
    surface: Color(0xFFFFFFFF),
    surfaceMuted: Color(0xFFF6F6F6),
    text: Color(0xFF272727),
    textMuted: Color(0xFF656565),
    border: Color(0xFFD9D9D9),
    icon: Color(0xFF8D8D8D),
    primary: Color(0xFF4B68FF),
    link: Color(0xFF3A56F0),
    highlight: Color(0xFFFFE24B),
    focusRing: Color(0xFFB0C7FF),
    info: Color(0xFF1976D2),
    success: Color(0xFF388E3C),
    warning: Color(0xFFF57C00),
    error: Color(0xFFD32F2F),
  );
  static const dark = ShopNodTheme(
    background: Color(0xFF121212),
    surface: Color(0xFF2A2A2A),
    surfaceMuted: Color(0x0DFFFFFF),
    text: Color(0xFFF6F6F6),
    textMuted: Color(0x80F6F6F6),
    border: Color(0xFF313131),
    icon: Color(0xFF939393),
    primary: Color(0xFF4B68FF),
    link: Color(0xFFB0C7FF),
    highlight: Color(0xFFFFE24B),
    focusRing: Color(0xFFB0C7FF),
    info: Color(0xFF1976D2),
    success: Color(0xFF388E3C),
    warning: Color(0xFFF57C00),
    error: Color(0xFFD32F2F),
  );

  @override
  ShopNodTheme copyWith() => this;
  @override
  ShopNodTheme lerp(covariant ShopNodTheme? other, double t) => this;
}

ThemeData buildShopNodTheme(Brightness brightness) {
  final t = brightness == Brightness.dark
      ? ShopNodTheme.dark
      : ShopNodTheme.light;
  final scheme =
      ColorScheme.fromSeed(
        seedColor: t.primary,
        brightness: brightness,
      ).copyWith(
        primary: t.primary,
        onPrimary: const Color(0xFFFFFFFF),
        surface: t.surface,
        onSurface: t.text,
        error: t.error,
        outline: t.border,
      );
  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    scaffoldBackgroundColor: t.background,
    extensions: [t],
    textTheme: ThemeData(brightness: brightness).textTheme
        .apply(bodyColor: t.text, displayColor: t.text, fontFamily: 'Roboto')
        .copyWith(
          headlineLarge: TextStyle(
            fontSize: 34,
            fontWeight: FontWeight.w800,
            color: t.text,
            height: 1.12,
          ),
          headlineMedium: TextStyle(
            fontSize: 27,
            fontWeight: FontWeight.w800,
            color: t.text,
          ),
          titleLarge: TextStyle(
            fontSize: 21,
            fontWeight: FontWeight.w700,
            color: t.text,
          ),
          titleMedium: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w700,
            color: t.text,
          ),
          bodyLarge: TextStyle(fontSize: 17, height: 1.45, color: t.text),
          bodyMedium: TextStyle(fontSize: 15, height: 1.4, color: t.text),
          labelLarge: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w700,
          ),
        ),
    cardTheme: CardThemeData(
      color: t.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
        side: BorderSide(color: t.border),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: t.primary,
        foregroundColor: const Color(0xFFFFFFFF),
        minimumSize: const Size(44, 56),
        textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(44, 54),
        side: BorderSide(color: t.border),
        foregroundColor: t.text,
        textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: t.surface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: t.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: t.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: t.focusRing, width: 2),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: t.surface,
      selectedColor: t.primary,
      secondarySelectedColor: t.primary,
      side: BorderSide(color: t.border),
      labelStyle: TextStyle(color: t.text, fontWeight: FontWeight.w600),
      secondaryLabelStyle: const TextStyle(
        color: Color(0xFFFFFFFF),
        fontWeight: FontWeight.w700,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: t.surface,
      modalBackgroundColor: t.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
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
    ),
  );
}

extension ThemeAccess on BuildContext {
  ShopNodTheme get tokens => Theme.of(this).extension<ShopNodTheme>()!;
}
