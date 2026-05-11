# 🐘 Dumpty - User Guide

Welcome to **Dumpty**, your centralized dashboard for managing automated database backups. This guide will help you set up your first backup and manage your data efficiently.

---

## 🚀 1. Connecting Your First Database

To start backing up your data, follow these steps:

1.  **Click "Add Database"**: Find this button on the main Dashboard or the Databases page.
2.  **Choose Database Type**: Select from MongoDB, PostgreSQL, MySQL, or MariaDB.
3.  **Enter Credentials**: 
    *   **Host & Port**: The address of your database server.
    *   **Database Name**: The specific database you want to back up.
    *   **Credentials**: Username and password (don't worry, we use these only for the backup process).
4.  **Set Backup Interval**: Choose how often you want the backup to run (e.g., every 24 hours, or every 60 minutes for high-traffic apps).
5.  **Save Connection**: Once saved, Dumpty will automatically trigger its first "Snapshot" to ensure everything is working.

---

## 📅 2. Understanding Backups

### Automatic Backups (Schedules)
Once a database is connected, Dumpty works in the background. It will create a new snapshot precisely at the interval you chose.

### Manual Backups (Instant)
Need a backup right now? 
- Go to the **Snapshots** tab of your database.
- Click **"Take Backup Now"**.
- This will trigger an immediate snapshot without affecting your regular schedule.

---

## ♻️ 3. The 7-Snapshot Rule (Retention)

To keep your storage clean and costs low, Dumpty follows a **smart retention policy**:
*   **We keep the latest 7 successful snapshots** for each database.
*   When an 8th backup is created, the **oldest one is automatically removed**.
*   This ensures you always have a full week of history (if set to daily) while preventing unnecessary storage growth.

---

## 📥 4. Managing Your Data

### Downloading Backups
Every successful snapshot can be downloaded directly to your computer.
1.  Go to the **Snapshots** list.
2.  Click the **Download** icon next to the snapshot you need.
3.  The file will be delivered as a compressed archive (`.sql` or `.gz`).

### Monitoring Health
On the main dashboard, you'll see a **Reliability Graph** for each database. This shows a history of your recent backups. 
*   **Green**: Successful backup.
*   **Red**: Failed backup (usually due to a server connection issue).

---

## 🔔 5. Notifications

Stay updated without checking the dashboard:
1.  Go to **Settings**.
2.  **Backup Failure (Recommended)**: Get a Slack notification if a backup fails so you can take action.
3.  **Backup Success**: Optional notification for every successful backup (disabled by default).

---

## 🆘 Need Help?

If you encounter issues connecting your database or downloading a snapshot, please reach out to your system administrator or contact our support team via the **Feedback** link in the dashboard.
