import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AppStorage {
  final _secure = const FlutterSecureStorage();
  late SharedPreferences prefs;
  Future<void> init() async => prefs = await SharedPreferences.getInstance();
  Future<String?> readToken() async {
    try {
      return await _secure.read(key: 'install_token');
    } catch (_) {
      return prefs.getString('install_token');
    }
  }

  Future<void> writeToken(String value) async {
    try {
      await _secure.write(key: 'install_token', value: value);
    } catch (_) {
      await prefs.setString('install_token', value);
    }
  }

  Future<void> clear() async {
    try {
      await _secure.deleteAll();
    } catch (_) {}
    await prefs.clear();
  }

  List<Map<String, dynamic>> readJsonList(String key) {
    try {
      return (jsonDecode(prefs.getString(key) ?? '[]') as List)
          .cast<Map>()
          .map((e) => e.cast<String, dynamic>())
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> writeJson(String key, Object value) =>
      prefs.setString(key, jsonEncode(value));
}
