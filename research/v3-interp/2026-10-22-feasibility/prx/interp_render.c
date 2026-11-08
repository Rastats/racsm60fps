/* InterpRender IR-v2: exploratory render-only interpolation for LEVEL_01 (Pokitaru).
 *
 * Exploratory prototype, not a proposed patch. Loaded as a PSP plugin, it does
 * nothing until the bench (scripts/ir_apply.py) writes ir_cfg and redirects two
 * LEVEL_01 call sites:
 *   0x15230 `jal 0x6B7F4` (group pump 1)        -> jal ir_pump   (delay slot mov.s f12,f20 kept)
 *   0x15AB0 `jal 0x156DC` (render pass)         -> jal ir_render (delay slot nop)
 * plus the C1 core words. Those words vanish when another level is loaded.
 *
 * ir_pump is the G1 gate of tools/runtime/pump-gate.py in C: pump 1 runs every
 * second update with the accumulated delta. Before each run it copies the world
 * matrix (+0x00..+0x3F, rows 0-2 xyz and row 3 xyz) of every active pump-1
 * entity. ir_render, on the frame where the pump ran, writes
 * lerp(previous, current, 0.5) into entities that moved, calls the render pass,
 * then restores the authoritative words. On the other frame it records which
 * entities moved without a pump run (60 Hz-driven: Ratchet's moby and
 * attachments) and never blends them again.
 *
 * Lean pattern of InterpGate IG-v16: no libc, no thread, no imports;
 * module_start returns 0 so the module stays resident. */
#include <pspkernel.h>
#include <stdint.h>

PSP_MODULE_INFO("InterpRender", PSP_MODULE_USER, 0, 1);

#define MAX_ENTRIES 640
#define MAX_RESTORE 160
#define SPAN_SLOTS 2048

typedef void (*PumpFn)(float);
typedef void (*RenderFn)(void);

/* ir_cfg: [0] mode (0 pass-through, 1 gate only, 2 gate + interpolation),
 *         [1] pump 1 address, [2] render address, [3] address of the entity manager pointer,
 *         [4] snap distance squared (float bits). */
volatile uint32_t ir_cfg[8] = {0u, 0u, 0u, 0u, 0x41800000u /* 16.0 = 4 u squared */, 0u, 0u, 0u};
/* ir_stat: [0] runs, [1] skips, [2] blended frames, [3] blended matrices, [4] snapped,
 *          [5] exempted entities, [6] entries in last snapshot, [7] snapshot overflow,
 *          [8] restores, [9] span base, [10] restore overflow. */
volatile uint32_t ir_stat[12];

typedef struct {
    float *m;           /* entity record (world matrix at +0x00) */
    uint32_t hash;      /* authoritative matrix hash at the last pump-frame render */
    float p[12];        /* rows 0-2 xyz, row 3 xyz before the pump ran */
} Entry;

typedef struct {
    float *m;
    float v[12];
} Saved;

static Entry entries[MAX_ENTRIES];
static Saved saved[MAX_RESTORE];
static uint32_t exempt[SPAN_SLOTS / 32];
static uint32_t n_entries, n_saved, phase, ran, span_lo;
static float accum;

static const uint8_t IDX[12] = {0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14};

static uint32_t mhash(const float *m) {
    const uint32_t *w = (const uint32_t *)m;
    uint32_t h = 2166136261u;
    for (int i = 0; i < 12; i++) h = (h ^ w[IDX[i]]) * 16777619u;
    return h;
}

static int slot_of(const float *m) {
    uint32_t a = (uint32_t)(uintptr_t)m;
    if (a < span_lo) return -1;
    a = (a - span_lo) >> 7;
    return a < SPAN_SLOTS ? (int)a : -1;
}

static int is_exempt(const float *m) {
    int s = slot_of(m);
    return s >= 0 && (exempt[s >> 5] >> (s & 31)) & 1u;
}

static void set_exempt(const float *m) {
    int s = slot_of(m);
    if (s >= 0 && !((exempt[s >> 5] >> (s & 31)) & 1u)) {
        exempt[s >> 5] |= 1u << (s & 31);
        ir_stat[5]++;
    }
}

