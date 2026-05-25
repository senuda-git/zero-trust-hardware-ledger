import subprocess
import json
import wmi
import psutil
import platform
import datetime
import os
import sys

def resource_path(relative_path: str) -> str:
    """Get absolute path to a bundled resource. Crucial for PyInstaller --onefile executables."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class HardwareExtractor:
    def __init__(self):
        # Initialize the Windows Management Instrumentation (WMI) client
        self.wmi_client = wmi.WMI()
        
        # 1. Get the absolute path of the current script's directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 2. Join that directory to create a secure, fixed path for the report
        self.output_file = os.path.join(script_dir, "hardware_report.txt")
        
        # Windows API flag to hide console windows during subprocesses
        self.HIDDEN_WINDOW = 0x08000000
        
        print(f"Targeting path: {self.output_file}")

    def get_cpu_info(self) -> dict:
        """Extracts deep CPU specs and hardware-level ACPI thermal zone data."""
        try:
            # WMI Win32_Processor shows us the basic identity.
            cpu = self.wmi_client.Win32_Processor()[0]
            
            # Attempt to pull hardware ACPI temperatures directly from the motherboard.
            # This is crucial for verifying cooling systems without running stress tests.
            current_temp = "Unknown (Blocked by BIOS/Controller)"
            try:
                wmi_root = wmi.WMI(namespace=r"root\wmi")
                thermal_zones = wmi_root.MSAcpi_ThermalZoneTemperature()
                if thermal_zones:
                    celsius = (thermal_zones[0].CurrentTemperature / 10.0) - 273.15
                    current_temp = f"{celsius:.1f} °C"
            except Exception:
                pass

            return {
                "Name": cpu.Name.strip(),
                "Cores": cpu.NumberOfCores,
                "Threads": cpu.NumberOfLogicalProcessors,
                "MaxClock": f"{cpu.MaxClockSpeed} MHz",
                "Cache_L1": f"{cpu.L2CacheSize} KB" if cpu.L2CacheSize else "Unknown",
                "Cache_L2": f"{cpu.L3CacheSize} KB" if cpu.L3CacheSize else "Unknown",
            }
        except Exception as e:
            return {"Error": f"CPU Extraction Error: {str(e)}"}
        
    def get_ram_info(self) -> dict:
        """Extracts active physical memory usage using psutil."""
        try:
            ram = psutil.virtual_memory()
            return {
                "Total_Installed": f"{ram.total / (1024**3):.2f} GB",
                "Currently_Available": f"{ram.available / (1024**3):.2f} GB",
                "Usage_Percentage": f"{ram.percent}%",
            }
        except Exception as e:
            return {"Error": f"RAM Extraction Error: {str(e)}"}
        
    def get_gpu_info(self) -> list:
        """Extracts Graphics Card information and safely patches integer overflows."""
        gpus = []
        try:
            for gpu in self.wmi_client.Win32_VideoController():
                vram_bytes = int(gpu.AdapterRAM) if gpu.AdapterRAM else 0
                
                if vram_bytes < 0:
                    vram_bytes += (1 << 32)

                if vram_bytes > 0:
                    vram_gb = vram_bytes / (1024**3)
                    vram_display = f"{vram_gb:.2f} GB" if vram_gb >= 1 else f"{vram_bytes / (1024**2):.0f} MB"
                else:
                    vram_display = "Dynamic/Shared Memory"

                gpus.append({
                    "Model": gpu.Name.strip() if gpu.Name else "Unknown",
                    "VRAM": vram_display,
                    "Driver_Version": gpu.DriverVersion if gpu.DriverVersion else "Unknown",
                    "Status": gpu.Status if gpu.Status else "Unknown",
                    "Video_Mode": gpu.VideoModeDescription.strip() if gpu.VideoModeDescription else "Unknown",
                    "Manufacturer": gpu.AdapterCompatibility.strip() if gpu.AdapterCompatibility else "Unknown"
                })
            return gpus
        except Exception as e:
            return [{"Error": f"GPU Extraction Error: {str(e)}"}]
        
    def get_physical_ram_specs(self) -> list:
        """Extracts physical RAM stick details to check for mismatched speeds/brands."""
        sticks = []
        try:
            for mem in self.wmi_client.Win32_PhysicalMemory():
                sticks.append({
                    "Capacity": f"{int(mem.Capacity) / (1024**3):.0f} GB",
                    "Speed": f"{mem.Speed} MHz" if mem.Speed else "Unknown",
                    "Manufacturer": mem.Manufacturer.strip() if mem.Manufacturer else "Unknown",
                    "Part_Number": mem.PartNumber.strip() if mem.PartNumber else "Unknown",
                    "Serial_Number": mem.SerialNumber.strip() if mem.SerialNumber else "Unknown"
                })
            return sticks
        except Exception as e:
            return [{"Error": f"RAM Spec Error: {str(e)}"}]

    def get_display_info(self) -> list:
        """Extracts active monitor specs, pixel depth, and deep EDID panel data for color accuracy lookup."""
        displays = []
        try:
            # 1. Get raw panel EDID from root\wmi (Manufacturer and Model ID)
            edid_panels = []
            try:
                wmi_root = wmi.WMI(namespace=r"root\wmi")
                for m in wmi_root.WmiMonitorID():
                    mfg = "".join([chr(c) for c in m.ManufacturerName if c > 0])
                    model = "".join([chr(c) for c in m.ProductCodeID if c > 0])
                    edid_panels.append(f"{mfg} {model}".strip())
            except Exception:
                pass # Usually fails if no external monitor is attached or admin rights are missing

            # 2. Get standard resolution and deep technical specs
            idx = 0
            for monitor in self.wmi_client.Win32_VideoController():
                # We only want active displays, so we check if a refresh rate exists
                if monitor.CurrentRefreshRate and monitor.CurrentHorizontalResolution:
                    panel_id = edid_panels[idx] if idx < len(edid_panels) else "Unknown/Generic"

                    displays.append({
                        "Monitor_Name": monitor.Name.strip() if monitor.Name else "Unknown",
                        "Manufacturer": monitor.AdapterCompatibility.strip() if monitor.AdapterCompatibility else "Unknown",
                        "Resolution": f"{monitor.CurrentHorizontalResolution}x{monitor.CurrentVerticalResolution}",
                        "Refresh_Rate": f"{monitor.CurrentRefreshRate} Hz",
                        "Pixel_Depth": f"{monitor.CurrentBitsPerPixel} bits" if monitor.CurrentBitsPerPixel else "Unknown",
                        "True_Panel_ID_EDID": panel_id,
                        "Status": monitor.Status if monitor.Status else "Unknown"
                    })
                    idx += 1
                    
            return displays if displays else [{"Status": "No active display detected"}]
        except Exception as e:
            return [{"Error": f"Display Extraction Failed: {str(e)}"}]

    def get_motherboard_info(self) -> dict:
        """Extracts the core motherboard fingerprint, BIOS status, and calculates true Hardware Age."""
        try:
            board = self.wmi_client.Win32_BaseBoard()[0]
            bios = self.wmi_client.Win32_BIOS()[0]
            
            # Formatting the WMI date string
            bios_date_formatted = "Unknown"
            if bios.ReleaseDate:
                raw_date = bios.ReleaseDate.split('.')[0]
                if len(raw_date) >= 8:
                    try:
                        bios_date_formatted = datetime.datetime.strptime(raw_date[:8], "%Y%m%d").strftime("%Y-%m-%d")
                    except ValueError:
                        bios_date_formatted = raw_date
            
            # Calculate Age
            hardware_age = "Unknown"
            if bios_date_formatted and len(bios_date_formatted) >= 4:
                bios_year = int(bios_date_formatted[:4])
                current_year = datetime.datetime.now().year
                hardware_age = f"{current_year - bios_year} Years Old"

            return {
                "Manufacturer": board.Manufacturer.strip() if board.Manufacturer else "Unknown",
                "Product_Model": board.Product.strip() if board.Product else "Unknown",
                "Serial_Number": board.SerialNumber.strip() if board.SerialNumber else "Unknown",
                "BIOS_Version": bios.SMBIOSBIOSVersion.strip() if bios.SMBIOSBIOSVersion else "Unknown",
                "BIOS_Release_Date": bios_date_formatted if bios_date_formatted else "Unknown",
                "Hardware_Age": hardware_age,
                "BIOS_Vendor": bios.Manufacturer.strip() if bios.Manufacturer else "Unknown"
            }
        except Exception as e:
            return {"Error": f"Motherboard Extraction Error: {str(e)}"}    

    def get_network_info(self) -> list:
        """Extracts hardware-bound MAC addresses to verify adapter integrity and check for spoofing."""
        macs = []
        try:
            # PhysicalAdapter=True filters out useless virtual VPN/VMware adapters
            for nic in self.wmi_client.Win32_NetworkAdapter(PhysicalAdapter=True):
                current_mac = nic.MACAddress.strip() if nic.MACAddress else None
                permanent_mac = nic.PermanentAddress.strip() if getattr(nic, 'PermanentAddress', None) else None
                
                # Check if the user is masking their true hardware MAC
                is_spoofed = False
                if permanent_mac and current_mac != permanent_mac:
                    is_spoofed = True
                
                macs.append({
                    "Adapter_Name": nic.Name.strip() if nic.Name else "Unknown",
                    "Manufacturer": nic.Manufacturer.strip() if nic.Manufacturer else "Unknown",
                    "MAC_Current": current_mac or "Unknown",
                    "MAC_Hardware_Burned": permanent_mac or "Unknown",
                    "MAC_Spoofed": is_spoofed,
                    "Connection_Status": "Connected" if nic.NetConnectionStatus == 2 else "Disconnected",
                })
            return macs
            
        except Exception as e:
            return [{"Error": f"Network Hardware Extraction Error: {str(e)}"}]
         
    def get_battery_info(self) -> dict:
        """Extracts battery health and cycle degradation."""
        try:
            battery_stats = self.wmi_client.query("SELECT * FROM Win32_Battery")
            if not battery_stats:
                return {"Status": "No Battery Detected (Likely a Desktop or Failed ACPI)"}
            
            b = battery_stats[0]
            full = b.FullChargeCapacity if b.FullChargeCapacity else "Unknown"
            design = b.DesignCapacity if b.DesignCapacity else "Unknown"
            
            # The wear level is the delta between what the factory designed it to hold, 
            # and what the battery chemistry can actually hold today.
            return {
                "Status": b.Status,
                "Design_Capacity": f"{design} mWh" if isinstance(design, int) else design,
                "Full_Charge_Capacity": f"{full} mWh" if isinstance(full, int) else full,
                "Battery_Health_Percentage": f"{(full / design * 100):.2f}%" if isinstance(full, int) and isinstance(design, int) and design > 0 else "Unknown",
                "Wear_Level": f"{((design - full) / design * 100):.2f}%" if isinstance(full, int) and isinstance(design, int) and design > 0 else "Unknown",
            }
        except Exception as e:
            return {"Error": f"Battery Error: {str(e)}"}
        
    def _get_smartctl_fallback(self, drive_index: int):
        """
        Ultimate Fallback: Bypasses Windows to pull direct SMART data using smartctl.exe.
        BEST PRACTICE: We use JSON output (-j) instead of string parsing to ensure
        the script doesn't crash if a specific drive manufacturer formats their text weirdly.
        """
        try:
            smartctl_path = resource_path("smartctl.exe")
            
            if not os.path.exists(smartctl_path):
                return None, None 

            # /dev/pd{X} targets the raw silicon, ignoring Windows logical volumes
            cmd = [smartctl_path, "-a", "-j", f"/dev/pd{drive_index}"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=self.HIDDEN_WINDOW)
            
            if not result.stdout.strip():
                return None, None
                
            data = json.loads(result.stdout)
            hours = None
            temp = None
            
            # MODERN PROTOCOL: NVMe Drives log data in a specific health structure
            if "nvme_smart_health_information_log" in data:
                hours = data["nvme_smart_health_information_log"].get("power_on_hours")
                temp = data["nvme_smart_health_information_log"].get("temperature")
                
            # LEGACY PROTOCOL: Mechanical IDE/SATA drives use the ATA Attribute Table
            elif "ata_smart_attributes" in data:
                for attr in data["ata_smart_attributes"].get("table", []):
                    # ID 9 is industry standard for Hours, ID 194 is Temp
                    if attr.get("id") == 9:
                        hours = attr.get("raw", {}).get("value")
                    elif attr.get("id") == 194:
                        temp = attr.get("raw", {}).get("value")
                        
            return hours, temp
            
        except Exception:
            return None, None

    def get_unified_storage_info(self) -> list:
        """Extracts complete physical and health data, injecting warnings for legacy IDE/HDD setups."""
        formatted_disks = []
        
        # 1. Grab Immutable Hardware IDs from WMI
        physical_disks = {}
        try:
            for disk in self.wmi_client.Win32_DiskDrive():
                clean_model = disk.Model.strip() if disk.Model else "Unknown"
                physical_disks[clean_model] = {
                    "Model": clean_model,
                    "Serial": disk.SerialNumber.strip() if disk.SerialNumber else "Unknown",
                    "Size_GB": round(int(disk.Size) / (1024**3), 2) if disk.Size else "Unknown",
                    "Interface": disk.InterfaceType.strip() if disk.InterfaceType else "Unknown"
                }
        except Exception as e:
            return [{"Error": f"WMI Physical Disk Extraction Failed: {str(e)}"}]

        # 2. Try PowerShell for OS-level health counters
        ps_command = """
        $disks = Get-PhysicalDisk
        $results = @()
        foreach ($disk in $disks) {
            $counters = $disk | Get-StorageReliabilityCounter
            $results += [PSCustomObject]@{
                Model = $disk.Model
                MediaType = $disk.MediaType
                HealthStatus = $disk.HealthStatus
                Wear = $counters.Wear
            }
        }
        $results | ConvertTo-Json -Compress
        """
        
        try:
            result = subprocess.run(["powershell", "-Command", ps_command], capture_output=True, text=True, creationflags=self.HIDDEN_WINDOW)
            
            if not result.stdout.strip():
                return [{"Error": "ACCESS DENIED: Administrator privileges required for deep storage data."}]

            ps_data = json.loads(result.stdout)
            if isinstance(ps_data, dict):
                ps_data = [ps_data]

            # 3. Match health data to hardware IDs, utilizing the smartctl bypass if OS fails
            drive_index_counter = 0
            for disk in ps_data:
                model = disk.get("Model", "Unknown").strip()
                media_type = disk.get("MediaType", "Unknown")
                
                wear = disk.get("Wear")
                hours = disk.get("PowerOnHours")

                # The Hardware Bypass Fallback
                # If Windows blocked the read, we force the question directly to the hardware controller
                if hours is None:
                    smart_hours, smart_temp = self._get_smartctl_fallback(drive_index_counter)
                    if smart_hours is not None: hours = smart_hours

                base_info = physical_disks.get(model, {})
                interface = base_info.get("Interface", "Unknown")
                
                # Zero-Trust Flagging for ancient/failing hardware
                # Mechanical drives are unacceptable for modern professional reliability
                normie_warning = "None"
                if "IDE" in interface or "HDD" in str(media_type):
                    normie_warning = "CRITICAL: Mechanical or IDE drive detected. Expect severe performance bottlenecks."

                formatted_disks.append({
                    "Model": model,
                    "Serial_Number": base_info.get("Serial", "Unknown"),
                    "Size_GB": base_info.get("Size_GB", "Unknown"),
                    "Interface": interface,
                    "Type": media_type,
                    "OS_Health_Status": disk.get("HealthStatus", "Unknown"),
                    "Wear_Level": f"{wear}%" if wear is not None else "N/A (HDD)",
                    "Normie_Warning": normie_warning
                })
                
                # Incremented so the smartctl fallback checks the correct drive next loop
                drive_index_counter += 1
                
            return formatted_disks
        except Exception as e:
            return [{"Error": f"Deep Health Extraction Error: {str(e)}"}]

    def get_system_timeline(self) -> dict:
        """Calculates uptime, initial OS installation date, and flags suspicious reboots."""
        try:
            boot_time_timestamp = psutil.boot_time()
            boot_time = datetime.datetime.fromtimestamp(boot_time_timestamp)
            uptime = datetime.datetime.now() - boot_time

            os_info = self.wmi_client.Win32_OperatingSystem()[0]
            raw_date = os_info.InstallDate.split('.')[0] 
            install_date = datetime.datetime.strptime(raw_date, "%Y%m%d%H%M%S").strftime("%Y-%m-%d")

            # Zero-Trust Flag: If uptime is less than 15 minutes, warn the buyer
            warning = "None"
            if uptime.total_seconds() < 900:  # 900 seconds = 15 mins
                warning = "SUSPICIOUS: PC was just rebooted. Use it for 15 minutes to test for thermal throttling or idle crashes before buying."

            return {
                "OS_Original_Install_Date": install_date,
                "Current_Session_Uptime": str(uptime).split('.')[0],
                "Last_Boot_Time": boot_time.strftime("%Y-%m-%d %H:%M:%S"),
                "Normie_Warning": warning
            }
        except Exception as e:
            return {"Error": f"System Timeline Error: {str(e)}"}
        
    def get_abuse_history(self) -> dict:
        """Queries Windows Event Logs for critical power losses, unexpected shutdowns, BSODs, and failing disk I/O."""
        ps_command = """
        $power = (Get-WinEvent -FilterHashtable @{LogName='System'; Id=41} -ErrorAction SilentlyContinue).Count
        $unexpected = (Get-WinEvent -FilterHashtable @{LogName='System'; Id=6008} -ErrorAction SilentlyContinue).Count
        $bsod = (Get-WinEvent -FilterHashtable @{LogName='System'; Id=1001} -ErrorAction SilentlyContinue).Count
        $disk = (Get-WinEvent -FilterHashtable @{LogName='System'; Id=7} -ErrorAction SilentlyContinue).Count
        $thermal = (Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Processor-Power'; Id=37} -ErrorAction SilentlyContinue).Count
        $fetal = (Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'; Id=1} -ErrorAction SilentlyContinue).Count
        
        [PSCustomObject]@{
            CriticalPowerLoss = if ($null -eq $power) {0} else {$power}
            UnexpectedShutdowns = if ($null -eq $unexpected) {0} else {$unexpected}
            BSODs = if ($null -eq $bsod) {0} else {$bsod}
            BadDiskBlocks = if ($null -eq $disk) {0} else {$disk}
            ThermalThrottling = if ($null -eq $thermal) {0} else {$thermal}
            FatalHardwareErrors = if ($null -eq $fetal) {0} else {$fetal}
        } | ConvertTo-Json
        """
        try:
            result = subprocess.run(["powershell", "-Command", ps_command], capture_output=True, text=True, creationflags=self.HIDDEN_WINDOW)
            
            if not result.stdout.strip():
                return {"Status": "ACCESS DENIED - Requires Administrator"}

            data = json.loads(result.stdout)
            
            pwr = data.get("CriticalPowerLoss", 0)
            unexpected = data.get("UnexpectedShutdowns", 0)
            bsods = data.get("BSODs", 0)
            bad_blocks = data.get("BadDiskBlocks", 0)
            thermal = data.get("ThermalThrottling", 0)
            fetal = data.get("FatalHardwareErrors", 0)
            
            # Total crashes combines power failures, forced shutdowns, and blue screens
            total_crashes = pwr + unexpected + bsods
            
            # Stricter translation for professional reliability
            if bad_blocks > 0:
                stability = f"CRITICAL WARNING: {bad_blocks} Bad Disk Blocks. Motherboard I/O or Drive is dying."
            elif total_crashes == 0:
                stability = "Excellent (No logged crashes, BSODs, or forced shutdowns)"
            elif total_crashes < 5:
                stability = "Normal (Occasional crash or forced shutdown)"
            else:
                stability = f"WARNING: High Instability ({total_crashes} critical faults logged)"

            return {
                "Critical_Power_Failures": pwr,
                "Unexpected_Shutdowns": unexpected,
                "Blue_Screens_of_Death": bsods,
                "Disk_Bad_Blocks_Logged": bad_blocks,
                "Historical_Thermal_Throttling": thermal,
                "Fatal_Hardware_Errors": fetal,
                "Total_Crash_Count": total_crashes,
                "System_Stability_Rating": stability,
            }

        except Exception as e:
            return {"Error": f"Event Log Extraction Error: {str(e)}"}
        
    def get_full_ledger(self) -> dict:
        """Compiles all hardware data into a single, clean Python dictionary."""
        os_info = {
            "OS_Name": f"{platform.system()} {platform.release()}",
            "Architecture": platform.architecture()[0],
            "Timeline": self.get_system_timeline()
        }

        return {
            "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "System": os_info,
            "Motherboard": self.get_motherboard_info(),
            "CPU": self.get_cpu_info(),
            "GPU": self.get_gpu_info(),
            "Display": self.get_display_info(),
            "RAM_Physical": self.get_physical_ram_specs(),
            "RAM_Usage": self.get_ram_info(),
            "Battery": self.get_battery_info(),
            "Storage": self.get_unified_storage_info(),
            "Network_Adapters": self.get_network_info(),
            "Abuse_History": self.get_abuse_history()
        }

    def write_report(self):
        """Compiles the ledger into a highly readable, professional text dashboard."""
        data = self.get_full_ledger()

        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write("====================================================\n")
            f.write("      ZERO-TRUST HARDWARE DIAGNOSTIC LEDGER         \n")
            f.write("====================================================\n")
            f.write(f"Generated On: {data.get('Timestamp')}\n\n")

            for category, details in data.items():
                if category == "Timestamp":
                    continue

                f.write(f"[{category.replace('_', ' ').upper()}]\n")
                f.write("-" * 52 + "\n")

                if isinstance(details, dict):
                    for key, value in details.items():
                        clean_key = key.replace("_", " ")
                        
                        # Formatting nested dictionaries cleanly
                        if isinstance(value, dict):
                            f.write(f"  > {clean_key:<25}:\n")
                            for sub_key, sub_val in value.items():
                                clean_sub = sub_key.replace("_", " ")
                                f.write(f"      - {clean_sub:<21}: {sub_val}\n")
                        else:
                            f.write(f"  > {clean_key:<25}: {value}\n")
                
                elif isinstance(details, list):
                    for index, item in enumerate(details):
                        if isinstance(item, dict):
                            f.write(f"  -- Item {index + 1} --\n")
                            for key, value in item.items():
                                clean_key = key.replace("_", " ")
                                f.write(f"     * {clean_key:<22}: {value}\n")
                        else:
                            f.write(f"  > {item}\n")
                        f.write("\n")
                
                else:
                    f.write(f"  > {details}\n")
                
                f.write("\n")
        
        print(f"[*] Extraction Complete. Report saved to: {self.output_file}")
        
if __name__ == "__main__":
    print("[*] Accessing deep Kernel Data and System Logs...")
    extractor = HardwareExtractor()
    extractor.write_report()
    input("\nPress ENTER to exit...")