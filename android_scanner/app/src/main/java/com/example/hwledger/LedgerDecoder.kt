package com.example.hwledger

import android.util.Base64
import java.io.ByteArrayOutputStream
import java.security.MessageDigest
import java.util.zip.Inflater
import org.json.JSONObject

class LedgerDecoder {

    data class VerificationResult(
        val isAuthentic: Boolean,
        val payload: JSONObject?,
        val errorMessage: String? = null
    )

    fun unpackAndVerify(scannedUri: String): VerificationResult {
        try {
            // 1. Strip the custom scheme
            if (!scannedUri.startsWith("hwledger://verify?data=")) {
                return VerificationResult(false, null, "Invalid QR Format")
            }
            val base64Data = scannedUri.substringAfter("data=").trim()

            // 2. Base64 Decode outer shell
            val compressedBytes = Base64.decode(base64Data, Base64.URL_SAFE or Base64.NO_WRAP)

            // 3. Zlib Decompression
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

            // 4. Parse the Outer Package
            val packageJson = JSONObject(jsonString)

            // We extract the pure Base64 text and signature
            val payloadB64 = packageJson.getString("p")
            val providedSignature = packageJson.getString("s")

            // 5. The Zero-Trust Verification (Hash the pure text)
            val digest = MessageDigest.getInstance("SHA-256")
            val hashBytes = digest.digest(payloadB64.toByteArray(Charsets.UTF_8))
            val calculatedSignature = hashBytes.joinToString("") { "%02x".format(it) }

            // 6. The Final Check
            return if (calculatedSignature == providedSignature) {

                // Decode the inner Base64 armor back into the JSON Object for the UI
                val decodedPayloadBytes = Base64.decode(payloadB64, Base64.DEFAULT)
                val decodedJsonString = String(decodedPayloadBytes, Charsets.UTF_8)
                val payloadObj = JSONObject(decodedJsonString)

                VerificationResult(true, payloadObj)
            } else {
                VerificationResult(false, null, "TAMPER DETECTED: Hashes do not match.")
            }

        } catch (e: Exception) {
            return VerificationResult(false, null, "Decryption Failed: ${e.message}")
        }
    }
}