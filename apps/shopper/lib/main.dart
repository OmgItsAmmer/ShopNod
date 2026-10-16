import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/storage.dart';
import 'l10n/app_strings.dart';
import 'router.dart';
import 'state/app_controller.dart';
import 'state/providers.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final storage = AppStorage();
  final app = AppController(storage);
  await app.init();
  runApp(
    ProviderScope(
      overrides: [
        storageProvider.overrideWithValue(storage),
        appControllerProvider.overrideWith((ref) => app),
      ],
      child: const ShopNodApp(),
    ),
  );
}

class ShopNodApp extends ConsumerWidget {
  const ShopNodApp({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = ref.watch(appControllerProvider);
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      debugShowCheckedModeBanner: false,
      title: 'ShopNod',
      routerConfig: router,
      theme: buildShopNodTheme(Brightness.light),
      darkTheme: buildShopNodTheme(Brightness.dark),
      themeMode: ThemeMode.system,
      locale: Locale(app.language),
      supportedLocales: AppStrings.supported,
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
    );
  }
}
