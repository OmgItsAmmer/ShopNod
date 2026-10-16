import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../core/models.dart';
import '../state/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/shared.dart';

class WalletScreen extends ConsumerWidget {
  const WalletScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = ref.watch(appControllerProvider);
    String money(int v) => 'Rs ${(v / 100).toStringAsFixed(0)}';
    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(
          child: PageFrame(
            maxWidth: 760,
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Your wallet',
                  style: Theme.of(context).textTheme.headlineLarge,
                ),
                const SizedBox(height: 18),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(22),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        context.tokens.primary,
                        context.tokens.primary.withBlue(210),
                      ],
                    ),
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'SAVED THIS MONTH',
                        style: TextStyle(
                          color: Colors.white70,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        money(app.savingsMinor),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 36,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${app.claimItems.where((c) => c.status == ClaimStatus.redeemed).length} redeemed offers',
                        style: const TextStyle(color: Colors.white70),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        if (app.claimItems.isEmpty)
          const SliverFillRemaining(
            child: EmptyState(
              icon: Icons.wallet_outlined,
              title: 'No claimed offers yet',
              message:
                  'Tap “Get offer” on a deal and its QR code will stay here.',
            ),
          )
        else
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
            sliver: SliverList.builder(
              itemCount: app.claimItems.length,
              itemBuilder: (ctx, i) {
                final c = app.claimItems[i];
                final color = c.status == ClaimStatus.redeemed
                    ? context.tokens.success
                    : c.status == ClaimStatus.expired
                    ? context.tokens.error
                    : context.tokens.info;
                return Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 720),
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Card(
                        child: ListTile(
                          onTap: () => context.push('/claim/${c.id}'),
                          contentPadding: const EdgeInsets.all(16),
                          leading: Container(
                            width: 52,
                            height: 52,
                            decoration: BoxDecoration(
                              color: color.withValues(alpha: .12),
                              borderRadius: BorderRadius.circular(15),
                            ),
                            child: Icon(
                              c.status == ClaimStatus.redeemed
                                  ? Icons.check_circle_outline
                                  : Icons.qr_code_rounded,
                              color: color,
                            ),
                          ),
                          title: Text(
                            c.offer.title,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          subtitle: Text(c.offer.shopName),
                          trailing: StatusPill(
                            text: c.status.name.toUpperCase(),
                            icon: c.status == ClaimStatus.redeemed
                                ? Icons.check
                                : Icons.schedule,
                            color: color,
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
      ],
    );
  }
}
