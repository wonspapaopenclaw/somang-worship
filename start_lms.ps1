# LM Studio 서버 실행 스크립트
$lmStudioPath = "C:\Users\chajh\.lmstudio\bin\lms.exe"
$argList = @("--server", "--port", "1234")

Write-Host "LM Studio 서버 시작 시도..."
Start-Process -FilePath $lmStudioPath -ArgumentList $argList -WindowStyle Hidden
Write-Host "서버 시작 완료. 5초 대기..."
Start-Sleep -Seconds 5
Write-Host "작업 완료."
