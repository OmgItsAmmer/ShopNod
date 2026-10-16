import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:get/get.dart';

import '../../../utils/constants/colors.dart';
import '../../../utils/helpers/focus_utils.dart';
import '../loaders/tloaders.dart';
import 'custom_autocomplete.dart';

/// An enhanced autocomplete widget that exactly matches the behavior of ProductSearchBar
/// in sale_product_bar.dart with additional error handling capabilities.
///
/// Key features:
/// 1. Shows overlay with options immediately on focus (for address, brand, category)
/// 2. Properly hides overlay when clicking elsewhere
/// 3. Shows validation errors for invalid entries
/// 4. Allows syncing with an external controller
class EnhancedAutocomplete<T extends Object> extends StatefulWidget {
  /// The label text for the field
  final String labelText;

  /// The hint text for the field
  final String hintText;

  /// Function that converts an object to its display string
  final String Function(T) displayStringForOption;

  /// List of all available options
  final List<T> options;

  /// External controller to sync with
  final TextEditingController? externalController;

  /// Flag to track if text was manually entered (GetX RxBool)
  final RxBool? isManualTextEntry;

  /// Value notifier for the selected item name (GetX Rx<String>)
  final Rx<String>? selectedItemName;

  /// Value notifier for the selected item ID (GetX Rx<int>)
  final Rx<int>? selectedItemId;

  /// Function to extract ID from an item
  final int? Function(T)? getItemId;

  /// Function called when an option is selected
  final Function(T)? onSelected;

  /// Function called after manual text entry
  final Function(String)? onManualTextEntry;

  /// Optional validator function
  final String? Function(String?)? validator;

  /// Whether to show options immediately on focus (for address, brand, category fields)
  final bool showOptionsOnFocus;

  /// Increment (e.g. from GetX) to programmatically focus and open the options overlay.
  final int openOptionsTick;

  /// Called when the underlying field [FocusNode] is ready (POS tab order).
  final void Function(FocusNode focusNode)? onFocusNodeReady;

  /// When true, Enter on an empty field opens the list but never picks the first option.
  final bool preventAutoSelectOnSubmit;

  /// When true (default), moves focus to the next field after a list item is selected.
  /// Set false when the parent [onSelected] handles focus (e.g. product → variant).
  final bool advanceFocusOnSelect;

  /// Custom focus node (optional)
  final FocusNode? focusNode;

  const EnhancedAutocomplete({
    super.key,
    this.labelText = 'Item',
    this.hintText = 'Select an item',
    required this.displayStringForOption,
    required this.options,
    this.externalController,
    this.isManualTextEntry,
    this.selectedItemName,
    this.selectedItemId,
    this.getItemId,
    this.onSelected,
    this.onManualTextEntry,
    this.validator,
    this.showOptionsOnFocus = false,
    this.openOptionsTick = 0,
    this.onFocusNodeReady,
    this.preventAutoSelectOnSubmit = false,
    this.advanceFocusOnSelect = true,
    this.focusNode,
  });

  @override
  State<EnhancedAutocomplete<T>> createState() =>
      _EnhancedAutocompleteState<T>();
}

