// Three.js Background & Interface Logic for LoanShield Custom Frontend

// 1. Initialize WebGL Particle Background (Three.js)
let scene, camera, renderer, particles;
let mouseX = 0, mouseY = 0;
const windowHalfX = window.innerWidth / 2;
const windowHalfY = window.innerHeight / 2;

function initWebGL() {
    const canvas = document.getElementById('webgl-canvas');
    if (!canvas) return;

    // Create scene
    scene = new THREE.Scene();

    // Camera setup
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 1, 3000);
    camera.position.z = 1000;

    // Create dot-matrix particles
    const particleCount = 600;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    const color1 = new THREE.Color("#A3E635");
    const color2 = new THREE.Color("#BEF264");

    for (let i = 0; i < particleCount; i++) {
        // Dot particles scattered in wide scene band
        positions[i * 3] = (Math.random() - 0.5) * 2000;
        positions[i * 3 + 1] = (Math.random() - 0.5) * 1000;
        positions[i * 3 + 2] = (Math.random() - 0.5) * 1000;

        // Custom soft colors (interpolated neon green)
        const t = Math.random();
        const mixedColor = color1.clone().lerp(color2, t);
        colors[i * 3] = mixedColor.r;
        colors[i * 3 + 1] = mixedColor.g;
        colors[i * 3 + 2] = mixedColor.b;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    // Circular particle material
    const material = new THREE.PointsMaterial({
        size: 4,
        vertexColors: true,
        transparent: true,
        opacity: 0.35,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    });

    // Create system
    particles = new THREE.Points(geometry, material);
    scene.add(particles);

    // Renderer setup
    renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // DPR clamp
    renderer.setSize(window.innerWidth, window.innerHeight);

    // Document events
    document.addEventListener('mousemove', onDocumentMouseMove);
    window.addEventListener('resize', onWindowResize);

    animate();
}

function onDocumentMouseMove(event) {
    mouseX = (event.clientX - windowHalfX) * 0.25;
    mouseY = (event.clientY - windowHalfY) * 0.25;
}

function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    drawNodeConnections(); // Redraw connections when nodes scale
}

function animate() {
    requestAnimationFrame(animate);

    // Slow breathing pulse
    const time = Date.now() * 0.0003;
    particles.rotation.y = time * 0.1;
    particles.rotation.x = Math.sin(time) * 0.05;

    // Pointer-reactive parallax drift
    camera.position.x += (mouseX - camera.position.x) * 0.02;
    camera.position.y += (-mouseY - camera.position.y) * 0.02;
    camera.lookAt(scene.position);

    renderer.render(scene, camera);
}

// 2. SVG Node Connections Drawer
function drawNodeConnections() {
    const lines = [
        { from: "node-start", to: "node-gatekeeper", path: "path-start-gate" },
        { from: "node-gatekeeper", to: "node-financial", path: "path-gate-fin" },
        { from: "node-gatekeeper", to: "node-fraud", path: "path-gate-fraud" },
        { from: "node-financial", to: "node-join", path: "path-fin-join" },
        { from: "node-fraud", to: "node-join", path: "path-fraud-join" },
        { from: "node-join", to: "node-scorer", path: "path-join-score" },
        { from: "node-scorer", to: "node-hitl", path: "path-score-hitl" },
        { from: "node-scorer", to: "node-explanation", path: "path-score-exp" },
        { from: "node-hitl", to: "node-explanation", path: "path-hitl-exp" },
        { from: "node-explanation", to: "node-notifier", path: "path-exp-notif" }
    ];

    const viewport = document.querySelector('.graph-viewport');
    if (!viewport) return;
    const viewRect = viewport.getBoundingClientRect();

    lines.forEach(line => {
        const fromNode = document.getElementById(line.from);
        const toNode = document.getElementById(line.to);
        const pathEl = document.getElementById(line.path);

        if (fromNode && toNode && pathEl) {
            const rFrom = fromNode.getBoundingClientRect();
            const rTo = toNode.getBoundingClientRect();

            // Calculate center points relative to viewport container
            const x1 = (rFrom.left + rFrom.width / 2) - viewRect.left;
            const y1 = (rFrom.top + rFrom.height / 2) - viewRect.top;
            const x2 = (rTo.left + rTo.width / 2) - viewRect.left;
            const y2 = (rTo.top + rTo.height / 2) - viewRect.top;

            // Draw clean curved bezier paths
            const dx = x2 - x1;
            const dy = y2 - y1;
            let d = `M ${x1} ${y1} C ${x1 + dx * 0.4} ${y1}, ${x2 - dx * 0.4} ${y2}, ${x2} ${y2}`;

            // Adjust paths for direct top-to-bottom lines
            if (Math.abs(dx) < 10) {
                d = `M ${x1} ${y1} L ${x2} ${y2}`;
            }

            pathEl.setAttribute('d', d);
        }
    });
}

