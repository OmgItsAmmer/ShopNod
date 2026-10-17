import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../state/app_controller.dart';
import '../state/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/shared.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = ref.watch(appControllerProvider);
    return ListView(
      padding: const EdgeInsets.only(bottom: 100),
      children: [
        PageFrame(
          maxWidth: 760,
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Settings',
                style: Theme.of(context).textTheme.headlineLarge,
              ),
              const SizedBox(height: 5),
              Text(
                'Privacy, preferences and notifications',
                style: TextStyle(color: context.tokens.textMuted),
              ),
            ],
          ),
        ),
        _section(context, 'DISCOVERY', [
          ListTile(
            leading: const Icon(Icons.social_distance_rounded),
            title: const Text('Maximum distance'),
            subtitle: Text('${app.preferences.maxDistanceM} metres'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _distance(context, app),
          ),
          ListTile(
            leading: const Icon(Icons.notifications_active_outlined),
            title: const Text('Daily notification limit'),
            subtitle: Text(
              '${app.preferences.dailyLimit} per day · quiet 21:00–08:00',
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _daily(context, app),
          ),
          ListTile(
            leading: const Icon(Icons.language_rounded),
            title: const Text('Language'),
            subtitle: Text(
              {
                'en': 'English',
                'ur': 'اردو',
                'ar': 'العربية',
                'es': 'Español',
              }[app.language]!,
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _language(context, app),
          ),
        ]),
        _section(context, 'YOUR PRIVACY', [
          SwitchListTile(
            secondary: const Icon(Icons.location_on_outlined),
            title: const Text('Location'),
            subtitle: const Text('Use your broad area for nearby deals'),
            value: app.consents.location,
            onChanged: (v) => app.saveSettings(
              app.preferences,
              app.consents.copyWith(location: v),
            ),
          ),
          SwitchListTile(
            secondary: const Icon(Icons.notifications_none),
            title: const Text('Notifications'),
            subtitle: const Text('Matching offer alerts'),
            value: app.consents.notifications,
            onChanged: (v) => app.saveSettings(
              app.preferences,
              app.consents.copyWith(notifications: v),
            ),
          ),
          SwitchListTile(
            secondary: const Icon(Icons.list_alt),
            title: const Text('Shopping list'),
            subtitle: const Text('Stored for up to 30 days'),
            value: app.consents.list,
            onChanged: (v) => app.saveSettings(
              app.preferences,
              app.consents.copyWith(list: v),
            ),
          ),
          SwitchListTile(
            secondary: const Icon(Icons.auto_awesome_outlined),
            title: const Text('Personalisation'),
            subtitle: const Text('Otherwise offers sort by distance only'),
            value: app.consents.personalisation,
            onChanged: (v) => app.saveSettings(
              app.preferences,
              app.consents.copyWith(personalisation: v),
            ),
          ),
        ]),
        _section(context, 'DATA & CONTROL', [
          ListTile(
            leading: const Icon(Icons.psychology_alt_outlined),
            title: const Text('What we’ve learned'),
            subtitle: const Text('View or reset category affinity'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push('/learned'),
          ),
          ListTile(
            leading: const Icon(Icons.folder_shared_outlined),
            title: const Text('My data'),
            subtitle: const Text('Export or delete everything'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push('/my-data'),
          ),
        ]),
        Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              const AppLogo(compact: true),
              const SizedBox(height: 10),
              Text(
                AppController.apiUrl.isEmpty
                    ? 'Demo mode · no server required'
                    : 'Connected securely',
                style: TextStyle(color: context.tokens.textMuted),
              ),
              const SizedBox(height: 4),
              Text(
                'ShopNod Shopper 1.0.0',
                style: TextStyle(color: context.tokens.textMuted),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _section(BuildContext c, String title, List<Widget> children) =>
      PageFrame(
        maxWidth: 760,
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(4, 0, 4, 9),
              child: Text(
                title,
                style: TextStyle(
                  color: c.tokens.textMuted,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1,
                ),
              ),
            ),
            Card(
              child: Column(
                children: [
                  for (int i = 0; i < children.length; i++) ...[
                    children[i],
                    if (i < children.length - 1)
                      Divider(height: 1, indent: 64, color: c.tokens.border),
                  ],
                ],
              ),
            ),
          ],
        ),
      );
  void _distance(BuildContext c, dynamic app) {
    double v = app.preferences.maxDistanceM.toDouble();
    showModalBottomSheet(
      context: c,
      showDragHandle: true,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, set) => Padding(
          padding: const EdgeInsets.fromLTRB(24, 4, 24, 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Maximum distance',
                style: Theme.of(ctx).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              Text(
                '${v.round()} metres',
                textAlign: TextAlign.center,
                style: Theme.of(ctx).textTheme.headlineMedium,
              ),
              Slider(
                value: v,
                min: 250,
                max: 3000,
                divisions: 11,
                label: '${v.round()} m',
                onChanged: (x) => set(() => v = x),
              ),
              FilledButton(
                onPressed: () {
                  app.saveSettings(
                    app.preferences.copyWith(maxDistanceM: v.round()),
                    app.consents,
                  );
                  Navigator.pop(ctx);
                },
                child: const Text('Save'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _daily(BuildContext c, dynamic app) {
    showModalBottomSheet(
      context: c,
      showDragHandle: true,
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Daily limit', style: Theme.of(ctx).textTheme.titleLarge),
            const SizedBox(height: 12),
            for (final n in [1, 2, 3, 5, 10])
              RadioListTile<int>(
                value: n,
                groupValue: app.preferences.dailyLimit,
                title: Text('$n notification${n == 1 ? '' : 's'} per day'),
                onChanged: (v) {
                  app.saveSettings(
                    app.preferences.copyWith(dailyLimit: v),
                    app.consents,
                  );
                  Navigator.pop(ctx);
                },
              ),
          ],
        ),
      ),
    );
  }

  void _language(BuildContext c, dynamic app) {
    showModalBottomSheet(
      context: c,
      showDragHandle: true,
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final e in {
              'en': 'English',
              'ur': 'اردو',
              'ar': 'العربية',
              'es': 'Español',
            }.entries)
              RadioListTile(
                value: e.key,
                groupValue: app.language,
                title: Text(e.value),
                onChanged: (v) {
                  app.chooseLanguage(v);
                  Navigator.pop(ctx);
                },
              ),
          ],
        ),
      ),
    );
  }
}
