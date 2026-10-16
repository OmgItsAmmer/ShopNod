import 'package:flutter/material.dart';

import '../constants/colors.dart';
import '../helpers/helper_functions.dart';

/// Snackbars and toasts in the shared design (floating, rounded, coloured by meaning).
class TLoaders {
  static void hideSnackBar(BuildContext context) =>
      ScaffoldMessenger.of(context).hideCurrentSnackBar();

  static void customToast(BuildContext context, {required String message}) {
    final dark = THelperFunctions.isDarkMode(context);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        elevation: 0,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
        backgroundColor: Colors.transparent,
        content: Container(
          padding: const EdgeInsets.all(12.0),
          margin: const EdgeInsets.symmetric(horizontal: 30),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(30),
            color: dark
                ? TColors.darkerGrey.withValues(alpha: 0.9)
                : TColors.grey.withValues(alpha: 0.9),
          ),
          child: Center(
            child: Text(message, style: Theme.of(context).textTheme.labelLarge),
          ),
        ),
      ),
    );
  }

  static void successSnackBar(
    BuildContext context, {
    required String title,
    String message = '',
    int duration = 3,
  }) => _show(
    context,
    title: title,
    message: message,
    color: TColors.primary,
    icon: Icons.check_circle_outline,
    duration: duration,
  );

  static void warningSnackBar(
    BuildContext context, {
    required String title,
    String message = '',
  }) => _show(
    context,
    title: title,
    message: message,
    color: TColors.warning,
    icon: Icons.warning_amber_rounded,
  );

  static void errorSnackBar(
    BuildContext context, {
    required String title,
    String message = '',
  }) => _show(
    context,
    title: title,
    message: message,
    color: TColors.error,
    icon: Icons.error_outline,
  );

  static void _show(
    BuildContext context, {
    required String title,
    required String message,
    required Color color,
    required IconData icon,
    int duration = 3,
  }) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          behavior: SnackBarBehavior.floating,
          backgroundColor: color,
          duration: Duration(seconds: duration),
          margin: const EdgeInsets.all(16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          content: Row(
            children: [
              Icon(icon, color: TColors.white),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: TColors.white,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    if (message.isNotEmpty)
                      Text(
                        message,
                        style: const TextStyle(color: TColors.white),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
  }
}
