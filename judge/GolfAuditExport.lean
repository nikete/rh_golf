import Export

/-! The exporter runs only in the judge. Its input is an environment reconstructed from
the inert certificate and the pinned course. The candidate cannot supply an environment. -/
namespace Golf.Audit
open Lean

structure Paths where
  solution : System.FilePath
  challenge : System.FilePath

-- The stock comparator validates these primitive declarations even on tiny proofs.
private def comparatorPrimitives : List Name :=
  ((include_str "audit/primitives.txt").splitOn "\n").filterMap fun line =>
    if line.isEmpty then none else some line.toName

private def write (file : System.FilePath) (env : Environment) (act : M Unit) : IO Unit := do
  let h ← IO.FS.Handle.mk file .write
  IO.withStdout (IO.FS.Stream.ofHandle h) <| M.run env do
    initState env
    dumpMetadata
    act
    for primitive in comparatorPrimitives do dumpConstant primitive
  h.flush

private def dumpDeps (e : Expr) : M Unit := do
  for c in e.getUsedConstants do dumpConstant c

/-- The fixed public goal is emitted from the clean base without a proof. Only
declared dependencies of the pinned type enter the challenge stream. -/
private def challenge (file : System.FilePath) (env : Environment) (n : Name)
    (type : Expr) (params : List Name) (oldDef : Option ConstantInfo) : IO Unit := do
  if let some info := oldDef then
    let some body := info.value? true | throw <| IO.userError "missing pinned definition"
    let body := body.instantiateLevelParams info.levelParams (params.map Level.param)
    let cv : ConstantVal := {name := n, type, levelParams := params}
    let decl ← match info with
      | .defnInfo d => pure <| Declaration.defnDecl {cv with value := body, safety := d.safety, hints := d.hints}
      | .opaqueInfo d => pure <| Declaration.opaqueDecl {cv with value := body, isUnsafe := d.isUnsafe}
      | _ => throw <| IO.userError "unexpected computational declaration"
    let .ok trusted := env.addDeclCore 150000000 8192 decl none
      | throw <| IO.userError "could not recreate pinned computational challenge"
    return ← write file trusted (dumpConstant n)
  -- Comparator expects a theorem of the right type with a sorry placeholder in
  -- the independent challenge. The solution's axiom policy forbids this axiom.
  let placeholder := mkApp2 (mkConst `sorryAx [.zero]) type (mkConst `Bool.false)
  write file env do
    dumpDeps type
    dumpDeps placeholder
    let name ← dumpName n
    let levels ← dumpUparams params
    let typ ← dumpExpr type
    let value ← dumpExpr placeholder
    if (← get).visitedConstants.contains n then throw <| IO.userError "cyclic challenge"
    IO.println (Json.mkObj [("thm", Json.mkObj [("name", name),
      ("levelParams", levels), ("type", typ), ("value", value), ("all", ← dumpNames [n])])]).compress

/-- In an archive-module attempt the name riemannHypothesis already belongs to
the original theorem. Emit the *new body* at that name in the independent stream,
rejecting a path that would reintroduce the original implementation. -/
private def dumpRootAs (env : Environment) (source target : Name) : M Unit := do
  let some declaration := env.find? source | throw <| IO.userError "missing replacement root"
  let some body := declaration.value? true | throw <| IO.userError "missing replacement body"
  dumpDeps declaration.type
  dumpDeps body
  let typ ← dumpExpr declaration.type
  let value ← dumpExpr body
  if (← get).visitedConstants.contains target then
    throw <| IO.userError "the replacement closure contains the original RH theorem"
  IO.println (Json.mkObj [("thm", Json.mkObj [("name", ← dumpName target),
    ("levelParams", ← dumpUparams declaration.levelParams), ("type", typ),
    ("value", value), ("all", ← dumpNames [target])])]).compress

/-- A type-checkable conversion obligation. Its identity body requires P oldBody
and P newBody to be convertible for an arbitrary predicate P, including for opaque definitions. -/
private def conversionWitness (env : Environment) (root : Name) (oldBody : Expr) :
    IO (Environment × Name) := do
  let some ci := env.find? root | throw <| IO.userError "missing replacement"
  let some newBody := ci.value? true | throw <| IO.userError "missing replacement value"
  let predType := Expr.forallE .anonymous ci.type (.sort .zero) .default
  let hypType := mkApp (.bvar 0) oldBody
  let goalType := mkApp (.bvar 1) newBody
  let name := root ++ `conversion
  let type := Expr.forallE `P predType (.forallE `h hypType goalType .default) .default
  let value := Expr.lam `P predType (.lam `h hypType (.bvar 0) .default) .default
  let d := Declaration.thmDecl {name, type, value, levelParams := ci.levelParams}
  let .ok checked := env.addDeclCore 150000000 8192 d none
    | throw <| IO.userError "could not construct the independent conversion obligation"
  return (checked, name)

def emit (paths : Paths) (base linked : Environment) (root : Name) (wholeRH : Bool)
    (pinnedType : Expr) (params : List Name) (oldDef : Option ConstantInfo := none) : IO Name := do
  let subject := if wholeRH then `riemannHypothesis else root
  let expected := if wholeRH then mkConst `RiemannHypothesis else pinnedType
  challenge paths.challenge base subject expected params oldDef
  let oldBody := oldDef.bind fun d =>
    (d.value? true).map (·.instantiateLevelParams d.levelParams (params.map Level.param))
  let (env, obligation) ← match oldBody with
    | none => pure (linked, none)
    | some old =>
      let (env, witness) ← conversionWitness linked root old
      pure (env, some witness)
  write paths.solution env do
    if oldDef.isSome then dumpConstant root else dumpRootAs env root subject
    if let some n := obligation then dumpConstant n
  return subject

end Golf.Audit
