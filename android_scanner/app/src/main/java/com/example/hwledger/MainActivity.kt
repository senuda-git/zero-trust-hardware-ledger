package com.example.hwledger

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Log
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var cameraExecutor: ExecutorService
    private lateinit var viewFinder: PreviewView
    private lateinit var statusText: TextView
    private var isScanning = true

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) startCamera() 
        else {
            Toast.makeText(this, getString(R.string.permission_denied), Toast.LENGTH_SHORT).show()
            finish()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        viewFinder = findViewById(R.id.viewFinder)
        statusText = findViewById(R.id.statusText)
        cameraExecutor = Executors.newSingleThreadExecutor()

        findViewById<ImageButton>(R.id.btnCloseScanner).setOnClickListener { finish() }

        if (allPermissionsGranted()) startCamera()
        else requestPermissionLauncher.launch(Manifest.permission.CAMERA)
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()
            val preview = Preview.Builder().build().also { it.setSurfaceProvider(viewFinder.surfaceProvider) }
            val imageAnalyzer = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
                .also {
                    it.setAnalyzer(cameraExecutor, QrCodeAnalyzer { qrData ->
                        runOnUiThread { processScannedData(qrData) }
                    })
                }
            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, imageAnalyzer)
            } catch (exc: Exception) { Log.e("Scanner", "Error", exc) }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun processScannedData(scannedUri: String) {
        if (!isScanning || !scannedUri.startsWith("hwledger://")) return
        isScanning = false

        // Haptic feedback (if available)
        viewFinder.performHapticFeedback(android.view.HapticFeedbackConstants.LONG_PRESS)

        statusText.text = getString(R.string.status_decrypting)
        statusText.setTextColor(getColor(R.color.apple_orange))

        val decoder = LedgerDecoder()
        val result = decoder.unpackAndVerify(scannedUri)

        if (result.isAuthentic) {
            val intent = Intent(this, DashboardActivity::class.java)
            intent.putExtra("PAYLOAD_JSON", result.payload?.toString())
            startActivity(intent)
            finish()
        } else {
            // Save failed scan to history too
            result.payload?.let { ScanHistoryManager.saveScan(this, it, false) }
            
            statusText.text = getString(R.string.status_tamper)
            statusText.setTextColor(getColor(R.color.apple_red))
            viewFinder.postDelayed({ 
                isScanning = true
                statusText.text = getString(R.string.scanner_status)
                statusText.setTextColor(getColor(R.color.white))
            }, 3000)
        }
    }

    private fun allPermissionsGranted() = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    override fun onDestroy() { super.onDestroy(); cameraExecutor.shutdown() }

    private inner class QrCodeAnalyzer(private val onQrCodeScanned: (String) -> Unit) : ImageAnalysis.Analyzer {
        private val scanner = BarcodeScanning.getClient(BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build())
        @androidx.camera.core.ExperimentalGetImage
        override fun analyze(imageProxy: ImageProxy) {
            val mediaImage = imageProxy.image ?: return imageProxy.close()
            val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
            scanner.process(image)
                .addOnSuccessListener { barcodes -> barcodes.firstOrNull()?.rawValue?.let { onQrCodeScanned(it) } }
                .addOnCompleteListener { imageProxy.close() }
        }
    }
}