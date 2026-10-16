import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../state/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/shared.dart';

class OnboardingScaffold extends StatelessWidget {
  const OnboardingScaffold({
    super.key,
    required this.step,
    required this.title,
    required this.subtitle,
    required this.child,
    required this.action,
  });
  final int step;
  final String title, subtitle;
  final Widget child, action;
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: PageFrame(
        maxWidth: 620,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 8),
            Row(
              children: [
                const AppLogo(),
                const Spacer(),
                Text(
                  '$step of 5',
                  style: TextStyle(
                    color: context.tokens.textMuted,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 22),
            LinearProgressIndicator(
              value: step / 5,
              minHeight: 6,
              borderRadius: BorderRadius.circular(99),
              backgroundColor: context.tokens.border,
            ),
            const SizedBox(height: 40),
            Text(title, style: Theme.of(context).textTheme.headlineLarge),
            const SizedBox(height: 10),
            Text(
              subtitle,
              style: Theme.of(
                context,
              ).textTheme.bodyLarge?.copyWith(color: context.tokens.textMuted),
            ),
            const SizedBox(height: 30),
            Expanded(child: SingleChildScrollView(child: child)),
            const SizedBox(height: 16),
            action,
          ],
        ),
      ),
    ),
  );
}

class AgeScreen extends ConsumerWidget {
  const AgeScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) => OnboardingScaffold(
    step: 1,
    title: 'Good deals, less waste.',
    subtitle:
        'ShopNod finds nearby offers that fit what you need. No account or name required.',
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          children: [
            Icon(
              Icons.shield_outlined,
              color: context.tokens.primary,
              size: 48,
            ),
            const SizedBox(height: 16),
            Text(
              'You must be 18 or older to continue.',
              style: Theme.of(context).textTheme.titleMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'We ask once and store only your confirmation.',
              style: TextStyle(color: context.tokens.textMuted),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    ),
    action: FilledButton(
      onPressed: () async {
        await ref.read(appControllerProvider).confirmAge();
        if (context.mounted) context.go('/language');
      },
      child: const Text('I’m 18 or older'),
    ),
  );
}

class LanguageScreen extends ConsumerWidget {
  const LanguageScreen({super.key});
  static const options = [
    ('en', 'English', 'Hello'),
    ('ur', 'اردو', 'خوش آمدید'),
    ('ar', 'العربية', 'مرحباً'),
    ('es', 'Español', 'Hola'),
  ];
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = ref.watch(appControllerProvider);
    return OnboardingScaffold(
      step: 2,
      title: 'Choose your language',
      subtitle: 'You can change this any time in Settings.',
      child: Column(
        children: options
            .map(
              (o) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Card(
                  child: RadioListTile<String>(
                    value: o.$1,
                    groupValue: app.language,
                    onChanged: (v) => app.chooseLanguage(v!),
                    title: Text(
                      o.$2,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    subtitle: Text(o.$3),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 18,
                      vertical: 7,
                    ),
                  ),
                ),
              ),
            )
            .toList(),
      ),
      action: FilledButton(
        onPressed: () => context.go('/consent'),
        child: const Text('Continue'),
      ),
    );
  }
}

class ConsentScreen extends ConsumerWidget {
  const ConsentScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = ref.watch(appControllerProvider);
    final c = app.consents;
    Widget tile(
      String title,
      String sub,
      IconData icon,
      bool value,
      ValueChanged<bool> set,
    ) => Card(
      child: SwitchListTile(
        value: value,
        onChanged: set,
        secondary: Icon(icon, color: context.tokens.primary),
        title: Text(title, style: Theme.of(context).textTheme.titleMedium),
        subtitle: Text(sub),
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 6),
      ),
    );
    return OnboardingScaffold(
      step: 3,
      title: 'You’re in control',
      subtitle: 'Choose each use separately. You can withdraw consent later.',
      child: Column(
        children: [
          tile(
            'Approximate location',
            'Find offers within your chosen distance.',
            Icons.location_on_outlined,
            c.location,
            (v) => app.updateConsents(c.copyWith(location: v)),
          ),
          const SizedBox(height: 10),
          tile(
            'Notifications',
            'Tell me when a matching offer goes live.',
            Icons.notifications_none_rounded,
            c.notifications,
            (v) => app.updateConsents(c.copyWith(notifications: v)),
          ),
          const SizedBox(height: 10),
          tile(
            'Shopping list',
            'Save my list for up to 30 days.',
            Icons.list_alt_rounded,
            c.list,
            (v) => app.updateConsents(c.copyWith(list: v)),
          ),
          const SizedBox(height: 10),
          tile(
            'Personalisation',
            'Rank offers using my choices and activity.',
            Icons.tune_rounded,
            c.personalisation,
            (v) => app.updateConsents(c.copyWith(personalisation: v)),
          ),
          const SizedBox(height: 10),
          tile(
            'Anonymous analytics',
            'Help improve ShopNod. Optional.',
            Icons.insights_outlined,
            c.analytics,
            (v) => app.updateConsents(c.copyWith(analytics: v)),
          ),
          const SizedBox(height: 14),
          TextButton.icon(
            onPressed: () => showDialog(
              context: context,
              builder: (_) => AlertDialog(
                title: const Text('Privacy in plain words'),
                content: const Text(
                  'We do not ask for your name. We keep only an anonymous install ID, your chosen area, and the preferences you allow. Exact location history is never stored. You can export or delete everything at any time.',
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Got it'),
                  ),
                ],
              ),
            ),
            icon: const Icon(Icons.privacy_tip_outlined),
            label: const Text('Read our privacy promise'),
          ),
        ],
      ),
      action: FilledButton(
        onPressed: () => context.go('/interests'),
        child: const Text('Save choices'),
      ),
    );
  }
}

