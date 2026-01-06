import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Global State
let scene, camera, renderer, controls;
let globalCurve = null;
let maxDepthMD = 0;
let surveyData = [];
let mechanicalData = []; 
let tubeMeshes = [];

// Movement State (Hold-to-Move)
const moveState = {
    up: false,
    down: false,
    left: false,
    right: false,
    zoomIn: false,
    zoomOut: false
};
const CONFIG = {
    tubeScale: 15,
    tubeOpacity: 0.7,
    lightBg: 0xf0f4f8,
    fogDensity: 0.0002,
    panSpeed: 20,
    zoomSpeed: 10
};

// --- Initialization ---
export function initEditor(inSurveyData, inMechData) {
    surveyData = inSurveyData;
    mechanicalData = JSON.parse(JSON.stringify(inMechData || [])); 

    // Normalize Data (Hex Colors)
    mechanicalData.forEach(item => {
        item.color = colorToHex(item.color);
    });

    if (!surveyData || surveyData.length < 2) {
        console.error("Insufficient survey data");
        return;
    }
    maxDepthMD = surveyData[surveyData.length - 1].md;

    // Initialize Slider Range
    const slider = document.getElementById('depth-slider');
    if(slider) {
        slider.max = maxDepthMD;
        slider.value = 0;
    }

    initScene();
    setupLighting();
    setupEnvironment();
    setupWellPath();
    
    rebuildMechanical(mechanicalData);
    renderPanel();
    
    // Setup Controls
    setupControls();

    animate();
}

// Helper: Convert color name to Hex
function colorToHex(color) {
    if (!color) return '#888888';
    if (color.startsWith('#') && color.length >= 7) return color;
    const ctx = document.createElement('canvas').getContext('2d');
    ctx.fillStyle = color;
    return ctx.fillStyle;
}

// --- Scene Setup ---
function initScene() {
    const container = document.getElementById('canvas-container');
    scene = new THREE.Scene();
    scene.background = new THREE.Color(CONFIG.lightBg);
    scene.fog = new THREE.FogExp2(CONFIG.lightBg, CONFIG.fogDensity);

    camera = new THREE.PerspectiveCamera(60, container.clientWidth / container.clientHeight, 0.1, 50000);
    camera.position.set(100, 200, 300);

    renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0, -50, 0);
    controls.enablePan = true;
    
    window.addEventListener('resize', onWindowResize);
}

function setupLighting() {
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);
    const sunLight = new THREE.DirectionalLight(0xffffff, 1.2);
    sunLight.position.set(200, 500, 300);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 2048;
    sunLight.shadow.mapSize.height = 2048;
    scene.add(sunLight);
    const fillLight = new THREE.DirectionalLight(0xe8f4ff, 0.5);
    fillLight.position.set(-200, 100, -200);
    scene.add(fillLight);
}

function setupEnvironment() {
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(3000, 3000), new THREE.MeshStandardMaterial({ color: 0xe0d5c1, roughness: 0.8, side: THREE.FrontSide }));
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const wallMat = new THREE.MeshBasicMaterial({ color: 0xcccccc, transparent: true, opacity: 0.15, side: THREE.DoubleSide });
    const wall1 = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000), wallMat);
    wall1.position.set(0, -1000, -1000);
    scene.add(wall1);
    const wall2 = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000), wallMat);
    wall2.position.set(-1000, -1000, 0);
    wall2.rotation.y = Math.PI / 2;
    scene.add(wall2);

    const grid1 = new THREE.GridHelper(2000, 20, 0x888888, 0xcccccc);
    grid1.rotation.x = Math.PI / 2; grid1.position.set(0, -1000, -1000); scene.add(grid1);
    const grid2 = new THREE.GridHelper(2000, 20, 0x888888, 0xcccccc);
    grid2.rotation.x = Math.PI / 2; grid2.rotation.z = Math.PI / 2; grid2.position.set(-1000, -1000, 0); scene.add(grid2);
    
    createProceduralRig();
}

