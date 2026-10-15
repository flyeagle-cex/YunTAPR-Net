@echo off
cd /d "%~dp0..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\phase_b_v2_operator\Monitor-Training.ps1" -Open -IntervalSeconds 60
