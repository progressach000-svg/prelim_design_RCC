// ======================= SHARED =======================

// Tab switching
document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
    });
});

// Show/hide manual eta input (beam + column)
function bindEtaToggle(prefix) {
    document.getElementById(prefix + 'eta_option').addEventListener('change', (e) => {
        const custom = e.target.value === 'custom';
        document.getElementById(prefix + 'eta-custom-wrapper').style.display = custom ? 'flex' : 'none';
        document.getElementById(prefix + 'eta_custom').required = custom;
    });
}
bindEtaToggle('beam-');
bindEtaToggle('col-');

function setText(id, v) { document.getElementById(id).textContent = v; }

// Spin animation for the loading state
const style = document.createElement('style');
style.innerHTML = `
@keyframes spin {
    100% { transform: rotate(360deg); }
}
`;
document.head.appendChild(style);

// Submit helper: loading state, collect form data, POST, show result
async function submitForm(e, url, prepare, onResult) {
    e.preventDefault();

    const btn = e.target.querySelector('.btn-primary');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span style="display:inline-block; animation: spin 1s linear infinite;">↻</span> Calculating...';
    btn.disabled = true;

    const data = Object.fromEntries(new FormData(e.target).entries());
    if (prepare) prepare(data);

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (response.ok) {
            onResult(result);
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Network Error: ' + error.message);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Resolve eta (preset or manual)
function resolveEta(data) {
    data.eta = data.eta_option === 'custom' ? data.eta_custom : data.eta_option;
    delete data.eta_option;
    delete data.eta_custom;
}

function resetSection(section) {
    section.style.display = 'none';
    section.classList.remove('fade-in');
    void section.offsetWidth;   // allow reflow
}

function showSection(section) {
    section.style.display = 'block';
    section.classList.add('fade-in');
}


// ======================= SLAB =======================
document.getElementById('slab-form').addEventListener('submit', (e) =>
    submitForm(e, '/calculate', null, displaySlabResults));

function displaySlabResults(data) {
    const resultSection = document.getElementById('slab-result-section');
    resetSection(resultSection);

    // Populate data
    const badge = document.getElementById('slab-status-badge');
    badge.className = `badge ${data.status}`;
    badge.textContent = data.status === 'success' ? 'Optimal' : 'Revise Design';

    setText('slab-main-message', data.message);

    // Raw Calculations
    setText('slab-val-slab-type', data.slab_type);
    setText('slab-val-d-min', data.d_min);
    setText('slab-val-d-calc', data.D_calc);

    // Final Verdict
    document.getElementById('slab-val-d-final').innerHTML = `${data.D_final} <span style="font-size:0.5em">mm</span>`;

    // Alerts
    const reviseNote = document.getElementById('slab-revise-note');
    const finalVerdictContainer = document.getElementById('slab-final-verdict-container');
    const rawCalculations = document.getElementById('slab-raw-calculations');

    // Always show the calculations
    rawCalculations.style.display = 'block';

    if (data.status === 'success') {
        reviseNote.style.display = 'none';
        finalVerdictContainer.style.display = 'grid';
    } else {
        reviseNote.style.display = 'block';
        finalVerdictContainer.style.display = 'none';
    }

    if (window.MathJax && window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise([resultSection]).catch((err) => console.log('MathJax error:', err));
    }

    showSection(resultSection);
}


// ======================= BEAM =======================
document.getElementById('beam-form').addEventListener('submit', (e) =>
    submitForm(e, '/calculate_beam', resolveEta, displayBeamResults));

function displayBeamResults(data) {
    const resultSection = document.getElementById('beam-result-section');
    resetSection(resultSection);

    // Badge + message
    const badge = document.getElementById('beam-status-badge');
    badge.className = `badge ${data.status}`;
    badge.textContent = data.status === 'success' ? 'Deflection Governs' : 'Flexure Governs';

    setText('beam-main-message', data.message);

    // Outputs
    setText('beam-val-d-trial', data.d_trial);
    setText('beam-val-b-trial', data.b_trial);
    setText('beam-val-D-trial', data.D_trial);
    setText('beam-val-trial-size', `${data.b_trial} × ${data.D_trial}`);
    setText('beam-val-W', data.W);
    setText('beam-val-w', data.w);
    setText('beam-val-M', data.M_max);
    setText('beam-val-X', data.X);
    setText('beam-val-d-req', data.d_req);
    setText('beam-val-D-req', data.D_req);
    setText('beam-val-D-gov', data.D_gov);
    setText('beam-val-d-final', data.d_final);

    // Final verdict
    document.getElementById('beam-val-final-size').innerHTML =
        `${data.b_final} × ${data.D_final} <span style="font-size:0.5em">mm</span>`;

    // Note shown only when flexure governs
    document.getElementById('beam-revise-note').style.display =
        data.status === 'success' ? 'none' : 'flex';

    if (window.MathJax && window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise([resultSection]).catch((err) => console.log('MathJax error:', err));
    }

    showSection(resultSection);
}


// ======================= COLUMN =======================
// Show aspect ratio only for rectangular columns
document.getElementById('col-section_type').addEventListener('change', (e) => {
    document.getElementById('col-aspect-group').style.display =
        e.target.value === 'Rectangular' ? 'block' : 'none';
});

document.getElementById('column-form').addEventListener('submit', (e) =>
    submitForm(e, '/calculate_column', resolveEta, displayColumnResults));

function displayColumnResults(d) {
    const section = document.getElementById('col-result-section');
    resetSection(section);

    setText('col-status-badge', d.section_type + ' Section');
    setText('col-main-message', d.message);

    setText('col-val-W-slab', d.W_slab);
    setText('col-val-W-beam', d.W_beam);
    setText('col-val-W-wall', d.W_wall);
    setText('col-val-W-floor', d.W_floor);
    setText('col-val-W-total', d.W_total);
    setText('col-val-K', d.K_seismic);
    setText('col-val-Pu', d.Pu);
    setText('col-val-A-gross', d.A_gross);
    setText('col-val-b-calc', d.b_calc);
    setText('col-val-D-calc', d.D_calc);
    setText('col-val-A-prov', d.A_provided);
    setText('col-val-p', d.p_steel);
    setText('col-val-A-steel', d.A_steel_final);

    document.getElementById('col-val-final-size').innerHTML =
        `${d.b_final} × ${d.D_final} <span style="font-size:0.5em">mm</span>`;

    showSection(section);
}
