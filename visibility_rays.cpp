// Count first-hit rays per triangle from a set of viewpoints.
// usage: visibility_rays triangles.bin points.bin rays_per_point hits.bin [occluders.bin]
// occluders.bin: uint8 [N]; 0 = see-through (never blocks a ray, still counted when reached)
// triangles.bin: float32 [N][3][3]; points.bin: float32 [M][3]; hits.bin: uint32 [N]
// Rays follow a Fibonacci sphere, rotated per point so directions interleave.
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <thread>
#include <vector>
#include <cstring>
#include <string>
#include <random>

struct V { float x, y, z; };
static V sub(V a, V b) { return {a.x-b.x, a.y-b.y, a.z-b.z}; }
static V cross(V a, V b) { return {a.y*b.z-a.z*b.y, a.z*b.x-a.x*b.z, a.x*b.y-a.y*b.x}; }
static float dot(V a, V b) { return a.x*b.x+a.y*b.y+a.z*b.z; }

struct Node { float lo[3], hi[3]; int left, count; };  // count>0: leaf with first=left
static std::vector<V> tri;            // 3 per triangle
static std::vector<int> order;
static std::vector<Node> nodes;
static std::vector<uint8_t> occ;

static int build(int first, int count, std::vector<V>& c) {
    Node n; for (int k = 0; k < 3; k++) { n.lo[k] = 1e30f; n.hi[k] = -1e30f; }
    float clo[3] = {1e30f, 1e30f, 1e30f}, chi[3] = {-1e30f, -1e30f, -1e30f};
    for (int i = first; i < first+count; i++) {
        int t = order[i];
        for (int j = 0; j < 3; j++) {
            const float* p = &tri[t*3+j].x;
            for (int k = 0; k < 3; k++) { n.lo[k] = std::min(n.lo[k], p[k]); n.hi[k] = std::max(n.hi[k], p[k]); }
        }
        const float* q = &c[t].x;
        for (int k = 0; k < 3; k++) { clo[k] = std::min(clo[k], q[k]); chi[k] = std::max(chi[k], q[k]); }
    }
    int index = (int)nodes.size(); nodes.push_back(n);
    if (count <= 4) { nodes[index].left = first; nodes[index].count = count; return index; }
    int axis = 0; for (int k = 1; k < 3; k++) if (chi[k]-clo[k] > chi[axis]-clo[axis]) axis = k;
    int mid = first+count/2;
    std::nth_element(order.begin()+first, order.begin()+mid, order.begin()+first+count,
                     [&](int a, int b) { return (&c[a].x)[axis] < (&c[b].x)[axis]; });
    int l = build(first, mid-first, c); int r = build(mid, first+count-mid, c);
    (void)l; nodes[index].left = r; nodes[index].count = 0;  // left child is index+1
    return index;
}

static bool slab(const Node& n, V o, V inv, float tmax) {
    float t0 = 0, t1 = tmax; const float* oo = &o.x; const float* ii = &inv.x;
    for (int k = 0; k < 3; k++) {
        float a = (n.lo[k]-oo[k])*ii[k], b = (n.hi[k]-oo[k])*ii[k];
        if (a > b) std::swap(a, b);
        t0 = std::max(t0, a); t1 = std::min(t1, b);
        if (t0 > t1) return false;
    }
    return true;
}

static int trace(V o, V d, std::vector<int>& through) {
    V inv = {1.f/d.x, 1.f/d.y, 1.f/d.z}; float best = 1e30f; int hit = -1; through.clear();
    std::vector<std::pair<float,int>> clear;
    int stack[128]; int sp = 0; stack[sp++] = 0;
    while (sp) {
        const Node& n = nodes[stack[--sp]];
        if (!slab(n, o, inv, best)) continue;
        if (n.count) {
            for (int i = n.left; i < n.left+n.count; i++) {
                int t = order[i]; V a = tri[t*3], e1 = sub(tri[t*3+1], a), e2 = sub(tri[t*3+2], a);
                V h = cross(d, e2); float det = dot(e1, h);
                if (std::fabs(det) < 1e-9f) continue;
                float f = 1.f/det; V s = sub(o, a); float u = f*dot(s, h);
                if (u < 0 || u > 1) continue;
                V q = cross(s, e1); float v = f*dot(d, q);
                if (v < 0 || u+v > 1) continue;
                float t2 = f*dot(e2, q);
                if (t2 > 0.5f && t2 < best) {
                    if (occ.empty() || occ[t]) { best = t2; hit = t; } else clear.push_back({t2, t});
                }
            }
        } else {
            int self = (int)(&n-&nodes[0]);
            stack[sp++] = n.left; stack[sp++] = self+1;
        }
    }
    for (auto& c : clear) if (c.first < best) through.push_back(c.second);
    return hit;
}

