import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:get/get.dart';
import 'package:lottie/lottie.dart';
import '../../../controllers/onboarding/guided_tour_controller.dart';
import '../../../controllers/settings/settings_controller.dart';
import '../../../utils/constants/colors.dart';
import '../../../utils/constants/image_strings.dart';
import '../../../utils/helpers/helper_functions.dart';


// ─────────────────────────────────────────────────────────────────────────────
// Entry point: placed once in AppShell around the main content tree
// ─────────────────────────────────────────────────────────────────────────────

class TutorialSpotlightOverlay extends StatelessWidget {
  final Widget child;
  const TutorialSpotlightOverlay({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final tourCtrl = Get.isRegistered<GuidedTourController>()
        ? Get.find<GuidedTourController>()
        : Get.put(GuidedTourController());

    return Stack(
      children: [
        // Layer 0: Main screen content (never rebuilt by tour state changes)
        child,

        // Layer 1: Tour overlay — only rendered when tour is active
        Obx(() {
          if (!tourCtrl.isTourActive) return const SizedBox.shrink();
          return const _TourOverlayContent();
        }),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal stateful widget that polls for target rect each frame
// ─────────────────────────────────────────────────────────────────────────────

class _TourOverlayContent extends StatefulWidget {
  const _TourOverlayContent();

  @override
  State<_TourOverlayContent> createState() => _TourOverlayContentState();
}

class _TourOverlayContentState extends State<_TourOverlayContent> {
  Rect? _targetRect;
  bool _loopActive = false;

  @override
  void initState() {
    super.initState();
    _startLoop();
  }

  @override
  void dispose() {
    _loopActive = false;
    super.dispose();
  }

  void _startLoop() {
    if (_loopActive) return;
    _loopActive = true;
    WidgetsBinding.instance.addPostFrameCallback((_) => _tick());
  }

  void _tick() {
    if (!mounted || !_loopActive) return;

    final tourCtrl = Get.find<GuidedTourController>();
    if (!tourCtrl.isTourActive) {
      _loopActive = false;
      return;
    }

    final key = tourCtrl.getCurrentTargetKey();
    if (key == null) {
      debugPrint("TourDebug: Key is null");
      if (_targetRect != null) {
        setState(() => _targetRect = null);
      }
    } else {
      final newRect = tourCtrl.getWidgetRect(key);
      debugPrint("TourDebug: Key label = ${key.toString()}, context = ${key.currentContext != null ? 'non-null' : 'null'}, rect = $newRect");
      if (newRect != null && newRect != _targetRect) {
        setState(() => _targetRect = newRect);
      }
    }

    WidgetsBinding.instance.addPostFrameCallback((_) => _tick());
  }

  @override
  Widget build(BuildContext context) {
    final dark = THelperFunctions.isDarkMode(context);
    return Obx(() {
      final tourCtrl = Get.find<GuidedTourController>();

      if (tourCtrl.showWelcomeCard.value) {
        return Stack(
          children: [
            IgnorePointer(
              child: Container(
                color: Colors.black.withValues(alpha: dark ? 0.78 : 0.50),
              ),
            ),
            Positioned.fill(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () {},
              ),
            ),
            Center(
              child: _WelcomeCard(
                onStart: () {
                  tourCtrl.dismissWelcomeCard();
                },
                onSkip: () {
                  tourCtrl.skipAll();
                },
              ),
            ),
          ],
        );
      }

      final step = tourCtrl.getCurrentStep();
      if (step == null) return const SizedBox.shrink();

      final targetRect = _targetRect;

      return TweenAnimationBuilder<Rect?>(
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeOutCubic,
        tween: RectTween(end: targetRect ?? Rect.zero),
        builder: (context, animatedRect, child) {
          final isTargetValid = animatedRect != null && animatedRect != Rect.zero && animatedRect.width > 0;
          final finalRect = isTargetValid ? animatedRect : null;

          return Stack(
            children: [
              // 1. Semi-transparent dim overlay with spotlight cutout
              IgnorePointer(
                child: ClipPath(
                  clipper: InvertedCutoutClipper(finalRect),
                  child: Container(
                    color: Colors.black.withValues(alpha: dark ? 0.78 : 0.50),
                  ),
                ),
              ),

              // 2. Click blocker — absorbs taps outside the spotlight
              Positioned.fill(
                child: _ClickBlocker(
                  targetRect: finalRect,
                  child: GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: () {}, // absorb
                  ),
                ),
              ),

              // 3. Pulsing glow border around target
              if (finalRect != null) _PulsingBorder(targetRect: finalRect),

              // 4. Animated virtual cursor
              if (finalRect != null)
                _AnimatedCursor(targetCenter: finalRect.center),

              // 5. Tour snackbar (appears above everything)
              const _TourSnackBar(),

              // 6. Instruction card — positioned away from target
              _TourCard(
                step: step,
                stepIndex: tourCtrl.currentStepIndex.value,
                totalSteps: tourCtrl.getMaxSteps(step.flowId),
                targetRect: finalRect,
                onNext: tourCtrl.nextStep,
                onBack: tourCtrl.currentStepIndex.value > 0 ? tourCtrl.previousStep : null,
                onSkip: tourCtrl.skipCurrentTutorial,
                onSkipAll: tourCtrl.skipAll,
              ),
            ],
          );
        },
      );
    });
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Onboarding Welcome & Language selection Card
// ─────────────────────────────────────────────────────────────────────────────

class _WelcomeCard extends StatefulWidget {
  final VoidCallback onStart;
  final VoidCallback onSkip;

  const _WelcomeCard({required this.onStart, required this.onSkip});

  @override
  State<_WelcomeCard> createState() => _WelcomeCardState();
}

class _WelcomeCardState extends State<_WelcomeCard> with SingleTickerProviderStateMixin {
  late AnimationController _entranceCtrl;
  late Animation<double> _scale;
  late Animation<double> _opacity;

  @override
  void initState() {
    super.initState();
    _entranceCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _scale = Tween<double>(begin: 0.92, end: 1.0).animate(
      CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOutBack),
    );
    _opacity = CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeIn);
    _entranceCtrl.forward();
  }

  @override
  void dispose() {
    _entranceCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final dark = THelperFunctions.isDarkMode(context);
    final settingsCtrl = Get.find<SettingsController>();
    final locale = settingsCtrl.locale.value;
    final isUrdu = locale.languageCode == 'ur' && locale.countryCode == 'PK';
    final textDirection = isUrdu ? TextDirection.rtl : TextDirection.ltr;

    return Directionality(
      textDirection: textDirection,
      child: FadeTransition(
        opacity: _opacity,
        child: ScaleTransition(
          scale: _scale,
          child: Material(
            color: Colors.transparent,
            child: Container(
              width: 380,
              decoration: BoxDecoration(
                color: dark ? const Color(0xFF1B1D2A) : Colors.white,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: dark ? Colors.white.withValues(alpha: 0.08) : Colors.grey.shade200,
                  width: 1,
                ),
                boxShadow: [
                  BoxShadow(
                    color: TColors.primary.withValues(alpha: dark ? 0.20 : 0.15),
                    blurRadius: 32,
                    spreadRadius: 0,
                    offset: const Offset(0, 8),
                  ),
                  BoxShadow(
                    color: Colors.black.withValues(alpha: dark ? 0.50 : 0.12),
                    blurRadius: 16,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Header with Lottie animation
                  ClipRRect(
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
                    child: SizedBox(
                      height: 140,
                      child: Stack(
                        children: [
                          Container(
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: dark
                                    ? const [Color(0xFF252837), Color(0xFF1B1D2A)]
                                    : const [Color(0xFFF1F5F9), Color(0xFFE2E8F0)],
                                begin: Alignment.topCenter,
                                end: Alignment.bottomCenter,
                              ),
                            ),
                          ),
                          Center(
                            child: Lottie.asset(
                              TImages.cartAnimation,
                              fit: BoxFit.contain,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                  // Content
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          'welcomeTourTitle'.tr,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: dark ? Colors.white : const Color(0xFF1E293B),
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          'welcomeTourBody'.tr,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 13,
                            height: 1.6,
                            color: dark ? const Color(0xFF9CA3AF) : Colors.grey.shade600,
                          ),
                        ),
                        const SizedBox(height: 20),

                        // Language prompt label
                        Row(
                          children: [
                            Expanded(
                              child: Divider(
                                color: dark ? Colors.white10 : Colors.grey.shade200,
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 8),
                              child: Text(
                                'welcomeTourLanguagePrompt'.tr,
                                style: TextStyle(
                                  fontSize: 11,
                                  color: dark ? Colors.white38 : Colors.grey.shade500,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                            Expanded(
                              child: Divider(
                                color: dark ? Colors.white10 : Colors.grey.shade200,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),

                        // Language selector chips
                        Obx(() {
                          final locale = settingsCtrl.locale.value;
                          final String selectedCode;
                          if (locale.languageCode == 'ur' && locale.countryCode == 'PK') {
                            selectedCode = 'ur';
                          } else if (locale.languageCode == 'ur' && locale.countryCode == 'Latn') {
                            selectedCode = 'roman';
                          } else {
                            selectedCode = 'en';
                          }

                          return Row(
                            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                            children: [
                              _buildLanguageChip(
                                label: 'English',
                                isSelected: selectedCode == 'en',
                                dark: dark,
                                onTap: () => settingsCtrl.changeLocale('en', 'US'),
                              ),
                              _buildLanguageChip(
                                label: 'اردو',
                                isSelected: selectedCode == 'ur',
                                dark: dark,
                                onTap: () => settingsCtrl.changeLocale('ur', 'PK'),
                              ),
                              _buildLanguageChip(
                                label: 'Roman',
                                isSelected: selectedCode == 'roman',
                                dark: dark,
                                onTap: () => settingsCtrl.changeLocale('ur', 'Latn'),
                              ),
                            ],
                          );
                        }),
                        const SizedBox(height: 24),

                        // Start Tour Button
                        SizedBox(
                          height: 48,
                          child: ElevatedButton(
                            onPressed: widget.onStart,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: TColors.primary,
                              foregroundColor: TColors.white,
                              elevation: 2,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text(
                                  'startTour'.tr,
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 0.5,
                                  ),
                                ),
                                const SizedBox(width: 6),
                                const Icon(Icons.arrow_forward_rounded, size: 16),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),

                        // Skip Button
                        TextButton(
                          onPressed: widget.onSkip,
                          child: Text(
                            'skipTourAll'.tr,
                            style: TextStyle(
                              color: dark ? Colors.white38 : Colors.grey.shade500,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLanguageChip({
    required String label,
    required bool isSelected,
    required bool dark,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected
              ? TColors.primary
              : (dark ? Colors.transparent : Colors.grey.shade100),
          borderRadius: BorderRadius.circular(30),
          border: Border.all(
            color: isSelected
                ? TColors.primary
                : (dark ? Colors.white24 : Colors.grey.shade300),
            width: 1.5,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected
                ? Colors.white
                : (dark ? const Color(0xFF9CA3AF) : Colors.grey.shade700),
            fontWeight: FontWeight.bold,
            fontSize: 12,
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tour instruction card with animations
// ─────────────────────────────────────────────────────────────────────────────


class _TourCard extends StatefulWidget {
  final TutorialStep step;
  final int stepIndex;
  final int totalSteps;
  final Rect? targetRect;
  final VoidCallback onNext;
  final VoidCallback? onBack;
  final VoidCallback onSkip;
  final VoidCallback onSkipAll;

  const _TourCard({
    required this.step,
    required this.stepIndex,
    required this.totalSteps,
    required this.targetRect,
    required this.onNext,
    required this.onBack,
    required this.onSkip,
    required this.onSkipAll,
  });

  @override
  State<_TourCard> createState() => _TourCardState();
}

class _TourCardState extends State<_TourCard> with TickerProviderStateMixin {
  late AnimationController _entranceCtrl;
  late AnimationController _stepChangeCtrl;
  late Animation<double> _fadeIn;
  late Animation<Offset> _slideIn;
  late Animation<double> _contentFade;

  int _displayedStepIndex = -1;
  TutorialStep? _displayedStep;

  @override
  void initState() {
    super.initState();

    _entranceCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 350),
    );
    _stepChangeCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 220),
    );

    _fadeIn = CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOut);
    _slideIn = Tween<Offset>(
      begin: const Offset(0, 0.08),
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOutCubic));

    _contentFade = Tween<double>(begin: 1.0, end: 0.0).animate(
      CurvedAnimation(parent: _stepChangeCtrl, curve: Curves.easeIn),
    );

    _displayedStepIndex = widget.stepIndex;
    _displayedStep = widget.step;
    _entranceCtrl.forward();
  }

  @override
  void didUpdateWidget(covariant _TourCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.step.flowId != widget.step.flowId) {
      if (mounted) {
        setState(() {
          _displayedStepIndex = widget.stepIndex;
          _displayedStep = widget.step;
        });
        _entranceCtrl.forward(from: 0.0);
      }
    } else if (oldWidget.stepIndex != widget.stepIndex) {
      _stepChangeCtrl.forward(from: 0).then((_) {
        if (mounted) {
          setState(() {
            _displayedStepIndex = widget.stepIndex;
            _displayedStep = widget.step;
          });
          _stepChangeCtrl.reverse();
        }
      });
    }
  }

  @override
  void dispose() {
    _entranceCtrl.dispose();
    _stepChangeCtrl.dispose();
    super.dispose();
  }

  Positioned _buildPositioned({required Widget child}) {
    const cardWidth = 340.0;
    const cardPadding = 16.0;
    const cardGap = 20.0;
    final screenSize = MediaQuery.sizeOf(context);
    final targetRect = widget.targetRect;

    double? top, bottom, left;
    double maxHeight;

    if (targetRect == null) {
      top = screenSize.height * 0.3;
      left = (screenSize.width - cardWidth) / 2;
      maxHeight = screenSize.height * 0.6;
    } else {
      final centerY = targetRect.center.dy;
      final clampedBottom = targetRect.bottom.clamp(0.0, screenSize.height);
      final clampedTop = targetRect.top.clamp(0.0, screenSize.height);

      if (centerY < screenSize.height * 0.55) {
        // Card goes below the target
        top = clampedBottom + cardGap;
        maxHeight = (screenSize.height - top - cardPadding).clamp(100.0, screenSize.height);
      } else {
        // Card goes above the target
        bottom = (screenSize.height - clampedTop) + cardGap;
        maxHeight = (clampedTop - cardGap - cardPadding).clamp(100.0, screenSize.height);
      }

      left = (targetRect.center.dx - cardWidth / 2)
          .clamp(cardPadding, screenSize.width - cardWidth - cardPadding);
    }

    return Positioned(
      left: left,
      top: top,
      bottom: bottom,
      width: cardWidth,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: maxHeight),
        child: child,
      ),
    );
  }

  String _getLottiePath(TutorialFlowId flowId) {
    switch (flowId) {
      case TutorialFlowId.product:
        return TImages.cartAnimation;
      case TutorialFlowId.purchase:
        return TImages.packageAnimation;
      case TutorialFlowId.invoice:
        return TImages.paymentSuccessfulAnimation;
      case TutorialFlowId.report:
        return TImages.searchAnimation;
      default:
        return TImages.cartAnimation;
    }
  }

  @override
  Widget build(BuildContext context) {
    final dark = THelperFunctions.isDarkMode(context);
    final step = _displayedStep ?? widget.step;
    final stepIndex = _displayedStepIndex;
    final animPath = _getLottiePath(step.flowId);

    final locale = Get.locale;
    final isUrdu = locale?.languageCode == 'ur' && locale?.countryCode == 'PK';
    final textDirection = isUrdu ? TextDirection.rtl : TextDirection.ltr;

    return _buildPositioned(
      child: Directionality(
        textDirection: textDirection,
        child: FadeTransition(
          opacity: _fadeIn,
          child: SlideTransition(
            position: _slideIn,
            child: FadeTransition(
              opacity: _contentFade,
              child: Material(
                color: Colors.transparent,
                child: Container(
                  decoration: BoxDecoration(
                    color: dark ? const Color(0xFF1B1D2A) : Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: dark ? Colors.white.withValues(alpha: 0.06) : Colors.grey.shade200,
                      width: 1.0,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: TColors.primary.withValues(alpha: dark ? 0.20 : 0.15),
                        blurRadius: 32,
                        spreadRadius: 0,
                        offset: const Offset(0, 8),
                      ),
                      BoxShadow(
                        color: Colors.black.withValues(alpha: dark ? 0.50 : 0.12),
                        blurRadius: 16,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: SingleChildScrollView(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // Top Lottie Media Header
                        ClipRRect(
                          borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
                          child: SizedBox(
                            height: 90,
                            child: Stack(
                              children: [
                                Container(
                                  decoration: BoxDecoration(
                                    gradient: LinearGradient(
                                      colors: dark
                                          ? const [Color(0xFF252837), Color(0xFF1B1D2A)]
                                          : const [Color(0xFFF1F5F9), Color(0xFFE2E8F0)],
                                      begin: Alignment.topCenter,
                                      end: Alignment.bottomCenter,
                                    ),
                                  ),
                                ),
                                Center(
                                  child: Lottie.asset(animPath, fit: BoxFit.contain),
                                ),
                                // Close Button (✕) top-right
                                Positioned(
                                  top: 6,
                                  right: 6,
                                  child: GestureDetector(
                                    onTap: widget.onSkip,
                                    child: Container(
                                      width: 28,
                                      height: 28,
                                      decoration: BoxDecoration(
                                        color: dark
                                            ? Colors.white.withValues(alpha: 0.12)
                                            : Colors.black.withValues(alpha: 0.06),
                                        shape: BoxShape.circle,
                                      ),
                                      child: Icon(
                                        Icons.close_rounded,
                                        size: 15,
                                        color: dark ? Colors.white70 : Colors.black54,
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),

                        // Step title row
                        Padding(
                          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                          child: Row(
                            children: [
                              Container(
                                width: 7,
                                height: 7,
                                decoration: const BoxDecoration(
                                  color: TColors.primary,
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  step.title.tr,
                                  style: TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.bold,
                                    color: dark ? Colors.white : const Color(0xFF1E293B),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),

                        // Instruction body
                        Padding(
                          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                          child: Text(
                            step.instruction.tr,
                            style: TextStyle(
                              fontSize: 12.5,
                              height: 1.6,
                              color: dark ? const Color(0xFF9CA3AF) : Colors.grey.shade600,
                            ),
                          ),
                        ),

                        // Step progress Dots
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: List.generate(widget.totalSteps, (i) {
                            final active = i == stepIndex;
                            return AnimatedContainer(
                              duration: const Duration(milliseconds: 250),
                              margin: const EdgeInsets.symmetric(horizontal: 3),
                              width: active ? 18 : 6,
                              height: 6,
                              decoration: BoxDecoration(
                                color: active
                                    ? TColors.primary
                                    : (dark ? Colors.white24 : Colors.grey.shade300),
                                borderRadius: BorderRadius.circular(4),
                              ),
                            );
                          }),
                        ),
                        const SizedBox(height: 12),

                        Divider(
                          height: 1,
                          color: dark ? Colors.white10 : Colors.grey.shade200,
                        ),

                        // Button and Actions Section
                        Padding(
                          padding: const EdgeInsets.all(12.0),
                          child: Row(
                            children: [
                              TextButton(
                                onPressed: widget.onSkipAll,
                                style: TextButton.styleFrom(
                                  padding: const EdgeInsets.symmetric(horizontal: 8),
                                  minimumSize: Size.zero,
                                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                ),
                                child: Text(
                                  'skipAll'.tr,
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: dark ? Colors.white30 : Colors.grey.shade500,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                              const Spacer(),
                              if (widget.onBack != null) ...[
                                TextButton(
                                  onPressed: widget.onBack,
                                  style: TextButton.styleFrom(
                                    padding: const EdgeInsets.symmetric(horizontal: 12),
                                    minimumSize: Size.zero,
                                  ),
                                  child: Text(
                                    'back'.tr,
                                    style: TextStyle(
                                      color: dark ? Colors.white38 : Colors.grey.shade600,
                                      fontSize: 12,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                                if (!step.isActionStep) const SizedBox(width: 8),
                              ],
                              if (!step.isActionStep)
                                SizedBox(
                                  height: 36,
                                  child: ElevatedButton(
                                    onPressed: () {
                                      if (step.isCompleted != null && !step.isCompleted!()) {
                                        Get.find<GuidedTourController>().showTourSnackBar(
                                          'validation'.tr,
                                          _validationMessage(),
                                          backgroundColor: Colors.orange.shade700,
                                          icon: Icons.warning_rounded,
                                        );
                                        return;
                                      }
                                      widget.onNext();
                                    },
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: TColors.primary,
                                      foregroundColor: TColors.white,
                                      elevation: 2,
                                      padding: const EdgeInsets.symmetric(horizontal: 16),
                                      minimumSize: Size.zero,
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(10),
                                      ),
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Text(
                                          'next'.tr,
                                          style: const TextStyle(
                                            fontWeight: FontWeight.bold,
                                            fontSize: 12,
                                          ),
                                        ),
                                        const SizedBox(width: 4),
                                        const Icon(Icons.arrow_forward_rounded, size: 14),
                                      ],
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  String _validationMessage() {
    final localeStr = Get.locale?.toString() ?? 'en';
    if (localeStr.startsWith('ur')) {
      return 'براہ کرم نمایاں کردہ فیلڈ کو پہلے پُر کریں۔';
    }
    return 'Please fill out the highlighted field correctly first.';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tour snackbar (floats above the overlay)
// ─────────────────────────────────────────────────────────────────────────────

class _TourSnackBar extends StatelessWidget {
  const _TourSnackBar();

  @override
  Widget build(BuildContext context) {
    final tourCtrl = Get.find<GuidedTourController>();

    return Obx(() {
      if (!tourCtrl.isTourSnackBarVisible.value) return const SizedBox.shrink();

      return Positioned(
        top: 40,
        left: 16,
        right: 16,
        child: Material(
          color: Colors.transparent,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 250),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: tourCtrl.tourSnackBarColor.value,
                  borderRadius: BorderRadius.circular(10),
                  boxShadow: const [
                    BoxShadow(
                      color: Colors.black26,
                      blurRadius: 10,
                      offset: Offset(0, 4),
                    ),
                  ],
                ),
                child: Row(
                  children: [
                    Icon(tourCtrl.tourSnackBarIcon.value,
                        color: Colors.white, size: 22),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (tourCtrl.tourSnackBarTitle.value.isNotEmpty)
                            Text(
                              tourCtrl.tourSnackBarTitle.value.tr,
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                                fontSize: 13,
                              ),
                            ),
                          if (tourCtrl.tourSnackBarMessage.value.isNotEmpty) ...[
                            const SizedBox(height: 2),
                            Text(
                              tourCtrl.tourSnackBarMessage.value.tr,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, color: Colors.white, size: 18),
                      onPressed: () =>
                          tourCtrl.isTourSnackBarVisible.value = false,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    });
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Spotlight clipper — cuts a rounded hole for the target widget
// ─────────────────────────────────────────────────────────────────────────────

class InvertedCutoutClipper extends CustomClipper<Path> {
  final Rect? targetRect;
  InvertedCutoutClipper(this.targetRect);

  @override
  Path getClip(Size size) {
    final base = Path()..addRect(Rect.fromLTWH(0, 0, size.width, size.height));
    if (targetRect == null) return base;

    final cutout = Path()
      ..addRRect(RRect.fromRectAndRadius(
        targetRect!.inflate(10.0),
        const Radius.circular(10.0),
      ));
    return Path.combine(PathOperation.difference, base, cutout);
  }

  @override
  bool shouldReclip(covariant InvertedCutoutClipper old) =>
      old.targetRect != targetRect;
}

// ─────────────────────────────────────────────────────────────────────────────
// Click blocker — blocks taps outside spotlight but passes through inside
// ─────────────────────────────────────────────────────────────────────────────

class _ClickBlocker extends SingleChildRenderObjectWidget {
  final Rect? targetRect;
  const _ClickBlocker({required this.targetRect, super.child});

  @override
  _RenderClickBlocker createRenderObject(BuildContext context) =>
      _RenderClickBlocker(targetRect);

  @override
  void updateRenderObject(BuildContext context, _RenderClickBlocker r) =>
      r.targetRect = targetRect;
}

class _RenderClickBlocker extends RenderProxyBox {
  Rect? _targetRect;
  _RenderClickBlocker(this._targetRect);

  Rect? get targetRect => _targetRect;
  set targetRect(Rect? v) {
    if (_targetRect != v) {
      _targetRect = v;
      markNeedsPaint();
    }
  }

  @override
  bool hitTest(BoxHitTestResult result, {required Offset position}) {
    if (_targetRect == null) {
      return false; // Let clicks pass through for instruction-only/dialog steps
    }
    if (_targetRect!.inflate(10.0).contains(position)) {
      return false; // Let clicks pass through inside spotlight
    }
    return true; // Block clicks outside spotlight
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Pulsing glow border around the highlighted target
// ─────────────────────────────────────────────────────────────────────────────

class _PulsingBorder extends StatefulWidget {
  final Rect targetRect;
  const _PulsingBorder({required this.targetRect});

  @override
  State<_PulsingBorder> createState() => _PulsingBorderState();
}

class _PulsingBorderState extends State<_PulsingBorder>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _glow;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    )..repeat(reverse: true);

    _glow = Tween<double>(begin: 2.0, end: 12.0).animate(
      CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const inflate = 10.0;
    return Positioned(
      left: widget.targetRect.left - inflate,
      top: widget.targetRect.top - inflate,
      width: widget.targetRect.width + inflate * 2,
      height: widget.targetRect.height + inflate * 2,
      child: IgnorePointer(
        child: AnimatedBuilder(
          animation: _glow,
          builder: (_, __) => Container(
            decoration: BoxDecoration(
              border: Border.all(
                color: TColors.primary.withValues(alpha: 0.85),
                width: 1.5,
              ),
              borderRadius: BorderRadius.circular(12),
              boxShadow: [
                BoxShadow(
                  color: TColors.primary.withValues(alpha: 0.40),
                  blurRadius: _glow.value,
                  spreadRadius: _glow.value / 6,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Animated virtual cursor — moves smoothly to new targets
// ─────────────────────────────────────────────────────────────────────────────

class _AnimatedCursor extends StatefulWidget {
  final Offset targetCenter;
  const _AnimatedCursor({required this.targetCenter});

  @override
  State<_AnimatedCursor> createState() => _AnimatedCursorState();
}

class _AnimatedCursorState extends State<_AnimatedCursor>
    with TickerProviderStateMixin {
  late AnimationController _moveCtrl;
  late AnimationController _pulseCtrl;
  late Animation<Offset> _position;
  late Animation<double> _pulse;

  @override
  void initState() {
    super.initState();

    _moveCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    );
    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat();

    _position = Tween<Offset>(
      begin: widget.targetCenter,
      end: widget.targetCenter,
    ).animate(CurvedAnimation(parent: _moveCtrl, curve: Curves.easeOutCubic));

    _pulse = CurvedAnimation(parent: _pulseCtrl, curve: Curves.linear);

    _moveCtrl.forward();
  }

  @override
  void didUpdateWidget(covariant _AnimatedCursor old) {
    super.didUpdateWidget(old);
    if (old.targetCenter != widget.targetCenter) {
      final start = _position.value;
      _position = Tween<Offset>(begin: start, end: widget.targetCenter).animate(
        CurvedAnimation(parent: _moveCtrl, curve: Curves.easeOutCubic),
      );
      _moveCtrl.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _moveCtrl.dispose();
    _pulseCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const double maxRadius = 52.0;

    return AnimatedBuilder(
      animation: Listenable.merge([_moveCtrl, _pulseCtrl]),
      builder: (_, __) {
        final pos = _position.value;
        final t = _pulse.value;

        // Staggered ring properties
        // Ring 3 (Outer): starts after 0.3 delay, expands to 1.0 scale, fades out
        double scale3 = 0.0;
        double opacity3 = 0.0;
        if (t > 0.3) {
          final progress3 = (t - 0.3) / 0.7;
          scale3 = 0.4 + (0.6 * progress3);
          opacity3 = 0.15 * (1.0 - progress3);
        }

        // Ring 2 (Mid): starts at 0.0, expands to 1.0 scale, fades out
        final scale2 = 0.3 + (0.7 * t);
        final opacity2 = 0.30 * (1.0 - t);

        // Ring 1 (Inner): breathes gently
        final scale1 = 0.9 + 0.15 * (1.0 - (t - 0.5).abs() * 2);

        return Positioned(
          left: pos.dx - (maxRadius / 2),
          top: pos.dy - (maxRadius / 2),
          child: IgnorePointer(
            child: SizedBox(
              width: maxRadius,
              height: maxRadius,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  // Ring 3 (Outer)
                  if (opacity3 > 0)
                    Transform.scale(
                      scale: scale3,
                      child: Container(
                        width: maxRadius,
                        height: maxRadius,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: TColors.primary.withValues(alpha: opacity3),
                            width: 1.5,
                          ),
                        ),
                      ),
                    ),

                  // Ring 2 (Mid)
                  if (opacity2 > 0)
                    Transform.scale(
                      scale: scale2,
                      child: Container(
                        width: maxRadius * 0.7,
                        height: maxRadius * 0.7,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: TColors.primary.withValues(alpha: opacity2),
                            width: 1.5,
                          ),
                        ),
                      ),
                    ),

                  // Ring 1 (Inner)
                  Transform.scale(
                    scale: scale1,
                    child: Container(
                      width: maxRadius * 0.4,
                      height: maxRadius * 0.4,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: TColors.primary,
                          width: 2.0,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: TColors.primary.withValues(alpha: 0.4),
                            blurRadius: 4,
                            spreadRadius: 1,
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
