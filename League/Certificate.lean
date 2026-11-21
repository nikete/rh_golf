import Lean

/-! Data-only exchange between the untrusted elaborator and the clean kernel.
Expressions use earlier node indices. Binder labels and metadata have no kernel significance.
Numeric name components and universe levels must round-trip exactly. -/
namespace Golf.Cert
open Lean

inductive QName where
  | root
  | str (parent : QName) (s : String)
  | num (parent : QName) (i : Nat)
  deriving ToJson, FromJson, Inhabited

def QName.pack : Name → QName
  | .anonymous => .root
  | .str p s => .str (pack p) s
  | .num p i => .num (pack p) i

def QName.unpack : QName → Name
  | .root => .anonymous
  | .str p s => .str p.unpack s
  | .num p i => .num p.unpack i

inductive U where
  | zero
  | succ (v : U)
  | max (a b : U)
  | imax (a b : U)
  | param (n : QName)
  deriving ToJson, FromJson, Inhabited

def U.pack : Level → Except String U
  | .zero => return .zero
  | .succ v => return .succ (← pack v)
  | .max a b => return .max (← pack a) (← pack b)
  | .imax a b => return .imax (← pack a) (← pack b)
  | .param n => return .param (.pack n)
  | .mvar _ => throw "unresolved universe"

def U.unpack : U → Level
  | .zero => .zero
  | .succ v => .succ v.unpack
  | .max a b => .max a.unpack b.unpack
  | .imax a b => .imax a.unpack b.unpack
  | .param n => .param n.unpack

inductive Node where
  | var (i : Nat)
  | sort (u : U)
  | const (n : QName) (us : List U)
  | app (fn arg : Nat)
  | lam (ty body : Nat)
  | pi (ty body : Nat)
  | letE (ty val body : Nat)
  | proj (n : QName) (i val : Nat)
  | natLit (i : Nat)
  | strLit (s : String)
  deriving ToJson, FromJson, Inhabited

structure Item where
  name : QName
  params : List QName
  kind : String
  type : Nat
  value : Nat
  deriving ToJson, FromJson

structure Certificate where
  nodes : Array Node
  items : Array Item
  deriving ToJson, FromJson

end Golf.Cert
