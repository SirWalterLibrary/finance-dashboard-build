import pytest

from app.rules import merchant_key


@pytest.mark.parametrize(
    ("desc", "expected"),
    [
        ("PURCHASE                                AUTHORIZED ON   09/30 SAMS CLUB #6312           WOODBURY      MN  P000000244641285   CARD 7673",
         "SAMS CLUB"),
        ("KWIK TRIP #178 SOUTH ST PAUL",
         "KWIK TRIP"),
        ("PURCHASE INTL                           AUTHORIZED ON   05/04 PAYMOB-*Samra Aqua        CAIRO         EGY S356124285784368   CARD 3543",
         "PAYMOB-*SAMRA AQUA"),
        ("ZELLE TO  MAMA ON 09/26 REF # WFCT00TEST01",
         "ZELLE TO MAMA"),
        ("ZELLE FROM SHEIKH AHMED ON 09/05 REF # WFCT22M7ZSYG DUGSI TUITION",
         "ZELLE FROM SHEIKH"),
        ("AplPay LYFT         855-280-0278        CA",
         "LYFT CA"),
        ("SAM'S CLUB FUEL 6309WHITE BEAR LAKE     MN",
         "SAMS CLUB"),
        ("MONEY TRANSFER                          AUTHORIZED ON   08/12 CASH APP*ABDIRAHMA        Oakland       CA  S306224494194481   CARD 3543",
         "CASH APP*ABDIRAHMA"),
        ("",
         ""),
        ("ATM",
         "ATM"),
    ],
)
def test_merchant_key(desc, expected):
    assert merchant_key(desc) == expected
