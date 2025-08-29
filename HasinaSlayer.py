# bd_map_sword_big_upgrade.py — Big Bangladesh map • Sword→Gun upgrade • 10 RABs
# LMB = sword swing (5 uses; breaks into shards, pick new sword) / gun fire (after upgrade)
# RMB = FP/TP • W/S move • A/D turn • R restart • ESC quit
# RABs creep very slowly; each swing/shot makes them hop EXACTLY one step toward you.
# Kill 10 RABs → Gun pickup spawns. Gun has 5 ammo; when empty, one ammo pack spawns.
# NOTE: No gun pickup will spawn while you already have ammo / a gun.

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import math, random, time

# ---------------- window / camera ----------------
W, H = 1300, 980                   # a little larger window
ASPECT, FOVY = W / H, 65.0
first_person = False
tp_orbit_deg = 36.0
tp_height = 720.0                  # raised for larger scene
tp_radius = 1180.0

# FP eye offset (so we don't sit inside the head)
EYE_Z = 148.0                      # +12% higher
FP_EYE_PUSH = 16.0
FP_EYE_UP   = 10.0

# ---------------- Bangladesh polygon (map) ----------------
BD_POLY_BASE = [
    (-300,120),(-280,180),(-260,220),(-230,240),(-190,250),
    (-150,220),(-110,240),(-70,200),(-35,230),(5,200),
    (35,220),(70,185),(105,195),(140,150),(120,115),
    (150,80),(120,20),(85,0),(45,-30),(10,-70),
    (-35,-105),(-45,-150),(-110,-180),(-160,-160),(-200,-120),
    (-242,-75),(-262,-25),(-280,35),(-295,90)
]
MAP_SCALE = 7.5                    # bigger map (was 6.5)
BD_POLY = [(x*MAP_SCALE, y*MAP_SCALE) for (x,y) in BD_POLY_BASE]
MAP_MIN_X = min(x for x,_ in BD_POLY); MAP_MAX_X = max(x for x,_ in BD_POLY)
MAP_MIN_Y = min(y for _,y in BD_POLY); MAP_MAX_Y = max(y for _,y in BD_POLY)
MAP_W = MAP_MAX_X - MAP_MIN_X; MAP_H = MAP_MAX_Y - MAP_MIN_Y
MAP_RADIUS = 0.5*max(MAP_W, MAP_H)

def point_in_poly(x, y, poly=BD_POLY):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i+1) % n]
        if ((y1 > y) != (y2 > y)) and (x < (x2-x1)*(y-y1)/(y2-y1+1e-9) + x1):
            inside = not inside
    return inside

def rand_in_map():
    for _ in range(8192):
        x = random.uniform(MAP_MIN_X, MAP_MAX_X)
        y = random.uniform(MAP_MIN_Y, MAP_MAX_Y)
        if point_in_poly(x, y): return x, y
    return 0.0, 0.0

# ---------------- player ----------------
px, py, yaw_deg = 0.0, 0.0, 0.0
MOVE, TURN = 16.0, 4.5              # a touch faster for the larger map
PLAYER_R = 44.0                     # bigger hit body

def fwd(deg):    a = math.radians(deg); return -math.sin(a), math.cos(a)
def rightv(deg): a = math.radians(deg); return  math.cos(a), math.sin(a)

# ---------------- weapons & pickups ----------------
WEAPON_SWORD = "sword"
WEAPON_GUN   = "gun"
weapon = WEAPON_SWORD

# —— sword / melee
SWORD_SWINGS = 5
sword_uses = SWORD_SWINGS
sword_pick = None                   # {"x","y"} — one pickup total at a time

SWING_TIME = 0.28
SWING_ARC_DEG = 105.0
SWING_RANGE = 220.0                 # bigger melee reach
SWING_COOLDOWN = 0.10
_last_swing_end = 0.0
swing_active = False
swing_t0 = 0.0

# visual break FX after 5th swing
pending_break = False
BREAK_FX_DUR = 0.7
BREAK_SHARDS = 18
GRAVITY_Z = -260.0
break_fx_active = False
break_fx_t0 = 0.0
break_shards = []   # dicts {x,y,z,vx,vy,vz,rot,rv,sx,sy,sz}

