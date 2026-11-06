# Deterministic regression evals for the machine-expert skill tooling. Each eval gets a fresh project.
$me = "$env:USERPROFILE\.claude\skills\machine-expert\scripts\me.ps1"
$root = $PSScriptRoot; $summary = @()
foreach ($d in Get-ChildItem $root -Directory | Sort-Object Name) {
    $p = Join-Path $d.FullName "eval.project"
    Get-ChildItem $d.FullName -Filter "eval*" | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
    $args = @("--project", $p, "--src", (Join-Path $d.FullName "src"), "--create")
    $t = Join-Path $d.FullName "tests.json"; if (Test-Path $t) { $args += @("--tests", $t) }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $out = & powershell -NoProfile -File $me @args 2>&1 | Out-String
    $out | Set-Content (Join-Path $d.FullName "last_run.log") -Encoding utf8
    $b = [regex]::Match($out, "BUILD_RESULT errors=(\d+)").Groups[1].Value
    $s = [regex]::Match($out, "SIM_RESULT pass=(\d+) fail=(\d+)")
    $expectFail = Test-Path (Join-Path $d.FullName "expected.txt")
    $ok = if ($expectFail) { [int]$b -gt 0 } elseif ($s.Success) { $b -eq "0" -and $s.Groups[2].Value -eq "0" } else { $b -eq "0" }
    $summary += "{0,-22} {1,-5} build_errors={2} sim={3} ({4:N0}s)" -f $d.Name, $(if ($ok) {"PASS"} else {"FAIL"}), $b, $(if ($s.Success) {"$($s.Groups[1].Value)/$([int]$s.Groups[1].Value+[int]$s.Groups[2].Value)"} else {"-"}), $sw.Elapsed.TotalSeconds
}
$summary
