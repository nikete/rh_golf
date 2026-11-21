import SourceOverlayExport
import League.CertReplay

/-! The caller compiles the pinned archive and imports its original constants. Only the
exporter's lookup changes. References keep their original names and the old declaration's
kind, signature, universe parameter names and reducibility metadata are preserved. -/
namespace Golf.SourceBuild
open Lean Golf.Cert

private def replacementInfo (old : ConstantInfo) (body : Expr) : IO ConstantInfo := do
  match old with
  | .thmInfo v => return .thmInfo {v with value := body}
  | .defnInfo v =>
    unless v.safety == .safe do throw <| IO.userError "unsafe target definition"
    return .defnInfo {v with value := body}
  | .opaqueInfo v =>
    if v.isUnsafe then throw <| IO.userError "unsafe opaque target"
    return .opaqueInfo {v with value := body}
  | _ => throw <| IO.userError "unsupported replacement kind"

def link (base : Environment) (target : Name) (cert : Certificate) : IO (Environment × ConstantInfo) := do
  let some old := base.find? target | throw <| IO.userError "missing original declaration"
  let freshName := `RHGolfSource ++ target
  let added := cert.items.foldl (fun (s : NameSet) v => s.insert v.name.unpack) {}
  let rename := fun n => if added.contains n then freshName ++ n else n
  let (env, _) ← Golf.CertReplay.install base cert rename
  let some entry := env.find? (rename `Entry.answer) | throw <| IO.userError "missing Entry.answer"
  unless added.contains `Entry.answer && old.levelParams.length == entry.levelParams.length do
    throw <| IO.userError "certificate does not contain a matching declaration"
  let levels := old.levelParams.map Level.param
  let typ := entry.type.instantiateLevelParams entry.levelParams levels
  unless Kernel.isDefEqGuarded env {} old.type typ do throw <| IO.userError "changed target type"
  let some proof := entry.value? true | throw <| IO.userError "missing candidate body"
  let body := proof.instantiateLevelParams entry.levelParams levels
  if !old.isTheorem then
    let some original := old.value? true | throw <| IO.userError "missing original body"
    unless Kernel.isDefEqGuarded env {} original body do throw <| IO.userError "changed target computation"
  return (env, ← replacementInfo old body)

def write (env : Environment) (replacement : ConstantInfo) (path : System.FilePath)
    (primary : Name) (also : List Name) : IO Unit := do
  let stream ← IO.FS.Handle.mk path .write
  IO.withStdout (IO.FS.Stream.ofHandle stream) do
    let action : M Unit := do
      initState env
      dumpMetadata
      dumpConstant primary
      unless (← get).visitedConstants.contains replacement.name do
        throw <| IO.userError "replacement is unreachable from the ordinary RH root"
      for n in also do dumpConstant n
    StateT.run' (s := {}) <| ReaderT.run (r := {env, replacement := some replacement}) action
  stream.flush

end Golf.SourceBuild

open Lean Golf.Cert

def main (args : List String) : IO Unit := do
  let [mods, nameJson, input, output] := args | throw <| IO.userError "expected modules, name, certificate, output"
  initSearchPath (← findSysroot)
  let text ← IO.FS.readFile input
  unless text.utf8ByteSize ≤ 8 * 1024 * 1024 do throw <| IO.userError "certificate size limit"
  let cert : Certificate ← IO.ofExcept (Json.parse text >>= fromJson?)
  unless cert.nodes.size ≤ 100000 && cert.items.size ≤ 1000 do throw <| IO.userError "certificate size limit"
  let parts ← IO.ofExcept (Json.parse nameJson >>= (·.getArr?))
  let mut target : Name := .anonymous
  for part in parts do
    target ← match part with
      | .str s => pure (.str target s)
      | _ => do pure (.num target (← IO.ofExcept part.getNat?))
  let imports := (["League.Course", "Main"] ++ (mods.splitOn ",").filter (!·.isEmpty)).eraseDups
  let env ← importModules (imports.map (fun m => {module := m.toName : Import})).toArray {}
  let (linked, replacement) ← Golf.SourceBuild.link env target cert
  Golf.SourceBuild.write linked replacement output `riemannHypothesis
    [`riemannZeta_eq_zero_re, `LFunction_ne_zero_of_half_lt_re,
     `LFunction_eq_zero_re, `LFunction_eq_zero_re_of_isPrimitive]
