import 'package:flutter/widgets.dart';

class AppStrings {
  AppStrings(this.locale);
  final Locale locale;
  static AppStrings of(BuildContext context) =>
      AppStrings(Localizations.localeOf(context));
  static const supported = [
    Locale('en'),
    Locale('ur'),
    Locale('ar'),
    Locale('es'),
  ];
  static const _values = <String, Map<String, String>>{
    'en': {
      'forYou': 'For you',
      'list': 'My list',
      'wallet': 'Wallet',
      'settings': 'Settings',
      'retry': 'Try again',
      'getOffer': 'Get offer',
      'why': 'Why you see this',
      'samePrice': 'Everyone sees the same price',
      'aiLabel': 'AI-written, approved by the shop',
      'rules': 'Rule-based',
      'ends': 'ends in',
      'remaining': 'left',
      'saved': 'You saved',
      'continue': 'Continue',
      'skip': 'Not now',
    },
    'ur': {
      'forYou': 'آپ کے لیے',
      'list': 'میری فہرست',
      'wallet': 'والیٹ',
      'settings': 'ترتیبات',
      'retry': 'دوبارہ کوشش',
      'getOffer': 'آفر حاصل کریں',
      'why': 'یہ کیوں دکھایا گیا',
      'samePrice': 'سب کے لیے ایک ہی قیمت',
      'aiLabel': 'AI سے تحریر، دکان سے منظور',
      'rules': 'قواعد پر مبنی',
      'ends': 'ختم ہونے میں',
      'remaining': 'باقی',
      'saved': 'آپ نے بچائے',
      'continue': 'جاری رکھیں',
      'skip': 'ابھی نہیں',
    },
    'ar': {
      'forYou': 'لك',
      'list': 'قائمتي',
      'wallet': 'المحفظة',
      'settings': 'الإعدادات',
      'retry': 'حاول مجدداً',
      'getOffer': 'احصل على العرض',
      'why': 'لماذا ترى هذا',
      'samePrice': 'السعر نفسه للجميع',
      'aiLabel': 'كتبه الذكاء الاصطناعي ووافق عليه المتجر',
      'rules': 'حسب القواعد',
      'ends': 'ينتهي خلال',
      'remaining': 'متبقي',
      'saved': 'وفّرت',
      'continue': 'متابعة',
      'skip': 'ليس الآن',
    },
    'es': {
      'forYou': 'Para ti',
      'list': 'Mi lista',
      'wallet': 'Cartera',
      'settings': 'Ajustes',
      'retry': 'Reintentar',
      'getOffer': 'Obtener oferta',
      'why': 'Por qué ves esto',
      'samePrice': 'El mismo precio para todos',
      'aiLabel': 'Escrito con IA, aprobado por la tienda',
      'rules': 'Basado en reglas',
      'ends': 'termina en',
      'remaining': 'restantes',
      'saved': 'Ahorraste',
      'continue': 'Continuar',
      'skip': 'Ahora no',
    },
  };
  String t(String key) =>
      _values[locale.languageCode]?[key] ?? _values['en']![key] ?? key;
}
