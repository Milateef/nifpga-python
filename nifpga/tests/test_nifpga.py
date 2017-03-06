import ctypes
import mock
import unittest
import sys
import warnings
from contextlib import contextmanager

import jobrunner
import nifpga
from nifpga.statuscheckedlibrary import (check_status,
                                         FunctionInfo,
                                         StatusCheckedFunctions,
                                         NamedArgtype,
                                         LibraryFunctionInfo,
                                         LibraryNotFoundError,
                                         StatusCheckedLibrary)

python_version = 3 if sys.version_info >= (3,0) else 2

def raise_an_exception():
    """
    A helper for NiFpgaStatusExceptionTest
    """
    session = ctypes.c_int32(0x0000beef)
    fifo = ctypes.c_uint32(0x0000f1f0)
    data = ctypes.c_uint64(0x0000da7a)
    number_of_elements = ctypes.c_size_t(0x100)
    timeout_ms = ctypes.c_size_t(0x200)
    elements_remaining = ctypes.c_size_t(0x300)
    bogus_string_argument = ctypes.c_char_p(b"I am a string")
    exception = nifpga.FifoTimeoutError(
                            function_name="Dummy Function Name",
                            argument_names=["session",
                                            "fifo",
                                            "data",
                                            "number of elements",
                                            "timeout ms",
                                            "elements remaining",
                                            "a bogus string argument"],
                            function_args=(session,
                                        fifo,
                                        data,
                                        number_of_elements,
                                        timeout_ms,
                                        elements_remaining,
                                        bogus_string_argument))
    raise exception

class NiFpgaStatusExceptionTest(unittest.TestCase):
    def test_autogenerated_status_warning_and_error_classes_exist(self):
        some_warning_class = nifpga.FifoTimeoutWarning
        some_error_class = nifpga.FifoTimeoutError

    def test_can_get_arguments_from_exception(self):
        try:
            raise_an_exception()
            fail("An exception should have been raised")
        except nifpga.FifoTimeoutError as e:
            self.assertEqual(-50400, e.get_code())
            self.assertEqual("FifoTimeout", e.get_code_string())
            self.assertEqual("Dummy Function Name", e.get_function_name())

            args = e.get_args()
            self.assertEqual(args["session"], 0x0000beef)
            self.assertEqual(args["fifo"], 0x0000f1f0)
            self.assertEqual(args["data"], 0x0000da7a)
            self.assertEqual(args["number of elements"], 0x100)
            self.assertEqual(args["timeout ms"], 0x200)
            self.assertEqual(args["elements remaining"], 0x300)
            self.assertEqual(args["a bogus string argument"], b"I am a string")

            # Spot check a couple different types of args in the
            # printed string that should be helpful for readability
            exception_str = str(e)
            # numbers in hex!
            self.assertIn("session: 0xbeef", exception_str)
            # strings have single quotes around them
            if python_version == 2:
                self.assertIn("a bogus string argument: 'I am a string'", exception_str)
            else:
                self.assertIn("a bogus string argument: b'I am a string'", exception_str)

    def test_status_exceptions_can_be_pickled_across_processes(self):
        runner = jobrunner.JobRunner(jobrunner.JobRunner.RUN_MODE_MULTIPROCESS,
                                        runnables=[raise_an_exception],
                                        auto_assert=False)
        result = runner.run()[0]
        self.assertTrue(result.exception_occured())
        self.assertEqual(str(result.err_type), str(nifpga.FifoTimeoutError))
        self.assertIn("session: 0xbeef", result.err_class)
        if python_version == 2:
            self.assertIn("a bogus string argument: 'I am a string'", result.err_class)
        else:
            self.assertIn("a bogus string argument: b'I am a string'", result.err_class)

@check_status(function_name="Fake Function Name", argument_names=["code"])
def return_a_checked_status(code):
    """
    A helper for CheckStatusTest
    """
    return code

@contextmanager
def assert_warns(warning):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        yield
        # verify the warning occured
        assert len(w) == 1
        assert isinstance(w[0].message, warning)

class CheckStatusTest(unittest.TestCase):
    def test_success(self):
        return_a_checked_status(0)

    def test_get_known_error(self):
        with self.assertRaises(nifpga.FifoTimeoutError):
            return_a_checked_status(-50400)

    def test_get_known_warning(self):
        with assert_warns(nifpga.FifoTimeoutWarning):
            return_a_checked_status(50400)

    def test_get_unknown_error(self):
        with self.assertRaises(nifpga.UnknownError):
            return_a_checked_status(-1)

    def test_get_unknown_warning(self):
        with assert_warns(nifpga.UnknownWarning):
            return_a_checked_status(1)