# —— gun / bullets (unlocked)
ammo = 0
GUN_AMMO_INIT = 5
AMMO_PACK = 5
bullets = []         # dict: x,y,z,dx,dy,t0
GUN_BULLET_SPEED = 920.0
GUN_BULLET_RADIUS = 10.0
GUN_BULLET_TTL = 2.2
ammo_pick = None     # {"x","y"}
gun_pick  = None     # {"x","y"} after 10 kills
gun_unlocked_once = False
rab_kills_for_upgrade = 0
gun_pending_spawn = False          # if another pickup is out, delay gun spawn

# ---------------- enemies (RABs) ----------------
N_RABS = 10
RAB_R = 40.0
STEP_PER_SWING_RAB = 48.0          # hop distance on swing
STEP_PER_SHOT_RAB  = STEP_PER_SWING_RAB
RAB_SLOW_SPEED = 6.0               # very slow creep (units/sec) when not swinging
rabs = []

# ---------------- Hasina ----------------
has_x, has_y = 200.0*MAP_SCALE/3.2, -120.0*MAP_SCALE/3.2
HAS_R_BODY = 54.0
HAS_R_HEAD = 26.0
STEP_PER_SWING_HAS = 48.0
STEP_PER_SHOT_HAS  = STEP_PER_SWING_HAS
win = False

# ---------------- lives / state ----------------
lives = 5
game_over = False

# ---------------- GLU quadric ----------------
_q = None
def sphere(r): gluSphere(_q, r, 24, 24)
def cone(r,h): gluCylinder(_q, 0.0, r, h, 16, 1)

# ---------------- drawing helpers ----------------
def draw_text(x, y, s, font=GLUT_BITMAP_HELVETICA_18, rgb=(1,1,1)):
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0, W, 0, H)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glColor3f(*rgb); glRasterPos2f(x, y)
    for ch in s: glutBitmapCharacter(font, ord(ch))
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW)

# ---------------- scene ----------------
def draw_map():
    glColor3f(0.14, 0.55, 0.26)
    glBegin(GL_POLYGON)
    for x,y in BD_POLY: glVertex3f(x, y, 0)
    glEnd()

def draw_player():
    glPushMatrix(); glTranslatef(px, py, 0); glRotatef(yaw_deg, 0,0,1)
    # torso (bigger)
    glColor3f(0.2, 0.95, 0.95)
    glPushMatrix(); glTranslatef(0,0,70); glScalef(60,34,138); glutSolidCube(1.0); glPopMatrix()
    # head (ring + ball)
    glPushMatrix(); glTranslatef(0,0,168)
    glColor3f(1.0, 0.85, 0.2); gluDisk(_q, 20.0, 26.0, 28, 1)
    glColor3f(0.1, 0.3, 0.95); sphere(28.0)
    glPopMatrix()
    # floating arrow
    glPushMatrix(); glTranslatef(0,0,228); glColor3f(1,1,1); cone(10.0, 30.0); glPopMatrix()
    glPopMatrix()

def hand_world_pos():
    """Approximate world position of the weapon hand in TP coordinates."""
    fx, fy = fwd(yaw_deg)
    hx = px + 62 * fx
    hy = py + 62 * fy
    hz = 124.0
    return hx, hy, hz

# --------- weapon drawers ----------
def draw_sword():
    """Draw sword – TP on hand; FP overlay near camera. Hidden if broken & not swinging."""
    should_draw = (weapon == WEAPON_SWORD) and (swing_active or (sword_uses > 0))
    if not should_draw: return
    ang = 0.0
    if swing_active:
        t = (time.time() - swing_t0) / SWING_TIME
        ang = -60 + 120*min(max(t,0.0),1.0)

    if first_person:
        fx, fy = fwd(yaw_deg); rx, ry = rightv(yaw_deg)
        gx = px + (FP_EYE_PUSH+12)*fx + 24*rx
        gy = py + (FP_EYE_PUSH+12)*fy + 24*ry
        glPushMatrix(); glTranslatef(gx, gy, EYE_Z + FP_EYE_UP)
        glRotatef(yaw_deg, 0,0,1); glRotatef(ang, 0,0,1)
        glColor3f(0.85,0.85,0.95); glScalef(7, 92, 7); glutSolidCube(1.0)
        glPopMatrix()
    else:
        glPushMatrix(); glTranslatef(px, py, 0); glRotatef(yaw_deg, 0,0,1)
        glTranslatef(0, 62, 124)
        glRotatef(ang, 0,0,1)
        glColor3f(0.85,0.85,0.95); glScalef(14, 112, 14); glutSolidCube(1.0)
        glPopMatrix()

