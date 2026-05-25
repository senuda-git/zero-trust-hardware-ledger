package com.example.hwledger

import android.util.Base64
import java.io.ByteArrayOutputStream
import java.security.MessageDigest
import java.util.zip.Inflater
import org.json.JSONObject

class LedgerDecoder {

    // A data class to hold our final UI results
    data class VerificationResult(
        val isAuthentic: Boolean,
        val payload: JSONObject?,
        val errorMessage: String? = null
    )

    fun unpackAndVerify(scannedUri: String): VerificationResult {
        try {
            // 1. Strip the custom scheme to isolate the Base64 data
            if (!scannedUri.startsWith("hwledger://verify?data=")) {
                return VerificationResult(false, null, "Invalid QR Format")
            }
            val base64Data = scannedUri.substringAfter("data=")

            // 2. Base64 Decode
            val compressedBytes = Base64.decode(base64Data, Base64.DEFAULT)

            // 3. Zlib Decompression (The reverse of Python's zlib.compress)
            val inflater = Inflater()
            inflater.setInput(compressedBytes)
            val outputStream = ByteArrayOutputStream()
            val buffer = ByteArray(1024)
            while (!inflater.finished()) {
                val count = inflater.inflate(buffer)
                outputStream.write(buffer, 0, count)
            }
            inflater.end()
            val jsonString = outputStream.toString("UTF-8")

            // 4. Parse the JSON Package
            val packageJson = JSONObject(jsonString)
            val payloadObj = packageJson.getJSONObject("p")
            val providedSignature = packageJson.getString("s")

            // 5. The Zero-Trust Verification (Re-hash the payload)
            // We must minify the JSON exactly like Python did: separators=(',', ':')
            val minifiedPayloadString = payloadObj.toString()

            val digest = MessageDigest.getInstance("SHA-256")
            val hashBytes = digest.digest(minifiedPayloadString.toByteArray(Charsets.UTF_8))
            val calculatedSignature = hashBytes.joinToString("") { "%02x".format(it) }

            // 6. The Final Check
            return if (calculatedSignature == providedSignature) {
                VerificationResult(true, payloadObj) // Authentic!
            } else {
                VerificationResult(false, null, "TAMPER DETECTED: Hashes do not match.")
            }

        } catch (e: Exception) {
            return VerificationResult(false, null, "Decryption Failed: ${e.message}")
        }
    }
}