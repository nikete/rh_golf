-- archive-module: Development.WeilBound.RepresentationTheoryGL.ResidualSpectrum.ExponentialNegativity.NormalisedExistence.ExistsNormed
-- Adapted from Fortytwo, Osgood001/riemann-hypothesis PR #19 (a2e6aed);
-- earlier attempts include Vladyslav Larin / Fortytwo #103322, Mikko Nyman
-- et al. #103701, and Larin #104025.
open NumberField MeasureTheory Measure GlobalTheory CuspRep GroundTheory Global Automorphic AutomorphicForm Reduction PositivityTheory Rg Rs Affgl CT An Real InfinitePlace RingHom RingEquiv IsTotallyComplex IdeleGroup UnitaryBC

set_option maxHeartbeats 4000000 in
theorem Entry.answer : type_of% @PositivityTheory.Rg.Rs.dict_holds := by
  repeat intro
  repeat' constructor
  rotate_right
  · intro _ hφ
    intros
    -- The standard fundamental domain has volume one for the unipotent measure.
    unfold ctn IsCT ct
    rw [← BorelSpace.measurable_eq]
    simp [measureReal_def, unipMeasure_unipFundamentalDomain]
    refine ⟨⟨_, inferInstance, _, isAddFundamentalDomain_unipFundamentalDomain, by
      unfold constantTerm
      congr!
      aesop⟩, ?_⟩
    rintro F μ hμ 𝓕 h𝓕 rfl
    use addHaarScalarFactor μ (unipMeasure ..)
    constructor
    · exact_mod_cast (addHaarScalarFactor_pos_of_isAddHaarMeasure ..).ne'
    ext1
    rw [constantTerm_eq_setIntegral hφ.1 (h𝓕.mono $ absolutelyContinuous_isAddHaarMeasure ..)]
    nth_rw 1 [isAddLeftInvariant_eq_smul μ (unipMeasure ..)]
    simp
    congr!
    aesop
  rotate_right
  unfold latticeGL lat
  congr 2
  all_goals
    intros
    symm
    -- Compare infinite and finite projections for all three torus and lattice goals.
    apply ga_ext
    · erw [pInf_infGL]
      ext i j w
      by_cases i = j <;> simp_all [aR, tor, aInf]
      erw [comp_apply, coe_fst, piCongrRight_apply]
      simp_all [← coe_infiniteProj, infiniteProj_posIdele, posRealToUnits, posRealElem, ← not_isComplex_iff_isReal, isComplex, sqrt_sq_eq_abs, expU, apply_ite, ← exp_half]
    · erw [pFin_infGL]
      apply prodEquiv_diagUnits_posIdele_snd
