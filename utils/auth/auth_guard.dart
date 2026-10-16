import 'package:get/get.dart';

import '../../repositories/authentication/authicatioon_repository.dart';

/// True only after [AuthenticationRepository] confirms a valid session.
bool get isAppAuthenticated {
  if (!Get.isRegistered<AuthenticationRepository>()) return false;
  return AuthenticationRepository.instance.isAuthenticated.value;
}
