// Traverse file-backed expression blocks. The OS can reclaim clean pages on
// memory-limited runners while densely accessed blocks stay cached.
#include "blocks.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <limits>
#include <queue>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

using Word = std::uint32_t;
constexpr Word none = std::numeric_limits<Word>::max();
constexpr Word tag = Word(1) << 31;
using Pair = std::array<Word, 2>;
using Triple = std::array<Word, 3>;

template<class T> struct File {
  std::size_t size;
  const T* data;
  explicit File(const std::string& path, bool prefetch = false) {
    int fd = open(path.c_str(), O_RDONLY);
    struct stat st{};
    if (fd < 0 || fstat(fd, &st) < 0 || st.st_size % sizeof(T)) throw std::runtime_error(path);
    size = st.st_size / sizeof(T);
    data = size ? static_cast<const T*>(mmap(nullptr, st.st_size, PROT_READ, MAP_PRIVATE | (prefetch ? MAP_POPULATE : 0), fd, 0)) : nullptr;
    close(fd);
    if (data == MAP_FAILED) throw std::runtime_error("mmap " + path);
  }
  ~File() { if (data) munmap(const_cast<T*>(data), size * sizeof(T)); }
  const T& operator[](std::size_t i) const {
    if (i >= size) throw std::out_of_range("corrupt graph index");
    return data[i];
  }
};

struct Expressions {
  File<blocks::ShortPair> edges;
  File<Word> offsets, values;
  explicit Expressions(const std::string& dir, bool prefetch):
    edges(dir + "/edges.bin", prefetch), offsets(dir + "/offsets.bin", prefetch), values(dir + "/values.bin", prefetch) {}
  Pair operator[](Word e) const {
    Word block = e / blocks::width;
    auto decode = [&](std::uint16_t v) -> Word {
      return v < blocks::width ? block * blocks::width + v : values[offsets[block] + v - blocks::width];
    };
    const auto& pair = edges[e];
    return {decode(pair[0]), decode(pair[1])};
  }
};

struct Group {
  std::vector<Word> roots, dependencies;
  std::uint64_t weight = 0;
  bool measured = false;
};

struct Graph {
  Expressions expr;
  File<Triple> lets;
  File<Word> owner;
  std::vector<Group> groups{1};
  std::vector<std::uint64_t> marked;
  std::vector<Word> touched, stack;
  explicit Graph(const std::string& dir, bool load_groups = true):
    expr(dir, load_groups), lets(dir + "/let.bin"), owner(dir + "/owner.bin"), marked((expr.edges.size + 63) / 64) {
    if (!load_groups) return;
    File<Word> records(dir + "/groups.bin");
    for (std::size_t pos = 0; pos < records.size;) {
      Word n = records[pos++];
      if (pos + n > records.size) throw std::runtime_error("truncated group record");
      Group g;
      g.roots.assign(records.data+pos, records.data+pos+n);
      pos += n;
      groups.push_back(std::move(g));
    }
  }
  void measure_group(Word id) {
    auto& g = groups.at(id);
    if (g.measured) return;
    auto dependency = [&](Word n) {
      Word d = owner[n];
      if (d == none) throw std::runtime_error("unresolved constant " + std::to_string(n));
      if (d && d != id) g.dependencies.push_back(d);
    };
    stack.assign(g.roots.begin(), g.roots.end());
    touched.clear();
    while (!stack.empty()) {
      Word e = stack.back(); stack.pop_back();
      auto mask = std::uint64_t(1) << (e % 64);
      auto& word = marked.at(e / 64);
      if (word & mask) continue;
      word |= mask;
      touched.push_back(e);
      auto [a,b] = expr[e];
      if (a == none) {
        if (b != none) dependency(b);
      } else if (a & tag) {
        for (auto x : lets[a & ~tag]) stack.push_back(x);
      } else {
        stack.push_back(a);
        if (b != none) {
          if (b & tag) dependency(b & ~tag); else stack.push_back(b);
        }
      }
    }
    g.weight = touched.size();
    g.measured = true;
    for (auto e : touched) marked[e / 64] = 0;
    std::sort(g.dependencies.begin(), g.dependencies.end());
    g.dependencies.erase(std::unique(g.dependencies.begin(), g.dependencies.end()), g.dependencies.end());
  }
  void write_substitution_graph(const std::string& dir, Word root) {
    // At this point only declarations reachable from ordinary RH are measured.
    // Reference counts let independent edits update the closure incrementally.
    std::vector<Word> references(groups.size());
    references[root] = 1;
    for (const auto& g : groups) {
      if (g.measured) for (auto dep : g.dependencies) ++references.at(dep);
    }
    std::ofstream nodes(dir + "/archive-graph/groups.bin", std::ios::binary);
    std::ofstream edges(dir + "/archive-graph/dependencies.bin", std::ios::binary);
    nodes.exceptions(std::ios::badbit | std::ios::failbit);
    edges.exceptions(std::ios::badbit | std::ios::failbit);
    Word offset = 0;
    for (Word id = 0; id < groups.size(); ++id) {
      if (id) measure_group(id);
      const auto& g = groups[id];
      if (g.weight >= none || g.dependencies.size() >= none-offset)
        throw std::runtime_error("archive group or edge count too large");
      for (auto dep : g.dependencies) {
        if (dep >= id) throw std::runtime_error("archive group order is not topological");
      }
      Word degree = static_cast<Word>(g.dependencies.size());
      std::array<Word, 4> record{static_cast<Word>(g.weight), offset, degree, references[id]};
      nodes.write(reinterpret_cast<const char*>(record.data()), sizeof(record));
      if (degree) edges.write(reinterpret_cast<const char*>(g.dependencies.data()), degree*sizeof(Word));
      offset += degree;
    }
  }

