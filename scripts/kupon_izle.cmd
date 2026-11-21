@echo off
rem Coupon watcher (Windows task QuantFoot\KuponIzle, every 15 min): re-reads every leg of the coupons in force on the
rem live Nesine bulletin; a leg whose market closed / was suspended raises one alert. Log: reports\daily\logs\kupon_izle.log
rem It also archives yesterday's API-Football results once a day (team history for leagues ESPN lacks; user, 20 Nov).
rem QUANTFOOT_AI must be set in the scheduled task (e.g. claudetahmin for the Windows owner). There is no default.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
if "%QUANTFOOT_AI%"=="" (
  echo QUANTFOOT_AI tanimli degil. Gorev ortaminda QUANTFOOT_AI=claudetahmin (veya kendi klasorunuz) ayarlayin.
  exit /b 1
)
echo [%date% %time%] QUANTFOOT_AI=%QUANTFOOT_AI% >> reports\daily\logs\kupon_izle.log
".venv\Scripts\python.exe" scripts\kupon_kontrol.py kontrol >> reports\daily\logs\kupon_izle.log 2>&1
".venv\Scripts\python.exe" scripts\api_gecmis.py --arsiv >> reports\daily\logs\kupon_izle.log 2>&1