def _draw_pistol_primitive(fp):
    """Tiny pistol model: slide+barrel+grip (boxes), FP overlay or TP in hand."""
    if fp:
        fx, fy = fwd(yaw_deg); rx, ry = rightv(yaw_deg)
        gx = px + (FP_EYE_PUSH+12)*fx + 18*rx
        gy = py + (FP_EYE_PUSH+12)*fy + 18*ry
        glPushMatrix(); glTranslatef(gx, gy, EYE_Z + FP_EYE_UP); glRotatef(yaw_deg, 0,0,1)
        # slide (top)
        glPushMatrix(); glTranslatef(0, 26, 0); glScalef(8, 42, 10); glColor3f(0.2,0.2,0.22); glutSolidCube(1.0); glPopMatrix()
        # barrel front
        glPushMatrix(); glTranslatef(0, 44, 0); glScalef(6, 10, 8); glColor3f(0.35,0.35,0.4); glutSolidCube(1.0); glPopMatrix()
        # grip (angled)
        glPushMatrix(); glTranslatef(-8, 16, -2); glRotatef(-24, 0,0,1); glScalef(10, 22, 8); glColor3f(0.1,0.1,0.12); glutSolidCube(1.0); glPopMatrix()
        glPopMatrix()
    else:
        glPushMatrix(); glTranslatef(px, py, 0); glRotatef(yaw_deg, 0,0,1); glTranslatef(0, 62, 124)
        # slide
        glPushMatrix(); glTranslatef(0, 30, 0); glScalef(14, 52, 16); glColor3f(0.2,0.2,0.22); glutSolidCube(1.0); glPopMatrix()
        # barrel
        glPushMatrix(); glTranslatef(0, 58, 0); glScalef(10, 14, 12); glColor3f(0.35,0.35,0.4); glutSolidCube(1.0); glPopMatrix()
        # grip
        glPushMatrix(); glTranslatef(-10, 22, -2); glRotatef(-24, 0,0,1); glScalef(16, 28, 12); glColor3f(0.1,0.1,0.12); glutSolidCube(1.0); glPopMatrix()
        glPopMatrix()

def draw_gun():
    if weapon != WEAPON_GUN: return
    _draw_pistol_primitive(first_person)

def draw_break_fx():
    if not break_fx_active: return
    glColor3f(0.9,0.9,1.0)
    for s in break_shards:
        glPushMatrix()
        glTranslatef(s["x"], s["y"], s["z"])
        glRotatef(s["rot"], 0,0,1)
        glScalef(s["sx"], s["sy"], s["sz"])
        glutSolidCube(1.0)
        glPopMatrix()

def draw_rab(e):
    glPushMatrix(); glTranslatef(e["x"], e["y"], 0)
    glColor3f(0,0,0)
    glPushMatrix(); glTranslatef(0,0,RAB_R); sphere(RAB_R); glPopMatrix()
    glPushMatrix(); glTranslatef(0,0,RAB_R*2 + 5); sphere(RAB_R*0.7); glPopMatrix()
    glColor3f(0.35, 0.08, 0.08)
    glPushMatrix(); glTranslatef(-12,8,RAB_R*2 + 22); glRotatef(-18,1,0,0); cone(6.0, 18); glPopMatrix()
    glPushMatrix(); glTranslatef( 12,8,RAB_R*2 + 22); glRotatef(-18,1,0,0); cone(6.0, 18); glPopMatrix()
    glPopMatrix()

