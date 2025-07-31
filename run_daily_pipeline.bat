@echo off
REM MLB RFI Pipeline Daily Runner Batch File
cd /d "C:\dev\vscode\workspaces\ai-ml-predictive-models"
powershell.exe -ExecutionPolicy Bypass -File "run_daily_pipeline.ps1"
