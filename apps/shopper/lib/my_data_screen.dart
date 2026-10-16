import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'state/app_controller.dart';
import 'state/providers.dart';
import 'theme/app_theme.dart';
import 'widgets/shared.dart';

class MyDataScreen extends ConsumerWidget {
  const MyDataScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = ref.read(appControllerProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('My data')),
      body: PageFrame(
        maxWidth: 680,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Your data belongs to you',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Export a readable JSON copy or permanently delete your anonymous profile.',
              style: TextStyle(color: context.tokens.textMuted),
            ),
            const SizedBox(height: 26),
            _DataCard(
              icon: Icons.file_download_outlined,
              color: context.tokens.primary,
              title: 'Export my data',
              body:
                  'Includes consent history, preferences, list, claims, events and notifications.',
              action: FilledButton.tonalIcon(
                onPressed: () => _export(context, app),
                icon: const Icon(Icons.download),
                label: const Text('Create export'),
              ),
            ),
            const SizedBox(height: 16),
            _DataCard(
              icon: Icons.delete_forever_outlined,
              color: context.tokens.error,
              title: 'Delete my data',
              body:
                  'This cannot be undone. Completed redemption totals stay anonymous for shop billing.',
              action: OutlinedButton.icon(
                onPressed: () => _delete(context, app),
                icon: Icon(Icons.delete_outline, color: context.tokens.error),
                label: Text(
                  'Delete everything',
                  style: TextStyle(color: context.tokens.error),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _export(BuildContext context, AppController app) async {
    final data = await app.exportData();
    final text = const JsonEncoder.withIndent('  ').convert(data);
    if (!context.mounted) return;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Your ShopNod data'),
        content: SizedBox(
          width: 600,
          child: SingleChildScrollView(child: SelectableText(text)),
        ),
        actions: [
          TextButton.icon(
            onPressed: () {
              Clipboard.setData(ClipboardData(text: text));
              ScaffoldMessenger.of(
                ctx,
              ).showSnackBar(const SnackBar(content: Text('Export copied.')));
            },
            icon: const Icon(Icons.copy),
            label: const Text('Copy'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Done'),
          ),
        ],
      ),
    );
  }

  Future<void> _delete(BuildContext context, AppController app) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete everything?'),
        content: const Text(
          'Your install token will stop working and all shopper data will be permanently removed.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: context.tokens.error,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete permanently'),
          ),
        ],
      ),
    );
    if (yes == true) {
      await app.deleteMe();
      if (context.mounted) context.go('/age');
    }
  }
}

class _DataCard extends StatelessWidget {
  const _DataCard({
    required this.icon,
    required this.color,
    required this.title,
    required this.body,
    required this.action,
  });
  final IconData icon;
  final Color color;
  final String title, body;
  final Widget action;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 32),
          const SizedBox(height: 12),
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          Text(body),
          const SizedBox(height: 18),
          action,
        ],
      ),
    ),
  );
}
