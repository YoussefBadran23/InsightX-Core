import os
import sys
from dotenv import load_dotenv

# override=True ensures it overwrites the dummy variables that docker-compose injected
load_dotenv("/app/.env", override=True)

def test_database():
    try:
        from sqlalchemy import create_engine
        db_url = os.getenv("DATABASE_URL")
        print(f"Testing DB URL: {db_url.split('@')[-1]}")
        
        # Test connection
        engine = create_engine(db_url, connect_args={'connect_timeout': 5})
        connection = engine.connect()
        connection.close()
        print(f"✅ Successfully connected to AWS RDS PostgreSQL at {db_url.split('@')[-1].split('/')[0]}")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to DB: {e}")
        return False

def test_s3():
    try:
        import boto3
        s3 = boto3.client('s3', 
                         region_name=os.getenv("AWS_REGION", "us-east-1"),
                         aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                         aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"))
        bucket_name = os.getenv("S3_BUCKET_NAME")
        
        # We use get_bucket_location or list_objects which requires specific creds
        s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        print(f"✅ Successfully authenticated with AWS S3 and accessed bucket: {bucket_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to access AWS S3: {e}")
        return False

if __name__ == "__main__":
    print("-" * 50)
    print("🔍 VERIFYING AWS INFRASTRUCTURE (PHASE 1, STEP 3)")
    print("-" * 50)
    
    db_ok = test_database()
    s3_ok = test_s3()
    
    if db_ok and s3_ok:
        print("\n🎉 ALL AWS CONNECTIONS SUCCESSFUL! Phase 1 is flawlessly verified.")
        sys.exit(0)
    else:
        print("\n⚠️ SOME CONNECTIONS FAILED.")
        sys.exit(1)
