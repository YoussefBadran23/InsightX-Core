import os
import uuid
import time
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tasks.insights import run_insights 

# Connection setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@localhost:5432/insightx_db")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def verify_worker_flow():
    print("\n🚀 Starting Full-Loop InsightX Worker Test...")
    db = Session()
    job_id = str(uuid.uuid4())
    
    try:
        # 1. Create Mock Data in Cache
        print(f"📦 Step 1: Seeding cache for Job ID: {job_id}")
        dummy_data = {
            "summary": "Revenue spiked 15% in Cairo region.",
            "top_products": ["HP Z440 Workstation", "RTX 3060"],
            "trends": "Consistent growth in hardware sector."
        }
        
        db.execute(text("""
            INSERT INTO analysis_results_cache (id, analysis_type, result_json, is_stale, computed_at)
            VALUES (:id, 'revenue', :result, false, now())
        """), {"id": job_id, "result": json.dumps(dummy_data)})
        db.commit()
        
        # 2. Trigger task ASYNCHRONOUSLY
        print(f"📨 Step 2: Dispatching task to Redis...")
        task = run_insights.delay(job_id) 
        
        # 3. Wait and Poll
        print(f"⏳ Step 3: Waiting for worker to process (ID: {task.id})...")
        timeout = 20
        start = time.time()
        while task.status not in ['SUCCESS', 'FAILURE']:
            if time.time() - start > timeout:
                print("❌ TIMEOUT: Worker is likely not running or stuck.")
                return
            print(f"   Current Worker Status: {task.status}")
            time.sleep(2)
            
        if task.status == 'SUCCESS':
            print(f"✅ Step 4: Worker finished task successfully!")
        else:
            print(f"❌ Step 4: Worker failed the task. Check Celery logs.")
            return

        # 5. Verify the Result in DB
        res = db.execute(text("SELECT bullet_text FROM insights WHERE job_id = :job_id"), {"job_id": job_id}).fetchall()
        
        if res:
            print(f"\n🎉 TEST PASSED! {len(res)} insights found in DB:")
            for row in res:
                print(f"   • {row[0]}")
        else:
            print(f"❌ FAIL: Task succeeded but no rows were written to the 'insights' table.")
            
    except Exception as e:
        db.rollback()
        print(f"💥 CRITICAL ERROR: {e}")
    finally:
        # Cleanup
        db.execute(text("DELETE FROM insights WHERE job_id = :job_id"), {"job_id": job_id})
        db.execute(text("DELETE FROM analysis_results_cache WHERE id = :job_id"), {"job_id": job_id})
        db.commit()
        db.close()

if __name__ == "__main__":
    verify_worker_flow()