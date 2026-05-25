# 🛡️ Zero-Trust Hardware Diagnostic Ledger

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Kotlin](https://img.shields.io/badge/Kotlin-Android-green.svg)
![Cryptography](https://img.shields.io/badge/Security-SHA--256-red.svg)
![ML Kit](https://img.shields.io/badge/Vision-Google_ML_Kit-yellow.svg)

## The Problem
In the second-hand PC and laptop market, buyers rely on trust. Diagnostic tools like HWiNFO are easily spoofed by scammers who can edit text reports, hide historical system crashes, or swap components before a sale. 

## The Solution
A Zero-Trust, immutable diagnostic pipeline. This project extracts deep kernel-level hardware telemetry, compresses it, signs it with a cryptographic hash, and transmits it via a QR code directly to a bespoke Android verification app. **No network connection required. No editable files left on the host machine.**

### 📸 Demonstration
*(Drop a GIF here of your Android phone scanning your computer screen and flashing the red/green Trust Score)*

---

## ⚙️ System Architecture

### Phase 1: Deep Telemetry Extraction (Python / Windows Kernel)
* **Kernel Bypass:** Utilizes raw WMI namespaces and hidden PowerShell execution to extract data that legacy SATA controllers attempt to block (e.g., S.M.A.R.T. Wear Levels, Power-On Hours).
* **The "Ghost" Log:** Queries the Windows Event Viewer to extract historical `Event 41` (Critical Power Loss) and `Event 6008` (Unexpected Shutdown) logs, exposing fundamentally unstable machines.
* **Hardware Fingerprinting:** Extracts Motherboard Serial Numbers and Network MAC addresses to prevent component swapping and verify HWID ban statuses.

### Phase 2: The Cryptographic Handshake
* **Minification & Compression:** The payload is minified and subjected to `Zlib` compression (Level 9) to fit massive JSON datasets into a physically scannable QR matrix.
* **Immutability:** The data is signed using a **SHA-256 cryptographic hash**. If a scammer alters a single byte of the payload to hide a crash, the signature breaks, and the mobile scanner flags the device as tampered.
* **Base64 Encoding:** Generates a custom URI scheme (`hwledger://verify?data=...`) encoded into a high-contrast visual matrix for optical transmission.

### Phase 3: Android Optics & Trust UI (Kotlin)
* **High-Speed Optics:** Implements **CameraX** and **Google ML Kit** for instantaneous, off-thread QR code parsing.
* **Decryption Engine:** Catches the custom URI via Android Intent Filters, reverses the Base64/Zlib compression, and recalculates the SHA-256 hash locally.
* **The Trust Algorithm:** Translates raw JSON data into a human-readable financial risk score, heavily penalizing historical system crashes and hidden thermal failures.

---

## 🚀 How to Run

### The Payload Extractor (Windows)
1. Download the compiled executable from the `/payload_extractor/dist/` folder.
2. Run `HardwareLedger_Scanner.exe` as an Administrator (Required for deep kernel S.M.A.R.T. extraction).
3. The host machine will generate a secure QR code on the screen.

### The Verification Scanner (Android)
1. Build the APK from the `/android_scanner/` source using Android Studio.
2. Grant camera permissions.
3. Scan the generated QR code to verify hardware authenticity and calculate the Trust Score.