/* Copy the world matrix of every active pump-1 entity (manager layout: tools/bench/entities.py). */
static void snapshot(void) {
    uint32_t mgr = *(volatile uint32_t *)(uintptr_t)ir_cfg[3];
    uint32_t arr = *(uint32_t *)(uintptr_t)(mgr + 0x34), ng = *(uint32_t *)(uintptr_t)(mgr + 0x38);
    uint32_t lo = 0xFFFFFFFFu;
    n_entries = 0;
    for (uint32_t i = 0; i < ng; i++) {
        uint32_t g = arr + i * 0x50;
        uint32_t ents = *(uint32_t *)(uintptr_t)(g + 0x0C), cap = *(uint32_t *)(uintptr_t)(g + 0x3C);
        if (!ents || !cap || cap > 512) continue;
        if (ents < lo) lo = ents;
        for (uint32_t k = 0; k < cap; k++) {
            float *m = (float *)(uintptr_t)(ents + k * 0x80);
            if (!(*(uint32_t *)((char *)m + 0x64) & 1u) || is_exempt(m)) continue;
            if (n_entries >= MAX_ENTRIES) { ir_stat[7]++; goto done; }
            Entry *e = &entries[n_entries++];
            e->m = m;
            e->hash = 0;
            for (int j = 0; j < 12; j++) e->p[j] = m[IDX[j]];
        }
    }
done:
    if (span_lo == 0 && lo != 0xFFFFFFFFu) { span_lo = lo; ir_stat[9] = lo; }
    ir_stat[6] = n_entries;
}

void ir_pump(float dt) {
    PumpFn pump = (PumpFn)(uintptr_t)ir_cfg[1];
    if (!ir_cfg[0]) { pump(dt); return; }
    phase ^= 1u;
    if (phase) { accum = dt; ir_stat[1]++; return; }    /* skipped update: keep its delta */
    dt += accum;
    accum = 0.0f;
    if (ir_cfg[0] == 2) snapshot();
    pump(dt);
    ir_stat[0]++;
    ran = 1;
}

static int finite3(const float *m) {
    for (int j = 12; j < 15; j++)
        if (((*(const uint32_t *)&m[j]) & 0x7F800000u) == 0x7F800000u) return 0;
    return 1;
}

void ir_render(void) {
    RenderFn render = (RenderFn)(uintptr_t)ir_cfg[2];
    if (ir_cfg[0] != 2) { render(); ran = 0; return; }
    if (!ran) {
        for (uint32_t i = 0; i < n_entries; i++)
            if (entries[i].hash && (mhash(entries[i].m) | 1u) != entries[i].hash) set_exempt(entries[i].m);
        render();
        return;
    }
    ran = 0;
    n_saved = 0;
    float snap2;
    *(uint32_t *)&snap2 = ir_cfg[4];
    for (uint32_t i = 0; i < n_entries; i++) {
        Entry *e = &entries[i];
        float *m = e->m;
        e->hash = mhash(m) | 1u;
        if (is_exempt(m) || !(*(uint32_t *)((char *)m + 0x64) & 1u) || !finite3(m)) continue;
        int same = 1;
        for (int j = 0; j < 12; j++) if (m[IDX[j]] != e->p[j]) { same = 0; break; }
        if (same) continue;
        float dx = m[12] - e->p[9], dy = m[13] - e->p[10], dz = m[14] - e->p[11];
        if (dx * dx + dy * dy + dz * dz > snap2) { ir_stat[4]++; continue; }
        if (n_saved >= MAX_RESTORE) { ir_stat[10]++; continue; }
        Saved *s = &saved[n_saved++];
        s->m = m;
        for (int j = 0; j < 12; j++) {
            float c = m[IDX[j]];
            s->v[j] = c;
            m[IDX[j]] = e->p[j] + (c - e->p[j]) * 0.5f;
        }
    }
    if (n_saved) { ir_stat[2]++; ir_stat[3] += n_saved; }
    render();
    for (uint32_t i = 0; i < n_saved; i++)
        for (int j = 0; j < 12; j++) saved[i].m[IDX[j]] = saved[i].v[j];
    ir_stat[8] += n_saved;
}

int module_start(SceSize args, void *argp) { (void)args; (void)argp; return 0; }
int module_stop(SceSize args, void *argp) { (void)args; (void)argp; return 0; }
