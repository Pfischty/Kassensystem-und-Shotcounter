
// =========================
// Canvas and Resize Setup
// =========================
const canvas = document.getElementById('backgroundCanvas');
const ctx = canvas.getContext('2d');
let width, height;

function resizeCanvas() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
}
window.addEventListener('resize', () => {
    resizeCanvas();
    createStars(); // Re-create star positions on resize
});
resizeCanvas();

// =========================
// Star Setup
// =========================
const stars = [];
const numStars = 250;

function createStars() {
    stars.length = 0; // Clear existing stars
    for (let i = 0; i < numStars; i++) {
        stars.push({
            x: Math.random() * width,
            y: Math.random() * height,
            radius: Math.random() * 1.5 + 1,
            speed: Math.random() * 0.002, // Adjust for faster/slower star movement
        });
    }
}
createStars();

// =========================
// Meteor & Rocket Setup
// =========================

// We'll store meteorites and rockets in arrays:
const meteors = [];
const rockets = [];

// ----- Random helpers -----

// Return a random integer in [min, max]
function randInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

// Return a random float in [min, max]
function randFloat(min, max) {
    return Math.random() * (max - min) + min;
}

/**
 * Spawns a single meteor (asteroid) at a random edge of the screen,
 * traveling in a random direction.
 */
function spawnMeteor() {
    // Randomly pick which edge: 0=left,1=right,2=top,3=bottom
    const edge = randInt(0, 3);
    let x, y;

    // Speed in pixels per animation frame (approx)
    const speed = randFloat(2, 6);
    // Direction in radians
    let angle = randFloat(0, 2 * Math.PI);

    // Start coordinates depending on the chosen edge
    if (edge === 0) {         // left edge
        x = 0;
        y = randFloat(0, height);
        angle = randFloat(-Math.PI/4, Math.PI/4); // mostly to the right
    } else if (edge === 1) {  // right edge
        x = width;
        y = randFloat(0, height);
        angle = Math.PI + randFloat(-Math.PI/4, Math.PI/4); // mostly to the left
    } else if (edge === 2) {  // top edge
        x = randFloat(0, width);
        y = 0;
        angle = randFloat(Math.PI/4, (3*Math.PI)/4); // mostly downward
    } else {                  // bottom edge
        x = randFloat(0, width);
        y = height;
        angle = randFloat(-(3*Math.PI)/4, -Math.PI/4); // mostly upward
    }

    meteors.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        radius: randFloat(30, 60), // bigger asteroid size
        // Random brownish/gray color; feel free to tweak
        baseColor: `hsl(${randInt(20,40)}, ${randInt(40,60)}%, ${randInt(20,35)}%)`, 
    });
}

/**
 * Spawns a single rocket at a random edge of the screen,
 * traveling in a random direction.
 */
function spawnRocket() {
    // We'll do a similar approach as for the meteor
    const edge = randInt(0, 3);
    let x, y;

    // Speed in pixels per animation frame (approx)
    const speed = randFloat(3, 8);
    let angle = randFloat(0, 2 * Math.PI);

    if (edge === 0) {         // left edge
        x = 0;
        y = randFloat(0, height);
        angle = randFloat(-Math.PI/4, Math.PI/4); 
    } else if (edge === 1) {  // right edge
        x = width;
        y = randFloat(0, height);
        angle = Math.PI + randFloat(-Math.PI/4, Math.PI/4);
    } else if (edge === 2) {  // top edge
        x = randFloat(0, width);
        y = 0;
        angle = randFloat(Math.PI/4, (3*Math.PI)/4);
    } else {                  // bottom edge
        x = randFloat(0, width);
        y = height;
        angle = randFloat(-(3*Math.PI)/4, -Math.PI/4);
    }

    rockets.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        angle,  // Store direction for rocket drawing
        scale: randFloat(0.9, 1.3), // rocket scaling (increased base size)
    });
}

/**
 * Continuously schedule meteor spawns at random intervals.
 * Adjust min/max delays as you wish.
 */
