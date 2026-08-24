import hashlib
import json
import zlib
import base64
import qrcode
import os
from hardware import HardwareExtractor

# Where the verification web page is hosted
GITHUB_PAGES_URL = "https://senuda-git.github.io/zero-trust-hardware-ledger/"

# Maximum Zlib compression to minimize QR density
COMPRESSION_LEVEL = 9

# Payload format version — bump this if you change the compact key schema
PAYLOAD_VERSION = 2

# Safe upper limit for a Version 40-L QR code URI. The absolute max is ~2953 bytes.
QR_MAX_URI_LENGTH = 2900


def _strip_empty(obj):
    """Recursively removes None and 'Unknown' values to save QR space.
    Keeps 0, False, and empty lists since those carry meaning."""
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            stripped = _strip_empty(v)
            if stripped is not None and stripped != "Unknown" and stripped != "":
                cleaned[k] = stripped
        return cleaned if cleaned else None
    elif isinstance(obj, list):
        cleaned = [_strip_empty(i) for i in obj]
        return [i for i in cleaned if i is not None]
    return obj

def _handle_data_overflow(uri_length: int):
    """Creates and opens a specific error file for QR data overflow."""
    error_file = "Hardware-Ledger-Error.txt"
    with open(error_file, "w") as f:
        f.write("CRITICAL ERROR: Hardware telemetry payload exceeded maximum QR Code density.\n")
        f.write("This PC has too many crash logs or components to compress into an offline image.\n")
        f.write(f"Generated Data Length: {uri_length} characters (Max is ~{QR_MAX_URI_LENGTH}).\n")
    if os.name == "nt":
        os.startfile(error_file)


