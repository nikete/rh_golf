import Mathlib.NumberTheory.LSeries.RiemannZeta
import Mathlib.NumberTheory.ArithmeticFunction.VonMangoldt
import Mathlib.NumberTheory.Harmonic.EulerMascheroni

/-! The propositions in season 1. This module contains no solutions. -/
namespace Golf

/-- The quantifier step in the localized Landau argument. -/
def WindowLogic : Prop :=
  ∀ (I : Type) (later : I → I → Prop) (zero : Prop) (good bad : I → Prop),
    (∀ k, ∃ y, later k y ∧ good y) →
    (zero → ∃ k, ∀ y, later k y → bad y) →
    (∀ y, good y → bad y → False) → ¬zero

/-- The classical final deduction, stated for Mathlib's actual zeta function. -/
def Reflection : Prop :=
  (∀ s : ℂ, 1 / 2 < s.re → s ≠ 1 → riemannZeta s ≠ 0) → RiemannHypothesis

/-- The archive's centered ramp sum specialized to the unit character. -/
noncomputable def centered (y : ℝ) : ℝ :=
  (∑ n ∈ Finset.range (⌊y⌋₊ + 1),
    (ArithmeticFunction.vonMangoldt n : ℂ) * (1 : ℂ) * (max (y / n - 1) 0 : ℝ)).re
    - y * Real.log y + (1 + Real.eulerMascheroniConstant) * y

def Windows : Prop :=
  ∀ θ : ℝ, 1 / 2 < θ → θ < 1 → ∃ C : ℝ,
    ∀ cutoff : ℝ, ∃ Y : ℝ, cutoff ≤ Y ∧
      ∀ y ∈ Set.Icc Y (Y ^ (3 / 2 : ℝ)), centered y ≤ C * y ^ θ

def PrimeWindow : Prop := Windows → RiemannHypothesis

end Golf
