import Lean

open Lean

private def components : Name → List Json → List Json
  | .anonymous, tail => tail
  | .str p s, tail => components p (.str s :: tail)
  | .num p n, tail => components p (toJson n :: tail)

def main : IO Unit := do
  initSearchPath (← findSysroot)
  let env ← importModules #[{module := `Mathlib}] {}
  let out ← IO.getStdout
  for (n, _) in env.constants.toList do
    out.putStrLn (Json.arr (components n []).toArray).compress
