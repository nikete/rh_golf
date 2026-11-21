import League.Certificate

namespace Golf.CertReplay
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

end Golf.CertReplay
