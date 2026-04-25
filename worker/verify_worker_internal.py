import os
import uuid
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tasks.insights import run_insights

# Inside worker container
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://insightx_user:insightx_pass@db:5432/insightx_db")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def verify_worker_flow():
    print("=== Testing Local LLM Worker Flow ===")
    db = Session()
    # UUID for job_id
    job_id = str(uuid.uuid4())
    
    try:
        # 1. Create dummy analysis result
        print(f"Creating dummy analysis for ID {job_id}...")
        dummy_result = {
            "summary": "Monthly sales up by 20%",
            "top_products": ["Widget A", "Gadget B"],
            "trends": "Upward trend in Q3"
        }
        import json
        # Corrected columns for AnalysisResultsCache
        db.execute(text("""
            INSERT INTO analysis_results_cache (id, analysis_type, result_json, is_stale, computed_at)
            VALUES (:id, :type, :result, :stale, now())
        """), {
            "id": job_id, 
            "type": "rfm", 
            "result": json.dumps(dummy_result),
            "stale": False
        })
        db.commit()
        
        # 2. Trigger task Synchronously
        print("Triggering run_insights task synchronously...")
        # Since we use SessionLocal in the task, we need to ensure our inserts are visible
        # SQLAlchemy Session in script vs SessionLocal in task
        result = run_insights(job_id) 
        print(f"Task status result: {result}")
        
        # 3. Verify Database
        print("Verifying database for generated insights...")
        res = db.execute(text("SELECT bullet_text FROM insights WHERE job_id = :job_id"), {"job_id": job_id}).fetchall()
        
        if res:
            print(f"✅ PASS | Insights generated: {len(res)} points found.")
            for i, row in enumerate(res):
                print(f"   Insight {i+1}: {row[0]}")
        else:
            print(f"❌ FAIL | No insights found in database for job {job_id}. Check worker logs.")
            
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR: {e}")
    finally:
        # Cleanup
        try:
            db.execute(text("DELETE FROM insights WHERE job_id = :job_id"), {"job_id": job_id})
            db.execute(text("DELETE FROM analysis_results_cache WHERE id = :job_id"), {"job_id": job_id})
            db.commit()
        except:
            db.rollback()
        db.close()

if __name__ == "__main__":
    verify_worker_flow()
