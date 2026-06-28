import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import datetime

# Add the src directory to the Python path to allow imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from hardware import HardwareExtractor

class TestHardwareExtractor(unittest.TestCase):

    @patch('hardware.wmi.WMI')
    @patch('hardware.psutil')
    def setUp(self, mock_psutil, mock_wmi_constructor):
        """Set up a mocked environment before each test."""
        # Mock the WMI client instance
        self.mock_wmi_client = MagicMock()
        mock_wmi_constructor.return_value = self.mock_wmi_client

        # Mock psutil
        self.mock_psutil = mock_psutil

        # Instantiate the class to be tested
        self.extractor = HardwareExtractor()
        self.extractor.wmi_client = self.mock_wmi_client

    def test_get_cpu_info_success(self):
        """Test successful CPU info extraction."""
        mock_cpu = MagicMock()
        mock_cpu.Name = "Test CPU "
        mock_cpu.NumberOfCores = 4
        mock_cpu.NumberOfLogicalProcessors = 8
        mock_cpu.MaxClockSpeed = 3400
        mock_cpu.L2CacheSize = 1024
        mock_cpu.L3CacheSize = 8192
        self.mock_wmi_client.Win32_Processor.return_value = [mock_cpu]

        # Mock temperature (which uses a different WMI namespace)
        with patch('hardware.wmi.WMI') as mock_wmi_root:
            mock_thermal = MagicMock()
            mock_thermal.CurrentTemperature = 3232 # 323.2K = 50.05C
            mock_wmi_root.return_value.MSAcpi_ThermalZoneTemperature.return_value = [mock_thermal]
            
            cpu_info = self.extractor.get_cpu_info()

        self.assertEqual(cpu_info['Name'], 'Test CPU')
        self.assertEqual(cpu_info['Cores'], 4)
        self.assertEqual(cpu_info['MaxClock'], '3.40 GHz')
        self.assertEqual(cpu_info['Temperature'], '50.1 °C')

    def test_get_cpu_info_failure(self):
        """Test CPU info extraction failure."""
        self.mock_wmi_client.Win32_Processor.side_effect = Exception("WMI Error")
        cpu_info = self.extractor.get_cpu_info()
        self.assertIn("Error", cpu_info)
        self.assertIn("WMI Error", cpu_info["Error"])

    @patch('hardware.psutil')
    def test_get_ram_info_success(self, mock_psutil):
        """Test successful RAM usage info extraction."""
        mock_vmem = MagicMock()
        type(mock_vmem).total = PropertyMock(return_value=16 * 1024**3)
        type(mock_vmem).available = PropertyMock(return_value=8 * 1024**3)
        type(mock_vmem).percent = PropertyMock(return_value=50.0)
        mock_psutil.virtual_memory.return_value = mock_vmem

        ram_info = self.extractor.get_ram_info()
        self.assertEqual(ram_info['Total_Installed'], '16.00 GB')
        self.assertEqual(ram_info['Currently_Available'], '8.00 GB')
        self.assertEqual(ram_info['Usage_Percentage'], '50.0%')

    def test_get_gpu_info_success(self):
        """Test successful GPU info extraction."""
        mock_gpu = MagicMock()
        mock_gpu.Name = "Test GPU"
        mock_gpu.AdapterRAM = 4 * 1024**3
        mock_gpu.DriverVersion = "123.45"
        mock_gpu.Status = "OK"
        mock_gpu.VideoModeDescription = "1920x1080"
        mock_gpu.AdapterCompatibility = "TestCorp"
        self.mock_wmi_client.Win32_VideoController.return_value = [mock_gpu]

        gpu_info = self.extractor.get_gpu_info()
        self.assertEqual(len(gpu_info), 1)
        self.assertEqual(gpu_info[0]['Model'], 'Test GPU')
        self.assertEqual(gpu_info[0]['VRAM'], '4.00 GB')

    def test_get_motherboard_info_success(self):
        """Test successful motherboard info extraction."""
        mock_board = MagicMock()
        mock_board.Manufacturer = "TestBoard Inc. "
        mock_board.Product = "TB-101"
        mock_board.SerialNumber = "123456789"
        self.mock_wmi_client.Win32_BaseBoard.return_value = [mock_board]

        mock_bios = MagicMock()
        mock_bios.SMBIOSBIOSVersion = "1.2.3"
        mock_bios.ReleaseDate = "20200101000000.000000+000"
        mock_bios.Manufacturer = "TestBIOS"
        self.mock_wmi_client.Win32_BIOS.return_value = [mock_bios]

        mb_info = self.extractor.get_motherboard_info()

        self.assertEqual(mb_info['Manufacturer'], 'TestBoard Inc.')
        self.assertEqual(mb_info['Product_Model'], 'TB-101')
        self.assertEqual(mb_info['BIOS_Release_Date'], '2020-01-01')
        current_year = datetime.datetime.now().year
        self.assertEqual(mb_info['Hardware_Age'], f'{current_year - 2020} Years Old')

    def test_get_network_info_spoof_detection(self):
        """Test MAC address spoof detection."""
        mock_nic = MagicMock()
        mock_nic.Name = "Test Adapter"
        mock_nic.Manufacturer = "TestNic Corp"
        mock_nic.MACAddress = "00:11:22:33:44:55"
        mock_nic.PermanentAddress = "AA:BB:CC:DD:EE:FF" # Different from current
        mock_nic.NetConnectionStatus = 2
        self.mock_wmi_client.Win32_NetworkAdapter.return_value = [mock_nic]

        net_info = self.extractor.get_network_info()
        self.assertEqual(len(net_info), 1)
        self.assertTrue(net_info[0]['MAC_Spoofed'])
        self.assertEqual(net_info[0]['MAC_Current'], "00:11:22:33:44:55")
        self.assertEqual(net_info[0]['MAC_Hardware_Burned'], "AA:BB:CC:DD:EE:FF")

    def test_get_battery_info_no_battery(self):
        """Test battery info when no battery is present (desktops)."""
        self.mock_wmi_client.query.return_value = []
        bat_info = self.extractor.get_battery_info()
        self.assertEqual(bat_info['Status'], 'No Battery Detected (Likely a Desktop)')

    def test_get_battery_info_with_battery(self):
        """Test battery info with a healthy battery."""
        mock_battery = MagicMock()
        mock_battery.Status = "OK"
        mock_battery.DesignCapacity = 50000
        mock_battery.FullChargeCapacity = 45000
        self.mock_wmi_client.query.return_value = [mock_battery]

        bat_info = self.extractor.get_battery_info()
        self.assertEqual(bat_info['Battery_Health_Percentage'], '90.00%')
        self.assertEqual(bat_info['Wear_Level'], '10.00%')

    @patch('hardware.subprocess.run')
    def test_get_unified_storage_info_powershell_works(self, mock_run):
        """Test storage info when PowerShell command succeeds."""
        # Mock WMI for basic info
        mock_disk = MagicMock()
        mock_disk.Model = "Test NVMe Drive "
        mock_disk.SerialNumber = "SN9876"
        mock_disk.Size = 512 * 1024**3
        mock_disk.InterfaceType = "NVMe"
        self.mock_wmi_client.Win32_DiskDrive.return_value = [mock_disk]

        # Mock PowerShell output
        ps_output = '[{"Model": "Test NVMe Drive", "MediaType": "SSD", "HealthStatus": "Healthy", "Wear": 10}]'
        mock_run.return_value = MagicMock(stdout=ps_output, returncode=0)

        storage_info = self.extractor.get_unified_storage_info()
        self.assertEqual(len(storage_info), 1)
        self.assertEqual(storage_info[0]['Model'], 'Test NVMe Drive')
        self.assertEqual(storage_info[0]['OS_Health_Status'], 'Healthy')
        self.assertEqual(storage_info[0]['Wear_Level'], '10%')
        self.assertEqual(storage_info[0]['Serial_Number'], 'SN9876')

    @patch('hardware.subprocess.run')
    def test_get_unified_storage_info_powershell_fails(self, mock_run):
        """Test storage info fallback when PowerShell fails (e.g., no admin)."""
        # Mock WMI for basic info
        mock_disk = MagicMock()
        mock_disk.Model = "Test SATA Drive "
        mock_disk.SerialNumber = "SN1234"
        mock_disk.Size = 1024 * 1024**3
        mock_disk.InterfaceType = "SATA"
        self.mock_wmi_client.Win32_DiskDrive.return_value = [mock_disk]

        # Mock PowerShell failure (empty output)
        mock_run.return_value = MagicMock(stdout="", returncode=1)

        storage_info = self.extractor.get_unified_storage_info()
        self.assertEqual(len(storage_info), 1)
        self.assertEqual(storage_info[0]['Model'], 'Test SATA Drive')
        self.assertEqual(storage_info[0]['OS_Health_Status'], 'Blocked (Run Exe as Admin)')
        self.assertEqual(storage_info[0]['Wear_Level'], 'Blocked (Run Exe as Admin)')

    @patch('hardware.psutil')
    def test_get_system_timeline_success(self, mock_psutil):
        """Test successful system timeline extraction."""
        # Mock psutil boot time
        boot_timestamp = datetime.datetime.now().timestamp() - 3600 # 1 hour ago
        mock_psutil.boot_time.return_value = boot_timestamp

        # Mock WMI OS install date
        mock_os = MagicMock()
        mock_os.InstallDate = "20210101120000.000000+000"
        self.mock_wmi_client.Win32_OperatingSystem.return_value = [mock_os]

        timeline = self.extractor.get_system_timeline()
        self.assertEqual(timeline['OS_Original_Install_Date'], '2021-01-01')
        self.assertEqual(timeline['Current_Session_Uptime'], '1:00:00')
        self.assertEqual(timeline['Normie_Warning'], 'None')

    @patch('hardware.psutil')
    def test_get_system_timeline_suspicious_reboot(self, mock_psutil):
        """Test suspicious reboot warning."""
        # Mock psutil boot time to 5 minutes ago
        boot_timestamp = datetime.datetime.now().timestamp() - 300
        mock_psutil.boot_time.return_value = boot_timestamp
        self.mock_wmi_client.Win32_OperatingSystem.return_value = [MagicMock(InstallDate="20210101120000.000000+000")]

        timeline = self.extractor.get_system_timeline()
        self.assertIn("SUSPICIOUS", timeline['Normie_Warning'])

    @patch('hardware.subprocess.run')
    def test_get_abuse_history_success(self, mock_run):
        """Test successful abuse history extraction."""
        ps_output = '{"CriticalPowerLoss": 1, "UnexpectedShutdowns": 2, "BSODs": 0, "BadDiskBlocks": 0, "ThermalThrottling": 5, "FatalHardwareErrors": 0}'
        mock_run.return_value = MagicMock(stdout=ps_output, returncode=0)

        abuse_history = self.extractor.get_abuse_history()
        self.assertEqual(abuse_history['Critical_Power_Failures'], 1)
        self.assertEqual(abuse_history['Unexpected_Shutdowns'], 2)
        self.assertEqual(abuse_history['Total_Crash_Count'], 3)
        self.assertEqual(abuse_history['System_Stability_Rating'], 'Normal (Occasional fault)')

    @patch('hardware.subprocess.run')
    def test_get_abuse_history_access_denied(self, mock_run):
        """Test abuse history when PowerShell access is denied."""
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        abuse_history = self.extractor.get_abuse_history()
        self.assertEqual(abuse_history['Status'], 'ACCESS DENIED - Requires Administrator')

    def test_get_full_ledger_structure(self):
        """Test the structure of the final get_full_ledger output."""
        # We can mock the individual methods to test the final assembly
        self.extractor.get_cpu_info = MagicMock(return_value={"Name": "Test CPU"})
        self.extractor.get_motherboard_info = MagicMock(return_value={"Manufacturer": "TestBoard"})
        
        ledger = self.extractor.get_full_ledger()
        
        self.assertIn("Timestamp", ledger)
        self.assertIn("System", ledger)
        self.assertIn("Motherboard", ledger)
        self.assertIn("CPU", ledger)
        self.assertIn("GPU", ledger)
        self.assertIn("Storage_Deep_SMART", ledger)
        self.assertIn("Abuse_History", ledger)
        self.assertEqual(ledger["CPU"]["Name"], "Test CPU")

if __name__ == '__main__':
    unittest.main()