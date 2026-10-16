import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

/// Requests focus only when the node is still attached to the widget tree.
void safeRequestFocus(FocusNode? node) {
  if (node == null) return;
  try {
    if (node.context != null) {
      node.requestFocus();
    }
  } catch (e) {
    if (kDebugMode) {
      debugPrint('safeRequestFocus skipped: $e');
    }
  }
}