class StatusCheckedLibraryTestCRunTime(unittest.TestCase):
    """
    Since we can't load NiFpga on a dev machine unless we have all its
    dependencies installed (i.e. a bunch of NI software we don't want on
    a dev machine), we'll cheat and use the C runtime library and
    strcmp. strcmp doesn't really return a NiFpga_Status, but we can pretend.
    """
    def setUp(self):
        self._c_runtime = StatusCheckedLibrary("c",
                library_function_infos=\
                [
                    LibraryFunctionInfo(
                        pretty_name="c_strcmp",
                        name_in_library="strcmp",
                        named_argtypes=\
                        [
                            NamedArgtype("string1", ctypes.c_char_p),
                            NamedArgtype("string2", ctypes.c_char_p),
                        ])
                ])

    def test_success(self):
        self._c_runtime.c_strcmp(b"equal", b"equal")
        self._c_runtime["c_strcmp"](b"equal", b"equal")

    def test_get_unknown_error(self):
        # strcmp returns -1
        with self.assertRaises(nifpga.UnknownError):
            self._c_runtime.c_strcmp(b"not equal", b"these are")

    def test_get_unknown_warning(self):
        with warnings.catch_warnings(record=True) as w:
            # strcmp returns 1
            self._c_runtime.c_strcmp(b"these are", b"not equal")

            assert len(w) == 1
            warning = w[0].message
            # Make sure all this propagates into the warning.
            self.assertEqual(1, warning.get_code())
            self.assertEqual(b"these are", warning.get_args()["string1"])
            self.assertEqual(b"not equal", warning.get_args()["string2"])

            # These make the warning message readable
            self.assertIn("strcmp", str(warning))
            if python_version == 2:
                self.assertIn("string1: 'these are'", str(warning))
                self.assertIn("string2: 'not equal'", str(warning))
            else:
                self.assertIn("string1: b'these are'", str(warning))
                self.assertIn("string2: b'not equal'", str(warning))

class StatusCheckedLibraryTestMockedLibrary(unittest.TestCase):
    """
    Since we can't load NiFpga on a dev machine unless we have all its
    dependencies installed (i.e. a bunch of NI software we don't want on
    a dev machine), we'll monkey patch and use mocked libraries.
    """
    # so nose shows test names instead of docstrings
    def shortDescription(self): return None

    @mock.patch('nifpga.statuscheckedlibrary.ctypes.util.find_library')
    @mock.patch('nifpga.statuscheckedlibrary.ctypes.cdll')
    def setUp(self, mock_cdll, mock_find_library):
        """
        Setup up self._library so that self._library.AwesomeFunction(int, str)
        can be called, and the return value can be changed by setting
        self._mock_awesome_function.return_value.
        """
        mock_loaded_library = mock.Mock()
        mock_cdll.LoadLibrary.return_value = mock_loaded_library
        self._mock_awesome_function = mock.Mock()
        self._mock_awesome_function.__name__ = "Entrypoint_AwesomeFunction"
        mock_loaded_library.Entrypoint_AwesomeFunction = self._mock_awesome_function
        self._library = StatusCheckedLibrary(
                    library_name="CoolLibrary",
                    library_function_infos=[\
                        LibraryFunctionInfo(
                            pretty_name="AwesomeFunction",
                            name_in_library="Entrypoint_AwesomeFunction",
                            named_argtypes=[NamedArgtype("some_integer", ctypes.c_uint32),
                                            NamedArgtype("some_string", ctypes.c_char_p)])
                    ])

    def test_good_error_message_from_memory_full_error(self):
        """ Tests a good error message from a library call that fails.
        1. Correctly converts -52000 to NiFpgaMemoryFullError
        2. An integer arg gets printed as hex (easier to debug than decimal)
        3. A string arg gets printed with quotes surrounding it (so it's obviously a string)
        """
        self._mock_awesome_function.return_value = -52000
        try:
            self._library.AwesomeFunction(ctypes.c_uint32(33), ctypes.c_char_p(b"2"))
            self.fail("AwesomeFunction should have raised MemoryFull")
        except nifpga.MemoryFullError as e:
            if python_version == 2:
                self.assertEqual(
                    "Error: MemoryFull (-52000) when calling 'Entrypoint_AwesomeFunction' with arguments:"
                    "\n\tsome_integer: 0x21L"
                    "\n\tsome_string: '2'", str(e))
            else:
                self.assertEqual(
                    "Error: MemoryFull (-52000) when calling 'Entrypoint_AwesomeFunction' with arguments:"
                    "\n\tsome_integer: 0x21"
                    "\n\tsome_string: b'2'", str(e))

    def test_success_when_library_function_is_success(self):
        """ Tests that a 0 status return value does not raise any errors. """
        self._mock_awesome_function.return_value = 0
        self._library.AwesomeFunction(ctypes.c_uint32(33), ctypes.c_char_p(b"2"))

    def test_good_error_message_if_wrong_number_of_arguments(self):
        """ Tests that calling a function with wrong number of arguments is error """
        try:
            self._library.AwesomeFunction(ctypes.c_uint32(33))
            self.fail("AwesomeFunction should have raised TypeError")
        except TypeError as e:
            self.assertEqual("Entrypoint_AwesomeFunction takes exactly 2 arguments (1 given)", str(e))

class NiFpgaTest(unittest.TestCase):
    def test_that_we_at_least_get_to_try_loading_library(self):
        # We can't do much without NiFpga and other NI software actually
        # being installed, but on a dev machine we can at least
        # catch a few more errors by trying to creating a NiFpga instance and
        # expect to fail when the library can't be found.
        try:
            lib = nifpga.nifpga._NiFpga()
        except LibraryNotFoundError as e:
            pass