// Position nodes dynamically inside the Logic Grid
function positionNodes() {
    // Percentages below were solved against the guaranteed minimum viewport
    // width (see .graph-viewport min-width: 1020px in style.css) so that,
    // combined with each node's real box width (145px default / 60px start /
    // 50px small) and the translate(-50%, -50%) centering below, every pair
    // of horizontally-adjacent nodes keeps a positive gap (~15-30px) instead
    // of overlapping or spilling past the container edge. If the panel
    // renders wider than 1020px (the common case) these same percentages
    // just spread out further apart — still safe, just roomier.
    const positions = {
        "node-start": { left: "6%", top: "15%" },
        "node-gatekeeper": { left: "19%", top: "50%" },
        "node-financial": { left: "35%", top: "22%" },
        "node-fraud": { left: "35%", top: "78%" },
        "node-join": { left: "47%", top: "50%" },
        "node-scorer": { left: "58%", top: "50%" },
        "node-hitl": { left: "75%", top: "22%" },
        "node-explanation": { left: "75%", top: "78%" },
        "node-notifier": { left: "91%", top: "50%" }
    };

    for (const [id, pos] of Object.entries(positions)) {
        const el = document.getElementById(id);
        if (el) {
            el.style.left = pos.left;
            el.style.top = pos.top;
            // Center the node placement using transform translate offset
            el.style.transform = "translate(-50%, -50%)";
        }
    }
}

// 3. API & Workflow Execution States
let activeSessionId = null;
let lastLetterInfo = null; // { letter, applicant_name, applicant_id, decision, decision_date }
let currentAuditLength = 0;

