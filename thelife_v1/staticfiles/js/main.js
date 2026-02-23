/* ============================================
   TheLife — Main JavaScript
   HTMX helpers, activity search, push notifications
   ============================================ */

document.addEventListener('DOMContentLoaded', function() {
    initActivitySearch();
    initCatchupPrompts();
    initScoreAnimations();
    initMetadataToggle();
});

/* --- Activity Search (for quick logging) --- */
function initActivitySearch() {
    const searchInputs = document.querySelectorAll('[data-activity-search]');
    searchInputs.forEach(input => {
        let timeout;
        const resultsContainer = input.closest('.search-container')?.querySelector('.search-results');
        if (!resultsContainer) return;

        input.addEventListener('input', function() {
            clearTimeout(timeout);
            const q = this.value.trim();
            if (q.length < 1) {
                resultsContainer.classList.remove('active');
                return;
            }
            timeout = setTimeout(() => {
                fetch(`/activities/search/?q=${encodeURIComponent(q)}`)
                    .then(r => r.json())
                    .then(data => {
                        resultsContainer.innerHTML = '';
                        if (data.results && data.results.length > 0) {
                            data.results.forEach(item => {
                                const div = document.createElement('div');
                                div.className = 'search-result-item';
                                div.innerHTML = `
                                    <span style="color:${item.color}">●</span>
                                    <span>${item.label}</span>
                                `;
                                div.addEventListener('click', () => {
                                    selectSearchResult(input, item);
                                    resultsContainer.classList.remove('active');
                                });
                                resultsContainer.appendChild(div);
                            });
                            resultsContainer.classList.add('active');
                        } else {
                            resultsContainer.classList.remove('active');
                        }
                    });
            }, 250);
        });

        // Close on outside click
        document.addEventListener('click', function(e) {
            if (!input.contains(e.target) && !resultsContainer.contains(e.target)) {
                resultsContainer.classList.remove('active');
            }
        });
    });
}

function selectSearchResult(input, item) {
    // Set category and type dropdowns based on selection
    const form = input.closest('form');
    if (!form) return;

    if (item.type === 'category') {
        const catSelect = form.querySelector('#id_category');
        if (catSelect) {
            catSelect.value = item.id;
            catSelect.dispatchEvent(new Event('change'));
        }
    } else if (item.type === 'activity_type') {
        const catSelect = form.querySelector('#id_category');
        if (catSelect) {
            catSelect.value = item.category_id;
            catSelect.dispatchEvent(new Event('change'));
            // Wait for HTMX to load types, then select
            setTimeout(() => {
                const typeSelect = form.querySelector('#id_activity_type');
                if (typeSelect) typeSelect.value = item.id;
            }, 500);
        }
    }

    input.value = item.label;
}

/* --- Catch-up Prompts --- */
function initCatchupPrompts() {
    const catchupBlocks = document.querySelectorAll('.catchup-block');
    catchupBlocks.forEach(block => {
        block.addEventListener('click', function() {
            const start = this.dataset.start;
            const end = this.dataset.end;
            const date = this.dataset.date;
            // Navigate to create activity with pre-filled times
            window.location.href = `/activities/create/?date=${date}&start_time=${start}&end_time=${end}`;
        });
    });
}

/* --- Score Animations --- */
function initScoreAnimations() {
    const scoreCircles = document.querySelectorAll('.score-circle');
    scoreCircles.forEach(circle => {
        const score = parseFloat(circle.dataset.score || 0);
        circle.style.setProperty('--score-pct', score + '%');

        // Color class based on score
        circle.classList.remove('score-high', 'score-medium', 'score-low', 'score-danger');
        if (score >= 75) circle.classList.add('score-high');
        else if (score >= 50) circle.classList.add('score-medium');
        else if (score >= 25) circle.classList.add('score-low');
        else circle.classList.add('score-danger');
    });
}

/* --- Metadata Toggle (category-specific fields) --- */
function initMetadataToggle() {
    const categorySelect = document.querySelector('#id_category');
    if (!categorySelect) return;

    categorySelect.addEventListener('change', function() {
        // HTMX handles loading metadata form
        // Also trigger activity type reload
        const typeSelect = document.querySelector('#id_activity_type');
        if (typeSelect) {
            typeSelect.innerHTML = '<option value="">-- Select Type --</option>';
        }
    });
}

/* --- HTMX Event Hooks --- */
document.body.addEventListener('htmx:afterSwap', function(e) {
    // Re-init components after HTMX swaps
    initScoreAnimations();
    initCatchupPrompts();
    initActivitySearch();
});

document.body.addEventListener('htmx:beforeRequest', function(e) {
    // Show loading state
    const indicator = e.detail.elt.querySelector('.htmx-indicator');
    if (indicator) indicator.style.display = 'inline-block';
});

document.body.addEventListener('htmx:afterRequest', function(e) {
    // Hide loading state
    const indicator = e.detail.elt.querySelector('.htmx-indicator');
    if (indicator) indicator.style.display = 'none';
});

/* --- Push Notification Registration --- */
async function registerPushNotifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        console.log('Push notifications not supported');
        return;
    }

    try {
        const registration = await navigator.serviceWorker.register('/static/js/sw.js');
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(window.VAPID_PUBLIC_KEY),
        });

        await fetch('/accounts/push-subscription/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify(subscription.toJSON()),
        });
    } catch (err) {
        console.error('Push registration failed:', err);
    }
}

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    return Uint8Array.from([...rawData].map(char => char.charCodeAt(0)));
}

function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
           document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
}

/* --- Utility: Format time --- */
function formatTime(timeStr) {
    const [h, m] = timeStr.split(':');
    const hour = parseInt(h);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const h12 = hour % 12 || 12;
    return `${h12}:${m} ${ampm}`;
}

/* --- Confirm Delete --- */
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this?');
}
