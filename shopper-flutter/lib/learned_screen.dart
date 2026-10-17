import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'state/providers.dart';
import 'theme/app_theme.dart';
import 'widgets/shared.dart';
import 'common/widgets/appbar/appbar.dart';
import 'utils/popups/loaders.dart';

class LearnedScreen extends ConsumerStatefulWidget {
  const LearnedScreen({super.key});
  @override
  ConsumerState<LearnedScreen> createState() => _LearnedScreenState();
}

class _LearnedScreenState extends ConsumerState<LearnedScreen> {
  late Future<Map<String, dynamic>> future;
  @override
  void initState() {
    super.initState();
    future = ref.read(appControllerProvider).affinity();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: const TAppBar(title: Text('What we’ve learned')),
    body: FutureBuilder<Map<String, dynamic>>(
      future: future,
      builder: (ctx, snapshot) {
        if (!snapshot.hasData)
          return const Center(child: CircularProgressIndicator());
        final categories = snapshot.data!['categories'] as List? ?? [];
        return PageFrame(
          maxWidth: 680,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Only broad interests',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 8),
              Text(
                'These scores come from your list, saves and redeemed offers. Older activity counts less.',
                style: TextStyle(color: context.tokens.textMuted),
              ),
              const SizedBox(height: 26),
              for (final raw in categories) ...[
                _affinityRow(context, (raw as Map).cast<String, dynamic>()),
                const SizedBox(height: 16),
              ],
              const Spacer(),
              OutlinedButton.icon(
                onPressed: _reset,
                icon: Icon(Icons.restart_alt, color: context.tokens.error),
                label: Text(
                  'Reset what ShopNod learned',
                  style: TextStyle(color: context.tokens.error),
                ),
              ),
            ],
          ),
        );
      },
    ),
  );
  Widget _affinityRow(BuildContext context, Map<String, dynamic> value) {
    final score = (value['score'] as num).toDouble();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                '${value['name']}',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            Text(
              '${(score * 100).round()}%',
              style: TextStyle(
                color: context.tokens.textMuted,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        LinearProgressIndicator(
          value: score,
          minHeight: 10,
          borderRadius: BorderRadius.circular(99),
          backgroundColor: context.tokens.surfaceMuted,
        ),
      ],
    );
  }

  Future<void> _reset() async {
    await ref.read(appControllerProvider).resetAffinity();
    if (mounted) {
      TLoaders.successSnackBar(
        context,
        title: 'Learning reset',
        message: 'Your explicit interests are unchanged.',
      );
      setState(() => future = Future.value({'categories': <dynamic>[]}));
    }
  }
}
