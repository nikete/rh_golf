import League.Certificate
import League.Footprint

/-! Reconstruct and score the certificate without importing anything from the entrant.
The kernel checks every body against its declared type and the selected course target. -/
open Lean Golf.Cert

def decode (rename : Name → Name) (xs : Array Expr) (n : Node) : Except String Expr := do
  let atIndex (i : Nat) : Except String Expr := match xs[i]? with
    | some e => .ok e
    | none => .error "invalid or forward expression reference"
  match n with
  | .var i => return .bvar i
  | .sort u => return .sort u.unpack
  | .const c us => return .const (rename c.unpack) (us.map U.unpack)
  | .app f a => return .app (← atIndex f) (← atIndex a)
  | .lam t b => return .lam .anonymous (← atIndex t) (← atIndex b) .default
  | .pi t b => return .forallE .anonymous (← atIndex t) (← atIndex b) .default
  | .letE t v b => return .letE .anonymous (← atIndex t) (← atIndex v) (← atIndex b) false
  | .proj c i v => return .proj (rename c.unpack) i (← atIndex v)
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

def install (base : Environment) (cert : Certificate) (rename : Name → Name)
    (topType : Option Expr := none) : IO (Environment × NameSet) := do
  let mut xs := #[]
  for node in cert.nodes do xs := xs.push (← IO.ofExcept <| decode rename xs node)
  let mut env := base
  let mut added : NameSet := {}
  for row in cert.items do
    let original := row.name.unpack
    let n := rename original
    if n.isAnonymous || env.contains n then throw <| IO.userError "duplicate or reserved name"
    let some t := xs[row.type]? | throw <| IO.userError "missing type"
    let some v := xs[row.value]? | throw <| IO.userError "missing value"
    let t := if original == `Entry.answer then topType.getD t else t
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
  return (env, added)

private def nameParts : Name → List Json → List Json
  | .anonymous, acc => acc
  | .str p s, acc => nameParts p (.str s :: acc)
  | .num p i, acc => nameParts p (toJson i :: acc)

private def archiveRoots : List Name :=
  [`BuildAid, `CompanionTheory, `Development, `Formalism, `GroundTheory, `Lemmata,
   `Main, `PositivityTheory, `ReciprocityTheory, `Statements, `Supplements]

private def moduleOf (env : Environment) (n : Name) : Option Name := do
  let idx ← env.getModuleIdxFor? n
  return env.header.modules[idx.toNat]!.module

private def archiveName (target : String) : IO Name := do
  if !target.startsWith "[" then return target.toName
  let parts ← IO.ofExcept (Json.parse target >>= (·.getArr?))
  let mut name := Name.anonymous
  for part in parts do
    if let .str s := part then name := .str name s
    else name := .num name (← IO.ofExcept part.getNat?)
  return name

