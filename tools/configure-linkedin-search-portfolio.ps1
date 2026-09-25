param(
    [string]$ApiUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Invoke-JoltJson(
    [string]$Uri,
    [string]$Method = "GET",
    [object]$Body = $null
) {
    $params = @{
        Uri = $Uri
        Method = $Method
        UseBasicParsing = $true
    }
    if ($null -ne $Body) {
        $params["ContentType"] = "application/json"
        $params["Body"] = ($Body | ConvertTo-Json -Depth 12)
    }

    $response = Invoke-WebRequest @params
    if ([string]::IsNullOrWhiteSpace($response.Content)) {
        return $null
    }
    $response.Content | ConvertFrom-Json
}

function Get-CanonicalKey([string]$Url) {
    $uri = [System.Uri]$Url
    $pairs = @{}
    foreach ($part in $uri.Query.TrimStart("?").Split("&", [System.StringSplitOptions]::RemoveEmptyEntries)) {
        $bits = $part.Split("=", 2)
        $key = [System.Uri]::UnescapeDataString($bits[0]).ToLowerInvariant()
        $value = if ($bits.Count -gt 1) { [System.Uri]::UnescapeDataString($bits[1]).Replace("+", " ") } else { "" }
        if ($key -notin @("currentjobid", "trackingid", "refid", "origin", "refresh", "start")) {
            $pairs[$key] = $value
        }
    }

    ($pairs.GetEnumerator() |
        Sort-Object Name |
        ForEach-Object { "$($_.Name)=$($_.Value)" }) -join "&"
}

function New-LinkedInSearchUrl(
    [string]$Keywords,
    [string]$GeoId,
    [bool]$RemoteOnly
) {
    $encodedKeywords = [System.Uri]::EscapeDataString($Keywords).Replace("%20", "+")
    $workType = if ($RemoteOnly) { "&f_WT=2" } else { "" }
    "https://www.linkedin.com/jobs/search/?f_TPR=r604800$workType&geoId=$GeoId&keywords=$encodedKeywords&sortBy=DD"
}

$health = Invoke-JoltJson "$ApiUrl/api/health"
if ($null -eq $health) {
    throw "JOLT API is not reachable at $ApiUrl."
}

# Layer 1: cross-border remote. EMEA/Microsoft qualifiers reduce country-local and
# unrelated specialist noise observed in the first real 175-item production batch.
$portfolio = @(
    @{
        label = "Application Support Engineer - EU Remote"
        keywords = "Application Support Engineer EMEA"
        geo_id = "91000000"
        remote_only = $true
        notes = "Core remote search - EMEA/EU - past week - newest first."
    },
    @{
        label = "Technical Support Engineer - EU Remote"
        keywords = "Technical Support Engineer EMEA"
        geo_id = "91000000"
        remote_only = $true
        notes = "Core remote search - EMEA/EU - past week - newest first."
    },
    @{
        label = "Production Support Engineer - EU Remote"
        keywords = "Production Support Engineer Windows EMEA"
        geo_id = "91000000"
        remote_only = $true
        notes = "Refined remote search - Windows/support bias - EMEA/EU - past week."
    },
    @{
        label = "IT Operations Engineer - EU Remote"
        keywords = "IT Operations Engineer Microsoft 365 EMEA"
        geo_id = "91000000"
        remote_only = $true
        notes = "Refined remote search - Microsoft operations bias - EMEA/EU - past week."
    },
    @{
        label = "Microsoft 365 Support Engineer - EU Remote"
        keywords = "Microsoft 365 Support Engineer EMEA"
        geo_id = "91000000"
        remote_only = $true
        notes = "Core Microsoft 365 remote search - EMEA/EU - past week."
    },
    @{
        label = "Intune Engineer - EU Remote"
        keywords = "Intune Endpoint Engineer EMEA"
        geo_id = "91000000"
        remote_only = $true
        notes = "Refined endpoint/Intune remote search - EMEA/EU - past week."
    },
    @{
        label = "System Administrator - EU Remote"
        keywords = "Windows System Administrator EMEA"
        geo_id = "91000000"
        remote_only = $true
        notes = "Refined Windows systems remote search - EMEA/EU - past week."
    },
    @{
        label = "SaaS Support Engineer - EU Remote"
        keywords = "SaaS Support Engineer EMEA"
        geo_id = "91000000"
        remote_only = $true
        notes = "Expanded remote search - SaaS/product support - EMEA/EU - past week."
    },
    @{
        label = "Infrastructure Support Engineer - EU Remote"
        keywords = "Infrastructure Support Engineer EMEA"
        geo_id = "91000000"
        remote_only = $true
        notes = "Expanded remote search - infrastructure support - EMEA/EU - past week."
    },
    @{
        label = "Cloud Support Engineer - EU Remote"
        keywords = "Cloud Support Engineer EMEA"
        geo_id = "91000000"
        remote_only = $true
        notes = "Expanded remote search - cloud support - EMEA/EU - past week."
    },

    # Layer 2: Vigo / Greater Pontevedra. No workplace filter on purpose:
    # local onsite, hybrid, and remote roles are all acceptable for discovery.
    # English/Spanish pairs are intentional so real yield can determine whether
    # both languages are worth retaining after the next production batch.
    @{
        label = "Application Support - Pontevedra Local EN"
        keywords = "Application Support Engineer"
        geo_id = "90009802"
        remote_only = $false
        notes = "Local bilingual test - Greater Pontevedra - all workplace types - English title."
    },
    @{
        label = "Soporte de Aplicaciones - Pontevedra Local ES"
        keywords = "Soporte de Aplicaciones"
        geo_id = "90009802"
        remote_only = $false
        notes = "Local bilingual test - Greater Pontevedra - all workplace types - Spanish title."
    },
    @{
        label = "IT Support - Pontevedra Local EN"
        keywords = "IT Support Engineer"
        geo_id = "90009802"
        remote_only = $false
        notes = "Local bilingual test - Greater Pontevedra - all workplace types - English title."
    },
    @{
        label = "Soporte IT - Pontevedra Local ES"
        keywords = "Técnico de Soporte IT"
        geo_id = "90009802"
        remote_only = $false
        notes = "Local bilingual test - Greater Pontevedra - all workplace types - Spanish title."
    },
    @{
        label = "System Administrator - Pontevedra Local EN"
        keywords = "System Administrator"
        geo_id = "90009802"
        remote_only = $false
        notes = "Local bilingual test - Greater Pontevedra - all workplace types - English title."
    },
    @{
        label = "Administrador de Sistemas - Pontevedra Local ES"
        keywords = "Administrador de Sistemas"
        geo_id = "90009802"
        remote_only = $false
        notes = "Local bilingual test - Greater Pontevedra - all workplace types - Spanish title."
    },

    # Layer 3: global remote / US-company opportunity capture. These searches are
    # intentionally broad on geography; JOLT Stage 1 must reject US-only,
    # residency-restricted, or work-authorization-restricted vacancies and keep
    # only roles that explicitly support Spain/EMEA/worldwide/EOR/contractor hiring.
    @{
        label = "Technical Support Engineer - Worldwide Remote"
        keywords = "Technical Support Engineer"
        geo_id = "92000000"
        remote_only = $true
        notes = "Global remote search - retain only explicit worldwide/Spain/EMEA/EOR/contractor eligibility."
    },
    @{
        label = "Application Support Engineer - Worldwide Remote"
        keywords = "Application Support Engineer"
        geo_id = "92000000"
        remote_only = $true
        notes = "Global remote search - retain only explicit worldwide/Spain/EMEA/EOR/contractor eligibility."
    },
    @{
        label = "IT Operations Engineer - Worldwide Remote"
        keywords = "IT Operations Engineer"
        geo_id = "92000000"
        remote_only = $true
        notes = "Global remote search - retain only explicit worldwide/Spain/EMEA/EOR/contractor eligibility."
    },
    @{
        label = "System Administrator - Worldwide Remote"
        keywords = "System Administrator"
        geo_id = "92000000"
        remote_only = $true
        notes = "Global remote search - retain only explicit worldwide/Spain/EMEA/EOR/contractor eligibility."
    },
    @{
        label = "SaaS Support Engineer - Worldwide Remote"
        keywords = "SaaS Support Engineer"
        geo_id = "92000000"
        remote_only = $true
        notes = "Global remote SaaS/product-support search - retain only explicit worldwide/Spain/EMEA/EOR/contractor eligibility."
    }
)

$existingResponse = Invoke-JoltJson "$ApiUrl/api/linkedin-searches"
$existing = @()
if ($null -ne $existingResponse) {
    $existing = @($existingResponse)
}

$desiredLabels = @{}
$results = @()

foreach ($definition in $portfolio) {
    $desiredLabels[$definition.label] = $true
    $url = New-LinkedInSearchUrl $definition.keywords $definition.geo_id $definition.remote_only
    $key = Get-CanonicalKey $url

    $payload = @{
        label = $definition.label
        search_url = $url
        notes = $definition.notes
        enabled = $true
        max_jobs = 50
        max_pages = 5
    }

    # Preserve saved-search identity/history when refining an existing production
    # search. Fall back to canonical URL for idempotent first-time setup.
    $match = $existing |
        Where-Object { $_.label -eq $definition.label } |
        Select-Object -First 1
    if ($null -eq $match) {
        $match = $existing |
            Where-Object { (Get-CanonicalKey ([string]$_.search_url)) -eq $key } |
            Select-Object -First 1
    }

    if ($null -eq $match) {
        $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches" "POST" $payload
        $results += [pscustomobject]@{
            action = "created"
            label = $saved.label
            id = $saved.id
        }
        $existing += $saved
        continue
    }

    $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches/$($match.id)" "POST" $payload
    $results += [pscustomobject]@{
        action = "updated"
        label = $saved.label
        id = $saved.id
    }
}

# Acceptance-only searches remain as immutable history references but are retired
# from the active portfolio and hidden from the normal list by the UI.
foreach ($search in $existing) {
    if ($search.label -notlike "Acceptance - LinkedIn*") {
        continue
    }

    $payload = @{
        label = $search.label
        search_url = $search.search_url
        notes = "Retired acceptance search retained only for discovery-history integrity."
        enabled = $false
        max_jobs = [int]$search.max_jobs
        max_pages = [int]$search.max_pages
    }
    $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches/$($search.id)" "POST" $payload
    $results += [pscustomobject]@{
        action = "retired"
        label = $saved.label
        id = $saved.id
    }
}

# Keep user-owned classification preferences aligned with what the portfolio now
# searches for. Preserve every existing preference and only extend the explicit
# title/work-mode scope the operator requested.
$preferences = Invoke-JoltJson "$ApiUrl/api/job-search-preferences"
$targetTitles = @($preferences.target_titles)
foreach ($title in @(
    "System Administrator",
    "Intune Engineer",
    "IT Support Engineer",
    "Administrador de Sistemas",
    "Técnico de Soporte IT",
    "Soporte de Aplicaciones",
    "Cloud Support Engineer",
    "Modern Workplace Engineer",
    "Endpoint Engineer",
    "Systems Support Engineer"
)) {
    if ($title -notin $targetTitles) {
        $targetTitles += $title
    }
}
$preferences.target_titles = $targetTitles

$workModes = @($preferences.preferred_work_modes)
if ("onsite" -notin $workModes) {
    $workModes += "onsite"
}
$preferences.preferred_work_modes = $workModes

# Shift/on-call patterns are not exclusion criteria. Keep them visible as job facts,
# but do not remove opportunities because of schedule pattern alone.
$preferences.preferred_shifts = @("business_hours", "flexible", "evening", "night", "rotating", "weekend")
$preferences.excluded_shifts = @()

$localNote = "On-site roles are acceptable when they are in Vigo/Greater Pontevedra; remote and hybrid remain preferred outside the local area. Shift, weekend, maintenance-window and on-call patterns are acceptable and must not independently exclude a vacancy."
if ([string]$preferences.notes -notlike "*Shift, weekend, maintenance-window and on-call patterns are acceptable*") {
    $preferences.notes = ([string]$preferences.notes).Trim()
    if ($preferences.notes) {
        $preferences.notes += " "
    }
    $preferences.notes += $localNote
}

Invoke-JoltJson "$ApiUrl/api/job-search-preferences" "POST" $preferences | Out-Null

# Persist the operator's explicit professional-experience statement as current
# reasoning context. Each track is a completed structured refresh of an existing
# professional domain with at least 3 years of real-world experience; the refresh
# does not invent additional years or specialist production depth.
$aiContextExchange = Invoke-JoltJson "$ApiUrl/api/ai-context/export"
$professionalRefresh = @{
    schema_version = "1.0"
    as_of = "2026-09-25"
    source = "explicit_user_assertion"
    professional_domain_refreshes = @(
        @{ domain = "Application Support"; minimum_professional_years = 3; refresh_track = "N2 Application Support"; refresh_completed = $true },
        @{ domain = "IT Operations"; minimum_professional_years = 3; refresh_track = "N2 IT Operations"; refresh_completed = $true },
        @{ domain = "Automation"; minimum_professional_years = 3; refresh_track = "N2 Automation"; refresh_completed = $true },
        @{ domain = "Modern Workplace"; minimum_professional_years = 3; refresh_track = "N2 Modern Workplace"; refresh_completed = $true },
        @{ domain = "Cloud"; minimum_professional_years = 3; refresh_track = "N2 Cloud"; refresh_completed = $true },
        @{ domain = "Cybersecurity"; minimum_professional_years = 3; refresh_track = "N2 Cybersecurity"; refresh_completed = $true }
    )
    interpretation = @(
        "These completed tracks systematize and update existing real professional experience; they are not study-only evidence.",
        "Treat the stated minimum years as professional-domain evidence and the completed tracks as recent structured/hands-on refresh evidence.",
        "Do not infer extra years or unrelated specialist depth such as OpenEdge, IMS/SIP/Diameter, SAP functional consulting, Oracle DBA, or other specializations not supported by the candidate record."
    )
}

$aiContextImport = @{
    contract_type = "jolt_ai_exchange_output"
    contract_version = "1.0"
    exchange_id = $aiContextExchange.exchange_id
    reviewed_at = (Get-Date).ToUniversalTime().ToString("o")
    review_source = "chatgpt"
    review_version = "jolt-explicit-professional-refresh-2026-09-25"
    scope = $aiContextExchange.scope
    feedback = @()
    context_patch = @{ candidate_evidence_summary = $professionalRefresh }
    summary = @{ source = "explicit_user_assertion" }
}
Invoke-JoltJson "$ApiUrl/api/ai-context/import" "POST" $aiContextImport | Out-Null

Invoke-JoltJson "$ApiUrl/api/evaluations/refresh" "POST" | Out-Null

$finalResponse = Invoke-JoltJson "$ApiUrl/api/linkedin-searches"
$final = @($finalResponse)
$core = @(
    $final |
        Where-Object { $_.enabled -eq $true -and $desiredLabels.ContainsKey([string]$_.label) }
)

if ($core.Count -ne $portfolio.Count) {
    throw "Portfolio verification failed: expected $($portfolio.Count) enabled production searches, found $($core.Count)."
}

Write-Host ""
Write-Host "JOLT LinkedIn portfolio v3 configured." -ForegroundColor Green
$results | Format-Table -AutoSize
Write-Host ""
Write-Host "Enabled production searches: $($core.Count)/$($portfolio.Count)"
Write-Host "Remote layer: 10 refined/expanded EU searches"
Write-Host "Local layer: 6 bilingual Greater Pontevedra searches (onsite + hybrid + remote)"
Write-Host "Global layer: 5 Worldwide Remote searches for international/EOR/contractor opportunities"
Write-Host "Sampling: 50 jobs / up to 5 pages per search"
Write-Host "Shift/on-call exclusions removed."
Write-Host "Six professional-domain refresh tracks persisted as completed (3+ years real experience each)."
Write-Host "Job-search preferences aligned and existing jobs re-evaluated."
$core |
    Sort-Object label |
    Select-Object label, max_jobs, max_pages |
    Format-Table -AutoSize
