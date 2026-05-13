# worker/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from services.backup_service import backup_service
from database.connection import get_collection
import asyncio
import logging
from bson import ObjectId
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class BackupScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.db_configs_collection = get_collection("dumpty", "database_configs")
        self.backups_collection = get_collection("dumpty", "backups")
        logger.info("BackupScheduler initialized")
    
    async def execute_backup(self, db_id: str, user_id: str, company_id: str):
        try:
            logger.info(f"Starting backup for DB: {db_id}")
            result = await backup_service.create_backup(user_id, company_id, db_id, "Scheduled backup")
            
            # Fetch notification settings
            from services.settings_service import settings_service
            settings = await settings_service.get_settings(company_id)
            from services.notification_service import notification_service

            if result and result.get("status") != "failed":
                logger.info(f"Backup completed: {result.get('filename')}")
                # Optional: send success notification if enabled
                if settings.get("backup_success"):
                    await notification_service.send_slack_alert(
                        f"*Backup Successful*\n*Database:* {db_id}\n*File:* {result.get('filename')}",
                        level="info"
                    )
            else:
                # Handle logical failure (status='failed')
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Backup failed for {db_id}: {error_msg}")
                
                if settings.get("backup_failed", True): # Default to true for failures
                    await notification_service.send_slack_alert(
                        f"❌ *Backup Failed*\n*Database:* {db_id}\n*Error:* {error_msg}",
                        level="error"
                    )
        except Exception as e:
            logger.error(f"Backup error: {e}")
            try:
                from services.settings_service import settings_service
                settings = await settings_service.get_settings(company_id)
                if settings.get("backup_failed", True):
                    from services.notification_service import notification_service
                    await notification_service.send_slack_alert(
                        f"❌ *Backup Scheduler Error*\n*Database:* {db_id}\n*Error:* {str(e)}",
                        level="error"
                    )
            except:
                pass # Don't let notification failure crash the scheduler
        finally:
            # Update next run time in DB
            job = self.scheduler.get_job(f"backup_{db_id}")
            if job and job.next_run_time:
                await self.db_configs_collection.update_one(
                    {"_id": ObjectId(db_id)},
                    {"$set": {"next_run_at": job.next_run_time}}
                )
    
    async def initialize_schedules(self):
        configs = await self.db_configs_collection.find({}).to_list(1000)
        for cfg in configs:
            await self.add_backup_job(
                str(cfg["_id"]), 
                cfg["user_id"], 
                cfg["company_id"],
                cfg.get("backup_interval", 24),
                cfg.get("backup_interval_unit", "hours"),
                run_immediately=False
            )
        logger.info(f"Initialized {len(configs)} schedules")
    
    async def add_backup_job(self, db_id: str, user_id: str, company_id: str, interval: int, interval_unit: str = "hours", run_immediately: bool = False):
        job_id = f"backup_{db_id}"
        existing = self.scheduler.get_job(job_id)
        
        # Don't re-add identical job
        if existing and not run_immediately:
            try:
                trigger = existing.trigger
                if interval_unit == "hours":
                    current = trigger.interval.total_seconds() / 3600
                else:
                    current = trigger.interval.total_seconds() / 60
                
                if current == interval:
                    return
            except:
                pass
            self.scheduler.remove_job(job_id)
        
        # Smart check: if no successful backups exist, run immediately
        if not run_immediately:
            last_backup = await self.backups_collection.find_one({
                "db_get_id": db_id, # db_id is string here
                "status": "completed"
            })
            if not last_backup:
                # Also check with db_id as string key (since we store it as string in backup doc)
                last_backup = await self.backups_collection.find_one({
                    "db_id": db_id,
                    "status": "completed"
                })
                
            if not last_backup:
                logger.info(f"New or empty DB detected: {db_id}. Triggering initial backup.")
                run_immediately = True

        # First run is NOW if run_immediately, else NOW + interval
        if interval_unit == "hours":
            next_run = datetime.now() if run_immediately else datetime.now() + timedelta(hours=interval)
            trigger = IntervalTrigger(hours=interval)
        else:
            next_run = datetime.now() if run_immediately else datetime.now() + timedelta(minutes=interval)
            trigger = IntervalTrigger(minutes=interval)
        
        self.scheduler.add_job(
            self.execute_backup,
            trigger,
            args=[db_id, user_id, company_id],
            id=job_id,
            replace_existing=True,
            next_run_time=next_run,
            misfire_grace_time=3600
        )
        
        # Update next run time in DB immediately
        await self.db_configs_collection.update_one(
            {"_id": ObjectId(db_id)},
            {"$set": {"next_run_at": next_run}}
        )
        
        logger.info(f"Scheduled {db_id} every {interval} {interval_unit} -> next at {next_run.strftime('%H:%M:%S')}")
    
    def remove_backup_job(self, db_id: str):
        job_id = f"backup_{db_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
    
    def start(self): 
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Backup scheduler started")
    
    def shutdown(self): 
        self.scheduler.shutdown()
    
    async def watch_configs(self):
        logger.info("Starting configuration watcher...")
        try:
            # FIX: Motor requires await here
            change_stream = await self.db_configs_collection.watch(full_document='updateLookup')
            logger.info("Change Streams active")
            
            async for change in change_stream:
                op = change["operationType"]
                doc_id = str(change["documentKey"]["_id"])
                
                if op == "insert":
                    doc = change["fullDocument"]
                    await self.add_backup_job(doc_id, doc["user_id"], doc["company_id"], doc.get("backup_interval", 24), doc.get("backup_interval_unit", "hours"), True)
                elif op in ["update", "replace"]:
                    doc = change["fullDocument"]
                    await self.add_backup_job(doc_id, doc["user_id"], doc["company_id"], doc.get("backup_interval", 24), doc.get("backup_interval_unit", "hours"), False)
                elif op == "delete":
                    self.remove_backup_job(doc_id)
                    
        except Exception as e:
            logger.warning(f"Change Streams not available: {e}")
            logger.warning("Using polling every 5 minutes")
            
            # Wait 10 seconds first, not 5 minutes
            await asyncio.sleep(10)
            while True:
                await self._safe_refresh()
                await asyncio.sleep(300)
    
    async def _safe_refresh(self):
        configs = await self.db_configs_collection.find({}).to_list(1000)
        active_ids = {str(c["_id"]) for c in configs}
        
        for c in configs:
            await self.add_backup_job(str(c["_id"]), c["user_id"], c["company_id"], c.get("backup_interval", 24), c.get("backup_interval_unit", "hours"), False)
        
        # cleanup deleted
        for job in self.scheduler.get_jobs():
            if job.id.startswith("backup_") and job.id[7:] not in active_ids:
                self.scheduler.remove_job(job.id)


backup_scheduler = BackupScheduler()