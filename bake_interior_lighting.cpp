// Reuse the validated read-only triangle tracer; only local-light visibility
// is baked here. Native shaders evaluate the actual PBR point-light response.
#define main SunBakeMain
#include "bake_phase_lighting.cpp"
#undef main
struct Fixture{V p;float radius;V colour;uint32_t index;};
struct Local{uint32_t ids=0x00FFFFC0;uint8_t vis[4]={0,0,0,0};V fill={0,0,0};};
static_assert(sizeof(Fixture)==32);static_assert(sizeof(Local)==20);
std::vector<Pixel> raster(const std::vector<Job>& jobs,int w,int h,int pages){
 std::vector<Pixel> pixels(size_t(w)*h*pages);for(auto &p:pixels)p.face=UINT32_MAX;
 for(uint32_t i=0;i<jobs.size();i++){const auto &j=jobs[i];
  float den=(j.uv[1].y-j.uv[2].y)*(j.uv[0].x-j.uv[2].x)+(j.uv[2].x-j.uv[1].x)*(j.uv[0].y-j.uv[2].y);if(std::abs(den)<1e-12f)continue;
  int x0=std::max(0,int(std::floor(std::min({j.uv[0].x,j.uv[1].x,j.uv[2].x})))),x1=std::min(w-1,int(std::ceil(std::max({j.uv[0].x,j.uv[1].x,j.uv[2].x}))));
  int y0=std::max(0,int(std::floor(std::min({j.uv[0].y,j.uv[1].y,j.uv[2].y})))),y1=std::min(h-1,int(std::ceil(std::max({j.uv[0].y,j.uv[1].y,j.uv[2].y}))));
  for(int y=y0;y<=y1;y++)for(int x=x0;x<=x1;x++){float xx=x+.5f,yy=y+.5f;
   float a=((j.uv[1].y-j.uv[2].y)*(xx-j.uv[2].x)+(j.uv[2].x-j.uv[1].x)*(yy-j.uv[2].y))/den;
   float b=((j.uv[2].y-j.uv[0].y)*(xx-j.uv[2].x)+(j.uv[0].x-j.uv[2].x)*(yy-j.uv[2].y))/den,c=1-a-b;
   if(std::min({a,b,c})<-.0001f)continue;
   pixels[(size_t(j.page)*h+y)*w+x]={j.p[0]*a+j.p[1]*b+j.p[2]*c,unit(j.n[0]*a+j.n[1]*b+j.n[2]*c),i};
  }
 }return pixels;
}
int main(int argc,char**argv){try{
 if(argc!=9){std::cerr<<"triangles jobs fixtures output width height pages caster-mask\n";return 2;}
 tri=load<T>(argv[1]);auto jobs=load<Job>(argv[2]);auto lights=load<Fixture>(argv[3]);auto casters=load<uint8_t>(argv[8]);
 int w=std::stoi(argv[5]),h=std::stoi(argv[6]),pages=std::stoi(argv[7]);
 if(casters.size()!=tri.size()||jobs.size()!=tri.size()||lights.size()>61)throw std::runtime_error("invalid local-light input");
 for(uint32_t i=0;i<tri.size();i++)if(casters[i])order.push_back(i);if(order.empty())throw std::runtime_error("empty casters");build(0,order.size());
 auto pixels=raster(jobs,w,h,pages);std::vector<Local> output(pixels.size());std::atomic<size_t> next{0},lit{0};std::vector<std::thread> pool;
 unsigned threads=std::min(8u,std::max(1u,std::thread::hardware_concurrency()));
 for(unsigned th=0;th<threads;th++)pool.emplace_back([&]{while(true){size_t from=next.fetch_add(512);if(from>=pixels.size())break;
  for(size_t i=from;i<std::min(pixels.size(),from+512);i++){const auto &p=pixels[i];if(p.face==UINT32_MAX||!casters[p.face])continue;
   struct Pick{float score;const Fixture* light;};Pick best[3]={{0,nullptr},{0,nullptr},{0,nullptr}};
   V o=p.p+p.n*1.25f;
   for(const auto &l:lights){V delta=l.p-o;float d2=dot(delta,delta);if(d2>=l.radius*l.radius||d2<1)continue;float d=std::sqrt(d2);V direction=delta*(1/d);
    float falloff=std::max(0.f,1-d/l.radius);float score=falloff*std::max(.1f,dot(p.n,direction))*std::max({l.colour.x,l.colour.y,l.colour.z});
    if(score<=best[2].score||hit(o,direction,p.face,d-1.5f))continue;
    best[2]={score,&l};std::sort(best,best+3,[](const Pick&a,const Pick&b){return a.score>b.score;});
   }
   if(!best[0].light)continue;lit++;auto &r=output[i];r.ids=0;
   for(int k=0;k<3;k++){uint32_t id=best[k].light?best[k].light->index:63;r.ids|=id<<(6*(k+1));
    if(best[k].light){r.vis[k+1]=255;r.fill=r.fill+best[k].light->colour*(.025f*best[k].score);}
   }
  }
 }});
 for(auto &t:pool)t.join();std::ofstream file(argv[4],std::ios::binary);file.write((char*)output.data(),output.size()*sizeof(Local));
 std::cout<<"Interior lights "<<lights.size()<<", directly lit surface luxels "<<lit<<", threads "<<threads<<"\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
