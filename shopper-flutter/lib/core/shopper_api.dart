import 'dart:math';
import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';
import 'models.dart';

class FriendlyException implements Exception {
  FriendlyException(this.message);
  final String message;
  @override
  String toString() => message;
}

abstract class ShopperApi {
  Future<Map<String, String>> install(String language);
  Future<void> saveConsents(Consents value);
  Future<void> savePreferences(Preferences value, String language);
  Future<void> saveLocation({double? lat, double? lng, String? market});
  Future<List<Offer>> feed(String language);
  Future<Claim> claim(Offer offer, String key);
  Future<List<Claim>> claims();

  /// Live status of one claim: `{status: issued|redeemed|expired, saved_minor: int}`.
  Future<Map<String, dynamic>> claimStatus(String claimId);
  Future<void> saveList(List<String> items);
  Future<void> event(String type, Offer offer, {String? reason});
  Future<Map<String, dynamic>> affinity();
  Future<void> resetAffinity();
  Future<Map<String, dynamic>> exportData();
  Future<void> deleteMe();
}

class RemoteShopperApi implements ShopperApi {
  RemoteShopperApi(String baseUrl, String? token)
    : _dio = Dio(
        BaseOptions(
          baseUrl: baseUrl.replaceAll(RegExp(r'/$'), ''),
          connectTimeout: const Duration(seconds: 8),
          receiveTimeout: const Duration(seconds: 12),
          headers: token == null ? {} : {'Authorization': 'Bearer $token'},
        ),
      ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onError: (e, h) {
          final data = e.response?.data;
          final message = data is Map
              ? ((data['error'] as Map?)?['message'] ?? data['detail'])
              : null;
          h.reject(
            DioException(
              requestOptions: e.requestOptions,
              error: FriendlyException(
                '${message ?? 'We couldn’t reach ShopNod. Please try again.'}',
              ),
            ),
          );
        },
      ),
    );
  }
  final Dio _dio;
  void token(String token) =>
      _dio.options.headers['Authorization'] = 'Bearer $token';
  @override
  Future<Map<String, String>> install(String language) async {
    final r = await _dio.post(
      '/v1/shopper/installs',
      data: {
        'platform': 'flutter',
        'languages': [language],
        'age_confirmed': true,
      },
    );
    return {
      'id': '${r.data['install_id']}',
      'token': '${r.data['install_token']}',
    };
  }

  @override
  Future<void> saveConsents(Consents v) async =>
      _dio.put('/v1/shopper/consents', data: v.toJson());
  @override
  Future<void> savePreferences(Preferences v, String l) async =>
      _dio.put('/v1/shopper/preferences', data: v.toJson(l));
  @override
  Future<void> saveLocation({double? lat, double? lng, String? market}) async =>
      _dio.post(
        '/v1/shopper/location',
        data: market != null ? {'market': market} : {'lat': lat, 'lng': lng},
      );
  @override
  Future<List<Offer>> feed(String language) async {
    final r = await _dio.get(
      '/v1/shopper/feed',
      queryParameters: {'lang': language},
    );
    final list = r.data is List ? r.data as List : r.data['items'] as List;
    return list.map((e) => Offer.fromJson((e as Map).cast())).toList();
  }

  @override
  Future<Claim> claim(Offer o, String key) async {
    final r = await _dio.post(
      '/v1/shopper/offers/${o.id}/claim',
      options: Options(headers: {'Idempotency-Key': key}),
    );
    final d = r.data;
    return Claim(
      id: '${d['claim_id']}',
      offer: o,
      qrPayload: '${d['qr_payload']}',
      shortCode: '${d['short_code']}',
      expiresAt: DateTime.parse(d['expires_at']),
      status: ClaimStatus.issued,
    );
  }

  @override
  Future<List<Claim>> claims() async => []; // hydrated locally; feed details are needed to render cards
  @override
  Future<Map<String, dynamic>> claimStatus(String claimId) async =>
      ((await _dio.get('/v1/shopper/claims/$claimId')).data as Map)
          .cast<String, dynamic>();
  @override
  Future<void> saveList(List<String> i) async =>
      _dio.put('/v1/shopper/list', data: {'items': i});
  @override
  Future<void> event(String t, Offer o, {String? reason}) async => _dio.post(
    '/v1/shopper/events',
    data: {'type': t, 'offer_id': o.id, if (reason != null) 'reason': reason},
  );
  @override
  Future<Map<String, dynamic>> affinity() async =>
      (await _dio.get('/v1/shopper/affinity')).data;
  @override
  Future<void> resetAffinity() async => _dio.delete('/v1/shopper/affinity');
  @override
  Future<Map<String, dynamic>> exportData() async =>
      (await _dio.get('/v1/shopper/me/export')).data;
  @override
  Future<void> deleteMe() async => _dio.delete('/v1/shopper/me');
}