async function loadBenchmarkTemplates() {
    const grid = document.getElementById('benchmark-grid');
    if (!grid) return;

    try {
        const response = await fetch('/api/benchmark');
        if (!response.ok) throw new Error('Failed to fetch benchmark profiles');

        const cases = await response.json();
        grid.innerHTML = '';

        // Select specific rows to represent key scenarios (Rows 1, 18, 31, 42, 47, 51)
        const highlightRows = [1, 18, 31, 42, 47, 51];
        const profiles = cases.filter(c => highlightRows.includes(c.row));

        profiles.forEach(profile => {
            const card = document.createElement('div');
            card.className = `benchmark-card`;

            let badgeClass = 'badge-prime';
            let label = 'Prime';
            if (profile.target_scenario === 'Thin Credit') {
                badgeClass = 'badge-thin';
                label = 'Review';
            } else if (['High DTI', 'Fraud', 'Terminated Employment'].includes(profile.target_scenario)) {
                badgeClass = 'badge-reject';
                label = 'Reject';
            } else if (profile.target_scenario === 'Missing Documents') {
                badgeClass = 'badge-thin';
                label = 'Incomplete';
            }

            card.innerHTML = `
                <div class="benchmark-title">${profile.name}</div>
                <div class="benchmark-desc">ID: ${profile.applicant_id} (${profile.purpose})</div>
                <span class="benchmark-badge ${badgeClass}">${label}</span>
            `;

            card.addEventListener('click', () => {
                // Reset UI state before loading new candidate data
                activeSessionId = null;
                currentAuditLength = 0;
                resetWorkflowUI();

                // Remove active class from others
                document.querySelectorAll('.benchmark-card').forEach(el => el.classList.remove('active'));
                card.classList.add('active');

                // Fill Form
                document.getElementById('applicant_id').value = profile.applicant_id;
                document.getElementById('customer_id').value = profile.customer_id;
                document.getElementById('name').value = profile.name;
                document.getElementById('aadhaar_number').value = profile.aadhaar_number;
                document.getElementById('dob').value = profile.dob;
                document.getElementById('phone_number').value = profile.phone_number;
                document.getElementById('home_address').value = profile.home_address;
                document.getElementById('age').value = profile.age;
                document.getElementById('declared_income_monthly').value = profile.declared_income_monthly;
                document.getElementById('loan_amount').value = profile.loan_amount;
                document.getElementById('purpose').value = profile.purpose;
                document.getElementById('target_scenario').value = profile.target_scenario;
                document.getElementById('email').value = '';

                logToTerminal(`[System] Loaded template for ${profile.name} (${profile.target_scenario})`);
            });

            grid.appendChild(card);
        });

    } catch (error) {
        grid.innerHTML = `<div class="log-line error">Failed to load benchmark templates. Make sure custom server is running.</div>`;
    }
}

// Log line helper
function logToTerminal(message, severity = 'info') {
    const body = document.getElementById('terminal-body');
    if (!body) return;

    const line = document.createElement('div');
    line.className = `log-line ${severity}`;
    line.innerText = message;
    body.appendChild(line);
    body.scrollTop = body.scrollHeight;
}

// Reset UI state
function resetWorkflowUI() {
    currentAuditLength = 0;
    document.getElementById('terminal-body').innerHTML = '';
    document.getElementById('metric-score').innerText = '-';

    const badge = document.getElementById('verdict-badge');
    badge.className = 'verdict-badge neutral';
    badge.innerText = 'PENDING';

    // Hide letter
    document.getElementById('ecoa-section').style.display = 'none';
    document.getElementById('ecoa-letter-content').innerHTML = '';
    lastLetterInfo = null;

    // Reset hitl Empty controls
    document.getElementById('hitl-controls-body').innerHTML = `
        <div class="hitl-empty-state">
            <i class="fa-solid fa-hourglass-empty"></i>
            <p>No active escalation interrupts. Workflow running normally.</p>
        </div>
    `;

    // Remove graph node glow states
    document.querySelectorAll('.graph-node').forEach(node => {
        node.className = 'graph-node';
        if (node.id === 'node-start') node.classList.add('node-start');
        if (node.id === 'node-join') node.classList.add('node-small');

        const status = node.querySelector('.node-status');
        if (status) status.innerText = 'Idle';
    });

    document.querySelectorAll('.connection-line').forEach(line => line.classList.remove('active'));
}

