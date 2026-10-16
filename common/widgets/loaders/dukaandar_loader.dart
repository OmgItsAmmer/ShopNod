import 'package:flutter/material.dart';
import 'package:path_drawing/path_drawing.dart';

/// Brand loader: reproduces the DukaanDar shop-front animation
/// (`assets/loaders/Dukaandar_loader.svg`) natively in Flutter.
///
/// The source SVG drives its slide-in animation with SMIL
/// (`<animateTransform>`), which Flutter's SVG renderers don't play back.
/// So instead of rendering the SVG, the same path data is parsed into real
/// Flutter [Path]s and the same clip-to-static-silhouette + translate trick
/// the SVG uses is replayed with an [AnimationController], matching the
/// original's keyTimes/keySplines frame for frame.
class TDukaandarLoader extends StatefulWidget {
  const TDukaandarLoader({super.key, this.size = 100});

  final double size;

  @override
  State<TDukaandarLoader> createState() => _TDukaandarLoaderState();
}

class _TDukaandarLoaderState extends State<TDukaandarLoader>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2300),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) => CustomPaint(
        size: Size.square(widget.size),
        painter: _DukaandarPainter(_controller.value),
      ),
    );
  }
}

// Matches the SVG's keySplines="0.16 1 0.3 1" ease-out segments.
const Cubic _kSlideSpline = Cubic(0.16, 1.0, 0.3, 1.0);

/// Reproduces one <animateTransform> translate-X track: holds at [from]
/// until [holdEnd0] (fraction of the loop), eases to [to] by [holdEnd1],
/// then holds at [to] for the remainder — same as the SVG's keyTimes.
double _slideX(double t, double holdEnd0, double holdEnd1, double from, double to) {
  if (t <= holdEnd0) return from;
  if (t >= holdEnd1) return to;
  final local = (t - holdEnd0) / (holdEnd1 - holdEnd0);
  return from + (to - from) * _kSlideSpline.transform(local);
}

class _DukaandarPainter extends CustomPainter {
  _DukaandarPainter(this.t);

  final double t;

  static const double _viewBox = 1080;
  static const Rect _panelRect = Rect.fromLTWH(232, 234, 616, 604);
  static final RRect _panel = RRect.fromRectAndRadius(_panelRect, const Radius.circular(114));

  static final Path _dCore = (parseSvgPathData(_dCoreData)..fillType = PathFillType.evenOdd);
  static final Path _unit1 = (parseSvgPathData(_unit1Data)..fillType = PathFillType.evenOdd);
  static final Path _unit2 = (parseSvgPathData(_unit2Data)..fillType = PathFillType.evenOdd);
  static final Path _unit3 = (parseSvgPathData(_unit3Data)..fillType = PathFillType.evenOdd);

  static final Paint _white = Paint()..color = Colors.white;
  static final Paint _shadow = Paint()
    ..color = const Color(0x29028BCF)
    ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 7);
  static final Paint _panelPaint = Paint()
    ..shader = const LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFF22AEF4), Color(0xFF13A9F3)],
    ).createShader(_panelRect);

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / _viewBox, size.height / _viewBox);

    canvas.drawRRect(_panel.shift(const Offset(0, 5)), _shadow);
    canvas.drawRRect(_panel, _panelPaint);

    canvas.drawPath(_dCore, _white);
    canvas.drawPath(_unit1, _white);

    // Second bay: 0.0-0.3s hold off-screen, 0.3-0.8s slides in, then holds.
    final dx2 = _slideX(t, 0.1304, 0.3478, 150, 0);
    canvas.save();
    canvas.clipPath(_unit2);
    canvas.translate(dx2, 0);
    canvas.drawPath(_unit2, _white);
    canvas.restore();

    // Third bay: 0.8-1.3s hold off-screen, 1.3-1.8s slides in, then holds.
    final dx3 = _slideX(t, 0.5652, 0.7826, 220, 0);
    canvas.save();
    canvas.clipPath(_unit3);
    canvas.translate(dx3, 0);
    canvas.drawPath(_unit3, _white);
    canvas.restore();

    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _DukaandarPainter oldDelegate) => oldDelegate.t != t;
}

const String _dCoreData =
    'M 527 380 L 527 394 L 557 394 L 559 396 L 557 407 L 555 411 L 554 420 L 550 432 L 549 441 L 544 458 L 544 463 L 539 481 L 535 504 L 533 506 L 527 506 L 527 542 L 529 537 L 532 536 L 537 546 L 545 553 L 553 556 L 566 556 L 567 555 L 570 555 L 579 550 L 585 543 L 587 539 L 589 532 L 590 511 L 591 510 L 591 497 L 592 496 L 592 479 L 593 478 L 593 464 L 594 463 L 594 450 L 595 449 L 595 433 L 596 432 L 596 419 L 597 418 L 597 398 L 600 394 L 633 394 L 635 396 L 635 427 L 636 428 L 658 428 L 659 429 L 663 429 L 672 432 L 680 437 L 689 446 L 692 451 L 696 462 L 697 472 L 698 473 L 698 587 L 697 588 L 697 597 L 695 602 L 694 610 L 692 616 L 683 632 L 675 640 L 668 645 L 660 649 L 654 651 L 645 652 L 644 653 L 628 653 L 627 654 L 534 654 L 533 653 L 533 575 L 529 576 L 527 578 L 527 711 L 645 711 L 646 710 L 660 710 L 661 709 L 668 709 L 669 708 L 687 705 L 704 699 L 716 693 L 737 678 L 737 677 L 745 670 L 756 656 L 763 645 L 767 635 L 769 633 L 772 622 L 774 619 L 777 601 L 778 600 L 779 577 L 780 576 L 780 497 L 779 496 L 779 481 L 778 480 L 777 469 L 772 451 L 762 431 L 753 418 L 745 410 L 731 399 L 729 399 L 714 390 L 691 383 L 674 382 L 673 381 L 652 381 L 651 380 Z';