def draw_hasina():
    if win: return
    glPushMatrix(); glTranslatef(has_x, has_y, 0)
    glColor3f(1,1,1); glPushMatrix(); glTranslatef(0,0,HAS_R_BODY); sphere(HAS_R_BODY); glPopMatrix()
    glColor3f(1,1,1); glPushMatrix(); glTranslatef(0,0,HAS_R_BODY*2 + 6); sphere(HAS_R_HEAD); glPopMatrix()
    glPopMatrix()

# --------- bullets (visible) ----------
def draw_bullets():
    if not bullets: return
    glColor3f(1.0, 0.9, 0.2)
    for b in bullets:
        glPushMatrix()
        glTranslatef(b["x"], b["y"], b["z"])
        glutSolidSphere(GUN_BULLET_RADIUS, 12, 12)
        glPopMatrix()

# --------- pickups ----------
def pickup_busy():
    return (sword_pick is not None) or (ammo_pick is not None) or (gun_pick is not None)

def draw_sword_pickup():
    if sword_pick is None: return
    t = glutGet(GLUT_ELAPSED_TIME)/1000.0
    glPushMatrix()
    glTranslatef(sword_pick["x"], sword_pick["y"], 20.0)
    glRotatef((t*90.0)%360.0, 0,0,1)
    glColor3f(0.1, 0.9, 0.3); glScalef(30,30,12); glutSolidCube(1.0); glScalef(1/30,1/30,1/12)
    glColor3f(0.95,0.95,1.0); glScalef(9, 160, 9); glutSolidCube(1.0)
    glPopMatrix()

def _draw_pistol_geometry_local():
    """Same pistol geometry as in-hand, drawn at local origin (facing +Y)."""
    # slide
    glPushMatrix(); glTranslatef(0, 30, 0); glScalef(14, 52, 16); glColor3f(0.2,0.2,0.22); glutSolidCube(1.0); glPopMatrix()
    # barrel
    glPushMatrix(); glTranslatef(0, 58, 0); glScalef(10, 14, 12); glColor3f(0.35,0.35,0.4); glutSolidCube(1.0); glPopMatrix()
    # grip
    glPushMatrix(); glTranslatef(-10, 22, -2); glRotatef(-24, 0,0,1); glScalef(16, 28, 12); glColor3f(0.1,0.1,0.12); glutSolidCube(1.0); glPopMatrix()

def draw_ammo_pickup():
    if ammo_pick is None: return
    t = glutGet(GLUT_ELAPSED_TIME)/1000.0
    glPushMatrix()
    glTranslatef(ammo_pick["x"], ammo_pick["y"], 22.0)
    glRotatef((t*120.0)%360.0, 0,0,1)
    glColor3f(0.2, 1.0, 0.4); glScalef(34,34,16); glutSolidCube(1.0)
    glPopMatrix()

def draw_gun_pickup():
    if gun_pick is None: return
    t = glutGet(GLUT_ELAPSED_TIME)/1000.0
    glPushMatrix()
    glTranslatef(gun_pick["x"], gun_pick["y"], 26.0)
    # pedestal glow
    glPushMatrix(); glScalef(26,26,12); glColor3f(0.15, 0.6, 0.95); glutSolidCube(1.0); glPopMatrix()
    # spin the actual pistol so it looks like the in-hand gun
    glRotatef((t*60.0)%360.0, 0,0,1)
    _draw_pistol_geometry_local()
    glPopMatrix()

# ---------------- camera ----------------
def setup_camera():
    glMatrixMode(GL_PROJECTION); glLoadIdentity(); gluPerspective(FOVY, ASPECT, 0.3, 9000.0)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()

    fx, fy = fwd(yaw_deg)
    if first_person:
        eye_x = px + FP_EYE_PUSH*fx
        eye_y = py + FP_EYE_PUSH*fy
        eye_z = EYE_Z + FP_EYE_UP
        gluLookAt(eye_x, eye_y, eye_z, eye_x + 60*fx, eye_y + 60*fy, eye_z, 0, 0, 1)
    else:
        ang = math.radians(tp_orbit_deg)
        cx = px + tp_radius*math.cos(ang)
        cy = py + tp_radius*math.sin(ang)
        gluLookAt(cx, cy, tp_height, px, py, 60, 0, 0, 1)