// Node State Glow Controller
function updateGraphVisualization(state, isInterrupted, interruptId) {
    const auditTrail = state.audit_trail || [];

    // Set nodes to completed if we have processed past them
    auditTrail.forEach(log => {
        let nodeEl = null;
        if (log.node_name === 'gatekeeper_node') nodeEl = document.getElementById('node-gatekeeper');
        if (log.node_name === 'financial_analysis_node') nodeEl = document.getElementById('node-financial');
        if (log.node_name === 'fraud_analysis_node') nodeEl = document.getElementById('node-fraud');
        if (log.node_name === 'risk_scoring_node') {
            nodeEl = document.getElementById('node-scorer');
            // Once Scorer is hit, Join node is implied complete
            document.getElementById('node-join').classList.add('completed');
            document.getElementById('path-fin-join').classList.add('active');
            document.getElementById('path-fraud-join').classList.add('active');
            document.getElementById('path-join-score').classList.add('active');
        }
        if (log.node_name === 'human_underwriter_hitl_node') nodeEl = document.getElementById('node-hitl');
        if (log.node_name === 'explanation_node') nodeEl = document.getElementById('node-explanation');
        if (log.node_name === 'notifier_node') nodeEl = document.getElementById('node-notifier');

        if (nodeEl) {
            nodeEl.classList.remove('running', 'paused');
            nodeEl.classList.add('completed');
            const status = nodeEl.querySelector('.node-status');
            if (status) status.innerText = 'Complete';
        }
    });

    // Make connection paths glow active dynamically
    if (auditTrail.length > 0) {
        document.getElementById('path-start-gate').classList.add('active');
        document.getElementById('node-start').classList.add('completed');
    }

    const lastLog = auditTrail[auditTrail.length - 1];
    if (lastLog) {
        // Highlight current running node
        let runningNode = null;
        if (lastLog.node_name === 'gatekeeper_node') {
            runningNode = document.getElementById('node-gatekeeper');
            document.getElementById('path-start-gate').classList.add('active');
        }
        if (lastLog.node_name === 'financial_analysis_node' || lastLog.node_name === 'fraud_analysis_node') {
            document.getElementById('node-financial').classList.add('running');
            document.getElementById('node-fraud').classList.add('running');
            document.getElementById('path-gate-fin').classList.add('active');
            document.getElementById('path-gate-fraud').classList.add('active');
        }
        if (lastLog.node_name === 'risk_scoring_node') {
            runningNode = document.getElementById('node-scorer');
        }

        if (runningNode && !isInterrupted) {
            runningNode.classList.add('running');
            const status = runningNode.querySelector('.node-status');
            if (status) status.innerText = 'Active';
        }
    }

    // Handle paused nodes (Interrupted HITL states)
    if (isInterrupted) {
        if (interruptId === 'document_override') {
            const gateNode = document.getElementById('node-gatekeeper');
            gateNode.classList.remove('running', 'completed');
            gateNode.classList.add('paused');
            gateNode.querySelector('.node-status').innerText = 'Paused';
        }
        if (interruptId === 'underwriter_override') {
            const hitlNode = document.getElementById('node-hitl');
            hitlNode.classList.remove('running', 'completed');
            hitlNode.classList.add('paused');
            hitlNode.querySelector('.node-status').innerText = 'Escalated';

            document.getElementById('path-score-hitl').classList.add('active');
            document.getElementById('node-scorer').classList.add('completed');
        }
    }
}

// Stream and print Audit Trail lines
function printAuditTrailLogs(auditTrail) {
    if (auditTrail.length > currentAuditLength) {
        for (let i = currentAuditLength; i < auditTrail.length; i++) {
            const log = auditTrail[i];
            let severity = 'info';
            if (log.severity === 'WARNING') severity = 'warn';
            if (log.severity === 'CRITICAL') severity = 'error';

            logToTerminal(`[${log.node_name}] ${log.message}`, severity);
        }
        currentAuditLength = auditTrail.length;
    }
}

