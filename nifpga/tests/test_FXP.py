from nifpga import DataType
from nifpga.session import _FxpRegister
from decimal import Decimal
import unittest
import warnings


class MockFxpRegister(_FxpRegister):
    def __init__(self,
                 signed,
                 enableOverflowStatus,
                 word_length,
                 integer_word_length):
        self._signed = signed
        self._word_length = word_length
        self._integer_word_length = integer_word_length
        self._delta = self._calculate_delta(word_length,
                                            integer_word_length)
        self._overflow_enabled = enableOverflowStatus
        self.set_register_attributes()

    def set_register_attributes(self):
        self._name = "MockFxpRegister"
        self._radix_point = self._calculate_radix_point()
        self._offset = 0  # Not needed for mock
        self._datatype = DataType.FXP  # FXP is always DataType.FXP
        self._ctype_type = self._datatype._return_ctype()
        self._access_may_timeout = False  # Does not affect FXP any different
        self._internal = False  # Cant be internal
        self._is_array = False  # This mock is always a single FXP

""" These are a couple of arbitrary binary strings that the following unit
to test a non random value.
"""
binary_string_16bit = '1110010010010110'  # 2's comp = 0001101101101010
binary_string_32bit = '01000101100100100011000100001100'


class FXPRegister16bitWord16bitInteger(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxpRegister(signed=False,
                                            enableOverflowStatus=False,
                                            word_length=16,
                                            integer_word_length=16)

    def test_converting_binary_into_decimal(self):
        value = (int(binary_string_16bit, 2))
        actual = self.testRegister._convert_from_read_value_to_decimal(
            value)
        """ The expected value should be equal to
        2^(15) + 2^(14) + 2^(13) + 2^(10) + 2^(7) + 2^(4) + 2^(2) + 2^(1)
        """
        expected = Decimal(58518)
        self.assertEqual(expected, actual)

    def test_converting_user_data_into_binary(self):
        value = Decimal(58518)
        actual = self.testRegister._convert_data_to_binary_fxp(value)

        expected = binary_string_16bit
        self.assertEqual(expected, actual)

    def test_converting_user_data_too_small_warns_and_coerces_zero(self):
        value = Decimal(-6)  # Arbitrary negative number
        with warnings.catch_warnings(record=True) as recordedWarning:
            self.assertEqual(0, len(recordedWarning))
            actual = self.testRegister._convert_data_to_binary_fxp(value)
            self.assertEqual(1, len(recordedWarning))
            expected = '0'.zfill(16)
            self.assertEqual(expected, actual)


class FXPRegister16bitWord16bitIntegerSigned(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxpRegister(signed=True,
                                            enableOverflowStatus=False,
                                            word_length=16,
                                            integer_word_length=16)

    def test_converting_binary_into_decimal(self):
        value = int(binary_string_16bit, 2)
        actual = self.testRegister._convert_from_read_value_to_decimal(value)
        """ The expected value should be equal to
        (-1)(1*(2^(12) + 2^(11) + 2^(9) + 2^(8) + 2^(6) + 2^(5) + 2^(3) + 2^(1))
        """
        expected = Decimal(-7018)
        self.assertEqual(expected, actual)

    def test_converting_user_data_into_binary(self):
        value = Decimal(-7018)
        actual = self.testRegister._convert_data_to_binary_fxp(value)

        expected = binary_string_16bit
        self.assertEqual(expected, actual)


class FXPRegister15bitWord15bitIntegerOverflow(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxpRegister(signed=False,
                                            enableOverflowStatus=True,
                                            word_length=15,
                                            integer_word_length=15)

    def test_converting_binary_into_decimal(self):
        value = int(binary_string_16bit, 2)
        actual = self.testRegister._convert_from_read_value_to_decimal(value)
        """ The expected value should be equal to an overflow with a value
        of
        2^(15) + 2^(14) + 2^(13) + 2^(10) + 2^(7) + 2^(4) + 2^(2) + 2^(1)
        """
        expected = Decimal(25750)
        self.assertEqual(expected, actual)
        self.assertTrue(self.testRegister.overflow)

    def test_overflow_is_only_set_after_read(self):
        self.assertFalse(hasattr(self.testRegister, "overflow"))
        value = int('1' + ''.zfill(self.testRegister._word_length), 2)
        self.testRegister._convert_from_read_value_to_decimal(value)
        self.assertTrue(self.testRegister.overflow)

    def test_converting_user_data_into_binary_with_overflow(self):
        value = Decimal(25750)
        self.testRegister.overflow = True
        actual = self.testRegister._convert_data_to_binary_fxp(value)

        expected = binary_string_16bit
        self.assertEqual(expected, actual)

    def test_converting_user_data_without_setting_overflow_warns(self):
        value = Decimal(25750)
        with warnings.catch_warnings(record=True) as recordedWarning:
            self.assertEqual(0, len(recordedWarning))
            actual = self.testRegister._convert_data_to_binary_fxp(value)
            self.assertEqual(1, len(recordedWarning))
            # Because overflow is not set the overflow bit should be False.
            expected = '0' + binary_string_16bit[1:]
            self.assertEqual(expected, actual)


class FXPRegister15bitWord15bitIntegerSignedOverflow(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxpRegister(signed=True,
                                            enableOverflowStatus=True,
                                            word_length=15,
                                            integer_word_length=15)

    def test_converting_binary_into_decimal(self):
        value = int(binary_string_16bit, 2)
        actual = self.testRegister._convert_from_read_value_to_decimal(value)
        """ The expected value should be equal to a
        -1*(2^(12) + 2^(11) + 2^(9) + 2^(8) + 2^(6) + 2^(5) + 2^(3) + 2^(1))
        """
        expected = Decimal(-7018)
        self.assertEqual(expected, actual)
        self.assertTrue(self.testRegister.overflow)

    def test_overflow_bit_is_not_calculated_in_twos_compliment(self):
        # Create a 16 bit word that is all 1's
        value = int('1' * (self.testRegister._word_length + 1), 2)
        actual = self.testRegister._convert_from_read_value_to_decimal(value)
        """ The expected value of overflow(1) 111 1111 1111 1111, would
        expect -1 and an overflow. as the twos complement of the non-overflow
        bits would be 000 0000 0000 0001"""
        self.assertTrue(self.testRegister.overflow)
        self.assertEqual(-1, actual)

    def test_converting_user_data_into_binary(self):
        value = Decimal(-7018)
        self.testRegister.overflow = True
        actual = self.testRegister._convert_data_to_binary_fxp(value)

        expected = binary_string_16bit
        self.assertEqual(expected, actual)


class FXPRegister16bitWord0bitInteger(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxpRegister(signed=False,
                                            enableOverflowStatus=False,
                                            word_length=16,
                                            integer_word_length=0)

    def test_converting_binary_into_decimal(self):
        value = int(binary_string_16bit, 2)
        actual = self.testRegister._convert_from_read_value_to_decimal(value)
        """ The expected value should be equal to
        2^(-1) + 2^(-2) + 2^(-3) + 2^(-6) + 2^(-9) + 2^(-12) + 2^(-14) + 2^(-15)
        """
        expected = Decimal(0.892913818359375)
        self.assertEqual(expected, actual)

    def test_converting_user_data_into_binary(self):
        value = Decimal(0.892913818359375)
        actual = self.testRegister._convert_data_to_binary_fxp(value)
        expected = binary_string_16bit
        self.assertEqual(expected, actual)


class FXPRegister15bitWord0bitIntegerOverflow(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxpRegister(signed=False,
                                            enableOverflowStatus=True,
                                            word_length=15,
                                            integer_word_length=0)

    def test_converting_binary_into_decimal(self):
        value = int(binary_string_16bit, 2)
        actual = self.testRegister._convert_from_read_value_to_decimal(value)
        """ The expected value should be equal to
        2^(-1) + 2^(-2) + 2^(-5) + 2^(-8) + 2^(-11) + 2^(-13) + 2^(-14)
        """
        expected = Decimal(0.78582763671875)
        self.assertEqual(expected, actual)
        self.assertTrue(self.testRegister.overflow)

    def test_converting_user_data_into_binary(self):
        value = Decimal(0.78582763671875)
        self.testRegister.overflow = True
        actual = self.testRegister._convert_data_to_binary_fxp(value)
        expected = binary_string_16bit
        self.assertEqual(expected, actual)


class FXPRegister15bitWord0bitIntegerSignedOverflow(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxpRegister(signed=True,
                                            enableOverflowStatus=True,
                                            word_length=15,
                                            integer_word_length=0)

    def test_converting_binary_into_decimal(self):
        value = int(binary_string_16bit, 2)
        actual = self.testRegister._convert_from_read_value_to_decimal(value)
        """ The expected value should be equal to
        2^(-3) + 2^(-4) + 2^(-6) + 2^(-7) + 2^(-9) + 2^(-10) + 2^(-12) + 2^(-14)
        """
        expected = Decimal(-0.21417236328125)
        self.assertEqual(expected, actual)
        self.assertTrue(self.testRegister.overflow)

    def test_converting_user_data_into_binary(self):
        value = Decimal(-0.21417236328125)
        self.testRegister.overflow = True
        actual = self.testRegister._convert_data_to_binary_fxp(value)
        expected = binary_string_16bit
        self.assertEqual(expected, actual)


class FXPRegister32bitWord16bitIntegerOverflow(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxpRegister(signed=False,
                                            enableOverflowStatus=True,
                                            word_length=32,
                                            integer_word_length=16)

    def test_converting_binary_into_decimal(self):

        #'(1) 0100010110010010.0011000100001100'
        """ The expected value should be equal to
        2^(1) + 2^(4) + 2^(7) + 2^(8) + 2^(10) + 2^(14) +
        2^(-3) + 2^(-4) + 2^(-8) + 2^(-13) + 2^(-14)
        """
        value = int('0' + binary_string_32bit, 2)
        actual = self.testRegister._convert_from_read_value_to_decimal(value)
        expected = Decimal(17810.19158935546875)
        self.assertEqual(expected, actual)
        self.assertFalse(self.testRegister.overflow)

    def test_converting_user_data_into_binary(self):
        value = Decimal(17810.19158935546875)
        self.testRegister.overflow = False
        actual = self.testRegister._convert_data_to_binary_fxp(value)
        expected = '0' + binary_string_32bit
        self.assertEqual(expected, actual)


class FXPRegister16bitWord100bitInteger(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxpRegister(signed=False,
                                            enableOverflowStatus=False,
                                            word_length=16,
                                            integer_word_length=100)

    def test_converting_binary_into_decimal(self):
        value = int(binary_string_16bit, 2)
        actual = self.testRegister._convert_from_read_value_to_decimal(value)
        """ The expected value should be equal to
        2^(99) + 2^(98) + 2^(97) + 2^(94) + 2^(91) + 2^(88) + 2^(86) + 2^(85)
        """
        expected = Decimal(1131902737795341920727296114688)
        self.assertTrue(expected, actual)

    def test_converting_user_data_into_binary(self):
        value = Decimal(1131902737795341920727296114688)
        actual = self.testRegister._convert_data_to_binary_fxp(value)
        expected = binary_string_16bit
        self.assertEqual(expected, actual)


class FXPRegister16bitWordNegative100bitInteger(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxpRegister(signed=False,
                                            enableOverflowStatus=False,
                                            word_length=16,
                                            integer_word_length=-100)
        self.decimal_value = Decimal(2**(-101) + 2**(-102) + 2**(-103)
                                     + 2**(-106) + 2**(-109) + 2**(-112)
                                     + 2**(-114) + 2**(-115))

    def test_converting_binary_into_decimal(self):
        value = int(binary_string_16bit, 2)
        """ The expected value should be equal to
        2^(-101) + 2^(-102) + 2^(-103) + 2^(-106) + 2^(-109) + 2^(-112)
        + 2^(-114) + 2^(-115)
        """
        actual = self.testRegister._convert_from_read_value_to_decimal(value)
        expected = self.decimal_value
        self.assertEqual(expected, actual)

    def test_converting_user_data_into_binary(self):
        value = self.decimal_value
        actual = self.testRegister._convert_data_to_binary_fxp(value)
        expected = binary_string_16bit
        self.assertEqual(expected, actual)


class FXPRegister64bitWord64bitIntegerOverflow(unittest.TestCase):
    def setUp(self):
        self.testRegister = MockFxpRegister(signed=False,
                                            enableOverflowStatus=True,
                                            word_length=64,
                                            integer_word_length=64)
        self.binary_string = '1' + binary_string_32bit + binary_string_32bit

    def test_converting_binary_into_decimal(self):
        """Read value is equal to
        (1)0100010110010010001100010000110001000101100100100011000100001100
        """
        value = int(self.binary_string, 2)
        actual = self.testRegister._convert_from_read_value_to_decimal(value)
        expected = Decimal(5013123263993360652)
        self.assertEqual(expected, actual)
        self.assertTrue(self.testRegister.overflow)

    def test_converting_user_data_into_binary(self):
        value = Decimal(5013123263993360652)
        self.testRegister.overflow = True
        actual = self.testRegister._convert_data_to_binary_fxp(value)
        expected = self.binary_string
        self.assertEqual(expected, actual)
