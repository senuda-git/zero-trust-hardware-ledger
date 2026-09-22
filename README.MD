# 🛡️ Zero-Trust Hardware Diagnostic Ledger

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Kotlin](https://img.shields.io/badge/Kotlin-Android-green.svg)
![Cryptography](https://img.shields.io/badge/Security-SHA--256-red.svg)
![ML Kit](https://img.shields.io/badge/Vision-Google_ML_Kit-yellow.svg)

## The Problem
In the second-hand PC and laptop market, buyers rely heavily on trust. Standard diagnostic tools are easily spoofed by bad actors who can edit text reports, hide historical system crashes, or swap components before a sale. 

## The Solution
A secure, tamper-proof diagnostic pipeline. This project extracts accurate hardware health data, compresses it, securely signs it, and transmits it via a QR code directly to a custom Android verification app. It requires no network connection and leaves no editable files on the host machine.

## ⚙️ System Architecture

### Phase 1: Deep Telemetry Extraction (Python / Windows Kernel)
Securely pulls critical hardware data (like hard drive wear levels and power-on hours) directly from the operating system. It also checks system event logs for histories of unexpected shutdowns to expose unstable machines, and logs motherboard/network serial numbers to prevent component swapping.

### Phase 2: Secure Data Packaging
To fit massive datasets into a physically scannable QR code, the payload is heavily compressed. More importantly, the data is signed using a SHA-256 cryptographic hash. If a scammer alters a single byte of the data to hide a crash, the signature breaks, and the mobile app flags the device as tampered.

### Phase 3: Android Verification App (Kotlin)
Utilizes the phone's camera for rapid, offline QR code parsing. The app catches the QR code, reverses the compression, recalculates the hash to verify authenticity, and translates the raw data into a human-readable "Trust Score" (penalizing historical crashes and hardware degradation).

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
