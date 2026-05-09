import * as THREE from './vendor/three/three.module.js';
import { OrbitControls } from './vendor/three/OrbitControls.js';

const ROOM_COLORS = {
    s1: 0xd4a574,
    s2: 0xa8c5dd,
    s3: 0x2d8a5c,
};

// Texture cache to avoid regenerating the same textures
const textureCache = {};

// Procedural texture generation functions
function generateBrickColorMap(w = 512, h = 512) {
    if (textureCache['brick-color']) return textureCache['brick-color'];

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');

    const brickW = w / 8;
    const brickH = h / 10;
    const mortarThickness = 4;

    ctx.fillStyle = '#c47a45';
    ctx.fillRect(0, 0, w, h);

    for (let y = 0; y < 10; y++) {
        const offset = (y % 2) * (brickW / 2);
        for (let x = 0; x < 10; x++) {
            const posX = x * brickW + offset;
            const posY = y * brickH;

            // Vary brick color
            const variation = 0.8 + Math.random() * 0.2;
            const hue = Math.floor(194 * variation);
            ctx.fillStyle = `hsl(20, ${50 + Math.random() * 10}%, ${50 + (variation - 1) * 10}%)`;
            ctx.fillRect(posX, posY, brickW - mortarThickness, brickH - mortarThickness);

            // Highlight on brick
            ctx.fillStyle = 'rgba(255,255,255,0.08)';
            ctx.fillRect(posX + 2, posY + 2, brickW - mortarThickness - 4, 3);
        }
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.magFilter = THREE.LinearFilter;
    texture.minFilter = THREE.LinearMipMapLinearFilter;
    texture.repeat.set(2, 2);
    textureCache['brick-color'] = texture;
    return texture;
}

function generateBrickNormalMap(w = 512, h = 512) {
    if (textureCache['brick-normal']) return textureCache['brick-normal'];

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');

    const brickW = w / 8;
    const brickH = h / 10;
    const mortarThickness = 4;

    // Base normal (facing forward)
    ctx.fillStyle = 'rgb(128, 128, 255)';
    ctx.fillRect(0, 0, w, h);

    for (let y = 0; y < 10; y++) {
        const offset = (y % 2) * (brickW / 2);
        for (let x = 0; x < 10; x++) {
            const posX = x * brickW + offset;
            const posY = y * brickH;

            // Mortar joints (inset)
            ctx.fillStyle = 'rgb(100, 100, 200)';
            // Right edge
            ctx.fillRect(posX + brickW - mortarThickness, posY, mortarThickness, brickH);
            // Bottom edge
            ctx.fillRect(posX, posY + brickH - mortarThickness, brickW, mortarThickness);

            // Highlight (edges curving upward)
            ctx.fillStyle = 'rgb(140, 140, 255)';
            ctx.fillRect(posX + 2, posY + 2, brickW - mortarThickness - 4, 2);
        }
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.magFilter = THREE.LinearFilter;
    texture.minFilter = THREE.LinearMipMapLinearFilter;
    texture.repeat.set(2, 2);
    textureCache['brick-normal'] = texture;
    return texture;
}

function generateRoofTileColorMap(w = 512, h = 512) {
    if (textureCache['roof-tile-color']) return textureCache['roof-tile-color'];

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#6b3d25';
    ctx.fillRect(0, 0, w, h);

    const tileW = w / 6;
    const tileH = h / 8;

    for (let y = 0; y < 10; y++) {
        const offset = (y % 2) * (tileW / 2);
        for (let x = 0; x < 10; x++) {
            const posX = x * tileW + offset;
            const posY = y * tileH;

            // Tile base color with variation
            const variation = 0.9 + Math.random() * 0.15;
            ctx.fillStyle = `hsl(15, 70%, ${35 * variation}%)`;
            ctx.fillRect(posX, posY, tileW - 2, tileH);

            // Shadow at bottom of tile
            ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
            ctx.fillRect(posX, posY + tileH - 3, tileW - 2, 3);

            // Highlight at top
            ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
            ctx.fillRect(posX, posY, tileW - 2, 2);
        }
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.magFilter = THREE.LinearFilter;
    texture.minFilter = THREE.LinearMipMapLinearFilter;
    texture.repeat.set(3, 4);
    textureCache['roof-tile-color'] = texture;
    return texture;
}

function generateRoofTileNormalMap(w = 512, h = 512) {
    if (textureCache['roof-tile-normal']) return textureCache['roof-tile-normal'];

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = 'rgb(128, 128, 255)';
    ctx.fillRect(0, 0, w, h);

    const tileW = w / 6;
    const tileH = h / 8;

    for (let y = 0; y < 10; y++) {
        const offset = (y % 2) * (tileW / 2);
        for (let x = 0; x < 10; x++) {
            const posX = x * tileW + offset;
            const posY = y * tileH;

            // Curved surface (side edges pointing outward)
            for (let i = 0; i < tileW - 2; i++) {
                const intensity = Math.abs((tileW / 2 - i) / (tileW / 2)) * 20;
                const rVal = Math.min(255, 128 + intensity);
                ctx.fillStyle = `rgb(${rVal}, 128, 255)`;
                ctx.fillRect(posX + i, posY, 1, tileH);
            }

            // Shadow at bottom
            ctx.fillStyle = 'rgb(100, 100, 200)';
            ctx.fillRect(posX, posY + tileH - 2, tileW - 2, 2);
        }
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(3, 4);
    textureCache['roof-tile-normal'] = texture;
    return texture;
}

function generateWoodColorMap(w = 512, h = 512) {
    if (textureCache['wood-color']) return textureCache['wood-color'];

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#8b6f47';
    ctx.fillRect(0, 0, w, h);

    // Wood grain lines
    for (let y = 0; y < h; y++) {
        const noise = Math.sin(y * 0.02 + Math.random() * 0.5) * 3 + Math.random() * 2;
        const brightness = 0.8 + Math.random() * 0.15;
        ctx.fillStyle = `hsl(30, 40%, ${50 * brightness}%)`;
        ctx.fillRect(0, y, w, 1);
    }

    // Wood nodes (knots)
    for (let i = 0; i < 8; i++) {
        const x = Math.random() * w;
        const y = Math.random() * h;
        const r = 10 + Math.random() * 15;

        ctx.fillStyle = 'rgba(0, 0, 0, 0.15)';
        ctx.beginPath();
        ctx.ellipse(x, y, r, r * 0.7, Math.random() * Math.PI, 0, Math.PI * 2);
        ctx.fill();
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.magFilter = THREE.LinearFilter;
    texture.minFilter = THREE.LinearMipMapLinearFilter;
    texture.repeat.set(1, 2);
    textureCache['wood-color'] = texture;
    return texture;
}

function generateWoodNormalMap(w = 512, h = 512) {
    if (textureCache['wood-normal']) return textureCache['wood-normal'];

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = 'rgb(128, 128, 255)';
    ctx.fillRect(0, 0, w, h);

    // Subtle wood grain normals
    for (let y = 0; y < h; y += 4) {
        const noise = Math.sin(y * 0.02) * 5;
        ctx.fillStyle = `rgb(${128 + noise}, ${128 - noise * 0.5}, 255)`;
        ctx.fillRect(0, y, w, 4);
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(1, 2);
    textureCache['wood-normal'] = texture;
    return texture;
}

function generateFloorTileColorMap(w = 512, h = 256) {
    if (textureCache['floor-tile-color']) return textureCache['floor-tile-color'];

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');

    const tileSize = w / 6;

    ctx.fillStyle = '#c8a878';
    ctx.fillRect(0, 0, w, h);

    for (let y = 0; y < 4; y++) {
        for (let x = 0; x < 6; x++) {
            const posX = x * tileSize;
            const posY = y * tileSize;

            // Tile color with variation
            const variation = 0.95 + Math.random() * 0.1;
            ctx.fillStyle = `hsl(35, 35%, ${60 * variation}%)`;
            ctx.fillRect(posX, posY, tileSize - 6, tileSize - 6);

            // Grout lines
            ctx.fillStyle = '#9a7a58';
            ctx.fillRect(posX + tileSize - 6, posY, 6, tileSize);
            ctx.fillRect(posX, posY + tileSize - 6, tileSize, 6);
        }
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.magFilter = THREE.LinearFilter;
    texture.minFilter = THREE.LinearMipMapLinearFilter;
    texture.repeat.set(3, 3);
    textureCache['floor-tile-color'] = texture;
    return texture;
}

function generateConcreteColorMap(w = 512, h = 512) {
    if (textureCache['concrete-color']) return textureCache['concrete-color'];

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#a0938a';
    ctx.fillRect(0, 0, w, h);

    // Concrete texture - random speckles
    const imageData = ctx.getImageData(0, 0, w, h);
    const data = imageData.data;

    for (let i = 0; i < data.length; i += 4) {
        const variation = (Math.random() - 0.5) * 0.15;
        const base = 160;
        data[i] = Math.max(0, Math.min(255, base + variation * 255));     // R
        data[i + 1] = Math.max(0, Math.min(255, base - 10 + variation * 255)); // G
        data[i + 2] = Math.max(0, Math.min(255, base - 15 + variation * 255)); // B
        data[i + 3] = 255; // A
    }

    ctx.putImageData(imageData, 0, 0);

    const texture = new THREE.CanvasTexture(canvas);
    texture.magFilter = THREE.LinearFilter;
    texture.minFilter = THREE.LinearMipMapLinearFilter;
    textureCache['concrete-color'] = texture;
    return texture;
}

function generateGrassColorMap(w = 512, h = 512) {
    if (textureCache['grass-color']) return textureCache['grass-color'];

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#4a9d6f';
    ctx.fillRect(0, 0, w, h);

    // Grass variation - lighter and darker spots
    const imageData = ctx.getImageData(0, 0, w, h);
    const data = imageData.data;

    for (let i = 0; i < data.length; i += 4) {
        const variation = (Math.random() - 0.5) * 0.2;
        data[i] = Math.max(0, Math.min(255, 74 + variation * 255));       // R
        data[i + 1] = Math.max(0, Math.min(255, 157 + variation * 255));  // G
        data[i + 2] = Math.max(0, Math.min(255, 111 + variation * 255));  // B
        data[i + 3] = 255; // A
    }

    ctx.putImageData(imageData, 0, 0);

    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.magFilter = THREE.LinearFilter;
    texture.minFilter = THREE.LinearMipMapLinearFilter;
    texture.repeat.set(4, 4);
    textureCache['grass-color'] = texture;
    return texture;
}

let scene;
let camera;
let renderer;
let controls;
let raycaster;
let pointer;
let mountPoint;
let roomMeshes = {};
function createLabelSprite(text) {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 128;

    const context = canvas.getContext('2d');
    if (context) {
        context.fillStyle = 'rgba(255, 255, 255, 0.95)';
        context.strokeStyle = 'rgba(148, 163, 184, 0.9)';
        context.lineWidth = 6;
        context.beginPath();
        if (typeof context.roundRect === 'function') {
            context.roundRect(12, 12, canvas.width - 24, canvas.height - 24, 28);
        } else {
            context.rect(12, 12, canvas.width - 24, canvas.height - 24);
        }
        context.fill();
        context.stroke();

        context.fillStyle = '#1e293b';
        context.font = 'bold 44px sans-serif';
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText(text, canvas.width / 2, canvas.height / 2);
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.anisotropy = 4;

    const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(1.6, 0.4, 1);
    return sprite;
}

function createRoom(width, depth, height, color, id, label, isUpperFloor) {
    const group = new THREE.Group();
    group.userData = { id, baseColor: color };

    const wallMaterial = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        map: generateBrickColorMap(),
        normalMap: generateBrickNormalMap(),
        normalScale: new THREE.Vector2(0.8, 0.8),
        roughness: 0.85,
        metalness: 0.0,
        emissive: 0x000000,
        side: THREE.DoubleSide,
    });

    const floorMaterial = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        map: generateFloorTileColorMap(),
        roughness: 0.6,
        metalness: 0,
    });

    const ceilingMaterial = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        map: generateConcreteColorMap(),
        roughness: 0.5,
        metalness: 0,
    });

    const windowMaterial = new THREE.MeshStandardMaterial({
        color: 0x88c8f0,
        roughness: 0.05,
        metalness: 0.3,
        transparent: true,
        opacity: 0.7,
        side: THREE.DoubleSide,
    });

    const frameMaterial = new THREE.MeshStandardMaterial({
        color: 0x2a2a2a,
        roughness: 0.4,
        metalness: 0.1,
    });

    // Floor
    const floorGeom = new THREE.BoxGeometry(width, 0.05, depth);
    const floor = new THREE.Mesh(floorGeom, floorMaterial);
    floor.position.y = 0;
    floor.castShadow = true;
    floor.receiveShadow = true;
    group.add(floor);

    // Baseboard (rodapié) - decorative trim at base of walls
    const baseboardMaterial = new THREE.MeshStandardMaterial({
        color: 0x6b5344,
        roughness: 0.55,
        metalness: 0.05,
    });

    // Back wall baseboard
    const baseBackGeom = new THREE.BoxGeometry(width, 0.15, 0.08);
    const baseBack = new THREE.Mesh(baseBackGeom, baseboardMaterial);
    baseBack.position.z = -depth / 2;
    baseBack.position.y = 0.075;
    baseBack.castShadow = true;
    group.add(baseBack);

    // Left wall baseboard
    const baseLeftGeom = new THREE.BoxGeometry(0.08, 0.15, depth);
    const baseLeft = new THREE.Mesh(baseLeftGeom, baseboardMaterial);
    baseLeft.position.x = -width / 2;
    baseLeft.position.y = 0.075;
    baseLeft.castShadow = true;
    group.add(baseLeft);

    // Right wall baseboard
    const baseRight = new THREE.Mesh(baseLeftGeom, baseboardMaterial);
    baseRight.position.x = width / 2;
    baseRight.position.y = 0.075;
    baseRight.castShadow = true;
    group.add(baseRight);

    // Window dimensions - defined here for wall segmentation
    const windowWidth = 0.45;
    const windowHeight = 0.55;
    const numWindows = 2;
    const windowSpacing = width / (numWindows + 1);
    const winCenterY = height * 0.55;
    const winBottomY = winCenterY - windowHeight / 2;
    const winTopY   = winCenterY + windowHeight / 2;
    const frameHalfW = (windowWidth + 0.12) / 2;
    const win1X = -width / 2 + windowSpacing;
    const win2X = -width / 2 + windowSpacing * 2;

    // Back wall - segmented around window openings so glass is visible
    const bwZ = -depth / 2;
    // Bottom belt (below windows, full width)
    const bwBotGeom = new THREE.BoxGeometry(width, winBottomY, 0.1);
    const bwBot = new THREE.Mesh(bwBotGeom, wallMaterial);
    bwBot.position.set(0, winBottomY / 2, bwZ);
    bwBot.castShadow = true; bwBot.receiveShadow = true;
    group.add(bwBot);
    // Top belt (above windows, full width)
    const topBeltH = height - winTopY;
    const bwTopGeom = new THREE.BoxGeometry(width, topBeltH, 0.1);
    const bwTop = new THREE.Mesh(bwTopGeom, wallMaterial);
    bwTop.position.set(0, winTopY + topBeltH / 2, bwZ);
    bwTop.castShadow = true; bwTop.receiveShadow = true;
    group.add(bwTop);
    // Left pillar (between left wall and window 1)
    const leftPW = win1X - frameHalfW + width / 2;
    const bwLeftGeom = new THREE.BoxGeometry(leftPW, windowHeight, 0.1);
    const bwLeftPillar = new THREE.Mesh(bwLeftGeom, wallMaterial);
    bwLeftPillar.position.set(-width / 2 + leftPW / 2, winCenterY, bwZ);
    bwLeftPillar.castShadow = true; bwLeftPillar.receiveShadow = true;
    group.add(bwLeftPillar);
    // Middle pillar (between window 1 and window 2)
    const midPW = (win2X - frameHalfW) - (win1X + frameHalfW);
    const bwMidGeom = new THREE.BoxGeometry(midPW, windowHeight, 0.1);
    const bwMidPillar = new THREE.Mesh(bwMidGeom, wallMaterial);
    bwMidPillar.position.set((win1X + win2X) / 2, winCenterY, bwZ);
    bwMidPillar.castShadow = true; bwMidPillar.receiveShadow = true;
    group.add(bwMidPillar);
    // Right pillar (between window 2 and right wall)
    const rightPW = width / 2 - (win2X + frameHalfW);
    const bwRightGeom = new THREE.BoxGeometry(rightPW, windowHeight, 0.1);
    const bwRightPillar = new THREE.Mesh(bwRightGeom, wallMaterial);
    bwRightPillar.position.set(width / 2 - rightPW / 2, winCenterY, bwZ);
    bwRightPillar.castShadow = true; bwRightPillar.receiveShadow = true;
    group.add(bwRightPillar);

    // Left wall
    const leftWallGeom = new THREE.BoxGeometry(0.1, height, depth);
    const leftWall = new THREE.Mesh(leftWallGeom, wallMaterial);
    leftWall.position.x = -width / 2;
    leftWall.position.y = height / 2;
    leftWall.castShadow = true;
    leftWall.receiveShadow = true;
    group.add(leftWall);

    // Right wall
    const rightWall = new THREE.Mesh(leftWallGeom, wallMaterial);
    rightWall.position.x = width / 2;
    rightWall.position.y = height / 2;
    rightWall.castShadow = true;
    rightWall.receiveShadow = true;
    group.add(rightWall);

    // NO FRONT WALL - it's open for isometric view

    // Ceiling with cornice
    const ceilingGeom = new THREE.BoxGeometry(width, 0.08, depth);
    const ceiling = new THREE.Mesh(ceilingGeom, ceilingMaterial);
    ceiling.position.y = height;
    ceiling.castShadow = true;
    ceiling.receiveShadow = true;
    group.add(ceiling);

    // Ceiling cornice (molding under ceiling) - back wall
    const corniceBackGeom = new THREE.BoxGeometry(width + 0.2, 0.12, 0.12);
    const corniceBackMat = new THREE.MeshStandardMaterial({
        color: 0xd4bfaa,
        roughness: 0.45,
        metalness: 0.08,
    });
    const corniceBack = new THREE.Mesh(corniceBackGeom, corniceBackMat);
    corniceBack.position.z = -depth / 2;
    corniceBack.position.y = height - 0.08;
    corniceBack.castShadow = true;
    group.add(corniceBack);

    // Windows on back wall - placed at wall plane, visible through openings
    for (let i = 0; i < numWindows; i++) {
        const xPos = -width / 2 + windowSpacing * (i + 1);
        
        // Outer window frame (dark wood)
        const frameGeom = new THREE.BoxGeometry(windowWidth + 0.12, windowHeight + 0.12, 0.18);
        const frame = new THREE.Mesh(frameGeom, frameMaterial);
        frame.position.set(xPos, height * 0.55, -depth / 2);
        frame.castShadow = true;
        group.add(frame);
        
        // Glass pane with slight blue tint
        const glassGeom = new THREE.BoxGeometry(windowWidth, windowHeight, 0.08);
        const glass = new THREE.Mesh(glassGeom, windowMaterial);
        glass.position.set(xPos, height * 0.55, -depth / 2);
        group.add(glass);
        
        // Window muntins (cross dividers)
        const muntinMaterial = new THREE.MeshStandardMaterial({
            color: 0x2d2d2d,
            roughness: 0.5,
            metalness: 0.2,
        });
        // Vertical muntins
        const vertGeom = new THREE.BoxGeometry(0.02, windowHeight * 0.95, 0.04);
        const vertMuntin = new THREE.Mesh(vertGeom, muntinMaterial);
        vertMuntin.position.set(xPos, height * 0.55, -depth / 2);
        group.add(vertMuntin);
        // Horizontal muntins
        const horizGeom = new THREE.BoxGeometry(windowWidth * 0.95, 0.02, 0.04);
        const horizMuntin = new THREE.Mesh(horizGeom, muntinMaterial);
        horizMuntin.position.set(xPos, height * 0.55, -depth / 2);
        group.add(horizMuntin);

        // Window sill (alféizar)
        const sillGeom = new THREE.BoxGeometry(windowWidth + 0.18, 0.08, 0.15);
        const sillMaterial = new THREE.MeshStandardMaterial({
            color: 0x6b5344,
            roughness: 0.55,
            metalness: 0.05,
        });
        const sill = new THREE.Mesh(sillGeom, sillMaterial);
        sill.position.set(xPos, height * 0.55 - windowHeight / 2 - 0.02, -depth / 2 - 0.06);
        sill.castShadow = true;
        group.add(sill);
    }

    // Small side windows (left and right walls) - positioned in the front face of side walls
    const sideWindowWidth = 0.32;
    const sideWindowHeight = 0.4;

    // Left wall window (on front face of left wall)
    const sideFrameLeftGeom = new THREE.BoxGeometry(0.15, sideWindowHeight + 0.1, sideWindowWidth + 0.1);
    const sideFrameLeft = new THREE.Mesh(sideFrameLeftGeom, frameMaterial);
    sideFrameLeft.position.set(-width / 2 - 0.08, height * 0.65, depth / 4);
    sideFrameLeft.castShadow = true;
    group.add(sideFrameLeft);

    const sideGlassLeftGeom = new THREE.BoxGeometry(0.08, sideWindowHeight, sideWindowWidth);
    const sideGlassLeft = new THREE.Mesh(sideGlassLeftGeom, windowMaterial);
    sideGlassLeft.position.set(-width / 2 - 0.06, height * 0.65, depth / 4);
    group.add(sideGlassLeft);

    // Right wall window (on front face of right wall)
    const sideFrameRightGeom = new THREE.BoxGeometry(0.15, sideWindowHeight + 0.1, sideWindowWidth + 0.1);
    const sideFrameRight = new THREE.Mesh(sideFrameRightGeom, frameMaterial);
    sideFrameRight.position.set(width / 2 + 0.08, height * 0.65, depth / 4);
    sideFrameRight.castShadow = true;
    group.add(sideFrameRight);

    const sideGlassRightGeom = new THREE.BoxGeometry(0.08, sideWindowHeight, sideWindowWidth);
    const sideGlassRight = new THREE.Mesh(sideGlassRightGeom, windowMaterial);
    sideGlassRight.position.set(width / 2 + 0.06, height * 0.65, depth / 4);
    group.add(sideGlassRight);

    // Door (only on lower floor, left side of back wall)
    if (!isUpperFloor) {
        const doorFrameMaterial = new THREE.MeshStandardMaterial({
            color: 0x5a3a2a,
            roughness: 0.55,
            metalness: 0.05,
        });

        const doorKnobMaterial = new THREE.MeshStandardMaterial({
            color: 0xd4af37,
            roughness: 0.2,
            metalness: 0.9,
        });

        // Door centered on back wall near left side, starting from floor
        const doorCenterX = -width / 2 + 0.375;
        const doorCenterY = 0.475; // door spans y=0 to y=0.95

        // Door frame (surrounding box embedded in back wall)
        const doorFrameGeom = new THREE.BoxGeometry(0.77, 1.05, 0.06);
        const doorFrame = new THREE.Mesh(doorFrameGeom, doorFrameMaterial);
        doorFrame.position.set(doorCenterX, doorCenterY, -depth / 2 + 0.02);
        doorFrame.castShadow = true;
        group.add(doorFrame);

        // Door panel (wooden door)
        const doorPanelGeom = new THREE.BoxGeometry(0.65, 0.95, 0.05);
        const doorPanelMat = new THREE.MeshStandardMaterial({
            color: 0xffffff,
            map: generateWoodColorMap(),
            normalMap: generateWoodNormalMap(),
            roughness: 0.55,
            metalness: 0.02,
        });
        const doorPanel = new THREE.Mesh(doorPanelGeom, doorPanelMat);
        doorPanel.position.set(doorCenterX, doorCenterY, -depth / 2 + 0.07);
        doorPanel.castShadow = true;
        group.add(doorPanel);

        // Door knob (brass) on right side of door
        const knobGeom = new THREE.SphereGeometry(0.06, 12, 12);
        const knob = new THREE.Mesh(knobGeom, doorKnobMaterial);
        knob.position.set(doorCenterX + 0.22, doorCenterY, -depth / 2 + 0.11);
        knob.castShadow = true;
        group.add(knob);

        // Door lock plate
        const lockPlateGeom = new THREE.BoxGeometry(0.06, 0.15, 0.02);
        const lockPlateMat = new THREE.MeshStandardMaterial({
            color: 0x9a8a7a,
            roughness: 0.3,
            metalness: 0.7,
        });
        const lockPlate = new THREE.Mesh(lockPlateGeom, lockPlateMat);
        lockPlate.position.set(doorCenterX + 0.22, doorCenterY, -depth / 2 + 0.10);
        group.add(lockPlate);
    }

    // Ceiling light fixture
    const lightFixtureMaterial = new THREE.MeshStandardMaterial({
        color: 0x9a8a7a,
        roughness: 0.35,
        metalness: 0.4,
    });
    const fixtureGeom = new THREE.CylinderGeometry(0.15, 0.15, 0.08, 16);
    const fixture = new THREE.Mesh(fixtureGeom, lightFixtureMaterial);
    fixture.position.set(0, height - 0.1, 0);
    fixture.castShadow = true;
    group.add(fixture);

    // Label sprite (floating at center height for lower floor, adjusted for upper floor)
    const labelSprite = createLabelSprite(label);
    const labelY = isUpperFloor ? height / 2 : height / 2.5;
    labelSprite.position.set(0, labelY, 0.3);
    group.add(labelSprite);

    return group;
}

function createRoof(width, depth) {
    const group = new THREE.Group();

    // Refined roof material with better appearance
    const roofMaterial = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        map: generateRoofTileColorMap(),
        normalMap: generateRoofTileNormalMap(),
        roughness: 0.9,
        metalness: 0.03,
    });

    const overhang = 0.5;
    const pitch = 1.2; // Higher peak
    const roofDepth = depth + overhang * 1.2;
    const roofWidth = width + overhang * 1.6;

    // Left slope from center to left edge
    const leftSlopeVerts = new Float32Array([
        0, pitch, -roofDepth/2,          // peak front
        0, pitch, roofDepth/2,           // peak back
        -roofWidth/2, 0, -roofDepth/2,   // left front bottom
        -roofWidth/2, 0, roofDepth/2,    // left back bottom
    ]);
    
    const leftSlopeIdx = new Uint16Array([0, 2, 1, 1, 2, 3]);
    const leftSlopeGeom = new THREE.BufferGeometry();
    leftSlopeGeom.setAttribute('position', new THREE.BufferAttribute(leftSlopeVerts, 3));
    leftSlopeGeom.setIndex(new THREE.BufferAttribute(leftSlopeIdx, 1));
    leftSlopeGeom.computeVertexNormals();
    
    const leftSlope = new THREE.Mesh(leftSlopeGeom, roofMaterial);
    leftSlope.castShadow = true;
    leftSlope.receiveShadow = true;
    group.add(leftSlope);

    // Right slope (mirror of left)
    const rightSlopeVerts = new Float32Array([
        0, pitch, -roofDepth/2,          // peak front
        0, pitch, roofDepth/2,           // peak back
        roofWidth/2, 0, -roofDepth/2,    // right front bottom
        roofWidth/2, 0, roofDepth/2,     // right back bottom
    ]);
    
    const rightSlopeIdx = new Uint16Array([0, 1, 2, 1, 3, 2]);
    const rightSlopeGeom = new THREE.BufferGeometry();
    rightSlopeGeom.setAttribute('position', new THREE.BufferAttribute(rightSlopeVerts, 3));
    rightSlopeGeom.setIndex(new THREE.BufferAttribute(rightSlopeIdx, 1));
    rightSlopeGeom.computeVertexNormals();
    
    const rightSlope = new THREE.Mesh(rightSlopeGeom, roofMaterial);
    rightSlope.castShadow = true;
    rightSlope.receiveShadow = true;
    group.add(rightSlope);

    // Front gable triangle
    const gableMaterial = new THREE.MeshStandardMaterial({
        color: 0xe8c8b0,
        roughness: 0.55,
        metalness: 0.02,
        side: THREE.DoubleSide,
    });

    const frontGableVerts = new Float32Array([
        -roofWidth/2, 0, -roofDepth/2,
        roofWidth/2, 0, -roofDepth/2,
        0, pitch, -roofDepth/2,
    ]);
    
    const gableIdx = new Uint16Array([0, 1, 2]);
    const frontGableGeom = new THREE.BufferGeometry();
    frontGableGeom.setAttribute('position', new THREE.BufferAttribute(frontGableVerts, 3));
    frontGableGeom.setIndex(new THREE.BufferAttribute(gableIdx, 1));
    frontGableGeom.computeVertexNormals();
    
    const frontGable = new THREE.Mesh(frontGableGeom, gableMaterial);
    frontGable.castShadow = true;
    frontGable.receiveShadow = true;
    group.add(frontGable);

    // Back gable (same as front)
    const backGableVerts = new Float32Array([
        -roofWidth/2, 0, roofDepth/2,
        roofWidth/2, 0, roofDepth/2,
        0, pitch, roofDepth/2,
    ]);
    
    const backGableGeom = new THREE.BufferGeometry();
    backGableGeom.setAttribute('position', new THREE.BufferAttribute(backGableVerts, 3));
    backGableGeom.setIndex(new THREE.BufferAttribute(gableIdx, 1));
    backGableGeom.computeVertexNormals();
    
    const backGable = new THREE.Mesh(backGableGeom, gableMaterial);
    backGable.castShadow = true;
    backGable.receiveShadow = true;
    group.add(backGable);

    // Eaves/soffit
    const eavesMaterial = new THREE.MeshStandardMaterial({
        color: 0x5a3d2a,
        roughness: 0.6,
        metalness: 0.1,
        side: THREE.DoubleSide,
    });

    const eaveDepthGeom = new THREE.BoxGeometry(roofWidth, 0.15, 0.3);
    const eaveFront = new THREE.Mesh(eaveDepthGeom, eavesMaterial);
    eaveFront.position.set(0, -0.08, -roofDepth/2 - 0.15);
    eaveFront.castShadow = true;
    eaveFront.receiveShadow = true;
    group.add(eaveFront);

    const eaveBack = new THREE.Mesh(eaveDepthGeom, eavesMaterial);
    eaveBack.position.set(0, -0.08, roofDepth/2 + 0.15);
    eaveBack.castShadow = true;
    eaveBack.receiveShadow = true;
    group.add(eaveBack);

    // Ridge cap
    const ridgeMaterial = new THREE.MeshStandardMaterial({
        color: 0x5a3535,
        roughness: 0.5,
        metalness: 0.15,
        side: THREE.DoubleSide,
    });
    
    const ridgeGeom = new THREE.BoxGeometry(0.3, 0.15, roofDepth + 0.2);
    const ridge = new THREE.Mesh(ridgeGeom, ridgeMaterial);
    ridge.position.set(0, pitch, 0);
    ridge.castShadow = true;
    ridge.receiveShadow = true;
    group.add(ridge);

    // Chimneys
    const chimneyBrickMaterial = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        map: generateBrickColorMap(),
        normalMap: generateBrickNormalMap(),
        roughness: 0.85,
        metalness: 0.02,
        side: THREE.DoubleSide,
    });

    const chimneyPositions = [-0.6, 0.6];
    
    chimneyPositions.forEach(xPos => {
        const chimneyGeom = new THREE.BoxGeometry(0.32, 1.1, 0.32);
        const chimney = new THREE.Mesh(chimneyGeom, chimneyBrickMaterial);
        chimney.position.set(xPos, 0.95, 0);
        chimney.castShadow = true;
        chimney.receiveShadow = true;
        group.add(chimney);
        
        const potGeom = new THREE.CylinderGeometry(0.12, 0.14, 0.22, 8);
        const potMaterial = new THREE.MeshStandardMaterial({
            color: 0x9a2f1a,
            roughness: 0.8,
            side: THREE.DoubleSide,
        });
        const pot = new THREE.Mesh(potGeom, potMaterial);
        pot.position.set(xPos, 1.61, 0);
        pot.castShadow = true;
        pot.receiveShadow = true;
        group.add(pot);
        
        const capGeom = new THREE.CylinderGeometry(0.14, 0.12, 0.1, 8);
        const capMaterial = new THREE.MeshStandardMaterial({
            color: 0x6a3a3a,
            roughness: 0.6,
            metalness: 0.25,
            side: THREE.DoubleSide,
        });
        const cap = new THREE.Mesh(capGeom, capMaterial);
        cap.position.set(xPos, 1.77, 0);
        cap.castShadow = true;
        cap.receiveShadow = true;
        group.add(cap);
    });

    return group;
}