function scheduleMeteorSpawn() {
    setTimeout(() => {
        spawnMeteor();
        scheduleMeteorSpawn();
    }, randInt(1000, 6000)); // spawn every 1-6 seconds
}

/**
 * Continuously schedule rocket spawns at random intervals.
 * Adjust min/max delays as you wish.
 */
function scheduleRocketSpawn() {
    setTimeout(() => {
        spawnRocket();
        scheduleRocketSpawn();
    }, randInt(5000, 15000)); // spawn every 5-15 seconds
}

// Start the scheduling:
scheduleMeteorSpawn();
scheduleRocketSpawn();

// =========================
// Drawing Helpers
// =========================

/**
 * Draw a custom asteroid shape:
 *  1. Irregular outer polygon
 *  2. Gradient fill
 *  3. Optional crater arcs
 */
function drawMeteor(meteor, ctx) {
    const { radius, baseColor } = meteor;

    ctx.save();
    ctx.translate(meteor.x, meteor.y);

    // 1) Create an irregular outer shape
    ctx.beginPath();
    // Increase number of segments for more rugged shapes
    const segments = randInt(7, 12);
    for (let i = 0; i < segments; i++) {
        const angle = (i / segments) * 2 * Math.PI;
        // offset radius with random fluctuations
        const offset = radius + randFloat(-0.2 * radius, 0.2 * radius);
        const px = offset * Math.cos(angle);
        const py = offset * Math.sin(angle);
        if (i === 0) {
            ctx.moveTo(px, py);
        } else {
            ctx.lineTo(px, py);
        }
    }
    ctx.closePath();

    // 2) Fill with a radial gradient
    const grad = ctx.createRadialGradient(0, 0, 5, 0, 0, radius);
    grad.addColorStop(0, lightenColor(baseColor, 30));
    grad.addColorStop(0.8, baseColor);
    grad.addColorStop(1, darkenColor(baseColor, 30));

    ctx.fillStyle = grad;
    ctx.fill();

    // Optional stroke
    ctx.lineWidth = 2;
    ctx.strokeStyle = darkenColor(baseColor, 50);
    ctx.stroke();

    // 3) Draw some small crater arcs on top
    const craterCount = randInt(2, 4); // random number of craters
    for (let c = 0; c < craterCount; c++) {
        const cx = randFloat(-radius * 0.5, radius * 0.5);
        const cy = randFloat(-radius * 0.5, radius * 0.5);
        const cr = randFloat(radius * 0.1, radius * 0.2);
        // only draw crater if it lies somewhat inside our shape
        ctx.beginPath();
        ctx.arc(cx, cy, cr, 0, 2 * Math.PI);
        ctx.fillStyle = darkenColor(baseColor, randInt(20, 40));
        ctx.fill();
    }

    ctx.restore();
}

/**
 * Draw a custom rocket shape (bigger).
 * We'll use the rocket's stored angle to rotate the shape.
 */
