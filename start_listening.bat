set default_ip=192.168.8.10
@if "%1" NEQ "" (
    set custom_ip=%1
) else (
    @echo Custom IP not specified in command line. Default: %default_ip%
    set custom_ip=%default_ip%
)
uvicorn pyholder:app --port 9018 --host %custom_ip% --reload --log-level debug 
