Write-Host "=================================================="
Write-Host "🚀 INITIATING STRICT VERIFICATION OF PHASE 1"
Write-Host "=================================================="

# ---------------------------------------------------------
Write-Host "`n=== Testing Step 1: Monorepo & Git ==="
# ---------------------------------------------------------
Write-Host "Checking directory structure:"
$dirs = Get-ChildItem -Directory | Select-Object -ExpandProperty Name
$required = @("frontend", "backend", "worker", "infrastructure")
$missing = $false
foreach ($req in $required) {
    if ($dirs -notcontains $req) {
        $missing = $true
    }
}
if (-not $missing) { Write-Host "✅ Monorepo folders exist." } else { Write-Host "❌ Monorepo folders missing." }

Write-Host "Checking Git Remote:"
$remote = git remote -v | Select-String "YoussefBadran23/InsightX-Core.git"
if ($remote) { Write-Host "✅ GitHub remote is correctly configured." } else { Write-Host "❌ GitHub remote missing or incorrect." }

# ---------------------------------------------------------
Write-Host "`n=== Testing Step 2: Docker Containers ==="
# ---------------------------------------------------------
Write-Host "Checking running containers:"
docker ps --format "{{.Names}} - {{.Ports}}" | Select-String "insightx"

$response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -ErrorAction SilentlyContinue
if ($response.StatusCode -eq 200) { Write-Host "✅ FastAPI Backend is LIVE on port 8000 (HTTP 200)" } else { Write-Host "❌ FastAPI Backend is DOWN." }
Write-Host "⚠️ Note: Worker and Frontend containers are defined in docker-compose.yml but only built/started in Phases 3 and 4."

# ---------------------------------------------------------
Write-Host "`n=== Testing Step 3: AWS Cloud Infrastructure ==="
# ---------------------------------------------------------
Write-Host "Running Python AWS Verification Script via Docker..."
docker exec insightx_backend python verify_aws.py | Select-String -Pattern "✅|❌"

# ---------------------------------------------------------
Write-Host "`n=== Testing Step 4: GitHub Actions CI/CD ==="
# ---------------------------------------------------------
if (Test-Path ".github\workflows\deploy.yml") { Write-Host "✅ deploy.yml exists in the codebase." } else { Write-Host "❌ deploy.yml missing." }

Write-Host "Querying GitHub API for latest Actions run status..."
try {
    $apiResponse = Invoke-RestMethod -Uri "https://api.github.com/repos/YoussefBadran23/InsightX-Core/actions/runs?per_page=1"
    $status = $apiResponse.workflow_runs[0].conclusion
    if ($status -eq "success") {
        Write-Host "✅ GitHub Actions Pipeline ran successfully on GitHub servers."
    } elseif ([string]::IsNullOrEmpty($status)) {
        Write-Host "⏳ GitHub Actions Pipeline is currently running or queued."
    } else {
        Write-Host "❌ GitHub Actions Pipeline failed or status unknown ($status)."
    }
} catch {
    Write-Host "❌ Failed to query GitHub API."
}

Write-Host "=================================================="
Write-Host "🏁 VERIFICATION COMPLETE"
Write-Host "=================================================="
