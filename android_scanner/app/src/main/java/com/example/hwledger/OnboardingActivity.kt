package com.example.hwledger

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import androidx.appcompat.app.AppCompatActivity

class OnboardingActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val sharedPref = getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        if (sharedPref.getBoolean("onboarding_complete", false)) {
            startHome()
            return
        }

        setContentView(R.layout.activity_onboarding)

        findViewById<Button>(R.id.btnGetStarted).setOnClickListener {
            sharedPref.edit().putBoolean("onboarding_complete", true).apply()
            startHome()
        }
    }

    private fun startHome() {
        startActivity(Intent(this, HomeActivity::class.java))
        finish()
    }
}