// Load final state outputs (gauges, decisions, ecoa notice letter)
function displayWorkflowResults(state) {
    // 1. Composite Score
    const score = state.composite_score;
    if (score !== undefined) {
        const scoreEl = document.getElementById('metric-score');
        scoreEl.innerText = typeof score === 'number' ? score.toFixed(1) : score;
        document.querySelector('.score-ring').classList.add('active');
    }

    // 2. Verdict Badge
    const decision = state.decision;
    const badge = document.getElementById('verdict-badge');
    if (decision) {
        let label = decision.replace('_', ' ');
        let badgeClass = 'neutral';

        if (decision === 'AUTO_APPROVE') {
            label = 'APPROVED';
            badgeClass = 'approve';
        } else if (decision === 'AUTO_REJECT') {
            // Check if it's due to incomplete documents
            const reasons = state.fraud_reasons || [];
            const isDocIssue = reasons.some(r => r.toLowerCase().includes('document') || r.toLowerCase().includes('missing'));
            if (isDocIssue) {
                label = 'INCOMPLETE';
                badgeClass = 'review';
            } else {
                label = 'REJECTED';
                badgeClass = 'reject';
            }
        } else if (decision === 'HUMAN_REVIEW') {
            label = 'HUMAN REVIEW';
            badgeClass = 'review';
        }

        badge.innerText = label;
        badge.className = `verdict-badge ${badgeClass}`;
    }

    // 3. Notification Dispatch Status
    const notif = state.notification_result;
    if (notif) {
        const channel = notif.channel || 'Mock Dispatcher';
        const recipient = notif.recipient || state.email || 'N/A';
        const delivered = notif.delivered ? '✓ Delivered' : '✗ Failed';
        logToTerminal(`[Notification] ${delivered} via ${channel} → ${recipient}`, delivered ? 'info' : 'error');
    }

    // 4. ECOA Notice Letter
    const ecoLetter = state.eco_letter || (state.explanation_result ? state.explanation_result.eco_letter : null);
    if (ecoLetter) {
        const letterPanel = document.getElementById('ecoa-section');
        const content = document.getElementById('ecoa-letter-content');

        const notifBanner = notif ? `
            <div style="background: rgba(163,230,53,0.1); border: 1px solid rgba(163,230,53,0.3); border-radius: 8px; padding: 12px 16px; margin-bottom: 16px;">
                <i class="fa-solid fa-bell" style="color: #A3E635;"></i>
                <strong style="color: #A3E635;">Notification Dispatch</strong>
                <span style="float: right; color: #A3E635;">${notif.delivered ? '✓ Delivered' : '✗ Failed'}</span>
                <div style="margin-top: 6px; font-size: 0.9rem; color: #ccc;">
                    Channel: ${notif.channel || 'Mock Dispatcher'} &nbsp;|&nbsp; 
                    Recipient: ${notif.recipient || state.email || 'N/A'}
                    ${notif.delivered && !notif.channel?.includes('SMTP') ? '<br><em style="color: #999;">(Mock mode — no real email sent. Configure SMTP env vars for actual delivery.)</em>' : ''}
                </div>
            </div>
        ` : '';

        content.innerHTML = `${notifBanner}<h3>Decision Notice Issued</h3>
        <p style="white-space: pre-wrap;">${ecoLetter}</p>`;

        letterPanel.style.display = 'block';
        letterPanel.scrollIntoView({ behavior: 'smooth' });

        // Keep the raw letter + metadata around so the PDF download button can use it
        lastLetterInfo = {
            letter: ecoLetter,
            applicant_name: state.name || '',
            applicant_id: state.applicant_id || '',
            decision: state.decision || '',
            decision_date: state.decision_date || ''
        };
    }
}

