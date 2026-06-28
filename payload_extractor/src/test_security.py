import unittest
from unittest.mock import patch, MagicMock
import json
import zlib
import base64
import hashlib

# Add the src directory to the Python path to allow imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from security import TrustLayer, _strip_empty, GITHUB_PAGES_URL

# A sample raw data payload mimicking the output of HardwareExtractor
SAMPLE_RAW_DATA = {
    "Timestamp": "2023-10-27 10:00:00",
    "CPU": {"Name": "Test CPU", "Cores": 8, "Threads": 16, "MaxClock": "4.00 GHz"},
    "Motherboard": {"Manufacturer": "TestBoard", "Product_Model": "TB-101", "Serial_Number": "12345", "Hardware_Age": "3 Years Old"},
    "GPU": [{"Model": "Test GPU", "VRAM": "8.00 GB", "Driver_Version": "123.45"}],
    "RAM_Usage": {"Total_Installed": "32.00 GB"},
    "Storage_Deep_SMART": [{"Model": "Test SSD", "Size_GB": "1024 GB", "OS_Health_Status": "Healthy", "Wear_Level": "5%", "Normie_Warning": "None"}],
    "Battery": {"Status": "No Battery Detected (Likely a Desktop)"},
    "Network_Adapters": [{"MAC_Current": "00:11:22:33:44:55", "MAC_Spoofed": False}],
    "Abuse_History": {"Critical_Power_Failures": 1, "Unexpected_Shutdowns": 2, "Blue_Screens_of_Death": 0, "Disk_Bad_Blocks_Logged": 0, "Historical_Thermal_Throttling": 10, "Fatal_Hardware_Errors": 0},
    "System": {"Timeline": {"Current_Session_Uptime": "1 day, 2:00:00", "Normie_Warning": "None"}},
    # Extra data that should be stripped
    "WinSAT_Benchmarks": {"Base_Score": "8.1"},
    "Display": [{"Monitor_Name": "Generic PnP Monitor"}]
}

class TestSecurity(unittest.TestCase):

    def setUp(self):
        self.security_layer = TrustLayer(SAMPLE_RAW_DATA)

    def test_strip_empty(self):
        """Test the helper function that removes None, 'Unknown', and empty strings."""
        obj = {
            "a": "has_value",
            "b": None,
            "c": "Unknown",
            "d": "",
            "e": 0,
            "f": False,
            "g": {"nested_empty": None},
            "h": [1, None, 2],
            "i": []
        }
        stripped = _strip_empty(obj)
        self.assertEqual(stripped, {
            "a": "has_value",
            "e": 0,
            "f": False,
            "h": [1, 2],
            "i": []
        })

    def test_build_compact_payload(self):
        """Verify that the payload is correctly minified and stripped of non-essentials."""
        compact_payload = self.security_layer._build_compact_payload()

        # Check for minified keys
        self.assertIn("v", compact_payload) # version
        self.assertIn("t", compact_payload) # timestamp
        self.assertIn("c", compact_payload) # cpu
        self.assertIn("g", compact_payload) # gpu
        self.assertIn("b", compact_payload) # motherboard
        self.assertIn("s", compact_payload) # storage
        self.assertIn("a", compact_payload) # abuse

        # Check that non-essential data is gone
        self.assertNotIn("WinSAT_Benchmarks", compact_payload)
        self.assertNotIn("Display", compact_payload)
        self.assertNotIn("Driver_Version", compact_payload["g"][0])

        # Check specific values
        self.assertEqual(compact_payload["c"]["n"], "Test CPU")
        self.assertEqual(compact_payload["a"]["p"], 1) # Critical Power Failures
        self.assertEqual(compact_payload["a"]["u"], 2) # Unexpected Shutdowns

    def test_generate_secure_payload_structure_and_integrity(self):
        """Test the entire payload generation pipeline for structure and data integrity."""
        secure_uri = self.security_layer.generate_secure_payload()

        self.assertTrue(secure_uri.startswith(GITHUB_PAGES_URL))

        # Decode the payload to verify its contents
        encoded_part = secure_uri.split('?d=')[1]
        compressed_part = base64.urlsafe_b64decode(encoded_part)
        package_str = zlib.decompress(compressed_part).decode('utf-8')
        package = json.loads(package_str)

        # 1. Check that the package has the payload and signature
        self.assertIn("p", package) # payload
        self.assertIn("s", package) # signature

        payload_str = package["p"]
        signature = package["s"]

        # 2. Verify the signature
        expected_signature = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        self.assertEqual(signature, expected_signature)

        # 3. Verify the contents of the payload itself
        payload_data = json.loads(payload_str)
        self.assertEqual(payload_data["c"]["n"], "Test CPU")
        self.assertEqual(payload_data["b"]["m"], "TB-101")

    @patch('security.qrcode')
    @patch('security.os.startfile')
    def test_display_qr(self, mock_startfile, mock_qrcode):
        """Test that the QR code generation and display logic is called correctly."""
        mock_qr_instance = MagicMock()
        mock_img = MagicMock()
        mock_qr_instance.make_image.return_value = mock_img
        mock_qrcode.QRCode.return_value = mock_qr_instance

        test_uri = "http://example.com?d=123"
        self.security_layer.display_qr(test_uri)

        mock_qr_instance.add_data.assert_called_once_with(test_uri)
        mock_img.save.assert_called_once_with("Hardware-Ledger-QR.png")
        mock_startfile.assert_called_once_with("Hardware-Ledger-QR.png")

if __name__ == '__main__':
    unittest.main()