class _EnhancedAutocompleteState<T extends Object>
    extends State<EnhancedAutocomplete<T>> {
  /// Invisible char used to open the options overlay without selecting an item.
  static const String _overlayTrigger = '\u200b';

  late TextEditingController _innerController;
  late FocusNode _innerFocusNode;
  final LayerLink _layerLink = LayerLink();
  bool _isMounted = false;
  FocusNode? _fieldFocusNode;
  TextEditingController? _fieldTextController;
  int? _highlightedOptionIndex;
  int _lastOptionCount = 0;

  FocusNode? _registeredFocusNode;
  TextEditingController? _registeredController;

  String _effectiveFieldText(String text) =>
      text.replaceAll(_overlayTrigger, '');

  @override
  void initState() {
    super.initState();
    _innerController = TextEditingController();
    _innerFocusNode = FocusNode();
    _isMounted = true;

    // Listen to changes in the external controller
    if (widget.externalController != null) {
      widget.externalController!.addListener(_updateInnerFromExternal);
    }
  }

  // Method to update inner controller when external changes
  void _updateInnerFromExternal() {
    if (!_isMounted) return;

    if (widget.externalController != null &&
        _innerController != widget.externalController &&
        _innerController.text != widget.externalController!.text) {
      // Need to use setState to update the UI
      setState(() {
        _innerController.value = TextEditingValue(
          text: widget.externalController!.text,
          selection: TextSelection.collapsed(
              offset: widget.externalController!.text.length),
        );
      });
    }
  }

  @override
  void didUpdateWidget(covariant EnhancedAutocomplete<T> oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.openOptionsTick != oldWidget.openOptionsTick) {
      _scheduleOpenOptionsOverlay();
    }
    _refreshOverlayWhenOptionsChange(oldWidget);
  }

  /// The suggestion list is only recomputed when the text changes. When the options arrive later
  /// (a search that goes to the server), the list stayed stale until the user typed another
  /// character, for example a space. Nudge the field so the list is rebuilt with the new options.
  void _refreshOverlayWhenOptionsChange(EnhancedAutocomplete<T> oldWidget) {
    if (!_isMounted) return;
    String signature(List<T> items) =>
        items.map(widget.displayStringForOption).join('\u0001');
    if (signature(oldWidget.options) == signature(widget.options)) return;
    if (widget.options.isEmpty) return;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      final focus = _fieldFocusNode;
      final tc = _fieldTextController;
      if (!_isMounted || focus == null || tc == null || !focus.hasFocus) return;
      final visible = _effectiveFieldText(tc.text);
      if (visible.trim().isEmpty) return;
      tc.value = TextEditingValue(
        text: '$visible$_overlayTrigger',
        selection: TextSelection.collapsed(offset: visible.length),
      );
    });
  }

  void _scheduleOpenOptionsOverlay() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_isMounted) return;
      _showAllOptionsOverlay();
    });
  }

  void _showAllOptionsOverlay() {
    if (!_isMounted ||
        !widget.showOptionsOnFocus ||
        widget.options.isEmpty ||
        _fieldFocusNode == null ||
        _fieldTextController == null) {
      return;
    }
    final tc = _fieldTextController!;
    if (_effectiveFieldText(tc.text).isNotEmpty) return;

    _fieldFocusNode!.requestFocus();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_isMounted || !(_fieldFocusNode?.hasFocus ?? false)) return;
      if (_effectiveFieldText(tc.text).isEmpty) {
        tc.value = const TextEditingValue(
          text: _overlayTrigger,
          selection: TextSelection.collapsed(offset: 1),
        );
      }
    });
  }

  void _updateControllerText(TextEditingController controller, String newText) {
    final oldText = controller.text;
    if (oldText == newText) return;

    final oldSelection = controller.selection;
    int newOffset = oldSelection.end;

    if (oldText.startsWith(_overlayTrigger) && !newText.startsWith(_overlayTrigger)) {
      newOffset = (newOffset - 1).clamp(0, newText.length);
    } else {
      newOffset = newOffset.clamp(0, newText.length);
    }

    controller.value = TextEditingValue(
      text: newText,
      selection: TextSelection.collapsed(offset: newOffset),
    );
  }

  void _onControllerChanged() {
    if (!_isMounted || _registeredController == null) return;

    final currentText = _registeredController!.text;
    final visibleText = _effectiveFieldText(currentText);

    _updateControllerText(_registeredController!, visibleText);

    // Sync with external controller if provided (only if different instance)
    if (widget.externalController != null &&
        widget.externalController != _registeredController) {
      _updateControllerText(widget.externalController!, visibleText);
    }

    // Check if the text was manually edited and doesn't match the selected item
    if (widget.selectedItemName != null &&
        visibleText != widget.selectedItemName!.value) {
      // Set flag to indicate manual text entry
      if (widget.isManualTextEntry != null) {
        widget.isManualTextEntry!.value = true;
      }

      // Call the manual text entry callback if provided
      if (widget.onManualTextEntry != null) {
        widget.onManualTextEntry!(visibleText);
      }
    }
  }

  void _onFocusChanged() {
    if (!_isMounted || _registeredFocusNode == null || _registeredController == null) return;

    if (!_registeredFocusNode!.hasFocus) {
      _highlightedOptionIndex = null;
      if (widget.isManualTextEntry != null &&
          widget.isManualTextEntry!.value) {
        _validateManualEntry(_registeredController!.text);
      }
    }

    if (_registeredFocusNode!.hasFocus &&
        widget.showOptionsOnFocus &&
        _effectiveFieldText(_registeredController!.text).isEmpty &&
        widget.options.isNotEmpty) {
      _scheduleOpenOptionsOverlay();
    }
  }

  @override
  void dispose() {
    _isMounted = false;
    if (widget.externalController != null) {
      widget.externalController!.removeListener(_updateInnerFromExternal);
    }
    if (_registeredController != null) {
      _registeredController!.removeListener(_onControllerChanged);
    }
    if (_registeredFocusNode != null) {
      _registeredFocusNode!.removeListener(_onFocusChanged);
    }
    if (widget.externalController == null) {
      _innerController.dispose();
    }
    _innerFocusNode.dispose();
    super.dispose();
  }

  void _validateManualEntry(String text) {
    if (!_isMounted || text.trim().isEmpty) return;

    final trimmedLowerText = text.trim().toLowerCase();
    bool isValid = widget.options.any((option) =>
        widget.displayStringForOption(option).trim().toLowerCase() ==
        trimmedLowerText);

    if (!isValid) {
      TLoaders.errorSnackBar(
          title: 'Invalid Selection',
          message: '${widget.labelText} "${text.trim()}" not found in the list');

      // Reset the field if needed
      if (_isMounted && widget.externalController != null) {
        widget.externalController!.clear();
      }

      // Call the manual text entry callback if provided
      if (_isMounted && widget.onManualTextEntry != null) {
        widget.onManualTextEntry!('');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return CustomAutocomplete<T>(
      focusNode: widget.focusNode ?? _innerFocusNode,
      textEditingController: widget.externalController ?? _innerController,
      displayStringForOption: widget.displayStringForOption,
      optionsViewBuilder: (BuildContext context, void Function(T) onSelected,
          Iterable<T> options) {
        const AlignmentDirectional optionsAlignment =
            AlignmentDirectional.topStart;
        final isDark = Theme.of(context).brightness == Brightness.dark;
        _lastOptionCount = options.length;

        final int? highlightedIndex =
            AutocompleteHighlightedOption.of(context);
        if (highlightedIndex != _highlightedOptionIndex) {
          SchedulerBinding.instance.addPostFrameCallback((_) {
            if (_isMounted) {
              setState(() => _highlightedOptionIndex = highlightedIndex);
            }
          });
        }

        return Align(
          alignment: optionsAlignment,
          child: Material(
            elevation: 4.0,
            color: isDark ? TColors.dark : TColors.white,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 200.0),
              child: ListView.builder(
                padding: EdgeInsets.zero,
                shrinkWrap: true,
                itemCount: options.length,
                itemBuilder: (BuildContext context, int index) {
                  final T option = options.elementAt(index);
                  return InkWell(
                    onTap: () => onSelected(option),
                    child: Builder(
                      builder: (BuildContext itemContext) {
                        final bool highlight =
                            AutocompleteHighlightedOption.of(itemContext) ==
                                index;
                        if (highlight) {
                          SchedulerBinding.instance.addPostFrameCallback(
                            (_) {
                              Scrollable.ensureVisible(
                                itemContext,
                                alignment: 0.5,
                              );
                            },
                            debugLabel:
                                'EnhancedAutocomplete.ensureVisible',
                          );
                        }

                        final Color bg = highlight
                            ? (isDark
                                ? TColors.primary.withValues(alpha: 0.35)
                                : TColors.primary.withValues(alpha: 0.12))
                            : TColors.transparent;
                        final Color textColor = highlight
                            ? (isDark ? TColors.white : TColors.primary)
                            : (isDark ? TColors.white : TColors.textPrimary);

                        return Container(
                          decoration: BoxDecoration(
                            color: bg,
                            border: highlight
                                ? const Border(
                                    left: BorderSide(
                                      color: TColors.primary,
                                      width: 3,
                                    ),
                                  )
                                : null,
                          ),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 10,
                          ),
                          child: Text(
                            widget.displayStringForOption(option),
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: highlight
                                  ? FontWeight.w600
                                  : FontWeight.normal,
                              color: textColor,
                            ),
                          ),
                        );
                      },
                    ),
                  );
                },
              ),
            ),
          ),
        );
      },
      fieldViewBuilder: (BuildContext context,
          TextEditingController textEditingController,
          FocusNode focusNode,
          VoidCallback onFieldSubmitted) {
        _innerController = textEditingController;
        _fieldFocusNode = focusNode;
        _fieldTextController = textEditingController;
        widget.onFocusNodeReady?.call(focusNode);

        // Ensure proper listener registration without duplicates
        if (_registeredController != textEditingController) {
          if (_registeredController != null) {
            _registeredController!.removeListener(_onControllerChanged);
          }
          _registeredController = textEditingController;
          _registeredController!.addListener(_onControllerChanged);
        }

        if (_registeredFocusNode != focusNode) {
          if (_registeredFocusNode != null) {
            _registeredFocusNode!.removeListener(_onFocusChanged);
          }
          _registeredFocusNode = focusNode;
          _registeredFocusNode!.addListener(_onFocusChanged);
        }

        // This is crucial: Always ensure the internal controller matches the external
        // regardless of whether they're empty or not (only if they are different instances)
        if (widget.externalController != null &&
            textEditingController != widget.externalController &&
            textEditingController.text != widget.externalController!.text) {
          // Use WidgetsBinding to avoid text input issues
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (_isMounted) {
              textEditingController.value = TextEditingValue(
                text: widget.externalController!.text,
                selection: TextSelection.collapsed(
                    offset: widget.externalController!.text.length),
              );
            }
          });
        }

        return CompositedTransformTarget(
          link: _layerLink,
          child: TextFormField(
            focusNode: focusNode,
            controller: textEditingController,
            validator: widget.validator,
            onTap: () {
              if (widget.showOptionsOnFocus &&
                  _effectiveFieldText(textEditingController.text).isEmpty &&
                  widget.options.isNotEmpty) {
                _showAllOptionsOverlay();
              }
            },
            onFieldSubmitted: (String value) {
              if (!_isMounted) return;

              final visible = _effectiveFieldText(value);
              if (widget.preventAutoSelectOnSubmit && visible.isEmpty) {
                final canConfirmHighlight = _highlightedOptionIndex != null &&
                    _highlightedOptionIndex! >= 0 &&
                    _highlightedOptionIndex! < _lastOptionCount &&
                    _lastOptionCount > 0;
                if (canConfirmHighlight) {
                  onFieldSubmitted();
                  return;
                }
                _showAllOptionsOverlay();
                return;
              }

              onFieldSubmitted();

              if (widget.isManualTextEntry != null &&
                  widget.isManualTextEntry!.value) {
                _validateManualEntry(visible);
              }
            },
            decoration: InputDecoration(
              labelText: widget.labelText,
              hintText: widget.hintText,
              suffixIcon: textEditingController.text.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.close, size: 18),
                      onPressed: () {
                        if (!_isMounted) return;

                        textEditingController.clear();
                        if (widget.externalController != null) {
                          widget.externalController!.clear();
                        }
                        if (widget.selectedItemName != null) {
                          widget.selectedItemName!.value = '';
                        }
                        if (widget.selectedItemId != null) {
                          widget.selectedItemId!.value = -1;
                        }
                        if (widget.onManualTextEntry != null) {
                          widget.onManualTextEntry!('');
                        }
                      },
                    )
                  : null,
            ),
          ),
        );
      },
      optionsBuilder: (TextEditingValue textEditingValue) {
        final query = _effectiveFieldText(textEditingValue.text);

        if (query.isEmpty && !widget.showOptionsOnFocus) {
          return Iterable<T>.empty();
        }

        if (query.isEmpty && widget.showOptionsOnFocus) {
          return widget.options;
        }

        return widget.options.where((T option) {
          return widget
              .displayStringForOption(option)
              .toLowerCase()
              .contains(query.toLowerCase());
        });
      },
      onSelected: (T selectedItem) {
        if (!_isMounted) return;

        _highlightedOptionIndex = null;

        // Update controllers and notifiers
        final String itemName = widget.displayStringForOption(selectedItem);

        if (widget.externalController != null) {
          widget.externalController!.value = TextEditingValue(
            text: itemName,
            selection: TextSelection.collapsed(offset: itemName.length),
          );
        }

        if (widget.selectedItemName != null) {
          widget.selectedItemName!.value = itemName;
        }

        if (widget.selectedItemId != null && widget.getItemId != null) {
          final itemId = widget.getItemId!(selectedItem) ?? -1;
          widget.selectedItemId!.value = itemId;
        }

        if (widget.isManualTextEntry != null) {
          widget.isManualTextEntry!.value = false;
        }

        // Call the selection callback if provided
        if (widget.onSelected != null) {
          widget.onSelected!(selectedItem);
        }

        if (widget.advanceFocusOnSelect) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!_isMounted) return;
            final fn = _fieldFocusNode;
            if (fn != null && fn.hasFocus && fn.context != null) {
              FocusScope.of(fn.context!).nextFocus();
            }
          });
        }
      },
    );
  }
}
