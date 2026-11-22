-- archive-module: Development.AbelianVarietyTheory.Proofs.HomogeneousIdeals.DiagZEqNegAddY
import Lean
import Lean.Meta.Sym.Arith.ToExpr
import Lean.Data.RArray
open Lean Meta Elab Tactic
namespace SmallCert

private partial def reflect (e : Expr) : StateRefT (Array Expr) MetaM Lean.Grind.CommRing.Expr := do
  let e := e.consumeMData
  match_expr e with
  | HAdd.hAdd _ _ _ _ a b => return .add (← reflect a) (← reflect b)
  | HSub.hSub _ _ _ _ a b => return .sub (← reflect a) (← reflect b)
  | HMul.hMul _ _ _ _ a b => return .mul (← reflect a) (← reflect b)
  | Neg.neg _ _ a => return .neg (← reflect a)
  | HPow.hPow _ _ _ _ a k =>
    if let some n ← getNatValue? k then return .pow (← reflect a) n
  | OfNat.ofNat _ k _ =>
    if let some n ← getNatValue? k then return .num n
  | _ => pure ()
  let vars ← get
  for h : i in [:vars.size] do
    if ← isDefEq vars[i] e then return .var i
  modify (·.push e)
  return .var vars.size

elab "cert_ring" : tactic => withMainContext do
  let goal ← getMainGoal
  let_expr Eq ty a b ← (← goal.getType) | throwError "expected equality"
  let ((a', b'), vars) ← (do return (← reflect a, ← reflect b)).run #[]
  let u ← getLevel ty
  let .succ u := u | throwError "expected Type"
  let inst ← synthInstance (mkApp (mkConst ``Lean.Grind.CommRing [u]) ty)
  if h : 0 < vars.size then
    let ctx ← Lean.RArray.toExpr ty id (Lean.RArray.ofFn (vars[·]) h)
    let pf := mkApp6 (mkConst ``Lean.Grind.CommRing.Expr.eq_of_toPoly_eq [u]) ty inst ctx (toExpr a') (toExpr b') eagerReflBoolTrue
    goal.assign pf
    replaceMainGoal []
  else throwError "expected variables"
end SmallCert

open GlobalTheory.AddLaw WeierstrassCurve WeierstrassCurve.Projective
set_option maxRecDepth 24000 in
theorem Entry.answer : type_of% @GlobalTheory.AddLaw.diagZ_self := by
  intro R _ W P hP
  linear_combination (norm := (simp only [diagZ, dblZ, negY]; cert_ring))
    (-3 * W.a₁ * P 0 - 6 * P 1 - 3 * W.a₃ * P 2) * (sub_eq_zero.mpr <| (equation_iff _).mp hP)