class TrustLayer:
    """Handles compression, hashing, and QR generation for hardware payloads."""

    def __init__(self, raw_data: dict):
        self.raw_data = raw_data

    def _build_compact_payload(self) -> dict:
        """Strips non-essential fields, minifies keys, and transforms values for maximum QR density.

        Only includes data critical for trust scoring and hardware identification.
        Fields like WinSAT, Display EDID, and RAM part numbers are dropped because
        they don't affect the trust score and bloat the QR code.
        """
        d = self.raw_data

        cpu = d.get("CPU") or {}
        gpu_list = d.get("GPU") or []
        ram = d.get("RAM_Usage") or {}
        mb = d.get("Motherboard") or {}
        storage = d.get("Storage_Deep_SMART") or []
        bat = d.get("Battery") or {}
        net = d.get("Network_Adapters") or []
        abuse = d.get("Abuse_History") or {}
        sys_info = d.get("System") or {}
        timeline = (sys_info.get("Timeline") or {}) if isinstance(sys_info, dict) else {}

        compact = {"v": PAYLOAD_VERSION, "t": int(d.get("Unix_Timestamp", 0))}

        # CPU — name, cores, threads (identifies the machine)
        if "Error" not in cpu:
            compact["c"] = {
                "n": cpu.get("Name"),
                "co": cpu.get("Cores"),
                "th": cpu.get("Threads"),
                "cl": float(cpu.get("MaxClock", "0").split()[0]) if cpu.get("MaxClock") else None,
            }

        # GPU — model and VRAM per card (skip driver/status to save space)
        gpus = []
        for g in gpu_list:
            if "Error" not in g:
                vram_val = None
                if g.get("VRAM") and "GB" in g.get("VRAM"):
                    try:
                        vram_val = float(g.get("VRAM").split()[0])
                    except (ValueError, IndexError):
                        pass
                gpus.append({"m": g.get("Model"), "vr": vram_val})
        if gpus:
            compact["g"] = gpus

        # RAM — total installed is all the buyer needs to see
        if "Error" not in ram:
            ram_val = None
            if ram.get("Total_Installed") and "GB" in ram.get("Total_Installed"):
                try:
                    ram_val = float(ram.get("Total_Installed").split()[0])
                except (ValueError, IndexError):
                    pass
            compact["r"] = ram_val

        # Motherboard — hardware fingerprint for component-swap detection
        if "Error" not in mb:
            compact["b"] = {
                "mfg": mb.get("Manufacturer"),
                "m": mb.get("Product_Model"),
                "s": mb.get("Serial_Number"),
            }

        # Storage — health data is trust-critical
        disks = []
        for s in storage:
            if "Error" not in s:
                health_map = {"Healthy": "H", "Warning": "W", "Unhealthy": "U"}
                health_code = health_map.get(s.get("OS_Health_Status"), "U")

                warn_str = s.get("Normie_Warning", "None")
                warn_code = "C" if "CRITICAL" in warn_str else None

                wear_val = None
                if s.get("Wear_Level") and "%" in s.get("Wear_Level"):
                    try: wear_val = int(s.get("Wear_Level").replace('%', ''))
                    except (ValueError, IndexError): pass

                size_val = None
                if s.get("Size_GB") and "GB" in s.get("Size_GB"):
                    try: size_val = float(s.get("Size_GB").split()[0])
                    except (ValueError, IndexError): pass

                disk_payload = {
                    "m": s.get("Model"),
                    "sz": size_val,
                    "h": health_code,
                    "w": wear_val,
                }
                if warn_code:
                    disk_payload["nw"] = warn_code
                disks.append(disk_payload)
        if disks:
            compact["st"] = disks

        # Battery — health percentage and wear level
        if "Error" not in bat:
            if "No Battery" in bat.get("Status", ""):
                compact["bt"] = {"st": "N/A"}
            else:
                health_val, wear_val = None, None
                try: health_val = float(bat.get("Battery_Health_Percentage", "0").replace('%', ''))
                except (ValueError, IndexError): pass
                try: wear_val = float(bat.get("Wear_Level", "0").replace('%', ''))
                except (ValueError, IndexError): pass

                compact["bt"] = {
                    "h": health_val,
                    "w": wear_val,
                }

        # Network — MAC spoof detection is trust-critical
        nics = [{"ma": n.get("MAC_Current"), "sp": 1 if n.get("MAC_Spoofed") else 0} for n in net if "Error" not in n]
        if nics:
            compact["n"] = nics

        # Abuse history — the core of the trust score, every field matters
        if "Error" not in abuse and "Status" not in abuse:
            compact["ab"] = {
                "p": abuse.get("Critical_Power_Failures", 0),
                "u": abuse.get("Unexpected_Shutdowns", 0),
                "b": abuse.get("Blue_Screens_of_Death", 0),
                "d": abuse.get("Disk_Bad_Blocks_Logged", 0),
                "t": abuse.get("Historical_Thermal_Throttling", 0),
                "f": abuse.get("Fatal_Hardware_Errors", 0),
            }

        # System uptime — suspicious if machine was just rebooted before sale
        if timeline:
            uptime_info = {}
            warning = timeline.get("Normie_Warning")
            if warning and warning != "None":
                uptime_info["w"] = "S" # Suspicious
            if uptime_info:
                compact["sy"] = uptime_info

        return _strip_empty(compact)

    def generate_secure_payload(self) -> str:
        """Compresses, hashes, and encodes the payload for QR transmission."""
        def _create_uri_from_payload(payload_dict: dict) -> str:
            """Helper to perform the serialization, sealing, and encoding pipeline."""
            # Serialize to minimal JSON — sort_keys ensures deterministic hashing
            payload_str = json.dumps(payload_dict, separators=(",", ":"), sort_keys=True)
            # SHA-256 seal — any modification breaks this hash
            signature = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
            # Package the raw JSON string alongside its hash
            package = json.dumps({"p": payload_str, "s": signature}, separators=(",", ":"))
            # Default zlib stream is the interoperable standard for QR payload transport.
            # The SPA reads it using the browser-native decompressor when available, with a
            # proper fallback for legacy environments.
            compressed = zlib.compress(package.encode("utf-8"), level=COMPRESSION_LEVEL)
            encoded = base64.urlsafe_b64encode(compressed).decode("utf-8")
            return f"{GITHUB_PAGES_URL}?d={encoded}"

        # Build the compact payload with all data
        full_payload = self._build_compact_payload()
        secure_uri = _create_uri_from_payload(full_payload)

        return secure_uri

    def display_qr(self, secure_uri: str):
        """Renders the secure URI as a high-contrast QR code and opens it with the default image viewer."""
        try:
            # Pre-emptive check to avoid the DataOverflowError from the library
            if len(secure_uri) > QR_MAX_URI_LENGTH:
                _handle_data_overflow(len(secure_uri))
                return

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L,  # Lowest overhead for max data
                box_size=25,
                border=5,
            )
            qr.add_data(secure_uri)
            qr.make(fit=True)

            img = qr.make_image(fill_color="#000000", back_color="#FFFFFF")

            # Save locally to bypass Antivirus Temp folder restrictions
            qr_filename = "Hardware-Ledger-QR.png"
            img.save(qr_filename)

            if os.name == "nt":
                os.startfile(qr_filename)

        except qrcode.exceptions.DataOverflowError:
            # This will be triggered if even the trimmed payload is too large.
            _handle_data_overflow(len(secure_uri))


if __name__ == "__main__":
    print("[*] Extracting deep hardware telemetry... Please wait.")

    try:
        extractor = HardwareExtractor()
        data = extractor.get_full_ledger()

        print("[*] Compressing and applying Cryptographic Seal...")
        security = TrustLayer(data)

        # --- FOR DEBUGGING ---
        # Uncomment the line below to print the full compact payload to the console.
        # print(json.dumps(security._build_compact_payload(), indent=2))

        secure_uri = security.generate_secure_payload()

        print(f"[*] Secure URI Generated (Length: {len(secure_uri)} chars)")
        print("[*] Generating Zero-Trust QR Code...")

        security.display_qr(secure_uri)

    except Exception as e:
        # Failsafe for complete extraction collapse
        with open("Hardware-Ledger-Crash.txt", "w") as f:
            f.write(f"CRITICAL ERROR during extraction or encryption:\n{str(e)}")
        if os.name == "nt":
            os.startfile("Hardware-Ledger-Crash.txt")
            