class InterestsScreen extends ConsumerStatefulWidget {
  const InterestsScreen({super.key});
  @override
  ConsumerState<InterestsScreen> createState() => _InterestsScreenState();
}

class _InterestsScreenState extends ConsumerState<InterestsScreen> {
  final categories = <String>{'Bakery', 'Groceries'};
  final dietary = <String>{};
  @override
  Widget build(BuildContext context) {
    const cats = [
      'Bakery',
      'Groceries',
      'Fruit & veg',
      'Café',
      'Meals',
      'Household',
    ];
    const diets = ['Halal', 'Vegetarian', 'Vegan', 'Gluten-free'];
    return OnboardingScaffold(
      step: 4,
      title: 'What are you interested in?',
      subtitle: 'Pick a few so your first feed feels useful.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Categories', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: cats
                .map(
                  (x) => FilterChip(
                    label: Text(x),
                    selected: categories.contains(x),
                    onSelected: (v) => setState(
                      () => v ? categories.add(x) : categories.remove(x),
                    ),
                  ),
                )
                .toList(),
          ),
          const SizedBox(height: 28),
          Text(
            'Dietary preferences',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: diets
                .map(
                  (x) => FilterChip(
                    label: Text(x),
                    selected: dietary.contains(x),
                    onSelected: (v) =>
                        setState(() => v ? dietary.add(x) : dietary.remove(x)),
                  ),
                )
                .toList(),
          ),
        ],
      ),
      action: FilledButton(
        onPressed: categories.isEmpty
            ? null
            : () async {
                await ref
                    .read(appControllerProvider)
                    .updateInterests(categories.toList(), dietary.toList());
                if (context.mounted) context.go('/location');
              },
        child: const Text('Continue'),
      ),
    );
  }
}

class LocationScreen extends ConsumerWidget {
  const LocationScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = ref.watch(appControllerProvider);
    Future<void> finish(bool location) async {
      await app.finishOnboarding(demoMarket: !location, useLocation: location);
      if (context.mounted && app.onboarded) context.go('/');
    }

    return OnboardingScaffold(
      step: 5,
      title: 'Find offers around you',
      subtitle:
          'We save only a broad area, never your exact coordinates or location history.',
      child: Column(
        children: [
          Container(
            height: 190,
            decoration: BoxDecoration(
              color: context.tokens.primary.withValues(alpha: .1),
              borderRadius: BorderRadius.circular(24),
            ),
            child: Stack(
              children: [
                Center(
                  child: Icon(
                    Icons.map_outlined,
                    size: 100,
                    color: context.tokens.primary.withValues(alpha: .35),
                  ),
                ),
                Center(
                  child: Container(
                    width: 66,
                    height: 66,
                    decoration: BoxDecoration(
                      color: context.tokens.primary.withValues(alpha: .18),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      Icons.location_on_rounded,
                      size: 36,
                      color: context.tokens.primary,
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (app.error != null)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: StatusPill(
                text: app.error!,
                icon: Icons.error_outline,
                color: context.tokens.error,
              ),
            ),
          const SizedBox(height: 20),
          const InfoLabel(
            icon: Icons.lock_outline,
            text:
                'Precise coordinates are used once to find your area, then discarded.',
          ),
        ],
      ),
      action: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!app.demoMarketLink) ...[
            FilledButton.icon(
              onPressed: app.busy ? null : () => finish(true),
              icon: app.busy
                  ? const SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.near_me_outlined),
              label: const Text('Use my location'),
            ),
            const SizedBox(height: 10),
            OutlinedButton(
              onPressed: app.busy ? null : () => finish(false),
              child: const Text('Join Demo Market instead'),
            ),
          ] else
            FilledButton.icon(
              onPressed: app.busy ? null : () => finish(false),
              icon: const Icon(Icons.storefront_outlined),
              label: const Text('Join Demo Market'),
            ),
        ],
      ),
    );
  }
}
