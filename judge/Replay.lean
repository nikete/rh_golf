import League.Certificate

/-! Reconstruct and score the certificate without importing anything from the entrant.
The kernel checks every body against its declared type and the selected course target. -/
open Lean Golf.Cert

def decode (xs : Array Expr) (n : Node) : Except String Expr := do
  let atIndex (i : Nat) : Except String Expr := match xs[i]? with
    | some e => .ok e
    | none => .error "invalid or forward expression reference"
  match n with
  | .var i => return .bvar i
  | .sort u => return .sort u.unpack
  | .const c us => return .const c.unpack (us.map U.unpack)
  | .app f a => return .app (← atIndex f) (← atIndex a)
  | .lam t b => return .lam .anonymous (← atIndex t) (← atIndex b) .default
  | .pi t b => return .forallE .anonymous (← atIndex t) (← atIndex b) .default
  | .letE t v b => return .letE .anonymous (← atIndex t) (← atIndex v) (← atIndex b) false
  | .proj c i v => return .proj c.unpack i (← atIndex v)
  | .natLit i => return .lit (.natVal i)
  | .strLit s => return .lit (.strVal s)

structure Seen where
  exprs : ExprSet := {}
  helpers : NameSet := {}

/-- Structural DAG cardinality of the proof and all reachable submitted helper types and bodies.
The fixed course and Mathlib are the common library. Metadata and binder labels cost zero. -/
partial def visit (env : Environment) (added : NameSet) (e : Expr) : StateM Seen Unit := do
  if (← get).exprs.contains e then return
  modify fun s => {s with exprs := s.exprs.insert e}
  let child := visit env added
  match e with
  | .const n _ =>
    if added.contains n && !(← get).helpers.contains n then
      modify fun s => {s with helpers := s.helpers.insert n}
      if let some c := env.find? n then
        child c.type
        if let some v := c.value? true then child v
  | .app a b | .lam _ a b _ | .forallE _ a b _ => child a; child b
  | .letE _ t v b _ => child t; child v; child b
  | .proj _ _ a | .mdata _ a => child a
  | _ => pure ()

def main (args : List String) : IO Unit := do
  let [target, file] := args | throw <| IO.userError "expected trusted target and certificate"
  initSearchPath (← findSysroot)
  let data ← IO.FS.readFile file
  if data.utf8ByteSize > 8 * 1024 * 1024 then throw <| IO.userError "certificate exceeds 8 MiB"
  let cert : Certificate ← IO.ofExcept <| Json.parse data >>= fromJson?
  if cert.nodes.size > 100000 || cert.items.size > 1000 then throw <| IO.userError "certificate limit"
  let mut xs := #[]
  for node in cert.nodes do xs := xs.push (← IO.ofExcept <| decode xs node)
  let mut env ← importModules #[{module := `League.Course}] {}
  let mut added : NameSet := {}
  for row in cert.items do
    let n := row.name.unpack
    if n.isAnonymous || env.contains n then throw <| IO.userError "duplicate or reserved name"
    let some t := xs[row.type]? | throw <| IO.userError "missing type"
    let some v := xs[row.value]? | throw <| IO.userError "missing value"
    let cv : ConstantVal := {name := n, levelParams := row.params.map QName.unpack, type := t}
    let d : Declaration ← match row.kind with
      | "theorem" => pure <| .thmDecl {cv with value := v}
      | "definition" => pure <| .defnDecl {cv with value := v, safety := .safe, hints := .abbrev}
      | "opaque" => pure <| .opaqueDecl {cv with value := v, isUnsafe := false}
      | _ => throw <| IO.userError "unsupported declaration kind"
    match env.addDeclCore 150000000 8192 d none with
    | .error _ => throw <| IO.userError s!"kernel rejected {n}"
    | .ok env' => env := env'
    added := added.insert n
  let some (.thmInfo answer) := env.find? `Entry.answer | throw <| IO.userError "missing theorem Entry.answer"
  -- A fresh theorem with the locked type, using the supplied theorem only at universe level zero.
  let expected := mkConst (target.toName)
  let check : Declaration := .thmDecl {
    name := `Golf.CheckedEntry, type := expected, levelParams := [], value := mkConst `Entry.answer }
  let .ok checked := env.addDeclCore 150000000 8192 check none | throw <| IO.userError "wrong target"
  -- Count dependencies in the answer's claimed type as well. Entrants cannot hide work via defeq.
  let axioms ← Core.CoreM.toIO' (Lean.collectAxioms `Golf.CheckedEntry)
    {fileName := "<judge>", fileMap := default} {env := checked}
  let allowed := [`propext, `Classical.choice, `Quot.sound]
  unless axioms.all allowed.contains do throw <| IO.userError s!"disallowed axiom: {axioms}"
  let walk := do visit env added answer.type; visit env added answer.value
  let seen := (walk.run {}).2
  IO.println (Json.mkObj [("nodes", toJson seen.exprs.size),
    ("helpers", toJson seen.helpers.size), ("axioms", toJson axioms)]).compress
