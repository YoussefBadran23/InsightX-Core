#!/bin/bash
# test_phase_1.sh

echo "=================================================="
echo "🚀 INITIATING STRICT VERIFICATION OF PHASE 1"
echo "=================================================="

# ---------------------------------------------------------
echo -e "\n=== Testing Step 1: Monorepo & Git ==="
# ---------------------------------------------------------
echo "Checking directory structure:"
ls -la | awk '{print $9}' | grep -E '^frontend$|^backend$|^worker$|^infrastructure$'
if [ $? -eq 0 ]; then
  echo "✅ Monorepo folders exist."
else
  echo "❌ Monorepo folders missing."
fi

echo "Checking Git Remote:"
git remote -v | grep "YoussefBadran23/InsightX-Core.git" > /dev/null
if [ $? -eq 0 ]; then
  echo "✅ GitHub remote is correctly configured."
else
  echo "❌ GitHub remote missing or incorrect."
fi


# ---------------------------------------------------------
echo -e "\n=== Testing Step 2: Docker Containers ==="
# ---------------------------------------------------------
echo "Checking running containers:"
docker ps --format "{{.Names}} - {{.Ports}}" | grep insightx

# Check API health
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$HTTP_STATUS" == "200" ]; then
  echo "✅ FastAPI Backend is LIVE on port 8000 (HTTP 200)"
else
  echo "❌ FastAPI Backend is DOWN or unreachable."
fi

echo "⚠️ Note: Worker and Frontend containers are defined in docker-compose.yml but only built/started when their specific code is written in Phases 3 and 4."


# ---------------------------------------------------------
echo -e "\n=== Testing Step 3: AWS Cloud Infrastructure ==="
# ---------------------------------------------------------
echo "Running Python AWS Verification Script via Docker..."
docker exec insightx_backend python verify_aws.py | grep -E '✅|❌'


# ---------------------------------------------------------
echo -e "\n=== Testing Step 4: GitHub Actions CI/CD ==="
# ---------------------------------------------------------
if [ -f ".github/workflows/deploy.yml" ]; then
  echo "✅ deploy.yml exists in the codebase."
else
  echo "❌ deploy.yml missing."
fi

# Fetch the last workflow run status from GitHub API
echo "Querying GitHub API for latest Actions run status..."
WF_STATUS=$(curl -s "https://api.github.com/repos/YoussefBadran23/InsightX-Core/actions/runs?per_page=1" | grep '"conclusion":' | head -n 1 | awk -F'"' '{print $4}')

if [ "$WF_STATUS" == "success" ]; then
  echo "✅ GitHub Actions Pipeline ran successfully on GitHub servers."
elif [ "$WF_STATUS" == "null" ] || [ -z "$WF_STATUS" ]; then
  echo "⏳ GitHub Actions Pipeline is currently running or queued."
else
  echo "❌ GitHub Actions Pipeline failed or status unknown ($WF_STATUS)."
fi

echo "=================================================="
echo "🏁 VERIFICATION COMPLETE"
echo "=================================================="
