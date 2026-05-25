package com.example.hwledger

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import java.text.SimpleDateFormat
import java.util.*

class HistoryActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_history)

        findViewById<ImageButton>(R.id.btnBack).setOnClickListener { finish() }

        val recyclerView = findViewById<RecyclerView>(R.id.historyRecycler)
        val emptyState = findViewById<TextView>(R.id.emptyState)

        val history = ScanHistoryManager.getHistory(this)

        if (history.isEmpty()) {
            emptyState.visibility = View.VISIBLE
            recyclerView.visibility = View.GONE
        } else {
            emptyState.visibility = View.GONE
            recyclerView.visibility = View.VISIBLE
            recyclerView.layoutManager = LinearLayoutManager(this)
            recyclerView.adapter = HistoryAdapter(history)
        }
    }

    private inner class HistoryAdapter(private val items: List<ScanHistoryManager.ScanEntry>) :
        RecyclerView.Adapter<HistoryAdapter.ViewHolder>() {

        inner class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
            val deviceName: TextView = view.findViewById(R.id.deviceName)
            val timestamp: TextView = view.findViewById(R.id.timestamp)
            val indicator: View = view.findViewById(R.id.statusIndicator)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
            val view = LayoutInflater.from(parent.context).inflate(R.layout.item_history, parent, false)
            return ViewHolder(view)
        }

        override fun onBindViewHolder(holder: ViewHolder, position: Int) {
            val item = items[position]
            val cpu = item.payload.optJSONObject("cpu")
            holder.deviceName.text = cpu?.optString("Name", "Unknown Device") ?: "Unknown Device"
            
            val sdf = SimpleDateFormat("MMM dd, yyyy HH:mm", Locale.getDefault())
            holder.timestamp.text = sdf.format(Date(item.timestamp))
            
            holder.indicator.setBackgroundResource(
                if (item.isAuthentic) R.drawable.circle_green else R.drawable.circle_red
            )
        }

        override fun getItemCount() = items.size
    }
}