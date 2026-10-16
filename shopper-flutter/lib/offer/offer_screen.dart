import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../state/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/shared.dart';
import '../why/why_sheet.dart';
import '../common/widgets/appbar/appbar.dart';

class OfferScreen extends ConsumerWidget {
  const OfferScreen({super.key, required this.id});
  final String id;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = ref.watch(appControllerProvider);
    final matches = app.offers.where((o) => o.id == id);
    if (matches.isEmpty)
      return const Scaffold(
        body: EmptyState(
          icon: Icons.search_off,
          title: 'Offer unavailable',
          message: 'It may have ended or sold out.',
        ),
      );
    final o = matches.first;
    String money(int v) =>
        'Rs ${(v / 100).toStringAsFixed(v % 100 == 0 ? 0 : 2)}';
    final mins = o.endsAt.difference(DateTime.now()).inMinutes.clamp(0, 999);
    return Scaffold(
      appBar: TAppBar(title: Text(o.shopName)),
      body: SingleChildScrollView(
        child: PageFrame(
          maxWidth: 720,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                height: 210,
                decoration: BoxDecoration(
                  color: context.tokens.primary.withValues(alpha: .12),
                  borderRadius: BorderRadius.circular(28),
                ),
                child: Stack(
                  children: [
                    Center(
                      child: Icon(
                        Icons.shopping_bag_outlined,
                        size: 100,
                        color: context.tokens.primary.withValues(alpha: .45),
                      ),
                    ),
                    Positioned(
                      top: 18,
                      left: 18,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 11,
                        ),
                        decoration: BoxDecoration(
                          color: context.tokens.highlight,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Text(
                          '${o.discountPct}% OFF',
                          style: const TextStyle(
                            color: Color(0xFF272727),
                            fontWeight: FontWeight.w900,
                            fontSize: 20,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              Text(o.title, style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 6),
              Text(
                o.shopName,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: context.tokens.textMuted,
                ),
              ),
              const SizedBox(height: 18),
              Row(
                children: [
                  Text(
                    money(o.wasPrice),
                    style: TextStyle(
                      fontSize: 18,
                      color: context.tokens.textMuted,
                      decoration: TextDecoration.lineThrough,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    money(o.nowPrice),
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const Spacer(),
                  StatusPill(
                    text: '$mins min',
                    icon: Icons.schedule,
                    color: mins < 60
                        ? context.tokens.warning
                        : context.tokens.info,
                  ),
                ],
              ),
              const SizedBox(height: 22),
              Text(o.description, style: Theme.of(context).textTheme.bodyLarge),
              const SizedBox(height: 20),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: o.tags
                    .map(
                      (x) => Chip(
                        label: Text(x),
                        avatar: const Icon(Icons.check, size: 16),
                      ),
                    )
                    .toList(),
              ),
              const SizedBox(height: 24),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      InkWell(
                        onTap: () => showWhySheet(context, o),
                        child: Row(
                          children: [
                            Expanded(
                              child: InfoLabel(
                                icon: Icons.auto_awesome_outlined,
                                text: o.why,
                              ),
                            ),
                            const Icon(Icons.chevron_right),
                          ],
                        ),
                      ),
                      const SizedBox(height: 13),
                      InfoLabel(
                        icon: Icons.people_outline,
                        text: 'Everyone sees the same price',
                      ),
                      if (o.copySource == 'ai') ...[
                        const SizedBox(height: 9),
                        const InfoLabel(
                          icon: Icons.auto_awesome,
                          text: 'AI-written, approved by the shop',
                        ),
                      ],
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 26),
              FilledButton.icon(
                onPressed: app.busy
                    ? null
                    : () async {
                        final claim = await app.claim(o);
                        if (context.mounted && claim != null)
                          context.pushReplacement('/claim/${claim.id}');
                      },
                icon: app.busy
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 2,
                        ),
                      )
                    : const Icon(Icons.qr_code_rounded),
                label: Text(app.busy ? 'Getting your offer…' : 'Get offer'),
              ),
              const SizedBox(height: 10),
              Text(
                '${o.remaining} left · Claim expires after 30 minutes',
                textAlign: TextAlign.center,
                style: TextStyle(color: context.tokens.textMuted),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
