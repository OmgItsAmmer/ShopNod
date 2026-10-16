import 'package:flutter_riverpod/legacy.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart' show Provider;
import '../core/storage.dart';
import 'app_controller.dart';

final appControllerProvider = ChangeNotifierProvider<AppController>(
  (ref) => throw UnimplementedError('Overridden in main'),
);
final storageProvider = Provider<AppStorage>(
  (ref) => throw UnimplementedError('Overridden in main'),
);
