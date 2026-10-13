// CPU static-light baker. Native engine encoding is applied by the Python writer.
// Geometry is read-only; triangles serve only as shadow/sky occluders.
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>
struct V {float x,y,z; V operator+(V b)const{return{x+b.x,y+b.y,z+b.z};} V operator-(V b)const{return{x-b.x,y-b.y,z-b.z};} V operator*(float f)const{return{x*f,y*f,z*f};}};
float dot(V a,V b){return a.x*b.x+a.y*b.y+a.z*b.z;}
V cross(V a,V b){return{a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
V unit(V a){float d=std::sqrt(dot(a,a));return d>1e-8f?a*(1/d):V{0,0,1};}
float axis(V a,int k){return k==0?a.x:k==1?a.y:a.z;}
V low(V a,V b){return{std::min(a.x,b.x),std::min(a.y,b.y),std::min(a.z,b.z)};}
V high(V a,V b){return{std::max(a.x,b.x),std::max(a.y,b.y),std::max(a.z,b.z)};}
struct T {V p[3];};
struct Node{V lo,hi;uint32_t a,b,start,count;};
struct UV{float x,y;};
struct Job{V p[3],n[3];UV uv[3];int32_t page;};
static_assert(sizeof(Job)==100);
std::vector<T> tri;std::vector<uint32_t> order;std::vector<Node> nodes;
uint32_t build(uint32_t start,uint32_t count){
 uint32_t id=uint32_t(nodes.size());nodes.push_back({});V lo={1e30f,1e30f,1e30f},hi={-1e30f,-1e30f,-1e30f};
 for(uint32_t i=start;i<start+count;i++)for(V p:tri[order[i]].p){lo=low(lo,p);hi=high(hi,p);}
 nodes[id]={lo,hi,0,0,start,count};if(count<=8)return id;
 V e=hi-lo;int k=e.y>e.x?1:0;if(e.z>axis(e,k))k=2;
 uint32_t mid=start+count/2;std::nth_element(order.begin()+start,order.begin()+mid,order.begin()+start+count,[k](uint32_t a,uint32_t b){
  return axis(tri[a].p[0]+tri[a].p[1]+tri[a].p[2],k)<axis(tri[b].p[0]+tri[b].p[1]+tri[b].p[2],k);});
 uint32_t a=build(start,mid-start),b=build(mid,start+count-mid);nodes[id].a=a;nodes[id].b=b;nodes[id].count=0;return id;
}
bool box(const Node &n,V p,V d,float maxdist){
 float t0=.01f,t1=maxdist;for(int k=0;k<3;k++){
  float dd=axis(d,k),o=axis(p,k);if(std::abs(dd)<1e-10f){if(o<axis(n.lo,k)||o>axis(n.hi,k))return false;continue;}
  float a=(axis(n.lo,k)-o)/dd,b=(axis(n.hi,k)-o)/dd;if(a>b)std::swap(a,b);t0=std::max(t0,a);t1=std::min(t1,b);if(t0>t1)return false;
 }return true;
}
bool hit(V p,V d,uint32_t ignore,float far=60000){
 uint32_t stack[128],used=1;stack[0]=0;while(used){const Node &n=nodes[stack[--used]];if(!box(n,p,d,far))continue;
  if(!n.count){stack[used++]=n.a;stack[used++]=n.b;continue;}
  for(uint32_t i=n.start;i<n.start+n.count;i++){uint32_t t=order[i];if(t==ignore)continue;const T &q=tri[t];V e1=q.p[1]-q.p[0],e2=q.p[2]-q.p[0];V h=cross(d,e2);float det=dot(e1,h);if(std::abs(det)<1e-8f)continue;
   float inv=1/det;V s=p-q.p[0];float u=inv*dot(s,h);if(u<0||u>1)continue;V qq=cross(s,e1);float v=inv*dot(d,qq);if(v<0||u+v>1)continue;float at=inv*dot(e2,qq);if(at>.05f&&at<far)return true;
  }
 }return false;
}
template<class R>std::vector<R> load(const char*name){std::ifstream f(name,std::ios::binary|std::ios::ate);if(!f)throw std::runtime_error(name);auto size=f.tellg();if(size%sizeof(R))throw std::runtime_error("bad record length");std::vector<R> r(size/sizeof(R));f.seekg(0);f.read((char*)r.data(),size);return r;}
struct Pixel{V p,n;uint32_t face;};
struct Light{float sun,sky;V bent;};
int main(int argc,char **argv){try{
 if(argc!=7&&argc!=8&&argc!=11){std::cerr<<"triangles jobs output width height pages [caster-mask [sun-x sun-y sun-z]]\n";return 2;}tri=load<T>(argv[1]);auto jobs=load<Job>(argv[2]);int w=std::stoi(argv[4]),h=std::stoi(argv[5]),pages=std::stoi(argv[6]);
 auto casters=argc>=8?load<uint8_t>(argv[7]):std::vector<uint8_t>(tri.size(),1);
 if(casters.size()!=tri.size()||jobs.size()!=tri.size()||w<1||h<1||pages<1)throw std::runtime_error("invalid bake inputs");
 // Retain original IDs: the receiver job ID also identifies its triangle for
 // self-intersection rejection. Removing faces would silently break that link.
 order.reserve(tri.size());for(uint32_t i=0;i<tri.size();i++)if(casters[i])order.push_back(i);
 if(order.empty())throw std::runtime_error("no shadow casters");
 nodes.reserve(order.size()*2);build(0,order.size());std::cout<<"BVH "<<order.size()<<" casters, "<<tri.size()-order.size()<<" decorative receivers, "<<nodes.size()<<" nodes\n"<<std::flush;
 size_t size=size_t(w)*h*pages;std::vector<Pixel> pixel(size);for(auto &p:pixel)p.face=UINT32_MAX;
 for(uint32_t i=0;i<jobs.size();i++){auto &j=jobs[i];float den=(j.uv[1].y-j.uv[2].y)*(j.uv[0].x-j.uv[2].x)+(j.uv[2].x-j.uv[1].x)*(j.uv[0].y-j.uv[2].y);if(std::abs(den)<1e-12f)continue;
  int x0=std::max(0,int(std::floor(std::min({j.uv[0].x,j.uv[1].x,j.uv[2].x}))));int x1=std::min(w-1,int(std::ceil(std::max({j.uv[0].x,j.uv[1].x,j.uv[2].x}))));
  int y0=std::max(0,int(std::floor(std::min({j.uv[0].y,j.uv[1].y,j.uv[2].y}))));int y1=std::min(h-1,int(std::ceil(std::max({j.uv[0].y,j.uv[1].y,j.uv[2].y}))));
  for(int y=y0;y<=y1;y++)for(int x=x0;x<=x1;x++){float xx=x+.5f,yy=y+.5f;float a=((j.uv[1].y-j.uv[2].y)*(xx-j.uv[2].x)+(j.uv[2].x-j.uv[1].x)*(yy-j.uv[2].y))/den;
   float b=((j.uv[2].y-j.uv[0].y)*(xx-j.uv[2].x)+(j.uv[0].x-j.uv[2].x)*(yy-j.uv[2].y))/den,c=1-a-b;if(std::min({a,b,c})<-.0001f)continue;
   pixel[(size_t(j.page)*h+y)*w+x]={j.p[0]*a+j.p[1]*b+j.p[2]*c,unit(j.n[0]*a+j.n[1]*b+j.n[2]*c),i};
  }
 }
 std::vector<Light> result(size);std::vector<V> dirs;for(int k=0;k<24;k++){float z=std::sqrt((k+.5f)/24),r=std::sqrt(1-z*z),a=k*2.39996323f;dirs.push_back({r*std::cos(a),r*std::sin(a),z});}
 V sun=unit({.6178957224f,-.4823191166f,.6209453344f});
 if(argc==11){V requested={std::stof(argv[8]),std::stof(argv[9]),std::stof(argv[10])};if(!std::isfinite(dot(requested,requested))||dot(requested,requested)<1e-12f)throw std::runtime_error("invalid sun direction");sun=unit(requested);}
 std::atomic<size_t> next{0},valid{0},blocked{0};std::vector<std::thread> pool;
 unsigned threads=std::min(16u,std::max(1u,std::thread::hardware_concurrency()));
 for(unsigned th=0;th<threads;th++)pool.emplace_back([&]{while(true){size_t from=next.fetch_add(512);if(from>=size)break;for(size_t i=from;i<std::min(size,from+512);i++){
  const Pixel &p=pixel[i];if(p.face==UINT32_MAX)continue;valid++;
  if(!casters[p.face]){result[i]={0.f,-1.f,{0,0,0}};continue;}
  V o=p.p+p.n*1.25f;bool obstructed=hit(o,sun,p.face);blocked+=obstructed;float vis=0;V bent={0,0,0};
  for(V d:dirs)if(!hit(o,d,p.face)){vis+=1;bent=bent+d;}
  float sky=vis/dirs.size();result[i]={obstructed?0.f:1.f,sky,unit(bent)*std::cbrt(sky)};
 }}});
 for(auto &t:pool)t.join();std::ofstream f(argv[3],std::ios::binary);f.write((char*)result.data(),result.size()*sizeof(Light));
 std::ofstream mask(std::string(argv[3])+".mask",std::ios::binary);for(auto &p:pixel){uint8_t v=p.face!=UINT32_MAX;mask.write((char*)&v,1);}
 std::cout<<"Luxels "<<valid<<", sun occluded "<<blocked<<", threads "<<threads<<"\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
