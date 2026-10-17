import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../l10n/app_strings.dart';
import '../state/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/shared.dart';
import 'feed_screen.dart';
import 'list_screen.dart';
import 'settings_screen.dart';
import 'wallet_screen.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});
  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  int index = 0;
  @override
  Widget build(BuildContext context) {
    final app = ref.watch(appControllerProvider);
    final l = AppStrings.of(context);
    final wide = MediaQuery.sizeOf(context).width >= 900;
    final pages = [
      const FeedScreen(),
      const ListScreen(),
      const WalletScreen(),
      const SettingsScreen(),
    ];
    final destinations = [
      NavigationDestination(
        icon: const Icon(Icons.explore_outlined),
        selectedIcon: const Icon(Icons.explore_rounded),
        label: l.t('forYou'),
      ),
      NavigationDestination(
        icon: const Icon(Icons.list_alt_outlined),
        selectedIcon: const Icon(Icons.list_alt_rounded),
        label: l.t('list'),
      ),
      NavigationDestination(
        icon: const Icon(Icons.wallet_outlined),
        selectedIcon: const Icon(Icons.wallet_rounded),
        label: l.t('wallet'),
      ),
      NavigationDestination(
        icon: const Icon(Icons.settings_outlined),
        selectedIcon: const Icon(Icons.settings_rounded),
        label: l.t('settings'),
      ),
    ];
    Widget content = IndexedStack(index: index, children: pages);
    if (wide)
      content = Row(
        children: [
          NavigationRail(
            selectedIndex: index,
            onDestinationSelected: (v) => setState(() => index = v),
            extended: MediaQuery.sizeOf(context).width >= 1180,
            leading: const Padding(
              padding: EdgeInsets.fromLTRB(10, 18, 10, 28),
              child: AppLogo(compact: true),
            ),
            destinations: destinations
                .map(
                  (d) => NavigationRailDestination(
                    icon: d.icon,
                    selectedIcon: d.selectedIcon,
                    label: Text(d.label),
                  ),
                )
                .toList(),
          ),
          VerticalDivider(width: 1, color: context.tokens.border),
          Expanded(child: content),
        ],
      );
    return Scaffold(
      body: SafeArea(child: content),
      bottomNavigationBar: wide
          ? null
          : NavigationBar(
              selectedIndex: index,
              onDestinationSelected: (v) => setState(() => index = v),
              destinations: destinations,
            ),
      floatingActionButton: app.offline
          ? FloatingActionButton.extended(
              onPressed: () => app.refresh(),
              icon: const Icon(Icons.cloud_off_outlined),
              label: const Text('Offline'),
            )
          : null,
    );
  }
}