def retune_camera_for_map():
    global tp_radius, tp_height
    tp_radius = MAP_RADIUS * 2.3
    tp_height = MAP_RADIUS * 1.12

# ---------------- mechanics ----------------
def spawn_rab():
    x, y = rand_in_map()
    rabs.append({"x": x, "y": y, "phase": random.random()*6.283})

def ensure_rab_count():
    while len(rabs) < N_RABS: spawn_rab()

def per_swing_steps():
    # RABs hop one step; Hasina hops away one step.
    for e in rabs:
        dx, dy = px - e["x"], py - e["y"]
        d = max(1e-6, math.hypot(dx, dy))
        nx, ny = e["x"] + STEP_PER_SWING_RAB*dx/d, e["y"] + STEP_PER_SWING_RAB*dy/d
        if point_in_poly(nx, ny): e["x"], e["y"] = nx, ny
    global has_x, has_y
    dx, dy = has_x - px, has_y - py
    d = max(1e-6, math.hypot(dx, dy))
    nx, ny = has_x + STEP_PER_SWING_HAS*dx/d, has_y + STEP_PER_SWING_HAS*dy/d
    if point_in_poly(nx, ny): has_x, has_y = nx, ny

def per_shot_steps():
    # Same hop on gun shot
    for e in rabs:
        dx, dy = px - e["x"], py - e["y"]
        d = max(1e-6, math.hypot(dx, dy))
        nx, ny = e["x"] + STEP_PER_SHOT_RAB*dx/d, e["y"] + STEP_PER_SHOT_RAB*dy/d
        if point_in_poly(nx, ny): e["x"], e["y"] = nx, ny
    global has_x, has_y
    dx, dy = has_x - px, has_y - py
    d = max(1e-6, math.hypot(dx, dy))
    nx, ny = has_x + STEP_PER_SHOT_HAS*dx/d, has_y + STEP_PER_SHOT_HAS*dy/d
    if point_in_poly(nx, ny): has_x, has_y = nx, ny

def trigger_break_fx():
    """Spawn shard particles at the sword hand and start break animation."""
    global break_fx_active, break_fx_t0, break_shards
    hx, hy, hz = hand_world_pos()
    break_shards = []
    for _ in range(BREAK_SHARDS):
        ang = math.radians(yaw_deg + random.uniform(-70, 70))
        spd = random.uniform(200, 340)
        vx, vy = spd * math.cos(ang), spd * math.sin(ang)
        vz = random.uniform(160, 280)
        shard = {
            "x": hx, "y": hy, "z": hz,
            "vx": vx, "vy": vy, "vz": vz,
            "rot": random.uniform(0,360), "rv": random.uniform(-360,360),
            "sx": random.uniform(7,14), "sy": random.uniform(12,24), "sz": random.uniform(5,10)
        }
        break_shards.append(shard)
    break_fx_active = True
    break_fx_t0 = time.time()

def begin_swing():
    global swing_active, swing_t0, sword_uses, _last_swing_end, pending_break
    if weapon != WEAPON_SWORD: return
    if game_over or win or swing_active: return
    if sword_uses <= 0: return
    if time.time() - _last_swing_end < SWING_COOLDOWN: return
    swing_active = True
    swing_t0 = time.time()
    sword_uses -= 1
    if sword_uses == 0:
        pending_break = True
        if not pickup_busy():
            spawn_sword_pick()
    per_swing_steps()

def end_swing():
    global swing_active, _last_swing_end, pending_break
    swing_active = False
    _last_swing_end = time.time()
    if pending_break:
        trigger_break_fx()
        pending_break = False

def spawn_sword_pick():
    global sword_pick
    if not pickup_busy():
        x, y = rand_in_map(); sword_pick = {"x": x, "y": y}

def spawn_gun_pick():
    """Spawn gun upgrade ONLY if you don't already have a gun/ammo and no other pickup is active."""
    global gun_pick, gun_pending_spawn
    # --- guards to satisfy "no guns spawn while I already have ammo" ---
    if weapon == WEAPON_GUN or ammo > 0 or gun_unlocked_once:
        gun_pending_spawn = False
        return
    if not pickup_busy():
        x, y = rand_in_map(); gun_pick = {"x": x, "y": y}
        gun_pending_spawn = False
    else:
        gun_pending_spawn = True

