@echo off
rem Coupon watcher (Windows task QuantFoot\KuponIzle, every 15 min): re-reads every leg of the coupons in force on the
rem live Nesine bulletin; a leg whose market closed / was suspended raises one alert. Log: reports\daily\logs\kupon_izle.log
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
echo [%date% %time%] >> reports\daily\logs\kupon_izle.log
".venv\Scripts\python.exe" scripts\kupon_kontrol.py kontrol >> reports\daily\logs\kupon_izle.log 2>&1
