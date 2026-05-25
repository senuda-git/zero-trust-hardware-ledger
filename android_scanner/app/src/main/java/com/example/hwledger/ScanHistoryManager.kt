package com.example.hwledger

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

object ScanHistoryManager {
    private const val PREFS_NAME = "scan_history"
    private const val KEY_HISTORY = "history"

    fun saveScan(context: Context, payload: JSONObject, isAuthentic: Boolean) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val historyString = prefs.getString(KEY_HISTORY, "[]")
        val historyArray = JSONArray(historyString)

        val newEntry = JSONObject()
        newEntry.put("timestamp", System.currentTimeMillis())
        newEntry.put("payload", payload)
        newEntry.put("isAuthentic", isAuthentic)

        // Keep only last 20 scans
        val newList = JSONArray()
        newList.put(newEntry)
        for (i in 0 until minOf(historyArray.length(), 19)) {
            newList.put(historyArray.get(i))
        }

        prefs.edit().putString(KEY_HISTORY, newList.toString()).apply()
    }

    fun getHistory(context: Context): List<ScanEntry> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val historyString = prefs.getString(KEY_HISTORY, "[]")
        val historyArray = JSONArray(historyString)
        
        val entries = mutableListOf<ScanEntry>()
        for (i in 0 until historyArray.length()) {
            val obj = historyArray.getJSONObject(i)
            entries.add(ScanEntry(
                obj.getLong("timestamp"),
                obj.getJSONObject("payload"),
                obj.getBoolean("isAuthentic")
            ))
        }
        return entries
    }

    data class ScanEntry(val timestamp: Long, val payload: JSONObject, val isAuthentic: Boolean)
}