/-- Only examine the new part of the graph. Publication checks all boundary edges
against the checksum-bound archive graph, including paths back to the replaced body. -/
private partial def boundary (env : Environment) (added : NameSet) (pending : List Name)
    (seen deps : NameSet) : IO NameSet := do
  match pending with
  | [] => return deps
  | head :: tail =>
    if seen.contains head then return ← boundary env added tail seen deps
    let seen := seen.insert head
    let mod := moduleOf env head
    if added.contains head || mod.any (`League).isPrefixOf then
      let some ci := env.find? head | throw <| IO.userError s!"missing linked declaration {head}"
      return ← boundary env added ((Golf.Footprint.usedNames ci).toList ++ tail) seen deps
    if mod.any (fun m => archiveRoots.any (·.isPrefixOf m)) then
      return ← boundary env added tail seen (deps.insert head)
    return ← boundary env added tail seen deps

private def archiveScore (cert : Certificate) (moduleNames targetText : String) : IO Unit := do
  let target ← archiveName targetText
  let modules := (moduleNames.splitOn ",").map String.toName
  let some moduleName := modules.head? | throw <| IO.userError "missing archive module"
  let imports := #[{module := `League.Course : Import}] ++ (modules.map (fun n => {module := n : Import})).toArray
  let base ← importModules imports {}
  let some old := base.find? target | throw <| IO.userError "named archive declaration does not exist"
  unless moduleOf base target == some moduleName && archiveRoots.any (·.isPrefixOf moduleName) do
    throw <| IO.userError "declaration is outside the selected archive module"
  let isTheorem := match old with | .thmInfo _ => true | _ => false
  unless isTheorem || (match old with | .defnInfo v => v.safety == .safe
                                      | .opaqueInfo v => !v.isUnsafe | _ => false) do
    throw <| IO.userError "declaration has no independently replaceable safe body"
  let (original, added) ← install base cert id
  let some entry := original.find? `Entry.answer | throw <| IO.userError "missing Entry.answer"
  if entry.levelParams.length != old.levelParams.length then
    throw <| IO.userError "wrong number of universe parameters"
  let levels := entry.levelParams.map Level.param
  let expected := old.type.instantiateLevelParams old.levelParams levels
  unless Kernel.isDefEqGuarded original {} expected entry.type do
    throw <| IO.userError "wrong archive target type"
  let some value := entry.value? true | throw <| IO.userError "missing replacement body"
  if !isTheorem then
    let some orig := old.value? true | throw <| IO.userError "missing original body"
    unless Kernel.isDefEqGuarded original {} (orig.instantiateLevelParams old.levelParams levels) value do
      throw <| IO.userError "replacement definition changes computation"
  let root := `RHGolfImpact ++ target ++ `answer
  let rename := fun n => if n == `Entry.answer then root
                         else if added.contains n then `RHGolfImpact ++ target ++ `helpers ++ n else n
  let (linked, fresh) ← install base cert rename (some expected)
  let checkAxioms := fun (env : Environment) (n : Name) => do
    let axs ← Core.CoreM.toIO' (Lean.collectAxioms n)
      {fileName := "<archive judge>", fileMap := default} {env}
    unless axs.all ([`propext, `Classical.choice, `Quot.sound].contains ·) do
      throw <| IO.userError s!"disallowed axiom: {axs}"
    pure axs
  let axioms ← checkAxioms linked root
  if expected != entry.type then discard <| checkAxioms original `Entry.answer
  let footprint ← IO.ofExcept (Golf.Footprint.measure linked fresh root)
  let deps ← boundary linked fresh [root] {} {}
  if deps.contains target then throw <| IO.userError "replacement directly depends on its original"
  let seen := ((do visit original added entry.type; visit original added value).run {}).2
  IO.println (Json.mkObj [("nodes", toJson seen.exprs.size), ("helpers", toJson seen.helpers.size),
    ("axioms", toJson axioms), ("impact", footprint),
    ("archive_deps", toJson (deps.toList.map (fun n => nameParts n [])))]).compress

def main (args : List String) : IO Unit := do
  let (target, file, archiveModule) ← match args with
    | [t, f] => pure (t, f, none)
    | ["archive", m, t, f] => pure (t, f, some m)
    | _ => throw <| IO.userError "expected trusted target and certificate"
  initSearchPath (← findSysroot)
  let data ← IO.FS.readFile file
  if data.utf8ByteSize > 8 * 1024 * 1024 then throw <| IO.userError "certificate exceeds 8 MiB"
  let cert : Certificate ← IO.ofExcept <| Json.parse data >>= fromJson?
  if cert.nodes.size > 100000 || cert.items.size > 1000 then throw <| IO.userError "certificate limit"
  if let some m := archiveModule then return ← archiveScore cert m target
  let base ← importModules #[{module := `League.Course}] {}
  let (env, added) ← install base cert id
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
  -- All inserted helpers receive a separate namespace per hole. The original root type
  -- is used at the replacement boundary, even when Entry.answer used a reducible alias.
  let targetName := target.toName
  let root := if targetName == `Golf.Reflection then `Formalism.VW.rh_of_right
              else if targetName == `RiemannHypothesis then `riemannHypothesis
              else `RHGolfImpact ++ targetName ++ `answer
  let rename := fun n => if n == `Entry.answer then root
                         else if added.contains n then `RHGolfImpact ++ targetName ++ `helpers ++ n
                         else n
  let linkedType ← if targetName == `Golf.Reflection then
      match (base.find? targetName).bind (·.value? true) with
      | some t => pure t
      | none => throw (IO.userError "missing reflection interface")
    else pure expected
  let (linked, privateNames) ← install base cert rename (some linkedType)
  let footprint ← IO.ofExcept (Golf.Footprint.measure linked privateNames root)
  IO.println (Json.mkObj [("nodes", toJson seen.exprs.size),
    ("helpers", toJson seen.helpers.size), ("axioms", toJson axioms), ("impact", footprint)]).compress