// 6. Download the final decision letter as a PDF
async function downloadLetterPDF() {
    if (!lastLetterInfo || !lastLetterInfo.letter) {
        logToTerminal(`[System] No letter available to download yet.`, 'warn');
        return;
    }

    const btn = document.getElementById('btn-download-letter');
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Preparing PDF...`;

    try {
        const response = await fetch('/api/letter/pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(lastLetterInfo)
        });

        if (!response.ok) throw new Error('PDF generation failed');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const safeId = (lastLetterInfo.applicant_id || 'letter').replace(/[^A-Za-z0-9_-]/g, '');
        a.download = `LoanShield_Decision_Notice_${safeId}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

        logToTerminal(`[System] Decision letter PDF downloaded.`);
    } catch (err) {
        logToTerminal(`[System Error] Failed to generate PDF: ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

// Injects appropriate override buttons into the action pane
function displayHITLControls(interruptId, interruptMsg) {
    const controlsContainer = document.getElementById('hitl-controls-body');
    if (!controlsContainer) return;

    if (interruptId === 'document_override') {
        controlsContainer.innerHTML = `
            <div class="hitl-card">
                <p><strong><i class="fa-solid fa-triangle-exclamation" style="color:#F59E0B"></i> Document Verification Check failed:</strong></p>
                <p style="color:#A3A3A3">${interruptMsg}</p>
                <div class="hitl-options">
                    <button class="hitl-btn btn-reject" onclick="submitResumeOverride('reject')">Reject Application</button>
                    <button class="hitl-btn btn-approve" onclick="submitResumeOverride('resume')">Override & Resume</button>
                </div>
            </div>
        `;
    } else if (interruptId === 'underwriter_override') {
        controlsContainer.innerHTML = `
            <div class="hitl-card">
                <p><strong><i class="fa-solid fa-shield-halved" style="color:#F59E0B"></i> Escalated to Human Underwriting Review:</strong></p>
                <p style="color:#A3A3A3">${interruptMsg}</p>
                <div class="hitl-options">
                    <button class="hitl-btn btn-reject" onclick="submitResumeOverride('reject')">REJECT LOAN</button>
                    <button class="hitl-btn btn-approve" onclick="submitResumeOverride('approve')">APPROVE LOAN</button>
                </div>
            </div>
        `;
    }
}

// 4. Handle Submit Workflow Form
async function handleFormSubmit(e) {
    e.preventDefault();
    resetWorkflowUI();

    const btnSubmit = document.getElementById('btn-submit');
    btnSubmit.disabled = true;
    btnSubmit.innerHTML = `Running Analysis <span class="loading-pulse"></span>`;

    // Package fields
    const payload = {
        applicant_id: document.getElementById('applicant_id').value || "APP-NEW",
        customer_id: document.getElementById('customer_id').value || "CU-NEW",
        name: document.getElementById('name').value,
        aadhaar_number: document.getElementById('aadhaar_number').value,
        dob: document.getElementById('dob').value,
        phone_number: document.getElementById('phone_number').value,
        home_address: document.getElementById('home_address').value,
        age: parseInt(document.getElementById('age').value),
        declared_income_monthly: parseFloat(document.getElementById('declared_income_monthly').value),
        loan_amount: parseFloat(document.getElementById('loan_amount').value),
        purpose: document.getElementById('purpose').value,
        target_scenario: document.getElementById('target_scenario').value || "Custom",
        email: document.getElementById('email').value
    };

    logToTerminal(`[System] Dispatching request for ${payload.name} (Amount: ₹${payload.loan_amount.toLocaleString()})`);

    try {
        // Step 1: Create local session
        const sessResponse = await fetch('/api/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!sessResponse.ok) throw new Error('Failed to instantiate analysis session');

        const { session_id } = await sessResponse.json();
        activeSessionId = session_id;

        // Step 2: Open SSE stream endpoint
        const sse = new EventSource(`/api/run?session_id=${session_id}`);

        sse.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'event') {
                const state = data.state;
                printAuditTrailLogs(state.audit_trail || []);
                updateGraphVisualization(state, data.is_interrupted, data.interrupt_id);

                if (data.is_interrupted) {
                    logToTerminal(`[System] Graph workflow interrupted: ${data.interrupt_id}. Halting for input.`, 'warn');
                    displayHITLControls(data.interrupt_id, data.interrupt_message);
                    sse.close();
                    btnSubmit.disabled = false;
                    btnSubmit.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Verify Loan Approval Status`;
                }

                // If completed (has letter generated or notifier complete)
                if (state.decision && !data.is_interrupted && (state.eco_letter || (state.audit_trail && state.audit_trail.some(l => l.node_name === 'notifier_node')))) {
                    displayWorkflowResults(state);
                    sse.close();
                    btnSubmit.disabled = false;
                    btnSubmit.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Verify Loan Approval Status`;
                }
            } else if (data.type === 'error') {
                logToTerminal(`[System Error] ${data.message}`, 'error');
                sse.close();
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Verify Loan Approval Status`;
            }
        };

        sse.onerror = (err) => {
            logToTerminal(`[System Connection] Server-Sent Events stream terminated.`, 'warn');
            sse.close();
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Verify Loan Approval Status`;
        };

     } catch (err) {
        logToTerminal(`[System Connection] Connection failed: ${err.message}`, 'error');
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Verify Loan Approval Status`;
    }
}

