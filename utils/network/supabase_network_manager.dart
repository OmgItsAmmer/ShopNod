import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:http/http.dart' as http;

import '../../common/widgets/loaders/tloaders.dart';
import '../../supabase_strings.dart';

/// Special network manager for handling Supabase connection issues
class SupabaseNetworkManager {
  static final SupabaseNetworkManager _instance =
      SupabaseNetworkManager._internal();
  static SupabaseNetworkManager get instance => _instance;

  final Connectivity _connectivity = Connectivity();
  late StreamSubscription<ConnectivityResult> _connectivitySubscription;
  final Rx<ConnectivityResult> _connectionStatus = ConnectivityResult.none.obs;
  final RxBool _isSupabaseConnected = true.obs;

  // HTTP probe timeout (seconds)
  static const int _probeTimeout = 10;

  SupabaseNetworkManager._internal();

  void initialize() {
    _connectivitySubscription =
        _connectivity.onConnectivityChanged.listen(_updateConnectionStatus);
    // Start periodic connection check
    Timer.periodic(
        const Duration(minutes: 2), (_) => checkSupabaseConnection());
  }

  Future<void> _updateConnectionStatus(ConnectivityResult result) async {
    _connectionStatus.value = result;
    if (result == ConnectivityResult.none) {
      _isSupabaseConnected.value = false;
      if (kDebugMode) {
        print('No network connection detected');
      }
    } else {
      // When network is back, check Supabase connection
      checkSupabaseConnection();
    }
  }

  /// Check if device is connected to the internet
  Future<bool> isNetworkConnected() async {
    try {
      final result = await _connectivity.checkConnectivity();
      return result != ConnectivityResult.none;
    } on PlatformException catch (e) {
      if (kDebugMode) {
        print('Error checking connectivity: $e');
      }
      return false;
    }
  }

  /// Check if Supabase is reachable via an HTTP probe.
  Future<bool> checkSupabaseConnection() async {
    if (!await isNetworkConnected()) {
      _isSupabaseConnected.value = false;
      return false;
    }

    try {
      // HTTP probe — works on both web and native without dart:io Socket.
      final uri = Uri.parse('${SupabaseStrings.projectUrl}/auth/v1/settings');
      final response = await http
          .head(uri)
          .timeout(Duration(seconds: _probeTimeout));
      // Any non-5xx response means the server is reachable.
      _isSupabaseConnected.value = response.statusCode < 500;
      return _isSupabaseConnected.value;
    } catch (e) {
      if (kDebugMode) {
        print('Supabase connection check failed: $e');
      }
      _isSupabaseConnected.value = false;
      TLoaders.errorSnackBar(
          title: 'Connection Issue',
          message:
              'Having trouble connecting to the server. Please check your connection.');
      return false;
    }
  }

  /// Helper method to handle retry logic for Supabase operations
  Future<T?> executeWithRetry<T>({
    required Future<T> Function() operation,
    int maxRetries = 3,
    Duration retryDelay = const Duration(seconds: 2),
  }) async {
    int attempts = 0;
    while (attempts < maxRetries) {
      try {
        // Check connection before attempting operation
        if (!await isNetworkConnected()) {
          if (attempts == 0) {
            // Only show once
            TLoaders.warningSnackBar(
                title: 'No Connection',
                message: 'Please check your internet connection');
          }

          // Wait before retry
          await Future.delayed(retryDelay);
          attempts++;
          continue;
        }

        // Try the operation
        return await operation();
      } catch (e) {
        attempts++;

        if (kDebugMode) {
          print('Operation failed (attempt $attempts): $e');
        }

        // If this was our last attempt, rethrow
        if (attempts >= maxRetries) {
          rethrow;
        }

        // Wait before retry with exponential backoff
        await Future.delayed(
            Duration(seconds: retryDelay.inSeconds * attempts));
      }
    }
    return null;
  }

  void dispose() {
    _connectivitySubscription.cancel();
  }
}
