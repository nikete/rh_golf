// Partition the pinned lean4export stream while preserving every primitive ID.
// The unmodified primitives stream directly to the final temporary output.
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>

int main(int argc, char** argv) {
  if (argc != 2) return 2;
  std::ios::sync_with_stdio(false);
  std::cin.tie(nullptr);
  std::string dir = argv[1];
  std::ofstream metadata(dir + "/metadata"), constants(dir + "/constants"), counts(dir + "/counts");
  for (auto out : {&metadata, &constants, &counts}) out->exceptions(std::ios::failbit | std::ios::badbit);
  std::cout.exceptions(std::ios::failbit | std::ios::badbit);
  std::uint64_t expressions = 0, levels = 1;
  std::string line;
  while (std::getline(std::cin, line)) {
    std::string_view text(line);
    auto end = text.find('"', 2);
    if (text.substr(0, 2) != "{\"" || end == text.npos) throw std::runtime_error("not an export record");
    auto key = text.substr(2, end - 2);
    if (key == "axiom" || key == "def" || key == "opaque" || key == "thm" ||
        key == "inductive" || key == "quot") {
      metadata << line << '\n';
      continue;
    }
    std::cout << line << '\n';
    if (key == "in" || key == "il" || key == "meta") {
      metadata << line << '\n';
      if (key == "il") ++levels;
    } else {
      // The exporter emits compact JSON with lexicographically sorted keys.
      // Any other primitive is an expression; indices begin at zero.
      if (text.find("\"ie\":") == text.npos) throw std::runtime_error("unrecognized export record");
      ++expressions;
      if (key == "const") constants << line << '\n';
    }
  }
  if (!std::cin.eof()) throw std::runtime_error("reading origin failed");
  counts << expressions << ' ' << levels << '\n';
}
