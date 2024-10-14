@echo off
chcp 65001
setlocal EnableDelayedExpansion

:: Set number of threads for Whisper (if applicable)
set OMP_NUM_THREADS=8

:: Check for required tools
call :check_command "yt-dlp" "yt-dlp is required but not found. Please install it and ensure it's in your PATH."
call :check_command "whisper" "Whisper is required but not found. Please install it and ensure it's in your PATH."
call :check_command "curl" "curl is required but not found. Please install it and ensure it's in your PATH."
call :check_command "powershell" "PowerShell is required but not found. Please ensure it's available."

:: 1. Ask for YouTube URL
set /p yt_url="Enter YouTube URL: "
if "%yt_url%"=="" (
    echo Error: YouTube URL cannot be empty.
    goto :eof
)

:: 2. Sanitize the YouTube title for use as a filename
for /f "delims=" %%i in ('yt-dlp --get-filename -o "%%(title)s" "%yt_url%" 2^>^&1') do set "raw_title=%%i"
if "%raw_title%"=="" (
    echo Error: Failed to retrieve video title. Please check the YouTube URL.
    goto :eof
)

:: Use PowerShell to sanitize the title, keeping some useful characters
for /f "usebackq delims=" %%i in (`powershell -Command "$sanitized = '%raw_title%'.Trim() -replace '[^a-zA-Z0-9\(\)_-]', '_'; $sanitized -replace '__+', '_'; $sanitized -replace '^_|_$', ''; Write-Output $sanitized"`) do set "sanitized_title=%%i"

:: Output the sanitized title
echo RAW title: !raw_title!
echo Sanitized title: !sanitized_title!
echo.

:: Create 'videos' directory if it doesn't exist
if not exist "videos" (
    mkdir "videos"
)

:: 3. Download video and extract MP3 using yt-dlp, using sanitized title
echo Downloading and extracting audio...
yt-dlp -x --audio-format mp3 "%yt_url%" -o "videos/!sanitized_title!.mp3"
if errorlevel 1 (
    echo Error: Failed to download or extract audio.
    goto :eof
)

:: 4. Set video file name with extension
set "video_file=!sanitized_title!.mp3"

:: Log the video file name for debugging
echo Extracted and sanitized video file name: "!video_file!"

:: 5. Create the folder if it doesn't already exist
set "video_folder=videos\!sanitized_title!"
echo Creating folder: "!video_folder!"
if not exist "!video_folder!" (
    mkdir "!video_folder!"
)

:: 6. Move the downloaded MP3 into the folder
if exist "videos\!video_file!" (
    move "videos\!video_file!" "!video_folder!\"
    if errorlevel 1 (
        echo Error: Failed to move the file. Please check permissions.
        goto :eof
    ) else (
        echo File moved successfully.
    )
) else (
    echo Error: The file "videos\!video_file!" does not exist.
    goto :eof
)

:: 7. Ask for configuration selection
echo.
echo Select Configuration:
set count=1
set "config_base_dir=%~dp0configurations"  :: Assuming configurations are relative to script location

if not exist "%config_base_dir%" (
    echo Error: Configuration directory "%config_base_dir%" does not exist.
    goto :eof
)

:: Loop through configuration directories
for /D %%f in ("%config_base_dir%\*") do (
    echo !count!. %%~nxf
    set "config_!count!=%%f"
    set /A count+=1
)

set /A max_choice=count-1
set /p config_choice="Enter configuration number (1 to %max_choice%): "
if "%config_choice%"=="" (
    echo Error: Configuration choice cannot be empty.
    goto :eof
)

:: Validate config_choice is a number within range
for /f "tokens=* delims=0123456789" %%a in ("%config_choice%") do set not_number=%%a
if defined not_number (
    echo Error: Invalid input. Please enter a number.
    goto :eof
)

if %config_choice% LSS 1 (
    echo Error: Choice must be between 1 and %max_choice%.
    goto :eof
)

if %config_choice% GTR %max_choice% (
    echo Error: Choice must be between 1 and %max_choice%.
    goto :eof
)

set "config_folder=!config_%config_choice%!"

:: Check if the configuration folder exists
if not exist "!config_folder!\llm_config.txt" (
    echo Error: llm_config.txt not found in "!config_folder!".
    goto :eof
)

:: Read variables from llm_config.txt securely
call :read_config "!config_folder!\llm_config.txt"

:: After reading config, verify variables are set
if "%model%"=="" (
    echo Error: 'model' variable is not set. Please check your llm_config.txt.
    goto :eof
)
if "%max_tokens%"=="" (
    echo Error: 'max_tokens' variable is not set. Please check your llm_config.txt.
    goto :eof
)
if "%openai_api_key%"=="" (
    echo Error: 'openai_api_key' variable is not set. Please check your llm_config.txt.
    goto :eof
)

echo Running prompts with LLM API...