// True if a segment from o to target is blocked by an occluder (excluding self).
static bool blocked(V o, V target, int self) {
    V d = sub(target, o); float len = std::sqrt(dot(d, d)); if (len < 1) return false;
    d = {d.x/len, d.y/len, d.z/len}; V inv = {1.f/d.x, 1.f/d.y, 1.f/d.z};
    int stack[128]; int sp = 0; stack[sp++] = 0;
    while (sp) {
        const Node& n = nodes[stack[--sp]];
        if (!slab(n, o, inv, len)) continue;
        if (n.count) {
            for (int i = n.left; i < n.left+n.count; i++) {
                int t = order[i]; if (t == self || (!occ.empty() && !occ[t])) continue;
                V a = tri[t*3], e1 = sub(tri[t*3+1], a), e2 = sub(tri[t*3+2], a);
                V h = cross(d, e2); float det = dot(e1, h); if (std::fabs(det) < 1e-9f) continue;
                float f = 1.f/det; V s = sub(o, a); float u = f*dot(s, h); if (u < 0 || u > 1) continue;
                V q = cross(s, e1); float v = f*dot(d, q); if (v < 0 || u+v > 1) continue;
                float t2 = f*dot(e2, q); if (t2 > 0.5f && t2 < len-0.5f) return true;
            }
        } else { int self_i = (int)(&n-&nodes[0]); stack[sp++] = n.left; stack[sp++] = self_i+1; }
    }
    return false;
}

static int segments(int argc, char** argv);

int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "segments") return segments(argc, argv);
    if (argc != 5 && argc != 6) { std::puts("triangles points rays_per_point hits [occluders]"); return 2; }
    FILE* f = std::fopen(argv[1], "rb"); std::fseek(f, 0, SEEK_END); long size = std::ftell(f); std::fseek(f, 0, SEEK_SET);
    int n = (int)(size/36); tri.resize(n*3); std::fread(tri.data(), 36, n, f); std::fclose(f);
    f = std::fopen(argv[2], "rb"); std::fseek(f, 0, SEEK_END); size = std::ftell(f); std::fseek(f, 0, SEEK_SET);
    int m = (int)(size/12); std::vector<V> pts(m); std::fread(pts.data(), 12, m, f); std::fclose(f);
    int rays = std::atoi(argv[3]);
    if (argc == 6) { occ.resize(n); f = std::fopen(argv[5], "rb"); std::fread(occ.data(), 1, n, f); std::fclose(f); }
    std::vector<V> c(n); order.resize(n);
    for (int i = 0; i < n; i++) { order[i] = i; c[i] = {(tri[i*3].x+tri[i*3+1].x+tri[i*3+2].x)/3, (tri[i*3].y+tri[i*3+1].y+tri[i*3+2].y)/3, (tri[i*3].z+tri[i*3+1].z+tri[i*3+2].z)/3}; }
    nodes.reserve(n); build(0, n, c);
    std::vector<V> dirs(rays); const float g = 3.14159265f*(3.f-std::sqrt(5.f));
    for (int i = 0; i < rays; i++) { float z = 1-2*(i+.5f)/rays, r = std::sqrt(1-z*z); dirs[i] = {std::cos(g*i)*r, std::sin(g*i)*r, z}; }
    std::vector<std::atomic<uint32_t>> hits(n); for (auto& h : hits) h = 0;
    std::atomic<int> next(0); int threads = std::max(1u, std::thread::hardware_concurrency());
    std::vector<std::thread> pool;
    for (int w = 0; w < threads; w++) pool.emplace_back([&]() {
        std::vector<int> through;
        for (int p; (p = next++) < m;) {
            float a = 2.39996f*p, ca = std::cos(a), sa = std::sin(a);
            for (int i = 0; i < rays; i++) {
                V d = {dirs[i].x*ca-dirs[i].y*sa, dirs[i].x*sa+dirs[i].y*ca, dirs[i].z};
                int t = trace(pts[p], d, through); if (t >= 0) hits[t]++;
                for (int u : through) hits[u]++;
            }
            if (p % 500 == 0) std::fprintf(stderr, "point %d / %d\n", p, m);
        }
    });
    for (auto& t : pool) t.join();
    std::vector<uint32_t> out(n); for (int i = 0; i < n; i++) out[i] = hits[i];
    f = std::fopen(argv[4], "wb"); std::fwrite(out.data(), 4, n, f); std::fclose(f);
    std::printf("triangles %d points %d rays %d threads %d\n", n, m, rays, threads);
}

