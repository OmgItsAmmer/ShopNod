import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/models.dart';
import '../state/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/shared.dart';
import '../utils/popups/loaders.dart';

void showWhySheet(BuildContext context, Offer offer) => showModalBottomSheet(
  context: context,
  showDragHandle: true,
  isScrollControlled: true,
  builder: (_) => WhySheet(offer: offer),
);

class WhySheet extends ConsumerStatefulWidget {
  const WhySheet({super.key, required this.offer});
  final Offer offer;
  @override
  ConsumerState<WhySheet> createState() => _WhySheetState();
}

class _WhySheetState extends ConsumerState<WhySheet> {
  bool? vote;
  @override
  Widget build(BuildContext context) => SafeArea(
    child: Padding(
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: context.tokens.info.withValues(alpha: .12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  Icons.auto_awesome_outlined,
                  color: context.tokens.info,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Text(
                  'Why you see this',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
            ],
          ),
          const SizedBox(height: 22),
          Text(widget.offer.why, style: Theme.of(context).textTheme.bodyLarge),
          const SizedBox(height: 16),
          InfoLabel(
            icon: widget.offer.source == 'ai'
                ? Icons.auto_awesome
                : Icons.rule_rounded,
            text: widget.offer.source == 'ai'
                ? 'AI matched this offer using only your choices, distance band, and time of day.'
                : 'A simple rule matched this offer. No AI was used.',
          ),
          const SizedBox(height: 22),
          Text(
            'Was this useful?',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _vote(true),
                  icon: Icon(
                    vote == true ? Icons.thumb_up : Icons.thumb_up_outlined,
                  ),
                  label: const Text('Yes'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _vote(false),
                  icon: Icon(
                    vote == false
                        ? Icons.thumb_down
                        : Icons.thumb_down_outlined,
                  ),
                  label: const Text('No'),
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );
  void _vote(bool value) {
    setState(() => vote = value);
    ref.read(appControllerProvider).sendFeedback(widget.offer, value);
    TLoaders.successSnackBar(context, title: 'Thanks — feedback saved.');
  }
}
