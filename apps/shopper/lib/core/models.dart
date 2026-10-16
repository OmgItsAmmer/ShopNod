enum ClaimStatus { issued, redeemed, expired }

class Offer {
  const Offer({
    required this.id,
    required this.shopId,
    required this.shopName,
    required this.title,
    required this.description,
    required this.category,
    required this.discountPct,
    required this.wasPrice,
    required this.nowPrice,
    required this.currency,
    required this.distanceM,
    required this.endsAt,
    required this.remaining,
    required this.why,
    required this.source,
    required this.copySource,
    this.tags = const [],
  });
  final String id,
      shopId,
      shopName,
      title,
      description,
      category,
      currency,
      why,
      source,
      copySource;
  final int discountPct, wasPrice, nowPrice, distanceM, remaining;
  final DateTime endsAt;
  final List<String> tags;

  factory Offer.fromJson(Map<String, dynamic> j) {
    final o = (j['offer'] as Map?)?.cast<String, dynamic>() ?? j;
    final s =
        (j['shop'] as Map?)?.cast<String, dynamic>() ??
        const <String, dynamic>{};
    return Offer(
      id: '${o['id']}',
      shopId: '${o['shop_id'] ?? s['id'] ?? ''}',
      shopName: '${s['name'] ?? o['shop_name'] ?? 'Local shop'}',
      title: '${o['title'] ?? o['item_name'] ?? 'Special offer'}',
      description: '${o['description'] ?? ''}',
      category: '${o['category'] ?? 'Other'}',
      discountPct: (o['discount_pct'] as num?)?.round() ?? 0,
      wasPrice: (o['was_price'] as num?)?.round() ?? 0,
      nowPrice: (o['now_price'] as num?)?.round() ?? 0,
      currency: '${o['currency'] ?? 'PKR'}',
      distanceM: (j['distance_m'] as num?)?.round() ?? 0,
      endsAt:
          DateTime.tryParse('${o['ends_at']}') ??
          DateTime.now().add(const Duration(hours: 1)),
      remaining: (o['remaining'] as num?)?.round() ?? 1,
      why: '${j['why'] ?? 'Near you'}',
      source: '${j['source'] ?? 'rules'}',
      copySource: '${j['copy_source'] ?? o['copy_source'] ?? 'shop'}',
      tags: (o['tags'] as List? ?? const []).map((e) => '$e').toList(),
    );
  }
}

class Claim {
  const Claim({
    required this.id,
    required this.offer,
    required this.qrPayload,
    required this.shortCode,
    required this.expiresAt,
    required this.status,
    this.savedMinor = 0,
  });
  final String id, qrPayload, shortCode;
  final Offer offer;
  final DateTime expiresAt;
  final ClaimStatus status;
  final int savedMinor;
  Claim copyWith({ClaimStatus? status, int? savedMinor}) => Claim(
    id: id,
    offer: offer,
    qrPayload: qrPayload,
    shortCode: shortCode,
    expiresAt: expiresAt,
    status: status ?? this.status,
    savedMinor: savedMinor ?? this.savedMinor,
  );
}

class Consents {
  const Consents({
    this.location = true,
    this.notifications = true,
    this.list = true,
    this.personalisation = true,
    this.analytics = false,
  });
  final bool location, notifications, list, personalisation, analytics;
  Map<String, dynamic> toJson() => {
    'location': location,
    'notifications': notifications,
    'list': list,
    'personalisation': personalisation,
    'analytics': analytics,
    'policy_version': '1.0',
  };
  Consents copyWith({
    bool? location,
    bool? notifications,
    bool? list,
    bool? personalisation,
    bool? analytics,
  }) => Consents(
    location: location ?? this.location,
    notifications: notifications ?? this.notifications,
    list: list ?? this.list,
    personalisation: personalisation ?? this.personalisation,
    analytics: analytics ?? this.analytics,
  );
}

class Preferences {
  const Preferences({
    this.categories = const [],
    this.dietary = const [],
    this.maxDistanceM = 800,
    this.dailyLimit = 3,
    this.quietStart = '21:00',
    this.quietEnd = '08:00',
    this.mutedShops = const [],
    this.mutedCategories = const [],
  });
  final List<String> categories, dietary, mutedShops, mutedCategories;
  final int maxDistanceM, dailyLimit;
  final String quietStart, quietEnd;
  Map<String, dynamic> toJson(String language) => {
    'categories': categories,
    'dietary': dietary,
    'languages': [language],
    'max_distance_m': maxDistanceM,
    'daily_limit': dailyLimit,
    'quiet_start': quietStart,
    'quiet_end': quietEnd,
    'muted_shops': mutedShops,
    'muted_categories': mutedCategories,
  };
  Preferences copyWith({
    List<String>? categories,
    List<String>? dietary,
    int? maxDistanceM,
    int? dailyLimit,
    String? quietStart,
    String? quietEnd,
    List<String>? mutedShops,
    List<String>? mutedCategories,
  }) => Preferences(
    categories: categories ?? this.categories,
    dietary: dietary ?? this.dietary,
    maxDistanceM: maxDistanceM ?? this.maxDistanceM,
    dailyLimit: dailyLimit ?? this.dailyLimit,
    quietStart: quietStart ?? this.quietStart,
    quietEnd: quietEnd ?? this.quietEnd,
    mutedShops: mutedShops ?? this.mutedShops,
    mutedCategories: mutedCategories ?? this.mutedCategories,
  );
}