function createProceduralRig() {
    const rigGroup = new THREE.Group();
    const platform = new THREE.Mesh(new THREE.BoxGeometry(40, 2, 40), new THREE.MeshStandardMaterial({ color: 0x555555 }));
    platform.position.y = 1; platform.receiveShadow = true; rigGroup.add(platform);
    
    const legGeo = new THREE.CylinderGeometry(0.8, 1.5, 60, 4);
    const red = new THREE.MeshStandardMaterial({ color: 0xcc0000 });
    const white = new THREE.MeshStandardMaterial({ color: 0xffffff });
    
    [   {x:5,z:5,m:red, r:[-0.05,0,0.05]}, {x:-5,z:5,m:white, r:[-0.05,0,-0.05]},
        {x:5,z:-5,m:red, r:[0.05,0,0.05]}, {x:-5,z:-5,m:white, r:[0.05,0,-0.05]}
    ].forEach(p => {
        const l = new THREE.Mesh(legGeo, p.m);
        l.position.set(p.x,30,p.z);
        l.rotation.set(...p.r);
        rigGroup.add(l);
    });
    
    const crown = new THREE.Mesh(new THREE.BoxGeometry(6,4,6), new THREE.MeshStandardMaterial({ color: 0xffff00 }));
    crown.position.y = 62; rigGroup.add(crown);
    
    rigGroup.traverse(c => { if(c.isMesh) c.castShadow = true; });
    scene.add(rigGroup);
}

function setupWellPath() {
    const points = surveyData.map(p => new THREE.Vector3(p.east, -p.tvd, p.north));
    if(points.length > 0) {
        globalCurve = new THREE.CatmullRomCurve3(points);
        controls.target.copy(points[0]);
    }
}

function rebuildMechanical(data) {
    tubeMeshes.forEach(mesh => scene.remove(mesh));
    tubeMeshes = [];
    if(!globalCurve) return;

    data.forEach(item => {
        let startT = item.start_md / maxDepthMD;
        let endT = item.end_md / maxDepthMD;
        startT = Math.max(0, Math.min(1, startT));
        endT = Math.max(0, Math.min(1, endT));

        if(startT < endT) {
            // High Precision Sampling: Sample exact points along the curve for this segment
            // This avoids "stepping" issues caused by filtering a fixed set of global points.
            const samples = 100; // High resolution for smooth curves
            const segmentPoints = [];
            for(let i = 0; i <= samples; i++) {
                const t = startT + (endT - startT) * (i / samples);
                segmentPoints.push(globalCurve.getPoint(t));
            }
            
            if(segmentPoints.length > 1) {
                const segmentCurve = new THREE.CatmullRomCurve3(segmentPoints);
                const radius = (item.diameter * 0.0254 / 2) * CONFIG.tubeScale;
                const geo = new THREE.TubeGeometry(segmentCurve, 64, radius, 12, false);
                const mat = new THREE.MeshPhysicalMaterial({
                    color: item.color || 0x888888,
                    metalness: 0.3, roughness: 0.3, clearcoat: 0.8,
                    transparent: true, opacity: CONFIG.tubeOpacity,
                    side: THREE.FrontSide
                });
                const mesh = new THREE.Mesh(geo, mat);
                mesh.castShadow = true;
                scene.add(mesh);
                tubeMeshes.push(mesh);
            }
        }
    });
}

function renderPanel() {
    const container = document.getElementById('editor-rows');
    if(!container) return;
    container.innerHTML = '';

    mechanicalData.forEach((item, index) => {
        const row = document.createElement('div');
        row.className = "flex gap-2 items-end bg-slate-50 p-2 rounded border border-slate-200";
        row.innerHTML = `
            <div class="flex-1 min-w-[60px]">
                <label class="block text-[9px] text-slate-500 uppercase tracking-wide">Tipo</label>
                <input type="text" data-field="type" data-idx="${index}" value="${item.type || ''}" class="w-full text-xs text-slate-900 bg-white border border-slate-300 rounded px-1 py-1 focus:ring-1 focus:ring-indigo-500 outline-none">
            </div>
            <div class="w-14">
                <label class="block text-[9px] text-slate-500 uppercase tracking-wide">OD(")</label>
                <input type="number" step="any" data-field="diameter" data-idx="${index}" value="${item.diameter}" class="w-full text-xs text-slate-900 bg-white border border-slate-300 rounded px-1 py-1 text-center font-mono">
            </div>
            <div class="w-16">
                <label class="block text-[9px] text-slate-500 uppercase tracking-wide">Inicio</label>
                <input type="number" step="any" data-field="start_md" data-idx="${index}" value="${item.start_md}" class="w-full text-xs text-slate-900 bg-white border border-slate-300 rounded px-1 py-1 text-center font-mono">
            </div>
            <div class="w-16">
                <label class="block text-[9px] text-slate-500 uppercase tracking-wide">Fin</label>
                <input type="number" step="any" data-field="end_md" data-idx="${index}" value="${item.end_md}" class="w-full text-xs text-slate-900 bg-white border border-slate-300 rounded px-1 py-1 text-center font-mono">
            </div>
            <div class="w-8">
                <label class="block text-[9px] text-slate-500 uppercase tracking-wide text-center">Col</label>
                <input type="color" data-field="color" data-idx="${index}" value="${item.color}" class="w-full h-6 border-0 rounded cursor-pointer p-0">
            </div>
            <button class="text-slate-400 hover:text-red-500 px-1 transition-colors" onclick="window.removeRow(${index})" title="Eliminar Tramo">
                <i class="fa-solid fa-trash-can text-sm"></i>
            </button>
        `;
        container.appendChild(row);
    });

    container.querySelectorAll('input').forEach(input => {
        input.addEventListener('input', (e) => {
            const idx = parseInt(e.target.dataset.idx);
            const field = e.target.dataset.field;
            let val = e.target.value;
            if(field === 'diameter' || field.includes('md')) val = parseFloat(val) || 0;
            
            mechanicalData[idx][field] = val;
            rebuildMechanical(mechanicalData); 
        });
    });
}