def spawn_ammo_pick():
    global ammo_pick
    if not pickup_busy():
        x, y = rand_in_map(); ammo_pick = {"x": x, "y": y}

def muzzle(fp):
    """Compute muzzle (for gun) based on FP/TP."""
    if fp:
        fx, fy = fwd(yaw_deg); rx, ry = rightv(yaw_deg)
        gx = px + 24*fx + 10*rx; gy = py + 24*fy + 10*ry
        mx = gx + 30*fx; my = gy + 30*fy; mz = 88.0
        return mx, my, mz, fx, fy
    else:
        fx, fy = fwd(yaw_deg)
        mx = px + 62*fx; my = py + 62*fy; mz = 84.0
        return mx, my, mz, fx, fy

def shoot_gun():
    global ammo
    if weapon != WEAPON_GUN: return
    if game_over or win or ammo <= 0: return
    mx, my, mz, fx, fy = muzzle(first_person)
    bullets.append({"x": mx, "y": my, "z": mz, "dx": fx, "dy": fy, "t0": time.time()})
    ammo -= 1
    per_shot_steps()
    if ammo == 0 and not pickup_busy():
        spawn_ammo_pick()

def reset_world():
    global px, py, yaw_deg, rabs, has_x, has_y, sword_uses
    global lives, game_over, win, first_person, tp_orbit_deg
    global break_fx_active, break_shards, pending_break
    global weapon, ammo, bullets, ammo_pick, gun_pick, gun_unlocked_once, rab_kills_for_upgrade, gun_pending_spawn
    global sword_pick
    px, py, yaw_deg = 0.0, 0.0, 0.0
    rabs = []; ensure_rab_count()
    has_x, has_y = rand_in_map()
    sword_uses = SWORD_SWINGS; sword_pick = None
    weapon = WEAPON_SWORD
    ammo = 0; bullets = []; ammo_pick = None; gun_pick = None
    gun_unlocked_once = False; rab_kills_for_upgrade = 0; gun_pending_spawn = False
    lives = 5; game_over = False; win = False
    first_person = False; tp_orbit_deg = 36.0
    break_fx_active = False; break_shards = []; pending_break = False
    retune_camera_for_map()

# ---------------- input ----------------
def key_normal(k, *_):
    global px, py, yaw_deg
    if k == b'\x1b': glutLeaveMainLoop(); return
    if k == b'r': reset_world(); return
    if game_over or win: return
    if k in (b'w', b's'):
        fx, fy = fwd(yaw_deg); s = MOVE if k == b'w' else -MOVE
        nx, ny = px + s*fx, py + s*fy
        if point_in_poly(nx, ny): px, py = nx, ny
    if k == b'a': yaw_deg = (yaw_deg + TURN) % 360.0
    if k == b'd': yaw_deg = (yaw_deg - TURN) % 360.0

def key_special(k, *_):
    global tp_orbit_deg, tp_height
    if first_person: return
    if k == GLUT_KEY_LEFT:  tp_orbit_deg -= 2.0
    if k == GLUT_KEY_RIGHT: tp_orbit_deg += 2.0
    if k == GLUT_KEY_UP:    tp_height += 18.0
    if k == GLUT_KEY_DOWN:  tp_height = max(80.0, tp_height - 18.0)

def mouse(btn, state, *_):
    global first_person
    if btn == GLUT_LEFT_BUTTON  and state == GLUT_DOWN:
        if weapon == WEAPON_SWORD: begin_swing()
        else:                      shoot_gun()
    if btn == GLUT_RIGHT_BUTTON and state == GLUT_DOWN: first_person = not first_person

# ---------------- helpers ----------------
def within_arc_and_range(tx, ty):
    fx, fy = fwd(yaw_deg)
    vx, vy = tx - px, ty - py
    d = math.hypot(vx, vy)
    if d > SWING_RANGE: return False
    cos_th = (fx*vx + fy*vy) / (d + 1e-9)
    return cos_th >= math.cos(math.radians(SWING_ARC_DEG * 0.5))

