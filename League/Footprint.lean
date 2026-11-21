import Lean

/-! Expression nodes are shared within a declaration. Each reachable declaration is billed
once. Course definitions outside Mathlib have explicit weights so joined entries share them. -/
namespace Golf.Footprint
open Lean

private partial def normalize (e : Expr) : StateM (ExprMap Expr) Expr := do
  if let some v := (← get)[e]? then return v
  let v ← match e with
    | .mdata _ a => normalize a
    | .app f a => pure (.app (← normalize f) (← normalize a))
    | .lam _ t b _ => pure (.lam .anonymous (← normalize t) (← normalize b) .default)
    | .forallE _ t b _ => pure (.forallE .anonymous (← normalize t) (← normalize b) .default)
    | .letE _ t v b _ => pure (.letE .anonymous (← normalize t) (← normalize v) (← normalize b) false)
    | .proj n i a => pure (.proj n i (← normalize a))
    | _ => pure e
  modify fun memo => memo.insert e v
  return v

private structure Part where
  expressions : ExprSet := {}
  names : NameSet := {}

private partial def scan (e : Expr) (p : Part) : Part := Id.run do
  if p.expressions.contains e then return p
  let p := {p with expressions := p.expressions.insert e}
  match e with
  | .const n _ => return {p with names := p.names.insert n}
  | .app f a | .lam _ f a _ | .forallE _ f a _ => return scan a (scan f p)
  | .letE _ t v b _ => return scan b (scan v (scan t p))
  | .proj n _ a => return scan a {p with names := p.names.insert n}
  | .mdata _ a => return scan a p
  | _ => return p

/-- Every referenced constant or projection type in a declaration's type and body. -/
def usedNames (ci : ConstantInfo) : NameSet :=
  let part := scan ci.type {}
  match ci.value? true with
  | some body => (scan body part).names
  | none => part.names

private def courseConstant (env : Environment) (n : Name) : Bool := Id.run do
  let some i := env.getModuleIdxFor? n | return false
  return (`League).isPrefixOf env.header.modules[i.toNat]!.module

private structure Total where
  visited : NameSet := {}
  privateNodes : Nat := 0
  shared : List (String × Json) := []

private partial def charge (env : Environment) (added : NameSet) (n : Name) :
    StateT Total (Except String) Unit := do
  if (← get).visited.contains n then return
  let shared := courseConstant env n
  unless shared || added.contains n do return
  modify fun s => {s with visited := s.visited.insert n}
  let some ci := env.find? n | throw s!"missing linked declaration {n}"
  let some v := ci.value? true | throw s!"unsupported course dependency {n}"
  let (t, v) := (do return (← normalize ci.type, ← normalize v)).run' {}
  let p := scan v (scan t {})
  let weight := p.expressions.size
  if shared then
    modify fun s => {s with shared := (n.toString, toJson weight) :: s.shared}
  else
    modify fun s => {s with privateNodes := s.privateNodes + weight}
  for dep in p.names do charge env added dep

def measure (env : Environment) (added : NameSet) (root : Name) : Except String Json := do
  let (_, total) ← (charge env added root).run {}
  return Json.mkObj [("version", toJson 1), ("private_nodes", toJson total.privateNodes),
                     ("shared", Json.mkObj total.shared)]

end Golf.Footprint
