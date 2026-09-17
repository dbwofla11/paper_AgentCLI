[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$SkipSmokeTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Result {
    param(
        [ValidateSet('OK', 'WARN', 'FAIL', 'INFO')]
        [string]$Level,
        [string]$Message
    )

    $color = switch ($Level) {
        'OK'   { 'Green' }
        'WARN' { 'Yellow' }
        'FAIL' { 'Red' }
        default { 'Cyan' }
    }
    Write-Host ("[{0}] {1}" -f $Level, $Message) -ForegroundColor $color
}

function Get-PythonRuntime {
    $candidates = @(
        @{ Command = 'py'; Prefix = @('-3'); Label = 'Python launcher (py -3)' },
        @{ Command = 'python'; Prefix = @(); Label = 'python' }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) {
            continue
        }

        $versionScript = "import sys; print('{0}.{1}.{2}'.format(*sys.version_info[:3]))"
        $arguments = @($candidate.Prefix) + @('-c', $versionScript)
        try {
            $versionText = (& $candidate.Command @arguments 2>$null | Select-Object -First 1).Trim()
        } catch {
            continue
        }
        if (-not $versionText) {
            continue
        }

        try {
            return [pscustomobject]@{
                Command = $candidate.Command
                Prefix = @($candidate.Prefix)
                Label = $candidate.Label
                Version = [Version]$versionText
            }
        } catch {
            continue
        }
    }

    return $null
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$failures = New-Object System.Collections.Generic.List[string]

Push-Location $repositoryRoot
try {
    Write-Host ''
    Write-Host 'Paper Review & Research Harness setup' -ForegroundColor Cyan
    Write-Host ("Root: {0}" -f $repositoryRoot)
    if ($CheckOnly) {
        Write-Result INFO 'Check-only mode: no directories will be created.'
    }

    $requiredFiles = @(
        'AGENTS.md',
        'Home.md',
        '.codex/config.toml',
        '.mcp.json',
        '.scripts/bin/paper.py',
        '90-Templates/paper/review-template.md',
        '90-Templates/paper/triage-template.md'
    )
    foreach ($relativePath in $requiredFiles) {
        if (Test-Path (Join-Path $repositoryRoot $relativePath) -PathType Leaf) {
            Write-Result OK $relativePath
        } else {
            Write-Result FAIL ("Missing required file: {0}" -f $relativePath)
            $failures.Add($relativePath)
        }
    }

    $workspaceDirectories = @(
        '00-Inbox',
        '01-Papers/pdfs/wifi-csi',
        '01-Papers/pdfs/game-ai',
        '01-Papers/pdfs/agent-ai',
        '01-Papers/pdfs/computer-vision',
        '01-Papers/pdfs/other',
        '01-Papers/reviews/wifi-csi',
        '01-Papers/reviews/game-ai',
        '01-Papers/reviews/agent-ai',
        '01-Papers/reviews/computer-vision',
        '01-Papers/reviews/other',
        '01-Papers/triage',
        '01-Papers/library',
        '02-Concepts',
        '03-Trends/daily',
        '04-Projects',
        '05-ideas/thought-experiments',
        '99-Attachments'
    )
    foreach ($relativePath in $workspaceDirectories) {
        $directory = Join-Path $repositoryRoot $relativePath
        if (Test-Path $directory -PathType Container) {
            continue
        }
        if ($CheckOnly) {
            Write-Result WARN ("Missing directory (would create): {0}" -f $relativePath)
            $failures.Add("directory:$relativePath")
        } else {
            New-Item -ItemType Directory -Path $directory -Force | Out-Null
            Write-Result OK ("Created directory: {0}" -f $relativePath)
        }
    }

    if (Get-Command git -ErrorAction SilentlyContinue) {
        $gitStatus = & git -C $repositoryRoot status --porcelain 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Result OK 'Git can access this repository.'
        } else {
            Write-Result WARN 'Git could not access this repository. If it reports "dubious ownership", verify the owner and add this path as a safe.directory.'
            $failures.Add('git-repository-access')
        }
    } else {
        Write-Result FAIL 'Git was not found on PATH.'
        $failures.Add('git')
    }

    $python = Get-PythonRuntime
    if ($null -eq $python) {
        Write-Result FAIL 'Python 3.10+ was not found on PATH.'
        $failures.Add('python')
    } elseif ($python.Version -lt [Version]'3.10') {
        Write-Result FAIL ("Python {0} is too old; Python 3.10+ is required." -f $python.Version)
        $failures.Add('python-version')
    } else {
        Write-Result OK ("{0}: Python {1}" -f $python.Label, $python.Version)
        if (-not $SkipSmokeTest) {
            $paperScript = Join-Path $repositoryRoot '.scripts/bin/paper.py'
            $escapedPaperScript = $paperScript.Replace("'", "\\'")
            $syntaxCheck = "import ast, pathlib; ast.parse(pathlib.Path(r'$escapedPaperScript').read_text(encoding='utf-8'))"
            $compileArguments = @($python.Prefix) + @('-c', $syntaxCheck)
            & $python.Command @compileArguments
            if ($LASTEXITCODE -eq 0) {
                Write-Result OK 'paper.py syntax check passed without creating bytecode.'
            } else {
                Write-Result FAIL 'paper.py syntax check failed.'
                $failures.Add('paper.py')
            }
        }
    }

    if (Get-Command uv -ErrorAction SilentlyContinue) {
        $uvVersion = (& uv --version 2>$null | Select-Object -First 1).Trim()
        Write-Result OK ("{0}" -f $uvVersion)
    } else {
        Write-Result FAIL 'uv/uvx was not found. Install it with: winget install --id Astral-sh.UV -e'
        $failures.Add('uv')
    }

    if (Get-Command codex -ErrorAction SilentlyContinue) {
        Write-Result OK 'Codex CLI is available.'
    } else {
        Write-Result WARN 'Codex CLI was not found. Codex Desktop can still open this workspace.'
    }

    try {
        $mcpConfig = Get-Content -Raw -Encoding utf8 (Join-Path $repositoryRoot '.mcp.json') | ConvertFrom-Json
        if ($null -eq $mcpConfig.mcpServers) {
            throw 'mcpServers is missing.'
        }
        Write-Result OK '.mcp.json is valid JSON.'
    } catch {
        Write-Result FAIL (".mcp.json is invalid: {0}" -f $_.Exception.Message)
        $failures.Add('.mcp.json')
    }

    $codexConfig = Get-Content -Raw -Encoding utf8 (Join-Path $repositoryRoot '.codex/config.toml')
    $expectedServers = @('arxiv-mcp', 'exa', 'paper-search-mcp')
    foreach ($server in $expectedServers) {
        if ($codexConfig -match ("\[mcp_servers\.{0}\]" -f [regex]::Escape($server))) {
            Write-Result OK ("Codex MCP configured: {0}" -f $server)
        } else {
            Write-Result FAIL ("Codex MCP entry is missing: {0}" -f $server)
            $failures.Add("mcp:$server")
        }
    }

    if ([string]::IsNullOrWhiteSpace($env:EXA_API_KEY)) {
        Write-Result INFO 'EXA_API_KEY is not set; Exa search is optional and currently unavailable.'
    } else {
        Write-Result OK 'EXA_API_KEY is present for this session.'
    }

    Write-Host ''
    if ($failures.Count -eq 0) {
        Write-Result OK 'Harness is ready. Open this folder in Codex and start a new session.'
        exit 0
    }

    Write-Result FAIL ("Harness is not ready. Resolve: {0}" -f ($failures -join ', '))
    exit 1
} finally {
    Pop-Location
}
