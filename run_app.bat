@echo off
title LinkedIn Job Hunter - Hunter Pro
echo ===================================================
echo   LAUNCHING LINKEDIN JOB HUNTER (HUNTER PRO)
echo ===================================================
echo.
echo Starting Streamlit server on port 8502...
python -m streamlit run app.py --server.port 8502
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Failed to start Streamlit. Please make sure Python and Streamlit are installed.
    pause
)
