"""Stage a small AGPLv3 RPak decoder from the checked-out RSX source.

Only the upstream RTech decoder and its lookup tables are compiled; the original
RSX source and license remain in tools/rsx-source. This avoids any tool GUI.
"""
from pathlib import Path

base=Path('tools/rsx-source/src/game/rtech/utils')
header=(base/'utils.h').read_text()
source=(base/'utils.cpp').read_text()
tables=header[header.index('namespace'):header.index('#define PAK_DECODE_MASK')]
start=header.index('struct PakDecompressContext_t')
context=header[start:header.index('};',start)+2]
start=source.index('#define LAST_IND')
end=source.index("// I don't wanna deal with these warnings")
decoder=source[start:end]
output=Path('tools/rtech-decode')
output.mkdir(exist_ok=True)
wrapper=r'''
// Decoder code and lookup tables derived from RSX, AGPLv3.
#include <cstdint>
#include <cstddef>
#include <array>
#include <cstring>
#include <cstdio>
#include <vector>
#include <fstream>
#include <intrin.h>
#include <immintrin.h>
'''+tables+'\nclass RTech { public:\n'+context+r'''
static size_t InitPakDecoder(PakDecompressContext_t* const,const uint8_t* const,const uint64_t,const size_t,const size_t,const size_t);
static bool DecompressPakFile(PakDecompressContext_t*,size_t,size_t);
};
'''+decoder+r'''
int main(int argc,char** argv) {
    if(argc!=3) return 2;
    std::ifstream input(argv[1],std::ios::binary|std::ios::ate);
    if(!input) return 3;
    size_t size=static_cast<size_t>(input.tellg());
    if(size<88) return 4;
    std::vector<uint8_t> compressed(size+64,0);
    input.seekg(0);input.read(reinterpret_cast<char*>(compressed.data()),size);
    uint16_t version,flags;uint64_t expected;
    memcpy(&version,compressed.data()+4,2);memcpy(&flags,compressed.data()+6,2);
    memcpy(&expected,compressed.data()+40,8);
    if(version!=7 || !(flags&0x100) || expected<88 || expected>1073741824ULL) return 5;
    RTech::PakDecompressContext_t context{};
    uint64_t decoded=RTech::InitPakDecoder(&context,compressed.data(),UINT64_MAX,size,0,88);
    if(decoded!=expected) return 6;
    std::vector<uint8_t> uncompressed(expected+64,0);
    context.m_outputMask=UINT64_MAX;
    context.m_outputBuf=reinterpret_cast<uint64_t>(uncompressed.data());
    if(!RTech::DecompressPakFile(&context,size,decoded)) return 7;
    memcpy(uncompressed.data(),compressed.data(),88);
    flags&=~0x100;memcpy(uncompressed.data()+6,&flags,2);
    memcpy(uncompressed.data()+24,&expected,8);
    std::ofstream result(argv[2],std::ios::binary);
    result.write(reinterpret_cast<char*>(uncompressed.data()),expected);
    printf("Decoded %llu bytes\n",static_cast<unsigned long long>(expected));
    return result?0:8;
}
'''
(output/'decode.cpp').write_text(wrapper)
(output/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(rtech_decode LANGUAGES CXX)\nadd_executable(rtech_decode decode.cpp)\ntarget_compile_features(rtech_decode PRIVATE cxx_std_17)\n')
(output/'LICENSE').write_bytes(Path('tools/rsx-source/LICENSE').read_bytes())
print(output)