// 5. Submit HITL Overrides
async function submitResumeOverride(action) {
    if (!activeSessionId) return;

    logToTerminal(`[Underwriter] Submitted override input action: ${action.toUpperCase()}`);

    // Clear HITL action panel back to empty state
    document.getElementById('hitl-controls-body').innerHTML = `
        <div class="hitl-empty-state">
            <i class="fa-solid fa-circle-notch fa-spin" style="color:var(--primary)"></i>
            <p>Resuming workflow analysis...</p>
        </div>
    `;

    try {
        const response = await fetch(`/api/resume?session_id=${activeSessionId}&action=${action}`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Override request failed');

        const data = await response.json();
        const state = data.state;

        // Print subsequent logs
        printAuditTrailLogs(state.audit_trail || []);
        updateGraphVisualization(state, data.is_interrupted, data.interrupt_id);

        if (data.is_interrupted) {
            // Flow hit a secondary interrupt
            logToTerminal(`[System] Workflow hit secondary interrupt: ${data.interrupt_id}. Halting.`, 'warn');
            displayHITLControls(data.interrupt_id, data.interrupt_message);
        } else {
            // Flow completed!
            logToTerminal(`[System] Workflow evaluation completed successfully.`);
            displayWorkflowResults(state);
            // Restore overrides placeholder
            document.getElementById('hitl-controls-body').innerHTML = `
                <div class="hitl-empty-state">
                    <i class="fa-solid fa-check-circle" style="color:var(--primary)"></i>
                    <p>Verification completed. Session finished.</p>
                </div>
            `;
        }

    } catch (err) {
        logToTerminal(`[System Error] Failed to override: ${err.message}`, 'error');
    }
}

// Clear Form Controls
function clearForm() {
    document.getElementById('application-form').reset();
    document.getElementById('applicant_id').value = "APP-NEW";
    document.getElementById('customer_id').value = "CU-NEW";
    document.getElementById('target_scenario').value = "Custom";

    document.querySelectorAll('.benchmark-card').forEach(el => el.classList.remove('active'));
    resetWorkflowUI();
    logToTerminal(`[System] Cleared form fields and dashboard.`);
}

// 6. On Page Load Lifecycle
window.addEventListener('DOMContentLoaded', () => {
    // Coordinate nodes placement
    positionNodes();

    // Draw SVG connects
    setTimeout(drawNodeConnections, 100);

    // Keep connection lines aligned with nodes when the panel is resized
    let graphResizeTimer = null;
    window.addEventListener('resize', () => {
        clearTimeout(graphResizeTimer);
        graphResizeTimer = setTimeout(drawNodeConnections, 150);
    });

    // Initialize WebGL Dot particle system
    initWebGL();

    // Fetch mock database records
    loadBenchmarkTemplates();

    // Event bindings
    document.getElementById('application-form').addEventListener('submit', handleFormSubmit);
    document.getElementById('btn-clear').addEventListener('click', clearForm);

    const btnDownloadLetter = document.getElementById('btn-download-letter');
    if (btnDownloadLetter) {
        btnDownloadLetter.addEventListener('click', downloadLetterPDF);
    }
});