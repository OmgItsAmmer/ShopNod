import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../core/models.dart';
import '../state/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/shared.dart';
import '../why/why_sheet.dart';
import '../common/widgets/shimmers/shimmer.dart';
import '../utils/constants/sizes.dart';

class FeedScreen extends ConsumerWidget {
  const FeedScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final app = ref.watch(appControllerProvider);
    return RefreshIndicator(
      onRefresh: () => app.refresh(),
      child: CustomScrollView(
        key: const PageStorageKey('feed'),
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverToBoxAdapter(
            child: PageFrame(
              maxWidth: 820,
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'For you',
                          style: Theme.of(context).textTheme.headlineLarge,
                        ),
                        const SizedBox(height: 5),
                        Text(
                          'Fresh offers from Demo Market',
                          style: TextStyle(color: context.tokens.textMuted),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: context.tokens.highlight,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: const Row(
                      children: [
                        Icon(
                          Icons.bolt_rounded,
                          color: Color(0xFF272727),
                          size: 18,
                        ),
                        SizedBox(width: 4),
                        Text(
                          'LIVE',
                          style: TextStyle(
                            color: Color(0xFF272727),
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (app.offline || app.lastUpdated != null)
            SliverToBoxAdapter(
              child: PageFrame(
                maxWidth: 820,
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 14),
                child: InfoLabel(
                  icon: app.offline
                      ? Icons.cloud_off_outlined
                      : Icons.refresh_rounded,
                  text: app.offline
                      ? 'Offline · showing saved offers'
                      : 'Updated just now',
                ),
              ),
            ),
          if (app.busy && app.offers.isEmpty)
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
              sliver: SliverList.builder(
                itemCount: 3,
                itemBuilder: (context, i) => Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 780),
                    child: const Padding(
                      padding: EdgeInsets.only(bottom: 14),
                      child: TShimmerEffect(
                        width: double.infinity,
                        height: 190,
                        radius: TSizes.cardRadiusLg,
                      ),
                    ),
                  ),
                ),
              ),
            )
          else if (app.error != null && app.offers.isEmpty)
            SliverFillRemaining(
              child: EmptyState(
                icon: Icons.wifi_off_rounded,
                title: 'Couldn’t load offers',
                message: app.error!,
                action: FilledButton(
                  onPressed: () => app.refresh(),
                  child: const Text('Try again'),
                ),
              ),
            )
          else if (app.offers.isEmpty)
            const SliverFillRemaining(
              child: EmptyState(
                icon: Icons.search_off_rounded,
                title: 'No matching offers yet',
                message: 'Pull to refresh, or widen your distance in Settings.',
              ),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
              sliver: SliverList.builder(
                itemCount: app.offers.length,
                itemBuilder: (context, i) {
                  final o = app.offers[i];
                  return Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 780),
                      child: Padding(
                        padding: const EdgeInsets.only(bottom: 14),
                        child: OfferCard(
                          offer: o,
                          onTap: () => context.push('/offer/${o.id}'),
                          onWhy: () => showWhySheet(context, o),
                          onDismiss: () => _dismiss(context, app, o),
                          onLongPress: () => _mute(context, app, o),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }

  void _dismiss(BuildContext context, dynamic app, Offer o) =>
      showModalBottomSheet(
        context: context,
        showDragHandle: true,
        builder: (ctx) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Not for you?', style: Theme.of(ctx).textTheme.titleLarge),
                const SizedBox(height: 8),
                Text(
                  'Tell us why. This feedback disappears after 30 days.',
                  style: TextStyle(color: ctx.tokens.textMuted),
                ),
                const SizedBox(height: 16),
                for (final r in [
                  'Not interested',
                  'Too far away',
                  'Already bought it',
                ])
                  ListTile(
                    title: Text(r),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () {
                      Navigator.pop(ctx);
                      app.dismissOffer(o, r);
                    },
                  ),
              ],
            ),
          ),
        ),
      );
  void _mute(BuildContext context, dynamic app, Offer o) =>
      showModalBottomSheet(
        context: context,
        showDragHandle: true,
        builder: (ctx) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ListTile(
                  leading: const Icon(Icons.storefront_outlined),
                  title: Text('Mute ${o.shopName}'),
                  subtitle: const Text('Hide all offers from this shop'),
                  onTap: () {
                    Navigator.pop(ctx);
                    app.muteShop(o);
                  },
                ),
                ListTile(
                  leading: const Icon(Icons.category_outlined),
                  title: Text('Mute ${o.category}'),
                  subtitle: const Text('Hide this category'),
                  onTap: () {
                    Navigator.pop(ctx);
                    app.muteCategory(o);
                  },
                ),
              ],
            ),
          ),
        ),
      );
}