:: Define the transcribed files
set "transcribed_file=!video_folder!\!sanitized_title!.txt"
set "transcribed_srt_file=!video_folder!\!sanitized_title!.srt"

:: Run Whisper on the downloaded MP3 file
echo Transcribing audio with Whisper...
whisper "!video_folder!\!sanitized_title!.mp3" --output_format all --output_dir "!video_folder!"
if errorlevel 1 (
    echo Error: Whisper transcription failed.
    goto :eof
)

:: Check if Whisper output files exist
if not exist "!transcribed_file!" (
    echo Error: Whisper output file "!transcribed_file!" not found.
    goto :eof
)

if not exist "!transcribed_srt_file!" (
    echo Error: Whisper output file "!transcribed_srt_file!" not found.
    goto :eof
)

:: Processing prompts
echo.
echo Processing prompts...
set "prompts_folder=!config_folder!\prompts"

:: Check if prompts folder exists
if not exist "!prompts_folder!" (
    echo Error: Prompts folder "!prompts_folder!" not found.
    goto :eof
)

:: Check if any prompt files exist
dir "!prompts_folder!\*.txt" "!prompts_folder!\*.srt" >nul 2>&1
if errorlevel 1 (
    echo Error: No prompt files found in "!prompts_folder!".
    goto :eof
)
for %%p in ("!prompts_folder!\*.txt") do (
    call :process_prompt "%%~dpnxp"
)
for %%p in ("!prompts_folder!\*.srt") do (
    call :process_prompt "%%~dpnxp"
)
goto :after_prompts

:: Function to check if a command exists
:check_command
where %~1 >nul 2>&1
if errorlevel 1 (
    echo Error: %~2
    goto :eof
)
goto :eof

:: Function to read configuration variables securely
:read_config
for /f "usebackq tokens=1,* delims==" %%A in ("%~1") do (
    if not "%%B"=="" (
        set "%%A=%%B"
    )
)
goto :eof

:process_prompt
set "prompt_file=%~1"
set "prompt_name=%~n1"
echo Processing prompt: "!prompt_name!"

:: Read prompt content
set "prompt_content="
for /f "usebackq delims=" %%l in ("%prompt_file%") do (
    set "prompt_content=!prompt_content! %%l"
)
:: Trim leading space
set "prompt_content=!prompt_content:~1!"

:: Use appropriate transcribed content
if /I "%~x1"==".srt" (
    set "user_text_file=!transcribed_srt_file!"
) else (
    set "user_text_file=!transcribed_file!"
)

:: Build JSON payload
echo Building JSON payload...
set "json_payload_file=!video_folder!\payload_!prompt_name!.json"

(
    echo {
    echo    "model": "%model%",
    echo    "messages": [
    echo        {
    echo            "role": "system",
    echo            "content": "!prompt_content!"
    echo        },
    echo        {
    echo            "role": "user",
    echo            "content": "__USER_TEXT_FILE_CONTENT__"
    echo        }
    echo    ],
    echo    "max_tokens": %max_tokens%
    echo }
) > "!json_payload_file!"

:: Create temporary PowerShell script
set "ps_script=!video_folder!\replace_placeholder_%prompt_name%.ps1"

(
    echo $json = Get-Content '!json_payload_file!' -Raw
    echo $user_text = Get-Content '!user_text_file!' -Raw
    echo $user_text_escaped = $user_text -replace '\\', '\\\\' -replace '\"', '\\\"' -replace '\r?\n', '\\n'
    echo $json = $json -replace '__USER_TEXT_FILE_CONTENT__', $user_text_escaped
    echo Set-Content '!json_payload_file!' -Value $json
) > "!ps_script!"

:: Execute the PowerShell script
powershell -ExecutionPolicy Bypass -File "!ps_script!"

if errorlevel 1 (
    echo Error: Failed to prepare JSON payload.
    goto :eof
)

:: Delete the temporary PowerShell script
del "!ps_script!"

:: Run CURL command to send prompt to LLM API and save response
echo Sending request to OpenAI API...
curl -X POST "https://api.openai.com/v1/chat/completions" ^
    -H "Content-Type: application/json" ^
    -H "Authorization: Bearer %openai_api_key%" ^
    -d "@!json_payload_file!" > "!video_folder!\full_response_!prompt_name!.json"

if errorlevel 1 (
    echo Error: Failed to get response from OpenAI API.
    goto :eof
)

:: Extract the response content
echo Extracting response...
powershell -Command ^
    "$utf8NoBom = New-Object System.Text.UTF8Encoding($False); $json = Get-Content '!video_folder!\full_response_!prompt_name!.json' -Encoding UTF8 | ConvertFrom-Json; $content = $json.choices[0].message.content; [IO.File]::WriteAllText('!video_folder!\!prompt_name!.txt', $content, $utf8NoBom);"

if errorlevel 1 (
    echo Error: Failed to extract content from the API response.
    goto :eof
)

:: Cleanup
del "!json_payload_file!"
goto :eof

:after_prompts
echo.
echo Process complete!
