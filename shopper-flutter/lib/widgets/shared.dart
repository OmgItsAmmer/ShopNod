import 'package:flutter/material.dart';
import '../core/models.dart';
import '../l10n/app_strings.dart';
import '../theme/app_theme.dart';

class AppLogo extends StatelessWidget {
  const AppLogo({super.key, this.compact = false});
  final bool compact;
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: compact ? 38 : 46,
        height: compact ? 38 : 46,
        decoration: BoxDecoration(
          color: context.tokens.primary,
          borderRadius: BorderRadius.circular(14),
        ),
        child: const Icon(Icons.local_offer_rounded, color: Colors.white),
      ),
      const SizedBox(width: 10),
      Text(
        'shopnod',
        style: Theme.of(
          context,
        ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
      ),
    ],
  );
}

class PageFrame extends StatelessWidget {
  const PageFrame({
    super.key,
    required this.child,
    this.maxWidth = 720,
    this.padding = const EdgeInsets.all(20),
  });
  final Widget child;
  final double maxWidth;
  final EdgeInsets padding;
  @override
  Widget build(BuildContext context) => Center(
    child: ConstrainedBox(
      constraints: BoxConstraints(maxWidth: maxWidth),
      child: Padding(padding: padding, child: child),
    ),
  );
}

class InfoLabel extends StatelessWidget {
  const InfoLabel({
    super.key,
    required this.icon,
    required this.text,
    this.color,
  });
  final IconData icon;
  final String text;
  final Color? color;
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, size: 15, color: color ?? context.tokens.info),
      const SizedBox(width: 5),
      Flexible(
        child: Text(
          text,
          style: Theme.of(
            context,
          ).textTheme.bodySmall?.copyWith(color: context.tokens.textMuted),
        ),
      ),
    ],
  );
}

class StatusPill extends StatelessWidget {
  const StatusPill({
    super.key,
    required this.text,
    required this.icon,
    required this.color,
  });
  final String text;
  final IconData icon;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
    decoration: BoxDecoration(
      color: color.withValues(alpha: .12),
      borderRadius: BorderRadius.circular(999),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: color),
        const SizedBox(width: 6),
        Text(
          text,
          style: TextStyle(
            color: context.tokens.text,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    ),
  );
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
    this.action,
  });
  final IconData icon;
  final String title, message;
  final Widget? action;
  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: context.tokens.primary.withValues(alpha: .12),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: context.tokens.primary, size: 34),
          ),
          const SizedBox(height: 18),
          Text(
            title,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: TextStyle(color: context.tokens.textMuted, height: 1.45),
          ),
          if (action != null) ...[const SizedBox(height: 20), action!],
        ],
      ),
    ),
  );
}

class OfferCard extends StatefulWidget {
  const OfferCard({
    super.key,
    required this.offer,
    required this.onTap,
    required this.onWhy,
    required this.onDismiss,
    required this.onLongPress,
  });
  final Offer offer;
  final VoidCallback onTap, onWhy, onDismiss, onLongPress;
  @override
  State<OfferCard> createState() => _OfferCardState();
}

class _OfferCardState extends State<OfferCard> {
  bool hover = false;
  String money(int minor) =>
      'Rs ${(minor / 100).toStringAsFixed(minor % 100 == 0 ? 0 : 2)}';
  @override
  Widget build(BuildContext context) {
    final o = widget.offer;
    final l = AppStrings.of(context);
    final mins = o.endsAt.difference(DateTime.now()).inMinutes.clamp(0, 999);
    return Dismissible(
      key: ValueKey(o.id),
      direction: DismissDirection.endToStart,
      confirmDismiss: (_) async {
        widget.onDismiss();
        return false;
      },
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 28),
        decoration: BoxDecoration(
          color: context.tokens.error,
          borderRadius: BorderRadius.circular(24),
        ),
        child: const Icon(Icons.thumb_down_alt_outlined, color: Colors.white),
      ),
      child: MouseRegion(
        onEnter: (_) => setState(() => hover = true),
        onExit: (_) => setState(() => hover = false),
        child: AnimatedScale(
          scale: hover ? 1.008 : 1,
          duration: const Duration(milliseconds: 150),
          child: Card(
            child: InkWell(
              borderRadius: BorderRadius.circular(24),
              onTap: widget.onTap,
              onLongPress: widget.onLongPress,
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 13,
                            vertical: 9,
                          ),
                          decoration: BoxDecoration(
                            color: context.tokens.highlight,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Text(
                            '${o.discountPct}%\nOFF',
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                              color: Color(0xFF272727),
                              fontSize: 17,
                              height: 1.05,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                o.title,
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
                              const SizedBox(height: 3),
                              Text(
                                o.shopName,
                                style: TextStyle(
                                  color: context.tokens.textMuted,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Icon(
                          Icons.chevron_right_rounded,
                          color: context.tokens.icon,
                        ),
                      ],
                    ),
                    const SizedBox(height: 17),
                    Wrap(
                      crossAxisAlignment: WrapCrossAlignment.center,
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        Text(
                          money(o.wasPrice),
                          style: TextStyle(
                            color: context.tokens.textMuted,
                            decoration: TextDecoration.lineThrough,
                          ),
                        ),
                        Text(
                          money(o.nowPrice),
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        Text(
                          '· ${o.distanceM < 1000 ? '${o.distanceM} m' : '${(o.distanceM / 1000).toStringAsFixed(1)} km'}',
                          style: TextStyle(color: context.tokens.textMuted),
                        ),
                        Text(
                          '· ${l.t('ends')} $mins min',
                          style: TextStyle(
                            color: mins < 60
                                ? context.tokens.warning
                                : context.tokens.textMuted,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    InkWell(
                      onTap: widget.onWhy,
                      borderRadius: BorderRadius.circular(9),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: InfoLabel(
                          icon: Icons.auto_awesome_outlined,
                          text: o.why,
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 14,
                      runSpacing: 6,
                      children: [
                        if (o.copySource == 'ai')
                          InfoLabel(
                            icon: Icons.auto_awesome,
                            text: l.t('aiLabel'),
                          ),
                        if (o.source == 'rules')
                          StatusPill(
                            text: l.t('rules'),
                            icon: Icons.rule_rounded,
                            color: context.tokens.icon,
                          ),
                        InfoLabel(
                          icon: Icons.people_outline_rounded,
                          text: l.t('samePrice'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
