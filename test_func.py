from sms_bulk_app import mask_phone_number


def test_mask_phone_number():
    result = mask_phone_number('381123456789')
    assert result != '38112***6789'
    assert result == '381*******89'
