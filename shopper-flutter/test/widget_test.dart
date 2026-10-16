// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter_test/flutter_test.dart';
import 'package:shopnod_shopper/core/models.dart';

void main() {
  test('consent serialization keeps every purpose separate', () {
    const c = Consents(
      location: false,
      notifications: true,
      list: false,
      personalisation: true,
      analytics: false,
    );
    expect(c.toJson(), containsPair('location', false));
    expect(c.toJson(), containsPair('notifications', true));
    expect(c.toJson(), containsPair('policy_version', '1.0'));
  });
  test('preferences use contract defaults', () {
    const p = Preferences();
    expect(p.maxDistanceM, 800);
    expect(p.dailyLimit, 3);
    expect(p.quietStart, '21:00');
    expect(p.quietEnd, '08:00');
  });
}
