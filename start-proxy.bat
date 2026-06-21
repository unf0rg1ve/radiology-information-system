@echo off
start /B python "%~dp0orthanc-proxy.py" > "%~dp0orthanc-proxy.log" 2>&1
echo Orthanc proxy started on port 8043
