/**
 * Compute Mastery — Results handling, tab switching, judge polling
 */
(function() {
    const config = window.MASTERY_CONFIG || {};

    // --- Tab Switching ---
    document.querySelectorAll('.mastery-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            // Deactivate all
            document.querySelectorAll('.mastery-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.mastery-tab-content').forEach(c => c.classList.remove('active'));
            // Activate clicked
            this.classList.add('active');
            const target = document.getElementById('tab-' + this.dataset.tab);
            if (target) target.classList.add('active');
        });
    });

    // --- Get editor code ---
    function getCode() {
        if (window.masteryEditor) {
            return window.masteryEditor.state.doc.toString();
        }
        return '';
    }

    // --- Run (sample tests only) ---
    const runBtn = document.getElementById('run-btn');
    if (runBtn) {
        runBtn.addEventListener('click', async function() {
            const code = getCode();
            if (!code.trim()) return;

            setStatus('Compiling...', 'judge-running');
            runBtn.disabled = true;

            try {
                const resp = await fetch(config.runUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': config.csrfToken,
                    },
                    body: JSON.stringify({
                        slug: config.problemSlug,
                        language: 'cpp',
                        code: code,
                        compiler_flags: document.getElementById('compiler-flags').value,
                        custom_flags: document.getElementById('custom-flags').value,
                    }),
                });

                const data = await resp.json();
                if (data.error) {
                    setStatus('Error', 'text-danger');
                    showOutput(`<div class="result-row"><span class="text-danger">${data.error}</span></div>`);
                    return;
                }

                pollForResult(data.job_id);
            } catch (e) {
                setStatus('Request failed', 'text-danger');
                showOutput(`<div class="result-row"><span class="text-danger">${e.message}</span></div>`);
            } finally {
                runBtn.disabled = false;
            }
        });
    }

    // --- Submit (all tests) ---
    const submitBtn = document.getElementById('submit-btn');
    if (submitBtn) {
        submitBtn.addEventListener('click', async function() {
            const code = getCode();
            if (!code.trim()) return;

            // Prompt for optional notes
            const notes = prompt('Version notes (optional):', '') || '';

            setStatus('Submitting...', 'judge-running');
            submitBtn.disabled = true;

            try {
                const resp = await fetch(config.submitUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': config.csrfToken,
                    },
                    body: JSON.stringify({
                        slug: config.problemSlug,
                        language: 'cpp',
                        code: code,
                        notes: notes,
                        compiler_flags: document.getElementById('compiler-flags').value,
                        custom_flags: document.getElementById('custom-flags').value,
                    }),
                });

                const data = await resp.json();
                if (data.error) {
                    setStatus('Error', 'text-danger');
                    showOutput(`<div class="result-row"><span class="text-danger">${data.error}</span></div>`);
                    return;
                }

                setStatus(`v${data.version} — Judging...`, 'judge-running');
                // Reset AI analysis tab for new submission
                const analysisEl = document.getElementById('tab-analysis');
                if (analysisEl) {
                    analysisEl.innerHTML = '<div style="padding: 16px;" class="text-muted">Waiting for judge results before AI analysis...</div>';
                }
                pollForResult(data.job_id);
            } catch (e) {
                setStatus('Request failed', 'text-danger');
                showOutput(`<div class="result-row"><span class="text-danger">${e.message}</span></div>`);
            } finally {
                submitBtn.disabled = false;
            }
        });
    }

    // --- Poll for judge result ---
    let pollTimer = null;
    let currentJobId = null;

    function pollForResult(jobId) {
        if (pollTimer) clearInterval(pollTimer);
        currentJobId = jobId;

        let attempts = 0;
        const maxAttempts = 600; // 5 minutes at 500ms

        pollTimer = setInterval(async () => {
            attempts++;
            if (attempts > maxAttempts) {
                clearInterval(pollTimer);
                setStatus('Timeout — judge took too long', 'text-warning');
                return;
            }

            try {
                const resp = await fetch(`${config.pollUrlBase}${jobId}/`, {
                    headers: { 'X-CSRFToken': config.csrfToken },
                });
                const data = await resp.json();

                if (data.status === 'completed') {
                    clearInterval(pollTimer);
                    renderResults(data.result);

                    // If AI analysis is already in the result, show it
                    if (data.result.llm_analysis) {
                        showAnalysis(data.result.llm_analysis);
                    } else {
                        // Poll for AI analysis (runs after judge result)
                        pollForAnalysis(jobId);
                    }
                } else if (data.status === 'error') {
                    clearInterval(pollTimer);
                    setStatus('Judge error', 'text-danger');
                    showOutput(`<div class="result-row"><span class="text-danger">${data.message || 'Unknown error'}</span></div>`);
                }
                // else still pending — keep polling
            } catch (e) {
                // Network error — keep trying
            }
        }, 500);
    }

    // --- Poll for AI analysis (arrives after judge result) ---
    let analysisTimer = null;

    function pollForAnalysis(jobId) {
        if (analysisTimer) clearInterval(analysisTimer);

        const el = document.getElementById('tab-analysis');
        if (el) {
            el.innerHTML = '<div style="padding: 16px;" class="text-muted"><span class="judge-running">Analyzing with qwen2.5-coder...</span></div>';
        }

        let attempts = 0;
        const maxAttempts = 240; // 2 minutes at 500ms

        analysisTimer = setInterval(async () => {
            attempts++;
            if (attempts > maxAttempts) {
                clearInterval(analysisTimer);
                if (el) el.innerHTML = '<div style="padding: 16px;" class="text-warning">AI analysis timed out.</div>';
                return;
            }

            try {
                const resp = await fetch(`${config.pollUrlBase}${jobId}/`, {
                    headers: { 'X-CSRFToken': config.csrfToken },
                });
                const data = await resp.json();

                if (data.status === 'completed' && data.result.llm_analysis) {
                    clearInterval(analysisTimer);
                    showAnalysis(data.result.llm_analysis);
                }
            } catch (e) {
                // Network error — keep trying
            }
        }, 500);
    }

    // --- Render results ---
    function renderResults(result) {
        if (!result) return;

        // Check if compile error
        if (result.compile_error) {
            setStatus('Compile Error', 'text-danger');
            showOutput(`<div style="padding: 16px;"><pre class="mastery-pre" style="color: var(--danger);">${escapeHtml(result.compile_error)}</pre></div>`);
            return;
        }

        // Per-test results
        const tests = result.test_results || [];
        let allAccepted = true;
        let outputHtml = '';

        tests.forEach((t, i) => {
            const accepted = t.status === 'accepted';
            if (!accepted) allAccepted = false;

            const statusClass = accepted ? 'text-success' : 'text-danger';
            const statusText = t.status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

            outputHtml += `<div class="result-row">
                <span class="result-status ${statusClass}">${statusText}</span>
                <span class="result-time">${formatRuntime(t.median_time_us)}</span>
                <span class="result-detail">Test #${i + 1}</span>
            </div>`;

            // Show actual vs expected for wrong answers
            if (t.status === 'wrong_answer') {
                outputHtml += `<div style="padding: 4px 16px 12px 16px; font-size: 0.8rem;">
                    <div class="text-muted mb-1">Expected:</div>
                    <pre class="mastery-pre">${escapeHtml(t.expected || '')}</pre>
                    <div class="text-muted mb-1 mt-1">Got:</div>
                    <pre class="mastery-pre" style="color: var(--danger);">${escapeHtml(t.actual_output || '')}</pre>
                </div>`;
            }

            // Show stderr for runtime errors
            if (t.status === 'runtime_error' && t.stderr_output) {
                outputHtml += `<div style="padding: 4px 16px 12px 16px;">
                    <pre class="mastery-pre" style="color: var(--danger); font-size: 0.8rem;">${escapeHtml(t.stderr_output)}</pre>
                </div>`;
            }
        });

        setStatus(allAccepted ? 'Accepted' : 'Failed', allAccepted ? 'text-success' : 'text-danger');
        showOutput(outputHtml || '<div class="result-row text-muted">No test results.</div>');

        // Timing tab
        if (result.timing) {
            showTiming(result.timing);
        }

        // Perf tab
        if (result.perf) {
            showPerf(result.perf);
        }
    }

    function showTiming(timing) {
        const el = document.getElementById('tab-timing');
        if (!el) return;
        el.innerHTML = `<div class="timing-stats">
            <div class="timing-stat">
                <div class="stat-value">${formatRuntime(timing.median_us)}</div>
                <div class="stat-label">Median</div>
            </div>
            <div class="timing-stat">
                <div class="stat-value">${formatRuntime(timing.min_us)}</div>
                <div class="stat-label">Min</div>
            </div>
            <div class="timing-stat">
                <div class="stat-value">${formatRuntime(timing.max_us)}</div>
                <div class="stat-label">Max</div>
            </div>
            <div class="timing-stat">
                <div class="stat-value">${formatRuntime(timing.std_dev_us)}</div>
                <div class="stat-label">Std Dev</div>
            </div>
        </div>`;
    }

    function showPerf(perf) {
        const el = document.getElementById('tab-perf');
        if (!el) return;
        el.innerHTML = `<table class="perf-table">
            <tr><td>Instructions</td><td>${formatCount(perf.instructions)}</td></tr>
            <tr><td>Cycles</td><td>${formatCount(perf.cycles)}</td></tr>
            <tr><td>IPC</td><td>${perf.ipc != null ? perf.ipc.toFixed(2) : '—'}</td></tr>
            <tr><td>Cache Misses</td><td>${formatCount(perf.cache_misses)}</td></tr>
            <tr><td>Branch Misses</td><td>${formatCount(perf.branch_misses)}</td></tr>
            <tr><td>Context Switches</td><td>${perf.context_switches != null ? perf.context_switches : '—'}</td></tr>
        </table>`;
    }

    // --- AI Analysis rendering ---
    function showAnalysis(text) {
        const el = document.getElementById('tab-analysis');
        if (!el) return;
        // Simple markdown-to-HTML: bold, headers, lists, code blocks
        let html = escapeHtml(text);
        // Code blocks
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="mastery-pre">$2</pre>');
        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code style="background:var(--surface-2);padding:2px 6px;border-radius:4px;">$1</code>');
        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // Headers
        html = html.replace(/^### (.+)$/gm, '<h4 style="color:var(--text-primary);margin:12px 0 4px;">$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3 style="color:var(--text-primary);margin:12px 0 4px;">$1</h3>');
        // List items
        html = html.replace(/^- (.+)$/gm, '<li style="margin-left:16px;">$1</li>');
        html = html.replace(/^(\d+)\. (.+)$/gm, '<li style="margin-left:16px;">$2</li>');
        // Paragraphs (double newline)
        html = html.replace(/\n\n/g, '</p><p>');
        html = html.replace(/\n/g, '<br>');
        el.innerHTML = `<div class="mastery-description" style="padding:16px;font-size:0.88rem;"><p>${html}</p></div>`;
    }

    // --- Helpers ---
    function setStatus(text, className) {
        const el = document.getElementById('judge-status');
        if (el) {
            el.textContent = text;
            el.className = className || 'text-muted';
        }
    }

    function showOutput(html) {
        const el = document.getElementById('tab-output');
        if (el) el.innerHTML = html;
        // Switch to output tab
        document.querySelectorAll('.mastery-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.mastery-tab-content').forEach(c => c.classList.remove('active'));
        document.querySelector('[data-tab="output"]')?.classList.add('active');
        document.getElementById('tab-output')?.classList.add('active');
    }

    function formatRuntime(us) {
        if (us == null) return '—';
        if (us >= 1000000) return (us / 1000000).toFixed(2) + ' s';
        if (us >= 1000) return (us / 1000).toFixed(2) + ' ms';
        return us.toFixed(1) + ' us';
    }

    function formatCount(n) {
        if (n == null) return '—';
        return n.toLocaleString();
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
})();
