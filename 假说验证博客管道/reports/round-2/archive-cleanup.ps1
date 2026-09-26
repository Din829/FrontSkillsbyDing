$ErrorActionPreference = 'Stop'
$pipelineRoot = (Resolve-Path -LiteralPath 'C:\Users\q9951\Desktop\Blog\_pipeline').Path
$snapshotRoot = (Resolve-Path -LiteralPath (Join-Path $pipelineRoot 'archive\round-1')).Path
$pipelinePrefix = $pipelineRoot.TrimEnd('\') + '\'
$snapshotPrefix = $snapshotRoot.TrimEnd('\') + '\'
$reportPath = Join-Path $pipelineRoot 'reports\round-2\archive.json'
if (Test-Path -LiteralPath $reportPath) {
    throw 'Archive report already exists; preserve it and do not rerun this one-time cleanup.'
}
$snapshotFile = Join-Path $snapshotRoot 'SNAPSHOT.json'
$snapshotHashBefore = (Get-FileHash -LiteralPath $snapshotFile -Algorithm SHA256).Hash.ToLowerInvariant()
$snapshot = Get-Content -Raw -LiteralPath $snapshotFile | ConvertFrom-Json
$snapshotDigests = @{}
foreach ($property in $snapshot.sha256.PSObject.Properties) {
    $snapshotDigests[$property.Name.Replace('\', '/')] = $property.Value
}

# Fixed inventory captured before cleanup; never enumerate future runs into deletion scope.
$targets = @(
    'audit', 'experiments', 'tests/evidence_gate',
    'runs/audit-checkpoint-article-deleted',
    'runs/audit-checkpoint-brief-untracked-drift',
    'runs/audit-checkpoint-editorial-untracked',
    'runs/audit-checkpoint-final-article-deleted',
    'runs/audit-checkpoint-final-brief-untracked-drift',
    'runs/audit-checkpoint-final-editorial-untracked',
    'runs/audit-checkpoint-final-final-gate-invalid',
    'runs/audit-checkpoint-final-gate-invalid',
    'runs/audit-checkpoint-final-initial-empty-hash-map',
    'runs/audit-checkpoint-final-no-hashes',
    'runs/audit-checkpoint-final-normal',
    'runs/audit-checkpoint-final-raw-drift',
    'runs/audit-checkpoint-final-raw-untracked-drift',
    'runs/audit-checkpoint-initial-empty-hash-map',
    'runs/audit-checkpoint-no-hashes',
    'runs/audit-checkpoint-normal',
    'runs/audit-checkpoint-raw-drift',
    'runs/audit-checkpoint-raw-untracked-drift',
    'runs/autonomous-smoke', 'runs/autonomous-smoke-v2',
    'runs/blocked-recovery', 'runs/retrieval', 'runs/retrieval-final',
    'runs/retrieval-v3', 'runs/review-behavior-pinned'
)
$report = [ordered]@{
    started_at = [DateTimeOffset]::Now.ToString('o')
    snapshot = 'archive/round-1/SNAPSHOT.json'
    snapshot_sha256_before = $snapshotHashBefore
    snapshot_manifest_file_count = $snapshot.verified_files
    operation = 'Remove only verified identical working copies; immutable archive remains in place'
    preserved_runs = @('runs/retrieval-v4', 'runs/review-behavior')
    target_allowlist = $targets
    before_root_paths = @(Get-ChildItem -LiteralPath $pipelineRoot -Force | ForEach-Object Name)
    before_run_paths = @(Get-ChildItem -LiteralPath (Join-Path $pipelineRoot 'runs') -Force | ForEach-Object Name)
    objects = @()
    link_impacts = @(
        @{path='tests/test_model_events.py:25'; action='Updated real UTF-8 fixture path to archive/round-1/runs/autonomous-smoke-v2/sessions/02-experiment-run/events.jsonl'},
        @{path='runs/retrieval-v4/execution.md:10,16 and execution.claims.json'; action='Owner notified: replay/package instructions reference removed experiments; current run intentionally not edited by archive task'},
        @{path='runs/retrieval-v4/results/package_result.py'; action='Historical packaged script references removed audit paths; owner notified, preserved unchanged as evidence'},
        @{path='runs/review-behavior/results/execution.json and snapshots'; action='Historical absolute commands retain old audit/experiments/run locations; preserved unchanged, archived originals available under archive/round-1'},
        @{path='scripts/README.md and root REPORT/run/claims/gate/results'; action='Owned by parent/skills agent; not edited by archive task'}
    )
}

function Save-ArchiveReport {
    $json = $report | ConvertTo-Json -Depth 15
    [System.IO.File]::WriteAllText($reportPath, $json, (New-Object System.Text.UTF8Encoding($false)))
}

foreach ($relative in $targets) {
    $sourceCandidate = [System.IO.Path]::GetFullPath((Join-Path $pipelineRoot $relative))
    $archiveCandidate = [System.IO.Path]::GetFullPath((Join-Path $snapshotRoot $relative))
    if (-not $sourceCandidate.StartsWith($pipelinePrefix, [StringComparison]::OrdinalIgnoreCase) -or
        $sourceCandidate.StartsWith($snapshotPrefix, [StringComparison]::OrdinalIgnoreCase) -or
        -not $archiveCandidate.StartsWith($snapshotPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside explicit source/archive boundaries: $relative"
    }
    $entry = [ordered]@{path=$relative; archive_path=('archive/round-1/' + $relative); status='checking'; verified_files=0; mismatches=@(); before_files=@()}
    if (-not (Test-Path -LiteralPath $sourceCandidate -PathType Container)) {
        $entry.status = 'source_missing_not_deleted'
        $report.objects += $entry
        Save-ArchiveReport
        continue
    }
    if (-not (Test-Path -LiteralPath $archiveCandidate -PathType Container)) {
        $entry.status = 'archive_missing_retained'
        $report.objects += $entry
        Save-ArchiveReport
        continue
    }
    $sourceResolved = (Resolve-Path -LiteralPath $sourceCandidate).Path
    $archiveResolved = (Resolve-Path -LiteralPath $archiveCandidate).Path
    if ($sourceResolved -ne $sourceCandidate -or $archiveResolved -ne $archiveCandidate) {
        throw "Unexpected resolved path: $relative"
    }
    $sourceItems = @(Get-ChildItem -LiteralPath $sourceResolved -Recurse -Force)
    $archiveItems = @(Get-ChildItem -LiteralPath $archiveResolved -Recurse -Force)
    $allItems = @((Get-Item -LiteralPath $sourceResolved), (Get-Item -LiteralPath $archiveResolved)) + $sourceItems + $archiveItems
    if (@($allItems | Where-Object { ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 }).Count -gt 0) {
        $entry.mismatches += 'Reparse point found; refuse recursive deletion'
    }
    $sourceFiles = @($sourceItems | Where-Object { -not $_.PSIsContainer })
    $sourceNames = @($sourceFiles | ForEach-Object { $_.FullName.Substring($sourceResolved.Length + 1).Replace('\', '/') } | Sort-Object)
    $archiveNames = @($archiveItems | Where-Object { -not $_.PSIsContainer } | ForEach-Object { $_.FullName.Substring($archiveResolved.Length + 1).Replace('\', '/') } | Sort-Object)
    $entry.before_files = $sourceNames
    if (($sourceNames -join "`n") -ne ($archiveNames -join "`n")) {
        $entry.mismatches += 'Source/archive file inventories differ'
    }
    $sourceDirs = @($sourceItems | Where-Object { $_.PSIsContainer } | ForEach-Object { $_.FullName.Substring($sourceResolved.Length + 1).Replace('\', '/') } | Sort-Object)
    $archiveDirs = @($archiveItems | Where-Object { $_.PSIsContainer } | ForEach-Object { $_.FullName.Substring($archiveResolved.Length + 1).Replace('\', '/') } | Sort-Object)
    if (($sourceDirs -join "`n") -ne ($archiveDirs -join "`n")) {
        $entry.mismatches += 'Source/archive directory inventories differ'
    }
    foreach ($name in $sourceNames) {
        $sourceFile = Join-Path $sourceResolved $name
        $archiveFile = Join-Path $archiveResolved $name
        $manifestName = $relative + '/' + $name
        if (-not (Test-Path -LiteralPath $archiveFile -PathType Leaf) -or -not $snapshotDigests.ContainsKey($manifestName)) {
            $entry.mismatches += "Missing archive/manifest file: $manifestName"
            continue
        }
        $sourceDigest = (Get-FileHash -LiteralPath $sourceFile -Algorithm SHA256).Hash.ToLowerInvariant()
        $archiveDigest = (Get-FileHash -LiteralPath $archiveFile -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($sourceDigest -ne $archiveDigest -or $archiveDigest -ne $snapshotDigests[$manifestName]) {
            $entry.mismatches += "Byte/hash mismatch: $manifestName"
        } else {
            $entry.verified_files++
        }
    }
    if ($entry.mismatches.Count -ne 0) {
        $entry.status = 'changed_retained'
    } else {
        # Final absolute containment check immediately before a native PowerShell deletion.
        $deletePath = (Resolve-Path -LiteralPath $sourceResolved).Path
        if ($deletePath -ne $sourceCandidate -or -not $deletePath.StartsWith($pipelinePrefix, [StringComparison]::OrdinalIgnoreCase) -or $deletePath.StartsWith($snapshotPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing changed deletion boundary: $relative"
        }
        Remove-Item -LiteralPath $deletePath -Recurse -Force
        $entry.status = 'verified_archived_working_copy_removed'
        $entry.source_exists_after = Test-Path -LiteralPath $sourceCandidate
        $entry.archive_exists_after = Test-Path -LiteralPath $archiveCandidate -PathType Container
    }
    $report.objects += $entry
    Save-ArchiveReport
    Write-Output ("{0}: {1}, files={2}" -f $relative, $entry.status, $entry.verified_files)
}
$report.finished_at = [DateTimeOffset]::Now.ToString('o')
$report.after_root_paths = @(Get-ChildItem -LiteralPath $pipelineRoot -Force | ForEach-Object Name)
$report.after_run_paths = @(Get-ChildItem -LiteralPath (Join-Path $pipelineRoot 'runs') -Force | ForEach-Object Name)
$report.snapshot_sha256_after = (Get-FileHash -LiteralPath $snapshotFile -Algorithm SHA256).Hash.ToLowerInvariant()
$report.verified_files_total = ($report.objects | ForEach-Object { $_['verified_files'] } | Measure-Object -Sum).Sum
$report.removed_objects = @($report.objects | Where-Object { $_['status'] -eq 'verified_archived_working_copy_removed' }).Count
$report.retained_objects = @($report.objects | Where-Object { $_['status'] -ne 'verified_archived_working_copy_removed' }).Count
Save-ArchiveReport
