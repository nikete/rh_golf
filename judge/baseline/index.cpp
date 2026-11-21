// Compact the pinned lean4export expression graph while streaming its NDJSON.
// Structural edges are sufficient for reachability and counting syntax tree nodes.
#include "blocks.hpp"
#include <array>
#include <charconv>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>

using Word = std::uint32_t;
constexpr Word none = std::numeric_limits<Word>::max();
constexpr Word tag = Word(1) << 31;

Word field(std::string_view line, std::string_view key) {
  auto pos = line.find(key);
  if (pos == line.npos) throw std::runtime_error("missing numeric field");
  Word value;
  auto start = line.data() + pos + key.size();
  if (std::from_chars(start, line.data() + line.size(), value).ec != std::errc{} || value >= tag)
    throw std::runtime_error("invalid graph index");
  return value;
}

template <std::size_t N>
void emit(std::ostream& out, const std::array<Word, N>& record) {
  out.write(reinterpret_cast<const char*>(record.data()), sizeof(record));
}

int main(int argc, char** argv) {
  if (argc != 2) return 2;
  std::ios::sync_with_stdio(false);
  std::cin.tie(nullptr);
  const std::string dir = argv[1];
  blocks::Writer exprs(dir);
  std::ofstream lets(dir + "/let.bin", std::ios::binary);
  std::ofstream metadata(dir + "/declarations.ndjson");
  lets.exceptions(std::ios::badbit | std::ios::failbit);
  metadata.exceptions(std::ios::badbit | std::ios::failbit);
  std::string line;
  Word count = 0, letCount = 0;
  while (std::getline(std::cin, line)) {
    std::string_view s(line);
    if (s.find("\"ie\":") == s.npos) {
      if (s.find("\"il\":") == s.npos) metadata << line << '\n';
      continue;
    }
    if (field(s, "\"ie\":") != count++) throw std::runtime_error("nonconsecutive expression ID");
    std::array<Word, 2> edges{none, none};
    if (s.starts_with("{\"app\":")) {
      edges = {field(s, "\"fn\":"), field(s, "\"arg\":")};
    } else if (s.find("\"lam\":") != s.npos || s.starts_with("{\"forallE\":")) {
      edges = {field(s, "\"type\":"), field(s, "\"body\":")};
    } else if (s.starts_with("{\"const\":")) {
      edges[1] = field(s, "\"name\":");
    } else if (s.find("\"proj\":") != s.npos) {
      edges = {field(s, "\"struct\":"), tag | field(s, "\"typeName\":")};
    } else if (s.find("\"letE\":") != s.npos) {
      edges[0] = tag | letCount++;
      emit(lets, std::array<Word, 3>{field(s, "\"type\":"), field(s, "\"value\":"), field(s, "\"body\":")});
    } else if (s.find("\"bvar\":") == s.npos && s.find("\"sort\":") == s.npos &&
               s.find("\"natVal\":") == s.npos && s.find("\"strVal\":") == s.npos) {
      throw std::runtime_error("unsupported expression in pinned export");
    }
    exprs.push(edges);
  }
  std::cerr << count << " expression records\n";
}
