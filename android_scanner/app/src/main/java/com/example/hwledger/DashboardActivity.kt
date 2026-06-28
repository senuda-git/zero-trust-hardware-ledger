package com.example.hwledger

import android.graphics.Color
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.cardview.widget.CardView
import org.json.JSONObject

class DashboardActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_dashboard)

        val payloadString = intent.getStringExtra("PAYLOAD_JSON")
        val adviceText = findViewById<TextView>(R.id.trustAdviceText)

        if (payloadString == null) {
            adviceText.text = getString(R.string.no_data_scanned)
            return
        }

        try {
            val data = JSONObject(payloadString)
            populateDashboard(data)
            
            // Save to history automatically
            ScanHistoryManager.saveScan(this, data, true)
            
        } catch (e: Exception) {
            adviceText.text = getString(R.string.parsing_error, e.message)
            adviceText.setTextColor(Color.RED)
        }

        findViewById<Button>(R.id.btnBackToHome).setOnClickListener {
            finish()
        }
    }

    private fun populateDashboard(data: JSONObject) {
        val trustScoreText = findViewById<TextView>(R.id.trustScoreText)
        val trustAdviceText = findViewById<TextView>(R.id.trustAdviceText)
        val stabilityDetailsText = findViewById<TextView>(R.id.stabilityDetailsText)
        val specsDetailsText = findViewById<TextView>(R.id.specsDetailsText)

        val warningCard = findViewById<CardView>(R.id.warningCard)
        val warningText = findViewById<TextView>(R.id.warningText)

        // 1. Extract Abuse History
        val abuse = data.optJSONObject("ab")
        val powerFails = abuse?.optInt("Critical_Power_Failures", 0) ?: 0
        val unexpected = abuse?.optInt("Unexpected_Shutdowns", 0) ?: 0
        val badBlocks = abuse?.optInt("Disk_Bad_Blocks_Logged", 0) ?: 0
        val thermal = abuse?.optInt("Historical_Thermal_Throttling", 0) ?: 0
        val fatalWhea = abuse?.optInt("Fatal_Hardware_Errors", 0) ?: 0
        val totalCrashes = powerFails + unexpected

        // 2. Extract Core Specs
        val cpu = data.optJSONObject("cpu")
        val cpuName = cpu?.optString("Name", "Unknown CPU") ?: "Unknown CPU"
        val isVmSpoofed = cpu?.optString("VM_Spoof_Detected", "")?.contains("CRITICAL") == true

        val gpuArray = data.optJSONArray("gpu")
        val gpuName = if (gpuArray != null && gpuArray.length() > 0) {
            gpuArray.getJSONObject(0).optString("Model", "Unknown GPU")
        } else "Unknown GPU"

        val ram = data.optJSONObject("ram_u")?.optString("Total_Installed", "Unknown RAM")
        val mobo = data.optJSONObject("mb")?.optString("Product_Model", "Unknown Board")

        // 3. The Ultimate Trust Algorithm
        var score = 100.0
        var criticalFlag = false
        var criticalMessage = ""

        if (thermal > 0) { score = 0.0; criticalFlag = true; criticalMessage = "Cooling System Failed (Thermal Throttling)" }
        if (fatalWhea > 0) { score = 0.0; criticalFlag = true; criticalMessage = "Fatal Silicon Architecture Errors (WHEA)" }
        if (isVmSpoofed) { score = 0.0; criticalFlag = true; criticalMessage = "VM SPOOFING DETECTED. Fake Hardware." }

        score -= (badBlocks * 1.50) // 15 point penalty per dying disk block
        score -= (totalCrashes * 0.25) // 1/4 point penalty per power loss

        val finalScore = score.toInt().coerceIn(0, 100)
        trustScoreText.text = finalScore.toString()

        // 4. UI Formatting
        specsDetailsText.text = "CPU: $cpuName\nGPU: $gpuName\nRAM: $ram\nBoard: $mobo"

        val stabilityStr = StringBuilder()
        stabilityStr.append("Total Crashes/Power Losses: $totalCrashes\n")
        stabilityStr.append("Bad Disk Blocks: $badBlocks\n")
        stabilityStr.append("Thermal Throttling Events: $thermal")
        stabilityDetailsText.text = stabilityStr.toString()

        // Warnings Banner Logic
        if (criticalFlag || badBlocks > 0) {
            warningCard.visibility = View.VISIBLE
            warningText.text = "CRITICAL HARDWARE WARNING:\n${if (criticalFlag) criticalMessage else "$badBlocks Bad Disk Blocks detected."}"
        } else {
            warningCard.visibility = View.GONE
        }

        when {
            finalScore >= 80 -> {
                trustScoreText.setTextColor(Color.parseColor("#34C759")) // Apple Green
                trustAdviceText.text = "Excellent Condition. Safe to purchase."
            }
            finalScore >= 50 -> {
                trustScoreText.setTextColor(Color.parseColor("#FF9F0A")) // Apple Orange
                trustAdviceText.text = "Moderate Wear. Inspect system carefully."
            }
            else -> {
                trustScoreText.setTextColor(Color.parseColor("#FF3B30")) // Apple Red
                trustAdviceText.text = "CRITICAL DANGER. Do not buy."
            }
        }
    }
}