# MLB RFI Pipeline Daily Runner
# Run at 6:00 AM PST daily

param(
    [string]$Date = (Get-Date).ToString("yyyy-MM-dd")
)

# Set working directory
Set-Location "C:\dev\vscode\workspaces\ai-ml-predictive-models"

# Activate virtual environment
& ".\.venv\Scripts\Activate.ps1"

# Log start
$logFile = "logs\daily_pipeline_$(Get-Date -Format 'yyyyMMdd').log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logFile -Value "[$timestamp] Starting MLB RFI pipeline for $Date"

try {
    # Run the pipeline
    python -m src.pipelines.run_mlb_rfi_pipeline $Date
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "[$timestamp] Pipeline completed successfully"
    exit 0
}
catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "[$timestamp] Pipeline failed: $($_.Exception.Message)"
    exit 1
}
