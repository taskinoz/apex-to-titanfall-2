// Static diffuse contributions from source fixtures that do not fit native RTL slots.
#define SOURCE_LIGHT_LIBRARY
#include "bake_interior_lighting.cpp"
#undef main
struct SourceFixture { V p;float radius;V colour;float shadow;V direction;float inner,outer,spot; };
static_assert(sizeof(SourceFixture)==56);
int main(int argc,char**argv){try{
 if(argc!=10){std::cerr<<"triangles jobs fixtures output width height pages casters probe-positions\n";return 2;}
 tri=load<T>(argv[1]);auto jobs=load<Job>(argv[2]);auto lights=load<SourceFixture>(argv[3]);
 auto casters=load<uint8_t>(argv[8]);auto probes=load<V>(argv[9]);
 int w=std::stoi(argv[5]),h=std::stoi(argv[6]),pages=std::stoi(argv[7]);
 if(casters.size()!=tri.size()||jobs.size()!=tri.size())throw std::runtime_error("invalid geometry input");
 for(uint32_t i=0;i<tri.size();i++)if(casters[i])order.push_back(i);
 if(order.empty())throw std::runtime_error("empty casters");build(0,order.size());
 auto pixels=raster(jobs,w,h,pages);std::vector<V> output(pixels.size()+probes.size());
 std::atomic<size_t> next{0},lit{0};std::vector<std::thread> pool;
 for(unsigned th=0;th<std::min(8u,std::max(1u,std::thread::hardware_concurrency()));th++)pool.emplace_back([&]{
  while(true){size_t from=next.fetch_add(512);if(from>=output.size())break;
   for(size_t i=from;i<std::min(output.size(),from+512);i++){
    bool probe=i>=pixels.size();V p,n;uint32_t face=UINT32_MAX;
    if(probe){p=probes[i-pixels.size()];n={0,0,0};}
    else {auto px=pixels[i];if(px.face==UINT32_MAX||!casters[px.face])continue;p=px.p+px.n*1.25f;n=px.n;face=px.face;}
    V sum={0,0,0};
    for(const auto &l:lights){V delta=l.p-p;float d2=dot(delta,delta);
     if(d2<1||d2>=l.radius*l.radius)continue;float d=std::sqrt(d2);V direction=delta*(1/d);
     float cone=1;if(l.spot>0){float cosine=dot(direction*(-1),l.direction);
      cone=std::clamp((cosine-l.outer)/std::max(.00001f,l.inner-l.outer),0.f,1.f);}
     float falloff=1-d/l.radius;float weight=falloff*falloff*cone*(probe?.18f:.45f*std::max(0.f,dot(n,direction)));
     if(weight<.00001f)continue;
     if(l.shadow>0&&hit(p,direction,face,d-1.5f))continue;
     sum=sum+l.colour*weight;
    }
    output[i]={std::min(sum.x,2.f),std::min(sum.y,2.f),std::min(sum.z,2.f)};
    if(dot(sum,sum)>0)lit++;
   }
  }
 });for(auto&t:pool)t.join();
 std::ofstream file(argv[4],std::ios::binary);file.write((char*)output.data(),output.size()*sizeof(V));
 std::cout<<"Source fill fixtures "<<lights.size()<<", lit samples "<<lit<<", probes "<<probes.size()<<"\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