# ---------------- update ----------------
def update(dt):
    global lives, game_over, win, sword_pick, ammo_pick, gun_pick
    global rab_kills_for_upgrade, gun_unlocked_once
    global weapon, ammo, bullets, sword_uses, gun_pending_spawn
    global break_fx_active, break_shards, break_fx_t0

    # finish swing timing
    if swing_active and (time.time() - swing_t0 >= SWING_TIME):
        end_swing()

    if not (game_over or win):
        # VERY SLOW continuous creep toward player when not swinging
        if RAB_SLOW_SPEED > 0.0:
            for e in rabs:
                dx, dy = px - e["x"], py - e["y"]
                d = max(1e-6, math.hypot(dx, dy))
                step = RAB_SLOW_SPEED * dt
                nx, ny = e["x"] + step*dx/d, e["y"] + step*dy/d
                if point_in_poly(nx, ny): e["x"], e["y"] = nx, ny

        # --- sword damage window ---
        if swing_active and weapon == WEAPON_SWORD:
            survivors = []
            for e in rabs:
                if within_arc_and_range(e["x"], e["y"]):
                    rab_kills_for_upgrade += 1
                    continue
                survivors.append(e)
            rabs[:] = survivors
            ensure_rab_count()
            if within_arc_and_range(has_x, has_y):
                win = True

        # --- bullets update + damage ---
        if weapon == WEAPON_GUN and bullets:
            now = time.time()
            keep = []
            for b in bullets:
                b["x"] += b["dx"] * GUN_BULLET_SPEED * dt
                b["y"] += b["dy"] * GUN_BULLET_SPEED * dt
                if now - b["t0"] > GUN_BULLET_TTL: continue
                keep.append(b)
            bullets[:] = keep

            # bullet vs RAB
            survivors = []
            for e in rabs:
                killed = False
                for b in bullets:
                    if (e["x"]-b["x"])**2 + (e["y"]-b["y"])**2 <= (RAB_R + GUN_BULLET_RADIUS)**2:
                        b["t0"] = -999.0; killed = True; rab_kills_for_upgrade += 1; break
                if not killed: survivors.append(e)
            rabs[:] = survivors; ensure_rab_count()
            bullets[:] = [b for b in bullets if b["t0"] > 0]

            # bullet vs Hasina -> win
            for b in bullets:
                if (has_x - b["x"])**2 + (has_y - b["y"])**2 <= (HAS_R_BODY + GUN_BULLET_RADIUS)**2:
                    win = True; bullets.clear(); break

        # RAB contact with player
        for i, e in enumerate(list(rabs)):
            if (e["x"]-px)**2 + (e["y"]-py)**2 <= (RAB_R + PLAYER_R)**2:
                lives -= 1
                rabs[i]["x"], rabs[i]["y"] = rand_in_map()
                if lives <= 0: game_over = True
                break

        # --- spawn upgrade gun when 10 kills reached (and only if no ammo/gun) ---
        if (not gun_unlocked_once) and (weapon == WEAPON_SWORD) and rab_kills_for_upgrade >= 10 and ammo == 0:
            spawn_gun_pick()

        # --- pick up logic (only one pickup active at a time) ---
        if sword_pick is not None:
            if (sword_pick["x"]-px)**2 + (sword_pick["y"]-py)**2 <= (PLAYER_R + 22)**2 and weapon == WEAPON_SWORD:
                sword_pick = None
                sword_uses = SWORD_SWINGS

        if gun_pick is not None:
            # extra safety: if you somehow have ammo already, remove stray gun pickup
            if weapon == WEAPON_GUN or ammo > 0:
                gun_pick = None
            elif (gun_pick["x"]-px)**2 + (gun_pick["y"]-py)**2 <= (PLAYER_R + 22)**2:
                gun_pick = None
                gun_unlocked_once = True
                weapon = WEAPON_GUN
                ammo = GUN_AMMO_INIT

        if ammo_pick is not None and weapon == WEAPON_GUN:
            if (ammo_pick["x"]-px)**2 + (ammo_pick["y"]-py)**2 <= (PLAYER_R + 22)**2:
                ammo_pick = None
                ammo += AMMO_PACK

        # delayed gun spawn if another pickup was blocking it (but only if no ammo/gun)
        if gun_pending_spawn and not pickup_busy() and weapon == WEAPON_SWORD and ammo == 0 and not gun_unlocked_once:
            spawn_gun_pick()

    # ---- update sword-break particle FX ----
    if break_fx_active:
        t = time.time() - break_fx_t0
        if t > BREAK_FX_DUR:
            break_fx_active = False
            break_shards.clear()
        else:
            for s in break_shards:
                s["x"] += s["vx"] * dt
                s["y"] += s["vy"] * dt
                s["z"] += s["vz"] * dt
                s["vz"] += GRAVITY_Z * dt
                s["rot"] += s["rv"] * dt