  std::pair<std::uint64_t, Word> total(Word root, Word cut) {
    std::vector<bool> seen(groups.size());
    std::priority_queue<Word> pending;
    auto offer = [&](Word id) {
      if (id != cut && !seen.at(id)) { seen[id] = true; pending.push(id); }
    };
    offer(root);
    std::uint64_t cost = 0;
    Word count = 0;
    while (!pending.empty()) {
      Word id = pending.top(); pending.pop();
      measure_group(id);
      cost += groups[id].weight; ++count;
      if (count % 100000 == 0) std::cerr << count << " reachable groups, " << cost << " nodes\n";
      for (auto d : groups[id].dependencies) offer(d);
    }
    return {cost, count};
  }
};

int main(int argc, char** argv) {
  // Independent statement measurements for exact theorem reuse. Group zero
  // is scratch and has no owner, so all archive constants are reported.
  if (argc == 3 && std::string_view(argv[2]) == "--theorem-statements") {
    Graph graph(argv[1], false);
    Word root;
    auto& scratch = graph.groups.at(0);
    while (std::cin >> root) {
      scratch.roots = {root};
      scratch.dependencies.clear();
      scratch.measured = false;
      graph.measure_group(0);
      std::cout << root << ' ' << scratch.weight;
      for (auto dep : scratch.dependencies) std::cout << ' ' << dep;
      std::cout << '\n';
    }
    if (!std::cin.eof()) throw std::runtime_error("malformed expression ID list");
    return 0;
  }
  if (argc != 7) return 2;
  Graph graph(argv[1]);
  Word root = std::stoul(argv[2]), cut = std::stoul(argv[3]);
  Word wrapper = std::stoul(argv[4]), bridge = std::stoul(argv[5]), allChi = std::stoul(argv[6]);
  auto total = graph.total(root, 0);
  graph.write_substitution_graph(argv[1], root);
  auto spine = graph.total(root, cut);
  auto leaf = graph.total(cut, 0);
  auto edge = [&](Word a, Word b) {
    const auto& ds = graph.groups.at(a).dependencies;
    return std::find(ds.begin(), ds.end(), b) != ds.end();
  };
  if (!edge(root, wrapper) || !edge(wrapper, bridge) || !edge(wrapper, allChi) || !edge(bridge, cut))
    throw std::runtime_error("the published RH-to-reflection edges did not match");
  std::cout << "{\"archive_nodes\":" << total.first << ",\"spine_nodes\":" << spine.first
            << ",\"reflection_nodes\":" << leaf.first << ",\"archive_groups\":" << total.second
            << ",\"spine_groups\":" << spine.second << ",\"reflection_groups\":" << leaf.second << "}\n";
}
