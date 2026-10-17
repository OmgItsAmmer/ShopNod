import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:geolocator/geolocator.dart';
import 'package:uuid/uuid.dart';
import '../core/models.dart';
import '../core/shopper_api.dart';
import '../core/storage.dart';

class AppController extends ChangeNotifier with WidgetsBindingObserver {
  AppController(this.storage);
  final AppStorage storage;
  late ShopperApi api;
  String? token, installId;
  String language = 'en';
  bool ageConfirmed = false, onboarded = false, busy = false, offline = false;
  String? error, preferredShop;
  bool demoMarketLink = false;
  DateTime? lastUpdated;
  Consents consents = const Consents();
  Preferences preferences = const Preferences(
    categories: ['Bakery', 'Groceries'],
  );
  List<Offer> offers = [], hiddenOffers = [];
  List<Claim> claimItems = [];
  List<String> shoppingList = ['Bread', 'Milk'];
  Timer? _refresh;
  static const apiUrl = String.fromEnvironment('API_URL');

  Future<void> init() async {
    WidgetsBinding.instance.addObserver(this);
    await storage.init();
    token = await storage.readToken();
    installId = storage.prefs.getString('install_id');
    language = storage.prefs.getString('language') ?? 'en';
    ageConfirmed = storage.prefs.getBool('age_confirmed') ?? false;
    onboarded = storage.prefs.getBool('onboarded') ?? false;
    shoppingList =
        storage.prefs.getStringList('shopping_list') ?? ['Bread', 'Milk'];
    api = apiUrl.isEmpty ? DemoShopperApi() : RemoteShopperApi(apiUrl, token);
    claimItems = _readCachedClaims();
    if (onboarded) await refresh(silent: true);
    // New offers show up within ~10 s while the app is open (the server caches ranking, so this is cheap).
    _refresh = Timer.periodic(
      const Duration(seconds: 10),
      (_) => onboarded ? refresh(silent: true) : null,
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _refresh?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && onboarded) refresh(silent: true);
  }

  void configureDeepLink(Uri uri) {
    final shop = uri.queryParameters['shop'];
    if (shop != null) preferredShop = shop;
    if (uri.queryParameters['market'] == 'demo') demoMarketLink = true;
  }

  Future<void> confirmAge() async {
    ageConfirmed = true;
    await storage.prefs.setBool('age_confirmed', true);
    notifyListeners();
  }

  Future<void> chooseLanguage(String value) async {
    language = value;
    await storage.prefs.setString('language', value);
    notifyListeners();
  }

  Future<void> updateConsents(Consents value) async {
    consents = value;
    notifyListeners();
  }

  Future<void> updateInterests(
    List<String> categories,
    List<String> dietary,
  ) async {
    preferences = preferences.copyWith(
      categories: categories,
      dietary: dietary,
    );
    notifyListeners();
  }