// usage: visibility_rays segments triangles.bin occluders.bin points.bin candidates.bin radius per_tri out.bin
// For each candidate triangle, test unblocked lines of sight from 4 sample points
// to up to per_tri viewpoints within radius (all within radius/4 first). out: uint8 visible.
static int segments(int argc, char** argv) {
    if (argc != 9) { std::puts("segments triangles occluders points candidates radius per_tri out"); return 2; }
    auto readall = [](const char* p, std::vector<char>& b) { FILE* f = std::fopen(p, "rb"); std::fseek(f, 0, SEEK_END); long n = std::ftell(f); std::fseek(f, 0, SEEK_SET); b.resize(n); std::fread(b.data(), 1, n, f); std::fclose(f); };
    std::vector<char> b; readall(argv[2], b); int n = (int)(b.size()/36); tri.resize(n*3); std::memcpy(tri.data(), b.data(), b.size());
    readall(argv[3], b); occ.assign(b.begin(), b.end());
    readall(argv[4], b); int m = (int)(b.size()/12); std::vector<V> pts(m); std::memcpy(pts.data(), b.data(), b.size());
    readall(argv[5], b); int k = (int)(b.size()/4); std::vector<int> cand(k); std::memcpy(cand.data(), b.data(), b.size());
    float radius = (float)std::atof(argv[6]); int per = std::atoi(argv[7]);
    std::vector<V> c(n); order.resize(n);
    for (int i = 0; i < n; i++) { order[i] = i; c[i] = {(tri[i*3].x+tri[i*3+1].x+tri[i*3+2].x)/3, (tri[i*3].y+tri[i*3+1].y+tri[i*3+2].y)/3, (tri[i*3].z+tri[i*3+1].z+tri[i*3+2].z)/3}; }
    nodes.reserve(n); build(0, n, c);
    std::vector<uint8_t> vis(k, 0); std::atomic<int> next(0);
    int threads = std::max(1u, std::thread::hardware_concurrency()); std::vector<std::thread> pool;
    for (int w = 0; w < threads; w++) pool.emplace_back([&]() {
        std::mt19937 rng(1234+w); std::vector<int> near, far;
        for (int j; (j = next++) < k;) {
            int t = cand[j]; V a = tri[t*3], bb = tri[t*3+1], cc = tri[t*3+2];
            V sp[4] = {c[t], {(a.x*4+bb.x+cc.x)/6, (a.y*4+bb.y+cc.y)/6, (a.z*4+bb.z+cc.z)/6},
                       {(a.x+bb.x*4+cc.x)/6, (a.y+bb.y*4+cc.y)/6, (a.z+bb.z*4+cc.z)/6}, {(a.x+bb.x+cc.x*4)/6, (a.y+bb.y+cc.y*4)/6, (a.z+bb.z+cc.z*4)/6}};
            near.clear(); far.clear();
            for (int p = 0; p < m; p++) { V d = sub(pts[p], c[t]); float dd = dot(d, d);
                if (dd < radius*radius/16) near.push_back(p); else if (dd < radius*radius) far.push_back(p); }
            std::shuffle(near.begin(), near.end(), rng); std::shuffle(far.begin(), far.end(), rng);
            std::vector<int> pick(near.begin(), near.begin()+std::min((int)near.size(), per));
            for (int p : far) { if ((int)pick.size() >= per) break; pick.push_back(p); }
            bool seen = false;
            for (int p : pick) { for (auto& q : sp) if (!blocked(pts[p], q, t)) { seen = true; break; } if (seen) break; }
            vis[j] = seen;
            if (j % 5000 == 0) std::fprintf(stderr, "candidate %d / %d\n", j, k);
        }
    });
    for (auto& t : pool) t.join();
    FILE* f = std::fopen(argv[8], "wb"); std::fwrite(vis.data(), 1, k, f); std::fclose(f);
    int seen = 0; for (auto v : vis) seen += v; std::printf("candidates %d visible %d\n", k, seen); return 0;
}
