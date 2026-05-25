package com.example.hwledger

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.cardview.widget.CardView

class HomeActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_home)

        findViewById<CardView>(R.id.scanCard).setOnClickListener {
            startActivity(Intent(this, MainActivity::class.java))
        }

        findViewById<CardView>(R.id.btnViewHistory).setOnClickListener {
            startActivity(Intent(this, HistoryActivity::class.java))
        }
    }
}