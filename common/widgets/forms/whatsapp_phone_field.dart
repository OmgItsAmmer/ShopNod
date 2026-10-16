import 'package:ecommerce_dashboard/utils/constants/colors.dart';
import 'package:ecommerce_dashboard/utils/constants/sizes.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Compact WhatsApp checkbox + phone field row for POS entity forms.
class WhatsappPhoneField extends StatelessWidget {
  const WhatsappPhoneField({
    super.key,
    required this.isWhatsapp,
    required this.onWhatsappChanged,
    required this.phoneController,
    this.phoneValidator,
    this.dense = true,
  });

  final bool isWhatsapp;
  final ValueChanged<bool?> onWhatsappChanged;
  final TextEditingController phoneController;
  final String? Function(String?)? phoneValidator;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final labelStyle = Theme.of(context).textTheme.bodySmall;
    final fieldSpacing = dense ? TSizes.spaceBtwInputFields : TSizes.sm;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            SizedBox(
              height: dense ? 36 : 40,
              child: Checkbox(
                value: isWhatsapp,
                onChanged: onWhatsappChanged,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                visualDensity: VisualDensity.compact,
              ),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'WhatsApp Number',
                    style: labelStyle,
                  ),
                  Text(
                    'واٹس ایپ نمبر — خودکار الرٹس کے لیے تجویز کردہ',
                    style: labelStyle?.copyWith(
                      color: TColors.darkGrey,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        SizedBox(height: fieldSpacing),
        TextFormField(
          validator: phoneValidator,
          controller: phoneController,
          keyboardType: TextInputType.phone,
          inputFormatters: [
            FilteringTextInputFormatter.digitsOnly,
            LengthLimitingTextInputFormatter(11),
          ],
          maxLines: 1,
          style: Theme.of(context).textTheme.bodyMedium,
          decoration: const InputDecoration(
            labelText: 'Phone (Optional) / فون نمبر (اختیاری)',
            hintText: '03XXXXXXXXX — recommended',
            isDense: true,
          ),
        ),
      ],
    );
  }
}