function updateSelection(id) {
    Object.entries(roomMeshes).forEach(([roomId, mesh]) => {
        const isSelected = roomId === id;
        if (mesh.userData && mesh.userData.baseColor !== undefined) {
            if (isSelected) {
                mesh.userData.originalColor = mesh.userData.originalColor || mesh.userData.baseColor;
                mesh.children.forEach(child => {
                    if (child.material && child.material.emissive !== undefined) {
                        child.material.emissive.setHex(0x1d4ed8);
                    }
                });
            } else {
                mesh.children.forEach(child => {
                    if (child.material && child.material.emissive !== undefined) {
                        child.material.emissive.setHex(0x000000);
                    }
                });
            }
        }
        mesh.scale.setScalar(isSelected ? 1.06 : 1);
    });
}

function handleClick(event) {
    if (!renderer || !camera) return;

    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);

    raycaster.setFromCamera(pointer, camera);
    
    // Raycast against all meshes in the scene
    const allMeshes = [];
    scene.traverse(obj => {
        if (obj.userData && obj.userData.id) {
            allMeshes.push(obj);
        }
    });
    
    const hits = raycaster.intersectObjects(allMeshes, true);
    if (!hits.length) return;

    let selectedId = null;
    for (let hit of hits) {
        if (hit.object.parent && hit.object.parent.userData && hit.object.parent.userData.id) {
            selectedId = hit.object.parent.userData.id;
            break;
        } else if (hit.object.userData && hit.object.userData.id) {
            selectedId = hit.object.userData.id;
            break;
        }
    }

    if (selectedId) {
        updateSelection(selectedId);
        if (typeof window.selectNode === 'function') {
            window.selectNode(selectedId);
        }
    }
}