const String _unit1Data =
    'M 470 575 L 469 576 L 469 711 L 541 711 L 541 654 L 534 654 L 533 653 L 533 575 L 529 576 L 525 581 L 491 613 L 491 696 L 490 697 L 473 697 L 472 696 L 472 575 Z M 515 381 L 517 390 L 506 424 L 506 427 L 503 434 L 503 437 L 499 447 L 499 450 L 496 457 L 496 460 L 493 467 L 493 470 L 490 477 L 487 490 L 480 506 L 479 514 L 476 520 L 474 528 L 472 531 L 471 537 L 472 536 L 474 537 L 477 544 L 481 549 L 485 552 L 495 556 L 508 556 L 516 553 L 526 544 L 530 536 L 533 537 L 533 539 L 537 546 L 542 551 L 549 555 L 552 555 L 553 556 L 566 556 L 567 555 L 570 555 L 576 552 L 582 547 L 587 539 L 589 532 L 590 511 L 591 510 L 591 497 L 592 496 L 592 479 L 593 478 L 594 450 L 595 449 L 595 433 L 596 432 L 596 419 L 597 418 L 597 398 L 600 394 L 613 394 L 613 380 L 524 380 L 523 381 Z M 557 394 L 559 396 L 559 398 L 558 399 L 558 403 L 555 411 L 554 420 L 551 428 L 549 441 L 544 458 L 544 463 L 539 481 L 535 504 L 533 506 L 483 506 L 482 503 L 490 484 L 492 475 L 494 472 L 497 461 L 501 453 L 501 450 L 505 441 L 508 430 L 510 427 L 513 416 L 515 413 L 520 396 L 522 394 Z';

const String _unit2Data =
    'M 412 575 L 406 581 L 406 711 L 479 711 L 479 697 L 473 697 L 472 696 L 472 575 L 470 575 L 433 613 L 433 695 L 431 697 L 415 697 L 413 694 L 414 576 Z M 548 380 L 524 380 L 523 381 L 488 381 L 487 380 L 460 381 L 459 380 L 449 380 L 434 389 L 432 402 L 438 394 L 471 394 L 473 396 L 457 427 L 457 429 L 447 448 L 447 450 L 442 458 L 439 467 L 437 469 L 437 471 L 420 506 L 415 506 L 414 508 L 406 543 L 409 543 L 412 537 L 414 536 L 418 543 L 425 551 L 436 556 L 448 556 L 449 555 L 453 555 L 463 549 L 468 543 L 470 538 L 473 536 L 477 522 L 483 508 L 482 503 L 490 484 L 492 475 L 494 472 L 497 461 L 501 453 L 501 450 L 505 441 L 508 430 L 510 427 L 513 416 L 515 413 L 520 396 L 522 394 L 526 394 L 529 390 L 548 381 Z';

const String _unit3Data =
    'M 330 587 L 326 591 L 326 710 L 328 711 L 420 711 L 420 697 L 415 697 L 413 694 L 414 576 L 412 575 L 399 587 L 374 613 L 374 696 L 373 697 L 354 697 L 353 696 L 353 575 L 352 574 L 346 577 L 338 583 Z M 459 380 L 433 380 L 432 381 L 427 381 L 426 380 L 425 381 L 422 381 L 421 380 L 419 381 L 390 380 L 385 383 L 355 424 L 345 436 L 340 444 L 333 452 L 329 459 L 325 463 L 323 467 L 319 471 L 317 475 L 292 507 L 289 516 L 289 530 L 293 541 L 301 550 L 308 554 L 315 556 L 328 556 L 329 555 L 332 555 L 340 551 L 348 543 L 352 536 L 355 537 L 358 544 L 365 551 L 376 556 L 391 556 L 398 553 L 404 549 L 413 536 L 415 537 L 416 540 L 421 546 L 421 542 L 418 542 L 417 541 L 419 535 L 419 530 L 420 529 L 420 525 L 422 519 L 422 514 L 423 513 L 426 494 L 420 506 L 371 506 L 369 503 L 383 482 L 385 477 L 388 474 L 395 461 L 398 458 L 405 445 L 408 442 L 412 434 L 415 431 L 417 426 L 428 410 L 436 396 L 438 394 L 441 394 L 442 392 L 460 382 Z';
