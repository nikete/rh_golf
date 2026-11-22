-- archive-module: Formalism.ZeroFreeRegion.ZetaLogDerivativeBounds.ThreeFourOne
-- archive-import: Formalism.LandauZeroFreeBounds.ExceptionalZeroBounds.Positivity
namespace Formalism.ZF

open Formalism.ZeroFreeDirichlet

/-- The three-height Mertens inequality is the modulus-one case of character positivity. -/
theorem _root_.Entry.answer : ThreeFourOne := by
  intro σ t hσ
  simpa [negLD] using (negLogDerivPositivity 1 σ hσ).1 1 t

end Formalism.ZF
