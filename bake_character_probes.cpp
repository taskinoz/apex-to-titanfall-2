// Bake moving-model lighting against the same read-only world shadow geometry.
#define main SurfaceBakeMain
#include "bake_phase_lighting.cpp"
#undef main
struct Fixture {V p;float radius;V colour;uint32_t index;};
struct Result {float sh[12]={},sky[4]={},weights[4]={},indices[4]={-1,-1,-1,-1};};
static_assert(sizeof(Result)==96);
int main(int argc,char**argv){try{
 if(argc!=5){std::cerr<<"casters positions fixtures output\n";return 2;}
 tri=load<T>(argv[1]);auto points=load<V>(argv[2]);auto fixtures=load<Fixture>(argv[3]);
 for(uint32_t i=0;i<tri.size();i++)order.push_back(i);
 if(order.empty()||points.empty())throw std::runtime_error("Empty bake input");build(0,order.size());
 std::vector<V> dirs;for(int k=0;k<64;k++){float z=std::sqrt((k+.5f)/64),r=std::sqrt(1-z*z),a=k*2.39996323f;dirs.push_back({r*std::cos(a),r*std::sin(a),z});}
 V sun=unit({.6178957224f,-.4823191166f,.6209453344f});
 std::vector<Result> results(points.size());std::atomic<size_t> next{0},sunlit{0},local{0};std::vector<std::thread> pool;
 for(unsigned th=0;th<std::min(16u,std::max(1u,std::thread::hardware_concurrency()));th++)pool.emplace_back([&]{
  while(true){size_t from=next.fetch_add(128);if(from>=points.size())break;
   for(size_t i=from;i<std::min(points.size(),from+128);i++){
    V p=points[i];auto &r=results[i];V bent={0,0,0};float visible=0;
    for(V d:dirs)if(!hit(p,d,UINT32_MAX)){visible++;bent=bent+d;}
    float sky=visible/dirs.size();V direction=visible?unit(bent):V{0,0,0};
    V ambient={.025f*(.4f+.6f*sky),.027f*(.4f+.6f*sky),.032f*(.4f+.6f*sky)};
    bool clear=!hit(p,sun,UINT32_MAX);sunlit+=clear;
    V skyVector=direction*std::cbrt(sky);r.sky[0]=skyVector.x;r.sky[1]=skyVector.y;r.sky[2]=skyVector.z;r.sky[3]=clear?1.f:0.f;
    struct Pick{float score;const Fixture* light;};Pick picks[4]={{0,nullptr},{0,nullptr},{0,nullptr},{0,nullptr}};
    for(const auto &l:fixtures){V delta=l.p-p;float d2=dot(delta,delta);if(d2>=l.radius*l.radius||d2<1)continue;
     float d=std::sqrt(d2),falloff=1-d/l.radius;float score=falloff*std::max({l.colour.x,l.colour.y,l.colour.z});
     if(score<=picks[3].score||hit(p,delta*(1/d),UINT32_MAX,d-1.5f))continue;
     picks[3]={score,&l};std::sort(picks,picks+4,[](const Pick&a,const Pick&b){return a.score>b.score;});
    }
    if(picks[0].light)local++;
    for(int k=0;k<4;k++)if(picks[k].light){r.weights[k]=255;r.indices[k]=float(picks[k].light->index);ambient=ambient+picks[k].light->colour*(.025f*picks[k].score);}
    for(int c=0;c<3;c++){float value=axis(ambient,c);r.sh[c*4]=value*.35f*direction.x;r.sh[c*4+1]=value*.35f*direction.y;r.sh[c*4+2]=value*.35f*direction.z;r.sh[c*4+3]=value;}
   }
  }
 });for(auto &t:pool)t.join();
 std::ofstream f(argv[4],std::ios::binary);f.write((char*)results.data(),results.size()*sizeof(Result));
 std::cout<<"Character probes "<<points.size()<<", sunlit "<<sunlit<<", local-lit "<<local<<", casters "<<tri.size()<<"\n";
 return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