# ---------------- HUD ----------------
def hud():
    mode = "FIRST PERSON" if first_person else "THIRD PERSON"
    if weapon == WEAPON_SWORD:
        draw_text(16, H-40, f"Sword uses: {sword_uses}   Kills: {rab_kills_for_upgrade}   Lives: {lives}")
    else:
        draw_text(16, H-40, f"Ammo: {ammo}   Kills: {rab_kills_for_upgrade}   Lives: {lives}")
    draw_text(W-240, H-40, mode, GLUT_BITMAP_HELVETICA_18, (0.9,0.95,1))
    if gun_pick is not None:
        draw_text(16, 20, "UPGRADE READY → Pick up the GUN!", GLUT_BITMAP_HELVETICA_18, (1.0,0.9,0.4))
    elif sword_pick is not None:
        draw_text(16, 20, "New sword spawned: pick it up (+5)", GLUT_BITMAP_HELVETICA_18, (0.6,1,0.7))
    elif ammo_pick is not None:
        draw_text(16, 20, "Ammo pack spawned: +5 bullets", GLUT_BITMAP_HELVETICA_18, (0.6,1,0.7))
    if game_over:
        draw_text(W//2-60, H//2+12, "GAME OVER", GLUT_BITMAP_HELVETICA_18, (1,0.4,0.4))
        draw_text(W//2-150, H//2-12, "Press R to restart", GLUT_BITMAP_HELVETICA_18, (1,0.8,0.8))
    if win:
        draw_text(W//2-40, H//2+12, "YOU WIN!", GLUT_BITMAP_HELVETICA_18, (1,1,0.2))
        draw_text(W//2-150, H//2-12, "Press R to restart", GLUT_BITMAP_HELVETICA_18, (1,1,0.7))

# ---------------- GLUT display ----------------
_tprev = time.time()
def display():
    global _tprev
    t = time.time(); dt = t - _tprev; _tprev = t
    update(dt)

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glViewport(0, 0, W, H)
    setup_camera()

    draw_map()
    draw_sword_pickup()
    draw_gun_pickup()
    draw_ammo_pickup()
    for e in rabs: draw_rab(e)
    draw_hasina()
    if not first_person:
        draw_player()
    draw_sword()
    draw_gun()
    draw_bullets()                 # visible bullets
    draw_break_fx()
    hud()

    glutSwapBuffers()
    glutPostRedisplay()

# ---------------- main ----------------
def main():
    global _q, px, py, has_x, has_y
    random.seed()
    if not point_in_poly(px, py): px, py = rand_in_map()
    if not point_in_poly(has_x, has_y): has_x, has_y = rand_in_map()
    ensure_rab_count()
    retune_camera_for_map()

    glutInit(); glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(W, H); glutInitWindowPosition(60, 40)
    glutCreateWindow(b"BD Map: Sword->Gun Upgrade - 10 RABs, Slow Creep + Step Hop (Bigger)")
    glEnable(GL_DEPTH_TEST); glClearColor(0.04, 0.06, 0.09, 1.0)
    _q = gluNewQuadric()

    glutDisplayFunc(display)
    glutKeyboardFunc(key_normal)
    glutSpecialFunc(key_special)
    glutMouseFunc(mouse)
    glutMainLoop()

if __name__ == "__main__":
    from OpenGL.GLUT import GLUT_BITMAP_HELVETICA_18
    main()