function drawRocket(rocket, ctx) {
    ctx.save();
    // Move origin to rocket center
    ctx.translate(rocket.x, rocket.y);
    // Rotate rocket in direction of travel
    ctx.rotate(rocket.angle);
    // Scale rocket for some variety (already stored rocket.scale)
    ctx.scale(rocket.scale, rocket.scale);

    // Increase the rocket body parameters for a bigger rocket
    const rocketLength = 200; 
    const rocketWidth  = 70;

    // ----- Draw Body -----
    ctx.beginPath();
    // Body rectangle (main cylindrical part)
    ctx.rect(-rocketLength * 0.3, -rocketWidth / 2, rocketLength * 0.6, rocketWidth);
    ctx.fillStyle = '#ccc'; // main body color
    ctx.fill();

    // ----- Nose Cone -----
    ctx.beginPath();
    // Nose cone triangle at the front
    ctx.moveTo(rocketLength * 0.3, -rocketWidth / 2);
    ctx.lineTo(rocketLength * 0.3,  rocketWidth / 2);
    ctx.lineTo(rocketLength * 0.5, 0);
    ctx.closePath();
    ctx.fillStyle = '#f33';
    ctx.fill();

    // ----- Fins (one top, one bottom) -----
    ctx.beginPath();
    // Top fin
    ctx.moveTo(-rocketLength * 0.2, -rocketWidth / 2);
    ctx.lineTo(-rocketLength * 0.3, -rocketWidth - 10);
    ctx.lineTo(0, -rocketWidth / 2);
    ctx.closePath();
    ctx.fillStyle = '#444';
    ctx.fill();
    
    ctx.beginPath();
    // Bottom fin
    ctx.moveTo(-rocketLength * 0.2, rocketWidth / 2);
    ctx.lineTo(-rocketLength * 0.3, rocketWidth + 10);
    ctx.lineTo(0, rocketWidth / 2);
    ctx.closePath();
    ctx.fillStyle = '#444';
    ctx.fill();

    // ----- Flame (simple triangles) -----
    // Flicker effect: large flame ~80% of the time
    if (Math.random() < 0.8) {
        ctx.beginPath();
        ctx.moveTo(-rocketLength * 0.3, -10);
        ctx.lineTo(-rocketLength * 0.6, 0);
        ctx.lineTo(-rocketLength * 0.3, 10);
        ctx.closePath();
        ctx.fillStyle = 'orange';
        ctx.fill();

        // smaller flame inside
        ctx.beginPath();
        ctx.moveTo(-rocketLength * 0.3, -7);
        ctx.lineTo(-rocketLength * 0.55, 0);
        ctx.lineTo(-rocketLength * 0.3, 7);
        ctx.closePath();
        ctx.fillStyle = 'yellow';
        ctx.fill();
    } else {
        // short flame ~20% for a flicker effect
        ctx.beginPath();
        ctx.moveTo(-rocketLength * 0.3, -8);
        ctx.lineTo(-rocketLength * 0.45, 0);
        ctx.lineTo(-rocketLength * 0.3, 8);
        ctx.closePath();
        ctx.fillStyle = 'orange';
        ctx.fill();
    }

    ctx.restore();
}

// ====== Color Utilities (for asteroid gradient, etc.) ======
function lightenColor(hslColor, amount) {
    const [h, s, l] = extractHSL(hslColor);
    const newL = Math.min(100, l + amount);
    return `hsl(${h}, ${s}%, ${newL}%)`;
}

function darkenColor(hslColor, amount) {
    const [h, s, l] = extractHSL(hslColor);
    const newL = Math.max(0, l - amount);
    return `hsl(${h}, ${s}%, ${newL}%)`;
}

/** Extract h, s, l components from "hsl(H, S%, L%)" string. */
function extractHSL(hslString) {
    const regex = /hsl\(\s*(\d+),\s*(\d+)%,\s*(\d+)%\)/i;
    const match = hslString.match(regex);
    if (match) {
        return [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
    }
    // Fallback if something goes wrong:
    return [30, 50, 50];
}

// =========================
// Animation Loop
// =========================
function animate() {
    // Clear the entire canvas
    ctx.clearRect(0, 0, width, height);

    // 1) Draw and move stars
    stars.forEach(star => {
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fillStyle = 'white';
        ctx.fill();

        // Move star downward
        star.y += star.speed * 100;
        if (star.y > height) {
            star.y = 0;
            star.x = Math.random() * width;
        }
    });

    
    // 3) Draw and move rockets
    for (let i = rockets.length - 1; i >= 0; i--) {
        const r = rockets[i];
        r.x += r.vx;
        r.y += r.vy;

        drawRocket(r, ctx);

        // Remove rocket if off-screen
        if (r.x < -300 || r.x > width + 300 || r.y < -300 || r.y > height + 300) {
            rockets.splice(i, 1);
        }
    }

    // Request the next frame
    requestAnimationFrame(animate);
}

// Start the animation
animate();