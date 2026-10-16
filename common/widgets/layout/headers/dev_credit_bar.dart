import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:intl/intl.dart';

import '../../../../billing/credit_cost.dart';
import '../../../../controllers/dev/api_tracker_controller.dart';

Color _tierColor(ComputeTier? tier) => switch (tier) {
      ComputeTier.free || null => const Color(0xFF888888),
      ComputeTier.veryLow => const Color(0xFF66BBFF),
      ComputeTier.low => const Color(0xFF00CC66),
      ComputeTier.medium => const Color(0xFFFFAA00),
      ComputeTier.veryHigh => const Color(0xFFFF4444),
    };

/// Displays a compact API-credit tracking bar at the bottom of THeader.
/// Only rendered in [kDebugMode] builds — completely absent in release.
class DevCreditBar extends StatelessWidget {
  const DevCreditBar({super.key});

  @override
  Widget build(BuildContext context) {
    if (!kDebugMode) return const SizedBox.shrink();

    final tracker = Get.find<ApiTrackerController>();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final barBg = isDark ? const Color(0xFF1A1A2E) : const Color(0xFF0D0D1A);
    final accentColor = const Color(0xFF00FF88);

    return Obx(() {
      if (!tracker.isVisible.value) {
        return Align(
          alignment: Alignment.centerRight,
          child: GestureDetector(
            onTap: tracker.toggleVisibility,
            child: Container(
              margin: const EdgeInsets.only(right: 4, bottom: 2),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: barBg,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text('⚡ DEV',
                  style: TextStyle(
                      color: accentColor,
                      fontSize: 9,
                      fontFamily: 'monospace')),
            ),
          ),
        );
      }

      return Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // ── Compact summary bar ──────────────────────────────────────────
          GestureDetector(
            onTap: tracker.togglePanel,
            child: Container(
              color: barBg,
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
              child: Row(
                children: [
                  Text('⚡ DEV CREDITS',
                      style: TextStyle(
                          color: accentColor,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          fontFamily: 'monospace')),
                  const SizedBox(width: 12),
                  Obx(() => Text(
                        'Session: ${tracker.sessionCost.value.toStringAsFixed(1)} cr',
                        style: const TextStyle(
                            color: Color(0xFFFFD700),
                            fontSize: 10,
                            fontFamily: 'monospace'),
                      )),
                  const SizedBox(width: 12),
                  Obx(() => Text(
                        '${tracker.entries.length} calls',
                        style: const TextStyle(
                            color: Colors.white54,
                            fontSize: 10,
                            fontFamily: 'monospace'),
                      )),
                  const Spacer(),
                  if (tracker.entries.isNotEmpty)
                    _LastCallChip(tracker.entries.first),
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: tracker.clearSession,
                    child: const Text('CLEAR',
                        style: TextStyle(
                            color: Colors.redAccent,
                            fontSize: 9,
                            fontFamily: 'monospace')),
                  ),
                  const SizedBox(width: 10),
                  GestureDetector(
                    onTap: tracker.toggleVisibility,
                    child: const Text('HIDE',
                        style: TextStyle(
                            color: Colors.white38,
                            fontSize: 9,
                            fontFamily: 'monospace')),
                  ),
                  const SizedBox(width: 6),
                  Obx(() => Icon(
                        tracker.isPanelExpanded.value
                            ? Icons.expand_less
                            : Icons.expand_more,
                        color: Colors.white38,
                        size: 14,
                      )),
                ],
              ),
            ),
          ),

          // ── Expanded call log panel ──────────────────────────────────────
          Obx(() {
            if (!tracker.isPanelExpanded.value) return const SizedBox.shrink();
            return Container(
              constraints: const BoxConstraints(maxHeight: 200),
              color: const Color(0xFF0A0A18),
              child: tracker.entries.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.all(8),
                      child: Text('No API calls recorded yet.',
                          style: TextStyle(
                              color: Colors.white38,
                              fontSize: 10,
                              fontFamily: 'monospace')),
                    )
                  : ListView.builder(
                      reverse: false,
                      itemCount: tracker.entries.length,
                      itemBuilder: (_, i) =>
                          _CallRow(entry: tracker.entries[i], index: i),
                    ),
            );
          }),
        ],
      );
    });
  }
}

class _LastCallChip extends StatelessWidget {
  const _LastCallChip(this.entry);
  final ApiTrackEntry entry;

  @override
  Widget build(BuildContext context) {
    final costColor = _tierColor(entry.cost?.tier);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
      decoration: BoxDecoration(
        border: Border.all(color: costColor.withOpacity(0.6)),
        borderRadius: BorderRadius.circular(3),
      ),
      child: Text(
        '${entry.method} ${_truncatePath(entry.path, 28)}  [${entry.costLabel}]',
        style:
            TextStyle(color: costColor, fontSize: 9, fontFamily: 'monospace'),
      ),
    );
  }
}

class _CallRow extends StatelessWidget {
  const _CallRow({required this.entry, required this.index});
  final ApiTrackEntry entry;
  final int index;

  @override
  Widget build(BuildContext context) {
    final costColor = _tierColor(entry.cost?.tier);
    final time = DateFormat('HH:mm:ss.SSS').format(entry.timestamp);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(color: Colors.white.withOpacity(0.04)),
        ),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 28,
            child: Text('#${index + 1}',
                style: const TextStyle(
                    color: Colors.white24,
                    fontSize: 9,
                    fontFamily: 'monospace')),
          ),
          SizedBox(
            width: 80,
            child: Text(time,
                style: const TextStyle(
                    color: Colors.white38,
                    fontSize: 9,
                    fontFamily: 'monospace')),
          ),
          SizedBox(
            width: 36,
            child: Text(entry.method,
                style: const TextStyle(
                    color: Color(0xFF88AAFF),
                    fontSize: 9,
                    fontFamily: 'monospace')),
          ),
          Container(
            width: 36,
            padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 1),
            decoration: BoxDecoration(
              color: costColor.withOpacity(0.15),
              borderRadius: BorderRadius.circular(2),
            ),
            child: Text(entry.costLabel,
                style: TextStyle(
                    color: costColor,
                    fontSize: 9,
                    fontFamily: 'monospace')),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              entry.trigger != null
                  ? '${_truncatePath(entry.path, 50)}  ← ${entry.trigger}'
                  : _truncatePath(entry.path, 60),
              style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 9,
                  fontFamily: 'monospace'),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          SizedBox(
            width: 40,
            child: Text(
              '+${entry.creditValue.toStringAsFixed(entry.creditValue == entry.creditValue.roundToDouble() ? 0 : 2)} cr',
              textAlign: TextAlign.right,
              style: TextStyle(
                  color: costColor,
                  fontSize: 9,
                  fontFamily: 'monospace'),
            ),
          ),
        ],
      ),
    );
  }
}

String _truncatePath(String path, int max) =>
    path.length > max ? '…${path.substring(path.length - max + 1)}' : path;
