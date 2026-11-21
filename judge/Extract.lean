import League.Certificate
import Lean.Util.FoldConsts

/-! Runs only in the disposable candidate environment. Its output is untrusted. -/
open Lean Golf.Cert

structure Build where
  memo : ExprMap Nat := {}
  nodes : Array Node := #[]
  done : NameSet := {}
  items : Array Item := #[]

abbrev Builder := StateT Build (Except String)

partial def encode (e : Expr) : Builder Nat := do
  if let some i := (← get).memo[e]? then return i
  let v : Node ← match e with
    | .mdata _ a => return ← encode a
    | .bvar i => pure (.var i)
    | .sort u => pure (.sort (← U.pack u))
    | .const n us => pure (.const (.pack n) (← liftM (us.mapM U.pack : Except String (List U))))
    | .app a b => pure (.app (← encode a) (← encode b))
    | .lam _ a b _ => pure (.lam (← encode a) (← encode b))
    | .forallE _ a b _ => pure (.pi (← encode a) (← encode b))
    | .letE _ t v b _ => pure (.letE (← encode t) (← encode v) (← encode b))
    | .proj n i a => pure (.proj (.pack n) i (← encode a))
    | .lit (.natVal i) => pure (.natLit i)
    | .lit (.strVal s) => pure (.strLit s)
    | _ => throw "unresolved variable"
  let i := (← get).nodes.size
  modify fun s => {s with memo := s.memo.insert e i, nodes := s.nodes.push v}
  return i

partial def capture (inBase : Name → Bool) (env : Environment) (n : Name) : Builder Unit := do
  if inBase n || (← get).done.contains n then return
  modify fun s => {s with done := s.done.insert n}
  let some info := env.find? n | throw s!"missing {n}"
  let kind ← match info with
    | .thmInfo _ => pure "theorem"
    | .defnInfo v => if v.safety == .safe then pure "definition" else throw "unsafe helper"
    | .opaqueInfo v => if !v.isUnsafe then pure "opaque" else throw "unsafe helper"
    | _ => throw s!"unsupported helper {n}; use a theorem or nonrecursive definition over the course library"
  let some value := info.value? true | throw "missing proof"
  -- Ordinary constants and structure names in projections both matter.
  for e in #[info.type, value] do
    for dep in e.getUsedConstants do capture inBase env dep
  let item := { name := QName.pack n, params := info.levelParams.map QName.pack, kind,
                type := ← encode info.type, value := ← encode value : Item }
  modify fun s => {s with items := s.items.push item}

/-- Recover the selected archive import closure from the already-loaded Entry environment.
Many archive modules import all of Mathlib, so a second copy exceeds the sandbox budget. -/
private partial def importClosure (env : Environment) (todo : List Name) (seen : NameSet := {}) : NameSet :=
  match todo with
  | [] => seen
  | m :: rest => Id.run do
    if seen.contains m then return importClosure env rest seen
    let some idx := env.getModuleIdx? m | return importClosure env rest seen
    let imports := env.header.moduleData[idx]!.imports.toList.map (·.module)
    return importClosure env (imports ++ rest) (seen.insert m)

def main (args : List String) : IO Unit := do
  let (output, modules) ← match args with
    | [out] => pure (out, #[{module := `League.Course : Import}])
    | [out, mods] => pure (out, #[{module := `League.Course : Import}] ++
        ((mods.splitOn ",").map (fun m => {module := m.toName : Import})).toArray)
    | _ => throw <| IO.userError "expected output path and optional archive module"
  initSearchPath (← findSysroot)
  let env ← importModules #[{module := `Entry}] {}
  let inBase ← if args.length == 1 then do
      let base ← importModules modules {}
      pure base.contains
    else do
      let closure := importClosure env (modules.toList.map (·.module))
      pure fun n => (env.getModuleIdxFor? n).any fun idx => closure.contains env.header.modules[idx]!.module
  let (_, b) ← IO.ofExcept <| (capture inBase env `Entry.answer).run {}
  IO.FS.writeFile output (toJson ({nodes := b.nodes, items := b.items} : Certificate)).compress