  Future<void> finishOnboarding({
    bool demoMarket = true,
    bool useLocation = false,
  }) async {
    busy = true;
    error = null;
    notifyListeners();
    try {
      if (token == null) {
        final session = await api.install(language);
        token = session['token'];
        installId = session['id'];
        await storage.writeToken(token!);
        await storage.prefs.setString('install_id', installId!);
        if (api is RemoteShopperApi) (api as RemoteShopperApi).token(token!);
      }
      await api.saveConsents(consents);
      await api.savePreferences(preferences, language);
      if (useLocation) {
        final enabled = await Geolocator.isLocationServiceEnabled();
        if (!enabled)
          throw FriendlyException(
            'Location services are off. You can join Demo Market instead.',
          );
        var permission = await Geolocator.checkPermission();
        if (permission == LocationPermission.denied)
          permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied ||
            permission == LocationPermission.deniedForever)
          throw FriendlyException(
            'Location was not allowed. You can join Demo Market instead.',
          );
        final p = await Geolocator.getCurrentPosition();
        await api.saveLocation(lat: p.latitude, lng: p.longitude);
      } else {
        await api.saveLocation(market: 'demo');
      }
      if (consents.list) await api.saveList(shoppingList);
      onboarded = true;
      await storage.prefs.setBool('onboarded', true);
      await refresh(silent: true);
    } catch (e) {
      error = _message(e);
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> refresh({bool silent = false}) async {
    if (!silent) {
      busy = true;
      error = null;
      notifyListeners();
    }
    try {
      var loaded = await api.feed(language);
      loaded = loaded
          .where(
            (o) =>
                !preferences.mutedShops.contains(o.shopId) &&
                !preferences.mutedCategories.contains(o.category),
          )
          .toList();
      if (preferredShop != null)
        loaded.sort(
          (a, b) => a.shopId == preferredShop
              ? -1
              : b.shopId == preferredShop
              ? 1
              : 0,
        );
      offers = loaded;
      offline = false;
      lastUpdated = DateTime.now();
      await _cacheFeed(loaded);
    } catch (e) {
      error = _message(e);
      offline = true;
      if (offers.isEmpty) offers = _readCachedFeed();
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<Claim?> claim(Offer offer) async {
    busy = true;
    notifyListeners();
    try {
      final value = await api.claim(offer, const Uuid().v4());
      claimItems.removeWhere((c) => c.id == value.id);
      claimItems.insert(0, value);
      await _saveClaims();
      return value;
    } catch (e) {
      error = _message(e);
      return null;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  /// Ask the API whether the shop has scanned this claim yet (the QR screen polls this).
  Future<void> syncClaim(String claimId) async {
    final i = claimItems.indexWhere((c) => c.id == claimId);
    if (i < 0 || claimItems[i].status != ClaimStatus.issued) return;
    try {
      final s = await api.claimStatus(claimId);
      final status = ClaimStatus.values.firstWhere(
        (v) => v.name == s['status'],
        orElse: () => ClaimStatus.issued,
      );
      if (status == ClaimStatus.issued) return;
      final c = claimItems[i];
      claimItems[i] = c.copyWith(
        status: status,
        savedMinor: (s['saved_minor'] as num?)?.round() ?? c.savedMinor,
      );
      await _saveClaims();
      notifyListeners();
    } catch (_) {
      // Offline or a blip: the next poll tries again.
    }
  }

  void simulateRedemption(String claimId) {
    final i = claimItems.indexWhere((c) => c.id == claimId);
    if (i >= 0 && claimItems[i].status == ClaimStatus.issued) {
      final c = claimItems[i];
      claimItems[i] = c.copyWith(
        status: ClaimStatus.redeemed,
        savedMinor: c.offer.wasPrice - c.offer.nowPrice,
      );
      _saveClaims();
      notifyListeners();
    }
  }

  Future<void> saveShoppingList(List<String> items) async {
    shoppingList = items;
    await storage.prefs.setStringList('shopping_list', items);
    if (consents.list) await api.saveList(items);
    notifyListeners();
  }

  Future<void> sendFeedback(Offer offer, bool positive) =>
      api.event(positive ? 'why_up' : 'why_down', offer);
  Future<void> dismissOffer(Offer offer, String reason) async {
    hiddenOffers.add(offer);
    offers.removeWhere((o) => o.id == offer.id);
    notifyListeners();
    await api.event('dismiss', offer, reason: reason);
  }

  Future<void> muteShop(Offer o) async {
    preferences = preferences.copyWith(
      mutedShops: [...preferences.mutedShops, o.shopId],
    );
    offers.removeWhere((x) => x.shopId == o.shopId);
    notifyListeners();
    await api.savePreferences(preferences, language);
  }

  Future<void> muteCategory(Offer o) async {
    preferences = preferences.copyWith(
      mutedCategories: [...preferences.mutedCategories, o.category],
    );
    offers.removeWhere((x) => x.category == o.category);
    notifyListeners();
    await api.savePreferences(preferences, language);
  }

  Future<void> saveSettings(Preferences p, Consents c) async {
    preferences = p;
    consents = c;
    notifyListeners();
    await Future.wait([api.savePreferences(p, language), api.saveConsents(c)]);
  }

  Future<Map<String, dynamic>> exportData() => api.exportData();
  Future<Map<String, dynamic>> affinity() => api.affinity();
  Future<void> resetAffinity() => api.resetAffinity();
  Future<void> deleteMe() async {
    await api.deleteMe();
    await storage.clear();
    ageConfirmed = false;
    onboarded = false;
    token = null;
    offers = [];
    claimItems = [];
    notifyListeners();
  }

  int get savingsMinor => claimItems
      .where((c) => c.status == ClaimStatus.redeemed)
      .fold(0, (s, c) => s + c.savedMinor);
  String _message(Object e) {
    if (e is FriendlyException) return e.message;
    final text = '$e';
    if (text.contains('FriendlyException'))
      return text.split('FriendlyException:').last.trim();
    return 'Something went wrong. Please try again.';
  }

  Future<void> _cacheFeed(List<Offer> items) => storage.writeJson(
    'feed_cache',
    items
        .map(
          (o) => {
            'id': o.id,
            'shop_id': o.shopId,
            'shop_name': o.shopName,
            'title': o.title,
            'description': o.description,
            'category': o.category,
            'discount_pct': o.discountPct,
            'was_price': o.wasPrice,
            'now_price': o.nowPrice,
            'currency': o.currency,
            'distance_m': o.distanceM,
            'ends_at': o.endsAt.toIso8601String(),
            'remaining': o.remaining,
            'why': o.why,
            'source': o.source,
            'copy_source': o.copySource,
            'tags': o.tags,
          },
        )
        .toList(),
  );
  List<Offer> _readCachedFeed() {
    try {
      return (jsonDecode(storage.prefs.getString('feed_cache') ?? '[]') as List)
          .map((e) => Offer.fromJson((e as Map).cast()))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> _saveClaims() => storage.writeJson(
    'claims_cache',
    claimItems
        .map(
          (c) => {
            'id': c.id,
            'offer': {
              'id': c.offer.id,
              'shop_id': c.offer.shopId,
              'shop_name': c.offer.shopName,
              'title': c.offer.title,
              'description': c.offer.description,
              'category': c.offer.category,
              'discount_pct': c.offer.discountPct,
              'was_price': c.offer.wasPrice,
              'now_price': c.offer.nowPrice,
              'currency': c.offer.currency,
              'distance_m': c.offer.distanceM,
              'ends_at': c.offer.endsAt.toIso8601String(),
              'remaining': c.offer.remaining,
              'why': c.offer.why,
              'source': c.offer.source,
              'copy_source': c.offer.copySource,
              'tags': c.offer.tags,
            },
            'qr_payload': c.qrPayload,
            'short_code': c.shortCode,
            'expires_at': c.expiresAt.toIso8601String(),
            'status': c.status.name,
            'saved_minor': c.savedMinor,
          },
        )
        .toList(),
  );

  List<Claim> _readCachedClaims() {
    try {
      return (jsonDecode(storage.prefs.getString('claims_cache') ?? '[]')
              as List)
          .map((raw) {
            final j = (raw as Map).cast<String, dynamic>();
            return Claim(
              id: '${j['id']}',
              offer: Offer.fromJson(
                (j['offer'] as Map).cast<String, dynamic>(),
              ),
              qrPayload: '${j['qr_payload']}',
              shortCode: '${j['short_code']}',
              expiresAt: DateTime.parse('${j['expires_at']}'),
              status: ClaimStatus.values.firstWhere(
                (s) => s.name == j['status'],
                orElse: () => ClaimStatus.expired,
              ),
              savedMinor: (j['saved_minor'] as num?)?.round() ?? 0,
            );
          })
          .toList();
    } catch (_) {
      return [];
    }
  }
}
