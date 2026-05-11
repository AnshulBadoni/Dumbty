# worker/run_worker.py
import sys
import os
from pathlib import Path

# Add project root to sys.path
root_path = str(Path(__file__).resolve().parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import logging

# Configure logging immediately
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('worker.log')  # Optional: log to file
    ]
)
logger = logging.getLogger(__name__)

import asyncio
from scheduler import backup_scheduler
from dotenv import load_dotenv
import signal

load_dotenv()

# Global flag for graceful shutdown
shutdown_event = asyncio.Event()

async def main(): 
    logger.info("Initializing schedules...")
    await backup_scheduler.initialize_schedules()
    
    backup_scheduler.start()
    
    # Start real-time watcher in background
    watch_task = asyncio.create_task(backup_scheduler.watch_configs())
    
    logger.info("\n" + "="*50)
    logger.info("Worker is running. Press Ctrl+C to stop.")
    logger.info("="*50 + "\n")
    
    try:
        # Wait for shutdown signal
        await shutdown_event.wait()
    except asyncio.CancelledError:
        logger.info("Main task cancelled")
    finally:
        # Graceful shutdown
        logger.info("\nShutting down worker...")
        
        # Cancel the watch task
        watch_task.cancel()
        try:
            await watch_task
        except asyncio.CancelledError:
            pass
        
        # Shutdown scheduler
        backup_scheduler.shutdown()
        
        logger.info("Worker stopped successfully")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"\nReceived signal {signum}. Shutting down...")
    shutdown_event.set()

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nWorker interrupted by user")
    except Exception as e:
        logger.error(f"Worker crashed: {str(e)}", exc_info=True)
        sys.exit(1)