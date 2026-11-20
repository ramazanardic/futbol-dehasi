@echo off
rem Coupon watcher (Windows task QuantFoot\KuponIzle, every 15 min): re-reads every leg of the coupons in force on the
rem live Nesine bulletin; a leg whose market closed / was suspended raises one alert. Log: reports\daily\logs\kupon_izle.log
rem It also archives yesterday's API-Football results once a day (team history for leagues ESPN lacks; user, 20 Nov).
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
echo [%date% %time%] >> reports\daily\logs\kupon_izle.log
".venv\Scripts\python.exe" scripts\kupon_kontrol.py kontrol >> reports\daily\logs\kupon_izle.log 2>&1
".venv\Scripts\python.exe" scripts\api_gecmis.py --arsiv >> reports\daily\logs\kupon_izle.log 2>&1