function onResize() {
    if (!mountPoint || !camera || !renderer) return;

    const width = mountPoint.clientWidth || 1;
    const height = mountPoint.clientHeight || 1;

    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
}

function animate() {
    requestAnimationFrame(animate);
    if (controls) controls.update();
    if (renderer && scene && camera) renderer.render(scene, camera);
}

function showFallback(message) {
    if (!mountPoint) return;

    mountPoint.innerHTML = `
        <div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:1rem;color:#e2e8f0;background:linear-gradient(135deg,#0f172a,#1e293b);padding:2rem;text-align:center;">
            <div style="font-size:1.25rem;font-weight:700;">Vista 3D no disponible</div>
            <div style="max-width:24rem;font-size:0.95rem;line-height:1.5;color:#cbd5e1;">${message}</div>
        </div>
    `;
}

function initScene3D() {
    mountPoint = document.getElementById('scene3d-root');

    if (!mountPoint) return;

    mountPoint.style.position = 'absolute';
    mountPoint.style.inset = '0';
    mountPoint.style.width = '100%';
    mountPoint.style.height = '100%';

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x87CEEB);
    scene.fog = new THREE.Fog(0x87CEEB, 35, 90);

    const width = mountPoint.clientWidth || 360;
    const height = mountPoint.clientHeight || 560;
    const aspect = width / height;

    // Isometric view with orthographic camera
    const frustumSize = 8;
    camera = new THREE.OrthographicCamera(
        frustumSize * aspect / -2,
        frustumSize * aspect / 2,
        frustumSize / 2,
        frustumSize / -2,
        0.1,
        100
    );

    // Isometric angle (45 degrees on horizontal, ~35 degrees on vertical)
    camera.position.set(5, 4, 5);
    camera.lookAt(0, 1.5, 0);

    let webglReady = true;
    try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch (error) {
        webglReady = false;
    }

    if (!webglReady || !renderer) {
        showFallback('El navegador no pudo crear una superficie WebGL. Puedes seguir usando el dashboard y la selección de estancias.');
        return;
    }

    renderer.setSize(width, height, false);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.shadowMap.mapSize.width = 4096;
    renderer.shadowMap.mapSize.height = 4096;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.cursor = 'grab';
    mountPoint.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.minDistance = 4;
    controls.maxDistance = 15;
    controls.minPolarAngle = Math.PI / 4;
    controls.maxPolarAngle = Math.PI / 2.5;
    controls.autoRotate = false;
    controls.target.set(0, 1.5, 0);
    controls.update();

    // Lighting for isometric view - softer and more natural
    const hemisphere = new THREE.HemisphereLight(0x87CEEB, 0x4a7a4a, 0.8);
    scene.add(hemisphere);

    const sun = new THREE.DirectionalLight(0xffe5cc, 1.8);
    sun.position.set(10, 14, 8);
    sun.castShadow = true;
    sun.shadow.mapSize.width = 4096;
    sun.shadow.mapSize.height = 4096;
    sun.shadow.camera.left = -15;
    sun.shadow.camera.right = 15;
    sun.shadow.camera.top = 15;
    sun.shadow.camera.bottom = -5;
    sun.shadow.bias = -0.0005;
    scene.add(sun);

    const fill = new THREE.DirectionalLight(0xa8d5ff, 0.7);
    fill.position.set(-7, 6, -9);
    scene.add(fill);

    // Ground
    const groundMaterial = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        map: generateGrassColorMap(),
        roughness: 0.92,
        metalness: 0,
    });
    const groundGeom = new THREE.PlaneGeometry(20, 20);
    const ground = new THREE.Mesh(groundGeom, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    // Create the house as a single entity
    const houseGroup = new THREE.Group();

    // Lower floor: Salón (ground level)
    const salonRoom = createRoom(2.4, 2.2, 1.8, ROOM_COLORS.s1, 's1', 'Salón', false);
    salonRoom.position.y = 0;
    salonRoom.position.z = -0.5;
    houseGroup.add(salonRoom);

    // Upper floor: Dormitorio (on top of Salón, y = 1.85)
    const dormitorioRoom = createRoom(2.4, 2.2, 1.8, ROOM_COLORS.s2, 's2', 'Dormitorio', true);
    dormitorioRoom.position.y = 1.85;
    dormitorioRoom.position.z = -0.5;
    houseGroup.add(dormitorioRoom);

    // Roof (on top of house, y = 3.7)
    const roof = createRoof(2.4, 2.2);
    roof.position.y = 3.7;
    roof.position.z = -0.5;
    houseGroup.add(roof);

    // Decorative foundation/plinth around house
    const plinthMaterial = new THREE.MeshStandardMaterial({
        color: 0x8a7a6a,
        roughness: 0.75,
        metalness: 0.02,
    });

    // Foundation plinth (base ring around house)
    const plinthGeom = new THREE.BoxGeometry(3.0, 0.2, 2.6);
    const plinth = new THREE.Mesh(plinthGeom, plinthMaterial);
    plinth.position.set(0, -0.1, -0.5);
    plinth.castShadow = true;
    plinth.receiveShadow = true;
    houseGroup.add(plinth);

    // Add house to scene
    scene.add(houseGroup);

    // Garden / Patio INFRONT of the house (positive z)
    const patioMaterial = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        map: generateFloorTileColorMap(),
        roughness: 0.7,
        metalness: 0,
    });
    patioMaterial.map.repeat.set(2, 1);
    const patioGeom = new THREE.BoxGeometry(2.8, 0.2, 1.8);
    const patio = new THREE.Mesh(patioGeom, patioMaterial);
    patio.position.set(0, 0.1, 1.5);
    patio.userData = { id: 's3', baseColor: ROOM_COLORS.s3 };
    patio.castShadow = true;
    patio.receiveShadow = true;
    scene.add(patio);

    // Patio border (stone edge)
    const borderMaterial = new THREE.MeshStandardMaterial({
        color: 0x9a8a7a,
        roughness: 0.8,
        metalness: 0,
    });
    const borderGeom = new THREE.BoxGeometry(3.0, 0.08, 2.0);
    const border = new THREE.Mesh(borderGeom, borderMaterial);
    border.position.set(0, 0.24, 1.5);
    border.castShadow = true;
    border.receiveShadow = true;
    scene.add(border);

    // Grass/garden area around patio
    const grassMaterial = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        map: generateGrassColorMap(),
        roughness: 0.88,
        metalness: 0,
    });
    const grassGeom = new THREE.BoxGeometry(5, 0.05, 3);
    const grass = new THREE.Mesh(grassGeom, grassMaterial);
    grass.position.set(0, 0.02, 1.2);
    grass.receiveShadow = true;
    scene.add(grass);

    // Garden bushes (decorative plants)
    const bushMaterial = new THREE.MeshStandardMaterial({
        color: 0x2d6a3a,
        roughness: 0.7,
        metalness: 0,
    });
    
    const bushPositions = [
        [-1.5, 0.35, 2.2],
        [1.5, 0.35, 2.2],
        [-1.2, 0.35, 2.6],
        [1.2, 0.35, 2.6],
    ];
    
    bushPositions.forEach(pos => {
        // Tree trunk
        const trunkGeom = new THREE.CylinderGeometry(0.08, 0.1, 0.4, 8);
        const trunkMat = new THREE.MeshStandardMaterial({
            color: 0x654321,
            roughness: 0.8,
            metalness: 0,
        });
        const trunk = new THREE.Mesh(trunkGeom, trunkMat);
        trunk.position.set(pos[0], 0.2, pos[2]);
        trunk.castShadow = true;
        trunk.receiveShadow = true;
        scene.add(trunk);

        // Tree foliage (spherical bush)
        const bushGeom = new THREE.SphereGeometry(0.35, 8, 8);
        const bush = new THREE.Mesh(bushGeom, bushMaterial);
        bush.position.set(pos[0], 0.45, pos[2]);
        bush.castShadow = true;
        bush.receiveShadow = true;
        scene.add(bush);
    });

    // Decorative planter boxes
    const planterMaterial = new THREE.MeshStandardMaterial({
        color: 0xa0522d,
        roughness: 0.7,
        metalness: 0,
    });

    const planterPositions = [
        [-1.1, 0.35, 0.8],
        [1.1, 0.35, 0.8],
    ];

    planterPositions.forEach(pos => {
        const planterGeom = new THREE.BoxGeometry(0.25, 0.3, 0.25);
        const planter = new THREE.Mesh(planterGeom, planterMaterial);
        planter.position.set(pos[0], 0.15, pos[2]);
        planter.castShadow = true;
        planter.receiveShadow = true;
        scene.add(planter);

        // Soil/plants in planter
        const soilGeom = new THREE.SphereGeometry(0.12, 6, 6);
        const soilMat = new THREE.MeshStandardMaterial({
            color: 0x4a3728,
            roughness: 0.8,
        });
        const soil = new THREE.Mesh(soilGeom, soilMat);
        soil.position.set(pos[0], 0.32, pos[2]);
        soil.castShadow = true;
        scene.add(soil);
    });

    // Garden fence (simple wooden fence at edge)
    const fenceMaterial = new THREE.MeshStandardMaterial({
        color: 0x8b6f47,
        roughness: 0.7,
        metalness: 0,
    });

    // Left fence
    const fenceLeftGeom = new THREE.BoxGeometry(0.08, 0.6, 2.5);
    const fenceLeft = new THREE.Mesh(fenceLeftGeom, fenceMaterial);
    fenceLeft.position.set(-2.6, 0.3, 1.2);
    fenceLeft.castShadow = true;
    fenceLeft.receiveShadow = true;
    scene.add(fenceLeft);

    // Right fence
    const fenceRight = new THREE.Mesh(fenceLeftGeom, fenceMaterial);
    fenceRight.position.set(2.6, 0.3, 1.2);
    fenceRight.castShadow = true;
    fenceRight.receiveShadow = true;
    scene.add(fenceRight);

    // Wooden garden gate in the fence (left side of patio fence)
    const gateDoorMaterial = new THREE.MeshStandardMaterial({
        color: 0x6b4423,
        roughness: 0.6,
        metalness: 0.02,
    });

    const gateGeom = new THREE.BoxGeometry(0.08, 1.2, 0.9);
    const gate = new THREE.Mesh(gateGeom, gateDoorMaterial);
    gate.position.set(-2.6, 0.6, 1.2);
    gate.castShadow = true;
    gate.receiveShadow = true;
    scene.add(gate);

    // Gate frame
    const gateFrameMaterial = new THREE.MeshStandardMaterial({
        color: 0x4a2f20,
        roughness: 0.7,
        metalness: 0.08,
    });

    const gateFrameGeom = new THREE.BoxGeometry(0.12, 1.35, 1.0);
    const gateFrame = new THREE.Mesh(gateFrameGeom, gateFrameMaterial);
    gateFrame.position.set(-2.6, 0.6, 1.2);
    gateFrame.castShadow = true;
    scene.add(gateFrame);

    // Gate hinge detail (left)
    const hingeGeom = new THREE.CylinderGeometry(0.04, 0.04, 0.15, 8);
    const hingeMaterial = new THREE.MeshStandardMaterial({
        color: 0x8a7a6a,
        roughness: 0.5,
        metalness: 0.6,
        side: THREE.DoubleSide,
    });
    const hingeLeft = new THREE.Mesh(hingeGeom, hingeMaterial);
    hingeLeft.rotation.z = Math.PI / 2;
    hingeLeft.position.set(-2.6, 1.0, 0.75);
    hingeLeft.castShadow = true;
    scene.add(hingeLeft);

    // Gate hinge detail (bottom)
    const hingeBottom = new THREE.Mesh(hingeGeom, hingeMaterial);
    hingeBottom.rotation.z = Math.PI / 2;
    hingeBottom.position.set(-2.6, 0.2, 0.75);
    hingeBottom.castShadow = true;
    scene.add(hingeBottom);

    // Gate handle
    const gateHandleGeom = new THREE.SphereGeometry(0.05, 8, 8);
    const gateHandleMaterial = new THREE.MeshStandardMaterial({
        color: 0xc9a876,
        roughness: 0.3,
        metalness: 0.7,
    });
    const gateHandle = new THREE.Mesh(gateHandleGeom, gateHandleMaterial);
    gateHandle.position.set(-2.56, 0.6, 1.64);
    gateHandle.castShadow = true;
    scene.add(gateHandle);

    // Central patio fountain (decorative feature)
    const fountainBaseMaterial = new THREE.MeshStandardMaterial({
        color: 0x8a7a6a,
        roughness: 0.7,
        metalness: 0.05,
    });

    // Fountain base
    const baseCylinderGeom = new THREE.CylinderGeometry(0.35, 0.4, 0.15, 16);
    const fountainBase = new THREE.Mesh(baseCylinderGeom, fountainBaseMaterial);
    fountainBase.position.set(0, 0.25, 0.8);
    fountainBase.castShadow = true;
    fountainBase.receiveShadow = true;
    scene.add(fountainBase);

    // Fountain middle bowl
    const bowlGeom = new THREE.CylinderGeometry(0.25, 0.28, 0.12, 16);
    const bowlMat = new THREE.MeshStandardMaterial({
        color: 0x9a8a7a,
        roughness: 0.6,
        metalness: 0.1,
    });
    const bowl = new THREE.Mesh(bowlGeom, bowlMat);
    bowl.position.set(0, 0.47, 0.8);
    bowl.castShadow = true;
    bowl.receiveShadow = true;
    scene.add(bowl);

    // Fountain center column
    const columnFountainGeom = new THREE.CylinderGeometry(0.06, 0.08, 0.4, 8);
    const columnFountainMat = new THREE.MeshStandardMaterial({
        color: 0x7a6a5a,
        roughness: 0.7,
        metalness: 0.1,
    });
    const columnFountain = new THREE.Mesh(columnFountainGeom, columnFountainMat);
    columnFountain.position.set(0, 0.58, 0.8);
    columnFountain.castShadow = true;
    columnFountain.receiveShadow = true;
    scene.add(columnFountain);

    // Fountain top ornament
    const ornamentGeom = new THREE.SphereGeometry(0.1, 8, 8);
    const ornamentMat = new THREE.MeshStandardMaterial({
        color: 0xa0a0a0,
        roughness: 0.4,
        metalness: 0.6,
    });
    const ornament = new THREE.Mesh(ornamentGeom, ornamentMat);
    ornament.position.set(0, 0.95, 0.8);
    ornament.castShadow = true;
    ornament.receiveShadow = true;
    scene.add(ornament);

    // Fountain water effect (light blue accent at top)
    const waterGeom = new THREE.CylinderGeometry(0.08, 0.06, 0.08, 8);
    const waterMat = new THREE.MeshStandardMaterial({
        color: 0x87ceeb,
        roughness: 0.2,
        metalness: 0.5,
    });
    const water = new THREE.Mesh(waterGeom, waterMat);
    water.position.set(0, 1.05, 0.8);
    scene.add(water);

    // Add label for garden
    const gardenLabel = createLabelSprite('Jardín');
    gardenLabel.position.set(0, 0.6, 1.5);
    scene.add(gardenLabel);

    // Store references for click detection
    roomMeshes = { 
        s1: salonRoom, 
        s2: dormitorioRoom, 
        s3: patio 
    };

    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();
    renderer.domElement.addEventListener('click', handleClick);
    window.addEventListener('resize', onResize);

    updateSelection('s1');
    animate();
}

window.highlightRoom3D = function highlightRoom3D(id) {
    if (roomMeshes[id]) {
        updateSelection(id);
    }
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initScene3D, { once: true });
} else {
    initScene3D();
}