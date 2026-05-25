package com.example.hwledger

import android.graphics.Color
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
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
        val crashesText = findViewById<TextView>(R.id.crashesText)
        val cpuGpuText = findViewById<TextView>(R.id.cpuGpuText)

        val abuse = data.optJSONObject("ab")
        val powerFails = abuse?.optInt("Critical_Power_Failures", 0) ?: 0
        val unexpected = abuse?.optInt("Unexpected_Shutdowns", 0) ?: 0
        val totalCrashes = powerFails + unexpected

        val cpu = data.optJSONObject("cpu")
        val cpuName = cpu?.optString("Name", getString(R.string.unknown_cpu)) ?: getString(R.string.unknown_cpu)

        val gpuArray = data.optJSONArray("gpu")
        val gpuName = if (gpuArray != null && gpuArray.length() > 0) {
            gpuArray.getJSONObject(0).optString("Model", getString(R.string.unknown_gpu))
        } else getString(R.string.unknown_gpu)

        val ram = data.optJSONObject("ram_u")?.optString("Total_Installed", getString(R.string.unknown_ram))
        val mobo = data.optJSONObject("mb")?.optString("Product_Model", getString(R.string.unknown_board))

        cpuGpuText.text = getString(R.string.hardware_info_format, cpuName, gpuName, ram, mobo)
        crashesText.text = getString(R.string.crashes_format, totalCrashes)

        var score = 100
        if (totalCrashes > 0) {
            score -= (totalCrashes * 1/2)
        }
        score = score.coerceIn(0, 100)
        trustScoreText.text = score.toString()

        when {
            score >= 80 -> {
                trustScoreText.setTextColor(getColor(R.color.apple_green))
                trustAdviceText.text = getString(R.string.advice_excellent)
            }
            score >= 60 -> {
                trustScoreText.setTextColor(getColor(R.color.apple_orange))
                trustAdviceText.text = getString(R.string.advice_moderate)
            }
            else -> {
                trustScoreText.setTextColor(getColor(R.color.apple_red))
                trustAdviceText.text = getString(R.string.advice_bad)
            }
        }
    }
}