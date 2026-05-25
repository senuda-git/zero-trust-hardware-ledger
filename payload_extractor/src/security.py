import hashlib
import json
import zlib
import base64
import qrcode
from hardware import HardwareExtractor

class TrustLayer:
    def __init__(self, raw_data: dict):
        self.raw_data = raw_data

    def generate_secure_payload(self) -> str:
        """Compresses, hashes, and encodes the data for Zero-Trust verification."""
        
        # 1. Minification & Key Shortening (Saves massive QR space)
        minified_payload = {
            "sys": self.raw_data.get("System"),
            "mb": self.raw_data.get("Motherboard"),
            "cpu": self.raw_data.get("CPU"),
            "gpu": self.raw_data.get("GPU"),
            "disp": self.raw_data.get("Display"),
            "ram_p": self.raw_data.get("RAM_Physical"),
            "ram_u": self.raw_data.get("RAM_Usage"),
            "bat": self.raw_data.get("Battery"),
            "strg_b": self.raw_data.get("Storage_Basic"),
            "strg_d": self.raw_data.get("Storage_Deep_SMART"),
            "net": self.raw_data.get("Network_Adapters"),
            "ab": self.raw_data.get("Abuse_History")
        }

        # 2. Convert to string and seal with SHA-256
        json_string = json.dumps(minified_payload, separators=(',', ':'))
        hasher = hashlib.sha256()
        hasher.update(json_string.encode('utf-8'))
        signature = hasher.hexdigest()

        # 3. Create the final package
        final_package = {
            "p": minified_payload,
            "s": signature
        }

        # 4. Extreme Compression (Zlib) & Encoding (Base64)
        package_string = json.dumps(final_package, separators=(',', ':')).encode('utf-8')
        compressed_data = zlib.compress(package_string, level=9)
        encoded_data = base64.urlsafe_b64encode(compressed_data).decode('utf-8')

        # 5. The App Trigger (URI Scheme)
        return f"hwledger://verify?data={encoded_data}"

    def display_qr(self, secure_uri: str):
        """Converts the secure URI into a highly scannable visual QR code."""
        
        # We use the qrcode library to generate a QR code with optimal settings for phone cameras.
        qr = qrcode.QRCode(
            version=None, 
            error_correction=qrcode.constants.ERROR_CORRECT_M, # Better for phone cameras
            box_size=10,
            border=6,
        )
        qr.add_data(secure_uri)
        qr.make(fit=True)

        # Display the QR code
        img = qr.make_image(fill_color="#0D1117", back_color="#FFFFFF")
        img.show()

if __name__ == "__main__":
    print("[*] Extracting deep hardware telemetry... Please wait.")
    
    # We extract the full ledger of hardware data using our custom extractor
    try:
        extractor = HardwareExtractor()
        data = extractor.get_full_ledger()
    

        print("[*] Compressing and applying Cryptographic Seal...")
        security = TrustLayer(data)
    
        secure_uri = security.generate_secure_payload()
        
        print(f"[*] Secure URI Generated (Length: {len(secure_uri)} chars)")
        print("[*] Generating Zero-Trust QR Code...")
        
        security.display_qr(secure_uri)
        
    except Exception as e:
        print(f"\n[!] CRITICAL ERROR during extraction or encryption: {str(e)}")
    
    finally:
        input("\n[*] Extraction complete. Press ENTER to close the program...")
            