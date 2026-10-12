#pragma once
// Serialized little-endian records observed in this conversion, NOT runtime engine structs.
// Do not reinterpret untrusted bytes directly: bounds-check, memcpy/decode LE, validate floats.
// Version-dispatch the enclosing lump before interpreting a record. Unknown fields stay raw.
#include <cstdint>
#include <cstddef>
namespace phase_runner_conversion {
#pragma pack(push, 1)
struct Lump { uint32_t offset, length, version, fourcc; };
struct BspHeader { char magic[4]; uint32_t version, revision, last_lump; Lump lumps[128]; };
struct Vec3 { float x,y,z; };
struct Plane { Vec3 normal; float distance; };
struct ApexBvhNode { int16_t grouped_axis_bounds[24]; uint32_t words[4]; };
struct LitBumpVertex {
    uint32_t position, normal; float uv[2]; uint8_t color[4];
    float light_fields[4]; uint32_t tangent_and_mirror, extra;
};
struct Mesh {
    uint32_t first_index; uint16_t triangles, first_vertex, vertex_span;
    int8_t vertex_type, cubemap, light_styles[4]; int16_t luxel_origin[2];
    uint8_t luxel_max[2]; uint16_t material_sort; uint32_t flags;
};
struct MeshBounds { Vec3 center; float radius; Vec3 half_extent; float reserved; };
struct MaterialSort { int16_t texture, lightmap, cubemap; uint16_t last_local_vertex; uint32_t vertex_base; };
struct LightmapHeader { uint32_t count; uint16_t width,height; };
struct CellNode { Vec3 mins; uint8_t children,direct_refs; uint16_t subtree_refs; Vec3 maxs; uint16_t first_child,first_ref; };
struct ObjectBounds { Vec3 mins; uint32_t reserved0; Vec3 maxs; uint32_t reserved1; };
struct CmGridCell { uint16_t first_geoset, geosets; };
struct CmGeoSet { uint16_t group, count; uint32_t primitive_or_first; };
struct PackedBounds { int16_t center[3]; uint16_t flags; int16_t extent[3]; uint16_t unused; };
struct CmBrush { Vec3 center; uint8_t cuts,cuts_plus_bevels; uint16_t id; Vec3 extent; uint32_t plane_offset; };
struct TriCollHeader {
    int16_t flags,texture_flags,texture,vertices,triangles,bevels;
    int32_t first_vertex,first_triangle,first_node,first_bevel; Vec3 origin; float scale;
};
struct ShadowMesh { uint32_t vertex_base,triangles; int16_t opaque,material_sort; };
struct LightProbe { int16_t coefficients[16]; uint8_t visibility[4]; int16_t local_lights[4]; uint32_t reserved; };
struct ProbeRef { Vec3 origin; uint32_t index; int32_t reserved; };
struct ProbeParent { int32_t index; uint32_t first_probe,probes,first_ref,refs,first_tree,nodes; };
struct StaticProp13 {
    Vec3 origin; float raw_angles[3],scale; uint16_t model; uint8_t solid,flags;
    uint16_t skin,cubemap; float fade; Vec3 lighting_origin;
    int8_t cpu_gpu[4]; uint8_t color[4]; uint16_t collision_flags[2];
};
struct StbspMaterial { uint32_t string_offset,unknown; uint64_t guid; uint32_t unknown2,unknown3; };
struct StbspColumn { uint64_t payload_offset; uint32_t payload_length; float coverage; int16_t bounds_xy[4]; };
#pragma pack(pop)
static_assert(sizeof(Lump)==16 && sizeof(BspHeader)==2064);
static_assert(sizeof(Vec3)==12 && sizeof(Plane)==16 && sizeof(ApexBvhNode)==64);
static_assert(sizeof(LitBumpVertex)==44 && sizeof(Mesh)==28 && sizeof(MeshBounds)==32);
static_assert(sizeof(MaterialSort)==12 && sizeof(LightmapHeader)==8);
static_assert(sizeof(CellNode)==32 && sizeof(ObjectBounds)==32);
static_assert(sizeof(CmGridCell)==4 && sizeof(CmGeoSet)==8 && sizeof(PackedBounds)==16);
static_assert(sizeof(CmBrush)==32 && sizeof(TriCollHeader)==44 && sizeof(ShadowMesh)==12);
static_assert(sizeof(LightProbe)==48 && sizeof(ProbeRef)==20 && sizeof(ProbeParent)==28);
static_assert(sizeof(StaticProp13)==64 && sizeof(StbspMaterial)==24 && sizeof(StbspColumn)==24);
static_assert(offsetof(Mesh, material_sort)==22 && offsetof(Mesh,flags)==24);
constexpr uint32_t primitive_index(uint32_t w) { return (w>>8)&0xffffu; }
constexpr uint32_t primitive_kind(uint32_t w) { return w>>24; }
constexpr uint32_t primitive_contents(uint32_t w) { return w&0xffu; }
constexpr uint32_t padded_index_count(uint32_t triangles) { return 3u*(triangles+(triangles&1u)); }
} // namespace phase_runner_conversion