class DemoShopperApi implements ShopperApi {
  final _uuid = const Uuid();
  final List<Claim> _claims = [];
  @override
  Future<Map<String, String>> install(String l) async => {
    'id': _uuid.v7(),
    'token': 'demo.${_uuid.v4()}',
  };
  @override
  Future<void> saveConsents(Consents v) async {}
  @override
  Future<void> savePreferences(Preferences v, String l) async {}
  @override
  Future<void> saveLocation({double? lat, double? lng, String? market}) async {}
  @override
  Future<void> saveList(List<String> i) async {}
  @override
  Future<void> event(String t, Offer o, {String? reason}) async {}
  @override
  Future<Map<String, dynamic>> affinity() async => {
    'categories': [
      {'name': 'Bakery', 'score': .92},
      {'name': 'Groceries', 'score': .74},
      {'name': 'Fruit & veg', 'score': .51},
    ],
    'updated_at': DateTime.now().toIso8601String(),
  };
  @override
  Future<void> resetAffinity() async {}
  @override
  Future<void> deleteMe() async {
    _claims.clear();
  }

  @override
  Future<Map<String, dynamic>> exportData() async => {
    'profile': 'Anonymous shopper',
    'market': 'Demo Market',
    'claims': _claims.length,
    'generated_at': DateTime.now().toUtc().toIso8601String(),
  };
  @override
  Future<List<Claim>> claims() async => List.unmodifiable(_claims);
  @override
  Future<Map<String, dynamic>> claimStatus(String claimId) async {
    final c = _claims.where((x) => x.id == claimId).firstOrNull;
    return {
      'status': c?.status.name ?? 'expired',
      'saved_minor': c?.savedMinor ?? 0,
    };
  }

  @override
  Future<List<Offer>> feed(String language) async {
    await Future<void>.delayed(const Duration(milliseconds: 450));
    final now = DateTime.now();
    return [
      Offer(
        id: 'bread-10',
        shopId: 'alis',
        shopName: "Ali's Bakery",
        title: 'Fresh milk bread',
        description:
            'Soft, oven-fresh loaves baked today. Pick up before closing.',
        category: 'Bakery',
        discountPct: 30,
        wasPrice: 24000,
        nowPrice: 16800,
        currency: 'PKR',
        distanceM: 200,
        endsAt: now.add(const Duration(minutes: 42)),
        remaining: 8,
        why: 'On your list: bread · 200 m',
        source: 'ai',
        copySource: 'ai',
        tags: const ['Halal', 'Vegetarian'],
      ),
      Offer(
        id: 'mango-20',
        shopId: 'fresh',
        shopName: 'Fresh Basket',
        title: 'Sindhri mango box',
        description: 'A fragrant 2 kg box of ripe Sindhri mangoes.',
        category: 'Fruit & veg',
        discountPct: 22,
        wasPrice: 120000,
        nowPrice: 93600,
        currency: 'PKR',
        distanceM: 350,
        endsAt: now.add(const Duration(hours: 1, minutes: 18)),
        remaining: 12,
        why: 'You like fresh produce · 350 m',
        source: 'ai',
        copySource: 'shop',
        tags: const ['Vegan'],
      ),
      Offer(
        id: 'rice-30',
        shopId: 'noor',
        shopName: 'Noor Supermarket',
        title: 'Basmati rice — 5 kg',
        description: 'Long-grain basmati rice for everyday meals.',
        category: 'Groceries',
        discountPct: 15,
        wasPrice: 265000,
        nowPrice: 225250,
        currency: 'PKR',
        distanceM: 550,
        endsAt: now.add(const Duration(hours: 2, minutes: 5)),
        remaining: 5,
        why: 'Popular near Demo Market · 550 m',
        source: 'rules',
        copySource: 'shop',
        tags: const ['Halal', 'Vegan'],
      ),
      Offer(
        id: 'coffee-40',
        shopId: 'corner',
        shopName: 'The Corner Café',
        title: 'Coffee & croissant',
        description: 'Any hot coffee paired with a butter croissant.',
        category: 'Café',
        discountPct: 18,
        wasPrice: 78000,
        nowPrice: 63960,
        currency: 'PKR',
        distanceM: 700,
        endsAt: now.add(const Duration(minutes: 55)),
        remaining: 4,
        why: 'Ending soon near you · 700 m',
        source: 'rules',
        copySource: 'ai',
        tags: const ['Vegetarian'],
      ),
    ];
  }

  @override
  Future<Claim> claim(Offer o, String key) async {
    final existing = _claims
        .where((c) => c.offer.id == o.id && c.status == ClaimStatus.issued)
        .firstOrNull;
    if (existing != null) return existing;
    const chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
    final rand = Random();
    final code = List.generate(
      6,
      (_) => chars[rand.nextInt(chars.length)],
    ).join();
    final claim = Claim(
      id: _uuid.v7(),
      offer: o,
      qrPayload: 'SN1:demo.${_uuid.v4()}.${o.id}',
      shortCode: code,
      expiresAt: DateTime.now().add(const Duration(minutes: 30)),
      status: ClaimStatus.issued,
    );
    _claims.insert(0, claim);
    return claim;
  }
}
