#include <vector>
#include <algorithm>
#include <cstdint>
#include <cstddef>
// Weld IDs are generated from positions, so UV/normal seams do not fragment a
// physical component. Keep an anchor triangle and the six extremal positions
// of every connected component. Only active seam vertices are locked.
extern "C" __declspec(dllexport) size_t component_render_locks(
 uint8_t* locks, const uint32_t* indices, size_t count,
 const float* positions, size_t vertices, const uint32_t* weld) {
 std::vector<uint32_t> parent(vertices), first(vertices, UINT32_MAX);
 std::vector<uint8_t> active(vertices,0), selected(vertices,0);
 for(size_t i=0;i<vertices;i++)parent[i]=uint32_t(i);
 auto root=[&](uint32_t i){while(parent[i]!=i){parent[i]=parent[parent[i]];i=parent[i];}return i;};
 for(size_t i=0;i<count;i+=3){
  uint32_t a=root(weld[indices[i]]);
  for(int j=0;j<3;j++){auto v=indices[i+j];active[v]=1;auto b=root(weld[v]);parent[b]=a;}
 }
 std::vector<uint32_t> extrema(vertices*6,UINT32_MAX);
 for(size_t i=0;i<vertices;i++)if(active[i]){
  auto r=root(weld[i]);
  for(int k=0;k<3;k++)for(int side=0;side<2;side++){
   auto &old=extrema[r*6+k*2+side];
   if(old==UINT32_MAX || (side?positions[i*3+k]>positions[old*3+k]:positions[i*3+k]<positions[old*3+k]))old=uint32_t(i);
  }
 }
 size_t components=0;
 for(size_t i=0;i<count;i+=3){auto r=root(weld[indices[i]]);if(first[r]==UINT32_MAX){
  first[r]=uint32_t(i);components++;
  for(int j=0;j<3;j++)selected[weld[indices[i+j]]]=1;
  for(int j=0;j<6;j++)selected[weld[extrema[r*6+j]]]=1;
 }}
 for(size_t i=0;i<vertices;i++)locks[i]=active[i]&&selected[weld[i]]?1:0;
 return components;
}
