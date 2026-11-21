// References inside a 16K-expression block use a 16-bit offset. All other
// edge values are stored in a per-block dictionary, including literal markers.
#pragma once
#include <array>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace blocks {
constexpr std::uint32_t width = 1 << 14;
using Pair = std::array<std::uint32_t, 2>;
using ShortPair = std::array<std::uint16_t, 2>;

class Writer {
  std::ofstream edges, offsets, values;
  std::unordered_map<std::uint32_t, std::uint16_t> lookup;
  std::uint32_t index = 0, value_count = 0;

  template<class T> static void append(std::ofstream& out, const T& value) {
    out.write(reinterpret_cast<const char*>(&value), sizeof(T));
  }

public:
  explicit Writer(const std::string& dir):
    edges(dir + "/edges.bin", std::ios::binary), offsets(dir + "/offsets.bin", std::ios::binary),
    values(dir + "/values.bin", std::ios::binary) {
    for (auto out : {&edges, &offsets, &values}) out->exceptions(std::ios::badbit | std::ios::failbit);
    lookup.reserve(width * 2);
  }
  void push(const Pair& input) {
    auto base = index - index % width;
    if (index == base) {
      lookup.clear();
      append(offsets, value_count);
    }
    ShortPair encoded;
    for (unsigned j = 0; j < 2; ++j) {
      auto v = input[j];
      if (v >= base && v < base + width) {
        encoded[j] = v - base;
      } else {
        auto [pos, inserted] = lookup.try_emplace(v, static_cast<std::uint16_t>(width + lookup.size()));
        if (inserted) { append(values, v); ++value_count; }
        encoded[j] = pos->second;
      }
    }
    append(edges, encoded);
    ++index;
  }
};
}