// --- Camera Controls ---
function setupControls() {
    function bindBtn(id, key) {
        const btn = document.getElementById(id);
        if(!btn) return;
        const start = (e) => { e.preventDefault(); moveState[key] = true; };
        const stop = (e) => { e.preventDefault(); moveState[key] = false; };
        
        btn.addEventListener('mousedown', start);
        btn.addEventListener('mouseup', stop);
        btn.addEventListener('mouseleave', stop);
        btn.addEventListener('touchstart', start, {passive: false});
        btn.addEventListener('touchend', stop);
    }
    
    bindBtn('cam-up', 'up');
    bindBtn('cam-down', 'down');
    bindBtn('cam-left', 'left');
    bindBtn('cam-right', 'right');
    bindBtn('cam-zoom-in', 'zoomIn');
    bindBtn('cam-zoom-out', 'zoomOut');
    
    // Quick Views
    document.getElementById('view-top')?.addEventListener('click', () => {
        controls.target.set(0,0,0); camera.position.set(0, 500, 0); camera.lookAt(0,0,0);
    });
    document.getElementById('view-side')?.addEventListener('click', () => {
         controls.target.set(0, -maxDepthMD/2, 0); camera.position.set(500, -maxDepthMD/2, 0);
    });
    document.getElementById('view-reset')?.addEventListener('click', () => {
        controls.reset();
    });
}

function panCamera(dx, dy) {
    // Adaptive Speed: Calculate distance to target
    const distance = camera.position.distanceTo(controls.target);
    // Base speed factor: 20 speed at 1000 units distance. Min speed 0.5 to avoiding getting stuck.
    const speedFactor = Math.max(0.05, distance / 1000); 

    const vRight = new THREE.Vector3(1, 0, 0).applyQuaternion(camera.quaternion);
    const vUp = new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion);
    
    const moveVec = new THREE.Vector3()
       .addScaledVector(vRight, dx * speedFactor)
       .addScaledVector(vUp, dy * speedFactor);
       
    camera.position.add(moveVec);
    controls.target.add(moveVec);
}

function doZoom(dir) {
    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    camera.position.addScaledVector(forward, dir * CONFIG.zoomSpeed);
}

// --- Loop ---
function onWindowResize() {
    if(!camera || !renderer) return;
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
    requestAnimationFrame(animate);
    
    if(moveState.up) panCamera(0, CONFIG.panSpeed);
    if(moveState.down) panCamera(0, -CONFIG.panSpeed);
    if(moveState.left) panCamera(-CONFIG.panSpeed, 0);
    if(moveState.right) panCamera(CONFIG.panSpeed, 0);
    if(moveState.zoomIn) doZoom(1);
    if(moveState.zoomOut) doZoom(-1);

    controls.update();
    renderer.render(scene, camera);
}

// Public API
window.removeRow = (index) => {
    mechanicalData.splice(index, 1);
    renderPanel();
    rebuildMechanical(mechanicalData);
};

window.addNewRow = () => {
    mechanicalData.push({ type: 'Nuevo', diameter: 7, start_md: 0, end_md: 100, color: '#555555' });
    renderPanel();
    rebuildMechanical(mechanicalData);
};

export function setCameraDepth(md) {
    if(!globalCurve) return;
    const t = Math.min(1, Math.max(0, md / maxDepthMD));
    const p = globalCurve.getPoint(t);
    controls.target.copy(p);
    camera.position.set(p.x + 80, p.y + 40, p.z + 80);
    
    // Update label
    const lbl = document.getElementById('depth-val');
    if(lbl) lbl.innerText = Math.round(md);
}
