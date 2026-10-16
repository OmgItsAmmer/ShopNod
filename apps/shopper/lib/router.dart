import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'claim/claim_screen.dart';
import 'learned_screen.dart';
import 'my_data_screen.dart';
import 'offer/offer_screen.dart';
import 'onboarding/onboarding_screens.dart';
import 'state/providers.dart';
import 'tabs/app_shell.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final app = ref.read(appControllerProvider);
  return GoRouter(
    initialLocation: '/',
    refreshListenable: app,
    redirect: (context, state) {
      app.configureDeepLink(state.uri);
      final path = state.matchedLocation;
      final onboarding =
          path == '/age' ||
          path == '/language' ||
          path == '/consent' ||
          path == '/interests' ||
          path == '/location';
      if (!app.onboarded && !onboarding)
        return app.ageConfirmed ? '/language' : '/age';
      if (app.onboarded && onboarding) return '/';
      return null;
    },
    routes: [
      GoRoute(path: '/', builder: (_, __) => const AppShell()),
      GoRoute(path: '/age', builder: (_, __) => const AgeScreen()),
      GoRoute(path: '/language', builder: (_, __) => const LanguageScreen()),
      GoRoute(path: '/consent', builder: (_, __) => const ConsentScreen()),
      GoRoute(path: '/interests', builder: (_, __) => const InterestsScreen()),
      GoRoute(path: '/location', builder: (_, __) => const LocationScreen()),
      GoRoute(
        path: '/offer/:id',
        builder: (_, s) => OfferScreen(id: s.pathParameters['id']!),
      ),
      GoRoute(
        path: '/claim/:id',
        builder: (_, s) => ClaimScreen(id: s.pathParameters['id']!),
      ),
      GoRoute(path: '/learned', builder: (_, __) => const LearnedScreen()),
      GoRoute(path: '/my-data', builder: (_, __) => const MyDataScreen()),
    ],
  );
});
