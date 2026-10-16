import 'dart:async';
import 'package:confetti/confetti.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../core/models.dart';
import '../state/app_controller.dart';
import '../state/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/shared.dart';

class ClaimScreen extends ConsumerStatefulWidget {
  const ClaimScreen({super.key, required this.id});
  final String id;
  @override
  ConsumerState<ClaimScreen> createState() => _ClaimScreenState();
}

class _ClaimScreenState extends ConsumerState<ClaimScreen> {
  Timer? timer;
  late final ConfettiController confetti;
  bool celebrated = false;
  @override
  void initState() {
    super.initState();
    confetti = ConfettiController(duration: const Duration(seconds: 2));
    timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    confetti.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final app = ref.watch(appControllerProvider);
    final matches = app.claimItems.where((c) => c.id == widget.id);
    if (matches.isEmpty)
      return const Scaffold(
        body: EmptyState(
          icon: Icons.qr_code_2,
          title: 'Claim unavailable',
          message: 'Return to your wallet and try again.',
        ),
      );
    final c = matches.first;
    if (c.status == ClaimStatus.redeemed && !celebrated) {
      celebrated = true;
      WidgetsBinding.instance.addPostFrameCallback((_) => confetti.play());
    }
    final left = c.expiresAt.difference(DateTime.now());
    final expired = left.isNegative;
    final mm = left.inMinutes.clamp(0, 99).toString().padLeft(2, '0');
    final ss = (left.inSeconds % 60).clamp(0, 59).toString().padLeft(2, '0');
    return Scaffold(
      appBar: AppBar(title: const Text('Your offer')),
      body: Stack(
        alignment: Alignment.topCenter,
        children: [
          SingleChildScrollView(
            child: PageFrame(
              maxWidth: 620,
              child: Column(
                children: [
                  if (c.status == ClaimStatus.redeemed) ...[
                    const SizedBox(height: 20),
                    StatusPill(
                      text: 'Redeemed!',
                      icon: Icons.check_circle,
                      color: context.tokens.success,
                    ),
                    const SizedBox(height: 14),
                    Text(
                      'You saved Rs ${(c.savedMinor / 100).toStringAsFixed(0)}',
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Nice one — and less food went to waste.',
                      style: TextStyle(color: context.tokens.textMuted),
                    ),
                    const SizedBox(height: 28),
                  ] else ...[
                    Text(
                      'Show this at ${c.offer.shopName}',
                      style: Theme.of(context).textTheme.headlineMedium,
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'The shop scans it once at checkout.',
                      style: TextStyle(color: context.tokens.textMuted),
                    ),
                    const SizedBox(height: 24),
                  ],
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(color: const Color(0xFFD9D9D9)),
                    ),
                    child: Opacity(
                      opacity: c.status == ClaimStatus.redeemed || expired
                          ? .45
                          : 1,
                      child: QrImageView(
                        data: c.qrPayload,
                        size: 240,
                        backgroundColor: Colors.white,
                        eyeStyle: const QrEyeStyle(color: Colors.black),
                        dataModuleStyle: const QrDataModuleStyle(
                          color: Colors.black,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    c.shortCode,
                    style: TextStyle(
                      fontSize: 38,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 7,
                      color: context.tokens.text,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Use this code if the camera can’t scan',
                    style: TextStyle(color: context.tokens.textMuted),
                  ),
                  const SizedBox(height: 20),
                  if (c.status == ClaimStatus.issued && !expired)
                    StatusPill(
                      text: 'Expires in $mm:$ss',
                      icon: Icons.timer_outlined,
                      color: context.tokens.info,
                    )
                  else if (expired)
                    StatusPill(
                      text: 'Expired',
                      icon: Icons.timer_off_outlined,
                      color: context.tokens.error,
                    ),
                  const SizedBox(height: 24),
                  OutlinedButton.icon(
                    onPressed: () {
                      Clipboard.setData(ClipboardData(text: c.qrPayload));
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('QR text copied.')),
                      );
                    },
                    icon: const Icon(Icons.copy),
                    label: const Text('Copy QR text'),
                  ),
                  if (AppController.apiUrl.isEmpty &&
                      c.status == ClaimStatus.issued) ...[
                    const SizedBox(height: 12),
                    TextButton.icon(
                      onPressed: () => app.simulateRedemption(c.id),
                      icon: const Icon(Icons.bolt),
                      label: const Text('Demo: simulate shop scan'),
                    ),
                  ],
                ],
              ),
            ),
          ),
          ConfettiWidget(
            confettiController: confetti,
            blastDirectionality: BlastDirectionality.explosive,
            colors: [
              context.tokens.primary,
              context.tokens.highlight,
              context.tokens.focusRing,
            ],
            numberOfParticles: 28,
          ),
        ],
      ),
    );
  }
}
